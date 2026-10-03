#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Master Build Driver
# Single-entry build CLI for NebulaOS
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${ROOT_DIR}/src/release/release.conf"

print_usage() {
    cat <<EOF
Usage: ./build.sh [COMMAND]

Commands:
  check       Verify host tools and dependencies
  plymouth    Build Plymouth bootsplash theme and assets
  kernel      Prepare upstream Linux kernel and modules
  sysroot     Assemble base userspace filesystem
  initramfs   Generate custom live initramfs
  rootfs      Package root filesystem into SquashFS
  iso         Generate complete hybrid bootable ISO deliverable
  qemu        Run generated ISO in QEMU emulator
  clean       Remove temporary build artifacts
  help        Show this help message

Target Release: ${PRODUCT_NAME} ${VERSION} "${CODENAME}" (${ARCHITECTURE})
Output Deliverable: build/output/${ISO_NAME}
EOF
}

CMD="${1:-iso}"

case "${CMD}" in
    check)
        bash "${ROOT_DIR}/scripts/check-host.sh"
        ;;
    plymouth)
        bash "${ROOT_DIR}/scripts/build-plymouth.sh"
        ;;
    kernel)
        bash "${ROOT_DIR}/scripts/build-kernel.sh"
        ;;
    sysroot)
        bash "${ROOT_DIR}/scripts/build-sysroot.sh"
        ;;
    initramfs)
        bash "${ROOT_DIR}/scripts/build-initramfs.sh"
        ;;
    rootfs)
        bash "${ROOT_DIR}/scripts/build-rootfs.sh"
        ;;
    debian-base)
        bash "${ROOT_DIR}/scripts/build-debian-base.sh"
        ;;
    iso)
        echo "=============================================================================="
        echo " Starting NebulaOS Debian-Based Live Build: ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
        echo "=============================================================================="
        bash "${ROOT_DIR}/scripts/check-host.sh"
        bash "${ROOT_DIR}/scripts/build-debian-base.sh"
        bash "${ROOT_DIR}/scripts/build-iso.sh"
        ;;
    qemu)
        bash "${ROOT_DIR}/scripts/run-qemu.sh" "${@:2}"
        ;;
    clean)
        echo "Cleaning build artifacts..."
        rm -rf "${ROOT_DIR}/build/sysroot" "${ROOT_DIR}/build/initramfs" "${ROOT_DIR}/build/iso_root" "${ROOT_DIR}/build/live"
        echo "Clean complete."
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo "Unknown command: ${CMD}"
        print_usage
        exit 1
        ;;
esac
