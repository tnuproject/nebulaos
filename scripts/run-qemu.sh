#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — QEMU Live ISO Runner (UEFI & BIOS)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

ISO_PATH="${ROOT_DIR}/build/output/${ISO_NAME}"

if [ ! -f "${ISO_PATH}" ]; then
    echo "Error: ISO not found at ${ISO_PATH}."
    echo "Please build it first with: ./build.sh iso"
    exit 1
fi

echo "=============================================================================="
echo " Booting ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\" in QEMU"
echo " ISO: ${ISO_PATH}"
echo "=============================================================================="

# Check for OVMF UEFI firmware
OVMF_CODE=""
for p in /usr/share/OVMF/OVMF_CODE.fd /usr/share/ovmf/OVMF.fd /usr/share/qemu/OVMF.fd; do
    if [ -f "$p" ]; then
        OVMF_CODE="$p"
        break
    fi
done

QEMU_ARGS=(
    -m 4096
    -smp 4
    -cdrom "${ISO_PATH}"
    -boot d
    -vga virtio
    -display gtk,gl=on 2>/dev/null || -display default
)

if [ -n "${OVMF_CODE}" ]; then
    echo "[qemu] Booting with UEFI firmware: ${OVMF_CODE}"
    qemu-system-x86_64 -bios "${OVMF_CODE}" -m 4096 -smp 4 -cdrom "${ISO_PATH}" -boot d -vga virtio "$@"
else
    echo "[qemu] OVMF not detected, booting in standard hybrid mode..."
    qemu-system-x86_64 -m 4096 -smp 4 -cdrom "${ISO_PATH}" -boot d -vga virtio "$@"
fi
