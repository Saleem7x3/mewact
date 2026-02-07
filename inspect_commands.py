import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    target_ids = [134, 106, 105, 356, 28, 204]
    results = {}
    
    for key, val in data['commands'].items():
        if isinstance(val, dict) and val.get('id') in target_ids:
            results[key] = val

    with open('debug_cmnd_utf8.txt', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)
    print("Done")
except Exception as e:
    print(e)
