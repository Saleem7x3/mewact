
import sys
import os
import time
from colorama import Fore, Style, init

# Initialize Colorama
init(autoreset=True)

# --- MCP COMPATIBILITY MODE ---
# If True, redirects all print() calls to stderr to avoid breaking JSON-RPC
MCP_MODE = False
_builtin_print = print

def safe_print(*args, **kwargs):
    if MCP_MODE:
        kwargs['file'] = sys.stderr
    _builtin_print(*args, **kwargs)

# Export the safe print as 'print' for other modules to import
print = safe_print

# --- CONFIGURATION ---
MODEL_NAME = "gemma3:4b-cloud" 
OCR_ENGINE = "rapidocr"  # "rapidocr", "easyocr", or "paddleocr"
TARGET_WINDOW_TITLE = ""  # Focus on specific window (e.g., "Chrome")
TARGET_MONITORS = []      # List of monitor indices (1-based). Empty = all. E.g., [1] or [1, 2]
LIBRARY_FILE = "command_library.json"
SESSION_FILE = "sessions.json"

# --- ACTIVE VISION CONFIGURATION ---
ACTIVE_MODE = False 
# ... (existing keys) ...
EMBEDDING_MODEL = "nomic-embed-text" 

# --- SANDBOX CONFIGURATION ---
SANDBOX_ENABLED = False # Set True to route 'execute_script' to Docker
DOCKER_IMAGE = "mewact-runner"

# --- AUTONOMY CONFIGURATION ---
PLANNER_MODEL = "mistral" # Requires: ollama pull mistral

# --- MOBILE CONFIGURATION ---
MOBILE_ENABLED = False # Set True to enable Android control via ADB
ADB_PATH = "adb" # Helper assumes 'adb' in PATH, or provide absolute path





# --- ROBUST MULTI-TRIGGER REGEX ---


# Format: <ID>&&$47 <command> [| <var>] <ID>$&47
TRIGGER_PATTERN = r"(\d+)&&\$47\s*(.*?)\s*\1\$&47"

# Variable definition pattern: &&VAR <num> <content> VAR&&
VAR_PATTERN = r"&&VAR\s*(\d+)\s+(.*?)\s*VAR&&"

LOOP_DELAY = 0.2
DEBUG_OCR = False
OCR_USE_GPU = True  # Set to True to use GPU for OCR (EasyOCR/PaddleOCR only) 

# Adaptive OCR Configuration
OCR_ADAPTIVE_MODE = False # Default to Full Screen (Performance). Set True via --power-saver
OCR_STRIP_THRESHOLD = 0.53  # Windows occupying >53% of screen use strip mode
OCR_STRIP_COUNT = 3         # Number of horizontal strips to split large windows into 
OCR_STRIP_OVERLAP = 30      # Pixels of overlap between strips to prevent cutting text lines 

# Scan Mode Configuration
OCR_SCAN_MODE = "monitor"   # "monitor" (default) or "window"
OCR_MONITOR_STRATEGY = "full" # "full" (default) or "window" (iterates windows on monitor) 

# --- AUTO-ROLLBACK CONFIG ---
# When enabled, automatically focuses back to chat window after each command
AUTO_ROLLBACK_ENABLED = False
AUTO_ROLLBACK_CHAT = "gemini"  # "gemini", "chatgpt", "claude", or "tab" for generic tab switch

# --- IDLE WATCHDOG CONFIG ---
LAST_ACTIVITY = time.time()
IDLE_TIMEOUT = 0 # 0 = Disabled

# --- 0. DEPENDENCY CHECK ---
def check_deps():
    try:
        import rapidocr_onnxruntime
        import ollama
    except ImportError as e:
        safe_print(f"{Fore.RED}[!] CRITICAL MISSING LIB: {e.name}")
        sys.exit(1)
    
    try: 
        ollama.list()
    except ConnectionError:
        safe_print(f"{Fore.RED}[!] Ollama Server not found. Run 'ollama serve'.")
        sys.exit(1)
    except Exception as e:
        safe_print(f"{Fore.RED}[!] Ollama error: {type(e).__name__}: {e}")
        sys.exit(1)
    safe_print(f"{Fore.GREEN}[*] System Ready. ID-Selector Mode Active.")
