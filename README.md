# MewAct

**AI Desktop Control via MCP + 400+ Commands**

> MewAct is a Model Context Protocol (MCP) server that enables AI assistants (Claude, GPT, Gemini) to control your Windows PC. It also supports **direct control from chatbots like Gemini/ChatGPT** without CLI (via legacy OCR triggers). Features smart screenshots, coordinate normalization, human-like mouse movements, and a 400+ command library.

---

## 🚀 Quick Start (MCP Mode)

### 1. Install
```bash
pip install mcp pyautogui mss opencv-python numpy pillow colorama pywinauto pywin32 rapidocr-onnxruntime
```
*(Or use Docker: `docker build -t mewact .`)*

### 2. Configure Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mewact": {
      "command": "python",
      "args": ["C:/path/to/mewact_mcp.py"]
    }
  }
}
```

### 3. Start Using!
Claude can now control your desktop, no not only claude, any LLM can control your desktop:
- *"Take a screenshot and click the Submit button"*
- *"Open Chrome, search for Python tutorials, and summarize the first result"*
- *"Create a new Word document and type a meeting agenda"*

---

## 📋 MCP Tools

| Tool | Description |
|------|-------------|
| `capture_screen()` | 📸 Smart Screenshot - detects UI elements with numbered IDs |
| `click_element(id)` | 🖱️ Click numbered element from screenshot |
| `click_text("text")` | 🔍 Find and click visible text |
| `click_at_normalized(x, y)` | 🎯 Click at 0-1000 coordinates |
| `type_text("text")` | ⌨️ Type text with human-like timing |
| `press_key("ctrl+s")` | ⚡ Keyboard shortcuts |
| `drag_drop(x1, y1, x2, y2)` | ↕️ Drag and drop |
| `execute_script("code")` | 🐍 Run Python code directly (safe mode) |
| `describe_screen("prompt")` | 🧠 VLM screen understanding (requires Ollama) |
| `focus_window("title")` | 🪟 Switch to specific app |
| `get/set_clipboard()` | 📋 Manage clipboard content |
| `check_screen_changed()` | ⚡ Differential screenshot detection |
| `get_ui_tree(depth)` | 🌳 Get hierarchical UI structure |
| `omniparser_parse(img)` | 👁️ OmniParser client (requires server) |
| `execute_command(700)` | 📚 Run command by ID |
| `list_commands("word")` | 📖 Search command library |

---

## ✨ Key Features

### Smart Screenshots
AI sees numbered UI elements instead of guessing coordinates:
```
capture_screen() → {elements: [{id: 5, text: "Submit"}, ...]}
click_element(5) → Clicks "Submit" button
```

### Coordinate Normalization (0-1000)
AI uses resolution-independent coordinates:
```
click_at_normalized(500, 500) → Center of screen
click_at_normalized(0, 0) → Top-left
```

### Human-Like Mouse Movement
Bezier curves with random variations avoid bot detection.

### 400+ Command Library
```python
execute_command(700)  # Open Word
execute_command(836, "fix: bug")  # git commit
list_commands("browser")  # Find browser commands
```

---

## 🔧 Legacy Mode (Trigger-Based)

For direct LLM control via OCR triggers:

```bash
pip install ollama
ollama serve
python mewact_legacy.py --target "Chrome"
```

AI outputs triggers in chat:
```
1&&$47 open chrome 1$&47
2&&$47 type | hello world 2$&47
3&&$47 mew act 3$&47
```

See [documentation.md](documentation.md) for full legacy mode details.

---

## 📁 Files

| File | Purpose |
|------|---------|
| `mewact_mcp.py` | **MCP Server** - Main entry point for Claude/AI |
| `mewact_legacy.py` | Legacy mode + core engine |
| `command_library.json` | 400+ predefined commands |

---

## ⚠️ Security

- Runs with your user permissions
- Only use with trusted AI assistants
- Commands execute what AI requests

---

## 📖 Documentation

- [Full Documentation](documentation.md) - Architecture, commands, troubleshooting
- [Walkthrough](walkthrough.md) - Session-by-session development notes

---

<p align="center">
  <b>MewAct — AI Desktop Control</b><br>
  <i>MCP Server with Smart Screenshots + Human-Like Input</i>
</p>
