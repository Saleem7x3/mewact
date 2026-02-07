import json

try:
    with open('command_library.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cmds = data.get('commands', {})
    
    # Check for ID 400
    for key, val in cmds.items():
        if val.get('id') == 400:
            print(f"ID 400 found in: '{key}'")
            
    # Check for 'excel new sheet'
    if 'excel new sheet' in cmds:
        print(f"Entry 'excel new sheet': {cmds['excel new sheet']}")
    else:
        print("'excel new sheet' not found as a key.")
        
except Exception as e:
    print(f"Error: {e}")
