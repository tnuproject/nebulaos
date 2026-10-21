#!/usr/bin/env python3
"""
MyNebula Screen Mirroring
Uses scrcpy to mirror Android screen over USB or Wi-Fi (ADB) with ultra-low latency,
high frame rate, audio forwarding, and keyboard/mouse control.
"""

import os
import sys
import json
import time
import shutil
import subprocess
import threading
import urllib.request

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

APP_ID = "org.nebulaos.ScreenMirror"
COMPANION_STATUS_URL = "http://127.0.0.1:53317/api/status"

def get_scrcpy_binary():
    which = shutil.which("scrcpy")
    if which:
        return which
    for p in ["/usr/bin/scrcpy", "/usr/local/bin/scrcpy", os.path.expanduser("~/.local/bin/scrcpy")]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None

def check_scrcpy_installed():
    return get_scrcpy_binary() is not None

def check_adb_installed():
    return shutil.which("adb") is not None

def download_scrcpy_user():
    """Downloads scrcpy portable release to ~/.local/bin and ~/.local/share/scrcpy."""
    try:
        url = "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-linux-x86_64-v3.1.tar.gz"
        dest_bin = os.path.expanduser("~/.local/bin")
        dest_share = os.path.expanduser("~/.local/share/scrcpy")
        os.makedirs(dest_bin, exist_ok=True)
        os.makedirs(dest_share, exist_ok=True)
        tmp_tar = "/tmp/scrcpy_dl.tar.gz"
        urllib.request.urlretrieve(url, tmp_tar)
        import tarfile
        with tarfile.open(tmp_tar, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("/scrcpy"):
                    f = tar.extractfile(member)
                    if f:
                        with open(os.path.join(dest_bin, "scrcpy"), "wb") as out:
                            out.write(f.read())
                        os.chmod(os.path.join(dest_bin, "scrcpy"), 0o755)
                elif member.name.endswith("/scrcpy-server"):
                    f = tar.extractfile(member)
                    if f:
                        with open(os.path.join(dest_share, "scrcpy-server"), "wb") as out:
                            out.write(f.read())
                        os.chmod(os.path.join(dest_share, "scrcpy-server"), 0o644)
        if os.path.exists(tmp_tar):
            os.remove(tmp_tar)
        return True
    except Exception:
        return False

def get_adb_devices():
    """Returns list of connected ADB device serials/IPs."""
    try:
        res = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        lines = res.stdout.strip().split("\n")[1:]
        devices = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []

def launch_scrcpy(target=None, phone_name="Android Phone"):
    """Launches scrcpy process."""
    scrcpy_bin = get_scrcpy_binary()
    if not scrcpy_bin:
        return False, "scrcpy binary not found"
    cmd = [scrcpy_bin]
    if target:
        cmd.extend(["-s", target])
    cmd.extend([
        "--window-title", f"{phone_name} — MyNebula Screen Mirror",
        "--stay-awake"
    ])
    env = os.environ.copy()
    for sp in ["/usr/share/scrcpy/scrcpy-server", "/usr/local/share/scrcpy/scrcpy-server", os.path.expanduser("~/.local/share/scrcpy/scrcpy-server")]:
        if os.path.isfile(sp):
            env["SCRCPY_SERVER_PATH"] = sp
            break
    # Portable scrcpy looks for adb next to its own binary unless ADB is set
    adb_bin = shutil.which("adb")
    if adb_bin and "ADB" not in env:
        env["ADB"] = adb_bin
    try:
        proc = subprocess.Popen(cmd, env=env)
        return True, proc
    except Exception as e:
        return False, str(e)

class ScreenMirrorLauncherWindow(Adw.ApplicationWindow):
    def __init__(self, app, phone_name="Android Phone", phone_ip=None):
        super().__init__(application=app)
        self.set_title("Screen Mirroring — MyNebula")
        self.set_default_size(480, 520)
        self.set_resizable(False)

        self.phone_name = phone_name
        self.phone_ip = phone_ip or ""

        # Query companion for paired phone IP if not provided
        if not self.phone_ip:
            self._fetch_companion_ip()

        self._build_ui()

        # Try automatic direct launch if device is already plugged in via USB
        GLib.timeout_add(400, self._auto_connect_if_ready)

    def _fetch_companion_ip(self):
        try:
            with urllib.request.urlopen(COMPANION_STATUS_URL, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("paired_device_name"):
                    self.phone_name = data["paired_device_name"]
                if data.get("is_paired"):
                    # Check paired device details
                    pass
        except Exception:
            pass

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        # Header bar
        header = Adw.HeaderBar()
        root.append(header)

        # Content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(24)
        root.append(content_box)

        # Banner icon & title
        banner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        banner_box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("video-display-symbolic")
        icon.set_pixel_size(56)
        banner_box.append(icon)

        title_lbl = Gtk.Label(label="Phone Screen Mirroring", css_classes=["title-2", "bold"])
        banner_box.append(title_lbl)

        sub_lbl = Gtk.Label(
            label=f"Mirror and control {self.phone_name} in real-time with scrcpy.\nConnect via USB cable or local Wi-Fi network.",
            css_classes=["caption", "dim-label"]
        )
        sub_lbl.set_justify(Gtk.Justification.CENTER)
        sub_lbl.set_wrap(True)
        banner_box.append(sub_lbl)

        content_box.append(banner_box)

        # Preferences Group
        pref_group = Adw.PreferencesGroup()
        content_box.append(pref_group)

        # 1. USB Connection ActionRow
        usb_row = Adw.ActionRow(
            title="USB Cable (Recommended)",
            subtitle="Connect via USB cable with USB Debugging enabled for lowest latency"
        )
        usb_row.add_prefix(Gtk.Image.new_from_icon_name("media-removable-symbolic"))
        btn_usb = Gtk.Button(label="Connect USB", css_classes=["suggested-action"])
        btn_usb.set_valign(Gtk.Align.CENTER)
        btn_usb.connect("clicked", self._on_connect_usb)
        usb_row.add_suffix(btn_usb)
        pref_group.add(usb_row)

        # 2. Wi-Fi (Wireless Debugging) ActionRow
        wifi_row = Adw.ActionRow(
            title="Wi-Fi (Wireless ADB)",
            subtitle="Connect over your local network using wireless debugging (port 5555)"
        )
        wifi_row.add_prefix(Gtk.Image.new_from_icon_name("network-wireless-symbolic"))
        btn_wifi = Gtk.Button(label="Connect Wi-Fi", css_classes=["flat"])
        btn_wifi.set_valign(Gtk.Align.CENTER)
        btn_wifi.connect("clicked", self._on_connect_wifi)
        wifi_row.add_suffix(btn_wifi)
        pref_group.add(wifi_row)

        # IP Entry Row for Wi-Fi
        self.entry_ip = Adw.EntryRow(title="Phone IP Address")
        if self.phone_ip:
            self.entry_ip.set_text(self.phone_ip)
        pref_group.add(self.entry_ip)

        # Status & Spinner
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_box.set_halign(Gtk.Align.CENTER)
        self.status_box.set_margin_top(8)

        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        self.status_box.append(self.spinner)

        self.lbl_status = Gtk.Label(label="", css_classes=["caption"])
        self.status_box.append(self.lbl_status)

        content_box.append(self.status_box)

    def _ensure_scrcpy_ready(self, on_ready_callback):
        if check_scrcpy_installed():
            on_ready_callback()
            return

        self._set_status("Downloading screen mirror engine...", is_busy=True)
        def _dl():
            ok = download_scrcpy_user()
            if ok and check_scrcpy_installed():
                self._set_status("Screen mirror engine ready.", is_busy=False)
                on_ready_callback()
            else:
                self._set_status("Screen mirror engine not found. Connect to internet or install adb.", is_error=True)
        threading.Thread(target=_dl, daemon=True).start()

    def _auto_connect_if_ready(self):
        if not check_scrcpy_installed():
            return False

        devices = get_adb_devices()
        if devices:
            self._set_status(f"Found ADB device: {devices[0]}. Launching scrcpy...", is_busy=True)
            threading.Thread(target=self._launch_target, args=(devices[0],), daemon=True).start()
        return False

    def _set_status(self, text, is_busy=False, is_error=False):
        def _apply():
            self.lbl_status.set_text(text)
            if is_busy:
                self.spinner.set_visible(True)
                self.spinner.start()
            else:
                self.spinner.stop()
                self.spinner.set_visible(False)

            if is_error:
                self.lbl_status.add_css_class("error")
            else:
                self.lbl_status.remove_css_class("error")
            return GLib.SOURCE_REMOVE
        GLib.idle_add(_apply)

    def _on_connect_usb(self, _):
        def _proceed():
            self._set_status("Scanning for USB connected Android device...", is_busy=True)
            def _task():
                time.sleep(0.5)
                devices = get_adb_devices()
                if devices:
                    self._launch_target(devices[0])
                else:
                    # Try adb usb or adb start-server
                    subprocess.run(["adb", "start-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(1)
                    devices = get_adb_devices()
                    if devices:
                        self._launch_target(devices[0])
                    else:
                        self._set_status("No USB device detected. Make sure USB Debugging is ON in Android Settings.", is_error=True)

            threading.Thread(target=_task, daemon=True).start()

        self._ensure_scrcpy_ready(_proceed)

    def _on_connect_wifi(self, _):
        ip = self.entry_ip.get_text().strip()
        if not ip:
            self._set_status("Please enter phone IP address", is_error=True)
            return

        def _proceed():
            target = f"{ip}:5555" if ":" not in ip else ip
            self._set_status(f"Connecting to wireless ADB at {target}...", is_busy=True)

            def _task():
                try:
                    res = subprocess.run(["adb", "connect", target], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    out = res.stdout.strip()
                    if "connected to" in out.lower() and "cannot" not in out.lower():
                        self._launch_target(target)
                    else:
                        self._set_status(f"Could not connect to {target}. Enable Wireless Debugging on port 5555.", is_error=True)
                except Exception as e:
                    self._set_status(f"Wireless ADB error: {e}", is_error=True)

            threading.Thread(target=_task, daemon=True).start()

        self._ensure_scrcpy_ready(_proceed)

    def _launch_target(self, target):
        self._set_status(f"Launching screen mirror for {target}...", is_busy=True)
        success, proc_or_err = launch_scrcpy(target, self.phone_name)
        if success:
            self._set_status("Screen mirroring active! You can minimize this window.")
            # Minimize launcher window while scrcpy runs
            GLib.idle_add(lambda: self.minimize())
        else:
            self._set_status(f"Failed to launch scrcpy: {proc_or_err}", is_error=True)

def main():
    GLib.set_prgname("org.nebulaos.ScreenMirror")
    GLib.set_application_name("Screen Mirroring")
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)

    phone_name = "Android Phone"
    phone_ip = ""

    args = sys.argv[1:]
    if len(args) >= 1:
        phone_name = args[0]
    if len(args) >= 2:
        phone_ip = args[1]

    def on_activate(a):
        win = ScreenMirrorLauncherWindow(a, phone_name, phone_ip)
        win.present()

    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
