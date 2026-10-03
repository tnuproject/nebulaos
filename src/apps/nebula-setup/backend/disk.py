"""
Nebula Setup — Disk Detection & Partitioning Backend
Handles lsblk-based disk listing, parted partitioning, mkfs and mounting.
"""

import json
import os
import re
import subprocess
import time
from typing import List, Optional

from backend.state import get_state


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

class DiskInfo:
    def __init__(self, path: str, name: str, size: str, model: str,
                 size_bytes: int, is_removable: bool = False, has_os: bool = False):
        self.path = path          # e.g. /dev/sda
        self.name = name          # e.g. sda
        self.size = size          # e.g. "256G"
        self.model = model        # e.g. "Samsung SSD 860"
        self.size_bytes = size_bytes
        self.is_removable = is_removable
        self.has_os = has_os

    def __repr__(self):
        return f"DiskInfo({self.path}, {self.size}, {self.model!r})"


class PartitionInfo:
    def __init__(self, path: str, name: str, size: str, size_bytes: int,
                 fstype: str = "", label: str = "", is_efi: bool = False,
                 is_suitable: bool = True, os_name: str = ""):
        self.path = path              # e.g. /dev/sda3
        self.name = name              # e.g. sda3
        self.size = size              # e.g. "120.0 GB"
        self.size_bytes = size_bytes
        self.fstype = fstype          # e.g. "ext4", "ntfs", "vfat"
        self.label = label            # e.g. "Windows", "Data"
        self.is_efi = is_efi          # True if ESP
        self.is_suitable = is_suitable # True if >= 10GB and not live/efi
        self.os_name = os_name        # e.g. "Windows", "Linux"

    def __repr__(self):
        return f"PartitionInfo({self.path}, {self.size}, {self.fstype}, is_efi={self.is_efi})"


# ──────────────────────────────────────────────────────────────────────────────
# Disk listing
# ──────────────────────────────────────────────────────────────────────────────

def list_disks() -> List[DiskInfo]:
    """Return a list of physical disks excluding the live media."""
    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-b", "-o", "NAME,SIZE,MODEL,TYPE,RM,MOUNTPOINTS"],
            text=True
        )
        data = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return []

    disks = []
    live_device = _detect_live_device()

    for block in data.get("blockdevices", []):
        if block.get("type") != "disk":
            continue

        name = block.get("name", "")
        path = f"/dev/{name}"

        # Skip the live USB/CD itself
        if name == live_device or path == live_device:
            continue

        size_bytes = int(block.get("size", 0) or 0)
        if size_bytes < 8 * 1024 ** 3:   # Skip disks < 8GB
            continue

        size_str = _human_size(size_bytes)
        model = (block.get("model") or "").strip() or name.upper()
        is_removable = bool(int(block.get("rm", 0) or 0))
        has_os = _disk_has_os(block)

        disks.append(DiskInfo(
            path=path,
            name=name,
            size=size_str,
            model=model,
            size_bytes=size_bytes,
            is_removable=is_removable,
            has_os=has_os,
        ))

    return sorted(disks, key=lambda d: d.size_bytes, reverse=True)


def _detect_live_device() -> str:
    """Detect which device is the live boot media."""
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE", "/cdrom"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        # Return base device: /dev/sdb1 -> sdb
        return re.sub(r'\d+$', '', os.path.basename(out))
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE", "/run/live/medium"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        return re.sub(r'\d+$', '', os.path.basename(out))
    except Exception:
        return ""


def _disk_has_os(block: dict) -> bool:
    """Heuristic: check if any child partition has a mounted filesystem (non-live)."""
    for child in block.get("children", []):
        mounts = child.get("mountpoints", [])
        if mounts and any(m and not m.startswith("/cdrom") and not m.startswith("/run/live") for m in mounts):
            return True
    return False


def _human_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def is_efi_partition(part_path: str, fstype: str, label: str) -> bool:
    """Check if partition is an EFI System Partition (ESP)."""
    f_lower = (fstype or "").lower()
    l_upper = (label or "").upper()
    if f_lower in ["vfat", "fat32", "fat16"]:
        if l_upper in ["EFI", "ESP", "SYSTEM", "BOOT"]:
            return True
        try:
            out = subprocess.check_output(
                ["blkid", "-o", "value", "-s", "PARTLABEL", part_path],
                text=True, stderr=subprocess.DEVNULL
            ).strip().lower()
            if "efi" in out or "esp" in out:
                return True
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["udevadm", "info", "--query=property", "--name", part_path],
                text=True, stderr=subprocess.DEVNULL
            )
            if "ID_PART_ENTRY_SCHEME=gpt" in out and "c12a7328-f81f-11d2-ba4b-00a0c93ec93b" in out.lower():
                return True
        except Exception:
            pass
    return False


def list_partitions(device: str) -> List[PartitionInfo]:
    """Return all partitions of device suitable for inspection or dual boot."""
    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS", device],
            text=True
        )
        data = json.loads(out)
    except Exception:
        return []

    partitions = []

    def process_block(block):
        btype = block.get("type", "")
        bname = block.get("name", "")
        bpath = block.get("path") or f"/dev/{bname}"

        if btype == "part":
            size_bytes = int(block.get("size", 0) or 0)
            fstype = block.get("fstype") or ""
            label = block.get("label") or ""
            mounts = block.get("mountpoints") or []

            # Skip live media mounts
            if any(m and (m.startswith("/cdrom") or m.startswith("/run/live")) for m in mounts):
                return

            is_efi = is_efi_partition(bpath, fstype, label)
            os_name = ""
            if fstype.lower() in ["ntfs"]:
                os_name = "Windows"
            elif label and "windows" in label.lower():
                os_name = "Windows"
            elif fstype.lower() in ["ext4", "btrfs", "xfs"]:
                os_name = "Linux"

            # Suitable for NebulaOS if >= 10GB and not an EFI system partition
            is_suitable = (size_bytes >= 10 * 1024**3) and not is_efi

            partitions.append(PartitionInfo(
                path=bpath,
                name=bname,
                size=_human_size(size_bytes),
                size_bytes=size_bytes,
                fstype=fstype or "unformatted",
                label=label,
                is_efi=is_efi,
                is_suitable=is_suitable,
                os_name=os_name
            ))

        for child in block.get("children", []):
            process_block(child)

    for dev in data.get("blockdevices", []):
        for child in dev.get("children", []):
            process_block(child)

    return sorted(partitions, key=lambda p: p.name)


def find_efi_partition(disk_device: Optional[str] = None) -> Optional[str]:
    """Find an existing EFI partition on disk_device, or fallback to any disk."""
    if disk_device:
        for p in list_partitions(disk_device):
            if p.is_efi:
                return p.path

    # Search all block devices for an EFI partition
    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,FSTYPE,LABEL"],
            text=True
        )
        data = json.loads(out)
        for dev in data.get("blockdevices", []):
            for child in dev.get("children", []):
                p_path = child.get("path") or f"/dev/{child.get('name')}"
                p_fstype = child.get("fstype") or ""
                p_label = child.get("label") or ""
                if is_efi_partition(p_path, p_fstype, p_label):
                    return p_path
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# EFI detection
# ──────────────────────────────────────────────────────────────────────────────

def is_efi_system() -> bool:
    """Return True if the current system booted with UEFI."""
    return os.path.isdir("/sys/firmware/efi")


# ──────────────────────────────────────────────────────────────────────────────
# Partitioning
# ──────────────────────────────────────────────────────────────────────────────

class PartitionError(RuntimeError):
    pass


def partition_and_format(device: str, progress_cb=None,
                         install_mode: str = "erase",
                         target_partition: Optional[str] = None,
                         efi_partition: Optional[str] = None) -> dict:
    """
    Prepare disk or partition for installation:
      - If install_mode == "dualboot":
          Format only target_partition as ext4. Preserve all other partitions
          and locate existing EFI System Partition (ESP) without wiping.
      - If install_mode == "erase":
          Wipe device and create new GPT/EFI or MBR scheme with fresh root.

    Returns dict with keys: efi_part, root_part
    Raises PartitionError on failure.
    """

    def run(cmd, **kwargs):
        return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)

    def step(msg):
        if progress_cb:
            progress_cb(msg)

    use_efi = is_efi_system()

    # ── DUAL BOOT MODE ────────────────────────────────────────────────────────
    if install_mode == "dualboot":
        if not target_partition:
            raise PartitionError("No destination partition selected for dual boot.")

        step(f"Formatting partition {target_partition} (ext4) for NebulaOS…")
        run(["mkfs.ext4", "-L", "NebulaOS", "-F", target_partition])

        efi_part = None
        if use_efi:
            efi_part = efi_partition or find_efi_partition(device)
            if not efi_part:
                step("Searching for existing EFI system partition…")
                efi_part = find_efi_partition(None)

        time.sleep(1)
        subprocess.run(["partprobe", device], capture_output=True)
        time.sleep(1)

        return {"efi_part": efi_part, "root_part": target_partition}

    # ── ERASE ENTIRE DISK MODE ────────────────────────────────────────────────
    step(f"Wiping {device}…")
    run(["wipefs", "-a", device])
    run(["sgdisk", "-Z", device])   # zap all
    time.sleep(0.5)

    if use_efi:
        step("Creating GPT partition table…")
        run(["parted", "-s", device, "mklabel", "gpt"])

        step("Creating EFI partition (512 MiB)…")
        run(["parted", "-s", device, "mkpart", "EFI", "fat32", "1MiB", "513MiB"])
        run(["parted", "-s", device, "set", "1", "esp", "on"])

        step("Creating root partition…")
        run(["parted", "-s", device, "mkpart", "root", "ext4", "513MiB", "100%"])

        # Determine partition names (nvme0n1 → nvme0n1p1, sda → sda1)
        if re.search(r'nvme|mmcblk', device):
            efi_part = f"{device}p1"
            root_part = f"{device}p2"
        else:
            efi_part = f"{device}1"
            root_part = f"{device}2"

        step("Formatting EFI partition…")
        run(["mkfs.fat", "-F32", "-n", "EFI", efi_part])

        step("Formatting root partition (ext4)…")
        run(["mkfs.ext4", "-L", "NebulaOS", "-F", root_part])

    else:
        # BIOS/MBR
        step("Creating MBR partition table…")
        run(["parted", "-s", device, "mklabel", "msdos"])

        step("Creating root partition…")
        run(["parted", "-s", device, "mkpart", "primary", "ext4", "1MiB", "100%"])
        run(["parted", "-s", device, "set", "1", "boot", "on"])

        if re.search(r'nvme|mmcblk', device):
            root_part = f"{device}p1"
        else:
            root_part = f"{device}1"
        efi_part = None

        step("Formatting root partition (ext4)…")
        run(["mkfs.ext4", "-L", "NebulaOS", "-F", root_part])

    # Update kernel partition table
    time.sleep(1)
    subprocess.run(["partprobe", device], capture_output=True)
    time.sleep(1)

    return {"efi_part": efi_part, "root_part": root_part}


# ──────────────────────────────────────────────────────────────────────────────
# Mounting
# ──────────────────────────────────────────────────────────────────────────────

def mount_target(parts: dict, mount_root: str, progress_cb=None):
    """Mount root partition at mount_root."""
    def step(msg):
        if progress_cb:
            progress_cb(msg)

    def run(cmd):
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    step(f"Mounting root partition at {mount_root}…")
    os.makedirs(mount_root, exist_ok=True)
    run(["mount", parts["root_part"], mount_root])


def mount_efi(efi_part: str, mount_root: str, progress_cb=None):
    """Mount EFI partition at mount_root/boot/efi (after squashfs is unpacked)."""
    if not efi_part:
        return
    efi_mnt = os.path.join(mount_root, "boot", "efi")
    os.makedirs(efi_mnt, exist_ok=True)
    if progress_cb:
        progress_cb(f"Mounting EFI partition ({efi_part})…")
    subprocess.run(["mount", efi_part, efi_mnt], check=True, capture_output=True)


def unmount_target(mount_root: str):
    """Unmount all target mounts in reverse order."""
    subprocess.run(["umount", "-lf", os.path.join(mount_root, "boot/efi")], capture_output=True)
    subprocess.run(["umount", "-lf", mount_root], capture_output=True)
    subprocess.run(["umount", "-R", mount_root], capture_output=True)


def get_uuid(partition: str) -> Optional[str]:
    """Return the UUID of a partition."""
    try:
        out = subprocess.check_output(
            ["blkid", "-s", "UUID", "-o", "value", partition],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        return out or None
    except Exception:
        return None
