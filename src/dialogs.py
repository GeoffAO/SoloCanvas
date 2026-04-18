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

"""All application dialogs: Settings, Recall, Session picker, Background."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QSize, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout,
    QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

_DIALOG_STYLE = """
QDialog, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
}

/* ── Tabs ── */
QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 4px;
    top: -1px;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 7px 18px;
    border: 1px solid #313244;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #313244; color: #cdd6f4; border-color: #45475a; }
QTabBar::tab:hover:!selected { background: #252535; color: #cdd6f4; }

/* ── Tables ── */
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    border: 1px solid #45475a;
    gridline-color: #313244;
    selection-background-color: #313244;
}
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background: #313244; color: #cdd6f4; }
QHeaderView::section {
    background-color: #252535;
    color: #cdd6f4;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #313244;
    border-bottom: 1px solid #45475a;
    font-weight: bold;
}

/* ── List widgets ── */
QListWidget {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    outline: none;
}
QListWidget::item { padding: 5px 6px; border-radius: 3px; color: #cdd6f4; }
QListWidget::item:selected { background: #313244; }
QListWidget::item:hover:!selected { background: #252535; }

/* ── Buttons ── */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 14px;
    min-width: 60px;
}
QPushButton:hover  { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { color: #585b70; border-color: #313244; }
QPushButton:default {
    border: 1px solid #89b4fa;
    background-color: #1e3a5f;
}
QPushButton:default:hover { background-color: #264b78; }

/* ── Slider ── */
QSlider::groove:horizontal {
    background: #313244;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #89b4fa;
    width: 16px; height: 16px;
    border-radius: 8px;
    margin: -5px 0;
}
QSlider::handle:horizontal:hover { background: #b4d0fa; }
QSlider::sub-page:horizontal { background: #4a5588; border-radius: 3px; }

/* ── Combo box ── */
QComboBox {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
    min-width: 120px;
}
QComboBox:hover { border-color: #6c7086; }
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #313244;
    outline: none;
}

/* ── Line edit ── */
QLineEdit {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}
QLineEdit:focus { border-color: #89b4fa; }

/* ── Checkboxes ── */
QCheckBox { color: #cdd6f4; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
}
QCheckBox::indicator:unchecked {
    background: #181825;
    border: 1px solid #45475a;
}
QCheckBox::indicator:unchecked:hover { border-color: #89b4fa; }
QCheckBox::indicator:checked {
    background: #89b4fa;
    border: 1px solid #89b4fa;
    image: none;
}

/* ── Labels ── */
QLabel { color: #cdd6f4; }

/* ── Group boxes ── */
QGroupBox {
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    color: #89b4fa;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #181825;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #585b70;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #6c7086; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: #181825;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #585b70;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #6c7086; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* ── List widget ── */
QListWidget {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    outline: none;
}
QListWidget::item { padding: 6px 8px; border-radius: 3px; }
QListWidget::item:selected { background: #313244; color: #cdd6f4; }
QListWidget::item:hover:!selected { background: #252535; }
"""


# ==============================================================================
# Settings Dialog
# ==============================================================================

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, sticky_notes=None, initial_tab=None):
        super().__init__(parent)
        self._settings = settings
        self._sticky_notes = sticky_notes or []
        self.setWindowTitle("Settings")
        self.setMinimumSize(680, 500)
        self.setWindowModality(Qt.WindowModality.NonModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._make_hotkeys_tab(),  "Hotkeys")
        self._tabs.addTab(self._make_canvas_tab(),   "Canvas")
        self._tabs.addTab(self._make_display_tab(),  "Display")
        self._tabs.addTab(self._make_system_tab(),   "System")
        self._tabs.addTab(self._make_sticky_tab(),   "Sticky Notes")
        layout.addWidget(self._tabs)

        if initial_tab is not None:
            self._tabs.setCurrentIndex(initial_tab)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
        layout.addWidget(btns)

    def select_tab(self, name: str) -> None:
        """Switch to the tab with the given label name."""
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == name:
                self._tabs.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    # Hotkeys tab
    # ------------------------------------------------------------------

    def _make_hotkeys_tab(self) -> QWidget:
        from .settings_manager import HOTKEY_LABELS
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)

        info = QLabel("Click a row to rebind its hotkey.")
        info.setStyleSheet("font-size: 11px;")
        lay.addWidget(info)

        self._hk_table = QTableWidget()
        self._hk_table.setColumnCount(2)
        self._hk_table.setHorizontalHeaderLabels(["Action", "Key Binding"])
        self._hk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._hk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._hk_table.setColumnWidth(1, 160)
        self._hk_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hk_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hk_table.verticalHeader().setVisible(False)

        all_hk = self._settings.all_hotkeys()
        self._hk_table.setRowCount(len(all_hk))
        self._hk_rows = {}
        for row, (action, key) in enumerate(sorted(all_hk.items())):
            label = HOTKEY_LABELS.get(action, action)
            self._hk_table.setItem(row, 0, QTableWidgetItem(label))
            self._hk_table.setItem(row, 1, QTableWidgetItem(key))
            self._hk_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, action)
            self._hk_rows[action] = row

        self._hk_table.cellDoubleClicked.connect(self._rebind_row)
        lay.addWidget(self._hk_table)
        return w

    def _rebind_row(self, row: int, col: int) -> None:
        action_item = self._hk_table.item(row, 0)
        if not action_item:
            return
        action = action_item.data(Qt.ItemDataRole.UserRole)
        dlg = HotkeyCaptureDialog(action, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured:
            self._hk_table.item(row, 1).setText(dlg.captured)

    # ------------------------------------------------------------------
    # Canvas tab
    # ------------------------------------------------------------------

    def _make_canvas_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)

        # Color
        self._bg_color_btn = QPushButton()
        self._bg_color = self._settings.canvas("background_color")
        self._update_color_btn()
        self._bg_color_btn.clicked.connect(self._pick_bg_color)
        form.addRow("Background Color:", self._bg_color_btn)

        # Grid
        self._grid_chk = QCheckBox("Show grid")
        self._grid_chk.setChecked(self._settings.canvas("grid_enabled"))
        form.addRow("Grid:", self._grid_chk)

        self._grid_snap_chk = QCheckBox("Snap to grid")
        self._grid_snap_chk.setChecked(self._settings.canvas("grid_snap"))
        form.addRow("", self._grid_snap_chk)

        self._grid_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._grid_size_slider.setRange(10, 200)
        self._grid_size_slider.setValue(self._settings.canvas("grid_size"))
        self._grid_size_label = QLabel(f"{self._grid_size_slider.value()} px")
        self._grid_size_slider.valueChanged.connect(
            lambda v: self._grid_size_label.setText(f"{v} px")
        )
        gs_row = QWidget()
        gs_lay = QHBoxLayout(gs_row)
        gs_lay.setContentsMargins(0, 0, 0, 0)
        gs_lay.addWidget(self._grid_size_slider)
        gs_lay.addWidget(self._grid_size_label)
        form.addRow("Grid Size:", gs_row)

        # Grid color
        self._grid_color_val = self._settings.canvas("grid_color")
        self._grid_color_btn = QPushButton(self._grid_color_val)
        self._grid_color_btn.setStyleSheet(
            f"background-color: {self._grid_color_val}; color: white; border-radius: 4px; padding: 4px 10px;"
        )
        self._grid_color_btn.clicked.connect(self._pick_grid_color)
        form.addRow("Grid Color:", self._grid_color_btn)

        # Reset colors to defaults
        reset_btn = QPushButton("Reset Canvas Colors to Default")
        reset_btn.clicked.connect(self._reset_canvas_colors)
        form.addRow("", reset_btn)

        return w

    def _reset_canvas_colors(self) -> None:
        from .settings_manager import DEFAULT_CANVAS
        self._bg_color = DEFAULT_CANVAS["background_color"]
        self._update_color_btn()
        self._grid_color_val = DEFAULT_CANVAS["grid_color"]
        self._grid_color_btn.setText(self._grid_color_val)
        self._grid_color_btn.setStyleSheet(
            f"background-color: {self._grid_color_val}; color: white; border-radius: 4px; padding: 4px 10px;"
        )

    def _pick_grid_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._grid_color_val), self, "Grid Color")
        if c.isValid():
            self._grid_color_val = c.name()
            self._grid_color_btn.setText(self._grid_color_val)
            self._grid_color_btn.setStyleSheet(
                f"background-color: {self._grid_color_val}; color: white; border-radius: 4px; padding: 4px 10px;"
            )

    def _update_color_btn(self) -> None:
        self._bg_color_btn.setText(self._bg_color)
        self._bg_color_btn.setStyleSheet(
            f"background-color: {self._bg_color}; color: white; border-radius: 4px; padding: 4px 10px;"
        )

    def _pick_bg_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._bg_color), self, "Background Color")
        if color.isValid():
            self._bg_color = color.name()
            self._update_color_btn()

    # ------------------------------------------------------------------
    # Display tab
    # ------------------------------------------------------------------

    def _make_display_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(12)

        # Max hand card width
        self._hand_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._hand_size_slider.setRange(40, 200)
        self._hand_size_slider.setValue(self._settings.display("max_hand_card_width"))
        self._hand_size_label = QLabel(f"{self._hand_size_slider.value()} px")
        self._hand_size_slider.valueChanged.connect(
            lambda v: self._hand_size_label.setText(f"{v} px")
        )
        hs_row = QWidget()
        hs_lay = QHBoxLayout(hs_row)
        hs_lay.setContentsMargins(0, 0, 0, 0)
        hs_lay.addWidget(self._hand_size_slider)
        hs_lay.addWidget(self._hand_size_label)
        form.addRow("Max Hand Card Width:", hs_row)

        # Auto magnify (enabled by default; checkbox turns it off)
        self._auto_magnify_chk = QCheckBox("Show hover preview")
        self._auto_magnify_chk.setChecked(self._settings.display("auto_magnify"))
        form.addRow("Card Preview:", self._auto_magnify_chk)

        # Magnify preview size
        cur_mag_size = self._settings.display("magnify_size")
        self._magnify_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._magnify_size_slider.setRange(100, 400)
        self._magnify_size_slider.setSingleStep(10)
        self._magnify_size_slider.setValue(cur_mag_size)
        self._magnify_size_spin = QSpinBox()
        self._magnify_size_spin.setRange(100, 400)
        self._magnify_size_spin.setSingleStep(10)
        self._magnify_size_spin.setSuffix(" px")
        self._magnify_size_spin.setValue(cur_mag_size)
        self._magnify_size_slider.valueChanged.connect(self._magnify_size_spin.setValue)
        self._magnify_size_spin.valueChanged.connect(self._magnify_size_slider.setValue)
        ms_row = QWidget()
        ms_lay = QHBoxLayout(ms_row)
        ms_lay.setContentsMargins(0, 0, 0, 0)
        ms_lay.addWidget(self._magnify_size_slider)
        ms_lay.addWidget(self._magnify_size_spin)
        form.addRow("Preview Size:", ms_row)

        # Magnify corner
        self._magnify_corner_combo = QComboBox()
        for label, val in [
            ("Bottom Right", "bottom_right"),
            ("Bottom Left",  "bottom_left"),
            ("Top Right",    "top_right"),
            ("Top Left",     "top_left"),
        ]:
            self._magnify_corner_combo.addItem(label, val)
        cur = self._settings.display("magnify_corner")
        for i in range(self._magnify_corner_combo.count()):
            if self._magnify_corner_combo.itemData(i) == cur:
                self._magnify_corner_combo.setCurrentIndex(i)
                break
        form.addRow("Preview Corner:", self._magnify_corner_combo)

        # Rotation step
        self._rotation_step_combo = QComboBox()
        for deg in (15, 45, 90):
            self._rotation_step_combo.addItem(f"{deg}°", deg)
        cur_step = self._settings.display("rotation_step")
        for i in range(self._rotation_step_combo.count()):
            if self._rotation_step_combo.itemData(i) == cur_step:
                self._rotation_step_combo.setCurrentIndex(i)
                break
        form.addRow("Rotation Step:", self._rotation_step_combo)

        # Image import default size
        self._img_import_size_spin = QDoubleSpinBox()
        self._img_import_size_spin.setRange(0.25, 20.0)
        self._img_import_size_spin.setSingleStep(0.25)
        self._img_import_size_spin.setDecimals(2)
        self._img_import_size_spin.setSuffix(" cells")
        self._img_import_size_spin.setValue(self._settings.display("image_import_size"))
        form.addRow("Image Import Size:", self._img_import_size_spin)

        # Auto-save
        self._auto_save_chk = QCheckBox("Auto-save session on close")
        self._auto_save_chk.setChecked(self._settings.display("auto_save_on_close"))
        form.addRow("Session:", self._auto_save_chk)

        return w

    # ------------------------------------------------------------------
    # System tab
    # ------------------------------------------------------------------

    def _make_system_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(12)

        self._undo_stack_spin = QSpinBox()
        self._undo_stack_spin.setRange(1, 100)
        self._undo_stack_spin.setValue(self._settings.system("undo_stack_size"))
        self._undo_stack_spin.setSuffix(" levels")
        form.addRow("Undo History:", self._undo_stack_spin)

        return w

    # ------------------------------------------------------------------
    # Sticky Notes tab
    # ------------------------------------------------------------------

    def _make_sticky_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        # Font family
        self._sticky_font_combo = QFontComboBox()
        self._sticky_font_combo.setCurrentFont(
            QFont(self._settings.sticky("default_font_family"))
        )
        form.addRow("Default Font:", self._sticky_font_combo)

        # Font size
        self._sticky_font_size_spin = QSpinBox()
        self._sticky_font_size_spin.setRange(6, 72)
        self._sticky_font_size_spin.setValue(self._settings.sticky("default_font_size"))
        form.addRow("Default Font Size:", self._sticky_font_size_spin)

        # Font color
        self._sticky_font_color = self._settings.sticky("default_font_color")
        self._sticky_font_color_btn = QPushButton()
        self._sticky_font_color_btn.setFixedSize(80, 28)
        self._set_color_btn(self._sticky_font_color_btn, self._sticky_font_color)
        self._sticky_font_color_btn.clicked.connect(self._pick_sticky_font_color)
        form.addRow("Default Font Color:", self._sticky_font_color_btn)

        # Note color
        self._sticky_note_color = self._settings.sticky("default_note_color")
        self._sticky_note_color_btn = QPushButton()
        self._sticky_note_color_btn.setFixedSize(80, 28)
        self._set_color_btn(self._sticky_note_color_btn, self._sticky_note_color)
        self._sticky_note_color_btn.clicked.connect(self._pick_sticky_note_color)
        form.addRow("Default Note Color:", self._sticky_note_color_btn)

        # Apply to all existing notes
        apply_btn = QPushButton("Apply to All Existing Notes")
        apply_btn.clicked.connect(self._apply_sticky_to_all)
        form.addRow("", apply_btn)

        return w

    @staticmethod
    def _set_color_btn(btn: QPushButton, hex_color: str) -> None:
        """Paint a color-swatch button to reflect the chosen color."""
        c = QColor(hex_color)
        text_c = "#000000" if (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 > 128 else "#ffffff"
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; color: {text_c}; "
            f"border: 1px solid #4B4D63; border-radius: 3px; }}"
        )
        btn.setText(hex_color.upper())

    def _pick_sticky_font_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._sticky_font_color), self, "Font Color")
        if color.isValid():
            self._sticky_font_color = color.name()
            self._set_color_btn(self._sticky_font_color_btn, self._sticky_font_color)

    def _pick_sticky_note_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._sticky_note_color), self, "Note Color")
        if color.isValid():
            self._sticky_note_color = color.name()
            self._set_color_btn(self._sticky_note_color_btn, self._sticky_note_color)

    def _apply_sticky_to_all(self) -> None:
        """Apply current sticky settings to all existing notes immediately."""
        family = self._sticky_font_combo.currentFont().family()
        size   = self._sticky_font_size_spin.value()
        for note in self._sticky_notes:
            note._font_family = family
            note._font_size   = size
            note._font_color  = self._sticky_font_color
            note._note_color  = self._sticky_note_color
            note._apply_editor_style()
            note.update()

    # ------------------------------------------------------------------
    # Save / restore
    # ------------------------------------------------------------------

    def _save_and_accept(self) -> None:
        # Hotkeys
        for row in range(self._hk_table.rowCount()):
            action_item = self._hk_table.item(row, 0)
            key_item    = self._hk_table.item(row, 1)
            if action_item and key_item:
                action = action_item.data(Qt.ItemDataRole.UserRole)
                self._settings.set_hotkey(action, key_item.text())

        # Canvas
        self._settings.set_canvas("background_color", self._bg_color)
        self._settings.set_canvas("grid_enabled", self._grid_chk.isChecked())
        self._settings.set_canvas("grid_snap",    self._grid_snap_chk.isChecked())
        self._settings.set_canvas("grid_size",    self._grid_size_slider.value())
        self._settings.set_canvas("grid_color",   self._grid_color_val)

        # Display
        self._settings.set_display(
            "max_hand_card_width", self._hand_size_slider.value()
        )
        self._settings.set_display("auto_magnify",     self._auto_magnify_chk.isChecked())
        self._settings.set_display("magnify_size",     self._magnify_size_slider.value())
        self._settings.set_display(
            "magnify_corner", self._magnify_corner_combo.currentData()
        )
        self._settings.set_display("auto_save_on_close", self._auto_save_chk.isChecked())
        self._settings.set_display("rotation_step", self._rotation_step_combo.currentData())
        self._settings.set_display("image_import_size", self._img_import_size_spin.value())

        # System
        self._settings.set_system("undo_stack_size", self._undo_stack_spin.value())

        # Sticky Notes
        self._settings.set_sticky("default_font_family", self._sticky_font_combo.currentFont().family())
        self._settings.set_sticky("default_font_size",   self._sticky_font_size_spin.value())
        self._settings.set_sticky("default_font_color",  self._sticky_font_color)
        self._settings.set_sticky("default_note_color",  self._sticky_note_color)

        self._settings.save()
        self.accept()

    def _restore_defaults(self) -> None:
        self._settings.reset_hotkeys()
        # Reload table
        all_hk = self._settings.all_hotkeys()
        for action, row in self._hk_rows.items():
            item = self._hk_table.item(row, 1)
            if item:
                item.setText(all_hk.get(action, ""))


# ==============================================================================
# Hotkey Capture Dialog
# ==============================================================================

class HotkeyCaptureDialog(QDialog):
    def __init__(self, action_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Rebind: {action_name}")
        self.setFixedSize(320, 160)
        self.captured: Optional[str] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        label = QLabel(f"Press the new key for:\n<b>{action_name}</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(label)

        self._key_label = QLabel("Waiting for input…")
        self._key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_label.setStyleSheet(
            "background: #313244; border-radius: 6px; padding: 10px; font-size: 15px;"
        )
        lay.addWidget(self._key_label)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        from .canvas_view import _key_event_to_str
        key_str = _key_event_to_str(event)
        if key_str:
            self.captured = key_str
            self._key_label.setText(key_str)
            # Auto-close after brief display
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(400, self.accept)


# ==============================================================================
# Recall Dialog
# ==============================================================================

class RecallDialog(QDialog):
    """Recall dialog — resets selected decks to their original full card lists."""

    def __init__(self, deck_models: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recall Cards")
        self.setMinimumWidth(420)
        self.setMinimumHeight(340)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._deck_models = deck_models  # {id: DeckModel}
        self._deck_checks: dict = {}     # {id: QCheckBox}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lay.addWidget(QLabel(
            "Select decks to recall. Each selected deck will be fully restored\n"
            "to its original card list in original order."
        ))

        # All Decks toggle
        self._all_chk = QCheckBox("All Decks")
        self._all_chk.setChecked(True)
        self._all_chk.toggled.connect(self._on_all_toggled)
        lay.addWidget(self._all_chk)

        # Per-deck list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(160)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(6, 6, 6, 6)
        inner_lay.setSpacing(6)

        for dm in deck_models.values():
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(8)

            # Card back thumbnail
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(36, 50)
            if dm.back_path:
                pix = QPixmap(dm.back_path)
                if not pix.isNull():
                    thumb_lbl.setPixmap(pix.scaled(
                        36, 50,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
            row_lay.addWidget(thumb_lbl)

            chk = QCheckBox(f"{dm.name}  ({dm.count}/{len(dm.all_cards)} cards remaining)")
            chk.setChecked(True)
            chk.toggled.connect(self._on_deck_toggled)
            row_lay.addWidget(chk, 1)

            inner_lay.addWidget(row)
            self._deck_checks[dm.id] = chk

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        # Options
        self._include_hand_chk = QCheckBox("Include cards in hand")
        self._include_hand_chk.setChecked(True)
        self._include_hand_chk.setToolTip(
            "If unchecked, hand cards are left in hand and excluded from the restored deck."
        )
        lay.addWidget(self._include_hand_chk)

        self._restore_deleted_chk = QCheckBox("Restore deleted cards")
        self._restore_deleted_chk.setChecked(True)
        self._restore_deleted_chk.setToolTip(
            "If unchecked, cards that were explicitly deleted will not be restored."
        )
        lay.addWidget(self._restore_deleted_chk)

        self._shuffle_after_chk = QCheckBox("Shuffle decks after recall")
        self._shuffle_after_chk.setChecked(False)
        lay.addWidget(self._shuffle_after_chk)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_all_toggled(self, checked: bool) -> None:
        for chk in self._deck_checks.values():
            chk.blockSignals(True)
            chk.setChecked(checked)
            chk.blockSignals(False)

    def _on_deck_toggled(self, _checked: bool) -> None:
        all_checked = all(c.isChecked() for c in self._deck_checks.values())
        self._all_chk.blockSignals(True)
        self._all_chk.setChecked(all_checked)
        self._all_chk.blockSignals(False)

    def result_options(self) -> dict:
        return {
            "deck_ids":        [did for did, chk in self._deck_checks.items() if chk.isChecked()],
            "include_hand":    self._include_hand_chk.isChecked(),
            "restore_deleted": self._restore_deleted_chk.isChecked(),
            "shuffle_after":   self._shuffle_after_chk.isChecked(),
        }


# ==============================================================================
# Session Picker Dialog
# ==============================================================================

_THUMB_W_SESSION = 96
_THUMB_H_SESSION = 54
_ROW_H_SESSION   = _THUMB_H_SESSION + 12


class _SessionRowWidget(QWidget):
    """Custom row widget: thumbnail + text + delete button."""

    def __init__(self, name: str, deck_count: int, saved_at: str,
                 thumb_pix: Optional[QPixmap], on_delete: Callable,
                 parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 4, 4)
        lay.setSpacing(10)

        # Thumbnail
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(_THUMB_W_SESSION, _THUMB_H_SESSION)
        if thumb_pix and not thumb_pix.isNull():
            thumb_lbl.setPixmap(thumb_pix.scaled(
                _THUMB_W_SESSION, _THUMB_H_SESSION,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            thumb_lbl.setStyleSheet("background-color: #000;")
        lay.addWidget(thumb_lbl)

        # Text
        text_lbl = QLabel(f"<b>{name}</b><br><small>{deck_count} deck(s)  ·  {saved_at[:19]}</small>")
        text_lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(text_lbl, 1)

        # Delete button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("Delete this saved session")
        del_btn.setStyleSheet(
            "QPushButton { background: #3b1e1e; color: #f38ba8; border: 1px solid #5a2020;"
            " border-radius: 4px; padding: 0; font-size: 12px; }"
            "QPushButton:hover { background: #5a2020; }"
        )
        del_btn.clicked.connect(lambda _checked: on_delete())
        lay.addWidget(del_btn)


class SessionPickerDialog(QDialog):
    def __init__(self, sessions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Session")
        self.setMinimumSize(560, 380)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.selected_path: Optional[str] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Select a saved session to open:"))

        self._list = QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.setSpacing(2)
        self._populate(sessions)
        self._list.itemDoubleClicked.connect(self._accept_selected)
        lay.addWidget(self._list)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept_selected)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _populate(self, sessions: list) -> None:
        self._list.clear()
        for s in sessions:
            png_path = Path(s["path"]).with_suffix(".png")
            thumb_pix = QPixmap(str(png_path)) if png_path.exists() else None

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, s["path"])
            item.setSizeHint(QSize(500, _ROW_H_SESSION))
            self._list.addItem(item)

            row_w = _SessionRowWidget(
                s["name"], s["deck_count"], s.get("saved_at", ""), thumb_pix,
                on_delete=lambda it=item, p=s["path"]: self._delete_session(it, p),
            )
            self._list.setItemWidget(item, row_w)

    def _delete_session(self, item: QListWidgetItem, path: str) -> None:
        name = Path(path).stem
        reply = QMessageBox.question(
            self, "Delete Session",
            f"Delete saved session '{name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            Path(path).unlink(missing_ok=True)
            Path(path).with_suffix(".png").unlink(missing_ok=True)
        except Exception:
            pass
        self._list.takeItem(self._list.row(item))

    def _accept_selected(self) -> None:
        items = self._list.selectedItems()
        if items:
            self.selected_path = items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()


# ==============================================================================
# Startup Dialog
# ==============================================================================

def _make_logo_label(rel_path: str, color: str, display_w: int) -> QLabel:
    """Load an SVG from a project-relative path, tint it, and return a centred QLabel."""
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QSize as _QSize
    import sys as _sys
    _base = Path(_sys.executable).parent if getattr(_sys, "frozen", False) else Path(__file__).parent.parent
    svg_path = _base / rel_path
    renderer = QSvgRenderer(str(svg_path))
    vb = renderer.viewBox()
    aspect = vb.width() / vb.height() if vb.height() else 1.0
    display_h = int(display_w / aspect)
    size = _QSize(display_w, display_h)
    # Render SVG into an alpha-capable image
    mask_img = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    mask_img.fill(0)
    p = QPainter(mask_img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    # Tint: solid colour masked by SVG alpha
    tinted = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    tinted.fill(QColor(color))
    p2 = QPainter(tinted)
    p2.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p2.drawImage(0, 0, mask_img)
    p2.end()
    lbl = QLabel()
    lbl.setPixmap(QPixmap.fromImage(tinted))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class StartupDialog(QDialog):
    """Shown on launch — lets user start a new session or load an existing one."""

    def __init__(self, sessions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SoloCanvas")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(320)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.selected_path: Optional[str] = None
        self._sessions = sessions

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)

        logo = _make_logo_label("resources/images/logo.svg", "#FFFFFF", 280)
        lay.addWidget(logo)

        lay.addSpacing(6)

        new_btn = QPushButton("  New Session")
        new_btn.setMinimumHeight(42)
        new_btn.setStyleSheet(
            "QPushButton { font-size: 14px; text-align: left; padding-left: 14px; }"
        )
        new_btn.clicked.connect(self.accept)
        lay.addWidget(new_btn)

        load_btn = QPushButton("  Load Session…")
        load_btn.setMinimumHeight(42)
        load_btn.setStyleSheet(
            "QPushButton { font-size: 14px; text-align: left; padding-left: 14px; }"
        )
        load_btn.clicked.connect(self._do_load)
        lay.addWidget(load_btn)

        lay.addSpacing(12)

        notice = QLabel(
            "SoloCanvas\n"
            "Copyright 2026 Geoffrey Osterberg\n\n"
            "SoloCanvas is free software: you can redistribute it and/or modify it "
            "under the terms of the GNU General Public License as published by the "
            "Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version."
        )
        notice.setWordWrap(True)
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice.setStyleSheet("font-size: 9px;")
        lay.addWidget(notice)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.parent():
            p = self.parent()
            self.move(
                p.x() + (p.width()  - self.width())  // 2,
                p.y() + (p.height() - self.height()) // 2,
            )

    def _do_load(self) -> None:
        dlg = SessionPickerDialog(self._sessions, self)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            self.selected_path = dlg.selected_path
            self.accept()


# ==============================================================================
# Background Dialog (opened from canvas right-click)
# ==============================================================================

class BackgroundDialog(QDialog):
    color_applied = pyqtSignal()   # fired each time Apply is clicked

    def __init__(self, canvas_scene, parent=None):
        super().__init__(parent)
        self._scene = canvas_scene
        self.setWindowTitle("Customize Canvas Background")
        self.setMinimumWidth(420)
        self.setWindowModality(Qt.WindowModality.NonModal)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        # Background color
        self._color = canvas_scene.bg_color
        self._color_btn = QPushButton(self._color)
        self._color_btn.setStyleSheet(
            f"background-color: {self._color}; color: white; border-radius: 4px;"
        )
        self._color_btn.clicked.connect(self._pick_color)
        form.addRow("Background Color:", self._color_btn)

        # ── Grid color ──
        self._grid_color = canvas_scene.grid_color
        self._grid_color_btn = QPushButton(self._grid_color)
        self._grid_color_btn.setStyleSheet(
            f"background-color: {self._grid_color}; color: white; border-radius: 4px;"
        )
        self._grid_color_btn.clicked.connect(self._pick_grid_color)
        form.addRow("Grid Color:", self._grid_color_btn)

        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.RestoreDefaults |
            QDialogButtonBox.StandardButton.Close
        )
        btns.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        btns.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._reset_defaults
        )
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self._color_btn.setText(self._color)
            self._color_btn.setStyleSheet(
                f"background-color: {self._color}; color: white; border-radius: 4px;"
            )

    def _pick_grid_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._grid_color), self, "Grid Color")
        if c.isValid():
            self._grid_color = c.name()
            self._grid_color_btn.setText(self._grid_color)
            self._grid_color_btn.setStyleSheet(
                f"background-color: {self._grid_color}; color: white; border-radius: 4px;"
            )

    def _reset_defaults(self) -> None:
        from .settings_manager import DEFAULT_CANVAS
        self._color = DEFAULT_CANVAS["background_color"]
        self._color_btn.setText(self._color)
        self._color_btn.setStyleSheet(
            f"background-color: {self._color}; color: white; border-radius: 4px;"
        )
        self._grid_color = DEFAULT_CANVAS["grid_color"]
        self._grid_color_btn.setText(self._grid_color)
        self._grid_color_btn.setStyleSheet(
            f"background-color: {self._grid_color}; color: white; border-radius: 4px;"
        )

    def _apply(self) -> None:
        self._scene.set_background(mode="color", color=self._color, image_path=None)
        self._scene.set_grid_color(self._grid_color)
        self.color_applied.emit()


# ==============================================================================
# Deck Library Dialog
# ==============================================================================

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}
_THUMB_W, _THUMB_H = 54, 76   # thumbnail dimensions for previews


class DeckLibraryDialog(QDialog):
    """
    Shows all decks in the project Decks/ folder with image previews.
    Decks can be added to the canvas via a callback.  An import button
    copies an external folder into the library and optionally adds it.
    """

    def __init__(
        self,
        decks_dir: Path,
        add_deck_callback: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self._decks_dir = decks_dir
        self._add_deck_cb = add_deck_callback
        self.setWindowTitle("Deck Library")
        self.setMinimumSize(640, 520)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(8)

        # Header
        header = QLabel("Your Deck Library")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding-bottom: 4px;")
        lay.addWidget(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(self._scroll.Shape.NoFrame)

        self._container = QWidget()
        self._deck_layout = QVBoxLayout(self._container)
        self._deck_layout.setSpacing(6)
        self._deck_layout.setContentsMargins(0, 0, 4, 0)
        self._deck_layout.addStretch()

        self._scroll.setWidget(self._container)
        lay.addWidget(self._scroll, 1)

        # Bottom bar
        bar = QWidget()
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(0, 4, 0, 0)

        import_btn = QPushButton("Import Folder into Library…")
        import_btn.clicked.connect(self._import_folder)
        bar_lay.addWidget(import_btn)
        bar_lay.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bar_lay.addWidget(close_btn)

        lay.addWidget(bar)

        self._refresh()

    # ------------------------------------------------------------------
    # Load / refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Re-scan the Decks folder and rebuild the list."""
        # Remove all items except the trailing stretch
        while self._deck_layout.count() > 1:
            item = self._deck_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        deck_dirs = sorted(
            (d for d in self._decks_dir.iterdir() if d.is_dir()),
            key=lambda p: p.name.lower(),
        ) if self._decks_dir.exists() else []

        if not deck_dirs:
            placeholder = QLabel('No decks found.\nUse "Import Folder into Library" to add one.')
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("font-size: 13px; padding: 30px;")
            self._deck_layout.insertWidget(0, placeholder)
            return

        for i, deck_path in enumerate(deck_dirs):
            entry = self._make_entry(deck_path)
            self._deck_layout.insertWidget(i, entry)

    def _make_entry(self, deck_path: Path) -> QWidget:
        """Build one deck row widget."""
        back_pix: Optional[QPixmap] = None
        front_pixmaps: List[QPixmap] = []
        card_count = 0

        for f in sorted(deck_path.iterdir()):
            if not f.is_file() or f.suffix.lower() not in _IMAGE_EXTS:
                continue
            if f.stem.lower() == "back":
                back_pix = QPixmap(str(f))
            else:
                card_count += 1
                if len(front_pixmaps) < 3:
                    front_pixmaps.append(QPixmap(str(f)))

        # Outer card
        entry = QWidget()
        entry.setObjectName("deckEntry")
        outer = QHBoxLayout(entry)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        # Thumbnails: back + up to 3 fronts
        for pix in [back_pix] + front_pixmaps + [None] * (3 - len(front_pixmaps)):
            lbl = QLabel()
            lbl.setFixedSize(_THUMB_W, _THUMB_H)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if pix and not pix.isNull():
                scaled = pix.scaled(
                    _THUMB_W, _THUMB_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lbl.setPixmap(scaled)
            outer.addWidget(lbl)

        outer.addSpacing(6)

        # Deck name + card count
        info = QWidget()
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(0, 0, 0, 0)
        info_lay.setSpacing(3)
        name_lbl = QLabel(deck_path.name)
        name_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        count_lbl = QLabel(f"{card_count} card{'s' if card_count != 1 else ''}")
        count_lbl.setStyleSheet("font-size: 12px;")
        info_lay.addWidget(name_lbl)
        info_lay.addWidget(count_lbl)
        info_lay.addStretch()
        outer.addWidget(info, 1)

        # Add to Canvas button
        add_btn = QPushButton("Add to Canvas")
        add_btn.clicked.connect(
            lambda checked=False, p=str(deck_path), b=add_btn: self._add_deck(p, b)
        )
        outer.addWidget(add_btn)

        return entry

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_deck(self, folder_path: str, btn: "QPushButton") -> None:
        self._add_deck_cb(folder_path)
        btn.setText("Added ✓")
        btn.setEnabled(False)

    def _import_folder(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        folder = QFileDialog.getExistingDirectory(self, "Select Deck Folder to Import")
        if not folder:
            return
        src = Path(folder)
        dest = self._decks_dir / src.name
        if dest.exists():
            QMessageBox.information(
                self, "Already in Library",
                f'"{src.name}" is already in your Deck Library.',
            )
        else:
            try:
                shutil.copytree(str(src), str(dest))
            except Exception as exc:
                QMessageBox.warning(self, "Import Failed", f"Could not copy deck:\n{exc}")
                return
        self._refresh()
        # Auto-add the newly imported deck
        self._add_deck_cb(str(dest))


# ==============================================================================
# Card Picker Dialog  (search & pull from a Deck or Stack)
# ==============================================================================

class CardPickerDialog(QDialog):
    """
    Browse all cards in a deck/stack with search + multi-select.
    Cards are listed top-to-bottom (index 0 = next to draw).
    Supports drag-drop reorder, split, shuffle, and reset order.
    """

    _DEFAULT_THUMB_W = 48
    _THUMB_ASPECT    = 67 / 48   # height / width

    def __init__(
        self,
        deck_model,
        on_to_hand:   "Callable[[object], None]",
        on_to_canvas: "Callable[[object], None]",
        on_split:     "Optional[Callable[[list], None]]" = None,
        settings=None,
        parent=None,
    ):
        super().__init__(parent)
        self._deck_model   = deck_model
        self._on_to_hand   = on_to_hand
        self._on_to_canvas = on_to_canvas
        self._on_split     = on_split
        self._settings     = settings

        w = self._DEFAULT_THUMB_W
        if settings is not None:
            w = int(settings.display("card_picker_thumb_w") or w)
        self._thumb_w = w

        self.setWindowTitle(f'Cards in "{deck_model.name}"')
        self.setMinimumSize(520, 540)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui()

    def _thumb_h(self) -> int:
        return round(self._thumb_w * self._THUMB_ASPECT)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(8)

        # Header
        self._header = QLabel()
        self._header.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #cdd6f4; padding-bottom: 2px;"
        )
        lay.addWidget(self._header)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search cards…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        lay.addWidget(self._search)

        # Card list — index 0 = top of deck = next to draw
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.setIconSize(QSize(self._thumb_w, self._thumb_h()))
        self._list.setSpacing(1)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._list_context_menu)
        # Drag-drop reorder (disabled while search filter is active)
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        lay.addWidget(self._list, 1)

        # Selection count hint
        self._sel_label = QLabel("")
        self._sel_label.setStyleSheet("font-size: 11px;")
        self._list.itemSelectionChanged.connect(self._update_sel_label)
        lay.addWidget(self._sel_label)

        # Thumbnail size slider row
        thumb_row = QHBoxLayout()
        thumb_row.setSpacing(6)
        thumb_row.addWidget(QLabel("Thumb:"))
        self._thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self._thumb_slider.setMinimum(self._DEFAULT_THUMB_W)
        self._thumb_slider.setMaximum(self._DEFAULT_THUMB_W * 4)
        self._thumb_slider.setValue(self._thumb_w)
        self._thumb_slider.setFixedWidth(130)
        self._thumb_slider.valueChanged.connect(self._on_thumb_slider)
        thumb_row.addWidget(self._thumb_slider)
        reset_thumb_btn = QPushButton("↺")
        reset_thumb_btn.setFixedWidth(28)
        reset_thumb_btn.setToolTip("Reset thumbnail to default size")
        reset_thumb_btn.clicked.connect(self._reset_thumb_size)
        thumb_row.addWidget(reset_thumb_btn)
        thumb_row.addStretch()
        lay.addLayout(thumb_row)

        # Bottom button bar
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 4, 0, 0)
        bar.setSpacing(6)

        self._hand_btn    = QPushButton("→ Hand")
        self._canvas_btn  = QPushButton("→ Canvas")
        self._split_btn   = QPushButton("Split")
        self._shuffle_btn = QPushButton("Shuffle")
        self._reset_btn   = QPushButton("Reset Order")
        close_btn         = QPushButton("Close")

        self._hand_btn.setToolTip("Send selected cards to hand")
        self._canvas_btn.setToolTip("Send selected cards to canvas")
        self._split_btn.setToolTip(
            "Move all cards above the selected card into a new stack"
        )
        self._shuffle_btn.setToolTip("Shuffle the deck randomly")
        self._reset_btn.setToolTip("Restore original alphabetical card order")

        self._hand_btn.clicked.connect(self._send_selected_to_hand)
        self._canvas_btn.clicked.connect(self._send_selected_to_canvas)
        self._split_btn.clicked.connect(self._do_split)
        self._shuffle_btn.clicked.connect(self._do_shuffle)
        self._reset_btn.clicked.connect(self._do_reset_order)
        close_btn.clicked.connect(self.accept)

        bar.addWidget(self._hand_btn)
        bar.addWidget(self._canvas_btn)
        bar.addWidget(self._split_btn)
        bar.addWidget(self._shuffle_btn)
        bar.addWidget(self._reset_btn)
        bar.addStretch()
        bar.addWidget(close_btn)
        lay.addLayout(bar)

        self._rebuild_list()

    # ------------------------------------------------------------------
    # List population & filtering
    # ------------------------------------------------------------------

    def _rebuild_list(self) -> None:
        self._list.clear()
        filter_text = self._search.text().strip().lower()
        shown = 0
        for card in self._deck_model.cards:
            if filter_text and filter_text not in card.name.lower():
                continue
            item = QListWidgetItem(card.name)
            item.setData(Qt.ItemDataRole.UserRole, card)
            if card.image_path and Path(card.image_path).exists():
                pix = QPixmap(card.image_path).scaled(
                    self._thumb_w, self._thumb_h(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                if getattr(card, "reversed", False):
                    from PyQt6.QtGui import QTransform
                    pix = pix.transformed(QTransform().rotate(180))
                item.setIcon(QIcon(pix))
            self._list.addItem(item)
            shown += 1

        total = len(self._deck_model.cards)
        suffix = f"  ({shown} shown)" if filter_text and shown != total else ""
        self._header.setText(
            f'"{self._deck_model.name}" — '
            f'{total} card{"s" if total != 1 else ""} remaining{suffix}'
        )
        self._update_sel_label()

    def _apply_filter(self) -> None:
        is_filtered = bool(self._search.text().strip())
        # Disable drag-drop and split while a filter is active
        mode = (QListWidget.DragDropMode.NoDragDrop if is_filtered
                else QListWidget.DragDropMode.InternalMove)
        self._list.setDragDropMode(mode)
        self._split_btn.setEnabled(not is_filtered)
        self._rebuild_list()

    def _update_sel_label(self) -> None:
        n = len(self._list.selectedItems())
        self._sel_label.setText(f"{n} selected" if n else "")

    # ------------------------------------------------------------------
    # Drag-drop reorder → sync deck model
    # ------------------------------------------------------------------

    def _on_rows_moved(self, parent, start, end, dest, row) -> None:
        new_cards = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]
        self._deck_model.cards = new_cards

    # ------------------------------------------------------------------
    # Thumbnail slider
    # ------------------------------------------------------------------

    def _on_thumb_slider(self, value: int) -> None:
        self._thumb_w = value
        self._list.setIconSize(QSize(value, self._thumb_h()))
        self._rebuild_list()
        if self._settings is not None:
            self._settings.set_display("card_picker_thumb_w", value)
            self._settings.save()

    def _reset_thumb_size(self) -> None:
        self._thumb_slider.setValue(self._DEFAULT_THUMB_W)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_cards(self) -> list:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self._list.selectedItems()]

    def _send_selected_to_hand(self) -> None:
        for card in self._selected_cards():
            self._on_to_hand(card)
        self._rebuild_list()

    def _send_selected_to_canvas(self) -> None:
        for card in self._selected_cards():
            self._on_to_canvas(card)
        self._rebuild_list()

    def _do_split(self) -> None:
        if self._on_split is None:
            return
        sel = self._list.selectedItems()
        if not sel:
            return
        split_row = self._list.row(sel[0])
        if split_row == 0:
            return  # nothing above the top card to split off
        cards_to_split = self._deck_model.cards[:split_row]
        self._deck_model.cards = self._deck_model.cards[split_row:]
        self._on_split(cards_to_split)
        self._rebuild_list()

    def _do_shuffle(self) -> None:
        import random
        random.shuffle(self._deck_model.cards)
        self._rebuild_list()

    def _do_reset_order(self) -> None:
        remaining = {id(c) for c in self._deck_model.cards}
        self._deck_model.cards = [
            c for c in self._deck_model.all_cards if id(c) in remaining
        ]
        self._rebuild_list()

    def _list_context_menu(self, pos) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        n = len(items)
        lbl = f"{n} card{'s' if n > 1 else ''}"
        menu.addAction(f"→ Hand ({lbl})",   self._send_selected_to_hand)
        menu.addAction(f"→ Canvas ({lbl})", self._send_selected_to_canvas)
        menu.exec(self._list.mapToGlobal(pos))


# ==============================================================================
# Hotkey Reference Dialog
# ==============================================================================

class HotkeyReferenceDialog(QDialog):
    """Read-only popup listing all hotkeys and their functions."""

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hotkey Reference")
        self.setMinimumSize(500, 560)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._settings = settings_manager
        self._build_ui()

    def _build_ui(self) -> None:
        from .settings_manager import HOTKEY_LABELS
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(10)

        header = QLabel("Hotkey Reference")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding-bottom: 4px;")
        lay.addWidget(header)

        # Table
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Key", "Action"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setAlternatingRowColors(False)
        table.setStyleSheet("""
            QTableWidget { font-size: 13px; }
            QHeaderView::section { font-weight: bold; padding: 5px 8px; }
        """)

        configurable = []
        for action, label in HOTKEY_LABELS.items():
            key = self._settings.hotkey(action)
            if key:
                configurable.append((key, label))

        # Fixed system / mouse bindings (not rebindable)
        fixed = [
            ("Space",             "Pan canvas (hold) / measurement waypoint"),
            ("F11",               "Toggle fullscreen"),
            ("Scroll wheel",      "Zoom in / out"),
            ("Middle mouse drag", "Pan canvas"),
            ("Drag card → deck",  "Merge card into deck"),
        ]

        all_rows = configurable + [None] + fixed

        table.setRowCount(len(all_rows))
        for i, row in enumerate(all_rows):
            if row is None:
                # Section header row
                header_item = QTableWidgetItem("── Mouse & Fixed Keys ──")
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                header_item.setForeground(QColor("#888888"))
                table.setItem(i, 0, header_item)
                table.setSpan(i, 0, 1, 2)
                continue
            key, action = row
            key_item = QTableWidgetItem(key)
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 0, key_item)
            table.setItem(i, 1, QTableWidgetItem(action))

        lay.addWidget(table, 1)

        note = QLabel("Hotkeys can be customized in Settings → Hotkeys.")
        note.setStyleSheet("font-size: 11px;")
        lay.addWidget(note)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


# ==============================================================================
# Dice Color Dialog  (create / edit a dice colour set)
# ==============================================================================

class DiceColorDialog(QDialog):
    """
    Edit per-die colour specs for a new or existing DiceSet.
    Supports solid color, radial gradient, and vertical gradient per die.
    Caller reads .result_set after accept().
    """

    def __init__(self, dice_manager, initial_set=None, parent=None):
        super().__init__(parent)
        self._manager   = dice_manager
        self._initial   = initial_set
        self.result_set = None

        self.setWindowTitle("Dice Color Set")
        self.setMinimumWidth(560)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        from .dice_manager import DIE_TYPES

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # Name field
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Set name:"))
        self._name_edit = QLineEdit()
        if self._initial:
            self._name_edit.setText(self._initial.name)
        self._name_edit.setPlaceholderText("My Set")
        name_row.addWidget(self._name_edit, 1)
        lay.addLayout(name_row)

        apply_all_btn = QPushButton("Apply Color 1 to All Dice")
        apply_all_btn.clicked.connect(self._apply_to_all)
        lay.addWidget(apply_all_btn)

        # Column headers
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        lbl_die = QLabel("Die");  lbl_die.setFixedWidth(30);  hdr.addWidget(lbl_die)
        lbl_c1  = QLabel("Color 1"); lbl_c1.setFixedWidth(70);  hdr.addWidget(lbl_c1)
        lbl_c2  = QLabel("Color 2"); lbl_c2.setFixedWidth(70);  hdr.addWidget(lbl_c2)
        lbl_mode = QLabel("Mode");  lbl_mode.setFixedWidth(90); hdr.addWidget(lbl_mode)
        lbl_ctr = QLabel("Center"); hdr.addWidget(lbl_ctr, 1)
        hdr.addWidget(QLabel(""), 0)
        lay.addLayout(hdr)

        self._specs:          dict = {}
        self._swatch_btns1:   dict = {}
        self._swatch_btns2:   dict = {}
        self._mode_combos:    dict = {}
        self._sliders:        dict = {}
        self._preview_labels: dict = {}

        grid = QWidget()
        grid_lay = QVBoxLayout(grid)
        grid_lay.setSpacing(6)
        grid_lay.setContentsMargins(0, 0, 0, 0)

        for die_type in DIE_TYPES:
            init_color1 = "#ffffff"
            init_color2 = "#000000"
            init_mode   = "solid"
            init_center = 0.5

            if self._initial and die_type in self._initial.colors:
                c = self._initial.colors[die_type]
                if isinstance(c, str):
                    init_color1 = c
                elif isinstance(c, dict):
                    init_color1 = c.get("color1", "#ffffff")
                    init_color2 = c.get("color2", "#000000")
                    init_mode   = c.get("type",   "solid")
                    init_center = float(c.get("center", 0.5))
            elif self._initial:
                # Die type missing from old set — inherit first available color
                first = next(iter(self._initial.colors.values()), "#ffffff")
                if isinstance(first, str):
                    init_color1 = first
                elif isinstance(first, dict):
                    init_color1 = first.get("color1", "#ffffff")
                    init_color2 = first.get("color2", "#000000")
                    init_mode   = first.get("type",   "solid")
                    init_center = float(first.get("center", 0.5))

            self._specs[die_type] = {
                "type":   init_mode,
                "color1": init_color1,
                "color2": init_color2,
                "center": init_center,
            }

            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(8)

            lbl = QLabel(die_type); lbl.setFixedWidth(30); row_lay.addWidget(lbl)

            btn1 = QPushButton()
            btn1.setFixedSize(70, 24)
            btn1.setStyleSheet(
                f"background-color: {init_color1}; border: 1px solid #45475a; border-radius: 4px;"
            )
            btn1.clicked.connect(lambda checked=False, dt=die_type: self._pick_color1(dt))
            row_lay.addWidget(btn1)
            self._swatch_btns1[die_type] = btn1

            btn2 = QPushButton()
            btn2.setFixedSize(70, 24)
            btn2.setStyleSheet(
                f"background-color: {init_color2}; border: 1px solid #45475a; border-radius: 4px;"
            )
            btn2.clicked.connect(lambda checked=False, dt=die_type: self._pick_color2(dt))
            btn2.setEnabled(init_mode != "solid")
            row_lay.addWidget(btn2)
            self._swatch_btns2[die_type] = btn2

            combo = QComboBox()
            combo.addItems(["Solid", "Radial", "Vertical"])
            combo.setCurrentText(init_mode.capitalize())
            combo.setFixedWidth(90)
            combo.currentTextChanged.connect(
                lambda text, dt=die_type: self._on_mode_changed(dt, text)
            )
            row_lay.addWidget(combo)
            self._mode_combos[die_type] = combo

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(init_center * 100))
            slider.setEnabled(init_mode != "solid")
            slider.valueChanged.connect(
                lambda val, dt=die_type: self._on_center_changed(dt, val)
            )
            row_lay.addWidget(slider, 1)
            self._sliders[die_type] = slider

            preview = QLabel()
            preview.setFixedSize(32, 32)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_lay.addWidget(preview)
            self._preview_labels[die_type] = preview

            grid_lay.addWidget(row)

        lay.addWidget(grid)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Set"); save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        self._update_all_previews()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _pick_color1(self, die_type: str) -> None:
        c = QColorDialog.getColor(QColor(self._specs[die_type]["color1"]), self, f"Color 1 – {die_type}")
        if c.isValid():
            self._specs[die_type]["color1"] = c.name()
            self._swatch_btns1[die_type].setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid #45475a; border-radius: 4px;"
            )
            self._update_preview(die_type)

    def _pick_color2(self, die_type: str) -> None:
        c = QColorDialog.getColor(QColor(self._specs[die_type]["color2"]), self, f"Color 2 – {die_type}")
        if c.isValid():
            self._specs[die_type]["color2"] = c.name()
            self._swatch_btns2[die_type].setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid #45475a; border-radius: 4px;"
            )
            self._update_preview(die_type)

    def _on_mode_changed(self, die_type: str, text: str) -> None:
        mode = text.lower()
        self._specs[die_type]["type"] = mode
        is_gradient = mode != "solid"
        self._swatch_btns2[die_type].setEnabled(is_gradient)
        self._sliders[die_type].setEnabled(is_gradient)
        self._update_preview(die_type)

    def _on_center_changed(self, die_type: str, value: int) -> None:
        self._specs[die_type]["center"] = value / 100.0
        self._update_preview(die_type)

    def _apply_to_all(self) -> None:
        from .dice_manager import DIE_TYPES
        first = self._specs[DIE_TYPES[0]]["color1"]
        c = QColorDialog.getColor(QColor(first), self, "Apply Color 1 to All Dice")
        if not c.isValid():
            return
        for dt in DIE_TYPES:
            self._specs[dt]["color1"] = c.name()
            self._swatch_btns1[dt].setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid #45475a; border-radius: 4px;"
            )
        self._update_all_previews()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self, die_type: str) -> None:
        preview = self._preview_labels.get(die_type)
        if not preview:
            return
        spec = self._specs.get(die_type, {"type": "solid", "color1": "#ffffff", "color2": "#000000", "center": 0.5})
        try:
            pix = self._manager.get_face_pixmap_for_preview(die_type, spec, 32)
            if pix.isNull():
                preview.setText("?")
            else:
                preview.setPixmap(pix)
        except Exception:
            preview.setText("?")

    def _update_all_previews(self) -> None:
        from .dice_manager import DIE_TYPES
        for dt in DIE_TYPES:
            self._update_preview(dt)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Name Required", "Please enter a name for the set.")
            return
        from .dice_manager import DiceSet
        colors = {}
        for dt, spec in self._specs.items():
            colors[dt] = spec["color1"] if spec["type"] == "solid" else dict(spec)
        self.result_set = DiceSet(name=name, colors=colors, is_builtin=False)
        self.accept()


# ==============================================================================
# Dice Library Dialog
# ==============================================================================

class DiceLibraryDialog(QDialog):
    """
    Browse dice sets and add dice to the canvas.
    Left: list of sets.
    Right: grid of 7 die icons (64px) for the selected set.
    """

    dice_requested = pyqtSignal(list)   # list of (die_type, set_name) tuples

    def __init__(self, dice_manager, settings, parent=None):
        super().__init__(parent)
        self._manager  = dice_manager
        self._settings = settings
        self._selected_set: Optional[str] = None

        self.setWindowTitle("Dice Bag")
        self.setMinimumSize(580, 400)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        from .dice_manager import DIE_TYPES

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # ── Left: set list ──
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        left_lay.addWidget(QLabel("Dice Sets"))
        self._set_list = QListWidget()
        self._set_list.currentItemChanged.connect(self._on_set_changed)
        self._set_list.itemDoubleClicked.connect(lambda item: self._on_set_changed(item, None))
        left_lay.addWidget(self._set_list, 1)

        btn_row = QHBoxLayout()
        self._new_set_btn    = QPushButton("New Set")
        self._edit_set_btn   = QPushButton("Edit Set")
        self._delete_set_btn = QPushButton("Delete Set")
        self._edit_set_btn.setEnabled(False)
        self._delete_set_btn.setEnabled(False)
        self._new_set_btn.clicked.connect(self._new_set)
        self._edit_set_btn.clicked.connect(self._edit_set)
        self._delete_set_btn.clicked.connect(self._delete_set)
        btn_row.addWidget(self._new_set_btn)
        btn_row.addWidget(self._edit_set_btn)
        btn_row.addWidget(self._delete_set_btn)
        left_lay.addLayout(btn_row)

        lay.addWidget(left, 1)

        # ── Right: die icon grid ──
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        right_lay.addWidget(QLabel("Select dice to add:"))

        self._die_list = QListWidget()
        self._die_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._die_list.setIconSize(QSize(64, 64))
        self._die_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._die_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._die_list.setSpacing(6)
        self._die_list.itemDoubleClicked.connect(self._add_die_and_close)
        right_lay.addWidget(self._die_list, 1)

        add_btn = QPushButton("Add Selected")
        add_btn.clicked.connect(self._add_selected)
        add_set_btn = QPushButton("Add Set")
        add_set_btn.setToolTip("Add one of each die type from the selected set")
        add_set_btn.clicked.connect(self._add_set)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(add_btn)
        btn_bar.addWidget(add_set_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(close_btn)
        right_lay.addLayout(btn_bar)

        lay.addWidget(right, 2)

        self._refresh_sets()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_sets(self) -> None:
        self._set_list.clear()
        for name in self._manager.set_names():
            item = QListWidgetItem(name)
            self._set_list.addItem(item)
        if self._set_list.count() > 0:
            self._set_list.setCurrentRow(0)

    def _on_set_changed(self, current, previous) -> None:
        if current is None:
            return
        name = current.text()
        self._selected_set = name
        ds = self._manager.get_set(name)
        editable = ds is not None and not ds.is_builtin
        self._edit_set_btn.setEnabled(editable)
        self._delete_set_btn.setEnabled(editable)
        self._refresh_dice_grid()

    def _refresh_dice_grid(self) -> None:
        from .dice_manager import DIE_TYPES
        self._die_list.clear()
        if not self._selected_set:
            return
        for die_type in DIE_TYPES:
            pix = self._manager.get_preview_pixmap(die_type, self._selected_set, 64)
            item = QListWidgetItem(die_type)
            from PyQt6.QtGui import QIcon
            item.setIcon(QIcon(pix))
            item.setData(Qt.ItemDataRole.UserRole, die_type)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self._die_list.addItem(item)

    def _add_selected(self) -> None:
        selected = self._die_list.selectedItems()
        if not selected or not self._selected_set:
            return
        pairs = [(item.data(Qt.ItemDataRole.UserRole), self._selected_set)
                 for item in selected]
        self.dice_requested.emit(pairs)

    def _add_set(self) -> None:
        if not self._selected_set:
            return
        from .dice_manager import DIE_TYPES
        pairs = [(dt, self._selected_set) for dt in DIE_TYPES]
        self.dice_requested.emit(pairs)

    def _add_die_and_close(self, item) -> None:
        die_type = item.data(Qt.ItemDataRole.UserRole)
        if die_type and self._selected_set:
            self.dice_requested.emit([(die_type, self._selected_set)])

    def _edit_set(self) -> None:
        if not self._selected_set:
            return
        ds = self._manager.get_set(self._selected_set)
        if ds is None or ds.is_builtin:
            return
        dlg = DiceColorDialog(self._manager, initial_set=ds, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_set:
            self._manager.add_or_replace_set(dlg.result_set)
            self._refresh_sets()
            for i in range(self._set_list.count()):
                if self._set_list.item(i).text() == dlg.result_set.name:
                    self._set_list.setCurrentRow(i)
                    break

    def _new_set(self) -> None:
        dlg = DiceColorDialog(self._manager, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_set:
            self._manager.add_or_replace_set(dlg.result_set)
            self._refresh_sets()
            # Select the newly created set
            for i in range(self._set_list.count()):
                if self._set_list.item(i).text() == dlg.result_set.name:
                    self._set_list.setCurrentRow(i)
                    break

    def _delete_set(self) -> None:
        if not self._selected_set:
            return
        from PyQt6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self, "Delete Set",
            f'Delete the dice set "{self._selected_set}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._manager.delete_set(self._selected_set)
            self._selected_set = None
            self._die_list.clear()
            self._refresh_sets()


# ==============================================================================
# Roll Log Dialog
# ==============================================================================

class RollLogDialog(QDialog):
    """Shows the session roll history. Holds a reference to the live log list."""

    def __init__(self, roll_log: list, parent=None):
        super().__init__(parent)
        self._log = roll_log
        self.setWindowTitle("Roll Log")
        self.setMinimumSize(420, 500)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list.setStyleSheet("QListWidget::item { font-family: monospace; }")
        lay.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        for entry in reversed(self._log):
            time_str = entry.get("time", "")
            dice = entry.get("dice", [])
            total = entry.get("total", 0)
            if len(dice) == 1:
                d = dice[0]
                text = f"[{time_str}]  {d['type']} → {d['value']}"
                color_name = d.get("color_name")
                if color_name:
                    text += f"  [{color_name}]"
            else:
                def _fmt_die(die: dict) -> str:
                    c = die.get("color_name")
                    base = f"{die['type']}({die['value']})"
                    return f"{base}[{c}]" if c else base

                parts = " + ".join(_fmt_die(d) for d in dice)
                text = f"[{time_str}]  {parts}  =  {total}"
            self._list.addItem(text)

    def _clear(self) -> None:
        self._log.clear()
        self._list.clear()


# ---------------------------------------------------------------------------
# ImageSizeDialog – enter width/height in grid cells when importing an image
# ---------------------------------------------------------------------------

class ImageSizeDialog(QDialog):
    """Ask the user for the initial size (in grid cells) of an imported image."""

    def __init__(
        self,
        parent=None,
        w_cells: float = 1.2,
        h_cells: float = 1.2,
        aspect_ratio: float = None,  # w/h; if provided, lock toggle is available
    ):
        super().__init__(parent)
        self.setWindowTitle("Image Size")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(300)

        self.w_cells: float = w_cells
        self.h_cells: float = h_cells
        self._aspect_ratio  = aspect_ratio  # None means unknown
        self._updating      = False         # re-entrancy guard for linked spinboxes

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self._w_spin = QDoubleSpinBox()
        self._w_spin.setRange(0.25, 200.0)
        self._w_spin.setSingleStep(0.25)
        self._w_spin.setDecimals(2)
        self._w_spin.setValue(w_cells)

        self._h_spin = QDoubleSpinBox()
        self._h_spin.setRange(0.25, 200.0)
        self._h_spin.setSingleStep(0.25)
        self._h_spin.setDecimals(2)
        self._h_spin.setValue(h_cells)

        form.addRow("Width (cells):", self._w_spin)
        form.addRow("Height (cells):", self._h_spin)
        layout.addLayout(form)

        # Aspect ratio lock (enabled when a ratio is known)
        self._lock_chk = QCheckBox("Lock aspect ratio")
        self._lock_chk.setChecked(aspect_ratio is not None)
        self._lock_chk.setEnabled(aspect_ratio is not None)
        layout.addWidget(self._lock_chk)

        self._w_spin.valueChanged.connect(self._on_w_changed)
        self._h_spin.valueChanged.connect(self._on_h_changed)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_w_changed(self, v: float) -> None:
        if self._updating:
            return
        if self._lock_chk.isChecked() and self._aspect_ratio:
            self._updating = True
            self._h_spin.setValue(max(0.25, v / self._aspect_ratio))
            self._updating = False

    def _on_h_changed(self, v: float) -> None:
        if self._updating:
            return
        if self._lock_chk.isChecked() and self._aspect_ratio:
            self._updating = True
            self._w_spin.setValue(max(0.25, v * self._aspect_ratio))
            self._updating = False

    def _accept(self) -> None:
        self.w_cells = self._w_spin.value()
        self.h_cells = self._h_spin.value()
        self.accept()


# ---------------------------------------------------------------------------
# ImageResizeDialog – resize an existing ImageItem
# ---------------------------------------------------------------------------

class ImageResizeDialog(ImageSizeDialog):
    """Pre-populated resize dialog for an existing ImageItem."""

    def __init__(
        self,
        w_cells: float,
        h_cells: float,
        aspect_ratio: float = None,
        parent=None,
    ):
        super().__init__(parent, w_cells=w_cells, h_cells=h_cells, aspect_ratio=aspect_ratio)
        self.setWindowTitle("Resize Image")


# ---------------------------------------------------------------------------
# MissingImageDialog – resolve a missing image file on session load
# ---------------------------------------------------------------------------

class MissingImageDialog(QDialog):
    """Shown when an ImageItem's file cannot be found at load time."""

    def __init__(self, missing_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Not Found")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(420)

        self.result_action: str = "skip"   # "skip" | "remove" | "found"
        self.new_path: str = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        msg = QLabel(f"Image not found:\n{missing_path}")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        find_btn   = QPushButton("Find…")
        remove_btn = QPushButton("Remove")
        skip_btn   = QPushButton("Skip")
        btn_row.addWidget(find_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        btn_row.addWidget(skip_btn)
        layout.addLayout(btn_row)

        self._missing_path = missing_path
        find_btn.clicked.connect(self._find)
        remove_btn.clicked.connect(self._remove)
        skip_btn.clicked.connect(self._skip)

    def _find(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Find Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp)"
        )
        if path:
            self.result_action = "found"
            self.new_path = path
            self.accept()

    def _remove(self) -> None:
        self.result_action = "remove"
        self.accept()

    def _skip(self) -> None:
        self.result_action = "skip"
        self.accept()


# ---------------------------------------------------------------------------
# ImageLibraryDialog – scene image manager + localized image library
# ---------------------------------------------------------------------------

_IMG_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp'}
_CHILD_ROW_BG = "#11111b"   # slightly darker bg for child image rows in expanded folders


def _no_ctx(w: QWidget) -> QWidget:
    """Prevent a cell widget from swallowing right-click events so they reach the viewport."""
    w.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    for child in w.findChildren(QWidget):
        child.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    return w


class RotatingArrowButton(QPushButton):
    """A flat button that draws a right-pointing arrow and rotates it smoothly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle: float = 0.0
        self.setFixedSize(26, 26)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

        self._anim = QPropertyAnimation(self, b"arrow_angle")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_angle(self) -> float:
        return self._angle

    def _set_angle(self, v: float) -> None:
        self._angle = v
        self.update()

    arrow_angle = pyqtProperty(float, _get_angle, _set_angle)

    def set_expanded(self, expanded: bool, animated: bool = False) -> None:
        target = 90.0 if expanded else 0.0
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._angle)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._angle = target
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(self._angle)
        path = QPainterPath()
        path.moveTo(-4.5, -6.0)
        path.lineTo(5.5, 0.0)
        path.lineTo(-4.5, 6.0)
        path.closeSubpath()
        p.fillPath(path, QColor("#a6adc8"))
        p.end()


class ImageLibraryDialog(QDialog):
    """Non-modal dialog for managing image imports.

    Tab 1 (Scene): lists every ImageItem in the current scene with status
    indicators (Linked / Local), per-item Duplicate / Center / Localize actions,
    and a bulk "Localize All Linked" button.

    Tab 2 (Library): lists every image file in the shared /Images folder and
    lets the user spawn copies onto the canvas.
    """

    duplicate_requested        = pyqtSignal(object)   # ImageItem
    center_view_requested      = pyqtSignal(object)   # ImageItem
    localize_requested         = pyqtSignal(list)     # list[ImageItem]
    spawn_requested            = pyqtSignal(str)      # absolute path string
    rename_requested           = pyqtSignal(str, str) # old_path, new_path
    delete_from_library_requested = pyqtSignal(str)   # path of deleted file
    remove_from_scene_requested   = pyqtSignal(list)  # list[ImageItem]

    def __init__(self, image_items_ref: list, images_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Library")
        self.setMinimumSize(680, 500)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint,
        )
        self._items_ref       = image_items_ref   # live reference to MainWindow._image_items
        self._images_dir      = images_dir
        self._expanded_folders: set = set()       # folder names currently expanded
        self._checked_images:  set = set()        # str paths of checked images (Library tab)
        self._checked_scene:   set = set()        # ImageItem objects checked in Scene tab
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_localized(self, path: str) -> bool:
        try:
            Path(path).relative_to(self._images_dir)
            return True
        except (ValueError, OSError):
            return False

    def _thumb_label(self, path: str) -> QLabel:
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(52, 52)
        lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        p = Path(path)
        if p.exists():
            pix = QPixmap(str(p)).scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if not pix.isNull():
                lbl.setPixmap(pix)
                return lbl
        lbl.setText("⚠")
        lbl.setStyleSheet("font-size: 18px;")
        return lbl

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self._tabs = QTabWidget()
        lay.addWidget(self._tabs)

        self._tabs.addTab(self._build_scene_tab(), "Scene")
        self._tabs.addTab(self._build_library_tab(), "Library")

    def _build_scene_tab(self) -> QWidget:
        w = QWidget()
        vlay = QVBoxLayout(w)
        vlay.setContentsMargins(6, 6, 6, 6)
        vlay.setSpacing(6)

        self._scene_table = QTableWidget()
        self._scene_table.setColumnCount(4)
        self._scene_table.setHorizontalHeaderLabels(["", "", "Status", "Name"])
        hdr = self._scene_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._scene_table.setColumnWidth(0, 32)   # checkbox
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._scene_table.setColumnWidth(1, 58)   # thumbnail
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._scene_table.setColumnWidth(2, 92)   # status
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # name
        self._scene_table.verticalHeader().setVisible(False)
        self._scene_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._scene_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._scene_table.setAlternatingRowColors(False)
        self._scene_table.cellDoubleClicked.connect(self._on_scene_double_click)
        vlay.addWidget(self._scene_table)

        btm = QHBoxLayout()
        btm.setContentsMargins(0, 0, 0, 0)
        ref_btn = QPushButton("Refresh")
        ref_btn.clicked.connect(self.refresh)
        btm.addWidget(ref_btn)
        loc_btn = QPushButton("Localize")
        loc_btn.setToolTip("Localize all checked linked images")
        loc_btn.clicked.connect(self._localize_checked_scene)
        btm.addWidget(loc_btn)
        spawn_btn = QPushButton("Spawn")
        spawn_btn.setToolTip("Spawn a copy of each checked image onto the canvas")
        spawn_btn.clicked.connect(self._spawn_checked_scene)
        btm.addWidget(spawn_btn)
        rem_btn = QPushButton("Remove")
        rem_btn.setToolTip("Remove checked items from the canvas")
        rem_btn.clicked.connect(self._remove_checked_scene)
        btm.addWidget(rem_btn)
        btm.addStretch()
        vlay.addLayout(btm)
        return w

    def _build_library_tab(self) -> QWidget:
        w = QWidget()
        vlay = QVBoxLayout(w)
        vlay.setContentsMargins(6, 6, 6, 6)
        vlay.setSpacing(6)

        note = QLabel(f"Localized images folder:  {self._images_dir}")
        note.setStyleSheet("font-size: 11px;")
        note.setWordWrap(True)
        vlay.addWidget(note)

        # Columns: arrow/cb (0) | thumb (1) | name (2)
        self._lib_table = QTableWidget()
        self._lib_table.setColumnCount(3)
        self._lib_table.setHorizontalHeaderLabels(["", "", "Name"])
        lib_hdr = self._lib_table.horizontalHeader()
        lib_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._lib_table.setColumnWidth(0, 32)   # arrow / checkbox
        lib_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._lib_table.setColumnWidth(1, 62)   # thumbnail
        lib_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # name
        self._lib_table.verticalHeader().setVisible(False)
        self._lib_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._lib_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._lib_table.setAlternatingRowColors(False)
        self._lib_table.cellDoubleClicked.connect(self._on_lib_double_click)
        vlay.addWidget(self._lib_table)

        btm = QHBoxLayout()
        btm.setContentsMargins(0, 0, 0, 0)
        ref_btn = QPushButton("Refresh")
        ref_btn.clicked.connect(self.refresh)
        btm.addWidget(ref_btn)
        new_folder_btn = QPushButton("New Folder")
        new_folder_btn.clicked.connect(self._new_folder)
        btm.addWidget(new_folder_btn)
        move_btn = QPushButton("Move")
        move_btn.clicked.connect(self._move_checked_images)
        btm.addWidget(move_btn)
        spawn_btn = QPushButton("Spawn")
        spawn_btn.setToolTip("Spawn a copy of each checked image onto the canvas")
        spawn_btn.clicked.connect(self._bulk_spawn_lib)
        btm.addWidget(spawn_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete all checked images from the library")
        delete_btn.clicked.connect(self._bulk_delete_lib)
        btm.addWidget(delete_btn)
        rename_btn = QPushButton("Rename")
        rename_btn.setToolTip("Rename the single checked image")
        rename_btn.clicked.connect(self._rename_checked_lib)
        btm.addWidget(rename_btn)
        btm.addStretch()
        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._open_images_folder)
        btm.addWidget(open_btn)
        vlay.addLayout(btm)
        return w

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._populate_scene_tab()
        self._populate_library_tab()

    def _populate_scene_tab(self) -> None:
        self._checked_scene = set()  # reset checkboxes on every refresh
        table = self._scene_table
        table.setRowCount(0)
        table.setRowCount(len(self._items_ref))

        for row, item in enumerate(self._items_ref):
            table.setRowHeight(row, 54)

            # Col 0: checkbox
            cb_w = QWidget()
            cb_hl = QHBoxLayout(cb_w)
            cb_hl.setContentsMargins(0, 0, 0, 0)
            cb_hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.stateChanged.connect(
                lambda state, it=item: self._on_scene_check(it, bool(state))
            )
            cb_hl.addWidget(cb)
            table.setCellWidget(row, 0, _no_ctx(cb_w))

            # Col 1: thumbnail
            table.setCellWidget(row, 1, self._thumb_label(item._image_path))

            # Col 2: status badge
            localized = self._is_localized(item._image_path)
            status_item = QTableWidgetItem("📁  Local" if localized else "🔗  Linked")
            status_item.setForeground(
                QColor("#a6e3a1") if localized else QColor("#f9e2af")
            )
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, status_item)

            # Col 3: filename + path tooltip
            name_item = QTableWidgetItem(Path(item._image_path).name)
            name_item.setToolTip(item._image_path)
            table.setItem(row, 3, name_item)

    # ------------------------------------------------------------------
    # Library tab helpers
    # ------------------------------------------------------------------

    def _is_image_file(self, p: Path) -> bool:
        return p.is_file() and p.suffix.lower() in _IMG_EXTS

    def _lib_subfolders(self) -> list:
        if not self._images_dir.exists():
            return []
        return sorted(d for d in self._images_dir.iterdir() if d.is_dir())

    def _lib_root_images(self) -> list:
        if not self._images_dir.exists():
            return []
        return sorted(f for f in self._images_dir.iterdir() if self._is_image_file(f))

    def _lib_folder_images(self, folder: Path) -> list:
        return sorted(f for f in folder.iterdir() if self._is_image_file(f))

    def _add_folder_row(self, table: QTableWidget, row: int, folder: Path) -> None:
        table.setRowHeight(row, 40)
        expanded = folder.name in self._expanded_folders

        # Col 0: rotating arrow button
        arrow_btn = RotatingArrowButton()
        arrow_btn.set_expanded(expanded, animated=False)
        arrow_btn.clicked.connect(
            lambda _c=False, n=folder.name: self._toggle_folder_anim(n)
        )
        _no_ctx(arrow_btn)
        table.setCellWidget(row, 0, arrow_btn)

        # Col 1: folder icon
        icon_lbl = QLabel("📁")
        icon_lbl.setStyleSheet("font-size: 20px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _no_ctx(icon_lbl)
        table.setCellWidget(row, 1, icon_lbl)

        # Col 2: name
        img_count = len(self._lib_folder_images(folder))
        name_item = QTableWidgetItem(f"  {folder.name}  ({img_count})")
        name_item.setData(Qt.ItemDataRole.UserRole, ("folder", folder.name, str(folder)))
        font = name_item.font()
        font.setBold(True)
        name_item.setFont(font)
        table.setItem(row, 2, name_item)

    def _add_image_row(self, table: QTableWidget, row: int, fpath: Path, indent: bool = False) -> None:
        table.setRowHeight(row, 54)

        bg = _CHILD_ROW_BG if indent else ""

        # Col 0: checkbox
        cb_w = QWidget()
        cb_hl = QHBoxLayout(cb_w)
        cb_hl.setContentsMargins(0, 0, 0, 0)
        cb_hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(str(fpath) in self._checked_images)
        cb.stateChanged.connect(
            lambda state, p=str(fpath): self._on_image_check(p, bool(state))
        )
        cb_hl.addWidget(cb)
        if bg:
            cb_w.setStyleSheet(f"background-color: {bg};")
        table.setCellWidget(row, 0, _no_ctx(cb_w))

        # Col 1: thumbnail wrapped in a full-cell container so bg fills the whole cell
        thumb_w = QWidget()
        thumb_hl = QHBoxLayout(thumb_w)
        thumb_hl.setContentsMargins(0, 0, 0, 0)
        thumb_hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_hl.addWidget(self._thumb_label(str(fpath)))
        if bg:
            thumb_w.setStyleSheet(f"background-color: {bg};")
        table.setCellWidget(row, 1, _no_ctx(thumb_w))

        # Col 2: name
        name_item = QTableWidgetItem(fpath.name)
        name_item.setToolTip(str(fpath))
        name_item.setData(Qt.ItemDataRole.UserRole, ("image", str(fpath)))
        if bg:
            name_item.setBackground(QBrush(QColor(bg)))
        table.setItem(row, 2, name_item)

    def _populate_library_tab(self) -> None:
        table = self._lib_table
        table.setRowCount(0)
        if not self._images_dir.exists():
            return

        # Remove checked paths that no longer exist on disk
        self._checked_images = {p for p in self._checked_images if Path(p).exists()}

        subfolders   = self._lib_subfolders()
        root_images  = self._lib_root_images()

        # Count total rows
        total = len(subfolders) + len(root_images)
        for folder in subfolders:
            if folder.name in self._expanded_folders:
                total += len(self._lib_folder_images(folder))
        table.setRowCount(total)

        row = 0
        for folder in subfolders:
            self._add_folder_row(table, row, folder)
            row += 1
            if folder.name in self._expanded_folders:
                for fpath in self._lib_folder_images(folder):
                    self._add_image_row(table, row, fpath, indent=True)
                    row += 1

        for fpath in root_images:
            self._add_image_row(table, row, fpath, indent=False)
            row += 1

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_image_check(self, path: str, checked: bool) -> None:
        if checked:
            self._checked_images.add(path)
        else:
            self._checked_images.discard(path)

    def _on_lib_double_click(self, row: int, col: int) -> None:
        name_item = self._lib_table.item(row, 2)
        if not name_item:
            return
        data = name_item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "folder":
            self._toggle_folder_anim(data[1])
        else:
            self.spawn_requested.emit(data[1])

    def _on_lib_context_menu(self, pos) -> None:
        row = self._lib_table.rowAt(pos.y())
        if row < 0:
            return
        name_item = self._lib_table.item(row, 2)
        if not name_item:
            return
        data = name_item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        menu = QMenu(self)
        if data[0] == "folder":
            folder = Path(data[2])
            menu.addAction("Rename", lambda: self._rename_lib_folder(folder))
            menu.addAction("Delete", lambda: self._delete_lib_folder(folder))
        else:
            fpath = Path(data[1])
            menu.addAction("Spawn", lambda: self.spawn_requested.emit(str(fpath)))
            menu.addAction("Rename", lambda: self._rename_lib_image(fpath))
            menu.addAction("Delete", lambda: self._delete_lib_image(fpath))
        menu.exec(self._lib_table.viewport().mapToGlobal(pos))

    def _toggle_folder_anim(self, name: str) -> None:
        expanding = name not in self._expanded_folders
        if expanding:
            self._expanded_folders.add(name)
        else:
            self._expanded_folders.discard(name)
        # Animate the arrow button for this folder row
        for r in range(self._lib_table.rowCount()):
            item = self._lib_table.item(r, 2)
            if item:
                d = item.data(Qt.ItemDataRole.UserRole)
                if d and d[0] == "folder" and d[1] == name:
                    btn = self._lib_table.cellWidget(r, 0)
                    if isinstance(btn, RotatingArrowButton):
                        btn.set_expanded(expanding, animated=True)
                    break
        QTimer.singleShot(160, self._populate_library_tab)

    def _bulk_spawn_lib(self) -> None:
        valid = sorted(p for p in self._checked_images if Path(p).exists())
        if not valid:
            QMessageBox.information(self, "Spawn", "No images are checked.")
            return
        for path_str in valid:
            self.spawn_requested.emit(path_str)

    def _bulk_delete_lib(self) -> None:
        valid = sorted(p for p in self._checked_images if Path(p).exists())
        if not valid:
            QMessageBox.information(self, "Delete", "No images are checked.")
            return
        in_use_names = [
            Path(p).name for p in valid
            if any(it._image_path == p for it in self._items_ref)
        ]
        names_list = "\n".join(f"  \u2022 {Path(p).name}" for p in valid)
        msg = f"Delete {len(valid)} image(s) from the library?\n\n{names_list}"
        if in_use_names:
            msg += (
                f"\n\n{len(in_use_names)} image(s) are currently in use on the canvas. "
                f"Canvas items will remain but may show a missing-image indicator."
            )
        msg += "\n\nThis cannot be undone."
        reply = QMessageBox.question(
            self, "Delete Images", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for path_str in valid:
            p = Path(path_str)
            try:
                p.unlink(missing_ok=True)
            except Exception:
                continue
            self._checked_images.discard(path_str)
        self.refresh()

    def _rename_checked_lib(self) -> None:
        valid = [p for p in self._checked_images if Path(p).exists()]
        if len(valid) != 1:
            QMessageBox.information(
                self, "Rename", "Check exactly one image to rename."
            )
            return
        self._rename_lib_image(Path(valid[0]))

    def _new_folder(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        new_dir = self._images_dir / name
        if new_dir.exists():
            QMessageBox.warning(self, "New Folder", f"'{name}' already exists.")
            return
        try:
            new_dir.mkdir(parents=True, exist_ok=False)
        except Exception as e:
            QMessageBox.warning(self, "New Folder", str(e))
            return
        self._expanded_folders.add(name)
        self.refresh()

    def _rename_lib_folder(self, folder: Path) -> None:
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Rename Folder", "New folder name:", text=folder.name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        new_folder = folder.parent / new_name
        if new_folder == folder:
            return
        if new_folder.exists():
            QMessageBox.warning(self, "Rename Folder", f"'{new_name}' already exists.")
            return
        # Collect paths before rename so we can emit signals
        old_images = self._lib_folder_images(folder)
        try:
            folder.rename(new_folder)
        except Exception as e:
            QMessageBox.warning(self, "Rename Failed", str(e))
            return
        # Update canvas items
        for old_p in old_images:
            new_p = new_folder / old_p.name
            self.rename_requested.emit(str(old_p), str(new_p))
        # Update expanded state
        if folder.name in self._expanded_folders:
            self._expanded_folders.discard(folder.name)
            self._expanded_folders.add(new_name)
        # Update checked images
        self._checked_images = {
            str(new_folder / Path(p).name) if Path(p).parent == folder else p
            for p in self._checked_images
        }
        self.refresh()

    def _delete_lib_folder(self, folder: Path) -> None:
        images = self._lib_folder_images(folder)
        in_use_count = sum(
            1 for img in images
            if any(it._image_path == str(img) for it in self._items_ref)
        )
        msg = f"Delete folder '{folder.name}'"
        if images:
            msg += f" and all {len(images)} image(s) inside?"
            if in_use_count:
                msg += f"\n\n{in_use_count} image(s) are currently on the canvas and will be removed."
        else:
            msg += "? (Empty folder)"
        msg += "\n\nThis cannot be undone."
        reply = QMessageBox.question(
            self, "Delete Folder", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for img in images:
            self._checked_images.discard(str(img))
            try:
                img.unlink(missing_ok=True)
            except Exception:
                pass
            self.delete_from_library_requested.emit(str(img))
        try:
            folder.rmdir()
        except Exception as e:
            QMessageBox.warning(self, "Delete Failed", str(e))
            return
        self._expanded_folders.discard(folder.name)
        self.refresh()

    def _move_checked_images(self) -> None:
        valid = {p for p in self._checked_images if Path(p).exists()}
        if not valid:
            QMessageBox.information(self, "Move", "No images are checked.")
            return
        subfolders = self._lib_subfolders()
        # Build destination list
        destinations = [("(Root — Images folder)", self._images_dir)]
        destinations += [(f.name, f) for f in subfolders]

        dlg = QDialog(self)
        dlg.setWindowTitle("Move Images")
        dlg.setMinimumWidth(320)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(QLabel(f"Move {len(valid)} checked image(s) to:"))
        lst = QListWidget()
        for label, _ in destinations:
            lst.addItem(label)
        lst.setCurrentRow(0)
        lay.addWidget(lst)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Continue")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dest_dir = destinations[lst.currentRow()][1]
        dest_dir.mkdir(parents=True, exist_ok=True)

        for old_str in list(valid):
            old_p = Path(old_str)
            new_p = dest_dir / old_p.name
            if new_p == old_p:
                self._checked_images.discard(old_str)
                continue
            if new_p.exists():
                # Resolve collision
                stem, suffix = old_p.stem, old_p.suffix
                n = 1
                while new_p.exists():
                    new_p = dest_dir / f"{stem}_{n}{suffix}"
                    n += 1
            try:
                old_p.rename(new_p)
            except Exception:
                continue
            self.rename_requested.emit(str(old_p), str(new_p))
            self._checked_images.discard(old_str)

        self.refresh()

    def _rename_lib_image(self, path: Path) -> None:
        from PyQt6.QtWidgets import QInputDialog
        new_stem, ok = QInputDialog.getText(
            self, "Rename Image", "New filename (without extension):",
            text=path.stem,
        )
        if not ok or not new_stem.strip():
            return
        new_path = path.parent / (new_stem.strip() + path.suffix)
        if new_path == path:
            return
        if new_path.exists():
            QMessageBox.warning(self, "Rename", f"'{new_path.name}' already exists.")
            return
        try:
            path.rename(new_path)
        except Exception as e:
            QMessageBox.warning(self, "Rename Failed", str(e))
            return
        self._checked_images.discard(str(path))
        self.rename_requested.emit(str(path), str(new_path))
        self.refresh()

    def _delete_lib_image(self, path: Path) -> None:
        in_use = [it for it in self._items_ref if it._image_path == str(path)]
        if in_use:
            msg = (
                f"'{path.name}' is used by {len(in_use)} canvas item(s).\n"
                f"Canvas items will remain but may show a missing-image indicator.\n\n"
                f"This cannot be undone. Continue?"
            )
        else:
            msg = f"Delete '{path.name}' from the library?\n\nThis cannot be undone."
        reply = QMessageBox.question(
            self, "Delete Image", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink(missing_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Delete Failed", str(e))
            return
        self._checked_images.discard(str(path))
        self.refresh()

    def _on_scene_check(self, item, checked: bool) -> None:
        if checked:
            self._checked_scene.add(item)
        else:
            self._checked_scene.discard(item)

    def _on_scene_double_click(self, row: int, col: int) -> None:
        if 0 <= row < len(self._items_ref):
            self.duplicate_requested.emit(self._items_ref[row])

    def _on_scene_context_menu(self, pos) -> None:
        row = self._scene_table.rowAt(pos.y())
        if row < 0 or row >= len(self._items_ref):
            return
        item = self._items_ref[row]
        menu = QMenu(self)
        menu.addAction("Spawn", lambda: self.duplicate_requested.emit(item))
        menu.addAction("Center", lambda: self.center_view_requested.emit(item))
        localized = self._is_localized(item._image_path)
        loc_act = menu.addAction("Localize", lambda: self.localize_requested.emit([item]))
        loc_act.setEnabled(not localized)
        menu.exec(self._scene_table.viewport().mapToGlobal(pos))

    def _remove_checked_scene(self) -> None:
        if not self._checked_scene:
            QMessageBox.information(self, "Remove", "No items are checked.")
            return
        self.remove_from_scene_requested.emit(list(self._checked_scene))

    def _spawn_checked_scene(self) -> None:
        if not self._checked_scene:
            QMessageBox.information(self, "Spawn", "No items are checked.")
            return
        for item in list(self._checked_scene):
            self.duplicate_requested.emit(item)

    def _localize_checked_scene(self) -> None:
        linked = [it for it in self._checked_scene
                  if not self._is_localized(it._image_path)]
        if not linked:
            QMessageBox.information(self, "Localize", "No checked linked images to localize.")
            return
        names = "\n".join(f"  \u2022 {Path(it._image_path).name}" for it in linked)
        reply = QMessageBox.question(
            self, "Localize Images",
            f"Copy {len(linked)} image(s) to the local Images folder?\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.localize_requested.emit(linked)
        self.refresh()

    def _open_images_folder(self) -> None:
        import subprocess, sys as _sys
        self._images_dir.mkdir(parents=True, exist_ok=True)
        if _sys.platform == 'win32':
            subprocess.Popen(['explorer', str(self._images_dir)])
        elif _sys.platform == 'darwin':
            subprocess.Popen(['open', str(self._images_dir)])
        else:
            subprocess.Popen(['xdg-open', str(self._images_dir)])


# ---------------------------------------------------------------------------
# MeasurementSettingsDialog
# ---------------------------------------------------------------------------

class MeasurementSettingsDialog(QDialog):
    """Configure cell size, unit label, and cone angle for measurements."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Measurement Settings")
        self.setModal(True)
        self.setFixedWidth(320)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        # Cell value
        self._cell_val = QSpinBox()
        self._cell_val.setRange(1, 9999)
        self._cell_val.setValue(int(settings.measurement("cell_value")))
        form.addRow("Cell value:", self._cell_val)

        # Cell unit
        self._cell_unit = QLineEdit(str(settings.measurement("cell_unit")))
        self._cell_unit.setMaxLength(16)
        form.addRow("Unit label:", self._cell_unit)

        # Cone angle
        self._cone_angle = QSpinBox()
        self._cone_angle.setRange(1, 180)
        self._cone_angle.setSuffix("°")
        self._cone_angle.setValue(int(settings.measurement("cone_angle")))
        form.addRow("Cone angle:", self._cone_angle)

        # Decimals
        self._decimals = QCheckBox("Show decimals")
        self._decimals.setChecked(bool(settings.measurement("decimals")))
        form.addRow("", self._decimals)

        layout.addLayout(form)
        layout.addSpacing(4)

        info = QLabel("Cell value and unit define the measurement scale.\nCone angle sets the full width of cone measurements.")
        info.setStyleSheet("color: #8C8D9B; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(8)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save_and_accept(self) -> None:
        self._settings.set_measurement("cell_value",  self._cell_val.value())
        self._settings.set_measurement("cell_unit",   self._cell_unit.text().strip() or "ft")
        self._settings.set_measurement("cone_angle",  self._cone_angle.value())
        self._settings.set_measurement("decimals",    self._decimals.isChecked())
        self._settings.save()
        self.accept()
