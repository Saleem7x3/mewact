import json

path = 'command_library.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    code_template = """import ctypes
user32 = ctypes.windll.user32
def focus_window(title):
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if title.lower() in buff.value.lower():
                    user32.SetForegroundWindow(hwnd)
                    return False
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
focus_window('__VAR__')"""

    if 'focus window' not in data['commands']:
        data['commands']['focus window'] = {
            "type": "python",
            "code": code_template,
            "description": "Switch focus to a window matching the title",
            "id": 200
        }
        print('Added focus window (ID 200)')
    else:
        print('Focus window command already exists.')
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
except Exception as e:
    print(e)
