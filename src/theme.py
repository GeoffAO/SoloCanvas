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

"""Colour-derived UI theming for SoloCanvas.

All UI chrome derives its colour from the canvas background colour using the
same darkening formula as HandWidget._panel_color().  The editor / sidebar in
the Notepad uses the raw canvas colour so notes remain easy to read.
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QColor


# ---------------------------------------------------------------------------
# Colour math
# ---------------------------------------------------------------------------

def panel_color(canvas_hex: str) -> QColor:
    """Hand-widget panel colour — same formula as HandWidget._panel_color()."""
    c = QColor(canvas_hex)
    h, s, v, _ = c.getHsvF()
    out = QColor()
    out.setHsvF(h, min(1.0, s * 1.1), max(0.0, v * 0.45))
    return out


def text_color(bg: QColor) -> QColor:
    """Light text on dark backgrounds; dark text on light backgrounds."""
    lum = 0.299 * bg.redF() + 0.587 * bg.greenF() + 0.114 * bg.blueF()
    return QColor(230, 232, 235) if lum < 0.5 else QColor(22, 22, 28)


def _adj(c: QColor, v_factor: float, s_factor: float = 1.0) -> QColor:
    h, s, v, _ = c.getHsvF()
    out = QColor()
    out.setHsvF(h, min(1.0, max(0.0, s * s_factor)),
                min(1.0, max(0.0, v * v_factor)))
    return out


# ---------------------------------------------------------------------------
# Stylesheet builders
# ---------------------------------------------------------------------------

def _x_svg_path(txt_hex: str) -> str:
    """Write a themed X SVG for checkbox indicators; return its URL-safe path."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 11 11">'
        f'<line x1="2" y1="2" x2="9" y2="9" stroke="{txt_hex}" '
        f'stroke-width="1.8" stroke-linecap="round"/>'
        f'<line x1="9" y1="2" x2="2" y2="9" stroke="{txt_hex}" '
        f'stroke-width="1.8" stroke-linecap="round"/>'
        f'</svg>'
    )
    data_dir = Path(os.environ.get("APPDATA", Path.home())) / "SoloCanvas"
    data_dir.mkdir(parents=True, exist_ok=True)
    # Include color in filename so Qt doesn't serve a stale cached version
    p = data_dir / f"checkbox_x_{txt_hex.lstrip('#')}.svg"
    p.write_text(svg, encoding="utf-8")
    return str(p).replace("\\", "/")


def build_app_stylesheet(panel: QColor) -> str:
    """Full Qt stylesheet applied application-wide when canvas theming is on."""
    txt   = text_color(panel)
    btn   = _adj(panel, 1.30)          # buttons: a bit brighter
    btn_h = _adj(panel, 1.55)          # button hover
    brd   = _adj(panel, 1.65)          # borders
    inp   = _adj(panel, 1.15)          # input fields
    sel   = _adj(panel, 1.80)          # selection highlight
    dis   = _adj(panel, 1.40, 0.6)     # disabled text

    p  = panel.name()
    t  = txt.name()
    b  = btn.name()
    bh = btn_h.name()
    br = brd.name()
    ib = inp.name()
    sl = sel.name()
    ds = dis.name()
    xp = _x_svg_path(t)

    return f"""
/* ── Base ── */
QWidget {{
    background-color: {p};
    color: {t};
}}
QMainWindow, QDialog {{
    background-color: {p};
}}

/* ── Menu bar ── */
QMenuBar {{
    background-color: {p};
    color: {t};
    border-bottom: 1px solid {br};
    padding: 2px 0;
    font-size: 13px;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background-color: {bh}; }}

/* ── Drop-down menus ── */
QMenu {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    padding: 4px 0;
    font-size: 13px;
}}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {bh}; }}
QMenu::item:disabled {{ color: {ds}; }}
QMenu::separator {{ height: 1px; background: {br}; margin: 3px 8px; }}

/* ── Push buttons ── */
QPushButton {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    border-radius: 5px;
    padding: 5px 14px;
    font-size: 13px;
}}
QPushButton:hover   {{ background-color: {bh}; }}
QPushButton:pressed {{ background-color: {sl}; }}
QPushButton:disabled {{ color: {ds}; border-color: {p}; }}

/* ── Tool buttons ── */
QToolButton {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    padding: 3px 7px;
    border-radius: 3px;
}}
QToolButton:hover   {{ background-color: {bh}; }}
QToolButton:pressed {{ background-color: {sl}; }}

/* ── Toolbar ── */
QToolBar {{
    background-color: {p};
    border: none;
    spacing: 2px;
    padding: 2px;
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {p};
    color: {t};
    border-top: 1px solid {br};
    font-size: 11px;
}}

/* ── Labels ── */
QLabel {{
    background-color: transparent;
    color: {t};
}}

/* ── Line / spin / combo inputs ── */
QLineEdit {{
    background-color: {ib};
    color: {t};
    border: 1px solid {br};
    padding: 3px 5px;
    border-radius: 3px;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {ib};
    color: {t};
    border: 1px solid {br};
    padding: 2px 4px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {b};
    border: 1px solid {br};
    width: 16px;
}}
QComboBox {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    padding: 3px 8px;
    border-radius: 3px;
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background-color: {b};
    color: {t};
    selection-background-color: {bh};
    border: 1px solid {br};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    background-color: {p};
    border: 1px solid {br};
}}
QTabBar::tab {{
    background-color: {b};
    color: {t};
    padding: 5px 14px;
    border: 1px solid {br};
    border-bottom: none;
    border-radius: 3px 3px 0 0;
}}
QTabBar::tab:selected {{ background-color: {p}; }}
QTabBar::tab:hover    {{ background-color: {bh}; }}

/* ── Group boxes ── */
QGroupBox {{
    color: {t};
    border: 1px solid {br};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {t};
}}

/* ── Checkboxes / radio buttons ── */
QCheckBox {{ color: {t}; }}
QCheckBox::indicator {{
    background-color: {ib};
    border: 1px solid {br};
    border-radius: 3px;
    width: 13px;
    height: 13px;
}}
QCheckBox::indicator:checked {{
    background-color: {ib};
    image: url("{xp}");
}}
QRadioButton {{ color: {t}; }}
QRadioButton::indicator {{
    background-color: {ib};
    border: 1px solid {br};
    border-radius: 7px;
    width: 13px;
    height: 13px;
}}
QRadioButton::indicator:checked {{ background-color: {bh}; }}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    background: {ib};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {bh};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: {p};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {b};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {bh}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical  {{ background: none; }}
QScrollBar:horizontal {{
    background: {p};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {b};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {bh}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ── Trees / lists ── */
QTreeView, QListWidget, QListView {{
    background-color: {ib};
    color: {t};
    border: 1px solid {br};
    alternate-background-color: {p};
}}
QTreeView::item:selected, QListWidget::item:selected {{
    background-color: {bh};
    color: {t};
}}
QTreeView::item:hover, QListWidget::item:hover {{ background-color: {b}; }}

/* ── Text / plain-text editors ── */
QTextEdit, QPlainTextEdit {{
    background-color: {ib};
    color: {t};
    border: 1px solid {br};
}}

/* ── Splitter handles ── */
QSplitter::handle {{ background-color: {br}; }}

/* ── Header views ── */
QHeaderView::section {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    padding: 4px;
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {b};
    color: {t};
    border: 1px solid {br};
    padding: 4px 8px;
    font-size: 12px;
}}
"""


def build_canvas_item_stylesheet(canvas_hex: str) -> tuple[str, str]:
    """
    Returns (bg_css, text_hex) for widgets that should use the canvas colour.
    bg_css is a ready-to-use inline stylesheet fragment.
    """
    bg  = QColor(canvas_hex)
    txt = text_color(bg)
    brd = _adj(bg, 1.4) if bg.valueF() < 0.5 else _adj(bg, 0.7)
    sel = _adj(bg, 1.5) if bg.valueF() < 0.5 else _adj(bg, 0.75)
    return bg.name(), txt.name(), brd.name(), sel.name()
