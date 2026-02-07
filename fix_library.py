import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Fix ID 134 (Sequence missing code)
    for key, val in data['commands'].items():
        if val.get('id') == 134:
            if 'code' not in val:
                val['code'] = "pass # sequence" # Dummy code for planner

    # Add ID 28 (Open Google)
    found_28 = False
    for val in data['commands'].values():
        if val.get('id') == 28:
            found_28 = True
            break
    
    if not found_28:
        data['commands']['open google'] = {
            "type": "python",
            "code": "import webbrowser; webbrowser.open('https://google.com')",
            "description": "Open Google in default browser",
            "id": 28
        }
        print("Added ID 28 (open google)")

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print("Library patched successfully.")
    
except Exception as e:
    print(f"Error: {e}")
