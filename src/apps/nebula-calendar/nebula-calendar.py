#!/usr/bin/env python3
"""
NebulaOS Calendar
Modern desktop calendar and event planner built with GTK4 & Libadwaita.
"""

import os
import sys
import json
import calendar
import datetime

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

APP_ID = "org.nebulaos.Calendar"
CONFIG_DIR = os.path.expanduser("~/.config/nebula")
EVENTS_FILE = os.path.join(CONFIG_DIR, "calendar_events.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

class CalendarAppWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Calendar")
        self.set_default_size(950, 680)

        self.today = datetime.date.today()
        self.view_year = self.today.year
        self.view_month = self.today.month
        self.selected_date = self.today

        self.events = self._load_events()

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.root_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.root_box.append(self.header)

        # Main horizontal split: Calendar Grid (left) + Day Events List (right)
        self.split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.split_box.set_hexpand(True)
        self.split_box.set_vexpand(True)
        self.root_box.append(self.split_box)

        self._build_calendar_left()
        self._build_events_right()

        self._refresh_calendar()
        self._refresh_events_list()

    def _load_events(self):
        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_events(self):
        try:
            with open(EVENTS_FILE, "w") as f:
                json.dump(self.events, f, indent=2)
        except Exception:
            pass

    def _build_calendar_left(self):
        cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        cal_box.set_hexpand(True)
        cal_box.set_vexpand(True)
        cal_box.set_margin_start(24)
        cal_box.set_margin_end(24)
        cal_box.set_margin_top(16)
        cal_box.set_margin_bottom(16)

        # Nav bar: Prev, Month Year, Next, Today
        nav_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        btn_prev = Gtk.Button(icon_name="go-previous-symbolic")
        btn_prev.connect("clicked", lambda _: self._change_month(-1))
        nav_bar.append(btn_prev)

        self.month_label = Gtk.Label(label="")
        self.month_label.add_css_class("title-2")
        nav_bar.append(self.month_label)

        btn_next = Gtk.Button(icon_name="go-next-symbolic")
        btn_next.connect("clicked", lambda _: self._change_month(1))
        nav_bar.append(btn_next)

        nav_bar.append(Gtk.Box(hexpand=True))

        btn_today = Gtk.Button(label="Today")
        btn_today.connect("clicked", self._go_today)
        nav_bar.append(btn_today)

        cal_box.append(nav_bar)

        # Days of week header (Mon, Tue, Wed...)
        dow_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            lbl = Gtk.Label(label=dow)
            lbl.add_css_class("dim-label")
            lbl.add_css_class("heading")
            dow_box.append(lbl)
        cal_box.append(dow_box)

        # Calendar 7x6 Grid
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(8)
        self.grid.set_row_spacing(8)
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.grid.set_hexpand(True)
        self.grid.set_vexpand(True)
        cal_box.append(self.grid)

        self.split_box.append(cal_box)

    def _build_events_right(self):
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_size_request(320, -1)
        right_box.set_margin_start(16)
        right_box.set_margin_end(20)
        right_box.set_margin_top(16)
        right_box.set_margin_bottom(16)

        # Selected day title
        self.sel_day_label = Gtk.Label(label="")
        self.sel_day_label.set_halign(Gtk.Align.START)
        self.sel_day_label.add_css_class("title-3")
        right_box.append(self.sel_day_label)

        btn_add = Gtk.Button(label="+ New Event")
        btn_add.add_css_class("suggested-action")
        btn_add.connect("clicked", self._open_add_event_dialog)
        right_box.append(btn_add)

        # Event list scrolled
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        self.events_list = Gtk.ListBox()
        self.events_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.events_list.add_css_class("boxed-list")
        scroll.set_child(self.events_list)
        right_box.append(scroll)

        # Separator line
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.split_box.append(sep)
        self.split_box.append(right_box)

    def _refresh_calendar(self):
        # Clear grid
        child = self.grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.grid.remove(child)
            child = next_child

        month_name = calendar.month_name[self.view_month]
        self.month_label.set_text(f"{month_name} {self.view_year}")

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(self.view_year, self.view_month)

        for row_idx, week in enumerate(month_days):
            for col_idx, day_date in enumerate(week):
                btn = Gtk.Button()
                btn.set_hexpand(True)
                btn.set_vexpand(True)

                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.set_halign(Gtk.Align.CENTER)
                box.set_valign(Gtk.Align.CENTER)

                lbl = Gtk.Label(label=str(day_date.day))
                if day_date.month != self.view_month:
                    lbl.add_css_class("dim-label")
                if day_date == self.today:
                    lbl.add_css_class("accent")
                    lbl.add_css_class("bold")

                box.append(lbl)

                # Event dot
                date_key = day_date.strftime("%Y-%m-%d")
                if date_key in self.events and len(self.events[date_key]) > 0:
                    dot = Gtk.Box()
                    dot.set_size_request(6, 6)
                    dot.add_css_class("accent")
                    dot.set_halign(Gtk.Align.CENTER)
                    box.append(dot)

                btn.set_child(box)

                if day_date == self.selected_date:
                    btn.add_css_class("suggested-action")
                else:
                    btn.add_css_class("flat")

                btn.connect("clicked", lambda _, d=day_date: self._select_date(d))
                self.grid.attach(btn, col_idx, row_idx, 1, 1)

    def _select_date(self, d):
        self.selected_date = d
        self._refresh_calendar()
        self._refresh_events_list()

    def _change_month(self, delta):
        m = self.view_month + delta
        y = self.view_year
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        self.view_month = m
        self.view_year = y
        self._refresh_calendar()

    def _go_today(self, _):
        self.view_year = self.today.year
        self.view_month = self.today.month
        self.selected_date = self.today
        self._refresh_calendar()
        self._refresh_events_list()

    def _refresh_events_list(self):
        child = self.events_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.events_list.remove(child)
            child = next_child

        date_key = self.selected_date.strftime("%Y-%m-%d")
        display_str = self.selected_date.strftime("%A, %B %d, %Y")
        self.sel_day_label.set_text(display_str)

        day_events = self.events.get(date_key, [])
        if not day_events:
            empty_row = Adw.ActionRow(title="No events scheduled", subtitle="Click '+ New Event' to plan this day")
            self.events_list.append(empty_row)
            return

        for idx, ev in enumerate(day_events):
            row = Adw.ActionRow(title=ev.get("title", "Event"), subtitle=f"{ev.get('time', 'All Day')} • {ev.get('category', 'General')}")
            btn_del = Gtk.Button(icon_name="user-trash-symbolic")
            btn_del.add_css_class("flat")
            btn_del.connect("clicked", lambda _, i=idx: self._delete_event(date_key, i))
            row.add_suffix(btn_del)
            self.events_list.append(row)

    def _delete_event(self, date_key, idx):
        if date_key in self.events and 0 <= idx < len(self.events[date_key]):
            self.events[date_key].pop(idx)
            if not self.events[date_key]:
                del self.events[date_key]
            self._save_events()
            self._refresh_calendar()
            self._refresh_events_list()

    def _open_add_event_dialog(self, _):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Add Event",
            body=f"Schedule a new event for {self.selected_date.strftime('%B %d, %Y')}"
        )

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)

        entry_title = Gtk.Entry(placeholder_text="Event Title (e.g. Team Meeting)")
        content_box.append(entry_title)

        entry_time = Gtk.Entry(placeholder_text="Time (e.g. 14:30)")
        content_box.append(entry_time)

        combo_cat = Gtk.DropDown.new_from_strings(["Work", "Personal", "Reminder", "Important"])
        content_box.append(combo_cat)

        dialog.set_extra_child(content_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add Event")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def _on_response(d, resp):
            if resp == "add":
                title = entry_title.get_text().strip()
                if title:
                    time_val = entry_time.get_text().strip() or "All Day"
                    cat_val = ["Work", "Personal", "Reminder", "Important"][combo_cat.get_selected()]
                    date_key = self.selected_date.strftime("%Y-%m-%d")
                    if date_key not in self.events:
                        self.events[date_key] = []
                    self.events[date_key].append({
                        "title": title,
                        "time": time_val,
                        "category": cat_val
                    })
                    self._save_events()
                    self._refresh_calendar()
                    self._refresh_events_list()
        dialog.connect("response", _on_response)
        dialog.present()

def main():
    _wizard_done = os.path.exists(os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")) or os.path.exists("/run/nebula-desktop-unlocked")
    if not _wizard_done:
        sys.exit(0)

    GLib.set_prgname("org.nebulaos.Calendar")
    GLib.set_application_name("Calendar")
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    def on_activate(a):
        win = CalendarAppWindow(a)
        win.present()
    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
