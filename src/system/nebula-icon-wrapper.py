#!/usr/bin/env python3
"""
NebulaOS Squircle Icon Wrapper
Automatically wraps non-squircle application icons onto the official
Nebula squircle background (bg_white or bg_black).
Supports both vector (SVG) and raster (PNG/XPM) source icons.
"""

import os
import sys
import base64
import re
import subprocess
from pathlib import Path
from PIL import Image

def get_theme_dirs():
    dirs = []
    # User theme dir
    user_nebula = Path.home() / ".local" / "share" / "icons" / "Nebula" / "scalable" / "apps"
    dirs.append(user_nebula)
    # System theme dir
    sys_nebula = Path("/usr/share/icons/Nebula/scalable/apps")
    dirs.append(sys_nebula)
    return dirs

def find_system_icon(icon_name: str) -> Path | None:
    if not icon_name:
        return None

    # If already an absolute path
    p = Path(icon_name)
    if p.is_file():
        return p

    # Standard icon search directories
    search_dirs = [
        Path.home() / ".local/share/icons",
        Path("/usr/share/icons/hicolor"),
        Path("/usr/share/icons"),
        Path("/usr/share/pixmaps"),
        Path("/usr/local/share/pixmaps")
    ]

    # Look for exact SVG first
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        # SVG match
        svg_matches = list(sdir.glob(f"**/{icon_name}.svg"))
        if svg_matches:
            return svg_matches[0]

    # Look for PNG (prioritizing highest resolution)
    png_candidates = []
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        png_matches = list(sdir.glob(f"**/{icon_name}.png"))
        png_candidates.extend(png_matches)

    if png_candidates:
        def get_size(path):
            parts = path.parts
            for p in parts:
                if "x" in p and p.replace("x", "").isdigit():
                    try:
                        return int(p.split("x")[0])
                    except:
                        pass
            return 0
        png_candidates.sort(key=get_size, reverse=True)
        return png_candidates[0]

    return None

def is_predominantly_light(img_path: Path) -> bool:
    try:
        im = Image.open(img_path).convert("RGBA")
        im.thumbnail((64, 64))
        arr = list(im.getdata())
        # Inspect pixels with significant alpha
        visible_px = [p for p in arr if p[3] > 60]
        if not visible_px:
            return False
        avg_lum = sum(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in visible_px) / len(visible_px)
        return avg_lum > 210
    except Exception:
        return False

def wrap_icon_to_squircle(icon_name: str, force: bool = False) -> Path | None:
    if not icon_name or icon_name in ["bg_white", "bg_black"]:
        return None

    # Determine destination
    sys_dir = Path("/usr/share/icons/Nebula/scalable/apps")
    user_dir = Path.home() / ".local" / "share" / "icons" / "Nebula" / "scalable" / "apps"

    dest_dir = sys_dir if os.access("/usr/share/icons", os.W_OK) else user_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{icon_name}.svg"

    def is_squircle(p: Path) -> bool:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            return ('rx="120"' in txt or '<rect width="343' in txt or ('<rect' in txt and 'rx="' in txt and 'width="34' in txt))
        except Exception:
            return False

    # If already in Nebula theme and has squircle, keep it
    if dest_file.exists() and not force and is_squircle(dest_file):
        return dest_file

    # Also check if already in system Nebula with squircle
    if sys_dir.exists() and (sys_dir / f"{icon_name}.svg").exists() and not force and is_squircle(sys_dir / f"{icon_name}.svg"):
        return sys_dir / f"{icon_name}.svg"

    # Find the source icon
    source_icon = find_system_icon(icon_name)
    if not source_icon:
        return None


    bg_color = "black" if is_predominantly_light(source_icon) else "white"

    squircle_svg = None

    if source_icon.suffix.lower() == ".svg":
        try:
            content = source_icon.read_text(encoding="utf-8", errors="ignore")
            vb_match = re.search(r'viewBox="([^"]+)"', content)
            if vb_match:
                vb = vb_match.group(1)
                _, _, w, h = map(float, vb.split())
            else:
                w_match = re.search(r'width="([0-9.]+)', content)
                h_match = re.search(r'height="([0-9.]+)', content)
                w = float(w_match.group(1)) if w_match else 512.0
                h = float(h_match.group(1)) if h_match else 512.0

            inner = re.sub(r"^.*?<svg[^>]*>", "", content, flags=re.DOTALL)
            inner = re.sub(r"</svg>\s*$", "", inner, flags=re.DOTALL)

            target_size = 344.0 * 0.68
            offset = (344.0 - target_size) / 2.0
            s_factor = target_size / max(w, h, 1.0)

            squircle_svg = f"""<svg width="344" height="344" viewBox="0 0 344 344" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <rect width="343.04" height="343.04" rx="120" fill="{bg_color}"/>
  <g transform="translate({offset:.2f}, {offset:.2f}) scale({s_factor:.4f})">
    {inner}
  </g>
</svg>
"""
        except Exception:
            squircle_svg = None

    if not squircle_svg:
        # Fallback / PNG raster embedding
        try:
            with open(source_icon, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("ascii")
            mime = "image/svg+xml" if source_icon.suffix.lower() == ".svg" else "image/png"
            data_uri = f"data:{mime};base64,{b64_data}"

            target_size = 230
            offset = (344 - target_size) / 2

            squircle_svg = f"""<svg width="344" height="344" viewBox="0 0 344 344" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <rect width="343.04" height="343.04" rx="120" fill="{bg_color}"/>
  <image x="{offset}" y="{offset}" width="{target_size}" height="{target_size}" href="{data_uri}"/>
</svg>
"""
        except Exception as e:
            print(f"[!] Icon wrap error for {icon_name}: {e}")
            return None

    dest_file.write_text(squircle_svg, encoding="utf-8")
    
    # Fast GTK icon cache update
    try:
        subprocess.run(["gtk-update-icon-cache", "-q", "-t", str(dest_dir.parent.parent)], check=False)
    except Exception:
        pass

    return dest_file

def wrap_desktop_file(desktop_path: Path):
    try:
        content = desktop_path.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            if line.startswith("Icon="):
                icon_val = line.split("=", 1)[1].strip()
                wrap_icon_to_squircle(icon_val)
                break
    except Exception:
        pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith(".desktop"):
            wrap_desktop_file(Path(arg))
        else:
            wrap_icon_to_squircle(arg)
