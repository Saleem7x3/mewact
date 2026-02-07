import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Remove specific waits to force generic wait usage
    ids_to_remove = [355, 356]
    new_commands = {}
    removed_count = 0
    for key, val in data['commands'].items():
        if val.get('id') not in ids_to_remove:
            new_commands[key] = val
        else:
            print(f'Removing {key} (ID {val.get("id")})')
            removed_count += 1

    data['commands'] = new_commands
    print(f'Removed {removed_count} conflicting commands.')

    # Add ID 900 (Wait For Text)
    # Use SYSTEM prefix for special handling in mew.py
    if 'wait for text' not in data['commands']:
        data['commands']['wait for text'] = {
            "type": "python",
            "code": "SYSTEM:WAIT_FOR_TEXT:__VAR__", 
            "description": "Wait until specific text appears on screen",
            "id": 900
        }
        print('Added wait for text (ID 900)')

    # Add ID 28 if missing (User also reported issue, just to be safe)
    # (Already checks in previous script but good to be robust)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print('Library updated successfully.')

except Exception as e:
    print(f'Error: {e}')
