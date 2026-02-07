import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cmds = {
        "snap window left": {
            "type": "python",
            "code": "pyautogui.hotkey('win', 'left')",
            "description": "Snap current window to the left",
            "id": 501
        },
        "snap window right": {
            "type": "python",
            "code": "pyautogui.hotkey('win', 'right')",
            "description": "Snap current window to the right",
            "id": 502
        },
        "snap window up": {
             "type": "python",
             "code": "pyautogui.hotkey('win', 'up')",
             "description": "Maximize or snap window up",
             "id": 503
        }
    }

    for key, val in cmds.items():
        if key not in data['commands']:
            data['commands'][key] = val
            print(f"Added {key} (ID {val['id']})")
        else:
            print(f"{key} already exists.")
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        print("Done.")
        
except Exception as e:
    print(e)
