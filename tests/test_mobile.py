
import sys
import os
import time
from colorama import init, Fore

init(autoreset=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mewact.config as config
config.MOBILE_ENABLED = True # Force enable for test

try:
    from mewact.mobile import MobileController
    
    print(f"{Fore.CYAN}[*] Initializing Mobile Controller...")
    mobile = MobileController()
    
    if mobile.device_id:
        print(f"{Fore.GREEN}[+] Device Connected: {mobile.device_id}")
        
        print(f"{Fore.CYAN}[*] Capturing screen...")
        img = mobile.capture_screen()
        if img:
            print(f"{Fore.GREEN}[+] Screen captured: {img.size} format={img.format}")
        else:
            print(f"{Fore.RED}[!] Screen capture failed.")
            
        # Optional: Test Home Button
         # print("[*] Pressing Home...")
         # mobile.home()
         
    else:
        print(f"{Fore.YELLOW}[!] No device found. Please connect Android phone via USB and enable Debugging.")
        print(f"    check 'adb devices' in terminal.")

except ImportError as e:
    print(f"{Fore.RED}[!] Import Error: {e}")
except Exception as e:
    print(f"{Fore.RED}[!] Error: {e}")
