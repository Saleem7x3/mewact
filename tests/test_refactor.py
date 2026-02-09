
import sys
import os
import traceback

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


print("[-] Testing imports...")

try:
    import mewact
    print("[+] Import mewact: OK")
except Exception as e:
    print(f"[!] Failed to import mewact: {e}")
    traceback.print_exc()

try:
    from mewact import config
    print("[+] Import config: OK")
    print(f"    OCR_ENGINE: {config.OCR_ENGINE}")
except Exception as e:
    print(f"[!] Failed to import config: {e}")
    traceback.print_exc()

try:
    from mewact import memory
    print("[+] Import memory: OK")
    lib = memory.LibraryManager()
    print("    LibraryManager initialized: OK")
except Exception as e:
    print(f"[!] Failed to import/init memory: {e}")
    traceback.print_exc()

try:
    from mewact import planning
    print("[+] Import planning: OK")
except Exception as e:
    print(f"[!] Failed to import planning: {e}")
    traceback.print_exc()

try:
    from mewact import execution
    print("[+] Import execution: OK")
except Exception as e:
    print(f"[!] Failed to import execution: {e}")
    traceback.print_exc()

try:
    from mewact import session
    print("[+] Import session: OK")
except Exception as e:
    print(f"[!] Failed to import session: {e}")
    traceback.print_exc()

try:
    from mewact import perception
    print("[+] Import perception: OK")
except Exception as e:
    print(f"[!] Failed to import perception: {e}")
    traceback.print_exc()

try:
    import mewact_legacy
    print("[+] Import mewact_legacy logic: OK")
except Exception as e:
    print(f"[!] Failed to import mewact_legacy: {e}")
    traceback.print_exc()

print("[-] Done.")
