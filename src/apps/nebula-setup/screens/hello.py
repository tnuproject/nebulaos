"""
Nebula Setup — Hello Screen
Displays the wallpaper background with a slot-machine 'hello' animation
and a 'Start Installation' button.
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk
import os

WALLPAPER_PATH = "/usr/share/backgrounds/nebula/plains-default.svg"

# "Hello" in common Latin/Cyrillic/Arabic languages (excluding CJK)
HELLOS = [
    "hello",        # English
    "ciao",         # Italian
    "hola",         # Spanish
    "bonjour",      # French
    "hallo",        # German
    "olá",          # Portuguese
    "مرحبا",        # Arabic
    "привет",       # Russian
    "merhaba",      # Turkish
    "γεια σου",     # Greek
]


class HelloScreen(Gtk.Overlay):
    """Full-screen hello with parallax wallpaper and animated greeting."""

    def __init__(self, on_start):
        super().__init__()
        self._on_start = on_start
        self._hello_index = 0
        self._animation_timer = None
        self._blur_timer = None
        self._phase = "visible"   # "visible" | "blurring"

        self._build()

    def _build(self):
        # ── Background ────────────────────────────────────────────────────
        self._bg = Gtk.Picture()
        self._bg.set_hexpand(True)
        self._bg.set_vexpand(True)
        self._bg.set_content_fit(Gtk.ContentFit.COVER)
        self._load_wallpaper()
        self.set_child(self._bg)

        # ── Gradient overlay ──────────────────────────────────────────────
        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay_box.add_css_class("hello-overlay")
        overlay_box.set_hexpand(True)
        overlay_box.set_vexpand(True)
        self.add_overlay(overlay_box)

        # ── Center box ────────────────────────────────────────────────────
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)
        self.add_overlay(center_box)

        # Hello word label
        self._hello_label = Gtk.Label(label="hello")
        self._hello_label.add_css_class("hello-word")
        self._hello_label.add_css_class("visible")
        center_box.append(self._hello_label)

        # ── Bottom area ───────────────────────────────────────────────────
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        bottom_box.set_halign(Gtk.Align.CENTER)
        bottom_box.set_valign(Gtk.Align.END)
        bottom_box.set_margin_bottom(72)
        self.add_overlay(bottom_box)

        # Start button
        start_btn = Gtk.Button(label="Start Installation")
        start_btn.add_css_class("nebula-primary")
        start_btn.connect("clicked", self._on_start_clicked)
        bottom_box.append(start_btn)

    def _load_wallpaper(self):
        paths = [
            WALLPAPER_PATH,
            "/usr/share/backgrounds/nebula/plains-default.svg",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..",
                         "src", "branding", "wallpapers", "plains-default.svg"),
        ]
        for p in paths:
            if os.path.exists(p):
                self._bg.set_filename(p)
                return
        # Fallback solid color
        self._bg.set_can_shrink(True)

    # ── Animation ─────────────────────────────────────────────────────────

    def on_shown(self):
        self._start_animation()

    def _start_animation(self):
        if self._animation_timer:
            GLib.source_remove(self._animation_timer)
        # Show each word for ~1300ms, then blur for 300ms
        self._animation_timer = GLib.timeout_add(1300, self._begin_blur)

    def _begin_blur(self):
        """Start the blur-out transition."""
        self._hello_label.remove_css_class("visible")
        self._hello_label.add_css_class("blurring")
        self._blur_timer = GLib.timeout_add(300, self._swap_word)
        return False   # Don't repeat

    def _swap_word(self):
        """Update to next word and blur back in."""
        self._hello_index = (self._hello_index + 1) % len(HELLOS)
        self._hello_label.set_label(HELLOS[self._hello_index])
        self._hello_label.remove_css_class("blurring")
        self._hello_label.add_css_class("visible")
        # Schedule next cycle
        self._animation_timer = GLib.timeout_add(1300, self._begin_blur)
        return False

    def _stop_animation(self):
        for tid in [self._animation_timer, self._blur_timer]:
            if tid:
                try:
                    GLib.source_remove(tid)
                except Exception:
                    pass
        self._animation_timer = None
        self._blur_timer = None

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_start_clicked(self, _btn):
        self._stop_animation()
        self._on_start()
