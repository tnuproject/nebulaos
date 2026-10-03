#!/usr/bin/env python3
"""
NebulaOS Boot Recovery Interceptor
Monitors early boot (Plymouth) for recovery keystrokes:
- Command+R / Super+R
- Ctrl+R
- Alt+R
- Key 'r' / 'R'
- Kernel parameter 'nebula.recovery=1' or 'recovery'

When triggered, creates /run/nebula-recovery-trigger and notifies Plymouth.
"""

import os
import sys
import glob
import struct
import select
import time
import subprocess

TRIGGER_FILE = "/run/nebula-recovery-trigger"
CMDLINE_FILE = "/proc/cmdline"

# Linux input event codes
EV_KEY = 1
KEY_R = 19
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97
KEY_LEFTALT = 56
KEY_RIGHTALT = 100
KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126

# struct input_event format (64-bit Linux: timeval (16 bytes) + type (2) + code (2) + value (4) = 24 bytes)
EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


def check_cmdline() -> bool:
    try:
        if os.path.exists(CMDLINE_FILE):
            with open(CMDLINE_FILE, "r") as f:
                cmdline = f.read()
                if "nebula.recovery=1" in cmdline or " recovery" in cmdline:
                    return True
    except Exception:
        pass
    return False


def notify_plymouth(msg: str = "Entering NebulaOS Recovery…"):
    try:
        subprocess.run(["plymouth", "display-message", f"--text={msg}"], timeout=2)
    except Exception:
        pass


def trigger_recovery():
    try:
        with open(TRIGGER_FILE, "w") as f:
            f.write("1\n")
    except Exception:
        pass
    notify_plymouth()
    print("[nebula-recovery-watcher] Recovery triggered!", file=sys.stderr)


def open_input_devices():
    fds = []
    for path in glob.glob("/dev/input/event*"):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            fds.append(fd)
        except Exception:
            continue
    return fds


def watch_inputs(timeout_seconds: float = 12.0):
    start_time = time.time()
    fds = open_input_devices()

    # Plymouth keystroke watcher helper in background
    plymouth_proc = None
    try:
        plymouth_proc = subprocess.Popen(
            ["plymouth", "watch-keystroke", "--keys=rR\x12", f"--command=touch {TRIGGER_FILE}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    modifiers_down = set()

    try:
        while time.time() - start_time < timeout_seconds:
            if os.path.exists(TRIGGER_FILE):
                return True

            if not fds:
                fds = open_input_devices()
                if not fds:
                    time.sleep(0.1)
                    continue

            r, _, _ = select.select(fds, [], [], 0.1)
            for fd in r:
                try:
                    data = os.read(fd, EVENT_SIZE)
                    if len(data) >= EVENT_SIZE:
                        _, _, ev_type, code, val = struct.unpack(EVENT_FORMAT, data[:EVENT_SIZE])
                        if ev_type == EV_KEY:
                            if val in (1, 2):  # press or repeat
                                if code in (KEY_LEFTMETA, KEY_RIGHTMETA, KEY_LEFTCTRL, KEY_RIGHTCTRL, KEY_LEFTALT, KEY_RIGHTALT):
                                    modifiers_down.add(code)
                                elif code == KEY_R:
                                    # Triggered! (Either 'r' by itself or with Super/Ctrl/Alt)
                                    trigger_recovery()
                                    return True
                            elif val == 0:  # release
                                modifiers_down.discard(code)
                except Exception:
                    continue

    finally:
        for fd in fds:
            try:
                os.close(fd)
            except Exception:
                pass
        if plymouth_proc:
            try:
                plymouth_proc.terminate()
            except Exception:
                pass

    return os.path.exists(TRIGGER_FILE)


def main():
    if check_cmdline():
        trigger_recovery()
        sys.exit(0)

    # Watch inputs for up to 10 seconds during bootsplash
    if watch_inputs(timeout_seconds=10.0):
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
