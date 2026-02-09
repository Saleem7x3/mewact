
import subprocess
import time
import os
import io
import sys
from colorama import Fore
from . import config

# Requires ADB in PATH or configured in config.py
# Uses 'adb exec-out screencap -p' for fast screen capture
# Uses 'adb shell input' for control

class MobileController:
    def __init__(self):
        self.adb_path = getattr(config, 'ADB_PATH', 'adb')
        self.enabled = getattr(config, 'MOBILE_ENABLED', False)
        self.device_id = None
        
        if self.enabled:
            self.connect()

    def _run_adb(self, args, binary=False):
        """Run ADB command."""
        cmd = [self.adb_path] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=not binary)
            if result.returncode != 0:
                # print(f"{Fore.RED}[!] ADB Error: {result.stderr}")
                return None
            return result.stdout
        except FileNotFoundError:
            print(f"{Fore.RED}[!] ADB binary not found at '{self.adb_path}'")
            self.enabled = False
            return None
        except Exception as e:
            print(f"{Fore.RED}[!] ADB Exception: {e}")
            return None

    def connect(self):
        """Check for connected devices."""
        if not self.enabled: return False
        
        output = self._run_adb(["devices"])
        if not output: return False
        
        lines = output.strip().split('\n')[1:]
        devices = [line.split('\t')[0] for line in lines if '\tdevice' in line]
        
        if devices:
            self.device_id = devices[0]
            print(f"{Fore.CYAN}[*] Connected to Android Device: {self.device_id}")
            return True
        else:
            print(f"{Fore.YELLOW}[!] No Android devices found. Enable USB Debugging.")
            return False

    def capture_screen(self):
        """Capture screen as PIL Image."""
        if not self.enabled or not self.device_id: return None
        
        # Binary output for image
        img_data = self._run_adb(["exec-out", "screencap", "-p"], binary=True)
        if img_data:
            try:
                from PIL import Image
                return Image.open(io.BytesIO(img_data))
            except Exception as e:
                print(f"{Fore.RED}[!] Image Parse Error: {e}")
        return None

    def tap(self, x, y):
        """Tap at coordinates."""
        if not self.enabled: return
        self._run_adb(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1, y1, x2, y2, duration=300):
        """Swipe from (x1,y1) to (x2,y2)."""
        if not self.enabled: return
        self._run_adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    def type_text(self, text):
        """Type text (escapes spaces)."""
        if not self.enabled: return
        # ADB requires %s for space
        safe_text = text.replace(" ", "%s").replace("'", "\\'")
        self._run_adb(["shell", "input", "text", safe_text])

    def key_event(self, key_code):
        """Send key event (3=HOME, 4=BACK, 187=APP_SWITCH)."""
        if not self.enabled: return
        self._run_adb(["shell", "input", "keyevent", str(key_code)])

    def home(self): self.key_event(3)
    def back(self): self.key_event(4)
    def app_switch(self): self.key_event(187)
