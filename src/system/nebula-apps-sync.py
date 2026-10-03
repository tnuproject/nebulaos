#!/usr/bin/env python3
"""
NebulaOS Applications Synchronizer
Monitors and synchronizes ~/Applications (or ~/Applicazioni based on user locale)
with the GNOME application grid, ensuring ONLY GUI applications are visible
and terminal/CLI tools are isolated under Legacy.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

try:
    from nebula_icon_wrapper import wrap_desktop_file
except ImportError:
    sys.path.insert(0, "/usr/lib/nebulaos")
    sys.path.insert(0, "/usr/bin")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from nebula_icon_wrapper import wrap_desktop_file
    except ImportError:
        def wrap_desktop_file(p): pass

def get_apps_folder():
    lang = os.environ.get("LANG", "en_US.UTF-8")
    folder_name = "Applicazioni" if "it" in lang.lower() else "Applications"
    home = Path.home()
    apps_dir = home / folder_name
    apps_dir.mkdir(parents=True, exist_ok=True)
    return apps_dir

EXCLUDED_APPS = {
    "software-properties-gtk.desktop",
    "software-properties-gnome.desktop",
    "update-manager.desktop",
    "nebula-updater.desktop",
    "org.gnome.Epiphany.desktop",
    "epiphany-browser.desktop",
    "org.gnome.SystemMonitor.desktop",
    "gnome-system-monitor.desktop",
    "nm-connection-editor.desktop",
}

def sync_applications():
    apps_dir = get_apps_folder()
    sys_apps = Path("/usr/share/applications")

    if not sys_apps.exists():
        return

    # Scan system desktop files
    for df in sys_apps.glob("*.desktop"):
        target_link = apps_dir / df.name
        if df.name in EXCLUDED_APPS:
            if target_link.exists() and target_link.is_symlink():
                target_link.unlink()
            continue

        try:
            content = df.read_text(encoding="utf-8", errors="ignore")
            if "NoDisplay=true" in content:
                if target_link.exists() and target_link.is_symlink():
                    target_link.unlink()
                continue

            # Ensure squircle icon exists for this app
            wrap_desktop_file(df)

            # Determine if CLI / Terminal application
            is_cli = "Terminal=true" in content or "Categories=ConsoleOnly" in content or "Categories=Legacy" in content

            if not is_cli:
                # GUI Application -> Must be present in ~/Applications
                if not target_link.exists():
                    target_link.symlink_to(df)
            else:
                # CLI Tool -> Remove from main ~/Applications if present
                if target_link.exists() and target_link.is_symlink():
                    target_link.unlink()
        except Exception:
            pass


    # Also scan ~/Applications directly for any user-added .desktop files
    for udf in apps_dir.glob("*.desktop"):
        if not udf.is_symlink():
            wrap_desktop_file(udf)

def main():
    # Initial sync
    sync_applications()

    # Loop with gentle check
    while True:
        time.sleep(15)
        sync_applications()

if __name__ == "__main__":
    main()

