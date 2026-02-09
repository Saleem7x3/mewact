import sys
import unicodedata
import time
import json
import re
import threading
import subprocess
import platform
import os
import io
import contextlib
import traceback
import difflib
import random
import numpy as np
import cv2
import mss
import pyautogui
import ast
import ctypes
import argparse
from ctypes import wintypes
from colorama import Fore, Style, init
from typing import Dict, Any, List, Tuple, Optional, Union
import collections
import webbrowser

# Initialize Colorama
init(autoreset=True)

# --- CONFIGURATION ---
MODEL_NAME = "gemma3:4b-cloud" 
OCR_ENGINE = "rapidocr"  # "rapidocr", "easyocr", or "paddleocr"
TARGET_WINDOW_TITLE = ""  # Focus on specific window (e.g., "Chrome")
TARGET_MONITORS = []      # List of monitor indices (1-based). Empty = all. E.g., [1] or [1, 2]
LIBRARY_FILE = "command_library.json"
SESSION_FILE = "sessions.json"

# --- ROBUST MULTI-TRIGGER REGEX ---
# Format: <ID>&&$47 <command> [| <var>] <ID>$&47
# Example: 1&&$47 open notepad 1$&47
TRIGGER_PATTERN = r"(\d+)&&\$47\s*(.*?)\s*\1\$&47"

# Variable definition pattern: &&VAR <num> <content> VAR&&
VAR_PATTERN = r"&&VAR\s*(\d+)\s+(.*?)\s*VAR&&"

LOOP_DELAY = 0.2
DEBUG_OCR = False
OCR_USE_GPU = True  # Set to True to use GPU for OCR (EasyOCR/PaddleOCR only) 

# Adaptive OCR Configuration
OCR_ADAPTIVE_MODE = False # Default to Full Screen (Performance). Set True via --power-saver
OCR_STRIP_THRESHOLD = 0.53  # Windows occupying >53% of screen use strip mode
OCR_STRIP_COUNT = 3         # Number of horizontal strips to split large windows into 
OCR_STRIP_OVERLAP = 30      # Pixels of overlap between strips to prevent cutting text lines 

# Scan Mode Configuration
OCR_SCAN_MODE = "monitor"   # "monitor" (default) or "window"
OCR_MONITOR_STRATEGY = "full" # "full" (default) or "window" (iterates windows on monitor) 

# --- AUTO-ROLLBACK CONFIG ---
# When enabled, automatically focuses back to chat window after each command
AUTO_ROLLBACK_ENABLED = False
AUTO_ROLLBACK_CHAT = "gemini"  # "gemini", "chatgpt", "claude", or "tab" for generic tab switch

# --- IDLE WATCHDOG CONFIG ---
LAST_ACTIVITY = time.time()
IDLE_TIMEOUT = 0 # 0 = Disabled


# --- 0. DEPENDENCY CHECK ---
def check_deps():
    try:
        import rapidocr_onnxruntime
        import ollama
    except ImportError as e:
        print(f"{Fore.RED}[!] CRITICAL MISSING LIB: {e.name}")
        sys.exit(1)
    
    try: 
        ollama.list()
    except ConnectionError:
        print(f"{Fore.RED}[!] Ollama Server not found. Run 'ollama serve'.")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}[!] Ollama error: {type(e).__name__}: {e}")
        sys.exit(1)
    print(f"{Fore.GREEN}[*] System Ready. ID-Selector Mode Active.")

# Only check deps when running directly, not when imported
if __name__ == "__main__":
    check_deps()

# --- GLOBAL VARIABLE STORE ---
class VariableStore:
    """Stores variables that can be referenced by $V1, $V2, etc."""
    def __init__(self):
        self.vars = {}  # {"1": "long text here", "2": "another var"}
        self._seen_hashes = set()  # Track what we've already parsed
    
    def set(self, var_id: str, value: str):
        # Deduplication: only set if value is new
        value_hash = hash(f"{var_id}:{value}")
        if value_hash in self._seen_hashes:
            return  # Already processed this exact var
        self._seen_hashes.add(value_hash)
        
        self.vars[str(var_id)] = value
        preview = value[:50].replace('\n', ' ')
        print(f"{Fore.BLUE}[VAR] Set $V{var_id} = '{preview}{'...' if len(value) > 50 else ''}'")
    
    def get(self, var_id: str) -> str:
        val = self.vars.get(str(var_id), "")
        if not val:
            print(f"{Fore.YELLOW}[!] Warning: $V{var_id} not found")
        return val
    
    def parse_from_text(self, text: str):
        """Extract variable definitions from OCR text."""
        matches = re.finditer(VAR_PATTERN, text, re.DOTALL)
        for m in matches:
            self.set(m.group(1), m.group(2).strip())
    
    def resolve(self, text: str) -> str:
        """Replace $V1, $V2 etc. with actual values."""
        def replacer(m):
            var_id = m.group(1)
            return self.get(var_id)
        return re.sub(r'\$V(\d+)', replacer, text)
    
    def clear(self):
        """Clear all variables (useful for session reset)."""
        self.vars.clear()
        self._seen_hashes.clear()

VAR_STORE = VariableStore()

# --- WATCHDOG THREAD ---
class IdleWatchdog(threading.Thread):
    def __init__(self, executor, timeout):
        super().__init__(daemon=True)
        self.executor = executor
        self.timeout = timeout
        self.triggered = False

    def run(self):
        print(f"{Fore.CYAN}[*] Watchdog started (Timeout: {self.timeout}s)")
        while True:
            time.sleep(1.0)
            if self.timeout <= 0: continue
            
            idle_time = time.time() - globals()['LAST_ACTIVITY']
            if idle_time > self.timeout:
                if not self.triggered:
                    # Only trigger if anchor is set
                    if 'ANCHOR_HWND' in self.executor.locals:
                        print(f"{Fore.YELLOW}[WATCHDOG] Idle for {int(idle_time)}s. Triggering Auto-Mew...")
                        self.triggered = True
                        
                        # Helper to run by ID
                        def run_id(cid):
                            cmd = self.executor.library.get_command_by_id(cid)
                            if cmd: 
                                self.executor.execute(cmd['code'], cmd_type=cmd['type'], cmd_data=cmd)
                        
                        run_id(301) # Focus Anchor
                        time.sleep(2.0)
                        run_id(107) # Mew Act
                        
                        self.triggered = False
                    else:
                        # No anchor, logic
                        pass

            else:
                self.triggered = False



# --- 1. MEMORY MANAGER ---
class LibraryManager:
    def __init__(self):
        self.lib_path = LIBRARY_FILE
        self.sess_path = SESSION_FILE
        self.library = self._load_json(self.lib_path)
        
        # Ensure 'commands' key exists
        if "commands" not in self.library:
            self.library = {"schema_version": 2, "commands": {}}
            self._seed_defaults()
            
        self.sessions = self._load_json(self.sess_path)
        self.is_recording = False
        self.current_session_name = ""
        self.current_session_data = []
        self.last_action_time = 0

    def _seed_defaults(self):
        # Default with placeholders for variables
        defaults = {
            "open app": {"id": 101, "code": "subprocess.Popen('__VAR__', shell=True)"},
            "type text": {"id": 102, "code": "pyautogui.write('__VAR__')"},
            "click text": {"id": 103, "code": "# AUTO-AIM HANDLED EXTERNALLY"},
            "minimize": {"id": 104, "code": "pyautogui.hotkey('win', 'd')"}
        }
        for k, v in defaults.items():
            self.library["commands"][k] = {"type": "python", "code": v["code"], "id": v["id"], "timestamp": time.time()}
        self._save_lib()

    def _load_json(self, path) -> Dict:
        if not os.path.exists(path): return {"schema_version": 2, "commands": {}}
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if "schema_version" not in data: return {"schema_version": 2, "commands": {}}
                return data
        except json.JSONDecodeError as e:
            print(f"{Fore.YELLOW}[!] Warning: JSON parse error in {path}: {e}. Starting fresh.")
            return {"schema_version": 2, "commands": {}}
        except Exception as e:
            print(f"{Fore.YELLOW}[!] Warning: Could not load {path}: {e}")
            return {"schema_version": 2, "commands": {}}

    def _save_lib(self):
        try: 
            with open(self.lib_path, 'w') as f: 
                json.dump(self.library, f, indent=4)
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to save library: {e}")

    def save_entry(self, command: str, code: str):
        if "session" in command.lower(): return
        if "AI Error" in code: return 
        # Auto-generate an ID if saving from Sentinel (random high number)
        new_id = random.randint(1000, 9999)
        self.library["commands"][command.lower()] = {
            "type": "python",
            "code": code,
            "id": new_id,
            "timestamp": time.time()
        }
        self._save_lib()

    def handle_session_command(self, command: str) -> str:
        cmd = command.lower()
        if cmd.startswith("start session"):
            name = cmd.replace("start session", "").strip()
            self.is_recording = True; self.current_session_name = name; self.current_session_data = []; self.last_action_time = time.time()
            return f"Recording: '{name}'"
        elif cmd.startswith("continue session"):
            name = cmd.replace("continue session", "").strip()
            if name in self.sessions:
                self.is_recording = True; self.current_session_name = name; self.current_session_data = self.sessions[name]; self.last_action_time = time.time()
                return f"Resumed: '{name}'"
        elif cmd == "end session":
            self.is_recording = False; self.sessions[self.current_session_name] = self.current_session_data
            with open(self.sess_path, 'w') as f: json.dump(self.sessions, f, indent=4)
            return "Saved"
        elif cmd.startswith("play session"):
            name = cmd.replace("play session", "").strip()
            return "PLAY:" + name if name in self.sessions else "Error"
        return None

    def record_action(self, command: str, code: str):
        if self.is_recording:
            now = time.time()
            pause = round(now - self.last_action_time, 2)
            if pause > 60: pause = 1.0
            self.last_action_time = now
            self.current_session_data.append({"command": command, "code": code, "pause": pause})
            print(f"{Fore.BLUE}[REC] Step {len(self.current_session_data)}: {command}")

    def get_command_by_id(self, cmd_id: int) -> Optional[Dict]:
        """Find a command by its ID for sequence execution"""
        for name, cmd in self.library.get("commands", {}).items():
            if cmd.get("id") == cmd_id:
                return {**cmd, "name": name}
        return None


# --- 2. PERCEPTION ENGINE ---
class WindowCapture:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        try:
            self.shcore = ctypes.windll.shcore
            self.shcore.SetProcessDpiAwareness(1)
        except:
            self.user32.SetProcessDPIAware() 

    def get_window_rect(self, title_keyword):
        found_hwnd = None
        def callback(hwnd, extra):
            nonlocal found_hwnd
            if not self.user32.IsWindowVisible(hwnd): return 1
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length == 0: return 1
            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            if title_keyword.lower() in buff.value.lower():
                found_hwnd = hwnd
                return 0 
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)

        if found_hwnd:
            rect = wintypes.RECT()
            self.user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            return {"top": rect.top, "left": rect.left, "width": w, "height": h}
        return None

    
    def get_all_window_rects(self):
        """Return list of rects for all visible application windows."""
        window_rects = []
        def callback(hwnd, extra):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    # Get title to filter Program Manager/System stuff
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    
                    if title and title != "Program Manager":
                        rect = wintypes.RECT()
                        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        
                        # Filter tiny windows (likely tooltips/hidden)
                        if w > 20 and h > 20:
                             window_rects.append({"top": rect.top, "left": rect.left, "width": w, "height": h, "title": title})
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)
        # Sort by Z-order? EnumWindows usually enumerates in Z-order (top first).
        # We might want to capture top-down or bottom-up. Standard iteration is fine.
        return window_rects

    def list_windows(self):
        window_list = []
        def callback(hwnd, extra):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title != "Program Manager": 
                         window_list.append((hwnd, title))
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)
        return window_list

class PerceptionEngine:
    def __init__(self):
        self.ocr_engine = OCR_ENGINE.lower()
        gpu_status = "GPU" if OCR_USE_GPU else "CPU"
        print(f"{Fore.CYAN}[*] Initialization: {self.ocr_engine.upper()} Engine ({gpu_status})")
        
        # --- ENGINE INITIALIZATION ---
        if self.ocr_engine == "easyocr":
            try:
                import easyocr
                self.ocr = easyocr.Reader(['en'], gpu=OCR_USE_GPU)
            except ImportError:
                print(f"{Fore.YELLOW}[!] EasyOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        elif self.ocr_engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False, use_gpu=OCR_USE_GPU)
            except ImportError:
                print(f"{Fore.YELLOW}[!] PaddleOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        # Default / Fallback
        if self.ocr_engine == "rapidocr":
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR(det_use_gpu=OCR_USE_GPU, cls_use_gpu=OCR_USE_GPU, rec_use_gpu=OCR_USE_GPU, intra_op_num_threads=4)
            
        self.win_cap = WindowCapture()
        self.last_image = None  # DEPRECATED: Only used if we do full capture loop
        self.current_capture_regions = [] # Store regions for mew act command
        with mss.mss() as sct:
            self.monitors = sct.monitors[1:] if len(sct.monitors) > 2 else [sct.monitors[1]]

    def _get_capture_regions(self, sct):
        # 1. Target Window Override (Highest Priority)
        if TARGET_WINDOW_TITLE:
            rect = self.win_cap.get_window_rect(TARGET_WINDOW_TITLE)
            if rect: return [rect]
            else:
                if DEBUG_OCR: print(f"{Fore.RED}[!] Target window '{TARGET_WINDOW_TITLE}' not found.")
                return []
        
        # 2. Window Scan Logic
        # Active if mode="window" OR (mode="monitor" AND strategy="window")
        use_window_logic = (OCR_SCAN_MODE == "window") or (OCR_SCAN_MODE == "monitor" and OCR_MONITOR_STRATEGY == "window")
        
        if use_window_logic:
            # Get all visible windows
            all_windows = self.win_cap.get_all_window_rects()
            
            # Determine relevant monitors (if filtered)
            target_indices = TARGET_MONITORS if TARGET_MONITORS else range(1, len(sct.monitors))
            valid_monitors = [sct.monitors[i] for i in target_indices if i < len(sct.monitors)]
            
            if not valid_monitors: return []
            
            filtered_windows = []
            for win in all_windows:
                # Check if window center is inside any valid monitor
                cx = win['left'] + win['width'] // 2
                cy = win['top'] + win['height'] // 2
                
                is_valid = False
                for mon in valid_monitors:
                     if (mon['left'] <= cx < mon['left'] + mon['width'] and 
                         mon['top'] <= cy < mon['top'] + mon['height']):
                         is_valid = True
                         break
                
                if is_valid:
                    filtered_windows.append(win)
            
            # Sort windows by coordinate (Top-Left -> Bottom-Right) for consistent reading order
            # EnumWindows is Z-order, but for OCR reading, spatial order might be better?
            # User didn't specify, sticking to Z-order (EnumWindows default) is fine.
            return filtered_windows

        # 3. Monitor Scan Logic (Full Screen) - Default
        target_indices = TARGET_MONITORS if TARGET_MONITORS else range(1, len(sct.monitors))
        regions = [sct.monitors[i] for i in target_indices if i < len(sct.monitors)]
        
        if not regions:
             return [sct.monitors[1]] if len(sct.monitors) > 1 else []
             
        return regions

    def _ocr_image(self, img, region_offset_x, region_offset_y):
        """Helper to run OCR on an image and return adjusted coordinates."""
        ui_data = []
        txt_parts = []
        try:
            if self.ocr_engine == "easyocr":
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                results = self.ocr.readtext(img_rgb)
                for (bbox, text, prob) in results:
                    if prob < 0.2: continue
                    cx = int((bbox[0][0] + bbox[2][0]) / 2) + region_offset_x
                    cy = int((bbox[0][1] + bbox[2][1]) / 2) + region_offset_y
                    ui_data.append({"text": text, "x": cx, "y": cy})
                    txt_parts.append(text)
                    
            elif self.ocr_engine == "paddleocr":
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                result = self.ocr.ocr(img_rgb, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        box = line[0]
                        text, score = line[1]
                        if score < 0.5: continue
                        cx = int((box[0][0] + box[2][0]) / 2) + region_offset_x
                        cy = int((box[0][1] + box[2][1]) / 2) + region_offset_y
                        ui_data.append({"text": text, "x": cx, "y": cy})
                        txt_parts.append(text)
                        
            else: # RapidOCR
                result, _ = self.ocr(img)
                if result:
                    for line in result:
                        box = line[0]
                        text, score = line[1], line[2]
                        if score < 0.4: continue
                        cx = int((box[0][0] + box[2][0]) / 2) + region_offset_x
                        cy = int((box[0][1] + box[2][1]) / 2) + region_offset_y
                        ui_data.append({"text": text, "x": cx, "y": cy})
                        txt_parts.append(text)
        except Exception as e:
            if DEBUG_OCR: print(f"OCR Error: {e}")
        return ui_data, txt_parts

    def capture_and_scan(self):
        time.sleep(0.1) 
        try:
            with mss.mss() as sct:
                all_ui_data = [] 
                all_txt_parts = []
                
                self.current_capture_regions = self._get_capture_regions(sct)
                if not self.current_capture_regions: return [], ""

                # Assume screen 0 for coverage calculation (simplification)
                screen_area = sct.monitors[0]['width'] * sct.monitors[0]['height']
                
                # Disable splitting for window-based modes (User request: "without cutting")
                is_window_mode = (OCR_SCAN_MODE == "window") or (OCR_SCAN_MODE == "monitor" and OCR_MONITOR_STRATEGY == "window")
                allow_splitting = OCR_ADAPTIVE_MODE and not is_window_mode

                for region in self.current_capture_regions:
                    region_area = region['width'] * region['height']
                    coverage = region_area / screen_area
                    
                    # ADAPTIVE OCR STRATEGY (Power Saver Mode - Full Monitor Only)
                    if allow_splitting and coverage > OCR_STRIP_THRESHOLD:
                        # Large window: Split into strips to reduce peak memory/CPU load
                        # print(f"[DEBUG] Adaptive OCR: Strip mode for large window ({coverage:.2f} coverage)")
                        strip_height = region['height'] // OCR_STRIP_COUNT
                        for i in range(OCR_STRIP_COUNT):
                            # Calculate base dimensions
                            base_top = region['top'] + (i * strip_height)
                            base_height = strip_height
                            # Adjust height for last strip to cover remainder
                            if i == OCR_STRIP_COUNT - 1:
                                base_height = region['height'] - (i * strip_height)
                            
                            # Add overlap: Extend strip DOWNWARDS to capture text on the cut line
                            # (Except for the very last strip which is bounded by window bottom)
                            final_height = base_height
                            if i < OCR_STRIP_COUNT - 1:
                                final_height += OCR_STRIP_OVERLAP
                                
                            strip_rect = {
                                'left': region['left'],
                                'top': base_top,
                                'width': region['width'],
                                'height': final_height
                            }
                            img = np.array(sct.grab(strip_rect))
                            s_data, s_txt = self._ocr_image(img, strip_rect['left'], strip_rect['top'])
                            all_ui_data.extend(s_data)
                            all_txt_parts.extend(s_txt)
                    else:
                        # Small window: Full capture
                        # print(f"[DEBUG] Adaptive OCR: Full mode for small window ({coverage:.2f} coverage)")
                        img = np.array(sct.grab(region))
                        s_data, s_txt = self._ocr_image(img, region['left'], region['top'])
                        all_ui_data.extend(s_data)
                        all_txt_parts.extend(s_txt)
                
                full_text = " ".join(all_txt_parts)
                # --- NORMALIZE "STYLISH" FONTS ---
                # Chatbots sometimes output mathematical bold/italic unicode (e.g. 𝐇𝐞𝐥𝐥𝐨)
                full_text = unicodedata.normalize('NFKD', full_text).encode('ascii', 'ignore').decode('utf-8')
                
                return all_ui_data, full_text
        except Exception as e:
            if DEBUG_OCR: print(f"Capture Error: {e}")
            return [], ""

    def copy_last_image_to_clipboard(self) -> bool:
        """Capture FRESH full-screen image (or relevant context) and copy to clipboard."""
        try:
            with mss.mss() as sct:
                # Determine best region to capture for context
                # Prioritize explicit targets, otherwise default to Primary Monitor
                region = None
                
                if TARGET_WINDOW_TITLE:
                    rect = self.win_cap.get_window_rect(TARGET_WINDOW_TITLE)
                    if rect: region = rect
                elif TARGET_MONITORS:
                    # Capture the first targeted monitor
                    idx = TARGET_MONITORS[0]
                    if idx < len(sct.monitors):
                        region = sct.monitors[idx]
                
                # Fallback: Capture Primary Monitor (sct.monitors[1])
                # Note: sct.monitors[0] is 'All Monitors Combined' - good for context but maybe too big?
                # Sticking to Primary Monitor for consistency.
                if not region:
                    region = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                
                img = np.array(sct.grab(region))
            
            from PIL import Image
            import win32clipboard
            
            # Convert BGRA to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # Convert to BMP format for clipboard
            output = io.BytesIO()
            pil_img.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # Remove BMP header
            output.close()
            
            # Copy to clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            print(f"{Fore.GREEN}[+] Fresh full-screen image copied to clipboard!")
            return True
        except ImportError as e:
            print(f"{Fore.RED}[!] Missing module: {e.name}. Install with: pip install pywin32 pillow")
            return False
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to copy image: {e}")
            return False


    def wait_for_text(self, target_text, timeout=30):
        print(f"{Fore.YELLOW}[*] Waiting for text: '{target_text}' (Timeout: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            ui_data, txt = self.capture_and_scan()
            if target_text.lower() in txt.lower():
                print(f"{Fore.GREEN}[+] Text '{target_text}' detected!")
                return True
            time.sleep(1) # Poll every second
        print(f"{Fore.RED}[!] Timeout waiting for text.")
        return False


# --- 3. COGNITIVE PLANNER (ID SELECTOR) ---
class CognitivePlanner:
    def __init__(self, library_manager):
        from ollama import Client
        self.client = Client(host='http://localhost:11434')
        self.library = library_manager 

    def _extract_json(self, text: str) -> str:
        try:
            match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
            if match: return match.group(1)
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end != -1: return text[start:end+1]
            return text
        except: return text

    def _find_target_coords(self, goal: str, ui_data: List[Dict]) -> Optional[Tuple[int, int]]:
        goal_lower = goal.lower()
        if not any(x in goal_lower for x in ["click", "double", "right"]): return None
        target = goal_lower.replace("double click", "").replace("right click", "").replace("click", "").replace(" on ", "").strip()
        target = target.replace("[", "").replace("]", "")
        if not target: return None
        best_match, best_ratio = None, 0.0
        for item in ui_data:
            ui_text = item['text'].lower()
            if target == ui_text: return (item['x'], item['y'])
            ratio = difflib.SequenceMatcher(None, target, ui_text).ratio()
            if ratio > 0.8 and ratio > best_ratio:
                best_ratio = ratio; best_match = (item['x'], item['y'])
        return best_match


# --- 4. SESSION MANAGER (CONTEXT MEMORY) ---
class SessionManager:
    def __init__(self, session_file="sessions.json"):
        self.session_file = session_file
        self.sessions = self._load()
        self.active_recording = None 
        self.is_recording = False
        
    def _load(self):
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f: return json.load(f)
            except: return {}
        return {}

    def start_recording(self, name, description=""):
        self.active_recording = {"name": name, "description": description, "steps": []}
        self.is_recording = True
        print(f"{Fore.CYAN}[SESSION] Started recording: {name}")

    def record_step(self, cmd_id, cmd_data, keywords):
        # Filter keywords to keep only meaningful ones (len > 3, alphanumeric)
        clean_keywords = [k for k in keywords if len(k) > 3 and k.isalnum()][:20]
        args = cmd_data.get('args', '')
        
        # 1. Log to persistent text file (Command History)
        try:
            with open("recording.txt", "a", encoding="utf-8") as f:
                 f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] CMD: {cmd_id} | ARGS: {args} | KEYWORDS: {clean_keywords}\n")
        except Exception as e: print(f"{Fore.RED}[SESSION] Log error: {e}")

        # 2. Add to active recording buffer if enabled
        if self.is_recording:
            step = {
                "id": cmd_id,
                "args": args,
                "keywords": clean_keywords 
            }
            self.active_recording["steps"].append(step)
            print(f"{Fore.CYAN}[SESSION] Recorded step: {cmd_id} (Context: {clean_keywords[:3]}...)")

    def save_session(self):
        if not self.is_recording or not self.active_recording: return
        name = self.active_recording["name"]
        self.sessions[name] = self.active_recording
        with open(self.session_file, 'w') as f:
            json.dump(self.sessions, f, indent=4)
        self.is_recording = False
        self.active_recording = None
        print(f"{Fore.GREEN}[SESSION] Saved session: {name}")

    def get_session(self, name):
        return self.sessions.get(name)

    def verify_context(self, current_keywords, expected_keywords, threshold=0.3):
        if not expected_keywords: return True, 1.0
        current_set = set([k.lower() for k in current_keywords if len(k) > 3])
        expected_set = set([k.lower() for k in expected_keywords])
        if not expected_set: return True, 1.0
        
        intersection = current_set.intersection(expected_set)
        score = len(intersection) / len(expected_set)
        return score >= threshold, score

    def scan_for_suggestions(self, current_text):
        # Return list of session names found in text
        suggestions = []
        for name, data in self.sessions.items():
            if name.lower() in current_text.lower():
                suggestions.append(name)
        return suggestions

    def plan(self, goal: str, ui_data: List[Dict]) -> Tuple[str, bool]:
        goal_clean = goal.strip()
        
        # --- PARSE INLINE VARIABLE ---
        # Format: "command | variable content" OR "command $V1"
        inline_var = ""
        
        # 1. Standard Pipe Separator
        if "|" in goal_clean:
            parts = goal_clean.split("|", 1)
            goal_clean = parts[0].strip()
            inline_var = parts[1].strip()
            
            # Handle Quoted Variables (ignore garbage after quote)
            # Example: type | "hello" garbage -> var="hello"
            if inline_var.startswith('"') and '"' in inline_var[1:]:
                 end_quote = inline_var.find('"', 1)
                 inline_var = inline_var[1:end_quote]
                 if DEBUG_OCR: print(f"{Fore.YELLOW}[*] Extracted quoted var: '{inline_var}'")
        
        # 2. Handle common typo " I " instead of " | " (OCR error)
        elif " I " in goal_clean:
             # Heuristic: If it looks like "type I text", treat I as separator
             if goal_clean.lower().startswith(("type", "write", "search")):
                 parts = goal_clean.split(" I ", 1)
                 goal_clean = parts[0].strip()
                 inline_var = parts[1].strip()
                 print(f"{Fore.YELLOW}[*] Auto-Corrected 'I' to '|' separator")

        # Resolve any $V references in the variable
        inline_var = VAR_STORE.resolve(inline_var)
        
        # Also resolve $V references in the goal itself (e.g., "type $V1")
        var_ref_match = re.search(r'\$V(\d+)', goal_clean)
        if var_ref_match:
            inline_var = VAR_STORE.get(var_ref_match.group(1))
            goal_clean = re.sub(r'\$V\d+', '', goal_clean).strip()

        # --- LAYER 1: REFLEXES ---
        if goal_clean.lower().startswith(("cmd", "powershell", "echo")):
            print(f"{Fore.CYAN}[*] Reflex: Shell")
            # Escape quotes and backslashes for safe shell execution
            safe_goal = goal_clean.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            return f"subprocess.Popen('{safe_goal}', shell=True)", False

        # --- LAYER 2: SMART KEYWORD FILTER ---
        print(f"{Fore.MAGENTA}    [*] Smart Filter: Matching keywords...")
        
        cmds = self.library.library["commands"]
        if not cmds:
            print(f"{Fore.RED}    [!] Library empty.")
            return "", False

        # 1. Extract keywords from goal
        goal_words = set(goal_clean.lower().split())
        # Remove common stopwords
        stopwords = {'a', 'an', 'the', 'to', 'for', 'on', 'in', 'with', 'and', 'or', 'is', 'it', 'my', 'me', 'i'}
        goal_keywords = goal_words - stopwords
        
        # 2. Find commands matching keywords
        def match_score(cmd_name: str) -> int:
            """Higher score = better match"""
            cmd_words = set(cmd_name.lower().split())
            return len(goal_keywords & cmd_words)
        
        matched_cmds = {}
        for key, data in cmds.items():
            if not isinstance(data, dict): continue
            cid = data.get("id")
            if cid is None: continue
            
            score = match_score(key)
            # Also check description for matches
            desc = data.get("description", "").lower()
            desc_words = set(desc.split())
            score += len(goal_keywords & desc_words) // 2  # Half weight for description
            
            if score > 0:
                matched_cmds[str(cid)] = (key, data, score)
        
        # 3. If no matches, ask LLM to generate keywords
        if not matched_cmds:
            print(f"{Fore.YELLOW}    [*] No keyword matches. Asking AI for keywords...")
            try:
                kw_prompt = (
                    "Given this user goal, output 3-5 single-word keywords that might match automation commands.\n"
                    "Return JSON: {\"keywords\": [\"word1\", \"word2\", ...]}\n"
                    "Examples: 'open browser' → [\"open\", \"browser\", \"chrome\", \"web\"]\n"
                    "'save file' → [\"save\", \"file\", \"ctrl\", \"document\"]"
                )
                kw_res = self.client.chat(
                    model=MODEL_NAME,
                    messages=[{'role':'system','content':kw_prompt},{'role':'user','content':f"GOAL: {goal_clean}"}],
                    format='json',
                    options={'timeout': 15}
                )
                kw_data = json.loads(self._extract_json(kw_res['message']['content']))
                ai_keywords = set(kw.lower() for kw in kw_data.get("keywords", []))
                print(f"{Fore.CYAN}    [*] AI Keywords: {ai_keywords}")
                
                # Re-search with AI-generated keywords
                goal_keywords = ai_keywords
                for key, data in cmds.items():
                    if not isinstance(data, dict): continue
                    cid = data.get("id")
                    if cid is None: continue
                    
                    score = match_score(key)
                    desc = data.get("description", "").lower()
                    desc_words = set(desc.split())
                    score += len(goal_keywords & desc_words) // 2
                    
                    if score > 0:
                        matched_cmds[str(cid)] = (key, data, score)
                        
            except Exception as e:
                print(f"{Fore.YELLOW}    [!] Keyword generation failed: {e}")
        
        # 4. If still no matches, fall back to core commands
        if not matched_cmds:
            print(f"{Fore.YELLOW}    [*] Using core commands as fallback...")
            for key, data in cmds.items():
                if not isinstance(data, dict): continue
                cid = data.get("id")
                if cid and int(cid) < 200:  # Core commands are 101-107
                    matched_cmds[str(cid)] = (key, data, 0)
        
        # 5. Sort by score and limit to top 15 matches
        sorted_matches = sorted(matched_cmds.items(), key=lambda x: -x[1][2])[:15]
        
        # 6. Build prompt for AI
        id_map = {}
        prompt_list = []
        for cid_str, (cmd_key, cmd_data, score) in sorted_matches:
            id_map[cid_str] = cmd_key
            prompt_list.append(f"ID {cid_str}: {cmd_key}")
        
        print(f"{Fore.CYAN}    [*] Filtered to {len(prompt_list)} relevant commands")
        
        # 7. Ask AI to select from filtered list
        sys_prompt = (
            "You are a Command Selector. Match the GOAL to the best Command ID.\n"
            "If the goal implies content (e.g. 'type hello'), extract it into 'var'.\n"
            "Return JSON: {\"id\": <number>, \"var\": \"content\"}\n"
            f"COMMANDS:\n{chr(10).join(prompt_list)}"
        )
        
        # Retry logic for LLM calls
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                res = self.client.chat(
                    model=MODEL_NAME, 
                    messages=[{'role':'system','content':sys_prompt},{'role':'user','content':f"GOAL: {goal_clean}"}], 
                    format='json',
                    options={'timeout': 30}  # 30 second timeout
                )
                clean_json = self._extract_json(res['message']['content'])
                
                data = json.loads(clean_json)
                selected_id = str(data.get("id", ""))
                # Use inline_var from trigger, fallback to AI-extracted var if present
                variable = inline_var or data.get("var", "")
                
                if selected_id in id_map:
                    cmd_key = id_map[selected_id]
                    var_preview = variable[:30] + '...' if len(variable) > 30 else variable
                    print(f"{Fore.CYAN}[*] AI Selected: ID {selected_id} ({cmd_key}) | Var: {var_preview}")
                    
                    # 4. MULTI-VARIABLE INJECTION
                    raw_code = cmds[cmd_key]["code"]
                    
                    # First, handle __VAR__ (legacy single var from inline | or $V reference)
                    if "__VAR__" in raw_code:
                        if not variable:
                            print(f"{Fore.YELLOW}[!] Warning: Command '{cmd_key}' expects __VAR__ but none provided.")
                        safe_var = str(variable).replace("\\", "\\\\").replace("'", "\\'")
                        raw_code = raw_code.replace("__VAR__", safe_var)
                    
                    # Second, handle __VAR1__, __VAR2__, etc. from VAR_STORE
                    var_placeholders = re.findall(r'__VAR(\d+)__', raw_code)
                    for var_num in var_placeholders:
                        stored_val = VAR_STORE.get(var_num)
                        if not stored_val:
                            print(f"{Fore.YELLOW}[!] Warning: __VAR{var_num}__ expected but $V{var_num} not set.")
                        safe_val = str(stored_val).replace("\\", "\\\\").replace("'", "\\'")
                        raw_code = raw_code.replace(f"__VAR{var_num}__", safe_val)
                    
                    final_code = raw_code
                    
                    # 5. AUTO-AIM FALLBACK (If var exists but code doesn't use it)
                    if variable and "__VAR" not in cmds[cmd_key]["code"]:
                         # Check if it's a click command that needs auto-aim
                         if "click" in cmd_key:
                             print(f"{Fore.GREEN}[+] Passing '{variable}' to Auto-Aim...")
                             auto_coords = self._find_target_coords(f"click {variable}", ui_data)
                             if auto_coords:
                                 act = "rightClick" if "right" in cmd_key else "doubleClick" if "double" in cmd_key else "click"
                                 return f"pyautogui.{act}({auto_coords[0]}, {auto_coords[1]})", False
                             else:
                                 print(f"{Fore.RED}    [!] Auto-Aim failed: Could not find '{variable}' on screen.")
                                 return "pass", False # Do nothing safely
                    
                    return final_code, True
                else:
                    print(f"{Fore.RED}    [!] AI returned invalid ID: {selected_id}")
                    return "", False
                    
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < max_retries:
                    print(f"{Fore.YELLOW}[!] JSON parse failed, retrying... ({attempt + 1}/{max_retries})")
                    continue
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"{Fore.YELLOW}[!] LLM call failed: {type(e).__name__}: {e}, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(0.5)  # Brief pause before retry
                    continue
                    
        # All retries exhausted
        error_msg = str(last_error).replace(chr(39), chr(34)) if last_error else "Unknown error"
        return f"print('AI Error after {max_retries} retries: {error_msg}')", False

# --- 4. ACTION EXECUTOR ---
class ActionExecutor:
    def __init__(self, library_manager, session_manager=None):
        self.session_manager = session_manager
        self.library = library_manager
        self.locals = {"pyautogui": pyautogui, "subprocess": subprocess, "time": time, "os": os, "open_app": self._open_app_impl, "webbrowser": webbrowser}

    def _open_app_impl(self, app_name):
        if platform.system() == "Windows":
            subprocess.Popen(f"start {app_name}", shell=True)
        else:
            subprocess.Popen(["open", "-a", app_name])

    def execute(self, code: Union[str, List[str]], record=True, cmd_type="python", cmd_data=None) -> bool:
        globals()['LAST_ACTIVITY'] = time.time()
        success = False

        """
        Execute a command based on its type.
        Supported types: python, shell, hotkey, sequence, url, file
        """
        if not code and cmd_type == "python": return False
        
        print(f"{Fore.YELLOW}    -> Executing ({cmd_type})...")
        
        try:
            if cmd_type == "python":
                success = self._exec_python(code)
            elif cmd_type == "shell":
                success = self._exec_shell(code)
            elif cmd_type == "hotkey":
                success = self._exec_hotkey(cmd_data)
            elif cmd_type == "sequence":
                success = self._exec_sequence(cmd_data)
            elif cmd_type == "url":
                success = self._exec_url(cmd_data)
            elif cmd_type == "file":
                success = self._exec_file(cmd_data)
            else:
                print(f"{Fore.RED}Unknown execution type: {cmd_type}")
                success = False
        except Exception as e:
            print(f"{Fore.RED}Runtime Error ({cmd_type}): {e}")
            success = False
            
        # SESSION RECORDING HOOK
        # We log ALL successful commands to recording.txt, and to session JSON if recording is active.
        if success and record and self.session_manager:
            try:
                # Avoid recording if command is 'mew record' or 'mew save' (IDs > 200 usually safe, but check)
                # Checking PERCEPTION_ENGINE
                p = self.locals.get('PERCEPTION_ENGINE')
                if p:
                    print(f"{Fore.YELLOW}[SESSION] Capturing context...")
                    # Scan only text for speed? Or full scan.
                    _, txt = p.capture_and_scan()
                    self.session_manager.record_step(cmd_data.get('id') if cmd_data else 0, cmd_data or {}, txt.split())
            except Exception as e:
                print(f"{Fore.RED}[SESSION] Record error: {e}")
                
        return success

    def _exec_python(self, code: Union[str, List[str]]) -> bool:
        """Execute Python code using exec()"""
        if isinstance(code, list): code = "\n".join(code)
        if code.startswith("#PLAY_SESSION:"):
            name = code.split(":")[1]
            session = self.session_manager.get_session(name) if self.session_manager else None
            if session:
                for step in session.get("steps", []):
                    # Execute step
                    cmd_id = step["id"]
                    # Retrieve code for ID from library
                    cmd = self.library.get_command_by_id(cmd_id)
                    if cmd:
                        self.execute(cmd["code"], record=False, cmd_type=cmd["type"], cmd_data=step.get("args"))
                        
                        # Verify Context (Post-execution)
                        expected = step.get("keywords", [])
                        if expected and self.session_manager:
                            try:
                                p = self.locals.get('PERCEPTION_ENGINE')
                                if p:
                                    _, txt = p.capture_and_scan()
                                    curr_kw = txt.split()
                                    ok, score = self.session_manager.verify_context(curr_kw, expected)
                                    if not ok:
                                        print(f"{Fore.RED}[SESSION] Context Mismatch! Score: {score:.2f}. Stopping.")
                                        return False
                                    print(f"{Fore.GREEN}[SESSION] Context Verified (Score: {score:.2f})")
                            except Exception as e:
                                print(f"{Fore.RED}[SESSION] Verification error: {e}")
                    time.sleep(1.0)
            return True

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer): exec(code, self.locals, self.locals)
        print(f"{Fore.GREEN}RESULT: {buffer.getvalue().strip() or 'Success'}")

        return True

    def _exec_shell(self, code: str) -> bool:
        """Execute shell/PowerShell command"""
        result = subprocess.run(code, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"{Fore.GREEN}OUTPUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"{Fore.YELLOW}STDERR: {result.stderr.strip()}")
        print(f"{Fore.GREEN}RESULT: Exit code {result.returncode}")
        return result.returncode == 0

    def _exec_hotkey(self, data: dict) -> bool:
        """Execute keyboard hotkey - data: {"keys": ["ctrl", "c"]}"""
        keys = data.get("keys", [])
        if not keys:
            print(f"{Fore.RED}Hotkey error: No keys specified")
            return False
        pyautogui.hotkey(*keys)
        print(f"{Fore.GREEN}RESULT: Pressed {'+'.join(keys)}")
        return True

    def _exec_sequence(self, data: dict) -> bool:
        """Execute a sequence of command IDs - data: {"steps": [101, 106, 102], "delay": 0.5}"""
        steps = data.get("steps", [])
        delay = data.get("delay", 0.5)
        if not steps:
            print(f"{Fore.RED}Sequence error: No steps specified")
            return False
        
        for i, cmd_id in enumerate(steps):
            print(f"{Fore.CYAN}  Sequence step {i+1}/{len(steps)}: CMD_ID {cmd_id}")
            cmd = self.library.get_command_by_id(cmd_id)
            if cmd:
                cmd_type = cmd.get("type", "python")
                cmd_code = cmd.get("code", "")
                cmd_data = {k: v for k, v in cmd.items() if k not in ["id", "type", "code", "description"]}
                self.execute(cmd_code, True, cmd_type, cmd_data)
                if i < len(steps) - 1:
                    time.sleep(delay)
            else:
                print(f"{Fore.RED}  Command ID {cmd_id} not found")
        
        print(f"{Fore.GREEN}RESULT: Sequence complete ({len(steps)} steps)")
        return True

    def _exec_url(self, data: dict) -> bool:
        """Open URL in browser - data: {"url": "https://..."}"""
        url = data.get("url", "")
        if not url:
            print(f"{Fore.RED}URL error: No URL specified")
            return False
        webbrowser.open(url)
        print(f"{Fore.GREEN}RESULT: Opened {url}")
        return True

    def _exec_file(self, data: dict) -> bool:
        """Open file with default application - data: {"path": "C:/path/to/file"}"""
        path = data.get("path", "")
        if not path:
            print(f"{Fore.RED}File error: No path specified")
            return False
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        print(f"{Fore.GREEN}RESULT: Opened {path}")
        return True

# --- 5. SENTINEL ---
class PassiveSentinel:
    def __init__(self, perception: PerceptionEngine, planner: CognitivePlanner, executor: ActionExecutor):
        self.perception = perception
        self.planner = planner
        self.executor = executor
        self.executed_ids = set()
        self.text_history = collections.deque(maxlen=10)  # Increased buffer for long triggers
        self.pending_triggers = {}  # {id: partial_content} for triggers waiting for end delimiter

    def _execute_auto_rollback(self, cmd: str):
        """Auto-focus back to chat window if enabled. Skip for mew act and focus commands."""
        if not AUTO_ROLLBACK_ENABLED:
            return
        
        # Skip rollback for perception/focus commands (they don't navigate away)
        skip_commands = ["mew act", "mewact", "focus", "goto", "switch tab", "previous tab"]
        if any(skip in cmd.lower() for skip in skip_commands):
            return
        
        print(f"{Fore.CYAN}    [AUTO-ROLLBACK] Focusing back to {AUTO_ROLLBACK_CHAT}...")
        time.sleep(0.5)  # Brief pause before rollback
        
        # Execute the appropriate focus method
        if AUTO_ROLLBACK_CHAT == "tab":
            # Simple Ctrl+Tab for 2-tab setup
            pyautogui.hotkey('ctrl', 'tab')
            time.sleep(0.3)
        elif AUTO_ROLLBACK_CHAT.startswith("window:"):
            # Window mode: Use Windows API to find and focus window by title
            # Format: --auto-rollback window:ChatGPT or window:Gemini
            window_title = AUTO_ROLLBACK_CHAT.split(":", 1)[1]
            self._focus_window_by_title(window_title)
        else:
            # Tab search mode: Use Chrome tab search (Ctrl+Shift+A)
            pyautogui.hotkey('ctrl', 'shift', 'a')
            time.sleep(0.5)
            pyautogui.write(AUTO_ROLLBACK_CHAT, interval=0.02)
            time.sleep(0.3)
            pyautogui.press('enter')
            time.sleep(0.5)
        
        # Click input field at bottom center
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height - 100)
        print(f"{Fore.GREEN}    [AUTO-ROLLBACK] Focused on {AUTO_ROLLBACK_CHAT}")

    def _focus_window_by_title(self, title: str):
        """Focus a window by its title using Windows API."""
        user32 = ctypes.windll.user32
        
        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title.lower() in buff.value.lower():
                        user32.SetForegroundWindow(hwnd)
                        return False
            return True
        
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        time.sleep(0.5)

    def start(self):
        print(f"{Fore.YELLOW}[*] Sentinel Active.")
        print(f"{Fore.YELLOW}[*] Listening for triggers...")
        
        # --- STARTUP SCAN: Process triggers already visible on screen ---
        print(f"{Fore.CYAN}[*] Scanning for existing triggers on screen...")
        ui_data, txt = self.perception.capture_and_scan()
        if txt:
            VAR_STORE.parse_from_text(txt)
            matches = list(re.finditer(TRIGGER_PATTERN, txt))
            if matches:
                print(f"{Fore.GREEN}[!] Found {len(matches)} trigger(s) already on screen!")
                for m in matches:
                    cid_str, cmd = m.group(1), m.group(2).strip()
                    print(f"{Fore.GREEN}    >>> Startup Command #{cid_str}: {cmd}")
                    self.executed_ids.add(cid_str)
                    code, is_cached = self.planner.plan(cmd, ui_data)
                    # --- Handle Visual Wait (Startup) ---
                    if code and code.startswith("SYSTEM:WAIT_FOR_TEXT:"):
                        target_text = code.split(":", 2)[2]
                        self.perception.wait_for_text(target_text)
                        code = None # Prevent execution

                    if code and self.executor.execute(code):
                        self._execute_auto_rollback(cmd)
                        if self.planner.library.is_recording:
                            self.planner.library.record_action(cmd, code)
                        elif not is_cached:
                            self.planner.library.save_entry(cmd, code)
        print(f"{Fore.YELLOW}[*] Startup scan complete. Now monitoring for new triggers...")
        
        while True:
            try:
                ui_data, txt = self.perception.capture_and_scan()
                if not txt:
                    time.sleep(LOOP_DELAY)
                    continue

                if DEBUG_OCR: print(f"\n[DEBUG] Raw: {txt[:50]}...")
                
                # Parse any variable definitions from OCR text
                VAR_STORE.parse_from_text(txt)

                self.text_history.append(txt)
                buffered_text = " ".join(self.text_history)
                
                # --- HANDLE PARTIAL TRIGGERS ---
                # Check for triggers that started but haven't ended yet
                self._check_pending_triggers(txt, buffered_text)
                
                # --- STANDARD TRIGGER MATCHING ---
                matches = list(re.finditer(TRIGGER_PATTERN, buffered_text))
                
                valid_cmds = []
                for m in matches:
                    cid_str, cmd = m.group(1), m.group(2).strip()
                    if cid_str not in self.executed_ids:
                        valid_cmds.append((int(cid_str), cid_str, cmd))

                valid_cmds.sort(key=lambda x: x[0])

                if valid_cmds:
                    # --- Serial Execution (Force Re-Scan) ---
                    valid_cmds = valid_cmds[:1] # Process only the first command
                    print(f"\n{Fore.GREEN}[!] Detected {len(valid_cmds)} new command(s).")

                for cid_int, cid_str, cmd in valid_cmds:
                    print(f"{Fore.GREEN}    >>> Command #{cid_int}: {cmd}")
                    self.executed_ids.add(cid_str)
                    
                    code, is_cached = self.planner.plan(cmd, ui_data)
                    
                    if code and code.startswith("SYSTEM:WAIT_FOR_TEXT:"):
                        target_text = code.split(":", 2)[2]
                        self.perception.wait_for_text(target_text)
                        code = None # Prevent execution

                    # --- Handle Batch Execution (Notepad Notedown) ---
                    if code and code.startswith("SYSTEM:NOTEDOWN:"):
                        print(f"{Fore.CYAN}[NOTEDOWN] Starting Batch Execution...")
                        content = code.split(":", 2)[2]
                        subprocess.Popen('notepad'); time.sleep(1.0)
                        # Use ';;' as separator to allow '|' inside commands (e.g. 'type | text')
                        # Fallback to '|' only if ';;' is missing to support simple lists
                        separator = ';;' if ';;' in content else '|'
                        lines = [x.strip() for x in content.replace(separator, '\n').split('\n') if x.strip()]
                        for line in lines: pyautogui.write(line + '\n')
                        
                        for i, cmd_text in enumerate(lines):
                            print(f"{Fore.CYAN}    [BATCH {i+1}/{len(lines)}] {cmd_text}")
                            batch_ui, _ = self.perception.capture_and_scan() # Fresh scan
                            batch_code, _ = self.planner.plan(cmd_text, batch_ui)
                            if batch_code and not batch_code.startswith("SYSTEM:") and self.executor.execute(batch_code):
                                self._execute_auto_rollback(cmd_text)
                        code = None # Done handling

                    if code and self.executor.execute(code):
                        # Auto-rollback to chat window if enabled
                        self._execute_auto_rollback(cmd)
                        
                        if self.planner.library.is_recording:
                            self.planner.library.record_action(cmd, code)
                        elif not is_cached:
                            self.planner.library.save_entry(cmd, code)
                            
                time.sleep(LOOP_DELAY)
            except KeyboardInterrupt: break

    def _check_pending_triggers(self, current_txt: str, buffered_text: str):
        """Handle triggers that span multiple screen views."""
        # Look for trigger starts without ends
        # Format: <ID>&&$47 ...
        start_pattern = r"(\d+)&&\$47\s*([^\$]*?)$"
        
        # Check if current text has an incomplete trigger at the end
        start_match = re.search(start_pattern, buffered_text)
        if start_match:
            cid = start_match.group(1)
            partial_cmd = start_match.group(2)
            
            # Only track if we don't already have this as pending and it's not executed
            if cid not in self.pending_triggers and cid not in self.executed_ids:
                # Verify this isn't already a complete trigger
                # We construct the specific end tag for this ID: ID$&47
                end_tag = f"{cid}$&47"
                if end_tag not in buffered_text:
                    self.pending_triggers[cid] = partial_cmd
                    print(f"{Fore.YELLOW}[*] Partial trigger #{cid} detected, waiting for end...")
        
        # Check if any pending triggers now have their end visible
        for cid in list(self.pending_triggers.keys()):
            # Look for end delimiter WITH MATCHING ID in current text
            # Pattern: (content) <ID>$&47
            end_match = re.search(r"(.*?)" + re.escape(cid) + r"\$&47", current_txt)
            if end_match:
                # Complete the pending trigger
                full_cmd = (self.pending_triggers[cid] + " " + end_match.group(1)).strip()
                if cid not in self.executed_ids:
                    print(f"{Fore.GREEN}[!] Completed pending trigger #{cid}: {full_cmd[:50]}...")
                    # Store for processing in next cycle (it will match the full pattern now)
                del self.pending_triggers[cid]

def complex_mew_act(exec_locals):
    print(f"{Fore.CYAN}[*] Executing Complex Mew Act Routine...")
    p = exec_locals.get('PERCEPTION_ENGINE')
    pyautogui, ctypes, time = exec_locals['pyautogui'], exec_locals['ctypes'], exec_locals['time']
    
    # 1. Focus Anchor
    if 'ANCHOR_HWND' in exec_locals:
        try:
            hwnd = exec_locals['ANCHOR_HWND']
            current_hwnd = ctypes.windll.user32.GetForegroundWindow()
            if current_hwnd != hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.5)
            if 'ANCHOR_POS' in exec_locals:
                pyautogui.click(exec_locals['ANCHOR_POS'])
            time.sleep(0.5)
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to focus anchor: {e}")

    # 2. Capture & Copy
    if p: 
        p.copy_last_image_to_clipboard()
        # SESSION SUGGESTION LOGIC
        try:
            sess_mgr = exec_locals.get('session_manager')
            if sess_mgr:
                _, txt = p.capture_and_scan()
                suggestions = sess_mgr.scan_for_suggestions(txt)
                if suggestions:
                    s_name = suggestions[0]
                    print(f"{Fore.GREEN}[SESSION] Found match: '{s_name}'")
                    # fetch steps
                    steps = sess_mgr.get_session(s_name).get('steps', [])
                    # Format for AI
                    summary = " | ".join([f"{s['id']}:{s['args']}" for s in steps])
                    msg = f"[MEMORY] Found session '{s_name}'. Steps: {summary}"
                    
                    # Type message before pasting image
                    pyautogui.write(msg)
                    time.sleep(0.5)
                    pyautogui.press('enter')
                    time.sleep(0.5)
        except Exception as e: print(f"{Fore.RED}[!] Suggestion error: {e}")
    time.sleep(1.0)

    # 3. Paste
    pyautogui.hotkey('ctrl', 'v')
    print(f"{Fore.YELLOW}[*] Waiting for image upload stability...")
    time.sleep(3.5) 

    # 4. Try sending via Enter
    pyautogui.press('enter')
    time.sleep(1.0)

    # 5. Fallback: If 'Send' button remains visible, click it
    # (This assumes Enter might have failed or just made a newline)
    if p:
        try:
            print(f"{Fore.YELLOW}[*] Verifying submission logic...")
            # We assume if Enter worked, input box cleared or sent.
            # We can't know for sure without diffing.
            # But user request: "if enter does job of /n... it clicks send"
            # So we check if 'Send' button is visible.
            ui, txt = p.capture_and_scan()
            send_btn = next((item for item in ui if 'send' in item['text'].lower() or 'submit' in item['text'].lower()), None)

            if send_btn:
                # If found, check if it looks clickable (not disabled)? Hard with OCR.
                # Just try clicking it.
                print(f"{Fore.GREEN}[+] 'Send' button detected at ({send_btn['x']}, {send_btn['y']}). Clicking...")
                pyautogui.click(send_btn['x'], send_btn['y'])
            else:
                # No 'Send' button found. Maybe Enter worked or it's an icon.
                pass
        except Exception as e:
            print(f"{Fore.RED}[!] Send fallback error: {e}")

def main():
    """Main entry point for CLI execution."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, help="Target window title")
    parser.add_argument("--monitors", type=str, help="Monitor indices (comma-separated, e.g., '1' or '1,2')")
    parser.add_argument("--ocr", choices=["rapidocr", "easyocr", "paddleocr"], help="Choose OCR engine")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for OCR (EasyOCR/PaddleOCR only)")
    parser.add_argument("--auto-rollback", type=str, metavar="CHAT", 
                        help="Auto-focus back to chat window after commands. Values: gemini, chatgpt, claude, tab, window:<title>")
    parser.add_argument("--power-saver", action="store_true", help="Enable Adaptive/Scattered OCR mode for low-end PCs")
    parser.add_argument("--idle-timeout", type=int, default=0, help="Enable Idle Watchdog with specific timeout (seconds)")
    
    parser.add_argument("--scan-mode", choices=["monitor", "window"], default="monitor", help="Scan Mode: monitor (default) or window (iterates all windows)")
    parser.add_argument("--monitor-strategy", choices=["full", "window"], default="full", help="Monitor Strategy: full (default) or window (iterates windows on monitor)")
    
    args = parser.parse_args()
    
    # Use globals() dict to modify module-level variables (avoids global declaration issues)
    if args.ocr:
        globals()['OCR_ENGINE'] = args.ocr
        print(f"{Fore.CYAN}[*] CLI OCR Override: {args.ocr}")
    
    if args.gpu:
        globals()['OCR_USE_GPU'] = True
        print(f"{Fore.CYAN}[*] GPU Mode: Enabled for OCR")
        
    if args.power_saver:
        globals()['OCR_ADAPTIVE_MODE'] = True
        print(f"{Fore.CYAN}[*] Power Saver Mode: Enabled (Adaptive/Scattered OCR)")

    # Set scan modes from CLI
    globals()['OCR_SCAN_MODE'] = args.scan_mode
    globals()['OCR_MONITOR_STRATEGY'] = args.monitor_strategy
    
    if args.target:
        globals()['TARGET_WINDOW_TITLE'] = args.target
        print(f"{Fore.CYAN}[*] CLI Target: '{args.target}'")
    
    if args.monitors:
        globals()['TARGET_MONITORS'] = [int(m.strip()) for m in args.monitors.split(',') if m.strip().isdigit()]
        print(f"{Fore.CYAN}[*] CLI Monitors: {globals()['TARGET_MONITORS']}")
    
    if args.auto_rollback:
        globals()['AUTO_ROLLBACK_ENABLED'] = True
        globals()['AUTO_ROLLBACK_CHAT'] = args.auto_rollback.lower()
        print(f"{Fore.CYAN}[*] AUTO-ROLLBACK ENABLED: Will focus back to '{args.auto_rollback.lower()}' after each command")

    if args.idle_timeout > 0:
        globals()['IDLE_TIMEOUT'] = args.idle_timeout
        print(f"{Fore.CYAN}[*] IDLE WATCHDOG ENABLED: Timeout {args.idle_timeout}s")
    
    if not args.target and not args.monitors:
        print(f"{Fore.CYAN}--- JAM A.I. ID-Selector Mode ---")
        print("  [1] All Monitors")
        print("  [2] Specific Window")
        print("  [3] Specific Monitor(s)")
        try: mode = input("Choice: ").strip()
        except: mode = "1"
        
        if mode == "2":
            wc_temp = WindowCapture()
            print(f"{Fore.YELLOW}[*] Scanning windows...")
            wins = wc_temp.list_windows()
            valid_wins = [w[1] for w in wins]
            
            if not valid_wins: print(f"{Fore.RED}[!] No windows.")
            else:
                for i, title in enumerate(valid_wins): print(f"  [{i+1}] {title}")
                try:
                    sel = int(input(f"Select ID: ").strip())
                    if 1 <= sel <= len(valid_wins):
                        globals()['TARGET_WINDOW_TITLE'] = valid_wins[sel-1]
                        print(f"{Fore.CYAN}[*] Targeted: '{valid_wins[sel-1]}'")
                except: pass
        
        elif mode == "3":
            with mss.mss() as sct:
                print(f"{Fore.YELLOW}[*] Available monitors:")
                for i, mon in enumerate(sct.monitors[1:], 1):
                    print(f"  [{i}] {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})")
                try:
                    sel = input("Enter monitor(s) (comma-separated, e.g., '1' or '1,2'): ").strip()
                    globals()['TARGET_MONITORS'] = [int(m.strip()) for m in sel.split(',') if m.strip().isdigit()]
                    print(f"{Fore.CYAN}[*] Targeted monitors: {globals()['TARGET_MONITORS']}")
                except: pass

    lib_mgr = LibraryManager() 
    p = PerceptionEngine()
    
    # Expose globally for mew act command
    global PERCEPTION_ENGINE
    PERCEPTION_ENGINE = p
    
    b = CognitivePlanner(lib_mgr) 
    session_mgr = SessionManager()
    h = ActionExecutor(lib_mgr, session_manager=session_mgr)
    
    # Add perception engine to executor locals for mew act command
    h.locals["PERCEPTION_ENGINE"] = p
    h.locals["complex_mew_act"] = complex_mew_act
    h.locals["session_manager"] = session_mgr
    
    # Start Watchdog if enabled
    if globals().get('IDLE_TIMEOUT', 0) > 0:
        wd = IdleWatchdog(h, globals()['IDLE_TIMEOUT'])
        wd.start()
    
    PassiveSentinel(p, b, h).start()


if __name__ == "__main__":
    main()