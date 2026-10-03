"""
Nebula Recovery — Disk and Partition Operations Backend
Provides listing, inspection, erasing, and formatting of drives and partitions.
"""

import json
import subprocess
import shutil
from typing import List, Dict, Any


def list_storage_devices() -> List[Dict[str, Any]]:
    """
    Returns list of disks and their partitions using lsblk.
    """
    devices = []
    try:
        res = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,MODEL,MOUNTPOINT,RM,RO"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            raw_devices = data.get("blockdevices", [])
            for dev in raw_devices:
                # Filter out loop, zram, and read-only cdrom/live media
                if dev.get("type") in ("loop", "zram") or dev.get("ro"):
                    continue

                size_bytes = int(dev.get("size") or 0)
                if size_bytes < 100 * 1024 * 1024:  # ignore < 100MB
                    continue

                size_gb = size_bytes / (1024 ** 3)
                size_str = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_bytes // (1024**2)} MB"

                children = []
                for child in dev.get("children", []):
                    c_bytes = int(child.get("size") or 0)
                    c_gb = c_bytes / (1024 ** 3)
                    c_size_str = f"{c_gb:.1f} GB" if c_gb >= 1 else f"{c_bytes // (1024**2)} MB"
                    children.append({
                        "name": child.get("name", ""),
                        "path": child.get("path", f"/dev/{child.get('name')}"),
                        "size_bytes": c_bytes,
                        "size_str": c_size_str,
                        "fstype": child.get("fstype") or "unformatted",
                        "label": child.get("label") or "",
                        "mountpoint": child.get("mountpoint") or "",
                    })

                devices.append({
                    "name": dev.get("name", ""),
                    "path": dev.get("path", f"/dev/{dev.get('name')}"),
                    "model": (dev.get("model") or "Generic Storage").strip(),
                    "size_bytes": size_bytes,
                    "size_str": size_str,
                    "fstype": dev.get("fstype") or "",
                    "label": dev.get("label") or "",
                    "removable": bool(dev.get("rm")),
                    "mountpoint": dev.get("mountpoint") or "",
                    "partitions": children,
                })
    except Exception as e:
        print(f"Error listing storage: {e}")

    return devices


def format_partition(partition_path: str, fstype: str = "ext4", label: str = "") -> tuple[bool, str]:
    """
    Formats the given partition with the specified filesystem.
    Supported: ext4, btrfs, vfat (FAT32), exfat, ntfs
    """
    fstype = fstype.lower().strip()
    cmd = []

    if fstype in ("ext4", "ext3", "ext2"):
        cmd = ["mkfs.ext4", "-F"]
        if label:
            cmd.extend(["-L", label[:16]])
        cmd.append(partition_path)

    elif fstype == "btrfs":
        cmd = ["mkfs.btrfs", "-f"]
        if label:
            cmd.extend(["-L", label])
        cmd.append(partition_path)

    elif fstype in ("vfat", "fat32", "fat"):
        cmd = ["mkfs.vfat", "-F", "32", "-I"]
        if label:
            cmd.extend(["-n", label[:11]])
        cmd.append(partition_path)

    elif fstype == "exfat":
        cmd = ["mkfs.exfat"]
        if label:
            cmd.extend(["-n", label])
        cmd.append(partition_path)

    elif fstype == "ntfs":
        cmd = ["mkfs.ntfs", "-f", "-q"]
        if label:
            cmd.extend(["-L", label])
        cmd.append(partition_path)
    else:
        return False, f"Unsupported filesystem type: {fstype}"

    # Verify tool exists
    if not shutil.which(cmd[0]):
        return False, f"Formatting tool '{cmd[0]}' is not installed on the system."

    # Unmount if mounted
    subprocess.run(["umount", "-f", partition_path], capture_output=True)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            return True, f"Successfully formatted {partition_path} as {fstype.upper()}."
        else:
            return False, res.stderr.strip() or res.stdout.strip() or "Formatting failed."
    except Exception as e:
        return False, str(e)


def wipe_and_create_gpt(disk_path: str) -> tuple[bool, str]:
    """
    Wipes the disk partition table and initializes a fresh GPT table.
    """
    # Unmount any partitions on this disk
    try:
        subprocess.run(["umount", "-f", f"{disk_path}*"], capture_output=True, shell=True)
    except Exception:
        pass

    try:
        # Wipe signatures
        subprocess.run(["wipefs", "-a", disk_path], capture_output=True, timeout=10)
        # Create fresh GPT table
        res = subprocess.run(["parted", "-s", disk_path, "mklabel", "gpt"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return True, f"Successfully wiped and initialized GPT label on {disk_path}."
        else:
            return False, res.stderr.strip() or "Failed to create partition table."
    except Exception as e:
        return False, str(e)
