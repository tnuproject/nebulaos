#!/usr/bin/env python3
"""
Fix Hatter Icon Theme:
1. Resolves Git/Windows pseudo-symlinks (text files pointing to target SVGs).
2. Prevents and removes circular symlinks (ELOOP).
3. Removes broken/unresolvable blocker files so GTK cleanly falls back to Adwaita/hicolor.
4. Ensures every remaining file is either a real valid SVG/PNG or a valid symlink to one.
"""

import os
import sys

def is_valid_image(fpath):
    try:
        if not os.path.isfile(fpath):
            return False
        with open(fpath, 'rb') as f:
            header = f.read(512).strip()
        return header.startswith(b'<') or header.startswith(b'\x89PNG')
    except Exception:
        return False

def fix_icon_theme(theme_dir):
    print(f"Scanning and fixing icon theme in: {theme_dir}")
    theme_dir = os.path.abspath(theme_dir)

    resolved = 0
    removed_blockers = 0

    # Pass 1: Resolve pseudo-symlinks and remove circular/broken ones
    for root, dirs, files in os.walk(theme_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            
            # If it's already a symlink, verify it doesn't loop and points to valid file
            if os.path.islink(fpath):
                try:
                    target = os.path.realpath(fpath)
                    if not is_valid_image(target):
                        os.unlink(fpath)
                        removed_blockers += 1
                except Exception:
                    os.unlink(fpath)
                    removed_blockers += 1
                continue

            try:
                st = os.stat(fpath)
                if st.st_size > 2048:
                    continue
                with open(fpath, 'rb') as f:
                    content = f.read()

                # If it's already a real SVG or PNG, it's good!
                if content.lstrip().startswith(b'<') or content.startswith(b'\x89PNG'):
                    continue

                # It's a text pseudo-symlink
                try:
                    target_rel = content.decode('utf-8').strip()
                except UnicodeDecodeError:
                    os.unlink(fpath)
                    removed_blockers += 1
                    continue

                # Resolve target chain
                curr_target = os.path.normpath(os.path.join(root, target_rel))
                visited = {os.path.normpath(fpath)}
                valid_found = False

                while os.path.exists(curr_target):
                    norm = os.path.normpath(curr_target)
                    if norm in visited:
                        # Circular reference! Break loop
                        break
                    visited.add(norm)

                    if is_valid_image(curr_target):
                        valid_found = True
                        break

                    # Check if next file is also a text pointer
                    try:
                        if os.path.getsize(curr_target) > 2048:
                            break
                        with open(curr_target, 'rb') as tf:
                            tcontent = tf.read()
                        if tcontent.lstrip().startswith(b'<') or tcontent.startswith(b'\x89PNG'):
                            valid_found = True
                            break
                        next_name = tcontent.decode('utf-8').strip()
                        curr_target = os.path.normpath(os.path.join(os.path.dirname(curr_target), next_name))
                    except Exception:
                        break

                if valid_found and os.path.exists(curr_target):
                    os.unlink(fpath)
                    try:
                        rel = os.path.relpath(curr_target, root)
                        os.symlink(rel, fpath)
                    except OSError:
                        # Copy content if symlink fails
                        with open(curr_target, 'rb') as s, open(fpath, 'wb') as d:
                            d.write(s.read())
                    resolved += 1
                else:
                    # Broken pointer: remove so GTK falls back to Adwaita/hicolor
                    os.unlink(fpath)
                    removed_blockers += 1

            except Exception:
                try:
                    os.unlink(fpath)
                    removed_blockers += 1
                except Exception:
                    pass

    print(f"Theme fix complete: {resolved} links resolved, {removed_blockers} broken blockers purged.")

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else '/tmp/nebulaos-chroot/usr/share/icons/Hatter'
    fix_icon_theme(target)
