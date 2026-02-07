<<<<<<< HEAD
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

## 🧠 How It Works: The MewAct Framework

MewAct isn't just a script; it's a **Perception-Cognition-Action** loop that turns any LLM into an agent.

### 1. The Cloud Brain (Claude/Gemini/GPT)
- **Role:** High-level reasoning, planning, and goal setting.
- **Input:** User prompt ("Send an email") + Screen Context (via `mew act`).
- **Output:** A structured trigger command: `1&&$47 open outlook 1$&47`.

### 2. The Local Cortex (MewAct + Ollama)
This Python script acts as the body, running a continuous feedback loop:

- **👁️ Perception Engine (`PerceptionEngine`)**:
  - Captures the screen (mss)
  - Reads text coordinates (OCR: RapidOCR/EasyOCR/PaddleOCR)
  - Identifies windows and monitors

- **🧠 Cognitive Planner (`CognitivePlanner`)**:
  - Detects the trigger from the Cloud Brain.
  - **Smart Filtering:** Extracts keywords from the goal ("open outlook").
  - **Local LLM Decision:** Uses a small, fast local model (Gemma/Llama via Ollama) to pick the *exact* Command ID from the library that matches the goal.
  - *Why?* This prevents the Cloud AI from needing to memorize 170+ command IDs perfectly. It just states the intent!

- **⚡ Action Executor (`ActionExecutor`)**:
  - Executes the Python code associated with the ID.
  - Handles variable injection (`$V1` → `__VAR1__`).
  - Performs the physical mouse clicks/keystrokes (PyAutoGUI).

### 3. The Visual Feedback Loop
- The cycle closes when the Cloud Brain requests `mew act`.
- MewAct captures the result and **auto-pastes** it back to the chat.
- The Cloud Brain sees the effect of its action and plans the next step.

---

## Visual Feedback: `mew act`

The `mew act` command triggers a screen capture and automatic paste action. This allows the AI to "see" the result of its previous commands.

```text
1&&$47 mew act 1$&47
```

**Workflow:**

1. AI outputs `mew act` command
2. MewAct captures the screen via OCR
3. MewAct copies the image and **automatically pastes** (Ctrl+V) it into the chat
4. The AI analyzes the screenshot and determines the next step

> **Note:** Ensure the cursor is in the chat input box before `mew act` triggers.

```text
1&&$47 mew act 1$&47
```

**How it works:**

1. AI outputs `mew act` command
2. MewAct copies the current OCR screen to clipboard
3. MewAct **auto-pastes** (Ctrl+V) into the active text field
4. The screenshot appears in the AI chat — AI can now **see** the result!

> 💡 **Pro tip:** Click on the chat input box before running MewAct, so the auto-paste lands in the right place.

This creates a closed feedback loop for autonomous operation.

---

## Available Commands

MewAct provides a streamlined set of commands to control any application:

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

## Configuration & CLI

```bash
# Target specific window
python jama_v13.py --target "Chrome"

# Target specific monitor
python jama_v13.py --monitors 1

# Multiple monitors
python jama_v13.py --monitors 1,2

# Interactive mode (menu)
python jama_v13.py
```

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
N&&$47 mew act N$&47

Always use sequential EXEC_IDs. End workflows with mew act to verify success.
```

### ChatGPT / Claude Custom Instructions

```text
You are an AI Agent with a body (MewAct). Can see screen via OCR.
Trigger commands by wrapping in: ID&&$47 ... ID$&47
Always end with: N&&$47 mew act N$&47
```

---

### Claude / ChatGPT (Simple - No File Upload)

```text
You can control my PC with MewAct. 

FORMAT: &&$47 <ID> <command> $$&47

COMMANDS: open <app>, type | <text>, click <text>, press <key>, wait <N>
VISUAL: mew act → captures screen and auto-pastes into chat

⚠️ MUST: ALWAYS start with &&$47 1 mew act $$&47 to see my screen first!

RULES:
1. Sequential IDs: 1, 2, 3...
2. Use wait between app launches
3. CRITICAL: End EVERY command sequence with 'mew act' to see the result

VARIABLES:
&&VAR 1 long content VAR&&
&&$47 2 type $V1 $$&47
```

---

## 💡 Best Practices & Troubleshooting

### 🚀 Optimizing AI Performance
- **Wait Commands**: Always include `wait 1` or `wait 2` after opening apps or clicking buttons. **Crucial for stability!**
- **Window Focus**: If the AI needs to switch tabs, use `click <tab name>` explicitly or `press ctrl+tab`.
- **Variable Usage**: Use `&&VAR` for any text longer than 50 characters to keep the trigger processing fast.
- **Sequential IDs**: Ensure the `EXEC_ID` always increments. If you repeat an ID, MewAct will ignore it (to prevent infinite loops).

### 🔧 Common Fixes
- **Splitting Commands**: Complex actions work best when split. Instead of "type url and press enter", do:
  1. `type | url`
  2. `press enter`
- **Implicit Variables**: `type hello` now works without the `|` separator, but for complex text, `type | text` is safer.
- **DPI / Scaling Issues**: If clicks are landing in the wrong spot, ensure your Windows Display Scaling is set to 100% or that you've run the script with Administrator privileges.
- **OCR Accuracy**: MewAct works best on dark mode or high-contrast themes. Avoid busy/transparent backgrounds.
- **Ollama Timeout**: If you see "LLM call failed", ensure `ollama serve` is running and the model (`gemma3:4b-cloud` by default) is downloaded.
- **Trigger Not Found**: The trigger must be visible on screen. If ChatGPT is hidden behind another window, MewAct can't see the commands!

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
=======
🐱# MewAct

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

&&$47 1 mew act $$&47
```

*Screenshot auto-pastes into chat*

**Gemini:**

```text
I can see Outlook is open. Let me compose the email:

&&$47 2 click New Email $$&47
&&$47 3 wait 1 $$&47
&&$47 4 type | john@company.com $$&47
&&$47 5 press tab $$&47
&&$47 6 type | Meeting Tomorrow $$&47
&&$47 7 press tab $$&47
&&VAR 1 Hi John,

Just a reminder about our meeting tomorrow at 2 PM.
Let me know if you need to reschedule.

Best,
[Your name] VAR&&
&&$47 8 type $V1 $$&47
&&$47 9 mew act $$&47

Let me verify the email looks correct...
```

---

### Example 2: "What's wrong with my code?"

**You:** "My Python code has a bug, can you check it?"

**Claude:**

```text
Let me see your screen:

&&$47 1 mew act $$&47
```

*Screenshot auto-pastes showing VS Code with error*

**Claude:**

```text
I see the issue! Line 42 has a missing colon. Let me fix it:

&&$47 2 click line 42 $$&47
&&$47 3 press end $$&47
&&$47 4 type | : $$&47
&&$47 5 press ctrl+s $$&47
&&$47 6 mew act $$&47

Checking if that fixed it...
```

---

### Example 3: "Research this topic for me"

**You:** "Find me info about quantum computing breakthroughs in 2025"

**Claude:**

```text
I'll search that for you:

&&$47 1 open chrome $$&47
&&$47 2 wait 2 $$&47
&&$47 3 type | quantum computing breakthroughs 2025 $$&47
&&$47 4 press enter $$&47
&&$47 5 wait 3 $$&47
&&$47 6 mew act $$&47

Let me summarize the results...
```

---

## 🧠 How It Works: The MewAct Framework

MewAct isn't just a script; it's a **Perception-Cognition-Action** loop that turns any LLM into an agent.

### 1. The Cloud Brain (Claude/Gemini/GPT)
- **Role:** High-level reasoning, planning, and goal setting.
- **Input:** User prompt ("Send an email") + Screen Context (via `mew act`).
- **Output:** A structured trigger command: `&&$47 1 open outlook $$&47`.

### 2. The Local Cortex (MewAct + Ollama)
This Python script acts as the body, running a continuous feedback loop:

- **👁️ Perception Engine (`PerceptionEngine`)**:
  - Captures the screen (mss)
  - Reads text coordinates (OCR: RapidOCR/EasyOCR/PaddleOCR)
  - Identifies windows and monitors

- **🧠 Cognitive Planner (`CognitivePlanner`)**:
  - Detects the trigger from the Cloud Brain.
  - **Smart Filtering:** Extracts keywords from the goal ("open outlook").
  - **Local LLM Decision:** Uses a small, fast local model (Gemma/Llama via Ollama) to pick the *exact* Command ID from the library that matches the goal.
  - *Why?* This prevents the Cloud AI from needing to memorize 170+ command IDs perfectly. It just states the intent!

- **⚡ Action Executor (`ActionExecutor`)**:
  - Executes the Python code associated with the ID.
  - Handles variable injection (`$V1` → `__VAR1__`).
  - Performs the physical mouse clicks/keystrokes (PyAutoGUI).

### 3. The Visual Feedback Loop
- The cycle closes when the Cloud Brain requests `mew act`.
- MewAct captures the result and **auto-pastes** it back to the chat.
- The Cloud Brain sees the effect of its action and plans the next step.

---

## Visual Feedback: `mew act`

The `mew act` command triggers a screen capture and automatic paste action. This allows the AI to "see" the result of its previous commands.

```text
&&$47 1 mew act $$&47
```

**Workflow:**

1. AI outputs `mew act` command
2. MewAct captures the screen via OCR
3. MewAct copies the image and **automatically pastes** (Ctrl+V) it into the chat
4. The AI analyzes the screenshot and determines the next step

> **Note:** Ensure the cursor is in the chat input box before `mew act` triggers.

```text
&&$47 1 mew act $$&47
```

**How it works:**

1. AI outputs `mew act` command
2. MewAct copies the current OCR screen to clipboard
3. MewAct **auto-pastes** (Ctrl+V) into the active text field
4. The screenshot appears in the AI chat — AI can now **see** the result!

> 💡 **Pro tip:** Click on the chat input box before running MewAct, so the auto-paste lands in the right place.

This creates a closed feedback loop for autonomous operation.

---

## Available Commands

MewAct provides a streamlined set of commands to control any application:

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
&&$47 1 type | Hello World $$&47
```

**Single variable (stored):**

```text
&&VAR 1 Your long text here... VAR&&
&&$47 1 type $V1 $$&47
```

**Multiple variables (for complex commands):**

```text
&&VAR 1 john@example.com VAR&&
&&VAR 2 Meeting Tomorrow VAR&&
&&VAR 3 Hi John, see you at 2pm! VAR&&
&&$47 1 send email $$&47
```

Commands use `__VAR__` for inline, or `__VAR1__`, `__VAR2__`, `__VAR3__` for stored variables.

---

## Configuration & CLI

```bash
# Target specific window
python jama_v13.py --target "Chrome"

# Target specific monitor
python jama_v13.py --monitors 1

# Multiple monitors
python jama_v13.py --monitors 1,2

# Interactive mode (menu)
python jama_v13.py
```

---

## AI System Prompts

### Gemini Gems (Recommended - File Upload)

1. Create a new Gem at [gemini.google.com](https://gemini.google.com)
2. **Upload** `command_library.json` as a knowledge file
3. Use this system prompt:

```text
You are MewAct Controller. You can control the user's PC by outputting trigger commands.

FORMAT: &&$47 <EXEC_ID> <command> $$&47
- EXEC_ID: Sequential number (1, 2, 3...) - prevents duplicate execution
- command: Natural language like "open notepad", "type hello", "click Save"

The attached command_library.json contains all available commands with their IDs.
MewAct will read your output via OCR and match to the best command.

⚠️ MUST: ALWAYS start with this command to see the user's screen first:
&&$47 1 mew act $$&47

VARIABLES (for long text):
&&VAR 1 your long content here VAR&&
&&$47 2 type $V1 $$&47

MULTI-VARIABLE (for complex commands):
&&VAR 1 recipient@email.com VAR&&
&&VAR 2 Subject line VAR&&
&&$47 3 send email $$&47

VISUAL FEEDBACK:
&&$47 N mew act $$&47
This captures the screen and AUTO-PASTES it into chat. Use after actions to see results.

⚠️ CRITICAL: You MUST end EVERY response with this command to see the result:
&&$47 N mew act $$&47

Always use sequential EXEC_IDs. End workflows with mew act to verify success.
```

---

### ChatGPT Custom GPT (File Upload)

1. Create a GPT at [chat.openai.com](https://chat.openai.com)
2. Upload `command_library.json` to Knowledge
3. Use the same prompt as Gemini above

---

### Claude / ChatGPT (Simple - No File Upload)

```text
You can control my PC with MewAct. 

FORMAT: &&$47 <ID> <command> $$&47

COMMANDS: open <app>, type | <text>, click <text>, press <key>, wait <N>
VISUAL: mew act → captures screen and auto-pastes into chat

⚠️ MUST: ALWAYS start with &&$47 1 mew act $$&47 to see my screen first!

RULES:
1. Sequential IDs: 1, 2, 3...
2. Use wait between app launches
3. CRITICAL: End EVERY command sequence with 'mew act' to see the result

VARIABLES:
&&VAR 1 long content VAR&&
&&$47 2 type $V1 $$&47
```

---

## 💡 Best Practices & Troubleshooting

### 🚀 Optimizing AI Performance
- **Wait Commands**: Always include `wait 1` or `wait 2` after opening apps or clicking buttons to allow UI loading.
- **Variable Usage**: Use `&&VAR` for any text longer than 50 characters to keep the trigger processing fast.
- **Sequential IDs**: Ensure the `EXEC_ID` always increments. If you repeat an ID, MewAct will ignore it (to prevent infinite loops).

### 🔧 Common Fixes
- **DPI / Scaling Issues**: If clicks are landing in the wrong spot, ensure your Windows Display Scaling is set to 100% or that you've run the script with Administrator privileges.
- **OCR Accuracy**: MewAct works best on dark mode or high-contrast themes. Avoid busy/transparent backgrounds.
- **Ollama Timeout**: If you see "LLM call failed", ensure `ollama serve` is running and the model (`gemma3:4b-cloud` by default) is downloaded.
- **Trigger Not Found**: The trigger must be visible on screen. If ChatGPT is hidden behind another window, MewAct can't see the commands!

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

>>>>>>> 0d0721b0c0ed839e678c8c932ae16837c087b8cb
