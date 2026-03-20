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

"""Floating drawing-tool settings dialog."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout,
)


class DrawingSettingsDialog(QDialog):
    """Non-modal floating panel for drawing tool options.

    Emits ``settings_changed`` whenever any value is modified.
    Remembers its screen position via SettingsManager.
    """

    settings_changed = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Drawing Settings")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(260)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        # --- Stroke width ---
        self._stroke_spin = QSpinBox()
        self._stroke_spin.setRange(1, 50)
        self._stroke_spin.setValue(settings.drawing("stroke_width"))
        self._stroke_spin.setSuffix(" px")
        self._stroke_spin.valueChanged.connect(self._on_stroke_width)
        form.addRow("Stroke width:", self._stroke_spin)

        # --- Stroke color ---
        self._stroke_btn = QPushButton()
        self._stroke_btn.setFixedHeight(28)
        self._stroke_btn.clicked.connect(self._pick_stroke_color)
        self._apply_btn_color(self._stroke_btn, settings.drawing("stroke_color"))
        form.addRow("Stroke color:", self._stroke_btn)

        # --- Fill color ---
        self._fill_btn = QPushButton()
        self._fill_btn.setFixedHeight(28)
        self._fill_btn.clicked.connect(self._pick_fill_color)
        self._apply_btn_color(self._fill_btn, settings.drawing("fill_color"))
        form.addRow("Fill color:", self._fill_btn)

        # --- Fill opacity ---
        opacity_row = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(settings.drawing("fill_opacity"))
        self._opacity_slider.setTickInterval(10)
        self._opacity_label = QLabel(f"{settings.drawing('fill_opacity')}%")
        self._opacity_label.setFixedWidth(36)
        self._opacity_slider.valueChanged.connect(self._on_opacity)
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        form.addRow("Fill opacity:", opacity_row)

        # --- Snap to grid ---
        self._snap_chk = QCheckBox()
        self._snap_chk.setChecked(bool(settings.drawing("snap_to_grid")))
        self._snap_chk.toggled.connect(self._on_snap)
        form.addRow("Snap to grid:", self._snap_chk)

        lay.addLayout(form)

        # Restore position
        x = settings.drawing("settings_x")
        y = settings.drawing("settings_y")
        if x is not None and y is not None:
            self.move(int(x), int(y))

    def refresh_from_settings(self) -> None:
        """Refresh widget values from the current SettingsManager values.

        Used when a right-click "Customize…" opens this dialog for existing shapes.
        """
        self.blockSignals(True)
        try:
            self._stroke_spin.setValue(self._settings.drawing("stroke_width"))
            self._apply_btn_color(self._stroke_btn, self._settings.drawing("stroke_color"))
            self._apply_btn_color(self._fill_btn, self._settings.drawing("fill_color"))
            self._opacity_slider.setValue(self._settings.drawing("fill_opacity"))
            self._opacity_label.setText(f"{self._settings.drawing('fill_opacity')}%")
            self._snap_chk.setChecked(bool(self._settings.drawing("snap_to_grid")))
        finally:
            self.blockSignals(False)

    # ------------------------------------------------------------------
    # Public accessors (read current live values)
    # ------------------------------------------------------------------

    @property
    def stroke_width(self) -> int:
        return self._stroke_spin.value()

    @property
    def stroke_color(self) -> str:
        return self._settings.drawing("stroke_color")

    @property
    def fill_color(self) -> str:
        return self._settings.drawing("fill_color")

    @property
    def fill_opacity(self) -> int:
        return self._opacity_slider.value()

    @property
    def snap_to_grid(self) -> bool:
        return self._snap_chk.isChecked()

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_stroke_width(self, v: int) -> None:
        self._settings.set_drawing("stroke_width", v)
        self._settings.save()
        self.settings_changed.emit()

    def _pick_stroke_color(self) -> None:
        current = QColor(self._settings.drawing("stroke_color"))
        color = QColorDialog.getColor(current, self, "Stroke Color")
        if color.isValid():
            self._settings.set_drawing("stroke_color", color.name())
            self._settings.save()
            self._apply_btn_color(self._stroke_btn, color.name())
            self.settings_changed.emit()

    def _pick_fill_color(self) -> None:
        current = QColor(self._settings.drawing("fill_color"))
        color = QColorDialog.getColor(current, self, "Fill Color")
        if color.isValid():
            self._settings.set_drawing("fill_color", color.name())
            self._settings.save()
            self._apply_btn_color(self._fill_btn, color.name())
            self.settings_changed.emit()

    def _on_opacity(self, v: int) -> None:
        self._opacity_label.setText(f"{v}%")
        self._settings.set_drawing("fill_opacity", v)
        self._settings.save()
        self.settings_changed.emit()

    def _on_snap(self, checked: bool) -> None:
        self._settings.set_drawing("snap_to_grid", checked)
        self._settings.save()
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_btn_color(self, btn: QPushButton, hex_color: str) -> None:
        c = QColor(hex_color)
        # Choose contrasting label color
        lum = 0.299 * c.redF() + 0.587 * c.greenF() + 0.114 * c.blueF()
        label = "#1F1F27" if lum > 0.5 else "#FFFFFF"
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; color: {label};"
            f" border: 1px solid #4B4D63; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {hex_color}; border-color: #BFA381; }}"
        )
        btn.setText(hex_color.upper())

    # ------------------------------------------------------------------
    # Save position on close/move
    # ------------------------------------------------------------------

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._settings.set_drawing("settings_x", self.x())
        self._settings.set_drawing("settings_y", self.y())
        self._settings.save()

    def closeEvent(self, event) -> None:
        self._settings.set_drawing("settings_x", self.x())
        self._settings.set_drawing("settings_y", self.y())
        self._settings.save()
        super().closeEvent(event)
