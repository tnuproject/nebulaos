#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUILD_DIR="/tmp/ota_build"
OUTPUT_DIR="${ROOT_DIR}/build/debs"
UPDATES_DIR="${ROOT_DIR}/webserver/updates"

mkdir -p "${OUTPUT_DIR}" "${UPDATES_DIR}"

build_deb() {
    local PKG_VERSION="$1"
    local PKG_STAGE="${BUILD_DIR}/nebula-desktop_${PKG_VERSION}"
    rm -rf "${PKG_STAGE}"
    mkdir -p "${PKG_STAGE}/DEBIAN"
    mkdir -p "${PKG_STAGE}/usr/bin"
    mkdir -p "${PKG_STAGE}/usr/share/thumbnailers"
    mkdir -p "${PKG_STAGE}/usr/share/applications"
    mkdir -p "${PKG_STAGE}/usr/share/glib-2.0/schemas"
    mkdir -p "${PKG_STAGE}/etc/default/grub.d"
    mkdir -p "${PKG_STAGE}/etc/xdg"
    mkdir -p "${PKG_STAGE}/usr/share/icons/hicolor/scalable/apps"
    mkdir -p "${PKG_STAGE}/usr/share/icons/Nebula/scalable/apps"
    mkdir -p "${PKG_STAGE}/usr/share/pixmaps"

    cat <<EOF > "${PKG_STAGE}/DEBIAN/control"
Package: nebula-desktop
Version: ${PKG_VERSION}
Section: gnome
Priority: optional
Architecture: all
Depends: gnome-shell, nautilus, python3, python3-gi, gir1.2-gtk-3.0
Maintainer: NebulaOS Team <support@nebulaos.org>
Description: NebulaOS desktop configuration, silent boot, branding, and shell integration.
 This package provides core NebulaOS desktop customizations including
 silent GRUB bootloader settings, FreeDesktop .desktop thumbnailer and
 launcher, window control layout overrides, and official system branding logos.
EOF

    cat <<'EOF' > "${PKG_STAGE}/DEBIAN/postinst"
#!/bin/sh
set -e

# Compile schemas
if [ -x /usr/bin/glib-compile-schemas ]; then
    /usr/bin/glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
fi

# Update desktop database
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database /usr/share/applications 2>/dev/null || true
fi

# Update icon caches
for theme in Nebula hicolor Adwaita; do
    if [ -d "/usr/share/icons/$theme" ] && [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -f -t "/usr/share/icons/$theme" 2>/dev/null || true
    fi
done

# Set OS logo in os-release
for osf in /etc/os-release /usr/lib/os-release; do
    if [ -f "$osf" ]; then
        if grep -q "^LOGO=" "$osf"; then
            sed -i 's/^LOGO=.*/LOGO=nebulaos-symbol/' "$osf"
        else
            echo "LOGO=nebulaos-symbol" >> "$osf"
        fi
    fi
done

# Ensure mime associations for .desktop launcher
for mf in /etc/xdg/mimeapps.list /usr/share/applications/mimeapps.list; do
    if [ -f "$mf" ]; then
        if ! grep -q "application/x-desktop" "$mf"; then
            sed -i '/\[Default Applications\]/a application/x-desktop=nebula-desktop-launcher.desktop' "$mf" 2>/dev/null || true
            sed -i '/\[Added Associations\]/a application/x-desktop=nebula-desktop-launcher.desktop;' "$mf" 2>/dev/null || true
        fi
    fi
done

# Silence GRUB bootloader
if [ -f /etc/grub.d/10_linux ]; then
    sed -i 's/quiet_boot="0"/quiet_boot="1"/' /etc/grub.d/10_linux
    sed -i "s/echo[[:space:]]\+'\$(echo \"\$message\" | grub_quote)'/:/g" /etc/grub.d/10_linux 2>/dev/null || true
fi
if [ -f /etc/grub.d/00_header ]; then
    sed -i 's/quick_boot="0"/quick_boot="1"/' /etc/grub.d/00_header
fi

# Remove textual echoes from existing grub.cfg files
if [ -f /boot/grub/grub.cfg ]; then
    sed -i "/echo[[:space:]]*['\"].*Loading/d" /boot/grub/grub.cfg 2>/dev/null || true
    sed -i "/echo[[:space:]]*['\"].*Launching/d" /boot/grub/grub.cfg 2>/dev/null || true
fi
find /boot/efi -name "grub.cfg" -exec sed -i "/echo[[:space:]]*['\"].*Loading/d" {} + 2>/dev/null || true
find /boot/efi -name "grub.cfg" -exec sed -i "/echo[[:space:]]*['\"].*Launching/d" {} + 2>/dev/null || true

if [ -x /usr/sbin/update-grub ]; then
    /usr/sbin/update-grub 2>/dev/null || true
fi

# Clear thumbnail cache for users so Nautilus re-renders .desktop previews immediately
rm -rf /home/*/.cache/thumbnails/ 2>/dev/null || true

# Record OTA update pending for first-boot notification
mkdir -p /var/lib/nebulaos
echo "${PKG_VERSION}" > /var/lib/nebulaos/ota_update_pending
chmod 666 /var/lib/nebulaos/ota_update_pending 2>/dev/null || true

exit 0
EOF
    chmod 755 "${PKG_STAGE}/DEBIAN/postinst"

    # Copy files
    cp -f "${ROOT_DIR}/src/system/nebula-desktop-thumbnailer.py" "${PKG_STAGE}/usr/bin/nebula-desktop-thumbnailer"
    chmod 755 "${PKG_STAGE}/usr/bin/nebula-desktop-thumbnailer"

    cp -f "${ROOT_DIR}/src/system/nebula-desktop.thumbnailer" "${PKG_STAGE}/usr/share/thumbnailers/nebula-desktop.thumbnailer"
    chmod 644 "${PKG_STAGE}/usr/share/thumbnailers/nebula-desktop.thumbnailer"

    cp -f "${ROOT_DIR}/src/system/nebula-desktop-launcher" "${PKG_STAGE}/usr/bin/nebula-desktop-launcher"
    chmod 755 "${PKG_STAGE}/usr/bin/nebula-desktop-launcher"

    cp -f "${ROOT_DIR}/src/system/nebula-welcome-launcher" "${PKG_STAGE}/usr/bin/nebula-welcome-launcher"
    chmod 755 "${PKG_STAGE}/usr/bin/nebula-welcome-launcher"

    cp -f "${ROOT_DIR}/src/apps/desktop-entries/nebula-desktop-launcher.desktop" "${PKG_STAGE}/usr/share/applications/nebula-desktop-launcher.desktop"
    chmod 644 "${PKG_STAGE}/usr/share/applications/nebula-desktop-launcher.desktop"

    cp -f "${ROOT_DIR}/src/system/99_nebulaos.gschema.override" "${PKG_STAGE}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"
    chmod 644 "${PKG_STAGE}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"

    cp -f "${ROOT_DIR}/src/system/00_nebula_silent.cfg" "${PKG_STAGE}/etc/default/grub.d/00_nebula_silent.cfg"
    chmod 644 "${PKG_STAGE}/etc/default/grub.d/00_nebula_silent.cfg"

    cp -f "${ROOT_DIR}/src/branding/logos/nebulaos-symbol.svg" "${PKG_STAGE}/usr/share/icons/hicolor/scalable/apps/nebulaos-symbol.svg"
    cp -f "${ROOT_DIR}/src/branding/logos/nebulaos-symbol.svg" "${PKG_STAGE}/usr/share/icons/Nebula/scalable/apps/nebulaos-symbol.svg"
    cp -f "${ROOT_DIR}/src/branding/logos/nebulaos-symbol.svg" "${PKG_STAGE}/usr/share/pixmaps/nebulaos-symbol.svg"
    chmod 644 "${PKG_STAGE}/usr/share/icons/hicolor/scalable/apps/nebulaos-symbol.svg" \
              "${PKG_STAGE}/usr/share/icons/Nebula/scalable/apps/nebulaos-symbol.svg" \
              "${PKG_STAGE}/usr/share/pixmaps/nebulaos-symbol.svg"

    dpkg-deb --build --root-owner-group "${PKG_STAGE}" "${OUTPUT_DIR}/nebula-desktop_${PKG_VERSION}_all.deb"
    echo "Built: ${OUTPUT_DIR}/nebula-desktop_${PKG_VERSION}_all.deb"
}

echo "=== [1/3] Building nebula-desktop debian package ==="
# DEB_VERSION is set by the CI workflow (e.g. 26.0~rev3 for delta, 26.0 for stable).
# Fall back to reading release.conf for local builds.
if [ -z "${DEB_VERSION:-}" ]; then
    source "${ROOT_DIR}/src/release/release.conf"
    DEB_VERSION="${VERSION}"
fi
build_deb "${DEB_VERSION}"

echo "=== [2/3] Setting up APT repository in ${UPDATES_DIR} ==="
cp -f "${OUTPUT_DIR}/nebula-desktop_${DEB_VERSION}_all.deb" "${UPDATES_DIR}/"

cd "${UPDATES_DIR}"
# Scan packages for flat repository
dpkg-scanpackages . /dev/null > Packages
gzip -9c Packages > Packages.gz

# Generate Release file
DATE_STR="$(date -Ru)"
PKG_MD5="$(md5sum Packages | awk '{print $1}')"
PKG_SIZE="$(stat -c %s Packages)"
PKG_GZ_MD5="$(md5sum Packages.gz | awk '{print $1}')"
PKG_GZ_SIZE="$(stat -c %s Packages.gz)"

PKG_SHA256="$(sha256sum Packages | awk '{print $1}')"
PKG_GZ_SHA256="$(sha256sum Packages.gz | awk '{print $1}')"

cat <<EOF > Release
Archive: stable
Component: main
Origin: NebulaOS
Label: NebulaOS Updates
Architecture: all amd64
Date: ${DATE_STR}
MD5Sum:
 ${PKG_MD5} ${PKG_SIZE} Packages
 ${PKG_GZ_MD5} ${PKG_GZ_SIZE} Packages.gz
SHA256:
 ${PKG_SHA256} ${PKG_SIZE} Packages
 ${PKG_GZ_SHA256} ${PKG_GZ_SIZE} Packages.gz
EOF

# Also copy to root of webserver so both https://<host>/updates/ and https://<host>/ work
cp -f "${UPDATES_DIR}/Packages" "${ROOT_DIR}/webserver/Packages" 2>/dev/null || true
cp -f "${UPDATES_DIR}/Packages.gz" "${ROOT_DIR}/webserver/Packages.gz" 2>/dev/null || true
cp -f "${UPDATES_DIR}/Release" "${ROOT_DIR}/webserver/Release" 2>/dev/null || true
cp -f "${UPDATES_DIR}/nebula-desktop_${DEB_VERSION}_all.deb" "${ROOT_DIR}/webserver/nebula-desktop_${DEB_VERSION}_all.deb" 2>/dev/null || true

echo "=== [3/3] OTA Repository Ready! ==="
echo "Files generated in ${UPDATES_DIR}:"
ls -la "${UPDATES_DIR}"
