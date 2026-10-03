#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Host Environment & Dependencies Checker
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

echo "=============================================================================="
echo " Checking Host Build Environment for ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

MISSING_TOOLS=()

check_command() {
    local cmd="$1"
    local desc="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        printf " [OK]      %-20s (%s)\n" "$cmd" "$desc"
    else
        printf " [MISSING] %-20s (%s)\n" "$cmd" "$desc"
        MISSING_TOOLS+=("$cmd")
    fi
}

echo ""
echo "Core Build Utilities:"
check_command gcc "C Compiler"
check_command make "Build Automation"
check_command cpio "Archive Tool for Initramfs"
check_command zstd "Fast Lossless Compression"
check_command python3 "Release & Package Scripts"

echo ""
echo "Filesystem & ISO Tools:"
check_command mksquashfs "SquashFS Image Generator"
check_command xorriso "Hybrid ISO Generator"
check_command mcopy "Mtools FAT32 ESP Copier"
check_command mformat "Mtools FAT32 ESP Formatter"

echo ""
echo "Virtualization & Emulation:"
check_command qemu-system-x86_64 "x86_64 Hardware Emulator"

echo ""
if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
    echo "------------------------------------------------------------------------------"
    echo "Warning: Missing required build dependencies: ${MISSING_TOOLS[*]}"
    echo "On Debian/Ubuntu hosts or WSL2, install them using:"
    echo "  sudo apt-get update && sudo apt-get install -y gcc make cpio zstd squashfs-tools xorriso mtools qemu-system-x86"
    echo "------------------------------------------------------------------------------"
    exit 1
else
    echo "All core build dependencies are satisfied!"
    echo "Host is ready to build ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\"."
fi
