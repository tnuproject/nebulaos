#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Hybrid UEFI / BIOS Live ISO Generator
# Produces universally bootable hybrid ISO (UEFI + BIOS + Rufus/dd compatible)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

ISO_ROOT="${ROOT_DIR}/build/iso_root"
OUTPUT_DIR="${ROOT_DIR}/build/output"
FINAL_ISO="${OUTPUT_DIR}/${ISO_NAME}"

echo "=============================================================================="
echo " Building Official Live ISO: ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo " Output Target: ${FINAL_ISO}"
echo "=============================================================================="

# 1. Prepare Directories (preserving live/filesystem.squashfs)
mkdir -p "${ISO_ROOT}"/{boot/grub,EFI/BOOT,live} "${OUTPUT_DIR}"

# 2. Check dependencies and build Debian base if needed
if [ ! -f "${ISO_ROOT}/live/filesystem.squashfs" ] || [ ! -f "${ROOT_DIR}/build/kernel/vmlinuz" ] || [ ! -f "${ROOT_DIR}/build/kernel/initrd.img" ]; then
    echo "[iso] Debian live base payload not found, executing build-debian-base.sh..."
    bash "${ROOT_DIR}/scripts/build-debian-base.sh"
fi

echo "[iso] Populating ISO payload..."
cp "${ROOT_DIR}/build/kernel/vmlinuz" "${ISO_ROOT}/boot/vmlinuz"
cp "${ROOT_DIR}/build/kernel/initrd.img" "${ISO_ROOT}/boot/initrd.img"

# 3. Generate GRUB Configuration
echo "[iso] Generating hidden GRUB live configuration..."
export PRODUCT_NAME VERSION CODENAME ISO_NAME
envsubst '${PRODUCT_NAME} ${VERSION} ${CODENAME} ${ISO_NAME}' < "${ROOT_DIR}/config/grub.cfg.template" > "${ISO_ROOT}/boot/grub/grub.cfg"

# 4. Generate Universally Bootable Hybrid ISO via grub-mkrescue
echo "[iso] Generating hybrid UEFI + BIOS ISO via grub-mkrescue..."
rm -f "${FINAL_ISO}"

grub-mkrescue -o "${FINAL_ISO}" "${ISO_ROOT}" -- -volid "${ISO_LABEL}"

echo "=============================================================================="
echo " ISO Generation Succeeded!"
echo " ISO File: ${FINAL_ISO}"
echo " Size:     $(du -h "${FINAL_ISO}" | cut -f1)"
echo " SHA256:   $(sha256sum "${FINAL_ISO}" | cut -d' ' -f1)"
echo "=============================================================================="
