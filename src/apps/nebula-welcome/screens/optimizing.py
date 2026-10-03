"""
Nebula Welcome — Optimizing Screen
Shown after the user finishes the last step and clicks the final button.
Displays a black screen with a centered spinning loading indicator
and 'Optimizing Applications…' at the bottom of the screen, then transitions
to the GNOME desktop with a smooth fade in.
"""

import os
import subprocess
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib

COMPLETION_FLAG = os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")

class OptimizingScreen(Gtk.Box):
    def __init__(self, on_complete):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_complete = on_complete
        self._build()

    def _build(self):
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_css_class("optimizing-screen")

        # Center spinning loading indicator
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(52, 52)
        self._spinner.add_css_class("optimizing-spinner")
        center_box.append(self._spinner)
        self.append(center_box)

        # Bottom label: "Optimizing Applications…"
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bottom_box.set_halign(Gtk.Align.CENTER)
        bottom_box.set_valign(Gtk.Align.END)
        bottom_box.set_margin_bottom(64)

        lbl = Gtk.Label(label="Optimizing Applications…")
        lbl.add_css_class("optimizing-label")
        bottom_box.append(lbl)
        self.append(bottom_box)

    def on_shown(self):
        # Start spinner animation
        self._spinner.start()

        # Run any background tasks (desktop db update etc.)
        def _background_tasks():
            try:
                apps_dir = os.path.expanduser("~/.local/share/applications")
                if os.path.exists(apps_dir):
                    subprocess.run(["update-desktop-database", apps_dir], check=False)
            except Exception:
                pass

        threading.Thread(target=_background_tasks, daemon=True).start()

        # Show optimizing screen for 2.5 seconds then finish
        GLib.timeout_add(2500, self._finish_transition)

    def _finish_transition(self):
        # Write completion flag FIRST (synchronously) so the shell extension
        # poll sees it as soon as nebula-welcome-active is removed
        try:
            os.makedirs(os.path.dirname(COMPLETION_FLAG), exist_ok=True)
            with open(COMPLETION_FLAG, "w") as f:
                f.write("1\n")
        except Exception:
            pass

        # Remove welcome-active kiosk flag — extension polls this to show dock/panel
        try:
            os.remove("/run/nebula-welcome-active")
        except Exception:
            pass

        # Signal desktop unlocked
        try:
            with open("/run/nebula-desktop-unlocked", "w") as f:
                f.write("1\n")
        except Exception:
            pass

        if callable(self._on_complete):
            self._on_complete()
        return GLib.SOURCE_REMOVE
