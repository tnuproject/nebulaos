"""
Nebula Welcome — Android Device Pairing Screen
Allows pairing with the MyNebula Android app via QR Code or wireless PIN.
"""

import json
import urllib.request
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from backend.qr import QRCode, draw_qr_cairo

COMPANION_API = "http://127.0.0.1:53317/api/status"

class PairScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._poll_timer = None
        self._is_paired = False
        self._token = "NB-000000"
        self._local_ip = "127.0.0.1"
        self._qr_widget = None
        self._pin_label = None
        self._status_label = None
        self._paired_info_box = None
        self._pairing_controls_box = None

        self._build()

    def _build(self):
        self.set_margin_top(40)
        self.set_margin_bottom(40)
        self.set_margin_start(48)
        self.set_margin_end(48)
        self.set_hexpand(True)
        self.set_vexpand(True)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label()
        title.set_markup("<span font='30' weight='bold'>Pair MyNebula for Android</span>")
        header.append(title)

        sub = Gtk.Label(label="Connect your smartphone to use PetalDrop and access your Cloud gallery.")
        sub.add_css_class("dim-label")
        header.append(sub)

        self.append(header)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(720)
        clamp.set_vexpand(True)
        clamp.set_valign(Gtk.Align.CENTER)
        clamp.set_margin_top(20)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        card.add_css_class("feature-card")

        self._pairing_controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        self._pairing_controls_box.set_halign(Gtk.Align.CENTER)

        # Left side: QR Code
        qr_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        qr_frame.add_css_class("qr-container")
        qr_frame.set_size_request(220, 220)

        self._qr_area = Gtk.DrawingArea()
        self._qr_area.set_content_width(200)
        self._qr_area.set_content_height(200)
        self._qr_area.set_draw_func(self._on_draw_qr)
        qr_frame.append(self._qr_area)
        self._pairing_controls_box.append(qr_frame)

        # Right side: Instructions & PIN
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        right_box.set_valign(Gtk.Align.CENTER)

        step1 = Gtk.Label()
        step1.set_markup("<b>1.</b> Open the <b>MyNebula</b> app on your Android phone")
        step1.set_xalign(0.0)
        right_box.append(step1)

        step2 = Gtk.Label()
        step2.set_markup("<b>2.</b> Scan this QR code or enter the PIN:")
        step2.set_xalign(0.0)
        right_box.append(step2)

        self._pin_label = Gtk.Label(label=self._token)
        self._pin_label.add_css_class("pairing-pin")
        self._pin_label.set_halign(Gtk.Align.START)
        right_box.append(self._pin_label)

        self._status_label = Gtk.Label(label="Waiting for device connection...")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_xalign(0.0)
        right_box.append(self._status_label)

        self._pairing_controls_box.append(right_box)
        card.append(self._pairing_controls_box)

        # Success Banner Box (hidden until paired)
        self._paired_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._paired_info_box.set_visible(False)
        self._paired_info_box.set_halign(Gtk.Align.CENTER)

        check_img = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        check_img.set_pixel_size(56)
        self._paired_info_box.append(check_img)

        self._paired_device_label = Gtk.Label()
        self._paired_device_label.set_markup("<span font='20' weight='bold'>Device Paired!</span>")
        self._paired_info_box.append(self._paired_device_label)

        p_desc = Gtk.Label(label="Your smartphone is now connected. You can share files with PetalDrop and sync photos.")
        p_desc.add_css_class("dim-label")
        self._paired_info_box.append(p_desc)

        card.append(self._paired_info_box)

        clamp.set_child(card)
        self.append(clamp)

        # Nav Buttons
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_halign(Gtk.Align.CENTER)
        nav_box.set_margin_top(20)

        back_btn = Gtk.Button(label="Back")
        back_btn.add_css_class("nebula-secondary")
        back_btn.connect("clicked", lambda _: self._on_back_clicked())
        nav_box.append(back_btn)

        self._skip_btn = Gtk.Button(label="Set up later")
        self._skip_btn.add_css_class("nebula-secondary")
        self._skip_btn.connect("clicked", lambda _: self._on_next_clicked())
        nav_box.append(self._skip_btn)

        self._continue_btn = Gtk.Button(label="Continue")
        self._continue_btn.add_css_class("nebula-primary")
        self._continue_btn.connect("clicked", lambda _: self._on_next_clicked())
        nav_box.append(self._continue_btn)

        self.append(nav_box)

    def _on_draw_qr(self, area, cr, width, height):
        url = f"http://{self._local_ip}:53317/?pair={self._token}"
        qr = QRCode(url)
        draw_qr_cairo(cr, width, height, qr)

    def on_shown(self):
        self._fetch_status()
        if not self._poll_timer:
            self._poll_timer = GLib.timeout_add(1500, self._fetch_status)

    def _fetch_status(self):
        try:
            req = urllib.request.Request(COMPANION_API, headers={"User-Agent": "NebulaWelcome"})
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
                    dev_name = data.get("paired_device_name", "Android Phone")
                    self._pairing_controls_box.set_visible(False)
                    self._paired_device_label.set_markup(f"<span font='20' weight='bold'>{dev_name} Connected!</span>")
                    self._paired_info_box.set_visible(True)
                    self._skip_btn.set_visible(False)
                    self._continue_btn.set_label("Continue")
        except Exception:
            pass
        return GLib.SOURCE_CONTINUE

    def _on_back_clicked(self):
        if self._poll_timer:
            GLib.source_remove(self._poll_timer)
            self._poll_timer = None
        self._on_back()

    def _on_next_clicked(self):
        if self._poll_timer:
            GLib.source_remove(self._poll_timer)
            self._poll_timer = None
        self._on_next()
