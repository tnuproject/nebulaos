#!/usr/bin/env python3
"""
PetalDrop Fixed Overlay for NebulaOS
Floating, pinned GTK4 / Libadwaita drop-zone for sharing files with nearby
NebulaOS and MyNebula Android devices.
"""

import os
import sys
import json
import signal
import threading
import urllib.request
import urllib.error

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

PID_FILE = "/tmp/petaldrop.pid"
COMPANION_PEERS_API = "http://127.0.0.1:53317/api/drop/peers"
COMPANION_PUSH_API = "http://127.0.0.1:53317/api/drop/push"

CSS_DATA = """
window.petaldrop-window {
    background-color: #222225;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 24px;
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.6);
}

.petaldrop-header {
    padding: 14px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.petaldrop-title {
    font-weight: 700;
    font-size: 15px;
    color: #ffffff;
}

.petaldrop-close-btn {
    border-radius: 9999px;
    min-width: 28px;
    min-height: 28px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.7);
    border: none;
}
.petaldrop-close-btn:hover {
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
}

.dropzone-box {
    border: 2px dashed rgba(255, 255, 255, 0.22);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.03);
    padding: 24px 16px;
    margin: 16px;
    transition: all 180ms ease;
}

.dropzone-box.drag-hover {
    border-color: #3584e4;
    background: rgba(53, 132, 228, 0.12);
}

.petaldrop-prompt {
    font-weight: 600;
    font-size: 14px;
    color: #ffffff;
    margin-top: 10px;
    margin-bottom: 4px;
}

.petaldrop-subtext {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.55);
}

.peer-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 12px 14px;
    margin-bottom: 8px;
    transition: background 150ms ease;
}
.peer-card:hover {
    background: rgba(53, 132, 228, 0.16);
    border-color: rgba(53, 132, 228, 0.4);
}

.pill-btn {
    border-radius: 9999px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
}
"""

class PetalDropWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("PetalDrop")
        self.add_css_class("petaldrop-window")
        self.set_default_size(440, 320)
        self.set_resizable(False)
        self.set_decorated(False)

        self._file_to_send = None
        self._build_ui()
        self._setup_dnd()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # 1. Header Bar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.add_css_class("petaldrop-header")

        icon = Gtk.Image.new_from_icon_name("document-send-symbolic")
        icon.set_pixel_size(18)
        header.append(icon)

        title = Gtk.Label(label="Petal Drop")
        title.add_css_class("petaldrop-title")
        header.append(title)

        spacer = Gtk.Box(hexpand=True)
        header.append(spacer)

        close_btn = Gtk.Button()
        close_btn.add_css_class("petaldrop-close-btn")
        close_icon = Gtk.Image.new_from_icon_name("window-close-symbolic")
        close_icon.set_pixel_size(14)
        close_btn.set_child(close_icon)
        close_btn.connect("clicked", lambda _: self.close())
        header.append(close_btn)

        main_box.append(header)

        # 2. Content Stack (Drop Zone vs Peers vs Transferring vs Success)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)
        main_box.append(self.stack)

        # Page 1: Drop Zone View
        self.drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.drop_box.add_css_class("dropzone-box")
        self.drop_box.set_valign(Gtk.Align.CENTER)
        self.drop_box.set_halign(Gtk.Align.FILL)
        self.drop_box.set_vexpand(True)

        center_icon = Gtk.Image.new_from_icon_name("folder-drag-accept-symbolic")
        center_icon.set_pixel_size(48)
        self.drop_box.append(center_icon)

        prompt_lbl = Gtk.Label(label="Drop here the media you want to share via PetalDrop")
        prompt_lbl.add_css_class("petaldrop-prompt")
        prompt_lbl.set_wrap(True)
        prompt_lbl.set_justify(Gtk.Justification.CENTER)
        self.drop_box.append(prompt_lbl)

        sub_lbl = Gtk.Label(label="Offline & local Wi-Fi sharing with nearby NebulaOS & Android devices")
        sub_lbl.add_css_class("petaldrop-subtext")
        sub_lbl.set_wrap(True)
        sub_lbl.set_justify(Gtk.Justification.CENTER)
        self.drop_box.append(sub_lbl)

        browse_btn = Gtk.Button(label="Browse Files...")
        browse_btn.add_css_class("pill-btn")
        browse_btn.set_halign(Gtk.Align.CENTER)
        browse_btn.set_margin_top(12)
        browse_btn.connect("clicked", self._on_browse_clicked)
        self.drop_box.append(browse_btn)

        self.stack.add_named(self.drop_box, "dropzone")

        # Page 2: Peers View
        self.peers_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.peers_container.set_margin_start(16)
        self.peers_container.set_margin_end(16)
        self.peers_container.set_margin_top(12)
        self.peers_container.set_margin_bottom(12)

        self.file_info_lbl = Gtk.Label()
        self.file_info_lbl.set_markup("<b>Ready to send:</b> <span color='#3584e4'>file.jpg</span>")
        self.peers_container.append(self.file_info_lbl)

        peers_scroll = Gtk.ScrolledWindow()
        peers_scroll.set_vexpand(True)
        peers_scroll.set_min_content_height(140)
        self.peers_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        peers_scroll.set_child(self.peers_list_box)
        self.peers_container.append(peers_scroll)

        back_to_drop_btn = Gtk.Button(label="Cancel")
        back_to_drop_btn.add_css_class("pill-btn")
        back_to_drop_btn.set_halign(Gtk.Align.CENTER)
        back_to_drop_btn.connect("clicked", lambda _: self.stack.set_visible_child_name("dropzone"))
        self.peers_container.append(back_to_drop_btn)

        self.stack.add_named(self.peers_container, "peers")

        # Page 3: Sending / Status View
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.status_box.set_valign(Gtk.Align.CENTER)
        self.status_box.set_halign(Gtk.Align.CENTER)
        self.status_box.set_vexpand(True)

        self.status_spinner = Gtk.Spinner()
        self.status_spinner.set_size_request(40, 40)
        self.status_box.append(self.status_spinner)

        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(48)
        self.status_box.append(self.status_icon)

        self.status_title = Gtk.Label()
        self.status_title.add_css_class("petaldrop-prompt")
        self.status_box.append(self.status_title)

        self.status_sub = Gtk.Label()
        self.status_sub.add_css_class("petaldrop-subtext")
        self.status_box.append(self.status_sub)

        self.status_done_btn = Gtk.Button(label="Done")
        self.status_done_btn.add_css_class("pill-btn")
        self.status_done_btn.connect("clicked", lambda _: self.close())
        self.status_box.append(self.status_done_btn)

        self.stack.add_named(self.status_box, "status")
        self.stack.set_visible_child_name("dropzone")

    def _setup_dnd(self):
        # Native GTK4 Wayland Drag-and-Drop Target
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_file_dropped)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        self.add_controller(drop_target)

    def _on_drag_enter(self, target, x, y):
        self.drop_box.add_css_class("drag-hover")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, target):
        self.drop_box.remove_css_class("drag-hover")

    def _on_file_dropped(self, target, gfile, x, y):
        self.drop_box.remove_css_class("drag-hover")
        if isinstance(gfile, Gio.File):
            path = gfile.get_path()
            if path and os.path.exists(path):
                self._handle_file_selected(path)
                return True
        return False

    def _on_browse_clicked(self, _btn):
        dialog = Gtk.FileChooserNative.new(
            "Select Media to Share via PetalDrop",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel"
        )
        def on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                gfile = dlg.get_file()
                if gfile:
                    path = gfile.get_path()
                    if path and os.path.exists(path):
                        self._handle_file_selected(path)
        dialog.connect("response", on_response)
        dialog.show()

    def _handle_file_selected(self, file_path):
        self._file_to_send = file_path
        filename = os.path.basename(file_path)
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{int(os.path.getsize(file_path)/1024)} KB"
        
        self.file_info_lbl.set_markup(f"<b>Share:</b> <span color='#3584e4'>{GLib.markup_escape_text(filename)}</span> ({size_str})")
        self.stack.set_visible_child_name("peers")
        self._fetch_peers()

    def _fetch_peers(self):
        # Clear list
        while child := self.peers_list_box.get_first_child():
            self.peers_list_box.remove(child)

        loading_lbl = Gtk.Label(label="Searching for nearby devices...")
        loading_lbl.add_css_class("petaldrop-subtext")
        loading_lbl.set_margin_top(16)
        self.peers_list_box.append(loading_lbl)

        def worker():
            peers = []
            try:
                req = urllib.request.Request(COMPANION_PEERS_API, headers={"User-Agent": "PetalDrop"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    data = json.loads(resp.read().decode())
                    peers = data.get("peers", [])
            except Exception:
                pass
            GLib.idle_add(lambda: self._populate_peers(peers))

        threading.Thread(target=worker, daemon=True).start()

    def _populate_peers(self, peers):
        while child := self.peers_list_box.get_first_child():
            self.peers_list_box.remove(child)

        if not peers:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            empty_box.set_margin_top(20)
            
            lbl = Gtk.Label(label="No nearby devices found.")
            lbl.add_css_class("petaldrop-prompt")
            empty_box.append(lbl)

            sub = Gtk.Label(label="Ensure MyNebula is open on your Android phone or nearby laptop.")
            sub.add_css_class("petaldrop-subtext")
            empty_box.append(sub)

            retry_btn = Gtk.Button(label="Refresh Devices")
            retry_btn.add_css_class("pill-btn")
            retry_btn.set_halign(Gtk.Align.CENTER)
            retry_btn.set_margin_top(10)
            retry_btn.connect("clicked", lambda _: self._fetch_peers())
            empty_box.append(retry_btn)

            self.peers_list_box.append(empty_box)
            return

        for peer in peers:
            name = peer.get("name", "Unknown Device")
            ip = peer.get("ip", "")
            is_paired = peer.get("is_paired", False)

            btn = Gtk.Button()
            btn.add_css_class("peer-card")

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            
            icon_name = "phone-symbolic" if "Android" in name or is_paired else "computer-symbolic"
            dev_icon = Gtk.Image.new_from_icon_name(icon_name)
            dev_icon.set_pixel_size(24)
            row.append(dev_icon)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            name_lbl = Gtk.Label(label=name)
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.add_css_class("petaldrop-title")
            info_box.append(name_lbl)

            status_str = "Paired Device" if is_paired else f"Ready • {ip}"
            status_lbl = Gtk.Label(label=status_str)
            status_lbl.set_halign(Gtk.Align.START)
            status_lbl.add_css_class("petaldrop-subtext")
            info_box.append(status_lbl)

            row.append(info_box)

            send_icon = Gtk.Image.new_from_icon_name("document-send-symbolic")
            send_icon.set_pixel_size(16)
            row.append(send_icon)

            btn.set_child(row)
            btn.connect("clicked", lambda _, p=peer: self._send_file_to_peer(p))
            self.peers_list_box.append(btn)

    def _send_file_to_peer(self, peer):
        self.stack.set_visible_child_name("status")
        self.status_spinner.set_visible(True)
        self.status_spinner.start()
        self.status_icon.set_visible(False)
        self.status_title.set_text("Sending via PetalDrop...")
        self.status_sub.set_text(f"Transferring to {peer.get('name', 'Device')}...")
        self.status_done_btn.set_visible(False)

        def worker():
            success = False
            err_msg = ""
            try:
                payload = json.dumps({
                    "file_path": self._file_to_send,
                    "target_ip": peer.get("ip")
                }).encode("utf-8")
                req = urllib.request.Request(
                    COMPANION_PUSH_API,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "PetalDrop"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    res = json.loads(resp.read().decode())
                    success = res.get("success", False)
                    if not success:
                        err_msg = res.get("error", "Transfer failed")
            except Exception as e:
                err_msg = str(e)

            GLib.idle_add(lambda: self._on_send_completed(success, peer.get("name", "Device"), err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_send_completed(self, success, peer_name, err_msg):
        self.status_spinner.stop()
        self.status_spinner.set_visible(False)
        self.status_icon.set_visible(True)
        self.status_done_btn.set_visible(True)

        if success:
            self.status_icon.set_from_icon_name("emblem-ok-symbolic")
            self.status_title.set_text("Sent Successfully!")
            self.status_sub.set_text(f"File delivered to {peer_name}")
            self.status_done_btn.set_label("Close")
        else:
            self.status_icon.set_from_icon_name("dialog-error-symbolic")
            self.status_title.set_text("Transfer Failed")
            self.status_sub.set_text(err_msg or "Could not transfer file.")
            self.status_done_btn.set_label("Try Again")
            self.status_done_btn.disconnect_by_func(self.close)
            self.status_done_btn.connect("clicked", lambda _: self.stack.set_visible_child_name("peers"))


class PetalDropApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.nebulaos.petaldrop",
            flags=Gio.ApplicationFlags.NON_UNIQUE
        )

    def do_startup(self):
        super().do_startup()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = PetalDropWindow(self)
        win.present()


def handle_pid_toggle():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                content = f.read().strip()
            if content:
                pid = int(content)
                # Check if process is actually running
                os.kill(pid, 0)
                # Process is running, toggle off
                os.kill(pid, signal.SIGTERM)
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass
                return True
        except (ProcessLookupError, OSError):
            # Process was not alive, remove stale PID
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        except Exception:
            pass
    return False

def write_pid():
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

def remove_pid(*_args):
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def main():
    if "--toggle" in sys.argv:
        if handle_pid_toggle():
            sys.exit(0)

    write_pid()
    signal.signal(signal.SIGTERM, remove_pid)
    signal.signal(signal.SIGINT, remove_pid)

    app = PetalDropApp()
    try:
        # Pass only executable name so GTK doesn't fail on custom flags like --toggle
        app.run([sys.argv[0]])
    finally:
        remove_pid()

if __name__ == "__main__":
    main()
