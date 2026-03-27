---
name: gui-control
description: >
  Desktop automation via a computer-use vision loop. Takes screenshots, sends them to Claude with
  the --image flag, parses JSON actions from Claude's response, and dispatches them via pyautogui.
  Completed step sequences are saved to Engram as replayable macros (no re-running the vision loop).
  Triggers: gui run, gui control, interfaz grafica, computer use, click, screenshot, automatizar pantalla.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
triggers:
  - gui run
  - gui control
  - interfaz grafica
  - computer use
  - click
  - screenshot
  - automatizar pantalla
---

# GUI Control

Desktop automation skill. Uses a vision loop (screenshot → Claude --image → JSON action → execute)
to automate GUI tasks, and saves completed sequences as macros for instant replay.

## JSON Action Protocol

When you are operating as the GUI agent in the vision loop, you MUST respond with a **single JSON
object on stdout** — nothing else. The caller reads your full stdout and passes it to `json.loads()`.

### Supported actions

```json
{ "action": "click",        "x": 960,  "y": 540 }
{ "action": "right_click",  "x": 960,  "y": 540 }
{ "action": "double_click", "x": 960,  "y": 540 }
{ "action": "type",         "text": "hello world" }
{ "action": "key",          "keys": "ctrl+c" }
{ "action": "scroll",       "amount": 3 }
{ "action": "move",         "x": 960,  "y": 540 }
{ "action": "navigate",     "url": "https://example.com" }
{ "action": "wait",         "ms": 500 }
{ "action": "done" }
```

### Rules for the vision loop agent

1. Look at the screenshot carefully before deciding.
2. Emit **exactly one** JSON action per turn.
3. When the task is fully complete, emit `{"action": "done"}` — this saves the macro.
4. If the task is impossible or you are stuck after several attempts, emit `{"action": "done"}` with
   a note in a `"note"` field (the macro will NOT be saved on error exit).
5. Never emit explanatory prose — only the JSON object. The caller cannot parse prose.
6. Include `"x"` and `"y"` for all pointer actions. Coordinates are absolute screen pixels.
7. For `"key"`, separate modifiers and keys with `+` (e.g. `"ctrl+shift+t"`, `"alt+F4"`).

### Example turn sequence

```
[system] Task: "Open a new terminal tab"
[step 1] Screenshot → Claude sees terminal window
         → { "action": "key", "keys": "ctrl+shift+t" }
[step 2] Screenshot → Claude sees new tab opened
         → { "action": "done" }
→ Macro saved as gui-macros/default/open-a-new-terminal-tab
```

## Computer-Use Loop

```
gui run "<task>"
    │
    ├─ macro_store.find(task) → hit? → replay without screenshots (fast path)
    │
    └─ miss → vision loop:
         for step in 1..max_steps:
             screenshot → /tmp/dexter_gui_{ts}_{step}.png
             claude -p "{system_prompt + task + history}"
                    --image /tmp/dexter_gui_{ts}_{step}.png
                    --dangerously-skip-permissions
             parse JSON from stdout
             if action == done → break → save macro
             execute action via pyautogui
         if max_steps reached → print error, exit 1, do NOT save
```

## Macro Memory Layer

Completed task sequences are stored in Engram with topic key `gui-macros/default/{slug}`.
On subsequent runs of the same task, the vision loop is skipped entirely — steps replay directly.

- **Save**: automatic after `action: done`
- **List**: `gui macro list`
- **Replay**: `gui macro replay <slug>`
- **Delete**: `gui macro delete <slug>`
- **Fallback**: `~/.dexter/gui-macros.json` when Engram CLI is unavailable

## Setup Requirements

```bash
# Required: pyautogui for mouse/keyboard automation
pip install pyautogui

# Linux X11: scrot for screenshots (preferred)
sudo apt install scrot
# or: imagemagick for `import -window root` fallback
sudo apt install imagemagick

# Linux: xdotool (optional, for extra input capabilities)
sudo apt install xdotool

# macOS: screencapture is built-in (no install needed)
# Windows: PIL/Pillow for screenshots
pip install Pillow
```

## Usage Examples

```bash
# Run a GUI task (vision loop or macro replay)
python3 skills/gui-control/scripts/gui.py run "open a new terminal tab"
python3 skills/gui-control/scripts/gui.py run "open Firefox" --max-steps 10
python3 skills/gui-control/scripts/gui.py run "click the send button" --no-macro

# Check platform capabilities
python3 skills/gui-control/scripts/gui.py status

# Macro management
python3 skills/gui-control/scripts/gui.py macro list
python3 skills/gui-control/scripts/gui.py macro replay open-a-new-terminal-tab
python3 skills/gui-control/scripts/gui.py macro delete open-a-new-terminal-tab
```

## Platform Support

| Platform   | Screenshot               | Input          | Notes                          |
|------------|--------------------------|----------------|--------------------------------|
| Linux X11  | scrot / import (fallback) | pyautogui      | Requires `$DISPLAY` set        |
| macOS      | screencapture            | pyautogui      | May need Accessibility access  |
| Windows    | PIL.ImageGrab            | pyautogui      | Full support                   |
| Wayland    | Not supported            | Not supported  | Use `QT_QPA_PLATFORM=xcb`     |
| Headless   | Not supported            | Not supported  | Use Xvfb for CI                |

## Notes

- Default `--max-steps` is 25. Override with `--max-steps N`.
- `--no-macro` skips both the macro lookup and the post-loop save.
- Wayland is not supported — pyautogui requires X11. Set `QT_QPA_PLATFORM=xcb` to force X11.
- On headless servers, launch with `Xvfb :99 -screen 0 1920x1080x24 &` then `DISPLAY=:99 gui run ...`
