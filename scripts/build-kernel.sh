#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Kernel Extraction & Packaging Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

STAGE_DIR="${ROOT_DIR}/build/kernel"
OUTPUT_VMLINUZ="${STAGE_DIR}/vmlinuz"
OUTPUT_MODULES_TAR="${STAGE_DIR}/modules.tar"

echo "=============================================================================="
echo " Preparing Upstream Linux Kernel for ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

if [ -f "${OUTPUT_VMLINUZ}" ] && [ -f "${OUTPUT_MODULES_TAR}" ]; then
    echo "[kernel] Existing kernel and modules archive found in ${STAGE_DIR}. Reusing cache."
    exit 0
fi

mkdir -p "${STAGE_DIR}"
TMP_DIR=$(mktemp -d /tmp/nebulaos-kernel-XXXXXX)
trap 'rm -rf "${TMP_DIR}"' EXIT

cd "${TMP_DIR}"

echo "[kernel] Fetching upstream x86_64 generic kernel package and modules..."
KERNEL_PKG=$(apt-cache search '^linux-image-[0-9].*-generic$' | sort -V | tail -n 1 | awk '{print $1}')
MODULES_PKG=$(echo "${KERNEL_PKG}" | sed 's/linux-image-/linux-modules-/')
echo "[kernel] Selected kernel package:  ${KERNEL_PKG}"
echo "[kernel] Selected modules package: ${MODULES_PKG}"

apt-get download "${KERNEL_PKG}" "${MODULES_PKG}"

echo "[kernel] Extracting kernel binary and core modules..."
for deb in *.deb; do
    dpkg -x "${deb}" extracted/
done

# Locate and install vmlinuz
VMLINUZ_SRC=$(ls extracted/boot/vmlinuz-* | head -n 1)
cp "${VMLINUZ_SRC}" "${OUTPUT_VMLINUZ}"
chmod 644 "${OUTPUT_VMLINUZ}"

# Archive modules to tar to preserve full POSIX case sensitivity across host filesystems
OUTPUT_MODULES_TAR="${STAGE_DIR}/modules.tar"
echo "[kernel] Archiving kernel modules into ${OUTPUT_MODULES_TAR}..."
tar -cf "${OUTPUT_MODULES_TAR}" -C extracted/lib/modules .

echo "[kernel] Kernel successfully prepared:"
echo "  Binary:  ${OUTPUT_VMLINUZ} ($(du -h "${OUTPUT_VMLINUZ}" | cut -f1))"
echo "  Modules: ${OUTPUT_MODULES_TAR} ($(du -h "${OUTPUT_MODULES_TAR}" | cut -f1))"
