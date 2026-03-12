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

"""HandWidget – the persistent card-hand strip at the bottom of the window."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

import qtawesome as qta

from PyQt6.QtCore import QEvent, QMimeData, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QDrag, QFont, QMouseEvent, QPainter, QPen,
    QPixmap, QWheelEvent,
)
from PyQt6.QtWidgets import QMenu, QToolTip, QWidget


HAND_PADDING_V = 8
HAND_PADDING_H = 12
MAX_OVERLAP     = 0.40   # cards may overlap up to 40% before shrinking
_LIB_BTN_W      = 52     # width reserved on the left for the side buttons
_DICE_BTN_W     = 52     # width reserved on the right for the dice button
_BTN_SIZE       = 36     # side button square size in px
TAB_HEIGHT      = 22     # height of the collapse/restore tab strip


@dataclass
class HandCardState:
    card_data: object       # CardData
    face_up:   bool  = True
    rotation:  float = 0.0
    # Cached pixmaps (populated lazily)
    _front_pix: Optional[QPixmap] = field(default=None, repr=False)
    _back_pix:  Optional[QPixmap] = field(default=None, repr=False)

    def front_pixmap(self) -> Optional[QPixmap]:
        if self._front_pix is None and self.card_data.image_path:
            if Path(self.card_data.image_path).exists():
                self._front_pix = QPixmap(self.card_data.image_path)
        return self._front_pix

    def back_pixmap(self) -> Optional[QPixmap]:
        if self._back_pix is None and self.card_data.back_path:
            if Path(self.card_data.back_path).exists():
                self._back_pix = QPixmap(self.card_data.back_path)
        return self._back_pix

    def current_pixmap(self) -> Optional[QPixmap]:
        return self.front_pixmap() if self.face_up else self.back_pixmap()


class HandWidget(QWidget):
    """
    Horizontal strip showing cards in hand.
    Cards shrink to fit window width; supports multi-select, flip, rotate,
    drag-to-canvas, and right-click context menu.

    Rendered as a semi-transparent overlay over the canvas when
    WA_TranslucentBackground is set by the parent.
    """

    # Signals
    send_to_canvas           = pyqtSignal(object, object)  # CardData, QPointF (scene pos hint)
    return_to_deck           = pyqtSignal(object)           # CardData
    request_canvas_pos       = pyqtSignal()                 # ask MainWindow for a default drop pos
    library_button_clicked   = pyqtSignal()                 # user clicked the library icon
    recall_clicked           = pyqtSignal()                 # user clicked the recall button
    stack_to_canvas_requested = pyqtSignal(list)            # List[(CardData, face_up bool)]
    request_undo_snapshot     = pyqtSignal()                # ask MainWindow to push undo before action
    dice_library_clicked      = pyqtSignal()                # user clicked the dice button
    roll_log_clicked          = pyqtSignal()                # user clicked the roll log button
    notepad_clicked           = pyqtSignal()                # user clicked the notepad button
    image_library_clicked     = pyqtSignal()                # user clicked the image library button
    hand_card_hovered         = pyqtSignal(object)          # CardData — mouse entered a hand card
    hand_card_unhovered       = pyqtSignal()                # mouse left a hand card

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings   = settings
        self.hand_cards: List[HandCardState] = []
        self._selected:  Set[int]            = set()

        # Max card size from settings
        self._max_cw: int = settings.display("max_hand_card_width")
        # Maintain aspect ratio (poker)
        self._max_ch: int = int(self._max_cw * 168 / 120)
        self._collapsed: bool = False  # must be set before _update_height

        self.setMinimumHeight(60)
        self._update_height()

        # Mouse tracking for hover / drag
        self.setMouseTracking(True)
        self._drag_start_idx: Optional[int] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._hovered_idx: Optional[int] = None
        self._last_clicked_idx: Optional[int] = None  # anchor for Shift+click range
        self._pending_deselect: bool = False           # deselect multi on release (if no drag)

        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._drop_highlight: bool = False
        self._hovered_btn: Optional[str] = None  # 'lib', 'rcl', 'dice', 'log', or None

        # Reorder drag state
        self._reorder_mode: bool = False
        self._reorder_drag_idx: Optional[int] = None
        self._reorder_insert_pos: Optional[int] = None

        # Rubber-band selection state
        self._rubber_active: bool = False
        self._rubber_origin: Optional[QPointF] = None
        self._rubber_rect: Optional[QRect] = None

    def set_drop_highlight(self, active: bool) -> None:
        if active != self._drop_highlight:
            self._drop_highlight = active
            self.update()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        if self._collapsed:
            return QSize(0, TAB_HEIGHT)
        return QSize(0, TAB_HEIGHT + self._max_ch + 2 * HAND_PADDING_V)

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._update_height()
        self.update()

    def add_card(self, card_data, face_up: bool = True, rotation: float = 0.0) -> None:
        self.hand_cards.append(HandCardState(card_data, face_up, rotation))
        self._update_height()
        self.update()

    def remove_card_by_id(self, card_id: str) -> Optional[HandCardState]:
        for i, hs in enumerate(self.hand_cards):
            if hs.card_data.id == card_id:
                self._selected.discard(i)
                self._selected = {j if j < i else j - 1 for j in self._selected if j != i}
                return self.hand_cards.pop(i)
        return None

    def remove_card_by_image_path(self, path: str) -> Optional[HandCardState]:
        for i, hs in enumerate(self.hand_cards):
            if hs.card_data.image_path == path:
                self._selected.discard(i)
                self._selected = {j if j < i else j - 1 for j in self._selected if j != i}
                return self.hand_cards.pop(i)
        return None

    def clear(self) -> List[HandCardState]:
        removed = list(self.hand_cards)
        self.hand_cards.clear()
        self._selected.clear()
        self.update()
        return removed

    def set_max_card_width(self, w: int) -> None:
        self._max_cw = max(40, w)
        self._max_ch = int(self._max_cw * 168 / 120)
        self._update_height()
        self.update()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _lib_btn_rect(self) -> QRect:
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = _LIB_BTN_W // 2
        cy = TAB_HEIGHT + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _recall_btn_rect(self) -> QRect:
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = _LIB_BTN_W // 2
        cy = TAB_HEIGHT + third_h + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _img_lib_btn_rect(self) -> QRect:
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = _LIB_BTN_W // 2
        cy = TAB_HEIGHT + 2 * third_h + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _dice_btn_rect(self) -> QRect:
        """Dice button in the top third of the right column."""
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = self.width() - _DICE_BTN_W // 2
        cy = TAB_HEIGHT + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _log_btn_rect(self) -> QRect:
        """Roll Log button in the middle third of the right column."""
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = self.width() - _DICE_BTN_W // 2
        cy = TAB_HEIGHT + third_h + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _notepad_btn_rect(self) -> QRect:
        """Notepad button in the bottom third of the right column."""
        card_area_h = self.height() - TAB_HEIGHT
        third_h = card_area_h // 3
        cx = self.width() - _DICE_BTN_W // 2
        cy = TAB_HEIGHT + 2 * third_h + third_h // 2
        return QRect(cx - _BTN_SIZE // 2, cy - _BTN_SIZE // 2, _BTN_SIZE, _BTN_SIZE)

    def _card_rects(self) -> List[QRect]:
        n = len(self.hand_cards)
        if n == 0:
            return []

        ch = self._max_ch
        card_area_h = self.height() - TAB_HEIGHT
        cy = TAB_HEIGHT + (card_area_h - ch) // 2
        avail = self.width() - _LIB_BTN_W - _DICE_BTN_W - 2 * HAND_PADDING_H

        # Per-card natural width derived from each card's actual image aspect ratio
        nat_widths = []
        for hs in self.hand_cards:
            pix = hs.current_pixmap()
            if pix and not pix.isNull() and pix.height() > 0:
                w = int(ch * pix.width() / pix.height())
            else:
                w = self._max_cw
            nat_widths.append(w)

        # Total natural width with overlap
        if n > 1:
            total_nat = sum(w * (1 - MAX_OVERLAP) for w in nat_widths[:-1]) + nat_widths[-1]
        else:
            total_nat = nat_widths[0]

        # Scale all widths proportionally if they don't fit
        scale = min(1.0, avail / total_nat) if total_nat > 0 else 1.0
        widths = [max(1, int(w * scale)) for w in nat_widths]

        # Center cards in available area
        if n > 1:
            total_w = sum(w * (1 - MAX_OVERLAP) for w in widths[:-1]) + widths[-1]
        else:
            total_w = widths[0]
        x = _LIB_BTN_W + HAND_PADDING_H + max(0, int((avail - total_w) / 2))

        rects = []
        for i, w in enumerate(widths):
            rects.append(QRect(x, cy, w, ch))
            if i < n - 1:
                x += int(w * (1 - MAX_OVERLAP))
        return rects

    def _update_height(self) -> None:
        if self._collapsed:
            self.setFixedHeight(TAB_HEIGHT)
        else:
            self.setFixedHeight(TAB_HEIGHT + self._max_ch + 2 * HAND_PADDING_V)

    def _index_at(self, pos: QPointF) -> Optional[int]:
        """Return card index under pos, topmost (rightmost) first."""
        if self._collapsed:
            return None
        rects = self._card_rects()
        for i in range(len(rects) - 1, -1, -1):
            if rects[i].contains(pos.toPoint()):
                return i
        return None

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _panel_color(self) -> QColor:
        """Darker shade of the current canvas background color."""
        c = QColor(self._settings.canvas("background_color"))
        h, s, v, _ = c.getHsvF()
        result = QColor()
        result.setHsvF(h, min(1.0, s * 1.1), max(0.0, v * 0.45))
        return result

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = self._panel_color()
        painter.fillRect(self.rect(), bg)

        # Tab strip (always visible)
        tab_rect = QRect(0, 0, self.width(), TAB_HEIGHT)
        tab_bg = QColor(bg)
        tab_bg.setHsvF(tab_bg.hsvHueF(), tab_bg.hsvSaturationF(),
                       min(1.0, tab_bg.valueF() + 0.12))
        painter.fillRect(tab_rect, tab_bg)
        # Tab bottom divider
        divider = QColor(bg)
        divider.setHsvF(divider.hsvHueF(), divider.hsvSaturationF(),
                        min(1.0, divider.valueF() + 0.22))
        painter.setPen(QPen(divider, 1))
        painter.drawLine(0, TAB_HEIGHT, self.width(), TAB_HEIGHT)
        # Tab label
        arrow = "▲" if self._collapsed else "▼"
        count = len(self.hand_cards)
        tab_label = f"{arrow}  Hand  ({count})"
        txt_color = QColor(bg)
        txt_color.setHsvF(txt_color.hsvHueF(),
                          max(0.0, txt_color.hsvSaturationF() - 0.15),
                          min(1.0, txt_color.valueF() + 0.65))
        painter.setPen(txt_color)
        painter.setFont(QFont("Arial", 9))
        painter.drawText(tab_rect, Qt.AlignmentFlag.AlignCenter, tab_label)

        if self._collapsed:
            painter.end()
            return

        if self._drop_highlight:
            card_area = self.rect().adjusted(0, TAB_HEIGHT, 0, 0)
            painter.fillRect(card_area, QColor(80, 180, 255, 35))
            for thickness, alpha in ((8, 30), (5, 60), (3, 110), (2, 180), (1, 255)):
                painter.setPen(QPen(QColor(100, 200, 255, alpha), thickness))
                painter.drawLine(0, TAB_HEIGHT, self.width(), TAB_HEIGHT)
            painter.setPen(QColor(180, 230, 255, 220))
            painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            label_rect = self.rect().adjusted(_LIB_BTN_W, TAB_HEIGHT, 0, 0)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "↓  Drop to Hand")
        else:
            btn_bg  = QColor(bg); btn_bg.setHsvF(btn_bg.hsvHueF(), btn_bg.hsvSaturationF(), min(1.0, btn_bg.valueF() + 0.15))
            btn_pen = QColor(bg); btn_pen.setHsvF(btn_pen.hsvHueF(), btn_pen.hsvSaturationF(), min(1.0, btn_pen.valueF() + 0.45))
            btn_txt = QColor(bg); btn_txt.setHsvF(btn_txt.hsvHueF(), max(0.0, btn_txt.hsvSaturationF() - 0.2), min(1.0, btn_txt.valueF() + 0.6))
            btn_hov = QColor(bg); btn_hov.setHsvF(btn_hov.hsvHueF(), btn_hov.hsvSaturationF(), min(1.0, btn_hov.valueF() + 0.28))

            icon_color = btn_txt.name()
            icon_size  = QSize(_BTN_SIZE - 14, _BTN_SIZE - 14)

            lb = self._lib_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'lib' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(lb, 9, 9)
            lib_pix = qta.icon('fa5s.layer-group', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(lb.center().x() - icon_size.width() // 2,
                               lb.center().y() - icon_size.height() // 2, lib_pix)

            rb = self._recall_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'rcl' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(rb, 9, 9)
            rcl_pix = qta.icon('fa5s.undo-alt', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(rb.center().x() - icon_size.width() // 2,
                               rb.center().y() - icon_size.height() // 2, rcl_pix)

            ilb = self._img_lib_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'img_lib' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(ilb, 9, 9)
            img_lib_pix = qta.icon('fa5s.images', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(ilb.center().x() - icon_size.width() // 2,
                               ilb.center().y() - icon_size.height() // 2, img_lib_pix)

            db = self._dice_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'dice' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(db, 9, 9)
            dice_pix = qta.icon('fa5s.dice', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(db.center().x() - icon_size.width() // 2,
                               db.center().y() - icon_size.height() // 2, dice_pix)

            lgb = self._log_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'log' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(lgb, 9, 9)
            log_pix = qta.icon('fa5s.scroll', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(lgb.center().x() - icon_size.width() // 2,
                               lgb.center().y() - icon_size.height() // 2, log_pix)

            npb = self._notepad_btn_rect()
            painter.setBrush(QBrush(btn_hov if self._hovered_btn == 'notepad' else btn_bg))
            painter.setPen(QPen(btn_pen, 1))
            painter.drawRoundedRect(npb, 9, 9)
            notepad_pix = qta.icon('fa5s.book-open', color=icon_color).pixmap(icon_size)
            painter.drawPixmap(npb.center().x() - icon_size.width() // 2,
                               npb.center().y() - icon_size.height() // 2, notepad_pix)

            rects = self._card_rects()
            n = len(rects)

            # Compute ghost rect for reorder preview (drawn inside the card loop
            # so the card at ins renders on top of the ghost)
            ghost_rect = None
            ghost_ins  = None
            if (self._reorder_mode and self._reorder_insert_pos is not None
                    and self._reorder_drag_idx is not None
                    and 0 <= self._reorder_drag_idx < n):
                drag_rect = rects[self._reorder_drag_idx]
                gw, gh = drag_rect.width(), drag_rect.height()
                ins = self._reorder_insert_pos
                if ins == 0:
                    gcx = rects[0].left() - gw // 2
                elif ins >= n:
                    gcx = rects[-1].right() + gw // 2
                else:
                    gcx = (rects[ins - 1].right() + rects[ins].left()) // 2
                ghost_rect = QRect(gcx - gw // 2, drag_rect.top(), gw, gh)
                ghost_ins  = ins

            for i, (hs, rect) in enumerate(zip(self.hand_cards, rects)):
                # Draw ghost just before card[ins] so that card overlaps the ghost
                if ghost_rect is not None and i == ghost_ins:
                    painter.save()
                    painter.setOpacity(0.55)
                    painter.setBrush(QBrush(QColor(70, 130, 255)))
                    painter.setPen(QPen(QColor(140, 190, 255), 2))
                    painter.drawRoundedRect(ghost_rect, 5, 5)
                    painter.restore()
                    ghost_rect = None  # mark drawn
                self._draw_card(painter, hs, rect, i in self._selected, i == self._hovered_idx)

            # ins == n: ghost goes after all cards, nothing overlaps it
            if ghost_rect is not None:
                painter.save()
                painter.setOpacity(0.55)
                painter.setBrush(QBrush(QColor(70, 130, 255)))
                painter.setPen(QPen(QColor(140, 190, 255), 2))
                painter.drawRoundedRect(ghost_rect, 5, 5)
                painter.restore()

        # Rubber-band selection rect
        if self._rubber_rect and not self._rubber_rect.isNull():
            painter.setPen(QPen(QColor(100, 180, 255, 220), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(100, 180, 255, 35)))
            painter.drawRect(self._rubber_rect)

        painter.end()

    def _draw_card(
        self, painter: QPainter, hs: HandCardState,
        rect: QRect, selected: bool, hovered: bool
    ) -> None:
        cx = rect.center().x()
        cy = rect.center().y()

        painter.save()
        painter.translate(cx, cy)
        if hs.rotation:
            painter.rotate(hs.rotation)
        painter.translate(-rect.width() // 2, -rect.height() // 2)

        draw_rect = QRect(0, 0, rect.width(), rect.height())
        pix = hs.current_pixmap()
        if pix and not pix.isNull():
            painter.drawPixmap(draw_rect, pix)
        else:
            color = QColor(45, 85, 200) if hs.face_up else QColor(160, 35, 35)
            painter.fillRect(draw_rect, color)
            painter.setPen(QColor(255, 255, 255, 180))
            painter.setFont(QFont("Arial", 7))
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter,
                             hs.card_data.name[:20])

        # Border
        r = 5
        if selected:
            pen = QPen(QColor(255, 215, 0), 2)
        elif hovered:
            pen = QPen(QColor(150, 200, 255), 1)
        else:
            pen = QPen(QColor(0, 0, 0, 80), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(draw_rect, r, r)

        painter.restore()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Tab strip click — toggle collapse
        if event.button() == Qt.MouseButton.LeftButton:
            if event.pos().y() < TAB_HEIGHT:
                self.toggle_collapse()
                return
        if self._collapsed:
            return

        # Side buttons
        if event.button() == Qt.MouseButton.LeftButton:
            if self._lib_btn_rect().contains(event.pos()):
                self.library_button_clicked.emit()
                return
            if self._recall_btn_rect().contains(event.pos()):
                self.recall_clicked.emit()
                return
            if self._img_lib_btn_rect().contains(event.pos()):
                self.image_library_clicked.emit()
                return
            if self._dice_btn_rect().contains(event.pos()):
                self.dice_library_clicked.emit()
                return
            if self._log_btn_rect().contains(event.pos()):
                self.roll_log_clicked.emit()
                return
            if self._notepad_btn_rect().contains(event.pos()):
                self.notepad_clicked.emit()
                return

        idx = self._index_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            if idx is not None:
                mods = event.modifiers()
                if mods & Qt.KeyboardModifier.ShiftModifier and self._last_clicked_idx is not None:
                    # Range select from anchor to current
                    lo = min(self._last_clicked_idx, idx)
                    hi = max(self._last_clicked_idx, idx)
                    self._selected.update(range(lo, hi + 1))
                elif mods & Qt.KeyboardModifier.ControlModifier:
                    if idx in self._selected:
                        self._selected.discard(idx)
                    else:
                        self._selected.add(idx)
                    self._last_clicked_idx = idx
                else:
                    if idx in self._selected and len(self._selected) > 1:
                        # Clicked inside existing multi-selection — defer deselect
                        # until release so drag can carry all selected cards
                        self._pending_deselect = True
                    else:
                        self._selected = {idx}
                        self._pending_deselect = False
                    self._last_clicked_idx = idx
                self._drag_start_idx = idx
                self._drag_start_pos = event.position()
            else:
                self._selected.clear()
                self._last_clicked_idx = None
                self._drag_start_idx = None
                # Start rubber-band selection on empty area
                self._rubber_active = True
                self._rubber_origin = event.position()
                self._rubber_rect = None
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            if idx is not None and idx not in self._selected:
                self._selected = {idx}
                self.update()
            self._show_context_menu(idx, event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._collapsed:
            return
        # Track button hover for highlight
        pos = event.pos()
        if self._lib_btn_rect().contains(pos):
            new_hov = 'lib'
        elif self._recall_btn_rect().contains(pos):
            new_hov = 'rcl'
        elif self._img_lib_btn_rect().contains(pos):
            new_hov = 'img_lib'
        elif self._dice_btn_rect().contains(pos):
            new_hov = 'dice'
        elif self._log_btn_rect().contains(pos):
            new_hov = 'log'
        elif self._notepad_btn_rect().contains(pos):
            new_hov = 'notepad'
        else:
            new_hov = None
        if new_hov != self._hovered_btn:
            self._hovered_btn = new_hov
        # Update card hover and emit signals on change
        old_idx = self._hovered_idx
        self._hovered_idx = self._index_at(event.position())
        if self._hovered_idx != old_idx:
            if self._hovered_idx is not None and self._hovered_idx < len(self.hand_cards):
                self.hand_card_hovered.emit(self.hand_cards[self._hovered_idx].card_data)
            else:
                self.hand_card_unhovered.emit()
        self.update()

        # Rubber-band selection
        if self._rubber_active and self._rubber_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            o = self._rubber_origin.toPoint()
            p = event.pos()
            self._rubber_rect = QRect(o, p).normalized()
            rects = self._card_rects()
            self._selected.clear()
            for i, r in enumerate(rects):
                if r.intersects(self._rubber_rect):
                    self._selected.add(i)
            self.update()
            return

        # Reorder mode — track insert position or bail out to canvas drag
        if self._reorder_mode and event.buttons() & Qt.MouseButton.LeftButton:
            if event.position().y() < 0:
                # Mouse left top of hand — switch to canvas drag
                self._reorder_mode = False
                self._reorder_insert_pos = None
                idx = self._reorder_drag_idx
                self._reorder_drag_idx = None
                self._drag_start_idx = None
                self._drag_start_pos = None
                if idx is not None:
                    self._start_drag(idx)
            else:
                self._update_reorder_insert_pos(event.position().x())
            return

        # Drag initiation
        if (self._drag_start_idx is not None
                and self._drag_start_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            dist = (event.position() - self._drag_start_pos).manhattanLength()
            if dist > 8:
                self._pending_deselect = False
                if event.position().y() >= TAB_HEIGHT:
                    # Still within hand — enter reorder mode
                    self._reorder_mode = True
                    self._reorder_drag_idx = self._drag_start_idx
                    self._drag_start_idx = None
                    self._drag_start_pos = None
                    self._update_reorder_insert_pos(event.position().x())
                else:
                    # Dragged above hand — canvas drag
                    self._start_drag(self._drag_start_idx)
                    self._drag_start_idx = None
                    self._drag_start_pos = None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._reorder_mode:
                self._do_reorder()
                self._reorder_mode = False
                self._reorder_drag_idx = None
                self._reorder_insert_pos = None
            elif self._rubber_active:
                self._rubber_active = False
                self._rubber_rect = None
                self._rubber_origin = None
            elif self._pending_deselect and self._drag_start_idx is not None:
                self._selected = {self._drag_start_idx}
                self._last_clicked_idx = self._drag_start_idx
                self._pending_deselect = False
        self._drag_start_idx = None
        self._drag_start_pos = None
        self.update()

    def leaveEvent(self, event) -> None:
        had_hover = self._hovered_idx is not None
        self._hovered_idx = None
        self._hovered_btn = None
        if had_hover:
            self.hand_card_unhovered.emit()
        # Cancel rubber band on leave; reorder handled by mouseMoveEvent (y < 0 check)
        if self._rubber_active:
            self._rubber_active = False
            self._rubber_rect = None
            self._rubber_origin = None
        self.update()

    def clear_selection(self) -> None:
        """Deselect all hand cards (called when user clicks on canvas)."""
        if self._selected:
            self._selected.clear()
            self._last_clicked_idx = None
            self.update()

    # ------------------------------------------------------------------
    # Tooltip for side buttons
    # ------------------------------------------------------------------

    def event(self, ev) -> bool:
        if ev.type() == QEvent.Type.ToolTip and not self._collapsed:
            pos = ev.pos()
            if self._lib_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Deck Library", self)
            elif self._recall_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Recall Cards", self)
            elif self._img_lib_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Image Library", self)
            elif self._dice_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Dice Library", self)
            elif self._log_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Roll Log", self)
            elif self._notepad_btn_rect().contains(pos):
                QToolTip.showText(ev.globalPos(), "Notepad", self)
            else:
                QToolTip.hideText()
            return True
        return super().event(ev)

    # ------------------------------------------------------------------
    # Keyboard (flip / rotate selected)
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        if self._collapsed:
            super().keyPressEvent(event)
            return
        key_str = _hk(event)
        settings = self._settings
        if key_str == settings.hotkey("flip"):
            self._flip_selected()
        elif key_str == settings.hotkey("rotate_cw"):
            self._rotate_selected(settings.display("rotation_step"))
        elif key_str == settings.hotkey("rotate_ccw"):
            self._rotate_selected(-settings.display("rotation_step"))
        elif key_str == settings.hotkey("delete_selected"):
            self._remove_selected()
        elif key_str == "Ctrl+G" and len(self._selected) >= 2:
            self._stack_selected_emit()
        else:
            super().keyPressEvent(event)

    def _stack_selected_emit(self) -> None:
        """Remove selected hand cards and emit them for canvas stacking."""
        indices = sorted(self._selected)
        cards = [
            (self.hand_cards[i].card_data, self.hand_cards[i].face_up)
            for i in indices if 0 <= i < len(self.hand_cards)
        ]
        if len(cards) < 2:
            return
        self.request_undo_snapshot.emit()  # snapshot before hand state changes
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.hand_cards):
                self.hand_cards.pop(i)
        self._selected.clear()
        self._last_clicked_idx = None
        self.update()
        self.stack_to_canvas_requested.emit(cards)

    def _flip_selected(self) -> None:
        for i in self._selected:
            if 0 <= i < len(self.hand_cards):
                self.hand_cards[i].face_up = not self.hand_cards[i].face_up
        self.update()

    def _rotate_selected(self, degrees: float) -> None:
        for i in self._selected:
            if 0 <= i < len(self.hand_cards):
                self.hand_cards[i].rotation = (
                    self.hand_cards[i].rotation + degrees
                ) % 360
        self.update()

    def _remove_selected(self) -> None:
        indices = sorted(self._selected, reverse=True)
        for i in indices:
            if 0 <= i < len(self.hand_cards):
                hs = self.hand_cards.pop(i)
                self.return_to_deck.emit(hs.card_data)
        self._selected.clear()
        self.update()

    # ------------------------------------------------------------------
    # Reorder helpers
    # ------------------------------------------------------------------

    def _update_reorder_insert_pos(self, x: float) -> None:
        rects = self._card_rects()
        n = len(rects)
        insert = n
        for i, r in enumerate(rects):
            if x < r.center().x():
                insert = i
                break
        self._reorder_insert_pos = insert
        self.update()

    def _do_reorder(self) -> None:
        insert = self._reorder_insert_pos
        drag_idx = self._reorder_drag_idx
        if insert is None or drag_idx is None or drag_idx >= len(self.hand_cards):
            return
        is_multi = len(self._selected) > 1 and drag_idx in self._selected
        moving_indices = sorted(self._selected) if is_multi else [drag_idx]
        moving_cards = [self.hand_cards[i] for i in moving_indices if 0 <= i < len(self.hand_cards)]
        moving_set = set(moving_indices)
        remaining = [c for i, c in enumerate(self.hand_cards) if i not in moving_set]
        # Adjust insert: subtract how many moving cards were before the insert point
        adj_insert = max(0, min(insert - sum(1 for i in moving_indices if i < insert), len(remaining)))
        self.hand_cards = remaining[:adj_insert] + moving_cards + remaining[adj_insert:]
        self._selected = set(range(adj_insert, adj_insert + len(moving_cards)))
        self._last_clicked_idx = adj_insert
        self.update()

    # ------------------------------------------------------------------
    # Drag from hand to canvas
    # ------------------------------------------------------------------

    def _start_drag(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.hand_cards):
            return
        hs = self.hand_cards[idx]

        # Multi-select drag: pack all selected cards
        is_multi = len(self._selected) > 1 and idx in self._selected
        mime = QMimeData()

        if is_multi:
            selected_states = [
                self.hand_cards[i] for i in sorted(self._selected)
                if 0 <= i < len(self.hand_cards)
            ]
            cards_list = [
                {
                    "image_path": h.card_data.image_path,
                    "deck_id":    h.card_data.deck_id,
                    "face_up":    h.face_up,
                    "rotation":   h.rotation,
                }
                for h in selected_states
            ]
            mime.setData(
                "application/x-solocanvas-cards",
                json.dumps(cards_list).encode("utf-8"),
            )
        else:
            card_dict = {
                "image_path": hs.card_data.image_path,
                "deck_id":    hs.card_data.deck_id,
                "face_up":    hs.face_up,
                "rotation":   hs.rotation,
            }
            mime.setData(
                "application/x-solocanvas-card",
                json.dumps(card_dict).encode("utf-8"),
            )

        # Thumbnail for drag
        pix = hs.current_pixmap()
        drag = QDrag(self)
        drag.setMimeData(mime)
        if pix and not pix.isNull():
            thumb = pix.scaled(60, 84, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            drag.setPixmap(thumb)
            drag.setHotSpot(thumb.rect().center())

        result = drag.exec(Qt.DropAction.MoveAction)
        if result == Qt.DropAction.MoveAction:
            if is_multi:
                for i in sorted(self._selected, reverse=True):
                    if 0 <= i < len(self.hand_cards):
                        self.hand_cards.pop(i)
                self._selected.clear()
                self._last_clicked_idx = None
            else:
                self.remove_card_by_image_path(hs.card_data.image_path)
            self.update()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, idx: Optional[int], global_pos) -> None:
        menu = QMenu()

        n_sel = len(self._selected)

        if idx is not None and 0 <= idx < len(self.hand_cards):
            menu.addAction("Flip",     lambda: self._flip_one(idx))
            menu.addAction("Rotate CW",  lambda: self._rotate_one(idx, 45))
            menu.addAction("Rotate CCW", lambda: self._rotate_one(idx, -45))
            menu.addSeparator()
            menu.addAction("Send to Canvas",  lambda: self._send_to_canvas(idx))
            menu.addAction("Return to Deck",  lambda: self._return_one_to_deck(idx))

            if n_sel > 1:
                menu.addSeparator()
                lbl = f"{n_sel} Selected Cards"
                menu.addAction(f"Flip {lbl}",              self._flip_selected)
                menu.addAction(f"Send {lbl} to Canvas",    self._send_selected_to_canvas)
                menu.addAction(f"Return {lbl} to Deck",    self._return_selected_to_deck)

        menu.exec(global_pos)

    def _flip_one(self, idx: int) -> None:
        self.hand_cards[idx].face_up = not self.hand_cards[idx].face_up
        self.update()

    def _rotate_one(self, idx: int, deg: float) -> None:
        self.hand_cards[idx].rotation = (self.hand_cards[idx].rotation + deg) % 360
        self.update()

    def _send_to_canvas(self, idx: int) -> None:
        hs = self.hand_cards.pop(idx)
        self._selected.discard(idx)
        self._selected = {j if j < idx else j - 1 for j in self._selected if j != idx}
        self.send_to_canvas.emit(hs.card_data, QPointF(0, 0))
        self.update()

    def _return_one_to_deck(self, idx: int) -> None:
        if 0 <= idx < len(self.hand_cards):
            hs = self.hand_cards.pop(idx)
            self._selected.discard(idx)
            self.return_to_deck.emit(hs.card_data)
            self.update()

    def _send_selected_to_canvas(self) -> None:
        for i in sorted(self._selected, reverse=True):
            if 0 <= i < len(self.hand_cards):
                hs = self.hand_cards.pop(i)
                self.send_to_canvas.emit(hs.card_data, QPointF(0, 0))
        self._selected.clear()
        self._last_clicked_idx = None
        self.update()

    def _return_selected_to_deck(self) -> None:
        for i in sorted(self._selected, reverse=True):
            if 0 <= i < len(self.hand_cards):
                hs = self.hand_cards.pop(i)
                self.return_to_deck.emit(hs.card_data)
        self._selected.clear()
        self._last_clicked_idx = None
        self.update()

    # ------------------------------------------------------------------
    # Drop from canvas to hand
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-solocanvas-card"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat("application/x-solocanvas-card"):
            event.ignore()
            return
        # The MainWindow handles actual card movement on canvas→hand drags
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _hk(event) -> str:
    from .canvas_view import _key_event_to_str
    return _key_event_to_str(event)
