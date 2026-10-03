#!/usr/bin/env python3
"""
Generate .app bundles and compressed .tar.gz packages
for the NebulaOS repository (https://tnu-universe.it/) and drag-and-drop into /Applications.
"""

import os
import shutil
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
HATTER_APPS = ROOT_DIR / "src/branding/icons/Hatter/scalable/apps"
OUTPUT_DIR = ROOT_DIR / "webserver/packages"
BUNDLES_SRC_DIR = ROOT_DIR / "src/apps/bundles"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BUNDLES_SRC_DIR.mkdir(parents=True, exist_ok=True)

APPS = [
    {
        "folder": "PlanetBrowser.app",
        "tar_name": "PlanetBrowser.app.tar.gz",
        "name": "Planet Browser",
        "version": "1.4.0",
        "exec": "planet-browser",
        "icon": "PlanetBrowser.svg",
        "category": "Network",
        "code": """#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class PlanetBrowserWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Planet Browser")
        self.set_default_size(960, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Planet Browser")
        header.set_subtitle("NebulaOS Secure Web")
        self.set_titlebar(header)

        btn_back = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        btn_fwd = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        header.pack_start(btn_back)
        header.pack_start(btn_fwd)
        header.pack_start(btn_refresh)

        entry = Gtk.Entry()
        entry.set_text("https://tnu-universe.it")
        entry.set_width_chars(45)
        header.set_custom_title(entry)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_valign(Gtk.Align.CENTER)
        self.add(box)

        lbl = Gtk.Label()
        lbl.set_markup("<span size='xx-large' weight='bold'>🪐 Planet Browser</span>")
        box.pack_start(lbl, False, False, 0)

        sub = Gtk.Label(label="Fast, privacy-focused desktop web browsing for NebulaOS.\\nHardware-accelerated and ad-free.")
        sub.set_justify(Gtk.Justification.CENTER)
        box.pack_start(sub, False, False, 0)

def main():
    win = PlanetBrowserWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
"""
    },
    {
        "folder": "DeveloperStudio.app",
        "tar_name": "DeveloperStudio.app.tar.gz",
        "name": "Developer Studio",
        "version": "2.1.0",
        "exec": "developer-studio",
        "icon": "utilities-terminal.svg",
        "category": "Development",
        "code": """#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class DevStudioWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Developer Studio")
        self.set_default_size(900, 580)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Developer Studio")
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(12)
        self.add(box)

        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<span size='large' weight='bold'>Code Editor &amp; Workspace</span>")
        box.pack_start(lbl, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        box.pack_start(scroller, True, True, 0)

        textview = Gtk.TextView()
        textview.get_buffer().set_text("#!/usr/bin/env python3\\n# Welcome to Developer Studio on NebulaOS\\n\\ndef main():\\n    print('Hello NebulaOS!')\\n\\nif __name__ == '__main__':\\n    main()\\n")
        scroller.add(textview)

def main():
    win = DevStudioWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
"""
    },
    {
        "folder": "Calculator.app",
        "tar_name": "Calculator.app.tar.gz",
        "name": "Calculator",
        "version": "1.2.0",
        "exec": "calculator",
        "icon": "accessories-calculator.svg",
        "category": "Utility",
        "code": """#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class CalcWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Calculator")
        self.set_default_size(320, 420)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Calculator")
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(14)
        self.add(box)

        self.display = Gtk.Entry()
        self.display.set_text("0")
        self.display.set_alignment(1.0)
        box.pack_start(self.display, False, False, 6)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        box.pack_start(grid, True, True, 0)

        buttons = [
            ('C', 0, 0), ('(', 1, 0), (')', 2, 0), ('/', 3, 0),
            ('7', 0, 1), ('8', 1, 1), ('9', 2, 1), ('*', 3, 1),
            ('4', 0, 2), ('5', 1, 2), ('6', 2, 2), ('-', 3, 2),
            ('1', 0, 3), ('2', 1, 3), ('3', 2, 3), ('+', 3, 3),
            ('0', 0, 4), ('.', 1, 4), ('⌫', 2, 4), ('=', 3, 4)
        ]

        for text, c, r in buttons:
            btn = Gtk.Button(label=text)
            btn.set_hexpand(True)
            btn.set_vexpand(True)
            btn.connect("clicked", self.on_btn_clicked, text)
            grid.attach(btn, c, r, 1, 1)

    def on_btn_clicked(self, widget, text):
        curr = self.display.get_text()
        if text == 'C':
            self.display.set_text("0")
        elif text == '⌫':
            self.display.set_text(curr[:-1] if len(curr) > 1 else "0")
        elif text == '=':
            try:
                self.display.set_text(str(eval(curr)))
            except Exception:
                self.display.set_text("Error")
        else:
            if curr == "0" and text not in "./*+-":
                self.display.set_text(text)
            else:
                self.display.set_text(curr + text)

def main():
    win = CalcWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
"""
    },
    {
        "folder": "Weather.app",
        "tar_name": "Weather.app.tar.gz",
        "name": "Weather",
        "version": "1.1.0",
        "exec": "weather",
        "icon": "weather.svg",
        "category": "Utility",
        "code": """#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class WeatherWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Weather")
        self.set_default_size(520, 380)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Weather")
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_border_width(24)
        box.set_valign(Gtk.Align.CENTER)
        self.add(box)

        city = Gtk.Label()
        city.set_markup("<span size='xx-large' weight='bold'>Rome, Italy</span>")
        box.pack_start(city, False, False, 0)

        temp = Gtk.Label()
        temp.set_markup("<span size='32000' weight='bold' color='#38bdf8'>22°C</span>")
        box.pack_start(temp, False, False, 0)

        cond = Gtk.Label(label="Partly Sunny • Humidity 48% • Wind 12 km/h")
        box.pack_start(cond, False, False, 4)

def main():
    win = WeatherWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
"""
    },
    {
        "folder": "Notes.app",
        "tar_name": "Notes.app.tar.gz",
        "name": "Notes",
        "version": "1.0.2",
        "exec": "notes",
        "icon": "accessories-text-editor.svg",
        "category": "Utility",
        "code": """#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class NotesWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Notes")
        self.set_default_size(680, 480)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Notes")
        header.set_subtitle("Markdown Notes")
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.add(box)

        scroller = Gtk.ScrolledWindow()
        box.pack_start(scroller, True, True, 0)

        textview = Gtk.TextView()
        textview.get_buffer().set_text("# Welcome to NebulaOS Notes\\n\\n- Distraction free\\n- Instant autosave\\n- Drag and drop .app bundles supported!\\n")
        scroller.add(textview)

def main():
    win = NotesWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
"""
    }
]

print("Generating drag-and-drop .app bundles and repository packages...")

for app in APPS:
    # 1. Prepare bundle directory in bundles/ and webserver/packages/
    for dest_root in [BUNDLES_SRC_DIR, OUTPUT_DIR]:
        app_dir = dest_root / app["folder"]
        if app_dir.exists():
            shutil.rmtree(app_dir)
        app_dir.mkdir(parents=True)

        # Write AppRun
        apprun = app_dir / "AppRun"
        apprun.write_text(app["code"], encoding="utf-8")
        apprun.chmod(0o755)

        # Write Info.json
        info_json = app_dir / "Info.json"
        metadata = {
            "name": app["name"],
            "version": app["version"],
            "exec": "AppRun",
            "icon": "icon.svg",
            "category": app["category"]
        }
        import json
        info_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Copy icon from Hatter
        src_icon = HATTER_APPS / app["icon"]
        dest_icon = app_dir / "icon.svg"
        if src_icon.exists():
            shutil.copy(src_icon, dest_icon)
        else:
            # Fallback
            dest_icon.write_text("<svg width='48' height='48'><circle cx='24' cy='24' r='20' fill='#38bdf8'/></svg>", encoding="utf-8")

    # 2. Create .app.tar.gz in webserver/packages/
    tar_path = OUTPUT_DIR / app["tar_name"]
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(OUTPUT_DIR / app["folder"], arcname=app["folder"])
    print(f"Created: {app['folder']} and {app['tar_name']} ({os.path.getsize(tar_path)} bytes)")

print("All drag-and-drop software packages generated successfully!")
