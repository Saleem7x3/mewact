import json

try:
    with open('command_library.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cmds = data.get('commands', {})
    
    # Check for ID 301
    for key, val in cmds.items():
        if val.get('id') == 301:
            print(f"ID 301: '{key}'")
            
    # Check 'show ip address'
    if 'show ip address' in cmds:
        print(f"'show ip address': {cmds['show ip address']}")
        
except Exception as e:
    print(f"Error: {e}")
