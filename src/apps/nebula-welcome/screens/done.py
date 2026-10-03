"""
Nebula Welcome — Completion Screen
Final screen that completes the post-installation setup wizard.
"""

import os
import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

COMPLETION_FLAG = os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")

class DoneScreen(Gtk.Box):
    def __init__(self, on_finish):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_finish = on_finish
        self._build()

    def _build(self):
        self.set_margin_top(48)
        self.set_margin_bottom(64)
        self.set_margin_start(48)
        self.set_margin_end(48)
        self.set_hexpand(True)
        self.set_vexpand(True)

        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)

        icon = Gtk.Image.new_from_icon_name("emblem-default-symbolic")
        icon.set_pixel_size(84)
        center_box.append(icon)

        title = Gtk.Label()
        title.set_markup("<span font='34' weight='bold'>All Set!</span>")
        center_box.append(title)

        desc = Gtk.Label(label="NebulaOS setup has been completed successfully.\nExplore your system and discover a fresh way of working.")
        desc.set_justify(Gtk.Justification.CENTER)
        desc.add_css_class("welcome-subtitle")
        center_box.append(desc)

        # Finish button
        finish_btn = Gtk.Button(label="Start using NebulaOS")
        finish_btn.add_css_class("nebula-primary")
        finish_btn.set_margin_top(24)
        finish_btn.connect("clicked", lambda _: self._on_finish_clicked())
        center_box.append(finish_btn)

        self.append(center_box)

    def _on_finish_clicked(self):
        if callable(self._on_finish):
            self._on_finish()
