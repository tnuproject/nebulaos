#!/usr/bin/env python3
"""
NebulaOS Settings Application
Complete custom modern settings manager for NebulaOS using GTK4 & Libadwaita.
"""

import os
import sys
import subprocess
import threading
import shutil
import re
import json
import pwd

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango

APP_ID = "org.nebulaos.Settings"

# ── Helper Utilities ──────────────────────────────────────────────────────────

def run_cmd(cmd_list, timeout=4):
    """Run a shell command and return stdout stripped, or empty string on error."""
    try:
        res = subprocess.run(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return res.stdout.strip()
    except Exception:
        return ""

def gsettings_get(schema, key):
    try:
        res = subprocess.run(
            ["gsettings", "get", schema, key],
            stdout=subprocess.PIPE,
            text=True,
            timeout=2
        )
        val = res.stdout.strip()
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            return val[1:-1]
        return val
    except Exception:
        return ""

def gsettings_set(schema, key, val):
    def _worker():
        try:
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            elif isinstance(val, (int, float)):
                val_str = str(val)
            else:
                val_str = f"'{val}'"
            subprocess.run(["gsettings", "set", schema, key, val_str], timeout=3)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

# ── Modern UI Components ──────────────────────────────────────────────────────

def create_action_row(title, subtitle=None, icon_name=None, suffix_widget=None):
    row = Adw.ActionRow()
    row.set_title(title)
    if subtitle:
        row.set_subtitle(subtitle)
    if icon_name:
        img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(20)
        row.add_prefix(img)
    if suffix_widget:
        suffix_widget.set_valign(Gtk.Align.CENTER)
        row.add_suffix(suffix_widget)
        row.set_activatable_widget(suffix_widget)
    return row

def create_switch_row(title, subtitle=None, active=False, on_toggled=None, icon_name=None):
    sw = Gtk.Switch()
    sw.set_active(active)
    row = create_action_row(title, subtitle, icon_name, sw)
    if on_toggled:
        sw.connect("notify::active", lambda s, _: on_toggled(s.get_active()))
    return row, sw

def create_combo_row(title, options, active_idx=0, on_changed=None, icon_name=None):
    row = Adw.ComboRow()
    row.set_title(title)
    if icon_name:
        img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(20)
        row.add_prefix(img)
    
    model = Gtk.StringList.new(options)
    row.set_model(model)
    if 0 <= active_idx < len(options):
        row.set_selected(active_idx)
    
    if on_changed:
        row.connect("notify::selected", lambda r, _: on_changed(r.get_selected(), options[r.get_selected()]))
    return row

# ── Base Panel Class ─────────────────────────────────────────────────────────

class SettingsPanel(Adw.PreferencesPage):
    def __init__(self, title, icon_name=""):
        super().__init__()
        self.set_title(title)
        self.set_icon_name(icon_name)
        self._built = False

    def build_ui(self):
        if not self._built:
            self._built = True
            self.on_build()

    def on_build(self):
        pass

# ── Individual Panels ────────────────────────────────────────────────────────

class NetworkPanel(SettingsPanel):
    def on_build(self):
        self._refresh_timer = None
        self._connecting = False

        # Wi-Fi Section
        wifi_grp = Adw.PreferencesGroup(title="Wi-Fi", description="Manage wireless network connections")
        self.add(wifi_grp)

        wifi_state = run_cmd(["nmcli", "radio", "wifi"]) == "enabled"
        wifi_row, self.wifi_sw = create_switch_row(
            "Wi-Fi", "Enable or disable wireless networking",
            active=wifi_state,
            on_toggled=self._on_wifi_toggled,
            icon_name="network-wireless-symbolic"
        )
        wifi_grp.add(wifi_row)

        # Active Network Row
        self.btn_disconnect = Gtk.Button(label="Disconnect", css_classes=["flat"])
        self.btn_disconnect.set_visible(False)
        self.btn_disconnect.connect("clicked", self._on_disconnect_active)

        self.active_net_row = create_action_row(
            "Network Status",
            "Scanning...",
            "network-wireless-signal-excellent-symbolic",
            self.btn_disconnect
        )
        wifi_grp.add(self.active_net_row)

        # Available Networks List
        self.avail_grp = Adw.PreferencesGroup(title="Available Networks", description="Select a Wi-Fi network to connect")
        self.add(self.avail_grp)

        self.networks_box = Gtk.ListBox(css_classes=["boxed-list"])
        self.avail_grp.add(self.networks_box)

        # Wired Section
        wired_grp = Adw.PreferencesGroup(title="Wired Connection")
        self.add(wired_grp)
        wired_state = run_cmd(["nmcli", "-t", "-f", "TYPE,STATE", "dev"])
        wired_active = "ethernet:connected" in wired_state
        wired_row = create_action_row(
            "Ethernet",
            "Connected" if wired_active else "Disconnected or Cable unplugged",
            icon_name="network-wired-symbolic"
        )
        wired_grp.add(wired_row)

        # VPN Section
        vpn_grp = Adw.PreferencesGroup(title="Virtual Private Network (VPN)")
        self.add(vpn_grp)
        btn_vpn = Gtk.Button(label="Configure VPN")
        btn_vpn.connect("clicked", lambda _: subprocess.Popen(["nm-connection-editor"]))
        vpn_row = create_action_row("VPN Connections", "Add and manage encrypted tunnels", "network-vpn-symbolic", btn_vpn)
        vpn_grp.add(vpn_row)

        self._refresh_networks()
        # Periodic refresh every 4 seconds
        self._refresh_timer = GLib.timeout_add_seconds(4, self._refresh_networks)

    def _on_wifi_toggled(self, active):
        cmd = ["nmcli", "radio", "wifi", "on" if active else "off"]
        threading.Thread(target=lambda: subprocess.run(cmd), daemon=True).start()
        GLib.timeout_add(1000, self._refresh_networks)

    def _on_disconnect_active(self, btn):
        curr_ssid = getattr(self, "_active_ssid", None)
        if curr_ssid:
            btn.set_sensitive(False)
            def _disc():
                run_cmd(["nmcli", "con", "down", "id", curr_ssid])
                GLib.idle_add(lambda: (btn.set_sensitive(True), self._refresh_networks()))
            threading.Thread(target=_disc, daemon=True).start()

    def _connect_to_network(self, ssid, security):
        if self._connecting:
            return
        if not security or security == "--":
            # Open network
            self._do_connect(ssid, None)
            return

        # Prompt for password
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=f"Connect to {ssid}",
            body="Enter the Wi-Fi network password:"
        )
        entry = Gtk.PasswordEntry(activates_default=True, show_peek_icon=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("connect", "Connect")
        dialog.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("connect")

        def _resp(d, r):
            if r == "connect":
                pwd = entry.get_text()
                self._do_connect(ssid, pwd)

        dialog.connect("response", _resp)
        dialog.present()

    def _do_connect(self, ssid, password):
        self._connecting = True
        self.active_net_row.set_subtitle(f"Connecting to {ssid}...")

        def _task():
            if password:
                run_cmd(["nmcli", "dev", "wifi", "connect", ssid, "password", password], timeout=15)
            else:
                run_cmd(["nmcli", "dev", "wifi", "connect", ssid], timeout=15)
            self._connecting = False
            GLib.idle_add(self._refresh_networks)

        threading.Thread(target=_task, daemon=True).start()

    def _refresh_networks(self):
        if self._connecting:
            return GLib.SOURCE_CONTINUE

        def _scan():
            active_ssid = ""
            active_out = run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
            for line in active_out.splitlines():
                if line.startswith("yes:"):
                    active_ssid = line.split(":", 1)[1].strip()
                    break

            list_out = run_cmd(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
            networks = []
            seen = set()
            for line in list_out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and parts[0] and parts[0] not in seen:
                    ssid = parts[0].strip()
                    if ssid:
                        seen.add(ssid)
                        sig = parts[1].strip() if len(parts) > 1 else "50"
                        sec = parts[2].strip() if len(parts) > 2 else ""
                        networks.append((ssid, sig, sec))

            def _update():
                self._active_ssid = active_ssid
                if active_ssid:
                    self.active_net_row.set_subtitle(f"Connected to {active_ssid}")
                    self.btn_disconnect.set_visible(True)
                else:
                    self.active_net_row.set_subtitle("Not connected")
                    self.btn_disconnect.set_visible(False)

                # Clear previous available network rows
                child = self.networks_box.get_first_child()
                while child:
                    next_c = child.get_next_sibling()
                    self.networks_box.remove(child)
                    child = next_c

                if not networks:
                    empty_row = Adw.ActionRow(title="No Wi-Fi Networks Found", subtitle="Ensure Wi-Fi is turned on and in range")
                    self.networks_box.append(empty_row)
                    return GLib.SOURCE_REMOVE

                for ssid, sig, sec in networks[:12]:
                    sig_int = int(sig) if sig.isdigit() else 50
                    if sig_int >= 75:
                        sig_icon = "network-wireless-signal-excellent-symbolic"
                    elif sig_int >= 50:
                        sig_icon = "network-wireless-signal-good-symbolic"
                    elif sig_int >= 25:
                        sig_icon = "network-wireless-signal-ok-symbolic"
                    else:
                        sig_icon = "network-wireless-signal-weak-symbolic"

                    is_active = (ssid == active_ssid)
                    sec_desc = "Secured" if sec and sec != "--" else "Open"
                    row = Adw.ActionRow(
                        title=ssid,
                        subtitle=f"{sig}% • {sec_desc}" + (" • Connected" if is_active else "")
                    )
                    img = Gtk.Image.new_from_icon_name(sig_icon)
                    row.add_prefix(img)

                    if is_active:
                        badge = Gtk.Label(label="Connected", css_classes=["accent", "bold"])
                        row.add_suffix(badge)
                    else:
                        btn = Gtk.Button(label="Connect", css_classes=["suggested-action"])
                        btn.connect("clicked", lambda _, s=ssid, sc=sec: self._connect_to_network(s, sc))
                        row.add_suffix(btn)
                        row.set_activatable_widget(btn)

                    self.networks_box.append(row)

                return GLib.SOURCE_REMOVE

            GLib.idle_add(_update)

        threading.Thread(target=_scan, daemon=True).start()
        return GLib.SOURCE_CONTINUE


class BluetoothPanel(SettingsPanel):
    def on_build(self):
        grp = Adw.PreferencesGroup(title="Bluetooth", description="Connect headphones, mice, and accessories")
        self.add(grp)

        bt_out = run_cmd(["rfkill", "list", "bluetooth"])
        bt_active = "Soft blocked: yes" not in bt_out

        sw_row, _ = create_switch_row(
            "Bluetooth", "Enable or disable Bluetooth radio",
            active=bt_active,
            on_toggled=self._on_bt_toggle,
            icon_name="bluetooth-symbolic"
        )
        grp.add(sw_row)

        dev_grp = Adw.PreferencesGroup(title="Paired Devices")
        self.add(dev_grp)

        dev_out = run_cmd(["bluetoothctl", "devices"])
        if dev_out:
            for line in dev_out.splitlines()[:6]:
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    mac, name = parts[1], parts[2]
                    btn_forget = Gtk.Button(label="Disconnect")
                    btn_forget.connect("clicked", lambda _, m=mac: subprocess.run(["bluetoothctl", "disconnect", m]))
                    row = create_action_row(name, mac, "audio-headphones-symbolic", btn_forget)
                    dev_grp.add(row)
        else:
            dev_grp.add(create_action_row("No Paired Devices", "Devices in pairing mode will appear here"))

        action_grp = Adw.PreferencesGroup(title="Discovery")
        self.add(action_grp)
        btn_scan = Gtk.Button(label="Scan")
        btn_scan.connect("clicked", lambda _: subprocess.Popen(["bluetoothctl", "scan", "on"]))
        action_grp.add(create_action_row("Pair New Device", "Make system discoverable to nearby accessories", suffix_widget=btn_scan))

    def _on_bt_toggle(self, active):
        cmd = ["rfkill", "unblock" if active else "block", "bluetooth"]
        threading.Thread(target=lambda: subprocess.run(cmd), daemon=True).start()


class KeyboardPanel(SettingsPanel):
    def on_build(self):
        input_grp = Adw.PreferencesGroup(title="Input Sources")
        self.add(input_grp)

        layouts = ["English (US)", "Italian", "Spanish", "French", "German", "Portuguese", "Russian"]
        layout_codes = ["us", "it", "es", "fr", "de", "pt", "ru"]

        curr_xkb = run_cmd(["setxkbmap", "-query"])
        active_code = "us"
        for line in curr_xkb.splitlines():
            if line.strip().startswith("layout:"):
                active_code = line.split(":", 1)[1].strip().split(",")[0]
                break

        curr_idx = 0
        if active_code in layout_codes:
            curr_idx = layout_codes.index(active_code)

        def _set_layout(idx, _):
            code = layout_codes[idx]
            subprocess.run(["setxkbmap", code], check=False)
            gsettings_set("org.gnome.desktop.input-sources", "sources", [('xkb', code)])

        input_grp.add(create_combo_row("Keyboard Layout", layouts, curr_idx, _set_layout, "input-keyboard-symbolic"))

        # Typing settings
        typing_grp = Adw.PreferencesGroup(title="Typing and Repeat Keys")
        self.add(typing_grp)

        repeat_row, _ = create_switch_row(
            "Key Repeat", "Repeat keys when pressed and held",
            active=gsettings_get("org.gnome.desktop.peripherals.keyboard", "repeat") == "true",
            on_toggled=lambda a: gsettings_set("org.gnome.desktop.peripherals.keyboard", "repeat", a)
        )
        typing_grp.add(repeat_row)


class LanguagePanel(SettingsPanel):
    def on_build(self):
        lang_grp = Adw.PreferencesGroup(title="Language & Formats")
        self.add(lang_grp)

        langs = ["English (United States)", "Italiano", "Español", "Français", "Deutsch"]
        lang_grp.add(create_combo_row("System Language", langs, 0, None, "preferences-desktop-locale-symbolic"))

        formats = ["United States (12h, MM/DD/YYYY)", "Europe (24h, DD/MM/YYYY)"]
        lang_grp.add(create_combo_row("Regional Formats", formats, 0, None, "preferences-system-time-symbolic"))


class MyNebulaPanel(SettingsPanel):
    def on_build(self):
        self.dev_grp = Adw.PreferencesGroup(title="Connected Device", description="Companion phone paired with this system")
        self.add(self.dev_grp)

        self.pairing_row = Adw.ActionRow(
            title="Association Status",
            subtitle="Checking paired device..."
        )
        img = Gtk.Image.new_from_icon_name("phone-symbolic")
        img.set_pixel_size(24)
        self.pairing_row.add_prefix(img)

        self.btn_unpair = Gtk.Button(label="Unpair", css_classes=["destructive-action"])
        self.btn_unpair.set_visible(False)
        self.btn_unpair.connect("clicked", self._unpair_device)
        self.pairing_row.add_suffix(self.btn_unpair)
        self.dev_grp.add(self.pairing_row)

        # ── Pairing QR + Token (shown when not paired) ──
        pair_grp = Adw.PreferencesGroup(title="Connect a Device", description="Open the MyNebula app on Android and scan this code — both devices must be on the same Wi-Fi network")
        self.add(pair_grp)

        # Token display row
        tok_row = Adw.ActionRow(title="Pairing Code", subtitle="Enter this PIN on your Android phone")
        self.token_lbl = Gtk.Label(label="Loading...", css_classes=["title-2", "monospace"])
        self.token_lbl.set_selectable(True)
        tok_row.add_suffix(self.token_lbl)
        pair_grp.add(tok_row)

        # Refresh button row
        refresh_row = Adw.ActionRow(title="Pairing QR Code", subtitle="Scan with your Android camera from MyNebula")
        refresh_btn = Gtk.Button(label="Refresh Code", css_classes=["flat"])
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", lambda _: self._load_pairing_info())
        refresh_row.add_suffix(refresh_btn)
        pair_grp.add(refresh_row)

        # QR code image row
        self.qr_row = Adw.PreferencesRow()
        self.qr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8)
        self.qr_box.set_halign(Gtk.Align.CENTER)
        self.qr_pic = Gtk.Picture()
        self.qr_pic.set_size_request(200, 200)
        self.qr_box.append(self.qr_pic)
        self.qr_row.set_child(self.qr_box)
        pair_grp.add(self.qr_row)

        # ── Gallery Sync ──
        self.gallery_grp = Adw.PreferencesGroup(
            title="Gallery Sync",
            description="Real bidirectional photo synchronization between NebulaOS (~/Pictures) and mobile gallery"
        )
        self.add(self.gallery_grp)

        self.gallery_toggle_row, self.gallery_sw = create_switch_row(
            "Sync Mobile Gallery",
            "Automatically synchronize photos bidirectionally with paired phone",
            active=False,
            on_toggled=self._on_gallery_sync_toggled,
            icon_name="folder-pictures-symbolic"
        )
        self.gallery_grp.add(self.gallery_toggle_row)

        self.gallery_device_row = create_action_row(
            "Paired Device",
            "Checking...",
            icon_name="phone-symbolic"
        )
        self.gallery_grp.add(self.gallery_device_row)

        self.gallery_status_row = create_action_row(
            "Sync Status",
            "Disabled",
            icon_name="emblem-synchronizing-symbolic"
        )
        self.gallery_grp.add(self.gallery_status_row)

        self.gallery_last_sync_row = create_action_row(
            "Last Synchronization",
            "Never",
            icon_name="document-open-recent-symbolic"
        )
        self.gallery_grp.add(self.gallery_last_sync_row)

        self.gallery_progress_row = create_action_row(
            "Transfer Progress",
            "",
            icon_name="network-transmit-receive-symbolic"
        )
        self.gallery_progress_row.set_visible(False)
        self.gallery_grp.add(self.gallery_progress_row)

        self.gallery_error_row = create_action_row(
            "Sync Issues",
            "",
            icon_name="dialog-warning-symbolic"
        )
        self.gallery_error_row.set_visible(False)
        self.gallery_grp.add(self.gallery_error_row)

        self.gallery_actions_row = Adw.ActionRow(title="Sync Controls", subtitle="Manual trigger and temporary pause")
        self.btn_sync_now = Gtk.Button(label="Sync Now", css_classes=["suggested-action"])
        self.btn_sync_now.set_valign(Gtk.Align.CENTER)
        self.btn_sync_now.connect("clicked", self._sync_gallery_now)
        self.gallery_actions_row.add_suffix(self.btn_sync_now)

        self.btn_pause_sync = Gtk.Button(label="Pause Sync", css_classes=["flat"])
        self.btn_pause_sync.set_valign(Gtk.Align.CENTER)
        self.btn_pause_sync.connect("clicked", self._toggle_pause_sync)
        self.gallery_actions_row.add_suffix(self.btn_pause_sync)

        self.gallery_grp.add(self.gallery_actions_row)

        # ── Screen Mirroring ──
        mirror_grp = Adw.PreferencesGroup(
            title="Screen Mirroring",
            description="View and control your Android display wirelessly on your PC"
        )
        self.add(mirror_grp)

        mirror_row = Adw.ActionRow(
            title="Phone Screen Mirroring",
            subtitle="Send mirror request to phone and open live streaming window"
        )
        mirror_icon = Gtk.Image.new_from_icon_name("video-display-symbolic")
        mirror_icon.set_pixel_size(20)
        mirror_row.add_prefix(mirror_icon)

        btn_mirror = Gtk.Button(label="Mirror Screen", css_classes=["suggested-action"])
        btn_mirror.set_valign(Gtk.Align.CENTER)
        btn_mirror.connect("clicked", self._start_screen_mirror)
        mirror_row.add_suffix(btn_mirror)
        mirror_grp.add(mirror_row)

        # ── Other Features ──
        feat_grp = Adw.PreferencesGroup(title="Features")
        self.add(feat_grp)
        petal_row, _ = create_switch_row("PetalDrop Direct Share", "Fast wireless P2P file transfers", active=True)
        feat_grp.add(petal_row)
        notif_row, _ = create_switch_row("Notification Mirroring", "Receive phone alerts directly on the desktop", active=True)
        feat_grp.add(notif_row)

        self._check_pairing_status()
        self._load_pairing_info()
        self._update_gallery_sync_ui()
        GLib.timeout_add_seconds(3, lambda: (self._update_gallery_sync_ui(), True)[1])

    def _on_gallery_sync_toggled(self, active):
        def _task():
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:53317/api/gallery/sync/toggle",
                    data=json.dumps({"enabled": active}).encode(),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
            self._update_gallery_sync_ui()
        threading.Thread(target=_task, daemon=True).start()

    def _sync_gallery_now(self, btn):
        btn.set_sensitive(False)
        def _task():
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:53317/api/gallery/sync/now",
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
            GLib.idle_add(lambda: btn.set_sensitive(True))
            self._update_gallery_sync_ui()
        threading.Thread(target=_task, daemon=True).start()

    def _toggle_pause_sync(self, btn):
        def _task():
            is_paused = (btn.get_label() == "Resume Sync")
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:53317/api/gallery/sync/pause",
                    data=json.dumps({"paused": not is_paused}).encode(),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
            self._update_gallery_sync_ui()
        threading.Thread(target=_task, daemon=True).start()

    def _start_screen_mirror(self, _):
        def _launch():
            script_path = "/usr/share/mynebula-screen-mirror/screen-mirror.py"
            if not os.path.exists(script_path):
                script_path = os.path.join(os.path.dirname(__file__), "../mynebula-screen-mirror/screen-mirror.py")
            subprocess.Popen(["python3", script_path])
        threading.Thread(target=_launch, daemon=True).start()

    def _update_gallery_sync_ui(self):
        def _fetch():
            data = {}
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:53317/api/gallery/sync/status", timeout=2) as resp:
                    data = json.loads(resp.read().decode())
            except Exception:
                pass

            def _apply():
                enabled = data.get("enabled", False)
                paused = data.get("paused", False)
                status_str = data.get("status", "idle").capitalize()
                progress = data.get("progress", "")
                last_sync = data.get("last_sync", "Never")
                last_error = data.get("last_error")
                dev_name = data.get("paired_device_name") or "No device connected"

                if self.gallery_sw.get_active() != enabled:
                    self.gallery_sw.set_active(enabled)

                self.gallery_device_row.set_subtitle(dev_name)

                if not enabled:
                    self.gallery_status_row.set_subtitle("Disabled (turn ON toggle above to activate)")
                elif paused:
                    self.gallery_status_row.set_subtitle("Paused")
                elif status_str == "Syncing":
                    self.gallery_status_row.set_subtitle("Syncing photos...")
                else:
                    self.gallery_status_row.set_subtitle("Idle • Up to date")

                self.gallery_last_sync_row.set_subtitle(last_sync)

                if progress and enabled:
                    self.gallery_progress_row.set_subtitle(progress)
                    self.gallery_progress_row.set_visible(True)
                else:
                    self.gallery_progress_row.set_visible(False)

                if last_error and enabled:
                    self.gallery_error_row.set_subtitle(last_error)
                    self.gallery_error_row.set_visible(True)
                else:
                    self.gallery_error_row.set_visible(False)

                self.btn_sync_now.set_sensitive(enabled and not paused)
                self.btn_pause_sync.set_sensitive(enabled)
                self.btn_pause_sync.set_label("Resume Sync" if paused else "Pause Sync")

                return GLib.SOURCE_REMOVE

            GLib.idle_add(_apply)

        threading.Thread(target=_fetch, daemon=True).start()

    def _check_pairing_status(self):
        def _task():
            paired_name = None
            # Check local file state
            pairing_files = [
                os.path.expanduser("~/.config/nebula/companion_pairing.json"),
                os.path.expanduser("~/.config/nebula/mynebula_pairing.json")
            ]
            for pf in pairing_files:
                if os.path.exists(pf):
                    try:
                        with open(pf, "r") as f:
                            data = json.load(f)
                        pdev = data.get("paired_device")
                        if pdev and isinstance(pdev, dict) and pdev.get("name"):
                            paired_name = pdev.get("name")
                            break
                    except Exception:
                        pass

            # Also query companion status API
            if not paired_name:
                try:
                    import urllib.request
                    req = urllib.request.Request("http://127.0.0.1:53317/api/status", headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        sdata = json.loads(resp.read().decode())
                        pdev = sdata.get("paired_device")
                        if pdev and isinstance(pdev, dict) and pdev.get("name"):
                            paired_name = pdev.get("name")
                except Exception:
                    pass

            def _update():
                if paired_name:
                    self.pairing_row.set_title(f"Associato con {paired_name}")
                    self.pairing_row.set_subtitle("Device connected and ready for synchronization")
                    self.btn_unpair.set_visible(True)
                else:
                    self.pairing_row.set_title("Associato con nessun dispositivo")
                    self.pairing_row.set_subtitle("Open MyNebula on Android on your Wi-Fi network to connect")
                    self.btn_unpair.set_visible(False)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_update)

        threading.Thread(target=_task, daemon=True).start()

    def _unpair_device(self, btn):
        btn.set_sensitive(False)
        def _task():
            try:
                import urllib.request
                req = urllib.request.Request("http://127.0.0.1:53317/api/unpair", data=b"{}", headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass
            pairing_files = [
                os.path.expanduser("~/.config/nebula/companion_pairing.json"),
                os.path.expanduser("~/.config/nebula/mynebula_pairing.json")
            ]
            for pf in pairing_files:
                if os.path.exists(pf):
                    try:
                        with open(pf, "r") as f:
                            data = json.load(f)
                        data["paired_device"] = None
                        with open(pf, "w") as f:
                            json.dump(data, f, indent=2)
                    except Exception:
                        pass

            GLib.idle_add(lambda: (btn.set_sensitive(True), self._check_pairing_status(), self._load_pairing_info()))

        threading.Thread(target=_task, daemon=True).start()

    def _load_pairing_info(self):
        def _task():
            token = None
            local_ip = None
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:53317/api/status", timeout=2) as resp:
                    sdata = json.loads(resp.read().decode())
                    token = sdata.get("pairing_token")
                    local_ip = sdata.get("local_ip")
            except Exception:
                pass

            qr_text = token or "offline"
            if token and local_ip:
                qr_text = f"http://{local_ip}:53317/?pair={token}"

            qr_image_path = None
            try:
                import qrcode  # type: ignore
                qr = qrcode.QRCode(border=2, box_size=6)
                qr.add_data(qr_text)
                qr.make(fit=True)
                img = qr.make_image(fill_color="white", back_color="#1e1e2e")
                qr_image_path = "/tmp/nebula_pairing_qr.png"
                img.save(qr_image_path)
            except Exception:
                qr_image_path = None

            def _update():
                self.token_lbl.set_text(token if token else "Companion offline")
                if qr_image_path and os.path.exists(qr_image_path):
                    self.qr_pic.set_filename(qr_image_path)
                    self.qr_box.set_visible(True)
                else:
                    self.qr_box.set_visible(False)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_update)

        threading.Thread(target=_task, daemon=True).start()


class AppearancePanel(SettingsPanel):
    def on_build(self):
        style_grp = Adw.PreferencesGroup(title="Appearance Style")
        self.add(style_grp)

        is_dark = "prefer-dark" in gsettings_get("org.gnome.desktop.interface", "color-scheme")
        dark_row, _ = create_switch_row(
            "Dark Theme", "Apply system-wide dark style to all applications",
            active=is_dark,
            on_toggled=self._on_theme_toggled,
            icon_name="weather-clear-night-symbolic"
        )
        style_grp.add(dark_row)

        # Wallpaper Previews Grid
        wall_grp = Adw.PreferencesGroup(title="Wallpapers", description="Select a wallpaper preview to set your desktop background")
        self.add(wall_grp)

        self._build_wallpaper_grid(wall_grp)

        # Dock Configuration
        dock_grp = Adw.PreferencesGroup(title="Dock Configuration")
        self.add(dock_grp)

        autohide_row, _ = create_switch_row(
            "Intelligent Autohide", "Hide dock when windows overlap",
            active=gsettings_get("org.gnome.shell.extensions.dash-to-dock", "intellihide") == "true",
            on_toggled=lambda a: gsettings_set("org.gnome.shell.extensions.dash-to-dock", "intellihide", a)
        )
        dock_grp.add(autohide_row)

    def _on_theme_toggled(self, is_dark):
        val = "prefer-dark" if is_dark else "default"
        gsettings_set("org.gnome.desktop.interface", "color-scheme", val)
        # Update Adwaita manager
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK if is_dark else Adw.ColorScheme.FORCE_LIGHT)

    def _build_wallpaper_grid(self, parent_grp):
        flow = Gtk.FlowBox()
        flow.set_valign(Gtk.Align.START)
        flow.set_max_children_per_line(3)
        flow.set_min_children_per_line(2)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_column_spacing(16)
        flow.set_row_spacing(16)
        flow.set_margin_top(12)
        flow.set_margin_bottom(12)
        flow.set_margin_start(12)
        flow.set_margin_end(12)

        # Candidates for wallpapers
        wallpapers = [
            ("Plains Default", "/usr/share/backgrounds/nebula/plains-default.svg"),
            ("Space", "/usr/share/backgrounds/nebula/space.svg"),
            ("Beta", "/usr/share/backgrounds/nebula/beta.svg"),
            ("Pride", "/usr/share/backgrounds/nebula/pride.svg"),
            ("Plains Soft", "/usr/share/backgrounds/nebula/plains-blurred.jpg"),
        ]

        # Fallbacks for dev / testing workspace
        dev_wp_dir = "/d/nebulaos/src/branding/wallpapers"
        if not os.path.exists(wallpapers[0][1]) and os.path.exists("d:/nebulaos/src/branding/wallpapers/plains-default.svg"):
            wallpapers = [
                ("Plains Default", "d:/nebulaos/src/branding/wallpapers/plains-default.svg"),
                ("Space", "d:/nebulaos/src/branding/wallpapers/space.svg"),
                ("Beta", "d:/nebulaos/src/branding/wallpapers/beta.svg"),
                ("Pride", "d:/nebulaos/src/branding/wallpapers/pride.svg"),
            ]

        curr_uri = gsettings_get("org.gnome.desktop.background", "picture-uri")

        self.wp_cards = []

        for name, path in wallpapers:
            card = Gtk.Button()
            card.add_css_class("flat")
            card.add_css_class("wallpaper-card")

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            pic = Gtk.Picture()
            pic.set_size_request(180, 110)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            if os.path.exists(path):
                pic.set_filename(path)
            else:
                pic.set_paintable(None)

            pic_frame = Gtk.Frame()
            pic_frame.set_child(pic)
            pic_frame.add_css_class("wallpaper-thumb-frame")
            box.append(pic_frame)

            lbl = Gtk.Label(label=name, css_classes=["bold"])
            box.append(lbl)

            card.set_child(box)
            card.connect("clicked", lambda _, p=path, c=card: self._apply_wallpaper(p, c))

            if path in curr_uri:
                card.add_css_class("wallpaper-active")

            self.wp_cards.append((card, path))
            flow.append(card)

        # Custom image picker card
        btn_custom = Gtk.Button()
        btn_custom.add_css_class("flat")
        btn_custom.add_css_class("wallpaper-card")
        cbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cframe = Gtk.Frame(css_classes=["wallpaper-thumb-frame"])
        cframe.set_size_request(180, 110)
        cicon = Gtk.Image.new_from_icon_name("list-add-symbolic")
        cicon.set_pixel_size(36)
        cicon.set_halign(Gtk.Align.CENTER)
        cicon.set_valign(Gtk.Align.CENTER)
        cframe.set_child(cicon)
        cbox.append(cframe)
        clbl = Gtk.Label(label="Custom Image...", css_classes=["dim-label"])
        cbox.append(clbl)
        btn_custom.set_child(cbox)
        btn_custom.connect("clicked", self._pick_custom_wallpaper)
        flow.append(btn_custom)

        parent_grp.add(flow)

    def _apply_wallpaper(self, path, clicked_card):
        uri = f"file://{path}"
        gsettings_set("org.gnome.desktop.background", "picture-uri", uri)
        gsettings_set("org.gnome.desktop.background", "picture-uri-dark", uri)

        for card, _ in self.wp_cards:
            card.remove_css_class("wallpaper-active")
        clicked_card.add_css_class("wallpaper-active")

    def _pick_custom_wallpaper(self, btn):
        dialog = Gtk.FileChooserNative.new(
            "Select Wallpaper Image",
            btn.get_root(),
            Gtk.FileChooserAction.OPEN,
            "Select",
            "Cancel"
        )
        filter_imgs = Gtk.FileFilter()
        filter_imgs.set_name("Images")
        filter_imgs.add_mime_type("image/jpeg")
        filter_imgs.add_mime_type("image/png")
        filter_imgs.add_mime_type("image/svg+xml")
        dialog.add_filter(filter_imgs)

        def _on_response(d, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                gfile = d.get_file()
                if gfile:
                    path = gfile.get_path()
                    uri = f"file://{path}"
                    gsettings_set("org.gnome.desktop.background", "picture-uri", uri)
                    gsettings_set("org.gnome.desktop.background", "picture-uri-dark", uri)
            d.destroy()

        dialog.connect("response", _on_response)
        dialog.show()


class BatteryPanel(SettingsPanel):
    def on_build(self):
        bat_grp = Adw.PreferencesGroup(title="Battery Status")
        self.add(bat_grp)

        cap_val = 100
        status_val = "AC Connected"
        bat_dirs = [os.path.join("/sys/class/power_supply", d) for d in os.listdir("/sys/class/power_supply") if d.startswith("BAT")] if os.path.exists("/sys/class/power_supply") else []
        if bat_dirs:
            b_path = bat_dirs[0]
            try:
                with open(os.path.join(b_path, "capacity")) as f:
                    cap_val = int(f.read().strip())
                with open(os.path.join(b_path, "status")) as f:
                    status_val = f.read().strip()
            except Exception:
                pass

        pbar = Gtk.ProgressBar()
        pbar.set_fraction(cap_val / 100.0)
        pbar.set_size_request(120, -1)
        bat_row = create_action_row(f"{cap_val}%", status_val, "battery-good-symbolic", pbar)
        bat_grp.add(bat_row)

        sw_pct, _ = create_switch_row(
            "Show Battery Percentage", "Display charge numeric level in the panel",
            active=gsettings_get("org.gnome.desktop.interface", "show-battery-percentage") == "true",
            on_toggled=lambda a: gsettings_set("org.gnome.desktop.interface", "show-battery-percentage", a)
        )
        bat_grp.add(sw_pct)

        power_grp = Adw.PreferencesGroup(title="Power Management")
        self.add(power_grp)
        modes = ["Balanced", "Power Saver", "Performance"]
        power_grp.add(create_combo_row("Power Profile", modes, 0, None, "power-profile-balanced-symbolic"))

        idle_timeouts = ["5 minutes", "10 minutes", "15 minutes", "30 minutes", "Never"]
        idle_vals = [300, 600, 900, 1800, 0]
        power_grp.add(create_combo_row("Screen Blank Timeout", idle_timeouts, 1, lambda i, _: gsettings_set("org.gnome.desktop.session", "idle-delay", idle_vals[i])))


class AudioPanel(SettingsPanel):
    def on_build(self):
        # 1. Output Device & Volume
        out_grp = Adw.PreferencesGroup(title="Sound Output", description="Choose output device and set master playback volume")
        self.add(out_grp)

        # Detect sinks
        self.sinks = self._get_sinks()
        sink_names = [s[1] for s in self.sinks] if self.sinks else ["Default Audio Output (Speakers)"]
        combo_out = create_combo_row("Default Output Device", sink_names, 0, self._on_sink_changed, "audio-speakers-symbolic")
        out_grp.add(combo_out)

        self.scale_vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.scale_vol.set_value(75)
        self.scale_vol.set_size_request(180, -1)
        self.scale_vol.connect("value-changed", self._on_volume_changed)
        out_grp.add(create_action_row("Output Volume", "Adjust master speaker/headphone volume", "audio-volume-high-symbolic", self.scale_vol))

        # 2. Input Device & Microphone
        in_grp = Adw.PreferencesGroup(title="Sound Input", description="Choose microphone device and input levels")
        self.add(in_grp)

        self.sources = self._get_sources()
        source_names = [s[1] for s in self.sources] if self.sources else ["Default Microphone"]
        combo_in = create_combo_row("Default Microphone Input", source_names, 0, self._on_source_changed, "audio-input-microphone-symbolic")
        in_grp.add(combo_in)

        mic_mute, _ = create_switch_row(
            "Mute Microphone", "Silence input recording stream",
            active=False,
            on_toggled=lambda a: subprocess.run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if a else "0"], check=False),
            icon_name="microphone-sensitivity-muted-symbolic"
        )
        in_grp.add(mic_mute)

        # 3. System Sounds
        fx_grp = Adw.PreferencesGroup(title="System Sounds")
        self.add(fx_grp)
        fx_row, _ = create_switch_row(
            "Event Sounds", "Play sound notifications on system actions and alerts",
            active=gsettings_get("org.gnome.desktop.sound", "event-sounds") == "true",
            on_toggled=lambda a: gsettings_set("org.gnome.desktop.sound", "event-sounds", a)
        )
        fx_grp.add(fx_row)

    def _get_sinks(self):
        sinks = []
        out = run_cmd(["pactl", "list", "short", "sinks"])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                sink_id = parts[1]
                friendly = sink_id.replace("alsa_output.", "").replace(".analog-stereo", "").replace("_", " ").title()
                sinks.append((sink_id, friendly))
        return sinks

    def _get_sources(self):
        sources = []
        out = run_cmd(["pactl", "list", "short", "sources"])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                src_id = parts[1]
                if ".monitor" not in src_id:
                    friendly = src_id.replace("alsa_input.", "").replace(".analog-stereo", "").replace("_", " ").title()
                    sources.append((src_id, friendly))
        return sources

    def _on_sink_changed(self, idx, _):
        if self.sinks and 0 <= idx < len(self.sinks):
            sink_id = self.sinks[idx][0]
            threading.Thread(target=lambda: subprocess.run(["pactl", "set-default-sink", sink_id]), daemon=True).start()

    def _on_source_changed(self, idx, _):
        if self.sources and 0 <= idx < len(self.sources):
            src_id = self.sources[idx][0]
            threading.Thread(target=lambda: subprocess.run(["pactl", "set-default-source", src_id]), daemon=True).start()

    def _on_volume_changed(self, scale):
        vol = int(scale.get_value())
        threading.Thread(target=lambda: subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{vol}%"]), daemon=True).start()


class DisplayPanel(SettingsPanel):
    def on_build(self):
        bright_grp = Adw.PreferencesGroup(title="Brightness and Night Light")
        self.add(bright_grp)

        self.bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
        self.bright_scale.set_size_request(200, -1)

        # Get initial brightness
        initial_val = self._get_current_brightness()
        self.bright_scale.set_value(initial_val)
        self.bright_scale.connect("value-changed", self._on_brightness_changed)

        bright_grp.add(create_action_row("Brightness", "Screen backlight intensity", "display-brightness-symbolic", self.bright_scale))

        nl_active = gsettings_get("org.gnome.settings-daemon.plugins.color", "night-light-enabled") == "true"
        nl_row, _ = create_switch_row(
            "Night Light", "Warm display colors at sunset to reduce eye fatigue",
            active=nl_active,
            on_toggled=lambda a: gsettings_set("org.gnome.settings-daemon.plugins.color", "night-light-enabled", a),
            icon_name="weather-clear-night-symbolic"
        )
        bright_grp.add(nl_row)

        disp_grp = Adw.PreferencesGroup(title="Display Resolution and Scaling")
        self.add(disp_grp)

        resolutions = ["1920 × 1080 (16:9)", "1600 × 900", "1366 × 768", "2560 × 1440 (2K)", "3840 × 2160 (4K)"]
        disp_grp.add(create_combo_row("Resolution", resolutions, 0, None, "video-display-symbolic"))

        scales = ["100%", "125%", "150%", "200%"]
        disp_grp.add(create_combo_row("UI Scaling Factor", scales, 0, lambda i, _: gsettings_set("org.gnome.desktop.interface", "text-scaling-factor", [1.0, 1.25, 1.5, 2.0][i])))

    def _get_current_brightness(self):
        # Try brightnessctl
        b_out = run_cmd(["brightnessctl", "g"])
        m_out = run_cmd(["brightnessctl", "m"])
        if b_out.isdigit() and m_out.isdigit() and int(m_out) > 0:
            return int((int(b_out) / int(m_out)) * 100)
        # Try gdbus
        dbus_out = run_cmd([
            "gdbus", "call", "--session", "--dest", "org.gnome.SettingsDaemon.Power",
            "--object-path", "/org/gnome/SettingsDaemon/Power",
            "--method", "org.freedesktop.DBus.Properties.Get",
            "org.gnome.SettingsDaemon.Power.Screen", "Brightness"
        ])
        m = re.search(r"<int32\s+(\d+)>", dbus_out)
        if m:
            return int(m.group(1))
        return 80

    def _on_brightness_changed(self, scale):
        val = int(scale.get_value())
        def _apply():
            # 1. brightnessctl
            subprocess.run(["brightnessctl", "set", f"{val}%"], check=False)
            # 2. GNOME DBus
            subprocess.run([
                "gdbus", "call", "--session", "--dest", "org.gnome.SettingsDaemon.Power",
                "--object-path", "/org/gnome/SettingsDaemon/Power",
                "--method", "org.freedesktop.DBus.Properties.Set",
                "org.gnome.SettingsDaemon.Power.Screen", "Brightness", f"<int32 {val}>"
            ], check=False)
        threading.Thread(target=_apply, daemon=True).start()


class SecurityPanel(SettingsPanel):
    def on_build(self):
        # Screen Lock
        lock_grp = Adw.PreferencesGroup(title="Screen Lock and Privacy")
        self.add(lock_grp)

        lock_timeouts = ["Immediately", "1 minute", "2 minutes", "5 minutes", "15 minutes"]
        lock_vals = [0, 60, 120, 300, 900]
        lock_grp.add(create_combo_row("Lock Screen Delay", lock_timeouts, 1, lambda i, _: gsettings_set("org.gnome.desktop.screensaver", "lock-delay", lock_vals[i]), "system-lock-screen-symbolic"))

        # User Accounts Management
        self.user_grp = Adw.PreferencesGroup(title="User Accounts", description="Manage system users, login credentials, and privileges")
        self.add(self.user_grp)

        self._build_user_list()

        # Firewall Protection
        fw_grp = Adw.PreferencesGroup(title="Firewall Protection")
        self.add(fw_grp)
        fw_status = "active" in run_cmd(["ufw", "status"])
        fw_row, _ = create_switch_row(
            "System Firewall (UFW)", "Shield computer from unauthorized external connections",
            active=fw_status,
            on_toggled=lambda a: subprocess.run(["pkexec", "ufw", "enable" if a else "disable"], check=False),
            icon_name="security-high-symbolic"
        )
        fw_grp.add(fw_row)

    def _build_user_list(self):
        users = []
        try:
            for p in pwd.getpwall():
                if p.pw_uid >= 1000 and "nobody" not in p.pw_name:
                    users.append((p.pw_name, p.pw_gecos.split(",")[0] or p.pw_name, p.pw_uid))
        except Exception:
            users = [(os.environ.get("USER", "nebula"), "Administrator", 1000)]

        for uname, gecos, uid in users:
            row = Adw.ActionRow(title=gecos, subtitle=f"Username: {uname} • UID {uid}")
            u_img = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
            u_img.set_pixel_size(24)
            row.add_prefix(u_img)

            btn_pw = Gtk.Button(label="Change Password")
            btn_pw.connect("clicked", lambda _, u=uname: self._change_user_password(u))
            row.add_suffix(btn_pw)
            self.user_grp.add(row)

        btn_add = Gtk.Button(label="Add User", css_classes=["suggested-action"])
        btn_add.connect("clicked", self._add_new_user)
        self.user_grp.add(create_action_row("Add New Account", "Create standard or administrative user profile", suffix_widget=btn_add))

    def _change_user_password(self, username):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading=f"Change Password for {username}",
            body="Enter the new password:"
        )
        entry = Gtk.PasswordEntry(activates_default=True, show_peek_icon=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save Password")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def _resp(d, r):
            if r == "save":
                new_pw = entry.get_text()
                if new_pw:
                    subprocess.run(["pkexec", "chpasswd"], input=f"{username}:{new_pw}\n", text=True, check=False)
        dialog.connect("response", _resp)
        dialog.present()

    def _add_new_user(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Add New User",
            body="Configure account credentials and role:"
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ent_name = Gtk.Entry(placeholder_text="Full Name")
        ent_user = Gtk.Entry(placeholder_text="Username")
        ent_pass = Gtk.PasswordEntry(placeholder_text="Password", show_peek_icon=True)
        sw_admin = Gtk.CheckButton(label="Administrator privileges (sudo)")

        box.append(ent_name)
        box.append(ent_user)
        box.append(ent_pass)
        box.append(sw_admin)
        dialog.set_extra_child(box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create Account")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def _resp(d, r):
            if r == "create":
                u = ent_user.get_text().strip().lower()
                n = ent_name.get_text().strip() or u
                p = ent_pass.get_text()
                if u and p:
                    cmd = ["pkexec", "useradd", "-m", "-c", n, "-s", "/bin/bash", u]
                    subprocess.run(cmd, check=False)
                    subprocess.run(["pkexec", "chpasswd"], input=f"{u}:{p}\n", text=True, check=False)
                    if sw_admin.get_active():
                        subprocess.run(["pkexec", "usermod", "-aG", "sudo", u], check=False)

        dialog.connect("response", _resp)
        dialog.present()


class LocationPanel(SettingsPanel):
    def on_build(self):
        grp = Adw.PreferencesGroup(title="Location Services", description="Allow trusted applications to determine geographical coordinates")
        self.add(grp)

        loc_active = gsettings_get("org.gnome.system.location", "enabled") == "true"
        loc_row, _ = create_switch_row(
            "Location Services", "Enable GPS, Wi-Fi and IP-based geolocation",
            active=loc_active,
            on_toggled=lambda a: gsettings_set("org.gnome.system.location", "enabled", a),
            icon_name="find-location-symbolic"
        )
        grp.add(loc_row)

        app_grp = Adw.PreferencesGroup(title="Application Permissions")
        self.add(app_grp)
        app_grp.add(create_action_row("Weather", "Authorized while in use", "org.gnome.Weather"))
        app_grp.add(create_action_row("Maps", "Authorized while in use", "org.gnome.Maps"))
        app_grp.add(create_action_row("Web Browser", "Prompt each time requested", "firefox-esr"))


class EmergencyPanel(SettingsPanel):
    EMERGENCY_FILE = os.path.expanduser("~/.config/nebula/emergency.json")

    def on_build(self):
        sos_grp = Adw.PreferencesGroup(title="Emergency Contacts", description="People to notify during an emergency alert")
        self.add(sos_grp)

        self._emergency_data = self._load_emergency()

        for i in range(1, 3):
            key = f"contact_{i}"
            contact = self._emergency_data.get(key, {})
            name = contact.get("name", "")
            phone = contact.get("phone", "")
            sub = f"{name} � {phone}" if name else "Not set"
            btn = Gtk.Button(label="Edit", css_classes=["flat"])
            btn.connect("clicked", lambda _, idx=i: self._edit_contact(idx))
            sos_grp.add(create_action_row(f"Emergency Contact {i}", sub, "call-start-symbolic", btn))

        med_grp = Adw.PreferencesGroup(title="Medical Information", description="Accessible from the lock screen in an emergency")
        self.add(med_grp)

        med = self._emergency_data.get("medical", {})
        blood_lbl = Gtk.Label(label=med.get("blood_type", "Not set"), css_classes=["dim-label"])
        med_grp.add(create_action_row("Blood Type", "", "emblem-important-symbolic", blood_lbl))

        allergy_btn = Gtk.Button(label="Edit", css_classes=["flat"])
        allergy_btn.connect("clicked", self._edit_medical)
        med_grp.add(create_action_row("Allergies & Conditions", med.get("allergies", "None listed"), "dialog-warning-symbolic", allergy_btn))

        med_btn = Gtk.Button(label="Edit", css_classes=["flat"])
        med_btn.connect("clicked", self._edit_medical)
        med_grp.add(create_action_row("Current Medications", med.get("medications", "None listed"), "emblem-system-symbolic", med_btn))

    def _load_emergency(self):
        try:
            if os.path.exists(self.EMERGENCY_FILE):
                with open(self.EMERGENCY_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_emergency(self):
        os.makedirs(os.path.dirname(self.EMERGENCY_FILE), exist_ok=True)
        with open(self.EMERGENCY_FILE, "w") as f:
            json.dump(self._emergency_data, f, indent=2)

    def _edit_contact(self, idx):
        key = f"contact_{idx}"
        contact = self._emergency_data.get(key, {})
        win = self.get_root()
        dialog = Adw.MessageDialog(transient_for=win, heading=f"Emergency Contact {idx}")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        name_entry = Gtk.Entry(placeholder_text="Full Name", text=contact.get("name", ""))
        phone_entry = Gtk.Entry(placeholder_text="Phone Number", text=contact.get("phone", ""))
        rel_entry = Gtk.Entry(placeholder_text="Relationship (e.g. Spouse)", text=contact.get("relationship", ""))
        box.append(name_entry)
        box.append(phone_entry)
        box.append(rel_entry)
        dialog.set_extra_child(box)
        def _on_response(d, resp):
            if resp == "save":
                self._emergency_data[key] = {
                    "name": name_entry.get_text(),
                    "phone": phone_entry.get_text(),
                    "relationship": rel_entry.get_text()
                }
                self._save_emergency()
            d.destroy()
        dialog.connect("response", _on_response)
        dialog.present()

    def _edit_medical(self, _):
        med = self._emergency_data.get("medical", {})
        win = self.get_root()
        dialog = Adw.MessageDialog(transient_for=win, heading="Medical Information")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        blood_options = ["Not set", "A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
        blood_store = Gtk.StringList.new(blood_options)
        blood_current = med.get("blood_type", "Not set")
        blood_idx = blood_options.index(blood_current) if blood_current in blood_options else 0
        blood_combo = Gtk.DropDown(model=blood_store, selected=blood_idx)
        box.append(Gtk.Label(label="Blood Type", xalign=0))
        box.append(blood_combo)
        allergy_entry = Gtk.Entry(placeholder_text="Allergies", text=med.get("allergies", ""))
        box.append(Gtk.Label(label="Allergies & Conditions", xalign=0))
        box.append(allergy_entry)
        meds_entry = Gtk.Entry(placeholder_text="Medications", text=med.get("medications", ""))
        box.append(Gtk.Label(label="Current Medications", xalign=0))
        box.append(meds_entry)
        dialog.set_extra_child(box)
        def _on_response(d, resp):
            if resp == "save":
                self._emergency_data["medical"] = {
                    "blood_type": blood_options[blood_combo.get_selected()],
                    "allergies": allergy_entry.get_text(),
                    "medications": meds_entry.get_text()
                }
                self._save_emergency()
            d.destroy()
        dialog.connect("response", _on_response)
        dialog.present()


class WellbeingPanel(SettingsPanel):
    def on_build(self):
        time_grp = Adw.PreferencesGroup(title="Screen Time & Daily Balance")
        self.add(time_grp)

        self.screen_time_row = create_action_row("Today's Screen Time", "Calculating...", "preferences-system-symbolic")
        time_grp.add(self.screen_time_row)

        focus_grp = Adw.PreferencesGroup(title="Focus and Do Not Disturb")
        self.add(focus_grp)
        dnd_active = gsettings_get("org.gnome.desktop.notifications", "show-banners") == "false"
        dnd_row, _ = create_switch_row(
            "Do Not Disturb", "Silence notifications and alerts to remain focused",
            active=dnd_active,
            on_toggled=lambda a: gsettings_set("org.gnome.desktop.notifications", "show-banners", not a)
        )
        focus_grp.add(dnd_row)
        threading.Thread(target=self._calc_screen_time, daemon=True).start()

    def _calc_screen_time(self):
        import datetime
        seconds = 0
        try:
            result = run_cmd(["loginctl", "show-session", "--value", "-p", "Timestamp"])
            if result:
                parts = result.split()
                if len(parts) >= 3:
                    dt = datetime.datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M:%S")
                    seconds = int((datetime.datetime.now() - dt).total_seconds())
        except Exception:
            pass
        if seconds <= 0:
            try:
                with open("/proc/uptime") as f:
                    seconds = min(int(float(f.read().split()[0])), 12 * 3600)
            except Exception:
                seconds = 0
        h = seconds // 3600
        m = (seconds % 3600) // 60
        if h > 0:
            label = f"{h} hour{'s' if h != 1 else ''} {m} min"
        elif m > 0:
            label = f"{m} minute{'s' if m != 1 else ''}"
        else:
            label = "Less than a minute"
        GLib.idle_add(lambda: self.screen_time_row.set_subtitle(label) or False)



class AppsPanel(SettingsPanel):
    def on_build(self):
        grp = Adw.PreferencesGroup(title="Installed Applications", description="Core system software installed on NebulaOS")
        self.add(grp)

        app_names = [
            ("Gallery", "Photo viewer and doodle editor", "nebula-gallery"),
            ("Camera", "Webcam photo and video capture", "nebula-camera"),
            ("Calendar", "Personal schedule and events", "nebula-calendar"),
            ("Clock", "World clock, stopwatch and timer", "nebula-clock"),
        ]

        for name, sub, icon in app_names:
            grp.add(create_action_row(name, sub, icon))


class UpdatePanel(SettingsPanel):
    GITHUB_API_RELEASES = "https://api.github.com/repos/tnuproject/nebulaos/releases"

    def on_build(self):
        # 1. Detect Channel and current version
        self.current_channel = self._detect_channel()
        self.current_version = self._detect_current_version()
        self.latest_release_info = None

        stat_grp = Adw.PreferencesGroup(
            title="NebulaOS System Updates",
            description=f"System update channel: {self.current_channel.upper()} � Current Version: {self.current_version}"
        )
        self.add(stat_grp)

        self.status_lbl = Gtk.Label(label="Checking for updates...", css_classes=["accent"])
        self.channel_badge = Gtk.Label(label=f"Channel: {self.current_channel.capitalize()}", css_classes=["dim-label", "caption"])

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_box.append(self.status_lbl)
        status_box.append(self.channel_badge)

        stat_grp.add(create_action_row("System Update Status", "Synchronized with GitHub Official Repository", "software-update-available-symbolic", status_box))

        self.btn_check = Gtk.Button(label="Check for Updates", css_classes=["suggested-action"])
        self.btn_check.connect("clicked", lambda _: self._check_updates_async())

        self.btn_install = Gtk.Button(label="Install System Update", css_classes=["suggested-action"])
        self.btn_install.set_visible(False)
        self.btn_install.connect("clicked", lambda _: self._install_ota_async())

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_box.append(self.btn_check)
        action_box.append(self.btn_install)

        stat_grp.add(create_action_row("GitHub OTA Releases", "Query https://github.com/tnuproject/nebulaos/", suffix_widget=action_box))

        # Update details card
        self.details_grp = Adw.PreferencesGroup(title="Update Information")
        self.details_grp.set_visible(False)
        self.add(self.details_grp)

        self.version_row = create_action_row("Available Version", "�", "emblem-default-symbolic")
        self.details_grp.add(self.version_row)

        self.pkg_row = create_action_row("Update Package", "�", "package-x-generic-symbolic")
        self.details_grp.add(self.pkg_row)

        self.notes_row = create_action_row("Changelog / Notes", "�", "text-x-generic-symbolic")
        self.details_grp.add(self.notes_row)

        # Automatic checks
        cfg_grp = Adw.PreferencesGroup(title="Automatic Settings")
        self.add(cfg_grp)
        auto_row, _ = create_switch_row("Notify on new releases", "Automatically alert when new OTA updates are published", active=True)
        cfg_grp.add(auto_row)

        # Trigger check automatically on open
        self._check_updates_async()

    def _detect_channel(self):
        # 1. Check /etc/os-release for BUILD_CHANNEL
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("BUILD_CHANNEL="):
                            val = line.split("=", 1)[1].strip().strip('"\'').lower()
                            if val in ["stable", "delta"]:
                                return val
            except Exception:
                pass
        # 2. Check /etc/nebula/channel or release.conf
        for p in ["/etc/nebula/channel", "/usr/share/nebula/channel"]:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        val = f.read().strip().lower()
                        if val in ["stable", "delta"]:
                            return val
                except Exception:
                    pass
        return "stable"

    def _detect_current_version(self):
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("VERSION="):
                            return line.split("=", 1)[1].strip().strip('"\'')
            except Exception:
                pass
        return "26.0 \"Apollo\""

    def _clean_version(self, ver_str):
        # Extract digits like 26.0 or 26.0.4 from 'NebulaOS 26.0 "Apollo"' or 'v26.0.4'
        m = re.search(r'(\d+(\.\d+)+)', ver_str)
        return m.group(1) if m else ver_str.strip()

    def _is_newer_version(self, remote_ver, current_ver):
        r_clean = self._clean_version(remote_ver)
        c_clean = self._clean_version(current_ver)
        try:
            r_parts = [int(x) for x in r_clean.split(".")]
            c_parts = [int(x) for x in c_clean.split(".")]
            # Pad
            while len(r_parts) < len(c_parts): r_parts.append(0)
            while len(c_parts) < len(r_parts): c_parts.append(0)
            return r_parts > c_parts
        except Exception:
            return r_clean != c_clean

    def _check_updates_async(self):
        self.btn_check.set_sensitive(False)
        self.status_lbl.set_text("Checking GitHub releases...")
        self.details_grp.set_visible(False)
        self.btn_install.set_visible(False)

        def _task():
            import urllib.request
            target_release = None
            error_msg = None

            try:
                req = urllib.request.Request(
                    self.GITHUB_API_RELEASES,
                    headers={"User-Agent": "NebulaOS-Updater/26.0", "Accept": "application/vnd.github.v3+json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    releases = json.loads(resp.read().decode())

                for r in releases:
                    if r.get("draft"):
                        continue
                    is_prerelease = r.get("prerelease", False)

                    # Channel filtering:
                    # 'delta' channel -> only pre-releases
                    # 'stable' channel -> only stable (not pre-release)
                    if self.current_channel == "delta":
                        if is_prerelease:
                            target_release = r
                            break
                    else:
                        if not is_prerelease:
                            target_release = r
                            break
            except Exception as e:
                error_msg = str(e)

            def _done():
                self.btn_check.set_sensitive(True)
                if error_msg:
                    self.status_lbl.set_text("Offline or GitHub unreachable")
                    return GLib.SOURCE_REMOVE

                if not target_release:
                    self.status_lbl.set_text(f"No {self.current_channel} releases found")
                    return GLib.SOURCE_REMOVE

                rel_tag = target_release.get("tag_name", "")
                rel_name = target_release.get("name", rel_tag)
                rel_body = target_release.get("body", "No release notes provided.")
                assets = target_release.get("assets", [])

                # Find OTA update asset (.deb or .tar.gz)
                ota_asset = None
                for a in assets:
                    aname = a.get("name", "")
                    if aname.endswith(".deb") or "ota" in aname.lower() or aname.endswith(".tar.gz"):
                        ota_asset = a
                        break

                has_update = self._is_newer_version(rel_tag, self.current_version)

                if has_update:
                    self.latest_release_info = {
                        "release": target_release,
                        "ota_asset": ota_asset,
                        "version": rel_name
                    }
                    self.status_lbl.set_text(f"New update available: {rel_name}")
                    self.version_row.set_subtitle(rel_name)
                    self.pkg_row.set_subtitle(ota_asset.get("name", "OTA Package") if ota_asset else "ISO-only update")
                    self.notes_row.set_subtitle(rel_body.splitlines()[0] if rel_body else "NebulaOS System Update")
                    self.details_grp.set_visible(True)

                    if ota_asset:
                        self.btn_install.set_visible(True)
                        self.btn_install.set_label("Install System Update")
                    else:
                        self.btn_install.set_visible(False)
                else:
                    self.status_lbl.set_text(f"NebulaOS is up to date ({self.current_version})")
                    self.details_grp.set_visible(False)
                    self.btn_install.set_visible(False)

                return GLib.SOURCE_REMOVE

            GLib.idle_add(_done)

        threading.Thread(target=_task, daemon=True).start()

    def _install_ota_async(self):
        if not self.latest_release_info or not self.latest_release_info.get("ota_asset"):
            return

        ota_url = self.latest_release_info["ota_asset"].get("browser_download_url")
        ota_filename = self.latest_release_info["ota_asset"].get("name", "nebula-update.deb")

        self.btn_install.set_sensitive(False)
        self.btn_check.set_sensitive(False)
        self.status_lbl.set_text("Downloading and applying OTA update...")

        def _task():
            import urllib.request
            tmp_dir = "/tmp/nebula_ota_install"
            os.makedirs(tmp_dir, exist_ok=True)
            dest_file = os.path.join(tmp_dir, ota_filename)

            try:
                # Download
                urllib.request.urlretrieve(ota_url, dest_file)

                # Execute installation via pkexec
                if dest_file.endswith(".deb"):
                    cmd = f"pkexec bash -c 'dpkg -i {dest_file} || apt-get install -f -y; rm -f {dest_file}'"
                elif dest_file.endswith(".tar.gz") or dest_file.endswith(".tgz"):
                    cmd = f"pkexec bash -c 'tar -xzf {dest_file} -C / && rm -f {dest_file}'"
                else:
                    cmd = f"pkexec bash -c 'dpkg -i {dest_file}'"

                proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                success = (proc.returncode == 0)
            except Exception:
                success = False

            def _finish():
                self.btn_check.set_sensitive(True)
                if success:
                    self.status_lbl.set_text("System updated successfully! Restart to apply all changes.")
                    self.btn_install.set_visible(False)
                    try:
                        subprocess.Popen(["notify-send", "-a", "NebulaOS Update", "System Updated", "NebulaOS system update applied successfully."])
                    except Exception:
                        pass
                else:
                    self.status_lbl.set_text("Update installation failed or cancelled.")
                    self.btn_install.set_sensitive(True)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_finish)

        threading.Thread(target=_task, daemon=True).start()


class AboutPanel(SettingsPanel):
    def on_build(self):
        banner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        banner_box.set_halign(Gtk.Align.CENTER)
        banner_box.set_margin_top(24)
        banner_box.set_margin_bottom(24)

        logo = Gtk.Image.new_from_icon_name("distributor-logo-symbolic")
        if not logo.get_icon_name():
            logo = Gtk.Image.new_from_icon_name("computer-symbolic")
        logo.set_pixel_size(84)
        banner_box.append(logo)

        os_info = {"NAME": "NebulaOS", "VERSION": "26.0 (Apollo)", "PRETTY_NAME": "NebulaOS 26.0 (Apollo)"}
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            os_info[k] = v.strip('"\'')
            except Exception:
                pass

        arch = os.uname().machine if hasattr(os, "uname") else "x86_64"
        display_name = os_info.get("NAME", "NebulaOS")
        version_str = os_info.get("VERSION", os_info.get("VERSION_ID", "26.0 (Apollo)"))

        os_title = Gtk.Label(label=display_name, css_classes=["title-1"])
        banner_box.append(os_title)

        os_sub = Gtk.Label(label=f"Version {version_str} ({arch})", css_classes=["dim-label"])
        banner_box.append(os_sub)

        top_grp = Adw.PreferencesGroup()
        top_grp.add(banner_box)
        self.add(top_grp)

        # Hardware & Specs
        hw_grp = Adw.PreferencesGroup(title="Hardware and System Specifications")
        self.add(hw_grp)

        cpu_name = "Unknown Processor"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_name = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
        hw_grp.add(create_action_row("Processor", cpu_name, "cpu-symbolic"))

        mem_str = "Unknown"
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        mem_str = f"{kb / (1024 * 1024):.1f} GB"
                        break
        except Exception:
            pass
        hw_grp.add(create_action_row("Memory (RAM)", mem_str, "memory-symbolic"))

        kernel_str = run_cmd(["uname", "-r"])
        hw_grp.add(create_action_row("Linux Kernel", kernel_str, "application-x-executable-symbolic"))


# ── Main Settings Window ─────────────────────────────────────────────────────

class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Settings")
        self.set_default_size(1080, 720)

        self._load_css()

        # Main horizontal split: Sidebar (Left) + Content (Right)
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_content(main_box)

        # ── Left Sidebar Box ──
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(280, -1)
        sidebar_box.set_vexpand(True)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_start_title_buttons(True)
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_header.set_title_widget(Gtk.Label(label="Settings", css_classes=["title-2", "bold"]))
        sidebar_box.append(sidebar_header)

        sidebar_box.append(self._create_sidebar())
        main_box.append(sidebar_box)

        # Separator line
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # ── Right Content Box ──
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.content_header = Adw.HeaderBar()
        self.content_header.set_show_start_title_buttons(False)
        self.content_header.set_show_end_title_buttons(False)
        content_box.append(self.content_header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        content_box.append(self.stack)
        main_box.append(content_box)

        # Register panels
        self.panels = {}
        self._init_panels()

        # Select first row
        self._select_first_row()

    def _load_css(self):
        css = """
        .settings-sidebar {
            background-color: @window_bg_color;
        }
        .sidebar-section-header {
            font-size: 11px;
            font-weight: 700;
            color: alpha(@window_fg_color, 0.45);
            margin-top: 16px;
            margin-bottom: 6px;
            margin-left: 16px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }
        .sidebar-row {
            padding: 10px 16px;
            border-radius: 10px;
            margin: 2px 10px;
            min-height: 44px;
            transition: background-color 120ms ease;
        }
        .sidebar-row:hover {
            background-color: alpha(@window_fg_color, 0.06);
        }
        .sidebar-row:selected {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
            font-weight: 600;
        }
        .wallpaper-card {
            border-radius: 12px;
            padding: 6px;
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .wallpaper-thumb-frame {
            border-radius: 10px;
            border: 2px solid transparent;
            overflow: hidden;
        }
        .wallpaper-active .wallpaper-thumb-frame {
            border: 3px solid @accent_bg_color;
            box-shadow: 0 0 10px alpha(@accent_bg_color, 0.6);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _create_sidebar(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add_css_class("settings-sidebar")
        scrolled.set_vexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_sidebar_selected)
        scrolled.set_child(self.listbox)
        return scrolled

    def _add_section_header(self, title):
        lbl = Gtk.Label(label=title)
        lbl.set_halign(Gtk.Align.START)
        lbl.add_css_class("sidebar-section-header")
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_child(lbl)
        self.listbox.append(row)

    def _add_item(self, tag, title, icon_name):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        box.add_css_class("sidebar-row")

        img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(22)
        box.append(img)

        lbl = Gtk.Label(label=title)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        box.append(lbl)

        row = Gtk.ListBoxRow()
        row.set_child(box)
        row._tag = tag
        row._title = title
        self.listbox.append(row)

    def _init_panels(self):
        items = [
            ("HEADER", "Connectivity"),
            ("network", "Network", "network-wireless-symbolic", NetworkPanel),
            ("bluetooth", "Bluetooth", "bluetooth-symbolic", BluetoothPanel),

            ("HEADER", "Input"),
            ("keyboard", "Keyboard", "input-keyboard-symbolic", KeyboardPanel),
            ("language", "Language & Region", "preferences-desktop-locale-symbolic", LanguagePanel),

            ("HEADER", "Account"),
            ("mynebula", "MyNebula", "phone-symbolic", MyNebulaPanel),

            ("HEADER", "Appearance"),
            ("appearance", "Background & Themes", "preferences-desktop-wallpaper-symbolic", AppearancePanel),

            ("HEADER", "Hardware & Audio"),
            ("battery", "Battery", "battery-good-symbolic", BatteryPanel),
            ("audio", "Audio & Video", "audio-speakers-symbolic", AudioPanel),
            ("display", "Display", "video-display-symbolic", DisplayPanel),

            ("HEADER", "System & Privacy"),
            ("security", "Security", "system-lock-screen-symbolic", SecurityPanel),
            ("location", "Location", "find-location-symbolic", LocationPanel),
            ("emergency", "Emergency & SOS", "emblem-important-symbolic", EmergencyPanel),
            ("wellbeing", "Digital Wellbeing", "preferences-system-symbolic", WellbeingPanel),

            ("HEADER", "Applications"),
            ("apps", "Apps", "application-x-executable-symbolic", AppsPanel),
            ("updates", "Software Updates", "software-update-available-symbolic", UpdatePanel),
            ("about", "About System", "help-about-symbolic", AboutPanel),
        ]

        for item in items:
            if item[0] == "HEADER":
                self._add_section_header(item[1])
            else:
                tag, title, icon, panel_cls = item
                self._add_item(tag, title, icon)
                self.panels[tag] = (panel_cls, None, title)

    def _select_first_row(self):
        child = self.listbox.get_first_child()
        while child:
            if getattr(child, "_tag", None):
                self.listbox.select_row(child)
                break
            child = child.get_next_sibling()

    def _on_sidebar_selected(self, _, row):
        if not row or not hasattr(row, "_tag"):
            return
        tag = row._tag
        panel_cls, instance, title = self.panels[tag]

        if instance is None:
            instance = panel_cls(title)
            instance.build_ui()
            self.stack.add_named(instance, tag)
            self.panels[tag] = (panel_cls, instance, title)

        self.stack.set_visible_child_name(tag)
        self.content_header.set_title_widget(Gtk.Label(label=title))

# ── Application Main Entrypoint ──────────────────────────────────────────────

class NebulaSettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SettingsWindow(self)
        win.present()

def main():
    _wizard_done = os.path.exists(os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")) or os.path.exists("/run/nebula-desktop-unlocked")
    if not _wizard_done:
        sys.exit(0)

    GLib.set_prgname("org.nebulaos.Settings")
    GLib.set_application_name("Settings")
    app = NebulaSettingsApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
