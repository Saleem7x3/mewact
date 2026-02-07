import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cmds = data.get('commands', {})
    
    if 'notepad notedown' in cmds:
        cmds['notepad notedown']['id'] = 405
        print("Fixed 'notepad notedown' to ID 405")
        
    if 'excel new sheet' in cmds:
        cmds['excel new sheet']['id'] = 410
        cmds['excel new sheet']['type'] = 'hotkey'
        cmds['excel new sheet']['keys'] = ['ctrl', 'n']
        cmds['excel new sheet']['description'] = "Create new Excel workbook/sheet"
        print("Fixed 'excel new sheet' to ID 410 and added hotkey code")
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(f"Error: {e}")
