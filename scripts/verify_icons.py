import os

hatter_apps = set()
base_dir = "/mnt/d/nebulaos/src/branding/icons/Hatter"
for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith(('.svg', '.png')):
            hatter_apps.add(os.path.splitext(f)[0])

target_icons = {
    "app-store": ["Appstore", "software-store", "system-software-installer", "system-software-install"],
    "installer": ["system-os-installer", "system-installer", "system-software-installer"],
    "calculator": ["accessories-calculator", "Calculator", "gnome-calculator", "calc"],
    "weather": ["weather", "aweather", "weather-clear", "gnome-weather"],
    "planet-browser": ["browser", "internet-web-browser", "web-browser", "applications-webbrowsers"],
    "developer": ["utilities-terminal", "accessories-text-editor", "atom-text-editor", "applications-development"],
    "settings": ["preferences-system", "gnome-settings"],
    "restore-utility": ["timeshift", "preferences-system-backup", "system-backup"],
    "files": ["system-file-manager", "org.gnome.Nautilus"],
    "system-monitor": ["utilities-system-monitor", "gnome-system-monitor"],
    "disk-utility": ["gnome-disks", "drive-harddisk"],
    "hardware": ["computer", "preferences-desktop-display"],
    "security": ["security-high", "preferences-desktop-cryptography"],
    "services": ["system-run", "applications-system"],
    "software-update": ["system-software-update", "software-update-available"]
}

for app, candidates in target_icons.items():
    found = [c for c in candidates if c in hatter_apps]
    print(f"{app}: candidates={candidates} -> MATCHED: {found[0] if found else 'NONE'}")
