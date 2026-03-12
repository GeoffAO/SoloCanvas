# Copyright © 2026 Geoffrey Osterberg
#
# SoloCanvas is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SoloCanvas is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Persistent settings and hotkey configuration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_HOTKEYS: Dict[str, str] = {
    "shuffle":           "R",
    "flip":              "F",
    "rotate_cw":         "E",
    "rotate_ccw":        "Q",
    "recall":            "Ctrl+R",
    "magnify":           "M",
    "zoom_in":           "=",
    "zoom_out":          "-",
    "zoom_reset":        "Ctrl+0",
    "draw_1":            "1",
    "draw_2":            "2",
    "draw_3":            "3",
    "draw_4":            "4",
    "draw_5":            "5",
    "draw_6":            "6",
    "draw_7":            "7",
    "draw_8":            "8",
    "draw_9":            "9",
    "select_all":        "Ctrl+A",
    "delete_selected":   "Delete",
    "import_deck":       "Ctrl+I",
    "new_session":       "Ctrl+N",
    "save_session":      "Ctrl+S",
    "open_session":      "Ctrl+O",
    "grid_toggle":       "G",
    "lock_toggle":       "L",
    "hand_toggle":       "H",
    "send_to_back":      "U",
    "stack_selected":    "Ctrl+G",
    "spread_deck":       "Ctrl+Shift+G",
    "copy":              "Ctrl+C",
    "paste":             "Ctrl+V",
    "hotkey_reference":  "K",
    "open_notepad":      "N",
    "open_deck_library": "D",
    "open_image_library":"I",
    "open_dice_bag":     "B",
}

HOTKEY_LABELS: Dict[str, str] = {
    "shuffle":           "Shuffle active deck",
    "flip":              "Flip selected",
    "rotate_cw":         "Rotate clockwise",
    "rotate_ccw":        "Rotate counter-clockwise",
    "recall":            "Open recall menu",
    "magnify":           "Magnify hovered card",
    "zoom_in":           "Zoom in",
    "zoom_out":          "Zoom out",
    "zoom_reset":        "Reset zoom",
    "draw_1":            "Draw 1 card to hand",
    "draw_2":            "Draw 2 cards to hand",
    "draw_3":            "Draw 3 cards to hand",
    "draw_4":            "Draw 4 cards to hand",
    "draw_5":            "Draw 5 cards to hand",
    "draw_6":            "Draw 6 cards to hand",
    "draw_7":            "Draw 7 cards to hand",
    "draw_8":            "Draw 8 cards to hand",
    "draw_9":            "Draw 9 cards to hand",
    "select_all":        "Select all",
    "delete_selected":   "Delete selected",
    "import_deck":       "Import deck from folder",
    "new_session":       "New session",
    "save_session":      "Save session",
    "open_session":      "Open session",
    "grid_toggle":       "Toggle grid visibility",
    "lock_toggle":       "Toggle lock on selected",
    "hand_toggle":       "Toggle hand widget",
    "send_to_back":      "Send selected to back (Z-order)",
    "stack_selected":    "Stack selected items into a deck",
    "spread_deck":       "Spread selected deck horizontally",
    "copy":              "Copy selected",
    "paste":             "Paste",
    "hotkey_reference":  "Show hotkey reference",
    "open_notepad":      "Open Notepad",
    "open_deck_library": "Open Deck Library",
    "open_image_library":"Open Image Library",
    "open_dice_bag":     "Open Dice Bag",
}

DEFAULT_CANVAS: Dict[str, Any] = {
    "background_mode":       "color",   # color | image_centered | image_tiled | image_scaled | image_stretched
    "background_color":      "#55557f",
    "background_image_path": None,
    "grid_enabled":          True,
    "grid_size":             40,
    "grid_snap":             False,
    "grid_color":            "#7070a0",
    "grid_snap_mode":        "centered", # centered | lines
}

DEFAULT_DISPLAY: Dict[str, Any] = {
    "max_hand_card_width":  100,
    "auto_magnify":         True,
    "magnify_corner":       "bottom_right",  # bottom_right | bottom_left | top_right | top_left
    "magnify_size":         220,
    "auto_save_on_close":   True,
    "card_canvas_width":    120,
    "card_canvas_height":   168,
    "rotation_step":        45,             # degrees per rotate CW/CCW: 15 | 45 | 90
    "image_import_size":    1.2,            # default width/height in grid cells
    "use_canvas_theme":     True,           # tint UI chrome to match canvas colour
    "card_picker_thumb_w":  48,             # thumbnail width in CardPickerDialog
}


def _config_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "SoloCanvas"
    base.mkdir(parents=True, exist_ok=True)
    return base


class SettingsManager:
    """Loads, saves and provides access to all application settings."""

    def __init__(self):
        self._path = _config_dir() / "settings.json"
        self._data: Dict[str, Any] = {
            "hotkeys": dict(DEFAULT_HOTKEYS),
            "canvas":  dict(DEFAULT_CANVAS),
            "display": dict(DEFAULT_DISPLAY),
        }
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Deep-merge: keep defaults for any missing keys
            for section in ("hotkeys", "canvas", "display"):
                if section in saved:
                    self._data[section].update(saved[section])
        except Exception:
            pass  # Silently fall back to defaults

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Hotkeys
    # ------------------------------------------------------------------

    def hotkey(self, action: str) -> str:
        return self._data["hotkeys"].get(action, DEFAULT_HOTKEYS.get(action, ""))

    def set_hotkey(self, action: str, key: str) -> None:
        self._data["hotkeys"][action] = key

    def all_hotkeys(self) -> Dict[str, str]:
        return dict(self._data["hotkeys"])

    def reset_hotkeys(self) -> None:
        self._data["hotkeys"] = dict(DEFAULT_HOTKEYS)

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------

    def canvas(self, key: str) -> Any:
        return self._data["canvas"].get(key, DEFAULT_CANVAS.get(key))

    def set_canvas(self, key: str, value: Any) -> None:
        self._data["canvas"][key] = value

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display(self, key: str) -> Any:
        return self._data["display"].get(key, DEFAULT_DISPLAY.get(key))

    def set_display(self, key: str, value: Any) -> None:
        self._data["display"][key] = value

    # ------------------------------------------------------------------
    # Sessions dir
    # ------------------------------------------------------------------

    def sessions_dir(self) -> Path:
        d = _config_dir() / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def decks_dir(self) -> Path:
        """Decks library folder – next to the exe when frozen, otherwise project root."""
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent
        d = base / "Decks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def images_dir(self) -> Path:
        """Localized images folder – next to the exe when frozen, otherwise project root."""
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent
        d = base / "Images"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def notes_dir(self) -> Path:
        """Notes folder – sibling of /Decks and /Images next to the exe."""
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent
        d = base / "Notes"
        d.mkdir(parents=True, exist_ok=True)
        (d / "Images").mkdir(parents=True, exist_ok=True)
        return d

    def notepad_config_path(self) -> Path:
        """Path to notepad.json in %APPDATA%/SoloCanvas/."""
        return _config_dir() / "notepad.json"
