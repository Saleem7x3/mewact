
import json
import os
import re
import time
import random
from typing import Dict, Optional
from colorama import Fore

from .config import print, VAR_PATTERN, LIBRARY_FILE, SESSION_FILE

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
    def __init__(self, lib_path=None):
        self.lib_path = lib_path if lib_path else LIBRARY_FILE
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
