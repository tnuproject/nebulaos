#!/usr/bin/env bash
set -e

rm -f /tmp/qmp.sock /tmp/qemu_screen.ppm /mnt/d/nebulaos/build/qemu_desktop_new.png

qemu-system-x86_64 -enable-kvm -m 4096 -smp 4 \
    -cdrom /mnt/d/nebulaos/build/output/NebulaOS-26.0-Plains-x86_64.iso \
    -boot d -vga virtio -display none \
    -qmp unix:/tmp/qmp.sock,server=on,wait=off &
QEMU_PID=$!

echo "Waiting 45 seconds for GNOME desktop to boot..."
sleep 45

python3 - << 'PYEOF'
import socket, json, time
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("/tmp/qmp.sock")
s.recv(1024)
s.sendall(b'{"execute": "qmp_capabilities"}\n')
time.sleep(0.5)
s.recv(1024)
s.sendall(b'{"execute": "screendump", "arguments": {"filename": "/tmp/qemu_screen.ppm"}}\n')
time.sleep(1)
s.recv(1024)
s.close()
PYEOF

kill $QEMU_PID 2>/dev/null || true
wait $QEMU_PID 2>/dev/null || true

if [ -f /tmp/qemu_screen.ppm ]; then
    python3 -c "
from PIL import Image
Image.open('/tmp/qemu_screen.ppm').save('/mnt/d/nebulaos/build/qemu_desktop_new.png')
print('SUCCESS: Screenshot saved to /mnt/d/nebulaos/build/qemu_desktop_new.png')
" 2>/dev/null || cp /tmp/qemu_screen.ppm /mnt/d/nebulaos/build/qemu_screen.ppm
fi
