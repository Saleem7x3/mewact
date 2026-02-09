
import subprocess
import json
import sys
import time
import os

def run_demo():
    print("🚀 Starting MCP Integration Demo...")
    print("   Scenario: Open Notepad -> Type Text -> Capture Screen -> Close Notepad")
    
    # Path to the MCP server script
    server_script = os.path.join(os.path.dirname(__file__), "mewact_mcp.py")
    
    # Start the server process
    process = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8', # Force UTF-8 for emojis
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    print(f"✅ Server started (PID: {process.pid})")
    
    def send_request(method, params=None, id=1):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "id": id
        }
        if params:
            msg["params"] = params
        
        json_str = json.dumps(msg)
        # print(f"\n📤 Sending: {json_str[:100]}...")
        process.stdin.write(json_str + "\n")
        process.stdin.flush()
    
    def read_response():
        while True:
            line = process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                # print(f"📥 Received: {str(data)[:100]}...")
                return data
            except json.JSONDecodeError:
                # print(f"⚠️ Log/Stderr: {line}")
                pass
    
    try:
        # 1. Initialize
        send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "DemoClient", "version": "1.0"}
        }, id=1)
        read_response() # Result
        
        # 2. Initialized Notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        process.stdin.flush()
        
        print("\n--- STEP 1: OPEN NOTEPAD ---")
        send_request("tools/call", {
            "name": "execute_command",
            "arguments": {"command_id": "201"} # Open Notepad
        }, id=10)
        resp = read_response()
        print(f"Result: {resp['result']['content'][0]['text']}")
        
        print("Waiting 2s for Notepad to open...")
        time.sleep(2)
        
        print("\n--- STEP 2: TYPE TEXT ---")
        send_request("tools/call", {
            "name": "type_text",
            "arguments": {"text": "Hello from MewAct MCP Integration Test! 🚀"}
        }, id=11)
        resp = read_response()
        print(f"Result: {resp['result']['content'][0]['text']}")
        
        time.sleep(1)
        
        print("\n--- STEP 3: CAPTURE SCREEN ---")
        send_request("tools/call", {
            "name": "capture_screen",
            "arguments": {"annotate": True}
        }, id=12)
        resp = read_response()
        print("Screen captured! (Image data received)")
        
        # Verify image data exists
        content = resp['result']['content'][0]
        if content['type'] == 'image':
             print(f"Image Size: {len(content['data'])} bytes (Base64)")
        else:
             print("Warning: No image returned?")

        time.sleep(1)

        print("\n--- STEP 4: CLOSE NOTEPAD (CLEANUP) ---")
        # Don't save
        send_request("tools/call", {
            "name": "execute_command",
            "arguments": {"command_id": "550"} # Close Window
        }, id=13)
        read_response()
        
        time.sleep(0.5)
        # Handle "Do you want to save?" dialog if it appears -> Press Tab then Enter (Don't Save)
        # Usually it's Right Arrow -> Enter? or Tab -> Enter.
        # Let's just press 'n' for Don't Save if prompted.
        send_request("tools/call", {
            "name": "type_text",
            "arguments": {"text": "n"} 
        }, id=14)
        read_response()
        print("Cleanup attempted.")

        print("\n✅ DEMO COMPLETE!")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Stderr output:")
        print(process.stderr.read())
        
    finally:
        print("\n🛑 Terminating server...")
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()

if __name__ == "__main__":
    run_demo()
