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

import sys
import os
import traceback
import datetime
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Crash log setup ────────────────────────────────────────────────────────────
_LOG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SoloCanvas"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "crash.log"


def _write_crash(exc_type, exc_value, exc_tb):
    """Write unhandled exception to crash.log then also print to stderr."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"\n{'='*60}",
        f"CRASH  {timestamp}",
        f"{'='*60}",
    ] + traceback.format_exception(exc_type, exc_value, exc_tb)
    text = "\n".join(lines)

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass

    print(text, file=sys.stderr)


# Install as the global exception handler
sys.excepthook = _write_crash

# Also catch exceptions that happen inside Qt slots (PyQt6-specific)
def _qt_exception_hook(exc_type, exc_value, exc_tb):
    _write_crash(exc_type, exc_value, exc_tb)
    # Don't call sys.exit here — let Qt continue if possible so the log flushes

# ── App entry point ────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from src.main_window import MainWindow


def main():
    # Log the start of each session (helps separate multiple runs)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'─'*60}\n")
        f.write(f"START  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    app = QApplication(sys.argv)
    app.setApplicationName("SoloCanvas")
    app.setOrganizationName("SoloCanvas")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _write_crash(*sys.exc_info())
        raise
