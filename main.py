#!/usr/bin/env python3
"""
WinMacros - Simple, effective global hotkey macros for Windows.

Create text insertion macros, bind them to global hotkeys, toggle on/off.
Runs from the system tray.
"""

import customtkinter as ctk
from tkinter import messagebox
import keyboard
import pyautogui
import pystray
from PIL import Image, ImageDraw, ImageFont
import threading
import json
import os
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Set

# ----------------------------- Config -----------------------------
APP_NAME = "WinMacros"
APP_VERSION = "1.0.0"
DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
MACROS_FILE = DATA_DIR / "macros.json"

SPEED_OPTIONS = ["Instant", "Fast", "Normal", "Slow"]
SPEED_DELAYS = {
    "Instant": 0.0,
    "Fast": 0.005,
    "Normal": 0.025,
    "Slow": 0.07,
}

# New action types for expanded macro variety
ACTION_TYPES = ["text", "key_repeat", "mouse", "turbo_key"]

MOUSE_BUTTONS = ["left", "right", "middle"]
MOUSE_ACTIONS = ["click", "double_click", "toggle_hold", "hold_duration"]

# Friendly names for UI
ACTION_TYPE_LABELS = {
    "text": "Text Insertion",
    "key_repeat": "Repeat Key",
    "mouse": "Mouse Button",
    "turbo_key": "Turbo Key (multi-press on physical key)",
}

# ----------------------------- Macro Manager -----------------------------
class MacroManager:
    """Handles loading, saving, hotkey registration, and execution for all macro types."""

    def __init__(self):
        self.macros: List[Dict[str, Any]] = []
        self._hotkey_handles: Dict[str, Any] = {}      # hotkey -> handle
        self.toggled_active: Set[str] = set()          # macro ids that are currently "on" (for toggle mode)
        self.turbo_hooks: Dict[str, Any] = {}          # source_key -> hook handle for turbo macros
        self.held_mouse_buttons: Set[str] = set()      # currently held mouse buttons via toggle
        self.load()

    def load(self):
        if not MACROS_FILE.exists():
            self.macros = []
            return
        try:
            with open(MACROS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.macros = data if isinstance(data, list) else []
            for m in self.macros:
                m.setdefault("id", str(uuid.uuid4()))
                m.setdefault("enabled", True)
                m.setdefault("speed", "Instant")
                m.setdefault("is_toggle", False)
                if "action" not in m:
                    m["action"] = {"type": "text", "mode": "type", "text": m.get("text", "")}
                action = m["action"]
                action.setdefault("type", "text")
                # legacy migration
                if action["type"] == "text":
                    action.setdefault("mode", "type")
                    action.setdefault("text", "")
        except Exception as e:
            print(f"[WinMacros] Failed to load macros: {e}")
            self.macros = []

    def save(self):
        try:
            with open(MACROS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.macros, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WinMacros] Failed to save macros: {e}")

    def get_by_id(self, macro_id: str) -> Optional[Dict[str, Any]]:
        return next((m for m in self.macros if m.get("id") == macro_id), None)

    def add_or_update(self, macro: Dict[str, Any]):
        existing = self.get_by_id(macro["id"])
        if existing:
            existing.update(macro)
        else:
            self.macros.append(macro)
        self.save()

    def delete(self, macro_id: str):
        # Clean up any active state for this macro
        self.toggled_active.discard(macro_id)
        self._cleanup_turbo_for_macro(macro_id)
        self.macros = [m for m in self.macros if m.get("id") != macro_id]
        self.save()

    def set_enabled(self, macro_id: str, enabled: bool):
        m = self.get_by_id(macro_id)
        if m:
            m["enabled"] = enabled
            if not enabled:
                self.toggled_active.discard(macro_id)
                self._cleanup_turbo_for_macro(macro_id)
            self.save()

    def get_enabled_macros(self) -> List[Dict[str, Any]]:
        return [m for m in self.macros if m.get("enabled") and m.get("hotkey")]

    def find_conflicting_macro(self, hotkey: str, exclude_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not hotkey:
            return None
        for m in self.macros:
            if exclude_id and m.get("id") == exclude_id:
                continue
            if m.get("enabled") and m.get("hotkey") == hotkey:
                return m
        return None

    # ---------------- Toggle / State Management ----------------
    def is_macro_active(self, macro_id: str) -> bool:
        return macro_id in self.toggled_active

    def toggle_macro(self, macro_id: str) -> bool:
        """Flip the active state of a toggle-style macro and perform side effects."""
        macro = self.get_by_id(macro_id)
        if not macro or not macro.get("enabled"):
            return False

        is_active = macro_id in self.toggled_active
        action_type = macro.get("action", {}).get("type", "text")

        if is_active:
            # Turn OFF
            self.toggled_active.discard(macro_id)
            self._deactivate_macro_behavior(macro)
            return False
        else:
            # Turn ON
            self.toggled_active.add(macro_id)
            self._activate_macro_behavior(macro)
            return True

    def _activate_macro_behavior(self, macro: Dict[str, Any]):
        action = macro.get("action", {})
        atype = action.get("type", "text")

        if atype == "mouse":
            btn = action.get("button", "left")
            maction = action.get("mouse_action", "toggle_hold")
            if maction == "toggle_hold":
                self._set_mouse_button(btn, True)
            elif maction == "hold_duration":
                dur = max(10, int(action.get("hold_duration_ms", 500)))
                threading.Thread(target=self._temp_mouse_hold, args=(btn, dur / 1000.0), daemon=True).start()

        elif atype == "turbo_key":
            self._install_turbo_hook(macro)

    def _deactivate_macro_behavior(self, macro: Dict[str, Any]):
        action = macro.get("action", {})
        atype = action.get("type", "text")

        if atype == "mouse":
            btn = action.get("button", "left")
            self._set_mouse_button(btn, False)

        elif atype == "turbo_key":
            self._remove_turbo_hook(macro)

    def _cleanup_turbo_for_macro(self, macro_id: str):
        macro = self.get_by_id(macro_id)
        if macro:
            self._remove_turbo_hook(macro)

    # ---------------- Turbo Key (multi-press on physical key) ----------------
    def _install_turbo_hook(self, macro: Dict[str, Any]):
        action = macro.get("action", {})
        source = action.get("source_key", "space").lower().strip()
        count = max(1, int(action.get("count", 5)))
        interval = max(0, int(action.get("interval_ms", 10))) / 1000.0

        if not source:
            return

        # Remove existing hook for this source if any (simple model: last one wins per key)
        self._remove_turbo_hook_for_key(source)

        def turbo_callback(event):
            # Perform the repeats. Use pyautogui so we don't retrigger our own hooks easily.
            try:
                for i in range(count):
                    if i > 0 and interval > 0:
                        time.sleep(interval)
                    pyautogui.press(source)
            except Exception as e:
                print(f"[WinMacros] Turbo error on '{source}': {e}")

        try:
            hook = keyboard.on_press_key(source, turbo_callback, suppress=True)
            self.turbo_hooks[source] = {"hook": hook, "macro_id": macro["id"]}
            print(f"[WinMacros] Turbo hook installed for key: {source}")
        except Exception as e:
            print(f"[WinMacros] Failed to install turbo hook for {source}: {e}")

    def _remove_turbo_hook(self, macro: Dict[str, Any]):
        action = macro.get("action", {})
        source = action.get("source_key", "").lower().strip()
        if source:
            self._remove_turbo_hook_for_key(source)

    def _remove_turbo_hook_for_key(self, source_key: str):
        if source_key in self.turbo_hooks:
            try:
                keyboard.unhook(self.turbo_hooks[source_key]["hook"])
            except Exception:
                pass
            del self.turbo_hooks[source_key]

    # ---------------- Mouse Control (using pyautogui) ----------------
    def _set_mouse_button(self, button: str, down: bool):
        try:
            if down:
                pyautogui.mouseDown(button=button)
                self.held_mouse_buttons.add(button)
            else:
                pyautogui.mouseUp(button=button)
                self.held_mouse_buttons.discard(button)
        except Exception as e:
            print(f"[WinMacros] Mouse button error ({button} {'down' if down else 'up'}): {e}")

    def _temp_mouse_hold(self, button: str, seconds: float):
        try:
            pyautogui.mouseDown(button=button)
            time.sleep(seconds)
            pyautogui.mouseUp(button=button)
        except Exception as e:
            print(f"[WinMacros] Temp mouse hold error: {e}")

    # ---------------- Hotkey Registration (supports toggle macros) ----------------
    def register_hotkeys(self, on_direct_execute):
        """Register hotkeys. Toggle macros get special handling."""
        self.unregister_hotkeys()

        for macro in self.get_enabled_macros():
            hk = macro.get("hotkey")
            if not hk:
                continue
            is_toggle = macro.get("is_toggle", False)

            try:
                if is_toggle:
                    # Toggle-style: hotkey flips state + side effects
                    handle = keyboard.add_hotkey(
                        hk,
                        lambda m=macro: self._handle_toggle_hotkey(m),
                        suppress=True,
                    )
                else:
                    # Normal one-shot
                    handle = keyboard.add_hotkey(
                        hk,
                        lambda m=macro: on_direct_execute(m),
                        suppress=True,
                    )
                self._hotkey_handles[hk] = handle
            except Exception as e:
                print(f"[WinMacros] Failed to register hotkey '{hk}': {e}")

    def _handle_toggle_hotkey(self, macro: Dict[str, Any]):
        """Called when a toggle macro's hotkey is pressed."""
        was_active = self.toggle_macro(macro["id"])
        state = "ON" if was_active else "OFF"
        # We can't easily update UI from here, but we can print
        print(f"[WinMacros] Toggled '{macro.get('name')}' → {state}")

    def unregister_hotkeys(self):
        for hk, handle in list(self._hotkey_handles.items()):
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkey_handles.clear()

        # Also clean all turbo hooks when fully unregistering
        for key in list(self.turbo_hooks.keys()):
            try:
                keyboard.unhook(self.turbo_hooks[key]["hook"])
            except Exception:
                pass
        self.turbo_hooks.clear()

    # ---------------- Main Execution Dispatcher ----------------
    def execute(self, macro: Dict[str, Any], root_widget: Optional[ctk.CTk] = None):
        """Main entry point for one-shot macro execution."""
        if not macro.get("enabled"):
            return

        # If this is a toggle macro, the hotkey path already handled it via _handle_toggle_hotkey
        if macro.get("is_toggle", False):
            return

        action = macro.get("action", {})
        atype = action.get("type", "text")

        try:
            # Release modifiers that might be held
            for mod in ("ctrl", "shift", "alt", "windows"):
                try:
                    keyboard.release(mod)
                except Exception:
                    pass
            time.sleep(0.03)

            if atype == "text":
                self._execute_text(action, root_widget)

            elif atype == "key_repeat":
                self._execute_key_repeat(action)

            elif atype == "mouse":
                self._execute_mouse_action(action)

            elif atype == "turbo_key":
                # Turbo is primarily toggle-driven. If someone triggers it directly, just toggle it.
                self.toggle_macro(macro["id"])

        except Exception as e:
            print(f"[WinMacros] Error executing macro '{macro.get('name')}': {e}")

    def _execute_text(self, action: dict, root_widget):
        mode = action.get("mode", "type")
        text = action.get("text", "")
        if not text.strip():
            return
        delay = SPEED_DELAYS.get("Fast", 0.005)  # keep fast for non-text actions

        if mode == "paste" and root_widget is not None:
            try:
                root_widget.clipboard_clear()
                root_widget.clipboard_append(text)
                time.sleep(0.03)
                keyboard.press_and_release("ctrl+v")
            except Exception:
                pyautogui.write(text, interval=0.0)
        else:
            pyautogui.write(text, interval=0.0)

    def _execute_key_repeat(self, action: dict):
        key = action.get("key", "space").lower().strip()
        count = max(1, int(action.get("count", 5)))
        interval = max(0, int(action.get("interval_ms", 30))) / 1000.0

        if not key:
            return
        try:
            pyautogui.press(key, presses=count, interval=interval)
        except Exception as e:
            print(f"[WinMacros] key_repeat error: {e}")

    def _execute_mouse_action(self, action: dict):
        button = action.get("button", "left")
        maction = action.get("mouse_action", "click")

        try:
            if maction == "click":
                pyautogui.click(button=button)
            elif maction == "double_click":
                pyautogui.doubleClick(button=button)
            elif maction == "toggle_hold":
                # This is normally driven by toggle state, but allow direct use
                if button in self.held_mouse_buttons:
                    pyautogui.mouseUp(button=button)
                    self.held_mouse_buttons.discard(button)
                else:
                    pyautogui.mouseDown(button=button)
                    self.held_mouse_buttons.add(button)
            elif maction == "hold_duration":
                dur = max(0.01, int(action.get("hold_duration_ms", 500)) / 1000.0)
                pyautogui.mouseDown(button=button)
                time.sleep(dur)
                pyautogui.mouseUp(button=button)
        except Exception as e:
            print(f"[WinMacros] mouse action error: {e}")


# ----------------------------- Tray Icon -----------------------------
def create_tray_image() -> Image.Image:
    """Create a clean modern tray icon with an M."""
    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded blue square (modern Windows 11 style)
    margin = 6
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=20,
        fill="#2563eb",
        outline="#1e40af",
        width=3,
    )

    # Try a nice bold font for the M, fall back to lines
    try:
        font = ImageFont.truetype("arialbd.ttf", 68)
        draw.text((size // 2, size // 2 - 2), "M", fill="white", font=font, anchor="mm")
    except Exception:
        # Fallback geometric M
        cx, cy = size // 2, size // 2 + 2
        s = 30
        draw.line([(cx - s, cy + s), (cx - s + 12, cy - s)], fill="white", width=9)
        draw.line([(cx - s + 12, cy - s), (cx, cy + 8)], fill="white", width=9)
        draw.line([(cx, cy + 8), (cx + s - 12, cy - s)], fill="white", width=9)
        draw.line([(cx + s - 12, cy - s), (cx + s, cy + s)], fill="white", width=9)

    return img


# ----------------------------- Main Application -----------------------------
class WinMacrosApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.manager = MacroManager()
        self.tray_icon: Optional[pystray.Icon] = None
        self._editing_macro_id: Optional[str] = None
        self._captured_hotkey: Optional[str] = None
        self._captured_hotkey_display: str = ""

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("860x560")
        self.minsize(720, 480)

        # Modern dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build_ui()
        self.refresh_list()
        self._register_hotkeys()
        self._setup_tray()

        # Handle close button -> minimize to tray
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._set_status("Ready — macros active in background")

    # ---------------- UI Construction ----------------
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=72, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        title_label = ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title_label.pack(side="left", padx=24, pady=16)

        version_label = ctk.CTkLabel(
            header,
            text=f"v{APP_VERSION}",
            text_color=("gray60", "gray70"),
            font=ctk.CTkFont(size=13),
        )
        version_label.pack(side="left", padx=(4, 0), pady=20)

        # Big New Macro button
        new_btn = ctk.CTkButton(
            header,
            text="+ New Macro",
            width=160,
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.new_macro,
        )
        new_btn.pack(side="right", padx=24, pady=15)

        # Main content area
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        # Toolbar row
        toolbar = ctk.CTkFrame(main, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            toolbar,
            text="Your Macros",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left", padx=4)

        self.pause_all_var = ctk.BooleanVar(value=False)
        pause_switch = ctk.CTkSwitch(
            toolbar,
            text="Pause All Hotkeys",
            variable=self.pause_all_var,
            command=self._toggle_pause_all,
        )
        pause_switch.pack(side="right", padx=8)

        # Scrollable list container
        self.list_frame = ctk.CTkScrollableFrame(
            main,
            label_text="",
            fg_color=("gray10", "gray16"),
            corner_radius=10,
        )
        self.list_frame.pack(fill="both", expand=True)

        # Status bar
        status_bar = ctk.CTkFrame(self, height=32, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_bar,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left", padx=16, fill="x", expand=True)

        count_label = ctk.CTkLabel(
            status_bar,
            text="Hotkeys work globally even when this window is closed",
            text_color=("gray55", "gray65"),
            font=ctk.CTkFont(size=11),
        )
        count_label.pack(side="right", padx=16)

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    # ---------------- Macro List ----------------
    def refresh_list(self):
        # Clear existing rows
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        macros = self.manager.macros

        if not macros:
            empty = ctk.CTkLabel(
                self.list_frame,
                text="No macros yet.\n\nClick the big \"+ New Macro\" button above.\nThen capture a hotkey (e.g. Ctrl+Alt+T) and enter the text you want typed.",
                text_color=("gray50", "gray60"),
                font=ctk.CTkFont(size=13),
                justify="center",
            )
            empty.pack(expand=True, pady=50)
            return

        for macro in macros:
            self._create_macro_row(macro)

    def _create_macro_row(self, macro: Dict[str, Any]):
        row = ctk.CTkFrame(self.list_frame, corner_radius=8, fg_color=("gray17", "gray20"))
        row.pack(fill="x", padx=6, pady=5)

        # Enable switch
        enabled_var = ctk.BooleanVar(value=bool(macro.get("enabled", True)))

        def on_toggle():
            self.manager.set_enabled(macro["id"], enabled_var.get())
            self._register_hotkeys()
            self._set_status(f"{'Enabled' if enabled_var.get() else 'Disabled'}: {macro['name']}")

        switch = ctk.CTkSwitch(
            row,
            text="",
            variable=enabled_var,
            width=42,
            command=on_toggle,
        )
        switch.pack(side="left", padx=(12, 6), pady=10)

        # Name
        name_label = ctk.CTkLabel(
            row,
            text=macro.get("name", "Unnamed"),
            font=ctk.CTkFont(size=14, weight="bold"),
            width=220,
            anchor="w",
        )
        name_label.pack(side="left", padx=4)

        # Hotkey pill
        hotkey = macro.get("hotkey", "")
        hotkey_text = self._format_hotkey(hotkey) if hotkey else "No hotkey"
        hotkey_label = ctk.CTkLabel(
            row,
            text=hotkey_text,
            font=ctk.CTkFont(size=12, family="Consolas"),
            text_color=("#3b82f6", "#60a5fa") if hotkey else ("gray50", "gray60"),
            fg_color=("gray25", "gray28"),
            corner_radius=6,
            padx=10,
            pady=3,
        )
        hotkey_label.pack(side="left", padx=10)

        # Action summary (supports all new types)
        action = macro.get("action", {})
        atype = action.get("type", "text")
        is_tog = " [Toggle]" if macro.get("is_toggle") else ""

        if atype == "text":
            preview = (action.get("text", "")[:45] or "").replace("\n", " ")
            if len(action.get("text", "")) > 45:
                preview += "…"
            mode = "Paste" if action.get("mode") == "paste" else "Type"
            summary = f"[{mode}] {preview or '[empty]'}{is_tog}"

        elif atype == "key_repeat":
            key = action.get("key", "?")
            cnt = action.get("count", 1)
            summary = f"[Repeat {key} ×{cnt}]{is_tog}"

        elif atype == "mouse":
            btn = action.get("button", "left")
            mact = action.get("mouse_action", "click")
            summary = f"[Mouse {btn} {mact}]{is_tog}"

        elif atype == "turbo_key":
            src = action.get("source_key", "?")
            cnt = action.get("count", 1)
            summary = f"[Turbo {src} ×{cnt}]{is_tog}"

        else:
            summary = f"[{atype}]{is_tog}"

        summary_label = ctk.CTkLabel(
            row,
            text=summary,
            text_color=("gray60", "gray70"),
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        summary_label.pack(side="left", padx=6, fill="x", expand=True)

        # Buttons
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=8, pady=6)

        def make_cmd(cmd):
            return lambda: cmd(macro["id"])

        test_btn = ctk.CTkButton(
            btn_frame,
            text="Test",
            width=58,
            height=28,
            font=ctk.CTkFont(size=11),
            command=make_cmd(self.test_macro),
        )
        test_btn.pack(side="left", padx=3)

        edit_btn = ctk.CTkButton(
            btn_frame,
            text="Edit",
            width=58,
            height=28,
            font=ctk.CTkFont(size=11),
            command=make_cmd(self.edit_macro),
        )
        edit_btn.pack(side="left", padx=3)

        del_btn = ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=58,
            height=28,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=11),
            command=make_cmd(self.delete_macro),
        )
        del_btn.pack(side="left", padx=3)

    # ---------------- Hotkey formatting ----------------
    def _format_hotkey(self, hk: str) -> str:
        if not hk:
            return ""
        parts = [p.strip() for p in hk.lower().split("+")]
        pretty = []
        for p in parts:
            if p in ("ctrl", "control"):
                pretty.append("Ctrl")
            elif p == "alt":
                pretty.append("Alt")
            elif p in ("shift",):
                pretty.append("Shift")
            elif p in ("win", "windows", "super"):
                pretty.append("Win")
            else:
                pretty.append(p.upper() if len(p) == 1 else p.title())
        return " + ".join(pretty)

    # ---------------- Hotkey registration ----------------
    def _register_hotkeys(self):
        def on_trigger(macro):
            # Execute from a thread to avoid blocking the keyboard hook thread
            threading.Thread(
                target=lambda: self.manager.execute(macro, root_widget=self),
                daemon=True,
            ).start()
            # Update status on main thread
            self.after(0, lambda: self._set_status(f"▶ {macro['name']}  •  {datetime.now().strftime('%H:%M:%S')}"))

        self.manager.register_hotkeys(on_trigger)

    def _toggle_pause_all(self):
        if self.pause_all_var.get():
            self.manager.unregister_hotkeys()
            self._set_status("All hotkeys paused")
        else:
            self._register_hotkeys()
            self._set_status("Hotkeys resumed")

    # ---------------- Tray ----------------
    def _setup_tray(self):
        image = create_tray_image()

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self.show_window, default=True),
            pystray.MenuItem("New Macro", self.new_macro),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause All", self._tray_toggle_pause, checked=lambda item: self.pause_all_var.get()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app),
        )

        self.tray_icon = pystray.Icon(APP_NAME, image, f"{APP_NAME} v{APP_VERSION}", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_toggle_pause(self, icon, item):
        self.pause_all_var.set(not self.pause_all_var.get())
        self._toggle_pause_all()

    def show_window(self, *_):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        # Hide instead of closing so hotkeys keep working
        self.withdraw()
        self._set_status("Running in system tray (right-click tray icon to exit)")

    def quit_app(self, *_):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.manager.unregister_hotkeys()
        self.destroy()

    # ---------------- CRUD ----------------
    def new_macro(self):
        self._show_edit_dialog(None)

    def edit_macro(self, macro_id: str):
        self._show_edit_dialog(macro_id)

    def delete_macro(self, macro_id: str):
        macro = self.manager.get_by_id(macro_id)
        if not macro:
            return
        if not messagebox.askyesno(
            "Delete Macro",
            f"Delete '{macro['name']}'?\nThis cannot be undone.",
            icon="warning",
        ):
            return

        self.manager.delete(macro_id)
        self._register_hotkeys()
        self.refresh_list()
        self._set_status(f"Deleted: {macro['name']}")

    def test_macro(self, macro_id: str):
        macro = self.manager.get_by_id(macro_id)
        if not macro:
            return

        # Give user 2.5 seconds to focus the target window
        self._set_status(f"Testing in 2.5s — focus target window... ({macro['name']})")
        self.update()

        def delayed():
            time.sleep(2.5)
            self.manager.execute(macro, root_widget=self)
            self.after(0, lambda: self._set_status(f"Tested: {macro['name']}"))

        threading.Thread(target=delayed, daemon=True).start()

    # ---------------- Edit Dialog ----------------
    def _show_edit_dialog(self, macro_id: Optional[str]):
        macro = self.manager.get_by_id(macro_id) if macro_id else None

        dialog = ctk.CTkToplevel(self)
        dialog.title("New Macro" if not macro else "Edit Macro")
        dialog.geometry("720x580")
        dialog.minsize(620, 460)
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Scrollable content (so all controls are reachable even on small/high-DPI screens)
        content = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(16, 8))

        # Name
        ctk.CTkLabel(content, text="Name", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        name_entry = ctk.CTkEntry(content, placeholder_text="e.g. Email Signature, Ticket Template...")
        name_entry.pack(fill="x", pady=(0, 14))
        if macro:
            name_entry.insert(0, macro.get("name", ""))

        # Hotkey
        ctk.CTkLabel(content, text="Hotkey", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))

        hk_row = ctk.CTkFrame(content, fg_color="transparent")
        hk_row.pack(fill="x", pady=(0, 14))

        self._captured_hotkey = macro.get("hotkey") if macro else None
        self._captured_hotkey_display = self._format_hotkey(self._captured_hotkey) if self._captured_hotkey else ""

        hk_display = ctk.CTkLabel(
            hk_row,
            text=self._captured_hotkey_display or "No hotkey set",
            font=ctk.CTkFont(size=13, family="Consolas"),
            fg_color=("gray20", "gray25"),
            corner_radius=6,
            padx=14,
            pady=6,
        )
        hk_display.pack(side="left", padx=(0, 8))

        def update_hk_display(text):
            hk_display.configure(text=text or "No hotkey set")

        capture_btn = ctk.CTkButton(
            hk_row,
            text="Capture Hotkey",
            width=150,
            command=lambda: self._capture_hotkey_in_dialog(dialog, update_hk_display),
        )
        capture_btn.pack(side="left")

        clear_btn = ctk.CTkButton(
            hk_row,
            text="Clear",
            width=70,
            fg_color="gray",
            command=lambda: self._clear_captured(update_hk_display),
        )
        clear_btn.pack(side="left", padx=6)

        # ===================== NEW: Action Type + Dynamic Fields =====================
        current_action = macro.get("action", {}) if macro else {}
        current_type = current_action.get("type", "text")

        # Action Type selector
        ctk.CTkLabel(content, text="Action Type", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 4))
        action_type_var = ctk.StringVar(value=ACTION_TYPE_LABELS.get(current_type, "Text Insertion"))
        action_type_menu = ctk.CTkOptionMenu(
            content,
            values=list(ACTION_TYPE_LABELS.values()),
            variable=action_type_var,
            width=320,
        )
        action_type_menu.pack(anchor="w", pady=(0, 10))

        # Container for dynamic action-specific fields
        action_frame = ctk.CTkFrame(content, fg_color="transparent")
        action_frame.pack(fill="x", pady=(0, 8))

        # We will store references to dynamic widgets on the dialog object
        dialog._action_widgets = {}

        def rebuild_action_fields(*_):
            # Clear previous widgets
            for w in action_frame.winfo_children():
                w.destroy()
            dialog._action_widgets.clear()

            selected_label = action_type_var.get()
            atype = next((k for k, v in ACTION_TYPE_LABELS.items() if v == selected_label), "text")

            if atype == "text":
                # --- Text Insertion ---
                ctk.CTkLabel(action_frame, text="Text to insert", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                tb = ctk.CTkTextbox(action_frame, height=160, wrap="word")
                tb.pack(fill="x", pady=6)
                if macro:
                    tb.insert("0.0", current_action.get("text", ""))
                dialog._action_widgets["text_box"] = tb

                row = ctk.CTkFrame(action_frame, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text="Mode").pack(side="left")
                mv = ctk.StringVar(value=current_action.get("mode", "type"))
                ctk.CTkOptionMenu(row, values=["type", "paste"], variable=mv, width=100).pack(side="left", padx=6)
                dialog._action_widgets["mode_var"] = mv

            elif atype == "key_repeat":
                ctk.CTkLabel(action_frame, text="Key to repeat (e.g. space, f5, enter, a)", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                key_entry = ctk.CTkEntry(action_frame, placeholder_text="space")
                key_entry.pack(fill="x", pady=4)
                key_entry.insert(0, current_action.get("key", "space"))
                dialog._action_widgets["key_entry"] = key_entry

                row = ctk.CTkFrame(action_frame, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text="Times").pack(side="left")
                count_var = ctk.StringVar(value=str(current_action.get("count", 8)))
                ctk.CTkEntry(row, textvariable=count_var, width=70).pack(side="left", padx=6)
                ctk.CTkLabel(row, text="Interval (ms)").pack(side="left", padx=(12, 4))
                int_var = ctk.StringVar(value=str(current_action.get("interval_ms", 30)))
                ctk.CTkEntry(row, textvariable=int_var, width=70).pack(side="left")
                dialog._action_widgets["key_count_var"] = count_var
                dialog._action_widgets["key_interval_var"] = int_var

            elif atype == "mouse":
                ctk.CTkLabel(action_frame, text="Mouse Button Action", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                row = ctk.CTkFrame(action_frame, fg_color="transparent")
                row.pack(fill="x", pady=4)

                ctk.CTkLabel(row, text="Button").pack(side="left")
                btn_var = ctk.StringVar(value=current_action.get("button", "left"))
                ctk.CTkOptionMenu(row, values=MOUSE_BUTTONS, variable=btn_var, width=90).pack(side="left", padx=6)

                ctk.CTkLabel(row, text="Action").pack(side="left", padx=(12, 4))
                mact_var = ctk.StringVar(value=current_action.get("mouse_action", "toggle_hold"))
                ctk.CTkOptionMenu(row, values=MOUSE_ACTIONS, variable=mact_var, width=130).pack(side="left")

                dur_var = ctk.StringVar(value=str(current_action.get("hold_duration_ms", 600)))
                ctk.CTkLabel(action_frame, text="Duration (ms) — only used for 'hold_duration'").pack(anchor="w", pady=(6, 2))
                ctk.CTkEntry(action_frame, textvariable=dur_var, width=100).pack(anchor="w")

                dialog._action_widgets["mouse_btn_var"] = btn_var
                dialog._action_widgets["mouse_action_var"] = mact_var
                dialog._action_widgets["mouse_dur_var"] = dur_var

            elif atype == "turbo_key":
                ctk.CTkLabel(action_frame, text="Every time you physically press this key → it will be sent multiple times", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 6))

                ctk.CTkLabel(action_frame, text="Physical key to watch (e.g. space, w, mouse_left, f)").pack(anchor="w")
                src_entry = ctk.CTkEntry(action_frame, placeholder_text="space")
                src_entry.pack(fill="x", pady=4)
                src_entry.insert(0, current_action.get("source_key", "space"))
                dialog._action_widgets["turbo_source"] = src_entry

                row = ctk.CTkFrame(action_frame, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text="Repeat").pack(side="left")
                tcount = ctk.StringVar(value=str(current_action.get("count", 12)))
                ctk.CTkEntry(row, textvariable=tcount, width=70).pack(side="left", padx=6)
                ctk.CTkLabel(row, text="Interval (ms)").pack(side="left", padx=(12, 4))
                tint = ctk.StringVar(value=str(current_action.get("interval_ms", 8)))
                ctk.CTkEntry(row, textvariable=tint, width=70).pack(side="left")
                dialog._action_widgets["turbo_count"] = tcount
                dialog._action_widgets["turbo_interval"] = tint

        # Bind change
        action_type_menu.configure(command=rebuild_action_fields)
        # Initial build
        rebuild_action_fields()

        # ===================== End dynamic action section =====================

        # Toggle Mode (very important for mouse hold and turbo)
        is_toggle_var = ctk.BooleanVar(value=bool(macro.get("is_toggle", False)) if macro else False)
        toggle_switch = ctk.CTkSwitch(
            content,
            text="Toggle Mode (hotkey turns this macro ON/OFF instead of firing once)",
            variable=is_toggle_var
        )
        toggle_switch.pack(anchor="w", pady=(10, 4))

        # Enabled
        enabled_var = ctk.BooleanVar(value=macro.get("enabled", True) if macro else True)
        enabled_switch = ctk.CTkSwitch(content, text="Enabled", variable=enabled_var)
        enabled_switch.pack(anchor="w", pady=8)

        # Buttons (kept outside the scrollable area so they are always visible)
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 16))

        def on_save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a name for the macro.", parent=dialog)
                return
            if not self._captured_hotkey:
                messagebox.showerror("Error", "Please capture a hotkey for this macro.", parent=dialog)
                return

            selected_label = action_type_var.get()
            atype = next((k for k, v in ACTION_TYPE_LABELS.items() if v == selected_label), "text")
            w = dialog._action_widgets

            action_data = {"type": atype}

            if atype == "text":
                action_data["mode"] = w.get("mode_var").get() if "mode_var" in w else "type"
                action_data["text"] = w.get("text_box").get("0.0", "end").rstrip("\n") if "text_box" in w else ""

            elif atype == "key_repeat":
                action_data["key"] = w.get("key_entry").get().strip().lower() if "key_entry" in w else "space"
                action_data["count"] = int(w.get("key_count_var").get() or 5) if "key_count_var" in w else 5
                action_data["interval_ms"] = int(w.get("key_interval_var").get() or 30) if "key_interval_var" in w else 30

            elif atype == "mouse":
                action_data["button"] = w.get("mouse_btn_var").get() if "mouse_btn_var" in w else "left"
                action_data["mouse_action"] = w.get("mouse_action_var").get() if "mouse_action_var" in w else "click"
                action_data["hold_duration_ms"] = int(w.get("mouse_dur_var").get() or 600) if "mouse_dur_var" in w else 600

            elif atype == "turbo_key":
                action_data["source_key"] = w.get("turbo_source").get().strip().lower() if "turbo_source" in w else "space"
                action_data["count"] = int(w.get("turbo_count").get() or 10) if "turbo_count" in w else 10
                action_data["interval_ms"] = int(w.get("turbo_interval").get() or 8) if "turbo_interval" in w else 8

            new_macro = {
                "id": macro["id"] if macro else str(uuid.uuid4()),
                "name": name,
                "enabled": enabled_var.get(),
                "is_toggle": is_toggle_var.get(),
                "hotkey": self._captured_hotkey,
                "speed": "Instant",   # speed only really matters for text now
                "action": action_data,
            }

            # Conflict check
            conflict = self.manager.find_conflicting_macro(
                new_macro.get("hotkey"), exclude_id=new_macro.get("id")
            )
            if conflict:
                if not messagebox.askyesno(
                    "Hotkey Conflict",
                    f"The hotkey {self._format_hotkey(new_macro['hotkey'])} is already used by \"{conflict['name']}\".\n\n"
                    f"Do you want to disable the other macro and continue?",
                    parent=dialog,
                ):
                    return
                self.manager.set_enabled(conflict["id"], False)

            self.manager.add_or_update(new_macro)
            self._register_hotkeys()
            self.refresh_list()
            self._set_status(f"Saved: {name}")
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        save_btn = ctk.CTkButton(btn_row, text="Save Macro", width=130, command=on_save)
        save_btn.pack(side="right", padx=6)

        cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=100, fg_color="gray", command=on_cancel)
        cancel_btn.pack(side="right", padx=6)

        # Store references so capture can update them
        dialog.name_entry = name_entry  # type: ignore
        dialog.hk_display = hk_display  # type: ignore
        dialog.text_box = text_box  # type: ignore
        dialog.mode_var = mode_var  # type: ignore
        dialog.speed_var = speed_var  # type: ignore

    def _capture_hotkey_in_dialog(self, dialog, update_display_callback):
        def worker():
            try:
                # Pause our own hotkeys during capture so they don't interfere
                self.manager.unregister_hotkeys()

                # Small visual hint
                self.after(0, lambda: update_display_callback("Press keys now... (ESC to cancel)"))

                captured = keyboard.read_hotkey(suppress=True)

                # Format nicely
                display = self._format_hotkey(captured)
                self._captured_hotkey = captured
                self._captured_hotkey_display = display

                self.after(0, lambda: update_display_callback(display))
            except Exception as e:
                self.after(0, lambda: update_display_callback(f"Capture failed: {e}"))
            finally:
                # Always restore hotkeys
                self.after(0, self._register_hotkeys)

        threading.Thread(target=worker, daemon=True).start()

    def _clear_captured(self, update_display_callback):
        self._captured_hotkey = None
        self._captured_hotkey_display = ""
        update_display_callback("No hotkey set")

    # ---------------- Cleanup ----------------
    def on_exit(self):
        self.quit_app()


# ----------------------------- Entry Point -----------------------------
if __name__ == "__main__":
    app = WinMacrosApp()
    app.mainloop()
