"""
Nebula Setup — Installation Orchestrator
Coordinates all install steps with progress callbacks.
"""

import threading
from typing import Callable, Optional

from backend.state import InstallState, get_state
from backend.disk import (
    partition_and_format, mount_target, mount_efi, unmount_target,
    is_efi_system, PartitionError
)
from backend.system import (
    unpack_squashfs, bind_vfs, unbind_vfs, setup_fstab,
    setup_locale, setup_hostname, create_user, set_theme,
    install_bootloader, update_initramfs, post_cleanup, setup_resolv
)


ProgressCB = Callable[[int, str], None]   # (step_number, message)


STEPS = [
    "Partitioning disk",
    "Mounting filesystems",
    "Copying system files",
    "Configuring locale",
    "Setting up hostname",
    "Creating user account",
    "Applying theme",
    "Installing bootloader",
    "Finalizing",
]


class InstallError(RuntimeError):
    pass


def run_install(progress_cb: ProgressCB, done_cb: Callable[[], None],
                error_cb: Callable[[str], None]):
    """
    Run the full installation in a background thread.
    Calls progress_cb(step_index, message) to report progress.
    Calls done_cb() on success, error_cb(message) on failure.
    """
    thread = threading.Thread(target=_install_thread,
                              args=(progress_cb, done_cb, error_cb),
                              daemon=True)
    thread.start()
    return thread


def _install_thread(progress_cb: ProgressCB,
                    done_cb: Callable[[], None],
                    error_cb: Callable[[str], None]):
    state: InstallState = get_state()

    def step(n: int, msg: str):
        progress_cb(n, msg)

    def substep(msg: str):
        # substep reuses the current step number
        progress_cb(state.current_step, msg)

    use_efi = is_efi_system()
    state.use_efi = use_efi

    try:
        # ── Step 1: Partition & Format ─────────────────────────────────────
        state.current_step = 0
        step_msg = "Preparing partitions for dual boot…" if state.install_mode == "dualboot" else "Partitioning disk…"
        step(0, step_msg)
        try:
            parts = partition_and_format(
                state.target_disk,
                progress_cb=substep,
                install_mode=state.install_mode,
                target_partition=state.target_partition,
                efi_partition=state.efi_partition
            )
        except Exception as e:
            raise InstallError(f"Disk partitioning failed: {e}")

        # ── Step 2: Mount Root Filesystem ─────────────────────────────────
        state.current_step = 1
        step(1, "Mounting root filesystem…")
        try:
            mount_target(parts, state.mount_root, progress_cb=substep)
        except Exception as e:
            raise InstallError(f"Mount failed: {e}")

        # ── Step 3: Unpack squashfs ────────────────────────────────────────
        state.current_step = 2
        step(2, "Copying system files (this may take a few minutes)…")
        try:
            unpack_squashfs(state.mount_root, state.squashfs_source,
                            progress_cb=substep)
        except Exception as e:
            raise InstallError(f"Filesystem copy failed: {e}")

        # Mount EFI partition (after squashfs is unpacked into /boot)
        if parts.get("efi_part"):
            try:
                mount_efi(parts["efi_part"], state.mount_root, progress_cb=substep)
            except Exception as e:
                raise InstallError(f"EFI mount failed: {e}")

        # Bind virtual filesystems & resolv.conf for chroot
        try:
            bind_vfs(state.mount_root)
            setup_resolv(state.mount_root)
        except Exception:
            pass

        # ── Step 4: fstab ─────────────────────────────────────────────────
        substep("Writing /etc/fstab…")
        setup_fstab(
            state.mount_root,
            parts["root_part"],
            parts.get("efi_part"),
            progress_cb=substep
        )

        # ── Step 5: Locale & Timezone ─────────────────────────────────────
        state.current_step = 3
        step(3, "Configuring locale and timezone…")
        setup_locale(
            state.mount_root,
            state.language,
            state.timezone,
            state.keyboard_layout,
            state.keyboard_model,
            progress_cb=substep
        )

        # ── Step 6: Hostname ──────────────────────────────────────────────
        state.current_step = 4
        step(4, "Setting up hostname…")
        setup_hostname(state.mount_root, state.hostname, progress_cb=substep)

        # ── Step 7: Create User ───────────────────────────────────────────
        state.current_step = 5
        step(5, "Creating your user account…")
        create_user(
            state.mount_root,
            state.username,
            state.full_name,
            state.password,
            progress_cb=substep
        )

        # ── Step 8: Theme ─────────────────────────────────────────────────
        state.current_step = 6
        step(6, "Applying theme…")
        set_theme(
            state.mount_root,
            state.color_scheme,
            state.username,
            progress_cb=substep
        )

        # ── Step 9: Bootloader ────────────────────────────────────────────
        state.current_step = 7
        step(7, "Installing bootloader…")
        install_bootloader(
            state.mount_root,
            state.target_disk,
            use_efi,
            install_mode=state.install_mode,
            progress_cb=substep
        )

        # Initramfs
        substep("Updating initramfs…")
        update_initramfs(state.mount_root, progress_cb=substep)

        # ── Step 10: Cleanup ──────────────────────────────────────────────
        state.current_step = 8
        step(8, "Finalizing installation…")
        post_cleanup(state.mount_root, state.username,
                     install_mode=state.install_mode,
                     progress_cb=substep)

    except InstallError as e:
        try:
            unbind_vfs(state.mount_root)
            unmount_target(state.mount_root)
        except Exception:
            pass
        state.install_error = str(e)
        error_cb(str(e))
        return
    except Exception as e:
        try:
            unbind_vfs(state.mount_root)
            unmount_target(state.mount_root)
        except Exception:
            pass
        state.install_error = f"Unexpected error: {e}"
        error_cb(state.install_error)
        return
    finally:
        # Always unbind VFS and unmount target filesystems
        try:
            unbind_vfs(state.mount_root)
            unmount_target(state.mount_root)
        except Exception:
            pass

    state.install_done = True
    done_cb()
