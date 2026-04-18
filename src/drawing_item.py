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

"""Drawing layer items: freehand strokes and geometric shapes."""
from __future__ import annotations

import math
from typing import List

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject

# Drawing items are placed just above the grid (Z = -1) but below regular
# canvas items (cards/decks/images start at Z = 1.0+).
_DRAWING_INITIAL_Z = 0.5


# ---------------------------------------------------------------------------
# Path smoothing helpers
# ---------------------------------------------------------------------------

def _douglas_peucker(points: List[QPointF], epsilon: float) -> List[QPointF]:
    """Ramer–Douglas–Peucker path simplification."""
    if len(points) <= 2:
        return list(points)
    start, end = points[0], points[-1]
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    dist_sq = dx * dx + dy * dy
    max_dist, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        if dist_sq == 0.0:
            d = math.hypot(points[i].x() - start.x(), points[i].y() - start.y())
        else:
            t = max(0.0, min(1.0,
                ((points[i].x() - start.x()) * dx + (points[i].y() - start.y()) * dy) / dist_sq
            ))
            px = start.x() + t * dx
            py = start.y() + t * dy
            d = math.hypot(points[i].x() - px, points[i].y() - py)
        if d > max_dist:
            max_dist, idx = d, i
    if max_dist > epsilon:
        left  = _douglas_peucker(points[:idx + 1], epsilon)
        right = _douglas_peucker(points[idx:], epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]


def make_smooth_path(points: List[QPointF], epsilon: float = 2.5) -> QPainterPath:
    """Convert a list of input points into a smoothed QPainterPath."""
    if not points:
        return QPainterPath()
    if len(points) == 1:
        path = QPainterPath()
        path.moveTo(points[0])
        return path
    simplified = _douglas_peucker(points, epsilon)
    path = QPainterPath()
    path.moveTo(simplified[0])
    if len(simplified) < 3:
        for p in simplified[1:]:
            path.lineTo(p)
        return path
    # Smooth via quadratic bezier through midpoints
    for i in range(1, len(simplified) - 1):
        p1 = simplified[i]
        p2 = simplified[i + 1]
        mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        path.quadTo(p1, mid)
    path.lineTo(simplified[-1])
    return path


# ---------------------------------------------------------------------------
# DrawingStrokeItem — freehand stroke, not interactive
# ---------------------------------------------------------------------------

class DrawingStrokeItem(QGraphicsObject):
    """A single committed freehand stroke.  Not selectable or movable."""

    def __init__(self, path: QPainterPath, stroke_color: str, stroke_width: int,
                 points: List[QPointF] = None):
        super().__init__()
        self._path         = path
        self._stroke_color = QColor(stroke_color)
        self._stroke_width = stroke_width
        self._points: List[QPointF] = list(points) if points else []

        self.setZValue(_DRAWING_INITIAL_Z)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    False)

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        extra = self._stroke_width / 2.0 + 1.0
        return self._path.boundingRect().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(self._stroke_color, self._stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

    def shape(self) -> QPainterPath:
        # Make hit-testing use the stroked outline so clicks don't register
        return QPainterPath()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "type":         "stroke",
            "stroke_color": self._stroke_color.name(),
            "stroke_width": self._stroke_width,
            "points":       [[p.x(), p.y()] for p in self._points],
            "z":            self.zValue(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DrawingStrokeItem":
        """Reconstruct from points list (current format) or legacy elements (old sessions)."""
        if "points" in data:
            points = [QPointF(p[0], p[1]) for p in data["points"]]
            path = make_smooth_path(points) if points else QPainterPath()
            item = cls(path, data.get("stroke_color", "#FFFFFF"),
                       data.get("stroke_width", 3), points)
            item.setZValue(data.get("z", _DRAWING_INITIAL_Z))
            return item
        # Legacy: reconstruct from serialized path elements
        return cls._from_elements(data)

    @classmethod
    def from_dict_with_elements(cls, data: dict) -> "DrawingStrokeItem":
        """Alias kept for backward compatibility."""
        return cls.from_dict(data)

    @classmethod
    def _from_elements(cls, data: dict) -> "DrawingStrokeItem":
        """Legacy path-element reconstruction for old session files."""
        path = QPainterPath()
        elements = data.get("elements", [])
        i = 0
        while i < len(elements):
            el = elements[i]
            t = el["t"]
            if t == 0:
                path.moveTo(el["x"], el["y"])
                i += 1
            elif t == 1:
                path.lineTo(el["x"], el["y"])
                i += 1
            elif t == 2:
                if i + 1 < len(elements) and elements[i + 1]["t"] == 3:
                    ctrl = elements[i]
                    end  = elements[i + 1]
                    path.quadTo(ctrl["x"], ctrl["y"], end["x"], end["y"])
                    i += 2
                else:
                    path.lineTo(el["x"], el["y"])
                    i += 1
            else:
                path.lineTo(el["x"], el["y"])
                i += 1
        item = cls(path, data.get("stroke_color", "#FFFFFF"), data.get("stroke_width", 3))
        item.setZValue(data.get("z", _DRAWING_INITIAL_Z))
        return item


# ---------------------------------------------------------------------------
# DrawingShapeItem — circle or square, fully interactive
# ---------------------------------------------------------------------------

class DrawingShapeItem(QGraphicsObject):
    """A geometric shape (circle or square) placed on the canvas.

    Behaves like ImageItem: selectable, movable, rotatable, Z-raisable.
    """

    delete_requested = pyqtSignal(object)
    customize_requested = pyqtSignal()  # edit selected shapes via DrawingSettingsDialog

    def __init__(
        self,
        shape:        str,    # "circle" | "square"
        rect:         QRectF,
        stroke_color: str,
        stroke_width: int,
        fill_color:   str,
        fill_opacity: int,    # 0–100
    ):
        super().__init__()
        self._shape        = shape
        self._rect         = QRectF(rect)
        self._stroke_color = QColor(stroke_color)
        self._stroke_width = stroke_width
        fill               = QColor(fill_color)
        fill.setAlpha(int(fill_opacity * 255 / 100))
        self._fill_color   = fill
        self._base_z       = _DRAWING_INITIAL_Z

        self.setZValue(self._base_z)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,    True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        extra = self._stroke_width / 2.0 + 1.0
        return self._rect.adjusted(-extra, -extra, extra, extra)

    def shape(self) -> QPainterPath:
        # Ensure right-click hit-testing (scene.itemAt) can find this item.
        # Without an explicit shape(), some platforms default to an
        # "empty" hit-test region for QGraphicsObject-derived items.
        from PyQt6.QtGui import QPainterPath as _QPainterPath
        path = _QPainterPath()
        extra = self._stroke_width / 2.0 + 1.0
        hit = self._rect.adjusted(-extra, -extra, extra, extra)
        if self._shape == "circle":
            path.addEllipse(hit)
        else:
            path.addRect(hit)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(self._stroke_color, self._stroke_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(self._fill_color))
        if self._shape == "circle":
            painter.drawEllipse(self._rect)
        else:
            painter.drawRect(self._rect)

        # Selection highlight
        if self.isSelected():
            sel_pen = QPen(QColor("#BFA381"), 1, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            extra = self._stroke_width / 2.0 + 3.0
            painter.drawRect(self._rect.adjusted(-extra, -extra, extra, extra))

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._raise_to_top()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QMenu

        # Ensure right-clicked shape participates in selection.
        if not self.isSelected():
            if self.scene():
                self.scene().clearSelection()
            self.setSelected(True)

        scene = self.scene()
        sel_shapes = [i for i in scene.selectedItems() if isinstance(i, DrawingShapeItem)] if scene else [self]
        if self not in sel_shapes:
            sel_shapes = [self] + sel_shapes
        multi = len(sel_shapes) > 1

        views = scene.views() if scene else []
        parent = views[0] if views else None

        menu = QMenu(parent)

        customize_label = f"Customize… ({len(sel_shapes)})" if multi else "Customize…"
        menu.addAction(customize_label, self.customize_requested.emit)

        del_label = f"Delete ({len(sel_shapes)})" if multi else "Delete"
        menu.addAction(del_label, lambda: [sh.delete_requested.emit(sh) for sh in sel_shapes])

        menu.exec(QCursor.pos())

    # ------------------------------------------------------------------
    # Z-order
    # ------------------------------------------------------------------

    def _raise_to_top(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        from .card_item   import CardItem
        from .deck_item   import DeckItem
        from .image_item  import ImageItem
        candidates = [
            it for it in scene.items()
            if isinstance(it, (CardItem, DeckItem, ImageItem, DrawingShapeItem))
            and it is not self
        ]
        max_z = max((it.zValue() for it in candidates), default=0.0)
        self._base_z = max_z + 1
        self.setZValue(self._base_z)

    def send_to_back(self) -> None:
        self._base_z = _DRAWING_INITIAL_Z
        self.setZValue(self._base_z)

    # ------------------------------------------------------------------
    # Live resize during placement (update rect while user drags)
    # ------------------------------------------------------------------

    def update_rect(self, rect: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self.update()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "type":         "shape",
            "shape":        self._shape,
            "x":            self._rect.x(),
            "y":            self._rect.y(),
            "w":            self._rect.width(),
            "h":            self._rect.height(),
            "stroke_color": self._stroke_color.name(),
            "stroke_width": self._stroke_width,
            "fill_color":   QColor(
                self._fill_color.red(),
                self._fill_color.green(),
                self._fill_color.blue(),
            ).name(),
            "fill_opacity": int(self._fill_color.alpha() * 100 / 255),
            "rotation":     self.rotation(),
            "pos_x":        self.pos().x(),
            "pos_y":        self.pos().y(),
            "z":            self.zValue(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DrawingShapeItem":
        rect = QRectF(data["x"], data["y"], data["w"], data["h"])
        item = cls(
            shape        = data.get("shape", "square"),
            rect         = rect,
            stroke_color = data.get("stroke_color", "#FFFFFF"),
            stroke_width = data.get("stroke_width", 3),
            fill_color   = data.get("fill_color",   "#FFFFFF"),
            fill_opacity = data.get("fill_opacity",  0),
        )
        item.setPos(data.get("pos_x", 0.0), data.get("pos_y", 0.0))
        item.setRotation(data.get("rotation", 0.0))
        item.setZValue(data.get("z", _DRAWING_INITIAL_Z))
        item._base_z = item.zValue()
        return item
