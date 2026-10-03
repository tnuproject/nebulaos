"""
Nebula Setup — Theme Selector Screen
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from backend.state import get_state
from backend.i18n import t, register_listener


class ThemeScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected = "prefer-dark"
        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.add_css_class("setup-header")
        self.append(header)

        self._title = Gtk.Label(label=t("theme_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("theme_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        header.append(self._sub)

        # ── Themes row ────────────────────────────────────────────────────
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
        row.set_halign(Gtk.Align.CENTER)
        row.set_valign(Gtk.Align.CENTER)
        row.set_vexpand(True)
        self.append(row)

        self._dark_btn, self._dark_lbl = self._make_theme_card(
            row, "prefer-dark", t("dark"),
            preview_css="theme-preview-dark",
            wallpaper_dark=True
        )
        self._light_btn, self._light_lbl = self._make_theme_card(
            row, "prefer-light", t("light"),
            preview_css="theme-preview-light",
            wallpaper_dark=False
        )

        # Default selection
        self._select("prefer-dark")

        # ── Footer ────────────────────────────────────────────────────────
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.add_css_class("nav-footer")
        self.append(footer)

        self._back_btn = Gtk.Button(label=t("back"))
        self._back_btn.add_css_class("nebula-back")
        self._back_btn.connect("clicked", lambda _: self._on_back())
        footer.append(self._back_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.append(spacer)

        self._next_btn = Gtk.Button(label=t("continue"))
        self._next_btn.add_css_class("nebula-primary")
        self._next_btn.connect("clicked", self._on_next_clicked)
        footer.append(self._next_btn)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("theme_title"))
        self._sub.set_label(t("theme_sub"))
        self._dark_lbl.set_label(t("dark"))
        self._light_lbl.set_label(t("light"))
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("continue"))

    def _make_theme_card(self, parent, scheme, label_text,
                         preview_css, wallpaper_dark) -> tuple[Gtk.Button, Gtk.Label]:
        btn = Gtk.Button()
        btn.add_css_class("theme-option")
        btn.connect("clicked", lambda _: self._select(scheme))
        parent.append(btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)

        # Preview mockup
        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        preview.add_css_class(preview_css)

        # Tiny fake topbar
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        bar.set_margin_top(12)
        bar.set_margin_bottom(8)
        clock = Gtk.Label(label="12:00")
        clock.add_css_class("theme-preview-clock")
        bar.append(clock)
        preview.append(bar)

        # Fake dock
        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dock.set_halign(Gtk.Align.CENTER)
        dock.set_valign(Gtk.Align.END)
        dock.set_vexpand(True)
        dock.set_margin_bottom(14)
        for _ in range(5):
            dot = Gtk.Box()
            dot.set_size_request(26, 26)
            bg = "rgba(255,255,255,0.15)" if wallpaper_dark else "rgba(0,0,0,0.08)"
            dot.set_css_classes(["theme-preview-dock-icon"])
            dock.append(dot)
        preview.append(dock)

        box.append(preview)

        label = Gtk.Label(label=label_text)
        label.add_css_class("theme-label")
        box.append(label)

        btn.set_child(box)
        return btn, label

    def _select(self, scheme: str):
        self._selected = scheme
        if scheme == "prefer-dark":
            self._dark_btn.add_css_class("selected")
            self._light_btn.remove_css_class("selected")
        else:
            self._light_btn.add_css_class("selected")
            self._dark_btn.remove_css_class("selected")
        try:
            from backend.system import apply_live_theme
            apply_live_theme(scheme)
        except Exception:
            pass

    def _on_next_clicked(self, _btn):
        get_state().color_scheme = self._selected
        try:
            from backend.system import apply_live_theme
            apply_live_theme(self._selected)
        except Exception:
            pass
        self._on_next()
