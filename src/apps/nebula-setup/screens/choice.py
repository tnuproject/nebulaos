"""
Nebula Setup — Choice Screen
Lets the user choose between "Try NebulaOS" and "Install NebulaOS".
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from backend.i18n import t, register_listener


class ChoiceScreen(Gtk.Box):
    def __init__(self, on_try, on_install):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_try = on_try
        self._on_install = on_install
        self._build()

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header.set_halign(Gtk.Align.CENTER)
        header.set_valign(Gtk.Align.CENTER)
        header.set_vexpand(True)
        header.set_margin_top(72)
        header.set_margin_bottom(48)
        self.append(header)

        self._title = Gtk.Label(label=t("welcome_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.CENTER)
        header.append(self._title)

        self._subtitle = Gtk.Label(label=t("welcome_sub"))
        self._subtitle.add_css_class("setup-subtitle")
        self._subtitle.set_halign(Gtk.Align.CENTER)
        header.append(self._subtitle)

        # ── Cards ─────────────────────────────────────────────────────────
        cards_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        cards_row.set_halign(Gtk.Align.CENTER)
        cards_row.set_valign(Gtk.Align.CENTER)
        cards_row.set_vexpand(True)
        self.append(cards_row)

        # Try card
        try_card, self._try_title, self._try_sub = self._make_card(
            icon="🖥️",
            title=t("try_title"),
            subtitle=t("try_sub"),
            primary=False,
            callback=self._on_try_clicked
        )
        cards_row.append(try_card)

        # Install card
        install_card, self._install_title, self._install_sub = self._make_card(
            icon="⬇️",
            title=t("install_title"),
            subtitle=t("install_sub"),
            primary=True,
            callback=self._on_install_clicked
        )
        cards_row.append(install_card)

        # ── Spacer ────────────────────────────────────────────────────────
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.append(spacer)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("welcome_title"))
        self._subtitle.set_label(t("welcome_sub"))
        self._try_title.set_label(t("try_title"))
        self._try_sub.set_label(t("try_sub"))
        self._install_title.set_label(t("install_title"))
        self._install_sub.set_label(t("install_sub"))

    def _make_card(self, icon, title, subtitle, primary, callback):
        btn = Gtk.Button()
        btn.add_css_class("choice-card")
        btn.connect("clicked", lambda _: callback())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)

        icon_lbl = Gtk.Label(label=icon)
        icon_lbl.add_css_class("card-icon")
        box.append(icon_lbl)

        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("card-title")
        title_lbl.set_halign(Gtk.Align.CENTER)
        box.append(title_lbl)

        sub_lbl = Gtk.Label(label=subtitle)
        sub_lbl.add_css_class("card-subtitle")
        sub_lbl.set_halign(Gtk.Align.CENTER)
        sub_lbl.set_justify(Gtk.Justification.CENTER)
        sub_lbl.set_wrap(True)
        sub_lbl.set_max_width_chars(28)
        box.append(sub_lbl)

        btn.set_child(box)
        return btn, title_lbl, sub_lbl

    def _on_try_clicked(self):
        try:
            with open("/run/nebula-desktop-unlocked", "w") as f:
                f.write("1")
        except Exception:
            pass
        self._on_try()

    def _on_install_clicked(self):
        self._on_install()

