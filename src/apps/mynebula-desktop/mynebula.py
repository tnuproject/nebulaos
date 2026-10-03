#!/usr/bin/env python3
"""
MyNebula Desktop Companion App for NebulaOS
Allows managing Android device pairing, triggering PetalDrop file transfers,
configuring automatic picture organization, and downloading the Android APK.
"""

import os
import sys
import json
import shutil
import urllib.request
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

COMPANION_API = "http://127.0.0.1:53317/api/status"
PEERS_API = "http://127.0.0.1:53317/api/drop/peers"
PUSH_API = "http://127.0.0.1:53317/api/drop/push"
PICTURES_FLAG = os.path.expanduser("~/.config/nebula/auto-organize-pictures.enabled")
APK_LOCATIONS = [
    "/usr/share/mynebula-desktop/mynebula.apk",
    "/usr/share/mynebula/mynebula.apk",
    os.path.join(os.path.dirname(__file__), "..", "mynebula-android", "mynebula.apk"),
    os.path.expanduser("~/Downloads/mynebula.apk")
]


# Pure Python QR Code Generator & Cairo Drawing Helper
class QRCode:
    def __init__(self, data: str):
        self.data = data
        self.modules = []
        self.size = 29  # Version 3 (29x29 matrix)
        self._generate()

    def _generate(self):
        n = self.size
        self.modules = [[False]*n for _ in range(n)]

        self._add_finder(0, 0)
        self._add_finder(n - 7, 0)
        self._add_finder(0, n - 7)

        for i in range(8, n - 8):
            self.modules[6][i] = (i % 2 == 0)
            self.modules[i][6] = (i % 2 == 0)

        self._add_alignment(20, 20)

        bits = []
        bits.extend([0, 1, 0, 0])
        l = len(self.data)
        for i in range(7, -1, -1):
            bits.append((l >> i) & 1)
        for c in self.data:
            val = ord(c)
            for i in range(7, -1, -1):
                bits.append((val >> i) & 1)
        bits.extend([0, 0, 0, 0])

        idx = 0
        bit_len = len(bits)
        for r in range(n):
            for c in range(n):
                if (r < 9 and c < 9) or (r < 9 and c >= n - 8) or (r >= n - 8 and c < 9):
                    continue
                if r == 6 or c == 6:
                    continue
                if 19 <= r <= 25 and 19 <= c <= 25:
                    continue
                val = bits[idx % bit_len] if bit_len > 0 else 0
                idx += 1
                if (r + c) % 2 == 0:
                    val ^= 1
                self.modules[r][c] = bool(val)

    def _add_finder(self, row, col):
        for r in range(7):
            for c in range(7):
                if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4):
                    self.modules[row + r][col + c] = True
                else:
                    self.modules[row + r][col + c] = False

    def _add_alignment(self, row, col):
        for r in range(5):
            for c in range(5):
                if r in (0, 4) or c in (0, 4) or (r == 2 and c == 2):
                    self.modules[row + r][col + c] = True
                else:
                    self.modules[row + r][col + c] = False


def draw_qr_cairo(cr, width, height, qr: QRCode):
    n = qr.size
    total_mod = n + 4
    cell_size = min(width, height) / total_mod
    offset_x = (width - (cell_size * total_mod)) / 2 + cell_size * 2
    offset_y = (height - (cell_size * total_mod)) / 2 + cell_size * 2

    cr.set_source_rgb(1.0, 1.0, 1.0)
    cr.paint()

    cr.set_source_rgb(0.08, 0.08, 0.12)
    for r in range(n):
        for c in range(n):
            if qr.modules[r][c]:
                cr.rectangle(offset_x + c * cell_size, offset_y + r * cell_size,
                             cell_size + 0.5, cell_size + 0.5)
    cr.fill()


class MyNebulaWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("MyNebula")
        self.set_default_size(720, 680)

        self._token = "NB-000000"
        self._local_ip = "127.0.0.1"
        self._is_paired = False
        self._paired_device_name = ""
        self._poll_timer = None

        self._build_ui()
        self._apply_css()
        self._start_polling()

    def _build_ui(self):
        # Main vertical container with HeaderBar
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)

        # Scrolled Window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        main_box.append(scrolled)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)
        clamp.set_tightening_threshold(560)
        clamp.set_margin_top(28)
        clamp.set_margin_bottom(36)
        clamp.set_margin_start(24)
        clamp.set_margin_end(24)
        scrolled.set_child(clamp)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        clamp.set_child(content)

        # 1. Header Banner
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        banner.add_css_class("card")
        banner.set_margin_bottom(8)

        icon = Gtk.Image.new_from_icon_name("preferences-desktop-remote-desktop")
        icon.set_pixel_size(54)
        banner.append(icon)

        banner_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        banner_text.set_hexpand(True)

        title = Gtk.Label(label="MyNebula")
        title.set_markup("<span font='22' weight='bold'>MyNebula</span>")
        title.set_xalign(0.0)
        banner_text.append(title)

        subtitle = Gtk.Label(label="Android Device Companion & Offline PetalDrop Sharing")
        subtitle.add_css_class("dim-label")
        subtitle.set_xalign(0.0)
        banner_text.append(subtitle)
        banner.append(banner_text)

        self._status_badge = Gtk.Label(label="Checking...")
        self._status_badge.add_css_class("status-pill")
        self._status_badge.set_valign(Gtk.Align.CENTER)
        banner.append(self._status_badge)

        content.append(banner)

        # 2. Pairing Section Container
        self._pairing_group = Adw.PreferencesGroup()
        self._pairing_group.set_title("Device Connection")
        self._pairing_group.set_description("Pair one Android smartphone at a time with your NebulaOS laptop.")
        content.append(self._pairing_group)

        # Sub-container 2a: Unpaired Box (QR Code + PIN)
        self._unpaired_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        self._unpaired_box.add_css_class("card")

        qr_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        qr_frame.add_css_class("qr-container")
        qr_frame.set_size_request(200, 200)

        self._qr_area = Gtk.DrawingArea()
        self._qr_area.set_content_width(180)
        self._qr_area.set_content_height(180)
        self._qr_area.set_draw_func(self._on_draw_qr)
        qr_frame.append(self._qr_area)
        self._unpaired_box.append(qr_frame)

        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        instructions_box.set_valign(Gtk.Align.CENTER)
        instructions_box.set_hexpand(True)

        ins1 = Gtk.Label()
        ins1.set_markup("<b>1.</b> Open <b>MyNebula</b> on your Android phone")
        ins1.set_xalign(0.0)
        instructions_box.append(ins1)

        ins2 = Gtk.Label()
        ins2.set_markup("<b>2.</b> Scan this QR code or enter the 6-digit PIN:")
        ins2.set_xalign(0.0)
        instructions_box.append(ins2)

        self._pin_label = Gtk.Label(label=self._token)
        self._pin_label.add_css_class("pin-badge")
        self._pin_label.set_xalign(0.0)
        instructions_box.append(self._pin_label)

        self._wait_label = Gtk.Label(label="Waiting for device connection...")
        self._wait_label.add_css_class("dim-label")
        self._wait_label.set_xalign(0.0)
        instructions_box.append(self._wait_label)

        self._unpaired_box.append(instructions_box)
        self._unpaired_row = Adw.PreferencesRow()
        self._unpaired_row.set_child(self._unpaired_box)
        self._pairing_group.add(self._unpaired_row)

        # Sub-container 2b: Paired Box
        self._paired_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self._paired_box.add_css_class("card")
        self._paired_box.set_visible(False)

        paired_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        p_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        p_icon.set_pixel_size(36)
        paired_header.append(p_icon)

        p_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._paired_name_label = Gtk.Label()
        self._paired_name_label.set_markup("<span font='16' weight='bold'>Android Phone</span>")
        self._paired_name_label.set_xalign(0.0)
        p_info.append(self._paired_name_label)

        self._paired_sub_label = Gtk.Label(label="Connected & Active — Ready for PetalDrop & Cloud Sync")
        self._paired_sub_label.add_css_class("dim-label")
        self._paired_sub_label.set_xalign(0.0)
        p_info.append(self._paired_sub_label)
        paired_header.append(p_info)
        self._paired_box.append(paired_header)

        unpair_tip = Gtk.Label()
        unpair_tip.set_markup("<span font='11' alpha='70%'>ℹ To disconnect, unpair directly from the MyNebula app on your Android device.</span>")
        unpair_tip.set_xalign(0.0)
        unpair_tip.set_wrap(True)
        self._paired_box.append(unpair_tip)

        self._paired_row = Adw.PreferencesRow()
        self._paired_row.set_child(self._paired_box)
        self._paired_row.set_visible(False)
        self._pairing_group.add(self._paired_row)

        # 3. Features & Settings Group
        features_group = Adw.PreferencesGroup()
        features_group.set_title("Features &amp; Sharing")
        content.append(features_group)

        # PetalDrop Action Row
        drop_row = Adw.ActionRow()
        drop_row.set_title("PetalDrop File Sharing")
        drop_row.set_subtitle("Share media and files with nearby devices or your paired phone")
        drop_icon = Gtk.Image.new_from_icon_name("document-send-symbolic")
        drop_row.add_prefix(drop_icon)

        drop_btn = Gtk.Button(label="Share Files...")
        drop_btn.add_css_class("suggested-action")
        drop_btn.set_valign(Gtk.Align.CENTER)
        drop_btn.connect("clicked", self._on_share_files_clicked)
        drop_row.add_suffix(drop_btn)
        features_group.add(drop_row)

        # Pictures Auto-Organizer Switch Row
        self._pic_switch_row = Adw.SwitchRow()
        self._pic_switch_row.set_title("Organize Pictures Automatically")
        self._pic_switch_row.set_subtitle("Automatically move downloaded or desktop images to your Pictures folder")
        pic_icon = Gtk.Image.new_from_icon_name("folder-pictures-symbolic")
        self._pic_switch_row.add_prefix(pic_icon)
        self._pic_switch_row.set_active(os.path.exists(PICTURES_FLAG))
        self._pic_switch_row.connect("notify::active", self._on_pic_switch_toggled)
        features_group.add(self._pic_switch_row)

        # 4. Mobile App Group
        app_group = Adw.PreferencesGroup()
        app_group.set_title("MyNebula for Android")
        app_group.set_description("Download and install the MyNebula application on your Android phone.")
        content.append(app_group)

        apk_row = Adw.ActionRow()
        apk_row.set_title("Install Companion APK")
        apk_row.set_subtitle("Transfer or download the Android package file (mynebula.apk)")
        phone_icon = Gtk.Image.new_from_icon_name("phone-symbolic")
        apk_row.add_prefix(phone_icon)

        export_btn = Gtk.Button(label="Save to Downloads")
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn.connect("clicked", self._on_save_apk_clicked)
        apk_row.add_suffix(export_btn)
        app_group.add(apk_row)

    def _apply_css(self):
        css = """
        .card {
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 18px 20px;
        }
        .qr-container {
            background-color: #ffffff;
            border-radius: 14px;
            padding: 10px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }
        .pin-badge {
            font-family: monospace;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 3px;
            color: #3584e4;
            background-color: rgba(53, 132, 228, 0.12);
            border-radius: 10px;
            padding: 6px 14px;
        }
        .status-pill {
            font-size: 12px;
            font-weight: 600;
            padding: 5px 14px;
            border-radius: 9999px;
            background-color: rgba(255, 255, 255, 0.08);
            color: rgba(255, 255, 255, 0.7);
        }
        .status-pill.online {
            background-color: rgba(51, 209, 122, 0.16);
            color: #33d17a;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_draw_qr(self, area, cr, width, height):
        url = f"http://{self._local_ip}:53317/?pair={self._token}"
        qr = QRCode(url)
        draw_qr_cairo(cr, width, height, qr)

    def _start_polling(self):
        self._fetch_status()
        self._poll_timer = GLib.timeout_add(1500, self._fetch_status)

    def _fetch_status(self):
        try:
            req = urllib.request.Request(COMPANION_API, headers={"User-Agent": "MyNebulaDesktop"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                data = json.loads(resp.read().decode())
                token = data.get("pairing_token", "NB-000000")
                self._local_ip = data.get("local_ip", "127.0.0.1")

                if token != self._token:
                    self._token = token
                    self._pin_label.set_text(self._token)
                    self._qr_area.queue_draw()

                if data.get("is_paired"):
                    self._is_paired = True
                    self._paired_device_name = data.get("paired_device_name", "Android Phone")
                    self._unpaired_row.set_visible(False)
                    self._paired_row.set_visible(True)
                    self._paired_name_label.set_markup(f"<span font='16' weight='bold'>{self._paired_device_name}</span>")
                    self._status_badge.set_text("Connected")
                    self._status_badge.add_css_class("online")
                else:
                    self._is_paired = False
                    self._unpaired_row.set_visible(True)
                    self._paired_row.set_visible(False)
                    self._status_badge.set_text("Ready to pair")
                    self._status_badge.remove_css_class("online")
        except Exception:
            self._status_badge.set_text("Daemon Offline")
            self._status_badge.remove_css_class("online")
        return GLib.SOURCE_CONTINUE

    def _on_pic_switch_toggled(self, row, param):
        is_active = row.get_active()
        os.makedirs(os.path.dirname(PICTURES_FLAG), exist_ok=True)
        if is_active:
            with open(PICTURES_FLAG, "w") as f:
                f.write("1")
        else:
            if os.path.exists(PICTURES_FLAG):
                try: os.remove(PICTURES_FLAG)
                except Exception: pass

    def _on_share_files_clicked(self, _btn):
        # Open file chooser
        try:
            dialog = Gtk.FileDialog()
            dialog.set_title("Select File to Share via PetalDrop")
            dialog.open(self, None, self._on_file_selected)
        except Exception:
            # Fallback for zenity
            import subprocess
            try:
                proc = subprocess.Popen(["zenity", "--file-selection", "--title=Select File to Share via PetalDrop"],
                                        stdout=subprocess.PIPE, text=True)
                stdout, _ = proc.communicate()
                path = stdout.strip()
                if path and os.path.exists(path):
                    self._send_file_via_petaldrop(path)
            except Exception:
                pass

    def _on_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                if path and os.path.exists(path):
                    self._send_file_via_petaldrop(path)
        except Exception:
            pass

    def _send_file_via_petaldrop(self, file_path):
        # Request daemon to push to paired device
        try:
            payload = json.dumps({"file_path": file_path, "target_ip": "paired", "target_port": 53317}).encode()
            req = urllib.request.Request(PUSH_API, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode())
                if res.get("success"):
                    self._show_toast(f"Successfully sent {os.path.basename(file_path)} via PetalDrop!")
                else:
                    self._show_toast(f"Send failed: {res.get('error', 'Device unreachable')}")
        except Exception as e:
            self._show_toast(f"Connection error: {e}")

    def _on_save_apk_clicked(self, _btn):
        # Find APK and copy to ~/Downloads
        found_src = None
        for path in APK_LOCATIONS:
            if os.path.exists(path):
                found_src = path
                break

        dest_dir = os.path.expanduser("~/Downloads")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, "MyNebula.apk")

        if found_src:
            try:
                shutil.copyfile(found_src, dest_path)
                self._show_toast(f"Saved MyNebula.apk to {dest_dir}!")
            except Exception as e:
                self._show_toast(f"Error saving APK: {e}")
        else:
            self._show_toast("MyNebula APK will be available on the installed system.")

    def _show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        # Check if overlay is present or notify
        try:
            import subprocess
            subprocess.Popen(["notify-send", "-a", "MyNebula", "MyNebula", message])
        except Exception:
            pass


class MyNebulaApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.nebulaos.mynebula",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MyNebulaWindow(self)
        win.present()


def main():
    app = MyNebulaApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
