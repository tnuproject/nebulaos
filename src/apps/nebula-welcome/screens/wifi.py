"""
Nebula Welcome — Wi-Fi Setup Screen (Mandatory)
Allows scanning, selecting and connecting to wireless networks.
Proceeding to MyNebula pairing requires an active network connection.
"""

import os
import subprocess
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

class WifiScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._is_connected = False
        self._connected_ssid = ""
        self._networks = []
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
        header.set_margin_bottom(24)

        icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic")
        icon.set_pixel_size(64)
        header.append(icon)

        title = Gtk.Label()
        title.set_markup("<span font='28' weight='bold'>Connect to Wi-Fi</span>")
        header.append(title)

        sub = Gtk.Label(label="A network connection is required to pair with MyNebula and enable system features.")
        sub.add_css_class("welcome-subtitle")
        header.append(sub)
        self.append(header)

        # Status badge box
        self._status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._status_box.set_halign(Gtk.Align.CENTER)
        self._status_box.set_margin_bottom(16)
        self._status_icon = Gtk.Image.new_from_icon_name("network-wireless-signal-excellent-symbolic")
        self._status_label = Gtk.Label(label="Scanning for networks…")
        self._status_label.set_css_classes(["welcome-subtitle"])
        self._status_box.append(self._status_icon)
        self._status_box.append(self._status_label)
        self.append(self._status_box)

        # Scrolled network list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_max_content_height(320)
        scrolled.set_min_content_height(200)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        scrolled.set_child(self._list_box)
        self.append(scrolled)

        # Password input section (hidden initially)
        self._pw_revealer = Gtk.Revealer()
        self._pw_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._pw_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._pw_box.set_margin_top(14)
        self._pw_box.set_halign(Gtk.Align.CENTER)

        self._pw_entry = Gtk.Entry()
        self._pw_entry.set_visibility(False)
        self._pw_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._pw_entry.set_placeholder_text("Network password")
        self._pw_entry.set_size_request(280, -1)
        self._pw_entry.connect("activate", lambda _: self._on_connect_clicked())
        self._pw_box.append(self._pw_entry)

        self._connect_btn = Gtk.Button(label="Connect")
        self._connect_btn.add_css_class("suggested-action")
        self._connect_btn.connect("clicked", lambda _: self._on_connect_clicked())
        self._pw_box.append(self._connect_btn)

        self._pw_revealer.set_child(self._pw_box)
        self.append(self._pw_revealer)

        # Bottom navigation
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_margin_top(28)
        nav_box.set_halign(Gtk.Align.CENTER)

        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.add_css_class("nebula-secondary")
        self._back_btn.connect("clicked", lambda _: self._on_back())
        nav_box.append(self._back_btn)

        self._refresh_btn = Gtk.Button()
        self._refresh_btn.set_icon_name("view-refresh-symbolic")
        self._refresh_btn.add_css_class("nebula-secondary")
        self._refresh_btn.set_tooltip_text("Rescan networks")
        self._refresh_btn.connect("clicked", lambda _: self._scan_networks())
        nav_box.append(self._refresh_btn)

        self._next_btn = Gtk.Button(label="Continue")
        self._next_btn.add_css_class("nebula-primary")
        self._next_btn.set_sensitive(False)  # Mandatory: disabled until connected
        self._next_btn.connect("clicked", lambda _: self._on_next())
        nav_box.append(self._next_btn)

        self.append(nav_box)
        self._selected_ssid = ""

    def on_shown(self):
        self._check_connection()
        self._scan_networks()

    def _check_connection(self):
        def _check():
            connected = False
            ssid = ""
            try:
                # Check active network manager status
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "dev"],
                    stderr=subprocess.DEVNULL, text=True
                )
                for line in out.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3 and parts[1] == "connected":
                        connected = True
                        ssid = parts[2]
                        break
            except Exception:
                pass

            GLib.idle_add(self._update_connection_status, connected, ssid)

        threading.Thread(target=_check, daemon=True).start()

    def _update_connection_status(self, connected: bool, ssid: str):
        self._is_connected = connected
        self._connected_ssid = ssid
        if connected:
            self._status_icon.set_from_icon_name("emblem-ok-symbolic")
            self._status_label.set_label(f"Connected: {ssid or 'Network Active'}")
            self._next_btn.set_sensitive(True)
            self._pw_revealer.set_reveal_child(False)
        else:
            self._status_icon.set_from_icon_name("network-wireless-signal-none-symbolic")
            self._status_label.set_label("Select a Wi-Fi network below to connect")
            self._next_btn.set_sensitive(False)

    def _scan_networks(self):
        self._status_label.set_label("Scanning for networks…")

        def _scan():
            nets = []
            try:
                subprocess.run(["nmcli", "dev", "wifi", "rescan"], stderr=subprocess.DEVNULL, check=False)
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                    stderr=subprocess.DEVNULL, text=True
                )
                seen = set()
                for line in out.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        in_use, ssid, signal_lvl, sec = parts[0], parts[1], parts[2], parts[3]
                        if ssid and ssid not in seen:
                            seen.add(ssid)
                            nets.append({
                                "in_use": in_use == "*",
                                "ssid": ssid,
                                "signal": int(signal_lvl) if signal_lvl.isdigit() else 50,
                                "security": sec
                            })
            except Exception:
                pass

            GLib.idle_add(self._populate_networks, nets)

        threading.Thread(target=_scan, daemon=True).start()

    def _populate_networks(self, nets):
        self._networks = nets
        # Clear existing rows
        while True:
            row = self._list_box.get_row_at_index(0)
            if not row:
                break
            self._list_box.remove(row)

        if not nets:
            row = Adw.ActionRow()
            row.set_title("No wireless networks found")
            row.set_subtitle("Ensure Wi-Fi is enabled or an Ethernet cable is connected.")
            self._list_box.append(row)
            return

        for net in nets:
            row = Adw.ActionRow()
            row.set_title(net["ssid"])
            sig = net["signal"]
            icon_name = "network-wireless-signal-excellent-symbolic" if sig >= 75 else \
                        "network-wireless-signal-good-symbolic" if sig >= 50 else \
                        "network-wireless-signal-ok-symbolic" if sig >= 25 else \
                        "network-wireless-signal-weak-symbolic"

            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))

            if net["in_use"]:
                self._is_connected = True
                self._next_btn.set_sensitive(True)
                connected_badge = Gtk.Label(label="Connected")
                connected_badge.add_css_class("accent")
                row.add_suffix(connected_badge)
            else:
                btn = Gtk.Button(label="Connect")
                btn.set_valign(Gtk.Align.CENTER)
                btn.connect("clicked", lambda _, s=net["ssid"], sec=net["security"]: self._on_select_network(s, sec))
                row.add_suffix(btn)

            self._list_box.append(row)

    def _on_select_network(self, ssid: str, security: str):
        self._selected_ssid = ssid
        if not security or security == "--":
            # Open network, connect directly
            self._connect_to_wifi(ssid, "")
        else:
            self._pw_entry.set_text("")
            self._pw_entry.set_placeholder_text(f"Password for {ssid}")
            self._pw_revealer.set_reveal_child(True)
            self._pw_entry.grab_focus()

    def _on_connect_clicked(self):
        pw = self._pw_entry.get_text()
        ssid = self._selected_ssid
        if ssid:
            self._connect_to_wifi(ssid, pw)

    def _connect_to_wifi(self, ssid: str, password: str):
        self._status_label.set_label(f"Connecting to {ssid}…")
        self._connect_btn.set_sensitive(False)

        def _do_connect():
            success = False
            try:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]
                if password:
                    cmd += ["password", password]
                res = subprocess.run(cmd, capture_output=True, text=True)
                success = (res.returncode == 0)
            except Exception:
                success = False

            GLib.idle_add(self._on_connect_result, success, ssid)

        threading.Thread(target=_do_connect, daemon=True).start()

    def _on_connect_result(self, success: bool, ssid: str):
        self._connect_btn.set_sensitive(True)
        if success:
            self._update_connection_status(True, ssid)
            self._scan_networks()
        else:
            self._status_label.set_label(f"Failed to connect to {ssid}. Check password.")
