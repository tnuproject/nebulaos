"""
Nebula Welcome — Base Application Window
Full-screen, non-bypassable GTK4 / Libadwaita window.
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

class WelcomeWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("Welcome to NebulaOS")
        self.fullscreen()
        self.set_decorated(False)
        self.connect("realize", lambda win: win.fullscreen())

        # Suppress any closing attempts
        self.connect("close-request", self._on_close_request)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "styles.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.add_css_class("nebula-welcome")

        # Stack container
        self.stack = Gtk.Stack()
        self.stack.set_transition_duration(350)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.set_content(self.stack)

        self._screens = {}
        self._nav_stack = []

    def add_screen(self, name: str, widget: Gtk.Widget):
        self._screens[name] = widget
        self.stack.add_named(widget, name)

    def show_screen(self, name: str, direction: str = "forward"):
        if direction == "forward":
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        elif direction == "back":
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
        else:
            self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        if name in self._screens:
            self.stack.set_visible_child_name(name)
            if direction == "forward":
                self._nav_stack.append(name)
            elif direction == "back" and len(self._nav_stack) > 1:
                self._nav_stack.pop()

        screen = self._screens.get(name)
        if screen and hasattr(screen, "on_shown"):
            GLib.idle_add(screen.on_shown)

    def go_back(self):
        if len(self._nav_stack) >= 2:
            self._nav_stack.pop()
            prev = self._nav_stack[-1]
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
            self.stack.set_visible_child_name(prev)

    def _on_close_request(self, *_args) -> bool:
        # Prevent user from closing until wizard is finished
        return True
