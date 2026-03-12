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

"""MainWindow – orchestrates the entire SoloCanvas application."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QCloseEvent, QColor, QFont, QIcon,
    QKeySequence, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QInputDialog, QLabel,
    QMainWindow, QMenu, QMessageBox,
    QStatusBar, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QShortcut

from .canvas_scene   import CanvasScene
from .canvas_view    import CanvasView
from .card_item      import CARD_H, CardItem
from .deck_item      import DeckItem
from .dialogs        import (
    BackgroundDialog, CardPickerDialog, DeckLibraryDialog,
    DiceLibraryDialog, HotkeyReferenceDialog, ImageLibraryDialog,
    ImageResizeDialog, ImageSizeDialog, MissingImageDialog, RecallDialog,
    RollLogDialog, SessionPickerDialog, SettingsDialog, StartupDialog,
)
from .image_item     import ImageItem
from .die_item       import DieItem
from .dice_manager   import DiceSetsManager
from .hand_widget    import HandWidget
from .models         import CardData, DeckModel
from .session_manager  import SessionManager
from .settings_manager import SettingsManager
from .notepad_dialog   import NotepadDialog
from . import theme as _theme

_WINDOW_STYLE = """
QMainWindow, QWidget#central {
    background-color: #11111b;
}

/* ── Menu bar ── */
QMenuBar {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
    font-size: 13px;
    padding: 2px 0;
}
QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: #313244; }

/* ── Drop-down menus ── */
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    font-size: 13px;
    padding: 4px 0;
}
QMenu::item { padding: 5px 24px 5px 12px; border-radius: 4px; }
QMenu::item:selected { background: #313244; }
QMenu::item:disabled { color: #585b70; }
QMenu::separator { height: 1px; background: #45475a; margin: 3px 8px; }
QMenu::indicator { width: 14px; height: 14px; }

/* ── Status bar ── */
QStatusBar {
    background-color: #1e1e2e;
    color: #a6adc8;
    font-size: 11px;
    border-top: 1px solid #313244;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #11111b;
    width: 8px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #585b70;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #6c7086; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: #11111b;
    height: 8px;
    border: none;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #585b70;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #6c7086; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; border: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* ── Tooltip ── */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px 8px;
    font-size: 12px;
}

/* ── Generic push buttons (fallback) ── */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 14px;
    font-size: 13px;
}
QPushButton:hover  { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { color: #585b70; border-color: #313244; }
"""


class MagnifyOverlay(QWidget):
    """Floating corner widget showing a zoomed card image."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._pixmap: Optional[QPixmap] = None
        self.set_size(220)
        self.hide()

    def set_size(self, width_px: int) -> None:
        """Set the preview width; height adjusts to the card's actual aspect ratio."""
        self._display_width = width_px
        self._resize_to_pixmap()

    def _resize_to_pixmap(self) -> None:
        w = getattr(self, '_display_width', 220)
        pix = self._pixmap
        if pix and not pix.isNull() and pix.width() > 0:
            h = int(w * pix.height() / pix.width())
        else:
            h = int(w * 168 / 120)
        self.setFixedSize(w, h)

    def set_card(self, pix: Optional[QPixmap]) -> None:
        self._pixmap = pix
        self._resize_to_pixmap()
        if pix:
            self.show()
        else:
            self.hide()
        self.update()

    def reposition(self, parent_size, corner: str = "bottom_right") -> None:
        m = 10
        w, h = self.width(), self.height()
        pw, ph = parent_size.width(), parent_size.height()
        if corner == "bottom_right":
            self.move(pw - w - m, ph - h - m)
        elif corner == "bottom_left":
            self.move(m, ph - h - m)
        elif corner == "top_right":
            self.move(pw - w - m, m)
        else:
            self.move(m, m)

    def paintEvent(self, event) -> None:
        if not self._pixmap:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Background panel
        painter.setBrush(QColor(15, 15, 25, 210))
        painter.setPen(QPen(QColor(100, 100, 150), 1))
        painter.drawRoundedRect(self.rect(), 8, 8)
        # Card image
        padding = 8
        card_rect = self.rect().adjusted(padding, padding, -padding, -padding)
        painter.drawPixmap(card_rect, self._pixmap)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()
        self._session  = SessionManager(self._settings)

        # State
        self._deck_models: Dict[str, DeckModel] = {}   # deck_id → DeckModel
        self._deck_items:  Dict[str, DeckItem]  = {}   # deck_id → DeckItem
        self._canvas_cards: Dict[str, CardItem] = {}   # card img_path → CardItem
        self._active_deck_id: Optional[str]     = None
        self._session_path: Optional[Path]      = None
        self._magnify_key_held = False

        # Dice
        self._dice_manager = DiceSetsManager()
        self._die_items: List[DieItem] = []
        self._roll_log: List[dict] = []
        self._dice_cascade_col: int = 0
        self._dice_cascade_row: int = 0

        # Image items
        self._image_items: List[ImageItem] = []

        # Clipboard for copy/paste (list of {"type": str, "state": dict})
        self._clipboard: list = []

        # Non-modal dialog tracking (prevents GC, allows raise-on-reopen)
        self._active_dialogs: set = set()
        self._dice_library_dlg = None
        self._roll_log_dlg = None
        self._image_library_dlg = None
        self._notepad_dlg: Optional[NotepadDialog] = None

        # Undo / redo (snapshot-based, max 10 levels)
        self._undo_stack: list = []
        self._redo_stack: list = []

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._restore_window_state()
        self.setWindowTitle("SoloCanvas")
        self._apply_theme()
        QTimer.singleShot(0, self._show_startup_dialog)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Theme applied after full init via _apply_theme()
        self.setMinimumSize(800, 600)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        # Layout: canvas view fills available space, hand strip is below it
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scene = CanvasScene(self._settings)
        self._view  = CanvasView(self._scene, self._settings)
        layout.addWidget(self._view, 1)

        self._hand = HandWidget(self._settings)
        layout.addWidget(self._hand, 0)

        # Magnify overlay – child of central, raised above everything
        self._magnify = MagnifyOverlay(central)
        self._magnify.set_size(self._settings.display("magnify_size"))
        self._magnify.raise_()

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._hotkey_hint_label = QLabel("Press K for hotkey reference")
        self._hotkey_hint_label.setStyleSheet("color: #585b70; margin-left: 6px;")
        self._status.addWidget(self._hotkey_hint_label)
        self._zoom_label = QLabel("100 %")
        self._zoom_label.setStyleSheet("color: #a6adc8; margin-right: 8px;")
        self._status.addPermanentWidget(self._zoom_label)

        # Connect signals
        self._scene.hand_card_dropped.connect(self._on_hand_card_dropped)
        self._scene.hand_cards_dropped.connect(self._on_hand_cards_dropped)
        self._scene.external_image_dropped.connect(self._on_external_image_dropped)
        self._view.zoom_changed.connect(self._on_zoom_changed)
        self._view.key_action.connect(self._dispatch_key)
        self._view.rotate_held_item.connect(self._rotate_held)
        self._view.items_dropped_on_hand.connect(self._on_canvas_items_dropped_on_hand)
        self._view.items_merged_into_deck.connect(self._on_items_merged_into_deck)
        self._view.drag_near_hand.connect(self._hand.set_drop_highlight)

        self._hand.send_to_canvas.connect(self._on_hand_send_to_canvas)
        self._hand.return_to_deck.connect(self._on_hand_return_to_deck)
        self._hand.library_button_clicked.connect(self._open_deck_library)
        self._hand.recall_clicked.connect(self._recall_dialog)
        self._hand.stack_to_canvas_requested.connect(self._on_hand_stack_to_canvas)
        self._hand.request_undo_snapshot.connect(self._push_undo)
        self._hand.dice_library_clicked.connect(self._open_dice_library)
        self._hand.roll_log_clicked.connect(self._open_roll_log)
        self._hand.image_library_clicked.connect(self._open_image_library)
        self._hand.notepad_clicked.connect(self._open_notepad)
        self._hand.hand_card_hovered.connect(self._on_card_hovered)
        self._hand.hand_card_unhovered.connect(self._on_card_unhovered)
        self._view.canvas_pressed.connect(self._hand.clear_selection)

        # Auto-magnify on mouse move in canvas
        self._view.viewport().setMouseTracking(True)
        self._view.viewport().installEventFilter(self)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menu(self) -> None:
        mb = self.menuBar()

        def act(menu, label, slot, shortcut=None):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            menu.addAction(a)
            return a

        # File
        file_menu = mb.addMenu("&File")
        act(file_menu, "New Session",       self._new_session,    "Ctrl+N")
        act(file_menu, "Open Session…",     self._open_session,   "Ctrl+O")
        act(file_menu, "Save Session",      self._save_session,   "Ctrl+S")
        act(file_menu, "Save Session As…",  self._save_session_as)
        file_menu.addSeparator()
        act(file_menu, "Import Deck…",      self._import_deck)
        file_menu.addSeparator()
        act(file_menu, "Import Image…",     self._import_image)
        self._localize_action = act(file_menu, "Localize Images", self._localize_images)
        file_menu.addSeparator()
        act(file_menu, "Settings…",         self._open_settings,  "Ctrl+,")
        file_menu.addSeparator()
        act(file_menu, "Quit",              self.close,           "Ctrl+Q")

        # Canvas
        canvas_menu = mb.addMenu("&Canvas")
        act(canvas_menu, "Reset Zoom",             self._view.reset_zoom,      "Ctrl+0")
        act(canvas_menu, "Center View",            self._view.center_on_origin)
        canvas_menu.addSeparator()
        act(canvas_menu, "Toggle Grid",            self._toggle_grid)
        act(canvas_menu, "Recall Cards…",          self._recall_dialog,        "Ctrl+R")
        canvas_menu.addSeparator()
        act(canvas_menu, "Customize Background…",  self._open_bg_dialog)

        # Edit
        edit_menu = mb.addMenu("&Edit")
        self._undo_action = act(edit_menu, "Undo",  self._undo, "Ctrl+Z")
        self._redo_action = act(edit_menu, "Redo",  self._redo, "Ctrl+Shift+Z")
        self._undo_action.setEnabled(False)
        self._redo_action.setEnabled(False)
        edit_menu.addSeparator()
        act(edit_menu, "Select All",       self._select_all,      "Ctrl+A")
        act(edit_menu, "Delete Selected",  self._delete_selected, "Delete")

        # Tools
        tools_menu = mb.addMenu("&Tools")
        act(tools_menu, "Notepad",       self._open_notepad,       "Ctrl+P")
        act(tools_menu, "Deck Library…", self._open_deck_library,  "Ctrl+L")
        act(tools_menu, "Image Library…",self._open_image_library)
        act(tools_menu, "Dice Bag…",     self._open_dice_library)

        # Help
        help_menu = mb.addMenu("&Help")
        act(help_menu, "Hotkey Reference…  (K)", self._open_hotkey_reference)
        help_menu.addSeparator()
        act(help_menu, "About SoloCanvas", self._about)

    def _setup_shortcuts(self) -> None:
        pass  # Key dispatch handled via canvas_view.key_action signal

    # ------------------------------------------------------------------
    # Key dispatch (from canvas_view)
    # ------------------------------------------------------------------

    def _dispatch_key(self, key_str: str) -> None:
        s = self._settings
        selected_cards = [
            i for i in self._scene.selectedItems()
            if isinstance(i, (CardItem, DeckItem, ImageItem))
        ]

        if key_str == s.hotkey("flip"):
            if selected_cards:
                self._push_undo()
            for item in selected_cards:
                if isinstance(item, CardItem):
                    item.flip()
                elif isinstance(item, DeckItem):
                    item.flip()

        elif key_str == s.hotkey("rotate_cw"):
            if selected_cards:
                self._push_undo()
            step = s.display("rotation_step")
            for item in selected_cards:
                if isinstance(item, (CardItem, ImageItem)):
                    item.rotate_cw(step)
                elif isinstance(item, DeckItem):
                    item.setRotation((item.rotation() + step) % 360)
        elif key_str == s.hotkey("rotate_ccw"):
            if selected_cards:
                self._push_undo()
            step = s.display("rotation_step")
            for item in selected_cards:
                if isinstance(item, (CardItem, ImageItem)):
                    item.rotate_ccw(step)
                elif isinstance(item, DeckItem):
                    item.setRotation((item.rotation() - step) % 360)

        elif key_str == s.hotkey("shuffle"):
            selected_decks = [i for i in self._scene.selectedItems() if isinstance(i, DeckItem)]
            selected_dice  = [i for i in self._scene.selectedItems() if isinstance(i, DieItem)]
            if selected_decks:
                self._push_undo()
                for deck in selected_decks:
                    deck.shuffle()
            elif not selected_dice:
                # Only check hovered deck when no dice/decks selected
                from PyQt6.QtGui import QCursor
                vp_pos = self._view.mapFromGlobal(QCursor.pos())
                scene_pos = self._view.mapToScene(vp_pos)
                hovered_deck = next(
                    (it for it in self._scene.items(scene_pos) if isinstance(it, DeckItem)),
                    None,
                )
                if hovered_deck:
                    self._push_undo()
                    hovered_deck.shuffle()
            # Roll selected dice (simultaneously with or without selected decks)
            if len(selected_dice) > 1:
                # Group roll — suppress individual signals and log as one entry
                for die in selected_dice:
                    die._log_individual = False
                    die.roll()
                self._append_roll_log(selected_dice)
            else:
                for die in selected_dice:
                    die.roll()

        elif key_str in [s.hotkey(f"draw_{n}") for n in range(1, 10)]:
            # Only draw when the cursor is hovering over a deck or stack
            from PyQt6.QtGui import QCursor
            vp_pos = self._view.mapFromGlobal(QCursor.pos())
            scene_pos = self._view.mapToScene(vp_pos)
            hovered_deck = next(
                (it for it in self._scene.items(scene_pos) if isinstance(it, DeckItem)),
                None,
            )
            if hovered_deck:
                for n in range(1, 10):
                    if key_str == s.hotkey(f"draw_{n}"):
                        hovered_deck.draw_cards_to_hand(n)  # before_draw signal pushes undo
                        break

        elif key_str == s.hotkey("send_to_back"):
            # Send hovered or selected items to the bottom of the Z stack
            from PyQt6.QtGui import QCursor
            targets = [i for i in self._scene.selectedItems()
                       if isinstance(i, (CardItem, ImageItem))
                       and not getattr(i, 'is_anchor', False)]
            if not targets:
                vp_pos = self._view.mapFromGlobal(QCursor.pos())
                scene_pos = self._view.mapToScene(vp_pos)
                for it in self._scene.items(scene_pos):
                    if isinstance(it, (CardItem, ImageItem)) and not getattr(it, 'is_anchor', False):
                        targets = [it]
                        break
            if targets:
                self._push_undo()
            for item in targets:
                others_z = [it.zValue() for it in self._scene.items()
                            if isinstance(it, (CardItem, DeckItem, ImageItem, DieItem))
                            and not getattr(it, 'is_anchor', False)
                            and it is not item]
                item._base_z = (min(others_z) - 1) if others_z else 0
                item.setZValue(item._base_z)

        elif key_str == s.hotkey("stack_selected"):
            self._push_undo()
            self._on_stack_requested()

        elif key_str == s.hotkey("spread_deck"):
            spread_targets = [i for i in self._scene.selectedItems() if isinstance(i, DeckItem)]
            if spread_targets:
                self._push_undo()
                for deck in spread_targets:
                    deck._spread_horizontal_action()

        elif key_str == s.hotkey("recall"):
            self._recall_dialog()

        elif key_str == s.hotkey("magnify"):
            self._magnify_key_held = not self._magnify_key_held
            if not self._magnify_key_held:
                self._magnify.set_card(None)

        elif key_str == s.hotkey("zoom_in"):
            self._view.zoom_in()
        elif key_str == s.hotkey("zoom_out"):
            self._view.zoom_out()
        elif key_str == s.hotkey("zoom_reset"):
            self._view.reset_zoom()

        elif key_str == s.hotkey("grid_toggle"):
            self._toggle_grid()

        elif key_str == s.hotkey("hotkey_reference"):
            self._open_hotkey_reference()

        elif key_str == s.hotkey("hand_toggle"):
            self._hand.toggle_collapse()

        elif key_str == s.hotkey("lock_toggle"):
            lockable = [i for i in selected_cards if hasattr(i, "_toggle_lock")]
            if lockable:
                # Lock all if any are unlocked; unlock all only when all are locked
                target_locked = any(not getattr(i, "locked", False) for i in lockable)
                for item in lockable:
                    if item.locked != target_locked:
                        item._toggle_lock()

        elif key_str == s.hotkey("copy"):
            self._copy_selected()

        elif key_str == s.hotkey("paste"):
            self._paste_clipboard()

        elif key_str == s.hotkey("delete_selected"):
            self._delete_selected()

        elif key_str == s.hotkey("select_all"):
            self._select_all()

        elif key_str == s.hotkey("open_notepad"):
            self._open_notepad()
        elif key_str == s.hotkey("open_deck_library"):
            self._open_deck_library()
        elif key_str == s.hotkey("open_image_library"):
            self._open_image_library()
        elif key_str == s.hotkey("open_dice_bag"):
            self._open_dice_library()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def _rotate_held(self, direction: int) -> None:
        if self._view._held_item:
            item = self._view._held_item
            step = self._settings.display("rotation_step")
            if isinstance(item, (CardItem, ImageItem)):
                if direction > 0:
                    item.rotate_cw(step)
                else:
                    item.rotate_ccw(step)
            elif isinstance(item, DeckItem):
                delta = step * direction
                item.setRotation((item.rotation() + delta) % 360)

    # ------------------------------------------------------------------
    # Deck management
    # ------------------------------------------------------------------

    def _import_deck(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Deck Folder")
        if not folder:
            return
        src = Path(folder)
        dest = self._settings.decks_dir() / src.name
        if not dest.exists():
            try:
                shutil.copytree(str(src), str(dest))
                folder = str(dest)
            except Exception:
                pass
        self._add_deck_from_path(folder)

    # ------------------------------------------------------------------
    # Non-modal dialog helper
    # ------------------------------------------------------------------

    def _show_nonmodal(self, dlg) -> None:
        """Show a non-modal dialog, holding a reference to prevent GC."""
        self._active_dialogs.add(dlg)
        dlg.finished.connect(lambda: self._active_dialogs.discard(dlg))
        dlg.show()

    def _open_deck_library(self) -> None:
        dlg = DeckLibraryDialog(
            self._settings.decks_dir(),
            self._add_deck_from_path,
            self,
        )
        self._show_nonmodal(dlg)

    def _add_deck_from_path(self, folder_path: str) -> None:
        dm = DeckModel(folder_path)
        if not dm.all_cards:
            QMessageBox.warning(self, "No Cards Found",
                                "No card images were found in the selected folder.\n"
                                "Make sure front images exist alongside a 'back' image.")
            return
        if not dm.back_path:
            QMessageBox.warning(self, "No Back Image",
                                "No 'back' image found. Please add a file named 'back.png' (or similar).")
            return
        self._add_deck(dm)

    def _add_deck(self, dm: DeckModel) -> None:
        self._deck_models[dm.id] = dm

        from PyQt6.QtCore import QPoint
        from .card_item import CARD_W, CARD_H
        top_left = self._view.mapToScene(QPoint(20, 20))
        offset_x = (len(self._deck_items) % 5) * (CARD_W + 30)
        offset_y = (len(self._deck_items) // 5) * (CARD_H + 20)
        # DeckItem origin is its centre — shift by half card size so it's fully visible
        pos = QPointF(top_left.x() + CARD_W // 2 + offset_x,
                      top_left.y() + CARD_H // 2 + offset_y)

        di = DeckItem(dm)
        di.setPos(pos)
        di.grid_snap = self._settings.canvas("grid_snap")
        di.grid_size = self._settings.canvas("grid_size")
        self._connect_deck_item(di)

        self._scene.addItem(di)
        self._deck_items[dm.id] = di
        self._active_deck_id = dm.id
        self._status.showMessage(
            f"Imported: {dm.name}  ({dm.count} cards)", 4000
        )

    def _connect_deck_item(self, di: DeckItem) -> None:
        """Wire up all signals for a DeckItem (or StackItem)."""
        di.draw_to_hand_signal.connect(self._on_draw_to_hand)
        di.draw_to_canvas_signal.connect(
            lambda cards, _di=di: self._on_draw_to_canvas(cards, _di.pos(), _di.card_h)
        )
        di.search_cards_requested.connect(self._open_card_picker)
        di.recall_stack_requested.connect(self._on_recall_stack)
        di.stack_emptied.connect(self._on_stack_emptied)
        di.stack_requested.connect(self._on_stack_requested)
        di.before_draw.connect(self._push_undo)
        di.duplicate_requested.connect(self._on_deck_duplicate)

    # ------------------------------------------------------------------
    # Dice management
    # ------------------------------------------------------------------

    def _open_image_library(self) -> None:
        if self._image_library_dlg and self._image_library_dlg.isVisible():
            self._image_library_dlg.raise_()
            self._image_library_dlg.activateWindow()
            self._image_library_dlg.refresh()
            return
        dlg = ImageLibraryDialog(
            self._image_items,
            self._settings.images_dir(),
            self,
        )
        dlg.duplicate_requested.connect(self._on_image_duplicate)
        dlg.center_view_requested.connect(self._on_image_center_view)
        dlg.localize_requested.connect(self._localize_image_items)
        dlg.spawn_requested.connect(self._on_image_spawn)
        dlg.rename_requested.connect(self._on_image_rename)
        dlg.delete_from_library_requested.connect(self._on_library_image_deleted)
        self._image_library_dlg = dlg
        self._show_nonmodal(dlg)

    def _on_image_center_view(self, item: ImageItem) -> None:
        self._view.centerOn(item)

    def _on_image_spawn(self, path: str) -> None:
        from PyQt6.QtCore import QPoint
        grid_size = self._settings.canvas("grid_size")
        top_left = self._view.mapToScene(QPoint(0, 0))
        default_sz = self._settings.display("image_import_size")
        item = ImageItem(path, h_cells=default_sz, grid_size=grid_size)
        item.grid_snap = self._settings.canvas("grid_snap")
        item.setPos(top_left)
        self._connect_image_item(item)
        self._scene.addItem(item)
        self._image_items.append(item)
        if self._image_library_dlg and self._image_library_dlg.isVisible():
            self._image_library_dlg.refresh()

    def _open_dice_library(self) -> None:
        if self._dice_library_dlg and self._dice_library_dlg.isVisible():
            self._dice_library_dlg.raise_()
            self._dice_library_dlg.activateWindow()
            return
        dlg = DiceLibraryDialog(self._dice_manager, self._settings, self)
        dlg.dice_requested.connect(self._on_dice_requested)
        self._dice_library_dlg = dlg
        self._show_nonmodal(dlg)

    def _on_dice_requested(self, dice_list: list) -> None:
        """dice_list is a list of (die_type, set_name) tuples."""
        for die_type, set_name in dice_list:
            self._add_die_to_canvas(die_type, set_name)

    def _add_die_to_canvas(self, die_type: str, set_name: str) -> None:
        grid_size = self._settings.canvas("grid_size")
        step = grid_size * 2

        # Viewport top-left in scene coordinates
        from PyQt6.QtCore import QPoint
        top_left = self._view.mapToScene(QPoint(0, 0))
        vp_height = self._view.viewport().height()

        x = top_left.x() + self._dice_cascade_col * step
        y = top_left.y() + self._dice_cascade_row * step

        di = DieItem(die_type, set_name, self._dice_manager, self._settings)
        di.setPos(QPointF(x, y))
        di.setZValue(di._base_z)
        self._connect_die_item(di)
        self._scene.addItem(di)
        self._die_items.append(di)

        # Advance cascade position
        self._dice_cascade_row += 1
        next_y = top_left.y() + self._dice_cascade_row * step
        if next_y + step > top_left.y() + vp_height:
            self._dice_cascade_row = 0
            self._dice_cascade_col += 1

    def _connect_die_item(self, di: DieItem) -> None:
        di.delete_requested.connect(self._on_die_delete)
        di.duplicate_requested.connect(self._on_die_duplicate)
        di.rolled.connect(self._on_die_rolled)

    def _on_die_delete(self, di: DieItem) -> None:
        if di in self._die_items:
            self._die_items.remove(di)
        if di.scene():
            self._scene.removeItem(di)

    def _on_die_duplicate(self, di: DieItem) -> None:
        grid_size = self._settings.canvas("grid_size")
        new_di = DieItem(di.die_type, di.set_name, self._dice_manager, self._settings)
        new_di.value = di.value
        new_di.grid_snap = di.grid_snap
        new_di.grid_size = di.grid_size
        new_di.setPos(di.pos() + QPointF(grid_size, 0))
        self._connect_die_item(new_di)
        self._scene.addItem(new_di)
        self._die_items.append(new_di)

    def _on_image_duplicate(self, item: ImageItem) -> None:
        g = self._settings.canvas("grid_size")
        new_item = ImageItem(
            item._image_path,
            w_cells=item._w_cells,
            h_cells=item._h_cells,
            grid_size=item.grid_size,
        )
        new_item._orig_w_cells = item._orig_w_cells
        new_item._orig_h_cells = item._orig_h_cells
        new_item.grid_snap    = item.grid_snap
        new_item.hover_preview = item.hover_preview
        new_item.setRotation(item.rotation())
        new_item.setPos(item.pos() + QPointF(g, g))
        self._connect_image_item(new_item)
        self._scene.addItem(new_item)
        self._image_items.append(new_item)

    def _on_deck_duplicate(self, di: DeckItem) -> None:
        import uuid as _uuid
        state = di.deck_model.to_dict()
        state["id"] = str(_uuid.uuid4())
        new_dm = DeckModel.from_dict(state)
        g = self._settings.canvas("grid_size")
        new_di = DeckItem(new_dm)
        new_di.face_up   = di.face_up
        new_di.is_stack  = di.is_stack
        new_di.grid_snap = di.grid_snap
        new_di.grid_size = di.grid_size
        new_di.setPos(di.pos() + QPointF(g, g))
        new_di.setRotation(di.rotation())
        self._connect_deck_item(new_di)
        self._scene.addItem(new_di)
        self._deck_items[new_dm.id]  = new_di
        self._deck_models[new_dm.id] = new_dm

    def _on_die_rolled(self, die: DieItem, value: int) -> None:
        """Log a single individual die roll (called via rolled signal)."""
        self._append_roll_log([die])

    def _append_roll_log(self, dice: list) -> None:
        """Build and store a roll log entry for the given dice (using _final_value)."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        dice_entries = [
            {"type": d.die_type, "value": d._final_value}
            for d in dice
        ]
        total = sum(e["value"] for e in dice_entries)
        self._roll_log.append({
            "time": time_str,
            "dice": dice_entries,
            "total": total,
        })

    def _open_roll_log(self) -> None:
        if self._roll_log_dlg and self._roll_log_dlg.isVisible():
            self._roll_log_dlg.raise_()
            self._roll_log_dlg.activateWindow()
            return
        dlg = RollLogDialog(self._roll_log, self)
        self._roll_log_dlg = dlg
        self._show_nonmodal(dlg)

    # ------------------------------------------------------------------
    # Notepad
    # ------------------------------------------------------------------

    def _open_notepad(self) -> None:
        if self._notepad_dlg is None:
            self._notepad_dlg = NotepadDialog(
                self._settings.notes_dir(),
                self._settings.notepad_config_path(),
                self,
            )
            # Apply current theme immediately
            canvas_hex = self._settings.canvas("background_color")
            if self._settings.display("use_canvas_theme"):
                self._notepad_dlg.apply_theme(canvas_hex)
            else:
                self._notepad_dlg.apply_theme(None)
        if self._notepad_dlg.isVisible():
            self._notepad_dlg.raise_()
            self._notepad_dlg.activateWindow()
        else:
            self._notepad_dlg.show()

    def _restore_notepad_if_open(self) -> None:
        """Re-open the notepad on startup if it was open when last closed."""
        config_path = self._settings.notepad_config_path()
        if not config_path.exists():
            return
        try:
            import json as _json
            state = _json.loads(config_path.read_text(encoding="utf-8"))
            if state.get("was_open", False):
                self._open_notepad()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Image items
    # ------------------------------------------------------------------

    def _connect_image_item(self, item: ImageItem) -> None:
        item.delete_requested.connect(self._on_image_delete)
        item.duplicate_requested.connect(self._on_image_duplicate)
        item.resize_requested.connect(self._on_image_resize)
        item.localize_requested.connect(lambda img: self._localize_image_items([img]))
        item.image_hovered.connect(self._on_image_hovered)
        item.image_unhovered.connect(self._on_image_unhovered)

    def _on_external_image_dropped(self, path: str, scene_pos) -> None:
        """Called when an image file is dropped from Explorer onto the canvas."""
        grid_size = self._settings.canvas("grid_size")
        default_sz = self._settings.display("image_import_size")
        item = ImageItem(path, h_cells=default_sz, grid_size=grid_size)
        item.grid_snap = self._settings.canvas("grid_snap")
        if item.grid_snap:
            g = grid_size
            from PyQt6.QtCore import QPointF as _QP
            item.setPos(_QP(round(scene_pos.x() / g) * g, round(scene_pos.y() / g) * g))
        else:
            item.setPos(scene_pos)
        self._connect_image_item(item)
        self._scene.addItem(item)
        self._image_items.append(item)

    def _import_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp)"
        )
        if not path:
            return
        dlg = ImageSizeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        grid_size = self._settings.canvas("grid_size")
        center = self._view.mapToScene(self._view.viewport().rect().center())
        item = ImageItem(path, dlg.w_cells, dlg.h_cells, grid_size)
        item.grid_snap = self._settings.canvas("grid_snap")
        item.setPos(center)
        self._connect_image_item(item)
        self._scene.addItem(item)
        self._image_items.append(item)

    def _on_image_delete(self, item: ImageItem) -> None:
        if item in self._image_items:
            self._image_items.remove(item)
        if item.scene():
            self._scene.removeItem(item)
        if self._image_library_dlg and self._image_library_dlg.isVisible():
            self._image_library_dlg.refresh()

    def _on_image_rename(self, old_path: str, new_path: str) -> None:
        """Update any canvas ImageItems whose path matches the renamed file."""
        for item in self._image_items:
            if item._image_path == old_path:
                item._image_path = new_path
                item.reload_image()

    def _on_library_image_deleted(self, path: str) -> None:
        """Remove all canvas ImageItems that referenced the deleted file."""
        for item in [i for i in self._image_items if i._image_path == path]:
            self._on_image_delete(item)

    def _on_image_resize(self, item: ImageItem) -> None:
        dlg = ImageResizeDialog(item._w_cells, item._h_cells,
                                aspect_ratio=item._aspect_ratio, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            item.resize(dlg.w_cells, dlg.h_cells)

    def _localize_images(self) -> None:
        """Localize selected ImageItems (or all if none selected)."""
        selected = [i for i in self._scene.selectedItems() if isinstance(i, ImageItem)]
        targets = selected if selected else list(self._image_items)
        if targets:
            self._localize_image_items(targets)

    def _localize_image_items(self, items: List[ImageItem]) -> None:
        dest_dir = self._settings.images_dir()
        for item in items:
            src = Path(item._image_path)
            if not src.exists():
                continue
            # Skip if already inside the images dir
            try:
                src.relative_to(dest_dir)
                continue
            except ValueError:
                pass
            dest = dest_dir / src.name
            # Resolve name collisions
            if dest.exists() and dest != src:
                stem, suffix = src.stem, src.suffix
                n = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{n}{suffix}"
                    n += 1
            shutil.copy2(str(src), str(dest))
            item._image_path = str(dest)
            item.reload_image()
        if self._session_path:
            self._do_save(self._session_path)
        if self._image_library_dlg and self._image_library_dlg.isVisible():
            self._image_library_dlg.refresh()

    def _resolve_missing_images(self, items: List[ImageItem]) -> None:
        for item in list(items):
            dlg = MissingImageDialog(item._image_path, self)
            dlg.exec()
            if dlg.result_action == "found":
                item._image_path = dlg.new_path
                item.reload_image()
            elif dlg.result_action == "remove":
                self._on_image_delete(item)

    def _active_deck(self) -> Optional[DeckItem]:
        if self._active_deck_id and self._active_deck_id in self._deck_items:
            return self._deck_items[self._active_deck_id]
        for item in self._scene.selectedItems():
            if isinstance(item, DeckItem):
                self._active_deck_id = item.deck_model.id
                return item
        if self._deck_items:
            di = next(iter(self._deck_items.values()))
            self._active_deck_id = di.deck_model.id
            return di
        return None

    def _draw_to_hand_from_active(self, count: int) -> None:
        deck = self._active_deck()
        if deck:
            deck.draw_cards_to_hand(count)
        else:
            self._status.showMessage("No active deck selected.", 2000)

    # ------------------------------------------------------------------
    # Stack creation (from selected CardItems)
    # ------------------------------------------------------------------

    def _on_stack_requested(self) -> None:
        sel = self._scene.selectedItems()
        sel_cards = [i for i in sel if isinstance(i, CardItem)]
        sel_decks = [i for i in sel if isinstance(i, DeckItem)]

        if len(sel_cards) + len(sel_decks) < 2:
            return

        # Collect all CardData from both cards and stacks/decks
        all_card_data = [ci.card_data for ci in sel_cards]
        for di in sel_decks:
            all_card_data.extend(list(di.deck_model.cards))

        if not all_card_data:
            return

        # Majority face state (per item, not per card)
        fu = sum(1 for ci in sel_cards if ci.face_up) + sum(1 for di in sel_decks if di.face_up)
        majority_face_up = fu >= (len(sel_cards) + len(sel_decks)) / 2

        # Back path from first available source
        back_path = ""
        for ci in sel_cards:
            if ci.card_data.back_path:
                back_path = ci.card_data.back_path
                break
        if not back_path:
            for di in sel_decks:
                if di.deck_model.back_path:
                    back_path = di.deck_model.back_path
                    break

        # Centre position of all selected items
        all_items = sel_cards + sel_decks
        cx = sum(i.scenePos().x() for i in all_items) / len(all_items)
        cy = sum(i.scenePos().y() for i in all_items) / len(all_items)
        centre = QPointF(cx, cy)

        # Remove all source items from scene
        for ci in sel_cards:
            self._canvas_cards.pop(ci.card_data.image_path, None)
            self._scene.removeItem(ci)
        for di in sel_decks:
            self._scene.removeItem(di)
            self._deck_items.pop(di.deck_model.id, None)
            self._deck_models.pop(di.deck_model.id, None)

        # Build a new stack DeckModel
        import uuid
        stack_dm = DeckModel(name="Stack")
        stack_dm.id = str(uuid.uuid4())
        stack_dm.back_path = back_path
        stack_dm.all_cards = all_card_data
        stack_dm.cards     = list(all_card_data)

        di = DeckItem(stack_dm)
        di.is_stack = True
        di.face_up  = majority_face_up
        di.setPos(centre)
        di.grid_snap = self._settings.canvas("grid_snap")
        di.grid_size = self._settings.canvas("grid_size")
        self._connect_deck_item(di)

        self._scene.addItem(di)
        self._deck_items[stack_dm.id] = di
        self._deck_models[stack_dm.id] = stack_dm
        self._status.showMessage(
            f"Stacked {len(all_card_data)} cards into a stack.", 3000
        )

    # ------------------------------------------------------------------
    # Disband stack → return cards to original decks
    # ------------------------------------------------------------------

    def _on_recall_stack(self, deck_item: DeckItem) -> None:
        for card in list(deck_item.deck_model.cards):
            orig_dm = self._deck_models.get(card.deck_id)
            if orig_dm and orig_dm is not deck_item.deck_model:
                orig_dm.add_to_bottom(card)
                orig_di = self._deck_items.get(card.deck_id)
                if orig_di:
                    orig_di.update()

        deck_id = deck_item.deck_model.id
        self._scene.removeItem(deck_item)
        self._deck_items.pop(deck_id, None)
        self._deck_models.pop(deck_id, None)
        self._status.showMessage("Stack disbanded — cards returned to their decks.", 3000)

    def _on_stack_emptied(self, deck_item: DeckItem) -> None:
        """Auto-remove a stack when its last card is drawn out."""
        deck_id = deck_item.deck_model.id
        self._scene.removeItem(deck_item)
        self._deck_items.pop(deck_id, None)
        self._deck_models.pop(deck_id, None)

    # ------------------------------------------------------------------
    # Card picker (search & pull from deck / stack)
    # ------------------------------------------------------------------

    def _open_card_picker(self, deck_item: DeckItem) -> None:
        def _check_stack_empty():
            if deck_item.is_stack and deck_item.deck_model.count == 0:
                deck_item.stack_emptied.emit(deck_item)

        def on_to_hand(card_data):
            self._push_undo()
            deck_item.deck_model.remove_card(card_data)
            deck_item.draw_to_hand_signal.emit([card_data])
            deck_item._update_front_pix()
            deck_item.update()
            _check_stack_empty()

        def on_to_canvas(card_data):
            self._push_undo()
            deck_item.deck_model.remove_card(card_data)
            deck_item.draw_to_canvas_signal.emit([card_data])
            deck_item._update_front_pix()
            deck_item.update()
            _check_stack_empty()

        def on_split(cards_to_split: list):
            import uuid
            from .models import DeckModel
            self._push_undo()
            dm = DeckModel(name="Stack")
            dm.id        = str(uuid.uuid4())
            dm.back_path = deck_item.deck_model.back_path
            dm.all_cards = list(cards_to_split)
            dm.cards     = list(cards_to_split)
            di = DeckItem(dm)
            di.is_stack  = True
            di.face_up   = deck_item.face_up
            di.grid_snap = self._settings.canvas("grid_snap")
            di.grid_size = self._settings.canvas("grid_size")
            # Position below the source deck, same as a drawn card
            src_pos = deck_item.pos()
            di.setPos(src_pos + QPointF(0, CARD_H + 16))
            self._connect_deck_item(di)
            self._scene.addItem(di)
            self._deck_items[dm.id]  = di
            self._deck_models[dm.id] = dm
            deck_item._update_front_pix()
            deck_item.update()
            _check_stack_empty()

        dlg = CardPickerDialog(
            deck_item.deck_model, on_to_hand, on_to_canvas,
            on_split=on_split, settings=self._settings, parent=self,
        )
        self._show_nonmodal(dlg)

    # ------------------------------------------------------------------
    # Card creation helpers
    # ------------------------------------------------------------------

    def _create_card_item(self, card_data: CardData, face_up: bool = True) -> CardItem:
        item = CardItem(card_data, face_up=face_up)
        item.grid_snap = self._settings.canvas("grid_snap")
        item.grid_size = self._settings.canvas("grid_size")
        item.send_to_hand.connect(self._on_card_send_to_hand)
        item.return_to_deck.connect(self._on_card_return_to_deck)
        item.card_hovered.connect(self._on_card_hovered)
        item.card_unhovered.connect(self._on_card_unhovered)
        item.stack_requested.connect(self._on_stack_requested)
        self._scene.addItem(item)
        self._canvas_cards[card_data.image_path] = item
        return item

    # ------------------------------------------------------------------
    # Signal handlers – deck → canvas/hand
    # ------------------------------------------------------------------

    def _on_draw_to_hand(self, cards: list) -> None:
        for card_data in cards:
            self._hand.add_card(card_data, face_up=True)
        self._status.showMessage(f"Drew {len(cards)} card(s) to hand.", 2000)

    def _on_draw_to_canvas(self, cards: list, near_pos: QPointF, deck_card_h: int = CARD_H) -> None:
        spread = 130
        y_offset = deck_card_h + 16
        for i, card_data in enumerate(cards):
            item = self._create_card_item(card_data, face_up=True)
            offset = QPointF(i * spread, y_offset)
            item.setPos(near_pos + offset)

    # ------------------------------------------------------------------
    # Signal handlers – card item signals
    # ------------------------------------------------------------------

    def _on_canvas_items_dropped_on_hand(self, items: list) -> None:
        """Cards/stacks dragged from canvas down onto the hand strip."""
        if items:
            self._push_undo()
        for item in items:
            if isinstance(item, CardItem):
                card_data = item.card_data
                face_up   = item.face_up
                self._canvas_cards.pop(card_data.image_path, None)
                self._scene.removeItem(item)
                self._hand.add_card(card_data, face_up=face_up)
            elif isinstance(item, DeckItem):
                # Move all remaining cards in the deck/stack to hand
                for card_data in list(item.deck_model.cards):
                    self._hand.add_card(card_data, face_up=item.face_up)
                deck_id = item.deck_model.id
                self._scene.removeItem(item)
                self._deck_items.pop(deck_id, None)
                self._deck_models.pop(deck_id, None)

    def _on_items_merged_into_deck(self, items: list, target_deck: DeckItem) -> None:
        """Cards and/or stacks dragged onto a deck/stack — merge all into target."""
        if not items:
            return
        self._push_undo()
        for item in items:
            if isinstance(item, CardItem):
                self._canvas_cards.pop(item.card_data.image_path, None)
                self._scene.removeItem(item)
                target_deck.receive_card(item.card_data)
            elif isinstance(item, DeckItem):
                for card in list(item.deck_model.cards):
                    target_deck.receive_card(card)
                self._scene.removeItem(item)
                self._deck_items.pop(item.deck_model.id, None)
                self._deck_models.pop(item.deck_model.id, None)
        target_deck._update_front_pix()
        target_deck.update()

    def _on_card_send_to_hand(self, card_data: CardData) -> None:
        self._push_undo()
        item = self._canvas_cards.pop(card_data.image_path, None)
        if item:
            self._scene.removeItem(item)
        self._hand.add_card(card_data, face_up=True)

    def _on_card_return_to_deck(self, card_data: CardData) -> None:
        self._push_undo()
        item = self._canvas_cards.pop(card_data.image_path, None)
        if item:
            self._scene.removeItem(item)
        dm = self._deck_models.get(card_data.deck_id)
        if dm:
            dm.add_to_bottom(card_data)
            di = self._deck_items.get(card_data.deck_id)
            if di:
                di.update()

    def _on_card_hovered(self, card_data: CardData) -> None:
        should_show = (
            self._magnify_key_held
            or self._settings.display("auto_magnify")
        )
        if should_show:
            path = card_data.image_path
            if path and Path(path).exists():
                self._magnify.set_card(QPixmap(path))
                vp = self._view.viewport()
                self._magnify.reposition(
                    vp.size(),
                    self._settings.display("magnify_corner"),
                )

    def _on_card_unhovered(self) -> None:
        if not self._magnify_key_held:
            self._magnify.set_card(None)

    def _on_image_hovered(self, path: str) -> None:
        should_show = (
            self._magnify_key_held
            or self._settings.display("auto_magnify")
        )
        if should_show and path and Path(path).exists():
            self._magnify.set_card(QPixmap(path))
            vp = self._view.viewport()
            self._magnify.reposition(
                vp.size(),
                self._settings.display("magnify_corner"),
            )

    def _on_image_unhovered(self) -> None:
        if not self._magnify_key_held:
            self._magnify.set_card(None)

    # ------------------------------------------------------------------
    # Signal handlers – hand ↔ canvas
    # ------------------------------------------------------------------

    def _on_hand_card_dropped(self, card_dict: dict, scene_pos: QPointF) -> None:
        self._push_undo()
        image_path = card_dict.get("image_path", "")
        deck_id    = card_dict.get("deck_id", "")
        face_up    = card_dict.get("face_up", True)
        rotation   = card_dict.get("rotation", 0.0)

        dm = self._deck_models.get(deck_id)
        card_data: Optional[CardData] = None
        if dm:
            card_data = dm.card_by_image_path(image_path)
        if card_data is None:
            from .models import CardData as _CD
            import uuid
            card_data = _CD(
                id=str(uuid.uuid4()),
                deck_id=deck_id,
                image_path=image_path,
                back_path=dm.back_path if dm else "",
                name=Path(image_path).stem if image_path else "?",
            )

        self._hand.remove_card_by_image_path(image_path)

        item = self._create_card_item(card_data, face_up=face_up)
        item.setPos(scene_pos)
        if rotation:
            item.set_rotation_degrees(rotation)

    def _on_hand_cards_dropped(self, cards_list: list, scene_pos: QPointF) -> None:
        """Multiple hand cards dragged and dropped onto the canvas — spread them."""
        self._push_undo()
        spread = 130
        for i, card_dict in enumerate(cards_list):
            image_path = card_dict.get("image_path", "")
            deck_id    = card_dict.get("deck_id", "")
            face_up    = card_dict.get("face_up", True)
            rotation   = card_dict.get("rotation", 0.0)

            dm = self._deck_models.get(deck_id)
            card_data: Optional[CardData] = None
            if dm:
                card_data = dm.card_by_image_path(image_path)
            if card_data is None:
                from .models import CardData as _CD
                import uuid
                card_data = _CD(
                    id=str(uuid.uuid4()),
                    deck_id=deck_id,
                    image_path=image_path,
                    back_path=dm.back_path if dm else "",
                    name=Path(image_path).stem if image_path else "?",
                )

            item = self._create_card_item(card_data, face_up=face_up)
            item.setPos(scene_pos + QPointF(i * spread, 0))
            if rotation:
                item.set_rotation_degrees(rotation)

    def _on_hand_stack_to_canvas(self, cards: list) -> None:
        """Hand cards sent via Ctrl+G — stack them at canvas centre."""
        if len(cards) < 2:
            return
        # Undo snapshot already pushed by request_undo_snapshot signal before hand was modified

        # Majority face state: cards is List[(CardData, face_up)]
        face_up_count = sum(1 for _, fu in cards if fu)
        majority_face_up = face_up_count >= len(cards) / 2

        import uuid
        stack_dm = DeckModel(name="Stack")
        stack_dm.id = str(uuid.uuid4())
        stack_dm.back_path = cards[0][0].back_path
        stack_dm.all_cards = [cd for cd, _ in cards]
        stack_dm.cards     = list(stack_dm.all_cards)

        view_centre = self._view.mapToScene(
            self._view.viewport().rect().center()
        )
        di = DeckItem(stack_dm)
        di.is_stack = True
        di.face_up  = majority_face_up
        di.setPos(view_centre)
        di.grid_snap = self._settings.canvas("grid_snap")
        di.grid_size = self._settings.canvas("grid_size")
        self._connect_deck_item(di)

        self._scene.addItem(di)
        self._deck_items[stack_dm.id] = di
        self._deck_models[stack_dm.id] = stack_dm
        self._status.showMessage(
            f"Stacked {len(cards)} hand cards into a stack on canvas.", 3000
        )

    def _on_hand_send_to_canvas(self, card_data: CardData, _: QPointF) -> None:
        self._push_undo()
        view_centre = self._view.mapToScene(
            self._view.viewport().rect().center()
        )
        item = self._create_card_item(card_data, face_up=True)
        item.setPos(view_centre)

    def _on_hand_return_to_deck(self, card_data: CardData) -> None:
        self._push_undo()
        dm = self._deck_models.get(card_data.deck_id)
        if dm:
            dm.add_to_bottom(card_data)
            di = self._deck_items.get(card_data.deck_id)
            if di:
                di.update()

    # ------------------------------------------------------------------
    # Magnify event filter + viewport resize → reposition hand
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._view.viewport():
            t = event.type()
            if t == QEvent.Type.KeyPress:
                if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Alt:
                    self._magnify_key_held = True
            elif t == QEvent.Type.KeyRelease:
                if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Alt:
                    self._magnify_key_held = False
                    if not self._settings.display("auto_magnify"):
                        self._magnify.set_card(None)
            elif t == QEvent.Type.MouseMove:
                if self._magnify.isVisible():
                    vp = self._view.viewport()
                    self._magnify.reposition(
                        vp.size(),
                        self._settings.display("magnify_corner"),
                    )
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------

    def _recall_dialog(self) -> None:
        dlg = RecallDialog(self._deck_models, self)
        dlg.finished.connect(lambda result, d=dlg: self._on_recall_finished(d, result))
        self._show_nonmodal(dlg)

    def _on_recall_finished(self, dlg, result: int) -> None:
        if result != QDialog.DialogCode.Accepted:
            return
        opts = dlg.result_options()

        if opts["from_canvas"]:
            for item in list(self._scene.items()):
                if isinstance(item, CardItem):
                    if getattr(item, "locked", False):
                        continue
                    card_data = item.card_data
                    self._scene.removeItem(item)
                    self._canvas_cards.pop(card_data.image_path, None)
                    dm = self._deck_models.get(card_data.deck_id)
                    if dm:
                        dm.add_to_bottom(card_data)

        if opts["from_hand"]:
            for hs in list(self._hand.hand_cards):
                dm = self._deck_models.get(hs.card_data.deck_id)
                if dm:
                    dm.add_to_bottom(hs.card_data)
            self._hand.clear()

        if opts["shuffle_after"]:
            for dm in self._deck_models.values():
                dm.shuffle()

        for di in self._deck_items.values():
            di.update()

        self._magnify.set_card(None)
        self._status.showMessage("Cards recalled.", 3000)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _new_session(self) -> None:
        if self._scene.items():
            resp = QMessageBox.question(
                self, "New Session",
                "Start a new session? Unsaved changes will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self._clear_session()

    def _clear_session(self) -> None:
        from .canvas_scene import GridLayer
        self._magnify.set_card(None)
        for item in list(self._scene.items()):
            if not isinstance(item, GridLayer):
                self._scene.removeItem(item)
        self._deck_models.clear()
        self._deck_items.clear()
        self._canvas_cards.clear()
        self._die_items.clear()
        self._image_items.clear()
        self._roll_log.clear()
        self._dice_cascade_col = 0
        self._dice_cascade_row = 0
        self._hand.clear()
        self._active_deck_id = None
        self._session_path = None
        self._view.reset_zoom()
        self.setWindowTitle("SoloCanvas")

    def _save_session(self) -> None:
        if self._session_path is None:
            self._save_session_as()
        else:
            self._do_save(self._session_path)

    def _save_session_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Session", "Session name:")
        if not ok or not name.strip():
            return
        path = self._session.sessions_dir() / f"{name.strip()}.json"
        self._do_save(path, name=name.strip())

    def _do_save(self, path: Path, name: str = "") -> None:
        state = SessionManager.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            roll_log=self._roll_log,
            image_items=self._image_items,
        )
        saved = self._session.save(state, path=path, name=name or path.stem)
        self._session_path = saved
        self.setWindowTitle(f"SoloCanvas – {saved.stem}")
        self._status.showMessage(f"Session saved: {saved.name}", 3000)
        self._save_screenshot(saved)

    def _capture_canvas_screenshot(self) -> "QPixmap":
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainter
        vp = self._view.viewport().rect()
        visible = self._view.mapToScene(vp).boundingRect()
        cx, cy = visible.center().x(), visible.center().y()
        vw, vh = visible.width(), visible.height()
        # Expand the shorter dimension so the capture is exactly 16:9
        if vw / max(vh, 1) > 16 / 9:
            h = vw * 9 / 16
            w = vw
        else:
            w = vh * 16 / 9
            h = vh
        capture = QRectF(cx - w / 2, cy - h / 2, w, h)
        pix = QPixmap(400, 225)
        painter = QPainter(pix)
        self._scene.render(painter, QRectF(0, 0, 400, 225), capture)
        painter.end()
        return pix

    def _save_screenshot(self, session_path: Path) -> None:
        try:
            pix = self._capture_canvas_screenshot()
            pix.save(str(session_path.with_suffix(".png")), "PNG")
        except Exception:
            pass

    def _open_session(self) -> None:
        sessions = self._session.list_sessions()
        if not sessions:
            QMessageBox.information(self, "No Sessions", "No saved sessions found.")
            return
        dlg = SessionPickerDialog(sessions, self)
        dlg.finished.connect(lambda result, d=dlg: self._on_session_picked(d, result))
        self._show_nonmodal(dlg)

    def _on_session_picked(self, dlg, result: int) -> None:
        if result != QDialog.DialogCode.Accepted or not dlg.selected_path:
            return
        data = self._session.load(dlg.selected_path)
        if data:
            self._load_state(data)
            self._session_path = Path(dlg.selected_path)
            self.setWindowTitle(f"SoloCanvas – {self._session_path.stem}")

    def _load_state(self, data: dict, restore_zoom: bool = True) -> None:
        self._clear_session()

        for deck_dict in data.get("decks", []):
            dm = DeckModel.from_dict(deck_dict)
            if not dm.all_cards:
                continue
            self._deck_models[dm.id] = dm
            di = DeckItem(dm)
            di.setPos(deck_dict.get("canvas_x", 0), deck_dict.get("canvas_y", 0))
            di.setRotation(deck_dict.get("rotation", 0))
            di.face_up   = deck_dict.get("face_up", False)
            di.is_stack  = deck_dict.get("is_stack", False)
            di.grid_snap = self._settings.canvas("grid_snap")
            di.grid_size = self._settings.canvas("grid_size")
            self._connect_deck_item(di)
            self._scene.addItem(di)
            self._deck_items[dm.id] = di

        card_lookup: Dict[str, CardData] = {}
        for dm in self._deck_models.values():
            for c in dm.all_cards:
                card_lookup[c.image_path] = c

        for cd in data.get("canvas_cards", []):
            img_path = cd.get("image_path", "")
            card_data = card_lookup.get(img_path)
            if card_data is None:
                continue
            item = self._create_card_item(card_data, face_up=cd.get("face_up", True))
            item.setPos(cd.get("x", 0), cd.get("y", 0))
            item.set_rotation_degrees(cd.get("rotation", 0))
            item.locked = cd.get("locked", False)
            if item.locked:
                from PyQt6.QtWidgets import QGraphicsItem
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            item.setZValue(cd.get("z", 1))

        for hd in data.get("hand_cards", []):
            img_path = hd.get("image_path", "")
            card_data = card_lookup.get(img_path)
            if card_data:
                self._hand.add_card(
                    card_data,
                    face_up=hd.get("face_up", True),
                    rotation=hd.get("rotation", 0.0),
                )

        canvas = data.get("canvas", {})
        if restore_zoom:
            scale = canvas.get("scale", 1.0)
            self._view.reset_zoom()
            if scale != 1.0:
                self._view.scale(scale, scale)
                self._view._scale = scale

        bg = canvas.get("background", {})
        if bg:
            self._scene.set_background(
                mode       = bg.get("mode", "color"),
                color      = bg.get("color", "#55557f"),
                image_path = bg.get("image_path"),
            )

        for dd in data.get("dice", []):
            die_type = dd.get("die_type", "d6")
            set_name = dd.get("set_name", "White")
            di = DieItem(die_type, set_name, self._dice_manager, self._settings)
            di.value = dd.get("value", 1)
            di.setPos(dd.get("x", 0), dd.get("y", 0))
            di.setZValue(dd.get("z", 1))
            di._base_z = dd.get("z", 1)
            di.grid_snap = dd.get("grid_snap", False)
            di.grid_size = self._settings.canvas("grid_size")
            self._connect_die_item(di)
            self._scene.addItem(di)
            self._die_items.append(di)

        self._roll_log.extend(data.get("roll_log", []))

        missing_items: List[ImageItem] = []
        for img_dict in data.get("images", []):
            path = img_dict.get("path", "")
            item = ImageItem(
                path,
                w_cells=img_dict.get("w_cells", 1.0),
                h_cells=img_dict.get("h_cells", 1.0),
                grid_size=self._settings.canvas("grid_size"),
            )
            item.setPos(img_dict.get("x", 0), img_dict.get("y", 0))
            item.setRotation(img_dict.get("rotation", 0))
            item._base_z = img_dict.get("z", 0)
            item.setZValue(item._base_z)
            item.grid_snap = img_dict.get("grid_snap", True)
            item._orig_w_cells = img_dict.get("orig_w_cells", item._w_cells)
            item._orig_h_cells = img_dict.get("orig_h_cells", item._h_cells)
            item.locked = img_dict.get("locked", False)
            if item.locked:
                item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
            # Restore anchor state (must happen after addItem for scene to be set)
            self._connect_image_item(item)
            self._scene.addItem(item)
            if img_dict.get("is_anchor", False):
                item.is_anchor = True
                item._shadow.setEnabled(False)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
            self._image_items.append(item)
            if item._pixmap.isNull():
                missing_items.append(item)
        if missing_items:
            self._resolve_missing_images(missing_items)

        if self._deck_models:
            self._active_deck_id = next(iter(self._deck_models))

        # Restore global hover_preview state
        hp = data.get("hover_preview", True)
        for item in self._scene.items():
            if hasattr(item, "hover_preview"):
                item.hover_preview = hp

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        """Snapshot current state onto the undo stack (max 10)."""
        from .session_manager import SessionManager as _SM
        state = _SM.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            image_items=self._image_items,
        )
        self._undo_stack.append(state)
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._undo_action.setEnabled(True)
        self._redo_action.setEnabled(False)

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        from .session_manager import SessionManager as _SM
        # Save current state to redo stack
        current = _SM.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            image_items=self._image_items,
        )
        self._redo_stack.append(current)
        state = self._undo_stack.pop()
        self._load_state(state, restore_zoom=False)
        self._undo_action.setEnabled(bool(self._undo_stack))
        self._redo_action.setEnabled(True)

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        from .session_manager import SessionManager as _SM
        current = _SM.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            image_items=self._image_items,
        )
        self._undo_stack.append(current)
        state = self._redo_stack.pop()
        self._load_state(state, restore_zoom=False)
        self._undo_action.setEnabled(True)
        self._redo_action.setEnabled(bool(self._redo_stack))

    # ------------------------------------------------------------------
    # Edit actions
    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        for item in self._scene.items():
            item.setSelected(True)

    def _copy_selected(self) -> None:
        """Serialize selected copyable items into the internal clipboard."""
        entries = []
        for item in self._scene.selectedItems():
            if isinstance(item, ImageItem):
                entries.append({"type": "image", "state": item.to_state_dict()})
            elif isinstance(item, DieItem):
                entries.append({"type": "die", "state": item.to_state_dict()})
            elif isinstance(item, DeckItem):
                deck_state = item.deck_model.to_dict()
                deck_state["canvas_x"]  = item.pos().x()
                deck_state["canvas_y"]  = item.pos().y()
                deck_state["rotation"]  = item.rotation()
                deck_state["face_up"]   = item.face_up
                deck_state["is_stack"]  = item.is_stack
                deck_state["grid_snap"] = item.grid_snap
                entries.append({"type": "deck", "state": deck_state})
        if entries:
            self._clipboard = entries

    def _paste_clipboard(self) -> None:
        """Recreate clipboard items centered at the cursor's scene position.
        Falls back to pasting an image from the system clipboard if the internal
        clipboard is empty."""
        if not self._clipboard:
            self._paste_system_image()
            return
        import uuid as _uuid
        from PyQt6.QtGui import QCursor
        vp_pos = self._view.mapFromGlobal(QCursor.pos())
        cursor_scene = self._view.mapToScene(vp_pos)

        # Compute centroid of original positions to offset from
        positions = [
            QPointF(e["state"].get("x", e["state"].get("canvas_x", 0)),
                    e["state"].get("y", e["state"].get("canvas_y", 0)))
            for e in self._clipboard
        ]
        centroid = QPointF(
            sum(p.x() for p in positions) / len(positions),
            sum(p.y() for p in positions) / len(positions),
        )
        offset = cursor_scene - centroid

        self._push_undo()
        self._scene.clearSelection()
        for entry in self._clipboard:
            t = entry["type"]
            s = entry["state"]
            if t == "image":
                item = ImageItem(
                    s["path"],
                    w_cells=s.get("w_cells", 1.0),
                    h_cells=s.get("h_cells", 1.0),
                    grid_size=self._settings.canvas("grid_size"),
                )
                item._orig_w_cells  = s.get("orig_w_cells", item._w_cells)
                item._orig_h_cells  = s.get("orig_h_cells", item._h_cells)
                item.grid_snap      = s.get("grid_snap", True)
                item.hover_preview  = s.get("hover_preview", True)
                item.setRotation(s.get("rotation", 0))
                item.setPos(QPointF(s["x"], s["y"]) + offset)
                self._connect_image_item(item)
                self._scene.addItem(item)
                self._image_items.append(item)
                item.setSelected(True)
            elif t == "die":
                new_di = DieItem(s["die_type"], s["set_name"], self._dice_manager, self._settings)
                new_di.value     = s.get("value", 1)
                new_di.grid_snap = s.get("grid_snap", False)
                new_di.grid_size = self._settings.canvas("grid_size")
                new_di.setPos(QPointF(s["x"], s["y"]) + offset)
                self._connect_die_item(new_di)
                self._scene.addItem(new_di)
                self._die_items.append(new_di)
                new_di.setSelected(True)
            elif t == "deck":
                new_state = dict(s)
                new_state["id"] = str(_uuid.uuid4())
                new_dm = DeckModel.from_dict(new_state)
                new_di = DeckItem(new_dm)
                new_di.face_up   = s.get("face_up", False)
                new_di.is_stack  = s.get("is_stack", False)
                new_di.grid_snap = s.get("grid_snap", False)
                new_di.grid_size = self._settings.canvas("grid_size")
                new_di.setPos(
                    QPointF(s.get("canvas_x", 0), s.get("canvas_y", 0)) + offset
                )
                new_di.setRotation(s.get("rotation", 0))
                self._connect_deck_item(new_di)
                self._scene.addItem(new_di)
                self._deck_items[new_dm.id]  = new_di
                self._deck_models[new_dm.id] = new_dm
                new_di.setSelected(True)

    def _paste_system_image(self) -> None:
        """Paste an image from the system clipboard as a new ImageItem.
        The image is saved directly into images_dir (already localized)."""
        import uuid as _uuid
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        qimage = cb.image()
        if qimage.isNull():
            return

        dest_dir = self._settings.images_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"clipboard_{_uuid.uuid4().hex[:8]}.png"
        if not qimage.save(str(dest), "PNG"):
            return

        grid_size = self._settings.canvas("grid_size")
        default_sz = self._settings.display("image_import_size")
        vp_pos = self._view.mapFromGlobal(QCursor.pos())
        cursor_scene = self._view.mapToScene(vp_pos)

        self._push_undo()
        self._scene.clearSelection()
        item = ImageItem(str(dest), h_cells=default_sz, grid_size=grid_size)
        item.grid_snap = self._settings.canvas("grid_snap")
        if item.grid_snap:
            item.setPos(QPointF(
                round(cursor_scene.x() / grid_size) * grid_size,
                round(cursor_scene.y() / grid_size) * grid_size,
            ))
        else:
            item.setPos(cursor_scene)
        self._connect_image_item(item)
        self._scene.addItem(item)
        self._image_items.append(item)
        item.setSelected(True)

    def _delete_selected(self) -> None:
        if self._scene.selectedItems():
            self._push_undo()
        for item in list(self._scene.selectedItems()):
            if isinstance(item, CardItem):
                self._canvas_cards.pop(item.card_data.image_path, None)
                self._scene.removeItem(item)
            elif isinstance(item, DeckItem):
                deck_id = item.deck_model.id
                self._scene.removeItem(item)
                self._deck_items.pop(deck_id, None)
                self._deck_models.pop(deck_id, None)
            elif isinstance(item, DieItem):
                if item in self._die_items:
                    self._die_items.remove(item)
                self._scene.removeItem(item)
            elif isinstance(item, ImageItem):
                if item in self._image_items:
                    self._image_items.remove(item)
                self._scene.removeItem(item)

    # ------------------------------------------------------------------
    # Canvas actions
    # ------------------------------------------------------------------

    def _toggle_grid(self) -> None:
        visible = not self._scene.grid_visible
        self._scene.set_grid(visible)
        snap = self._settings.canvas("grid_snap")
        for item in self._scene.items():
            if hasattr(item, "grid_snap"):
                item.grid_snap = snap and visible
                item.grid_size = self._scene.grid_size
                if hasattr(item, "update_grid_size"):
                    item.update_grid_size(self._scene.grid_size)

    def _open_bg_dialog(self) -> None:
        dlg = BackgroundDialog(self._scene, self)
        def _on_bg_done(_):
            self._hand.update()
            self._apply_theme()
        dlg.finished.connect(_on_bg_done)
        self._show_nonmodal(dlg)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        dlg.finished.connect(lambda result: self._on_settings_closed(result))
        self._show_nonmodal(dlg)

    def _on_settings_closed(self, result: int) -> None:
        if result == QDialog.DialogCode.Accepted:
            self._hand.set_max_card_width(self._settings.display("max_hand_card_width"))
            self._hand.update()  # also picks up any canvas color change
            self._scene.grid_visible = self._settings.canvas("grid_enabled")
            self._scene.grid_size    = self._settings.canvas("grid_size")
            self._scene.grid_color   = self._settings.canvas("grid_color")
            self._scene.update()
            self._magnify.set_size(self._settings.display("magnify_size"))
            new_grid = self._settings.canvas("grid_size")
            for di in self._die_items:
                di.update_die_size(new_grid)
            self._apply_theme()

    # ------------------------------------------------------------------
    # UI theming
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        """Apply (or remove) the canvas-derived colour theme application-wide."""
        canvas_hex = self._settings.canvas("background_color")
        if self._settings.display("use_canvas_theme"):
            panel = _theme.panel_color(canvas_hex)
            ss = _theme.build_app_stylesheet(panel)
            QApplication.instance().setStyleSheet(ss)
        else:
            QApplication.instance().setStyleSheet(_WINDOW_STYLE)

        # Keep the zoom / hint labels readable against the status bar background
        from PyQt6.QtGui import QColor as _QColor
        if self._settings.display("use_canvas_theme"):
            _bg = _theme.panel_color(canvas_hex)
        else:
            _bg = _QColor(30, 30, 46)   # default dark window background
        _txt = _theme.text_color(_bg).name()
        self._zoom_label.setStyleSheet(f"color: {_txt}; margin-right: 8px;")
        self._hotkey_hint_label.setStyleSheet(f"color: {_txt}; margin-left: 6px;")

        # Propagate to notepad if open
        if self._notepad_dlg is not None:
            if self._settings.display("use_canvas_theme"):
                self._notepad_dlg.apply_theme(canvas_hex)
            else:
                self._notepad_dlg.apply_theme(None)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _on_zoom_changed(self, scale: float) -> None:
        self._zoom_label.setText(f"{int(scale * 100)} %")

    # ------------------------------------------------------------------
    # Window state & geometry
    # ------------------------------------------------------------------

    def _show_startup_dialog(self) -> None:
        sessions = self._session.list_sessions()
        if not sessions:
            return
        dlg = StartupDialog(sessions, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            data = self._session.load(dlg.selected_path)
            if data:
                self._load_state(data)
                self._session_path = Path(dlg.selected_path)
                self.setWindowTitle(f"SoloCanvas – {self._session_path.stem}")

    def _restore_window_state(self) -> None:
        from PyQt6.QtCore import QSettings as QS
        qs = QS("SoloCanvas", "SoloCanvas")
        geom = qs.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1280, 800)
            self.move(100, 80)

    def _save_window_state(self) -> None:
        from PyQt6.QtCore import QSettings as QS
        qs = QS("SoloCanvas", "SoloCanvas")
        qs.setValue("geometry", self.saveGeometry())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_magnify") and self._magnify.isVisible():
            vp = self._view.viewport()
            self._magnify.reposition(
                vp.size(),
                self._settings.display("magnify_corner"),
            )

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _open_hotkey_reference(self) -> None:
        dlg = HotkeyReferenceDialog(self._settings, self)
        self._show_nonmodal(dlg)

    def _about(self) -> None:
        QMessageBox.about(
            self, "About SoloCanvas",
            "<h3>SoloCanvas</h3>"
            "<p>An interactive canvas for custom card decks.</p>"
            "<p>Import a deck from a folder containing a <i>back</i> image and "
            "one image per card.</p>",
        )

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_window_state()
        if self._settings.display("auto_save_on_close") and self._scene.items():
            try:
                state = SessionManager.build_state(
                    self._view, self._scene, self._hand,
                    self._deck_models, self._deck_items,
                    die_items=self._die_items,
                    roll_log=self._roll_log,
                    image_items=self._image_items,
                )
                if self._session_path is not None:
                    # Save to the active named session
                    self._session.save(state, path=self._session_path,
                                       name=self._session_path.stem)
                    self._save_screenshot(self._session_path)
                else:
                    # No named session — save to Autosave slot
                    autosave_path = self._session.autosave_path()
                    self._session.autosave(state)
                    self._save_screenshot(autosave_path)
            except Exception:
                pass
        if self._notepad_dlg is not None:
            self._notepad_dlg.save_and_close()
        self._settings.save()
        event.accept()
