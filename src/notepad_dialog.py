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

"""NotepadDialog – WYSIWYG Markdown notepad."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import markdown as _md_lib
from markdownify import markdownify as _html_to_md_raw

from PyQt6.QtCore import QMimeData, QSize, Qt, QUrl
from PyQt6.QtGui import (
    QAction, QDragEnterEvent, QDropEvent,
    QFont, QFontDatabase, QKeySequence, QPainter, QPixmap,
    QShortcut, QTextBlockFormat, QTextCharFormat, QTextCursor,
)
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout,
    QLabel, QMenu, QMenuBar,
    QMessageBox, QSizePolicy, QTextEdit, QToolBar,
    QToolButton, QVBoxLayout,
)

# ──────────────────────────────────────────────────────────────────────────────
# Markdown ↔ HTML helpers
# ──────────────────────────────────────────────────────────────────────────────

_MD_EXT = ["extra", "nl2br", "sane_lists"]

_CB_UNCHECKED = "☐"
_CB_CHECKED   = "☑"


def _preprocess_md(text: str) -> str:
    text = re.sub(r"^(\s*[-*+]\s)\[ \]", rf"\1{_CB_UNCHECKED}", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*[-*+]\s)\[x\]", rf"\1{_CB_CHECKED}",   text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*[-*+]\s)\[X\]", rf"\1{_CB_CHECKED}",   text, flags=re.MULTILINE)
    return text


def _postprocess_md(text: str) -> str:
    text = re.sub(rf"^(\s*[-*+]\s){_CB_UNCHECKED}", r"\1[ ]", text, flags=re.MULTILINE)
    text = re.sub(rf"^(\s*[-*+]\s){_CB_CHECKED}",   r"\1[x]", text, flags=re.MULTILINE)
    return text


def md_to_html(md_text: str, base_dir: Path) -> str:
    preprocessed = _preprocess_md(md_text)
    html = _md_lib.markdown(preprocessed, extensions=_MD_EXT)
    def _resolve_img(m: re.Match) -> str:
        src = m.group(1)
        if not src.startswith(("http://", "https://", "file://")):
            abs_path = (base_dir / src).resolve()
            src = abs_path.as_uri()
        return f'src="{src}"'
    html = re.sub(r'src="([^"]+)"', _resolve_img, html)
    return html


def _semantify_qt_html(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for span in list(soup.find_all("span")):
        raw_style = span.get("style", "")
        style = raw_style.replace(" ", "").lower()
        wrappers = []
        if "font-weight:600" in style or "font-weight:bold" in style or "font-weight:700" in style:
            wrappers.append("strong")
        if "font-style:italic" in style:
            wrappers.append("em")
        if "text-decoration:underline" in style:
            wrappers.append("u")
        if "text-decoration:line-through" in style:
            wrappers.append("s")
        if wrappers:
            outer = soup.new_tag(wrappers[0])
            inner = outer
            for tag_name in wrappers[1:]:
                child_tag = soup.new_tag(tag_name)
                inner.append(child_tag)
                inner = child_tag
            for child in list(span.children):
                inner.append(child.extract())
            span.replace_with(outer)
    return str(soup)


def html_to_md(html: str, base_dir: Path) -> str:
    html = _semantify_qt_html(html)
    def _unresolve_img(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("file:///"):
            try:
                abs_path = Path(QUrl(src).toLocalFile())
                rel = abs_path.relative_to(base_dir)
                src = rel.as_posix()
            except (ValueError, Exception):
                pass
        return f'src="{src}"'
    html = re.sub(r'src="([^"]+)"', _unresolve_img, html)
    md = _html_to_md_raw(html, heading_style="ATX", bullets="-")
    md = _postprocess_md(md)
    return md.strip() + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# WYSIWYG editor with checkbox click-detection and image drop
# ──────────────────────────────────────────────────────────────────────────────

class _Editor(QTextEdit):
    def __init__(self, notes_dir: Path, parent=None):
        super().__init__(parent)
        self._notes_dir = notes_dir
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText()
            if word in (_CB_UNCHECKED, _CB_CHECKED):
                cursor.insertText(_CB_CHECKED if word == _CB_UNCHECKED else _CB_UNCHECKED)
                return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            _IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}
            if any(
                Path(u.toLocalFile()).suffix.lower() in _IMG_EXT
                for u in event.mimeData().urls() if u.isLocalFile()
            ):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            _IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}
            images_dir = self._notes_dir / "Images"
            images_dir.mkdir(parents=True, exist_ok=True)
            for url in event.mimeData().urls():
                if not url.isLocalFile():
                    continue
                src = Path(url.toLocalFile())
                if src.suffix.lower() not in _IMG_EXT:
                    continue
                dest = images_dir / src.name
                counter = 1
                while dest.exists():
                    dest = images_dir / f"{src.stem}_{counter}{src.suffix}"
                    counter += 1
                shutil.copy2(src, dest)
                self.textCursor().insertHtml(
                    f'<img src="{dest.as_uri()}" alt="{dest.name}"/>'
                )
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def keyPressEvent(self, event):
        event.accept()
        super().keyPressEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Main dialog
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_FONT_FAMILY = "Segoe UI"
_DEFAULT_FONT_SIZE   = 11

_TOOLBAR_STYLE = """
QToolBar { spacing: 2px; padding: 2px; }
QToolButton { padding: 2px 4px; }
"""

_OPEN_FILTER  = "Notes (*.md *.html *.txt);;Markdown (*.md);;HTML (*.html);;Text (*.txt);;All Files (*)"
_SAVE_FILTER  = "Markdown (*.md);;HTML (*.html);;Text (*.txt);;All Files (*)"

# Font size multipliers for headings (relative to the user's chosen base size)
_HEADING_SCALE = {1: 2.0, 2: 1.5, 3: 1.25}


class NotepadDialog(QDialog):
    """Floating, resizable Markdown notepad."""

    def __init__(self, notes_dir: Path, config_path: Path, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Notepad — Untitled")
        self.resize(900, 600)

        self._notes_dir   = notes_dir
        self._config_path = config_path
        self._current_file: Optional[Path] = None
        self._dirty: bool = False
        self._font_family: str = _DEFAULT_FONT_FAMILY
        self._font_size:   int = _DEFAULT_FONT_SIZE
        self._heading_underline: bool = True

        self._build_ui()
        self._load_state()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._editor = _Editor(self._notes_dir)
        self._editor.setAcceptRichText(True)
        self._editor.document().contentsChanged.connect(self._on_content_changed)

        self._menu_bar = QMenuBar(self)
        self._build_menus()
        self._menu_bar.setSizePolicy(
            self._menu_bar.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        root_layout.addWidget(self._menu_bar, 0)

        self._toolbar = self._build_toolbar()
        root_layout.addWidget(self._toolbar, 0)

        # Heading shortcuts (window-level so they fire regardless of focused widget)
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(lambda: self._insert_heading(1))
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(lambda: self._insert_heading(2))
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(lambda: self._insert_heading(3))

        root_layout.addWidget(self._editor, 1)

        self._status = QLabel("  Untitled")
        self._status.setStyleSheet("color: gray; font-size: 10px; padding: 2px 6px;")
        root_layout.addWidget(self._status, 0)

    def _build_menus(self):
        file_menu = self._menu_bar.addMenu("File")
        _a(file_menu, "New Note",      self._new_note,     "Ctrl+N")
        file_menu.addSeparator()
        _a(file_menu, "Open…",         self._open_note,    "Ctrl+O")
        file_menu.addSeparator()
        _a(file_menu, "Save",          self._save_current, "Ctrl+S")
        _a(file_menu, "Save As…",      self._save_as,      "Ctrl+Shift+S")
        file_menu.addSeparator()
        _a(file_menu, "Export to PDF", self._export_pdf)

        edit_menu = self._menu_bar.addMenu("Edit")
        _a(edit_menu, "Undo",      self._editor.undo,      "Ctrl+Z")
        _a(edit_menu, "Redo",      self._editor.redo,      "Ctrl+Y")
        edit_menu.addSeparator()
        _a(edit_menu, "Cut",       self._editor.cut,       "Ctrl+X")
        _a(edit_menu, "Copy",      self._editor.copy,      "Ctrl+C")
        _a(edit_menu, "Paste",     self._editor.paste,     "Ctrl+V")
        edit_menu.addSeparator()
        _a(edit_menu, "Bold",      self._toggle_bold,      "Ctrl+B")
        _a(edit_menu, "Italic",    self._toggle_italic,    "Ctrl+I")
        _a(edit_menu, "Underline", self._toggle_underline, "Ctrl+U")
        edit_menu.addSeparator()
        self._heading_underline_act = QAction("Heading Underline", self)
        self._heading_underline_act.setCheckable(True)
        self._heading_underline_act.setChecked(self._heading_underline)
        self._heading_underline_act.toggled.connect(self._toggle_heading_underline)
        edit_menu.addAction(self._heading_underline_act)

        self._font_menu = self._menu_bar.addMenu(f"Font: {self._font_family}")
        self._font_actions: dict[str, QAction] = {}
        for family in sorted(set(QFontDatabase.families())):
            act = QAction(family, self)
            act.setFont(QFont(family, 11))
            act.setCheckable(True)
            act.triggered.connect(lambda checked, f=family: self._set_font_family(f))
            self._font_menu.addAction(act)
            self._font_actions[family] = act

        self._size_menu = self._menu_bar.addMenu(f"Size: {self._font_size}")
        self._size_actions: dict[int, QAction] = {}
        for size in (8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 24, 28, 32):
            act = QAction(str(size), self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, s=size: self._set_font_size(s))
            self._size_menu.addAction(act)
            self._size_actions[size] = act

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setStyleSheet(_TOOLBAR_STYLE)
        tb.setIconSize(QSize(16, 16))

        def _btn(label, tip, slot):
            b = QToolButton()
            b.setText(label)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            tb.addWidget(b)

        _btn("B",  "Bold (Ctrl+B)",      self._toggle_bold)
        _btn("I",  "Italic (Ctrl+I)",    self._toggle_italic)
        _btn("U̲",  "Underline (Ctrl+U)", self._toggle_underline)
        tb.addSeparator()
        _btn("H1", "Heading 1 (Ctrl+1)", lambda: self._insert_heading(1))
        _btn("H2", "Heading 2 (Ctrl+2)", lambda: self._insert_heading(2))
        _btn("H3", "Heading 3 (Ctrl+3)", lambda: self._insert_heading(3))
        tb.addSeparator()
        _btn("☐", "Insert checkbox", self._insert_checkbox)
        _btn("•",  "Bullet list",    self._insert_bullet)
        return tb

    # ── Formatting actions ───────────────────────────────────────────────────

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        cur = self._editor.textCursor()
        current_weight = cur.charFormat().fontWeight()
        fmt.setFontWeight(
            QFont.Weight.Normal if current_weight == QFont.Weight.Bold else QFont.Weight.Bold
        )
        cur.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self._editor.currentCharFormat().fontItalic())
        self._editor.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self._editor.currentCharFormat().fontUnderline())
        self._editor.mergeCurrentCharFormat(fmt)

    def _insert_heading(self, level: int):
        cursor = self._editor.textCursor()
        doc = self._editor.document()

        sel_start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        sel_end   = cursor.selectionEnd()   if cursor.hasSelection() else cursor.position()

        # Toggle off if the first block already has this heading level
        first_block = doc.findBlock(sel_start)
        toggle_off  = (first_block.blockFormat().headingLevel() == level)

        cursor.beginEditBlock()
        block = first_block
        while block.isValid() and block.position() <= sel_end:
            bc = QTextCursor(block)
            bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                            QTextCursor.MoveMode.KeepAnchor)

            blk_fmt = QTextBlockFormat()
            char_fmt = QTextCharFormat()

            if toggle_off:
                blk_fmt.setHeadingLevel(0)
                char_fmt.setFontPointSize(self._font_size)
                char_fmt.setFontWeight(QFont.Weight.Normal)
                char_fmt.setFontUnderline(False)
            else:
                blk_fmt.setHeadingLevel(level)
                scale = _HEADING_SCALE[level]
                char_fmt.setFontPointSize(round(self._font_size * scale))
                char_fmt.setFontWeight(QFont.Weight.Bold)
                char_fmt.setFontUnderline(self._heading_underline)

            bc.mergeBlockFormat(blk_fmt)
            bc.mergeCharFormat(char_fmt)
            block = block.next()
        cursor.endEditBlock()

    def _toggle_heading_underline(self, checked: bool):
        self._heading_underline = checked
        self._apply_heading_styles_to_document()
        self._save_state()

    def _apply_heading_styles_to_document(self):
        """Re-apply custom heading sizes/bold/underline after a file load or font change."""
        doc = self._editor.document()
        saved_pos = self._editor.textCursor().position()
        block = doc.begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if level in _HEADING_SCALE:
                bc = QTextCursor(block)
                bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                                QTextCursor.MoveMode.KeepAnchor)
                char_fmt = QTextCharFormat()
                char_fmt.setFontPointSize(round(self._font_size * _HEADING_SCALE[level]))
                char_fmt.setFontWeight(QFont.Weight.Bold)
                char_fmt.setFontUnderline(self._heading_underline)
                bc.mergeCharFormat(char_fmt)
            block = block.next()
        # Restore cursor — bc.mergeCharFormat leaves Qt's undo system pointing at
        # the last-touched block, which pushes the visual cursor to the wrong spot.
        restore = QTextCursor(doc)
        restore.setPosition(min(saved_pos, max(0, doc.characterCount() - 1)))
        self._editor.setTextCursor(restore)

    def _insert_checkbox(self):
        self._editor.textCursor().insertText(f"- {_CB_UNCHECKED} ")

    def _insert_bullet(self):
        self._editor.textCursor().insertText("- ")

    def _set_font_family(self, family: str):
        self._font_family = family
        font = QFont(family, self._font_size)
        self._editor.setFont(font)
        self._editor.document().setDefaultFont(font)
        self._apply_heading_styles_to_document()
        for f, act in self._font_actions.items():
            act.setChecked(f == family)
        self._font_menu.setTitle(f"Font: {family}")
        self._save_state()

    def _set_font_size(self, size: int):
        self._font_size = size
        font = QFont(self._font_family, size)
        self._editor.setFont(font)
        self._editor.document().setDefaultFont(font)
        self._apply_heading_styles_to_document()
        for s, act in self._size_actions.items():
            act.setChecked(s == size)
        self._size_menu.setTitle(f"Size: {size}")
        self._save_state()

    # ── File operations ──────────────────────────────────────────────────────

    def _new_note(self):
        self._auto_save()
        self._editor.document().contentsChanged.disconnect(self._on_content_changed)
        self._editor.clear()
        self._editor.document().setDefaultFont(QFont(self._font_family, self._font_size))
        self._editor.document().contentsChanged.connect(self._on_content_changed)
        self._current_file = None
        self._dirty = False
        self._update_title()
        self._save_state()

    def _open_note(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Note", str(self._notes_dir), _OPEN_FILTER
        )
        if not path_str:
            return
        self._open_file(Path(path_str))

    def _open_file(self, path: Path):
        if path == self._current_file:
            return
        self._auto_save()
        self._current_file = path
        self._load_file_into_editor(path)
        self._dirty = False
        self._update_title()
        self._save_state()

    def _load_file_into_editor(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        suffix = path.suffix.lower()
        self._editor.document().contentsChanged.disconnect(self._on_content_changed)
        if suffix == ".html":
            self._editor.setHtml(text)
        elif suffix == ".txt":
            self._editor.setPlainText(text)
        else:  # .md and anything else
            self._editor.setHtml(md_to_html(text, path.parent))
        self._editor.document().setDefaultFont(QFont(self._font_family, self._font_size))
        self._apply_heading_styles_to_document()
        # Place cursor at start and ensure blink timer is running
        c = QTextCursor(self._editor.document())
        c.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(c)
        self._editor.document().contentsChanged.connect(self._on_content_changed)

    def _save_current(self):
        """Ctrl+S: save to current file; if untitled, show Save As."""
        if self._current_file is None:
            self._save_as()
        else:
            self._write_file(self._current_file)

    def _save_as(self):
        start = str(self._current_file or self._notes_dir)
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Note As", start, _SAVE_FILTER
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.suffix:
            path = path.with_suffix(".md")
        self._current_file = path
        self._write_file(path)
        self._update_title()
        self._save_state()

    def _write_file(self, path: Path):
        suffix = path.suffix.lower()
        try:
            if suffix == ".html":
                content = self._editor.toHtml()
            elif suffix == ".txt":
                content = self._editor.toPlainText()
            else:
                content = html_to_md(self._editor.toHtml(), path.parent)
            path.write_text(content, encoding="utf-8")
            self._dirty = False
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))

    def _auto_save(self):
        """Save current buffer — creates a timestamped file if no named file."""
        if not self._dirty:
            return
        if self._current_file is None:
            if self._editor.toPlainText().strip() == "":
                return  # nothing to save
            self._notes_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self._current_file = self._notes_dir / f"autosave_{ts}.md"
            self._update_title()
        self._write_file(self._current_file)

    def _on_content_changed(self):
        if not self._dirty:
            self._dirty = True

    def _update_title(self):
        if self._current_file is None:
            name = "Untitled"
            status = "  Untitled"
        else:
            name = self._current_file.name
            status = f"  {self._current_file}"
        self.setWindowTitle(f"Notepad — {name}")
        self._status.setText(status)

    # ── Export ───────────────────────────────────────────────────────────────

    def _export_pdf(self):
        if self._current_file is None:
            QMessageBox.information(self, "Export PDF", "Save the note first.")
            return
        default_name = self._current_file.with_suffix(".pdf").name
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export to PDF", str(Path.home() / default_name), "PDF Files (*.pdf)"
        )
        if not dest:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(dest)
        self._editor.document().print(printer)

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self):
        try:
            state = json.loads(self._config_path.read_text(encoding="utf-8")) \
                if self._config_path.exists() else {}
        except Exception:
            state = {}

        family = state.get("font_family", _DEFAULT_FONT_FAMILY)
        size   = int(state.get("font_size", _DEFAULT_FONT_SIZE))
        self._font_family = family
        self._font_size   = size
        self._heading_underline = bool(state.get("heading_underline", True))
        self._heading_underline_act.setChecked(self._heading_underline)
        font = QFont(family, size)
        self._editor.setFont(font)
        self._editor.document().setDefaultFont(font)
        for f, act in self._font_actions.items():
            act.setChecked(f == family)
        self._font_menu.setTitle(f"Font: {family}")
        for s, act in self._size_actions.items():
            act.setChecked(s == size)
        self._size_menu.setTitle(f"Size: {size}")

        last_file = state.get("last_file")
        if last_file:
            p = Path(last_file)
            if p.exists() and p.is_file():
                self._open_file(p)

    def _save_state(self):
        state = {
            "last_file":          str(self._current_file) if self._current_file else None,
            "font_family":        self._font_family,
            "font_size":          self._font_size,
            "heading_underline":  self._heading_underline,
            "was_open":           True,
        }
        try:
            self._config_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def mark_closed(self):
        try:
            state = json.loads(self._config_path.read_text(encoding="utf-8")) \
                if self._config_path.exists() else {}
        except Exception:
            state = {}
        state["was_open"] = False
        try:
            self._config_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Qt overrides ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._auto_save()
        self._save_state()
        self.mark_closed()
        event.accept()

    def hideEvent(self, event):
        self._auto_save()
        self._save_state()
        self.mark_closed()
        super().hideEvent(event)

    def showEvent(self, event):
        try:
            state = json.loads(self._config_path.read_text(encoding="utf-8")) \
                if self._config_path.exists() else {}
        except Exception:
            state = {}
        state["was_open"] = True
        try:
            self._config_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass
        super().showEvent(event)

    def keyPressEvent(self, event):
        event.accept()

    # ── Public API ───────────────────────────────────────────────────────────

    def save_and_close(self):
        """Called by MainWindow on app exit."""
        self._auto_save()
        self._save_state()
        self.mark_closed()

    def apply_theme(self, canvas_hex) -> None:
        if canvas_hex is None:
            self._editor.setStyleSheet("")
            self._status.setStyleSheet("color: gray; font-size: 10px; padding: 2px 6px;")
            return
        from . import theme as _theme
        from PyQt6.QtGui import QColor
        bg, txt, brd, sel = _theme.build_canvas_item_stylesheet(canvas_hex)
        canvas_ss = (
            f"background-color: {bg}; color: {txt}; "
            f"border: 1px solid {brd};"
        )
        self._editor.setStyleSheet(f"QTextEdit {{ {canvas_ss} }}")
        # Status bar: pick readable text colour against the panel background
        panel = _theme.panel_color(canvas_hex)
        status_txt = _theme.text_color(panel).name()
        self._status.setStyleSheet(
            f"color: {status_txt}; font-size: 10px; padding: 2px 6px;"
        )


# ── Helper ────────────────────────────────────────────────────────────────────

def _a(menu, label: str, slot, shortcut: str = "") -> QAction:
    act = QAction(label, menu)
    if shortcut:
        act.setShortcut(QKeySequence(shortcut))
    act.triggered.connect(slot)
    menu.addAction(act)
    return act
