#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Debian Base System Builder (GNOME + Wayland + GDM3)
# Features:
# - GNOME Desktop Environment + Mutter (Wayland) + GDM3 (Automatic Login)
# - /Applications drag-and-drop daemon (nebula-appd)
# - Custom Graphical Installer (with user, language, keyboard & self-removal)
# - Native App Store connected to https://tnu-universe.it/
# - Restore Utility (Btrfs snapshots & rollback)
# - Hatter official icon theme integration
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

CHROOT_DIR="/tmp/nebulaos-chroot"
LIVE_DIR="${ROOT_DIR}/build/live"
ISO_ROOT="${ROOT_DIR}/build/iso_root"

echo "=============================================================================="
echo " Building Debian GNOME/Wayland Base for ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

# 1. Clean previous chroot mounts if any
if [ -d "${CHROOT_DIR}" ]; then
    echo "[base] Cleaning up previous chroot..."
    umount -lf "${CHROOT_DIR}/dev/pts" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/dev" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/proc" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/sys" 2>/dev/null || true
    rm -rf "${CHROOT_DIR}"
fi

mkdir -p "${CHROOT_DIR}"

# 2. Debootstrap Debian Bookworm Base System
echo "[base] Running debootstrap for Debian Bookworm..."
debootstrap \
    --arch=amd64 \
    --variant=minbase \
    --include=linux-image-amd64,live-boot,live-config,live-config-systemd,systemd,systemd-sysv,udev,sudo,curl,ca-certificates,python3,btrfs-progs,plymouth,plymouth-themes,locales,kbd,kmod \
    bookworm \
    "${CHROOT_DIR}" \
    http://deb.debian.org/debian

# 3. Mount virtual filesystems for chroot operations
echo "[base] Mounting proc, sys, dev in chroot..."
mount --bind /dev "${CHROOT_DIR}/dev"
mount --bind /dev/pts "${CHROOT_DIR}/dev/pts"
mount -t proc proc "${CHROOT_DIR}/proc"
mount -t sysfs sysfs "${CHROOT_DIR}/sys"

cleanup() {
    echo "[base] Cleaning chroot mounts..."
    umount -lf "${CHROOT_DIR}/dev/pts" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/dev" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/proc" 2>/dev/null || true
    umount -lf "${CHROOT_DIR}/sys" 2>/dev/null || true
}
trap cleanup EXIT

# 4. Configure APT sources
cat <<'EOF' > "${CHROOT_DIR}/etc/apt/sources.list"
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
EOF

# 5. Install GNOME Core, Default Applications, Hardware Drivers, and Libraries
echo "[base] Installing GNOME Core, Firefox, Default GNOME Apps, Firmware, and GTK libraries..."
export DEBIAN_FRONTEND=noninteractive
chroot "${CHROOT_DIR}" apt-get update
chroot "${CHROOT_DIR}" apt-get install -y --no-install-recommends \
    gdm3 gnome-session gnome-shell mutter nautilus gnome-terminal dbus network-manager network-manager-gnome \
    gnome-control-center gnome-control-center-data \
    gnome-shell-extension-dashtodock \
    firefox-esr gnome-calculator gnome-text-editor gnome-disk-utility gnome-system-monitor gnome-weather \
    epiphany-browser gnome-software gnome-calendar cheese gnome-contacts gnome-calls geary gnome-music totem \
    gnome-keyring libpam-gnome-keyring policykit-1-gnome libsecret-1-0 libsecret-tools \
    evince eog file-roller libnotify-bin parted dosfstools btrfs-progs rsync squashfs-tools \
    grub-efi-amd64 grub-pc-bin \
    x11-xserver-utils \
    python3-gi gir1.2-gtk-3.0 xwayland libglib2.0-bin adwaita-icon-theme \
    librsvg2-common fonts-cantarell fonts-dejavu-core \
    firmware-linux-free firmware-linux-nonfree firmware-misc-nonfree firmware-amd-graphics firmware-iwlwifi firmware-realtek \
    firmware-atheros firmware-brcm80211 firmware-libertas firmware-sof-signed firmware-netxen firmware-bnx2 firmware-bnx2x \
    wireless-regdb wpasupplicant wireless-tools bluez bluez-firmware pulseaudio-utils \
    mesa-va-drivers mesa-vdpau-drivers mesa-vulkan-drivers pciutils usbutils xserver-xorg-video-all \
    xserver-xorg-video-intel xserver-xorg-video-amdgpu xserver-xorg-video-nouveau

# Configure live-config defaults
mkdir -p "${CHROOT_DIR}/etc/live"
cat <<'EOF' > "${CHROOT_DIR}/etc/live/config.conf"
LIVE_USERNAME="nebula"
LIVE_USER_DEFAULT_GROUPS="sudo,audio,video,plugdev,netdev"
LIVE_HOSTNAME="nebulaos"
EOF

# Configure Global GTK Dark Theme Defaults
mkdir -p "${CHROOT_DIR}/etc/gtk-3.0" "${CHROOT_DIR}/etc/gtk-4.0"
cat <<'EOF' > "${CHROOT_DIR}/etc/gtk-3.0/settings.ini"
[Settings]
gtk-theme-name = Adwaita-dark
gtk-icon-theme-name = Nebula
gtk-font-name = Cantarell 11
gtk-application-prefer-dark-theme = 1
EOF
cp "${CHROOT_DIR}/etc/gtk-3.0/settings.ini" "${CHROOT_DIR}/etc/gtk-4.0/settings.ini"

# 6. Configure GDM3 for Wayland and Automatic Login to live user 'nebula'
echo "[base] Configuring GDM3 automatic login for live session..."
mkdir -p "${CHROOT_DIR}/etc/gdm3"
cat <<'EOF' > "${CHROOT_DIR}/etc/gdm3/daemon.conf"
[daemon]
AutomaticLoginEnable = true
AutomaticLogin = nebula
WaylandEnable = true

[security]

[xdmcp]

[chooser]

[debug]
EOF

# Configure PAM for GDM autologin with gnome-keyring
if [ -f "${CHROOT_DIR}/etc/pam.d/gdm-autologin" ]; then
    if ! grep -q "pam_gnome_keyring.so" "${CHROOT_DIR}/etc/pam.d/gdm-autologin"; then
        echo "auth optional pam_gnome_keyring.so" >> "${CHROOT_DIR}/etc/pam.d/gdm-autologin"
        echo "session optional pam_gnome_keyring.so auto_start" >> "${CHROOT_DIR}/etc/pam.d/gdm-autologin"
    fi
fi

# Deploy Polkit Security Rules for NetworkManager and Sudo
mkdir -p "${CHROOT_DIR}/etc/polkit-1/rules.d"
cp "${ROOT_DIR}/src/system/50-org.freedesktop.NetworkManager.rules" "${CHROOT_DIR}/etc/polkit-1/rules.d/50-org.freedesktop.NetworkManager.rules"
cp "${ROOT_DIR}/src/system/49-nopasswd_admin.rules" "${CHROOT_DIR}/etc/polkit-1/rules.d/49-nopasswd_admin.rules"
chmod 644 "${CHROOT_DIR}/etc/polkit-1/rules.d/"*.rules

# 7. Configure Network, Hostname, and Locales
echo "nebulaos" > "${CHROOT_DIR}/etc/hostname"
cat <<'EOF' > "${CHROOT_DIR}/etc/hosts"
127.0.0.1   localhost nebulaos
::1         localhost ip6-localhost ip6-loopback
EOF

cat <<'EOF' > "${CHROOT_DIR}/etc/locale.gen"
en_US.UTF-8 UTF-8
it_IT.UTF-8 UTF-8
EOF
chroot "${CHROOT_DIR}" locale-gen

# Ensure networking directory for live-boot
mkdir -p "${CHROOT_DIR}/etc/network"
cat <<'EOF' > "${CHROOT_DIR}/etc/network/interfaces"
auto lo
iface lo inet loopback
EOF

# Disable Wi-Fi power saving to ensure full speed (prevents 200-300 kb/s throttle)
mkdir -p "${CHROOT_DIR}/etc/NetworkManager/conf.d"
cat <<'EOF' > "${CHROOT_DIR}/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf"
[connection]
wifi.powersave = 2
EOF

# 8. Create Live User 'nebula' with passwordless sudo & desktop folder
echo "[base] Creating live user 'nebula'..."
chroot "${CHROOT_DIR}" bash -c "useradd -m -s /bin/bash -G sudo,audio,video,plugdev,netdev nebula || true"
echo "nebula:nebula" | chroot "${CHROOT_DIR}" chpasswd
echo "nebula ALL=(ALL) NOPASSWD: ALL" > "${CHROOT_DIR}/etc/sudoers.d/nebula"
chmod 0440 "${CHROOT_DIR}/etc/sudoers.d/nebula"
mkdir -p "${CHROOT_DIR}/home/nebula/Desktop"

# Pre-configure User GTK Dark Theme Defaults
mkdir -p "${CHROOT_DIR}/home/nebula/.config/gtk-3.0" "${CHROOT_DIR}/home/nebula/.config/gtk-4.0"
cp "${CHROOT_DIR}/etc/gtk-3.0/settings.ini" "${CHROOT_DIR}/home/nebula/.config/gtk-3.0/settings.ini"
cp "${CHROOT_DIR}/etc/gtk-3.0/settings.ini" "${CHROOT_DIR}/home/nebula/.config/gtk-4.0/settings.ini"

mkdir -p "${CHROOT_DIR}/etc/skel/.config/gtk-3.0" "${CHROOT_DIR}/etc/skel/.config/gtk-4.0"
cp "${CHROOT_DIR}/etc/gtk-3.0/settings.ini" "${CHROOT_DIR}/etc/skel/.config/gtk-3.0/settings.ini"
cp "${CHROOT_DIR}/etc/gtk-3.0/settings.ini" "${CHROOT_DIR}/etc/skel/.config/gtk-4.0/settings.ini"

# 9. Configure /Applications directory
echo "[base] Setting up /Applications folder..."
mkdir -p "${CHROOT_DIR}/Applications"
chmod -R 777 "${CHROOT_DIR}/Applications"

# 10. Install neb Package Manager
echo "[base] Installing neb package manager..."
cp "${ROOT_DIR}/src/package-manager/bin/neb" "${CHROOT_DIR}/usr/bin/neb"
chmod 755 "${CHROOT_DIR}/usr/bin/neb"

# 11. Install System Helpers, Installer, and Apps Synchronizer
echo "[base] Installing System Helpers, Installer, and Apps Synchronizer..."
mkdir -p "${CHROOT_DIR}/usr/share/nebula-setup/screens" \
         "${CHROOT_DIR}/usr/share/nebula-setup/backend" \
         "${CHROOT_DIR}/usr/share/nebula-setup/ui"

# Deploy nebula-setup Custom Installer
cp -f "${ROOT_DIR}/src/apps/nebula-setup/nebula-setup.py" "${CHROOT_DIR}/usr/share/nebula-setup/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/screens/"*.py "${CHROOT_DIR}/usr/share/nebula-setup/screens/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/backend/"*.py "${CHROOT_DIR}/usr/share/nebula-setup/backend/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/ui/"*.py "${CHROOT_DIR}/usr/share/nebula-setup/ui/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/ui/styles.css" "${CHROOT_DIR}/usr/share/nebula-setup/ui/"
chmod -R 755 "${CHROOT_DIR}/usr/share/nebula-setup/"
chmod 644 "${CHROOT_DIR}/usr/share/nebula-setup/ui/styles.css"

# Installer Launchers
cp "${ROOT_DIR}/src/system/install-nebula" "${CHROOT_DIR}/usr/bin/install-nebula"
chmod 755 "${CHROOT_DIR}/usr/bin/install-nebula"
ln -sf /usr/bin/install-nebula "${CHROOT_DIR}/usr/bin/nebula-installer"
mkdir -p "${CHROOT_DIR}/usr/lib/nebulaos"
cp "${ROOT_DIR}/src/system/post-install-cleanup.sh" "${CHROOT_DIR}/usr/lib/nebulaos/post-install-cleanup.sh"
chmod 755 "${CHROOT_DIR}/usr/lib/nebulaos/post-install-cleanup.sh"

# Install Software Helper (.deb installer)
cp "${ROOT_DIR}/src/system/install-software.py" "${CHROOT_DIR}/usr/bin/install-software"
chmod 755 "${CHROOT_DIR}/usr/bin/install-software"

# Deploy MyNebula Desktop Companion App
mkdir -p "${CHROOT_DIR}/usr/share/mynebula-desktop"
cp -f "${ROOT_DIR}/src/apps/mynebula-desktop/mynebula.py" "${CHROOT_DIR}/usr/share/mynebula-desktop/mynebula.py"
chmod 755 "${CHROOT_DIR}/usr/share/mynebula-desktop/mynebula.py"
ln -sf /usr/share/mynebula-desktop/mynebula.py "${CHROOT_DIR}/usr/bin/mynebula"

# Applications Directory & GNOME Grid Synchronizer Daemon
cp "${ROOT_DIR}/src/system/nebula-apps-sync.py" "${CHROOT_DIR}/usr/lib/nebulaos/nebula-apps-sync.py"
chmod 755 "${CHROOT_DIR}/usr/lib/nebulaos/nebula-apps-sync.py"
mkdir -p "${CHROOT_DIR}/usr/lib/systemd/user"
cp "${ROOT_DIR}/src/system/nebula-apps-sync.service" "${CHROOT_DIR}/usr/lib/systemd/user/nebula-apps-sync.service"
mkdir -p "${CHROOT_DIR}/etc/systemd/user/default.target.wants"
ln -sf /usr/lib/systemd/user/nebula-apps-sync.service "${CHROOT_DIR}/etc/systemd/user/default.target.wants/nebula-apps-sync.service"

# Nebula Companion Daemon & Picture Organizer (PetalDrop & Cloud Gallery)
mkdir -p "${CHROOT_DIR}/usr/lib/nebulaos"
cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-companion.py" "${CHROOT_DIR}/usr/lib/nebulaos/nebula-companion.py"
cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-picture-organizer.py" "${CHROOT_DIR}/usr/lib/nebulaos/nebula-picture-organizer.py"
chmod 755 "${CHROOT_DIR}/usr/lib/nebulaos/nebula-companion.py" "${CHROOT_DIR}/usr/lib/nebulaos/nebula-picture-organizer.py"

cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-companion.service" "${CHROOT_DIR}/etc/systemd/user/nebula-companion.service"
cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-picture-organizer.service" "${CHROOT_DIR}/etc/systemd/user/nebula-picture-organizer.service"
chmod 644 "${CHROOT_DIR}/etc/systemd/user/"*.service

ln -sf /etc/systemd/user/nebula-companion.service "${CHROOT_DIR}/etc/systemd/user/default.target.wants/nebula-companion.service"
ln -sf /etc/systemd/user/nebula-picture-organizer.service "${CHROOT_DIR}/etc/systemd/user/default.target.wants/nebula-picture-organizer.service"

# Install Desktop entries
mkdir -p "${CHROOT_DIR}/usr/share/applications"
cp "${ROOT_DIR}/src/apps/desktop-entries/"*.desktop "${CHROOT_DIR}/usr/share/applications/"

# Place "Install Nebula" directly on the live user's desktop
cp "${ROOT_DIR}/src/apps/desktop-entries/installer.desktop" "${CHROOT_DIR}/home/nebula/Desktop/installer.desktop"
chmod 755 "${CHROOT_DIR}/home/nebula/Desktop/installer.desktop"
chroot "${CHROOT_DIR}" chown -R nebula:nebula /home/nebula
chroot "${CHROOT_DIR}" su - nebula -c "gio set -t string /home/nebula/Desktop/installer.desktop metadata::trusted true 2>/dev/null || true"

# 12. Integrate Nebula Squircle Icon Pack
echo "[base] Generating and integrating Nebula icon pack..."
python3 "${ROOT_DIR}/scripts/generate_nebula_icons.py"
mkdir -p "${CHROOT_DIR}/usr/share/icons/Nebula"
cp -r "${ROOT_DIR}/src/branding/icons/Nebula/"* "${CHROOT_DIR}/usr/share/icons/Nebula/"
chroot "${CHROOT_DIR}" gtk-update-icon-cache -f -t /usr/share/icons/Nebula 2>/dev/null || true
chroot "${CHROOT_DIR}" gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# 13. GNOME Desktop Theme & Behavior Overrides
echo "[base] Configuring GNOME styling and Nebula icon theme defaults..."
mkdir -p "${CHROOT_DIR}/usr/share/glib-2.0/schemas"
rm -f "${CHROOT_DIR}/usr/share/glib-2.0/schemas/"*gnome-shell.gschema.override 2>/dev/null || true
cp "${ROOT_DIR}/src/system/99_nebulaos.gschema.override" "${CHROOT_DIR}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"
chroot "${CHROOT_DIR}" glib-compile-schemas /usr/share/glib-2.0/schemas

# Register Default MIME handler for .deb packages to install-software
mkdir -p "${CHROOT_DIR}/usr/share/applications" "${CHROOT_DIR}/etc/xdg" "${CHROOT_DIR}/etc/skel/.config" "${CHROOT_DIR}/home/nebula/.config"
cat <<'EOF' > "${CHROOT_DIR}/etc/xdg/mimeapps.list"
[Default Applications]
application/vnd.debian.binary-package=install-software.desktop
application/x-deb=install-software.desktop
application/x-debian-package=install-software.desktop
application/x-desktop=nebula-desktop-launcher.desktop
image/jpeg=nebula-gallery.desktop
image/png=nebula-gallery.desktop
image/gif=nebula-gallery.desktop
image/webp=nebula-gallery.desktop
image/bmp=nebula-gallery.desktop
image/tiff=nebula-gallery.desktop
image/svg+xml=nebula-gallery.desktop

[Added Associations]
application/vnd.debian.binary-package=install-software.desktop;
application/x-deb=install-software.desktop;
application/x-debian-package=install-software.desktop;
application/x-desktop=nebula-desktop-launcher.desktop;
image/jpeg=nebula-gallery.desktop;
image/png=nebula-gallery.desktop;
image/gif=nebula-gallery.desktop;
image/webp=nebula-gallery.desktop;
image/bmp=nebula-gallery.desktop;
image/tiff=nebula-gallery.desktop;
image/svg+xml=nebula-gallery.desktop;
EOF

cp "${CHROOT_DIR}/etc/xdg/mimeapps.list" "${CHROOT_DIR}/usr/share/applications/mimeapps.list"
cp "${CHROOT_DIR}/etc/xdg/mimeapps.list" "${CHROOT_DIR}/etc/skel/.config/mimeapps.list"
cp "${CHROOT_DIR}/etc/xdg/mimeapps.list" "${CHROOT_DIR}/home/nebula/.config/mimeapps.list"
chroot "${CHROOT_DIR}" chown -R nebula:nebula /home/nebula/.config 2>/dev/null || true

# Strip deb mimetypes from file-roller so it never claims them over install-software
for fr in "${CHROOT_DIR}/usr/share/applications/org.gnome.FileRoller.desktop" "${CHROOT_DIR}/usr/share/applications/file-roller.desktop"; do
    if [ -f "${fr}" ]; then
        sed -i 's/application\/vnd.debian.binary-package;//g' "${fr}"
        sed -i 's/application\/x-deb;//g' "${fr}"
        sed -i 's/application\/x-debian-package;//g' "${fr}"
    fi
done

chroot "${CHROOT_DIR}" update-desktop-database /usr/share/applications 2>/dev/null || true
chroot "${CHROOT_DIR}" su - nebula -c "gio mime application/vnd.debian.binary-package install-software.desktop 2>/dev/null || true"
chroot "${CHROOT_DIR}" su - nebula -c "gio mime application/x-deb install-software.desktop 2>/dev/null || true"
chroot "${CHROOT_DIR}" su - nebula -c "gio mime application/x-debian-package install-software.desktop 2>/dev/null || true"

# Configure NebulaOS Transparent Topbar & Floating Detached Dock Theme
mkdir -p "${CHROOT_DIR}/usr/share/themes/NebulaOS/gnome-shell" "${CHROOT_DIR}/usr/share/gnome-shell/theme"
cat <<'EOF' > "${CHROOT_DIR}/usr/share/themes/NebulaOS/gnome-shell/gnome-shell.css"
@import url("resource:///org/gnome/shell/theme/gnome-shell.css");

/* NebulaOS Transparent Topbar */
#panel {
    background-color: rgba(15, 23, 42, 0.25) !important;
    font-weight: 600;
    box-shadow: none !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}

#panel.solid {
    background-color: rgba(15, 23, 42, 0.70) !important;
}

#panel .panel-button:hover {
    background-color: rgba(255, 255, 255, 0.12) !important;
}

/* NebulaOS Floating Detached Dock (spaced from bottom edge) */
#dashtodockContainer.bottom {
    margin-bottom: 14px !important;
}
#dashtodockContainer.bottom .dash-bottom {
    margin-bottom: 14px !important;
}
EOF
cp "${CHROOT_DIR}/usr/share/themes/NebulaOS/gnome-shell/gnome-shell.css" "${CHROOT_DIR}/usr/share/gnome-shell/theme/gnome-shell.css"

# 14. Install Plymouth Theme & Assets (with script fixes)
echo "[base] Installing customized Plymouth boot splash theme..."
PLYMOUTH_SRC="${ROOT_DIR}/src/branding/plymouth/nebulaos-breeze"
PLYMOUTH_DEST="${CHROOT_DIR}/usr/share/plymouth/themes/nebulaos-breeze"
mkdir -p "${PLYMOUTH_DEST}"
cp -r "${PLYMOUTH_SRC}/"* "${PLYMOUTH_DEST}/"

chroot "${CHROOT_DIR}" plymouth-set-default-theme -R nebulaos-breeze 2>/dev/null || true

# 15. Install Wallpapers & Distributor Logos
echo "[base] Installing custom wallpapers and version logos..."
rm -rf "${CHROOT_DIR}/usr/share/backgrounds/gnome"* "${CHROOT_DIR}/usr/share/gnome-background-properties/gnome-backgrounds.xml" 2>/dev/null || true
mkdir -p "${CHROOT_DIR}/usr/share/backgrounds/nebula" "${CHROOT_DIR}/usr/share/gnome-background-properties"
cp -r "${ROOT_DIR}/src/branding/wallpapers/"* "${CHROOT_DIR}/usr/share/backgrounds/nebula/" 2>/dev/null || true
cp "${ROOT_DIR}/src/branding/wallpapers/nebula-wallpapers.xml" "${CHROOT_DIR}/usr/share/gnome-background-properties/nebula-wallpapers.xml"

# Replace Debian logo in GNOME About with version badge
mkdir -p "${CHROOT_DIR}/usr/share/pixmaps" "${CHROOT_DIR}/usr/share/icons/hicolor/scalable/apps"
cp "${ROOT_DIR}/src/branding/logos/version-badge.svg" "${CHROOT_DIR}/usr/share/pixmaps/debian-logo.png" 2>/dev/null || true
cp "${ROOT_DIR}/src/branding/logos/version-badge.svg" "${CHROOT_DIR}/usr/share/icons/hicolor/scalable/apps/distributor-logo.svg" 2>/dev/null || true
cp "${ROOT_DIR}/src/branding/logos/version-badge.svg" "${CHROOT_DIR}/usr/share/icons/Nebula/scalable/apps/distributor-logo.svg" 2>/dev/null || true
cp "${ROOT_DIR}/src/branding/logos/version-badge.svg" "${CHROOT_DIR}/usr/share/icons/Nebula/scalable/apps/debian-logo.svg" 2>/dev/null || true
cp -r "${ROOT_DIR}/src/branding/logos" "${CHROOT_DIR}/usr/share/nebulaos/branding/" 2>/dev/null || true
cp -r "${ROOT_DIR}/src/release/assets" "${CHROOT_DIR}/usr/share/nebulaos/branding/" 2>/dev/null || true

# 16. Dynamic /etc/os-release
echo "[base] Generating /etc/os-release..."
export PRODUCT_NAME PRODUCT_ID VERSION MAJOR_VERSION MINOR_VERSION CODENAME ARCHITECTURE PRETTY_NAME DISTRO_FAMILY HOMEPAGE_URL SUPPORT_URL BUG_REPORT_URL PRIVACY_POLICY_URL BUILD_ID
envsubst < "${ROOT_DIR}/src/system/os-release.template" > "${CHROOT_DIR}/etc/os-release"
chmod 644 "${CHROOT_DIR}/etc/os-release"
ln -sf ../etc/os-release "${CHROOT_DIR}/usr/lib/os-release" 2>/dev/null || true

cat <<EOF > "${CHROOT_DIR}/etc/issue"
${PRODUCT_NAME} ${VERSION} "${CODENAME}" (x86_64) - \l
Kernel \r on an \m

EOF

# 17. Force Plymouth to terminate cleanly when GDM starts
mkdir -p "${CHROOT_DIR}/etc/systemd/system/multi-user.target.wants"
cat <<'EOF' > "${CHROOT_DIR}/etc/systemd/system/plymouth-quit-force.service"
[Unit]
Description=Ensure Plymouth Terminates on Display Manager Start
After=gdm.service gdm3.service multi-user.target graphical.target
DefaultDependencies=no

[Service]
Type=oneshot
ExecStart=-/usr/bin/plymouth quit
RemainAfterExit=yes

[Install]
WantedBy=graphical.target multi-user.target
EOF
chroot "${CHROOT_DIR}" systemctl enable plymouth-quit-force.service 2>/dev/null || true

# 18. Update Initramfs with live-boot hooks
echo "[base] Updating initramfs with live-boot and plymouth..."
chroot "${CHROOT_DIR}" update-initramfs -u -k all

# 19. Extract Kernel and Initramfs for ISO
echo "[base] Extracting vmlinuz and initrd.img from chroot..."
mkdir -p "${ROOT_DIR}/build/kernel"
VMLINUZ_FILE=$(ls -t "${CHROOT_DIR}/boot"/vmlinuz-* | head -n 1)
INITRD_FILE=$(ls -t "${CHROOT_DIR}/boot"/initrd.img-* | head -n 1)

cp "${VMLINUZ_FILE}" "${ROOT_DIR}/build/kernel/vmlinuz"
cp "${INITRD_FILE}" "${ROOT_DIR}/build/kernel/initrd.img"
echo "  Vmlinuz:    ${ROOT_DIR}/build/kernel/vmlinuz"
echo "  Initramfs:  ${ROOT_DIR}/build/kernel/initrd.img"

# 20. Clean up chroot cache and temporary files before squashfs
chroot "${CHROOT_DIR}" apt-get clean
rm -rf "${CHROOT_DIR}/tmp/"* "${CHROOT_DIR}/var/tmp/"*

# 21. Clean up chroot mounts BEFORE packaging
cleanup
trap - EXIT

# Ensure essential mountpoint directories exist as clean empty directories in rootfs
mkdir -p "${CHROOT_DIR}"/{dev,proc,sys,run,tmp,mnt,media}
chmod 755 "${CHROOT_DIR}"/{dev,proc,sys,run}
chmod 1777 "${CHROOT_DIR}/tmp"

# 22. Generate filesystem.squashfs
echo "[base] Generating live filesystem.squashfs..."
mkdir -p "${ISO_ROOT}/live"
rm -f "${ISO_ROOT}/live/filesystem.squashfs"

mksquashfs "${CHROOT_DIR}" "${ISO_ROOT}/live/filesystem.squashfs" \
    -comp zstd \
    -Xcompression-level 15 \
    -b 1048576 \
    -noappend

echo "[base] Debian GNOME/Wayland base successfully built and packaged into SquashFS!"
