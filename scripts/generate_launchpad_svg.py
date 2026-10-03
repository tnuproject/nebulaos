#!/usr/bin/env python3
import base64
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PNG_PATH = ROOT_DIR / "build" / "launchpad_344.png"
IMMUNE_SVG = ROOT_DIR / "build" / "launchpad_immune.svg"

png_bytes = PNG_PATH.read_bytes()
b64_str = base64.b64encode(png_bytes).decode("utf-8")

svg_content = f"""<svg width="344" height="344" viewBox="0 0 344 344" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <image width="344" height="344" xlink:href="data:image/png;base64,{b64_str}"/>
</svg>
"""

IMMUNE_SVG.write_text(svg_content)
print(f"[✔] Wrote immune SVG: {IMMUNE_SVG} ({len(svg_content)} bytes)")
