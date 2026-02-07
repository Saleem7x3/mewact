import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    found = False
    for key, val in data['commands'].items():
        if isinstance(val, dict) and val.get('id') == 128:
            print(f"Fixing '{key}' (ID 128)...")
            val['type'] = 'shell'
            found = True
            break # ID should be unique

    if found:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print("Successfully updated command type to 'shell'.")
    else:
        print("ID 128 not found.")

except Exception as e:
    print(f"Error: {e}")
