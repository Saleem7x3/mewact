# MewAct Technical Documentation

## Architecture

MewAct operates in two modes:

### Mode 1: MCP Server (Recommended)
```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│ Claude/GPT  │────▶│  mew_mcp.py     │────▶│   Desktop   │
│ (AI Client) │◀────│  (MCP Server)   │◀────│   Windows   │
└─────────────┘     └─────────────────┘     └─────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ mew.py core   │
                    │ (OCR, Input)  │
                    └───────────────┘
```

### Mode 2: Legacy (OCR Trigger)
```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│ Cloud LLM   │────▶│   Screen OCR    │────▶│   mew.py    │
│ (Chat)      │◀────│   (Triggers)    │◀────│   Engine    │
└─────────────┘     └─────────────────┘     └─────────────┘
```

---

## MCP Server Features

### Smart Screenshots
- Windows UI Automation (pywinauto) detects buttons, links, inputs
- OCR fallback for text-only elements
- Elements numbered 0-29 with red circles
- Image optimized to max 1568px edge

### Coordinate System
```python
# Normalized coordinates (0-1000)
click_at_normalized(500, 500)  # Center
click_at_normalized(0, 0)      # Top-left
click_at_normalized(1000, 1000) # Bottom-right

# Formula: X_pixel = (X_norm / 1000) × W_display
```

### Human-Like Input
- Bezier curve mouse movements
- Random timing variations (20-60ms between keystrokes)
- Avoids bot detection

### HiDPI Support
- Auto-detects Windows DPI scaling
- Coordinates auto-adjusted for 4K displays

---

## Command Library (400+)

### Categories
| Category | ID Range | Examples |
|----------|----------|----------|
| Core | 100-199 | type, click, wait, mew act |
| System | 500-599 | task manager, settings, explorer |
| Browser | 600-699 | chrome, new tab, refresh |
| Office | 700-799 | word, excel, powerpoint |
| Dev Tools | 800-899 | vs code, git, npm |
| Communication | 900-959 | discord, slack, zoom |

### Command Types
| Type | Example |
|------|---------|
| `python` | `pyautogui.click(100, 200)` |
| `hotkey` | `{"keys": ["ctrl", "c"]}` |
| `shell` | `{"code": "dir"}` |
| `url` | `{"url": "https://google.com"}` |
| `sequence` | `{"steps": [101, 106]}` |

---

## Legacy Mode

### Trigger Format
```
<ID>&&$47 <command> <ID>$&47
```

Example:
```
1&&$47 open chrome 1$&47
2&&$47 type | hello 2$&47
3&&$47 mew act 3$&47
```

### Variables
```
&&VAR 1 Long text content VAR&&
4&&$47 type $V1 4$&47
```

### CLI Arguments
| Flag | Description |
|------|-------------|
| `--target "Chrome"` | Focus on specific window |
| `--monitors 1,2` | Target specific monitors |
| `--ocr rapidocr` | OCR engine (rapidocr, easyocr, paddleocr) |
| `--auto-rollback gemini` | Auto-focus back to chat |
| `--power-saver` | Adaptive OCR for low-end machines |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Element not found | Run `capture_screen()` first |
| Wrong click location | Check DPI scaling, use normalized coords |
| Slow OCR | Use `--power-saver` or target specific window |
| Command not found | Use `list_commands("keyword")` to search |

---

## Security

- Runs with user permissions
- No sandboxing
- Only use with trusted AI
- Review command_library.json before use

---

## Dependencies

```bash
# Required
pip install mcp pyautogui mss opencv-python numpy pillow colorama pywin32

# MCP Mode (recommended)
pip install pywinauto

# Legacy Mode
pip install ollama rapidocr-onnxruntime
```
