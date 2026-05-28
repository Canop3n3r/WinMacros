# WinMacros

A simple, effective, and lightweight macros tool for Windows.

Create text-insertion macros, assign global hotkeys, toggle them on/off, and run them from anywhere.

## Features (v1)

- **Create macros** with a name and the text they should insert
- **Global hotkeys** — works in any application (Ctrl+Alt+... etc.)
- **Enable / disable** individual macros instantly
- **Test** any macro immediately
- **Capture hotkeys** with a single click (no manual typing)
- **Runs in the background** via system tray
- **Persists** all your macros automatically
- Clean modern UI (Windows 11 friendly)

## Installation

1. Make sure you have **Python 3.10+** installed (from python.org or Microsoft Store)
2. Open PowerShell or Command Prompt in this folder
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

## How to Run

**Recommended (no console window):**

```powershell
# Double-click this file, or run from terminal:
.\launch_silent.bat
```

Or with visible console (useful for seeing errors):

```powershell
python main.py
```

- The window will open.
- Create your first macro.
- Close the window (or minimize) — it keeps running in the **system tray** (look for the blue square with "M" near the clock).

To fully exit: right-click the tray icon → Exit.

## Usage

1. Click **New Macro**
2. Give it a name (e.g. "Email Signature")
3. Click **Capture Hotkey** and press your desired combination (e.g. `Ctrl + Alt + S`)
4. Type or paste the text you want inserted when the hotkey is pressed
5. Choose a typing speed (Instant works for most apps)
6. Save — the macro is immediately active
7. Switch to any app (Notepad, browser, Discord, VS Code...) and press your hotkey

The text will be typed exactly where your cursor is.

### Recommended Hotkeys

Avoid overriding common Windows shortcuts. Good patterns:
- `Ctrl + Alt + letter`
- `Ctrl + Shift + letter`
- `Win + Alt + letter`

## Data Location

All macros are saved to:

```
%APPDATA%\WinMacros\macros.json
```

You can back this file up or copy it to another machine.

## Tips & Notes

- Some games and certain full-screen apps may not receive simulated input (Windows security / UIPI).
- If a hotkey does nothing, make sure the macro is **enabled** and no other program is using the same combination.
- For very large text blocks or picky apps (terminals, some Electron apps), try the **"paste"** mode or a slower typing speed.
- The app must be running (even when the window is closed / in tray) for hotkeys to work.

### Hotkeys not working?

1. Try running as Administrator (right-click `launch_silent.bat` → Run as administrator).
2. Some security software or other macro tools (AutoHotkey, PowerToys, etc.) can block hooks.
3. The `keyboard` library is very reliable but occasionally needs elevation on locked-down Windows setups.

## Future Ideas (v2+)

- Recorded key sequences (play back complex actions)
- Mouse actions
- Variables / date insertion (e.g. {{date}})
- Import / export .json
- Multiple actions per macro
- Startup with Windows toggle

## License

MIT — do whatever you want with it.

---

Built to be simple and effective. Enjoy your macros!
