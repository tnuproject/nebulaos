"""
Nebula Recovery — Erase / Format Disk Sheet / Dialog
Allows formatting partitions or wiping entire drives in Nebula Recovery.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib
import threading
from backend.disk_ops import list_storage_devices, format_partition, wipe_and_create_gpt


class EraseDialog(Gtk.Window):
    def __init__(self, parent_window):
        super().__init__(transient_for=parent_window, modal=True)
        self.set_title("Erase / Format Disk")
        self.set_default_size(540, 560)
        self.set_resizable(False)

        self.add_css_class("recovery-sheet")
        self._devices = []
        self._target_items = []  # list of (display_name, path, is_disk)

        self._build_ui()
        self._load_devices()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_start(24)
        root.set_margin_end(24)
        root.set_margin_top(20)
        root.set_margin_bottom(20)
        self.set_child(root)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root.append(header)

        title = Gtk.Label(label="Erase Disk & System")
        title.add_css_class("dialog-title")
        title.set_halign(Gtk.Align.START)
        header.append(title)

        sub = Gtk.Label(label="Erasing a volume or disk permanently destroys all data on it.")
        sub.add_css_class("dialog-subtitle")
        sub.set_halign(Gtk.Align.START)
        header.append(sub)

        # Form fields
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        form.set_margin_top(8)
        root.append(form)

        # 1. Target volume/disk selector
        target_lbl = Gtk.Label(label="Target Volume or Disk:")
        target_lbl.set_halign(Gtk.Align.START)
        target_lbl.add_css_class("dialog-subtitle")
        form.append(target_lbl)

        self._target_combo = Gtk.DropDown()
        self._target_combo.connect("notify::selected", self._on_target_selected)
        form.append(self._target_combo)

        # 2. Volume Name
        name_lbl = Gtk.Label(label="Volume Name:")
        name_lbl.set_halign(Gtk.Align.START)
        name_lbl.add_css_class("dialog-subtitle")
        form.append(name_lbl)

        self._name_entry = Gtk.Entry()
        try:
            self._name_entry.set_property("placeholder-text", "Untitled")
        except Exception:
            pass
        self._name_entry.set_text("NebulaOS")
        form.append(self._name_entry)

        # 3. Format / Filesystem
        fs_lbl = Gtk.Label(label="Format (Filesystem):")
        fs_lbl.set_halign(Gtk.Align.START)
        fs_lbl.add_css_class("dialog-subtitle")
        form.append(fs_lbl)

        self._fs_types = [
            ("ext4", "Linux Native (ext4)"),
            ("btrfs", "Modern Copy-on-Write (btrfs)"),
            ("fat32", "Universal / EFI (FAT32)"),
            ("exfat", "Removable Storage (exFAT)"),
        ]
        fs_names = [display for _, display in self._fs_types]
        fs_model = Gtk.StringList.new(fs_names)
        self._fs_combo = Gtk.DropDown.new(fs_model, None)
        self._fs_combo.set_selected(0)
        form.append(self._fs_combo)

        # Spinner & progress label
        self._progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._progress_box.set_visible(False)
        self._spinner = Gtk.Spinner()
        self._spinner.start()
        self._progress_box.append(self._spinner)

        self._progress_lbl = Gtk.Label(label="Erasing and formatting…")
        self._progress_lbl.set_halign(Gtk.Align.START)
        self._progress_box.append(self._progress_lbl)
        root.append(self._progress_box)

        # Status result
        self._result_lbl = Gtk.Label()
        self._result_lbl.set_halign(Gtk.Align.START)
        self._result_lbl.set_wrap(True)
        self._result_lbl.set_visible(False)
        root.append(self._result_lbl)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        root.append(spacer)

        # Footer actions
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(footer)

        refresh_btn = Gtk.Button(label="Refresh Drives")
        refresh_btn.add_css_class("recovery-secondary-btn")
        refresh_btn.connect("clicked", lambda _: self._load_devices())
        footer.append(refresh_btn)

        f_spacer = Gtk.Box()
        f_spacer.set_hexpand(True)
        footer.append(f_spacer)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("recovery-secondary-btn")
        cancel_btn.connect("clicked", lambda _: self.close())
        footer.append(cancel_btn)

        self._erase_btn = Gtk.Button(label="Erase…")
        self._erase_btn.add_css_class("recovery-danger-btn")
        self._erase_btn.set_sensitive(False)
        self._erase_btn.connect("clicked", self._on_erase_clicked)
        footer.append(self._erase_btn)

    def _load_devices(self):
        self._devices = list_storage_devices()
        self._target_items = []
        labels = []

        for dev in self._devices:
            # Whole disk option
            disk_label = f"Disk: {dev['path']} ({dev['model']}, {dev['size_str']})"
            self._target_items.append((disk_label, dev["path"], True))
            labels.append(disk_label)

            # Partition options
            for part in dev["partitions"]:
                part_desc = f"{part['path']} ({part['size_str']}, {part['fstype']}"
                if part['label']:
                    part_desc += f", '{part['label']}'"
                part_desc += ")"
                self._target_items.append((f"   ↳ {part_desc}", part["path"], False))
                labels.append(f"   ↳ {part_desc}")

        if labels:
            model = Gtk.StringList.new(labels)
            self._target_combo.set_model(model)
            self._target_combo.set_selected(0)
            self._erase_btn.set_sensitive(True)
        else:
            empty_model = Gtk.StringList.new(["No writable storage devices found"])
            self._target_combo.set_model(empty_model)
            self._erase_btn.set_sensitive(False)

    def _on_target_selected(self, *_):
        idx = self._target_combo.get_selected()
        self._erase_btn.set_sensitive(0 <= idx < len(self._target_items))

    def _on_erase_clicked(self, _btn):
        idx = self._target_combo.get_selected()
        if not (0 <= idx < len(self._target_items)):
            return

        display_name, target_path, is_disk = self._target_items[idx]
        vol_name = self._name_entry.get_text().strip() or "Untitled"
        fs_idx = self._fs_combo.get_selected()
        fs_code, fs_display = self._fs_types[fs_idx]

        # Confirm dialog
        confirm = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Erase \"{target_path}\"?",
        )
        confirm.format_secondary_text(
            f"Are you sure you want to erase {target_path} and format it as {fs_display}?\n\n"
            f"All existing data and partitions will be permanently destroyed. "
            f"This operation cannot be undone."
        )
        confirm.connect("response", lambda d, r: self._on_confirm_response(d, r, target_path, fs_code, vol_name, is_disk))
        confirm.present()

    def _on_confirm_response(self, dialog, response, target_path, fs_code, vol_name, is_disk):
        dialog.close()
        if response != Gtk.ResponseType.OK:
            return

        self._erase_btn.set_sensitive(False)
        self._progress_box.set_visible(True)
        self._result_lbl.set_visible(False)
        self._progress_lbl.set_label(f"Formatting {target_path} as {fs_code.upper()}…")

        threading.Thread(
            target=self._format_worker,
            args=(target_path, fs_code, vol_name, is_disk),
            daemon=True
        ).start()

    def _format_worker(self, target_path, fs_code, vol_name, is_disk):
        if is_disk:
            # Wiping full disk, then creating new partition table
            ok, msg = wipe_and_create_gpt(target_path)
            if not ok:
                GLib.idle_add(self._on_format_finished, False, msg)
                return

        # Format partition
        ok, msg = format_partition(target_path, fstype=fs_code, label=vol_name)
        GLib.idle_add(self._on_format_finished, ok, msg)

    def _on_format_finished(self, ok: bool, message: str):
        self._progress_box.set_visible(False)
        self._erase_btn.set_sensitive(True)
        self._result_lbl.set_visible(True)

        if ok:
            self._result_lbl.set_markup(f"<span foreground='#27c93f'>✓ {message}</span>")
            self._load_devices()
        else:
            self._result_lbl.set_markup(f"<span foreground='#ff5f56'>✕ Error: {message}</span>")
