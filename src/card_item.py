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

"""CardItem – a single card on the canvas."""
from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QRectF,
    Qt, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap,
    QAction, QCursor,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsObject,
    QGraphicsItem, QMenu, QStyle,
)

try:
    from PyQt6.QtCore import QPropertyAnimation
except ImportError:
    from PyQt6.QtCore import QPropertyAnimation  # noqa

CARD_W = 120
CARD_H = 168
CORNER_R = 8


class CardItem(QGraphicsObject):
    """A playing card on the canvas with flip/rotate/lift animations."""

    # Signals for MainWindow coordination
    send_to_hand   = pyqtSignal(object)   # CardData
    return_to_deck = pyqtSignal(object)   # CardData
    card_hovered   = pyqtSignal(object)   # CardData
    card_unhovered = pyqtSignal()
    stack_requested = pyqtSignal()        # emitted when "Stack Selected" is chosen

    def __init__(self, card_data, face_up: bool = True, parent=None):
        super().__init__(parent)
        self.card_data      = card_data
        self.face_up        = face_up
        self.locked         = False
        self.hover_preview  = True
        self._rotation_step = 0   # legacy; kept for set_rotation_degrees compat

        # Load pixmaps
        self._front_pix: Optional[QPixmap] = None
        self._back_pix:  Optional[QPixmap] = None
        self._load_pixmaps()

        # Per-card dimensions derived from back image aspect ratio
        self.card_w, self.card_h = self._calc_dimensions()

        # Flip animation state: 0.0 = show back, 1.0 = show front
        self._flip_prog: float = 1.0 if face_up else 0.0
        self._flipped_mid = face_up  # tracks which side is visible at midpoint

        # Shadow / lift
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(4, 6)
        self._shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(self._shadow)

        # Flags
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        # Flip animation
        self._flip_anim = QPropertyAnimation(self, b"flip_prog")
        self._flip_anim.setDuration(280)
        self._flip_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._flip_anim.finished.connect(self._on_flip_finished)

        # Lift animation (drives shadow)
        self._lift_val: float = 0.0
        self._lift_anim = QPropertyAnimation(self, b"lift_val")
        self._lift_anim.setDuration(100)
        self._lift_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Grid snap (set by MainWindow from settings)
        self.grid_snap:  bool = False
        self.grid_size:  int  = 40

        # Persistent Z order (raised when clicked, restored on drop)
        self._base_z: float = 1.0

    # ------------------------------------------------------------------
    # Pixmap loading
    # ------------------------------------------------------------------

    def _calc_dimensions(self) -> tuple:
        """Return (card_w, card_h) scaled to CARD_W width, preserving back-image ratio."""
        pix = self._back_pix or self._front_pix
        if pix and not pix.isNull() and pix.width() > 0:
            return CARD_W, round(CARD_W * pix.height() / pix.width())
        return CARD_W, CARD_H

    def _load_pixmaps(self) -> None:
        if self.card_data.image_path and Path(self.card_data.image_path).exists():
            self._front_pix = QPixmap(self.card_data.image_path)
        if self.card_data.back_path and Path(self.card_data.back_path).exists():
            self._back_pix = QPixmap(self.card_data.back_path)

    # ------------------------------------------------------------------
    # Qt properties for animation
    # ------------------------------------------------------------------

    def _get_flip_prog(self) -> float:
        return self._flip_prog

    def _set_flip_prog(self, v: float) -> None:
        self._flip_prog = v
        # Swap visible face at midpoint
        if v >= 0.5 and not self._flipped_mid:
            self._flipped_mid = True
        elif v < 0.5 and self._flipped_mid:
            self._flipped_mid = False
        self.update()

    flip_prog = pyqtProperty(float, _get_flip_prog, _set_flip_prog)

    def _get_lift_val(self) -> float:
        return self._lift_val

    def _set_lift_val(self, v: float) -> None:
        self._lift_val = v
        self._shadow.setBlurRadius(12 + v * 22)
        self._shadow.setOffset(4 + v * 10, 6 + v * 12)
        self.update()

    lift_val = pyqtProperty(float, _get_lift_val, _set_lift_val)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        # Extra left margin reserves space for the lock icon (18px + 4px gap)
        extra = 26
        return QRectF(-self.card_w / 2 - extra, -self.card_h / 2, self.card_w + extra, self.card_h)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget) -> None:
        prog = self._flip_prog
        # cos gives 1→0→1 as prog goes 0→0.5→1
        scale_x = abs(math.cos(prog * math.pi))
        scale_x = max(scale_x, 0.001)

        show_front = self._flipped_mid
        pix = self._front_pix if show_front else self._back_pix

        rect = QRectF(-self.card_w / 2, -self.card_h / 2, self.card_w, self.card_h)

        # Nearest-neighbour when zoomed past native res
        transform = painter.worldTransform()
        view_scale = math.sqrt(transform.m11() ** 2 + transform.m12() ** 2)
        use_smooth = (pix is None) or (view_scale * self.card_w < pix.width() * 1.1)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, use_smooth)

        painter.save()
        painter.scale(scale_x, 1.0)

        if pix and not pix.isNull():
            painter.drawPixmap(rect.toRect(), pix)
        else:
            # Placeholder
            color = QColor(45, 85, 200) if show_front else QColor(160, 35, 35)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, CORNER_R, CORNER_R)
            painter.setPen(QPen(QColor(255, 255, 255, 180)))
            font = QFont("Arial", 9)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             self.card_data.name[:24])

        # Border
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if self.locked and selected:
            pen = QPen(QColor(220, 50, 50), 3)
        elif selected:
            pen = QPen(QColor(255, 215, 0), 3)
        elif self.locked:
            pen = QPen(QColor(220, 50, 50), 2)
        else:
            pen = QPen(QColor(0, 0, 0, 60), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, CORNER_R, CORNER_R)

        painter.restore()

        # Lock icon — drawn outside the flip-scale block so it doesn't distort
        if self.locked:
            try:
                import qtawesome as qta
                icon_size = 18
                gap = 4
                px = qta.icon("fa5s.lock", color="white").pixmap(icon_size, icon_size)
                painter.setOpacity(0.65)
                painter.drawPixmap(
                    int(-self.card_w / 2 - icon_size - gap),
                    int(-self.card_h / 2),
                    px,
                )
                painter.setOpacity(1.0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def flip(self) -> None:
        if self._flip_anim.state() == QAbstractAnimation.State.Running:
            return
        self.face_up = not self.face_up
        target = 1.0 if self.face_up else 0.0
        self._flip_anim.setStartValue(self._flip_prog)
        self._flip_anim.setEndValue(target)
        self._flip_anim.start()

    def _on_flip_finished(self) -> None:
        self._flip_prog = 1.0 if self.face_up else 0.0
        self._flipped_mid = self.face_up
        self.update()

    def rotate_cw(self, step: int = 45) -> None:
        cur = round(self.rotation() / step) * step
        self.setRotation((cur + step) % 360)

    def rotate_ccw(self, step: int = 45) -> None:
        cur = round(self.rotation() / step) * step
        self.setRotation((cur - step) % 360)

    def set_rotation_degrees(self, deg: float) -> None:
        self.setRotation(deg % 360)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def _raise_to_top(self) -> None:
        """Permanently raise this card above all other canvas items in the scene."""
        scene = self.scene()
        if scene:
            from .deck_item import DeckItem
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

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.locked:
            self.flip()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.locked:
                event.ignore()
                return
            _raise_selection_to_top(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.locked:
            event.ignore()
            return
        # Move all selected items together
        old_pos = self.pos()
        super().mouseMoveEvent(event)
        delta = self.pos() - old_pos
        if delta.manhattanLength() > 0:
            scene = self.scene()
            if scene:
                for item in scene.selectedItems():
                    if item is not self and isinstance(item, CardItem) and not item.locked:
                        item.setPos(item.pos() + delta)
                    elif item is not self:
                        from .deck_item import DeckItem
                        if isinstance(item, DeckItem) and not item.locked:
                            item.setPos(item.pos() + delta)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            _drop_selection(self)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        views = self.scene().views() if self.scene() else []
        parent = views[0] if views else None
        menu = QMenu(parent)

        menu.addAction("Flip",           self.flip)
        menu.addAction("Rotate CW",      self.rotate_cw)
        menu.addAction("Rotate CCW",     self.rotate_ccw)
        menu.addSeparator()
        menu.addAction("Send to Hand",   lambda: self.send_to_hand.emit(self.card_data))
        menu.addAction("Return to Deck", lambda: self.return_to_deck.emit(self.card_data))
        menu.addSeparator()

        # Stack option — visible when 2+ cards/stacks are selected
        if self.scene():
            from .deck_item import DeckItem as _DI
            sel_cards = [i for i in self.scene().selectedItems() if isinstance(i, CardItem)]
            sel_decks = [i for i in self.scene().selectedItems() if isinstance(i, _DI)]
            total_sel = len(sel_cards) + len(sel_decks)
            if total_sel >= 2:
                menu.addAction(
                    f"Stack {total_sel} Selected Items",
                    self.stack_requested.emit,
                )
                menu.addSeparator()

        lock_label = "Unlock" if self.locked else "Lock"
        menu.addAction(lock_label, self._toggle_lock)
        snap_label = "✓ Snap to Grid" if self.grid_snap else "Snap to Grid"
        menu.addAction(snap_label, self._toggle_snap)
        preview_label = "Preview: On" if self.hover_preview else "Preview: Off"
        menu.addAction(preview_label, self._toggle_hover_preview)

        from PyQt6.QtGui import QCursor
        menu.exec(QCursor.pos())

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
        if not new_val:
            self.card_unhovered.emit()
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, 'hover_preview'):
                    item.hover_preview = new_val

    # ------------------------------------------------------------------
    # Hover → magnify
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:
        if self.hover_preview and not self.locked:
            self.card_hovered.emit(self.card_data)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if self.hover_preview and not self.locked:
            self.card_unhovered.emit()
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Item change – clear hover when removed from scene
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSceneChange:
            # Removing from scene – clear magnify preview
            if value is None:
                self.card_unhovered.emit()
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
            "image_path": self.card_data.image_path,
            "deck_id":    self.card_data.deck_id,
            "x":          self.pos().x(),
            "y":          self.pos().y(),
            "rotation":   self.rotation(),
            "face_up":    self.face_up,
            "locked":     self.locked,
            "grid_snap":  self.grid_snap,
            "z":          self.zValue(),
        }


# ------------------------------------------------------------------
# Group Z-order helpers (used by CardItem and DeckItem)
# ------------------------------------------------------------------

def _raise_selection_to_top(clicked_item) -> None:
    """Raise the whole selection to the top of Z-order, preserving relative
    Z-order within the group. Falls back to single-item raise if alone."""
    from .deck_item import DeckItem
    from .image_item import ImageItem
    from .die_item import DieItem
    scene = clicked_item.scene()
    if not scene:
        clicked_item._raise_to_top()
        clicked_item._lift()
        return

    selected = [
        i for i in scene.selectedItems()
        if isinstance(i, (CardItem, DeckItem, ImageItem, DieItem))
        and not getattr(i, "locked", False)
        and not getattr(i, 'is_anchor', False)
    ]

    if len(selected) <= 1:
        clicked_item._raise_to_top()
        clicked_item._lift()
        return

    sel_ids = {id(i) for i in selected}
    max_z = max(
        (i.zValue() for i in scene.items()
         if isinstance(i, (CardItem, DeckItem, ImageItem, DieItem))
         and not getattr(i, 'is_anchor', False)
         and id(i) not in sel_ids),
        default=0,
    )
    for idx, item in enumerate(sorted(selected, key=lambda i: i.zValue())):
        item._base_z = max_z + 1 + idx
        if hasattr(item, '_lift'):
            item._lift()
        else:
            item.setZValue(item._base_z)


def _drop_selection(clicked_item) -> None:
    """Drop all selected items back to their base Z-order."""
    from .deck_item import DeckItem
    scene = clicked_item.scene()
    if not scene:
        clicked_item._drop()
        return

    selected = [
        i for i in scene.selectedItems()
        if isinstance(i, (CardItem, DeckItem))
    ]
    if len(selected) <= 1:
        clicked_item._drop()
        return

    for item in selected:
        item._drop()


# ------------------------------------------------------------------
# Shared stylesheet for context menus
# ------------------------------------------------------------------

_MENU_STYLE = """
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px;
    font-size: 13px;
}
QMenu::item {
    padding: 5px 20px 5px 10px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #313244;
}
QMenu::separator {
    height: 1px;
    background: #45475a;
    margin: 3px 6px;
}
"""
