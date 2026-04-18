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

import math
import random

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QPropertyAnimation,
    QRectF, Qt, QTimer, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsObject, QMenu,
)

from .dice_manager import DIE_MAX, DiceSetsManager, face_values, roll_value


class DieItem(QGraphicsObject):
    """A single die placed on the canvas.

    Displays the current face PNG, animates a roll with face cycling,
    cross-fade between faces, raise/scale effect, and shadow growth.
    """

    # Signals
    delete_requested          = pyqtSignal(object)  # self
    delete_selected_requested = pyqtSignal()        # delete all selected items
    duplicate_requested = pyqtSignal(object)        # self
    rolled              = pyqtSignal(object, int)   # self, final_value
    accent_apply_requested = pyqtSignal(object)     # (list[DieItem], accent_hex, accent_name)
    roll_group_requested   = pyqtSignal(object)     # list[DieItem]

    def __init__(
        self,
        die_type: str,
        set_name: str,
        dice_manager: DiceSetsManager,
        settings,
        parent=None,
    ):
        super().__init__(parent)

        self.die_type  = die_type
        self.set_name  = set_name
        self._manager  = dice_manager
        self._settings = settings

        self._die_size: int    = settings.canvas("grid_size")
        self._spin_angle: float = 0.0
        self.value: int        = DIE_MAX.get(die_type, 6)
        self._prev_value: int  = self.value

        # Cross-fade state
        self._face_fade_val: float = 1.0   # 1.0 = fully on current face

        # Persistent Z order
        self._base_z: float = 1.0

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
        )
        self.setAcceptHoverEvents(False)
        self.setZValue(1)
        self._update_transform_origin()

        # Drop shadow — resting values match DeckItem for visual consistency
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(14)
        self._shadow.setOffset(5, 8)
        self._shadow.setColor(QColor(0, 0, 0, 170))
        self.setGraphicsEffect(self._shadow)

        # Roll lift factor: 0.0 = resting, 1.0 = peak of roll arc
        # Drives shadow blur/offset and item scale simultaneously.
        self._roll_lift_val: float = 0.0

        # ── Spin animation ──────────────────────────────────────────────
        self._roll_anim = QPropertyAnimation(self, b"spin_angle")
        self._roll_anim.setDuration(1000)
        self._roll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._roll_anim.finished.connect(self._on_roll_finished)

        # ── Face cycling timer (interval lengthens as roll progresses) ──
        self._roll_timer = QTimer()
        self._roll_timer.setInterval(20)
        self._roll_timer.timeout.connect(self._randomise_face)

        # ── Cross-fade animation ─────────────────────────────────────────
        self._fade_anim = QPropertyAnimation(self, b"face_fade")
        self._fade_anim.setDuration(15)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)

        # ── Face lock-in timer — fires 50ms before roll ends ─────────────
        self._lock_timer = QTimer()
        self._lock_timer.setSingleShot(True)
        self._lock_timer.timeout.connect(self._lock_in_final_face)

        # ── Settle animation (eases roll_lift → 0 after roll ends) ──────
        self._settle_anim = QPropertyAnimation(self, b"roll_lift")
        self._settle_anim.setDuration(300)
        self._settle_anim.setEndValue(0.0)
        self._settle_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── D2 flip animation ─────────────────────────────────────────────
        self._flip_angle_val:   float = 0.0
        self._flip_start_face:  int   = 1
        self._flip_total_angle: float = 720.0
        self._flip_anim = QPropertyAnimation(self, b"flip_angle")
        self._flip_anim.setDuration(1000)
        self._flip_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._flip_anim.finished.connect(self._on_flip_finished)

        # Final value to snap to when animation ends
        self._final_value: int = self.value
        # When False, suppress the rolled signal (used for grouped rolls)
        self._log_individual: bool = True
        # When True, loop the roll animation seamlessly (hold-R behaviour)
        self.keep_rolling: bool = False

        self.hover_preview: bool = False
        self.grid_snap: bool     = False
        self.grid_size: int      = settings.canvas("grid_size")

    # ------------------------------------------------------------------
    # pyqtProperties
    # ------------------------------------------------------------------

    def _get_spin(self) -> float:
        return self._spin_angle

    def _set_spin(self, v: float) -> None:
        self._spin_angle = v
        self.update()

    spin_angle = pyqtProperty(float, _get_spin, _set_spin)

    def _get_face_fade(self) -> float:
        return self._face_fade_val

    def _set_face_fade(self, v: float) -> None:
        self._face_fade_val = v
        self.update()

    face_fade = pyqtProperty(float, _get_face_fade, _set_face_fade)

    def _get_roll_lift(self) -> float:
        return self._roll_lift_val

    def _set_roll_lift(self, v: float) -> None:
        self._roll_lift_val = v
        # Shadow grows from resting (blur=14, offset=5,8) toward peak (blur=34, offset=13,20.8)
        blur     = 14 + v * 20
        offset_x = 5  + v * 8
        offset_y = 8  + v * 12.8
        self._shadow.setBlurRadius(blur)
        self._shadow.setOffset(offset_x, offset_y)
        self.setScale(1.0 + v * 0.25)
        self.update()

    roll_lift = pyqtProperty(float, _get_roll_lift, _set_roll_lift)

    def _get_flip_angle(self) -> float:
        return self._flip_angle_val

    def _set_flip_angle(self, v: float) -> None:
        old_seg = int(self._flip_angle_val / 180)
        self._flip_angle_val = v
        new_seg = int(v / 180)
        if new_seg > old_seg:
            # Crossed a 180° boundary — toggle face (d2 has faces 1 and 2)
            other = 3 - self._flip_start_face
            self.value = self._flip_start_face if new_seg % 2 == 0 else other
        # Drive roll lift from flip progress (peaks at mid-flip)
        progress = min(1.0, v / max(1.0, self._flip_total_angle))
        self.roll_lift = math.sin(progress * math.pi)

    flip_angle = pyqtProperty(float, _get_flip_angle, _set_flip_angle)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        s = self._die_size
        return QRectF(0, 0, s, s)

    def _update_transform_origin(self) -> None:
        s = self._die_size
        self.setTransformOriginPoint(s / 2.0, s / 2.0)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget) -> None:
        s = self._die_size
        icon_rect = QRectF(0, 0, s, s)

        painter.save()
        cx, cy = s / 2.0, s / 2.0
        if self.die_type == "d2":
            # Vertical flip: squish Y around the horizontal centre axis
            scale_y = max(abs(math.cos(math.radians(self._flip_angle_val))), 0.001)
            painter.translate(cx, cy)
            painter.scale(1.0, scale_y)
            painter.translate(-cx, -cy)
        else:
            painter.translate(cx, cy)
            painter.rotate(self._spin_angle)
            painter.translate(-cx, -cy)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        curr_pix = self._manager.get_face_pixmap(
            self.die_type, self.value, self.set_name, s
        )

        if self._face_fade_val < 1.0 and self._prev_value != self.value:
            prev_pix = self._manager.get_face_pixmap(
                self.die_type, self._prev_value, self.set_name, s
            )
            painter.setOpacity(1.0 - self._face_fade_val)
            painter.drawPixmap(icon_rect.toRect(), prev_pix)
            painter.setOpacity(self._face_fade_val)
            painter.drawPixmap(icon_rect.toRect(), curr_pix)
            painter.setOpacity(1.0)
        else:
            painter.drawPixmap(icon_rect.toRect(), curr_pix)

        painter.restore()

        # Selection ring
        from PyQt6.QtWidgets import QStyle
        if bool(option.state & QStyle.StateFlag.State_Selected):
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(icon_rect)

    # ------------------------------------------------------------------
    # Roll logic
    # ------------------------------------------------------------------

    def roll(self) -> None:
        if self.die_type == "d2":
            if self._flip_anim.state() == QAbstractAnimation.State.Running:
                return
            self._settle_anim.stop()
            self._final_value      = roll_value(self.die_type)
            self._flip_start_face  = self.value
            # 4 full flips (1440°); add a half-flip (180°) if needed to land on the correct face
            total = 1440.0 if self._final_value == self.value else 1620.0
            self._flip_total_angle = total
            self._flip_angle_val   = 0.0
            self._flip_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._flip_anim.setStartValue(0.0)
            self._flip_anim.setEndValue(total)
            self._flip_anim.start()
            return

        if self._roll_anim.state() == QAbstractAnimation.State.Running:
            return

        self._settle_anim.stop()
        self._final_value = roll_value(self.die_type)

        self._spin_angle = 0.0
        self._roll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._roll_anim.setStartValue(0.0)
        self._roll_anim.setEndValue(1440.0)
        self._roll_timer.setInterval(20)
        self._roll_timer.start()
        self._roll_anim.start()
        self._lock_timer.start(self._roll_anim.duration() - 50)

    def _randomise_face(self) -> None:
        faces = face_values(self.die_type)
        new_val = self.value
        # Avoid same face twice in a row when there are choices
        if len(faces) > 1:
            while new_val == self.value:
                new_val = faces[random.randrange(len(faces))]
        self._prev_value = self.value
        self.value = new_val

        # Cross-fade to new face
        self._face_fade_val = 0.0
        self._fade_anim.stop()
        self._fade_anim.start()

        # Decelerate cycling: interval grows from 20ms → 400ms over roll duration
        elapsed  = self._roll_anim.currentTime()
        duration = max(1, self._roll_anim.duration())
        progress = min(1.0, elapsed / duration)
        self._roll_timer.setInterval(int(20 + progress * 380))

        # Raise effect peaks mid-roll — drives shadow + scale via roll_lift property
        self._roll_lift_val = math.sin(progress * math.pi)
        blur     = 14 + self._roll_lift_val * 20
        offset_x = 5  + self._roll_lift_val * 8
        offset_y = 8  + self._roll_lift_val * 12.8
        self._shadow.setBlurRadius(blur)
        self._shadow.setOffset(offset_x, offset_y)
        self.setScale(1.0 + self._roll_lift_val * 0.25)

        self.update()

    def _lock_in_final_face(self) -> None:
        """Stop face cycling and show the final result, called 50ms before roll ends."""
        self._roll_timer.stop()
        if self.value != self._final_value:
            self._prev_value = self.value
            self.value = self._final_value
            self._face_fade_val = 0.0
            self._fade_anim.stop()
            self._fade_anim.start()

    def _on_roll_finished(self) -> None:
        self._roll_timer.stop()
        self._spin_angle = 0.0

        # Final face (may already be set by the 50ms-early lock-in)
        if self.value != self._final_value:
            self._prev_value = self.value
            self.value = self._final_value
            self._face_fade_val = 0.0
            self._fade_anim.stop()
            self._fade_anim.start()

        if self.keep_rolling:
            # Seamless loop at full speed: linear easing, no settle, no signal
            self._final_value = roll_value(self.die_type)
            self._spin_angle  = 0.0
            self._roll_anim.setEasingCurve(QEasingCurve.Type.Linear)
            self._roll_anim.setStartValue(0.0)
            self._roll_anim.setEndValue(1440.0)
            self._roll_timer.setInterval(20)
            self._roll_timer.start()
            self._roll_anim.start()
            self._lock_timer.start(self._roll_anim.duration() - 50)
            return

        # Normal finish — settle raise effect back to resting
        self._lock_timer.stop()
        self._settle_anim.stop()
        self._settle_anim.setStartValue(self._roll_lift_val)
        self._settle_anim.start()
        self.update()

        if self._log_individual:
            self.rolled.emit(self, self._final_value)
        else:
            self._log_individual = True

    def _on_flip_finished(self) -> None:
        if self.keep_rolling:
            # Seamless loop: 4 half-flips (720°) at linear speed, no settle
            self._flip_start_face  = self.value
            self._flip_total_angle = 720.0
            self._flip_angle_val   = 0.0
            self._flip_anim.setEasingCurve(QEasingCurve.Type.Linear)
            self._flip_anim.setStartValue(0.0)
            self._flip_anim.setEndValue(720.0)
            self._flip_anim.start()
            return

        # Normal finish
        self._flip_angle_val = 0.0
        self._flip_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if self.value != self._final_value:
            self._prev_value = self.value
            self.value = self._final_value
            self._face_fade_val = 0.0
            self._fade_anim.stop()
            self._fade_anim.start()
        # Settle shadow/scale back to resting
        self._settle_anim.stop()
        self._settle_anim.setStartValue(self._roll_lift_val)
        self._settle_anim.start()
        self.update()
        if self._log_individual:
            self.rolled.emit(self, self._final_value)
        else:
            self._log_individual = True

    def set_face(self, value: int) -> None:
        """Display a specific face value immediately (no roll animation).

        No-op while a roll or flip animation is running — the animation owns
        the face during that time and would override the change anyway.
        """
        from PyQt6.QtCore import QAbstractAnimation
        if (self._roll_anim.state() == QAbstractAnimation.State.Running or
                self._flip_anim.state() == QAbstractAnimation.State.Running):
            return
        self._prev_value = self.value
        self.value = value
        # Short cross-fade (same 15 ms used during roll cycling) for visual feedback
        self._face_fade_val = 0.0
        self._fade_anim.stop()
        self._fade_anim.start()
        self.update()

    def reset_value(self) -> None:
        """Reset to the maximum (default) face value."""
        self._prev_value = self.value
        self.value = DIE_MAX.get(self.die_type, 6)
        self._face_fade_val = 1.0
        self.update()

    # ------------------------------------------------------------------
    # Size update (called when grid_size changes)
    # ------------------------------------------------------------------

    def update_die_size(self, new_size: int) -> None:
        self.prepareGeometryChange()
        self._die_size = new_size
        self._update_transform_origin()
        self.update()

    # ------------------------------------------------------------------
    # Z-order
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
            g = self.grid_size
            mode = getattr(self.scene(), "snap_mode", "centered")
            br = self.boundingRect()
            hw = br.width()  / 2
            hh = br.height() / 2
            cx = value.x() + hw
            cy = value.y() + hh
            if mode == "centered":
                snapped_cx = math.floor(cx / g) * g + g / 2
                snapped_cy = math.floor(cy / g) * g + g / 2
            else:
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
        # Option A: right-clicking an unselected item clears the selection
        if not self.isSelected():
            self.scene().clearSelection()
            self.setSelected(True)

        views = self.scene().views() if self.scene() else []
        parent = views[0] if views else None
        menu = QMenu(parent)

        sel_dice = [i for i in self.scene().selectedItems() if isinstance(i, DieItem)]
        multi = len(sel_dice) > 1

        roll_label = f"Roll ({len(sel_dice)})" if multi else "Roll"
        if multi:
            def _roll_group() -> None:
                # Suppress individual roll logs; main window logs once.
                for i in sel_dice:
                    i._log_individual = False
                for i in sel_dice:
                    i.roll()
                self.roll_group_requested.emit(sel_dice)

            menu.addAction(roll_label, _roll_group)
        else:
            menu.addAction(roll_label, self.roll)
            menu.addAction("Reset", self.reset_value)
        menu.addSeparator()
        if not multi:
            menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(self))
        del_label = f"Delete ({len(sel_dice)})" if multi else "Delete"
        menu.addAction(del_label, self.delete_selected_requested.emit)
        menu.addSeparator()
        snap_label    = "✓ Snap to Grid" if self.grid_snap    else "Snap to Grid"
        preview_label = "Preview: On"    if self.hover_preview else "Preview: Off"
        menu.addAction(snap_label,    self._toggle_snap)
        menu.addAction(preview_label, self._toggle_hover_preview)

        # Accent apply (color1 override) — applies to currently selected dice
        accent_label = f"Accent… ({len(sel_dice)})" if multi else "Accent…"
        accent_menu = menu.addMenu(accent_label)
        for name, hex_val in self._accent_presets():
            accent_menu.addAction(name, lambda _=False, h=hex_val, n=name: self._apply_accent_hex(sel_dice, h, n))
        accent_menu.addSeparator()
        accent_menu.addAction("Custom…", lambda _=False: self._request_accent_custom(sel_dice, parent))

        from PyQt6.QtGui import QCursor
        menu.exec(QCursor.pos())

    @staticmethod
    def _accent_presets() -> list[tuple[str, str]]:
        """Named accent palette (hex values stored in dice sets)."""
        return [
            ("White", "#ffffff"),
            ("Black", "#000000"),
            ("Red", "#ef4444"),
            ("Orange", "#f97316"),
            ("Amber", "#f59e0b"),
            ("Yellow", "#eab308"),
            ("Lime", "#a3e635"),
            ("Green", "#22c55e"),
            ("Emerald", "#10b981"),
            ("Teal", "#14b8a6"),
            ("Cyan", "#06b6d4"),
            ("Sky", "#0ea5e9"),
            ("Blue", "#3b82f6"),
            ("Indigo", "#6366f1"),
            ("Violet", "#8b5cf6"),
            ("Purple", "#a855f7"),
            ("Fuchsia", "#d946ef"),
            ("Pink", "#ec4899"),
            ("Brown", "#a16207"),
            ("Sand", "#d6bc8a"),
        ]

    def _apply_accent_hex(self, sel_dice: list["DieItem"], accent_hex: str, accent_name: str) -> None:
        """Emit MainWindow request to apply the given accent to the selected dice."""
        self.accent_apply_requested.emit((sel_dice, accent_hex, accent_name))

    def _request_accent_custom(self, sel_dice: list["DieItem"], parent) -> None:
        """Prompt for a custom accent color."""
        from PyQt6.QtWidgets import QColorDialog

        # Use the first dice's current color1 as the initial value.
        first = sel_dice[0] if sel_dice else self
        accent_hex = "#ffffff"
        ds = self._manager.get_set(getattr(first, "set_name", "")) if self._manager else None
        if ds:
            raw = ds.colors.get(first.die_type) or next(iter(ds.colors.values()), "#ffffff")
            if isinstance(raw, str):
                accent_hex = raw
            elif isinstance(raw, dict):
                accent_hex = raw.get("color1", "#ffffff")

        color = QColorDialog.getColor(
            QColor(accent_hex),
            parent,
            "Custom Accent Color (Color 1)",
        )
        if not color.isValid():
            return

        self.accent_apply_requested.emit((sel_dice, color.name(), "Custom"))

    def _toggle_snap(self) -> None:
        new_val = not self.grid_snap
        self.grid_snap = new_val
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, "grid_snap"):
                    item.grid_snap = new_val

    def _toggle_hover_preview(self) -> None:
        new_val = not self.hover_preview
        self.hover_preview = new_val
        if self.scene() and self.isSelected():
            for item in self.scene().selectedItems():
                if item is not self and hasattr(item, "hover_preview"):
                    item.hover_preview = new_val

    # ------------------------------------------------------------------
    # Serialisation
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
