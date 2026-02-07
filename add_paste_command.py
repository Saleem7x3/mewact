import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'paste' not in data['commands']:
        data['commands']['paste'] = {
            "type": "python",
            "code": "pyautogui.hotkey('ctrl', 'v')",
            "description": "Paste from clipboard",
            "id": 2000
        }
        print('Added paste (ID 2000)')
    else:
        print('Paste command already exists.')
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(e)
