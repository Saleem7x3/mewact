import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'notepad notedown' not in data['commands']:
        data['commands']['notepad notedown'] = {
            "type": "python",
            "code": "SYSTEM:NOTEDOWN:__VAR__",
            "description": "Write commands to Notepad and execute them sequentially (Batch Mode)",
            "id": 400
        }
        print('Added notepad notedown (ID 400)')
    else:
        print('Command already exists.')
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(e)
