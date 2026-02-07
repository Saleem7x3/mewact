# MewAct Technical Documentation

## Overview

MewAct is a bridge system that enables Cloud-based LLMs (Claude, ChatGPT, Gemini) to execute desktop automation tasks through a Perception-Cognition-Action framework. The system uses OCR for screen perception, a local LLM for command selection, and PyAutoGUI for action execution.

---

## Architecture

### System Components

MewAct operates as a three-layer agent system:

```mermaid
graph TB
    subgraph "Cloud Layer"
        A[Cloud LLM<br/>Claude/GPT/Gemini]
    end
    
    subgraph "Local Processing Layer"
        B[Perception Engine<br/>OCR Screen Capture]
        C[Cognitive Planner<br/>Local LLM + Command Matching]
        D[Action Executor<br/>PyAutoGUI + Code Execution]
    end
    
    subgraph "System Layer"
        E[Desktop Environment<br/>Applications & Windows]
        F[Command Library<br/>170+ Actions]
    end
    
    A -->|Trigger Commands<br/>ID&&$47 ... ID$&47| B
    B -->|Screen Text & Coordinates| C
    C -->|Query| F
    F -->|Matched Command| C
    C -->|Execute Code| D
    D -->|Perform Actions| E
    E -->|Visual Feedback| B
    B -->|Screenshot| A
```

### Process Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Cloud LLM
    participant P as Perception Engine
    participant G as Cognitive Planner
    participant L as Command Library
    participant A as Action Executor
    participant D as Desktop
    
    U->>C: Request task
    C->>P: 1&&$47 mew act 1$&47
    P->>D: Capture screen
    D-->>P: Screenshot
    P->>P: OCR processing
    P-->>C: Auto-paste screenshot
    C->>C: Analyze & plan
    C->>P: 2&&$47 open chrome 2$&47
    P->>G: Parse trigger
    G->>L: Find "open chrome"
    L-->>G: Command ID & code
    G->>A: subprocess.Popen('chrome')
    A->>D: Execute
    D-->>P: Screen state changes
```

---

## Component Details

### 1. Perception Engine

**Purpose**: Captures and processes visual information from the desktop environment.

**Implementation**:
- **Screen Capture**: Uses `mss` library for multi-monitor screenshot capture
- **OCR Processing**: Supports three OCR engines with automatic fallback:
  - **RapidOCR** (default): Fast, CPU-based, 4 threads
  - **EasyOCR**: Higher accuracy, GPU optional
  - **PaddleOCR**: Highest accuracy, angle detection support
- **Text Normalization**: Unicode NFKD normalization to handle styled fonts (mathematical alphanumeric symbols)
- **Output**: Text coordinates `{text, x, y}` and full text string

**Key Features**:
- Window-specific targeting via Win32 API
- Multi-monitor support with selective capture
- Clipboard integration for `mew act` command

### 2. Cognitive Planner

**Purpose**: Interprets Cloud LLM commands and selects appropriate actions from the command library.

**Processing Pipeline**:

```mermaid
flowchart LR
    A[OCR Text] --> B{Trigger Pattern<br/>Match?}
    B -->|No| A
    B -->|Yes| C[Extract ID & Command]
    C --> D[Keyword Extraction]
    D --> E[Fuzzy Match<br/>Command Library]
    E --> F[Top 15 Candidates]
    F --> G[Local LLM<br/>Final Selection]
    G --> H[Command ID]
    H --> I[Action Executor]
```

**Trigger Format**:
- Pattern: `(\d+)&&\$47\s*(.*?)\s*\1\$&47`
- Example: `5&&$47 open chrome 5$&47`
- ID matching ensures sequential execution and prevents duplicate triggers

**Command Selection**:
1. **Stage 1 (Keyword Filtering)**: Extract keywords from user goal, fuzzy match against 170+ commands
2. **Stage 2 (LLM Selection)**: Top 15 candidates sent to local LLM (Gemma/Llama via Ollama) for final selection
3. **Stage 3 (Validation)**: Verify command exists and is executable

### 3. Action Executor

**Purpose**: Executes the selected command code with variable injection.

**Execution Types**:
- **Python Code**: Direct execution via `exec()` in sandboxed context
- **Shell Commands**: Execute via `subprocess.Popen()`

**Variable System**:

| Type | Format | Example | Injection |
|------|--------|---------|-----------|
| Inline | `command \| text` | `type \| hello` | `__VAR__` |
| Stored | `$V1`, `$V2` | `&&VAR 1 content VAR&&` | `__VAR1__`, `__VAR2__` |
| Implicit | No separator | `type hello` | Extracted via LLM prompt |

**Safety Features**:
- Execution ID tracking (prevents duplicate execution)
- Command validation before execution
- Error handling with graceful fallback
- Session recording capability

---

## Visual Feedback Loop

The `mew act` command creates a closed perception-action loop:

```mermaid
stateDiagram-v2
    [*] --> CloudLLM: User request
    CloudLLM --> PerceptionEngine: mew act trigger
    PerceptionEngine --> OCR: Capture screen
    OCR --> Clipboard: Copy image
    Clipboard --> AutoPaste: Ctrl+V + Enter
    AutoPaste --> CloudLLM: Screenshot visible
    CloudLLM --> CommandOutput: Analyze & respond
    CommandOutput --> ActionExecutor: Next command
    ActionExecutor --> DesktopState: Execute action
    DesktopState --> PerceptionEngine: State changed
```

**Technical Details**:
- **Image Format**: BGRA → RGB conversion → BMP clipboard format
- **Auto-paste Mechanism**: `pyautogui.hotkey('ctrl', 'v')` + `pyautogui.press('enter')`
- **Timing**: 300ms clipboard delay, 500ms paste delay
- **Requirements**: Cursor must be in chat input field

---

## Configuration

### Command-Line Interface

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--target` | String | Focus on specific window title | `--target "Chrome"` |
| `--monitors` | List[Int] | Monitor indices (1-based) | `--monitors 1,2` |
| `--ocr` | String | OCR engine selection | `rapidocr`, `easyocr`, `paddleocr` |

### Configuration Constants

```python
MODEL_NAME = "gemma3:4b-cloud"    # Local LLM model
OCR_ENGINE = "rapidocr"           # OCR engine
TARGET_WINDOW_TITLE = ""          # Window filter
TARGET_MONITORS = []              # Monitor list (empty = all)
LOOP_DELAY = 0.2                  # Processing loop delay (seconds)
```

### Environment Requirements

| Dependency | Purpose | Installation |
|------------|---------|--------------|
| `numpy` | Array processing | `pip install numpy` |
| `opencv-python` | Image processing | `pip install opencv-python` |
| `mss` | Screen capture | `pip install mss` |
| `pyautogui` | Desktop automation | `pip install pyautogui` |
| `rapidocr-onnxruntime` | OCR (default) | `pip install rapidocr-onnxruntime` |
| `ollama` | Local LLM | `pip install ollama` + `ollama serve` |
| `pywin32` | Windows API | `pip install pywin32` |

---

## Troubleshooting

### Detection Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Trigger not detected | Window not visible | Ensure target window is on top |
| Trigger not detected | Stylish fonts | System normalizes unicode automatically (NFKD) |
| Trigger not detected | ID mismatch | Ensure opening and closing IDs match: `5&&$47 ... 5$&47` |
| Partial trigger detected | Multi-line command | Use explicit ID wrapping format |

### OCR Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Low accuracy | Poor contrast | Use dark mode or high-contrast themes |
| Missing text | Transparent background | Avoid busy/transparent backgrounds |
| Wrong coordinates | DPI scaling | Set Windows Display Scaling to 100% or run as Administrator |

### Execution Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Command not found | Library mismatch | Verify command exists in `command_library.json` |
| LLM timeout | Ollama not running | Ensure `ollama serve` is active |
| Variable not replaced | Variable not defined | Define variable with `&&VAR <id> ... VAR&&` before use |
| Duplicate execution | Repeated ID | Always increment ID: 1, 2, 3, ... |

### Performance Optimization

| Optimization | Recommendation | Impact |
|--------------|----------------|--------|
| Wait commands | Add `wait 1` after app launches | Prevents race conditions |
| Variable usage | Use `&&VAR` for text >50 chars | Reduces OCR processing time |
| Command splitting | Split complex actions | Improves reliability |
| Monitor targeting | Target specific monitors | Reduces OCR processing area |

---

## Technical Specifications

### Trigger Pattern Regex

```regex
(\d+)&&\$47\s*(.*?)\s*\1\$&47
```

- **Group 1**: Execution ID (digits only)
- **Group 2**: Command text
- **Backreference**: `\1` ensures closing ID matches opening ID

### Variable Pattern Regex

```regex
&&VAR\s*(\d+)\s+(.*?)\s*VAR&&
```

- **Group 1**: Variable ID
- **Group 2**: Variable content (captured with `re.DOTALL`)

### OCR Text Normalization

```python
unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
```

Converts mathematical alphanumeric symbols (U+1D400–U+1D7FF) to standard ASCII.

---

## Security Considerations

⚠️ **Critical**: MewAct executes arbitrary code visible on screen.

**Threat Model**:
- Code execution runs with user permissions
- No sandbox or privilege separation
- OCR-based command injection possible if malicious content displayed

**Mitigations**:
- Only use with trusted Cloud LLMs
- Execute ID deduplication prevents replay attacks
- Keyword filtering reduces attack surface
- Monitor OCR output in debug mode

**Recommended Practice**:
- Run in isolated VM for testing
- Review `command_library.json` regularly
- Use `--target` flag to limit scope
- Enable debug mode for initial testing
