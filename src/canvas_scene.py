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

"""CanvasScene – QGraphicsScene with custom background, grid, and drop support."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QTransform,
)
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene, QMenu

from .image_item import _is_image_path

_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp'}


def _is_image_url(url) -> bool:
    return url.isLocalFile() and _is_image_path(url.toLocalFile())


class GridLayer(QGraphicsItem):
    """Non-interactive item that draws the grid at Z=-1, above image anchors."""

    def __init__(self, canvas_scene: "CanvasScene"):
        super().__init__()
        self._canvas_scene = canvas_scene
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)

    def boundingRect(self) -> QRectF:
        return QRectF(-8000, -8000, 16000, 16000)

    def shape(self) -> QPainterPath:
        return QPainterPath()  # empty – never hit-tested by itemAt()

    def paint(self, painter: QPainter, option, widget) -> None:
        if self._canvas_scene.grid_visible:
            self._canvas_scene._draw_grid(painter, option.exposedRect)


class CanvasScene(QGraphicsScene):
    """
    The main canvas scene.
    Handles:
      • custom background (colour or image in various modes)
      • optional grid overlay
      • right-click context menu on empty space
      • drag-and-drop from HandWidget
    """

    # Emitted when a card (or cards) is dropped from the hand onto the canvas
    hand_card_dropped      = pyqtSignal(dict, QPointF)   # single card: raw dict, scene pos
    hand_cards_dropped     = pyqtSignal(list, QPointF)   # multi-card:  list of dicts, scene pos
    # Emitted when an image file is dragged from Explorer onto the canvas
    external_image_dropped = pyqtSignal(str, QPointF)    # local file path, scene pos

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings

        # Background
        self.bg_mode:       str            = settings.canvas("background_mode")
        self.bg_color:      str            = settings.canvas("background_color")
        self.bg_image_path: Optional[str]  = settings.canvas("background_image_path")
        self._bg_pix:       Optional[QPixmap] = None
        self._load_bg_image()

        # Grid
        self.grid_visible: bool = settings.canvas("grid_enabled")
        self.grid_size:    int  = settings.canvas("grid_size")
        self.grid_color:   str  = settings.canvas("grid_color")
        self.snap_mode:    str  = settings.canvas("grid_snap_mode")  # "lines" | "centered"

        # Very large scene rect for the "infinite" canvas feel
        self.setSceneRect(-8000, -8000, 16000, 16000)

        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)

        # Grid layer at Z=-1 so image anchors (Z<-1) render below it
        self._grid_layer = GridLayer(self)
        self.addItem(self._grid_layer)

    # ------------------------------------------------------------------
    # Background helpers
    # ------------------------------------------------------------------

    def _load_bg_image(self) -> None:
        self._bg_pix = None
        if self.bg_image_path and Path(self.bg_image_path).exists():
            self._bg_pix = QPixmap(self.bg_image_path)

    def set_background(
        self,
        mode: str,
        color: Optional[str] = None,
        image_path: Optional[str] = None,
    ) -> None:
        self.bg_mode = mode
        if color is not None:
            self.bg_color = color
        if image_path is not None:
            self.bg_image_path = image_path
            self._load_bg_image()
        self._settings.set_canvas("background_mode",       self.bg_mode)
        self._settings.set_canvas("background_color",      self.bg_color)
        self._settings.set_canvas("background_image_path", self.bg_image_path)
        self.update()

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    def set_grid(self, visible: bool, size: Optional[int] = None) -> None:
        self.grid_visible = visible
        if size is not None:
            self.grid_size = size
        self._settings.set_canvas("grid_enabled", visible)
        self.update()

    def set_grid_color(self, color: str) -> None:
        self.grid_color = color
        self._settings.set_canvas("grid_color", color)
        self.update()

    # ------------------------------------------------------------------
    # Background rendering
    # ------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        # 1. Solid colour fill
        painter.fillRect(rect, QColor(self.bg_color))

        # 2. Image layer
        if self._bg_pix and not self._bg_pix.isNull():
            mode = self.bg_mode
            if mode == "image_tiled":
                painter.drawTiledPixmap(rect, self._bg_pix)

            elif mode == "image_scaled":
                target = QRectF(self._bg_pix.rect())
                target.moveCenter(QPointF(0, 0))
                w = rect.width()
                h = rect.height()
                pw = self._bg_pix.width()
                ph = self._bg_pix.height()
                scale = min(w / pw, h / ph)
                sw, sh = pw * scale, ph * scale
                target = QRectF(-sw / 2, -sh / 2, sw, sh)
                painter.drawPixmap(target.toRect(), self._bg_pix)

            elif mode == "image_stretched":
                sr = self.sceneRect()
                painter.drawPixmap(sr.toRect(), self._bg_pix)

            elif mode == "image_centered":
                pw = self._bg_pix.width()
                ph = self._bg_pix.height()
                img_rect = QRectF(-pw / 2, -ph / 2, pw, ph)
                painter.drawPixmap(img_rect.toRect(), self._bg_pix)
                # Fade edges when image doesn't fill viewport
                self._draw_centered_fade(painter, rect, img_rect)

        # Grid is rendered by GridLayer at Z=-1 (above anchors, below normal items)

    def _draw_centered_fade(
        self, painter: QPainter, view_rect: QRectF, img_rect: QRectF
    ) -> None:
        """Fade the area outside the image to black."""
        bg = QColor(self.bg_color)
        alpha = 200
        fade_w = 80

        def _fill_grad(x, y, w, h, x1, y1, x2, y2, c_start, c_end):
            grad = QLinearGradient(x1, y1, x2, y2)
            grad.setColorAt(0, c_start)
            grad.setColorAt(1, c_end)
            painter.fillRect(QRectF(x, y, w, h), grad)

        trans = QColor(bg.red(), bg.green(), bg.blue(), 0)
        solid = QColor(bg.red(), bg.green(), bg.blue(), alpha)

        if view_rect.left() < img_rect.left():
            _fill_grad(view_rect.left(), view_rect.top(),
                       img_rect.left() - view_rect.left(), view_rect.height(),
                       view_rect.left(), 0, img_rect.left(), 0, solid, trans)
        if view_rect.right() > img_rect.right():
            _fill_grad(img_rect.right(), view_rect.top(),
                       view_rect.right() - img_rect.right(), view_rect.height(),
                       img_rect.right(), 0, view_rect.right(), 0, trans, solid)
        if view_rect.top() < img_rect.top():
            _fill_grad(view_rect.left(), view_rect.top(),
                       view_rect.width(), img_rect.top() - view_rect.top(),
                       0, view_rect.top(), 0, img_rect.top(), solid, trans)
        if view_rect.bottom() > img_rect.bottom():
            _fill_grad(view_rect.left(), img_rect.bottom(),
                       view_rect.width(), view_rect.bottom() - img_rect.bottom(),
                       0, img_rect.bottom(), 0, view_rect.bottom(), trans, solid)

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        g = self.grid_size
        pen = QPen(QColor(self.grid_color), 0.5, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        left   = int(rect.left()   / g) * g - g
        top    = int(rect.top()    / g) * g - g
        right  = int(rect.right()  / g) * g + g
        bottom = int(rect.bottom() / g) * g + g

        x = left
        while x <= right:
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += g
        y = top
        while y <= bottom:
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += g

    # ------------------------------------------------------------------
    # Context menu on empty space
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        transform = self.views()[0].transform() if self.views() else QTransform()
        item = self.itemAt(event.scenePos(), transform)
        if item is None or isinstance(item, GridLayer):
            self._show_canvas_menu(event)
        else:
            super().contextMenuEvent(event)

    def _show_canvas_menu(self, event) -> None:
        views = self.views()
        parent = views[0] if views else None
        menu = QMenu(parent)

        if views:
            view = views[0]
            menu.addAction("Reset Zoom",     lambda: view.reset_zoom())
            menu.addAction("Center View",    lambda: view.center_on_origin())
            menu.addSeparator()

        menu.addAction("Customize Background…", self._open_bg_dialog)
        menu.addSeparator()
        grid_label = "Hide Grid" if self.grid_visible else "Show Grid"
        menu.addAction(grid_label, lambda: self.set_grid(not self.grid_visible))
        lines_label    = "✓ Snap: Lines"    if self.snap_mode == "lines"    else "Snap: Lines"
        centered_label = "✓ Snap: Centered" if self.snap_mode == "centered" else "Snap: Centered"
        snap_sub = menu.addMenu("Grid Snap Mode")
        snap_sub.addAction(lines_label,    lambda: self._set_snap_mode("lines"))
        snap_sub.addAction(centered_label, lambda: self._set_snap_mode("centered"))

        from PyQt6.QtGui import QCursor
        menu.exec(QCursor.pos())

    def _set_snap_mode(self, mode: str) -> None:
        self.snap_mode = mode
        self._settings.set_canvas("grid_snap_mode", mode)

    def _open_bg_dialog(self) -> None:
        if not self.views():
            return
        from .dialogs import BackgroundDialog
        dlg = BackgroundDialog(self, self.views()[0].window())
        dlg.exec()

    # ------------------------------------------------------------------
    # Drag-and-drop from HandWidget
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if (mime.hasFormat("application/x-solocanvas-cards") or
                mime.hasFormat("application/x-solocanvas-card")):
            event.acceptProposedAction()
        elif mime.hasUrls() and any(_is_image_url(u) for u in mime.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        mime = event.mimeData()
        if (mime.hasFormat("application/x-solocanvas-cards") or
                mime.hasFormat("application/x-solocanvas-card")):
            event.acceptProposedAction()
        elif mime.hasUrls() and any(_is_image_url(u) for u in mime.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        import json
        mime = event.mimeData()
        scene_pos = event.scenePos()
        if mime.hasFormat("application/x-solocanvas-cards"):
            raw = mime.data("application/x-solocanvas-cards").data()
            cards_list = json.loads(raw.decode("utf-8"))
            self.hand_cards_dropped.emit(cards_list, scene_pos)
            event.acceptProposedAction()
        elif mime.hasFormat("application/x-solocanvas-card"):
            raw = mime.data("application/x-solocanvas-card").data()
            card_dict = json.loads(raw.decode("utf-8"))
            self.hand_card_dropped.emit(card_dict, scene_pos)
            event.acceptProposedAction()
        elif mime.hasUrls():
            for url in mime.urls():
                if _is_image_url(url):
                    self.external_image_dropped.emit(url.toLocalFile(), scene_pos)
            event.acceptProposedAction()
        else:
            event.ignore()
