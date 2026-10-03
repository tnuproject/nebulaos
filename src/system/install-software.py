#!/usr/bin/env python3
"""
Install Software — Nebula Drag-and-Drop Software Installer
Allows installing Debian packages (.deb) by dragging the Application icon
into the Applications folder.
"""

import sys
import os
import subprocess
import shutil
import tempfile
import threading
import urllib.parse
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk

GLib.set_prgname("install-software")
GLib.set_application_name("Install Software")

def get_apps_folder():
    lang = os.environ.get("LANG", "en_US.UTF-8")
    folder_name = "Applicazioni" if "it" in lang.lower() else "Applications"
    home = Path.home()
    apps_dir = home / folder_name
    apps_dir.mkdir(parents=True, exist_ok=True)
    return apps_dir

class DmgInstallerWindow(Gtk.Window):
    def __init__(self, deb_path=None):
        super().__init__(title="Install Software")
        self.set_wmclass("install-software", "install-software")
        self.set_role("installer")
        self.set_default_size(560, 340)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        # Force GTK Dark Mode
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)
            settings.set_property("gtk-theme-name", "Adwaita-dark")

        # Drag-and-drop installer styling with clean black text
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: #f5f5f7;
            }
            label {
                color: #000000;
            }
            .drop-target {
                border: 2.5px dashed #007aff;
                border-radius: 20px;
                background-color: rgba(0, 122, 255, 0.08);
            }
            .drop-target-hover {
                border: 2.5px solid #34c759;
                border-radius: 20px;
                background-color: rgba(52, 199, 89, 0.22);
            }
            .app-source {
                border: 2px solid rgba(0, 0, 0, 0.08);
                border-radius: 20px;
                background-color: rgba(255, 255, 255, 0.85);
            }
            .app-source:hover {
                background-color: #ffffff;
                border: 2px solid rgba(0, 122, 255, 0.4);
            }
            .drag-hint {
                color: #000000;
                font-size: 13.5px;
                font-weight: 600;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.tmp_dir = tempfile.mkdtemp(prefix="nebula_deb_")
        self.deb_path = None
        self.pkg_name = "Application"
        self.pkg_display_name = "Application"
        self.pkg_version = "1.0"
        self.extracted_icon_path = None
        self.is_installing = False

        if deb_path:
            self.set_deb_path(deb_path)

        self.init_ui()

    def set_deb_path(self, deb_path):
        if str(deb_path).startswith("file://"):
            deb_path = urllib.parse.unquote(str(deb_path)[7:])
        self.deb_path = Path(deb_path).resolve()
        self.read_deb_info()

    def read_deb_info(self):
        if not self.deb_path or not self.deb_path.exists():
            return

        # 1. Read package control info
        info = {}
        try:
            out = subprocess.check_output(
                ["dpkg-deb", "-I", str(self.deb_path)],
                stderr=subprocess.DEVNULL
            ).decode(errors="replace")
            for line in out.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()
        except Exception:
            pass

        self.pkg_name = info.get("Package", self.deb_path.stem)
        self.pkg_version = info.get("Version", "1.0")
        self.pkg_display_name = self.pkg_name

        # 2. Try to extract .desktop and icon directly from .deb
        try:
            listing = subprocess.check_output(
                ["dpkg-deb", "-c", str(self.deb_path)],
                stderr=subprocess.DEVNULL
            ).decode(errors="replace")

            desktop_file = None
            icon_file = None
            icon_candidates = []

            for line in listing.splitlines():
                parts = line.split()
                if len(parts) < 6:
                    continue
                path_in_deb = parts[-1].lstrip(".")
                if path_in_deb.endswith(".desktop") and "applications" in path_in_deb:
                    if not desktop_file:
                        desktop_file = path_in_deb.lstrip("/")
                if any(path_in_deb.endswith(ext) for ext in [".svg", ".png"]):
                    if "icons" in path_in_deb or "pixmaps" in path_in_deb:
                        icon_candidates.append(path_in_deb.lstrip("/"))

            # Extract desktop file to get real Display Name & Icon name
            icon_name_from_desktop = None
            if desktop_file:
                subprocess.run(
                    f"dpkg-deb --fsys-tarfile '{self.deb_path}' | tar -xf - -C '{self.tmp_dir}' '{desktop_file}' 2>/dev/null || true",
                    shell=True
                )
                dt_path = Path(self.tmp_dir) / desktop_file
                if dt_path.exists():
                    try:
                        with open(dt_path, "r", encoding="utf-8", errors="ignore") as f:
                            for dline in f:
                                if dline.startswith("Name=") and self.pkg_display_name == self.pkg_name:
                                    self.pkg_display_name = dline.split("=", 1)[1].strip()
                                elif dline.startswith("Icon="):
                                    icon_name_from_desktop = dline.split("=", 1)[1].strip()
                    except Exception:
                        pass

            # Pick best icon from package
            best_icon = None
            if icon_name_from_desktop:
                for c in icon_candidates:
                    if icon_name_from_desktop in c:
                        best_icon = c
                        break
            if not best_icon and icon_candidates:
                # Prefer svg or high-res png
                svgs = [c for c in icon_candidates if c.endswith(".svg")]
                if svgs:
                    best_icon = svgs[0]
                else:
                    best_icon = icon_candidates[-1]

            if best_icon:
                subprocess.run(
                    f"dpkg-deb --fsys-tarfile '{self.deb_path}' | tar -xf - -C '{self.tmp_dir}' '{best_icon}' 2>/dev/null || true",
                    shell=True
                )
                cand_file = Path(self.tmp_dir) / best_icon
                if cand_file.exists() and cand_file.stat().st_size > 0:
                    self.extracted_icon_path = str(cand_file)

        except Exception as e:
            print(f"[DEBUG] Error extracting deb metadata: {e}")

    def load_app_icon(self):
        if self.extracted_icon_path and os.path.exists(self.extracted_icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.extracted_icon_path, 80, 80, True)
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                pass

        # Try theme lookup
        theme = Gtk.IconTheme.get_default()
        candidates = [self.pkg_name, f"org.gnome.{self.pkg_name.capitalize()}", "package-x-generic", "application-x-executable"]
        for c in candidates:
            if theme.has_icon(c):
                img = Gtk.Image.new_from_icon_name(c, Gtk.IconSize.DIALOG)
                img.set_pixel_size(80)
                return img

        # Fallback
        img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
        img.set_pixel_size(80)
        return img

    def init_ui(self):
        # Header Bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title(f"Install {self.pkg_display_name}")
        header.set_subtitle("Drag application into Applications folder")
        self.set_titlebar(header)

        # Main Vertical Container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_border_width(24)
        self.add(main_box)

        # Instruction label
        lang = os.environ.get("LANG", "en_US.UTF-8").lower()
        if "it" in lang:
            hint_text = f"Trascina <b>{self.pkg_display_name}</b> nella cartella <b>Applicazioni</b> per installarlo"
            self.folder_title = "Applicazioni"
        else:
            hint_text = f"Drag <b>{self.pkg_display_name}</b> to <b>Applications</b> to install it"
            self.folder_title = "Applications"

        self.lbl_hint = Gtk.Label()
        self.lbl_hint.set_markup(f"<span size='medium'>{hint_text}</span>")
        self.lbl_hint.get_style_context().add_class("drag-hint")
        main_box.pack_start(self.lbl_hint, False, False, 8)

        # Drag and Drop Canvas Box
        dnd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=36)
        dnd_box.set_halign(Gtk.Align.CENTER)
        dnd_box.set_valign(Gtk.Align.CENTER)
        main_box.pack_start(dnd_box, True, True, 12)

        # 1. Source App Icon Widget
        self.app_event_box = Gtk.EventBox()
        self.app_event_box.get_style_context().add_class("app-source")
        app_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        app_inner.set_border_width(20)
        app_inner.set_size_request(150, 160)

        self.app_icon = self.load_app_icon()
        app_inner.pack_start(self.app_icon, False, False, 0)

        app_title = Gtk.Label()
        app_title.set_markup(f"<span weight='bold' size='large'>{self.pkg_display_name}</span>")
        app_title.set_ellipsize(3)
        app_title.set_max_width_chars(14)
        app_inner.pack_start(app_title, False, False, 0)

        self.app_event_box.add(app_inner)
        dnd_box.pack_start(self.app_event_box, False, False, 0)

        # Configure App as DND Source
        targets = [Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 100)]
        self.app_event_box.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            targets,
            Gdk.DragAction.COPY
        )
        self.app_event_box.connect("drag-data-get", self.on_drag_data_get)
        self.app_event_box.connect("drag-begin", self.on_drag_begin)

        # 2. Middle Arrow Graphic
        arrow_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        arrow_box.set_valign(Gtk.Align.CENTER)
        arrow_lbl = Gtk.Label()
        arrow_lbl.set_markup("<span size='32000' color='#1c1c1e'>➔</span>")
        arrow_box.pack_start(arrow_lbl, False, False, 0)
        dnd_box.pack_start(arrow_box, False, False, 0)

        # 3. Destination Applications Folder Widget
        self.dest_event_box = Gtk.EventBox()
        self.dest_event_box.get_style_context().add_class("drop-target")
        dest_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        dest_inner.set_border_width(20)
        dest_inner.set_size_request(150, 160)

        # Look for folder icon in theme or direct fallback
        folder_icon = None
        theme = Gtk.IconTheme.get_default()
        for c in ["folder", "folder-blue", "inode-directory", "system-file-manager"]:
            if theme.has_icon(c):
                folder_icon = Gtk.Image.new_from_icon_name(c, Gtk.IconSize.DIALOG)
                folder_icon.set_pixel_size(80)
                break
        if not folder_icon:
            # Check /usr/share/icons/Nebula/scalable/places/folder.svg
            for p in ["/usr/share/icons/Nebula/scalable/places/folder.svg", "/usr/share/icons/Hatter/scalable/places/folder.svg"]:
                if os.path.exists(p):
                    try:
                        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(p, 80, 80, True)
                        folder_icon = Gtk.Image.new_from_pixbuf(pb)
                        break
                    except Exception:
                        pass
        if not folder_icon:
            folder_icon = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.DIALOG)
            folder_icon.set_pixel_size(80)

        dest_inner.pack_start(folder_icon, False, False, 0)

        folder_title_lbl = Gtk.Label()
        folder_title_lbl.set_markup(f"<span weight='bold' size='large'>{self.folder_title}</span>")
        dest_inner.pack_start(folder_title_lbl, False, False, 0)

        self.dest_event_box.add(dest_inner)
        dnd_box.pack_start(self.dest_event_box, False, False, 0)

        # Configure Destination as DND Target
        self.dest_event_box.drag_dest_set(
            Gtk.DestDefaults.ALL,
            targets,
            Gdk.DragAction.COPY
        )
        self.dest_event_box.connect("drag-motion", self.on_drag_motion)
        self.dest_event_box.connect("drag-leave", self.on_drag_leave)
        self.dest_event_box.connect("drag-data-received", self.on_drag_data_received)

        # Bottom Progress / Status Area
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.status_box.set_no_show_all(True)
        main_box.pack_end(self.status_box, False, False, 0)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_pulse_step(0.1)
        self.status_box.pack_start(self.progress_bar, False, False, 0)

        self.lbl_status = Gtk.Label()
        self.lbl_status.set_markup("<span size='small' color='#a6adc8'>Installing...</span>")
        self.status_box.pack_start(self.lbl_status, False, False, 0)

    def on_drag_begin(self, widget, context):
        Gtk.drag_set_icon_name(context, "package-x-generic", 0, 0)

    def on_drag_data_get(self, widget, context, data, info, time):
        data.set_text(str(self.deb_path), -1)

    def on_drag_motion(self, widget, context, x, y, time):
        widget.get_style_context().remove_class("drop-target")
        widget.get_style_context().add_class("drop-target-hover")
        Gdk.drag_status(context, Gdk.DragAction.COPY, time)
        return True

    def on_drag_leave(self, widget, context, time):
        widget.get_style_context().remove_class("drop-target-hover")
        widget.get_style_context().add_class("drop-target")

    def on_drag_data_received(self, widget, context, x, y, data, info, time):
        widget.get_style_context().remove_class("drop-target-hover")
        widget.get_style_context().add_class("drop-target")
        context.finish(True, False, time)

        if not self.is_installing:
            self.start_installation()

    def start_installation(self):
        self.is_installing = True
        self.app_event_box.set_sensitive(False)
        self.dest_event_box.set_sensitive(False)
        self.lbl_hint.set_markup(f"<span size='medium' weight='bold' color='#7aa2f7'>Installing {self.pkg_display_name}...</span>")
        self.status_box.show_all()
        GLib.timeout_add(100, self.pulse_progress)

        threading.Thread(target=self.run_install_worker, daemon=True).start()

    def pulse_progress(self):
        if not self.is_installing:
            return False
        self.progress_bar.pulse()
        return True

    def run_install_worker(self):
        deb_file = str(Path(self.deb_path).resolve())
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        env["NEEDRESTART_MODE"] = "a"

        # Determine best privilege escalation
        if os.geteuid() == 0:
            cmd = ["apt-get", "install", "-y", "--allow-downgrades", deb_file]
        else:
            # Check if passwordless sudo works (e.g. live session or sudoer)
            sudo_check = subprocess.run(["sudo", "-n", "true"], capture_output=True)
            if sudo_check.returncode == 0:
                cmd = ["sudo", "-n", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "--allow-downgrades", deb_file]
            else:
                cmd = ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "--allow-downgrades", deb_file]

        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=300
            )

            if res.returncode == 0:
                self.sync_app_to_applications()
                GLib.idle_add(self.on_install_success)
            else:
                err = res.stderr.strip() or res.stdout.strip() or f"Process exited with code {res.returncode}"
                GLib.idle_add(self.on_install_failed, err)
        except subprocess.TimeoutExpired:
            GLib.idle_add(self.on_install_failed, "Installation timed out after 5 minutes.")
        except Exception as e:
            GLib.idle_add(self.on_install_failed, str(e))

    def sync_app_to_applications(self):
        try:
            apps_dir = get_apps_folder()
            out = subprocess.check_output(["dpkg", "-L", self.pkg_name], stderr=subprocess.DEVNULL, text=True)
            for line in out.splitlines():
                if line.endswith(".desktop") and "/applications/" in line:
                    desktop_src = Path(line)
                    if desktop_src.exists():
                        target_desktop = apps_dir / desktop_src.name
                        shutil.copy2(desktop_src, target_desktop)
                        os.chmod(target_desktop, 0o755)
                        subprocess.run(["gio", "set", "-t", "string", str(target_desktop), "metadata::trusted", "true"], check=False)
                        # Immediately wrap icon into official squircle
                        try:
                            subprocess.run(["python3", "/usr/lib/nebulaos/nebula-icon-wrapper.py", str(target_desktop)], timeout=5, check=False)
                        except Exception:
                            pass
            subprocess.run(["update-desktop-database", str(apps_dir)], check=False)
        except Exception as e:
            print(f"[INSTALL SYNC ERROR] {e}")


    def on_install_success(self):
        self.is_installing = False
        self.lbl_hint.set_markup(f"<span size='large' weight='bold' color='#9ece6a'>✔ {self.pkg_display_name} installed successfully!</span>")
        self.lbl_status.set_markup("<span color='#9ece6a'>Available in your Applications folder</span>")
        self.progress_bar.set_fraction(1.0)

        try:
            subprocess.run([
                "notify-send", "-i", "package-x-generic", "-a", "Install Software",
                "Installation Complete", f"{self.pkg_display_name} is now installed and ready in Applications."
            ], check=False)
        except Exception:
            pass

        GLib.timeout_add(1600, Gtk.main_quit)

    def on_install_failed(self, error_msg):
        self.is_installing = False
        self.status_box.hide()
        self.app_event_box.set_sensitive(True)
        self.dest_event_box.set_sensitive(True)
        self.lbl_hint.set_markup("<span size='medium' color='#f7768e'>Installation failed</span>")

        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Package Installation Failed"
        )
        dialog.format_secondary_text(f"Could not install {self.deb_path.name}:\n\n{error_msg[:300]}")
        dialog.run()
        dialog.destroy()

def main():
    _wizard_done = os.path.exists(os.path.expanduser("~/.config/nebula/postinstall-wizard-completed")) or os.path.exists("/run/nebula-desktop-unlocked")
    if not _wizard_done:
        sys.exit(0)

    deb_path = None
    if len(sys.argv) >= 2:
        deb_path = sys.argv[1]

    if not deb_path or not os.path.exists(deb_path.replace("file://", "")):
        # Show file chooser dialog if no file specified
        dialog = Gtk.FileChooserDialog(
            title="Choose a .deb package to install",
            parent=None,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        filt = Gtk.FileFilter()
        filt.set_name("Debian Packages (*.deb)")
        filt.add_pattern("*.deb")
        filt.add_mime_type("application/vnd.debian.binary-package")
        dialog.add_filter(filt)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            deb_path = dialog.get_filename()
            dialog.destroy()
        else:
            dialog.destroy()
            sys.exit(0)

    win = DmgInstallerWindow(deb_path)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
