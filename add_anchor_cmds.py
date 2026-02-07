import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cmds = {
        "set anchor": {
            "type": "python",
            "code": "import pyautogui, ctypes\nANCHOR_POS = pyautogui.position()\nANCHOR_HWND = ctypes.windll.user32.GetForegroundWindow()\nprint(f'Anchor set at {ANCHOR_POS} (Window: {ANCHOR_HWND})')",
            "description": "Save current mouse position and active window as anchor",
            "id": 300
        },
        "focus anchor": {
            "type": "python",
            "code": "import pyautogui, ctypes, time\nif 'ANCHOR_HWND' in locals():\n    ctypes.windll.user32.SetForegroundWindow(ANCHOR_HWND)\n    time.sleep(0.2)\n    if 'ANCHOR_POS' in locals():\n        pyautogui.click(ANCHOR_POS)\nelse:\n    print('No anchor set.')",
            "description": "Focus anchored window and click anchored position",
            "id": 301
        }
    }

    for key, val in cmds.items():
        data['commands'][key] = val
        print(f"Added {key} (ID {val['id']})")
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        print("Done.")
        
except Exception as e:
    print(e)
