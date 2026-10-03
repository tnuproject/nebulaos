"""
Nebula Setup — Timezone Selector Screen
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from backend.state import get_state
from backend.i18n import t, register_listener


# Regions and representative cities
TIMEZONES = [
    # (display, timezone_value)
    ("Europe/Rome", "Rome"),
    ("Europe/London", "London"),
    ("Europe/Paris", "Paris"),
    ("Europe/Berlin", "Berlin"),
    ("Europe/Madrid", "Madrid"),
    ("Europe/Amsterdam", "Amsterdam"),
    ("Europe/Zurich", "Zurich"),
    ("Europe/Brussels", "Brussels"),
    ("Europe/Stockholm", "Stockholm"),
    ("Europe/Oslo", "Oslo"),
    ("Europe/Helsinki", "Helsinki"),
    ("Europe/Warsaw", "Warsaw"),
    ("Europe/Prague", "Prague"),
    ("Europe/Budapest", "Budapest"),
    ("Europe/Athens", "Athens"),
    ("Europe/Bucharest", "Bucharest"),
    ("Europe/Moscow", "Moscow"),
    ("Europe/Kyiv", "Kyiv"),
    ("America/New_York", "New York"),
    ("America/Chicago", "Chicago"),
    ("America/Denver", "Denver"),
    ("America/Los_Angeles", "Los Angeles"),
    ("America/Toronto", "Toronto"),
    ("America/Vancouver", "Vancouver"),
    ("America/Mexico_City", "Mexico City"),
    ("America/Sao_Paulo", "São Paulo"),
    ("America/Buenos_Aires", "Buenos Aires"),
    ("America/Bogota", "Bogotá"),
    ("America/Lima", "Lima"),
    ("America/Santiago", "Santiago"),
    ("Asia/Tokyo", "Tokyo"),
    ("Asia/Shanghai", "Shanghai"),
    ("Asia/Seoul", "Seoul"),
    ("Asia/Kolkata", "Mumbai / Kolkata"),
    ("Asia/Singapore", "Singapore"),
    ("Asia/Bangkok", "Bangkok"),
    ("Asia/Jakarta", "Jakarta"),
    ("Asia/Dubai", "Dubai"),
    ("Asia/Tel_Aviv", "Tel Aviv"),
    ("Asia/Riyadh", "Riyadh"),
    ("Asia/Karachi", "Karachi"),
    ("Asia/Dhaka", "Dhaka"),
    ("Australia/Sydney", "Sydney"),
    ("Australia/Melbourne", "Melbourne"),
    ("Australia/Perth", "Perth"),
    ("Pacific/Auckland", "Auckland"),
    ("Africa/Cairo", "Cairo"),
    ("Africa/Lagos", "Lagos"),
    ("Africa/Nairobi", "Nairobi"),
    ("Africa/Johannesburg", "Johannesburg"),
    ("UTC", "UTC / Coordinated Universal Time"),
]


class TimezoneScreen(Gtk.Box):
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

        self._title = Gtk.Label(label=t("tz_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("tz_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        header.append(self._sub)

        # ── Search ────────────────────────────────────────────────────────
        self._search = Gtk.SearchEntry()
        try:
            self._search.set_property("placeholder-text", t("search_city"))
        except Exception:
            pass
        self._search.set_margin_start(64)
        self._search.set_margin_end(64)
        self._search.set_margin_bottom(16)
        self._search.connect("search-changed", self._on_search)
        self.append(self._search)

        # ── List ──────────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_margin_start(64)
        scroll.set_margin_end(64)
        self.append(scroll)

        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("options-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-selected", self._on_row_selected)
        scroll.set_child(self._list_box)

        self._all_tz = TIMEZONES
        self._filtered = list(TIMEZONES)
        self._selected_index = 0
        self._populate_list()

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
        self._title.set_label(t("tz_title"))
        self._sub.set_label(t("tz_sub"))
        try:
            self._search.set_property("placeholder-text", t("search_city"))
        except Exception:
            pass
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("continue"))

    def _populate_list(self, filter_text: str = ""):
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        ft = filter_text.lower()
        self._filtered = [
            tz for tz in self._all_tz
            if not ft or ft in tz[0].lower() or ft in tz[1].lower()
        ]

        state = get_state()
        for i, (tz_val, city) in enumerate(self._filtered):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            city_lbl = Gtk.Label(label=city)
            city_lbl.set_hexpand(True)
            city_lbl.set_halign(Gtk.Align.START)
            box.append(city_lbl)

            tz_lbl = Gtk.Label(label=tz_val)
            tz_lbl.set_halign(Gtk.Align.END)
            tz_lbl.set_opacity(0.5)
            box.append(tz_lbl)

            row.set_child(box)
            self._list_box.append(row)

            if tz_val == state.timezone:
                self._list_box.select_row(row)
                self._selected_index = i

    def _on_search(self, entry):
        self._populate_list(entry.get_text())

    def _on_row_selected(self, _lb, row):
        if row:
            self._selected_index = row.get_index()

    def _on_next_clicked(self, _btn):
        if self._filtered:
            tz_val, _ = self._filtered[self._selected_index]
            get_state().timezone = tz_val
            try:
                from backend.system import apply_live_timezone
                apply_live_timezone(tz_val)
            except Exception:
                pass
        self._on_next()
