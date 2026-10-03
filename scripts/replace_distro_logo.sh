#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Distro Logo Replacement Script for GNOME Settings ("About System")
#
# Searches for and replaces all Debian/distributor logo files in /usr/share/pixmaps
# and /usr/share/icons with the official NebulaOS symbol, keeping the exact same
# file name and format (.png or .svg), with backup copies created.
#
# Usage:
#   sudo ./scripts/replace_distro_logo.sh [TARGET_ROOT]
# ==============================================================================

set -euo pipefail

TARGET_ROOT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOGOS_SRC="${ROOT_DIR}/src/branding/logos"
SVG_SRC="${LOGOS_SRC}/nebulaos-symbol.svg"
PNG_DEFAULT="${LOGOS_SRC}/nebulaos-symbol.png"

echo "=============================================================================="
echo " Replacing Distro Logo in GNOME Settings / Pixmaps / Icons"
echo " Target Root: ${TARGET_ROOT:-/ (Live System)}"
echo "=============================================================================="

# Helper to safely replace with backup
replace_file() {
    local target="$1"
    local source="$2"

    if [ -e "${target}" ] || [ -L "${target}" ]; then
        if [ ! -f "${target}.nebula.bak" ] && [ ! -L "${target}" ]; then
            cp -p "${target}" "${target}.nebula.bak" 2>/dev/null || true
        fi
        rm -f "${target}"
        cp -f "${source}" "${target}"
        chmod 644 "${target}" 2>/dev/null || true
        echo "  [replaced] ${target}"
    fi
}

# ── 1. Target: /usr/share/pixmaps ─────────────────────────────────────────────

PIXMAPS_DIR="${TARGET_ROOT}/usr/share/pixmaps"
mkdir -p "${PIXMAPS_DIR}"

echo "[1/4] Processing ${PIXMAPS_DIR}..."

# Replace any existing debian/distributor/system logo files in pixmaps
for pattern in "debian-logo*" "debian-swirl*" "distributor-logo*" "system-logo*" "system-logo-white*" "desktop-base*"; do
    find "${PIXMAPS_DIR}" -maxdepth 1 -name "${pattern}" 2>/dev/null | while read -r img; do
        ext="${img##*.}"
        if [ "${ext}" = "svg" ]; then
            replace_file "${img}" "${SVG_SRC}"
        elif [ "${ext}" = "png" ]; then
            replace_file "${img}" "${PNG_DEFAULT}"
        fi
    done
done

# Ensure direct named files exist in /usr/share/pixmaps
for name in debian-logo debian-swirl distributor-logo system-logo nebulaos-symbol; do
    cp -f "${SVG_SRC}" "${PIXMAPS_DIR}/${name}.svg"
    cp -f "${PNG_DEFAULT}" "${PIXMAPS_DIR}/${name}.png"
    chmod 644 "${PIXMAPS_DIR}/${name}.svg" "${PIXMAPS_DIR}/${name}.png"
done

# ── 2. Target: /usr/share/icons ───────────────────────────────────────────────

ICONS_DIR="${TARGET_ROOT}/usr/share/icons"
echo "[2/4] Processing icon themes in ${ICONS_DIR}..."

# Find and replace all debian-logo / distributor-logo in all themes and resolutions
if [ -d "${ICONS_DIR}" ]; then
    for pattern in "*debian-logo*" "*debian-swirl*" "*distributor-logo*" "*system-logo*"; do
        find "${ICONS_DIR}" -type f -name "${pattern}" 2>/dev/null | while read -r icon_path; do
            ext="${icon_path##*.}"
            # Extract resolution if in a sized folder (e.g., 64x64, 128x128)
            dir_name="$(basename "$(dirname "$(dirname "${icon_path}")")")"
            size="${dir_name%x*}"

            if [ "${ext}" = "svg" ]; then
                replace_file "${icon_path}" "${SVG_SRC}"
            elif [ "${ext}" = "png" ]; then
                sized_png="${LOGOS_SRC}/nebulaos-symbol-${size}.png"
                if [ -f "${sized_png}" ]; then
                    replace_file "${icon_path}" "${sized_png}"
                else
                    replace_file "${icon_path}" "${PNG_DEFAULT}"
                fi
            fi
        done
    done

    # Ensure Nebula, hicolor, and Adwaita have explicit apps & places logos in scalable and 64x64, 128x128
    for theme in Nebula hicolor Adwaita; do
        for cat in apps places; do
            # Scalable
            mkdir -p "${ICONS_DIR}/${theme}/scalable/${cat}"
            for logo_name in nebulaos-symbol distributor-logo debian-logo debian-swirl system-logo; do
                cp -f "${SVG_SRC}" "${ICONS_DIR}/${theme}/scalable/${cat}/${logo_name}.svg"
                chmod 644 "${ICONS_DIR}/${theme}/scalable/${cat}/${logo_name}.svg"
            done

            # Common sizes
            for sz in 16 22 24 32 48 64 96 128 256; do
                sz_dir="${ICONS_DIR}/${theme}/${sz}x${sz}/${cat}"
                mkdir -p "${sz_dir}"
                sized_src="${LOGOS_SRC}/nebulaos-symbol-${sz}.png"
                [ -f "${sized_src}" ] || sized_src="${PNG_DEFAULT}"
                for logo_name in nebulaos-symbol distributor-logo debian-logo debian-swirl system-logo; do
                    cp -f "${sized_src}" "${sz_dir}/${logo_name}.png"
                    chmod 644 "${sz_dir}/${logo_name}.png"
                done
            done
        done
    done
fi

# Process desktop-base logos
DB_DIR="${TARGET_ROOT}/usr/share/desktop-base"
if [ -d "${DB_DIR}" ]; then
    find "${DB_DIR}" -type f \( -name "*logo*" -o -name "*debian*" \) 2>/dev/null | while read -r db_path; do
        ext="${db_path##*.}"
        if [ "${ext}" = "svg" ]; then
            replace_file "${db_path}" "${SVG_SRC}"
        elif [ "${ext}" = "png" ]; then
            replace_file "${db_path}" "${PNG_DEFAULT}"
        fi
    done
fi

# ── 3. Target: /etc/os-release & /usr/lib/os-release ─────────────────────────

echo "[3/4] Ensuring LOGO=nebulaos-symbol in os-release..."

for osf in "${TARGET_ROOT}/etc/os-release" "${TARGET_ROOT}/usr/lib/os-release"; do
    if [ -f "${osf}" ]; then
        if grep -q "^LOGO=" "${osf}"; then
            sed -i 's/^LOGO=.*/LOGO=nebulaos-symbol/' "${osf}"
        else
            echo "LOGO=nebulaos-symbol" >> "${osf}"
        fi
        echo "  [updated] ${osf}"
    fi
done

# ── 4. Update GTK Icon Caches ─────────────────────────────────────────────────

echo "[4/4] Updating GTK icon caches..."
for theme in Nebula hicolor Adwaita; do
    tdir="${ICONS_DIR}/${theme}"
    if [ -d "${tdir}" ]; then
        if command -v gtk-update-icon-cache >/dev/null 2>&1; then
            gtk-update-icon-cache -f -t "${tdir}" 2>/dev/null || true
            echo "  [cache updated] ${tdir}"
        fi
    fi
done

echo "=============================================================================="
echo " Distro Logo Successfully Replaced with NebulaOS Symbol!"
echo " GNOME Settings ('About System') will now display the NebulaOS logo."
echo "=============================================================================="
