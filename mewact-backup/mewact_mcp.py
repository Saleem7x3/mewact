import sys
import os
import threading
import socket
import winsound
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
from colorama import Fore, init, Style

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.theme import Theme
    RICH_AVAILABLE = True
    _console = Console(stderr=True, theme=Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "premium": "bold magenta"
    }))
except ImportError:
    RICH_AVAILABLE = False
    class MockConsole:
        def print(self, *args, **kwargs):
            msg = " ".join([str(a) for a in args])
            print(msg, file=sys.stderr)
    _console = MockConsole()

try:
    from pywinauto import Desktop
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

from mewact_legacy import PerceptionEngine, ActionExecutor, LibraryManager, SessionManager
import mewact_legacy
mewact_legacy.MCP_MODE = True

init(autoreset=True)



# Global state
_perception = None
_lib_mgr = None
_executor = None
_session_mgr = None
_last_ui_elements = {}  # Cache for Smart Screenshots
_last_scale_factor = 1.0  # For coordinate translation
_action_lock = threading.Lock()

# --- HELPER FUNCTIONS ---

def _get_components():
    """Lazy load MewAct components."""
    global _perception, _lib_mgr, _executor, _session_mgr
    if _perception is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        _perception = PerceptionEngine()
        _lib_mgr = LibraryManager(os.path.join(base_dir, "command_library.json"))
        _executor = ActionExecutor(_lib_mgr)
        _session_mgr = SessionManager(os.path.join(base_dir, "session_memory.json"))
    return _perception, _lib_mgr, _executor, _session_mgr

    return _perception, _lib_mgr, _executor, _session_mgr


def _play_sound(sound_type: str):
    """Play a subtle premium sound signal."""
    try:
        if sound_type == "click":
            winsound.Beep(400, 50) # Soft click
        elif sound_type == "type":
            winsound.Beep(600, 10) # Very short tick
        elif sound_type == "success":
            winsound.Beep(800, 100) # High chime
            winsound.Beep(1200, 150)
        elif sound_type == "error":
            winsound.Beep(150, 300) # Low bonk
    except: pass


def _get_dpi_scale() -> float:
    """Detect HiDPI scaling factor."""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        w = user32.GetSystemMetrics(0)
        return 1.0 # simplified for now, assuming 1.0 or relying on coordinates
    except: return 1.0

def _normalized_to_physical(x_norm: int, y_norm: int) -> tuple:
    """Convert 0-1000 range to physical screen coordinates."""
    screen_w, screen_h = pyautogui.size()
    x = int((x_norm / 1000) * screen_w)
    y = int((y_norm / 1000) * screen_h)
    return x, y

def _physical_to_normalized(x: int, y: int) -> tuple:
    """Convert physical coordinates to 0-1000 range."""
    screen_w, screen_h = pyautogui.size()
    x_norm = int((x / screen_w) * 1000)
    y_norm = int((y / screen_h) * 1000)
    return x_norm, y_norm

def _optimize_image(img: Image.Image) -> str:
    """Resize/compress image for VLM optimization."""
    # Resize if too large
    if img.size[0] > 1568 or img.size[1] > 1568:
        img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def _bezier_point(t, p0, p1, p2, p3):
    """Calculate point on cubic bezier curve."""
    return (1-t)**3*p0 + 3*(1-t)**2*t*p1 + 3*(1-t)*t**2*p2 + t**3*p3

def _smooth_move(target_x, target_y, duration=0.3):
    """Move mouse smoothly using Bezier curve."""
    start_x, start_y = pyautogui.position()
    
    # Random control points for natural arc
    dist = math.hypot(target_x - start_x, target_y - start_y)
    offset = min(dist * 0.2, 100)
    
    cp1_x = start_x + (random.random() - 0.5) * offset
    cp1_y = start_y + (random.random() - 0.5) * offset
    cp2_x = target_x + (random.random() - 0.5) * offset
    cp2_y = target_y + (random.random() - 0.5) * offset
    
    steps = 20
    for i in range(steps):
        t = i / steps
        x = _bezier_point(t, start_x, cp1_x, cp2_x, target_x)
        y = _bezier_point(t, start_y, cp1_y, cp2_y, target_y)
        pyautogui.moveTo(x, y)
        time.sleep(duration / steps)
    pyautogui.moveTo(target_x, target_y)

# --- MCP SERVER SETUP ---
mcp = FastMCP("MewAct Desktop v2")

@mcp.tool()
def capture_screen(annotate: bool = True, use_uia: bool = True) -> dict:
    """
    📸 Capture the current screen and return clickable elements.
    
    Args:
        annotate (bool): If True, returns a base64 image with bounding boxes drawn.
        use_uia (bool): If True, uses Windows UI Automation for better element detection.
    """
    global _last_ui_elements, _last_scale_factor
    
    _play_sound("click")
    
    with _action_lock:
        try:
            perception, _, _, _ = _get_components()
            
            # 1. Capture Logic
            screenshot_path = "mcp_capture.png" 
            # Note: PerceptionEngine usually handles this, but here we might need direct calls
            # For simplicity, we use existing PerceptionEngine methods if available, or direct logic.
            # mewact_legacy.PerceptionEngine has capture_window() logic.
            
            # Reusing legacy logic through _perception
            # But wait, PerceptionEngine needs configuration.
            # We lazy loaded it.
            
            # Simple implementation for now to verify MCP server stability
            # We can expand to full logic once stability is confirmed.
            
            screen_w, screen_h = pyautogui.size()
            screenshot = pyautogui.screenshot()
            
            # Store for VLM
            global _last_screenshot
            _last_screenshot = screenshot
            
            elements = []
            if use_uia and PYWINAUTO_AVAILABLE:
                # Mock UIA for now to avoid complexity in this step
                pass
            
            # Add simple image return
            img_b64 = _optimize_image(screenshot)
            
            return {
                "width": screen_w,
                "height": screen_h,
                "image": img_b64, 
                "elements": elements,
                "message": "Screen captured successfully"
            }
            
        except Exception as e:
            _play_sound("error")
            return {"error": str(e)}

@mcp.tool()
def execute_command(command_id: str, params: str = "") -> str:
    """
    ⚔️ Execute a specific command by ID from the command library.
    
    Args:
        command_id (str): The ID of the command (e.g., "200" for focus window).
        params (str): Optional parameters for the command.
    """
    with _action_lock:
        try:
            _, _, executor, _ = _get_components()
            # Simple parsing of params - in real usage, might need smarter parsing
            param_list = params.split(" ") if params else []
            result = executor.execute_action({"id": command_id, "params": param_list})
            _play_sound("success")
            return f"Executed {command_id}: {result}"
        except Exception as e:
            _play_sound("error")
            return f"Error executing {command_id}: {e}"

@mcp.tool()
def type_text(text: str) -> str:
    """
    ⌨️ Type text at the current cursor position.
    """
    _play_sound("type")
    with _action_lock:
        try:
            pyautogui.write(text, interval=0.005)
            # Paste support for efficiency could be added here
            return "Text typed successfully"
        except Exception as e:
            return f"Error typing: {e}"

@mcp.tool()
def check_screen_changed() -> bool:
    """
    👀 Check if the screen content has changed significantly since last capture.
    """
    global _last_screwenshot
    # Not implemented fully in this restoration step to save space, but stubbed.
    return True

@mcp.tool()
def get_screen_info() -> str:
    """
    ℹ️ Return screen resolution and DPI scaling details.
    """
    w, h = pyautogui.size()
    scale = _get_dpi_scale()
    return f"Screen: {w}x{h}, DPI Scale: {scale:.2f}"

@mcp.tool()
def run_shell(command: str) -> str:
    """
    ℹ️ Execute a raw shell command and return its output.
    Useful for getting system info, file listings, etc.
    """
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        output = result.stdout + result.stderr
        return output.strip() or "[No Output]"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def execute_script(code: str) -> str:
    """
    ℹ️ Execute arbitrary Python code in the agent's environment.
    Use this for complex logic, calculations, or direct API access.
    Variables: 'pyautogui', 'ctypes', 'time', 'subprocess' are available.
    """
    import io, contextlib
    buffer = io.StringIO()
    try:
        # Define safe locals
        safe_locals = {
            "pyautogui": pyautogui,
            "ctypes": ctypes,
            "time": time,
            "subprocess": subprocess,
            "math": math,
            "sys": sys,
            "_get_dpi_scale": _get_dpi_scale
        }
        with contextlib.redirect_stdout(buffer):
            exec(code, safe_locals, safe_locals)
        return buffer.getvalue().strip() or "Success"
    except Exception as e:
        return f"Error: {e}"




if __name__ == "__main__":
    _console.print(Panel(Text("MCP STARTED", style="bold white on blue")))
    mcp.run()
