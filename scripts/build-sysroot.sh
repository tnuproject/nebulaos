#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Base Userspace Sysroot Builder
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

SYSROOT="${ROOT_DIR}/build/sysroot"

echo "=============================================================================="
echo " Assembling NebulaOS Sysroot: ${PRODUCT_NAME} ${VERSION} \"${CODENAME}\""
echo "=============================================================================="

rm -rf "${SYSROOT}"
mkdir -p "${SYSROOT}"

# 1. Standard Filesystem Hierarchy
echo "[sysroot] Creating filesystem hierarchy..."
mkdir -p "${SYSROOT}"/{bin,sbin,dev,proc,sys,run,tmp,home,root,media,mnt,opt}
mkdir -p "${SYSROOT}"/etc/{nebulaos,systemd,network,init.d}
mkdir -p "${SYSROOT}"/usr/{bin,sbin,lib,lib64,share/applications,share/nebulaos,share/plymouth/themes}
mkdir -p "${SYSROOT}"/var/{log,cache/neb,lib/neb,run,tmp}
mkdir -p "${SYSROOT}"/.snapshots

chmod 1777 "${SYSROOT}/tmp" "${SYSROOT}/var/tmp"

# 2. Symlinks for merged /usr
ln -sf usr/bin "${SYSROOT}/bin" 2>/dev/null || true
ln -sf usr/sbin "${SYSROOT}/sbin" 2>/dev/null || true
ln -sf usr/lib "${SYSROOT}/lib" 2>/dev/null || true
ln -sf usr/lib64 "${SYSROOT}/lib64" 2>/dev/null || true

# 3. Base Userspace Binaries (BusyBox suite)
echo "[sysroot] Installing base userspace utilities..."
BUSYBOX_BIN=$(command -v busybox || echo "/usr/bin/busybox")
if [ -f "${BUSYBOX_BIN}" ]; then
    cp "${BUSYBOX_BIN}" "${SYSROOT}/usr/bin/busybox"
    chmod 755 "${SYSROOT}/usr/bin/busybox"
    # Install core symlinks
    for app in sh bash ash ls cp mv rm mkdir rmdir cat chmod chown echo grep sed awk date uname hostname ps kill mount umount df du tar gzip zstd sleep id whoami login su sync reboot poweroff; do
        ln -sf busybox "${SYSROOT}/usr/bin/${app}"
    done
fi

# 4. Generate /etc/os-release
echo "[sysroot] Generating /etc/os-release from release.conf..."
envsubst < "${ROOT_DIR}/src/system/os-release.template" > "${SYSROOT}/etc/os-release"
chmod 644 "${SYSROOT}/etc/os-release"
ln -sf ../etc/os-release "${SYSROOT}/usr/lib/os-release"

# 5. System Configuration Files
echo "[sysroot] Generating system configurations (/etc/passwd, /etc/fstab, /etc/issue)..."
cat <<EOF > "${SYSROOT}/etc/hostname"
nebulaos
EOF

cat <<EOF > "${SYSROOT}/etc/hosts"
127.0.0.1   localhost localhost.localdomain nebulaos
::1         localhost ip6-localhost ip6-loopback
EOF

cat <<EOF > "${SYSROOT}/etc/fstab"
# /etc/fstab: static file system information
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
overlay         /               overlay defaults        0       0
proc            /proc           proc    defaults        0       0
sysfs           /sys            sysfs   defaults        0       0
devtmpfs        /dev            devtmpfs defaults       0       0
tmpfs           /run            tmpfs   defaults,mode=755 0     0
tmpfs           /tmp            tmpfs   defaults,mode=1777 0    0
EOF

cat <<EOF > "${SYSROOT}/etc/passwd"
root:x:0:0:root:/root:/bin/sh
nebula:x:1000:1000:NebulaOS Live User:/home/nebula:/bin/sh
EOF

cat <<EOF > "${SYSROOT}/etc/group"
root:x:0:
wheel:x:10:root,nebula
sudo:x:27:nebula
users:x:100:nebula
nebula:x:1000:
EOF

cat <<EOF > "${SYSROOT}/etc/shadow"
root::19000:0:99999:7:::
nebula::19000:0:99999:7:::
EOF
chmod 600 "${SYSROOT}/etc/shadow"

cat <<EOF > "${SYSROOT}/etc/issue"
${PRODUCT_NAME} ${VERSION} "${CODENAME}" (x86_64) - \l
Kernel \r on an \m

EOF

# 6. /Applications folder & nebula-appd daemon
echo "[sysroot] Setting up /Applications and nebula-appd..."
mkdir -p "${SYSROOT}/Applications"
chmod 777 "${SYSROOT}/Applications"

mkdir -p "${SYSROOT}/usr/lib/nebulaos"
cp "${ROOT_DIR}/src/apps/app-daemon/nebula-appd.py" "${SYSROOT}/usr/lib/nebulaos/nebula-appd.py"
chmod 755 "${SYSROOT}/usr/lib/nebulaos/nebula-appd.py"

mkdir -p "${SYSROOT}/etc/systemd/system"
cp "${ROOT_DIR}/src/apps/app-daemon/nebula-appd.service" "${SYSROOT}/etc/systemd/system/nebula-appd.service"

# 7. Install Package Manager (neb)
echo "[sysroot] Installing neb package manager..."
cp "${ROOT_DIR}/src/package-manager/bin/neb" "${SYSROOT}/usr/bin/neb"
chmod 755 "${SYSROOT}/usr/bin/neb"

# 8. Install Settings & Desktop Applications
echo "[sysroot] Installing system desktop entries and settings..."
mkdir -p "${SYSROOT}/usr/lib/nebulaos/settings"
cp "${ROOT_DIR}/src/apps/settings/about.py" "${SYSROOT}/usr/lib/nebulaos/settings/about.py"
chmod 755 "${SYSROOT}/usr/lib/nebulaos/settings/about.py"

# Wrapper for settings
cat <<'EOF' > "${SYSROOT}/usr/bin/settings"
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "/usr/lib/nebulaos/settings")
import about
about.print_about_screen()
EOF
chmod 755 "${SYSROOT}/usr/bin/settings"

# Install .desktop files
cp "${ROOT_DIR}/src/apps/desktop-entries/"*.desktop "${SYSROOT}/usr/share/applications/"

# 9. Install Branding Assets & Hatter Icon Pack
echo "[sysroot] Installing branding assets..."
mkdir -p "${SYSROOT}/usr/share/nebulaos/branding"
cp -r "${ROOT_DIR}/src/branding/logos" "${SYSROOT}/usr/share/nebulaos/branding/" 2>/dev/null || true
cp -r "${ROOT_DIR}/src/branding/wallpapers" "${SYSROOT}/usr/share/nebulaos/branding/" 2>/dev/null || true
cp -r "${ROOT_DIR}/src/release/assets" "${SYSROOT}/usr/share/nebulaos/branding/" 2>/dev/null || true

# Hatter Icon Theme Integration
mkdir -p "${SYSROOT}/usr/share/icons"
if [ -d "${ROOT_DIR}/src/branding/icons/Hatter" ]; then
    echo "[sysroot] Found Hatter icon pack! Installing to /usr/share/icons/Hatter..."
    cp -r "${ROOT_DIR}/src/branding/icons/Hatter" "${SYSROOT}/usr/share/icons/"
elif [ -d "${ROOT_DIR}/src/branding/icons" ] && [ "$(ls -A "${ROOT_DIR}/src/branding/icons")" ]; then
    echo "[sysroot] Installing icon pack from src/branding/icons to /usr/share/icons/..."
    cp -r "${ROOT_DIR}/src/branding/icons/"* "${SYSROOT}/usr/share/icons/"
fi

# Set default GTK theme and Hatter icon theme
mkdir -p "${SYSROOT}/etc/gtk-3.0"
cat <<'EOF' > "${SYSROOT}/etc/gtk-3.0/settings.ini"
[Settings]
gtk-theme-name = Adwaita-dark
gtk-icon-theme-name = Hatter
gtk-font-name = Cantarell 11
gtk-cursor-theme-name = Adwaita
gtk-application-prefer-dark-theme = 1
EOF

# Install Plymouth Theme (using user's customized assets in src/branding/plymouth)
mkdir -p "${SYSROOT}/usr/share/plymouth/themes/nebulaos-breeze"
cp -r "${ROOT_DIR}/src/branding/plymouth/nebulaos-breeze/"* "${SYSROOT}/usr/share/plymouth/themes/nebulaos-breeze/"

# 9. Simple Init System (/sbin/init)
cat <<'EOF' > "${SYSROOT}/sbin/init"
#!/bin/sh
# NebulaOS Core System Initialization
export PATH=/usr/bin:/usr/sbin:/bin:/sbin

mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mkdir -p /dev/pts /dev/shm
mount -t devpts devpts /dev/pts 2>/dev/null || true
mount -t tmpfs tmpfs /dev/shm 2>/dev/null || true

# Set hostname
if [ -f /etc/hostname ]; then
    hostname $(cat /etc/hostname)
fi

echo ""
echo "================================================================================"
cat /etc/issue
echo "================================================================================"
echo " Welcome to NebulaOS Live System!"
echo " Type 'settings' to view system information."
echo " Type 'neb list' to inspect installed packages."
echo "================================================================================"
echo ""

# Launch auto-login shell on primary console
exec /bin/sh
EOF
chmod 755 "${SYSROOT}/sbin/init"

echo "[sysroot] Assembly complete at ${SYSROOT}"
