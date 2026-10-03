#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Root Filesystem (SquashFS) Packager
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

SYSROOT="${ROOT_DIR}/build/sysroot"
OUTPUT_LIVE="${ROOT_DIR}/build/live"
OUTPUT_SFS="${OUTPUT_LIVE}/rootfs.sfs"

echo "=============================================================================="
echo " Packaging Root Filesystem for ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

# 1. Assemble sysroot
bash "${ROOT_DIR}/scripts/build-sysroot.sh"

# 2. Stage in native Linux filesystem to handle case sensitivity & speed
ROOTFS_STAGE=$(mktemp -d /tmp/nebulaos-stage-XXXXXX)
trap 'rm -rf "${ROOTFS_STAGE}"' EXIT

echo "[rootfs] Staging rootfs in ${ROOTFS_STAGE}..."
cp -a "${SYSROOT}/." "${ROOTFS_STAGE}/"

# 3. Integrate Kernel Modules from tar archive
MODULES_TAR="${ROOT_DIR}/build/kernel/modules.tar"
if [ -f "${MODULES_TAR}" ]; then
    echo "[rootfs] Extracting kernel modules into rootfs stage..."
    mkdir -p "${ROOTFS_STAGE}/usr/lib/modules"
    tar -xf "${MODULES_TAR}" -C "${ROOTFS_STAGE}/usr/lib/modules"
fi

# 4. Create SquashFS image
echo "[rootfs] Compressing rootfs into SquashFS (${OUTPUT_SFS})..."
mkdir -p "${OUTPUT_LIVE}"
rm -f "${OUTPUT_SFS}"

mksquashfs "${ROOTFS_STAGE}" "${OUTPUT_SFS}" \
    -comp zstd \
    -Xcompression-level 15 \
    -b 1048576 \
    -noappend

echo "[rootfs] SquashFS generated: ${OUTPUT_SFS} ($(du -h "${OUTPUT_SFS}" | cut -f1))"
