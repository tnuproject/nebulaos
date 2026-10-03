#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Live Initramfs Generator
# Custom early userspace with Live ISO discovery, OverlayFS & Silent Plymouth
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

INITRAMFS_DIR="${ROOT_DIR}/build/initramfs/root"
OUTPUT_INITRD="${ROOT_DIR}/build/initramfs/initrd.img"

echo "=============================================================================="
echo " Building Live Initramfs for ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

rm -rf "${INITRAMFS_DIR}"
mkdir -p "${INITRAMFS_DIR}"/{bin,sbin,dev,proc,sys,run,mnt/iso,mnt/squashfs,newroot,etc,lib/modules}

# Install BusyBox
echo "[initramfs] Installing Busybox..."
BUSYBOX_BIN=$(command -v busybox || echo "/usr/bin/busybox")
cp "${BUSYBOX_BIN}" "${INITRAMFS_DIR}/bin/busybox"
chmod 755 "${INITRAMFS_DIR}/bin/busybox"

for app in sh ash mount umount mkdir rmdir cat echo sleep mknod blkid switch_root ls modprobe insmod cut grep sed find; do
    ln -sf busybox "${INITRAMFS_DIR}/bin/${app}"
done

# Copy essential kernel modules if available
MODULES_TAR="${ROOT_DIR}/build/kernel/modules.tar"
if [ -f "${MODULES_TAR}" ]; then
    echo "[initramfs] Extracting core storage & filesystem kernel modules from ${MODULES_TAR}..."
    TMP_MOD=$(mktemp -d /tmp/nebula-mod-XXXXXX)
    tar -xf "${MODULES_TAR}" -C "${TMP_MOD}"
    
    KVER=$(ls "${TMP_MOD}" | head -n 1)
    TARGET_MOD_DIR="${INITRAMFS_DIR}/lib/modules/${KVER}"
    mkdir -p "${TARGET_MOD_DIR}"
    
    # Copy essential drivers (virtio, cdrom, squashfs, overlay, ahci, nvme)
    while IFS= read -r mod; do
        [ -n "${mod}" ] || continue
        rel_path="${mod#${TMP_MOD}/}"
        dest="${INITRAMFS_DIR}/lib/modules/${rel_path}"
        mkdir -p "$(dirname "${dest}")"
        cp "${mod}" "${dest}"
    done < <(find "${TMP_MOD}/${KVER}/kernel/drivers/block" \
                  "${TMP_MOD}/${KVER}/kernel/drivers/virtio" \
                  "${TMP_MOD}/${KVER}/kernel/drivers/ata" \
                  "${TMP_MOD}/${KVER}/kernel/drivers/scsi" \
                  "${TMP_MOD}/${KVER}/kernel/drivers/cdrom" \
                  "${TMP_MOD}/${KVER}/kernel/fs/squashfs" \
                  "${TMP_MOD}/${KVER}/kernel/fs/overlayfs" \
                  "${TMP_MOD}/${KVER}/kernel/fs/isofs" \
                  -name "*.ko*" 2>/dev/null || true)
    rm -rf "${TMP_MOD}"
fi

# Write /init script
echo "[initramfs] Writing early /init boot script..."
cat << 'EOF' > "${INITRAMFS_DIR}/init"
#!/bin/sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

# Mount virtual filesystems
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev
mount -t tmpfs none /run

# Silent mode unless debug requested
VERBOSE=0
for arg in $(cat /proc/cmdline); do
    case "$arg" in
        debug) VERBOSE=1 ;;
        verbose) VERBOSE=1 ;;
    esac
done

if [ "$VERBOSE" -eq 1 ]; then
    echo "[NebulaOS Initramfs] Starting live bootloader..."
fi

# Load critical modules if available
for mod in virtio_pci virtio_blk sr_mod cdrom isofs squashfs overlay; do
    modprobe "$mod" 2>/dev/null || true
done

# Wait for storage devices to settle
sleep 1

# Locate live media
ISO_FOUND=0
mkdir -p /mnt/iso /mnt/squashfs /run/overlay/upper /run/overlay/work /newroot

# Try mounting by label NEBULAOS_LIVE or searching block devices
for dev in /dev/disk/by-label/NEBULAOS_LIVE /dev/sr* /dev/vd* /dev/sd*; do
    [ -e "$dev" ] || continue
    if mount -o ro "$dev" /mnt/iso 2>/dev/null; then
        if [ -f "/mnt/iso/live/rootfs.sfs" ]; then
            ISO_FOUND=1
            break
        fi
        umount /mnt/iso 2>/dev/null || true
    fi
done

if [ "$ISO_FOUND" -ne 1 ]; then
    echo "ERROR: Unable to locate NebulaOS live media!"
    echo "Dropping to rescue emergency shell..."
    exec /bin/sh
fi

# Mount the SquashFS rootfs
mount -t squashfs -o ro,loop /mnt/iso/live/rootfs.sfs /mnt/squashfs

# Create overlay filesystem for writable live session
mount -t overlay overlay -o lowerdir=/mnt/squashfs,upperdir=/run/overlay/upper,workdir=/run/overlay/work /newroot

# Move dev, proc, sys, run to newroot
mount --move /dev /newroot/dev
mount --move /proc /newroot/proc
mount --move /sys /newroot/sys
mount --move /run /newroot/run

# Move live media mount into new root
mkdir -p /newroot/mnt/iso
mount --move /mnt/iso /newroot/mnt/iso 2>/dev/null || true

# Hand over to /sbin/init
exec switch_root /newroot /sbin/init
EOF
chmod 755 "${INITRAMFS_DIR}/init"

# Create cpio.gz archive
echo "[initramfs] Packing initramfs archive (${OUTPUT_INITRD})..."
mkdir -p "$(dirname "${OUTPUT_INITRD}")"
(
    cd "${INITRAMFS_DIR}"
    find . | cpio -H newc -o 2>/dev/null | gzip -9 > "${OUTPUT_INITRD}"
)

echo "[initramfs] Built: ${OUTPUT_INITRD} ($(du -h "${OUTPUT_INITRD}" | cut -f1))"
