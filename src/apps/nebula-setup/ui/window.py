"""
Nebula Setup — Base Application Window
Full-screen, non-closeable, non-minimizable GTK4 window.
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk


class SetupWindow(Adw.ApplicationWindow):
    """
    The root window for nebula-setup.
    - Always full-screen
    - Cannot be closed or minimized (close-request intercepted)
    - Owns a Gtk.Stack for screen transitions
    """

    def __init__(self, app: Adw.Application):
        super().__init__(application=app)

        self.set_title("Nebula Setup")
        self.fullscreen()
        self.set_decorated(False)
        self.connect("realize", lambda win: win.fullscreen())

        # Prevent closing via any means
        self.connect("close-request", self._on_close_request)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "ui", "styles.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.add_css_class("nebula-setup")

        # Stack + transition
        self.stack = Gtk.Stack()
        self.stack.set_transition_duration(350)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.set_content(self.stack)

        # Screen registry
        self._screens: dict[str, Gtk.Widget] = {}
        self._nav_stack: list[str] = []

    # ── Navigation ────────────────────────────────────────────────────────

    def add_screen(self, name: str, widget: Gtk.Widget):
        """Register a screen by name."""
        self._screens[name] = widget
        self.stack.add_named(widget, name)

    def show_screen(self, name: str, direction: str = "forward"):
        """Switch to screen *name* with crossfade transition."""
        if direction == "forward":
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        elif direction == "back":
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
        else:
            self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        if name in self._screens:
            self.stack.set_visible_child_name(name)
            # Track history
            if direction == "forward":
                self._nav_stack.append(name)
            elif direction == "back" and len(self._nav_stack) > 1:
                self._nav_stack.pop()

        # Notify the screen it became visible
        screen = self._screens.get(name)
        if screen and hasattr(screen, "on_shown"):
            GLib.idle_add(screen.on_shown)

    def go_back(self):
        """Navigate to the previous screen."""
        if len(self._nav_stack) >= 2:
            self._nav_stack.pop()  # remove current
            prev = self._nav_stack[-1]
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
            self.stack.set_visible_child_name(prev)

    # ── Prevent closing ───────────────────────────────────────────────────

    def _on_close_request(self, *_args) -> bool:
        # Returning True suppresses the close
        return True
