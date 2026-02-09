import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server.fastmcp import FastMCP
    import pyautogui
    from mewact_legacy import PerceptionEngine

    mcp = FastMCP("Debug v2")
    print(f"DEBUG: mcp type: {type(mcp)}")
    # print(f"DEBUG: dir(mcp): {dir(mcp)}") 

    print("Attempting to decorate tool...")
    @mcp.tool()
    def test_tool() -> str:
        return "ok"
    print("Tool decorated successfully.")

    if __name__ == "__main__":
        print("Running mcp...")
        mcp.run()

except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
