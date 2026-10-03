"""
Nebula Welcome — Keyboard Layout Screen
Allows selecting and testing keyboard layout.
Applies immediately to user session and system configuration.
"""

import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

LAYOUTS = [
    {"name": "Italian", "code": "it", "desc": "Italian standard keyboard"},
    {"name": "English (US)", "code": "us", "desc": "US English standard QWERTY"},
    {"name": "English (UK)", "code": "gb", "desc": "United Kingdom English"},
    {"name": "Spanish", "code": "es", "desc": "Spanish standard layout"},
    {"name": "French", "code": "fr", "desc": "French AZERTY layout"},
    {"name": "German", "code": "de", "desc": "German QWERTZ layout"},
    {"name": "Portuguese", "code": "pt", "desc": "Portuguese standard layout"},
    {"name": "Russian", "code": "ru", "desc": "Russian Cyrillic layout"},
]

class KeyboardScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected_code = "it"
        self._build()

    def _build(self):
        self.set_margin_top(48)
        self.set_margin_bottom(48)
        self.set_margin_start(56)
        self.set_margin_end(56)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)
        header.set_margin_bottom(20)

        icon = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
        icon.set_pixel_size(64)
        header.append(icon)

        title = Gtk.Label()
        title.set_markup("<span font='28' weight='bold'>Keyboard Layout</span>")
        header.append(title)

        sub = Gtk.Label(label="Choose your keyboard input layout and test it below.")
        sub.add_css_class("welcome-subtitle")
        header.append(sub)
        self.append(header)

        # Layout list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_max_content_height(260)
        scrolled.set_min_content_height(180)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.connect("row-selected", self._on_row_selected)
        scrolled.set_child(self._list_box)
        self.append(scrolled)

        for item in LAYOUTS:
            row = Adw.ActionRow()
            row.set_title(item["name"])
            row.set_subtitle(item["desc"])
            row._code = item["code"]
            row.add_prefix(Gtk.Image.new_from_icon_name("input-keyboard-symbolic"))
            self._list_box.append(row)

        # Test entry box
        test_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        test_box.set_margin_top(16)
        test_box.set_halign(Gtk.Align.FILL)

        test_lbl = Gtk.Label(label="Test your keyboard here:")
        test_lbl.set_halign(Gtk.Align.START)
        test_lbl.add_css_class("caption")
        test_box.append(test_lbl)

        self._test_entry = Gtk.Entry()
        self._test_entry.set_placeholder_text("Type characters, punctuation and accents to test…")
        test_box.append(self._test_entry)
        self.append(test_box)

        # Navigation
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_margin_top(28)
        nav_box.set_halign(Gtk.Align.CENTER)

        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.add_css_class("nebula-secondary")
        self._back_btn.connect("clicked", lambda _: self._on_back())
        nav_box.append(self._back_btn)

        self._next_btn = Gtk.Button(label="Continue")
        self._next_btn.add_css_class("nebula-primary")
        self._next_btn.connect("clicked", lambda _: self._on_continue())
        nav_box.append(self._next_btn)

        self.append(nav_box)

    def on_shown(self):
        # Detect current layout or select Italian by default
        selected = False
        idx = 0
        while True:
            row = self._list_box.get_row_at_index(idx)
            if not row:
                break
            if hasattr(row, "_code") and row._code == self._selected_code:
                self._list_box.select_row(row)
                selected = True
                break
            idx += 1

        if not selected and self._list_box.get_row_at_index(0):
            self._list_box.select_row(self._list_box.get_row_at_index(0))

    def _on_row_selected(self, _box, row):
        if row and hasattr(row, "_code"):
            self._selected_code = row._code
            self._apply_layout(row._code)

    def _apply_layout(self, code: str):
        try:
            settings = Gio.Settings.new("org.gnome.desktop.input-sources")
            builder = GLib.VariantBuilder.new(GLib.VariantType.new("a(ss)"))
            builder.add_value(GLib.Variant.new_tuple(
                GLib.Variant.new_string("xkb"),
                GLib.Variant.new_string(code)
            ))
            settings.set_value("sources", builder.end())
        except Exception:
            pass

        try:
            subprocess.run(["setxkbmap", code], stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

        try:
            subprocess.run(["localectl", "set-x11-keymap", code], stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

    def _on_continue(self):
        self._apply_layout(self._selected_code)
        if callable(self._on_next):
            self._on_next()
