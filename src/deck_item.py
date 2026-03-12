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

"""DeckItem – a deck of cards on the canvas with pseudo-3D rendering."""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QRectF,
    QSequentialAnimationGroup, Qt, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsObject, QMenu,
)

try:
    from PyQt6.QtCore import QPropertyAnimation
except ImportError:
    from PyQt6.QtCore import QPropertyAnimation  # noqa

from .card_item import CARD_H, CARD_W, CORNER_R

STACK_LAYERS  = 8     # max visible layers in pseudo-3D
STACK_OFFSET  = 1.8   # px offset per layer (x and y)


class DeckItem(QGraphicsObject):
    """A deck (or stack) of cards sitting on the canvas."""

    draw_to_hand_signal    = pyqtSignal(list)   # List[CardData]
    draw_to_canvas_signal  = pyqtSignal(list)   # List[CardData]
    shuffle_done           = pyqtSignal()
    search_cards_requested = pyqtSignal(object)  # emits self
    recall_stack_requested = pyqtSignal(object)  # emits self (stacks only)
    stack_emptied          = pyqtSignal(object)  # emits self when last card drawn from a stack
    stack_requested        = pyqtSignal()        # request MainWindow to stack selected items
    before_draw            = pyqtSignal()        # fires before any card is removed from model
    duplicate_requested    = pyqtSignal(object)  # emits self

    def __init__(self, deck_model, parent=None):
        super().__init__(parent)
        self.deck_model     = deck_model
        self.face_up        = False   # when True, top card shows its front face
        self.locked         = False
        self.is_stack       = False   # True when created from stacked canvas cards
        self.hover_preview  = True
        self._base_z: float = 1.0

        # Shadow
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(14)
        self._shadow.setOffset(5, 8)
        self._shadow.setColor(QColor(0, 0, 0, 170))
        self.setGraphicsEffect(self._shadow)

        # Hover
        self._hovered = False

        # Drag-merge highlight (another item is being dragged over this deck)
        self._merge_highlight: bool = False

        # Shuffle animation
        self._shake_x:  float = 0.0
        self._is_shuffling = False

        # Lift animation
        self._lift_val: float = 0.0
        self._lift_anim = QPropertyAnimation(self, b"lift_val")
        self._lift_anim.setDuration(100)

        # Back pixmap
        self._back_pix: Optional[QPixmap] = None
        self._front_pix: Optional[QPixmap] = None  # top card's front face
        self._load_back()
        self._update_front_pix()

        # Per-deck dimensions derived from back image aspect ratio
        self.card_w, self.card_h = self._calc_dimensions()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        # Grid snap (set by MainWindow)
        self.grid_snap: bool = False
        self.grid_size: int  = 40

    # ------------------------------------------------------------------
    # Pixmap helpers
    # ------------------------------------------------------------------

    def _load_back(self) -> None:
        bp = self.deck_model.back_path
        if bp and Path(bp).exists():
            self._back_pix = QPixmap(bp)

    def _calc_dimensions(self) -> tuple:
        """Return (card_w, card_h) scaled to CARD_W width, preserving back-image ratio."""
        pix = self._back_pix
        if pix and not pix.isNull() and pix.width() > 0:
            return CARD_W, round(CARD_W * pix.height() / pix.width())
        return CARD_W, CARD_H

    def set_merge_highlight(self, active: bool) -> None:
        if active != self._merge_highlight:
            self._merge_highlight = active
            self.update()

    def _update_front_pix(self) -> None:
        """Cache the top card's front-face pixmap (called after card draws)."""
        if self.deck_model.cards:
            top = self.deck_model.cards[0]
            if top.image_path and Path(top.image_path).exists():
                self._front_pix = QPixmap(top.image_path)
                return
        self._front_pix = None

    # ------------------------------------------------------------------
    # Qt properties
    # ------------------------------------------------------------------

    def _get_shake_x(self) -> float:
        return self._shake_x

    def _set_shake_x(self, v: float) -> None:
        self._shake_x = v
        self.update()

    shake_x = pyqtProperty(float, _get_shake_x, _set_shake_x)

    def _get_lift_val(self) -> float:
        return self._lift_val

    def _set_lift_val(self, v: float) -> None:
        self._lift_val = v
        self._shadow.setBlurRadius(14 + v * 22)
        self._shadow.setOffset(5 + v * 10, 8 + v * 12)
        self.update()

    lift_val = pyqtProperty(float, _get_lift_val, _set_lift_val)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        extra = min(self.deck_model.count, STACK_LAYERS) * STACK_OFFSET + 4
        return QRectF(
            -self.card_w / 2 - 2,
            -self.card_h / 2 - 2,
            self.card_w + extra + 4,
            self.card_h + extra + 4,
        )

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget) -> None:
        count  = self.deck_model.count
        layers = min(count, STACK_LAYERS)

        sx = self._shake_x
        cw, ch = self.card_w, self.card_h

        # Deck shadow layers (bottom to top)
        for i in range(layers, 0, -1):
            offset = i * STACK_OFFSET
            layer_rect = QRectF(
                -cw / 2 + offset + sx * 0.3 * i / layers,
                -ch / 2 + offset,
                cw, ch,
            )
            alpha = int(80 + 100 * i / layers)
            painter.setBrush(QBrush(QColor(30, 30, 30, alpha)))
            painter.setPen(QPen(QColor(0, 0, 0, 40), 0.5))
            painter.drawRoundedRect(layer_rect, CORNER_R, CORNER_R)

            # Show a sliver of the back on each layer for realism
            if self._back_pix and not self._back_pix.isNull() and i <= 3:
                painter.setOpacity(0.4 + 0.2 * i)
                sliver = QRectF(layer_rect.x(), layer_rect.y(),
                                min(STACK_OFFSET * 2, 4), ch)
                painter.drawPixmap(sliver.toRect(),
                                   self._back_pix,
                                   self._back_pix.rect())
                painter.setOpacity(1.0)

        # Top card – pick pixmap based on face_up state
        top_rect = QRectF(-cw / 2 + sx, -ch / 2, cw, ch)
        if count == 0:
            # Empty deck – draw dashed outline
            painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
            pen = QPen(QColor(200, 200, 200, 80), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(top_rect, CORNER_R, CORNER_R)
            painter.setPen(QPen(QColor(200, 200, 200, 120)))
            painter.drawText(top_rect, Qt.AlignmentFlag.AlignCenter, "Empty")
        else:
            pix = (self._front_pix or self._back_pix) if self.face_up else self._back_pix
            if pix and not pix.isNull():
                painter.drawPixmap(top_rect.toRect(), pix)
            else:
                color = QColor(45, 85, 200) if self.face_up else QColor(160, 35, 35)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(top_rect, CORNER_R, CORNER_R)

            # Border
            from PyQt6.QtWidgets import QStyle
            if option.state & QStyle.StateFlag.State_Selected:
                pen = QPen(QColor(255, 215, 0), 3)
            elif self.locked:
                pen = QPen(QColor(255, 80, 80), 2)
            elif self.is_stack:
                pen = QPen(QColor(180, 100, 255), 2)  # purple tint for stacks
            else:
                pen = QPen(QColor(0, 0, 0, 80), 1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(top_rect, CORNER_R, CORNER_R)

        # Merge-drop glow overlay
        if self._merge_highlight:
            for thick, alpha in ((16, 12), (11, 28), (7, 55), (4, 105), (2, 190)):
                painter.setPen(QPen(QColor(80, 200, 255, alpha), thick))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(top_rect, CORNER_R, CORNER_R)
            painter.fillRect(top_rect, QColor(80, 180, 255, 22))

        # Deck / stack name label
        name = ("⬡ " if self.is_stack else "") + self.deck_model.name[:18]
        name_rect = QRectF(-cw / 2 + sx, ch / 2 - 22, cw, 22)
        painter.fillRect(name_rect, QColor(0, 0, 0, 120))
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Arial", 8)
        painter.setFont(font)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, name)

        # Hover count badge
        if self._hovered:
            badge = QRectF(top_rect.right() - 36, top_rect.top() - 10, 42, 22)
            painter.setBrush(QBrush(QColor(15, 15, 25, 210)))
            painter.setPen(QPen(QColor(100, 100, 150), 1))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(220, 220, 255))
            font2 = QFont("Arial", 9, QFont.Weight.Bold)
            painter.setFont(font2)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(count))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def flip(self) -> None:
        self.face_up = not self.face_up
        self._update_front_pix()
        self.update()

    def shuffle(self) -> None:
        if self._is_shuffling or self.deck_model.count == 0:
            return
        self._is_shuffling = True
        self.deck_model.shuffle()
        self._animate_shuffle()

    def _animate_shuffle(self) -> None:
        """Wobble deck left/right to visually indicate shuffle."""
        grp = QSequentialAnimationGroup(self)

        def make_step(start, end, dur):
            a = QPropertyAnimation(self, b"shake_x")
            a.setStartValue(start)
            a.setEndValue(end)
            a.setDuration(dur)
            a.setEasingCurve(QEasingCurve.Type.InOutSine)
            return a

        grp.addAnimation(make_step(0.0,  14.0, 80))
        grp.addAnimation(make_step(14.0, -12.0, 70))
        grp.addAnimation(make_step(-12.0, 9.0,  60))
        grp.addAnimation(make_step(9.0, -6.0,  55))
        grp.addAnimation(make_step(-6.0,  0.0,  50))

        def _done():
            self._is_shuffling = False
            self._shake_x = 0.0
            self._update_front_pix()
            self.shuffle_done.emit()

        grp.finished.connect(_done)
        grp.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def draw_cards_to_hand(self, count: int = 1) -> None:
        self.before_draw.emit()
        cards = self.deck_model.draw(count)
        if cards:
            self.draw_to_hand_signal.emit(cards)
        self._update_front_pix()
        self.update()
        if self.is_stack and self.deck_model.count == 0:
            self.stack_emptied.emit(self)

    def draw_cards_to_canvas(self, count: int = 1) -> None:
        self.before_draw.emit()
        cards = self.deck_model.draw(count)
        if cards:
            self.draw_to_canvas_signal.emit(cards)
        self._update_front_pix()
        self.update()
        if self.is_stack and self.deck_model.count == 0:
            self.stack_emptied.emit(self)

    def receive_card(self, card_data) -> None:
        self.deck_model.add_to_bottom(card_data)
        self._update_front_pix()
        self.update()

    def spread_horizontal(self, scene_pos: QPointF) -> list:
        """Remove top min(10, count) cards and return them for canvas placement."""
        count = min(self.deck_model.count, 10)
        cards = self.deck_model.draw(count)
        self._update_front_pix()
        return cards

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def _raise_to_top(self) -> None:
        scene = self.scene()
        if scene:
            from .card_item import CardItem
            from .image_item import ImageItem
            from .die_item import DieItem
            max_z = max(
                (it.zValue() for it in scene.items()
                 if isinstance(it, (CardItem, DeckItem, ImageItem, DieItem))
                 and not getattr(it, 'is_anchor', False)
                 and it is not self),
                default=0,
            )
            self._base_z = max_z + 1
        self.setZValue(self._base_z)

    def _lift(self) -> None:
        self._lift_anim.stop()
        self._lift_anim.setStartValue(self._lift_val)
        self._lift_anim.setEndValue(1.0)
        self._lift_anim.start()
        self.setZValue(self._base_z + 100)

    def _drop(self) -> None:
        self._lift_anim.stop()
        self._lift_anim.setStartValue(self._lift_val)
        self._lift_anim.setEndValue(0.0)
        self._lift_anim.start()
        self.setZValue(self._base_z)

    def _drop_lift(self) -> None:
        self._drop()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.locked:
            self.draw_cards_to_canvas(1)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.locked:
                event.ignore()
                return
            from .card_item import _raise_selection_to_top
            _raise_selection_to_top(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            from .card_item import _drop_selection
            _drop_selection(self)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.locked:
            event.ignore()
            return
        old_pos = self.pos()
        super().mouseMoveEvent(event)
        delta = self.pos() - old_pos
        if delta.manhattanLength() > 0:
            scene = self.scene()
            if scene:
                for item in scene.selectedItems():
                    if item is not self and not getattr(item, "locked", False):
                        item.setPos(item.pos() + delta)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event) -> None:
        views = self.scene().views() if self.scene() else []
        parent = views[0] if views else None
        menu = QMenu(parent)

        # Flip
        flip_label = "Flip (show front)" if not self.face_up else "Flip (show back)"
        menu.addAction(flip_label, self.flip)
        menu.addSeparator()

        draw_menu = menu.addMenu("Draw to Hand")
        for n in (1, 2, 3, 5, 7):
            draw_menu.addAction(f"{n} card{'s' if n > 1 else ''}",
                                lambda checked=False, c=n: self.draw_cards_to_hand(c))

        draw_canvas_menu = menu.addMenu("Draw to Canvas")
        for n in (1, 2, 3):
            draw_canvas_menu.addAction(
                f"{n} card{'s' if n > 1 else ''}",
                lambda checked=False, c=n: self.draw_cards_to_canvas(c),
            )

        menu.addSeparator()
        menu.addAction("Search Cards…", lambda: self.search_cards_requested.emit(self))
        menu.addSeparator()
        menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(self))
        menu.addSeparator()
        menu.addAction("Shuffle", self.shuffle)
        menu.addAction("Spread",  self._spread_horizontal_action)
        menu.addSeparator()
        lock_label = "Unlock" if self.locked else "Lock"
        menu.addAction(lock_label, self._toggle_lock)
        snap_label = "✓ Snap to Grid" if self.grid_snap else "Snap to Grid"
        menu.addAction(snap_label, self._toggle_snap)
        preview_label = "Preview: On" if self.hover_preview else "Preview: Off"
        menu.addAction(preview_label, lambda: self._toggle_hover_preview())

        # Stack selected items (when 2+ cards/stacks are selected)
        if self.scene():
            from .card_item import CardItem
            sel_cards = [i for i in self.scene().selectedItems() if isinstance(i, CardItem)]
            sel_decks = [i for i in self.scene().selectedItems() if isinstance(i, DeckItem)]
            total_sel = len(sel_cards) + len(sel_decks)
            if total_sel >= 2:
                menu.addSeparator()
                menu.addAction(f"Stack {total_sel} Selected Items",
                               self.stack_requested.emit)

        # Stack-only: disband back to parent decks
        if self.is_stack:
            menu.addSeparator()
            menu.addAction("Disband Stack to Decks",
                           lambda: self.recall_stack_requested.emit(self))

        from PyQt6.QtGui import QCursor
        menu.exec(QCursor.pos())

    def _spread_horizontal_action(self) -> None:
        cards = self.spread_horizontal(self.pos())
        if cards:
            self.draw_to_canvas_signal.emit(cards)
        if self.is_stack and self.deck_model.count == 0:
            self.stack_emptied.emit(self)

    def _toggle_snap(self) -> None:
        new_val = not self.grid_snap
        self.grid_snap = new_val
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, 'grid_snap'):
                    item.grid_snap = new_val

    def _toggle_lock(self) -> None:
        new_val = not self.locked
        self._apply_lock(new_val)
        if self.scene():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, '_apply_lock'):
                    item._apply_lock(new_val)

    def _apply_lock(self, val: bool) -> None:
        self.locked = val
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not val)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not val)
        if val:
            self.setSelected(False)
        self.update()

    def _toggle_hover_preview(self) -> None:
        new_val = not self.hover_preview
        self.hover_preview = new_val
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, 'hover_preview'):
                    item.hover_preview = new_val

    # ------------------------------------------------------------------
    # Grid snap
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
                and self.grid_snap and self.scene()):
            import math as _math
            g = self.grid_size
            mode = getattr(self.scene(), 'snap_mode', 'centered')
            br = self.boundingRect()
            hw = br.width() / 2
            hh = br.height() / 2
            cx = value.x() + hw
            cy = value.y() + hh
            if mode == 'centered':
                snapped_cx = _math.floor(cx / g) * g + g / 2
                snapped_cy = _math.floor(cy / g) * g + g / 2
            else:  # 'lines'
                snapped_cx = round(cx / g) * g
                snapped_cy = round(cy / g) * g
            return QPointF(snapped_cx - hw, snapped_cy - hh)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_state_dict(self) -> dict:
        return {
            "deck_id":   self.deck_model.id,
            "x":         self.pos().x(),
            "y":         self.pos().y(),
            "rotation":  self.rotation(),
            "face_up":   self.face_up,
            "locked":    self.locked,
            "grid_snap": self.grid_snap,
            "is_stack":  self.is_stack,
        }
