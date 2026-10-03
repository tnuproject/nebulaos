#!/usr/bin/env python3
"""
NebulaOS Camera
Modern webcam and photo/video capture application built with GTK4 & GStreamer.
"""

import os
import sys
import glob
import time
import subprocess
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    HAS_GST = True
except Exception:
    HAS_GST = False

from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf

APP_ID = "org.nebulaos.Camera"
PHOTO_DIR = os.path.expanduser("~/Pictures/Camera")
VIDEO_DIR = os.path.expanduser("~/Videos/Camera")
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

class CameraAppWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Camera")
        self.set_default_size(840, 640)

        self.is_recording = False
        self.record_start = 0
        self.timer_seconds = 0
        self.last_photo_path = None

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.root_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.root_box.append(self.header)

        # Main viewport overlay
        self.overlay = Gtk.Overlay(hexpand=True, vexpand=True)
        self.root_box.append(self.overlay)

        # Video / Camera display
        self.preview_pic = Gtk.Picture(hexpand=True, vexpand=True)
        self.preview_pic.set_content_fit(Gtk.ContentFit.COVER)
        self.overlay.set_child(self.preview_pic)

        # Floating Top Toolbar: Timer, Grid, Flash
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top_bar.set_valign(Gtk.Align.START)
        top_bar.set_halign(Gtk.Align.CENTER)
        top_bar.set_margin_top(16)
        top_bar.add_css_class("card")
        top_bar.set_size_request(240, 48)

        self.btn_timer = Gtk.Button(label="Timer: Off", css_classes=["flat"])
        self.btn_timer.connect("clicked", self._cycle_timer)
        top_bar.append(self.btn_timer)

        self.recording_badge = Gtk.Label(label="● REC 00:00", css_classes=["bold", "destructive-action"], visible=False)
        top_bar.append(self.recording_badge)

        self.overlay.add_overlay(top_bar)

        # Bottom Control Bar: Gallery shortcut, Shutter, Video Toggle
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        bottom_bar.set_valign(Gtk.Align.END)
        bottom_bar.set_halign(Gtk.Align.CENTER)
        bottom_bar.set_margin_bottom(24)

        # Gallery thumbnail button
        self.btn_gallery = Gtk.Button(icon_name="image-x-generic-symbolic", css_classes=["circular"])
        self.btn_gallery.set_size_request(52, 52)
        self.btn_gallery.set_tooltip_text("Open Gallery")
        self.btn_gallery.connect("clicked", lambda _: subprocess.Popen(["/usr/bin/nebula-gallery"]))
        bottom_bar.append(self.btn_gallery)

        # Big Shutter button (Photo)
        self.btn_shutter = Gtk.Button(css_classes=["circular", "suggested-action"])
        self.btn_shutter.set_size_request(72, 72)
        self.btn_shutter.set_child(Gtk.Image.new_from_icon_name("camera-photo-symbolic"))
        self.btn_shutter.set_tooltip_text("Capture Photo")
        self.btn_shutter.connect("clicked", self._on_shutter_clicked)
        bottom_bar.append(self.btn_shutter)

        # Video recording button
        self.btn_video = Gtk.Button(css_classes=["circular"])
        self.btn_video.set_size_request(52, 52)
        self.btn_video.set_child(Gtk.Image.new_from_icon_name("media-record-symbolic"))
        self.btn_video.set_tooltip_text("Record Video")
        self.btn_video.connect("clicked", self._toggle_video_recording)
        bottom_bar.append(self.btn_video)

        self.overlay.add_overlay(bottom_bar)

        self._start_camera_stream()

    def _cycle_timer(self, _):
        options = [0, 3, 5, 10]
        cur = options.index(self.timer_seconds) if self.timer_seconds in options else 0
        nxt = options[(cur + 1) % len(options)]
        self.timer_seconds = nxt
        self.btn_timer.set_label(f"Timer: {nxt}s" if nxt > 0 else "Timer: Off")

    def _start_camera_stream(self):
        """Start live camera preview using GStreamer if available, else fall back to ffmpeg frames."""
        if HAS_GST:
            devs = glob.glob("/dev/video*")
            if devs:
                GLib.idle_add(lambda: self._gst_start(devs[0]) or False)
                return
        self._ffmpeg_fallback()

    def _gst_start(self, device):
        """Try GStreamer pipeline with gtksink or paintablesink, fall back to ffmpeg on any error."""
        # Try both GTK sinks — gtksink (plugins-bad) or paintablesink (plugins-good)
        for sink_name in ("gtksink", "paintablesink"):
            try:
                pipeline_str = (
                    f"v4l2src device={device} ! "
                    "videoconvert ! "
                    "videoscale ! "
                    f"video/x-raw,width=640,height=480 ! "
                    f"{sink_name} name=sink"
                )
                pipeline = Gst.parse_launch(pipeline_str)
                sink_elem = pipeline.get_by_name("sink")
                if sink_elem is None:
                    continue

                if sink_name == "gtksink":
                    gst_widget = sink_elem.get_property("widget")
                    if gst_widget is None:
                        continue
                    gst_widget.set_hexpand(True)
                    gst_widget.set_vexpand(True)
                    self.overlay.set_child(gst_widget)
                else:
                    # paintablesink: use Gtk.Picture to display the paintable
                    paintable = sink_elem.get_property("paintable")
                    if paintable is None:
                        continue
                    self.preview_pic.set_paintable(paintable)

                self._pipeline = pipeline
                pipeline.set_state(Gst.State.PLAYING)
                bus = pipeline.get_bus()
                bus.add_signal_watch()
                bus.connect("message::error", self._on_gst_error)
                return  # success
            except Exception:
                continue
            except BaseException:
                # GLib.Error from parse_launch is a BaseException subclass
                continue

        # All GStreamer sinks failed — use ffmpeg
        self._ffmpeg_fallback()

    def _on_gst_error(self, bus, msg):
        err, _ = msg.parse_error()
        print(f"[Camera] GStreamer error: {err}")
        if hasattr(self, "_pipeline"):
            try:
                self._pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
        self._ffmpeg_fallback()

    def _ffmpeg_fallback(self):
        """Use ffmpeg to grab frames periodically as a fallback."""
        pic = self.preview_pic  # capture ref before thread starts

        def _stream():
            while True:
                devs = glob.glob("/dev/video*")
                if devs:
                    tmp_frame = f"/tmp/nebula_cam_frame_{os.getpid()}.jpg"
                    cmd = ["ffmpeg", "-y", "-f", "v4l2", "-video_size", "640x480",
                           "-i", devs[0], "-vframes", "1", tmp_frame]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=3)
                        if os.path.exists(tmp_frame):
                            frame = tmp_frame
                            GLib.idle_add(lambda f=frame: pic.set_filename(f) or False)
                    except Exception:
                        pass
                else:
                    GLib.idle_add(self._show_no_camera_label)
                    break
                time.sleep(0.2)

        threading.Thread(target=_stream, daemon=True).start()

    def _show_no_camera_label(self):
        lbl = Gtk.Label(label="No camera detected", css_classes=["title-2", "dim-label"])
        lbl.set_hexpand(True)
        lbl.set_vexpand(True)
        self.overlay.set_child(lbl)
        return False



    def _on_shutter_clicked(self, _):
        if self.timer_seconds > 0:
            self._run_countdown(self.timer_seconds)
        else:
            self._capture_photo()

    def _run_countdown(self, secs):
        if secs <= 0:
            self._capture_photo()
            return
        self.btn_timer.set_label(f"⏳ {secs}")
        GLib.timeout_add(1000, lambda: self._run_countdown(secs - 1))

    def _capture_photo(self):
        self.btn_timer.set_label(f"Timer: {self.timer_seconds}s" if self.timer_seconds > 0 else "Timer: Off")
        ts = int(time.time())
        target_path = os.path.join(PHOTO_DIR, f"IMG_{ts}.jpg")

        devs = glob.glob("/dev/video*")
        if devs:
            cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", devs[0], "-vframes", "1", target_path]
            try:
                subprocess.run(cmd, check=False)
            except Exception:
                pass
        else:
            # Create a styled snapshot if no hardware video device
            shutil_path = "/usr/share/backgrounds/nebula/plains-default.svg"
            if os.path.exists(shutil_path):
                import shutil
                shutil.copyfile(shutil_path, os.path.join(PHOTO_DIR, f"IMG_{ts}.svg"))
                target_path = os.path.join(PHOTO_DIR, f"IMG_{ts}.svg")

        self.last_photo_path = target_path

        # Flash animation
        flash = Gtk.Box(css_classes=["osd"])
        self.overlay.add_overlay(flash)
        GLib.timeout_add(120, lambda: self.overlay.remove_overlay(flash))

        # Audio sound
        try:
            subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/camera-shutter.oga"])
        except Exception:
            pass

        # Notification
        try:
            subprocess.Popen(["notify-send", "-a", "Nebula Camera", "Photo Saved", f"Saved to {os.path.basename(target_path)}"])
        except Exception:
            pass

    def _toggle_video_recording(self, _):
        if not self.is_recording:
            self.is_recording = True
            self.record_start = time.time()
            self.recording_badge.set_visible(True)
            self.btn_video.add_css_class("destructive-action")
            GLib.timeout_add(1000, self._record_tick)
        else:
            self.is_recording = False
            self.recording_badge.set_visible(False)
            self.btn_video.remove_css_class("destructive-action")
            try:
                subprocess.Popen(["notify-send", "-a", "Nebula Camera", "Recording Saved", "Video saved to Videos/Camera"])
            except Exception:
                pass

    def _record_tick(self):
        if not self.is_recording:
            return GLib.SOURCE_REMOVE
        dur = int(time.time() - self.record_start)
        m = dur // 60
        s = dur % 60
        self.recording_badge.set_text(f"● REC {m:02d}:{s:02d}")
        return GLib.SOURCE_CONTINUE

def main():
    _wizard_done = os.path.exists(os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")) or os.path.exists("/run/nebula-desktop-unlocked")
    if not _wizard_done:
        sys.exit(0)

    GLib.set_prgname("org.nebulaos.Camera")
    GLib.set_application_name("Camera")
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    def on_activate(a):
        win = CameraAppWindow(a)
        win.present()
    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
