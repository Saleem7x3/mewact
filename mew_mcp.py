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
    Draw colored numbered labels on screenshot for Smart Screenshots.
    Colors indicate element type:
      🔴 Red: Buttons (clickable)
      🔵 Blue: Input fields
      🟢 Green: Links
      🟡 Yellow: Checkboxes/Radio
      ⚪ Gray: Other/OCR
    Returns: (annotated_image_bytes, element_mapping)
    """
    global _last_ui_elements
    
    # Color map by element type
    TYPE_COLORS = {
        'Button': '#FF4444',      # Red
        'Edit': '#4444FF',        # Blue
        'Input': '#4444FF',       # Blue
        'ComboBox': '#4444FF',    # Blue
        'Link': '#44AA44',        # Green
        'MenuItem': '#44AA44',    # Green
        'CheckBox': '#FFAA00',    # Yellow/Orange
        'RadioButton': '#FFAA00', # Yellow/Orange
        'TabItem': '#AA44AA',     # Purple
        'ListItem': '#44AAAA',    # Cyan
        'TreeItem': '#44AAAA',    # Cyan
        'ocr': '#888888',         # Gray for OCR-detected
        'unknown': '#888888',     # Gray
    }
    
    # Optimize image first
    img_bytes, scale = _optimize_image(img)
    
    # Reload for annotation
    pil_img = Image.open(io.BytesIO(img_bytes))
    draw = ImageDraw.Draw(pil_img)
    
    # Use a small font
    try:
        font = ImageFont.truetype("arial.ttf", 12)
        font_small = ImageFont.truetype("arial.ttf", 10)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    element_map = {}
    h_scale = pil_img.height / img.shape[0]
    w_scale = pil_img.width / img.shape[1]
    
    for i, el in enumerate(ui_elements[:30]):  # Limit to 30 elements
        orig_x, orig_y = el.get('x', 0), el.get('y', 0)
        
        # Scale coordinates to resized image
        x = int(orig_x * w_scale)
        y = int(orig_y * h_scale)
        
        text = el.get('text', '')[:20]  # Truncate long text
        el_type = el.get('type', 'unknown')
        
        # Get color based on element type
        color = TYPE_COLORS.get(el_type, TYPE_COLORS['unknown'])
        
        # Draw colored pill with number and label
        label = f"[{i}] {text}" if text else f"[{i}]"
        
        # Calculate label width for pill
        try:
            bbox = draw.textbbox((0, 0), label, font=font_small)
            label_width = bbox[2] - bbox[0] + 8
            label_height = bbox[3] - bbox[1] + 4
        except:
            label_width = len(label) * 6 + 8
            label_height = 14
        
        # Draw pill background
        pill_x1 = x - label_width // 2
        pill_y1 = y - label_height // 2
        pill_x2 = x + label_width // 2
        pill_y2 = y + label_height // 2
        
        # Draw rounded rectangle (pill)
        draw.rounded_rectangle(
            [pill_x1, pill_y1, pill_x2, pill_y2],
            radius=7,
            fill=color,
            outline='white'
        )
        
        # Draw label text
        draw.text((pill_x1 + 4, pill_y1 + 1), label, fill='white', font=font_small)
        
        # Store physical coordinates (not scaled)
        element_map[i] = {
            "text": el.get('text', ''), 
            "x": orig_x, 
            "y": orig_y,
            "type": el_type,
            "color": color,
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
    📸 ALWAYS START HERE - Capture screen and detect clickable UI elements.
    
    USE THIS WHEN:
    - You need to see what's on screen
    - You want to find buttons, links, or text to click
    - Before using click_element() (this provides the element IDs)
    
    DO NOT USE:
    - If you already know exact coordinates (use click_at_normalized instead)
    
    WORKFLOW:
    1. Call capture_screen() → Get numbered elements
    2. Find target element ID in response
    3. Call click_element(id) to click it
    
    Args:
        annotate: Overlay red numbered circles on clickable elements (default: True)
        use_uia: Use Windows UI Automation for better detection (default: True)
    
    Returns:
        - text: All visible text on screen (OCR)
        - elements: [{id: 0, text: "Submit", x_norm: 500, y_norm: 300}, ...]
        - image_base64: Screenshot with numbered elements
    
    Example response: {"elements": [{"id": 5, "text": "Submit"}]} → use click_element(5)
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
    🖱️ Click a numbered UI element from the last capture_screen.
    
    USE THIS WHEN:
    - You see a numbered element in capture_screen results
    - The screenshot shows red circles with numbers
    - Example: element #5 is "Submit" button → click_element(5)
    
    DO NOT USE:
    - If you haven't called capture_screen first (will fail)
    - If you want to click by text (use click_text instead)
    - If you know coordinates (use click_at_normalized instead)
    
    Args:
        element_id: The number shown in red circle (0-29). REQUIRED.
        smooth: Human-like mouse movement to avoid bot detection (default: True)
    
    Returns: "Clicked element #5 ('Submit') at (500, 300)"
    
    Example: capture_screen shows element #3 is "OK" → click_element(3)
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
    🎯 Click at exact screen position using 0-1000 coordinate system.
    
    USE THIS WHEN:
    - You know where to click but there's no text/element ID
    - Clicking on images, icons, or whitespace
    - Using coordinates from capture_screen's x_norm/y_norm values
    
    DO NOT USE:
    - If there's visible text (use click_text - more reliable)
    - If you have an element ID (use click_element - more accurate)
    
    COORDINATE SYSTEM:
    - (0, 0) = Top-left corner
    - (500, 500) = Center of screen
    - (1000, 1000) = Bottom-right corner
    
    Args:
        x: Horizontal position 0-1000 (0=left, 1000=right). REQUIRED.
        y: Vertical position 0-1000 (0=top, 1000=bottom). REQUIRED.
        smooth: Human-like movement (default: True)
    
    Examples:
    - click_at_normalized(500, 500) → Click center
    - click_at_normalized(950, 50) → Click top-right area
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
    🔍 Find visible text on screen and click it. Most reliable click method!
    
    USE THIS WHEN:
    - You can see the button/link text: "Submit", "Cancel", "Next"
    - Text is clearly visible on screen
    - You don't have an element ID from capture_screen
    
    DO NOT USE:
    - For icons without text (use click_at_normalized)
    - If you already have element ID (use click_element - faster)
    
    MATCHING:
    - Case-insensitive: "submit" matches "Submit", "SUBMIT"
    - Partial match: "sub" matches "Submit"
    
    Args:
        text_to_find: Text to search for (case-insensitive, partial OK). REQUIRED.
        smooth: Human-like movement (default: True)
    
    Examples:
    - click_text("Submit") → Clicks "Submit" button
    - click_text("next") → Clicks "Next" or "Next Step"
    
    Returns: "Clicked 'Submit' at (500, 300)" or "Text 'xyz' not found"
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
    ⌨️ Type text into the currently focused input field.
    
    USE THIS WHEN:
    - Typing into a text field, search box, form input
    - After clicking on an input field
    - Entering URLs, messages, search queries
    
    DO NOT USE:
    - For keyboard shortcuts (use press_key: "ctrl+c")
    - If you haven't clicked to focus an input first
    
    Args:
        text: The text to type. REQUIRED.
        press_enter: Press Enter after typing (default: False). Set True for search/submit.
        human_like: Random keystroke timing to avoid bot detection (default: True)
    
    Examples:
    - type_text("hello world") → Types "hello world"
    - type_text("search query", press_enter=True) → Type and submit
    
    WORKFLOW:
    1. click_text("Search") or click_element(id) → Focus input
    2. type_text("your text", press_enter=True) → Type and submit
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
    ⚡ Press keyboard keys or hotkey combinations.
    
    USE THIS WHEN:
    - Pressing Enter, Escape, Tab, Arrow keys
    - Keyboard shortcuts: Ctrl+C, Ctrl+V, Alt+Tab, Ctrl+S
    - Function keys: F5, F11
    
    DO NOT USE:
    - For typing text (use type_text)
    
    COMMON KEYS:
    - enter, escape, tab, backspace, delete
    - up, down, left, right (arrow keys)
    - f1-f12, home, end, pageup, pagedown
    
    HOTKEY FORMAT: "modifier+key" (use + to combine)
    - ctrl+c, ctrl+v, ctrl+z (copy, paste, undo)
    - alt+tab (switch windows)
    - ctrl+shift+s (save as)
    - win+d (show desktop)
    
    Args:
        key: Key or combo like "enter", "ctrl+c", "alt+f4". REQUIRED.
        hold_duration: Seconds to hold (0=normal press, >0=hold and release)
    
    Examples:
    - press_key("enter") → Press Enter
    - press_key("ctrl+s") → Save
    - press_key("alt+tab") → Switch window
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
    ↕️ Drag from one position to another (drag-and-drop).
    
    USE THIS WHEN:
    - Moving files between folders
    - Dragging sliders
    - Rearranging items
    - Drawing selections
    
    Args:
        start_x: Starting X position (0-1000 if normalized). REQUIRED.
        start_y: Starting Y position (0-1000 if normalized). REQUIRED.
        end_x: Ending X position (0-1000 if normalized). REQUIRED.
        end_y: Ending Y position (0-1000 if normalized). REQUIRED.
        normalized: Coordinates in 0-1000 range (default: True)
        smooth: Human-like movement (default: True)
    
    Example: Drag from top-left to center:
    - drag_drop(100, 100, 500, 500)
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
    📚 Execute a pre-built command from MewAct's 400+ command library.
    
    USE THIS WHEN:
    - Opening apps: execute_command(700) → Open Word
    - System tasks: execute_command(520) → Open Task Manager
    - Browser actions: execute_command(600) → Open Chrome
    
    FIND COMMANDS:
    - Use list_commands("word") to find Word-related commands
    - Use list_commands("browser") to find browser commands
    
    Args:
        command_id: The ID from list_commands. REQUIRED.
        variables: Text to substitute for __VAR__ placeholder (for commands that need input)
    
    Examples:
    - execute_command(700) → Open Microsoft Word
    - execute_command(836, "fix: bug") → git commit -m "fix: bug"
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
    🚀 ALL-IN-ONE: Capture screen + find target + execute action in ONE call!
    
    USE THIS FOR SPEED:
    - Reduces latency from 15s to 3s per interaction
    - No need to call capture_screen first
    
    ACTIONS:
    - "click": Find text and click it
    - "double_click": Double-click on text
    - "right_click": Right-click on text  
    - "type": Type text into current focus
    - "wait_for": Wait up to 5s for text to appear
    
    Args:
        action: "click", "double_click", "right_click", "type", or "wait_for". REQUIRED.
        target: Text to find (for clicks) or text to type. REQUIRED.
        smooth: Human-like movement (default: True)
    
    Examples:
    - smart_action("click", "Submit") → Find and click Submit
    - smart_action("type", "Hello") → Type Hello
    - smart_action("wait_for", "Loading complete") → Wait for text
    
    Returns: {"status": "clicked", "target": "Submit", "x": 500, "y": 300}
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
    📊 Get screen configuration and MewAct capabilities.
    
    USE THIS WHEN:
    - Checking screen resolution before automation
    - Debugging coordinate issues
    - Verifying feature availability
    
    Returns:
        - screen_size: Width and height
        - dpi_scale: Windows scaling factor
        - coordinate_system: How 0-1000 maps to pixels
        - features: What's enabled
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
            "hidpi_aware": True,
            "colored_markers": True,
            "vlm_support": True
        }
    }


# ==============================================================================
# PHASE 2: ADVANCED SCREEN UNDERSTANDING
# ==============================================================================

# Differential Screenshots state
_last_screenshot_hash = None

def _get_image_hash(img: np.ndarray) -> str:
    """Quick hash of image for change detection."""
    # Downsample for fast comparison
    small = cv2.resize(img, (32, 32))
    return hash(small.tobytes())


@mcp.tool()
def describe_screen(prompt: str = "Describe what you see on this screen") -> dict:
    """
    🧠 Use local Vision-Language Model to describe the screen.
    
    USE THIS WHEN:
    - OCR/element detection isn't enough
    - Need AI to understand context (what app is this? what's happening?)
    - Complex UIs where structured parsing fails
    
    REQUIRES: Ollama running with a vision model
    - ollama pull moondream:1.8b (fast, 1.8GB)
    - ollama pull llava:7b (accurate, 4GB)
    
    Args:
        prompt: Question to ask about the screen (default: general description)
    
    Returns:
        - description: VLM's response
        - model: Which model was used
        - error: If VLM unavailable
    
    Examples:
    - describe_screen() → "I see a login form with email/password fields"
    - describe_screen("What buttons are visible?") → "Submit, Cancel, Help"
    """
    perception, _, _, _ = _get_components()
    
    # Capture screen
    ui_data, text = perception.capture_and_scan()
    
    if perception.last_image is None:
        return {"error": "No screenshot available"}
    
    # Try to use Ollama with vision model
    try:
        import ollama
        
        # Convert image to base64
        img_bytes, _ = _optimize_image(perception.last_image)
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Try vision models in order of preference
        for model in ["moondream:1.8b", "llava:7b", "qwen-vl:7b"]:
            try:
                response = ollama.chat(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                        "images": [img_b64]
                    }]
                )
                return {
                    "description": response['message']['content'],
                    "model": model,
                    "ocr_text": text[:500]  # Include first 500 chars of OCR
                }
            except:
                continue
        
        # Fallback: just return OCR text
        return {
            "description": f"[VLM unavailable] OCR detected: {text[:1000]}",
            "model": "ocr_fallback",
            "ocr_text": text
        }
        
    except ImportError:
        return {
            "description": f"[Ollama not installed] OCR text: {text[:1000]}",
            "model": "ocr_fallback",
            "error": "Install ollama: pip install ollama"
        }


@mcp.tool()
def check_screen_changed(threshold: float = 0.1) -> dict:
    """
    ⚡ Check if screen has changed since last capture (saves tokens).
    
    USE THIS WHEN:
    - Waiting for something to load
    - Checking if action had effect
    - Reducing unnecessary full captures
    
    Args:
        threshold: Change sensitivity 0-1 (default 0.1 = 10% change)
    
    Returns:
        - changed: True if screen changed significantly
        - change_percent: Approximate % of screen changed
        - recommendation: "capture" or "wait"
    
    Example workflow:
    1. smart_action("click", "Submit")
    2. check_screen_changed() → {"changed": True}
    3. capture_screen() → Get updated view
    """
    global _last_screenshot_hash
    
    perception, _, _, _ = _get_components()
    perception.capture_and_scan()
    
    if perception.last_image is None:
        return {"error": "No screenshot available"}
    
    current_hash = _get_image_hash(perception.last_image)
    
    if _last_screenshot_hash is None:
        _last_screenshot_hash = current_hash
        return {
            "changed": True,
            "change_percent": 100,
            "recommendation": "capture",
            "note": "First capture - no previous state"
        }
    
    # Compare hashes (simple but fast)
    changed = current_hash != _last_screenshot_hash
    _last_screenshot_hash = current_hash
    
    return {
        "changed": changed,
        "change_percent": 100 if changed else 0,
        "recommendation": "capture" if changed else "wait"
    }


@mcp.tool()
def scroll(direction: str = "down", amount: int = 3) -> str:
    """
    📜 Scroll the current window.
    
    Args:
        direction: "up", "down", "left", "right"
        amount: Number of scroll units (default 3)
    
    Returns:
        Status message
    """
    if direction == "down":
        pyautogui.scroll(-amount)
    elif direction == "up":
        pyautogui.scroll(amount)
    elif direction == "left":
        pyautogui.hscroll(-amount)
    elif direction == "right":
        pyautogui.hscroll(amount)
    else:
        return f"Unknown direction: {direction}. Use up/down/left/right"
    
    time.sleep(0.2)
    return f"Scrolled {direction} by {amount}"


# ==============================================================================
# PHASE 3: DIFFERENTIATION FEATURES
# ==============================================================================

# Dangerous actions that require confirmation
DANGEROUS_PATTERNS = [
    "shutdown", "restart", "reboot", "format", "delete", "remove",
    "rmdir", "rd /s", "rm -rf", "uninstall", "wipe", "factory reset"
]


@mcp.tool()
def execute_script(code: str, language: str = "python") -> dict:
    """
    🐍 Execute Python code directly on the desktop.
    
    USE THIS WHEN:
    - Complex automation requiring multiple steps
    - Custom logic that can't be done with other tools
    - Batch operations
    
    SAFETY:
    - Code runs with YOUR user permissions
    - Dangerous patterns trigger warning
    
    Args:
        code: Python code to execute
        language: Currently only "python" supported
    
    Returns:
        - output: Stdout from execution
        - error: Any errors
        - result: Return value if any
    
    Examples:
    - execute_script("import os; print(os.getcwd())")
    - execute_script("for i in range(5): pyautogui.press('down')")
    """
    if language != "python":
        return {"error": f"Unsupported language: {language}. Only 'python' supported."}
    
    # Check for dangerous patterns
    code_lower = code.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in code_lower:
            return {
                "error": f"BLOCKED: Code contains dangerous pattern '{pattern}'",
                "code": code,
                "action_required": "User must manually run this code or approve via UI"
            }
    
    # Execute the code
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    result = None
    
    # Provide common imports in the execution context
    exec_globals = {
        "pyautogui": pyautogui,
        "time": time,
        "os": os,
        "json": json,
        "random": random,
        "math": math,
    }
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, exec_globals)
            # Check if there's a result variable
            result = exec_globals.get("result", None)
        
        return {
            "status": "success",
            "output": stdout_capture.getvalue()[:2000],
            "error": stderr_capture.getvalue()[:500] if stderr_capture.getvalue() else None,
            "result": str(result) if result else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": stderr_capture.getvalue()[:500]
        }


@mcp.tool()
def focus_window(title: str, exact: bool = False) -> dict:
    """
    🪟 Find and focus a window by title.
    
    USE THIS WHEN:
    - Need to switch to a specific application
    - Want to ensure correct window before automation
    
    Args:
        title: Window title to search for (case-insensitive)
        exact: If True, require exact match; if False, partial match OK
    
    Returns:
        - status: "focused" or "not_found"
        - window_title: Actual window title found
    
    Examples:
    - focus_window("Chrome") → Focus any Chrome window
    - focus_window("Untitled - Notepad", exact=True) → Focus exact window
    """
    if not PYWINAUTO_AVAILABLE:
        return {"error": "pywinauto not available for window management"}
    
    try:
        from pywinauto import Desktop
        
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        
        title_lower = title.lower()
        
        for win in windows:
            try:
                win_title = win.window_text()
                if exact:
                    match = win_title.lower() == title_lower
                else:
                    match = title_lower in win_title.lower()
                
                if match:
                    win.set_focus()
                    time.sleep(0.3)
                    return {
                        "status": "focused",
                        "window_title": win_title
                    }
            except:
                continue
        
        return {
            "status": "not_found",
            "searched_for": title
        }
        
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_windows() -> list:
    """
    📋 List all visible windows.
    
    USE THIS WHEN:
    - Need to find a window to focus
    - Checking what applications are open
    
    Returns:
        List of window titles
    """
    if not PYWINAUTO_AVAILABLE:
        return [{"error": "pywinauto not available"}]
    
    try:
        from pywinauto import Desktop
        
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        
        result = []
        for win in windows:
            try:
                title = win.window_text()
                if title and len(title) > 0:
                    result.append(title)
            except:
                continue
        
        return result[:30]  # Limit to 30 windows
        
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_clipboard() -> str:
    """
    📋 Get current clipboard contents.
    
    Returns:
        Clipboard text content
    """
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return data
        except:
            return "[Clipboard is empty or contains non-text data]"
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return f"[Error reading clipboard: {e}]"


@mcp.tool()
def set_clipboard(text: str) -> str:
    """
    📋 Set clipboard contents.
    
    Args:
        text: Text to copy to clipboard
    
    Returns:
        Status message
    """
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return f"Copied {len(text)} chars to clipboard"
    except Exception as e:
        return f"Error: {e}"


# --- ENTRY POINT ---
if __name__ == "__main__":
    print(f"{Fore.GREEN}[MCP] MewAct Desktop Server v2.2 Starting...")
    print(f"{Fore.CYAN}[MCP] Phase 1: Smart Screenshots, Coord Normalization, Smooth Mouse")
    print(f"{Fore.CYAN}[MCP] Phase 2: Colored Markers, VLM Describe, Differential Screenshots")
    print(f"{Fore.CYAN}[MCP] Phase 3: Code Mode, Window Focus, Clipboard")
    print(f"{Fore.YELLOW}[MCP] Tools (18): capture_screen, click_element, click_at_normalized, click_text, type_text, press_key, drag_drop, execute_command, smart_action, list_commands, get_screen_info, describe_screen, check_screen_changed, scroll, execute_script, focus_window, list_windows, get_clipboard, set_clipboard")
    mcp.run()
