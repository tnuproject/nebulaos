"""
Nebula Welcome — Profile Picture Screen
Allows selecting a profile avatar from GNOME defaults or the default Nebula user avatar.
Updates AccountsService and local user profile picture.
"""

import os
import shutil
import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GdkPixbuf, Gio, GLib

FACES_DIR = "/usr/share/pixmaps/faces"

class AvatarScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected_path = os.path.expanduser("~/.face")
        if not os.path.exists(self._selected_path):
            self._selected_path = os.path.join(FACES_DIR, "default.png")
        self._build()

    def _build(self):
        self.set_margin_top(40)
        self.set_margin_bottom(44)
        self.set_margin_start(56)
        self.set_margin_end(56)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)
        header.set_margin_bottom(16)

        title = Gtk.Label()
        title.set_markup("<span font='28' weight='bold'>Choose Profile Picture</span>")
        header.append(title)

        sub = Gtk.Label(label="Select a photo for your account from the default collection.")
        sub.add_css_class("welcome-subtitle")
        header.append(sub)
        self.append(header)

        # Current Avatar Preview
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        preview_box.set_halign(Gtk.Align.CENTER)
        preview_box.set_margin_bottom(20)

        self._preview_image = Gtk.Image()
        self._preview_image.set_pixel_size(96)
        self._preview_image.add_css_class("avatar-preview-round")
        preview_box.append(self._preview_image)

        user_name = os.environ.get("USER", "nebula")
        name_lbl = Gtk.Label(label=user_name.capitalize())
        name_lbl.add_css_class("heading")
        preview_box.append(name_lbl)
        self.append(preview_box)

        # FlowBox for avatars
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_max_content_height(240)
        scrolled.set_min_content_height(180)

        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_max_children_per_line(8)
        self._flow.set_min_children_per_line(4)
        self._flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._flow.set_homogeneous(True)
        self._flow.set_column_spacing(14)
        self._flow.set_row_spacing(14)
        self._flow.connect("child-activated", self._on_child_activated)
        scrolled.set_child(self._flow)
        self.append(scrolled)

        self._populate_avatars()
        self._update_preview()

        # Navigation
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_margin_top(24)
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

    def _populate_avatars(self):
        avatar_paths = []
        default_user_path = os.path.join(FACES_DIR, "default.png")
        if os.path.exists(default_user_path):
            avatar_paths.append(default_user_path)

        if os.path.exists(FACES_DIR):
            for fname in sorted(os.listdir(FACES_DIR)):
                if fname.lower().endswith((".png", ".jpg", ".jpeg")) and fname != "default.png":
                    avatar_paths.append(os.path.join(FACES_DIR, fname))

        for path in avatar_paths:
            btn = Gtk.Button()
            btn.add_css_class("avatar-choice-btn")
            btn._path = path

            img = Gtk.Image.new_from_file(path)
            img.set_pixel_size(56)
            btn.set_child(img)
            self._flow.append(btn)

    def _on_child_activated(self, _flow, child):
        btn = child.get_child()
        if btn and hasattr(btn, "_path"):
            self._selected_path = btn._path
            self._update_preview()

    def _update_preview(self):
        if os.path.exists(self._selected_path):
            self._preview_image.set_from_file(self._selected_path)

    def _on_continue(self):
        # Apply avatar
        try:
            home = os.path.expanduser("~")
            face_dest = os.path.join(home, ".face")
            face_icon_dest = os.path.join(home, ".face.icon")
            if os.path.exists(self._selected_path):
                shutil.copy2(self._selected_path, face_dest)
                shutil.copy2(self._selected_path, face_icon_dest)
                os.chmod(face_dest, 0o644)
                os.chmod(face_icon_dest, 0o644)

            # Update AccountsService via D-Bus if possible
            user_name = os.environ.get("USER", "nebula")
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.Accounts",
                "/org/freedesktop/Accounts",
                "org.freedesktop.Accounts",
                None
            )
            user_path = proxy.FindUserByName("(s)", user_name)
            if user_path:
                user_proxy = Gio.DBusProxy.new_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.freedesktop.Accounts",
                    user_path,
                    "org.freedesktop.Accounts.User",
                    None
                )
                user_proxy.SetIconFile("(s)", face_dest)
        except Exception:
            pass

        if callable(self._on_next):
            self._on_next()
