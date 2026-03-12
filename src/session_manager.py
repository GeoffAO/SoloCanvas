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

"""Save and restore complete canvas state as JSON sessions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .settings_manager import SettingsManager

SESSION_VERSION = 2


class SessionManager:
    """Serialises/deserialises canvas state to/from JSON files."""

    def __init__(self, settings: "SettingsManager"):
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sessions_dir(self) -> Path:
        return self._settings.sessions_dir()

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return metadata dicts for every saved session, newest first."""
        sessions = []
        for p in sorted(self.sessions_dir().glob("*.json"), reverse=True):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "path": str(p),
                    "name": data.get("name", p.stem),
                    "saved_at": data.get("saved_at", ""),
                    "deck_count": len(data.get("decks", [])),
                })
            except Exception:
                pass
        return sessions

    def autosave_path(self) -> Path:
        return self.sessions_dir() / "_autosave.json"

    def save(
        self,
        state: Dict[str, Any],
        path: Optional[Path] = None,
        name: str = "",
    ) -> Path:
        if path is None:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            name = name or ts
            path = self.sessions_dir() / f"{ts}.json"

        state["version"] = SESSION_VERSION
        state["saved_at"] = datetime.now().isoformat()
        state["name"] = name or path.stem

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return path

    def autosave(self, state: Dict[str, Any]) -> None:
        self.save(state, path=self.autosave_path(), name="Autosave")

    def load(self, path: str | Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # State building helpers (called by MainWindow)
    # ------------------------------------------------------------------

    @staticmethod
    def build_state(
        canvas_view,         # CanvasView
        canvas_scene,        # CanvasScene
        hand_widget,         # HandWidget
        deck_models: dict,   # {deck_id: DeckModel}
        deck_items: dict,    # {deck_id: DeckItem}
        die_items: list = None,    # list[DieItem]
        roll_log: list = None,     # list of roll log entries
        image_items: list = None,  # list[ImageItem]
    ) -> Dict[str, Any]:
        from .card_item import CardItem
        from .deck_item import DeckItem

        # View transform
        t = canvas_view.transform()
        scale = t.m11()
        cx = canvas_view.horizontalScrollBar().value()
        cy = canvas_view.verticalScrollBar().value()

        # Canvas background
        bg = {
            "mode":       canvas_scene.bg_mode,
            "color":      canvas_scene.bg_color,
            "image_path": canvas_scene.bg_image_path,
        }

        # Decks
        decks_data = []
        for deck_id, dm in deck_models.items():
            di = deck_items.get(deck_id)
            entry = dm.to_dict()
            if di is not None:
                entry["canvas_x"]   = di.pos().x()
                entry["canvas_y"]   = di.pos().y()
                entry["rotation"]   = di.rotation()
                entry["face_up"]    = di.face_up
            decks_data.append(entry)

        # Cards on canvas
        canvas_cards = []
        for item in canvas_scene.items():
            if isinstance(item, CardItem):
                canvas_cards.append({
                    "image_path": item.card_data.image_path,
                    "deck_id":    item.card_data.deck_id,
                    "x":          item.pos().x(),
                    "y":          item.pos().y(),
                    "rotation":   item.rotation(),
                    "face_up":    item.face_up,
                    "locked":     item.locked,
                    "z":          item.zValue(),
                })

        # Hand cards
        hand_cards = []
        for hs in hand_widget.hand_cards:
            hand_cards.append({
                "image_path": hs.card_data.image_path,
                "deck_id":    hs.card_data.deck_id,
                "face_up":    hs.face_up,
                "rotation":   hs.rotation,
            })

        # Dice on canvas
        dice_data = []
        if die_items:
            from .die_item import DieItem
            for di in die_items:
                if di.scene() is not None:
                    dice_data.append(di.to_state_dict())

        # Image items on canvas
        images_data = []
        if image_items:
            for img in image_items:
                if img.scene() is not None:
                    images_data.append(img.to_state_dict())

        # Global hover_preview state — same value on all items; default True
        hover_preview = True
        for item in canvas_scene.items():
            if hasattr(item, "hover_preview"):
                hover_preview = item.hover_preview
                break

        return {
            "canvas": {
                "scale": scale,
                "scroll_x": cx,
                "scroll_y": cy,
                "background": bg,
            },
            "decks":         decks_data,
            "canvas_cards":  canvas_cards,
            "hand_cards":    hand_cards,
            "dice":          dice_data,
            "roll_log":      list(roll_log) if roll_log is not None else [],
            "images":        images_data,
            "hover_preview": hover_preview,
        }
