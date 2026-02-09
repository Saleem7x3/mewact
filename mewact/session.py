
import json
import os
import time
from colorama import Fore
from .config import print

# --- 4. SESSION MANAGER (CONTEXT MEMORY) ---
class SessionManager:
    def __init__(self, session_file=None):
        from .config import SESSION_FILE as DEFAULT_SESSION_FILE
        self.session_file = session_file if session_file else DEFAULT_SESSION_FILE
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
