import subprocess
import json
import sys
import time
import os

def run_mcp_test():
    print("🚀 Starting MCP Client Test...")
    
    # Path to the MCP server script
    # Points to ../mewact_mcp.py
    server_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mewact_mcp.py")
    
    # Start the server process
    process = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8', # Force UTF-8 for emojis
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        print(f"\n📤 Sending: {json_str[:100]}...")
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
                print(f"📥 Received: {str(data)[:100]}...")
                return data
            except json.JSONDecodeError:
                print(f"⚠️ Log/Stderr: {line}")
    
    try:
        # 1. Initialize
        send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"}
        }, id=1)
        
        resp = read_response()
        if resp and "result" in resp:
            print("✅ Initialization Successful!")
            print(f"   Server: {resp['result']['serverInfo']['name']}")
        
        # 2. Sent initialized notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        process.stdin.flush()
        
        # 3. List Tools
        send_request("tools/list", id=2)
        resp = read_response()
        if resp and "result" in resp:
            tools = resp['result']['tools']
            print(f"\n✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"   - {tool['name']}")
                
        # 4. Call a simple tool (get_screen_info)
        send_request("tools/call", {
            "name": "get_screen_info",
            "arguments": {}
        }, id=3)
        resp = read_response()
        if resp and "result" in resp:
            print(f"\n✅ Tool Execution Successful (get_screen_info)!")
            print(f"   Result: {resp['result']['content'][0]['text']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        # Print pending stderr
        print("Stderr output:")
        print(process.stderr.read())
        
    finally:
        print("\n🛑 Terminating server...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    run_mcp_test()
