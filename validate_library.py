import json

try:
    with open('command_library.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cmds = data.get('commands', {})
    print(f"Loaded {len(cmds)} commands.")
    
    ids = {}
    errors = []
    for key, val in cmds.items():
        if not isinstance(val, dict):
            errors.append(f"Invalid format for '{key}': {val}")
            continue
        
        cid = val.get('id')
        if cid is None:
            errors.append(f"Missing ID for '{key}'")
        elif cid in ids:
            errors.append(f"Duplicate ID {cid}: '{key}' and '{ids[cid]}'")
        else:
            ids[cid] = key
            
        if 'code' not in val and val.get('type') != 'sequence':
             # sequences might have 'steps' instead of 'code'
             if 'steps' not in val:
                 errors.append(f"Missing code/steps for '{key}'")
    
    if errors:
        print("Found errors:")
        for e in errors:
            print("- " + e)
    else:
        print("Library Logic Valid. No duplicate IDs or missing fields.")
        
except Exception as e:
    print(f"JSON Error: {e}")
