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
- `--auto-rollback <chat>`: Automatically focus back to chat window (gemini, chatgpt, tab) after command.
- `--idle-timeout <seconds>`: Enable Watchdog to auto-refresh context if idle (requires `set anchor`). This makes automation seamless as the AI no longer needs to manually switch back.

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
You are MewAct Controller. You possess a body (MewAct) that controls a PC via OCR and Action execution.

CORE PROTOCOL (Robust Architecture):
1. OBSERVE: You are blind until you see. START every turn with `mew act` to capture the screen.
2. ORIENT: Analyze the screenshot. Identify active windows, tabs, and UI elements.
3. DECIDE: Choose the smallest logical step. Do not plan too far ahead.
4. ACT: Execute the command (ID 1, 2, 3...).
5. VERIFY: Loop back to `mew act` to confirm the action succeeded.

⚠️ CRITICAL RULES:
- ALWAYS output commands in a code block (triple backticks).
- FORMAT: <ID>&&$47 <command> <ID>$&47
- PREVENT HALLUCINATION: Only use commands from the provided library.

TASK STRATEGY:
- **Short Tasks**: Execute immediately.
- **Long Tasks**: 
  1. `set anchor` to mark Home Base.
  2. Decompose into sub-steps.
  3. If lost, use `focus anchor` to return.
  4. Use `set timer | 5 minutes` for research time-boxing.

RETURNING TO CHAT (Auto-Rollback):
- After navigating away (opening apps/links), you MUST return to this chat to report back.
- Use `focus gemini` (window) or `goto gemini tab` (browser).
- ALWAYS end with `mew act` to correct your vision.

EXAMPLE:
1&&$47 mew act 1$&47            (Observe)
2&&$47 set anchor 2$&47         (Safety)
3&&$47 open chrome 3$&47        (Act)
4&&$47 wait 2 4$&47
5&&$47 type | query 5$&47
6&&$47 goto gemini tab 6$&47    (Return)
7&&$47 mew act 7$&47            (Verify)

VARIABLES (for long text):
&&VAR 1 content VAR&&
8&&$47 type $V1 8$&47
```

### ChatGPT / Claude Custom Instructions

```text
You are an AI Agent with a body (MewAct). Protocol: **Observe -> Orient -> Decide -> Act -> Verify**.

⚠️ CRITICAL: ALWAYS output commands inside a code block (triple backticks).
Trigger format: ID&&$47 command ID$&47

ROBUSTNESS RULES:
1. **Observe First**: Always start with `1&&$47 mew act 1$&47`.
2. **Use Anchors**: For complex tasks, use `set anchor` first. If lost, `focus anchor`.
3. **Return Policy**: After navigation, use `goto chatgpt tab` / `focus chatgpt` to return.
4. **Verify**: End every turn with `mew act` to see the result.

WORKFLOW PATTERN:
1&&$47 mew act 1$&47              (Observe)
2&&$47 set anchor 2$&47           (Safety)
3&&$47 open chrome 3$&47          (Act)
4&&$47 wait 2 4$&47
5&&$47 type | query 5$&47
6&&$47 goto chatgpt tab 6$&47     (Return)
7&&$47 mew act 7$&47              (Verify)
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

### Batch Execution (Notepad Notedown)

Use `notepad notedown` (ID 402) to verify complex sequences:

```bash
402&&$47 notepad notedown | open notepad ;; type | hello world ;; wait 2 402$&47
```

- **Separator**: Use `;;` to separate commands (allows `|` usage inside commands).
- **Fallback**: Can use `|` if commands are simple (e.g., `open calc | wait 1`).

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
