
import sys
import os
import time
from colorama import init, Fore

init(autoreset=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. Enable Active Mode Programmatically

import mewact.config as config
config.ACTIVE_MODE = True
print(f"{Fore.CYAN}[*] Active Mode Enabled via Script override.")

# 2. Test Import
try:
    from mewact.active_vision import ActiveVisionEngine
    print(f"{Fore.GREEN}[+] ActiveVision module imported successfully.")
    
    vlm = ActiveVisionEngine()
    
    # 3. Test Description (Requires Ollama)
    print(f"{Fore.CYAN}[*] Attempting description (Active Mode)...")
    result = vlm.describe_screen()
    
    if "Error" in result:
        print(f"{Fore.RED}[!] Result: {result}")
        print(f"{Fore.YELLOW}[!] Hint: Did you run 'ollama serve'?")
    else:
        print(f"{Fore.GREEN}[+] Success!")
        print(f"    Desc: {result[:100]}...")

except ImportError as e:
    print(f"{Fore.RED}[!] Import Error: {e}")
except Exception as e:
    print(f"{Fore.RED}[!] Unexpected Error: {e}")
