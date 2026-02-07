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

# --- AUTO-ROLLBACK CONFIG ---
# When enabled, automatically focuses back to chat window after each command
AUTO_ROLLBACK_ENABLED = False
AUTO_ROLLBACK_CHAT = "gemini"  # "gemini", "chatgpt", "claude", or "tab" for generic tab switch

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
        print(f"{Fore.CYAN}[*] Initialization: {self.ocr_engine.upper()} Engine")
        
        # --- ENGINE INITIALIZATION ---
        if self.ocr_engine == "easyocr":
            try:
                import easyocr
                # This will download models on first run
                self.ocr = easyocr.Reader(['en'], gpu=False)
            except ImportError:
                print(f"{Fore.YELLOW}[!] EasyOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        elif self.ocr_engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                # use_angle_cls=True for better text orientation detection
                self.ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            except ImportError:
                print(f"{Fore.YELLOW}[!] PaddleOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        # Default / Fallback
        if self.ocr_engine == "rapidocr":
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR(det_use_gpu=False, cls_use_gpu=False, rec_use_gpu=False, intra_op_num_threads=4)
            
        self.win_cap = WindowCapture()
        self.last_image = None  # Store last captured image for clipboard
        with mss.mss() as sct:
            self.monitors = sct.monitors[1:] if len(sct.monitors) > 2 else [sct.monitors[1]]

    def capture_and_scan(self):
        time.sleep(0.1) 
        try:
            with mss.mss() as sct:
                all_ui_data = [] 
                all_txt_parts = []
                capture_regions = []
                
                if TARGET_WINDOW_TITLE:
                    rect = self.win_cap.get_window_rect(TARGET_WINDOW_TITLE)
                    if rect: capture_regions = [rect]
                    else:
                        if DEBUG_OCR: print(f"{Fore.RED}[!] Target window '{TARGET_WINDOW_TITLE}' not found.")
                        return [], "" 
                else:
                    # Monitor selection: use TARGET_MONITORS if specified, else all
                    if TARGET_MONITORS:
                        all_mons = sct.monitors  # Index 0 is virtual, 1+ are real monitors
                        capture_regions = [all_mons[i] for i in TARGET_MONITORS if i < len(all_mons)]
                        if not capture_regions:
                            print(f"{Fore.YELLOW}[!] Invalid monitor indices: {TARGET_MONITORS}. Using all.")
                            capture_regions = sct.monitors[1:] if len(sct.monitors) > 2 else [sct.monitors[1]]
                    else:
                        capture_regions = sct.monitors[1:] if len(sct.monitors) > 2 else [sct.monitors[1]]

                for i, region in enumerate(capture_regions):
                    try:
                        img = np.array(sct.grab(region))
                        self.last_image = img.copy()  # Store for mew act command
                        
                        # --- OCR PROCESSING ---
                        if self.ocr_engine == "easyocr":
                            # EasyOCR prefers RGB
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                            results = self.ocr.readtext(img_rgb)
                            for (bbox, text, prob) in results:
                                if prob < 0.2: continue
                                # bbox format: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                                cx = int((bbox[0][0] + bbox[2][0]) / 2) + region["left"]
                                cy = int((bbox[0][1] + bbox[2][1]) / 2) + region["top"]
                                all_ui_data.append({"text": text, "x": cx, "y": cy})
                                all_txt_parts.append(text)
                                
                        elif self.ocr_engine == "paddleocr":
                            # PaddleOCR expects image path or numpy array (RGB)
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                            result = self.ocr.ocr(img_rgb, cls=True)
                            # Result structure: [ [ [ [x1,y1], [x2,y2]... ], (text, confidence) ], ... ]
                            if result and result[0]:
                                for line in result[0]:
                                    box = line[0]
                                    text, score = line[1]
                                    if score < 0.5: continue
                                    
                                    cx = int((box[0][0] + box[2][0]) / 2) + region["left"]
                                    cy = int((box[0][1] + box[2][1]) / 2) + region["top"]
                                    all_ui_data.append({"text": text, "x": cx, "y": cy})
                                    all_txt_parts.append(text)
                                    
                        else:
                            # RapidOCR (Default)
                            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                            result, _ = self.ocr(gray)
                            if result:
                                for item in result:
                                    box, text, _ = item
                                    all_txt_parts.append(text)
                                    cx = int(((box[0][0] + box[2][0]) / 2)) + region["left"]
                                    cy = int(((box[0][1] + box[2][1]) / 2)) + region["top"]
                                    all_ui_data.append({"text": text, "x": cx, "y": cy})
                        all_ui_data.append({"text": text, "x": cx, "y": cy})
                    except: continue
                
                full_text = " ".join(all_txt_parts)
                # --- NORMALIZE "STYLISH" FONTS ---
                # Chatbots sometimes output mathematical bold/italic unicode (e.g. 𝐇𝐞𝐥𝐥𝐨)
                full_text = unicodedata.normalize('NFKD', full_text).encode('ascii', 'ignore').decode('utf-8')
                
                return all_ui_data, full_text
        except: return [], ""

    def copy_last_image_to_clipboard(self) -> bool:
        """Copy the last captured OCR image to Windows clipboard."""
        if self.last_image is None:
            print(f"{Fore.RED}[!] No image captured yet.")
            return False
        try:
            from PIL import Image
            import win32clipboard
            
            # Convert BGRA to RGB
            img_rgb = cv2.cvtColor(self.last_image, cv2.COLOR_BGRA2RGB)
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
            
            print(f"{Fore.GREEN}[+] Image copied to clipboard! You can paste it now.")
            return True
        except ImportError as e:
            print(f"{Fore.RED}[!] Missing module: {e.name}. Install with: pip install pywin32 pillow")
            return False
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to copy image: {e}")
            return False


# --- 3. COGNITIVE PLANNER (ID SELECTOR) ---
class CognitivePlanner:
    def __init__(self, library_manager):
        import ollama
        self.client = ollama
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
    def __init__(self, library_manager):
        self.library = library_manager
        self.locals = {"pyautogui": pyautogui, "subprocess": subprocess, "time": time, "os": os, "open_app": self._open_app_impl, "webbrowser": webbrowser}

    def _open_app_impl(self, app_name):
        if platform.system() == "Windows":
            subprocess.Popen(f"start {app_name}", shell=True)
        else:
            subprocess.Popen(["open", "-a", app_name])

    def execute(self, code: Union[str, List[str]], record=True, cmd_type="python", cmd_data=None) -> bool:
        """
        Execute a command based on its type.
        Supported types: python, shell, hotkey, sequence, url, file
        """
        if not code and cmd_type == "python": return False
        
        print(f"{Fore.YELLOW}    -> Executing ({cmd_type})...")
        
        try:
            if cmd_type == "python":
                return self._exec_python(code)
            elif cmd_type == "shell":
                return self._exec_shell(code)
            elif cmd_type == "hotkey":
                return self._exec_hotkey(cmd_data)
            elif cmd_type == "sequence":
                return self._exec_sequence(cmd_data)
            elif cmd_type == "url":
                return self._exec_url(cmd_data)
            elif cmd_type == "file":
                return self._exec_file(cmd_data)
            else:
                print(f"{Fore.RED}Unknown execution type: {cmd_type}")
                return False
        except Exception as e:
            print(f"{Fore.RED}Runtime Error ({cmd_type}): {e}")
            return False

    def _exec_python(self, code: Union[str, List[str]]) -> bool:
        """Execute Python code using exec()"""
        if isinstance(code, list): code = "\n".join(code)
        if code.startswith("#PLAY_SESSION:"):
            name = code.split(":")[1]
            for s in self.library.sessions.get(name, []):
                time.sleep(s['pause']); self._exec_python(s['code'])
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
                    code, is_cached = self.planner.plan(cmd)
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
                    print(f"\n{Fore.GREEN}[!] Detected {len(valid_cmds)} new command(s).")

                for cid_int, cid_str, cmd in valid_cmds:
                    print(f"{Fore.GREEN}    >>> Command #{cid_int}: {cmd}")
                    self.executed_ids.add(cid_str)
                    
                    code, is_cached = self.planner.plan(cmd, ui_data)
                    
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, help="Target window title")
    parser.add_argument("--monitors", type=str, help="Monitor indices (comma-separated, e.g., '1' or '1,2')")
    parser.add_argument("--ocr", choices=["rapidocr", "easyocr", "paddleocr"], help="Choose OCR engine")
    parser.add_argument("--auto-rollback", type=str, metavar="CHAT", 
                        help="Auto-focus back to chat window after commands. Values: gemini, chatgpt, claude, tab, window:<title>")
    args = parser.parse_args()
    
    if args.ocr:
        OCR_ENGINE = args.ocr
        print(f"{Fore.CYAN}[*] CLI OCR Override: {OCR_ENGINE}")

    if args.target:
        TARGET_WINDOW_TITLE = args.target
        print(f"{Fore.CYAN}[*] CLI Target: '{TARGET_WINDOW_TITLE}'")
    
    if args.monitors:
        TARGET_MONITORS = [int(m.strip()) for m in args.monitors.split(',') if m.strip().isdigit()]
        print(f"{Fore.CYAN}[*] CLI Monitors: {TARGET_MONITORS}")
    
    if args.auto_rollback:
        AUTO_ROLLBACK_ENABLED = True
        AUTO_ROLLBACK_CHAT = args.auto_rollback.lower()
        print(f"{Fore.CYAN}[*] AUTO-ROLLBACK ENABLED: Will focus back to '{AUTO_ROLLBACK_CHAT}' after each command")
    
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
                        TARGET_WINDOW_TITLE = valid_wins[sel-1]
                        print(f"{Fore.CYAN}[*] Targeted: '{TARGET_WINDOW_TITLE}'")
                except: pass
        
        elif mode == "3":
            with mss.mss() as sct:
                print(f"{Fore.YELLOW}[*] Available monitors:")
                for i, mon in enumerate(sct.monitors[1:], 1):
                    print(f"  [{i}] {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})")
                try:
                    sel = input("Enter monitor(s) (comma-separated, e.g., '1' or '1,2'): ").strip()
                    TARGET_MONITORS = [int(m.strip()) for m in sel.split(',') if m.strip().isdigit()]
                    print(f"{Fore.CYAN}[*] Targeted monitors: {TARGET_MONITORS}")
                except: pass

    lib_mgr = LibraryManager() 
    p = PerceptionEngine()
    
    # Expose globally for mew act command
    global PERCEPTION_ENGINE
    PERCEPTION_ENGINE = p
    
    b = CognitivePlanner(lib_mgr) 
    h = ActionExecutor(lib_mgr)
    
    # Add perception engine to executor locals for mew act command
    h.locals["PERCEPTION_ENGINE"] = p
    
    PassiveSentinel(p, b, h).start()