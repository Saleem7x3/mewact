# 🐱 MewAct

**Give Any AI Chatbot Eyes and Hands**

> 🔮 **The Magic**: Ask Claude or ChatGPT to edit a document. ChatGPT outputs commands → MewAct reads them via OCR → Actions happen on your screen → ChatGPT sees the result and continues.

---

## ⚡ 30-Second Setup

```bash
pip install numpy opencv-python mss pyautogui colorama rapidocr-onnxruntime ollama pywin32 pillow

ollama serve                           # Start Ollama
python mewact_v13.py --target "Chrome"   # Run MewAct
```

---

## 🎭 Real Examples

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

## 🔮 The Magic Command: `mew act`

> **This is the secret sauce.** When the AI outputs `mew act`, MewAct grabs the current screen image and **automatically pastes it** into wherever your cursor is (the chat input box). No manual Ctrl+V needed!

```text
&&$47 1 mew act $$&47
```

**How it works:**

1. AI outputs `mew act` command
2. MewAct copies the current OCR screen to clipboard
3. MewAct **auto-pastes** (Ctrl+V) into the active text field
4. The screenshot appears in the AI chat — AI can now **see** the result!

> 💡 **Pro tip:** Click on the chat input box before running MewAct, so the auto-paste lands in the right place.

This creates a **visual feedback loop** — the AI sees what happened, adjusts, and continues until the task is done.

---

## 🤖 Commands

| Command | What it does |
|---------|--------------|
| `open <app>` | Launch any application |
| `type \| <text>` | Type text (short) |
| `type $V1` | Type variable (long text) |
| `click <text>` | Click button/link by text |
| `press <key>` | Press keyboard key |
| `wait <N>` | Wait N seconds |
| `mew act` | 📸 Screenshot + auto-paste |

Check the command library for all the hundreds of commands.

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

## 🎯 Run Options

```bash
# Target specific window
python mewact.py --target "Chrome"

# Target specific monitor
python mewact.py --monitors 1

# Multiple monitors
python mewact.py --monitors 1,2

# Interactive mode (menu)
python mewact.py
```

---

## 🤖 AI Setup (Choose Your Platform)

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
3. End with mew act to verify

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
  <b>🐱 MewAct — Where AI Gets Eyes and Hands</b><br>
  <i>Let your chatbot do more than just chat.</i>
</p>



