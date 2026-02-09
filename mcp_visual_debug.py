
import subprocess
import json
import sys
import time
import os

def run_visual_debug():
    print("🚀 Starting MCP VISUAL Debug...")
    
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
                # print(f"DEBUG: {str(data)[:60]}...")
                return data
            except: pass

    try:
        # Init
        send_request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "DebugClient", "version": "1.0"}}, id=1)
        read_response()
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        print("\n--- TEST 1: DISPLAY MESSAGE BOX ---")
        # 'msg' command shows a popup. Good for verifying visibility.
        send_request("tools/call", {
            "name": "run_shell",
            "arguments": {"command": "msg * \"MCP Visual Test: Can you see this?\""}
        }, id=10)
        resp1 = read_response()
        print(f"Msg Result: {resp1['result']['content'][0]['text']}")

        print("\n--- TEST 2: LAUNCH NOTEPAD (Run Shell) ---")
        # Use 'start notepad' which forces a new window
        send_request("tools/call", {
            "name": "run_shell",
            "arguments": {"command": "start notepad"}
        }, id=20)
        resp2 = read_response()
        print(f"Launch Result: {resp2['result']['content'][0]['text']}")
        
        print("Waiting 3s...")
        time.sleep(3)

        print("\n--- TEST 3: TYPE TEXT ---")
        send_request("tools/call", {
            "name": "type_text",
            "arguments": {"text": "If you can read this, the MCP Server is controlling your keyboard! 😺"}
        }, id=30)
        resp3 = read_response()
        print(f"Type Result: {resp3['result']['content'][0]['text']}")

        time.sleep(2)
        
        print("\n--- TEST 4: CHECK RESOLUTION ---")
        send_request("tools/call", {"name": "get_screen_info", "arguments": {}}, id=40)
        resp4 = read_response()
        print(f"Info: {resp4['result']['content'][0]['text']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        # print("Stderr:", process.stderr.read())

    finally:
        print("🛑 Terminating...")
        try: process.terminate()
        except: pass

if __name__ == "__main__":
    run_visual_debug()
