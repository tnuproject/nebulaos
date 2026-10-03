#!/usr/bin/env python3
"""
MyNebula Screen Mirroring Window
Receives and displays live screen stream frames from the paired Android device,
handling authorization requests, phone notifications, and user permission responses.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GdkPixbuf

REQUEST_URL = "http://127.0.0.1:53317/api/mirror/request"
STREAM_URL  = "http://127.0.0.1:53317/api/mirror/stream"
STATUS_URL  = "http://127.0.0.1:53317/api/mirror/status"
STOP_URL    = "http://127.0.0.1:53317/api/mirror/stop"

class ScreenMirrorWindow(Adw.ApplicationWindow):
    def __init__(self, app, phone_name="Android Phone"):
        super().__init__(application=app)
        self.set_title(f"{phone_name} — Screen Mirroring")
        self.set_default_size(440, 840)

        self.phone_name = phone_name
        self.running = True
        self.fps_count = 0
        self.fps_timer = time.time()
        self.current_state = "requesting"  # requesting, denied, streaming, error

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        # Header bar
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lbl_title = Gtk.Label(label=phone_name, css_classes=["title-4", "bold"])
        self.lbl_sub = Gtk.Label(label="Requesting phone permission...", css_classes=["caption", "dim-label"])
        title_box.append(lbl_title)
        title_box.append(self.lbl_sub)
        header.set_title_widget(title_box)

        btn_stop = Gtk.Button(label="Disconnect", css_classes=["destructive-action", "flat"])
        btn_stop.connect("clicked", self._on_disconnect_clicked)
        header.pack_end(btn_stop)

        root.append(header)

        # Main viewport overlay
        self.overlay = Gtk.Overlay(hexpand=True, vexpand=True)
        root.append(self.overlay)

        # Background container (phone bezel card)
        self.bg_box = Gtk.Box(hexpand=True, vexpand=True)
        self.bg_box.set_halign(Gtk.Align.FILL)
        self.bg_box.set_valign(Gtk.Align.FILL)
        self.bg_box.add_css_class("card")
        self.bg_box.set_margin_start(12)
        self.bg_box.set_margin_end(12)
        self.bg_box.set_margin_top(12)
        self.bg_box.set_margin_bottom(12)

        # Picture widget
        self.picture = Gtk.Picture(hexpand=True, vexpand=True)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.bg_box.append(self.picture)
        self.overlay.set_child(self.bg_box)

        # Overlay status container
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.status_box.set_halign(Gtk.Align.CENTER)
        self.status_box.set_valign(Gtk.Align.CENTER)
        self.status_box.set_margin_start(32)
        self.status_box.set_margin_end(32)

        # Spinner & icon
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)
        self.status_box.append(self.spinner)

        self.status_icon = Gtk.Image.new_from_icon_name("phone-symbolic")
        self.status_icon.set_pixel_size(48)
        self.status_icon.set_visible(False)
        self.status_box.append(self.status_icon)

        self.status_title = Gtk.Label(label="Waiting for Authorization", css_classes=["title-3", "bold"])
        self.status_box.append(self.status_title)

        self.status_desc = Gtk.Label(
            label="A notification has been sent to your phone.\nPlease tap 'Allow' on the device to share your screen.",
            css_classes=["caption", "dim-label"]
        )
        self.status_desc.set_justify(Gtk.Justification.CENTER)
        self.status_desc.set_wrap(True)
        self.status_box.append(self.status_desc)

        # Action buttons box (for denied / error state)
        self.actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.actions_box.set_halign(Gtk.Align.CENTER)
        self.actions_box.set_visible(False)

        self.btn_retry = Gtk.Button(label="Request Again", css_classes=["suggested-action"])
        self.btn_retry.connect("clicked", lambda _: self._send_request())
        self.actions_box.append(self.btn_retry)

        self.btn_cancel = Gtk.Button(label="Close", css_classes=["flat"])
        self.btn_cancel.connect("clicked", lambda _: self.close())
        self.actions_box.append(self.btn_cancel)

        self.status_box.append(self.actions_box)
        self.overlay.add_overlay(self.status_box)

        self.connect("close-request", self._on_close)

        # Initial request and background threads
        self._set_state("requesting")
        self._send_request()
        threading.Thread(target=self._status_poller, daemon=True).start()
        threading.Thread(target=self._stream_reader, daemon=True).start()

    def _set_state(self, state, error_msg=None):
        self.current_state = state
        def _update():
            if state == "requesting":
                self.spinner.set_visible(True)
                self.spinner.start()
                self.status_icon.set_visible(False)
                self.status_title.set_text("Waiting for Authorization")
                self.status_desc.set_text("A prompt appeared on your phone.\nTap 'Allow' on your device to share your screen.")
                self.actions_box.set_visible(False)
                self.lbl_sub.set_text("Waiting for phone permission...")
                self.status_box.set_visible(True)

            elif state == "denied":
                self.spinner.stop()
                self.spinner.set_visible(False)
                self.status_icon.set_from_icon_name("dialog-warning-symbolic")
                self.status_icon.set_visible(True)
                self.status_title.set_text("Permission Denied by Phone")
                self.status_desc.set_text("The screen sharing request was declined on your mobile device.")
                self.actions_box.set_visible(True)
                self.lbl_sub.set_text("Permission declined")
                self.status_box.set_visible(True)

            elif state == "error":
                self.spinner.stop()
                self.spinner.set_visible(False)
                self.status_icon.set_from_icon_name("network-error-symbolic")
                self.status_icon.set_visible(True)
                self.status_title.set_text("Connection Error")
                self.status_desc.set_text(error_msg or "Cannot connect to your phone. Ensure both devices are connected to the same Wi-Fi network.")
                self.actions_box.set_visible(True)
                self.lbl_sub.set_text("Error connecting to phone")
                self.status_box.set_visible(True)

            elif state == "streaming":
                self.spinner.stop()
                self.status_box.set_visible(False)
            return False
        GLib.idle_add(_update)

    def _send_request(self):
        self._set_state("requesting")
        def _req():
            try:
                req = urllib.request.Request(
                    REQUEST_URL,
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    if not data.get("success") and data.get("error"):
                        self._set_state("error", data.get("error"))
            except Exception as e:
                self._set_state("error", str(e))
        threading.Thread(target=_req, daemon=True).start()

    def _status_poller(self):
        while self.running:
            try:
                req = urllib.request.Request(STATUS_URL)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    state = data.get("state", "idle")
                    error = data.get("error")

                    if state == "denied" and self.current_state != "denied":
                        self._set_state("denied")
                    elif state == "error" and self.current_state != "error":
                        self._set_state("error", error)
                    elif state == "streaming" and self.current_state != "streaming":
                        self._set_state("streaming")
            except Exception:
                pass
            time.sleep(1)

    def _on_disconnect_clicked(self, _):
        self.close()

    def _on_close(self, _):
        self.running = False
        def _notify_stop():
            try:
                req = urllib.request.Request(STOP_URL, data=b"{}", headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass
        threading.Thread(target=_notify_stop, daemon=True).start()
        return False

    def _stream_reader(self):
        """Reads MJPEG stream from companion daemon."""
        while self.running:
            try:
                req = urllib.request.Request(STREAM_URL)
                with urllib.request.urlopen(req, timeout=10) as stream:
                    buffer = b""
                    while self.running:
                        chunk = stream.read(16384)
                        if not chunk:
                            break
                        buffer += chunk

                        start = buffer.find(b"\xff\xd8")
                        end = buffer.find(b"\xff\xd9", start + 2) if start != -1 else -1

                        if start != -1 and end != -1:
                            jpg_bytes = buffer[start:end+2]
                            buffer = buffer[end+2:]
                            self._display_frame(jpg_bytes)
            except Exception:
                time.sleep(1)

    def _display_frame(self, frame_bytes):
        self.fps_count += 1
        now = time.time()
        if now - self.fps_timer >= 1.0:
            fps = self.fps_count
            self.fps_count = 0
            self.fps_timer = now
            GLib.idle_add(lambda: self.lbl_sub.set_text(f"Live Screen • {fps} FPS") or False)

        try:
            loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
            loader.write(frame_bytes)
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf:
                paintable = Gdk.Texture.new_for_pixbuf(pixbuf)
                def _update():
                    if not self.running:
                        return False
                    self.picture.set_paintable(paintable)
                    if self.current_state != "streaming":
                        self._set_state("streaming")
                    return False
                GLib.idle_add(_update)
        except Exception:
            pass

def main():
    phone_name = "Android Phone"
    if len(sys.argv) > 1:
        phone_name = sys.argv[1]
    else:
        try:
            with urllib.request.urlopen("http://127.0.0.1:53317/api/status", timeout=1) as resp:
                data = json.loads(resp.read().decode())
                if data.get("paired_device_name"):
                    phone_name = data["paired_device_name"]
        except Exception:
            pass

    GLib.set_prgname("org.nebulaos.ScreenMirror")
    GLib.set_application_name("Screen Mirroring")
    app = Adw.Application(application_id="org.nebulaos.ScreenMirror", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def on_activate(a):
        win = ScreenMirrorWindow(a, phone_name)
        win.present()

    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
