#!/usr/bin/env python3
"""
NebulaOS Gallery
High-performance macOS/iOS Photos style photo browser, viewer, and doodle editor
with PetalDrop sharing and MyNebula sync.
"""

import os
import sys
import time
import json
import hashlib
import threading
import subprocess
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("cairo", "1.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf, Pango
import cairo

APP_ID = "org.nebulaos.Gallery"
PICTURES_DIR = os.path.expanduser("~/Pictures")
CACHE_DIR = os.path.expanduser("~/.cache/nebula/gallery_thumbs")
os.makedirs(PICTURES_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

THUMB_SIZE = 220
BATCH_SIZE = 24

# Global thread pool for fast asynchronous thumbnail rendering
THUMB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="thumb-worker")

def get_thumbnail_cache_path(file_path):
    """Generate cache path based on absolute file path and mtime."""
    try:
        mtime = os.path.getmtime(file_path)
    except Exception:
        mtime = 0
    key = f"{os.path.abspath(file_path)}_{mtime}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.png")

def make_square_thumbnail(file_path):
    """Creates a fast center-cropped square thumbnail on disk."""
    cache_path = get_thumbnail_cache_path(file_path)
    if os.path.isfile(cache_path):
        return cache_path

    try:
        # Load scaled keeping aspect ratio so minimum dimension is THUMB_SIZE
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            file_path,
            THUMB_SIZE * 2,
            THUMB_SIZE * 2,
            True
        )
        if not pb:
            return None

        w, h = pb.get_width(), pb.get_height()
        # Center-crop to square
        side = min(w, h)
        src_x = (w - side) // 2
        src_y = (h - side) // 2

        cropped = GdkPixbuf.Pixbuf.new(
            pb.get_colorspace(),
            pb.get_has_alpha(),
            pb.get_bits_per_sample(),
            side,
            side
        )
        pb.copy_area(src_x, src_y, side, side, cropped, 0, 0)

        # Scale down to final thumbnail size
        final_thumb = cropped.scale_simple(THUMB_SIZE, THUMB_SIZE, GdkPixbuf.InterpType.BILINEAR)
        if final_thumb:
            final_thumb.savev(cache_path, "png", [], [])
            return cache_path
    except Exception:
        pass
    return None


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

        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def _draw(self, area, cr, width, height):
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
        self.set_title("Photos")
        self.set_default_size(1060, 720)

        self.photos = []
        self.current_idx = 0
        self._loading_generation = 0
        self._cards = {}

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

        # Keyboard shortcuts (Left/Right to navigate, Esc to return to grid)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Modern macOS/iOS Photos CSS: seamless edge-to-edge square grid with hairline gap
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        .gallery-grid flowboxchild {
            padding: 0px !important;
            margin: 0px !important;
            border-radius: 0px !important;
            background: transparent !important;
        }
        .gallery-square-card {
            padding: 0px !important;
            margin: 0px !important;
            border: none !important;
            border-radius: 0px !important;
            box-shadow: none !important;
            background: #18181b !important;
            transition: transform 120ms ease, opacity 120ms ease;
        }
        .gallery-square-card:hover {
            opacity: 0.88;
        }
        .gallery-square-card:active {
            opacity: 0.75;
        }
        .gallery-placeholder {
            background-color: #242428;
        }
        .viewer-backdrop {
            background-color: #0c0c0e;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.show_grid()

        # Load photos list asynchronously so UI renders instantly
        GLib.idle_add(self._load_photos)

        # Monitor pictures directory for real-time file updates
        try:
            gfile = Gio.File.new_for_path(PICTURES_DIR)
            self.monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.monitor.connect("changed", self._on_pictures_changed)
        except Exception:
            self.monitor = None

        self._check_sync_status()
        GLib.timeout_add_seconds(5, lambda: (self._check_sync_status(), True)[1])

    def _on_key_pressed(self, controller, keyval, keycode, state):
        current_view = self.stack.get_visible_child_name()
        if current_view == "viewer":
            if keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace):
                self.show_grid()
                return True
            elif keyval in (Gdk.KEY_Left, Gdk.KEY_h, Gdk.KEY_Left):
                self._navigate(-1)
                return True
            elif keyval in (Gdk.KEY_Right, Gdk.KEY_l, Gdk.KEY_Right):
                self._navigate(1)
                return True
        elif current_view == "editor":
            if keyval == Gdk.KEY_Escape:
                self.show_viewer()
                return True
        return False

    def _on_pictures_changed(self, monitor, file, other_file, event_type):
        if hasattr(self, "_reload_timeout_id") and self._reload_timeout_id:
            GLib.source_remove(self._reload_timeout_id)
        self._reload_timeout_id = GLib.timeout_add(700, lambda: (setattr(self, "_reload_timeout_id", None), self._load_photos(), False)[2])

    def _build_grid_view(self):
        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Top Action Bar
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_bar.set_margin_start(18)
        action_bar.set_margin_end(18)
        action_bar.set_margin_top(10)
        action_bar.set_margin_bottom(10)

        title_lbl = Gtk.Label(label="Photos", css_classes=["title-2", "bold"])
        action_bar.append(title_lbl)

        self.photos_count_lbl = Gtk.Label(label="", css_classes=["caption", "dim-label"])
        self.photos_count_lbl.set_valign(Gtk.Align.CENTER)
        self.photos_count_lbl.set_margin_start(8)
        action_bar.append(self.photos_count_lbl)

        action_bar.append(Gtk.Box(hexpand=True))

        self.sync_badge = Gtk.Label(label="", css_classes=["caption", "dim-label"])
        self.sync_badge.set_valign(Gtk.Align.CENTER)
        action_bar.append(self.sync_badge)

        self.btn_sync = Gtk.Button(label="Sync with Phone", css_classes=["flat"])
        self.btn_sync.connect("clicked", self._sync_mynebula)
        action_bar.append(self.btn_sync)

        btn_refresh = Gtk.Button(icon_name="view-refresh-symbolic", css_classes=["flat"])
        btn_refresh.set_tooltip_text("Refresh Photos")
        btn_refresh.connect("clicked", lambda _: self._load_photos())
        action_bar.append(btn_refresh)

        grid_box.append(action_bar)

        # Scrolled FlowBox for Infinite Square Grid
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.set_min_children_per_line(3)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_column_spacing(2)
        self.flowbox.set_row_spacing(2)
        self.flowbox.set_margin_start(0)
        self.flowbox.set_margin_end(0)
        self.flowbox.set_margin_top(0)
        self.flowbox.set_margin_bottom(0)
        self.flowbox.add_css_class("gallery-grid")

        self.scroll.set_child(self.flowbox)
        grid_box.append(self.scroll)

        self.stack.add_named(grid_box, "grid")

    def _build_viewer_view(self):
        self.viewer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.viewer_box.add_css_class("viewer-backdrop")

        # Viewer toolbar
        v_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        v_bar.set_margin_start(16)
        v_bar.set_margin_end(16)
        v_bar.set_margin_top(8)
        v_bar.set_margin_bottom(8)

        btn_back = Gtk.Button(icon_name="go-previous-symbolic", css_classes=["flat"])
        btn_back.set_tooltip_text("Back to Grid (Esc)")
        btn_back.connect("clicked", lambda _: self.show_grid())
        v_bar.append(btn_back)

        self.viewer_title = Gtk.Label(label="", css_classes=["heading"])
        v_bar.append(self.viewer_title)

        v_bar.append(Gtk.Box(hexpand=True))

        btn_doodle = Gtk.Button(icon_name="document-edit-symbolic", css_classes=["flat"])
        btn_doodle.set_tooltip_text("Edit & Doodle")
        btn_doodle.connect("clicked", lambda _: self.show_editor())
        v_bar.append(btn_doodle)

        btn_share = Gtk.Button(icon_name="emblem-shared-symbolic", css_classes=["suggested-action"])
        btn_share.set_tooltip_text("Share via PetalDrop")
        btn_share.connect("clicked", self._share_current_photo)
        v_bar.append(btn_share)

        self.viewer_box.append(v_bar)

        # Picture display with left/right buttons
        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)

        btn_prev = Gtk.Button(icon_name="go-previous-symbolic", css_classes=["flat", "circular"])
        btn_prev.set_valign(Gtk.Align.CENTER)
        btn_prev.set_margin_start(12)
        btn_prev.connect("clicked", lambda _: self._navigate(-1))
        center_box.append(btn_prev)

        self.viewer_picture = Gtk.Picture()
        self.viewer_picture.set_hexpand(True)
        self.viewer_picture.set_vexpand(True)
        self.viewer_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        center_box.append(self.viewer_picture)

        btn_next = Gtk.Button(icon_name="go-next-symbolic", css_classes=["flat", "circular"])
        btn_next.set_valign(Gtk.Align.CENTER)
        btn_next.set_margin_end(12)
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

        btn_cancel = Gtk.Button(label="Cancel", css_classes=["flat"])
        btn_cancel.connect("clicked", lambda _: self.show_viewer())
        e_bar.append(btn_cancel)

        colors = [
            ("Blue", (0.2, 0.5, 0.9, 1.0)),
            ("Red", (0.9, 0.2, 0.2, 1.0)),
            ("Green", (0.2, 0.8, 0.3, 1.0)),
            ("Yellow", (0.95, 0.8, 0.1, 1.0)),
            ("White", (1.0, 1.0, 1.0, 1.0)),
            ("Black", (0.05, 0.05, 0.05, 1.0))
        ]
        for name, col in colors:
            btn_col = Gtk.Button(label=name, css_classes=["flat"])
            btn_col.connect("clicked", lambda _, c=col: self._set_brush_color(c))
            e_bar.append(btn_col)

        e_bar.append(Gtk.Box(hexpand=True))

        btn_undo = Gtk.Button(icon_name="edit-undo-symbolic", css_classes=["flat"])
        btn_undo.connect("clicked", lambda _: self.doodle_canvas.undo() if hasattr(self, "doodle_canvas") else None)
        e_bar.append(btn_undo)

        btn_clear = Gtk.Button(label="Clear", css_classes=["flat"])
        btn_clear.connect("clicked", lambda _: self.doodle_canvas.clear() if hasattr(self, "doodle_canvas") else None)
        e_bar.append(btn_clear)

        btn_save = Gtk.Button(label="Save", css_classes=["suggested-action"])
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
        self.header.set_title_widget(Gtk.Label(label="Photos"))

    def show_viewer(self):
        if not self.photos:
            return
        p = self.photos[self.current_idx]
        self.viewer_picture.set_filename(p)
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

        pb = self.doodle_canvas.base_pixbuf
        w, h = pb.get_width(), pb.get_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()

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
        """Asynchronously scan Pictures and populate grid in responsive batches."""
        self._loading_generation += 1
        gen = self._loading_generation

        # Clear flowbox
        child = self.flowbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flowbox.remove(child)
            child = next_child
        self._cards.clear()

        def _scan_worker():
            exts = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".bmp", ".gif", ".tiff"}
            found = []
            try:
                for root, _, files in os.walk(PICTURES_DIR):
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in exts:
                            full_path = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(full_path)
                                found.append((full_path, mtime))
                            except Exception:
                                pass
            except Exception:
                pass

            found.sort(key=lambda x: x[1], reverse=True)
            sorted_paths = [p[0] for p in found]

            def _init_grid():
                if gen != self._loading_generation:
                    return GLib.SOURCE_REMOVE
                self.photos = sorted_paths
                self.photos_count_lbl.set_text(f"{len(sorted_paths)} photos")

                # Populate flowbox with lightweight card buttons immediately
                for idx, path in enumerate(self.photos):
                    card = Gtk.Button()
                    card.add_css_class("flat")
                    card.add_css_class("gallery-square-card")
                    card.set_size_request(160, 160)

                    pic = Gtk.Picture()
                    pic.set_content_fit(Gtk.ContentFit.COVER)
                    pic.set_size_request(160, 160)
                    card.set_child(pic)

                    card.connect("clicked", lambda _, i=idx: self._open_photo(i))
                    self.flowbox.append(card)
                    self._cards[path] = (card, pic)

                # Start asynchronous thumbnail generation & loading
                self._load_thumbnails_async(gen)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_init_grid)

        threading.Thread(target=_scan_worker, daemon=True).start()

    def _load_thumbnails_async(self, gen):
        """Loads thumbnails in background threads and updates Picture widgets."""
        photos_copy = list(self.photos)

        def _process_photo(path):
            if gen != self._loading_generation:
                return
            thumb_path = make_square_thumbnail(path) or path
            def _apply():
                if gen == self._loading_generation and path in self._cards:
                    _, pic = self._cards[path]
                    pic.set_filename(thumb_path)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_apply)

        def _worker_dispatcher():
            for path in photos_copy:
                if gen != self._loading_generation:
                    break
                THUMB_EXECUTOR.submit(_process_photo, path)

        threading.Thread(target=_worker_dispatcher, daemon=True).start()

    def _open_photo(self, idx):
        self.current_idx = idx
        self.show_viewer()

    def open_file(self, file_path):
        if not file_path:
            return
        if file_path.startswith("file://"):
            file_path = urllib.parse.unquote(urllib.parse.urlparse(file_path).path)
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return

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

        def _send():
            try:
                payload = json.dumps({"file_path": photo_path, "target_ip": "paired"}).encode()
                req = urllib.request.Request("http://127.0.0.1:53317/api/drop/push", data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                subprocess.Popen(["/usr/bin/petaldrop", "--toggle"])

        threading.Thread(target=_send, daemon=True).start()

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="PetalDrop Sharing",
            body=f"Sending {os.path.basename(photo_path)} to nearby devices..."
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
                    self.sync_badge.set_text("Sync: Ready")
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
                try:
                    # Automatically enable gallery sync on Companion
                    req = urllib.request.Request("http://127.0.0.1:53317/api/gallery/sync/toggle", data=b"{}", headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass

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


def main():
    GLib.set_prgname("org.nebulaos.Gallery")
    GLib.set_application_name("Photos")
    app = Adw.Application(
        application_id=APP_ID,
        flags=Gio.ApplicationFlags.HANDLES_OPEN
    )

    def on_activate(a):
        win = a.get_active_window()
        if not win:
            win = GalleryWindow(a)
        args = sys.argv[1:]
        opened = False
        for arg in args:
            if not arg.startswith("-"):
                target = arg
                if target.startswith("file://"):
                    target = urllib.parse.unquote(urllib.parse.urlparse(target).path)
                if os.path.isfile(target):
                    win.open_file(target)
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
