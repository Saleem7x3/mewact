import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'open whatsapp' not in data['commands']:
        data['commands']['open whatsapp'] = {
            "type": "python",
            "code": "import webbrowser; webbrowser.open('https://web.whatsapp.com')",
            "description": "Open WhatsApp Web",
            "id": 220
        }
        print('Added open whatsapp (ID 220)')
    else:
        print('WhatsApp command already exists.')
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(e)
