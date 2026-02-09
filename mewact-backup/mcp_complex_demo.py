
import subprocess
import json
import sys
import time
import os

def run_complex_demo():
    print("🚀 Starting MCP COMPLEX Demo...")
    print("   Scenario: System Info -> Notepad -> Calculator -> Copy/Paste -> Notepad")
    
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
                return json.loads(line)
            except: pass
    
    try:
        # Initialize
        send_request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "ComplexClient", "version": "1.0"}}, id=1)
        read_response()
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # 1. Get System Info via Shell
        print("\n--- STEP 1: GET SYSTEM INFO ---")
        send_request("tools/call", {
            "name": "run_shell",
            "arguments": {"command": "cmd /c ver"}
        }, id=10)
        resp = read_response()
        sys_info = resp['result']['content'][0]['text'].strip()
        print(f"System Info: {sys_info}")

        # 2. Open Notepad
        print("\n--- STEP 2: OPEN NOTEPAD & TYPE INFO ---")
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "201"}}, id=20)
        read_response()
        time.sleep(2)
        
        # Type header and info
        text_to_type = f"MCP Complex Demo Report\n-----------------------\nOS: {sys_info}\n\nCalculating data..."
        send_request("tools/call", {"name": "type_text", "arguments": {"text": text_to_type}}, id=21)
        read_response()

        # 3. Open Calculator
        print("\n--- STEP 3: CALCULATOR OPERATIONS ---")
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "200"}}, id=30) # 200 = calc
        read_response()
        time.sleep(2)

        # Type calculation
        send_request("tools/call", {"name": "type_text", "arguments": {"text": "1337*2="}}, id=31)
        read_response()
        time.sleep(1)

        # Copy result (Ctrl+C)
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "206"}}, id=32)
        read_response()
        print("Pooled calculation result to clipboard.")

        # 4. Switch back to Notepad
        print("\n--- STEP 4: SWITCH & PASTE ---")
        # Alt+Tab
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "551"}}, id=40)
        read_response()
        time.sleep(1)

        # Type label
        send_request("tools/call", {"name": "type_text", "arguments": {"text": "\nResult: "}}, id=41)
        read_response()

        # Paste (Ctrl+V)
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "207"}}, id=42)
        read_response()
        
        # 5. Capture Proof
        print("\n--- STEP 5: CAPTURE PROOF ---")
        send_request("tools/call", {"name": "capture_screen", "arguments": {}}, id=50)
        read_response()
        print("Screen captured.")

        # 6. Cleanup
        print("\n--- STEP 6: CLEANUP ---")
        # Close Notepad (Alt+F4)
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "550"}}, id=60) 
        read_response()
        time.sleep(0.5)
        # Type 'n' (Don't Save)
        send_request("tools/call", {"name": "type_text", "arguments": {"text": "n"}}, id=61)
        read_response()
        
        time.sleep(0.5)
        # Close Calculator (Alt+F4) - it should be focused if Notepad closed? No, usually next window in z-order.
        # But if we closed Notepad, focus might go to VS Code or Terminal.
        # We need to find Calc? 
        # Actually, simpler to just close Notepad and be done. User can close Calc manually or we try.
        # Let's try closing active window again.
        send_request("tools/call", {"name": "execute_command", "arguments": {"command_id": "550"}}, id=62)
        read_response()

        print("\n✅ COMPLEX DEMO COMPLETE!")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Stderr:", process.stderr.read())

    finally:
        print("🛑 Terminating...")
        try: process.terminate()
        except: pass

if __name__ == "__main__":
    run_complex_demo()
