"""
Nebula Welcome — Multilingual Hello Screen
Greets the user by full name in multiple languages with smooth animations.
"""

import os
import pwd
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
try:
    gi.require_version("AccountsService", "1.0")
    from gi.repository import AccountsService
except Exception:
    AccountsService = None

from gi.repository import Gtk, GLib, Adw

WALLPAPER_PATH = "/usr/share/backgrounds/nebula/plains-default.svg"

HELLOS = [
    "Hello",         # English
    "Ciao",          # Italian
    "Bonjour",       # French
    "Hola",          # Spanish
    "Hallo",         # German
    "Olá",           # Portuguese
    "Привет",        # Russian
    "مرحبا",         # Arabic
    "Welcome to NebulaOS"   # Final — no trailing comma (format adds ", name!")
]

def get_user_full_name():
    username = GLib.get_user_name()
    if AccountsService:
        try:
            act = AccountsService.UserManager.get_default()
            user = act.get_user(username)
            if user and user.get_real_name():
                return user.get_real_name()
        except Exception:
            pass
    try:
        pw = pwd.getpwnam(username)
        gecos = pw.pw_gecos.split(',')[0].strip()
        if gecos:
            return gecos
    except Exception:
        pass
    return username.capitalize()

class HelloScreen(Gtk.Overlay):
    def __init__(self, on_start):
        super().__init__()
        self._on_start = on_start
        self._hello_index = 0
        self._timer_id = None
        self._user_name = get_user_full_name()

        self._build()

    def _build(self):
        # Background wallpaper
        self._bg = Gtk.Picture()
        self._bg.set_hexpand(True)
        self._bg.set_vexpand(True)
        self._bg.set_content_fit(Gtk.ContentFit.COVER)
        self._load_wallpaper()
        self.set_child(self._bg)

        # Gradient overlay
        overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.add_css_class("hello-overlay")
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        self.add_overlay(overlay)

        # Center Greeting Box
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)
        self.add_overlay(center_box)

        self._hello_label = Gtk.Label(label=f"Hello, {self._user_name}!")
        self._hello_label.add_css_class("welcome-hello-word")
        self._hello_label.add_css_class("visible")
        center_box.append(self._hello_label)

        sub_label = Gtk.Label(label="Let's configure your new NebulaOS experience")
        sub_label.add_css_class("welcome-subtitle")
        center_box.append(sub_label)

        # Bottom Button Box
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        bottom_box.set_halign(Gtk.Align.CENTER)
        bottom_box.set_valign(Gtk.Align.END)
        bottom_box.set_margin_bottom(64)
        self.add_overlay(bottom_box)

        start_btn = Gtk.Button(label="Get Started")
        start_btn.add_css_class("nebula-primary")
        start_btn.connect("clicked", lambda _: self._on_start_clicked())
        bottom_box.append(start_btn)

    def _load_wallpaper(self):
        paths = [
            WALLPAPER_PATH,
            "/usr/share/backgrounds/nebula/plains-default.svg",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "branding", "wallpapers", "plains-default.svg")
        ]
        for p in paths:
            if os.path.exists(p):
                self._bg.set_filename(p)
                return

    def on_shown(self):
        self._start_animation()

    def _start_animation(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(2200, self._cycle_hello)

    def _cycle_hello(self):
        self._hello_label.remove_css_class("visible")
        self._hello_label.add_css_class("blurring")

        def _update():
            self._hello_index = (self._hello_index + 1) % len(HELLOS)
            prefix = HELLOS[self._hello_index]
            self._hello_label.set_text(f"{prefix}, {self._user_name}!")
            self._hello_label.remove_css_class("blurring")
            self._hello_label.add_css_class("visible")
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(220, _update)
        return GLib.SOURCE_CONTINUE

    def _on_start_clicked(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._on_start()
