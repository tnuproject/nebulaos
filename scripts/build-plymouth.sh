#!/usr/bin/env bash
# ==============================================================================
# NebulaOS — Plymouth Bootsplash Theme Builder
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${ROOT_DIR}/src/release/release.conf"

STAGE_DIR="${ROOT_DIR}/build/plymouth/nebulaos-breeze"
mkdir -p "${STAGE_DIR}"

echo "[plymouth] Building ${PLYMOUTH_THEME} theme for ${PRODUCT_NAME} ${VERSION}..."

# Copy theme configuration and script
cp "${ROOT_DIR}/src/branding/plymouth/nebulaos-breeze/nebulaos-breeze.plymouth" "${STAGE_DIR}/"
cp "${ROOT_DIR}/src/branding/plymouth/nebulaos-breeze/nebulaos-breeze.script" "${STAGE_DIR}/"

# Generate crisp boot splash logo.png
python3 - <<EOF
from PIL import Image, ImageDraw
import math

size = (256, 256)
img = Image.new("RGBA", size, (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Center and radius
cx, cy = 128, 128

# Outer radiant ring
for r in range(80, 96):
    alpha = int(255 * (1.0 - abs(r - 88) / 8.0))
    # Electric Cyan & Violet Gradient
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(56, 189, 248, alpha), width=1)

# Dynamic orbital accents
draw.arc([cx - 70, cy - 70, cx + 70, cy + 70], start=30, end=210, fill=(129, 140, 248, 240), width=6)
draw.arc([cx - 52, cy - 52, cx + 52, cy + 52], start=180, end=340, fill=(236, 72, 153, 240), width=5)

# Stellar Core
draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(248, 250, 252, 255))
draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(15, 23, 42, 255))
draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(56, 189, 248, 255))

img.save("${STAGE_DIR}/logo.png", "PNG")
print("Generated Plymouth bootsplash asset: ${STAGE_DIR}/logo.png")
EOF

echo "[plymouth] Theme build complete: ${STAGE_DIR}"
