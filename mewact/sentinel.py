
import threading
import time
import re
import subprocess
import pyautogui
from colorama import Fore

from .config import print, LOOP_DELAY, DEBUG_OCR, TRIGGER_PATTERN
from .memory import VAR_STORE

# --- WATCHDOG THREAD ---
class IdleWatchdog(threading.Thread):
    def __init__(self, executor, timeout):
        from . import config # Late import to get current global value
        super().__init__(daemon=True)
        self.executor = executor
        self.timeout = timeout
        self.triggered = False

    def run(self):
        from . import config # Late import
        print(f"{Fore.CYAN}[*] Watchdog started (Timeout: {self.timeout}s)")
        while True:
            time.sleep(1.0)
            if self.timeout <= 0: continue
            
            idle_time = time.time() - config.LAST_ACTIVITY
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

class PassiveSentinel:
    def __init__(self, perception_engine, planner, executor):
        self.perception = perception_engine
        self.planner = planner
        self.executor = executor
        self.executed_ids = set() # Track executed IDs to prevent loops
        self.pending_triggers = {} # {id: "start command..."}
        self.text_history = [] 

    def _execute_auto_rollback(self, cmd_name):
        from . import config
        if config.AUTO_ROLLBACK_ENABLED:
            target = config.AUTO_ROLLBACK_CHAT
            print(f"{Fore.MAGENTA}[*] Rollback -> Focusing '{target}'...")
            if target in ["gemini", "chatgpt", "claude"]:
                 # Just type 'alt+tab'? Or find window?
                 # Finding window is safer.
                 # Assuming browser is open.
                 rect = self.perception.win_cap.get_window_rect(target) # Simple title match
                 # If not found, maybe generic browser
                 if not rect:
                     # Generic fallback: Search for *common* browser titles?
                     pass
                 
                 # Force focus
                 if rect:
                     # How to focus from rect? need hwnd.
                     # Re-use focus window logic if available.
                     # For now, simplistic approach:
                     pass
            
            # Simple Tab Switch for now as per user request flow
            if target == "tab":
                pyautogui.hotkey('ctrl', 'tab')

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
                from . import config
                ui_data, txt = self.perception.capture_and_scan()
                config.LAST_ACTIVITY = time.time() # Update activity for Watchdog

                if not txt:
                    time.sleep(LOOP_DELAY)
                    continue

                if DEBUG_OCR: print(f"\n[DEBUG] Raw: {txt[:50]}...")
                
                # Parse any variable definitions from OCR text
                VAR_STORE.parse_from_text(txt)

                self.text_history.append(txt)
                if len(self.text_history) > 5: self.text_history.pop(0) # Keep buffer small
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
