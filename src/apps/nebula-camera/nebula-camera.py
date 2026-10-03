#!/usr/bin/env python3
"""
NebulaOS Camera
Fast, modern webcam and photo/video capture application built with GTK4 & GStreamer.
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

        self.pipeline = None
        self.is_recording = False
        self.record_start = 0
        self.record_proc = None
        self.timer_seconds = 0
        self.last_photo_path = None
        self.current_device = None
        self.last_texture = None

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.root_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.root_box.append(self.header)

        # Rescan / Switch camera button in header
        self.btn_rescan = Gtk.Button(icon_name="view-refresh-symbolic")
        self.btn_rescan.set_tooltip_text("Rescan for Cameras")
        self.btn_rescan.connect("clicked", lambda _: self._rescan_cameras())
        self.header.pack_end(self.btn_rescan)

        # Main viewport overlay
        self.overlay = Gtk.Overlay(hexpand=True, vexpand=True)
        self.root_box.append(self.overlay)

        # Viewport stack: live stream vs standby placeholder
        self.view_stack = Gtk.Stack(hexpand=True, vexpand=True)
        self.view_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.overlay.set_child(self.view_stack)

        # 1. Live stream picture
        self.preview_pic = Gtk.Picture(hexpand=True, vexpand=True)
        self.preview_pic.set_content_fit(Gtk.ContentFit.COVER)
        self.view_stack.add_named(self.preview_pic, "stream")

        # 2. Standby / No camera box
        self.standby_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.standby_box.set_valign(Gtk.Align.CENTER)
        self.standby_box.set_halign(Gtk.Align.CENTER)

        icon_standby = Gtk.Image.new_from_icon_name("camera-web-symbolic")
        icon_standby.set_pixel_size(80)
        icon_standby.add_css_class("dim-label")
        self.standby_box.append(icon_standby)

        title_standby = Gtk.Label(label="No Camera Detected", css_classes=["title-2", "bold"])
        self.standby_box.append(title_standby)

        subtitle_standby = Gtk.Label(
            label="Connect a webcam or USB camera to begin streaming.",
            css_classes=["dim-label"]
        )
        self.standby_box.append(subtitle_standby)

        btn_retry = Gtk.Button(label="Scan for Devices", css_classes=["suggested-action", "pill"])
        btn_retry.set_halign(Gtk.Align.CENTER)
        btn_retry.connect("clicked", lambda _: self._rescan_cameras())
        self.standby_box.append(btn_retry)

        self.view_stack.add_named(self.standby_box, "standby")
        self.view_stack.set_visible_child_name("standby")

        # Floating Top Toolbar: Timer, Recording badge
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
        self.btn_gallery.connect("clicked", lambda _: self._open_gallery())
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

        # Cleanup on window destroy
        self.connect("destroy", self._on_destroy)

        # Start camera detection
        GLib.idle_add(self._start_camera_stream)

    def _open_gallery(self):
        try:
            subprocess.Popen(["/usr/bin/nebula-gallery"])
        except Exception:
            try:
                subprocess.Popen(["xdg-open", PHOTO_DIR])
            except Exception:
                pass

    def _cycle_timer(self, _):
        options = [0, 3, 5, 10]
        cur = options.index(self.timer_seconds) if self.timer_seconds in options else 0
        nxt = options[(cur + 1) % len(options)]
        self.timer_seconds = nxt
        self.btn_timer.set_label(f"Timer: {nxt}s" if nxt > 0 else "Timer: Off")

    def _rescan_cameras(self):
        self._stop_pipeline()
        self._start_camera_stream()

    def _stop_pipeline(self):
        if self.pipeline:
            try:
                self.pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            self.pipeline = None
        self.current_device = None

    def _on_destroy(self, _):
        self._stop_pipeline()
        if self.record_proc:
            try:
                self.record_proc.terminate()
            except Exception:
                pass

    def _start_camera_stream(self):
        devs = sorted(glob.glob("/dev/video*"))
        if not devs:
            self.view_stack.set_visible_child_name("standby")
            return False

        if not HAS_GST:
            self._start_ffmpeg_stream(devs[0])
            return False

        # Try GTK4 paintable sink first if available, else native appsink
        has_gtk4_sink = Gst.ElementFactory.find("gtk4paintablesink") is not None

        for dev in devs:
            if has_gtk4_sink:
                if self._try_gtk4paintablesink(dev):
                    return False
            if self._try_appsink(dev):
                return False

        # If GStreamer pipelines failed, fallback to ffmpeg grabber
        self._start_ffmpeg_stream(devs[0])
        return False

    def _try_gtk4paintablesink(self, device):
        try:
            pipeline_str = (
                f"v4l2src device={device} ! "
                "videoconvert ! "
                "videoscale ! "
                "video/x-raw,width=1280,height=720 ! "
                "gtk4paintablesink name=sink"
            )
            pipe = Gst.parse_launch(pipeline_str)
            sink = pipe.get_by_name("sink")
            if not sink:
                return False
            paintable = sink.get_property("paintable")
            if not paintable:
                return False

            pipe.set_state(Gst.State.PLAYING)
            bus = pipe.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", self._on_gst_error)

            self.pipeline = pipe
            self.current_device = device
            self.preview_pic.set_paintable(paintable)
            self.view_stack.set_visible_child_name("stream")
            return True
        except Exception:
            return False

    def _try_appsink(self, device):
        try:
            pipeline_str = (
                f"v4l2src device={device} ! "
                "videoconvert ! "
                "videoscale ! "
                "video/x-raw,format=RGB,width=640,height=480 ! "
                "appsink name=sink emit-signals=true max-buffers=1 drop=true"
            )
            pipe = Gst.parse_launch(pipeline_str)
            sink = pipe.get_by_name("sink")
            if not sink:
                return False

            sink.connect("new-sample", self._on_appsink_sample)
            pipe.set_state(Gst.State.PLAYING)
            bus = pipe.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", self._on_gst_error)

            self.pipeline = pipe
            self.current_device = device
            self.view_stack.set_visible_child_name("stream")
            return True
        except Exception:
            return False

    def _on_appsink_sample(self, sink):
        try:
            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK
            buf = sample.get_buffer()
            caps = sample.get_caps()
            struct = caps.get_structure(0)
            w = struct.get_value("width")
            h = struct.get_value("height")
            res, map_info = buf.map(Gst.MapFlags.READ)
            if res:
                data_bytes = bytes(map_info.data)
                buf.unmap(map_info)
                gbytes = GLib.Bytes.new(data_bytes)
                texture = Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.R8G8B8, gbytes, w * 3)
                self.last_texture = texture
                GLib.idle_add(lambda: self.preview_pic.set_paintable(texture) or False)
            return Gst.FlowReturn.OK
        except Exception:
            return Gst.FlowReturn.OK

    def _on_gst_error(self, bus, msg):
        self._stop_pipeline()
        devs = sorted(glob.glob("/dev/video*"))
        if devs:
            self._start_ffmpeg_stream(devs[0])
        else:
            self.view_stack.set_visible_child_name("standby")

    def _start_ffmpeg_stream(self, device):
        """Periodic frame capture fallback via ffmpeg."""
        self.current_device = device
        self.view_stack.set_visible_child_name("stream")

        def _worker():
            tmp_frame = f"/tmp/nebula_cam_{os.getpid()}.jpg"
            while self.current_device == device:
                if not os.path.exists(device):
                    GLib.idle_add(lambda: self.view_stack.set_visible_child_name("standby") or False)
                    break
                cmd = ["ffmpeg", "-y", "-f", "v4l2", "-video_size", "640x480",
                       "-i", device, "-vframes", "1", tmp_frame]
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    if os.path.exists(tmp_frame):
                        GLib.idle_add(lambda f=tmp_frame: self.preview_pic.set_filename(f) or False)
                except Exception:
                    pass
                time.sleep(0.15)

        threading.Thread(target=_worker, daemon=True).start()

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
        GLib.timeout_add(1000, lambda: self._run_countdown(secs - 1) or False)

    def _capture_photo(self):
        self.btn_timer.set_label(f"Timer: {self.timer_seconds}s" if self.timer_seconds > 0 else "Timer: Off")
        ts = int(time.time())
        target_path = os.path.join(PHOTO_DIR, f"IMG_{ts}.png")

        # 1. If we have a native GTK texture, save it directly
        if self.last_texture:
            try:
                self.last_texture.save_to_png(target_path)
                self._photo_saved_feedback(target_path)
                return
            except Exception:
                pass

        # 2. If video device exists, capture via ffmpeg
        devs = sorted(glob.glob("/dev/video*"))
        if devs:
            jpg_target = os.path.join(PHOTO_DIR, f"IMG_{ts}.jpg")
            cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", devs[0], "-vframes", "1", jpg_target]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                if os.path.exists(jpg_target):
                    self._photo_saved_feedback(jpg_target)
                    return
            except Exception:
                pass

        # 3. Fallback styled snapshot
        bg_candidate = "/usr/share/backgrounds/nebula/plains-default.svg"
        if os.path.exists(bg_candidate):
            import shutil
            svg_target = os.path.join(PHOTO_DIR, f"IMG_{ts}.svg")
            shutil.copyfile(bg_candidate, svg_target)
            self._photo_saved_feedback(svg_target)

    def _photo_saved_feedback(self, target_path):
        self.last_photo_path = target_path

        # Flash animation
        flash = Gtk.Box(css_classes=["osd"])
        self.overlay.add_overlay(flash)
        GLib.timeout_add(120, lambda: self.overlay.remove_overlay(flash) or False)

        # Audio sound
        try:
            subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/camera-shutter.oga"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # Notification
        try:
            subprocess.Popen(["notify-send", "-a", "Nebula Camera", "Photo Saved",
                              f"Saved to {os.path.basename(target_path)}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _toggle_video_recording(self, _):
        if not self.is_recording:
            devs = sorted(glob.glob("/dev/video*"))
            if not devs:
                try:
                    subprocess.Popen(["notify-send", "-a", "Nebula Camera", "Recording Unavailable", "No camera device detected."])
                except Exception:
                    pass
                return

            self.is_recording = True
            self.record_start = time.time()
            self.recording_badge.set_visible(True)
            self.btn_video.add_css_class("destructive-action")

            ts = int(time.time())
            vid_target = os.path.join(VIDEO_DIR, f"VID_{ts}.mp4")
            cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", devs[0], "-c:v", "libx264", "-preset", "ultrafast", vid_target]
            try:
                self.record_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                self.record_proc = None

            GLib.timeout_add(1000, self._record_tick)
        else:
            self.is_recording = False
            self.recording_badge.set_visible(False)
            self.btn_video.remove_css_class("destructive-action")
            if self.record_proc:
                try:
                    self.record_proc.terminate()
                    self.record_proc.wait(timeout=2)
                except Exception:
                    pass
                self.record_proc = None

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
