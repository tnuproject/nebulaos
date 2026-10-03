"""
Nebula Setup — Shared Installation State
Singleton class that holds all user choices across screens.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InstallState:
    # Language & Locale
    language: str = "en_US"
    language_display: str = "English"
    timezone: str = "Europe/Rome"
    keyboard_layout: str = "us"
    keyboard_model: str = "pc105"

    # User account
    full_name: str = ""
    username: str = ""
    password: str = ""
    hostname: str = "nebulaos"

    # Theme
    color_scheme: str = "prefer-dark"   # "prefer-dark" or "prefer-light"

    # Disk & Partitioning
    target_disk: Optional[str] = None   # e.g. "/dev/sda"
    target_disk_model: str = ""
    target_disk_size: str = ""
    use_efi: bool = True                # auto-detected
    install_mode: str = "erase"         # "erase" or "dualboot"
    target_partition: Optional[str] = None  # e.g. "/dev/sda3" (for dualboot)
    target_partition_size: str = ""
    efi_partition: Optional[str] = None     # e.g. "/dev/sda1" (existing ESP)

    # Install paths
    mount_root: str = "/mnt/nebula-install"
    squashfs_source: str = "/cdrom/live/filesystem.squashfs"

    # Progress tracking (set by installer.py)
    current_step: int = 0
    total_steps: int = 9
    step_label: str = ""
    install_error: Optional[str] = None
    install_done: bool = False


# Module-level singleton
_state: Optional[InstallState] = None


def get_state() -> InstallState:
    global _state
    if _state is None:
        _state = InstallState()
    return _state


def reset_state() -> InstallState:
    global _state
    _state = InstallState()
    return _state
