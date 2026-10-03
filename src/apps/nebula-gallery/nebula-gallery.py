#!/usr/bin/env python3
"""
NebulaOS Gallery
Modern photo browser, viewer, and doodle editor with PetalDrop sharing and MyNebula sync.
"""

import os
import sys
import glob
import json
import time
import subprocess
import threading
import urllib.request

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("cairo", "1.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf, Pango
import cairo

APP_ID = "org.nebulaos.Gallery"
PICTURES_DIR = os.path.expanduser("~/Pictures")
os.makedirs(PICTURES_DIR, exist_ok=True)

class DoodleCanvas(Gtk.DrawingArea):
    def __init__(self, pixbuf):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.base_pixbuf = pixbuf
        self.strokes = []  # list of list of (x, y, color, size)
        self.current_stroke = []
        self.brush_color = (0.2, 0.5, 0.9, 1.0)
        self.brush_size = 5

        self.set_draw_func(self._draw)

        # Gestures for drawing
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def _draw(self, area, cr, width, height):
        # Draw background image centered
        if self.base_pixbuf:
            pw = self.base_pixbuf.get_width()
            ph = self.base_pixbuf.get_height()
            scale = min(width / pw, height / ph, 1.0)
            target_w = int(pw * scale)
            target_h = int(ph * scale)
            offset_x = (width - target_w) / 2
            offset_y = (height - target_h) / 2

            cr.save()
            cr.translate(offset_x, offset_y)
            cr.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(cr, self.base_pixbuf, 0, 0)
            cr.paint()
            cr.restore()

        # Draw all finished strokes
        for stroke in self.strokes:
            if len(stroke) < 2:
                continue
            r, g, b, a = stroke[0][2]
            cr.set_source_rgba(r, g, b, a)
            cr.set_line_width(stroke[0][3])
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.move_to(stroke[0][0], stroke[0][1])
            for pt in stroke[1:]:
                cr.line_to(pt[0], pt[1])
            cr.stroke()

        # Draw current active stroke
        if len(self.current_stroke) >= 2:
            r, g, b, a = self.brush_color
            cr.set_source_rgba(r, g, b, a)
            cr.set_line_width(self.brush_size)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.move_to(self.current_stroke[0][0], self.current_stroke[0][1])
            for pt in self.current_stroke[1:]:
                cr.line_to(pt[0], pt[1])
            cr.stroke()

    def _on_drag_begin(self, gesture, x, y):
        self.current_stroke = [(x, y, self.brush_color, self.brush_size)]
        self.queue_draw()

    def _on_drag_update(self, gesture, offset_x, offset_y):
        start_x, start_y = gesture.get_start_point()[1:]
        x = start_x + offset_x
        y = start_y + offset_y
        self.current_stroke.append((x, y, self.brush_color, self.brush_size))
        self.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if self.current_stroke:
            self.strokes.append(self.current_stroke)
            self.current_stroke = []
            self.queue_draw()

    def clear(self):
        self.strokes = []
        self.current_stroke = []
        self.queue_draw()

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.queue_draw()

class GalleryWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Gallery")
        self.set_default_size(1000, 700)

        self.photos = []
        self.current_idx = 0

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.root_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.root_box.append(self.header)

        # Navigation stack: "grid", "viewer", "editor"
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.root_box.append(self.stack)

        self._build_grid_view()
        self._build_viewer_view()
        self._build_editor_view()

        self.show_grid()
        self._load_photos()

        # Monitor pictures directory for real-time updates when synced
        try:
            gfile = Gio.File.new_for_path(PICTURES_DIR)
            self.monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.monitor.connect("changed", self._on_pictures_changed)
        except Exception:
            self.monitor = None

        self._check_sync_status()
        GLib.timeout_add_seconds(5, lambda: (self._check_sync_status(), True)[1])

    def _on_pictures_changed(self, monitor, file, other_file, event_type):
        if hasattr(self, "_reload_timeout_id") and self._reload_timeout_id:
            GLib.source_remove(self._reload_timeout_id)
        self._reload_timeout_id = GLib.timeout_add(800, lambda: (setattr(self, "_reload_timeout_id", None), self._load_photos(), False)[2])

    def _build_grid_view(self):
        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Action toolbar inside grid
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_bar.set_margin_start(24)
        action_bar.set_margin_end(24)
        action_bar.set_margin_top(12)
        action_bar.set_margin_bottom(12)

        title_lbl = Gtk.Label(label="Photos")
        title_lbl.add_css_class("title-2")
        action_bar.append(title_lbl)

        action_bar.append(Gtk.Box(hexpand=True))

        self.sync_badge = Gtk.Label(label="", css_classes=["caption", "dim-label"])
        self.sync_badge.set_valign(Gtk.Align.CENTER)
        action_bar.append(self.sync_badge)

        self.btn_sync = Gtk.Button(label="Sync with Phone")
        self.btn_sync.add_css_class("flat")
        self.btn_sync.connect("clicked", self._sync_mynebula)
        action_bar.append(self.btn_sync)

        btn_refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        btn_refresh.connect("clicked", lambda _: self._load_photos())
        action_bar.append(btn_refresh)

        grid_box.append(action_bar)

        # Scrolled flowbox
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(8)
        self.flowbox.set_min_children_per_line(2)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_column_spacing(16)
        self.flowbox.set_row_spacing(16)
        self.flowbox.set_margin_start(24)
        self.flowbox.set_margin_end(24)
        self.flowbox.set_margin_bottom(24)

        scroll.set_child(self.flowbox)
        grid_box.append(scroll)

        self.stack.add_named(grid_box, "grid")

    def _build_viewer_view(self):
        self.viewer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Viewer toolbar
        v_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        v_bar.set_margin_start(16)
        v_bar.set_margin_end(16)
        v_bar.set_margin_top(8)
        v_bar.set_margin_bottom(8)

        btn_back = Gtk.Button(icon_name="go-previous-symbolic")
        btn_back.connect("clicked", lambda _: self.show_grid())
        v_bar.append(btn_back)

        self.viewer_title = Gtk.Label(label="")
        self.viewer_title.add_css_class("heading")
        v_bar.append(self.viewer_title)

        v_bar.append(Gtk.Box(hexpand=True))

        btn_doodle = Gtk.Button(icon_name="document-edit-symbolic")
        btn_doodle.set_tooltip_text("Edit & Doodle")
        btn_doodle.connect("clicked", lambda _: self.show_editor())
        v_bar.append(btn_doodle)

        btn_share = Gtk.Button(icon_name="emblem-shared-symbolic")
        btn_share.set_tooltip_text("Share via PetalDrop")
        btn_share.add_css_class("suggested-action")
        btn_share.connect("clicked", self._share_current_photo)
        v_bar.append(btn_share)

        self.viewer_box.append(v_bar)

        # Picture display with left/right buttons
        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)

        btn_prev = Gtk.Button(icon_name="go-previous-symbolic")
        btn_prev.set_valign(Gtk.Align.CENTER)
        btn_prev.connect("clicked", lambda _: self._navigate(-1))
        center_box.append(btn_prev)

        self.viewer_image = Gtk.Picture()
        self.viewer_image.set_hexpand(True)
        self.viewer_image.set_vexpand(True)
        self.viewer_image.set_content_fit(Gtk.ContentFit.CONTAIN)
        center_box.append(self.viewer_image)

        btn_next = Gtk.Button(icon_name="go-next-symbolic")
        btn_next.set_valign(Gtk.Align.CENTER)
        btn_next.connect("clicked", lambda _: self._navigate(1))
        center_box.append(btn_next)

        self.viewer_box.append(center_box)
        self.stack.add_named(self.viewer_box, "viewer")

    def _build_editor_view(self):
        self.editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Editor toolbar
        e_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        e_bar.set_margin_start(16)
        e_bar.set_margin_end(16)
        e_bar.set_margin_top(8)
        e_bar.set_margin_bottom(8)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda _: self.show_viewer())
        e_bar.append(btn_cancel)

        # Brush color palette
        colors = [
            ("Blue", (0.2, 0.5, 0.9, 1.0)),
            ("Red", (0.9, 0.2, 0.2, 1.0)),
            ("Green", (0.2, 0.8, 0.3, 1.0)),
            ("Yellow", (0.95, 0.8, 0.1, 1.0)),
            ("White", (1.0, 1.0, 1.0, 1.0)),
            ("Black", (0.05, 0.05, 0.05, 1.0))
        ]
        for name, col in colors:
            btn_col = Gtk.Button(label=name)
            btn_col.add_css_class("flat")
            btn_col.connect("clicked", lambda _, c=col: self._set_brush_color(c))
            e_bar.append(btn_col)

        e_bar.append(Gtk.Box(hexpand=True))

        btn_undo = Gtk.Button(icon_name="edit-undo-symbolic")
        btn_undo.connect("clicked", lambda _: self.doodle_canvas.undo() if hasattr(self, "doodle_canvas") else None)
        e_bar.append(btn_undo)

        btn_clear = Gtk.Button(label="Clear")
        btn_clear.connect("clicked", lambda _: self.doodle_canvas.clear() if hasattr(self, "doodle_canvas") else None)
        e_bar.append(btn_clear)

        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", self._save_doodle)
        e_bar.append(btn_save)

        self.editor_box.append(e_bar)

        self.canvas_container = Gtk.Box(hexpand=True, vexpand=True)
        self.editor_box.append(self.canvas_container)

        self.stack.add_named(self.editor_box, "editor")

    def _set_brush_color(self, color):
        if hasattr(self, "doodle_canvas"):
            self.doodle_canvas.brush_color = color

    def show_grid(self):
        self.stack.set_visible_child_name("grid")
        self.header.set_title_widget(Gtk.Label(label="Gallery"))

    def show_viewer(self):
        if not self.photos:
            return
        p = self.photos[self.current_idx]
        self.viewer_image.set_filename(p)
        self.viewer_title.set_text(os.path.basename(p))
        self.stack.set_visible_child_name("viewer")
        self.header.set_title_widget(Gtk.Label(label="Photo Viewer"))

    def show_editor(self):
        if not self.photos:
            return
        p = self.photos[self.current_idx]
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(p)
        except Exception:
            return

        # Replace canvas
        child = self.canvas_container.get_first_child()
        if child:
            self.canvas_container.remove(child)

        self.doodle_canvas = DoodleCanvas(pixbuf)
        self.canvas_container.append(self.doodle_canvas)
        self.stack.set_visible_child_name("editor")
        self.header.set_title_widget(Gtk.Label(label="Doodle Editor"))

    def _save_doodle(self, _):
        if not hasattr(self, "doodle_canvas") or not self.photos:
            return
        orig = self.photos[self.current_idx]
        base, ext = os.path.splitext(orig)
        out_path = f"{base}_doodle_{int(time.time())}.png"

        # Render to surface
        pb = self.doodle_canvas.base_pixbuf
        w, h = pb.get_width(), pb.get_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()

        # Scale strokes back to image coordinates
        scale = min(self.doodle_canvas.get_width() / w, self.doodle_canvas.get_height() / h, 1.0)
        off_x = (self.doodle_canvas.get_width() - w * scale) / 2
        off_y = (self.doodle_canvas.get_height() - h * scale) / 2

        for stroke in self.doodle_canvas.strokes:
            if len(stroke) < 2:
                continue
            r, g, b, a = stroke[0][2]
            cr.set_source_rgba(r, g, b, a)
            cr.set_line_width(stroke[0][3] / scale)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            p0x = (stroke[0][0] - off_x) / scale
            p0y = (stroke[0][1] - off_y) / scale
            cr.move_to(p0x, p0y)
            for pt in stroke[1:]:
                cr.line_to((pt[0] - off_x) / scale, (pt[1] - off_y) / scale)
            cr.stroke()

        surface.write_to_png(out_path)
        self._load_photos()
        self.show_grid()

    def _navigate(self, delta):
        if not self.photos:
            return
        self.current_idx = (self.current_idx + delta) % len(self.photos)
        self.show_viewer()

    def _load_photos(self):
        # Clear flowbox
        child = self.flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child

        self.photos = []
        exts = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.svg"]
        for ext in exts:
            self.photos.extend(glob.glob(os.path.join(PICTURES_DIR, "**", ext), recursive=True))

        self.photos.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

        for idx, path in enumerate(self.photos):
            card = Gtk.Button()
            card.add_css_class("flat")
            card.set_size_request(160, 160)

            pic = Gtk.Picture.new_for_filename(path)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(150, 150)
            card.set_child(pic)

            card.connect("clicked", lambda _, i=idx: self._open_photo(i))
            self.flowbox.append(card)

    def _open_photo(self, idx):
        self.current_idx = idx
        self.show_viewer()

    def open_file(self, file_path):
        if not file_path:
            return
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return
        # If photo is not in self.photos, prepend it
        if abs_path not in self.photos:
            self.photos.insert(0, abs_path)
            self.current_idx = 0
        else:
            self.current_idx = self.photos.index(abs_path)
        self.show_viewer()

    def _share_current_photo(self, _):
        if not self.photos:
            return
        photo_path = self.photos[self.current_idx]

        # Trigger PetalDrop share
        def _send():
            try:
                payload = json.dumps({"file_path": photo_path, "target_ip": "paired"}).encode()
                req = urllib.request.Request("http://127.0.0.1:53317/api/drop/push", data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                # Fallback to petaldrop overlay
                subprocess.Popen(["/usr/bin/petaldrop", "--toggle"])

        threading.Thread(target=_send, daemon=True).start()

        # User feedback
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="PetalDrop Sharing",
            body=f"Sending {os.path.basename(photo_path)} to paired device..."
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _check_sync_status(self):
        def _task():
            data = {}
            try:
                with urllib.request.urlopen("http://127.0.0.1:53317/api/gallery/sync/status", timeout=1.5) as resp:
                    data = json.loads(resp.read().decode())
            except Exception:
                pass

            def _apply():
                enabled = data.get("enabled", False)
                paused = data.get("paused", False)
                status = data.get("status", "idle")
                dev_name = data.get("paired_device_name")

                if enabled:
                    if paused:
                        self.sync_badge.set_text("Sync: Paused")
                    elif status == "syncing":
                        self.sync_badge.set_text("Syncing photos...")
                    else:
                        self.sync_badge.set_text(f"Synced with {dev_name}" if dev_name else "Phone Sync: Ready")
                    self.btn_sync.set_label("Sync Now")
                else:
                    self.sync_badge.set_text("Sync: Disabled")
                    self.btn_sync.set_label("Sync with Phone")
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_apply)
        threading.Thread(target=_task, daemon=True).start()

    def _sync_mynebula(self, btn):
        btn.set_sensitive(False)
        def _task():
            status_data = {}
            try:
                with urllib.request.urlopen("http://127.0.0.1:53317/api/gallery/sync/status", timeout=2) as resp:
                    status_data = json.loads(resp.read().decode())
            except Exception:
                pass

            enabled = status_data.get("enabled", False)
            if not enabled:
                def _show_disabled_dialog():
                    btn.set_sensitive(True)
                    dialog = Adw.MessageDialog(
                        transient_for=self,
                        heading="Gallery Sync is Disabled",
                        body="Photo synchronization with your phone is currently turned off.\n\nYou can enable it at any time in Settings > MyNebula > Gallery Sync."
                    )
                    dialog.add_response("cancel", "Cancel")
                    dialog.add_response("settings", "Open Settings")
                    dialog.set_response_appearance("settings", Adw.ResponseAppearance.SUGGESTED)
                    dialog.connect("response", self._on_open_settings_response)
                    dialog.present()
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(_show_disabled_dialog)
                return

            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:53317/api/gallery/sync/now",
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

            GLib.idle_add(lambda: (btn.set_sensitive(True), self._load_photos(), self._check_sync_status()))

        threading.Thread(target=_task, daemon=True).start()

    def _on_open_settings_response(self, dialog, response):
        if response == "settings":
            try:
                subprocess.Popen(["nebula-settings"])
            except Exception:
                try:
                    subprocess.Popen(["python3", "/usr/share/nebula-settings/nebula-settings.py"])
                except Exception:
                    pass

def main():
    GLib.set_prgname("org.nebulaos.Gallery")
    GLib.set_application_name("Gallery")
    app = Adw.Application(
        application_id=APP_ID,
        flags=Gio.ApplicationFlags.HANDLES_OPEN
    )

    def on_activate(a):
        win = a.get_active_window()
        if not win:
            win = GalleryWindow(a)
        # Check command line args if any image files were passed
        args = sys.argv[1:]
        opened = False
        for arg in args:
            if not arg.startswith("-") and os.path.isfile(arg):
                win.open_file(arg)
                opened = True
                break
        if not opened and win.stack.get_visible_child_name() != "viewer":
            win.show_grid()
        win.present()

    def on_open(a, files, hint):
        win = a.get_active_window()
        if not win:
            win = GalleryWindow(a)
        if files:
            path = files[0].get_path()
            if path:
                win.open_file(path)
        win.present()

    app.connect("activate", on_activate)
    app.connect("open", on_open)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
