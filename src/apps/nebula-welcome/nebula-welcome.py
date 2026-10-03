#!/usr/bin/env python3
"""
Nebula Welcome — Post-Installation Setup Wizard
Greets user, explains NebulaOS features, configures picture auto-organization,
and pairs with the MyNebula Android app.
"""

import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from ui.window import WelcomeWindow
from screens.hello import HelloScreen
from screens.wifi import WifiScreen
from screens.pair import PairScreen
from screens.keyboard import KeyboardScreen
from screens.theme import ThemeScreen
from screens.pictures import PicturesConfigScreen
from screens.done import DoneScreen
from screens.optimizing import OptimizingScreen

class NebulaWelcomeApp(Adw.Application):
    def __init__(self):
        GLib.set_prgname("org.nebulaos.Welcome")
        GLib.set_application_name("NebulaOS Welcome")
        super().__init__(
            application_id="org.nebulaos.Welcome",
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )
        self.connect("activate", self._on_activate)
        self._window = None

    def _on_activate(self, _app):
        # Set theme preference from settings or default to dark
        try:
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            curr = settings.get_string("color-scheme")
            style_mgr = Adw.StyleManager.get_default()
            if curr == "default":
                style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
            else:
                style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        except Exception:
            style_mgr = Adw.StyleManager.get_default()
            style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        self._window = WelcomeWindow(self)
        self._build_screens()
        self._window.show_screen("hello", direction="none")
        self._window.present()

    def _build_screens(self):
        win = self._window

        hello = HelloScreen(on_start=lambda: win.show_screen("wifi"))
        win.add_screen("hello", hello)

        wifi = WifiScreen(
            on_next=lambda: win.show_screen("pair"),
            on_back=lambda: win.show_screen("hello", direction="back")
        )
        win.add_screen("wifi", wifi)

        pair = PairScreen(
            on_next=lambda: win.show_screen("keyboard"),
            on_back=lambda: win.show_screen("wifi", direction="back")
        )
        win.add_screen("pair", pair)

        keyboard = KeyboardScreen(
            on_next=lambda: win.show_screen("theme"),
            on_back=lambda: win.show_screen("pair", direction="back")
        )
        win.add_screen("keyboard", keyboard)

        theme = ThemeScreen(
            on_next=lambda: win.show_screen("pictures"),
            on_back=lambda: win.show_screen("keyboard", direction="back")
        )
        win.add_screen("theme", theme)

        pictures = PicturesConfigScreen(
            on_next=lambda: win.show_screen("done"),
            on_back=lambda: win.show_screen("theme", direction="back")
        )
        win.add_screen("pictures", pictures)

        done = DoneScreen(on_finish=lambda: win.show_screen("optimizing", direction="none"))
        win.add_screen("done", done)

        optimizing = OptimizingScreen(on_complete=self._on_finish)
        win.add_screen("optimizing", optimizing)

    def _on_finish(self):
        # Mark wizard completed permanently
        try:
            flag_file = os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")
            os.makedirs(os.path.dirname(flag_file), exist_ok=True)
            with open(flag_file, "w") as f:
                f.write("1\n")
        except Exception:
            pass

        # Wizard completed: safely unhook close prevention and quit
        if self._window:
            self._window.disconnect_by_func(self._window._on_close_request)
            self._window.close()
        self.quit()

def main():
    app = NebulaWelcomeApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
