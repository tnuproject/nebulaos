"""
Nebula Setup — Partition / Disk Selector Screen
Supports full disk erase and Dual Boot partition selection.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
import threading
from typing import Optional, List
from backend.state import get_state
from backend.disk import list_disks, DiskInfo, list_partitions, PartitionInfo, find_efi_partition
from backend.i18n import t, register_listener


class PartitionScreen(Gtk.Box):
    def __init__(self, on_next, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_next = on_next
        self._on_back = on_back

        self._disks: List[DiskInfo] = []
        self._selected_disk: Optional[DiskInfo] = None
        self._selected_part: Optional[PartitionInfo] = None
        self._install_mode: str = "erase"  # "erase" or "dualboot"
        self._efi_part_path: Optional[str] = None

        self._disk_rows: List[Gtk.Button] = []
        self._part_rows: List[Gtk.Button] = []

        self._build()

    def _build(self):
        self.add_css_class("setup-screen")

        # ── Header ────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.add_css_class("setup-header")
        self.append(header)

        self._title = Gtk.Label(label=t("disk_title"))
        self._title.add_css_class("setup-title")
        self._title.set_halign(Gtk.Align.START)
        header.append(self._title)

        self._sub = Gtk.Label(label=t("disk_sub"))
        self._sub.add_css_class("setup-subtitle")
        self._sub.set_halign(Gtk.Align.START)
        self._sub.set_wrap(True)
        header.append(self._sub)

        # ── Scrollable Body ───────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_margin_start(64)
        scroll.set_margin_end(64)
        scroll.set_margin_bottom(12)
        self.append(scroll)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content_box.set_margin_top(8)
        self._content_box.set_margin_bottom(8)
        scroll.set_child(self._content_box)

        # ── Section 1: Disks ──
        self._disk_section_lbl = Gtk.Label(label="1. Target Disk")
        self._disk_section_lbl.add_css_class("field-label")
        self._disk_section_lbl.set_halign(Gtk.Align.START)
        self._content_box.append(self._disk_section_lbl)

        self._disk_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._content_box.append(self._disk_list)

        self._spinner = Gtk.Spinner()
        self._spinner.add_css_class("nebula-spinner")
        self._spinner.set_halign(Gtk.Align.CENTER)
        self._spinner.start()
        self._disk_list.append(self._spinner)

        # ── Section 2: Installation Mode (Erase vs Dual Boot) ──
        self._mode_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._mode_section.set_visible(False)
        self._content_box.append(self._mode_section)

        self._mode_section_lbl = Gtk.Label(label="2. Installation Mode")
        self._mode_section_lbl.add_css_class("field-label")
        self._mode_section_lbl.set_halign(Gtk.Align.START)
        self._mode_section.append(self._mode_section_lbl)

        mode_cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mode_cards_box.set_homogeneous(True)
        self._mode_section.append(mode_cards_box)

        # Erase Card
        self._erase_card = Gtk.Button()
        self._erase_card.add_css_class("mode-card")
        self._erase_card.connect("clicked", lambda _: self._set_install_mode("erase"))
        mode_cards_box.append(self._erase_card)

        erase_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        erase_box.set_valign(Gtk.Align.CENTER)
        self._erase_card_title = Gtk.Label(label=t("mode_erase_title"))
        self._erase_card_title.add_css_class("disk-name")
        self._erase_card_title.set_halign(Gtk.Align.START)
        erase_box.append(self._erase_card_title)

        self._erase_card_desc = Gtk.Label(label=t("mode_erase_desc"))
        self._erase_card_desc.add_css_class("disk-info")
        self._erase_card_desc.set_halign(Gtk.Align.START)
        self._erase_card_desc.set_wrap(True)
        erase_box.append(self._erase_card_desc)
        self._erase_card.set_child(erase_box)

        # Dual Boot Card
        self._dualboot_card = Gtk.Button()
        self._dualboot_card.add_css_class("mode-card")
        self._dualboot_card.connect("clicked", lambda _: self._set_install_mode("dualboot"))
        mode_cards_box.append(self._dualboot_card)

        dual_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        dual_box.set_valign(Gtk.Align.CENTER)
        self._dual_card_title = Gtk.Label(label=t("mode_dualboot_title"))
        self._dual_card_title.add_css_class("disk-name")
        self._dual_card_title.set_halign(Gtk.Align.START)
        dual_box.append(self._dual_card_title)

        self._dual_card_desc = Gtk.Label(label=t("mode_dualboot_desc"))
        self._dual_card_desc.add_css_class("disk-info")
        self._dual_card_desc.set_halign(Gtk.Align.START)
        self._dual_card_desc.set_wrap(True)
        dual_box.append(self._dual_card_desc)
        self._dualboot_card.set_child(dual_box)

        # ── Section 3: Dual Boot Partition Selection ──
        self._part_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._part_section.set_visible(False)
        self._content_box.append(self._part_section)

        self._part_section_lbl = Gtk.Label(label=t("select_partition_title"))
        self._part_section_lbl.add_css_class("field-label")
        self._part_section_lbl.set_halign(Gtk.Align.START)
        self._part_section.append(self._part_section_lbl)

        self._efi_info_lbl = Gtk.Label()
        self._efi_info_lbl.add_css_class("disk-info")
        self._efi_info_lbl.set_halign(Gtk.Align.START)
        self._efi_info_lbl.set_wrap(True)
        self._part_section.append(self._efi_info_lbl)

        self._part_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._part_section.append(self._part_list)

        self._part_spinner = Gtk.Spinner()
        self._part_spinner.add_css_class("nebula-spinner")
        self._part_spinner.set_halign(Gtk.Align.CENTER)

        # ── Warning Label ─────────────────────────────────────────────────
        self._warning_lbl = Gtk.Label()
        self._warning_lbl.add_css_class("disk-warning")
        self._warning_lbl.set_visible(False)
        self._warning_lbl.set_halign(Gtk.Align.START)
        self._warning_lbl.set_margin_start(64)
        self._warning_lbl.set_margin_end(64)
        self.append(self._warning_lbl)

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

        self._next_btn = Gtk.Button(label=t("install_now"))
        self._next_btn.add_css_class("nebula-primary")
        self._next_btn.set_sensitive(False)
        self._next_btn.connect("clicked", self._on_install_clicked)
        footer.append(self._next_btn)

        register_listener(self._refresh_text)

    def _refresh_text(self):
        self._title.set_label(t("disk_title"))
        self._sub.set_label(t("disk_sub"))
        self._back_btn.set_label(t("back"))
        self._next_btn.set_label(t("install_now"))
        self._erase_card_title.set_label(t("mode_erase_title"))
        self._erase_card_desc.set_label(t("mode_erase_desc"))
        self._dual_card_title.set_label(t("mode_dualboot_title"))
        self._dual_card_desc.set_label(t("mode_dualboot_desc"))
        self._part_section_lbl.set_label(t("select_partition_title"))
        if self._disks:
            self._populate_disks(self._disks)

    def on_shown(self):
        self._selected_disk = None
        self._selected_part = None
        self._install_mode = "erase"
        self._next_btn.set_sensitive(False)
        self._warning_lbl.set_visible(False)
        self._mode_section.set_visible(False)
        self._part_section.set_visible(False)
        self._erase_card.add_css_class("selected")
        self._dualboot_card.remove_css_class("selected")
        threading.Thread(target=self._load_disks, daemon=True).start()

    def _load_disks(self):
        disks = list_disks()
        GLib.idle_add(self._populate_disks, disks)

    def _populate_disks(self, disks: List[DiskInfo]):
        if self._spinner.get_parent() == self._disk_list:
            self._disk_list.remove(self._spinner)

        for row in self._disk_rows:
            self._disk_list.remove(row)
        self._disk_rows.clear()

        self._disks = disks

        if not disks:
            no_disk = Gtk.Label(label=f"⚠ {t('no_disks')}")
            no_disk.set_justify(Gtk.Justification.CENTER)
            no_disk.set_halign(Gtk.Align.CENTER)
            no_disk.set_opacity(0.6)
            self._disk_list.append(no_disk)
            return

        for disk in disks:
            row = self._make_disk_row(disk)
            self._disk_list.append(row)
            self._disk_rows.append(row)

    def _make_disk_row(self, disk: DiskInfo) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class("disk-row")
        btn.connect("clicked", lambda _, d=disk: self._select_disk(d, btn))

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        name_lbl = Gtk.Label(label=disk.model)
        name_lbl.add_css_class("disk-name")
        name_lbl.set_halign(Gtk.Align.START)
        left.append(name_lbl)

        info_text = f"{disk.path} · {disk.size}"
        if disk.is_removable:
            info_text += f" · {t('removable')}"
        info_lbl = Gtk.Label(label=info_text)
        info_lbl.add_css_class("disk-info")
        info_lbl.set_halign(Gtk.Align.START)
        left.append(info_lbl)

        if disk.has_os:
            warn = Gtk.Label(label=f"⚠ {t('has_os_warning')}")
            warn.add_css_class("disk-warning")
            warn.set_halign(Gtk.Align.START)
            left.append(warn)

        outer.append(left)

        size_lbl = Gtk.Label(label=disk.size)
        size_lbl.set_halign(Gtk.Align.END)
        size_lbl.set_opacity(0.5)
        outer.append(size_lbl)

        btn.set_child(outer)
        return btn

    def _select_disk(self, disk: DiskInfo, btn: Gtk.Button):
        for row in self._disk_rows:
            row.remove_css_class("selected")
        btn.add_css_class("selected")
        self._selected_disk = disk

        self._mode_section.set_visible(True)

        if disk.has_os:
            self._warning_lbl.set_label(
                f"⚠ {t('has_os_warning')}: {disk.model} ({disk.size})"
            )
            self._warning_lbl.set_visible(True)
        else:
            self._warning_lbl.set_visible(False)

        # If already on dualboot, reload partitions for newly selected disk
        if self._install_mode == "dualboot":
            self._load_partitions()
        else:
            self._next_btn.set_sensitive(True)

    def _set_install_mode(self, mode: str):
        self._install_mode = mode
        if mode == "erase":
            self._erase_card.add_css_class("selected")
            self._dualboot_card.remove_css_class("selected")
            self._part_section.set_visible(False)
            self._next_btn.set_sensitive(self._selected_disk is not None)
        else:
            self._dualboot_card.add_css_class("selected")
            self._erase_card.remove_css_class("selected")
            self._part_section.set_visible(True)
            self._next_btn.set_sensitive(self._selected_part is not None)
            if self._selected_disk:
                self._load_partitions()

    def _load_partitions(self):
        if not self._selected_disk:
            return

        self._selected_part = None
        self._next_btn.set_sensitive(False)

        for row in self._part_rows:
            self._part_list.remove(row)
        self._part_rows.clear()

        if self._part_spinner.get_parent() != self._part_list:
            self._part_list.append(self._part_spinner)
        self._part_spinner.start()

        threading.Thread(target=self._query_partitions, daemon=True).start()

    def _query_partitions(self):
        disk_path = self._selected_disk.path
        parts = list_partitions(disk_path)
        efi = find_efi_partition(disk_path)
        GLib.idle_add(self._populate_partitions, parts, efi)

    def _populate_partitions(self, parts: List[PartitionInfo], efi: Optional[str]):
        if self._part_spinner.get_parent() == self._part_list:
            self._part_list.remove(self._part_spinner)

        for row in self._part_rows:
            self._part_list.remove(row)
        self._part_rows.clear()

        self._efi_part_path = efi
        if efi:
            self._efi_info_lbl.set_label(f"✓ {t('efi_detected').format(part=efi)}")
            self._efi_info_lbl.remove_css_class("disk-warning")
        else:
            self._efi_info_lbl.set_label(f"⚠ {t('no_efi_warning')}")
            self._efi_info_lbl.add_css_class("disk-warning")

        if not parts:
            no_part = Gtk.Label(label=f"⚠ {t('no_partitions_found')}")
            no_part.set_opacity(0.7)
            no_part.set_halign(Gtk.Align.START)
            self._part_list.append(no_part)
            return

        for p in parts:
            row = self._make_partition_row(p)
            self._part_list.append(row)
            self._part_rows.append(row)

    def _make_partition_row(self, part: PartitionInfo) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class("part-row")

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Left: Partition details
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_lbl = Gtk.Label(label=f"{part.name} ({part.path})")
        name_lbl.add_css_class("disk-name")
        name_lbl.set_halign(Gtk.Align.START)
        title_box.append(name_lbl)

        if part.is_efi:
            badge = Gtk.Label(label="EFI / ESP")
            badge.add_css_class("part-badge")
            badge.add_css_class("part-badge-efi")
            title_box.append(badge)
        elif part.os_name:
            badge = Gtk.Label(label=part.os_name)
            badge.add_css_class("part-badge")
            badge.add_css_class("part-badge-os")
            title_box.append(badge)

        left.append(title_box)

        desc = f"{part.fstype.upper()}"
        if part.label:
            desc += f" · \"{part.label}\""
        if part.is_efi:
            desc += " · (System boot partition - Preserved)"
        elif not part.is_suitable:
            desc += " · (Too small, minimum 10 GB required)"

        info_lbl = Gtk.Label(label=desc)
        info_lbl.add_css_class("disk-info")
        info_lbl.set_halign(Gtk.Align.START)
        left.append(info_lbl)
        outer.append(left)

        # Right: Size
        size_lbl = Gtk.Label(label=part.size)
        size_lbl.set_halign(Gtk.Align.END)
        size_lbl.set_opacity(0.6)
        outer.append(size_lbl)

        btn.set_child(outer)

        if part.is_suitable:
            btn.connect("clicked", lambda _, p=part: self._select_partition(p, btn))
        else:
            btn.set_sensitive(False)

        return btn

    def _select_partition(self, part: PartitionInfo, btn: Gtk.Button):
        for row in self._part_rows:
            row.remove_css_class("selected")
        btn.add_css_class("selected")
        self._selected_part = part
        self._next_btn.set_sensitive(True)

    def _on_install_clicked(self, _btn):
        if not self._selected_disk:
            return

        root_win = self.get_root()

        if self._install_mode == "dualboot":
            if not self._selected_part:
                return
            body = t("dualboot_confirm_body").format(
                partition=self._selected_part.path,
                size=self._selected_part.size
            )
            dialog = Adw.MessageDialog(
                transient_for=root_win,
                heading=t("dualboot_confirm_title"),
                body=body
            )
            dialog.add_response("cancel", t("cancel") if t("cancel") != "cancel" else "Cancel")
            dialog.add_response("install", t("install_now") if t("install_now") != "install_now" else "Install Now")
            dialog.set_response_appearance("install", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.connect("response", self._on_confirm_response)
            dialog.present()
        else:
            body = t("erase_confirm_body").format(
                model=self._selected_disk.model,
                size=self._selected_disk.size
            )
            dialog = Adw.MessageDialog(
                transient_for=root_win,
                heading=t("erase_confirm_title"),
                body=body
            )
            dialog.add_response("cancel", t("cancel") if t("cancel") != "cancel" else "Cancel")
            dialog.add_response("install", t("install_now") if t("install_now") != "install_now" else "Install Now")
            dialog.set_response_appearance("install", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.connect("response", self._on_confirm_response)
            dialog.present()

    def _on_confirm_response(self, dialog, response_id):
        if response_id == "install" and self._selected_disk:
            state = get_state()
            state.target_disk = self._selected_disk.path
            state.target_disk_model = self._selected_disk.model
            state.target_disk_size = self._selected_disk.size
            state.install_mode = self._install_mode

            if self._install_mode == "dualboot" and self._selected_part:
                state.target_partition = self._selected_part.path
                state.target_partition_size = self._selected_part.size
                state.efi_partition = self._efi_part_path
            else:
                state.target_partition = None
                state.efi_partition = None

            self._on_next()
