# MewAct

**AI Chatbot Desktop Automation Bridge**

> MewAct enables AI chatbots (Claude, ChatGPT, Gemini) to control your PC by converting text commands into actions. It uses OCR to see the screen and a local LLM to execute commands, creating a feedback loop between the cloud AI and your desktop.

---

## Installation

```bash
pip install numpy opencv-python mss pyautogui colorama rapidocr-onnxruntime ollama pywin32 pillow

# Optional: For better OCR accuracy (slower)
pip install easyocr
# OR for highest accuracy (heavy)
pip install paddlepaddle paddleocr

ollama serve                           # Start Ollama
python jama_v13.py --target "Chrome"   # Run MewAct
```

---

## Recommended Setup

For best results, **keep your AI chat window separate** from other browser tabs:

1. **Separate Window (Best)**: Right-click the ChatGPT/Gemini tab → "Move tab to new window"
2. **Separate Monitor (Ideal)**: If you have multiple monitors, put the chat on one and work on the other
3. **Minimize Tabs**: If using tabs, limit to 2 tabs (chat + work) so `switch tab` works reliably

This helps MewAct navigate back to the chat reliably after performing tasks.

---

## 🔄 Auto-Rollback

MewAct can automatically focus back to your chat window/tab after each command. This makes automation seamless as the AI no longer needs to manually switch back.

| Mode | CLI Flag | Use Case |
|------|----------|----------|
| **Tab Search** | `--auto-rollback gemini` | Same browser, many tabs (uses Ctrl+Shift+A) |
| **Tab Toggle** | `--auto-rollback tab` | Exactly 2 tabs (uses Ctrl+Tab) |
| **Window Switch** | `--auto-rollback window:ChatGPT` | Separate window (uses Windows API) |

**Example:**
```bash
python mew.py --auto-rollback gemini
```

---

## 🚀 Session 3 Enhancements
- **Anchor System**: `set anchor` / `focus anchor` to mark and return to specific windows.
- **Focus Control**: `focus window | title` and `focus chatgpt/gemini` commands.
- **Timer**: `set timer | duration` opens Google Timer.
- **Window Snapping**: `snap window [left/right/up]` for layout control.
- **Clipboard**: `mew act` now captures screen and `paste` command enables seamless feedback.

## Usage Examples

### Example 1: "Help me write an email"

**You:** "I need to send a quick email to John about the meeting tomorrow"

**Gemini:**

```text
I'll help you compose that email. Let me first see your screen:

1&&$47 mew act 1$&47
```

*Screenshot auto-pastes into chat*

**Gemini:**

```text
I can see Outlook is open. Let me compose the email:

2&&$47 click New Email 2$&47
3&&$47 wait 1 3$&47
4&&$47 type | john@company.com 4$&47
5&&$47 press tab 5$&47
6&&$47 type | Meeting Tomorrow 6$&47
7&&$47 press tab 7$&47
&&VAR 1 Hi John,

Just a reminder about our meeting tomorrow at 2 PM.
Let me know if you need to reschedule.

Best,
[Your name] VAR&&
8&&$47 type $V1 8$&47
9&&$47 mew act 9$&47

Let me verify the email looks correct...
```

---

### Example 2: "What's wrong with my code?"

**You:** "My Python code has a bug, can you check it?"

**Claude:**

```text
Let me see your screen:

1&&$47 mew act 1$&47
```

*Screenshot auto-pastes showing VS Code with error*

**Claude:**

```text
I see the issue! Line 42 has a missing colon. Let me fix it:

2&&$47 click line 42 2$&47
3&&$47 press end 3$&47
4&&$47 type | : 4$&47
5&&$47 press ctrl+s 5$&47
6&&$47 mew act 6$&47

Checking if that fixed it...
```

---

### Example 3: "Research this topic for me"

**You:** "Find me info about quantum computing breakthroughs in 2025"

**Claude:**

```text
I'll search that for you:

1&&$47 open chrome 1$&47
2&&$47 wait 2 2$&47
3&&$47 type | quantum computing breakthroughs 2025 3$&47
4&&$47 press enter 4$&47
5&&$47 wait 3 5$&47
6&&$47 mew act 6$&47

Let me summarize the results...
```

---

---



## AI System Prompts

### Gemini Gems (Recommended - File Upload)

1. Create a new Gem at [gemini.google.com](https://gemini.google.com)
2. **Upload** `command_library.json` as a knowledge file
3. Use this system prompt:

```text
You are MewAct Controller. You can control the user's PC by outputting trigger commands.

⚠️ CRITICAL: ALWAYS output commands inside a code block (triple backticks) to prevent formatting issues!

FORMAT: <EXEC_ID>&&$47 <command> <EXEC_ID>$&47
- EXEC_ID: Sequential number (1, 2, 3...) - prevents duplicate execution
- command: Natural language like "open notepad", "type hello", "click Save"

The attached command_library.json contains all available commands with their IDs.
MewAct will read your output via OCR and match to the best command.

⚠️ MUST: ALWAYS start with this command to see the user's screen first:
```
1&&$47 mew act 1$&47
```

VARIABLES (for long text):
&&VAR 1 your long content here VAR&&
2&&$47 type $V1 2$&47

RETURNING TO CHAT AFTER NAVIGATION:
When you navigate away (open link, switch apps), you MUST return to this chat:
- If chat is in SEPARATE WINDOW: use "focus gemini" or "focus chatgpt"
- If chat shares browser with OTHER TABS: use "goto gemini tab" (searches and switches)
- If only 2 TABS: use "switch tab" (Ctrl+Tab)
- If using external apps: use "focus window | title" or "focus anchor"
After returning, ALWAYS use "mew act" to paste your findings.

TAB DETECTION: Look at the first screenshot. Count browser tabs visible at top.
- 1 tab = You're in dedicated window (ideal setup)
- 2 tabs = Use "switch tab" to toggle
- 3+ tabs = Use "goto gemini tab" to search and switch

EXAMPLES:
1&&$47 mew act 1$&47
2&&$47 open chrome 2$&47
3&&$47 wait 2 3$&47
4&&$47 type | search query 4$&47
5&&$47 press enter 5$&47
6&&$47 wait 3 6$&47
7&&$47 goto gemini tab 7$&47     ← Return to chat
8&&$47 mew act 8$&47             ← Paste results

⚠️ CRITICAL: You MUST end EVERY response with "mew act" to see the result!
99&&$47 mew act 99$&47
```

### ChatGPT / Claude Custom Instructions

```text
You are an AI Agent with a body (MewAct). Can see screen via OCR.

⚠️ CRITICAL: ALWAYS output commands inside a code block (triple backticks) to prevent $ from being formatted!

Trigger format: ID&&$47 command ID$&47

CRITICAL RULES:
1. ALWAYS start with: `1&&$47 mew act 1$&47` (to see screen)
2. After ANY navigation (open app, click link, switch window):
   - Use "goto chatgpt tab" OR "focus chatgpt" to return here
   - Then "mew act" to share what you found
3. ALWAYS end with: `99&&$47 mew act 99$&47`

WORKFLOW PATTERN:
1&&$47 mew act 1$&47              ← See screen
2&&$47 open chrome 2$&47          ← Do task
3&&$47 wait 2 3$&47
4&&$47 type | query 4$&47
5&&$47 press enter 5$&47
6&&$47 wait 3 6$&47
7&&$47 goto chatgpt tab 7$&47     ← RETURN TO CHAT
8&&$47 mew act 8$&47              ← Share results
```

---

### Claude / ChatGPT (Simple - No File Upload)

```text
You can control my PC with MewAct. 

FORMAT: <ID>&&$47 <command> <ID>$&47

COMMANDS: open <app>, type | <text>, click <text>, press <key>, wait <N>, set timer | <time>, set anchor, focus <window>
VISUAL: mew act → captures screen and auto-pastes into chat
FOCUS: goto chatgpt tab OR focus chatgpt → return to this chat

⚠️ CRITICAL WORKFLOW:
1. ALWAYS start with: 1&&$47 mew act 1$&47 (see screen first)
2. After ANY navigation: "goto chatgpt tab" + "mew act" (return & share)
3. ALWAYS end with: 99&&$47 mew act 99$&47

VARIABLES:
&&VAR 1 long content VAR&&
2&&$47 type $V1 2$&47

EXAMPLE:
1&&$47 mew act 1$&47
2&&$47 open chrome 2$&47
3&&$47 wait 2 3$&47
4&&$47 goto chatgpt tab 4$&47   ← Return here!
5&&$47 mew act 5$&47            ← Show results
```

---

## 📘 Documentation

For a deep dive into how MewAct works, execution types, and technical details, see the [**Full Documentation**](documentation.md).

---

## Available Commands

MewAct comes with a **massive command library** (defined in `command_library.json`). The system intelligently matches your goal to the best command.

| Command | Action |
|---------|--------|
| `open <app>` | Launch an application (e.g. `open calculator`) |
| `type \| <text>` | Type short text immediately |
| `type $V1` | Type long text from a variable |
| `click <text>` | Click on any text visible on screen |
| `press <key>` | Simulate a key press (e.g. `press enter`, `press f11`) |
| `wait <N>` | Pause execution for N seconds |
| `mew act` | Capture screen & auto-paste to chat |
| `set timer | <duration>` | Set Google timer (e.g. `5 minutes`) |
| `set anchor` / `focus anchor` | Mark and return to window/position |
| `focus window | <title>` | Switch to specific window |
| `snap window [left/right]` | Split screen management |

### Execution Types

| Type | Example |
|------|---------|
| `python` | Normal Python automation code |
| `hotkey` | `copy`, `paste`, `undo`, `redo`, `save` |
| `shell` | `run powershell \| <cmd>`, `list files`, `system info` |
| `url` | `open url \| <url>`, `open google`, `open github` |
| `file` | `open file \| <path>`, `open file dialog` |
| `sequence` | Chain multiple command IDs |

---

## ⚠️ Security

MewAct executes commands visible on screen. Only use with AI you trust. Commands run with your user permissions.

---

### 🖥️ Multi-Monitor Setup
Target specific screens in a multi-monitor environment (e.g., utilize only 2 screens out of 5):

```bash
# Capture only Monitor 2 and Monitor 4
python mew.py --monitors 2,4
```

Combine with scan modes:
```bash
# Scan only windows present on Monitor 2 (ignoring other screens)
python mew.py --monitors 2 --scan-mode window
```
```bash
# Scan Monitor 3 full-screen and Monitor 5 window-by-window
python mew.py --monitors 3,5 --monitor-strategy window
```

### ⚡ Performance Optimization
Toggle Adaptive OCR to save resources on low-end machines:
```bash
python mew.py --power-saver
```
This splits large windows into strips to reduce memory spikes.

---

## 💖 Support Me

If MewAct helped you, consider buying me a coffee!

<p align="center">
  <img src="https://drive.google.com/file/d/1b8JFHnbcMP9r1GvBFUQTxKd7sBJxzSKz/view?usp=sharing" alt="UPI QR Code" width="250"><br>
  <b>UPI ID:</b> <code>arshiyatamanna07@okhdfcbank</code>
</p>

---

<p align="center">
  <b>MewAct — AI Desktop Automation</b><br>
  <i>Bridge for Cloud AI and Local Execution</i>
</p>
