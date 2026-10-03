"""
Nebula Welcome — Theme Selector Screen (Dark Mode / Light Mode)
Allows user to pick between Dark and Light mode during welcome setup,
applying the choice instantly and persisting it.
"""

import os
import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib


def apply_theme(scheme: str):
    """
    Applies theme ('prefer-dark' or 'default') immediately to libadwaita
    and GNOME desktop interface settings, and persists it across reboots.
    """
    try:
        style_mgr = Adw.StyleManager.get_default()
        if scheme == "prefer-dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

        settings = Gio.Settings.new("org.gnome.desktop.interface")
        settings.set_string("color-scheme", "prefer-dark" if scheme == "prefer-dark" else "default")
        settings.set_string("gtk-theme", "Adwaita-dark" if scheme == "prefer-dark" else "Adwaita")
        settings.apply()
    except Exception:
        pass

    try:
        val = "prefer-dark" if scheme == "prefer-dark" else "default"
        subprocess.run(["dconf", "write", "/org/gnome/desktop/interface/color-scheme", f"'{val}'"], check=False)
        gtk_theme = "Adwaita-dark" if scheme == "prefer-dark" else "Adwaita"
        subprocess.run(["dconf", "write", "/org/gnome/desktop/interface/gtk-theme", f"'{gtk_theme}'"], check=False)

        for cfg_dir in [os.path.expanduser("~/.config/gtk-3.0"), os.path.expanduser("~/.config/gtk-4.0")]:
            os.makedirs(cfg_dir, exist_ok=True)
            ini_file = os.path.join(cfg_dir, "settings.ini")
            lines = []
            if os.path.exists(ini_file):
                with open(ini_file, "r") as f:
                    lines = [l for l in f if not l.startswith("gtk-application-prefer-dark-theme") and not l.startswith("gtk-theme-name")]
            if "[Settings]" not in "".join(lines):
                lines.insert(0, "[Settings]\n")
            lines.append(f"gtk-application-prefer-dark-theme={1 if scheme == 'prefer-dark' else 0}\n")
            lines.append(f"gtk-theme-name={gtk_theme}\n")
            with open(ini_file, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


class ThemeScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected = "prefer-dark"
        self._build()

    def _build(self):
        self.set_margin_top(48)
        self.set_margin_bottom(48)
        self.set_margin_start(64)
        self.set_margin_end(64)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label()
        title.set_markup("<span font='30' weight='bold'>Choose Your Appearance</span>")
        header.append(title)

        sub = Gtk.Label(label="Select a dark or light style for NebulaOS. You can change this anytime in Settings.")
        sub.add_css_class("dim-label")
        header.append(sub)

        self.append(header)

        # ── Theme Choices ─────────────────────────────────────────────────
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=36)
        row.set_halign(Gtk.Align.CENTER)
        row.set_valign(Gtk.Align.CENTER)
        row.set_vexpand(True)
        self.append(row)

        self._dark_btn, self._dark_lbl = self._make_card(row, "prefer-dark", "Dark Mode", True)
        self._light_btn, self._light_lbl = self._make_card(row, "prefer-light", "Light Mode", False)

        # Check existing setting
        try:
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            curr = settings.get_string("color-scheme")
            if curr == "default":
                self._select("prefer-light")
            else:
                self._select("prefer-dark")
        except Exception:
            self._select("prefer-dark")

        # ── Footer ────────────────────────────────────────────────────────
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        footer.set_valign(Gtk.Align.END)
        self.append(footer)

        back_btn = Gtk.Button(label="Back")
        back_btn.add_css_class("nebula-secondary")
        back_btn.connect("clicked", lambda _: self._on_back())
        footer.append(back_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.append(spacer)

        continue_btn = Gtk.Button(label="Continue")
        continue_btn.add_css_class("nebula-primary")
        continue_btn.connect("clicked", lambda _: self._on_next())
        footer.append(continue_btn)

    def _make_card(self, parent, scheme, label_text, is_dark):
        btn = Gtk.Button()
        btn.add_css_class("theme-option")
        btn.connect("clicked", lambda _: self._select(scheme))
        parent.append(btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_halign(Gtk.Align.CENTER)

        # Mockup preview rectangle
        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        preview.add_css_class("theme-preview-dark" if is_dark else "theme-preview-light")

        # Fake top bar
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.set_margin_start(14)
        bar.set_margin_end(14)
        bar.set_margin_top(12)
        clock = Gtk.Label(label="10:42")
        clock.add_css_class("theme-preview-clock")
        bar.append(clock)
        preview.append(bar)

        # Fake dock
        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dock.set_halign(Gtk.Align.CENTER)
        dock.set_valign(Gtk.Align.END)
        dock.set_vexpand(True)
        dock.set_margin_bottom(12)
        for _ in range(5):
            dot = Gtk.Box()
            dot.set_size_request(24, 24)
            dot.set_css_classes(["theme-preview-dock-icon"])
            dock.append(dot)
        preview.append(dock)

        box.append(preview)

        lbl = Gtk.Label(label=label_text)
        lbl.add_css_class("theme-label")
        box.append(lbl)

        btn.set_child(box)
        return btn, lbl

    def _select(self, scheme: str):
        self._selected = scheme
        if scheme == "prefer-dark":
            self._dark_btn.add_css_class("selected")
            self._light_btn.remove_css_class("selected")
        else:
            self._light_btn.add_css_class("selected")
            self._dark_btn.remove_css_class("selected")

        # Apply immediately to desktop & window!
        apply_theme(scheme)
