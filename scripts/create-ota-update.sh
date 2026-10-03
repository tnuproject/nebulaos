#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Multi-Version OTA Update & Release Generator
# Usage:
#   ./scripts/create-ota-update.sh [FROM_VER] [TO_VER] [CODENAME] [CHANGELOG]
# Examples:
#   ./scripts/create-ota-update.sh 26.0 27.0 Cosmos "Adds celestial wallpapers and updates"
#   ./scripts/create-ota-update.sh 25.0 26.0 Plains "Upgraded to GNOME Desktop, new installer"
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

FROM_VER="${1:-26.0}"
TO_VER="${2:-27.0}"
CODENAME="${3:-Cosmos}"
CHANGELOG="${4:-New wallpapers, performance fixes and security updates for ${TO_VER} (${CODENAME}).}"

RELEASE_DATE="$(date +%Y-%m-%d)"
OTA_DIR="${ROOT_DIR}/webserver/ota"
ISO_DIR="${ROOT_DIR}/webserver/iso"
OUTPUT_DIR="${ROOT_DIR}/build/output"
ARCHIVE_NAME="NebulaOS-Update-${FROM_VER}-to-${TO_VER}.tar.gz"
FINAL_ARCHIVE="${OTA_DIR}/${ARCHIVE_NAME}"
ISO_NAME="NebulaOS-${TO_VER}-${CODENAME}-x86_64.iso"
FINAL_ISO="${OUTPUT_DIR}/${ISO_NAME}"

echo "=============================================================================="
echo " Generating OTA Update: NebulaOS ${FROM_VER} -> ${TO_VER} \"${CODENAME}\""
echo "=============================================================================="

mkdir -p "${OTA_DIR}" "${ISO_DIR}" "${OUTPUT_DIR}"

# 1. Create Staging Directory for Update Payload
STAGE_DIR="/tmp/nebulaos-ota-stage"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/wallpapers"

# Include wallpapers if available
if [ -d "${ROOT_DIR}/src/branding/wallpapers" ]; then
    cp -r "${ROOT_DIR}/src/branding/wallpapers/"*.svg "${STAGE_DIR}/wallpapers/" 2>/dev/null || true
    cp "${ROOT_DIR}/src/branding/wallpapers/nebula-wallpapers.xml" "${STAGE_DIR}/" 2>/dev/null || true
fi

# Create update.sh script that executes when the update is applied
cat <<EOF > "${STAGE_DIR}/update.sh"
#!/usr/bin/env bash
set -e
PAYLOAD_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"

echo "Applying NebulaOS ${TO_VER} (${CODENAME}) update..."

# 1. Install updated wallpapers and configs if present
if [ -d "\${PAYLOAD_DIR}/wallpapers" ]; then
    mkdir -p /usr/share/backgrounds/nebula /usr/share/gnome-background-properties
    cp -r "\${PAYLOAD_DIR}/wallpapers/"*.svg /usr/share/backgrounds/nebula/ 2>/dev/null || true
    if [ -f "\${PAYLOAD_DIR}/nebula-wallpapers.xml" ]; then
        cp "\${PAYLOAD_DIR}/nebula-wallpapers.xml" /usr/share/gnome-background-properties/nebula-wallpapers.xml
    fi
fi

# 2. Update /etc/os-release
if [ -f /etc/os-release ]; then
    sed -i 's/^VERSION=.*/VERSION="${TO_VER} (${CODENAME})"/' /etc/os-release
    sed -i 's/^VERSION_ID=.*/VERSION_ID="${TO_VER}"/' /etc/os-release
    sed -i 's/^PRETTY_NAME=.*/PRETTY_NAME="NebulaOS ${TO_VER} (${CODENAME})"/' /etc/os-release
    sed -i 's/^VERSION_CODENAME=.*/VERSION_CODENAME="${CODENAME,,}"/' /etc/os-release
fi

if [ -f /usr/lib/os-release ]; then
    sed -i 's/^VERSION=.*/VERSION="${TO_VER} (${CODENAME})"/' /usr/lib/os-release
    sed -i 's/^VERSION_ID=.*/VERSION_ID="${TO_VER}"/' /usr/lib/os-release
    sed -i 's/^PRETTY_NAME=.*/PRETTY_NAME="NebulaOS ${TO_VER} (${CODENAME})"/' /usr/lib/os-release
    sed -i 's/^VERSION_CODENAME=.*/VERSION_CODENAME="${CODENAME,,}"/' /usr/lib/os-release
fi

# 3. Update /etc/issue
cat <<'ISSUE_EOF' > /etc/issue
NebulaOS ${TO_VER} "${CODENAME}" (x86_64) - \\l
Kernel \\r on an \\m

ISSUE_EOF

# 4. Refresh desktop database & icon cache
update-desktop-database /usr/share/applications 2>/dev/null || true

# 5. Notify user if desktop is running
if command -v notify-send >/dev/null 2>&1; then
    notify-send -i software-update-available -a "Software Update" \
        "Update Complete" "Successfully upgraded to NebulaOS ${TO_VER} ${CODENAME}!" 2>/dev/null || true
fi

echo "NebulaOS update to ${TO_VER} ${CODENAME} finished successfully!"
EOF

chmod +x "${STAGE_DIR}/update.sh"

# 2. Package the Delta Update Archive (.tar.gz)
echo "[ota] Packaging ${FINAL_ARCHIVE}..."
tar -czf "${FINAL_ARCHIVE}" -C "${STAGE_DIR}" .

ARCHIVE_SHA256="$(sha256sum "${FINAL_ARCHIVE}" | cut -d' ' -f1)"
ARCHIVE_SIZE="$(stat -c%s "${FINAL_ARCHIVE}")"

# 3. Update the Multi-Version ota.json Manifest
echo "[ota] Updating ${ROOT_DIR}/webserver/api/v1/ota.json..."
python3 - <<PYEOF
import json
import os

ota_path = "${ROOT_DIR}/webserver/api/v1/ota.json"
data = {
    "latest_version": "${TO_VER}",
    "latest_codename": "${CODENAME}",
    "release_date": "${RELEASE_DATE}",
    "releases": [],
    "isos": []
}

if os.path.exists(ota_path):
    try:
        with open(ota_path, "r") as f:
            data = json.load(f)
    except Exception:
        pass

# Update latest
data["latest_version"] = "${TO_VER}"
data["latest_codename"] = "${CODENAME}"
data["release_date"] = "${RELEASE_DATE}"
data["update_url"] = "https://tnu-universe.it/ota/${ARCHIVE_NAME}"
data["iso_url"] = "https://tnu-universe.it/iso/${ISO_NAME}"
data["sha256"] = "${ARCHIVE_SHA256}"
data["size_bytes"] = ${ARCHIVE_SIZE}
data["changelog"] = """${CHANGELOG}"""

# Ensure releases list
if "releases" not in data or not isinstance(data["releases"], list):
    data["releases"] = []

# Replace or append this release
new_release = {
    "version": "${TO_VER}",
    "codename": "${CODENAME}",
    "from_version": "${FROM_VER}",
    "release_date": "${RELEASE_DATE}",
    "update_url": "https://tnu-universe.it/ota/${ARCHIVE_NAME}",
    "sha256": "${ARCHIVE_SHA256}",
    "size_bytes": ${ARCHIVE_SIZE},
    "changelog": """${CHANGELOG}"""
}

updated = False
for i, r in enumerate(data["releases"]):
    if r.get("version") == "${TO_VER}" and r.get("from_version") == "${FROM_VER}":
        data["releases"][i] = new_release
        updated = True
        break
if not updated:
    data["releases"].append(new_release)

# Ensure isos list
if "isos" not in data or not isinstance(data["isos"], list):
    data["isos"] = []

new_iso = {
    "version": "${TO_VER}",
    "codename": "${CODENAME}",
    "filename": "${ISO_NAME}",
    "url": "https://tnu-universe.it/iso/${ISO_NAME}"
}
iso_updated = False
for i, item in enumerate(data["isos"]):
    if item.get("version") == "${TO_VER}":
        data["isos"][i] = new_iso
        iso_updated = True
        break
if not iso_updated:
    data["isos"].append(new_iso)

with open(ota_path, "w") as f:
    json.dump(data, f, indent=2)

print("  -> Successfully updated ota.json with release ${TO_VER} (from ${FROM_VER})")
PYEOF

# 4. Generate the Full Release ISO if requested / needed
if [ "${BUILD_ISO:-1}" = "1" ]; then
    echo "[ota] Building complete ${TO_VER} ${CODENAME} ISO..."
    ISO_ROOT_TMP="/tmp/nebulaos-isotmp-${TO_VER}"
    CHROOT_TMP="/tmp/nebulaos-chroot-${TO_VER}"
    rm -rf "${ISO_ROOT_TMP}" "${CHROOT_TMP}"
    mkdir -p "${ISO_ROOT_TMP}/live" "${ISO_ROOT_TMP}/boot/grub"

    BASE_SQUASHFS="${ROOT_DIR}/build/iso_root/live/filesystem.squashfs"
    if [ -f "${BASE_SQUASHFS}" ]; then
        echo "  -> Extracting base squashfs..."
        unsquashfs -d "${CHROOT_TMP}" "${BASE_SQUASHFS}"

        # Apply payload inside chroot
        mkdir -p "${CHROOT_TMP}/usr/share/backgrounds/nebula" "${CHROOT_TMP}/usr/share/gnome-background-properties"
        cp -r "${STAGE_DIR}/wallpapers/"*.svg "${CHROOT_TMP}/usr/share/backgrounds/nebula/" 2>/dev/null || true
        if [ -f "${STAGE_DIR}/nebula-wallpapers.xml" ]; then
            cp "${STAGE_DIR}/nebula-wallpapers.xml" "${CHROOT_TMP}/usr/share/gnome-background-properties/nebula-wallpapers.xml"
        fi

        if [ -f "${CHROOT_TMP}/usr/lib/os-release" ]; then
            sed -i "s/^VERSION=.*/VERSION=\"${TO_VER} (${CODENAME})\"/" "${CHROOT_TMP}/usr/lib/os-release"
            sed -i "s/^VERSION_ID=.*/VERSION_ID=\"${TO_VER}\"/" "${CHROOT_TMP}/usr/lib/os-release"
            sed -i "s/^PRETTY_NAME=.*/PRETTY_NAME=\"NebulaOS ${TO_VER} (${CODENAME})\"/" "${CHROOT_TMP}/usr/lib/os-release"
            sed -i "s/^VERSION_CODENAME=.*/VERSION_CODENAME=\"${CODENAME,,}\"/" "${CHROOT_TMP}/usr/lib/os-release"
        fi

        echo "  -> Compressing ${TO_VER} SquashFS..."
        mksquashfs "${CHROOT_TMP}" "${ISO_ROOT_TMP}/live/filesystem.squashfs" \
            -comp zstd -Xcompression-level 15 -b 1048576 -noappend

        cp "${ROOT_DIR}/build/kernel/vmlinuz" "${ISO_ROOT_TMP}/boot/vmlinuz"
        cp "${ROOT_DIR}/build/kernel/initrd.img" "${ISO_ROOT_TMP}/boot/initrd.img"

        cat <<EOF > "${ISO_ROOT_TMP}/boot/grub/grub.cfg"
set default="0"
set timeout=1
set timeout_style=hidden
set gfxmode=auto
set gfxpayload=keep
insmod all_video
insmod font
insmod gfxterm
insmod part_gpt
insmod part_msdos
insmod iso9660

menuentry "NebulaOS ${TO_VER} (${CODENAME}) [Live Desktop]" --id live {
    search --no-floppy --file --set=root /boot/vmlinuz
    linux /boot/vmlinuz boot=live components username=nebula quiet splash loglevel=0 vt.global_cursor_default=0 udev.log_level=0 rd.udev.log_level=0 systemd.show_status=auto
    initrd /boot/initrd.img
}
EOF

        echo "  -> Packaging ${TO_VER} ISO via grub-mkrescue..."
        grub-mkrescue -o "${FINAL_ISO}" "${ISO_ROOT_TMP}" -- -volid "NEBULAOS_${TO_VER//./_}"
        echo "  -> ${TO_VER} ISO created: ${FINAL_ISO}"

        cp -f "${FINAL_ISO}" "${ISO_DIR}/${ISO_NAME}" 2>/dev/null || true
    fi
    rm -rf "${ISO_ROOT_TMP}" "${CHROOT_TMP}"
fi

# Cleanup staging
rm -rf "${STAGE_DIR}"

echo "=============================================================================="
echo " OTA Update ${FROM_VER} -> ${TO_VER} successfully created!"
echo " Delta: ${FINAL_ARCHIVE} (${ARCHIVE_SIZE} bytes, SHA256: ${ARCHIVE_SHA256})"
if [ -f "${FINAL_ISO}" ]; then
    echo " Full ISO: ${FINAL_ISO} ($(du -h "${FINAL_ISO}" | cut -f1))"
fi
echo "=============================================================================="
