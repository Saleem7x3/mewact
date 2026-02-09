
import sys
import os
import json
from colorama import init, Fore

init(autoreset=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import mewact.config as config
# Force Active Mode for training to use Ollama
config.ACTIVE_MODE = True

try:
    from mewact.memory_engine import VectorMemory
    from mewact.memory import LibraryManager

    print(f"{Fore.CYAN}[*] Initializing Memory Training...")
    
    # Check Ollama
    try:
        import ollama
        ollama.embeddings(model="nomic-embed-text", prompt="test")
        print(f"{Fore.GREEN}[+] Ollama (nomic-embed-text) is ready.")
    except Exception as e:
        print(f"{Fore.RED}[!] Ollama Error: {e}")
        print(f"{Fore.YELLOW}[!] Please run: ollama pull nomic-embed-text")
        sys.exit(1)

    lib_mgr = LibraryManager()
    memory = VectorMemory()
    
    print(f"{Fore.CYAN}[*] Loading {len(lib_mgr.library)} commands from library...")
    
    count = 0
    for cmd_id, cmd_data in lib_mgr.library.items():
        desc = cmd_data.get('description', '')
        if not desc: continue
        
        # Create a rich text representation for embedding
        # "Open Notepad" -> "Open Notepad application tool editor"
        text = f"{desc} {cmd_data.get('category', '')} {cmd_data.get('tags', '')}"
        
        success = memory.add(text, metadata={"id": cmd_id, "command": cmd_data})
        if success:
            count += 1
            print(f"\rTraining: {count}/{len(lib_mgr.library)}", end="")
            
    print(f"\n{Fore.GREEN}[+] Training Complete! Added {count} items to memory_store.json")

except Exception as e:
    print(f"{Fore.RED}[!] Error: {e}")
