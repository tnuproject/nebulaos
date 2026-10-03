#!/bin/bash

rm -rf ~/.local/share/gnome-shell/extensions/gtk4-ding@smedius.gitlab.com/*
rm -rf .build
rm ./meson.build
mkdir .build
cp scripts/meson.build ./
meson setup --prefix=$HOME/.local/ --localedir=share/gnome-shell/extensions/gtk4-ding@smedius.gitlab.com/locale ./ .build
ninja -C .build install
rm -rf .build
rm ./meson.build

. /etc/lsb-release

if  [ $DISTRIB_ID = "Ubuntu" ] && (($(bc <<< "$DISTRIB_RELEASE > 22"))); then
    echo "Installing for Ubuntu Jammy...."
    rm -rf ~/.local/share/gnome-shell/extensions/gtk4-dingubuntu@smedius.gitlab.com
    mv ~/.local/share/gnome-shell/extensions/gtk4-ding@smedius.gitlab.com ~/.local/share/gnome-shell/extensions/gtk4-dingubuntu@smedius.gitlab.com
    sed -i "s#gtk4-ding@smedius#gtk4-dingubuntu@smedius#" ~/.local/share/gnome-shell/extensions/gtk4-dingubuntu@smedius.gitlab.com/metadata.json
    echo "Completed"
fi
