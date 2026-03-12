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

"""DiceSetsManager – manages dice colour sets and SVG rendering."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PyQt6.QtGui import QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray, QRectF
from PyQt6.QtGui import QPainter, QImage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent.parent

DICE_DIR = _BASE / "Dice"

# Register the SVG namespace so ET.tostring() preserves it
ET.register_namespace("", "http://www.w3.org/2000/svg")

# All die types
DIE_TYPES = ["d4", "d6", "d8", "d10", "d12", "d20", "dF"]
DIE_MAX = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20, "dF": 1}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DiceSet:
    name: str
    colors: Dict[str, Any]      # die_type → "#rrggbb" or ColorSpec dict
    is_builtin: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "colors": dict(self.colors),
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DiceSet":
        return cls(
            name=d.get("name", "Unnamed"),
            colors=dict(d.get("colors", {})),
            is_builtin=bool(d.get("is_builtin", False)),
        )


_BUILTIN_WHITE = DiceSet(
    name="White",
    colors={t: "#ffffff" for t in DIE_TYPES},
    is_builtin=True,
)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class DiceSetsManager:
    """Loads/saves dice colour sets and renders die SVGs as QPixmaps."""

    def __init__(self) -> None:
        self._sets: Dict[str, DiceSet] = {}
        self._cache: Dict[Tuple[str, str, int], QPixmap] = {}
        self.load_sets()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_path(self) -> Path:
        import os
        appdata = Path(os.environ.get("APPDATA", Path.home()))
        return appdata / "SoloCanvas" / "dice_sets.json"

    def load_sets(self) -> None:
        self._sets.clear()
        # Always inject builtins first
        self._sets[_BUILTIN_WHITE.name] = _BUILTIN_WHITE

        path = self._save_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data:
                    ds = DiceSet.from_dict(entry)
                    if not ds.is_builtin:  # don't overwrite builtins from file
                        self._sets[ds.name] = ds
            except Exception:
                pass

    def save_sets(self) -> None:
        path = self._save_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only save non-builtin sets
        data = [ds.to_dict() for ds in self._sets.values() if not ds.is_builtin]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Set management
    # ------------------------------------------------------------------

    def set_names(self) -> list:
        return list(self._sets.keys())

    def get_set(self, name: str) -> Optional[DiceSet]:
        return self._sets.get(name)

    def add_or_replace_set(self, dice_set: DiceSet) -> None:
        if dice_set.is_builtin:
            return
        self._sets[dice_set.name] = dice_set
        # Invalidate cache entries for this set
        keys_to_remove = [k for k in self._cache if k[1] == dice_set.name]
        for k in keys_to_remove:
            del self._cache[k]
        self.save_sets()

    def delete_set(self, name: str) -> bool:
        ds = self._sets.get(name)
        if ds is None or ds.is_builtin:
            return False
        del self._sets[name]
        keys_to_remove = [k for k in self._cache if k[1] == name]
        for k in keys_to_remove:
            del self._cache[k]
        self.save_sets()
        return True

    # ------------------------------------------------------------------
    # SVG recoloring
    # ------------------------------------------------------------------

    def recolor_svg(self, die_type: str, color_spec) -> bytes:
        """Load SVG, apply color_spec (str or ColorSpec dict) with optional gradient + cell shading."""
        svg_path = DICE_DIR / f"{die_type}.svg"
        if not svg_path.exists():
            raise FileNotFoundError(f"SVG not found: {svg_path}")

        tree = ET.parse(str(svg_path))
        root = tree.getroot()

        # Namespace handling
        ns = ""
        tag = root.tag
        if tag.startswith("{"):
            ns = tag.split("}")[0][1:]

        def _t(name: str) -> str:
            return f"{{{ns}}}{name}" if ns else name

        # Normalize color_spec
        if isinstance(color_spec, str):
            spec = {"type": "solid", "color1": color_spec, "color2": "#000000", "center": 0.5}
        else:
            spec = {
                "type":   color_spec.get("type", "solid"),
                "color1": color_spec.get("color1", "#ffffff"),
                "color2": color_spec.get("color2", "#000000"),
                "center": float(color_spec.get("center", 0.5)),
            }

        color1 = spec["color1"]
        color2 = spec["color2"]
        center = max(0.0, min(1.0, spec["center"]))
        mode   = spec["type"]

        # Find all paths
        paths = list(root.iter(_t("path")))

        # Find or create <defs> (insert at position 0)
        defs_el = root.find(_t("defs"))
        if defs_el is None:
            defs_el = ET.Element(_t("defs"))
            root.insert(0, defs_el)

        # Parse viewBox to get coordinate space (all dice SVGs use "0 0 1200 1200")
        vb = root.get("viewBox", "0 0 1200 1200").split()
        try:
            vb_w, vb_h = float(vb[2]), float(vb[3])
        except (IndexError, ValueError):
            vb_w, vb_h = 1200.0, 1200.0
        cx_mid, cy_mid = vb_w / 2, vb_h / 2
        r_full = min(vb_w, vb_h) * 0.65   # gradient radius covers the die

        # Add color gradient to defs if not solid (userSpaceOnUse for Qt compat)
        fill_value = color1
        if mode in ("radial", "vertical"):
            if mode == "radial":
                # Focal point offset from center toward upper-left; radius scales with center
                off_x = cx_mid - vb_w * 0.10
                off_y = cy_mid - vb_h * 0.15
                grad = ET.SubElement(defs_el, _t("radialGradient"))
                grad.set("id", "dg")
                grad.set("cx", f"{off_x:.1f}")
                grad.set("cy", f"{off_y:.1f}")
                grad.set("r",  f"{r_full:.1f}")
                grad.set("gradientUnits", "userSpaceOnUse")
                # center slider: stop offset determines how far color1 extends
                inner_r = f"{int(center * 80)}%"
                s1 = ET.SubElement(grad, _t("stop"))
                s1.set("offset", inner_r)
                s1.set("stop-color", color1)
                s2 = ET.SubElement(grad, _t("stop"))
                s2.set("offset", "100%")
                s2.set("stop-color", color2)
            else:  # vertical
                # center slider shifts the gradient band up/down
                y1 = (center - 0.5) * vb_h
                y2 = (center + 0.5) * vb_h
                grad = ET.SubElement(defs_el, _t("linearGradient"))
                grad.set("id", "dg")
                grad.set("x1", "0")
                grad.set("y1", f"{y1:.1f}")
                grad.set("x2", "0")
                grad.set("y2", f"{y2:.1f}")
                grad.set("gradientUnits", "userSpaceOnUse")
                s1 = ET.SubElement(grad, _t("stop"))
                s1.set("offset", "0%")
                s1.set("stop-color", color1)
                s2 = ET.SubElement(grad, _t("stop"))
                s2.set("offset", "100%")
                s2.set("stop-color", color2)
            fill_value = "url(#dg)"

        # Cell-shading highlight gradient (upper-left white radial, userSpaceOnUse)
        hl_grad = ET.SubElement(defs_el, _t("radialGradient"))
        hl_grad.set("id", "dh")
        hl_grad.set("cx", f"{cx_mid - vb_w * 0.15:.1f}")
        hl_grad.set("cy", f"{cy_mid - vb_h * 0.20:.1f}")
        hl_grad.set("r",  f"{r_full:.1f}")
        hl_grad.set("gradientUnits", "userSpaceOnUse")
        hs1 = ET.SubElement(hl_grad, _t("stop"))
        hs1.set("offset", "0%")
        hs1.set("stop-color", "white")
        hs1.set("stop-opacity", "0.30")
        hs2 = ET.SubElement(hl_grad, _t("stop"))
        hs2.set("offset", "65%")
        hs2.set("stop-color", "white")
        hs2.set("stop-opacity", "0")

        # Cell-shading shadow gradient (lower-right dark radial, userSpaceOnUse)
        sh_grad = ET.SubElement(defs_el, _t("radialGradient"))
        sh_grad.set("id", "ds")
        sh_grad.set("cx", f"{cx_mid + vb_w * 0.15:.1f}")
        sh_grad.set("cy", f"{cy_mid + vb_h * 0.20:.1f}")
        sh_grad.set("r",  f"{r_full:.1f}")
        sh_grad.set("gradientUnits", "userSpaceOnUse")
        ss1 = ET.SubElement(sh_grad, _t("stop"))
        ss1.set("offset", "0%")
        ss1.set("stop-color", "black")
        ss1.set("stop-opacity", "0")
        ss2 = ET.SubElement(sh_grad, _t("stop"))
        ss2.set("offset", "100%")
        ss2.set("stop-color", "black")
        ss2.set("stop-opacity", "0.22")

        # Set fill on all original paths
        for path_el in paths:
            path_el.set("fill", fill_value)

        # Append shading overlay paths (same d attribute, gradient fills, inherit evenodd)
        for path_el in paths:
            d_val = path_el.get("d", "")
            if not d_val:
                continue
            hl_path = ET.SubElement(root, _t("path"))
            hl_path.set("d", d_val)
            hl_path.set("fill", "url(#dh)")
            sh_path = ET.SubElement(root, _t("path"))
            sh_path.set("d", d_val)
            sh_path.set("fill", "url(#ds)")

        return ET.tostring(root, encoding="unicode").encode("utf-8")

    # ------------------------------------------------------------------
    # Pixmap rendering
    # ------------------------------------------------------------------

    def get_pixmap(self, die_type: str, set_name: str, size_px: int) -> QPixmap:
        """Return a QPixmap of the die icon at size_px × size_px, cached."""
        key = (die_type, set_name, size_px)
        if key in self._cache:
            return self._cache[key]

        ds = self._sets.get(set_name) or _BUILTIN_WHITE
        color = ds.colors.get(die_type, "#ffffff")

        try:
            svg_bytes = self.recolor_svg(die_type, color)
        except Exception:
            # Return blank pixmap on error
            pix = QPixmap(size_px, size_px)
            pix.fill()
            self._cache[key] = pix
            return pix

        renderer = QSvgRenderer(QByteArray(svg_bytes))
        image = QImage(size_px, size_px, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)  # transparent
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size_px, size_px))
        painter.end()

        pix = QPixmap.fromImage(image)
        self._cache[key] = pix
        return pix
