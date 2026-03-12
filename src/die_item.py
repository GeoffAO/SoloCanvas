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

"""DieItem – a single die on the canvas with roll animation."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QRectF,
    Qt, QTimer, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QFont, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsObject, QMenu,
)

try:
    from PyQt6.QtCore import QPropertyAnimation
except ImportError:
    from PyQt6.QtCore import QPropertyAnimation  # noqa

from .dice_manager import DIE_MAX, DIE_TYPES, DiceSetsManager

if TYPE_CHECKING:
    pass


class DieItem(QGraphicsObject):
    """A single die placed on the canvas.

    Bounding rect: width = die_size, height = 2 * die_size
    Top half shows the SVG icon; bottom half shows the current value label.
    """

    # Signals
    delete_requested    = pyqtSignal(object)        # self
    duplicate_requested = pyqtSignal(object)        # self
    rolled              = pyqtSignal(object, int)   # self, final_value

    def __init__(
        self,
        die_type: str,
        set_name: str,
        dice_manager: DiceSetsManager,
        settings,
        parent=None,
    ):
        super().__init__(parent)

        self.die_type     = die_type
        self.set_name     = set_name
        self._manager     = dice_manager
        self._settings    = settings

        self._die_size: int  = settings.canvas("grid_size")
        self._spin_angle: float = 0.0
        self.value: int      = DIE_MAX.get(die_type, 6)

        # Persistent Z order (same pattern as CardItem)
        self._base_z: float = 1.0

        # Flags
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
        )
        self.setAcceptHoverEvents(False)
        self.setZValue(1)

        # Roll animation
        self._roll_anim = QPropertyAnimation(self, b"spin_angle")
        self._roll_anim.setDuration(1000)
        self._roll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._roll_anim.finished.connect(self._on_roll_finished)

        # Value randomisation timer during animation
        self._roll_timer = QTimer()
        self._roll_timer.setInterval(80)
        self._roll_timer.timeout.connect(self._randomise_value)

        # Final value to snap to when animation ends
        self._final_value: int = self.value
        # When False, suppress the rolled signal (used for grouped rolls logged externally)
        self._log_individual: bool = True
        self.hover_preview: bool = False
        self.grid_snap: bool = False
        self.grid_size: int  = settings.canvas("grid_size")

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(4, 6)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

    # ------------------------------------------------------------------
    # pyqtProperty for spin_angle animation
    # ------------------------------------------------------------------

    def _get_spin(self) -> float:
        return self._spin_angle

    def _set_spin(self, v: float) -> None:
        self._spin_angle = v
        self.update()

    spin_angle = pyqtProperty(float, _get_spin, _set_spin)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        s = self._die_size
        return QRectF(0, 0, s, s + s // 2)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget) -> None:
        s = self._die_size
        icon_rect = QRectF(0, 0, s, s)
        label_rect = QRectF(0, s + 2, s, s // 2 - 2)

        # ---------- Icon (top half) ----------
        pix: QPixmap = self._manager.get_pixmap(self.die_type, self.set_name, s)

        painter.save()
        # Rotate the icon around its centre point
        cx = s / 2.0
        cy = s / 2.0
        painter.translate(cx, cy)
        painter.rotate(self._spin_angle)
        painter.translate(-cx, -cy)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(icon_rect.toRect(), pix)
        painter.restore()

        # ---------- Selection ring ----------
        from PyQt6.QtWidgets import QStyle
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(icon_rect)

        # ---------- Label (bottom half) ----------
        font_size = max(8, s // 3)
        font = QFont("Arial", font_size, QFont.Weight.Bold)
        painter.setFont(font)

        label = self._value_label()

        # Black outline via offset draws
        outline_offsets = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        painter.setPen(QColor(0, 0, 0, 180))
        for dx, dy in outline_offsets:
            offset_rect = label_rect.translated(dx, dy)
            painter.drawText(offset_rect, Qt.AlignmentFlag.AlignCenter, label)

        # White text on top
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _value_label(self) -> str:
        if self.die_type == "dF":
            if self.value > 0:
                return f"+{self.value}"
            return str(self.value)
        return str(self.value)

    # ------------------------------------------------------------------
    # Roll logic
    # ------------------------------------------------------------------

    def roll(self) -> None:
        if self._roll_anim.state() == QAbstractAnimation.State.Running:
            return

        # Determine final value now
        max_val = DIE_MAX.get(self.die_type, 6)
        if self.die_type == "dF":
            self._final_value = random.choice([-1, 0, 1])
        else:
            self._final_value = random.randint(1, max_val)

        self._spin_angle = 0.0
        self._roll_anim.setStartValue(0.0)
        self._roll_anim.setEndValue(720.0)
        self._roll_timer.start()
        self._roll_anim.start()

    def _randomise_value(self) -> None:
        max_val = DIE_MAX.get(self.die_type, 6)
        if self.die_type == "dF":
            self.value = random.choice([-1, 0, 1])
        else:
            self.value = random.randint(1, max_val)
        self.update()

    def _on_roll_finished(self) -> None:
        self._roll_timer.stop()
        self._spin_angle = 0.0
        self.value = self._final_value
        self.update()
        if self._log_individual:
            self.rolled.emit(self, self._final_value)
        else:
            self._log_individual = True  # reset for next roll

    def reset_value(self) -> None:
        """Reset to the maximum (default) value."""
        self.value = DIE_MAX.get(self.die_type, 6)
        self.update()

    # ------------------------------------------------------------------
    # Size update (called when grid_size changes)
    # ------------------------------------------------------------------

    def update_die_size(self, new_size: int) -> None:
        self.prepareGeometryChange()
        self._die_size = new_size
        self.update()

    # ------------------------------------------------------------------
    # Z-order (same pattern as CardItem)
    # ------------------------------------------------------------------

    def _raise_to_top(self) -> None:
        scene = self.scene()
        if scene:
            from .card_item import CardItem
            from .deck_item import DeckItem
            max_z = max(
                (it.zValue() for it in scene.items()
                 if isinstance(it, (CardItem, DeckItem, DieItem)) and it is not self),
                default=0,
            )
            self._base_z = max_z + 1
        self.setZValue(self._base_z)

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
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._raise_to_top()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.roll()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        views = self.scene().views() if self.scene() else []
        parent = views[0] if views else None
        menu = QMenu(parent)

        menu.addAction("Roll",  self.roll)
        menu.addAction("Reset", self.reset_value)
        menu.addSeparator()
        menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(self))
        menu.addAction("Delete",    lambda: self.delete_requested.emit(self))
        menu.addSeparator()
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

    def _toggle_hover_preview(self) -> None:
        new_val = not self.hover_preview
        self.hover_preview = new_val
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, 'hover_preview'):
                    item.hover_preview = new_val

    # ------------------------------------------------------------------
    # Serialisation helper
    # ------------------------------------------------------------------

    def to_state_dict(self) -> dict:
        return {
            "die_type":  self.die_type,
            "set_name":  self.set_name,
            "value":     self.value,
            "x":         self.pos().x(),
            "y":         self.pos().y(),
            "z":         self.zValue(),
            "grid_snap": self.grid_snap,
        }
