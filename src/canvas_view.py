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

"""CanvasView – QGraphicsView subclass with zoom, pan, and keyboard routing."""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QEvent, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QKeyEvent, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

ZOOM_MIN = 0.08
ZOOM_MAX = 8.0
ZOOM_FACTOR = 1.15
NN_THRESHOLD = 2.0  # switch to nearest-neighbour above this scale
_HAND_THRESHOLD = 80  # px from viewport bottom that activates the drop zone


class CanvasView(QGraphicsView):
    """
    Handles:
      • Smooth zoom via scroll wheel (when not holding a card)
      • Middle-mouse pan
      • Space-bar pan (drag mode toggle)
      • Rubber-band selection on empty space
      • Keyboard events forwarded to MainWindow via signals
      • Nearest-neighbour rendering above NN_THRESHOLD scale
    """

    zoom_changed             = pyqtSignal(float)    # current scale
    key_action               = pyqtSignal(str)      # action name to process
    rotate_held_item         = pyqtSignal(int)      # +1 = CW, -1 = CCW (wheel while holding)
    canvas_right_click       = pyqtSignal(QPointF)  # scene position
    canvas_pressed           = pyqtSignal()         # any left-press on the canvas
    items_dropped_on_hand    = pyqtSignal(list)     # list of CardItem/DeckItem dragged below viewport
    drag_near_hand           = pyqtSignal(bool)     # True while dragging within threshold of hand strip
    items_merged_into_deck   = pyqtSignal(list, object)  # (items, target DeckItem)

    def __init__(self, scene, settings, parent=None):
        super().__init__(scene, parent)
        self._settings = settings

        self._scale: float = 1.0
        self._panning  = False
        self._pan_last = QPointF()
        self._space_held = False
        self._held_item  = None    # item currently being dragged (left-button)
        self._near_hand: bool = False  # tracks drag-near-hand state to avoid redundant signals
        self._merge_target = None  # DeckItem currently glowing as merge target

        from PyQt6.QtGui import QPainter
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # FullViewportUpdate prevents stale shadow-effect artifacts when items move
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setAcceptDrops(True)

        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    @property
    def current_scale(self) -> float:
        return self._scale

    def _apply_zoom(self, factor: float) -> None:
        new_scale = self._scale * factor
        new_scale = max(ZOOM_MIN, min(ZOOM_MAX, new_scale))
        actual_factor = new_scale / self._scale
        self._scale = new_scale
        self.scale(actual_factor, actual_factor)
        self._update_render_hints()
        self.zoom_changed.emit(self._scale)

    def zoom_in(self)  -> None: self._apply_zoom(ZOOM_FACTOR)
    def zoom_out(self) -> None: self._apply_zoom(1.0 / ZOOM_FACTOR)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self._scale = 1.0
        self._update_render_hints()
        self.zoom_changed.emit(1.0)

    def center_on_origin(self) -> None:
        self.centerOn(0, 0)

    def center_on_item(self, item) -> None:
        self.centerOn(item)

    def _update_render_hints(self) -> None:
        from PyQt6.QtGui import QPainter
        smooth = self._scale < NN_THRESHOLD
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)

    # ------------------------------------------------------------------
    # Wheel event – zoom or rotate held item
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if self._held_item is not None:
            # Rotate held card/deck
            direction = 1 if delta > 0 else -1
            self.rotate_held_item.emit(direction)
            event.accept()
        else:
            factor = ZOOM_FACTOR if delta > 0 else 1.0 / ZOOM_FACTOR
            self._apply_zoom(factor)
            event.accept()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Middle-mouse pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last = event.position()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.canvas_pressed.emit()
            item = self.itemAt(event.pos())
            if item is not None:
                # Dragging an item
                self._held_item = item
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                # Rubber-band on empty space
                self._held_item = None
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return

        super().mouseMoveEvent(event)

        # Emit hovered scene position for magnify
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)
        from .card_item  import CardItem
        from .deck_item  import DeckItem
        for it in items:
            if isinstance(it, (CardItem, DeckItem)):
                break

        # Emit drag-near-hand highlight signal
        if self._held_item is not None and isinstance(self._held_item, (CardItem, DeckItem)):
            near = event.pos().y() >= (self.viewport().rect().bottom() - _HAND_THRESHOLD)
            if near != self._near_hand:
                self._near_hand = near
                self.drag_near_hand.emit(near)

            # Deck merge glow: find a non-selected DeckItem under the held item
            held_scene_pos = self._held_item.scenePos()
            new_target = None
            for item in self.scene().items(held_scene_pos):
                if isinstance(item, DeckItem) and item is not self._held_item and not item.isSelected():
                    new_target = item
                    break
            if new_target is not self._merge_target:
                if self._merge_target:
                    self._merge_target.set_merge_highlight(False)
                self._merge_target = new_target
                if self._merge_target:
                    self._merge_target.set_merge_highlight(True)
        elif self._near_hand:
            self._near_hand = False
            self.drag_near_hand.emit(False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            event.accept()
            return

        held = None
        if event.button() == Qt.MouseButton.LeftButton:
            held = self._held_item
            self._held_item = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

            # Clear near-hand highlight
            if self._near_hand:
                self._near_hand = False
                self.drag_near_hand.emit(False)

            # Clear merge glow
            if self._merge_target:
                self._merge_target.set_merge_highlight(False)
                self._merge_target = None

        # Let items handle their own release (lift animation, etc.)
        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and held is not None:
            from .card_item import CardItem
            from .deck_item import DeckItem
            if isinstance(held, (CardItem, DeckItem)):
                scene = self.scene()

                # Check for deck merge: held item (or any selected item) dropped on a DeckItem
                held_scene_pos = held.scenePos()
                target_deck = None
                for item in scene.items(held_scene_pos):
                    if isinstance(item, DeckItem) and item is not held and not item.isSelected():
                        target_deck = item
                        break

                if target_deck is not None:
                    selected = scene.selectedItems() if scene else []
                    # Only merge CardItems and stack DeckItems (not regular decks)
                    to_merge = [
                        it for it in selected
                        if (isinstance(it, CardItem) or
                            (isinstance(it, DeckItem) and it.is_stack))
                        and it is not target_deck
                    ]
                    if isinstance(held, CardItem) and held not in to_merge:
                        to_merge.append(held)
                    elif isinstance(held, DeckItem) and held.is_stack and held not in to_merge:
                        to_merge.append(held)
                    if to_merge:
                        self.items_merged_into_deck.emit(to_merge, target_deck)
                    return

                # Check if items were dragged down onto the hand strip
                vp = self.viewport()
                vp_bottom_global_y = vp.mapToGlobal(vp.rect().bottomLeft()).y()
                if QCursor.pos().y() > vp_bottom_global_y:
                    selected = scene.selectedItems() if scene else []
                    to_send = [
                        it for it in selected
                        if isinstance(it, (CardItem, DeckItem))
                    ]
                    if held not in to_send:
                        to_send.append(held)
                    self.items_dropped_on_hand.emit(to_send)

    # ------------------------------------------------------------------
    # Key events – forwarded to MainWindow via signal
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Space → temporary pan
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
            return

        # Build action name from key string and forward
        key_seq = _key_event_to_str(event)
        if key_seq:
            self.key_action.emit(key_seq)

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            event.accept()
            return
        super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drag/drop forwarded to scene
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if self.scene():
            # Convert to scene event
            self.scene().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self.scene():
            self.scene().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if self.scene():
            # Translate widget coords to scene coords for the scene drop handler
            scene_pos = self.mapToScene(event.position().toPoint())
            self.scene().dropEvent(_SceneDropProxy(event, scene_pos))
        else:
            event.ignore()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _key_event_to_str(event: QKeyEvent) -> str:
    """Convert a key event to a string like 'Ctrl+R' or 'F'."""
    key  = event.key()
    mods = event.modifiers()

    # Ignore lone modifiers
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
               Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return ""

    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")

    # Number keys
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        parts.append(str(key - Qt.Key.Key_0))
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        # Use key code directly — event.text() yields a control char when Ctrl is held
        parts.append(chr(key))
    elif key == Qt.Key.Key_Delete:
        parts.append("Delete")
    elif key == Qt.Key.Key_Escape:
        parts.append("Escape")
    else:
        text = event.text()
        if text and text.isprintable():
            parts.append(text.upper())
        else:
            return ""

    return "+".join(parts)


class _SceneDropProxy:
    """Lightweight proxy so scene.dropEvent gets a scenePos() method."""
    def __init__(self, event, scene_pos):
        self._event = event
        self._scene_pos = scene_pos

    def __getattr__(self, name):
        return getattr(self._event, name)

    def scenePos(self):
        return self._scene_pos
