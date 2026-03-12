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

"""Data models for SoloCanvas — no Qt dependencies."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}


@dataclass
class CardData:
    """Immutable identity of a single card."""
    id: str
    deck_id: str
    image_path: str   # absolute path to front image
    back_path: str    # absolute path to back image
    name: str         # display name (stem of filename)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "deck_id": self.deck_id,
            "image_path": self.image_path,
            "back_path": self.back_path,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CardData":
        return cls(**d)


class DeckModel:
    """Mutable state of a deck: which cards remain, in what order."""

    def __init__(
        self,
        folder_path: Optional[str] = None,
        name: Optional[str] = None,
        deck_id: Optional[str] = None,
    ):
        self.id: str = deck_id or str(uuid.uuid4())
        self.folder_path: Optional[str] = folder_path
        self.name: str = name or (Path(folder_path).name if folder_path else "Deck")
        self.back_path: Optional[str] = None

        # all_cards: every card that belongs to this deck
        self.all_cards: List[CardData] = []
        # cards: the pile (subset of all_cards that are still in the deck)
        self.cards: List[CardData] = []

        if folder_path:
            self._load_cards()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _load_cards(self) -> None:
        folder = Path(self.folder_path)
        if not folder.exists() or not folder.is_dir():
            return

        back_file: Optional[Path] = None
        card_files: List[Path] = []

        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                if f.stem.lower() == "back":
                    back_file = f
                else:
                    card_files.append(f)

        if back_file:
            self.back_path = str(back_file)

        self.all_cards = [
            CardData(
                id=str(uuid.uuid4()),
                deck_id=self.id,
                image_path=str(f),
                back_path=self.back_path or "",
                name=f.stem,
            )
            for f in card_files
        ]
        self.cards = list(self.all_cards)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> List[CardData]:
        count = min(count, len(self.cards))
        drawn, self.cards = self.cards[:count], self.cards[count:]
        return drawn

    def add_to_bottom(self, card: CardData) -> None:
        if card not in self.cards:
            self.cards.append(card)

    def add_to_top(self, card: CardData) -> None:
        if card not in self.cards:
            self.cards.insert(0, card)

    def remove_card(self, card: CardData) -> None:
        if card in self.cards:
            self.cards.remove(card)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def card_by_image_path(self, path: str) -> Optional[CardData]:
        for c in self.all_cards:
            if c.image_path == path:
                return c
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self.cards)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "folder_path": self.folder_path,
            "name": self.name,
            "back_path": self.back_path,
            "all_cards": [c.to_dict() for c in self.all_cards],
            "card_order": [c.image_path for c in self.cards],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DeckModel":
        deck = cls(
            folder_path=d.get("folder_path"),
            name=d.get("name"),
            deck_id=d.get("id"),
        )
        deck.back_path = d.get("back_path")

        # Prefer loading from folder (always fresh on disk)
        if deck.folder_path and Path(deck.folder_path).exists():
            deck._load_cards()
        else:
            deck.all_cards = [CardData.from_dict(c) for c in d.get("all_cards", [])]

        # Restore pile order from saved image paths
        path_lookup = {c.image_path: c for c in deck.all_cards}
        deck.cards = [
            path_lookup[p] for p in d.get("card_order", []) if p in path_lookup
        ]
        return deck
