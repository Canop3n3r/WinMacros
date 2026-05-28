# WinMacros

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

A simple, effective, and lightweight macros tool for Windows.

Create powerful macros with global hotkeys, including text insertion, key repeats, mouse button control (including toggle hold), and **Turbo Key** mode (multi-press on physical key presses).

## Features

- **Text Insertion** — Type or paste text on hotkey (with speed control)
- **Key Repeat** — Press any key multiple times with one hotkey
- **Mouse Button Actions** — Click, double-click, or **toggle-hold** mouse buttons
- **Turbo Key** — Turn on a mode where every physical press of a key (e.g. Space) is repeated X times
- **Toggle Mode** — Hotkeys can turn macros ON/OFF (perfect for mouse hold and turbo)
- Global hotkeys that work in any application
- System tray support (runs in background)
- Clean modern UI (Windows 11 friendly with CustomTkinter)
- Persistent macros (saved in `%APPDATA%`)

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

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Administrator rights are **strongly recommended** for reliable global hotkeys (especially with Turbo Key and Mouse actions)

## Known Limitations & Warnings

WinMacros is currently in **early public release (v0.9.0)**. Please be aware of the following:

- **Input simulation is not 100% reliable** — Some games, fullscreen applications, and certain Electron apps may ignore or partially receive simulated input.
- **Turbo Key mode** can feel laggy or inconsistent in high-performance scenarios.
- The underlying libraries (`keyboard` + `pyautogui`) sometimes require running the program **as Administrator**.
- There is currently **no standalone executable**. You must have Python installed.
- Complex combinations of toggle + turbo macros can occasionally conflict.
- No built-in way yet to see which toggle macros are currently active from the UI.

**Use at your own risk.** Input automation tools can interfere with other software.

## Building a Standalone Executable

We now have a proper build system:

```powershell
pip install pyinstaller
python build.py
```

The resulting application will be in `dist/WinMacros/`.

A pre-built .exe will be provided in future releases.

## Future Plans

- Pre-built standalone .exe releases
- Better visibility of active toggle macros in the UI
- Import / Export of macro sets
- Full migration to pynput for more reliable input simulation
- Per-macro logging and error reporting

## Contributing

This project is currently maintained by one person. Bug reports, feature suggestions, and pull requests are welcome.

## License

MIT License — see [LICENSE](LICENSE) file.


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
