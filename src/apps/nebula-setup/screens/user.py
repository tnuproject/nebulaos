"""
Nebula Setup — User Creation Screen
Collects full name, username, password, and hostname.
"""

import re
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from backend.state import get_state
from backend.i18n import t, register_listener


class UserScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._next_btn = None
        self._field_labels = {}
        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        # ── Scrollable content ────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.append(scroll)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll.set_child(content)

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.add_css_class("setup-header")
        content.append(header)

        self._title = Gtk.Label(label=t("user_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("user_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        header.append(self._sub)

        # ── Form ──────────────────────────────────────────────────────────
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        form.add_css_class("setup-content")
        form.add_css_class("user-form")
        form.set_size_request(480, -1)
        content.append(form)

        # Full Name
        self._full_name = self._make_field("full_name", form, t("full_name"), "Your name",
                                           placeholder="e.g. Luca Bianchi")
        self._full_name.connect("changed", self._auto_suggest_username)

        # Username
        self._username = self._make_field("username", form, t("username"), "System username",
                                          placeholder="e.g. luca")
        self._username.connect("changed", self._validate)

        # Password
        self._password = self._make_field("password", form, t("password"), "Password",
                                          placeholder="••••••••",
                                          is_password=True)
        self._password.connect("changed", self._on_password_changed)

        # Confirm Password
        self._confirm = self._make_field("confirm_password", form, t("confirm_password"), "Confirm",
                                         placeholder="••••••••",
                                         is_password=True)
        self._confirm.connect("changed", self._validate)

        # Hostname
        self._hostname = self._make_field("computer_name", form, t("computer_name"), "Hostname",
                                          placeholder="e.g. nebulaos")
        self._hostname.connect("changed", self._validate)

        # Error label
        self._error_lbl = Gtk.Label()
        self._error_lbl.set_halign(Gtk.Align.START)
        self._error_lbl.set_wrap(True)
        self._error_lbl.set_visible(False)
        self._error_lbl.add_css_class("disk-warning")
        form.append(self._error_lbl)

        # Pre-fill from state
        state = get_state()
        if state.full_name:
            self._full_name.set_text(state.full_name)
        if state.username:
            self._username.set_text(state.username)
        if state.hostname:
            self._hostname.set_text(state.hostname)

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
        self._title.set_label(t("user_title"))
        self._sub.set_label(t("user_sub"))
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("continue"))
        for key, lbl in self._field_labels.items():
            lbl.set_label(t(key))

    def _make_field(self, key: str, parent: Gtk.Box, label_text: str, aria_label: str,
                    placeholder: str = "", is_password: bool = False) -> Gtk.Entry:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        label = Gtk.Label(label=label_text)
        label.add_css_class("field-label")
        label.set_halign(Gtk.Align.START)
        box.append(label)
        self._field_labels[key] = label

        entry = Gtk.Entry()
        entry.set_placeholder_text(placeholder)
        if is_password:
            entry.set_visibility(False)
            entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        parent.append(box)
        box.append(entry)
        return entry

    # ── Auto-suggest username ─────────────────────────────────────────────

    def _auto_suggest_username(self, entry):
        name = entry.get_text().lower().strip()
        # Take first word, strip non-alphanumeric
        suggested = re.sub(r'[^a-z0-9]', '', name.split()[0] if name.split() else "")
        if suggested and not self._username.get_text():
            self._username.set_text(suggested)
        # Auto-suggest hostname
        if suggested and not self._hostname.get_text():
            self._hostname.set_text(f"{suggested}-nebulaos")
        self._validate()

    def _on_password_changed(self, entry):
        self._validate()

    def _validate(self, *_):
        username = self._username.get_text().strip()
        password = self._password.get_text()
        confirm  = self._confirm.get_text()
        hostname = self._hostname.get_text().strip()

        errors = []

        if username and not re.match(r'^[a-z][a-z0-9_-]{0,30}$', username):
            errors.append("Username must be lowercase letters/numbers/dash (start with a letter)")

        if password and len(password) < 8:
            errors.append("Password must be at least 8 characters")

        if confirm and password != confirm:
            errors.append("Passwords do not match")

        if hostname and not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', hostname):
            errors.append("Computer name must contain only letters, numbers and hyphens")

        if errors:
            self._error_lbl.set_label("\n".join(errors))
            self._error_lbl.set_visible(True)
            if self._next_btn:
                self._next_btn.set_sensitive(False)
        else:
            self._error_lbl.set_visible(False)
            # Enable only if all required fields filled
            ok = bool(self._full_name.get_text().strip()
                      and username
                      and password == confirm
                      and len(password) >= 8
                      and hostname)
            if self._next_btn:
                self._next_btn.set_sensitive(ok)

    def _on_next_clicked(self, _btn):
        state = get_state()
        state.full_name = self._full_name.get_text().strip()
        state.username  = self._username.get_text().strip()
        state.password  = self._password.get_text()
        state.hostname  = self._hostname.get_text().strip()
        self._on_next()
