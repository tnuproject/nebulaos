"""
Nebula Setup — Installing Screen
Shows real-time progress while the installer runs in the background.
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from backend.installer import run_install, STEPS
from backend.state import get_state
from backend.i18n import t, register_listener


class InstallingScreen(Gtk.Box):
    def __init__(self, on_done, on_error):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_done = on_done
        self._on_error = on_error
        self._total_steps = len(STEPS)
        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_vexpand(True)
        center.set_hexpand(True)
        center.set_margin_start(80)
        center.set_margin_end(80)
        self.append(center)

        # Icon / spinner area
        spinner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        spinner_box.set_halign(Gtk.Align.CENTER)
        center.append(spinner_box)

        self._spinner = Gtk.Spinner()
        self._spinner.add_css_class("nebula-spinner")
        self._spinner.set_size_request(40, 40)
        self._spinner.start()
        spinner_box.append(self._spinner)

        self._title_lbl = Gtk.Label(label=t("installing_title"))
        self._title_lbl.add_css_class("progress-title")
        self._title_lbl.set_halign(Gtk.Align.CENTER)
        center.append(self._title_lbl)

        # Progress bar
        self._progress = Gtk.ProgressBar()
        self._progress.add_css_class("nebula-progress")
        self._progress.set_fraction(0.0)
        self._progress.set_size_request(520, -1)
        center.append(self._progress)

        # Step label
        self._step_lbl = Gtk.Label(label=t("installing_sub"))
        self._step_lbl.add_css_class("progress-step")
        self._step_lbl.set_halign(Gtk.Align.CENTER)
        center.append(self._step_lbl)

        # Estimated time note
        self._note = Gtk.Label(label="This may take 5–20 minutes depending on your hardware.\nPlease do not turn off your computer.")
        self._note.set_justify(Gtk.Justification.CENTER)
        self._note.set_halign(Gtk.Align.CENTER)
        self._note.set_opacity(0.45)
        self._note.set_margin_top(12)
        center.append(self._note)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title_lbl.set_label(t("installing_title"))

    def on_shown(self):
        """Called when the screen becomes active — start the install."""
        self._start_install()

    def _start_install(self):
        run_install(
            progress_cb=self._on_progress,
            done_cb=self._on_install_done,
            error_cb=self._on_install_error,
        )

    def _on_progress(self, step_index: int, message: str):
        """Called from installer thread — must use GLib.idle_add."""
        GLib.idle_add(self._update_ui, step_index, message)

    def _update_ui(self, step_index: int, message: str):
        frac = min((step_index + 0.5) / self._total_steps, 0.99)
        self._progress.set_fraction(frac)
        self._step_lbl.set_label(message)

    def _on_install_done(self):
        GLib.idle_add(self._finish_ui)

    def _finish_ui(self):
        self._progress.set_fraction(1.0)
        self._spinner.stop()
        self._title_lbl.set_label("Installation Complete!")
        self._step_lbl.set_label("Your system is ready.")
        GLib.timeout_add(1200, self._on_done)

    def _on_install_error(self, message: str):
        GLib.idle_add(self._error_ui, message)

    def _error_ui(self, message: str):
        self._spinner.stop()
        self._title_lbl.set_label("Installation Failed")
        self._step_lbl.set_label(f"Error: {message}")
        self._progress.add_css_class("error")
        GLib.timeout_add(2000, lambda: self._on_error(message))
