"""
MewAct MCP Server v2.0
======================
Advanced desktop control with:
- Smart Screenshots (Windows UI Automation)
- Coordinate Normalization (0-1000 system)
- Image Optimization (1568px max)
- Smooth Mouse Animation (Bezier curves)
- HiDPI Auto-Scale Detection

Usage:
    python mew_mcp.py

Configure in claude_desktop_config.json:
{
    "mcpServers": {
        "mewact": {
            "command": "python",
            "args": ["C:/path/to/mew_mcp.py"]
        }
    }
}
"""

import sys
import os
import json
import base64
import io
import time
import math
import random
import ctypes

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: MCP library not installed. Run: pip install mcp")
    sys.exit(1)

import pyautogui
import mss
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from colorama import Fore, init

# Windows UI Automation for Smart Screenshots
try:
    from pywinauto import Desktop
    from pywinauto.controls.uiawrapper import UIAWrapper
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    print("[WARN] pywinauto not available - Smart Screenshots will use OCR only")

init(autoreset=True)

# Import MewAct components (without running main)
from mew import PerceptionEngine, ActionExecutor, LibraryManager, SessionManager

# --- CONSTANTS ---
MAX_IMAGE_EDGE = 1568  # Anthropic's recommended max
COORD_RANGE = 1000     # Normalized coordinate range (0-1000)
MOUSE_MOVE_DURATION = 0.3  # Seconds for smooth mouse movement

# --- MCP SERVER SETUP ---
mcp = FastMCP("MewAct Desktop v2")

# Global state
_perception = None
_lib_mgr = None
_executor = None
_session_mgr = None
_last_ui_elements = {}  # Cache for Smart Screenshots
_last_scale_factor = 1.0  # For coordinate translation
_screen_size = (1920, 1080)  # Will be auto-detected


def _get_components():
    """Lazy initialization of MewAct components."""
    global _perception, _lib_mgr, _executor, _session_mgr, _screen_size
    if _perception is None:
        _lib_mgr = LibraryManager()
        _perception = PerceptionEngine()
        _session_mgr = SessionManager()
        _executor = ActionExecutor(_lib_mgr, session_manager=_session_mgr)
        _executor.locals["PERCEPTION_ENGINE"] = _perception
        _executor.locals["session_manager"] = _session_mgr
        
        # Detect screen size
        _screen_size = pyautogui.size()
    return _perception, _lib_mgr, _executor, _session_mgr


# ==============================================================================
# PHASE 1 FEATURE 1: HiDPI Auto-Scale Detection
# ==============================================================================

def _get_dpi_scale() -> float:
    """Get Windows DPI scaling factor."""
    try:
        # Windows DPI awareness
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        
        # Get scale factor
        hdc = user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        user32.ReleaseDC(0, hdc)
        
        return dpi / 96.0  # 96 is standard DPI
    except:
        return 1.0


# ==============================================================================
# PHASE 1 FEATURE 2: Coordinate Normalization (0-1000 System)
# ==============================================================================

def _normalized_to_physical(x_norm: int, y_norm: int) -> tuple:
    """
    Convert normalized coordinates (0-1000) to physical pixels.
    
    Formula: X_pixel = (X_model / 1000) × W_display
    """
    global _screen_size, _last_scale_factor
    
    w, h = _screen_size
    
    # Apply scale factor if image was resized
    x_physical = int((x_norm / COORD_RANGE) * w * _last_scale_factor)
    y_physical = int((y_norm / COORD_RANGE) * h * _last_scale_factor)
    
    # Clamp to screen bounds
    x_physical = max(0, min(x_physical, w - 1))
    y_physical = max(0, min(y_physical, h - 1))
    
    return x_physical, y_physical


def _physical_to_normalized(x_phys: int, y_phys: int) -> tuple:
    """Convert physical pixels to normalized coordinates (0-1000)."""
    global _screen_size
    w, h = _screen_size
    
    x_norm = int((x_phys / w) * COORD_RANGE)
    y_norm = int((y_phys / h) * COORD_RANGE)
    
    return x_norm, y_norm


# ==============================================================================
# PHASE 1 FEATURE 3: Image Optimization Pipeline
# ==============================================================================

def _optimize_image(img: np.ndarray) -> tuple:
    """
    Resize image to max 1568px edge and compress to JPEG.
    Returns: (optimized_image_bytes, scale_factor)
    """
    global _last_scale_factor
    
    h, w = img.shape[:2]
    max_edge = max(w, h)
    
    if max_edge > MAX_IMAGE_EDGE:
        scale = MAX_IMAGE_EDGE / max_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        _last_scale_factor = 1 / scale  # Store for coordinate translation
    else:
        img_resized = img
        _last_scale_factor = 1.0
    
    # Convert to JPEG
    pil_img = Image.fromarray(cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB))
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=80)
    
    return buffer.getvalue(), _last_scale_factor


# ==============================================================================
# PHASE 1 FEATURE 4: Smooth Mouse Animation (Bezier Curves)
# ==============================================================================

def _bezier_point(t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple:
    """Calculate point on cubic Bezier curve at parameter t."""
    u = 1 - t
    x = u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1]
    return int(x), int(y)


def _smooth_move(x: int, y: int, duration: float = MOUSE_MOVE_DURATION):
    """
    Move mouse smoothly using Bezier curve with human-like variation.
    Avoids bot detection by simulating natural movement.
    """
    start_x, start_y = pyautogui.position()
    
    # Generate control points for smooth curve
    dx = x - start_x
    dy = y - start_y
    
    # Add randomness to control points for natural feel
    ctrl1 = (
        start_x + dx * 0.3 + random.randint(-20, 20),
        start_y + dy * 0.1 + random.randint(-20, 20)
    )
    ctrl2 = (
        start_x + dx * 0.7 + random.randint(-20, 20),
        start_y + dy * 0.9 + random.randint(-20, 20)
    )
    
    # Number of steps based on duration
    steps = max(10, int(duration * 60))  # ~60 FPS
    
    for i in range(steps + 1):
        t = i / steps
        # Ease-out timing for more natural deceleration
        t_eased = 1 - (1 - t) ** 2
        
        px, py = _bezier_point(t_eased, (start_x, start_y), ctrl1, ctrl2, (x, y))
        pyautogui.moveTo(px, py, _pause=False)
        time.sleep(duration / steps)


def _smooth_click(x: int, y: int, duration: float = MOUSE_MOVE_DURATION):
    """Move smoothly to position and click."""
    _smooth_move(x, y, duration)
    time.sleep(0.05 + random.uniform(0, 0.05))  # Small random delay
    pyautogui.click()


# ==============================================================================
# PHASE 1 FEATURE 5: Smart Screenshots with Windows UI Automation
# ==============================================================================

def _get_ui_elements_uia() -> list:
    """Get clickable UI elements using Windows UI Automation."""
    if not PYWINAUTO_AVAILABLE:
        return []
    
    elements = []
    try:
        desktop = Desktop(backend="uia")
        
        # Get windows
        for window in desktop.windows()[:5]:  # Limit to top 5 windows
            try:
                # Get interactive elements
                for ctrl in window.descendants(depth=3):
                    try:
                        rect = ctrl.rectangle()
                        if rect.width() > 5 and rect.height() > 5:
                            name = ctrl.window_text() or ""
                            ctrl_type = ctrl.friendly_class_name() or ""
                            
                            # Only include interactive elements
                            if ctrl_type in ['Button', 'Edit', 'CheckBox', 'RadioButton', 
                                            'ComboBox', 'ListItem', 'MenuItem', 'Link',
                                            'TabItem', 'TreeItem']:
                                elements.append({
                                    'text': name[:50] if name else ctrl_type,
                                    'x': rect.left + rect.width() // 2,
                                    'y': rect.top + rect.height() // 2,
                                    'type': ctrl_type,
                                    'clickable': True
                                })
                    except:
                        continue
            except:
                continue
    except Exception as e:
        print(f"[WARN] UI Automation error: {e}")
    
    return elements[:50]  # Limit elements


def _annotate_screenshot(img: np.ndarray, ui_elements: list) -> tuple:
    """
    Draw numbered labels on screenshot for Smart Screenshots.
    Returns: (annotated_image_bytes, element_mapping)
    """
    global _last_ui_elements
    
    # Optimize image first
    img_bytes, scale = _optimize_image(img)
    
    # Reload for annotation
    pil_img = Image.open(io.BytesIO(img_bytes))
    draw = ImageDraw.Draw(pil_img)
    
    # Use a small font
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()
    
    element_map = {}
    h_scale = pil_img.height / img.shape[0]
    w_scale = pil_img.width / img.shape[1]
    
    for i, el in enumerate(ui_elements[:30]):  # Limit to 30 elements
        orig_x, orig_y = el.get('x', 0), el.get('y', 0)
        
        # Scale coordinates to resized image
        x = int(orig_x * w_scale)
        y = int(orig_y * h_scale)
        
        text = el.get('text', '')
        el_type = el.get('type', 'unknown')
        
        # Draw red circle with number
        draw.ellipse([x-12, y-12, x+12, y+12], fill="red", outline="white")
        draw.text((x-6, y-8), str(i), fill="white", font=font)
        
        # Store physical coordinates (not scaled)
        element_map[i] = {
            "text": text, 
            "x": orig_x, 
            "y": orig_y,
            "type": el_type,
            "x_norm": int((orig_x / _screen_size[0]) * COORD_RANGE),
            "y_norm": int((orig_y / _screen_size[1]) * COORD_RANGE)
        }
    
    _last_ui_elements = element_map
    
    # Convert to base64 JPEG
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=80)
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return img_b64, element_map


# ==============================================================================
# MCP TOOLS
# ==============================================================================

@mcp.tool()
def capture_screen(annotate: bool = True, use_uia: bool = True) -> dict:
    """
    Capture screen with Smart Screenshots (numbered clickable elements).
    
    Args:
        annotate: If True, overlay numbered IDs on clickable elements
        use_uia: If True, use Windows UI Automation for better element detection
    
    Returns:
        dict with:
        - text: OCR content
        - elements: List of detected UI elements with IDs
        - image_base64: Annotated screenshot (if annotate=True)
        - scale_factor: Image resize factor for coordinate translation
        - hint: Usage instructions
    """
    perception, _, _, _ = _get_components()
    ui_data, text = perception.capture_and_scan()
    
    # Merge OCR elements with UI Automation elements
    if use_uia and PYWINAUTO_AVAILABLE:
        uia_elements = _get_ui_elements_uia()
        # Merge: UIA elements first (more reliable), then OCR
        all_elements = uia_elements + [el for el in ui_data if el not in uia_elements]
    else:
        all_elements = ui_data
    
    result = {
        "text": text[:4000],
        "element_count": len(all_elements),
        "elements": [
            {
                "id": i, 
                "text": el.get('text', '')[:50], 
                "x_norm": int((el.get('x', 0) / _screen_size[0]) * COORD_RANGE),
                "y_norm": int((el.get('y', 0) / _screen_size[1]) * COORD_RANGE),
                "type": el.get('type', 'ocr')
            } 
            for i, el in enumerate(all_elements[:30])
        ],
        "screen_size": {"width": _screen_size[0], "height": _screen_size[1]},
        "scale_factor": _last_scale_factor,
        "coordinate_system": "0-1000 normalized (use click_at_normalized)"
    }
    
    if annotate and perception.last_image is not None:
        img_b64, _ = _annotate_screenshot(perception.last_image, all_elements)
        result["image_base64"] = img_b64
        result["hint"] = "Use click_element(id) for numbered elements, or click_at_normalized(x, y) for coordinates"
    
    return result


@mcp.tool()
def click_element(element_id: int, smooth: bool = True) -> str:
    """
    Click on a detected UI element by its ID from last capture_screen.
    Uses smooth mouse animation to avoid bot detection.
    
    Args:
        element_id: The numbered ID shown on the annotated screenshot
        smooth: If True, use human-like smooth movement (default True)
    
    Returns:
        Status message with clicked coordinates
    """
    global _last_ui_elements
    
    if element_id not in _last_ui_elements:
        return f"Error: Element #{element_id} not found. Run capture_screen first."
    
    el = _last_ui_elements[element_id]
    x, y = el['x'], el['y']
    
    if smooth:
        _smooth_click(x, y)
    else:
        pyautogui.click(x, y)
    
    time.sleep(0.2)
    return f"Clicked element #{element_id} ('{el['text']}') at ({x}, {y}) [norm: {el.get('x_norm', '?')}, {el.get('y_norm', '?')}]"


@mcp.tool()
def click_at_normalized(x: int, y: int, smooth: bool = True) -> str:
    """
    Click at normalized coordinates (0-1000 range).
    
    The AI model can specify coordinates in a 0-1000 range for both axes,
    which will be automatically translated to physical screen pixels.
    
    Args:
        x: X coordinate in 0-1000 range
        y: Y coordinate in 0-1000 range
        smooth: If True, use human-like smooth movement
    
    Returns:
        Status message with physical coordinates
    """
    x_phys, y_phys = _normalized_to_physical(x, y)
    
    if smooth:
        _smooth_click(x_phys, y_phys)
    else:
        pyautogui.click(x_phys, y_phys)
    
    time.sleep(0.2)
    return f"Clicked at normalized ({x}, {y}) -> physical ({x_phys}, {y_phys})"


@mcp.tool()
def click_text(text_to_find: str, smooth: bool = True) -> str:
    """
    Find text on screen and click it with smooth mouse movement.
    
    Args:
        text_to_find: The text to search for and click
        smooth: If True, use human-like smooth movement
    
    Returns:
        Status message
    """
    perception, _, _, _ = _get_components()
    ui_data, _ = perception.capture_and_scan()
    
    # Find matching element
    text_lower = text_to_find.lower()
    for el in ui_data:
        if text_lower in el.get('text', '').lower():
            x, y = el['x'], el['y']
            if smooth:
                _smooth_click(x, y)
            else:
                pyautogui.click(x, y)
            time.sleep(0.2)
            return f"Clicked '{el['text']}' at ({x}, {y})"
    
    return f"Text '{text_to_find}' not found on screen"


@mcp.tool()
def type_text(text: str, press_enter: bool = False, human_like: bool = True) -> str:
    """
    Type text using the keyboard with optional human-like timing.
    
    Args:
        text: The text to type
        press_enter: If True, press Enter after typing
        human_like: If True, add slight random delays between keystrokes
    
    Returns:
        Status message
    """
    if human_like:
        for char in text:
            pyautogui.write(char, _pause=False)
            time.sleep(0.02 + random.uniform(0, 0.04))  # 20-60ms per char
    else:
        pyautogui.write(text, interval=0.02)
    
    if press_enter:
        time.sleep(0.1 + random.uniform(0, 0.1))
        pyautogui.press('enter')
    
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


@mcp.tool()
def press_key(key: str, hold_duration: float = 0) -> str:
    """
    Press a keyboard key or hotkey with optional hold duration.
    
    Args:
        key: Key name (e.g., 'enter', 'escape', 'ctrl+c', 'alt+tab')
        hold_duration: Seconds to hold key (0 for normal press)
    
    Returns:
        Status message
    """
    if '+' in key:
        parts = [k.strip() for k in key.split('+')]
        if hold_duration > 0:
            # Hold modifier keys
            for part in parts[:-1]:
                pyautogui.keyDown(part)
            time.sleep(hold_duration)
            pyautogui.press(parts[-1])
            for part in reversed(parts[:-1]):
                pyautogui.keyUp(part)
        else:
            pyautogui.hotkey(*parts)
    else:
        if hold_duration > 0:
            pyautogui.keyDown(key)
            time.sleep(hold_duration)
            pyautogui.keyUp(key)
        else:
            pyautogui.press(key)
    
    return f"Pressed: {key}" + (f" (held {hold_duration}s)" if hold_duration > 0 else "")


@mcp.tool()
def drag_drop(start_x: int, start_y: int, end_x: int, end_y: int, 
              normalized: bool = True, smooth: bool = True) -> str:
    """
    Perform drag and drop operation.
    
    Args:
        start_x: Start X coordinate
        start_y: Start Y coordinate
        end_x: End X coordinate
        end_y: End Y coordinate
        normalized: If True, coordinates are in 0-1000 range
        smooth: If True, use smooth movement
    
    Returns:
        Status message
    """
    if normalized:
        sx, sy = _normalized_to_physical(start_x, start_y)
        ex, ey = _normalized_to_physical(end_x, end_y)
    else:
        sx, sy = start_x, start_y
        ex, ey = end_x, end_y
    
    if smooth:
        _smooth_move(sx, sy)
        time.sleep(0.1)
        pyautogui.mouseDown()
        time.sleep(0.1)
        _smooth_move(ex, ey)
        time.sleep(0.1)
        pyautogui.mouseUp()
    else:
        pyautogui.moveTo(sx, sy)
        pyautogui.drag(ex - sx, ey - sy, duration=0.5)
    
    return f"Dragged from ({sx}, {sy}) to ({ex}, {ey})"


@mcp.tool()
def execute_command(command_id: int, variables: str = "") -> str:
    """
    Execute a command from the MewAct command library by ID.
    
    Args:
        command_id: The command ID (see list_commands)
        variables: Optional variables to pass (replaces __VAR__ in command)
    
    Returns:
        Status message
    """
    _, lib_mgr, executor, _ = _get_components()
    
    cmd = lib_mgr.get_command_by_id(command_id)
    if not cmd:
        return f"Command ID {command_id} not found"
    
    # Inject variables
    code = cmd.get('code', '')
    if '__VAR__' in code and variables:
        code = code.replace('__VAR__', variables)
    
    cmd_data = {"id": command_id, "args": variables}
    success = executor.execute(code, cmd_type=cmd.get('type', 'python'), cmd_data=cmd_data)
    
    return f"Command {command_id} executed: {'Success' if success else 'Failed'}"


@mcp.tool()
def smart_action(action: str, target: str = "", smooth: bool = True) -> dict:
    """
    Perform an intelligent action in one call (1-Call Workflow).
    Captures screen, finds target, and executes action - all in one tool call.
    
    Args:
        action: One of 'click', 'type', 'wait_for', 'double_click', 'right_click'
        target: Text to find/interact with, or text to type
        smooth: If True, use human-like smooth movement
    
    Returns:
        dict with status and details
    """
    perception, _, _, _ = _get_components()
    
    if action == "click":
        ui_data, _ = perception.capture_and_scan()
        target_lower = target.lower()
        for el in ui_data:
            if target_lower in el.get('text', '').lower():
                x, y = el['x'], el['y']
                if smooth:
                    _smooth_click(x, y)
                else:
                    pyautogui.click(x, y)
                return {"status": "clicked", "target": el['text'], "x": x, "y": y}
        return {"status": "not_found", "target": target}
    
    elif action == "double_click":
        ui_data, _ = perception.capture_and_scan()
        target_lower = target.lower()
        for el in ui_data:
            if target_lower in el.get('text', '').lower():
                x, y = el['x'], el['y']
                if smooth:
                    _smooth_move(x, y)
                pyautogui.doubleClick(x, y)
                return {"status": "double_clicked", "target": el['text'], "x": x, "y": y}
        return {"status": "not_found", "target": target}
    
    elif action == "right_click":
        ui_data, _ = perception.capture_and_scan()
        target_lower = target.lower()
        for el in ui_data:
            if target_lower in el.get('text', '').lower():
                x, y = el['x'], el['y']
                if smooth:
                    _smooth_move(x, y)
                pyautogui.rightClick(x, y)
                return {"status": "right_clicked", "target": el['text'], "x": x, "y": y}
        return {"status": "not_found", "target": target}
    
    elif action == "type":
        for char in target:
            pyautogui.write(char, _pause=False)
            time.sleep(0.02 + random.uniform(0, 0.04))
        return {"status": "typed", "text": target}
    
    elif action == "wait_for":
        # Wait up to 5 seconds for text to appear
        for _ in range(10):
            _, text = perception.capture_and_scan()
            if target.lower() in text.lower():
                return {"status": "found", "target": target}
            time.sleep(0.5)
        return {"status": "timeout", "target": target}
    
    return {"status": "error", "message": f"Unknown action: {action}. Use: click, type, wait_for, double_click, right_click"}


@mcp.tool()
def list_commands(filter_text: str = "", category: str = "") -> list:
    """
    List available commands from the 400+ command library.
    
    Args:
        filter_text: Optional text to filter commands by name/description
        category: Optional category filter (e.g., 'browser', 'office', 'system')
    
    Returns:
        List of command summaries with IDs
    """
    _, lib_mgr, _, _ = _get_components()
    
    commands = []
    for name, cmd in lib_mgr.commands.items():
        # Filter by text
        if filter_text and filter_text.lower() not in name.lower() and filter_text.lower() not in cmd.get('description', '').lower():
            continue
        # Filter by category (based on command name prefix)
        if category:
            if category.lower() not in name.lower():
                continue
        
        commands.append({
            "id": cmd.get('id'),
            "name": name,
            "description": cmd.get('description', '')[:100],
            "type": cmd.get('type', 'unknown')
        })
    
    return commands[:50]  # Limit to 50 results


@mcp.tool()
def get_screen_info() -> dict:
    """
    Get information about the screen and coordinate system.
    
    Returns:
        dict with screen size, DPI scale, and coordinate system info
    """
    _get_components()  # Ensure screen size is detected
    dpi_scale = _get_dpi_scale()
    
    return {
        "screen_size": {"width": _screen_size[0], "height": _screen_size[1]},
        "dpi_scale": dpi_scale,
        "coordinate_system": {
            "range": "0-1000 for both axes",
            "example": "click_at_normalized(500, 500) clicks center of screen",
            "translation": f"1 normalized unit = {_screen_size[0]/COORD_RANGE:.2f}px horizontal, {_screen_size[1]/COORD_RANGE:.2f}px vertical"
        },
        "image_optimization": {
            "max_edge": MAX_IMAGE_EDGE,
            "current_scale_factor": _last_scale_factor
        },
        "features": {
            "smart_screenshots": PYWINAUTO_AVAILABLE,
            "smooth_mouse": True,
            "hidpi_aware": True
        }
    }


# --- ENTRY POINT ---
if __name__ == "__main__":
    print(f"{Fore.GREEN}[MCP] MewAct Desktop Server v2.0 Starting...")
    print(f"{Fore.CYAN}[MCP] Phase 1 Features Enabled:")
    print(f"{Fore.CYAN}  - Smart Screenshots (UIA): {PYWINAUTO_AVAILABLE}")
    print(f"{Fore.CYAN}  - Coordinate Normalization: 0-{COORD_RANGE} system")
    print(f"{Fore.CYAN}  - Image Optimization: Max {MAX_IMAGE_EDGE}px edge")
    print(f"{Fore.CYAN}  - Smooth Mouse Animation: Bezier curves")
    print(f"{Fore.CYAN}  - HiDPI Detection: Scale = {_get_dpi_scale()}")
    print(f"{Fore.YELLOW}[MCP] Available tools: capture_screen, click_element, click_at_normalized, click_text, type_text, press_key, drag_drop, execute_command, smart_action, list_commands, get_screen_info")
    mcp.run()
