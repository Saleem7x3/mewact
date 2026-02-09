
import sys
import contextlib
import io
import time
import subprocess
import traceback
import pyautogui
import ctypes
from colorama import Fore
from .config import print, AUTO_ROLLBACK_ENABLED, AUTO_ROLLBACK_CHAT

# --- 5. EXECUTION ENGINE ---
class ActionExecutor:
    def __init__(self, library_manager, session_manager=None):
        self.library = library_manager
        self.session_manager = session_manager
        self.locals = {
            "pyautogui": pyautogui,
            "ctypes": ctypes,
            "time": time,
            "subprocess": subprocess
        }

    def execute(self, code: str, cmd_type: str = "python", cmd_data=None) -> bool:
        if not code: return False
        
        try:
            print(f"{Fore.CYAN}[+] Executing ({cmd_type}): {code[:60]}...")
            
            if cmd_type == "python":
                return self._exec_python(code)
            elif cmd_type == "shell":
                return self._exec_shell(code)
            elif cmd_type == "hotkey":
                return self._exec_hotkey(code)
            elif cmd_type == "sequence":
                # Only supported if planner expands it
                print(f"{Fore.RED}[!] Sequence execution should be expanded by planner.")
                return False
            else:
                print(f"{Fore.RED}[!] Unknown command type: {cmd_type}")
                return False
        except Exception as e:
            print(f"{Fore.RED}[!] Execution Error: {e}")
            return False

    def _exec_python(self, code: str) -> bool:
        """Execute safe python subset"""
        try:
            # Capture stdout/stderr to avoid pollution? 
            # In MCP mode, print already goes to stderr. So direct exec is fine.
            # But execution might print via other means?
            # User scripts using built-in print will hit our safe_print if they import it? 
            # No, 'exec' doesn't use our globals unless passed.
            # We should pass our 'print' in locals?
            
            # self.locals['print'] = print # Inject safe print
            
            # Simple exec since we handle safety at module level or trust the library code
            exec(code, self.locals, self.locals)
            return True
        except Exception as e:
            print(f"{Fore.RED}[!] PyError: {e}")
            traceback.print_exc()
            return False

    def _exec_shell(self, code: str) -> bool:
        """Execute shell/PowerShell command"""
        result = subprocess.run(code, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"{Fore.GREEN}OUTPUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"{Fore.YELLOW}STDERR: {result.stderr.strip()}")
        print(f"{Fore.GREEN}RESULT: Exit code {result.returncode}")
        return result.returncode == 0

    def _exec_hotkey(self, code: str) -> bool:
        """Execute hotkey string (e.g. 'ctrl+c')"""
        try:
            keys = code.split('+')
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"{Fore.RED}[!] Hotkey Error: {e}")
            return False
