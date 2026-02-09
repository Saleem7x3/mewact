
import sys
import os

# Ensure the package can be imported from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import mewact
except ImportError as e:
    print(f"Error importing mewact package: {e}")
    sys.exit(1)

# Re-export necessary classes for compatibility with mewact_mcp.py (if it still uses them directly)
PerceptionEngine = mewact.PerceptionEngine
ActionExecutor = mewact.ActionExecutor
LibraryManager = mewact.LibraryManager
SessionManager = mewact.SessionManager
MCP_MODE = mewact.config.MCP_MODE # Access via config module

if __name__ == "__main__":
    mewact.main()