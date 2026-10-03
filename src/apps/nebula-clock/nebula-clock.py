#!/usr/bin/env python3
"""
NebulaOS Clock
Complete modern Clock application featuring World Clock, Alarms, Stopwatch, and Timers.
"""

import os
import sys
import time
import json
import datetime
import subprocess

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

APP_ID = "org.nebulaos.Clock"
CONFIG_DIR = os.path.expanduser("~/.config/nebula")
ALARMS_FILE = os.path.join(CONFIG_DIR, "clock_alarms.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

class ClockAppWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Clock")
        self.set_default_size(780, 620)

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.root_box)

        # Header bar with view switcher
        self.header = Adw.HeaderBar()
        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header.set_title_widget(self.view_switcher)
        self.root_box.append(self.header)

        # ViewStack
        self.view_stack = Adw.ViewStack()
        self.view_switcher.set_stack(self.view_stack)
        self.root_box.append(self.view_stack)

        self._build_world_clock()
        self._build_alarm()
        self._build_stopwatch()
        self._build_timer()

        # Regular 1-second clock tick
        GLib.timeout_add(1000, self._on_tick)

    # ── 1. World Clock ────────────────────────────────────────────────────────
    def _build_world_clock(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page_box.set_margin_start(24)
        page_box.set_margin_end(24)
        page_box.set_margin_top(24)
        page_box.set_margin_bottom(24)

        # Big local clock
        hero_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hero_card.set_halign(Gtk.Align.CENTER)

        self.local_time_lbl = Gtk.Label(label="00:00:00")
        self.local_time_lbl.add_css_class("title-1")
        self.local_time_lbl.set_markup("<span font='48' weight='bold'>00:00:00</span>")
        hero_card.append(self.local_time_lbl)

        self.local_date_lbl = Gtk.Label(label="Today")
        self.local_date_lbl.add_css_class("dim-label")
        hero_card.append(self.local_date_lbl)

        page_box.append(hero_card)

        # World Cities Group
        grp = Adw.PreferencesGroup(title="World Timezones")
        page_box.append(grp)

        self.cities = [
            ("London, UK", 0),
            ("Rome / Paris, CET", 1),
            ("New York, USA", -4),
            ("Tokyo, Japan", 9),
            ("Sydney, Australia", 10),
        ]
        self.city_labels = []

        for city, offset in self.cities:
            lbl = Gtk.Label(label="--:--")
            lbl.add_css_class("heading")
            row = Adw.ActionRow(title=city, subtitle=f"UTC {offset:+d} hours")
            row.add_suffix(lbl)
            grp.add(row)
            self.city_labels.append((lbl, offset))

        self.view_stack.add_titled(page_box, "world", "World Clock").set_icon_name("globe-symbolic")

    # ── 2. Alarms ─────────────────────────────────────────────────────────────
    def _build_alarm(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page_box.set_margin_start(24)
        page_box.set_margin_end(24)
        page_box.set_margin_top(20)
        page_box.set_margin_bottom(20)

        # Toolbar
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_lbl = Gtk.Label(label="Scheduled Alarms")
        title_lbl.add_css_class("title-3")
        bar.append(title_lbl)

        bar.append(Gtk.Box(hexpand=True))

        btn_add = Gtk.Button(label="+ Add Alarm")
        btn_add.add_css_class("suggested-action")
        btn_add.connect("clicked", self._add_alarm_dialog)
        bar.append(btn_add)
        page_box.append(bar)

        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.alarm_list = Gtk.ListBox()
        self.alarm_list.add_css_class("boxed-list")
        scroll.set_child(self.alarm_list)
        page_box.append(scroll)

        self.alarms = self._load_alarms()
        self._refresh_alarms_ui()

        self.view_stack.add_titled(page_box, "alarms", "Alarms").set_icon_name("alarm-symbolic")

    def _load_alarms(self):
        if os.path.exists(ALARMS_FILE):
            try:
                with open(ALARMS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return [{"time": "07:30", "label": "Morning Wakeup", "active": True}, {"time": "08:15", "label": "Daily Standup", "active": False}]

    def _save_alarms(self):
        try:
            with open(ALARMS_FILE, "w") as f:
                json.dump(self.alarms, f, indent=2)
        except Exception:
            pass

    def _refresh_alarms_ui(self):
        child = self.alarm_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.alarm_list.remove(child)
            child = next_child

        for idx, a in enumerate(self.alarms):
            sw = Gtk.Switch(active=a.get("active", True), valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, _, i=idx: self._toggle_alarm(i, s.get_active()))

            row = Adw.ActionRow(title=a.get("time", "08:00"), subtitle=a.get("label", "Alarm"))
            row.add_suffix(sw)
            self.alarm_list.append(row)

    def _toggle_alarm(self, idx, active):
        if 0 <= idx < len(self.alarms):
            self.alarms[idx]["active"] = active
            self._save_alarms()

    def _add_alarm_dialog(self, _):
        dialog = Adw.MessageDialog(transient_for=self, heading="New Alarm", body="Set time and name for your alarm:")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=8)
        ent_time = Gtk.Entry(placeholder_text="Time (e.g. 09:00)")
        ent_label = Gtk.Entry(placeholder_text="Label (e.g. Workout)")
        box.append(ent_time)
        box.append(ent_label)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def _resp(d, r):
            if r == "save":
                t = ent_time.get_text().strip()
                l = ent_label.get_text().strip() or "Alarm"
                if t:
                    self.alarms.append({"time": t, "label": l, "active": True})
                    self._save_alarms()
                    self._refresh_alarms_ui()
        dialog.connect("response", _resp)
        dialog.present()

    # ── 3. Stopwatch ──────────────────────────────────────────────────────────
    def _build_stopwatch(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)

        self.sw_elapsed = 0.0
        self.sw_running = False
        self.sw_start_ts = 0.0

        self.sw_display = Gtk.Label()
        self.sw_display.set_markup("<span font='54' weight='bold'>00:00.00</span>")
        box.append(self.sw_display)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.btn_sw_start = Gtk.Button(label="Start")
        self.btn_sw_start.add_css_class("suggested-action")
        self.btn_sw_start.set_size_request(110, 48)
        self.btn_sw_start.connect("clicked", self._sw_toggle)
        btn_box.append(self.btn_sw_start)

        self.btn_sw_reset = Gtk.Button(label="Reset")
        self.btn_sw_reset.set_size_request(110, 48)
        self.btn_sw_reset.connect("clicked", self._sw_reset)
        btn_box.append(self.btn_sw_reset)

        box.append(btn_box)

        self.view_stack.add_titled(box, "stopwatch", "Stopwatch").set_icon_name("media-playback-start-symbolic")

    def _sw_toggle(self, _):
        if self.sw_running:
            self.sw_running = False
            self.sw_elapsed += time.time() - self.sw_start_ts
            self.btn_sw_start.set_label("Resume")
            self.btn_sw_start.remove_css_class("destructive-action")
            self.btn_sw_start.add_css_class("suggested-action")
        else:
            self.sw_running = True
            self.sw_start_ts = time.time()
            self.btn_sw_start.set_label("Stop")
            self.btn_sw_start.remove_css_class("suggested-action")
            self.btn_sw_start.add_css_class("destructive-action")
            GLib.timeout_add(40, self._sw_tick)

    def _sw_tick(self):
        if not self.sw_running:
            return GLib.SOURCE_REMOVE
        cur = self.sw_elapsed + (time.time() - self.sw_start_ts)
        mins = int(cur // 60)
        secs = int(cur % 60)
        centis = int((cur * 100) % 100)
        self.sw_display.set_markup(f"<span font='54' weight='bold'>{mins:02d}:{secs:02d}.{centis:02d}</span>")
        return GLib.SOURCE_CONTINUE

    def _sw_reset(self, _):
        self.sw_running = False
        self.sw_elapsed = 0.0
        self.btn_sw_start.set_label("Start")
        self.btn_sw_start.remove_css_class("destructive-action")
        self.btn_sw_start.add_css_class("suggested-action")
        self.sw_display.set_markup("<span font='54' weight='bold'>00:00.00</span>")

    # ── 4. Timer ──────────────────────────────────────────────────────────────
    def _build_timer(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)

        self.timer_seconds = 300
        self.timer_running = False

        self.timer_display = Gtk.Label()
        self.timer_display.set_markup("<span font='54' weight='bold'>05:00</span>")
        box.append(self.timer_display)

        # Quick preset buttons (1m, 5m, 10m, 15m)
        presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, secs in [("1 min", 60), ("5 min", 300), ("10 min", 600), ("15 min", 900)]:
            b = Gtk.Button(label=label)
            b.add_css_class("flat")
            b.connect("clicked", lambda _, s=secs: self._set_timer(s))
            presets.append(b)
        box.append(presets)

        t_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        t_btn_box.set_halign(Gtk.Align.CENTER)

        self.btn_timer_start = Gtk.Button(label="Start")
        self.btn_timer_start.add_css_class("suggested-action")
        self.btn_timer_start.set_size_request(110, 48)
        self.btn_timer_start.connect("clicked", self._timer_toggle)
        t_btn_box.append(self.btn_timer_start)

        btn_timer_reset = Gtk.Button(label="Reset")
        btn_timer_reset.set_size_request(110, 48)
        btn_timer_reset.connect("clicked", lambda _: self._set_timer(300))
        t_btn_box.append(btn_timer_reset)

        box.append(t_btn_box)

        self.view_stack.add_titled(box, "timer", "Timer").set_icon_name("preferences-system-time-symbolic")

    def _set_timer(self, secs):
        self.timer_running = False
        self.timer_seconds = secs
        self.btn_timer_start.set_label("Start")
        self._update_timer_display()

    def _update_timer_display(self):
        m = self.timer_seconds // 60
        s = self.timer_seconds % 60
        self.timer_display.set_markup(f"<span font='54' weight='bold'>{m:02d}:{s:02d}</span>")

    def _timer_toggle(self, _):
        if self.timer_running:
            self.timer_running = False
            self.btn_timer_start.set_label("Resume")
        else:
            self.timer_running = True
            self.btn_timer_start.set_label("Pause")
            GLib.timeout_add(1000, self._timer_tick)

    def _timer_tick(self):
        if not self.timer_running:
            return GLib.SOURCE_REMOVE
        if self.timer_seconds > 0:
            self.timer_seconds -= 1
            self._update_timer_display()
            return GLib.SOURCE_CONTINUE
        else:
            self.timer_running = False
            self.btn_timer_start.set_label("Start")
            # Ring alert
            try:
                subprocess.Popen(["notify-send", "-a", "Nebula Clock", "Timer Finished", "Your countdown timer has ended."])
                subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
            except Exception:
                pass
            return GLib.SOURCE_REMOVE

    # ── General Clock Tick ────────────────────────────────────────────────────
    def _on_tick(self):
        now = datetime.datetime.now()
        self.local_time_lbl.set_markup(f"<span font='48' weight='bold'>{now.strftime('%H:%M:%S')}</span>")
        self.local_date_lbl.set_text(now.strftime("%A, %B %d, %Y"))

        utc_now = datetime.datetime.utcnow()
        for lbl, offset in self.city_labels:
            city_time = utc_now + datetime.timedelta(hours=offset)
            lbl.set_text(city_time.strftime("%H:%M"))

        return GLib.SOURCE_CONTINUE

def main():
    _wizard_done = os.path.exists(os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")) or os.path.exists("/run/nebula-desktop-unlocked")
    if not _wizard_done:
        sys.exit(0)

    GLib.set_prgname("org.nebulaos.Clock")
    GLib.set_application_name("Clock")
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    def on_activate(a):
        win = ClockAppWindow(a)
        win.present()
    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
