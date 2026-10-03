"""
Nebula Setup — Main Entry Point
GTK4 + libadwaita full-screen installer application.
"""

import sys
import os
import subprocess

# Ensure our root is always first in sys.path so absolute imports resolve correctly
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from ui.window import SetupWindow
from screens.hello import HelloScreen
from screens.choice import ChoiceScreen
from screens.terms import TermsScreen
from screens.language import LanguageScreen
from screens.timezone import TimezoneScreen
from screens.user import UserScreen
from screens.partition import PartitionScreen
from screens.installing import InstallingScreen
from screens.done import DoneScreen, ErrorScreen


class NebulaSetupApp(Adw.Application):

    def __init__(self):
        GLib.set_prgname("org.nebulaos.Setup")
        GLib.set_application_name("Install NebulaOS")
        super().__init__(
            application_id="org.nebulaos.Setup",
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )
        self.connect("activate", self._on_activate)
        self._window: SetupWindow = None

    def _on_activate(self, _app):
        try:
            with open("/run/nebula-installer-active", "w") as f:
                f.write("1")
        except Exception:
            pass

        # Set dark theme via Adw.StyleManager (official libadwaita API)
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        self._window = SetupWindow(self)
        self._build_screens()
        self._window.show_screen("hello", direction="none")
        self._window.present()

    # ── Screen building ───────────────────────────────────────────────────

    def _build_screens(self):
        win = self._window

        # Hello — goes directly to Terms (no "Try NebulaOS" option)
        hello = HelloScreen(on_start=lambda: win.show_screen("terms"))
        win.add_screen("hello", hello)

        # Terms of Service & License
        terms = TermsScreen(
            on_next=lambda: win.show_screen("language"),
            on_back=lambda: win.show_screen("hello", direction="back")
        )
        win.add_screen("terms", terms)

        # Language
        language = LanguageScreen(
            on_next=lambda: win.show_screen("timezone"),
            on_back=lambda: win.show_screen("terms", direction="back")
        )
        win.add_screen("language", language)

        # Timezone
        timezone = TimezoneScreen(
            on_next=lambda: win.show_screen("user"),
            on_back=lambda: win.show_screen("language", direction="back")
        )
        win.add_screen("timezone", timezone)

        # User — non-skippable (Continue button stays insensitive until all fields valid)
        user = UserScreen(
            on_next=lambda: win.show_screen("partition"),
            on_back=lambda: win.show_screen("timezone", direction="back")
        )
        win.add_screen("user", user)

        # Partition
        partition = PartitionScreen(
            on_next=lambda: win.show_screen("installing"),
            on_back=lambda: win.show_screen("user", direction="back")
        )
        win.add_screen("partition", partition)

        # Installing
        error_screen = ErrorScreen(on_retry=lambda: win.show_screen("partition", direction="back"))
        win.add_screen("error", error_screen)

        installing = InstallingScreen(
            on_done=lambda: win.show_screen("done"),
            on_error=lambda msg: self._show_error(msg)
        )
        win.add_screen("installing", installing)

        # Done
        done = DoneScreen()
        win.add_screen("done", done)

    def _show_error(self, message: str):
        error_screen = self._window._screens.get("error")
        if error_screen:
            error_screen.set_error(message)
        self._window.show_screen("error")


# ──────────────────────────────────────────────────────────────────────────────

def check_root():
    if os.geteuid() != 0:
        print("nebula-setup: must be run as root", file=sys.stderr)
        sys.exit(1)


def main():
    # Dry-run mode for testing without root
    if "--dry-run" in sys.argv:
        print("nebula-setup: dry-run mode — importing screens only")
        import importlib
        for mod in ["screens.hello", "screens.choice", "screens.terms", "screens.language",
                    "screens.timezone", "screens.user", "screens.theme",
                    "screens.partition", "screens.installing",
                    "screens.done", "backend.disk", "backend.system",
                    "backend.installer", "backend.state", "backend.i18n"]:
            importlib.import_module(mod)
        print("All modules imported successfully.")
        return

    # X11 / Wayland display access for root
    if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
        os.environ.setdefault("DISPLAY", ":0")

    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ["GDK_BACKEND"] = "wayland"
    else:
        os.environ["GDK_BACKEND"] = "x11"

    # Allow root to connect to the display
    if os.geteuid() == 0:
        try:
            user_env = {}
            result = subprocess.run(
                ["bash", "-c", "who | grep -v root | head -1 | awk '{print $1}'"],
                capture_output=True, text=True
            )
            real_user = result.stdout.strip() or "nebula"
            subprocess.run(["xhost", f"+si:localuser:root"], capture_output=True)
        except Exception:
            pass

    app = NebulaSetupApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
