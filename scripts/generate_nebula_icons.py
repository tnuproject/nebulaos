#!/usr/bin/env python3
"""
NebulaOS Official Squircle Icon Pack Generator
Creates /usr/share/icons/Nebula from newiconpack/ SVGs and composites branded
applications (Firefox, VLC, custom system apps) onto the squircle background.
"""

import os
import sys
import shutil
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
NEWICONPACK_DIR = ROOT_DIR / "src" / "branding" / "icons_source"
HATTER_DIR = ROOT_DIR / "src" / "branding" / "icons" / "Hatter" / "scalable" / "apps"
CUSTOM_ICONS_DIR = ROOT_DIR / "src" / "branding" / "custom_icons"

DEST_THEME_DIR = ROOT_DIR / "src" / "branding" / "icons" / "Nebula"

# 1. Base mappings: SVG file from newiconpack -> target icon names (without .svg extension)
BASE_ICON_MAPPINGS = {
    "filemanager.svg": [
        "org.gnome.Nautilus",
        "nautilus",
        "system-file-manager",
        "file-manager",
        "org.gnome.Nautilus-symbolic"
    ],
    "music.svg": [
        "org.gnome.Music",
        "gnome-music",
        "rhythmbox",
        "media-player",
        "nebula-tune"
    ],
    "settings.svg": [
        "gnome-control-center",
        "org.gnome.Settings",
        "org.gnome.ControlCenter",
        "preferences-system",
        "system-settings",
        "nebula-settings"
    ],
    "photos.svg": [
        "org.gnome.eog",
        "eog",
        "org.gnome.Photos",
        "gnome-photos",
        "image-viewer",
        "accessories-image-viewer",
        "nebula-gallery"
    ],
    "notes.svg": [
        "org.gnome.TextEditor",
        "gnome-text-editor",
        "gedit",
        "org.gnome.gedit",
        "accessories-text-editor",
        "text-editor"
    ],
    "weather.svg": [
        "org.gnome.Weather",
        "gnome-weather",
        "org.gnome.Weather.Application"
    ],
    "calculator.svg": [
        "org.gnome.Calculator",
        "gnome-calculator",
        "accessories-calculator"
    ],
    "calendar.svg": [
        "org.gnome.Calendar",
        "gnome-calendar",
        "nebula-calendar"
    ],
    "camera.svg": [
        "org.gnome.Cheese",
        "cheese",
        "org.gnome.Camera",
        "camera",
        "camera-photo",
        "camera-web",
        "nebula-camera"
    ],
    "installer.svg": [
        "installer",
        "nebula-installer",
        "calamares",
        "io.calamares.calamares"
    ],
    "contacts.svg": [
        "org.gnome.Contacts",
        "gnome-contacts",
        "nebula-contacts"
    ],
    "dialer.svg": [
        "org.gnome.Calls",
        "calls",
        "call-start",
        "nebula-dialer"
    ],
    "email.svg": [
        "org.gnome.Geary",
        "geary",
        "evolution",
        "internet-mail"
    ],
    "Market.svg": [
        "gnome-software",
        "org.gnome.Software",
        "system-software-install",
        "software-center"
    ],
    "terminal.svg": [
        "gnome-terminal",
        "org.gnome.Terminal",
        "utilities-terminal",
        "terminal"
    ],
    "video_player.svg": [
        "totem",
        "org.gnome.Totem",
        "video-player"
    ],
    "launchpad.svg": [
        "view-app-grid",
        "view-grid",
        "launchpad",
        "gnome-launchpad"
    ],
    "tips.svg": [
        "tips",
        "dialog-information",
        "dialog-information-symbolic",
        "help-about"
    ],
    "Clock.svg": [
        "org.gnome.clocks",
        "gnome-clocks",
        "clocks",
        "org.gnome.clocks-symbolic",
        "nebula-clock"
    ],
    "folder.svg": [
        "folder",
        "folder-blue",
        "inode-directory"
    ]
}



def generate_index_theme(out_dir: Path):
    theme_index = """[Icon Theme]
Name=Nebula
Comment=NebulaOS Official Squircle Theme
Inherits=Adwaita,hicolor
Directories=scalable/apps,scalable/actions,scalable/categories,scalable/devices,scalable/mimetypes,scalable/places,scalable/status

[scalable/apps]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/actions]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/categories]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/devices]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/mimetypes]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/places]
Size=344
MinSize=16
MaxSize=512
Type=Scalable

[scalable/status]
Size=344
MinSize=16
MaxSize=512
Type=Scalable
"""
    with open(out_dir / "index.theme", "w", encoding="utf-8") as f:
        f.write(theme_index)

def create_firefox_squircle_svg() -> str:
    """
    Extract Firefox logo paths and gradients from Hatter's firefox.svg
    and composite them centered over the 344x344 white squircle.
    """
    hatter_firefox = HATTER_DIR / "firefox.svg"
    if not hatter_firefox.exists():
        raise FileNotFoundError(f"Missing {hatter_firefox}")

    with open(hatter_firefox, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Extract defs
    defs_match = re.search(r"<defs[^>]*>(.*?)</defs>", content, re.DOTALL)
    defs_content = defs_match.group(1) if defs_match else ""

    # Extract paths, excluding the background rect id="rect75" and drop shadow image
    # Keep path77, path78, path83, path79, path80, path81, path82, path84, path85, path86, path87
    paths = re.findall(r"(<path[^>]+/>)", content)
    logo_paths = [p for p in paths if 'id="rect75"' not in p]

    # Combine into 344x344 squircle
    # scale factor: original is 64x64, center 272x272 inside 344x344 -> scale 4.25, translate 36, 36
    firefox_squircle = f"""<svg width="344" height="344" viewBox="0 0 344 344" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <rect width="343.04" height="343.04" rx="120" fill="white"/>
  <defs>
    {defs_content}
  </defs>
  <g transform="translate(36, 36) scale(4.25)">
    {"".join(logo_paths)}
  </g>
</svg>
"""
    return firefox_squircle

def create_vlc_squircle_svg() -> str:
    """
    Composite VLC cone logo onto 344x344 white squircle.
    """
    hatter_vlc = HATTER_DIR / "vlc.svg"
    if not hatter_vlc.exists():
        raise FileNotFoundError(f"Missing {hatter_vlc}")

    with open(hatter_vlc, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    defs_match = re.search(r"<defs[^>]*>(.*?)</defs>", content, re.DOTALL)
    defs_content = defs_match.group(1) if defs_match else ""

    # Extract cone paths (path5, path5-5)
    paths = re.findall(r"(<path[^>]+/>)", content)

    vlc_squircle = f"""<svg width="344" height="344" viewBox="0 0 344 344" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  <rect width="343.04" height="343.04" rx="120" fill="white"/>
  <defs>
    {defs_content}
  </defs>
  <g transform="translate(36, 36) scale(4.25)">
    {"".join(paths)}
  </g>
</svg>
"""
    return vlc_squircle

def create_custom_app_squircle(svg_source_path: Path, bg_color="white", scale=0.62) -> str:
    """
    Embed a custom system SVG icon centered on a 344x344 squircle.
    """
    with open(svg_source_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Extract viewBox or width/height
    vb_match = re.search(r'viewBox="([^"]+)"', content)
    if vb_match:
        vb = vb_match.group(1)
        _, _, w, h = map(float, vb.split())
    else:
        w = h = 512.0

    # Extract inner elements between <svg...> and </svg>
    inner = re.sub(r"^.*?<svg[^>]*>", "", content, flags=re.DOTALL)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.DOTALL)

    target_size = 344.0 * scale
    offset = (344.0 - target_size) / 2.0
    s_factor = target_size / max(w, h)

    squircle = f"""<svg width="344" height="344" viewBox="0 0 344 344" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  <rect width="343.04" height="343.04" rx="120" fill="{bg_color}"/>
  <g transform="translate({offset:.2f}, {offset:.2f}) scale({s_factor:.4f})">
    {inner}
  </g>
</svg>
"""
    return squircle

def create_launchpad_immune_svg() -> str:
    """
    Generate an SVG that embeds the 344x344 launchpad bitmap as a base64 data URI.
    This makes the launchpad icon completely immune to GTK/librsvg symbolic recoloring
    (which would otherwise turn all 9 colored rects white on white).
    Falls back gracefully when rsvg-convert is not available.
    """
    import base64
    import shutil
    import subprocess

    png_cache = ROOT_DIR / "build" / "launchpad_344.png"
    src_svg = NEWICONPACK_DIR / "launchpad.svg"

    if not png_cache.exists():
        png_cache.parent.mkdir(parents=True, exist_ok=True)
        # Try rsvg-convert first
        if shutil.which("rsvg-convert"):
            subprocess.run(
                ["rsvg-convert", "-w", "344", "-h", "344", str(src_svg), "-o", str(png_cache)],
                check=True,
            )
        else:
            # Try cairosvg (pure-Python fallback)
            try:
                import cairosvg
                cairosvg.svg2png(url=str(src_svg), write_to=str(png_cache), output_width=344, output_height=344)
            except ImportError:
                # Neither tool available — embed the raw SVG directly (no PNG wrapping)
                print("  [warn] rsvg-convert not found, embedding raw SVG for launchpad icon")
                return src_svg.read_text(encoding="utf-8")

    png_bytes = png_cache.read_bytes()
    b64_str = base64.b64encode(png_bytes).decode("utf-8")
    return f"""<svg width="344" height="344" viewBox="0 0 344 344" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <image width="344" height="344" xlink:href="data:image/png;base64,{b64_str}"/>
</svg>
"""

def main():
    print(f"[*] Building Nebula Icon Theme in {DEST_THEME_DIR}...")
    if DEST_THEME_DIR.exists():
        shutil.rmtree(DEST_THEME_DIR)

    apps_dir = DEST_THEME_DIR / "scalable" / "apps"
    actions_dir = DEST_THEME_DIR / "scalable" / "actions"
    categories_dir = DEST_THEME_DIR / "scalable" / "categories"
    devices_dir = DEST_THEME_DIR / "scalable" / "devices"
    mimetypes_dir = DEST_THEME_DIR / "scalable" / "mimetypes"
    places_dir = DEST_THEME_DIR / "scalable" / "places"
    status_dir = DEST_THEME_DIR / "scalable" / "status"

    for d in [apps_dir, actions_dir, categories_dir, devices_dir, mimetypes_dir, places_dir, status_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generate_index_theme(DEST_THEME_DIR)

    # Copy background templates
    shutil.copy2(NEWICONPACK_DIR / "bg_white.svg", apps_dir / "bg_white.svg")
    shutil.copy2(NEWICONPACK_DIR / "bg_black.svg", apps_dir / "bg_black.svg")

    # Install base mappings from newiconpack
    for src_file, target_names in BASE_ICON_MAPPINGS.items():
        src_path = NEWICONPACK_DIR / src_file
        if not src_path.exists():
            print(f"[!] Warning: {src_path} not found!")
            continue

        for name in target_names:
            dest_svg = apps_dir / f"{name}.svg"
            shutil.copy2(src_path, dest_svg)
            if src_file == "folder.svg":
                shutil.copy2(src_path, places_dir / f"{name}.svg")

    # Copy Hatter places icons into Nebula places_dir
    hatter_places = ROOT_DIR / "src" / "branding" / "icons" / "Hatter" / "scalable" / "places"
    if hatter_places.exists():
        for f in hatter_places.glob("*.svg"):
            shutil.copy2(f, places_dir / f.name)

    # Deploy immune Launchpad SVG (immune to symbolic white recoloring)
    print("  -> Generating immune Launchpad squircle icons...")
    launchpad_svg_content = create_launchpad_immune_svg()
    for name in [
        "view-app-grid",
        "view-app-grid-symbolic",
        "view-grid",
        "view-grid-symbolic",
        "launchpad",
        "gnome-launchpad"
    ]:
        with open(apps_dir / f"{name}.svg", "w", encoding="utf-8") as f:
            f.write(launchpad_svg_content)
        with open(actions_dir / f"{name}.svg", "w", encoding="utf-8") as f:
            f.write(launchpad_svg_content)

    # Also update newiconpack launchpad and view-app-grid with immune SVG
    with open(NEWICONPACK_DIR / "view-app-grid.svg", "w", encoding="utf-8") as f:
        f.write(launchpad_svg_content)
    with open(NEWICONPACK_DIR / "view-app-grid-symbolic.svg", "w", encoding="utf-8") as f:
        f.write(launchpad_svg_content)

    # Generate and install composited Firefox squircle icon
    print("  -> Compositing Firefox squircle logo...")
    firefox_svg_content = create_firefox_squircle_svg()
    for name in ["firefox", "firefox-esr", "mozilla-firefox", "org.mozilla.firefox"]:
        with open(apps_dir / f"{name}.svg", "w", encoding="utf-8") as f:
            f.write(firefox_svg_content)

    # Generate and install composited VLC squircle icon
    print("  -> Compositing VLC squircle logo...")
    vlc_svg_content = create_vlc_squircle_svg()
    for name in ["vlc", "vlc-kb", "multimedia-vlc"]:
        with open(apps_dir / f"{name}.svg", "w", encoding="utf-8") as f:
            f.write(vlc_svg_content)

    # Generate and install custom app squircle icons
    print("  -> Compositing Custom Apps squircle icons...")
    installer_src = CUSTOM_ICONS_DIR / "Installer.svg"
    if installer_src.exists():
        installer_squircle = create_custom_app_squircle(installer_src, bg_color="white", scale=0.85)
        for name in ["installer", "nebula-installer"]:
            with open(apps_dir / f"{name}.svg", "w", encoding="utf-8") as f:
                f.write(installer_squircle)

    install_soft_src = CUSTOM_ICONS_DIR / "install-software.svg"
    if install_soft_src.exists():
        soft_squircle = create_custom_app_squircle(install_soft_src, bg_color="white", scale=0.85)
        with open(apps_dir / "install-software.svg", "w", encoding="utf-8") as f:
            f.write(soft_squircle)

    # Install Distributor and OS Logos
    version_badge = ROOT_DIR / "src" / "branding" / "logos" / "version-badge.svg"
    if version_badge.exists():
        shutil.copy2(version_badge, apps_dir / "distributor-logo.svg")
        shutil.copy2(version_badge, apps_dir / "debian-logo.svg")
        shutil.copy2(version_badge, places_dir / "distributor-logo.svg")

    # Install Installer icon directly from newiconpack/installer.svg if present
    new_installer = NEWICONPACK_DIR / "installer.svg"
    if new_installer.exists():
        shutil.copy2(new_installer, apps_dir / "installer.svg")
        shutil.copy2(new_installer, apps_dir / "nebula-installer.svg")
        shutil.copy2(new_installer, apps_dir / "calamares.svg")
        shutil.copy2(new_installer, apps_dir / "io.calamares.calamares.svg")

    # Universal Squircle Wrapping: Scan applications and wrap any non-squircle icons
    try:
        sys.path.insert(0, str(ROOT_DIR / "src" / "system"))
        import importlib
        wrap_desktop_file = importlib.import_module("nebula-icon-wrapper").wrap_desktop_file
        desktop_candidates = []
        for dpath in [Path("/usr/share/applications"), Path("/tmp/nebulaos-patch-chroot/usr/share/applications")]:
            if dpath.exists():
                desktop_candidates.extend(list(dpath.glob("*.desktop")))
        for df in desktop_candidates:
            wrap_desktop_file(df)
    except Exception as e:
        print(f"[!] Universal squircle pass note: {e}")

    # Install Wi-Fi status icons from svg/
    svg_dir = ROOT_DIR / "svg"
    wifi_full = svg_dir / "wifi_full.svg"
    wifi_mid = svg_dir / "wifi_middle.svg"

    wifi_empty = svg_dir / "wifi_empty.svg"

    if wifi_full.exists():
        for name in [
            "network-wireless-signal-excellent-symbolic",
            "network-wireless-connected-symbolic",
            "network-wireless-symbolic",
            "network-wireless-signal-excellent",
            "network-wireless-connected",
            "network-wireless"
        ]:
            shutil.copy2(wifi_full, status_dir / f"{name}.svg")

    if wifi_mid.exists():
        for name in [
            "network-wireless-signal-good-symbolic",
            "network-wireless-signal-ok-symbolic",
            "network-wireless-signal-good",
            "network-wireless-signal-ok"
        ]:
            shutil.copy2(wifi_mid, status_dir / f"{name}.svg")

    if wifi_empty.exists():
        for name in [
            "network-wireless-signal-weak-symbolic",
            "network-wireless-signal-none-symbolic",
            "network-wireless-signal-weak",
            "network-wireless-signal-none"
        ]:
            shutil.copy2(wifi_empty, status_dir / f"{name}.svg")

    # Clean all battery icons completely across theme so GNOME inherits the default original GNOME Adwaita battery icons
    for bat_file in DEST_THEME_DIR.rglob("*battery*"):
        bat_file.unlink(missing_ok=True)

    print(f"[OK] Successfully generated Nebula icon theme with {len(list(apps_dir.glob('*.svg')))} scalable application icons and {len(list(status_dir.glob('*.svg')))} status icons.")

if __name__ == "__main__":
    main()

