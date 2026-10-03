"""
Nebula Setup — Terms of Service Screen
Presents the user with the open-source license and privacy-first terms of service.
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from backend.i18n import t, register_listener


TERMS_SECTIONS = [
    (
        "1. Free & Open Source Software",
        "NebulaOS is an open-source operating system distributed under the terms of the "
        "GNU General Public License (GPL) along with compatible licenses (MIT, Apache, BSD). "
        "You are granted the freedom to use, copy, study, modify, and redistribute the software "
        "in accordance with their respective open-source licenses."
    ),
    (
        "2. Privacy & Telemetry-Free Guarantee",
        "NebulaOS is built on a strict privacy-first foundation. The operating system does not "
        "track your activity, install backdoors, or collect personal data. Telemetry is non-existent "
        "by default. Your files, accounts, cryptographic keys, and usage patterns remain exclusively "
        "on your local hardware."
    ),
    (
        "3. Software Ecosystem & Package Repositories",
        "NebulaOS provides curated access to official Debian repositories, Nebula updates, and "
        "sandboxed Flatpak applications. Any third-party software, codecs, or drivers you choose "
        "to install may be subject to their own proprietary or open-source license agreements."
    ),
    (
        "4. Updates & System Integrity",
        "NebulaOS delivers updates over-the-air (OTA) to provide security fixes, performance "
        "optimizations, and feature enhancements. You maintain complete administrative control over "
        "when and how updates are applied to your system."
    ),
    (
        "5. Disclaimer of Warranty & Limitation of Liability",
        "NebulaOS is provided \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, "
        "INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR "
        "PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE "
        "FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM THE USE OF THIS SOFTWARE."
    )
]


class TermsScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.add_css_class("setup-header")
        self.append(header)

        self._title = Gtk.Label(label=t("terms_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("terms_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        header.append(self._sub)

        # ── Scrollable Terms Box ──────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_margin_start(48)
        scroll.set_margin_end(48)
        scroll.set_margin_bottom(16)
        self.append(scroll)

        terms_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        terms_card.add_css_class("choice-card")
        terms_card.set_margin_top(8)
        terms_card.set_margin_bottom(8)
        terms_card.set_margin_start(16)
        terms_card.set_margin_end(16)
        scroll.set_child(terms_card)

        for sec_title, sec_body in TERMS_SECTIONS:
            sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

            h = Gtk.Label(label=sec_title)
            h.add_css_class("card-title")
            h.set_halign(Gtk.Align.START)
            sec_box.append(h)

            p = Gtk.Label(label=sec_body)
            p.add_css_class("card-subtitle")
            p.set_halign(Gtk.Align.START)
            p.set_wrap(True)
            p.set_justify(Gtk.Justification.LEFT)
            sec_box.append(p)

            terms_card.append(sec_box)

        # ── Agreement Checkbox ────────────────────────────────────────────
        agree_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        agree_box.set_margin_start(52)
        agree_box.set_margin_end(48)
        agree_box.set_margin_bottom(12)
        self.append(agree_box)

        self._check = Gtk.CheckButton(label=t("terms_agree"))
        self._check.connect("toggled", self._on_toggled)
        agree_box.append(self._check)

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
        self._next_btn.set_sensitive(False)
        self._next_btn.connect("clicked", lambda _: self._on_next())
        footer.append(self._next_btn)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("terms_title"))
        self._sub.set_label(t("terms_sub"))
        self._check.set_label(t("terms_agree"))
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("continue"))

    def _on_toggled(self, check: Gtk.CheckButton):
        self._next_btn.set_sensitive(check.get_active())
