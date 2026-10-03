#!/usr/bin/env python3
"""
NebulaOS Desktop File Thumbnailer
Extracts application icons from .desktop files and generates PNG thumbnails for Nautilus.
Pure GdkPixbuf implementation (runs 100% headlessly in bubblewrap sandboxes without X11/Wayland display).
"""

import sys
import os
import argparse
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf


ICON_SEARCH_DIRS = [
    "/usr/share/icons/Nebula/scalable/apps",
    "/usr/share/icons/Nebula/scalable/places",
    "/usr/share/icons/Nebula/scalable/actions",
    "/usr/share/icons/Nebula/256x256/apps",
    "/usr/share/icons/Nebula/128x128/apps",
    "/usr/share/icons/Nebula/64x64/apps",
    "/usr/share/icons/Nebula/48x48/apps",
    "/usr/share/icons/hicolor/scalable/apps",
    "/usr/share/icons/hicolor/256x256/apps",
    "/usr/share/icons/hicolor/128x128/apps",
    "/usr/share/icons/hicolor/64x64/apps",
    "/usr/share/icons/hicolor/48x48/apps",
    "/usr/share/icons/Adwaita/scalable/apps",
    "/usr/share/icons/Adwaita/48x48/apps",
    "/usr/share/pixmaps",
]


def extract_icon_name(desktop_path: str) -> str:
    """Parse the Icon= field from a .desktop file."""
    try:
        with open(desktop_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith("Icon="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def find_icon_file(icon_name: str) -> str:
    """Resolve an icon name or path to an absolute image file path."""
    if not icon_name:
        return ""

    # If it's already an absolute path and exists
    if os.path.isabs(icon_name) and os.path.exists(icon_name):
        return icon_name

    # Try exact match or with extensions
    extensions = ["", ".svg", ".png", ".jpg"]
    for d in ICON_SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in extensions:
            target = os.path.join(d, f"{icon_name}{ext}")
            if os.path.isfile(target):
                return target

    return ""


def generate_thumbnail(in_path: str, out_path: str, size: int = 128) -> int:
    if not os.path.isfile(in_path):
        return 1

    icon_name = extract_icon_name(in_path)
    icon_file = find_icon_file(icon_name)

    # Fallback to generic application icon if specific icon not found
    if not icon_file:
        for fallback in ["system-run", "application-x-executable", "org.gnome.Settings", "package-x-generic"]:
            icon_file = find_icon_file(fallback)
            if icon_file:
                break

    if not icon_file or not os.path.isfile(icon_file):
        return 1

    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_file, size, size, True)
        if not pixbuf:
            return 1

        # Ensure we have an RGBA pixbuf (with alpha channel) so the saved PNG
        # has a transparent background instead of an opaque one.
        if pixbuf.get_has_alpha():
            rgba_pixbuf = pixbuf
        else:
            # Create a new RGBA pixbuf with transparent background and composite the icon
            rgba_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
            rgba_pixbuf.fill(0x00000000)  # Fully transparent
            # Composite the icon onto the transparent background
            actual_w = pixbuf.get_width()
            actual_h = pixbuf.get_height()
            dest_x = (size - actual_w) // 2
            dest_y = (size - actual_h) // 2
            pixbuf.composite(
                rgba_pixbuf,
                dest_x, dest_y,      # dest_x, dest_y
                actual_w, actual_h,  # dest_width, dest_height
                dest_x, dest_y,      # offset_x, offset_y
                1.0, 1.0,            # scale_x, scale_y
                GdkPixbuf.InterpType.BILINEAR,
                255                  # overall_alpha (fully opaque icon)
            )

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        rgba_pixbuf.savev(out_path, 'png', [], [])
        return 0
    except Exception as e:
        sys.stderr.write(f"Thumbnailer error: {e}\n")
        return 1


def main():
    parser = argparse.ArgumentParser(description="NebulaOS .desktop file thumbnailer")
    parser.add_argument("-s", "--size", type=int, default=128, help="Thumbnail size")
    parser.add_argument("input", help="Input .desktop file path")
    parser.add_argument("output", help="Output PNG thumbnail path")
    args = parser.parse_args()

    ret = generate_thumbnail(args.input, args.output, args.size)
    sys.exit(ret)


if __name__ == "__main__":
    main()
