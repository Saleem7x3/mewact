
import subprocess
import json
import sys
import time
import os

def run_visual_fix():
    print("🚀 Starting MCP VISUAL FIX Test...")
    
    server_script = os.path.join(os.path.dirname(__file__), "mewact_mcp.py")
    
    process = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    print(f"✅ Server started (PID: {process.pid})")
    
    def send_request(method, params=None, id=1):
        msg = {"jsonrpc": "2.0", "method": method, "id": id}
        if params: msg["params"] = params
        process.stdin.write(json.dumps(msg) + "\n")
        process.stdin.flush()
    
    def read_response():
        while True:
            line = process.stdout.readline()
            if not line: break
            line = line.strip()
            if not line: continue
            try:
                data = json.loads(line)
                return data
            except: pass

    try:
        # Init
        send_request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "FixClient", "version": "1.0"}}, id=1)
        read_response()
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        print("\n--- TEST 1: EXECUTE_SCRIPT (POPUP) ---")
        # Try to show a popup. If this shows, GUI is working.
        code = "pyautogui.alert('MCP VISUAL TEST: Click OK to continue', 'MewAct MCP')"
        send_request("tools/call", {
            "name": "execute_script",
            "arguments": {"code": code}
        }, id=10)
        print("Sent alert request. Look at screen!")
        resp1 = read_response()
        print(f"Alert Result: {resp1['result']['content'][0]['text']}")

        print("\n--- TEST 2: EXECUTE_SCRIPT (NOTEPAD) ---")
        # Try Popen directly
        code = "subprocess.Popen('notepad')"
        send_request("tools/call", {
            "name": "execute_script",
            "arguments": {"code": code}
        }, id=20)
        resp2 = read_response()
        print(f"Notepad Result: {resp2['result']['content'][0]['text']}")
        
        print("Waiting 3s for Notepad...")
        time.sleep(3)

        print("\n--- TEST 3: TYPE INTO NOTEPAD ---")
        # Direct write
        code = "pyautogui.write('If you see this, execute_script works! 😺', interval=0.05)"
        send_request("tools/call", {
            "name": "execute_script",
            "arguments": {"code": code}
        }, id=30)
        resp3 = read_response()
        print(f"Type Result: {resp3['result']['content'][0]['text']}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        print("🛑 Terminating...")
        try: process.terminate()
        except: pass

if __name__ == "__main__":
    run_visual_fix()
