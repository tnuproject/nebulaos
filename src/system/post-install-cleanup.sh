#!/usr/bin/env bash
set -x

TARGET_USER="$1"
INSTALL_MODE="${2:-erase}"

# Remove all installer desktop files, binaries and autostart launchers from system
rm -f /usr/share/applications/installer.desktop \
      /usr/share/applications/install-nebula.desktop \
      /usr/share/applications/install-debian.desktop \
      /usr/share/applications/calamares.desktop \
      /usr/share/applications/nebula-installer-autostart.desktop \
      /usr/bin/install-nebula \
      /usr/bin/nebula-installer \
      /usr/bin/nebula-setup \
      /usr/bin/nebula-session-init \
      /etc/xdg/autostart/nebula-installer-autostart.desktop \
      /etc/xdg/autostart/calamares-desktop-icon.desktop \
      /etc/xdg/autostart/calamares.desktop 2>/dev/null || true

# Remove nebula-setup installer app and Calamares configs
rm -rf /etc/calamares /usr/lib/nebulaos/installer /usr/share/nebula-setup 2>/dev/null || true

# Remove desktop icons from all users and skel
rm -f /home/*/Desktop/installer.desktop \
      /home/*/Desktop/calamares.desktop \
      /home/*/Desktop/install-debian.desktop \
      /etc/skel/Desktop/installer.desktop \
      /etc/skel/Desktop/calamares.desktop \
      /etc/skel/Desktop/install-debian.desktop 2>/dev/null || true

# Remove live user 'nebula' and its home directory ONLY if the newly created user is not 'nebula'
if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "nebula" ]; then
    if id "nebula" &>/dev/null; then
        pkill -u nebula 2>/dev/null || true
        userdel -r -f nebula 2>/dev/null || true
    fi
    rm -rf /home/nebula 2>/dev/null || true
fi

# Configure GRUB depending on install mode
mkdir -p /etc/default/grub.d
if [ "$INSTALL_MODE" = "dualboot" ]; then
    # In dual boot mode, keep GRUB menu visible with a 5-second timeout and enable os-prober
    rm -f /etc/default/grub.d/00_nebula_silent.cfg 2>/dev/null || true
    if [ -f /etc/default/grub ]; then
        sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
        sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/' /etc/default/grub
        if grep -q "GRUB_DISABLE_OS_PROBER" /etc/default/grub; then
            sed -i 's/^GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' /etc/default/grub
        else
            echo "GRUB_DISABLE_OS_PROBER=false" >> /etc/default/grub
        fi
    fi
else
    # Single-OS mode: configure silent hidden GRUB
    if [ -f /etc/default/grub ]; then
        sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub
        sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=hidden/' /etc/default/grub
        if ! grep -q "GRUB_RECORDFAIL_TIMEOUT" /etc/default/grub; then
            echo "GRUB_RECORDFAIL_TIMEOUT=0" >> /etc/default/grub
        fi
        if ! grep -q "GRUB_HIDDEN_TIMEOUT_QUIET" /etc/default/grub; then
            echo "GRUB_HIDDEN_TIMEOUT_QUIET=true" >> /etc/default/grub
        fi
    fi
    cat << 'EOF' > /etc/default/grub.d/00_nebula_silent.cfg
GRUB_TIMEOUT=0
GRUB_TIMEOUT_STYLE=hidden
GRUB_RECORDFAIL_TIMEOUT=0
GRUB_HIDDEN_TIMEOUT_QUIET=true
EOF
fi

# Silence Debian 10_linux script so it never prints "Loading Linux" or "Launching NebulaOS"
if [ -f /etc/grub.d/10_linux ]; then
    sed -i 's/quiet_boot="0"/quiet_boot="1"/' /etc/grub.d/10_linux
    sed -i "s/echo[[:space:]]\+'\$(echo \"\$message\" | grub_quote)'/:/g" /etc/grub.d/10_linux 2>/dev/null || true
fi
if [ -f /etc/grub.d/00_header ]; then
    sed -i 's/quick_boot="0"/quick_boot="1"/' /etc/grub.d/00_header
fi

# Ensure OS logo is nebulaos-symbol in Settings About
if [ -f /etc/os-release ]; then
    sed -i 's/^LOGO=.*/LOGO=nebulaos-symbol/' /etc/os-release
fi
if [ -f /usr/lib/os-release ]; then
    sed -i 's/^LOGO=.*/LOGO=nebulaos-symbol/' /usr/lib/os-release
fi

# Ensure mime association for .desktop launcher
for mf in /etc/xdg/mimeapps.list /usr/share/applications/mimeapps.list; do
    if [ -f "$mf" ]; then
        if ! grep -q "application/x-desktop" "$mf"; then
            sed -i '/\[Default Applications\]/a application/x-desktop=nebula-desktop-launcher.desktop' "$mf" 2>/dev/null || true
        fi
    fi
done

if command -v update-grub &>/dev/null; then
    update-grub || true
fi

# Strip any residual echo Loading / Launching from generated grub.cfg
if [ -f /boot/grub/grub.cfg ]; then
    sed -i "/echo[[:space:]]*['\"].*Loading/d" /boot/grub/grub.cfg 2>/dev/null || true
    sed -i "/echo[[:space:]]*['\"].*Launching/d" /boot/grub/grub.cfg 2>/dev/null || true
fi
find /boot/efi -name "grub.cfg" -exec sed -i "/echo[[:space:]]*['\"].*Loading/d" {} + 2>/dev/null || true
find /boot/efi -name "grub.cfg" -exec sed -i "/echo[[:space:]]*['\"].*Launching/d" {} + 2>/dev/null || true

if [ -n "$TARGET_USER" ] && [ -d "/home/$TARGET_USER" ]; then
    chown -R "$TARGET_USER:$TARGET_USER" "/home/$TARGET_USER" 2>/dev/null || true
    chmod 700 "/home/$TARGET_USER" 2>/dev/null || true
    chmod -R u+rwX "/home/$TARGET_USER" 2>/dev/null || true
fi

# Configure GDM daemon.conf: strictly default to GNOME, disable autologin
mkdir -p /etc/gdm3
cat << 'GDMEOF' > /etc/gdm3/daemon.conf
[daemon]
AutomaticLoginEnable = false
WaylandEnable = true
DefaultSession = gnome.desktop

[security]

[xdmcp]

[chooser]

[debug]
GDMEOF
chmod 644 /etc/gdm3/daemon.conf

# Ensure AccountsService profile for target user with correct permissions
if [ -n "$TARGET_USER" ]; then
    mkdir -p /var/lib/AccountsService/users /var/lib/AccountsService/icons
    cat << ACCOFF > "/var/lib/AccountsService/users/$TARGET_USER"
[User]
Language=
Session=gnome
XSession=gnome
SystemAccount=false
Icon=/var/lib/AccountsService/icons/$TARGET_USER
ACCOFF
    chmod 700 /var/lib/AccountsService/users
    chmod 600 "/var/lib/AccountsService/users/$TARGET_USER"
    chown -R root:root /var/lib/AccountsService

    # Set .dmrc fallback in user home and skel
    mkdir -p "/home/$TARGET_USER" /etc/skel
    echo -e "[Desktop]\nSession=gnome" > "/home/$TARGET_USER/.dmrc"
    echo -e "[Desktop]\nSession=gnome" > /etc/skel/.dmrc
    chown "$TARGET_USER:$TARGET_USER" "/home/$TARGET_USER/.dmrc" 2>/dev/null || true
    chmod 644 "/home/$TARGET_USER/.dmrc" /etc/skel/.dmrc 2>/dev/null || true
fi

# Ensure default x-session-manager is gnome-session
if command -v update-alternatives &>/dev/null; then
    update-alternatives --set x-session-manager /usr/bin/gnome-session 2>/dev/null || true
fi

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

exit 0

