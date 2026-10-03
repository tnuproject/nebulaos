#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CHROOT_TMP="/tmp/nebulaos-patch-chroot"
SQUASHFS="${ROOT_DIR}/build/iso_root/live/filesystem.squashfs"

cleanup() {
    echo "[patch] Cleaning chroot mounts..."
    umount -lf "${CHROOT_TMP}/dev/pts" 2>/dev/null || true
    umount -lf "${CHROOT_TMP}/dev" 2>/dev/null || true
    umount -lf "${CHROOT_TMP}/proc" 2>/dev/null || true
    umount -lf "${CHROOT_TMP}/sys" 2>/dev/null || true
}
trap cleanup EXIT

echo "[1/8] Checking existing squashfs base..."
cleanup
rm -rf "${CHROOT_TMP}"

if [ ! -f "${SQUASHFS}" ]; then
    echo "[patch] Squashfs base not found at ${SQUASHFS}."
    echo "[patch] Generating fresh Debian base via build-debian-base.sh..."
    bash "${ROOT_DIR}/scripts/build-debian-base.sh"
fi

echo "[patch] Unpacking squashfs..."
unsquashfs -d "${CHROOT_TMP}" "${SQUASHFS}"

echo "[2/8] Mounting virtual filesystems for chroot operations..."
mount --bind /dev "${CHROOT_TMP}/dev"
mount --bind /dev/pts "${CHROOT_TMP}/dev/pts"
mount -t proc proc "${CHROOT_TMP}/proc"
mount -t sysfs sysfs "${CHROOT_TMP}/sys"
cp /etc/resolv.conf "${CHROOT_TMP}/etc/resolv.conf"

echo "[3/8] Installing GNOME packages, nebula-setup installer deps, polkit, and official apps..."
export DEBIAN_FRONTEND=noninteractive
rm -f "${CHROOT_TMP}/etc/apt/sources.list.d/nebula-updates.list" 2>/dev/null || true
chroot "${CHROOT_TMP}" apt-get update || true
chroot "${CHROOT_TMP}" apt-get purge -y epiphany-browser epiphany-browser-data calamares calamares-settings-debian gnome-shell-extension-desktop-icons-ng \
    gnome-calendar cheese gnome-contacts gnome-calls gnome-music totem gnome-clocks gnome-photos eog 2>/dev/null || true
chroot "${CHROOT_TMP}" apt-get install -y --no-install-recommends \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
    python3-gst-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-pulseaudio ffmpeg \
    parted gdisk dosfstools e2fsprogs grub-pc-bin grub-efi-amd64-bin efibootmgr \
    squashfs-tools \
    gnome-keyring libpam-gnome-keyring policykit-1-gnome libsecret-1-0 libsecret-tools \
    gnome-software gnome-weather geary \
    gnome-shell-extension-dashtodock \
    open-vm-tools open-vm-tools-desktop xserver-xorg-video-vmware \
    xserver-xorg-video-qxl spice-vdagent \
    xserver-xorg-video-all mesa-vulkan-drivers libgl1-mesa-dri \
    gnome-sushi \
    python3-qrcode python3-pil \
    os-prober

# Enable virtualization guest integration services and kernel modules
for svc in open-vm-tools.service spice-vdagentd.service; do
    chroot "${CHROOT_TMP}" systemctl enable "${svc}" 2>/dev/null || true
done

for mod in vmwgfx vboxguest vboxvideo vboxsf; do
    if ! grep -q "^${mod}" "${CHROOT_TMP}/etc/modules" 2>/dev/null; then
        echo "${mod}" >> "${CHROOT_TMP}/etc/modules"
    fi
done


echo "[4/8] Deploying Polkit security rules and PAM keyring configuration..."
mkdir -p "${CHROOT_TMP}/etc/polkit-1/rules.d"
cp "${ROOT_DIR}/src/system/50-org.freedesktop.NetworkManager.rules" "${CHROOT_TMP}/etc/polkit-1/rules.d/50-org.freedesktop.NetworkManager.rules"
cp "${ROOT_DIR}/src/system/49-nopasswd_admin.rules" "${CHROOT_TMP}/etc/polkit-1/rules.d/49-nopasswd_admin.rules"
chmod 644 "${CHROOT_TMP}/etc/polkit-1/rules.d/"*.rules

# Configure PAM for GDM autologin with gnome-keyring
if [ -f "${CHROOT_TMP}/etc/pam.d/gdm-autologin" ]; then
    if ! grep -q "pam_gnome_keyring.so" "${CHROOT_TMP}/etc/pam.d/gdm-autologin"; then
        echo "auth optional pam_gnome_keyring.so" >> "${CHROOT_TMP}/etc/pam.d/gdm-autologin"
        echo "session optional pam_gnome_keyring.so auto_start" >> "${CHROOT_TMP}/etc/pam.d/gdm-autologin"
    fi
fi

# Set up default keyring directory for live user
mkdir -p "${CHROOT_TMP}/home/nebula/.local/share/keyrings" "${CHROOT_TMP}/etc/skel/.local/share/keyrings"
chown -R 1000:1000 "${CHROOT_TMP}/home/nebula" 2>/dev/null || true

# Configure GDM3 greeter for Nebula Lockscreen/Login Parity
mkdir -p "${CHROOT_TMP}/etc/dconf/db/gdm.d" "${CHROOT_TMP}/etc/dconf/profile"
cat <<'GDMCONFEOF' > "${CHROOT_TMP}/etc/dconf/db/gdm.d/01-nebula-gdm"
[org/gnome/shell]
disable-user-extensions=false
enabled-extensions=['nebula-shell-effects@nebulaos.org']

[org/gnome/desktop/interface]
icon-theme='Nebula'
gtk-theme='Adwaita-dark'
font-name='Poppins 10.5'
enable-hot-corners=false
show-battery-percentage=false

[org/gnome/desktop/background]
picture-uri='file:///usr/share/backgrounds/nebula/plains-default.svg'
picture-uri-dark='file:///usr/share/backgrounds/nebula/plains-default.svg'
GDMCONFEOF

cat <<'PROFEOF' > "${CHROOT_TMP}/etc/dconf/profile/gdm"
user-db:user
system-db:gdm
file-db:/usr/share/gdm/greeter-dconf-defaults
PROFEOF

if [ -f "${CHROOT_TMP}/etc/gdm3/greeter.dconf-defaults" ]; then
    cat <<'GREETEREOF' >> "${CHROOT_TMP}/etc/gdm3/greeter.dconf-defaults"
[org/gnome/shell]
disable-user-extensions=false
enabled-extensions=['nebula-shell-effects@nebulaos.org']
[org/gnome/desktop/interface]
icon-theme='Nebula'
gtk-theme='Adwaita-dark'
font-name='Poppins 10.5'
GREETEREOF
fi
chroot "${CHROOT_TMP}" dconf update 2>/dev/null || true

# Configure GDM3 daemon.conf — autologin for live 'nebula' user
mkdir -p "${CHROOT_TMP}/etc/gdm3"
cat <<'GDMDAEMONEOF' > "${CHROOT_TMP}/etc/gdm3/daemon.conf"
[daemon]
AutomaticLoginEnable = true
AutomaticLogin = nebula
WaylandEnable = true
DefaultSession = gnome.desktop

[security]

[xdmcp]

[chooser]

[debug]
GDMDAEMONEOF
chmod 644 "${CHROOT_TMP}/etc/gdm3/daemon.conf"


# Ensure GDM PreSession hook guarantees Session=gnome
if [ -f "${CHROOT_TMP}/etc/gdm3/PreSession/Default" ]; then
    if ! grep -q "Session=gnome" "${CHROOT_TMP}/etc/gdm3/PreSession/Default"; then
        cat <<'PREEOF' >> "${CHROOT_TMP}/etc/gdm3/PreSession/Default"
if [ -n "$USER" ] && [ -f "/var/lib/AccountsService/users/$USER" ]; then
    sed -i 's|^Session=.*|Session=gnome|' "/var/lib/AccountsService/users/$USER" 2>/dev/null || true
fi
PREEOF
    fi
fi

# Configure silent shutdown and quiet console (no wall broadcast messages)
mkdir -p "${CHROOT_TMP}/etc/systemd/system.conf.d" "${CHROOT_TMP}/etc/sysctl.d"
cat <<'SYSCONEOF' > "${CHROOT_TMP}/etc/systemd/system.conf.d/10-silent-shutdown.conf"
[Manager]
ShowStatus=no
DefaultStandardOutput=null
DefaultStandardError=null
SYSCONEOF

cat <<'SYSCTLEOF' > "${CHROOT_TMP}/etc/sysctl.d/20-quiet-console.conf"
kernel.printk = 0 0 0 0
SYSCTLEOF

echo "[5/8] Generating and installing Nebula Squircle Icon Theme & Wi-Fi Icons..."
# Generate theme
python3 "${ROOT_DIR}/scripts/generate_nebula_icons.py"

# Remove Hatter completely and clean previous Nebula icons
rm -rf "${CHROOT_TMP}/usr/share/icons/Hatter" "${CHROOT_TMP}/usr/share/icons/Nebula" 2>/dev/null || true

# Purge ALL custom battery icons across all themes so GNOME defaults strictly to original GNOME Adwaita battery icons
find "${CHROOT_TMP}/usr/share/icons" -name "*battery*.svg" ! -path "*/Adwaita/*" -delete 2>/dev/null || true
find "${CHROOT_TMP}/usr/share/icons" -name "*battery*.png" ! -path "*/Adwaita/*" ! -path "*/swcatalog/*" -delete 2>/dev/null || true

# Install fresh Nebula theme
mkdir -p "${CHROOT_TMP}/usr/share/icons/Nebula"
cp -r "${ROOT_DIR}/src/branding/icons/Nebula/"* "${CHROOT_TMP}/usr/share/icons/Nebula/"
find "${CHROOT_TMP}/usr/share/icons/Nebula" -name "*battery*" -delete 2>/dev/null || true
chroot "${CHROOT_TMP}" gtk-update-icon-cache -f -t /usr/share/icons/Nebula 2>/dev/null || true
chroot "${CHROOT_TMP}" gtk-update-icon-cache -f -t /usr/share/icons/Adwaita 2>/dev/null || true
chroot "${CHROOT_TMP}" gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

# Update GTK settings to use Nebula icon theme
sed -i 's/gtk-icon-theme-name = Hatter/gtk-icon-theme-name = Nebula/g' "${CHROOT_TMP}/etc/gtk-3.0/settings.ini" 2>/dev/null || true
sed -i 's/gtk-icon-theme-name = Hatter/gtk-icon-theme-name = Nebula/g' "${CHROOT_TMP}/etc/gtk-4.0/settings.ini" 2>/dev/null || true
sed -i 's/gtk-icon-theme-name = Hatter/gtk-icon-theme-name = Nebula/g' "${CHROOT_TMP}/home/nebula/.config/gtk-3.0/settings.ini" 2>/dev/null || true
sed -i 's/gtk-icon-theme-name = Hatter/gtk-icon-theme-name = Nebula/g' "${CHROOT_TMP}/home/nebula/.config/gtk-4.0/settings.ini" 2>/dev/null || true

# Install Poppins fonts family
echo "[5b/8] Installing Poppins fonts and updating font cache..."
mkdir -p "${CHROOT_TMP}/usr/share/fonts/truetype/poppins"
cp "${ROOT_DIR}/fonts/"*.ttf "${CHROOT_TMP}/usr/share/fonts/truetype/poppins/"
chroot "${CHROOT_TMP}" fc-cache -f /usr/share/fonts/truetype/poppins 2>/dev/null || true

# Install Wallpapers
echo "[5c/8] Installing Nebula wallpapers..."
mkdir -p "${CHROOT_TMP}/usr/share/backgrounds/nebula" "${CHROOT_TMP}/usr/share/gnome-background-properties"
cp -r "${ROOT_DIR}/src/branding/wallpapers/"* "${CHROOT_TMP}/usr/share/backgrounds/nebula/" 2>/dev/null || true
cp "${ROOT_DIR}/src/branding/wallpapers/nebula-wallpapers.xml" "${CHROOT_TMP}/usr/share/gnome-background-properties/nebula-wallpapers.xml"
# Remove all default Debian, GNOME backgrounds, and desktop-base assets
rm -rf "${CHROOT_TMP}/usr/share/backgrounds/gnome" \
       "${CHROOT_TMP}/usr/share/backgrounds/debian" \
       "${CHROOT_TMP}/usr/share/desktop-base" \
       "${CHROOT_TMP}/usr/share/images/desktop-base" \
       "${CHROOT_TMP}/usr/share/wallpapers" 2>/dev/null || true
find "${CHROOT_TMP}/usr/share/gnome-background-properties" -type f ! -name "nebula-wallpapers.xml" -delete 2>/dev/null || true

# Deploy DefaultUser avatar for all existing and newly created users
echo "[5d/8] Deploying DefaultUser avatar..."
mkdir -p "${CHROOT_TMP}/etc/skel" "${CHROOT_TMP}/var/lib/AccountsService/icons" "${CHROOT_TMP}/usr/share/pixmaps/faces"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/etc/skel/.face"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/etc/skel/.face.icon"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/home/nebula/.face"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/home/nebula/.face.icon"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/var/lib/AccountsService/icons/nebula"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/var/lib/AccountsService/icons/default"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/usr/share/pixmaps/faces/default.png"
cp "${ROOT_DIR}/src/branding/assets/DefaultUser.png" "${CHROOT_TMP}/usr/share/pixmaps/faces/user-generic.png"
chmod 644 "${CHROOT_TMP}/etc/skel/.face"* 2>/dev/null || true
chown -R 1000:1000 "${CHROOT_TMP}/home/nebula/.face"* 2>/dev/null || true

# Configure AccountsService profile for nebula with explicit Session=gnome
mkdir -p "${CHROOT_TMP}/var/lib/AccountsService/users"
cat <<'USEREOF' > "${CHROOT_TMP}/var/lib/AccountsService/users/nebula"
[User]
Language=
Session=gnome
XSession=gnome
SystemAccount=false
Icon=/var/lib/AccountsService/icons/nebula
USEREOF
chmod 700 "${CHROOT_TMP}/var/lib/AccountsService/users"
chmod 600 "${CHROOT_TMP}/var/lib/AccountsService/users/nebula"
chown -R 0:0 "${CHROOT_TMP}/var/lib/AccountsService"

# Session fallback in .dmrc
echo -e "[Desktop]\nSession=gnome" > "${CHROOT_TMP}/etc/skel/.dmrc"
echo -e "[Desktop]\nSession=gnome" > "${CHROOT_TMP}/home/nebula/.dmrc"
chown 1000:1000 "${CHROOT_TMP}/home/nebula/.dmrc"
chmod 644 "${CHROOT_TMP}/home/nebula/.dmrc" "${CHROOT_TMP}/etc/skel/.dmrc"

chroot "${CHROOT_TMP}" update-alternatives --set x-session-manager /usr/bin/gnome-session 2>/dev/null || true

# Fix GNOME Settings About Logo: write clean os-release and nebulaos-symbol logo
echo "[5e/8] Configuring NebulaOS symbol in os-release and icon directories..."
SYS_VER="${RELEASE_VERSION:-$(grep -E '^VERSION=' "${ROOT_DIR}/src/release/release.conf" 2>/dev/null | head -1 | cut -d'"' -f2)}"
[ -z "$SYS_VER" ] && SYS_VER="26.0.1"
SYS_CHANNEL="${CHANNEL:-$(grep -E '^BUILD_CHANNEL=' "${ROOT_DIR}/src/release/release.conf" 2>/dev/null | head -1 | cut -d'"' -f2)}"
[ -z "$SYS_CHANNEL" ] && SYS_CHANNEL="stable"

if [ "$SYS_CHANNEL" = "delta" ] && [ -f "${ROOT_DIR}/src/release/delta_rev" ]; then
    DELTA_REV="$(cat "${ROOT_DIR}/src/release/delta_rev" | tr -d '[:space:]')"
    if [ -n "$DELTA_REV" ] && ! echo "$SYS_VER" | grep -qi "rev"; then
        BASE_V="$(echo "$SYS_VER" | sed -E 's/[-~](delta\.?)?rev[0-9]+.*//')"
        SYS_VER="${BASE_V}-delta.rev${DELTA_REV}"
    fi
fi

rm -f "${CHROOT_TMP}/etc/os-release" "${CHROOT_TMP}/usr/lib/os-release"
cat <<OSRELEOF > "${CHROOT_TMP}/usr/lib/os-release"
PRETTY_NAME="NebulaOS ${SYS_VER} (Apollo)"
NAME="NebulaOS"
VERSION_ID="${SYS_VER}"
VERSION="${SYS_VER} (Apollo)"
VERSION_CODENAME=apollo
ID=nebulaos
ID_LIKE=debian
HOME_URL="https://github.com/tnuproject/nebulaos"
SUPPORT_URL="https://github.com/tnuproject/nebulaos/issues"
BUG_REPORT_URL="https://github.com/tnuproject/nebulaos/issues"
LOGO=nebulaos-symbol
BUILD_CHANNEL=${SYS_CHANNEL}
OSRELEOF
cp -f "${CHROOT_TMP}/usr/lib/os-release" "${CHROOT_TMP}/etc/os-release"

mkdir -p "${CHROOT_TMP}/etc/nebula" "${CHROOT_TMP}/usr/share/nebula"
echo "${SYS_CHANNEL}" > "${CHROOT_TMP}/etc/nebula/channel"
echo "${SYS_CHANNEL}" > "${CHROOT_TMP}/usr/share/nebula/channel"
if [ -f "${ROOT_DIR}/src/release/delta_rev" ]; then
    cp -f "${ROOT_DIR}/src/release/delta_rev" "${CHROOT_TMP}/etc/nebula/delta_rev"
    cp -f "${ROOT_DIR}/src/release/delta_rev" "${CHROOT_TMP}/usr/share/nebula/delta_rev"
fi
if [ -f "${ROOT_DIR}/src/release/release.conf" ]; then
    cp -f "${ROOT_DIR}/src/release/release.conf" "${CHROOT_TMP}/etc/nebula/release.conf"
fi

# Replace all Debian/distributor logos in pixmaps and icon themes (both .svg and .png) with backup
bash "${ROOT_DIR}/scripts/replace_distro_logo.sh" "${CHROOT_TMP}"

echo "[6/8] Updating custom applications, schema overrides, shell extensions, and desktop entries..."

# Clean reinstall of Dash to Dock extension for 100% stability (dock elevation handled via stylesheet.css)
echo "[6a/8] Ensuring pristine Dash to Dock extension..."
chroot "${CHROOT_TMP}" apt-get install --reinstall -y gnome-shell-extension-dashtodock 2>/dev/null || true
mkdir -p "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/actions" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/apps"
cp "${ROOT_DIR}/src/branding/icons/Nebula/scalable/actions/view-app-grid.svg" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/actions/view-app-grid.svg"
cp "${ROOT_DIR}/src/branding/icons/Nebula/scalable/actions/view-app-grid.svg" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/actions/view-app-grid-symbolic.svg"
cp "${ROOT_DIR}/src/branding/icons/Nebula/scalable/actions/view-app-grid.svg" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/apps/view-app-grid.svg"
cp "${ROOT_DIR}/src/branding/icons/Nebula/scalable/actions/view-app-grid.svg" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/apps/view-app-grid-symbolic.svg"

# Shell Effects Extension (fluid bubble notifications, dock-up launchpad, dynamic topbar)
mkdir -p "${CHROOT_TMP}/usr/share/gnome-shell/extensions/nebula-shell-effects@nebulaos.org"
cp -r "${ROOT_DIR}/src/system/nebula-shell-effects/"* "${CHROOT_TMP}/usr/share/gnome-shell/extensions/nebula-shell-effects@nebulaos.org/"

# NebulaOS GNOME Shell Theme
mkdir -p "${CHROOT_TMP}/usr/share/themes/NebulaOS/gnome-shell" "${CHROOT_TMP}/usr/share/gnome-shell/theme"
cp -r "${ROOT_DIR}/src/branding/themes/NebulaOS/"* "${CHROOT_TMP}/usr/share/themes/NebulaOS/"
cp -f "${ROOT_DIR}/src/branding/themes/NebulaOS/gnome-shell/gnome-shell.css" "${CHROOT_TMP}/usr/share/gnome-shell/theme/gnome-shell.css"
chmod -R a+rX "${CHROOT_TMP}/usr/share/backgrounds" "${CHROOT_TMP}/usr/share/themes" "${CHROOT_TMP}/usr/share/gnome-shell/theme" 2>/dev/null || true

# Deploy Lockscreen & GDM lock icon
for icon_status_dir in "${CHROOT_TMP}/usr/share/icons/Nebula/scalable/status" \
                       "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/status" \
                       "${CHROOT_TMP}/usr/share/icons/Adwaita/scalable/status"; do
    mkdir -p "${icon_status_dir}"
    cp -f "${ROOT_DIR}/src/branding/icons/lock_symbolic.svg" "${icon_status_dir}/lock_symbolic.svg" 2>/dev/null || true
    cp -f "${ROOT_DIR}/src/branding/icons/lock_symbolic.svg" "${icon_status_dir}/channel-secure-symbolic.svg" 2>/dev/null || true
    cp -f "${ROOT_DIR}/src/branding/icons/lock_symbolic.svg" "${icon_status_dir}/system-lock-screen-symbolic.svg" 2>/dev/null || true
done

# Purge any legacy widget traces
rm -f "${CHROOT_TMP}/usr/bin/nebula-widgets-manager" 2>/dev/null || true
rm -rf "${CHROOT_TMP}/usr/share/nebulaos/widgets" 2>/dev/null || true

# Icon Wrapper Utility
cp "${ROOT_DIR}/src/system/nebula-icon-wrapper.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-icon-wrapper.py"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/nebula-icon-wrapper.py"
ln -sf /usr/lib/nebulaos/nebula-icon-wrapper.py "${CHROOT_TMP}/usr/bin/nebula-icon-wrapper"

# Install Software
cp "${ROOT_DIR}/src/system/install-software.py" "${CHROOT_TMP}/usr/bin/install-software"
chmod 755 "${CHROOT_TMP}/usr/bin/install-software"

# Apps Sync
cp "${ROOT_DIR}/src/system/nebula-apps-sync.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-apps-sync.py"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/nebula-apps-sync.py"

# FreeDesktop .desktop thumbnailer and direct application launcher
echo "[6a2/8] Installing FreeDesktop .desktop thumbnailer and application launcher..."
cp "${ROOT_DIR}/src/system/nebula-desktop-thumbnailer.py" "${CHROOT_TMP}/usr/bin/nebula-desktop-thumbnailer"
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-desktop-thumbnailer"

mkdir -p "${CHROOT_TMP}/usr/share/thumbnailers"
cp "${ROOT_DIR}/src/system/nebula-desktop.thumbnailer" "${CHROOT_TMP}/usr/share/thumbnailers/nebula-desktop.thumbnailer"
chmod 644 "${CHROOT_TMP}/usr/share/thumbnailers/nebula-desktop.thumbnailer"

cp "${ROOT_DIR}/src/system/nebula-desktop-launcher" "${CHROOT_TMP}/usr/bin/nebula-desktop-launcher"
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-desktop-launcher"

cp "${ROOT_DIR}/src/apps/desktop-entries/nebula-desktop-launcher.desktop" "${CHROOT_TMP}/usr/share/applications/nebula-desktop-launcher.desktop"
chmod 644 "${CHROOT_TMP}/usr/share/applications/nebula-desktop-launcher.desktop"

# Deploy additional GNOME Shell extensions (blur-my-shell, kiwi, kiwi-menu, ding, battery-indicator-icon)
echo "[6a3/8] Deploying blur-my-shell, kiwi, kiwi-menu, ding, and battery-indicator-icon..."
rm -rf "${CHROOT_TMP}/usr/share/gnome-shell/extensions/panel-corners@aunetx" 2>/dev/null || true
rm -rf "${CHROOT_TMP}/usr/share/gnome-shell/extensions/kiwimenu@kemma" "${CHROOT_TMP}/usr/share/gnome-shell/extensions/gtk4-ding@smedius.gitlab.com" 2>/dev/null || true
if [ -d "${ROOT_DIR}/src/extensions" ]; then
    for ext_dir in "${ROOT_DIR}/src/extensions/"*; do
        [ -d "${ext_dir}" ] || continue
        ext_uuid="$(basename "${ext_dir}")"
        [ "${ext_uuid}" = "panel-corners@aunetx" ] && continue
        [ "${ext_uuid}" = "kiwimenu@kemma" ] && continue
        [ "${ext_uuid}" = "gtk4-ding@smedius.gitlab.com" ] && continue
        mkdir -p "${CHROOT_TMP}/usr/share/gnome-shell/extensions/${ext_uuid}"
        cp -r "${ext_dir}/"* "${CHROOT_TMP}/usr/share/gnome-shell/extensions/${ext_uuid}/"
        if [ -d "${ext_dir}/schemas" ]; then
            cp -f "${ext_dir}/schemas/"*.gschema.xml "${CHROOT_TMP}/usr/share/glib-2.0/schemas/" 2>/dev/null || true
            chroot "${CHROOT_TMP}" glib-compile-schemas "/usr/share/gnome-shell/extensions/${ext_uuid}/schemas" 2>/dev/null || true
        fi
    done
fi

# NebulaOS Custom Installer Launcher & Post-Install Cleanup
cp "${ROOT_DIR}/src/system/install-nebula" "${CHROOT_TMP}/usr/bin/install-nebula"
chmod 755 "${CHROOT_TMP}/usr/bin/install-nebula"
mkdir -p "${CHROOT_TMP}/usr/lib/nebulaos"
cp "${ROOT_DIR}/src/system/post-install-cleanup.sh" "${CHROOT_TMP}/usr/lib/nebulaos/post-install-cleanup.sh"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/post-install-cleanup.sh"

# Clean legacy installer and updater binaries
rm -f "${CHROOT_TMP}/usr/bin/nebula-installer" "${CHROOT_TMP}/usr/bin/nebula-updater" "${CHROOT_TMP}/usr/bin/nebula-update" 2>/dev/null || true
rm -rf "${CHROOT_TMP}/usr/lib/nebulaos/installer" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-ota-check.py" 2>/dev/null || true

# Deploy nebula-setup Custom Installer (replaces Calamares)
echo "[6b/8] Deploying nebula-setup custom installer..."
mkdir -p "${CHROOT_TMP}/usr/share/nebula-setup/screens" \
         "${CHROOT_TMP}/usr/share/nebula-setup/backend" \
         "${CHROOT_TMP}/usr/share/nebula-setup/ui"

# Main script and subpackages
cp -f "${ROOT_DIR}/src/apps/nebula-setup/nebula-setup.py" "${CHROOT_TMP}/usr/share/nebula-setup/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/screens/"*.py "${CHROOT_TMP}/usr/share/nebula-setup/screens/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/backend/"*.py "${CHROOT_TMP}/usr/share/nebula-setup/backend/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/ui/"*.py "${CHROOT_TMP}/usr/share/nebula-setup/ui/"
cp -f "${ROOT_DIR}/src/apps/nebula-setup/ui/styles.css" "${CHROOT_TMP}/usr/share/nebula-setup/ui/"
chmod -R 755 "${CHROOT_TMP}/usr/share/nebula-setup/"
chmod 644 "${CHROOT_TMP}/usr/share/nebula-setup/ui/styles.css"

# Deploy Recovery Environment
echo "[6b2/8] Deploying NebulaOS Recovery Environment..."
mkdir -p "${CHROOT_TMP}/usr/share/nebula-recovery/ui" \
         "${CHROOT_TMP}/usr/share/nebula-recovery/backend" \
         "${CHROOT_TMP}/usr/lib/nebulaos" \
         "${CHROOT_TMP}/etc/systemd/system"

cp -f "${ROOT_DIR}/src/apps/nebula-recovery/nebula-recovery.py" "${CHROOT_TMP}/usr/share/nebula-recovery/"
cp -f "${ROOT_DIR}/src/apps/nebula-recovery/ui/"*.py "${CHROOT_TMP}/usr/share/nebula-recovery/ui/"
cp -f "${ROOT_DIR}/src/apps/nebula-recovery/ui/styles.css" "${CHROOT_TMP}/usr/share/nebula-recovery/ui/"
cp -f "${ROOT_DIR}/src/apps/nebula-recovery/backend/"*.py "${CHROOT_TMP}/usr/share/nebula-recovery/backend/"
chmod -R 755 "${CHROOT_TMP}/usr/share/nebula-recovery/"
chmod 644 "${CHROOT_TMP}/usr/share/nebula-recovery/ui/styles.css"

cp -f "${ROOT_DIR}/src/system/nebula-recovery" "${CHROOT_TMP}/usr/bin/nebula-recovery"
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-recovery"

cp -f "${ROOT_DIR}/src/system/nebula-session-init" "${CHROOT_TMP}/usr/bin/nebula-session-init"
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-session-init"

# Early-boot Plymouth Keystroke Interceptor (Command+R)
cp -f "${ROOT_DIR}/src/system/nebula-recovery-watcher.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-recovery-watcher.py"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/nebula-recovery-watcher.py"

cp -f "${ROOT_DIR}/src/system/nebula-recovery-watcher.service" "${CHROOT_TMP}/etc/systemd/system/nebula-recovery-watcher.service"
chmod 644 "${CHROOT_TMP}/etc/systemd/system/nebula-recovery-watcher.service"
chroot "${CHROOT_TMP}" systemctl enable nebula-recovery-watcher.service 2>/dev/null || true

# Deploy Nebula Companion Daemon & Picture Organizer (PetalDrop & Cloud Gallery)
echo "[6b3/8] Deploying Nebula Companion Daemon, PetalDrop & Cloud Gallery..."
mkdir -p "${CHROOT_TMP}/usr/lib/nebulaos" \
         "${CHROOT_TMP}/etc/systemd/user/default.target.wants" \
         "${CHROOT_TMP}/usr/share/mynebula"

cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-companion.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-companion.py"
cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-picture-organizer.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-picture-organizer.py"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/nebula-companion.py" "${CHROOT_TMP}/usr/lib/nebulaos/nebula-picture-organizer.py"

cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-companion.service" "${CHROOT_TMP}/etc/systemd/user/nebula-companion.service"
cp -f "${ROOT_DIR}/src/system/nebula-companion/nebula-picture-organizer.service" "${CHROOT_TMP}/etc/systemd/user/nebula-picture-organizer.service"
chmod 644 "${CHROOT_TMP}/etc/systemd/user/"*.service

rm -f "${CHROOT_TMP}/etc/systemd/user/default.target.wants/nebula-companion.service"
ln -sf /etc/systemd/user/nebula-companion.service "${CHROOT_TMP}/etc/systemd/user/default.target.wants/nebula-companion.service"
rm -f "${CHROOT_TMP}/etc/systemd/user/default.target.wants/nebula-picture-organizer.service"
ln -sf /etc/systemd/user/nebula-picture-organizer.service "${CHROOT_TMP}/etc/systemd/user/default.target.wants/nebula-picture-organizer.service"

cp -r "${ROOT_DIR}/src/apps/mynebula-android/"* "${CHROOT_TMP}/usr/share/mynebula/" 2>/dev/null || true
cp -f "${ROOT_DIR}/src/apps/mynebula-android/mynebula.apk" "${CHROOT_TMP}/usr/share/mynebula/mynebula.apk" 2>/dev/null || true
chmod 644 "${CHROOT_TMP}/usr/share/mynebula/mynebula.apk" 2>/dev/null || true


# Deploy MyNebula Desktop Application
echo "[6b3ba/8] Deploying MyNebula Desktop Application..."
mkdir -p "${CHROOT_TMP}/usr/share/mynebula-desktop"
cp -f "${ROOT_DIR}/src/apps/mynebula-desktop/mynebula.py" "${CHROOT_TMP}/usr/share/mynebula-desktop/mynebula.py"
chmod 755 "${CHROOT_TMP}/usr/share/mynebula-desktop/mynebula.py"
rm -f "${CHROOT_TMP}/usr/bin/mynebula"
ln -sf /usr/share/mynebula-desktop/mynebula.py "${CHROOT_TMP}/usr/bin/mynebula"

# Deploy Screen Mirroring Desktop Viewer
echo "[6b3bb/8] Deploying MyNebula Screen Mirroring Viewer..."
mkdir -p "${CHROOT_TMP}/usr/share/mynebula-screen-mirror"
cp -f "${ROOT_DIR}/src/apps/mynebula-screen-mirror/screen-mirror.py" "${CHROOT_TMP}/usr/share/mynebula-screen-mirror/screen-mirror.py"
chmod 755 "${CHROOT_TMP}/usr/share/mynebula-screen-mirror/screen-mirror.py"
rm -f "${CHROOT_TMP}/usr/bin/nebula-screen-mirror"
ln -sf /usr/share/mynebula-screen-mirror/screen-mirror.py "${CHROOT_TMP}/usr/bin/nebula-screen-mirror"

# Deploy PetalDrop Native Overlay
echo "[6b3c/8] Deploying PetalDrop Native Overlay..."
cp -f "${ROOT_DIR}/src/apps/petaldrop-desktop/petaldrop-overlay.py" "${CHROOT_TMP}/usr/lib/nebulaos/petaldrop-overlay.py"
chmod 755 "${CHROOT_TMP}/usr/lib/nebulaos/petaldrop-overlay.py"
rm -f "${CHROOT_TMP}/usr/bin/petaldrop"
ln -sf /usr/lib/nebulaos/petaldrop-overlay.py "${CHROOT_TMP}/usr/bin/petaldrop"

# Deploy Post-Installation Setup Wizard (nebula-welcome)
echo "[6b4/8] Deploying NebulaOS Post-Installation Setup Wizard (nebula-welcome)..."
mkdir -p "${CHROOT_TMP}/usr/share/nebula-welcome/screens" \
         "${CHROOT_TMP}/usr/share/nebula-welcome/backend" \
         "${CHROOT_TMP}/usr/share/nebula-welcome/ui" \
         "${CHROOT_TMP}/etc/xdg/autostart"

cp -f "${ROOT_DIR}/src/apps/nebula-welcome/nebula-welcome.py" "${CHROOT_TMP}/usr/share/nebula-welcome/"
cp -f "${ROOT_DIR}/src/apps/nebula-welcome/screens/"*.py "${CHROOT_TMP}/usr/share/nebula-welcome/screens/"
cp -f "${ROOT_DIR}/src/apps/nebula-welcome/backend/"*.py "${CHROOT_TMP}/usr/share/nebula-welcome/backend/"
cp -f "${ROOT_DIR}/src/apps/nebula-welcome/ui/"*.py "${CHROOT_TMP}/usr/share/nebula-welcome/ui/"
cp -f "${ROOT_DIR}/src/apps/nebula-welcome/ui/styles.css" "${CHROOT_TMP}/usr/share/nebula-welcome/ui/"
chmod -R 755 "${CHROOT_TMP}/usr/share/nebula-welcome/"
chmod 644 "${CHROOT_TMP}/usr/share/nebula-welcome/ui/styles.css"

cp -f "${ROOT_DIR}/src/system/nebula-welcome-launcher" "${CHROOT_TMP}/usr/bin/nebula-welcome-launcher"
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-welcome-launcher"

cp -f "${ROOT_DIR}/src/apps/desktop-entries/nebula-welcome-autostart.desktop" "${CHROOT_TMP}/etc/xdg/autostart/nebula-welcome-autostart.desktop"
chmod 644 "${CHROOT_TMP}/etc/xdg/autostart/nebula-welcome-autostart.desktop"

# Deploy Nebula Settings App
echo "[6b5/8] Deploying NebulaOS Settings Application..."
mkdir -p "${CHROOT_TMP}/usr/share/nebula-settings"
cp -f "${ROOT_DIR}/src/apps/nebula-settings/nebula-settings.py" "${CHROOT_TMP}/usr/share/nebula-settings/nebula-settings.py"
chmod 755 "${CHROOT_TMP}/usr/share/nebula-settings/nebula-settings.py"

# Create launcher wrapper in /usr/bin
cat <<'SETTINGSEOF' > "${CHROOT_TMP}/usr/bin/nebula-settings"
#!/usr/bin/env bash
exec python3 /usr/share/nebula-settings/nebula-settings.py "$@"
SETTINGSEOF
chmod 755 "${CHROOT_TMP}/usr/bin/nebula-settings"
rm -f "${CHROOT_TMP}/usr/bin/gnome-control-center"
ln -sf /usr/bin/nebula-settings "${CHROOT_TMP}/usr/bin/gnome-control-center"

# Install settings icon (SVG → multiple PNG sizes for icon theme)
mkdir -p "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/apps"
cp -f "${ROOT_DIR}/src/branding/icons/nebula-settings.svg" "${CHROOT_TMP}/usr/share/icons/hicolor/scalable/apps/nebula-settings.svg"
for size in 48 64 128 256; do
    mkdir -p "${CHROOT_TMP}/usr/share/icons/hicolor/${size}x${size}/apps"
    if command -v rsvg-convert &>/dev/null; then
        rsvg-convert -w ${size} -h ${size} "${ROOT_DIR}/src/branding/icons/nebula-settings.svg" \
            > "${CHROOT_TMP}/usr/share/icons/hicolor/${size}x${size}/apps/nebula-settings.png" 2>/dev/null || true
    elif command -v convert &>/dev/null; then
        convert -background none -resize "${size}x${size}" \
            "${ROOT_DIR}/src/branding/icons/nebula-settings.svg" \
            "${CHROOT_TMP}/usr/share/icons/hicolor/${size}x${size}/apps/nebula-settings.png" 2>/dev/null || true
    fi
done

# Deploy Custom Modern NebulaOS Core Applications
echo "[6b6/8] Deploying Custom Modern NebulaOS Core Applications..."

# 1. Gallery
mkdir -p "${CHROOT_TMP}/usr/share/nebula-gallery"
cp -f "${ROOT_DIR}/src/apps/nebula-gallery/nebula-gallery.py" "${CHROOT_TMP}/usr/share/nebula-gallery/nebula-gallery.py"
chmod 755 "${CHROOT_TMP}/usr/share/nebula-gallery/nebula-gallery.py"
rm -f "${CHROOT_TMP}/usr/bin/nebula-gallery"
ln -sf /usr/share/nebula-gallery/nebula-gallery.py "${CHROOT_TMP}/usr/bin/nebula-gallery"

# 2. Calendar
mkdir -p "${CHROOT_TMP}/usr/share/nebula-calendar"
cp -f "${ROOT_DIR}/src/apps/nebula-calendar/nebula-calendar.py" "${CHROOT_TMP}/usr/share/nebula-calendar/nebula-calendar.py"
chmod 755 "${CHROOT_TMP}/usr/share/nebula-calendar/nebula-calendar.py"
rm -f "${CHROOT_TMP}/usr/bin/nebula-calendar"
ln -sf /usr/share/nebula-calendar/nebula-calendar.py "${CHROOT_TMP}/usr/bin/nebula-calendar"

# 3. Clock
mkdir -p "${CHROOT_TMP}/usr/share/nebula-clock"
cp -f "${ROOT_DIR}/src/apps/nebula-clock/nebula-clock.py" "${CHROOT_TMP}/usr/share/nebula-clock/nebula-clock.py"
chmod 755 "${CHROOT_TMP}/usr/share/nebula-clock/nebula-clock.py"
rm -f "${CHROOT_TMP}/usr/bin/nebula-clock"
ln -sf /usr/share/nebula-clock/nebula-clock.py "${CHROOT_TMP}/usr/bin/nebula-clock"


# 5. Camera
mkdir -p "${CHROOT_TMP}/usr/share/nebula-camera"
cp -f "${ROOT_DIR}/src/apps/nebula-camera/nebula-camera.py" "${CHROOT_TMP}/usr/share/nebula-camera/nebula-camera.py"
chmod 755 "${CHROOT_TMP}/usr/share/nebula-camera/nebula-camera.py"
rm -f "${CHROOT_TMP}/usr/bin/nebula-camera"
ln -sf /usr/share/nebula-camera/nebula-camera.py "${CHROOT_TMP}/usr/bin/nebula-camera"


# Remove any stale/duplicate GNOME shortcuts so only Nebula apps are shown
rm -f "${CHROOT_TMP}/usr/share/applications/gnome-control-center.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Settings.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Calendar.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-calendar.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Cheese.desktop" \
      "${CHROOT_TMP}/usr/share/applications/cheese.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.clocks.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-clocks.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Music.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-music.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Contacts.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-contacts.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Calls.desktop" \
      "${CHROOT_TMP}/usr/share/applications/calls.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Photos.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-photos.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.eog.desktop" \
      "${CHROOT_TMP}/usr/share/applications/eog.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Totem.desktop" \
      "${CHROOT_TMP}/usr/share/applications/totem.desktop" 2>/dev/null || true

# Remove any stale Calamares configs
rm -rf "${CHROOT_TMP}/etc/calamares" 2>/dev/null || true

# Preconfigure NebulaOS Official OTA updates repository for GNOME Software
mkdir -p "${CHROOT_TMP}/etc/apt/sources.list.d"
cp -f "${ROOT_DIR}/src/system/nebula-updates.list" "${CHROOT_TMP}/etc/apt/sources.list.d/nebula-updates.list"
chmod 644 "${CHROOT_TMP}/etc/apt/sources.list.d/nebula-updates.list"

# Silent GRUB Configuration for live and installed systems (timeout 0, hidden)
mkdir -p "${CHROOT_TMP}/etc/default/grub.d"
cp -f "${ROOT_DIR}/src/system/grub_default" "${CHROOT_TMP}/etc/default/grub"
cp -f "${ROOT_DIR}/src/system/00_nebula_silent.cfg" "${CHROOT_TMP}/etc/default/grub.d/00_nebula_silent.cfg"

# Silence Debian 10_linux & 00_header scripts so no text message is ever generated in grub.cfg
if [ -f "${CHROOT_TMP}/etc/grub.d/10_linux" ]; then
    sed -i 's/quiet_boot="0"/quiet_boot="1"/' "${CHROOT_TMP}/etc/grub.d/10_linux"
    sed -i "s/echo[[:space:]]\+'\$(echo \"\$message\" | grub_quote)'/:/g" "${CHROOT_TMP}/etc/grub.d/10_linux" 2>/dev/null || true
fi
if [ -f "${CHROOT_TMP}/etc/grub.d/00_header" ]; then
    sed -i 's/quick_boot="0"/quick_boot="1"/' "${CHROOT_TMP}/etc/grub.d/00_header"
fi

# Rename X-GNOME-Utilities.directory to System Utilities
mkdir -p "${CHROOT_TMP}/usr/share/desktop-directories"
cp "${ROOT_DIR}/src/system/X-GNOME-Utilities.directory" "${CHROOT_TMP}/usr/share/desktop-directories/X-GNOME-Utilities.directory"

# Desktop entries
cp "${ROOT_DIR}/src/apps/desktop-entries/"*.desktop "${CHROOT_TMP}/usr/share/applications/"
chmod 644 "${CHROOT_TMP}/usr/share/applications/"*.desktop
chmod 755 "${CHROOT_TMP}/usr/share/applications/install-software.desktop" 2>/dev/null || true

# Purge any stray installer shortcuts, obsolete GNOME apps, and autostart-only entries from application grid
rm -f "${CHROOT_TMP}/usr/share/applications/install-debian.desktop" \
      "${CHROOT_TMP}/usr/share/applications/calamares.desktop" \
      "${CHROOT_TMP}/usr/share/applications/nebula-installer-autostart.desktop" \
      "${CHROOT_TMP}/usr/share/applications/nebula-welcome-autostart.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-control-center.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Settings.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Calendar.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-calendar.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Cheese.desktop" \
      "${CHROOT_TMP}/usr/share/applications/cheese.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.clocks.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-clocks.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Music.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-music.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Contacts.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-contacts.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Calls.desktop" \
      "${CHROOT_TMP}/usr/share/applications/calls.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Photos.desktop" \
      "${CHROOT_TMP}/usr/share/applications/gnome-photos.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.eog.desktop" \
      "${CHROOT_TMP}/usr/share/applications/eog.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Totem.desktop" \
      "${CHROOT_TMP}/usr/share/applications/totem.desktop" \
      "${CHROOT_TMP}/etc/xdg/autostart/calamares-desktop-icon.desktop" \
      "${CHROOT_TMP}/home/nebula/Desktop/install-debian.desktop" \
      "${CHROOT_TMP}/home/nebula/Desktop/calamares.desktop" \
      "${CHROOT_TMP}/etc/skel/Desktop/install-debian.desktop" \
      "${CHROOT_TMP}/etc/skel/Desktop/calamares.desktop" 2>/dev/null || true

# Aggressively remove ALL duplicate/alias desktop entries that cause double app-grid entries
# (any org.nebulaos.* files left from previous squashfs extraction, and GNOME Settings aliases)
find "${CHROOT_TMP}/usr/share/applications/" -name 'org.nebulaos.*.desktop' -delete 2>/dev/null || true
rm -f "${CHROOT_TMP}/usr/share/applications/gnome-control-center.desktop" \
      "${CHROOT_TMP}/usr/share/applications/org.gnome.Settings.desktop" \
      "${CHROOT_TMP}/usr/share/applications/nebula-contacts.desktop" \
      "${CHROOT_TMP}/usr/share/applications/nebula-dialer.desktop" \
      "${CHROOT_TMP}/usr/share/applications/nebula-tune.desktop" 2>/dev/null || true

# Create Desktop folders (no installer shortcut on desktop)
mkdir -p "${CHROOT_TMP}/home/nebula/Desktop" "${CHROOT_TMP}/etc/skel/Desktop"
chown -R 1000:1000 "${CHROOT_TMP}/home/nebula"

# Autostart Install NebulaOS on live session boot
mkdir -p "${CHROOT_TMP}/etc/xdg/autostart"
cp "${ROOT_DIR}/src/apps/desktop-entries/nebula-installer-autostart.desktop" "${CHROOT_TMP}/etc/xdg/autostart/nebula-installer-autostart.desktop"

# Rename GNOME Software to App Store
for sfd in "${CHROOT_TMP}/usr/share/applications/org.gnome.Software.desktop" "${CHROOT_TMP}/usr/share/applications/gnome-software.desktop"; do
    if [ -f "${sfd}" ]; then
        sed -i 's/^Name=.*/Name=App Store/' "${sfd}"
        sed -i 's/^Name\[it\]=.*/Name[it]=App Store/' "${sfd}"
    fi
done

# Hide unwanted applications per user request:
# - Software & Updates
# - Software Update
# - Web (Epiphany)
# - System Monitor
# - Advance Network Configuration
# - Document Viewer (Evince)
# - Disks (gnome-disk-utility)
# - Install Software
echo "[6c/8] Hiding excluded apps from application grid..."
for app_file in \
    "${CHROOT_TMP}/usr/share/applications/software-properties-gtk.desktop" \
    "${CHROOT_TMP}/usr/share/applications/software-properties-gnome.desktop" \
    "${CHROOT_TMP}/usr/share/applications/update-manager.desktop" \
    "${CHROOT_TMP}/usr/share/applications/nebula-updater.desktop" \
    "${CHROOT_TMP}/usr/share/applications/org.gnome.Epiphany.desktop" \
    "${CHROOT_TMP}/usr/share/applications/epiphany-browser.desktop" \
    "${CHROOT_TMP}/usr/share/applications/org.gnome.SystemMonitor.desktop" \
    "${CHROOT_TMP}/usr/share/applications/gnome-system-monitor.desktop" \
    "${CHROOT_TMP}/usr/share/applications/nm-connection-editor.desktop" \
    "${CHROOT_TMP}/usr/share/applications/org.gnome.Evince.desktop" \
    "${CHROOT_TMP}/usr/share/applications/evince.desktop" \
    "${CHROOT_TMP}/usr/share/applications/org.gnome.DiskUtility.desktop" \
    "${CHROOT_TMP}/usr/share/applications/gnome-disk-utility.desktop" \
    "${CHROOT_TMP}/usr/share/applications/install-software.desktop" \
    "${CHROOT_TMP}/usr/share/applications/org.gnome.eog.desktop" \
    "${CHROOT_TMP}/usr/share/applications/eog.desktop" \
    "${CHROOT_TMP}/usr/share/applications/installer.desktop" \
    "${CHROOT_TMP}/usr/share/applications/mynebula.desktop" \
    "${CHROOT_TMP}/usr/share/applications/nebula-recovery.desktop"; do
    if [ -f "${app_file}" ]; then
        if grep -q "NoDisplay=" "${app_file}"; then
            sed -i 's/NoDisplay=.*/NoDisplay=true/' "${app_file}"
        else
            echo "NoDisplay=true" >> "${app_file}"
        fi
    fi
done
rm -f "${CHROOT_TMP}/usr/share/applications/nebula-updater.desktop" 2>/dev/null || true

# GSchema Override (dock favorites order with Cheese, separator, trash, show-apps, Nebula theme, System Utilities)
rm -f "${CHROOT_TMP}/usr/share/glib-2.0/schemas/"*gnome-shell.gschema.override "${CHROOT_TMP}/usr/share/glib-2.0/schemas/00_nebulaos.gschema.override" 2>/dev/null || true
cp "${ROOT_DIR}/src/system/99_nebulaos.gschema.override" "${CHROOT_TMP}/usr/share/glib-2.0/schemas/99_nebulaos.gschema.override"
chroot "${CHROOT_TMP}" glib-compile-schemas /usr/share/glib-2.0/schemas

# MIME defaults for .deb and .desktop
mkdir -p "${CHROOT_TMP}/etc/xdg" "${CHROOT_TMP}/etc/skel/.config" "${CHROOT_TMP}/home/nebula/.config"
cat <<'MIMEOF' > "${CHROOT_TMP}/etc/xdg/mimeapps.list"
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
MIMEOF

cp "${CHROOT_TMP}/etc/xdg/mimeapps.list" "${CHROOT_TMP}/usr/share/applications/mimeapps.list"
cp "${CHROOT_TMP}/etc/xdg/mimeapps.list" "${CHROOT_TMP}/etc/skel/.config/mimeapps.list"
cp "${CHROOT_TMP}/etc/xdg/mimeapps.list" "${CHROOT_TMP}/home/nebula/.config/mimeapps.list"

# Purge any desktop widgets configuration
rm -rf "${CHROOT_TMP}/etc/skel/.config/nebulaos" "${CHROOT_TMP}/home/nebula/.config/nebulaos" 2>/dev/null || true
chown -R 1000:1000 "${CHROOT_TMP}/home/nebula/.config"



# Strip .deb from file-roller
for fr in "${CHROOT_TMP}/usr/share/applications/org.gnome.FileRoller.desktop" "${CHROOT_TMP}/usr/share/applications/file-roller.desktop"; do
    if [ -f "${fr}" ]; then
        sed -i 's/application\/vnd.debian.binary-package;//g' "${fr}"
        sed -i 's/application\/x-deb;//g' "${fr}"
        sed -i 's/application\/x-debian-package;//g' "${fr}"
    fi
done

chroot "${CHROOT_TMP}" update-desktop-database /usr/share/applications 2>/dev/null || true

# Ensure all .desktop files on Desktop are executable and trusted for direct launch
for dtf in "${CHROOT_TMP}/home/nebula/Desktop/"*.desktop "${CHROOT_TMP}/etc/skel/Desktop/"*.desktop; do
    [ -f "${dtf}" ] || continue
    chmod 755 "${dtf}"
    chroot "${CHROOT_TMP}" su - nebula -c "gio set ~/Desktop/$(basename "${dtf}") metadata::trusted true 2>/dev/null || true"
done

# Build OTA deb packages and register base nebula-desktop in system dpkg database
if [ -z "${DEB_VERSION:-}" ] && [ "$SYS_CHANNEL" = "delta" ] && [ -n "${DELTA_REV:-}" ]; then
    export DEB_VERSION="${BASE_V:-26.0.1}~rev${DELTA_REV}"
fi
bash "${ROOT_DIR}/scripts/build_ota_deb.sh"
DEB_FILE="$(ls -1 "${ROOT_DIR}/build/debs"/nebula-desktop_*_all.deb 2>/dev/null | head -1)"
if [ -n "${DEB_FILE}" ] && [ -f "${DEB_FILE}" ]; then
    cp "${DEB_FILE}" "${CHROOT_TMP}/tmp/nebula-desktop.deb"
    chroot "${CHROOT_TMP}" dpkg -i /tmp/nebula-desktop.deb 2>/dev/null || chroot "${CHROOT_TMP}" apt-get install -f -y
    rm -f "${CHROOT_TMP}/tmp/nebula-desktop.deb"
    rm -f "${CHROOT_TMP}/var/lib/nebulaos/ota_update_pending"
fi

echo "[7/8] Cleaning up and repacking SquashFS..."
chroot "${CHROOT_TMP}" apt-get clean
rm -rf "${CHROOT_TMP}/tmp/"* "${CHROOT_TMP}/var/tmp/"*
rm -f "${CHROOT_TMP}/var/lib/nebulaos/ota_update_pending"

cleanup
trap - EXIT

# Ensure empty essential mount points exist
mkdir -p "${CHROOT_TMP}"/{dev,proc,sys,run,tmp,mnt,media}
chmod 755 "${CHROOT_TMP}"/{dev,proc,sys,run}
chmod 1777 "${CHROOT_TMP}/tmp"

rm -f "${SQUASHFS}"
mksquashfs "${CHROOT_TMP}" "${SQUASHFS}" \
    -comp zstd -Xcompression-level 15 -b 1048576 -noappend

rm -rf "${CHROOT_TMP}"

echo "[8/8] Generating updated 26.0 ISO..."
bash "${ROOT_DIR}/scripts/build-iso.sh"

mkdir -p "${ROOT_DIR}/webserver/iso" 2>/dev/null || true
cp -f "${ROOT_DIR}/build/output/"*.iso "${ROOT_DIR}/webserver/iso/" 2>/dev/null || true

echo "=============================================================================="
echo " NEBULAOS 26.0 BUILT SUCCESSFULLY WITH NEBULA-SETUP & NEW CONFIGURATION!"
echo "=============================================================================="

