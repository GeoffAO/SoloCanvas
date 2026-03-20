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
    QAction, QActionGroup, QCloseEvent, QColor, QFont, QIcon,
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
    ImageResizeDialog, ImageSizeDialog, MeasurementSettingsDialog,
    MissingImageDialog, RecallDialog,
    RollLogDialog, SessionPickerDialog, SettingsDialog, StartupDialog,
)
from .measurement_item import MeasurementItem
from .drawing_item import DrawingStrokeItem, DrawingShapeItem, make_smooth_path
from .drawing_settings_dialog import DrawingSettingsDialog
from .image_item     import ImageItem
from .die_item       import DieItem
from .dice_manager   import DiceSet, DiceSetsManager
from .hand_widget    import HandWidget, _HAND_MARGIN_BOTTOM
from .models         import CardData, DeckModel
from .session_manager  import SessionManager
from .settings_manager import SettingsManager
from .minimap_dialog      import MiniMapDialog
from .sticky_note_item    import StickyNoteItem
from .notepad_dialog   import NotepadDialog
from .pdf_viewer       import PDFViewerWindow
from . import theme as _theme
from .floating_toolbar import FloatingToolbar, BUTTONS as _TB_BUTTONS



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


class _DimensionBubble(QWidget):
    """Small floating label that shows the current measurement value."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._text = ""
        self.setFixedSize(120, 28)
        self.hide()

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(15, 15, 25, 210))
        painter.setPen(QPen(QColor(191, 163, 129), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
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
        self._was_maximized = False
        self._fs_menu_timer = QTimer(self)
        self._fs_menu_timer.setInterval(100)
        self._fs_menu_timer.timeout.connect(self._check_fullscreen_menu)

        # Dice
        self._dice_manager = DiceSetsManager()
        self._die_items: List[DieItem] = []
        self._roll_log: List[dict] = []
        self._dice_cascade_col: int = 0
        self._dice_cascade_row: int = 0

        # Image items
        self._image_items: List[ImageItem] = []
        self._image_cascade_col: int = 0
        self._image_cascade_row: int = 0

        # Sticky notes
        self._sticky_notes: List["StickyNoteItem"] = []

        # Clipboard for copy/paste (list of {"type": str, "state": dict})
        self._clipboard: list = []
        self._clipboard_time: float = 0.0        # when internal clipboard was last written
        self._sys_clipboard_time: float = 0.0    # when system clipboard last changed
        QApplication.clipboard().dataChanged.connect(self._on_sys_clipboard_changed)

        # Non-modal dialog tracking (prevents GC, allows raise-on-reopen)
        self._active_dialogs: set = set()
        self._dice_library_dlg = None
        self._roll_log_dlg = None
        self._image_library_dlg = None
        self._notepad_dlg: Optional[NotepadDialog] = None
        self._pdf_dlg: Optional[PDFViewerWindow] = None
        self._minimaps: dict[str, MiniMapDialog] = {}   # image_path → dialog

        # Undo / redo (snapshot-based, configurable max levels)
        self._undo_stack: list = []
        self._redo_stack: list = []

        # Drawing tool
        self._drawing_items: list = []            # all DrawingStrokeItem / DrawingShapeItem on canvas
        self._active_draw_points: list = []       # freehand points being collected
        self._active_draw_stroke = None           # live DrawingStrokeItem during freehand drag
        self._active_draw_shape  = None           # live DrawingShapeItem during shape drag
        self._draw_start_pos     = None           # QPointF where current shape drag started
        self._draw_settings_dlg  = None           # DrawingSettingsDialog (non-modal, persistent)
        self._apply_draw_settings_to_selection = False
        self._draw_customize_needs_undo = False

        # Measurement tool
        self._active_measurement: Optional[MeasurementItem] = None  # item being drawn
        self._frozen_measurements: List[MeasurementItem] = []       # on-canvas frozen items
        self._measure_persistent: bool = False  # if True, frozen measurements survive canvas clicks

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
        self.setMinimumSize(400, 300)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        # Layout: canvas view fills all available space
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scene = CanvasScene(self._settings)
        self._view  = CanvasView(self._scene, self._settings)
        layout.addWidget(self._view, 1)

        # Floating hand panel – child of central, centred at bottom
        self._hand = HandWidget(self._settings, central)

        # Floating toolbar – child of central, anchored top-right (above hand)
        self._toolbar = FloatingToolbar(self._settings, central)
        self._toolbar.raise_()

        # Magnify overlay – child of central, raised above everything
        self._magnify = MagnifyOverlay(central)
        self._magnify.set_size(self._settings.display("magnify_size"))
        self._magnify.raise_()

        # Dimension bubble — shows current measurement value during drawing
        self._dim_bubble = _DimensionBubble(central)
        self._dim_bubble.raise_()

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._hotkey_hint_label = QLabel("Press K for hotkey reference")
        self._hotkey_hint_label.setStyleSheet("color: #585b70; margin-left: 6px;")
        self._status.addWidget(self._hotkey_hint_label)
        self._selection_label = QLabel("")
        self._selection_label.setStyleSheet("color: #8C8D9B; margin-left: 12px;")
        self._status.addWidget(self._selection_label)
        self._zoom_label = QLabel("100 %")
        self._zoom_label.setStyleSheet("color: #a6adc8; margin-right: 8px;")
        self._status.addPermanentWidget(self._zoom_label)

        # Connect signals
        self._scene.hand_card_dropped.connect(self._on_hand_card_dropped)
        self._scene.hand_cards_dropped.connect(self._on_hand_cards_dropped)
        self._scene.external_image_dropped.connect(self._on_external_image_dropped)
        self._scene.paste_requested.connect(self._paste_clipboard)
        self._scene.selectionChanged.connect(self._on_selection_changed)
        self._view.zoom_changed.connect(self._on_zoom_changed)
        self._view.key_action.connect(self._dispatch_key)
        self._view.key_release_action.connect(self._dispatch_key_release)
        self._r_held: bool = False
        self._view.rotate_held_item.connect(self._rotate_held)
        self._view.items_dropped_on_hand.connect(self._on_canvas_items_dropped_on_hand)
        self._view.items_merged_into_deck.connect(self._on_items_merged_into_deck)
        self._view.drag_near_hand.connect(self._hand.set_drop_highlight)

        self._hand.send_to_canvas.connect(self._on_hand_send_to_canvas)
        self._hand.return_to_deck.connect(self._on_hand_return_to_deck)
        self._hand.stack_to_canvas_requested.connect(self._on_hand_stack_to_canvas)
        self._hand.request_undo_snapshot.connect(self._push_undo)
        self._hand.hand_card_hovered.connect(self._on_card_hovered)
        self._hand.hand_card_unhovered.connect(self._on_card_unhovered)

        self._toolbar.hand_clicked.connect(self._toggle_hand_widget)
        self._toolbar.lib_clicked.connect(self._open_deck_library)
        self._toolbar.rcl_clicked.connect(self._recall_dialog)
        self._toolbar.img_lib_clicked.connect(self._open_image_library)
        self._toolbar.dice_clicked.connect(self._open_dice_library)
        self._toolbar.log_clicked.connect(self._open_roll_log)
        self._toolbar.notepad_clicked.connect(self._open_notepad)
        self._toolbar.sticky_clicked.connect(self._place_sticky_note)
        self._toolbar.pdf_clicked.connect(self._open_pdf_viewer)
        self._toolbar.tool_changed.connect(self._on_toolbar_tool_changed)
        self._toolbar.measure_mode_changed.connect(self._on_measure_mode_changed)
        self._toolbar.measure_type_changed.connect(self._on_measure_type_changed)
        self._toolbar.draw_tool_changed.connect(self._on_draw_tool_changed)
        self._toolbar.draw_trash_requested.connect(self._clear_all_drawings)

        self._hand.visibility_changed.connect(self._toolbar.set_hand_visible)
        self._hand.hand_card_count_changed.connect(self._toolbar.set_hand_card_count)

        self._view.measurement_toggled.connect(self._on_measurement_toggled)
        self._view.drawing_toggled.connect(self._on_drawing_toggled)
        self._view.measurement_press.connect(self._on_measurement_press)
        self._view.measurement_move.connect(self._on_measurement_move)
        self._view.measurement_release.connect(self._on_measurement_release)
        self._view.measurement_waypoint.connect(self._on_measurement_waypoint)
        self._view.draw_press.connect(self._on_draw_press)
        self._view.draw_move.connect(self._on_draw_move)
        self._view.draw_release.connect(self._on_draw_release)
        self._view.draw_cancel.connect(self._on_draw_cancel)
        self._view.canvas_pressed.connect(self._hand.clear_selection)
        self._view.canvas_pressed.connect(self._on_canvas_interaction)

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
        act(tools_menu, "PDF Viewer…",   self._open_pdf_viewer)

        # Measure
        measure_menu = mb.addMenu("&Measure")
        self._measure_actions: Dict[str, QAction] = {}
        for mtype, label in [("line", "Line"), ("area", "Area"), ("cone", "Cone")]:
            a = QAction(label, self)
            a.setCheckable(True)
            a.triggered.connect(lambda checked, t=mtype: self._set_measure_type_from_menu(t))
            measure_menu.addAction(a)
            self._measure_actions[mtype] = a
        measure_menu.addSeparator()
        self._measure_grid_action = QAction("Grid Mode", self)
        self._measure_grid_action.setCheckable(True)
        self._measure_grid_action.triggered.connect(
            lambda checked: self._set_measure_mode_from_menu("grid" if checked else "free")
        )
        measure_menu.addAction(self._measure_grid_action)
        measure_menu.addSeparator()
        self._measure_persistent_action = QAction("Persistent", self)
        self._measure_persistent_action.setCheckable(True)
        self._measure_persistent_action.setChecked(False)
        self._measure_persistent_action.triggered.connect(self._on_measure_persistent_toggled)
        measure_menu.addAction(self._measure_persistent_action)
        measure_menu.addSeparator()
        act(measure_menu, "Clear Measurements", self._clear_all_measurements)
        measure_menu.addSeparator()
        act(measure_menu, "Measurement Settings…", self._open_measurement_settings)
        self._update_measure_menu_state()

        # Toolbar visibility
        toolbar_menu = mb.addMenu("Tool&bar")
        for bid, _icon, label in _TB_BUTTONS:
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(self._settings.toolbar("button_visibility").get(bid, True))
            a.triggered.connect(
                lambda checked, b=bid: self._toolbar.set_button_visible(b, checked)
            )
            toolbar_menu.addAction(a)

        # View — window stacking
        view_menu = mb.addMenu("&View")
        layer_group = QActionGroup(self)
        layer_group.setExclusive(True)
        self._act_on_top    = QAction("Keep Window on Top",    self, checkable=True)
        self._act_on_bottom = QAction("Keep Window on Bottom", self, checkable=True)
        self._act_normal    = QAction("Normal Window",         self, checkable=True)
        self._act_normal.setChecked(True)
        for a in (self._act_on_top, self._act_on_bottom, self._act_normal):
            layer_group.addAction(a)
            view_menu.addAction(a)
        self._act_on_top.triggered.connect(lambda: self._set_window_layer("top"))
        self._act_on_bottom.triggered.connect(lambda: self._set_window_layer("bottom"))
        self._act_normal.triggered.connect(lambda: self._set_window_layer("normal"))

        # Help
        help_menu = mb.addMenu("&Help")
        act(help_menu, "Hotkey Reference…  (K)", self._open_hotkey_reference)
        help_menu.addSeparator()
        act(help_menu, "About SoloCanvas", self._about)

        # Drop shadow beneath the menu bar
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        mb_shadow = QGraphicsDropShadowEffect(mb)
        mb_shadow.setBlurRadius(12)
        mb_shadow.setOffset(0, 4)
        mb_shadow.setColor(QColor(0, 0, 0, 140))
        mb.setGraphicsEffect(mb_shadow)

    def _setup_shortcuts(self) -> None:
        pass  # Key dispatch handled via canvas_view.key_action signal

    # ------------------------------------------------------------------
    # Window layer (View menu)
    # ------------------------------------------------------------------

    def _set_window_layer(self, layer: str) -> None:
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowStaysOnTopHint
        flags &= ~Qt.WindowType.WindowStaysOnBottomHint
        if layer == "top":
            flags |= Qt.WindowType.WindowStaysOnTopHint
        elif layer == "bottom":
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        self.setWindowFlags(flags)
        self.show()

    # ------------------------------------------------------------------
    # Key dispatch (from canvas_view)
    # ------------------------------------------------------------------

    def _dispatch_key(self, key_str: str) -> None:
        s = self._settings
        selected_cards = [
            i for i in self._scene.selectedItems()
            if isinstance(i, (CardItem, DeckItem, ImageItem))
        ]

        if key_str == "Escape":
            if self._any_tool_active():
                self._escape_deactivate_tools()
            else:
                self._show_startup_dialog()
            return


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
            self._r_held = True
            if len(selected_dice) > 1:
                # Group roll — suppress individual signals and log as one entry
                for die in selected_dice:
                    die._log_individual = False
                    die.keep_rolling = True
                    die.roll()
                self._append_roll_log(selected_dice)
            else:
                for die in selected_dice:
                    die.keep_rolling = True
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
                       if isinstance(i, (CardItem, ImageItem, StickyNoteItem))
                       and not getattr(i, 'is_anchor', False)]
            if not targets:
                vp_pos = self._view.mapFromGlobal(QCursor.pos())
                scene_pos = self._view.mapToScene(vp_pos)
                for it in self._scene.items(scene_pos):
                    if isinstance(it, (CardItem, ImageItem, StickyNoteItem)) and not getattr(it, 'is_anchor', False):
                        targets = [it]
                        break
            if targets:
                self._push_undo()
            for item in targets:
                others_z = [it.zValue() for it in self._scene.items()
                            if isinstance(it, (CardItem, DeckItem, ImageItem, DieItem, StickyNoteItem))
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
            self._toggle_hand_widget()

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

    def _dispatch_key_release(self, key_str: str) -> None:
        if key_str != self._settings.hotkey("shuffle"):
            return
        self._r_held = False
        # Clear keep_rolling on every die in the scene so the current
        # animation completes normally and the die settles.
        for item in self._scene.items():
            if isinstance(item, DieItem) and item.keep_rolling:
                item.keep_rolling = False

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self._fs_menu_timer.stop()
                self.menuBar().setVisible(True)
                if self._was_maximized:
                    self.showMaximized()
                else:
                    self.showNormal()
            else:
                self._was_maximized = self.isMaximized()
                self.showFullScreen()
                self.menuBar().setVisible(False)
                self._fs_menu_timer.start()
            event.accept()
            return
        super().keyPressEvent(event)

    def _check_fullscreen_menu(self) -> None:
        """Show/hide the menu bar based on cursor proximity to the top edge."""
        if not self.isFullScreen():
            self._fs_menu_timer.stop()
            return
        from PyQt6.QtGui import QCursor
        # Keep visible if a menu is currently open
        if self.menuBar().activeAction():
            return
        cursor_y = QCursor.pos().y()
        win_top  = self.geometry().y()
        should_show = cursor_y <= win_top + 3
        if should_show != self.menuBar().isVisible():
            self.menuBar().setVisible(should_show)

    def _rotate_held(self, direction: int) -> None:
        if self._view._held_item:
            item = self._view._held_item
            # Proxy widgets (e.g. sticky note editor) → resolve to parent item
            from PyQt6.QtWidgets import QGraphicsProxyWidget
            if isinstance(item, QGraphicsProxyWidget) and item.parentItem():
                item = item.parentItem()
            step = self._settings.display("rotation_step")
            if isinstance(item, (CardItem, ImageItem)):
                if direction > 0:
                    item.rotate_cw(step)
                else:
                    item.rotate_ccw(step)
            elif isinstance(item, DeckItem):
                delta = step * direction
                item.setRotation((item.rotation() + delta) % 360)
            elif isinstance(item, StickyNoteItem) and not item.locked:
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
        di.delete_requested.connect(self._on_deck_delete)
        di.delete_selected_requested.connect(self._delete_selected)
        di.open_recall_requested.connect(self._recall_dialog)

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
        dlg.remove_from_scene_requested.connect(self._on_image_remove_from_scene)
        self._image_cascade_col = 0
        self._image_cascade_row = 0
        self._image_library_dlg = dlg
        self._show_nonmodal(dlg)

    def _on_image_center_view(self, item: ImageItem) -> None:
        self._view.centerOn(item)

    def _on_image_spawn(self, path: str) -> None:
        from PyQt6.QtCore import QPoint
        grid_size = self._settings.canvas("grid_size")
        step = grid_size * 2
        top_left = self._view.mapToScene(QPoint(0, 0))
        vp_height = self._view.viewport().height()

        x = top_left.x() + self._image_cascade_col * step
        y = top_left.y() + self._image_cascade_row * step

        default_sz = self._settings.display("image_import_size")
        item = ImageItem(path, h_cells=default_sz, grid_size=grid_size)
        item.grid_snap = self._settings.canvas("grid_snap")
        item.setPos(QPointF(x, y))
        self._connect_image_item(item)
        self._scene.addItem(item)
        self._image_items.append(item)

        self._image_cascade_row += 1
        if top_left.y() + self._image_cascade_row * step + step > top_left.y() + vp_height:
            self._image_cascade_row = 0
            self._image_cascade_col += 1

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

    def _open_pdf_viewer(self) -> None:
        if self._pdf_dlg and self._pdf_dlg.isVisible():
            self._pdf_dlg.raise_()
            self._pdf_dlg.activateWindow()
            return
        dlg = PDFViewerWindow(self._settings, self)
        self._pdf_dlg = dlg
        self._show_nonmodal(dlg)

    # ------------------------------------------------------------------
    # Mini map
    # ------------------------------------------------------------------

    def _on_minimap_requested(self, item: ImageItem) -> None:
        path = item._image_path
        dlg = self._minimaps.get(path)
        if item.minimap:
            # Toggle on — open (or raise if somehow already open)
            if dlg and dlg.isVisible():
                dlg.raise_()
                dlg.activateWindow()
            else:
                self._open_minimap(item)
        else:
            # Toggle off — close
            if dlg:
                dlg.closed.disconnect()
                dlg.close()
                self._minimaps.pop(path, None)

    def _open_minimap(self, item: ImageItem, geometry=None) -> None:
        dlg = MiniMapDialog(self._scene, item, geometry=geometry, parent=self)
        self._minimaps[item._image_path] = dlg
        item.minimap = True

        def _on_closed():
            item.minimap = False
            item.minimap_geo = None
            self._minimaps.pop(item._image_path, None)

        dlg.closed.connect(_on_closed)
        dlg.show()

    def _sync_minimap_geos(self) -> None:
        """Snapshot current dialog geometries back onto their ImageItems before save."""
        for path, dlg in self._minimaps.items():
            for item in self._image_items:
                if item._image_path == path and dlg.isVisible():
                    item.minimap_geo = dlg.geometry_list()
                    break

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
        di.delete_selected_requested.connect(self._delete_selected)
        di.duplicate_requested.connect(self._on_die_duplicate)
        di.rolled.connect(self._on_die_rolled)
        di.roll_group_requested.connect(self._on_die_group_rolled)
        di.accent_apply_requested.connect(self._on_die_accent_apply_requested)

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
        from PyQt6.QtCore import QPoint
        grid_size = self._settings.canvas("grid_size")
        step = grid_size * 2
        top_left = self._view.mapToScene(QPoint(0, 0))
        vp_height = self._view.viewport().height()

        x = top_left.x() + self._image_cascade_col * step
        y = top_left.y() + self._image_cascade_row * step

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
        new_item.setPos(QPointF(x, y))
        self._connect_image_item(new_item)
        self._scene.addItem(new_item)
        self._image_items.append(new_item)

        self._image_cascade_row += 1
        if top_left.y() + self._image_cascade_row * step + step > top_left.y() + vp_height:
            self._image_cascade_row = 0
            self._image_cascade_col += 1

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

    def _on_die_group_rolled(self, dice: list) -> None:
        """Log a multi-die roll as a single line entry."""
        self._append_roll_log(list(dice))

    def _on_die_accent_apply_requested(self, payload) -> None:
        """Apply a new accent (Color 1) to the selected dice."""
        try:
            dice, accent_hex, accent_name = payload
        except Exception:
            return
        if not dice:
            return

        self._push_undo()

        # Group by original dice set so we only create one derived set per set.
        by_set: dict[str, list[DieItem]] = {}
        for d in dice:
            by_set.setdefault(d.set_name, []).append(d)

        import uuid as _uuid
        for old_set_name, dice_in_set in by_set.items():
            orig = self._dice_manager.get_set(old_set_name)
            die_types = {d.die_type for d in dice_in_set}

            if orig is None:
                colors = {dt: accent_hex for dt in die_types}
                new_set_name = f"{old_set_name} (accent {accent_name}) {_uuid.uuid4().hex[:6]}"
                new_ds = DiceSet(name=new_set_name, colors=colors, is_builtin=False)
            else:
                # Clone all per-die specs, overriding Color 1.
                colors = {}
                for dt, raw in orig.colors.items():
                    if isinstance(raw, str):
                        colors[dt] = accent_hex
                    elif isinstance(raw, dict):
                        spec = dict(raw)
                        spec["color1"] = accent_hex
                        colors[dt] = spec
                    else:
                        colors[dt] = accent_hex

                # Ensure die types present on the canvas are always defined.
                for dt in die_types:
                    colors.setdefault(dt, accent_hex)

                new_set_name = f"{orig.name} (accent {accent_name}) {_uuid.uuid4().hex[:6]}"
                new_ds = DiceSet(name=new_set_name, colors=colors, is_builtin=False)

            self._dice_manager.add_or_replace_set(new_ds)

            for d in dice_in_set:
                d.set_name = new_ds.name
                d.update()

    def _append_roll_log(self, dice: list) -> None:
        """Build and store a roll log entry for the given dice (using _final_value)."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")

        preset_map = {hx.lower(): nm for nm, hx in DieItem._accent_presets()}

        def _die_color_name(d: DieItem) -> str:
            ds = self._dice_manager.get_set(getattr(d, "set_name", ""))
            if not ds:
                return "Custom"
            raw = ds.colors.get(d.die_type)
            if raw is None:
                raw = next(iter(ds.colors.values()), "#ffffff")
            if isinstance(raw, str):
                return preset_map.get(raw.lower(), "Custom")
            if isinstance(raw, dict):
                c1 = raw.get("color1", "#ffffff")
                return preset_map.get(str(c1).lower(), "Custom")
            return "Custom"

        dice_entries = [
            {"type": d.die_type, "value": d._final_value, "color_name": _die_color_name(d)}
            for d in dice
        ]
        total = sum(e["value"] for e in dice_entries)
        self._roll_log.append({
            "time": time_str,
            "dice": dice_entries,
            "total": total,
        })
        if self._roll_log_dlg and self._roll_log_dlg.isVisible():
            self._roll_log_dlg._refresh()

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
        item.delete_selected_requested.connect(self._delete_selected)
        item.duplicate_requested.connect(self._on_image_duplicate)
        item.resize_requested.connect(self._on_image_resize)
        item.localize_requested.connect(lambda img: self._localize_image_items([img]))
        item.image_hovered.connect(self._on_image_hovered)
        item.image_unhovered.connect(self._on_image_unhovered)
        item.minimap_requested.connect(self._on_minimap_requested)
        item.update_measure_settings(
            self._settings.measurement("cell_value"),
            self._settings.measurement("cell_unit"),
            self._settings.measurement("decimals"),
        )

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

    def _on_image_remove_from_scene(self, items: list) -> None:
        for item in items:
            self._on_image_delete(item)

    def _on_image_resize(self, item: ImageItem) -> None:
        dlg = ImageResizeDialog(item._w_cells, item._h_cells,
                                aspect_ratio=item._aspect_ratio, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            item.resize(dlg.w_cells, dlg.h_cells)

    # ------------------------------------------------------------------
    # Sticky notes
    # ------------------------------------------------------------------

    def _place_sticky_note(self) -> None:
        """Place a new sticky note at the canvas center using current defaults."""
        grid_size = self._settings.canvas("grid_size")
        center = self._view.mapToScene(self._view.viewport().rect().center())
        item = StickyNoteItem(
            w_cells=3.0, h_cells=3.0, grid_size=grid_size,
            note_color  = self._settings.sticky("default_note_color"),
            font_family = self._settings.sticky("default_font_family"),
            font_size   = self._settings.sticky("default_font_size"),
            font_color  = self._settings.sticky("default_font_color"),
        )
        item.grid_snap = self._settings.canvas("grid_snap")
        item.setPos(center.x() - item._px_w() / 2, center.y() - item._px_h() / 2)
        item.delete_requested.connect(self._on_sticky_delete)
        item.resize_requested.connect(self._on_sticky_resize)
        item.settings_requested.connect(self._open_sticky_settings)
        item.copy_requested.connect(self._copy_selected)
        item.paste_requested.connect(self._paste_clipboard)
        item.delete_selected_requested.connect(self._delete_selected)
        self._scene.addItem(item)
        self._sticky_notes.append(item)

    def _on_sticky_delete(self, item: "StickyNoteItem") -> None:
        if item in self._sticky_notes:
            self._sticky_notes.remove(item)
        if item.scene():
            self._scene.removeItem(item)

    def _on_sticky_resize(self, item: "StickyNoteItem") -> None:
        dlg = ImageResizeDialog(item._w_cells, item._h_cells,
                                aspect_ratio=item._w_cells / max(item._h_cells, 0.01),
                                parent=self)
        dlg.setWindowTitle("Resize Sticky Note")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            item.resize(dlg.w_cells, dlg.h_cells)

    def _open_sticky_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self,
                             sticky_notes=self._sticky_notes)
        dlg.select_tab("Sticky Notes")
        dlg.finished.connect(lambda result: self._on_settings_closed(result))
        self._show_nonmodal(dlg)

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
        item.copy_requested.connect(self._copy_selected)
        item.delete_requested.connect(self._on_card_delete)
        item.delete_selected_requested.connect(self._delete_selected)
        self._scene.addItem(item)
        self._canvas_cards[card_data.image_path] = item
        return item

    # ------------------------------------------------------------------
    # Signal handlers – deck → canvas/hand
    # ------------------------------------------------------------------

    def _on_draw_to_hand(self, cards: list) -> None:
        for card_data in cards:
            rotation = 180.0 if getattr(card_data, "reversed", False) else 0.0
            self._hand.add_card(card_data, face_up=True, rotation=rotation)
        self._status.showMessage(f"Drew {len(cards)} card(s) to hand.", 2000)

    def _on_draw_to_canvas(self, cards: list, near_pos: QPointF, deck_card_h: int = CARD_H) -> None:
        spread = 130
        y_offset = deck_card_h + 16
        for i, card_data in enumerate(cards):
            item = self._create_card_item(card_data, face_up=True)
            if getattr(card_data, "reversed", False):
                item.setRotation(180.0)
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
                rotation  = item.rotation() if item.rotation() != 0 else (
                    180.0 if getattr(card_data, "reversed", False) else 0.0
                )
                self._canvas_cards.pop(card_data.image_path, None)
                self._scene.removeItem(item)
                self._hand.add_card(card_data, face_up=face_up, rotation=rotation)
            elif isinstance(item, DeckItem):
                # Move all remaining cards in the deck/stack to hand
                for card_data in list(item.deck_model.cards):
                    rot = 180.0 if getattr(card_data, "reversed", False) else 0.0
                    self._hand.add_card(card_data, face_up=item.face_up, rotation=rot)
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
                pix = QPixmap(path)
                if getattr(card_data, "reversed", False):
                    from PyQt6.QtGui import QTransform
                    pix = pix.transformed(QTransform().rotate(180))
                self._magnify.set_card(pix)
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
        deck_ids = set(opts["deck_ids"])
        if not deck_ids:
            return

        # Remove canvas cards belonging to recalled decks
        for item in list(self._scene.items()):
            if isinstance(item, CardItem):
                if item.card_data.deck_id in deck_ids:
                    self._canvas_cards.pop(item.card_data.image_path, None)
                    self._scene.removeItem(item)

        # Handle hand cards
        if opts["include_hand"]:
            for hs in list(self._hand.hand_cards):
                if hs.card_data.deck_id in deck_ids:
                    self._hand.remove_card_by_id(hs.card_data.id)

        # Collect hand card IDs per deck (for exclusion if include_hand is False)
        hand_card_ids: dict = {}  # deck_id → set of card ids in hand
        if not opts["include_hand"]:
            for hs in self._hand.hand_cards:
                if hs.card_data.deck_id in deck_ids:
                    hand_card_ids.setdefault(hs.card_data.deck_id, set()).add(hs.card_data.id)

        # Restore each recalled deck
        for deck_id in deck_ids:
            dm = self._deck_models.get(deck_id)
            if dm:
                excluded = set()
                if not opts["restore_deleted"]:
                    excluded |= dm.deleted_card_ids
                if not opts["include_hand"]:
                    excluded |= hand_card_ids.get(deck_id, set())
                dm.cards = [c for c in dm.all_cards if c.id not in excluded]
                for card in dm.cards:
                    card.reversed = False
                if opts["restore_deleted"]:
                    dm.deleted_card_ids.clear()

        if opts["shuffle_after"]:
            for deck_id in deck_ids:
                dm = self._deck_models.get(deck_id)
                if dm:
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
        self._sticky_notes.clear()
        self._roll_log.clear()
        self._frozen_measurements.clear()
        self._cancel_active_measurement()
        self._drawing_items.clear()
        self._dice_cascade_col = 0
        self._dice_cascade_row = 0
        self._image_cascade_col = 0
        self._image_cascade_row = 0
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
        self._sync_minimap_geos()
        state = SessionManager.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            roll_log=self._roll_log,
            image_items=self._image_items,
            measurement_items=self._frozen_measurements,
            drawing_items=self._drawing_items,
            sticky_notes=self._sticky_notes,
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
            di.face_up          = deck_dict.get("face_up", False)
            di.is_stack         = deck_dict.get("is_stack", False)
            di.reversal_enabled = deck_dict.get("reversal_enabled", False)
            di.grid_snap        = self._settings.canvas("grid_snap")
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
            item.measure_movement = img_dict.get("measure_movement", False)
            item.minimap_geo = img_dict.get("minimap_geo", None)
            # Restore anchor state (must happen after addItem for scene to be set)
            self._connect_image_item(item)
            self._scene.addItem(item)
            if img_dict.get("is_anchor", False):
                item.is_anchor = True
                item._shadow.setEnabled(False)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
            self._image_items.append(item)
            if img_dict.get("minimap", False):
                self._open_minimap(item, geometry=item.minimap_geo)
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

        # Restore frozen measurement items
        for mi in list(self._frozen_measurements):
            if mi.scene():
                self._scene.removeItem(mi)
        self._frozen_measurements.clear()
        for md in data.get("measurements", []):
            try:
                item = MeasurementItem.from_dict(md)
                self._scene.addItem(item)
                item.delete_requested.connect(lambda i=item: self._remove_measurement(i))
                self._frozen_measurements.append(item)
            except Exception:
                pass

        # Restore drawing items
        self._drawing_items.clear()
        for dd in data.get("drawings", []):
            try:
                from .drawing_item import DrawingStrokeItem, DrawingShapeItem
                dtype = dd.get("type")
                if dtype == "stroke":
                    item = DrawingStrokeItem.from_dict(dd)
                    self._scene.addItem(item)
                    self._drawing_items.append(item)
                elif dtype == "shape":
                    item = DrawingShapeItem.from_dict(dd)
                    item.delete_requested.connect(lambda i=item: self._remove_drawing_item(i))
                    item.customize_requested.connect(self._on_drawing_customize_requested)
                    self._scene.addItem(item)
                    self._drawing_items.append(item)
            except Exception:
                pass

        # Restore sticky notes
        self._sticky_notes.clear()
        for sd in data.get("sticky_notes", []):
            try:
                item = StickyNoteItem.from_state_dict(
                    sd, grid_size=self._settings.canvas("grid_size")
                )
                item.delete_requested.connect(self._on_sticky_delete)
                item.resize_requested.connect(self._on_sticky_resize)
                item.settings_requested.connect(self._open_sticky_settings)
                item.copy_requested.connect(self._copy_selected)
                item.paste_requested.connect(self._paste_clipboard)
                item.delete_selected_requested.connect(self._delete_selected)
                self._scene.addItem(item)
                self._sticky_notes.append(item)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        """Snapshot current state onto the undo stack (configurable max levels)."""
        from .session_manager import SessionManager as _SM
        state = _SM.build_state(
            self._view, self._scene, self._hand,
            self._deck_models, self._deck_items,
            die_items=self._die_items,
            image_items=self._image_items,
            drawing_items=self._drawing_items,
            sticky_notes=self._sticky_notes,
        )
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._settings.system("undo_stack_size"):
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
            drawing_items=self._drawing_items,
            sticky_notes=self._sticky_notes,
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
            drawing_items=self._drawing_items,
            sticky_notes=self._sticky_notes,
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

    def _on_sys_clipboard_changed(self) -> None:
        import time as _time
        self._sys_clipboard_time = _time.monotonic()

    def _on_card_delete(self, item: CardItem) -> None:
        self._push_undo()
        dm = self._deck_models.get(item.card_data.deck_id)
        if dm:
            dm.deleted_card_ids.add(item.card_data.id)
        self._canvas_cards.pop(item.card_data.image_path, None)
        self._scene.removeItem(item)

    def _on_deck_delete(self, di: DeckItem) -> None:
        self._push_undo()
        deck_id = di.deck_model.id
        self._scene.removeItem(di)
        self._deck_items.pop(deck_id, None)
        self._deck_models.pop(deck_id, None)

    def _copy_selected(self) -> None:
        """Serialize selected copyable items into the internal clipboard."""
        entries = []
        for item in self._scene.selectedItems():
            if isinstance(item, CardItem):
                entries.append({"type": "card", "state": item.to_state_dict()})
            elif isinstance(item, ImageItem):
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
            elif isinstance(item, StickyNoteItem):
                entries.append({"type": "sticky", "state": item.to_state_dict()})
        if entries:
            import time as _time
            self._clipboard = entries
            self._clipboard_time = _time.monotonic()

    def _paste_clipboard(self, scene_pos=None) -> None:
        """Paste whichever clipboard was modified most recently —
        the internal canvas clipboard or the system image clipboard.
        scene_pos: optional QPointF; if None, uses current cursor position."""
        sys_has_image = not QApplication.clipboard().image().isNull()
        use_internal = (
            bool(self._clipboard)
            and (not sys_has_image or self._clipboard_time >= self._sys_clipboard_time)
        )
        if not use_internal:
            self._paste_system_image()
            return
        import uuid as _uuid
        from PyQt6.QtGui import QCursor
        if scene_pos is None:
            vp_pos = self._view.mapFromGlobal(QCursor.pos())
            scene_pos = self._view.mapToScene(vp_pos)
        cursor_scene = scene_pos

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
            if t == "card":
                dm = self._deck_models.get(s.get("deck_id"))
                if dm:
                    cd = dm.card_by_image_path(s["image_path"])
                    if cd is None:
                        continue
                    item = CardItem(cd, face_up=s.get("face_up", True))
                    item.grid_snap = s.get("grid_snap", False)
                    item.grid_size = self._settings.canvas("grid_size")
                    item.setRotation(s.get("rotation", 0))
                    item._base_z = s.get("z", 1.0)
                    item.send_to_hand.connect(self._on_card_send_to_hand)
                    item.return_to_deck.connect(self._on_card_return_to_deck)
                    item.card_hovered.connect(self._on_card_hovered)
                    item.card_unhovered.connect(self._on_card_unhovered)
                    item.stack_requested.connect(self._on_stack_requested)
                    item.copy_requested.connect(self._copy_selected)
                    item.delete_requested.connect(self._on_card_delete)
                    item.delete_selected_requested.connect(self._delete_selected)
                    item.setPos(QPointF(s["x"], s["y"]) + offset)
                    self._scene.addItem(item)
                    self._canvas_cards[cd.image_path] = item
                    item.setSelected(True)
            elif t == "image":
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
                new_di.face_up          = s.get("face_up", False)
                new_di.is_stack         = s.get("is_stack", False)
                new_di.reversal_enabled = s.get("reversal_enabled", False)
                new_di.grid_snap        = s.get("grid_snap", False)
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
            elif t == "sticky":
                note = StickyNoteItem.from_state_dict(
                    s, grid_size=self._settings.canvas("grid_size")
                )
                note.setPos(QPointF(s["x"], s["y"]) + offset)
                note.delete_requested.connect(self._on_sticky_delete)
                note.resize_requested.connect(self._on_sticky_resize)
                note.settings_requested.connect(self._open_sticky_settings)
                note.copy_requested.connect(self._copy_selected)
                note.paste_requested.connect(self._paste_clipboard)
                note.delete_selected_requested.connect(self._delete_selected)
                self._scene.addItem(note)
                self._sticky_notes.append(note)
                note.setSelected(True)

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
                dm = self._deck_models.get(item.card_data.deck_id)
                if dm:
                    dm.deleted_card_ids.add(item.card_data.id)
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
            elif isinstance(item, MeasurementItem):
                if item in self._frozen_measurements:
                    self._frozen_measurements.remove(item)
                self._scene.removeItem(item)
            elif isinstance(item, StickyNoteItem):
                if item in self._sticky_notes:
                    self._sticky_notes.remove(item)
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
        self._show_nonmodal(dlg)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self,
                             sticky_notes=self._sticky_notes)
        dlg.finished.connect(lambda result: self._on_settings_closed(result))
        self._show_nonmodal(dlg)

    def _on_settings_closed(self, result: int) -> None:
        if result == QDialog.DialogCode.Accepted:
            self._hand.set_max_card_width(self._settings.display("max_hand_card_width"))
            self._reposition_hand()
            self._update_hand_zone()
            self._hand.update()
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
        """Apply the static UI palette application-wide."""
        QApplication.instance().setStyleSheet(_theme.get_app_stylesheet())
        self._zoom_label.setStyleSheet("color: #8C8D9B; margin-right: 8px;")
        self._hotkey_hint_label.setStyleSheet("color: #8C8D9B; margin-left: 6px;")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _on_zoom_changed(self, scale: float) -> None:
        self._zoom_label.setText(f"{int(scale * 100)} %")

    def _on_selection_changed(self) -> None:
        count = len(self._scene.selectedItems())
        self._selection_label.setText(f"{count} selected" if count > 0 else "")

    # ------------------------------------------------------------------
    # Window state & geometry
    # ------------------------------------------------------------------

    def _show_startup_dialog(self) -> None:
        sessions = self._session.list_sessions()
        dlg = StartupDialog(sessions, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        # Save current session before switching away (if it has a known path)
        if self._session_path:
            self._do_save(self._session_path)
        if dlg.selected_path:
            # Load chosen session
            data = self._session.load(dlg.selected_path)
            if data:
                self._load_state(data)
                self._session_path = Path(dlg.selected_path)
                self.setWindowTitle(f"SoloCanvas – {self._session_path.stem}")
        else:
            # New Session — current session already saved above; start fresh
            self._clear_session()

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
        if hasattr(self, "_toolbar"):
            self._toolbar._reposition()
        self._reposition_hand()
        self._update_hand_zone()
        if hasattr(self, "_magnify") and self._magnify.isVisible():
            vp = self._view.viewport()
            self._magnify.reposition(
                vp.size(),
                self._settings.display("magnify_corner"),
            )
        if hasattr(self, "_dim_bubble"):
            self._reposition_dim_bubble()

    # ------------------------------------------------------------------
    # Measurement tool
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Hand widget helpers
    # ------------------------------------------------------------------

    def _toggle_hand_widget(self) -> None:
        self._hand.toggle_visible()

    def _reposition_hand(self) -> None:
        if not hasattr(self, "_hand"):
            return
        central = self.centralWidget()
        if central is None:
            return
        self._hand.reposition(central.width(), central.height())

    def _update_hand_zone(self) -> None:
        """Tell the canvas view where the hand zone is for drag detection."""
        if hasattr(self, "_hand") and hasattr(self, "_view"):
            self._view.set_hand_zone(self._hand.height() + _HAND_MARGIN_BOTTOM + 20)

    def _on_measurement_toggled(self, active: bool) -> None:
        """M key pressed: sync toolbar and cursor."""
        if active:
            self._finalize_active_draw()
            self._view.drawing_active = False
            self._close_draw_settings()
            self._toolbar.set_active_tool("measure")
            self._view.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._toolbar.set_active_tool("pointer")
            self._view.unsetCursor()
            self._cancel_active_measurement()

    def _on_drawing_toggled(self, active: bool) -> None:
        if active:
            # When using draw tool normally, dialog values apply to new drawings,
            # not to existing selected shapes.
            self._apply_draw_settings_to_selection = False
            self._draw_customize_needs_undo = False
            self._cancel_active_measurement()
            self._view.measurement_active = False
            self._toolbar.set_active_tool("draw")
            self._view.setCursor(Qt.CursorShape.CrossCursor)
            self._open_draw_settings()
        else:
            self._finalize_active_draw()
            self._close_draw_settings()
            self._toolbar.set_active_tool("pointer")
            self._view.unsetCursor()

    def _on_toolbar_tool_changed(self, tool: str) -> None:
        """Toolbar Pointer/Measure/Draw button clicked — sync view state."""
        self._view.measurement_active = (tool == "measure")
        self._view.drawing_active = (tool == "draw")
        if tool == "measure":
            self._view.setCursor(Qt.CursorShape.CrossCursor)
            self._cancel_active_measurement()
            self._finalize_active_draw()
            self._close_draw_settings()
        elif tool == "draw":
            self._apply_draw_settings_to_selection = False
            self._draw_customize_needs_undo = False
            self._view.setCursor(Qt.CursorShape.CrossCursor)
            self._cancel_active_measurement()
            self._open_draw_settings()
        else:
            self._view.unsetCursor()
            self._cancel_active_measurement()
            self._finalize_active_draw()
            self._close_draw_settings()

    def _on_measure_mode_changed(self, mode: str) -> None:
        self._settings.set_measurement("mode", mode)
        self._settings.save()

    def _on_measure_type_changed(self, mtype: str) -> None:
        self._settings.set_measurement("measure_type", mtype)
        self._settings.save()
        self._update_measure_menu_state()

    def _on_canvas_interaction(self) -> None:
        """Clear non-persistent frozen measurements when the canvas is clicked in pointer mode."""
        if not self._view.measurement_active and not self._measure_persistent:
            self._clear_all_measurements()

    def _on_measure_persistent_toggled(self, checked: bool) -> None:
        self._measure_persistent = checked

    def _clear_all_measurements(self) -> None:
        for item in list(self._frozen_measurements):
            if item.scene():
                self._scene.removeItem(item)
        self._frozen_measurements.clear()

    def _on_measurement_press(self, scene_pos) -> None:
        """Start a new measurement item; clear any previous frozen measurement."""
        self._cancel_active_measurement()
        if not self._measure_persistent:
            self._clear_all_measurements()
        m = self._settings
        item = MeasurementItem(
            origin       = scene_pos,
            measure_type = m.measurement("measure_type"),
            mode         = m.measurement("mode"),
            grid_size    = self._scene.grid_size,
            cell_value   = m.measurement("cell_value"),
            cell_unit    = m.measurement("cell_unit"),
            cone_angle   = m.measurement("cone_angle"),
            decimals     = m.measurement("decimals"),
        )
        self._scene.addItem(item)
        self._active_measurement = item
        self._dim_bubble.show()
        self._reposition_dim_bubble()

    def _on_measurement_move(self, scene_pos) -> None:
        """Update the active measurement and dimension bubble."""
        if self._active_measurement is not None:
            self._active_measurement.update_end(scene_pos)
            self._dim_bubble.set_text(self._active_measurement.dimension_text())

    def _on_measurement_waypoint(self) -> None:
        """Space pressed during line measurement — pin current endpoint as a waypoint."""
        if self._active_measurement is not None:
            self._active_measurement.add_waypoint()

    def _on_measurement_release(self, scene_pos) -> None:
        """Freeze the active measurement onto the canvas."""
        if self._active_measurement is None:
            return
        item = self._active_measurement
        self._active_measurement = None
        item.update_end(scene_pos)
        item.freeze()
        item.delete_requested.connect(lambda i=item: self._remove_measurement(i))
        self._frozen_measurements.append(item)
        self._dim_bubble.hide()

    def _any_tool_active(self) -> bool:
        """Return True if any canvas tool (measure, draw, …) is currently active.
        Add new tool flags here when future tools are introduced."""
        return self._view.measurement_active or self._view.drawing_active

    def _escape_deactivate_tools(self) -> None:
        """Cancel any in-progress operation, clear non-persistent measurements,
        and return to Pointer mode.  Add new tool teardown here for future tools."""
        # Cancel in-progress operations
        if self._view.measurement_active:
            self._cancel_active_measurement()
            self._view._measuring = False
        if self._view.drawing_active:
            self._on_draw_cancel()
        # Clear non-persistent measurements
        if not self._measure_persistent:
            self._clear_all_measurements()
        # Deactivate all tools → pointer
        self._view.measurement_active = False
        self._view.drawing_active = False
        self._toolbar.set_active_tool("pointer")
        self._view.unsetCursor()
        self._close_draw_settings()

    def _cancel_active_measurement(self) -> None:
        if self._active_measurement is not None:
            if self._active_measurement.scene():
                self._scene.removeItem(self._active_measurement)
            self._active_measurement = None
        if hasattr(self, "_dim_bubble"):
            self._dim_bubble.hide()

    def _remove_measurement(self, item: MeasurementItem) -> None:
        if item in self._frozen_measurements:
            self._frozen_measurements.remove(item)
        if item.scene():
            self._scene.removeItem(item)

    def _reposition_dim_bubble(self) -> None:
        if not hasattr(self, "_dim_bubble"):
            return
        central = self.centralWidget()
        if central is None:
            return
        bw = self._dim_bubble.width()
        bh = self._dim_bubble.height()
        # Lower-left of the canvas view area (avoids magnify overlay at bottom-right)
        view_rect = self._view.geometry()
        margin = 12
        self._dim_bubble.move(
            view_rect.left() + margin,
            view_rect.bottom() - bh - margin,
        )

    # Measure menu helpers
    def _update_measure_menu_state(self) -> None:
        if not hasattr(self, "_measure_actions"):
            return
        current = self._settings.measurement("measure_type")
        for mtype, action in self._measure_actions.items():
            action.setChecked(mtype == current)
        if hasattr(self, "_measure_grid_action"):
            self._measure_grid_action.setChecked(
                self._settings.measurement("mode") == "grid"
            )

    # ------------------------------------------------------------------
    # Drawing tool handlers
    # ------------------------------------------------------------------

    def _open_draw_settings(self) -> None:
        if self._draw_settings_dlg is None:
            self._draw_settings_dlg = DrawingSettingsDialog(self._settings, self)
            self._draw_settings_dlg.settings_changed.connect(self._on_draw_settings_changed)
        self._draw_settings_dlg.show()
        self._draw_settings_dlg.raise_()

    def _close_draw_settings(self) -> None:
        if self._draw_settings_dlg is not None:
            self._draw_settings_dlg.hide()
        self._apply_draw_settings_to_selection = False
        self._draw_customize_needs_undo = False

    def _on_draw_settings_changed(self) -> None:
        if not getattr(self, "_apply_draw_settings_to_selection", False):
            return

        # Apply current dialog values to all selected shape drawings.
        selected_shapes = [
            i for i in self._scene.selectedItems()
            if isinstance(i, DrawingShapeItem)
        ]
        if not selected_shapes:
            return

        # Push undo once, on first user edit after opening via context menu.
        if getattr(self, "_draw_customize_needs_undo", False):
            self._push_undo()
            self._draw_customize_needs_undo = False

        from PyQt6.QtGui import QColor

        stroke_w = self._settings.drawing("stroke_width")
        stroke_hex = self._settings.drawing("stroke_color")
        fill_hex = self._settings.drawing("fill_color")
        fill_op = self._settings.drawing("fill_opacity")  # 0..100

        fill_alpha = int(fill_op * 255 / 100)

        for sh in selected_shapes:
            sh._stroke_width = stroke_w
            sh._stroke_color = QColor(stroke_hex)
            sh._fill_color = QColor(fill_hex)
            sh._fill_color.setAlpha(fill_alpha)
            sh.update()

    def _on_drawing_customize_requested(self) -> None:
        """Open DrawingSettingsDialog preloaded from selected shapes.

        Changes in the dialog are applied live to the selected shapes.
        """
        selected_shapes = [
            i for i in self._scene.selectedItems()
            if isinstance(i, DrawingShapeItem)
        ]
        if not selected_shapes:
            return

        first = selected_shapes[0]

        # Preload drawing settings from the first selected shape.
        # (When multiple are selected, subsequent edits apply to all.)
        fill_op = int(round(first._fill_color.alpha() * 100 / 255))
        self._settings.set_drawing("stroke_width", first._stroke_width)
        self._settings.set_drawing("stroke_color", first._stroke_color.name())
        self._settings.set_drawing("fill_color", first._fill_color.name())
        self._settings.set_drawing("fill_opacity", fill_op)
        self._settings.save()

        if self._draw_settings_dlg is None:
            self._open_draw_settings()
        else:
            self._draw_settings_dlg.refresh_from_settings()
            self._draw_settings_dlg.show()
            self._draw_settings_dlg.raise_()

        # Apply subsequent dialog edits to the selected shapes.
        self._apply_draw_settings_to_selection = True
        self._draw_customize_needs_undo = True

    def _on_draw_tool_changed(self, sub_tool: str) -> None:
        """Draw sub-tool button changed (freehand/circle/square/eraser)."""
        self._finalize_active_draw()
        self._settings.set_drawing("sub_tool", sub_tool)
        self._settings.save()

    def _on_draw_press(self, scene_pos) -> None:
        sub = self._settings.drawing("sub_tool")
        self._eraser_did_erase = False
        if sub == "eraser":
            self._erase_at(scene_pos, push_undo=False)
            return
        snap = self._settings.drawing("snap_to_grid") and self._settings.canvas("grid_enabled")
        if snap:
            scene_pos = self._snap_to_grid(scene_pos)
        if sub == "freehand":
            self._active_draw_points = [scene_pos]
            # Create a temporary stroke item to show live feedback
            from .drawing_item import DrawingStrokeItem, make_smooth_path
            from PyQt6.QtCore import QPointF
            path = make_smooth_path([scene_pos])
            stroke = DrawingStrokeItem(
                path,
                self._settings.drawing("stroke_color"),
                self._settings.drawing("stroke_width"),
            )
            self._scene.addItem(stroke)
            self._active_draw_stroke = stroke
        elif sub in ("circle", "square"):
            self._draw_start_pos = scene_pos
            from .drawing_item import DrawingShapeItem
            from PyQt6.QtCore import QRectF
            item = DrawingShapeItem(
                shape        = sub,
                rect         = QRectF(scene_pos, scene_pos),
                stroke_color = self._settings.drawing("stroke_color"),
                stroke_width = self._settings.drawing("stroke_width"),
                fill_color   = self._settings.drawing("fill_color"),
                fill_opacity = self._settings.drawing("fill_opacity"),
            )
            self._scene.addItem(item)
            self._active_draw_shape = item

    def _on_draw_move(self, scene_pos) -> None:
        sub = self._settings.drawing("sub_tool")
        if sub == "eraser":
            self._erase_at(scene_pos, push_undo=False)
            return
        snap = self._settings.drawing("snap_to_grid") and self._settings.canvas("grid_enabled")
        if snap:
            scene_pos = self._snap_to_grid(scene_pos)
        if sub == "freehand" and self._active_draw_stroke is not None:
            self._active_draw_points.append(scene_pos)
            from .drawing_item import make_smooth_path
            path = make_smooth_path(self._active_draw_points)
            self._active_draw_stroke._path = path
            self._active_draw_stroke.prepareGeometryChange()
            self._active_draw_stroke.update()
        elif sub in ("circle", "square") and self._active_draw_shape is not None:
            from PyQt6.QtCore import QRectF
            rect = QRectF(self._draw_start_pos, scene_pos).normalized()
            self._active_draw_shape.update_rect(rect)

    def _on_draw_release(self, scene_pos) -> None:
        sub = self._settings.drawing("sub_tool")
        if sub == "eraser":
            if getattr(self, "_eraser_did_erase", False):
                self._push_undo()
            return
        snap = self._settings.drawing("snap_to_grid") and self._settings.canvas("grid_enabled")
        if snap:
            scene_pos = self._snap_to_grid(scene_pos)
        self._push_undo()
        if sub == "freehand" and self._active_draw_stroke is not None:
            self._active_draw_points.append(scene_pos)
            from .drawing_item import make_smooth_path
            path = make_smooth_path(self._active_draw_points)
            self._active_draw_stroke._path = path
            self._active_draw_stroke._points = list(self._active_draw_points)
            self._active_draw_stroke.prepareGeometryChange()
            self._active_draw_stroke.update()
            self._drawing_items.append(self._active_draw_stroke)
            self._active_draw_stroke = None
            self._active_draw_points = []
        elif sub in ("circle", "square") and self._active_draw_shape is not None:
            from PyQt6.QtCore import QRectF
            rect = QRectF(self._draw_start_pos, scene_pos).normalized()
            # Discard zero-size shapes
            if rect.width() < 2 and rect.height() < 2:
                self._scene.removeItem(self._active_draw_shape)
                self._undo_stack.pop() if self._undo_stack else None
            else:
                self._active_draw_shape.update_rect(rect)
                self._active_draw_shape.delete_requested.connect(
                    lambda i=self._active_draw_shape: self._remove_drawing_item(i)
                )
                self._active_draw_shape.customize_requested.connect(
                    self._on_drawing_customize_requested
                )
                self._drawing_items.append(self._active_draw_shape)
            self._active_draw_shape = None
            self._draw_start_pos = None

    def _finalize_active_draw(self) -> None:
        """Commit any in-progress drawing to the canvas (called on tool switch)."""
        if self._active_draw_stroke is not None:
            if len(self._active_draw_points) >= 2:
                from .drawing_item import make_smooth_path
                path = make_smooth_path(self._active_draw_points)
                self._active_draw_stroke._path = path
                self._active_draw_stroke._points = list(self._active_draw_points)
                self._active_draw_stroke.prepareGeometryChange()
                self._active_draw_stroke.update()
                self._push_undo()
                self._drawing_items.append(self._active_draw_stroke)
            else:
                if self._active_draw_stroke.scene():
                    self._scene.removeItem(self._active_draw_stroke)
            self._active_draw_stroke = None
            self._active_draw_points = []
        if self._active_draw_shape is not None:
            rect = self._active_draw_shape._rect
            if rect.width() >= 2 or rect.height() >= 2:
                self._push_undo()
                self._active_draw_shape.delete_requested.connect(
                    lambda i=self._active_draw_shape: self._remove_drawing_item(i)
                )
                self._active_draw_shape.customize_requested.connect(
                    self._on_drawing_customize_requested
                )
                self._drawing_items.append(self._active_draw_shape)
            else:
                if self._active_draw_shape.scene():
                    self._scene.removeItem(self._active_draw_shape)
            self._active_draw_shape = None
            self._draw_start_pos = None

    def _on_draw_cancel(self) -> None:
        """Discard any in-progress freehand stroke or shape without committing."""
        if self._active_draw_stroke is not None:
            if self._active_draw_stroke.scene():
                self._scene.removeItem(self._active_draw_stroke)
            self._active_draw_stroke = None
            self._active_draw_points = []
        if self._active_draw_shape is not None:
            if self._active_draw_shape.scene():
                self._scene.removeItem(self._active_draw_shape)
            self._active_draw_shape = None
            self._draw_start_pos = None

    def _erase_at(self, scene_pos, push_undo: bool = True) -> None:
        """Remove any drawing item that contains the given scene position."""
        from .drawing_item import DrawingStrokeItem, DrawingShapeItem
        from PyQt6.QtCore import QRectF
        hit_rect = QRectF(scene_pos.x() - 8, scene_pos.y() - 8, 16, 16)
        # Use bounding-rect mode so strokes (whose shape() is empty) are found
        items_hit = self._scene.items(
            hit_rect, Qt.ItemSelectionMode.IntersectsItemBoundingRect
        )
        removed = False
        for item in items_hit:
            if isinstance(item, (DrawingStrokeItem, DrawingShapeItem)):
                if item in self._drawing_items:
                    self._drawing_items.remove(item)
                self._scene.removeItem(item)
                removed = True
        if removed:
            self._eraser_did_erase = True
            if push_undo:
                self._push_undo()

    def _snap_to_grid(self, scene_pos):
        """Snap a scene QPointF to the nearest grid cell corner."""
        from PyQt6.QtCore import QPointF
        gs = self._settings.canvas("grid_size")
        if gs <= 0:
            return scene_pos
        x = round(scene_pos.x() / gs) * gs
        y = round(scene_pos.y() / gs) * gs
        return QPointF(x, y)

    def _remove_drawing_item(self, item) -> None:
        self._push_undo()
        if item in self._drawing_items:
            self._drawing_items.remove(item)
        if item.scene():
            self._scene.removeItem(item)

    def _clear_all_drawings(self) -> None:
        """Delete all drawing objects from the canvas (with confirmation)."""
        if not self._drawing_items:
            return
        resp = QMessageBox.question(
            self, "Clear All Drawings",
            "Delete all drawing objects? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        for item in list(self._drawing_items):
            if item.scene():
                self._scene.removeItem(item)
        self._drawing_items.clear()

    def _set_measure_type_from_menu(self, mtype: str) -> None:
        self._settings.set_measurement("measure_type", mtype)
        self._settings.save()
        self._toolbar.set_measure_type(mtype)
        self._update_measure_menu_state()

    def _set_measure_mode_from_menu(self, mode: str) -> None:
        self._settings.set_measurement("mode", mode)
        self._settings.save()
        self._toolbar.set_measure_mode(mode)
        self._update_measure_menu_state()

    def _open_measurement_settings(self) -> None:
        dlg = MeasurementSettingsDialog(self._settings, self)
        if dlg.exec():
            self._update_measure_menu_state()
            self._refresh_measure_settings()

    def _refresh_measure_settings(self) -> None:
        """Push updated cell_value/cell_unit/decimals to all image items immediately."""
        m = self._settings
        cv  = m.measurement("cell_value")
        cu  = m.measurement("cell_unit")
        dec = m.measurement("decimals")
        for item in self._image_items:
            item.update_measure_settings(cv, cu, dec)

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
                    measurement_items=self._frozen_measurements,
                    drawing_items=self._drawing_items,
                    sticky_notes=self._sticky_notes,
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
