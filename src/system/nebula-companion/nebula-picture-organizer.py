#!/usr/bin/env python3
"""
Nebula Picture Organizer Daemon
Automatically moves downloaded or desktop image files (.webp, .jpg, .jpeg, .png)
to the user's Pictures directory when enabled.
"""

import os
import time
import shutil

ENABLED_FLAG = os.path.expanduser("~/.config/nebula/auto-organize-pictures.enabled")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def get_pictures_dir():
    user_dirs = os.path.expanduser("~/.config/user-dirs.dirs")
    if os.path.exists(user_dirs):
        try:
            with open(user_dirs, "r") as f:
                for line in f:
                    if line.startswith("XDG_PICTURES_DIR"):
                        raw = line.split("=", 1)[1].strip().strip('"')
                        path = raw.replace("$HOME", os.path.expanduser("~"))
                        if os.path.isdir(path):
                            return path
        except Exception:
            pass
    for cand in [os.path.expanduser("~/Pictures"), os.path.expanduser("~/Immagini")]:
        if os.path.isdir(cand):
            return cand
    p = os.path.expanduser("~/Pictures")
    os.makedirs(p, exist_ok=True)
    return p

def organize():
    if not os.path.exists(ENABLED_FLAG):
        return

    dest_dir = get_pictures_dir()
    watch_dirs = [
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Scaricati"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Scrivania")
    ]

    for wdir in watch_dirs:
        if not os.path.isdir(wdir):
            continue
        try:
            for item in os.listdir(wdir):
                full_path = os.path.join(wdir, item)
                if not os.path.isfile(full_path):
                    continue

                # Skip temporary download files
                if item.endswith(".crdownload") or item.endswith(".part") or item.startswith("."):
                    continue

                ext = os.path.splitext(item)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    # Check if file has finished writing
                    try:
                        size1 = os.path.getsize(full_path)
                        time.sleep(0.4)
                        size2 = os.path.getsize(full_path)
                        if size1 != size2:
                            continue
                    except Exception:
                        continue

                    # Move file with unique name collision prevention
                    target_file = os.path.join(dest_dir, item)
                    base, ext = os.path.splitext(item)
                    counter = 1
                    while os.path.exists(target_file):
                        target_file = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                        counter += 1

                    try:
                        shutil.move(full_path, target_file)
                        print(f"Moved {full_path} -> {target_file}")
                    except Exception as e:
                        print(f"Failed to move {full_path}: {e}")
        except Exception:
            pass

def main():
    while True:
        try:
            organize()
        except Exception:
            pass
        time.sleep(4)

if __name__ == "__main__":
    main()
