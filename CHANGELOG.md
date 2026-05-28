# Changelog

All notable changes to WinMacros will be documented in this file.

## [0.9.0] - 2026-05-28

### Added
- **Turbo Key mode** — Enable a macro so that every physical press of a chosen key (e.g. Space) is automatically repeated X times.
- **Mouse Button actions** — Support for single click, double click, temporary hold, and toggle-hold (press once to hold mouse button down, press again to release).
- **Key Repeat action** — Trigger a hotkey to press any keyboard key multiple times with configurable count and interval.
- **Toggle Mode** — Macros can now be toggled on/off instead of always firing once (essential for Turbo and Mouse Hold).
- Dynamic action type selection in the macro editor.
- Better action summaries in the main list.

### Changed
- Major refactoring of the macro execution system to support multiple action types.
- Switched key simulation for new action types to `pyautogui` for better reliability with repeats and mouse control.
- Improved hotkey registration logic to support toggle-style macros.

### Known Issues
- The `keyboard` library can be unreliable in some games and fullscreen applications.
- Turbo Key mode may have slight input lag or conflicts when multiple turbo macros target similar keys.
- The application currently requires Python to be installed (no standalone .exe yet).
- Some users may need to run as Administrator for reliable global hooks.

## [0.8.0] and earlier

Initial development versions. Core text macro functionality with global hotkeys and system tray support.
