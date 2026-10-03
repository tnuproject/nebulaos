#!/usr/bin/env python3
import os
import subprocess
from PIL import Image, ImageFilter

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
wallpapers_dir = os.path.join(root_dir, "src", "branding", "wallpapers")

svg_src = os.path.join(wallpapers_dir, "plains-default.svg")
tmp_png = "/tmp/nebula_plains_temp.png"
out_jpg = os.path.join(wallpapers_dir, "plains-blurred.jpg")

print(f"Rasterizing {svg_src}...")
subprocess.run(["rsvg-convert", "-w", "1920", "-h", "1080", "-f", "png", svg_src, "-o", tmp_png], check=True)

print("Applying Gaussian Blur...")
img = Image.open(tmp_png).convert("RGB")
# Apply rich, smooth blur
blurred = img.filter(ImageFilter.GaussianBlur(radius=36))
blurred.save(out_jpg, "JPEG", quality=92)

if os.path.exists(tmp_png):
    os.remove(tmp_png)

print(f"Blurred wallpaper generated successfully at {out_jpg} (size: {os.path.getsize(out_jpg)} bytes)")
