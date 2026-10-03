"""
Nebula Setup — Language Selector Screen
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from backend.state import get_state
from backend.i18n import t, set_language, register_listener


LANGUAGES = [
    ("en_US", "English", "English"),
    ("it_IT", "Italiano", "Italian"),
    ("es_ES", "Español", "Spanish"),
    ("fr_FR", "Français", "French"),
    ("de_DE", "Deutsch", "German"),
    ("pt_BR", "Português (Brasil)", "Portuguese (Brazil)"),
    ("pt_PT", "Português (Portugal)", "Portuguese (Portugal)"),
    ("ja_JP", "日本語", "Japanese"),
    ("zh_CN", "中文 (简体)", "Chinese (Simplified)"),
    ("zh_TW", "中文 (繁體)", "Chinese (Traditional)"),
    ("ko_KR", "한국어", "Korean"),
    ("ru_RU", "Русский", "Russian"),
    ("ar_SA", "العربية", "Arabic"),
    ("hi_IN", "हिन्दी", "Hindi"),
    ("tr_TR", "Türkçe", "Turkish"),
    ("nl_NL", "Nederlands", "Dutch"),
    ("pl_PL", "Polski", "Polish"),
    ("sv_SE", "Svenska", "Swedish"),
    ("nb_NO", "Norsk Bokmål", "Norwegian"),
    ("da_DK", "Dansk", "Danish"),
    ("fi_FI", "Suomi", "Finnish"),
    ("el_GR", "Ελληνικά", "Greek"),
    ("he_IL", "עברית", "Hebrew"),
    ("cs_CZ", "Čeština", "Czech"),
    ("hu_HU", "Magyar", "Hungarian"),
]

# Map language code → keyboard layout
LANG_TO_KB = {
    "it_IT": ("it", "pc105"),
    "es_ES": ("es", "pc105"),
    "fr_FR": ("fr", "pc105"),
    "de_DE": ("de", "pc105"),
    "ru_RU": ("ru", "pc105"),
    "ja_JP": ("jp", "pc105"),
    "ar_SA": ("ara", "pc105"),
    "el_GR": ("gr", "pc105"),
    "he_IL": ("il", "pc105"),
    "ko_KR": ("kr", "pc104"),
    "zh_CN": ("cn", "pc105"),
    "zh_TW": ("tw", "pc105"),
    "tr_TR": ("tr", "pc105"),
    "pl_PL": ("pl", "pc105"),
    "sv_SE": ("se", "pc105"),
    "nb_NO": ("no", "pc105"),
    "da_DK": ("dk", "pc105"),
    "fi_FI": ("fi", "pc105"),
    "hu_HU": ("hu", "pc105"),
    "cs_CZ": ("cz", "pc105"),
    "nl_NL": ("nl", "pc105"),
}


class LanguageScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back
        self._selected_index = 0
        self._filtered = list(LANGUAGES)
        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.add_css_class("setup-header")
        self.append(header)

        self._title = Gtk.Label(label=t("lang_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("lang_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        header.append(self._sub)

        # ── Search ────────────────────────────────────────────────────────
        self._search = Gtk.SearchEntry()
        try:
            self._search.set_property("placeholder-text", t("search_lang"))
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

        self._populate_list()

        # ── Footer nav ────────────────────────────────────────────────────
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

    def _populate_list(self, filter_text: str = ""):
        # Clear existing rows
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        self._filtered = [
            lang for lang in LANGUAGES
            if (not filter_text
                or filter_text.lower() in lang[1].lower()
                or filter_text.lower() in lang[2].lower())
        ]

        state = get_state()
        for i, (code, native, english) in enumerate(self._filtered):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            native_lbl = Gtk.Label(label=native)
            native_lbl.set_hexpand(True)
            native_lbl.set_halign(Gtk.Align.START)
            box.append(native_lbl)

            eng_lbl = Gtk.Label(label=english)
            eng_lbl.set_halign(Gtk.Align.END)
            eng_lbl.set_opacity(0.55)
            box.append(eng_lbl)

            row.set_child(box)
            self._list_box.append(row)

            if code == state.language:
                self._list_box.select_row(row)

    def _on_search(self, entry):
        self._populate_list(entry.get_text())

    def _on_row_selected(self, _listbox, row):
        if row is not None:
            self._selected_index = row.get_index()
            if 0 <= self._selected_index < len(self._filtered):
                code, native, _ = self._filtered[self._selected_index]
                state = get_state()
                state.language = code
                state.language_display = native
                kb, model = LANG_TO_KB.get(code, ("us", "pc105"))
                state.keyboard_layout = kb
                state.keyboard_model = model
                set_language(code)
                try:
                    from backend.system import apply_live_keyboard_layout
                    apply_live_keyboard_layout(kb, model)
                except Exception:
                    pass

    def _refresh_text(self):
        self._title.set_label(t("lang_title"))
        self._sub.set_label(t("lang_sub"))
        try:
            self._search.set_property("placeholder-text", t("search_lang"))
        except Exception:
            pass
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("continue"))

    def _on_next_clicked(self, _btn):
        if self._filtered and 0 <= self._selected_index < len(self._filtered):
            code, native, _ = self._filtered[self._selected_index]
            state = get_state()
            state.language = code
            state.language_display = native
            kb, model = LANG_TO_KB.get(code, ("us", "pc105"))
            state.keyboard_layout = kb
            state.keyboard_model = model
            set_language(code)
            try:
                from backend.system import apply_live_keyboard_layout
                apply_live_keyboard_layout(kb, model)
            except Exception:
                pass
        self._on_next()
