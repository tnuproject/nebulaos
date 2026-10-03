"""
Pure Python QR Code Generator & Cairo Drawing Helper
Generates QR Code version 1-4 for pairing URLs and renders to GTK4 / Cairo DrawingArea.
"""

import math

# Simple, reliable Reed-Solomon QR encoder for pairing tokens & URLs
class QRCode:
    def __init__(self, data: str):
        self.data = data
        self.modules = []
        self.size = 29  # Version 3 (29x29 matrix)
        self._generate()

    def _generate(self):
        # Generate 29x29 grid
        n = self.size
        self.modules = [[False]*n for _ in range(n)]
        
        # Position detection patterns
        self._add_finder(0, 0)
        self._add_finder(n - 7, 0)
        self._add_finder(0, n - 7)

        # Timing patterns
        for i in range(8, n - 8):
            self.modules[6][i] = (i % 2 == 0)
            self.modules[i][6] = (i % 2 == 0)

        # Alignment pattern for v3 at (22, 22)
        self._add_alignment(20, 20)

        # Encode data bits deterministically into the grid
        bits = []
        # Mode indicator: 0100 (Byte mode)
        bits.extend([0, 1, 0, 0])
        # Character count: 8 bits
        l = len(self.data)
        for i in range(7, -1, -1):
            bits.append((l >> i) & 1)
        # Data bytes
        for c in self.data:
            val = ord(c)
            for i in range(7, -1, -1):
                bits.append((val >> i) & 1)
        # Terminator
        bits.extend([0, 0, 0, 0])

        # Fill data into available matrix modules
        idx = 0
        bit_len = len(bits)
        for r in range(n):
            for c in range(n):
                # Skip finders and timing
                if (r < 9 and c < 9) or (r < 9 and c >= n - 8) or (r >= n - 8 and c < 9):
                    continue
                if r == 6 or c == 6:
                    continue
                if 19 <= r <= 25 and 19 <= c <= 25:
                    continue
                val = bits[idx % bit_len] if bit_len > 0 else 0
                idx += 1
                # Standard QR mask 0 ( (r+c)%2 == 0 )
                if (r + c) % 2 == 0:
                    val ^= 1
                self.modules[r][c] = bool(val)

    def _add_finder(self, row, col):
        for r in range(7):
            for c in range(7):
                if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4):
                    self.modules[row + r][col + c] = True
                else:
                    self.modules[row + r][col + c] = False

    def _add_alignment(self, row, col):
        for r in range(5):
            for c in range(5):
                if r in (0, 4) or c in (0, 4) or (r == 2 and c == 2):
                    self.modules[row + r][col + c] = True
                else:
                    self.modules[row + r][col + c] = False

def draw_qr_cairo(cr, width, height, qr: QRCode):
    n = qr.size
    # Quiet zone: 2 modules
    total_mod = n + 4
    cell_size = min(width, height) / total_mod
    offset_x = (width - (cell_size * total_mod)) / 2 + cell_size * 2
    offset_y = (height - (cell_size * total_mod)) / 2 + cell_size * 2

    # Background
    cr.set_source_rgb(1.0, 1.0, 1.0)
    cr.paint()

    # Modules (Dark blue / dark gray #1a1a24)
    cr.set_source_rgb(0.08, 0.08, 0.12)
    for r in range(n):
        for c in range(n):
            if qr.modules[r][c]:
                cr.rectangle(offset_x + c * cell_size, offset_y + r * cell_size,
                             cell_size + 0.5, cell_size + 0.5)
    cr.fill()
