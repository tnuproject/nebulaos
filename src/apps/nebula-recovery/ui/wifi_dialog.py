"""
Nebula Recovery — Wi-Fi & Network Configuration Sheet / Dialog
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw
import threading
from backend.network import scan_wifi_networks, connect_wifi, get_network_status


class WifiDialog(Gtk.Window):
    def __init__(self, parent_window, on_status_changed=None):
        super().__init__(transient_for=parent_window, modal=True)
        self.set_title("Wi-Fi & Network Configuration")
        self.set_default_size(480, 520)
        self.set_resizable(False)
        self._on_status_changed = on_status_changed

        self.add_css_class("recovery-sheet")
        self._selected_network = None
        self._networks = []

        self._build_ui()
        self._refresh_networks()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_start(20)
        root.set_margin_end(20)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        self.set_child(root)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root.append(header)

        title = Gtk.Label(label="Wi-Fi & Network")
        title.add_css_class("dialog-title")
        title.set_halign(Gtk.Align.START)
        header.append(title)

        self._status_lbl = Gtk.Label(label="Checking network status…")
        self._status_lbl.add_css_class("dialog-subtitle")
        self._status_lbl.set_halign(Gtk.Align.START)
        header.append(self._status_lbl)

        # Networks list box
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_min_content_height(220)
        root.append(scroll)

        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("utility-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-selected", self._on_row_selected)
        scroll.set_child(self._list_box)

        # Password input section
        self._pwd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._pwd_box.set_visible(False)
        root.append(self._pwd_box)

        pwd_lbl = Gtk.Label(label="Password:")
        pwd_lbl.set_halign(Gtk.Align.START)
        pwd_lbl.add_css_class("dialog-subtitle")
        self._pwd_box.append(pwd_lbl)

        self._pwd_entry = Gtk.Entry()
        try:
            self._pwd_entry.set_property("placeholder-text", "Enter Wi-Fi password")
        except Exception:
            pass
        self._pwd_entry.set_visibility(False)
        self._pwd_entry.connect("activate", lambda _: self._on_connect_clicked())
        self._pwd_box.append(self._pwd_entry)

        # Error / feedback label
        self._feedback_lbl = Gtk.Label()
        self._feedback_lbl.set_wrap(True)
        self._feedback_lbl.set_visible(False)
        self._feedback_lbl.set_halign(Gtk.Align.START)
        root.append(self._feedback_lbl)

        # Footer action buttons
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(footer)

        refresh_btn = Gtk.Button(label="Rescan")
        refresh_btn.add_css_class("recovery-secondary-btn")
        refresh_btn.connect("clicked", lambda _: self._refresh_networks())
        footer.append(refresh_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.append(spacer)

        cancel_btn = Gtk.Button(label="Close")
        cancel_btn.add_css_class("recovery-secondary-btn")
        cancel_btn.connect("clicked", lambda _: self.close())
        footer.append(cancel_btn)

        self._connect_btn = Gtk.Button(label="Connect")
        self._connect_btn.add_css_class("recovery-primary-btn")
        self._connect_btn.set_sensitive(False)
        self._connect_btn.connect("clicked", lambda _: self._on_connect_clicked())
        footer.append(self._connect_btn)

    def _refresh_networks(self):
        self._status_lbl.set_label("Scanning available wireless networks…")
        # Clear list
        while True:
            row = self._list_box.get_row_at_index(0)
            if not row:
                break
            self._list_box.remove(row)

        loading_lbl = Gtk.Label(label="Scanning…")
        loading_lbl.set_opacity(0.5)
        self._list_box.append(loading_lbl)

        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        status = get_network_status()
        nets = scan_wifi_networks()
        GLib.idle_add(self._update_network_list, status, nets)

    def _update_network_list(self, status, nets):
        while True:
            row = self._list_box.get_row_at_index(0)
            if not row:
                break
            self._list_box.remove(row)

        self._networks = nets

        if status["connected"]:
            name = status["name"] or "Network"
            ip = f" ({status['ip']})" if status["ip"] else ""
            self._status_lbl.set_label(f"✓ Connected to {name}{ip}")
        else:
            self._status_lbl.set_label("Not connected to any network.")

        if self._on_status_changed:
            self._on_status_changed(status)

        if not nets:
            no_nets = Gtk.Label(label="No wireless networks found.\n(Ethernet may be active)")
            no_nets.set_opacity(0.6)
            no_nets.set_justify(Gtk.Justification.CENTER)
            self._list_box.append(no_nets)
            return

        for net in nets:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            icon_img = Gtk.Image.new_from_icon_name("network-wireless")
            icon_img.set_pixel_size(18)
            box.append(icon_img)

            ssid_lbl = Gtk.Label(label=net["ssid"])
            ssid_lbl.set_hexpand(True)
            ssid_lbl.set_halign(Gtk.Align.START)
            if net["in_use"]:
                ssid_lbl.set_markup(f"<b>{net['ssid']}</b>  (Connected)")
            box.append(ssid_lbl)

            if net["is_secured"]:
                sec_lbl = Gtk.Label(label="Secured")
                sec_lbl.add_css_class("dim-label")
                sec_lbl.set_opacity(0.7)
                box.append(sec_lbl)

            sig_lbl = Gtk.Label(label=f"{net['signal']}%")
            sig_lbl.set_opacity(0.5)
            box.append(sig_lbl)

            row.set_child(box)
            self._list_box.append(row)

    def _on_row_selected(self, _lb, row):
        if not row:
            return
        idx = row.get_index()
        if 0 <= idx < len(self._networks):
            self._selected_network = self._networks[idx]
            self._connect_btn.set_sensitive(True)
            if self._selected_network["is_secured"] and not self._selected_network["in_use"]:
                self._pwd_box.set_visible(True)
                self._pwd_entry.grab_focus()
            else:
                self._pwd_box.set_visible(False)

    def _on_connect_clicked(self):
        if not self._selected_network:
            return

        ssid = self._selected_network["ssid"]
        pwd = self._pwd_entry.get_text() if self._selected_network["is_secured"] else None

        self._connect_btn.set_sensitive(False)
        self._feedback_lbl.set_label(f"Connecting to {ssid}…")
        self._feedback_lbl.set_visible(True)

        threading.Thread(target=self._connect_thread, args=(ssid, pwd), daemon=True).start()

    def _connect_thread(self, ssid, pwd):
        ok, msg = connect_wifi(ssid, pwd)
        GLib.idle_add(self._on_connect_finished, ok, msg)

    def _on_connect_finished(self, ok, msg):
        self._connect_btn.set_sensitive(True)
        if ok:
            self._feedback_lbl.set_markup(f"<span foreground='#27c93f'>{msg}</span>")
            self._refresh_networks()
        else:
            self._feedback_lbl.set_markup(f"<span foreground='#ff5f56'>Error: {msg}</span>")
