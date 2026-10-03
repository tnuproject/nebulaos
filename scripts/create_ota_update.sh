#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Automated OTA Update & Debian Package Builder
#
# Generates a new OTA update package, rebuilds the APT repository metadata
# (Packages, Packages.gz, Release) into ota_updates/, and updates src/ versioning.
#
# Usage:
#   ./scripts/create_ota_update.sh [VERSION] [CHANGELOG]
#
# Examples:
#   ./scripts/create_ota_update.sh 26.0.2 "Recovery and dynamic language translation"
#   ./scripts/create_ota_update.sh 27.0.0 "Major release with celestial wallpapers"
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

RELEASE_CONF="${ROOT_DIR}/src/release/release.conf"
OTA_OUTPUT_DIR="${ROOT_DIR}/ota_updates"
UPDATES_SUBDIR="${OTA_OUTPUT_DIR}/updates"

mkdir -p "${OTA_OUTPUT_DIR}" "${UPDATES_SUBDIR}"

# ── 1. Determine Version & Changelog ──────────────────────────────────────────

CURRENT_VER="26.0.1"
if [ -f "${RELEASE_CONF}" ]; then
    CURRENT_VER="$(grep -E '^VERSION=' "${RELEASE_CONF}" | head -1 | cut -d'"' -f2)"
fi

if [ -n "${1:-}" ]; then
    NEW_VER="$1"
else
    # Auto-increment patch version: e.g. 26.0.1 -> 26.0.2
    IFS='.' read -r -a PARTS <<< "${CURRENT_VER}"
    MAJOR="${PARTS[0]:-26}"
    MINOR="${PARTS[1]:-0}"
    PATCH="${PARTS[2]:-0}"
    NEW_PATCH=$((PATCH + 1))
    NEW_VER="${MAJOR}.${MINOR}.${NEW_PATCH}"
fi

CHANGELOG="${2:-Maintenance update with system fixes and performance enhancements.}"
RELEASE_DATE="$(date +%Y-%m-%d)"
RFC_DATE="$(date -Ru)"

echo "=============================================================================="
echo " Building NebulaOS OTA Update: ${CURRENT_VER} -> ${NEW_VER}"
echo " Release Date : ${RELEASE_DATE}"
echo " Changelog    : ${CHANGELOG}"
echo "=============================================================================="

# ── 2. Update Source Repository Versioning (src/release/release.conf) ─────────

if [ -f "${RELEASE_CONF}" ]; then
    IFS='.' read -r -a NEW_PARTS <<< "${NEW_VER}"
    V_MAJ="${NEW_PARTS[0]:-26}"
    V_MIN="${NEW_PARTS[1]:-0}"
    V_PAT="${NEW_PARTS[2]:-0}"
    BUILD_ID="$(date +%Y.%m.%d.%H%M)"

    sed -i "s/^VERSION=.*/VERSION=\"${NEW_VER}\"/" "${RELEASE_CONF}"
    sed -i "s/^MAJOR_VERSION=.*/MAJOR_VERSION=\"${V_MAJ}\"/" "${RELEASE_CONF}"
    sed -i "s/^MINOR_VERSION=.*/MINOR_VERSION=\"${V_MIN}\"/" "${RELEASE_CONF}"
    sed -i "s/^PATCH_VERSION=.*/PATCH_VERSION=\"${V_PAT}\"/" "${RELEASE_CONF}"
    sed -i "s/^BUILD_ID=.*/BUILD_ID=\"${BUILD_ID}\"/" "${RELEASE_CONF}"
    echo "[src] Updated ${RELEASE_CONF} to version ${NEW_VER} (Build ${BUILD_ID})"
fi

# ── 3. Stage and Build the nebula-desktop Debian Package ───────────────────────

STAGE_DIR="/tmp/nebula-desktop-stage-${NEW_VER}"
rm -rf "${STAGE_DIR}"

mkdir -p "${STAGE_DIR}/DEBIAN"
mkdir -p "${STAGE_DIR}/usr/bin"
mkdir -p "${STAGE_DIR}/usr/lib/nebulaos"
mkdir -p "${STAGE_DIR}/usr/share/applications"
mkdir -p "${STAGE_DIR}/usr/share/glib-2.0/schemas"
mkdir -p "${STAGE_DIR}/usr/share/thumbnailers"
mkdir -p "${STAGE_DIR}/etc/default/grub.d"
mkdir -p "${STAGE_DIR}/etc/systemd/system"
mkdir -p "${STAGE_DIR}/usr/share/nebula-setup"
mkdir -p "${STAGE_DIR}/usr/share/nebula-recovery"
mkdir -p "${STAGE_DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${STAGE_DIR}/usr/share/icons/Nebula"
mkdir -p "${STAGE_DIR}/usr/share/pixmaps"

# Control file
cat <<EOF > "${STAGE_DIR}/DEBIAN/control"
Package: nebula-desktop
Version: ${NEW_VER}
Section: gnome
Priority: optional
Architecture: all
Depends: gnome-shell, nautilus, python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Maintainer: NebulaOS Team <support@nebulaos.org>
Description: NebulaOS core desktop experience, branding, recovery, and GNOME Shell integration.
 This package provides the latest official NebulaOS desktop configuration,
 including silent bootloader settings, FreeDesktop launcher, setup installer,
 recovery environment, and squircle branding assets.
EOF

# Postinst hook
cat <<'POSTINST_EOF' > "${STAGE_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e

# Compile GSettings schemas
if [ -x /usr/bin/glib-compile-schemas ]; then
    /usr/bin/glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
fi

# Update desktop application database
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database /usr/share/applications 2>/dev/null || true
fi

# Update icon caches
for theme in Nebula hicolor Adwaita; do
    if [ -d "/usr/share/icons/$theme" ] && [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -f -t "/usr/share/icons/$theme" 2>/dev/null || true
    fi
done

# Ensure mime associations for desktop launcher
for mf in /etc/xdg/mimeapps.list /usr/share/applications/mimeapps.list; do
    if [ -f "$mf" ]; then
        if ! grep -q "application/x-desktop" "$mf"; then
            sed -i '/\[Default Applications\]/a application/x-desktop=nebula-desktop-launcher.desktop' "$mf" 2>/dev/null || true
            sed -i '/\[Added Associations\]/a application/x-desktop=nebula-desktop-launcher.desktop;' "$mf" 2>/dev/null || true
        fi
    fi
done

# Clear user thumbnail cache for instant refresh
rm -rf /home/*/.cache/thumbnails/ 2>/dev/null || true

# Ensure LOGO=nebulaos-symbol in os-release
for osf in /etc/os-release /usr/lib/os-release; do
    if [ -f "$osf" ]; then
        if grep -q "^LOGO=" "$osf"; then
            sed -i 's/^LOGO=.*/LOGO=nebulaos-symbol/' "$osf"
        else
            echo "LOGO=nebulaos-symbol" >> "$osf"
        fi
    fi
done

exit 0
POSTINST_EOF
chmod 755 "${STAGE_DIR}/DEBIAN/postinst"

# Copy System binaries and scripts
cp -f "${ROOT_DIR}/src/system/nebula-desktop-thumbnailer.py" "${STAGE_DIR}/usr/bin/nebula-desktop-thumbnailer"
chmod 755 "${STAGE_DIR}/usr/bin/nebula-desktop-thumbnailer"

cp -f "${ROOT_DIR}/src/system/nebula-desktop.thumbnailer" "${STAGE_DIR}/usr/share/thumbnailers/nebula-desktop.thumbnailer"
chmod 644 "${STAGE_DIR}/usr/share/thumbnailers/nebula-desktop.thumbnailer"

cp -f "${ROOT_DIR}/src/system/nebula-desktop-launcher" "${STAGE_DIR}/usr/bin/nebula-desktop-launcher"
chmod 755 "${STAGE_DIR}/usr/bin/nebula-desktop-launcher"

cp -f "${ROOT_DIR}/src/system/nebula-icon-wrapper.py" "${STAGE_DIR}/usr/lib/nebulaos/nebula-icon-wrapper.py"
chmod 755 "${STAGE_DIR}/usr/lib/nebulaos/nebula-icon-wrapper.py"

cp -f "${ROOT_DIR}/src/system/install-nebula" "${STAGE_DIR}/usr/bin/install-nebula"
chmod 755 "${STAGE_DIR}/usr/bin/install-nebula"

cp -f "${ROOT_DIR}/src/system/nebula-recovery" "${STAGE_DIR}/usr/bin/nebula-recovery"
chmod 755 "${STAGE_DIR}/usr/bin/nebula-recovery"

cp -f "${ROOT_DIR}/src/system/nebula-session-init" "${STAGE_DIR}/usr/bin/nebula-session-init"
chmod 755 "${STAGE_DIR}/usr/bin/nebula-session-init"

cp -f "${ROOT_DIR}/src/system/nebula-recovery-watcher.py" "${STAGE_DIR}/usr/lib/nebulaos/nebula-recovery-watcher.py"
chmod 755 "${STAGE_DIR}/usr/lib/nebulaos/nebula-recovery-watcher.py"

cp -f "${ROOT_DIR}/src/system/nebula-recovery-watcher.service" "${STAGE_DIR}/etc/systemd/system/nebula-recovery-watcher.service"
chmod 644 "${STAGE_DIR}/etc/systemd/system/nebula-recovery-watcher.service"

cp -f "${ROOT_DIR}/src/system/99_nebulaos.gschema.override" "${STAGE_DIR}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"
chmod 644 "${STAGE_DIR}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"

cp -f "${ROOT_DIR}/src/system/00_nebula_silent.cfg" "${STAGE_DIR}/etc/default/grub.d/00_nebula_silent.cfg"
chmod 644 "${STAGE_DIR}/etc/default/grub.d/00_nebula_silent.cfg"

# Copy Desktop entries
cp -f "${ROOT_DIR}/src/apps/desktop-entries/"*.desktop "${STAGE_DIR}/usr/share/applications/"
chmod 644 "${STAGE_DIR}/usr/share/applications/"*.desktop

# Copy Nebula Setup & Recovery apps
cp -r "${ROOT_DIR}/src/apps/nebula-setup/"* "${STAGE_DIR}/usr/share/nebula-setup/"
cp -r "${ROOT_DIR}/src/apps/nebula-recovery/"* "${STAGE_DIR}/usr/share/nebula-recovery/"
chmod -R 755 "${STAGE_DIR}/usr/share/nebula-setup/" "${STAGE_DIR}/usr/share/nebula-recovery/"

# Copy GNOME Shell extensions if present
if [ -d "${ROOT_DIR}/src/extensions" ]; then
    for ext in "${ROOT_DIR}/src/extensions/"*; do
        [ -d "${ext}" ] || continue
        ext_uuid="$(basename "${ext}")"
        mkdir -p "${STAGE_DIR}/usr/share/gnome-shell/extensions/${ext_uuid}"
        cp -r "${ext}/"* "${STAGE_DIR}/usr/share/gnome-shell/extensions/${ext_uuid}/"
    done
fi

# Copy Shell Effects
if [ -d "${ROOT_DIR}/src/system/nebula-shell-effects" ]; then
    mkdir -p "${STAGE_DIR}/usr/share/gnome-shell/extensions/nebula-shell-effects@nebulaos.org"
    cp -r "${ROOT_DIR}/src/system/nebula-shell-effects/"* "${STAGE_DIR}/usr/share/gnome-shell/extensions/nebula-shell-effects@nebulaos.org/"
fi

# Copy branding symbols & logos (both SVG and PNG across themes and pixmaps)
LOGOS_DIR="${ROOT_DIR}/src/branding/logos"
mkdir -p "${STAGE_DIR}/usr/share/pixmaps"
for logo_name in nebulaos-symbol debian-logo debian-swirl distributor-logo system-logo; do
    cp -f "${LOGOS_DIR}/nebulaos-symbol.svg" "${STAGE_DIR}/usr/share/pixmaps/${logo_name}.svg"
    cp -f "${LOGOS_DIR}/nebulaos-symbol.png" "${STAGE_DIR}/usr/share/pixmaps/${logo_name}.png"
done

for theme in hicolor Nebula Adwaita; do
    mkdir -p "${STAGE_DIR}/usr/share/icons/${theme}/scalable/apps"
    for logo_name in nebulaos-symbol debian-logo debian-swirl distributor-logo system-logo; do
        cp -f "${LOGOS_DIR}/nebulaos-symbol.svg" "${STAGE_DIR}/usr/share/icons/${theme}/scalable/apps/${logo_name}.svg"
    done
    for sz in 16 22 24 32 48 64 96 128 256; do
        mkdir -p "${STAGE_DIR}/usr/share/icons/${theme}/${sz}x${sz}/apps"
        sized_src="${LOGOS_DIR}/nebulaos-symbol-${sz}.png"
        [ -f "${sized_src}" ] || sized_src="${LOGOS_DIR}/nebulaos-symbol.png"
        for logo_name in nebulaos-symbol debian-logo debian-swirl distributor-logo system-logo; do
            cp -f "${sized_src}" "${STAGE_DIR}/usr/share/icons/${theme}/${sz}x${sz}/apps/${logo_name}.png"
        done
    done
done

# Build .deb package
DEB_NAME="nebula-desktop_${NEW_VER}_all.deb"
DEB_PATH="${OTA_OUTPUT_DIR}/${DEB_NAME}"

dpkg-deb --build --root-owner-group "${STAGE_DIR}" "${DEB_PATH}"
echo "[deb] Generated package: ${DEB_PATH}"

# Copy to updates subfolder as well
cp -f "${DEB_PATH}" "${UPDATES_SUBDIR}/${DEB_NAME}"

# Clean stage
rm -rf "${STAGE_DIR}"

# ── 4. Generate APT Repository Metadata (Packages, Packages.gz, Release) ──────

echo "[apt] Generating repository metadata..."

generate_apt_repo() {
    local TARGET_DIR="$1"
    cd "${TARGET_DIR}"

    # Generate Packages file using dpkg-scanpackages or python fallback
    if command -v dpkg-scanpackages >/dev/null 2>&1; then
        dpkg-scanpackages -m . /dev/null > Packages
    else
        python3 - << 'PYEOF'
import os, glob, hashlib, subprocess
with open("Packages", "w") as out:
    for deb in sorted(glob.glob("*.deb")):
        ctrl = subprocess.run(["dpkg-deb", "-I", deb, "control"], capture_output=True, text=True)
        size = os.path.getsize(deb)
        with open(deb, "rb") as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()
            sha256 = hashlib.sha256(data).hexdigest()
        out.write(ctrl.stdout.strip() + "\n")
        out.write(f"Filename: ./{deb}\n")
        out.write(f"Size: {size}\n")
        out.write(f"MD5sum: {md5}\n")
        out.write(f"SHA256: {sha256}\n\n")
PYEOF
    fi

    gzip -9c Packages > Packages.gz

    # Calculate checksums for Release
    P_MD5="$(md5sum Packages | awk '{print $1}')"
    P_SIZE="$(stat -c %s Packages)"
    P_SHA256="$(sha256sum Packages | awk '{print $1}')"

    PGZ_MD5="$(md5sum Packages.gz | awk '{print $1}')"
    PGZ_SIZE="$(stat -c %s Packages.gz)"
    PGZ_SHA256="$(sha256sum Packages.gz | awk '{print $1}')"

    cat <<REL_EOF > Release
Archive: stable
Component: main
Origin: NebulaOS
Label: NebulaOS Official Updates
Architecture: all amd64
Version: ${NEW_VER}
Date: ${RFC_DATE}
MD5Sum:
 ${P_MD5} ${P_SIZE} Packages
 ${PGZ_MD5} ${PGZ_SIZE} Packages.gz
SHA256:
 ${P_SHA256} ${P_SIZE} Packages
 ${PGZ_SHA256} ${PGZ_SIZE} Packages.gz
REL_EOF
}

generate_apt_repo "${OTA_OUTPUT_DIR}"
generate_apt_repo "${UPDATES_SUBDIR}"

# ── 5. Generate ota.json Metadata for Fast System Querying ─────────────────────

DEB_SHA256="$(sha256sum "${DEB_PATH}" | awk '{print $1}')"
DEB_SIZE="$(stat -c %s "${DEB_PATH}")"

cat <<JSON_EOF > "${OTA_OUTPUT_DIR}/ota.json"
{
  "latest_version": "${NEW_VER}",
  "release_date": "${RELEASE_DATE}",
  "changelog": "${CHANGELOG}",
  "package": {
    "name": "nebula-desktop",
    "filename": "${DEB_NAME}",
    "version": "${NEW_VER}",
    "sha256": "${DEB_SHA256}",
    "size_bytes": ${DEB_SIZE}
  }
}
JSON_EOF
cp -f "${OTA_OUTPUT_DIR}/ota.json" "${UPDATES_SUBDIR}/ota.json"

echo "=============================================================================="
echo " OTA Update ${NEW_VER} Successfully Created in ota_updates/!"
echo " Package   : ${DEB_PATH} (${DEB_SIZE} bytes)"
echo " SHA256    : ${DEB_SHA256}"
echo " Repository: Packages, Packages.gz, Release, ota.json generated."
echo "=============================================================================="
