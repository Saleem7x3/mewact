
import sys
import os
import json
from colorama import init, Fore

init(autoreset=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mewact.config as config

config.ACTIVE_MODE = True # Enable Eye for context
config.PLANNER_MODEL = "mistral" # Ensure we use a capable model

try:
    from mewact.memory import LibraryManager
    from mewact.planning import CognitivePlanner
    
    print(f"{Fore.CYAN}[*] Initializing Autonomy Engine...")
    lib = LibraryManager()
    planner = CognitivePlanner(lib)

    goal = "Open Notepad and type 'Hello World'"
    print(f"\n{Fore.YELLOW}GOAL: {goal}")
    
    plan = planner.plan_goal(goal)
    
    print(f"\n{Fore.GREEN}[+] Final Plan:")
    print(json.dumps(plan, indent=2))

except ImportError as e:
    print(f"{Fore.RED}[!] Import Error: {e}")
except Exception as e:
    print(f"{Fore.RED}[!] Error: {e}")
