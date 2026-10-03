#!/usr/bin/env python3
"""
NebulaOS Recovery — Early Boot Recovery Environment
GNOME / Libadwaita native recovery console.
Provides tools to connect to Wi-Fi, format disks, reinstall NebulaOS,
browse the web, and launch an emergency terminal.
"""

import os
import sys
import subprocess
import shutil
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Gio

from ui.wifi_dialog import WifiDialog
from ui.erase_dialog import EraseDialog
from backend.network import get_network_status


UTILITIES = [
    {
        "id": "disks",
        "icon": "org.gnome.DiskUtility",
        "fallback_icon": "drive-harddisk",
        "title": "Disk Utility",
        "desc": "Inspect, partition, and manage storage drives and volumes.",
        "action": "disks",
    },
    {
        "id": "browser",
        "icon": "firefox-esr",
        "fallback_icon": "web-browser",
        "title": "Web Browser",
        "desc": "Search for documentation, troubleshooting guides, or online support.",
        "action": "browser",
    },
    {
        "id": "terminal",
        "icon": "org.gnome.Terminal",
        "fallback_icon": "utilities-terminal",
        "title": "Root Recovery Terminal",
        "desc": "Open an emergency root command-line shell for maintenance and repair.",
        "action": "terminal",
    },
    {
        "id": "wifi",
        "icon": "network-wireless",
        "fallback_icon": "preferences-system-network",
        "title": "Network & Wi-Fi Setup",
        "desc": "Connect to Wi-Fi networks, configure Ethernet, and verify connectivity.",
        "action": "wifi",
    },
]


class RecoveryWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("NebulaOS Recovery")
        self.set_default_size(920, 680)
        self.fullscreen()
        self.set_decorated(False)
        self.connect("realize", lambda win: win.fullscreen())
        self.add_css_class("recovery-window")

        self._load_css()
        self._build_ui()
        self._check_initial_network()

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(_ROOT, "ui", "styles.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(root)

        # ── 1. GNOME Header Bar ───────────────────────────────────────────
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.add_css_class("recovery-header")
        header.set_show_end_title_buttons(False)   # No close/minimize/maximize
        header.set_show_start_title_buttons(False)  # No back button either

        # Centered title
        title_widget = Adw.WindowTitle(
            title="NebulaOS Recovery",
            subtitle="System Recovery & Maintenance"
        )
        header.set_title_widget(title_widget)

        # Left / Start: Network status button
        self._wifi_btn = Gtk.Button()
        self._wifi_btn.add_css_class("flat")
        self._wifi_btn.add_css_class("recovery-status-btn")
        self._wifi_btn.connect("clicked", lambda _: self._open_wifi_dialog())

        wifi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._wifi_icon = Gtk.Image.new_from_icon_name("network-wireless")
        self._wifi_icon.set_pixel_size(18)
        wifi_box.append(self._wifi_icon)

        self._wifi_lbl = Gtk.Label(label="Network")
        wifi_box.append(self._wifi_lbl)
        self._wifi_btn.set_child(wifi_box)
        header.pack_start(self._wifi_btn)

        # Right / End: Power buttons only (Restart, Shut Down) — no Exit/Close
        restart_btn = Gtk.Button(label="Restart")
        restart_btn.add_css_class("flat")
        restart_btn.connect("clicked", lambda _: self._restart())
        header.pack_end(restart_btn)

        shutdown_btn = Gtk.Button(label="Shut Down")
        shutdown_btn.add_css_class("flat")
        shutdown_btn.connect("clicked", lambda _: self._shutdown())
        header.pack_end(shutdown_btn)

        root.append(header)

        # ── 2. Scrollable Body with Clamp ─────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        root.append(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(780)
        clamp.set_tightening_threshold(600)
        clamp.set_margin_top(28)
        clamp.set_margin_bottom(28)
        clamp.set_margin_start(24)
        clamp.set_margin_end(24)
        scroll.set_child(clamp)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        clamp.set_child(content_box)

        # Hero Banner
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hero.set_halign(Gtk.Align.CENTER)
        content_box.append(hero)

        logo = Gtk.Image.new_from_icon_name("nebulaos-symbol")
        logo.set_pixel_size(64)
        logo.set_halign(Gtk.Align.CENTER)
        hero.append(logo)

        hero_title = Gtk.Label(label="Recovery Tools")
        hero_title.add_css_class("title-1")
        hero_title.set_halign(Gtk.Align.CENTER)
        hero.append(hero_title)

        hero_sub = Gtk.Label(
            label="Select a utility to troubleshoot, reinstall, or repair your computer."
        )
        hero_sub.add_css_class("body")
        hero_sub.add_css_class("dim-label")
        hero_sub.set_halign(Gtk.Align.CENTER)
        hero.append(hero_sub)

        # Boxed List of Tools (Standard GNOME Libadwaita layout)
        pref_group = Adw.PreferencesGroup()
        content_box.append(pref_group)

        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        pref_group.add(self._list_box)

        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

        for util in UTILITIES:
            row = self._create_utility_row(util, theme)
            self._list_box.append(row)
        # No footer / Exit to Live Desktop button


    def _create_utility_row(self, util: dict, theme: Gtk.IconTheme) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.add_css_class("activatable")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Full-color application icon (No symbolics!)
        icon_name = util["icon"]
        if not theme.has_icon(icon_name) and util.get("fallback_icon"):
            if theme.has_icon(util["fallback_icon"]):
                icon_name = util["fallback_icon"]

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(44)
        icon.set_valign(Gtk.Align.CENTER)
        box.append(icon)

        # Text column
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text_box.set_valign(Gtk.Align.CENTER)
        text_box.set_hexpand(True)

        title_lbl = Gtk.Label(label=util["title"])
        title_lbl.add_css_class("heading")
        title_lbl.set_halign(Gtk.Align.START)
        text_box.append(title_lbl)

        desc_lbl = Gtk.Label(label=util["desc"])
        desc_lbl.add_css_class("body")
        desc_lbl.add_css_class("dim-label")
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.set_wrap(True)
        text_box.append(desc_lbl)

        box.append(text_box)

        # Action Button
        btn = Gtk.Button(label="Launch")
        btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _, act=util["action"]: self.launch_utility(act))
        box.append(btn)

        row.set_child(box)
        return row

    def launch_utility(self, action: str):
        if action == "reinstall":
            self._launch_installer()
        elif action == "disks":
            self._launch_disk_utility()
        elif action == "browser":
            self._launch_browser()
        elif action == "terminal":
            self._launch_terminal()
        elif action == "wifi":
            self._open_wifi_dialog()

    def _launch_installer(self):
        paths = [
            "/usr/bin/install-nebula",
            "/usr/share/nebula-setup/nebula-setup.py",
            os.path.join(os.path.dirname(_ROOT), "nebula-setup", "nebula-setup.py"),
        ]
        for p in paths:
            if os.path.exists(p):
                cmd = ["python3", p] if p.endswith(".py") else [p]
                subprocess.Popen(cmd)
                return
        subprocess.Popen(["install-nebula"])

    def _launch_disk_utility(self):
        if shutil.which("gnome-disks"):
            subprocess.Popen(["gnome-disks"])
        else:
            self._open_erase_dialog()

    def _open_erase_dialog(self):
        dialog = EraseDialog(self)
        dialog.present()

    def _launch_browser(self):
        for b in ["firefox-esr", "firefox", "x-www-browser", "chromium"]:
            if shutil.which(b):
                subprocess.Popen([b])
                return

    def _launch_terminal(self):
        for t in ["gnome-terminal", "kgx", "ptyxis", "x-terminal-emulator", "xterm"]:
            if shutil.which(t):
                subprocess.Popen([t])
                return

    def _open_wifi_dialog(self):
        dialog = WifiDialog(self, on_status_changed=self._on_network_status_changed)
        dialog.present()

    def _on_network_status_changed(self, status):
        if status.get("connected"):
            name = status.get("name") or "Connected"
            self._wifi_lbl.set_label(name)
        else:
            self._wifi_lbl.set_label("Not Connected")

    def _check_initial_network(self):
        def _check():
            try:
                st = get_network_status()
                GLib.idle_add(self._on_network_status_changed, st)
            except Exception:
                pass
        import threading
        threading.Thread(target=_check, daemon=True).start()

    def _restart(self):
        try:
            subprocess.run(["systemctl", "reboot"], check=False)
        except Exception:
            pass

    def _shutdown(self):
        try:
            subprocess.run(["systemctl", "poweroff"], check=False)
        except Exception:
            pass

    def _exit_to_desktop(self):
        try:
            os.remove("/run/nebula-recovery-trigger")
        except Exception:
            pass
        try:
            with open("/run/nebula-desktop-unlocked", "w") as f:
                f.write("1")
        except Exception:
            pass
        self.get_application().quit()


class NebulaRecoveryApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.nebulaos.Recovery",
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        self._window = RecoveryWindow(self)
        self._window.present()


def main():
    if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
        os.environ.setdefault("DISPLAY", ":0")

    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ["GDK_BACKEND"] = "wayland"
    else:
        os.environ["GDK_BACKEND"] = "x11"

    app = NebulaRecoveryApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
