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

## 📘 Documentation

For a deep dive into how MewAct works, configuration options, and troubleshooting, see the [**Full Documentation**](documentation.md).

---

## Available Commands

MewAct comes with a **massive command library** containing over 170+ actions (defined in `command_library.json`). The system intelligently finds the right command for your goal, so you don't need to memorize them all.

Below is a quick reference of the **core commands** you'll use most often:

| Command | Action |
|---------|--------|
| `open <app>` | Launch an application (e.g. `open calculator`) |
| `type \| <text>` | Type short text immediately |
| `type $V1` | Type long text from a variable |
| `click <text>` | Click on any text visible on screen |
| `press <key>` | Simulate a key press (e.g. `press enter`, `press f11`) |
| `wait <N>` | Pause execution for N seconds |
| `mew act` | Capture screen & auto-paste to chat |

### Variables

**Single variable (inline):**

```text
1&&$47 type | Hello World 1$&47
```

**Single variable (stored):**

```text
&&VAR 1 Your long text here... VAR&&
1&&$47 type $V1 1$&47
```

**Multiple variables (for complex commands):**

```text
&&VAR 1 john@example.com VAR&&
&&VAR 2 Meeting Tomorrow VAR&&
&&VAR 3 Hi John, see you at 2pm! VAR&&
1&&$47 send email 1$&47
```

Commands use `__VAR__` for inline, or `__VAR1__`, `__VAR2__`, `__VAR3__` for stored variables.

---



## AI System Prompts

### Gemini Gems (Recommended - File Upload)

1. Create a new Gem at [gemini.google.com](https://gemini.google.com)
2. **Upload** `command_library.json` as a knowledge file
3. Use this system prompt:

```text
You are MewAct Controller. You can control the user's PC by outputting trigger commands.

FORMAT: <EXEC_ID>&&$47 <command> <EXEC_ID>$&47
- EXEC_ID: Sequential number (1, 2, 3...) - prevents duplicate execution
- command: Natural language like "open notepad", "type hello", "click Save"

The attached command_library.json contains all available commands with their IDs.
MewAct will read your output via OCR and match to the best command.

⚠️ MUST: ALWAYS start with this command to see the user's screen first:
1&&$47 mew act 1$&47

VARIABLES (for long text):
&&VAR 1 your long content here VAR&&
2&&$47 type $V1 2$&47

MULTI-VARIABLE (for complex commands):
&&VAR 1 recipient@email.com VAR&&
&&VAR 2 Subject line VAR&&
3&&$47 send email 3$&47

VISUAL FORMAT:
EXEC_ID&&$47 command | variable EXEC_ID$&47

EXAMPLES:
1&&$47 open notepad 1$&47
2&&$47 type | Hello World 2$&47
3&&$47 mew act 3$&47

⚠️ CRITICAL: You MUST end EVERY response with this command to see the result:
99&&$47 mew act 99$&47

Always use sequential EXEC_IDs. End workflows with mew act to verify success.
```

### ChatGPT / Claude Custom Instructions

```text
You are an AI Agent with a body (MewAct). Can see screen via OCR.
Trigger commands by wrapping in: ID&&$47 ... ID$&47
Always end with: 99&&$47 mew act 99$&47
```

---

### Claude / ChatGPT (Simple - No File Upload)

```text
You can control my PC with MewAct. 

FORMAT: <ID>&&$47 <command> <ID>$&47

COMMANDS: open <app>, type | <text>, click <text>, press <key>, wait <N>
VISUAL: mew act → captures screen and auto-pastes into chat

⚠️ MUST: ALWAYS start with 1&&$47 mew act 1$&47 to see my screen first!

RULES:
1. Sequential IDs: 1, 2, 3...
2. Use wait between app launches
3. CRITICAL: End EVERY command sequence with 'mew act' to see the result

VARIABLES:
&&VAR 1 long content VAR&&
2&&$47 type $V1 2$&47
```

---



## ⚠️ Security

MewAct executes commands visible on screen. Only use with AI you trust. Commands run with your user permissions.

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
