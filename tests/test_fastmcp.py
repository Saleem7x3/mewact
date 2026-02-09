import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server.fastmcp import FastMCP
    print("✅ FastMCP imported successfully")
    
    # Simulate mewact_mcp setup FULL
    import pyautogui
    import mss
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from colorama import Fore, init, Style
    import threading
    import socket
    import winsound
    import io
    import time
    import math
    import random
    import ctypes
    
    try:
        from pywinauto import Desktop
        print("✅ pywinauto imported")
    except ImportError: pass
    
    from mewact_legacy import PerceptionEngine # Import from legacy to check side effects
    
    mcp = FastMCP("MewAct Desktop v2")


    print("Decorating tool...")
    try:
        @mcp.tool()
        def capture_screen(annotate: bool = True, use_uia: bool = True) -> dict:
            return {"status": "ok"}
        print("✅ Tool decorated")
    except Exception as e:
        print(f"❌ Tool decoration failed: {e}")
        import traceback
        traceback.print_exc()


    print("Running mcp.run() check with --help...")

    try:
        # Hack sys.argv to simulate --help
        sys.argv = [sys.argv[0], "--help"]
        print("Calling mcp.run()...")
        mcp.run()
        print("✅ mcp.run() finished (should exit)")
    except SystemExit as e:
        print(f"✅ mcp.run() exited with code {e.code}")
    except Exception as e:
        print(f"❌ mcp.run() CRASHED: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
