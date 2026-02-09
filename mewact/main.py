
import argparse
import mss
from colorama import Fore

from . import config
from .memory import LibraryManager
from .perception import WindowCapture, PerceptionEngine
from .planning import CognitivePlanner
from .execution import ActionExecutor
from .session import SessionManager
from .sentinel import PassiveSentinel, IdleWatchdog
from .utils import complex_mew_act
from .config import print

# Expose global just in case (legacy compat)
PERCEPTION_ENGINE = None

def main():
    """Main entry point for CLI execution."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, help="Target window title")
    parser.add_argument("--monitors", type=str, help="Monitor indices (comma-separated, e.g., '1' or '1,2')")
    parser.add_argument("--ocr", choices=["rapidocr", "easyocr", "paddleocr"], help="Choose OCR engine")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for OCR (EasyOCR/PaddleOCR only)")
    parser.add_argument("--auto-rollback", type=str, metavar="CHAT", 
                        help="Auto-focus back to chat window after commands. Values: gemini, chatgpt, claude, tab, window:<title>")
    parser.add_argument("--power-saver", action="store_true", help="Enable Adaptive/Scattered OCR mode for low-end PCs")
    parser.add_argument("--idle-timeout", type=int, default=0, help="Enable Idle Watchdog with specific timeout (seconds)")
    
    parser.add_argument("--scan-mode", choices=["monitor", "window"], default="monitor", help="Scan Mode: monitor (default) or window (iterates all windows)")
    parser.add_argument("--monitor-strategy", choices=["full", "window"], default="full", help="Monitor Strategy: full (default) or window (iterates windows on monitor)")
    
    args = parser.parse_args()
    
    # Update config globals
    if args.ocr:
        config.OCR_ENGINE = args.ocr
        print(f"{Fore.CYAN}[*] CLI OCR Override: {args.ocr}")
    
    if args.gpu:
        config.OCR_USE_GPU = True
        print(f"{Fore.CYAN}[*] GPU Mode: Enabled for OCR")
        
    if args.power_saver:
        config.OCR_ADAPTIVE_MODE = True
        print(f"{Fore.CYAN}[*] Power Saver Mode: Enabled (Adaptive/Scattered OCR)")

    # Set scan modes from CLI
    config.OCR_SCAN_MODE = args.scan_mode
    config.OCR_MONITOR_STRATEGY = args.monitor_strategy
    
    if args.target:
        config.TARGET_WINDOW_TITLE = args.target
        print(f"{Fore.CYAN}[*] CLI Target: '{args.target}'")
    
    if args.monitors:
        config.TARGET_MONITORS = [int(m.strip()) for m in args.monitors.split(',') if m.strip().isdigit()]
        print(f"{Fore.CYAN}[*] CLI Monitors: {config.TARGET_MONITORS}")
    
    if args.auto_rollback:
        config.AUTO_ROLLBACK_ENABLED = True
        config.AUTO_ROLLBACK_CHAT = args.auto_rollback.lower()
        print(f"{Fore.CYAN}[*] AUTO-ROLLBACK ENABLED: Will focus back to '{args.auto_rollback.lower()}' after each command")

    if args.idle_timeout > 0:
        config.IDLE_TIMEOUT = args.idle_timeout
        print(f"{Fore.CYAN}[*] IDLE WATCHDOG ENABLED: Timeout {args.idle_timeout}s")
    
    if not args.target and not args.monitors:
        print(f"{Fore.CYAN}--- JAM A.I. ID-Selector Mode ---")
        print("  [1] All Monitors")
        print("  [2] Specific Window")
        print("  [3] Specific Monitor(s)")
        try: mode = input("Choice: ").strip()
        except: mode = "1"
        
        if mode == "2":
            wc_temp = WindowCapture()
            print(f"{Fore.YELLOW}[*] Scanning windows...")
            wins = wc_temp.list_windows()
            valid_wins = [w[1] for w in wins]
            
            if not valid_wins: print(f"{Fore.RED}[!] No windows.")
            else:
                for i, title in enumerate(valid_wins): print(f"  [{i+1}] {title}")
                try:
                    sel = int(input(f"Select ID: ").strip())
                    if 1 <= sel <= len(valid_wins):
                        config.TARGET_WINDOW_TITLE = valid_wins[sel-1]
                        print(f"{Fore.CYAN}[*] Targeted: '{valid_wins[sel-1]}'")
                except: pass
        
        elif mode == "3":
            with mss.mss() as sct:
                print(f"{Fore.YELLOW}[*] Available monitors:")
                for i, mon in enumerate(sct.monitors[1:], 1):
                    print(f"  [{i}] {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})")
                try:
                    sel = input("Enter monitor(s) (comma-separated, e.g., '1' or '1,2'): ").strip()
                    config.TARGET_MONITORS = [int(m.strip()) for m in sel.split(',') if m.strip().isdigit()]
                    print(f"{Fore.CYAN}[*] Targeted monitors: {config.TARGET_MONITORS}")
                except: pass

    # Dependency Check
    config.check_deps()

    lib_mgr = LibraryManager() 
    p = PerceptionEngine()
    
    global PERCEPTION_ENGINE
    PERCEPTION_ENGINE = p
    
    b = CognitivePlanner(lib_mgr) 
    session_mgr = SessionManager()
    h = ActionExecutor(lib_mgr, session_manager=session_mgr)
    
    # Add perception engine to executor locals for mew act command
    h.locals["PERCEPTION_ENGINE"] = p
    h.locals["complex_mew_act"] = complex_mew_act
    h.locals["session_manager"] = session_mgr
    
    # Start Watchdog if enabled
    if config.IDLE_TIMEOUT > 0:
        wd = IdleWatchdog(h, config.IDLE_TIMEOUT)
        wd.start()
    
    PassiveSentinel(p, b, h).start()

if __name__ == "__main__":
    main()
