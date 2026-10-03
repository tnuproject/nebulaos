#!/usr/bin/env python3
"""
Patch Dash to Dock for NebulaOS:
1. Elevates the dock 36px from the bottom edge so it floats detached.
2. Ensures DockShowAppsIcon uses non-symbolic 'view-app-grid' icon and removes 'show-apps-icon' class.
"""
import sys
from pathlib import Path

def patch_d2d(base_dir: Path):
    docking_js = base_dir / "docking.js"
    if docking_js.exists():
        content = docking_js.read_text(encoding="utf-8")
        # Elevate dock translation_y by 36px
        content = content.replace(
            "this.connect('notify::height', () => this.translation_y = -this.height);",
            "this.connect('notify::height', () => this.translation_y = -this.height - 36);"
        )
        content = content.replace(
            "this._position == St.Side.BOTTOM ? this._box.height : 0",
            "this._position == St.Side.BOTTOM ? this._box.height + 36 : 0"
        )
        content = content.replace(
            "desktopIconsUsableArea.setMargins(this.monitorIndex, 0, this._box.height, 0, 0);",
            "desktopIconsUsableArea.setMargins(this.monitorIndex, 0, this._box.height + 36, 0, 0);"
        )
        docking_js.write_text(content, encoding="utf-8")
        print(f"[✔] Patched {docking_js}")

    app_icons_js = base_dir / "appIcons.js"
    if app_icons_js.exists():
        content = app_icons_js.read_text(encoding="utf-8")
        old_str = "class DockShowAppsIcon extends Dash.ShowAppsIcon {\n    _init(position) {\n        super._init();"
        safe_code = (
            "class DockShowAppsIcon extends Dash.ShowAppsIcon {\n"
            "    _init(position) {\n"
            "        super._init();\n"
            "        if (this.icon) {\n"
            "            try {\n"
            "                if ('icon_name' in this.icon) { this.icon.icon_name = 'view-app-grid'; }\n"
            "                else if (typeof this.icon.set_icon_name === 'function') { this.icon.set_icon_name('view-app-grid'); }\n"
            "                else if ('gicon' in this.icon && typeof Gio !== 'undefined') { this.icon.gicon = Gio.ThemedIcon.new('view-app-grid'); }\n"
            "                if (typeof this.icon.remove_style_class_name === 'function') { this.icon.remove_style_class_name('show-apps-icon'); }\n"
            "            } catch (e) {}\n"
            "        }"
        )
        if old_str in content:
            content = content.replace(old_str, safe_code)
        else:
            # Fallback replacement
            content = content.replace(
                "super._init();",
                "super._init(); if (this.icon) { try { if ('icon_name' in this.icon) this.icon.icon_name = 'view-app-grid'; else if (typeof this.icon.set_icon_name === 'function') this.icon.set_icon_name('view-app-grid'); if (typeof this.icon.remove_style_class_name === 'function') this.icon.remove_style_class_name('show-apps-icon'); } catch(e){} }",
                1
            )
        app_icons_js.write_text(content, encoding="utf-8")
        print(f"[✔] Patched {app_icons_js}")

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/d2d_extract/usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com")
    patch_d2d(target)
