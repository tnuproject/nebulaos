#!/usr/bin/env python3
"""
MyNebula Screen Mirroring Window
Receives and displays live screen stream frames from the paired Android device.
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

STREAM_URL = "http://127.0.0.1:53317/api/mirror/stream"
STATUS_URL = "http://127.0.0.1:53317/api/mirror/status"
STOP_URL   = "http://127.0.0.1:53317/api/mirror/stop"

class ScreenMirrorWindow(Adw.ApplicationWindow):
    def __init__(self, app, phone_name="Android Phone"):
        super().__init__(application=app)
        self.set_title(f"{phone_name} — Screen Mirroring")
        self.set_default_size(440, 840)

        self.running = True
        self.current_pixbuf = None
        self.fps_count = 0
        self.fps_timer = time.time()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        # Header bar
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lbl_title = Gtk.Label(label=phone_name, css_classes=["title-4", "bold"])
        self.lbl_sub = Gtk.Label(label="Connecting to phone screen...", css_classes=["caption", "dim-label"])
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

        # Background container (phone screen bezel style)
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

        # Loading / waiting spinner overlay
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.loading_box.set_halign(Gtk.Align.CENTER)
        self.loading_box.set_valign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)
        self.spinner.start()
        self.spinner_lbl = Gtk.Label(label="Waiting for video stream...", css_classes=["dim-label"])
        self.loading_box.append(self.spinner)
        self.loading_box.append(self.spinner_lbl)
        self.overlay.add_overlay(self.loading_box)

        self.connect("close-request", self._on_close)

        # Start stream reader thread
        threading.Thread(target=self._stream_reader, daemon=True).start()

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

                        # Find JPEG markers: 0xFFD8 to 0xFFD9
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
                    if self.loading_box.get_visible():
                        self.loading_box.set_visible(False)
                        self.spinner.stop()
                    return False
                GLib.idle_add(_update)
        except Exception:
            pass

def main():
    phone_name = "Android Phone"
    if len(sys.argv) > 1:
        phone_name = sys.argv[1]
    else:
        # Check pairing info
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
