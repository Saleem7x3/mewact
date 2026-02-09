
import time
from colorama import Fore
from .config import print

def complex_mew_act(exec_locals):
    print(f"{Fore.CYAN}[*] Executing Complex Mew Act Routine...")
    p = exec_locals.get('PERCEPTION_ENGINE')
    pyautogui, ctypes, time_mod = exec_locals['pyautogui'], exec_locals['ctypes'], exec_locals['time']
    # Note: 'time' variable shadowed by local 'time', so we use time_mod
    
    # 1. Focus Anchor
    if 'ANCHOR_HWND' in exec_locals:
        try:
            hwnd = exec_locals['ANCHOR_HWND']
            current_hwnd = ctypes.windll.user32.GetForegroundWindow()
            if current_hwnd != hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time_mod.sleep(0.5)
            if 'ANCHOR_POS' in exec_locals:
                pyautogui.click(exec_locals['ANCHOR_POS'])
            time_mod.sleep(0.5)
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to focus anchor: {e}")

    # 2. Capture & Copy
    if p: 
        p.copy_last_image_to_clipboard()
        # SESSION SUGGESTION LOGIC
        try:
            sess_mgr = exec_locals.get('session_manager')
            if sess_mgr:
                _, txt = p.capture_and_scan()
                suggestions = sess_mgr.scan_for_suggestions(txt)
                if suggestions:
                    s_name = suggestions[0]
                    print(f"{Fore.GREEN}[SESSION] Found match: '{s_name}'")
                    # fetch steps
                    steps = sess_mgr.get_session(s_name).get('steps', [])
                    # Format for AI
                    summary = " | ".join([f"{s['id']}:{s['args']}" for s in steps])
                    msg = f"[MEMORY] Found session '{s_name}'. Steps: {summary}"
                    
                    # Type message before pasting image
                    pyautogui.write(msg)
                    time_mod.sleep(0.5)
                    pyautogui.press('enter')
                    time_mod.sleep(0.5)
        except Exception as e: print(f"{Fore.RED}[!] Suggestion error: {e}")
    time_mod.sleep(1.0)

    # 3. Paste
    pyautogui.hotkey('ctrl', 'v')
    print(f"{Fore.YELLOW}[*] Waiting for image upload stability...")
    time_mod.sleep(3.5) 

    # 4. Try sending via Enter
    pyautogui.press('enter')
    time_mod.sleep(1.0)

    # 5. Fallback: If 'Send' button remains visible, click it
    # (This assumes Enter might have failed or just made a newline)
    if p:
        try:
            print(f"{Fore.YELLOW}[*] Verifying submission logic...")
            # We assume if Enter worked, input box cleared or sent.
            # We can't know for sure without diffing.
            # But user request: "if enter does job of /n... it clicks send"
            # So we check if 'Send' button is visible.
            ui, txt = p.capture_and_scan()
            send_btn = next((item for item in ui if 'send' in item['text'].lower() or 'submit' in item['text'].lower()), None)

            if send_btn:
                # If found, check if it looks clickable (not disabled)? Hard with OCR.
                # Just try clicking it.
                print(f"{Fore.GREEN}[+] 'Send' button detected at ({send_btn['x']}, {send_btn['y']}). Clicking...")
                pyautogui.click(send_btn['x'], send_btn['y'])
            else:
                # No 'Send' button found. Maybe Enter worked or it's an icon.
                pass
        except Exception as e:
            print(f"{Fore.RED}[!] Send fallback error: {e}")
