"""
MewAct MCP Server
==================
Exposes MewAct's desktop control capabilities as MCP tools for Cloud AI integration.

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

init(autoreset=True)

# Import MewAct components (without running main)
# We import after check_deps runs
from mew import PerceptionEngine, ActionExecutor, LibraryManager, SessionManager

# --- MCP SERVER SETUP ---
mcp = FastMCP("MewAct Desktop")

# Global instances (lazy init)
_perception = None
_lib_mgr = None
_executor = None
_session_mgr = None
_last_ui_elements = []  # Cache for Smart Screenshots

def _get_components():
    """Lazy initialization of MewAct components."""
    global _perception, _lib_mgr, _executor, _session_mgr
    if _perception is None:
        _lib_mgr = LibraryManager()
        _perception = PerceptionEngine()
        _session_mgr = SessionManager()
        _executor = ActionExecutor(_lib_mgr, session_manager=_session_mgr)
        _executor.locals["PERCEPTION_ENGINE"] = _perception
        _executor.locals["session_manager"] = _session_mgr
    return _perception, _lib_mgr, _executor, _session_mgr


def _annotate_screenshot(img: np.ndarray, ui_elements: list) -> tuple:
    """
    Draw numbered labels on screenshot for Smart Screenshots.
    Returns: (annotated_image_bytes, element_mapping)
    """
    global _last_ui_elements
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    # Use a small font
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()
    
    element_map = {}
    for i, el in enumerate(ui_elements[:30]):  # Limit to 30 elements
        x, y = el.get('x', 0), el.get('y', 0)
        text = el.get('text', '')
        
        # Draw red circle with number
        draw.ellipse([x-12, y-12, x+12, y+12], fill="red", outline="white")
        draw.text((x-6, y-8), str(i), fill="white", font=font)
        
        element_map[i] = {"text": text, "x": x, "y": y}
    
    _last_ui_elements = element_map
    
    # Convert to base64 JPEG
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=80)
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return img_b64, element_map


# --- MCP TOOLS ---

@mcp.tool()
def capture_screen(annotate: bool = True) -> dict:
    """
    Capture the screen and return OCR text + optional annotated screenshot.
    
    Args:
        annotate: If True, overlay numbered IDs on clickable elements (Smart Screenshots)
    
    Returns:
        dict with 'text' (OCR content), 'elements' (list of detected UI elements),
        and optionally 'image_base64' (annotated screenshot)
    """
    perception, _, _, _ = _get_components()
    ui_data, text = perception.capture_and_scan()
    
    result = {
        "text": text[:4000],  # Limit text length
        "element_count": len(ui_data),
        "elements": [{"id": i, "text": el.get('text', '')[:50], "x": el.get('x'), "y": el.get('y')} 
                     for i, el in enumerate(ui_data[:30])]
    }
    
    if annotate and perception.last_image is not None:
        img_b64, _ = _annotate_screenshot(perception.last_image, ui_data)
        result["image_base64"] = img_b64
        result["hint"] = "Use click_element(id) to click on numbered elements"
    
    return result


@mcp.tool()
def click_element(element_id: int) -> str:
    """
    Click on a detected UI element by its ID (from last capture_screen).
    
    Args:
        element_id: The numbered ID shown on the annotated screenshot
    
    Returns:
        Status message
    """
    global _last_ui_elements
    
    if element_id not in _last_ui_elements:
        return f"Error: Element #{element_id} not found. Run capture_screen first."
    
    el = _last_ui_elements[element_id]
    x, y = el['x'], el['y']
    
    pyautogui.click(x, y)
    time.sleep(0.3)
    
    return f"Clicked element #{element_id} ('{el['text']}') at ({x}, {y})"


@mcp.tool()
def click_text(text_to_find: str) -> str:
    """
    Find text on screen and click it.
    
    Args:
        text_to_find: The text to search for and click
    
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
            pyautogui.click(x, y)
            time.sleep(0.3)
            return f"Clicked '{el['text']}' at ({x}, {y})"
    
    return f"Text '{text_to_find}' not found on screen"


@mcp.tool()
def type_text(text: str, press_enter: bool = False) -> str:
    """
    Type text using the keyboard.
    
    Args:
        text: The text to type
        press_enter: If True, press Enter after typing
    
    Returns:
        Status message
    """
    pyautogui.write(text, interval=0.02)
    if press_enter:
        time.sleep(0.1)
        pyautogui.press('enter')
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


@mcp.tool()
def press_key(key: str) -> str:
    """
    Press a keyboard key or hotkey.
    
    Args:
        key: Key name (e.g., 'enter', 'escape', 'ctrl+c', 'alt+tab')
    
    Returns:
        Status message
    """
    if '+' in key:
        parts = [k.strip() for k in key.split('+')]
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(key)
    return f"Pressed: {key}"


@mcp.tool()
def execute_command(command_id: int, variables: str = "") -> str:
    """
    Execute a command from the MewAct command library by ID.
    
    Args:
        command_id: The command ID (see command_library.json)
        variables: Optional variables to pass (e.g., "hello world" for type commands)
    
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
def smart_action(action: str, target: str = "") -> dict:
    """
    Perform an intelligent action in one call (1-Call Workflow).
    Captures screen, finds target, and executes action.
    
    Args:
        action: One of 'click', 'type', 'wait_for'
        target: Text to find/interact with, or text to type
    
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
                pyautogui.click(x, y)
                return {"status": "clicked", "target": el['text'], "x": x, "y": y}
        return {"status": "not_found", "target": target}
    
    elif action == "type":
        pyautogui.write(target, interval=0.02)
        return {"status": "typed", "text": target}
    
    elif action == "wait_for":
        # Wait up to 5 seconds for text to appear
        for _ in range(10):
            _, text = perception.capture_and_scan()
            if target.lower() in text.lower():
                return {"status": "found", "target": target}
            time.sleep(0.5)
        return {"status": "timeout", "target": target}
    
    return {"status": "error", "message": f"Unknown action: {action}"}


@mcp.tool()
def list_commands(filter_text: str = "") -> list:
    """
    List available commands from the command library.
    
    Args:
        filter_text: Optional text to filter commands by name/description
    
    Returns:
        List of command summaries
    """
    _, lib_mgr, _, _ = _get_components()
    
    commands = []
    for name, cmd in lib_mgr.commands.items():
        if filter_text and filter_text.lower() not in name.lower() and filter_text.lower() not in cmd.get('description', '').lower():
            continue
        commands.append({
            "id": cmd.get('id'),
            "name": name,
            "description": cmd.get('description', '')[:100]
        })
    
    return commands[:50]  # Limit to 50 results


# --- ENTRY POINT ---
if __name__ == "__main__":
    print(f"{Fore.GREEN}[MCP] MewAct Desktop Server Starting...")
    print(f"{Fore.CYAN}[MCP] Available tools: capture_screen, click_element, click_text, type_text, press_key, execute_command, smart_action, list_commands")
    mcp.run()
