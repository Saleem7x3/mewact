import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cmds = data.get('commands', {})
    
    # Fix parent folder (avoid 301 conflict with focus anchor)
    if 'parent folder' in cmds:
        cmds['parent folder']['id'] = 305
        print("Fixed 'parent folder' to ID 305")
        
    # Fix notepad notedown (avoid 405 conflict with show ip address)
    if 'notepad notedown' in cmds:
        cmds['notepad notedown']['id'] = 402
        print("Fixed 'notepad notedown' to ID 402")
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(f"Error: {e}")
