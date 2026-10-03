"""
Nebula Setup — Done Screen
Shown after successful installation. Prompts to restart.
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
import subprocess
from backend.i18n import t, register_listener


class DoneScreen(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._build()

    def _build(self):
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_vexpand(True)
        center.set_hexpand(True)
        self.append(center)

        checkmark = Gtk.Label(label="✓")
        checkmark.set_css_classes(["hello-word"])
        checkmark.set_opacity(0.9)
        center.append(checkmark)

        self._title = Gtk.Label(label=t("done_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.CENTER)
        center.append(self._title)

        self._sub = Gtk.Label(label=t("done_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.CENTER)
        self._sub.set_justify(Gtk.Justification.CENTER)
        self._sub.set_wrap(True)
        center.append(self._sub)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(16)
        center.append(btn_box)

        self._restart_btn = Gtk.Button(label=t("restart_now"))
        self._restart_btn.add_css_class("nebula-primary")
        self._restart_btn.connect("clicked", self._on_restart)
        btn_box.append(self._restart_btn)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("done_title"))
        self._sub.set_label(t("done_sub"))
        self._restart_btn.set_label(t("restart_now"))

    def _on_restart(self, _btn):
        try:
            subprocess.run(["systemctl", "reboot"], check=False)
        except Exception:
            pass

    def _on_continue(self, _btn):
        try:
            with open("/run/nebula-desktop-unlocked", "w") as f:
                f.write("1")
        except Exception:
            pass
        # Close nebula-setup (in live mode the window is the app — quit it)
        app = self.get_root()
        if hasattr(app, "get_application") and callable(app.get_application):
            app.get_application().quit()


class ErrorScreen(Gtk.Box):
    """Shown when installation fails with an error message."""

    def __init__(self, on_retry=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_retry = on_retry
        self._build()

    def _build(self):
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_vexpand(True)
        self.append(center)

        icon = Gtk.Label(label="✕")
        icon.add_css_class("hello-word")
        icon.set_opacity(0.8)
        center.append(icon)

        self._title = Gtk.Label(label=t("install_failed_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.CENTER)
        center.append(self._title)

        self._error_lbl = Gtk.Label(label="An unexpected error occurred.")
        self._error_lbl.add_css_class("setup-subtitle")
        self._error_lbl.set_halign(Gtk.Align.CENTER)
        self._error_lbl.set_wrap(True)
        self._error_lbl.set_max_width_chars(60)
        center.append(self._error_lbl)

        if self._on_retry:
            self._retry_btn = Gtk.Button(label=t("try_again"))
            self._retry_btn.add_css_class("nebula-primary")
            self._retry_btn.connect("clicked", lambda _: self._on_retry())
            center.append(self._retry_btn)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("install_failed_title"))
        if hasattr(self, "_retry_btn"):
            self._retry_btn.set_label(t("try_again"))

    def set_error(self, message: str):
        self._error_lbl.set_label(message)
