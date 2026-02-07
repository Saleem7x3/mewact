import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Overwrite if exists to update code
    data['commands']['set timer'] = {
        "type": "python",
        "code": "import webbrowser, urllib.parse; webbrowser.open('https://www.google.com/search?q=set+timer+for+' + urllib.parse.quote('__VAR__'))",
        "description": "Set a Google timer for specified duration (e.g. '5 minutes')",
        "id": 2100
    }
    print("Updated/Added set timer (ID 2100)")
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(e)
