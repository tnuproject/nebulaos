"""
Nebula Welcome — Pictures Auto-Organizer Screen
Allows user to configure automatic relocation of all image files to Pictures folder.
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

ENABLED_FLAG = os.path.expanduser("~/.config/nebula/auto-organize-pictures.enabled")

class PicturesConfigScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._switch = None
        self._build()

    def _build(self):
        self.set_margin_top(48)
        self.set_margin_bottom(48)
        self.set_margin_start(64)
        self.set_margin_end(64)
        self.set_hexpand(True)
        self.set_vexpand(True)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label()
        title.set_markup("<span font='30' weight='bold'>Picture Organization</span>")
        header.append(title)

        sub = Gtk.Label(label="Keep your desktop and Downloads folder tidy.")
        sub.add_css_class("dim-label")
        header.append(sub)

        self.append(header)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_vexpand(True)
        clamp.set_valign(Gtk.Align.CENTER)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        card.add_css_class("feature-card")

        # Icon and header row
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        icon = Gtk.Image.new_from_icon_name("folder-pictures-symbolic")
        icon.set_pixel_size(44)
        row.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_box.set_hexpand(True)
        opt_title = Gtk.Label(label="Automatically move pictures to Pictures folder")
        opt_title.add_css_class("feature-title")
        opt_title.set_xalign(0.0)
        text_box.append(opt_title)

        opt_desc = Gtk.Label(label="All image files (.webp, .jpg, .png, .jpeg) downloaded or saved to your desktop will be automatically organized into your Pictures folder.")
        opt_desc.add_css_class("feature-desc")
        opt_desc.set_wrap(True)
        opt_desc.set_xalign(0.0)
        text_box.append(opt_desc)

        row.append(text_box)

        # Switch toggle
        self._switch = Gtk.Switch()
        self._switch.set_active(True)
        self._switch.set_valign(Gtk.Align.CENTER)
        row.append(self._switch)

        card.append(row)

        note = Gtk.Label()
        note.set_markup("<span font='12' alpha='65%'>Note: You can always change this setting later in system settings or the MyNebula app.</span>")
        note.set_wrap(True)
        note.set_xalign(0.0)
        card.append(note)

        clamp.set_child(card)
        self.append(clamp)

        # Navigation buttons
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_halign(Gtk.Align.CENTER)
        nav_box.set_margin_top(24)

        back_btn = Gtk.Button(label="Back")
        back_btn.add_css_class("nebula-secondary")
        back_btn.connect("clicked", lambda _: self._on_back())
        nav_box.append(back_btn)

        next_btn = Gtk.Button(label="Continue")
        next_btn.add_css_class("nebula-primary")
        next_btn.connect("clicked", lambda _: self._save_and_continue())
        nav_box.append(next_btn)

        self.append(nav_box)

    def _save_and_continue(self):
        os.makedirs(os.path.dirname(ENABLED_FLAG), exist_ok=True)
        if self._switch and self._switch.get_active():
            with open(ENABLED_FLAG, "w") as f:
                f.write("1")
        else:
            if os.path.exists(ENABLED_FLAG):
                try: os.remove(ENABLED_FLAG)
                except Exception: pass
        self._on_next()
