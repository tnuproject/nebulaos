"""
Nebula Recovery — Network Management Backend
Wraps nmcli to scan, inspect, and connect to Wi-Fi and wired networks.
"""

import subprocess
import shutil
import re
from typing import List, Dict, Optional


def has_nmcli() -> bool:
    return shutil.which("nmcli") is not None


def get_network_status() -> Dict[str, str]:
    """
    Returns current networking status:
    {'connected': bool, 'type': 'wifi'|'ethernet'|'none', 'ssid': str, 'ip': str}
    """
    status = {
        "connected": False,
        "type": "none",
        "name": "",
        "ip": ""
    }

    if not has_nmcli():
        # Fallback check via ip route
        try:
            res = subprocess.run(["ip", "route", "get", "1.1.1.1"],
                                 capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                status["connected"] = True
                m = re.search(r"src\s+([0-9\.]+)", res.stdout)
                if m:
                    status["ip"] = m.group(1)
        except Exception:
            pass
        return status

    try:
        # Check active connections
        res = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
                             capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().splitlines()
            for line in lines:
                parts = line.split(":")
                if len(parts) >= 2:
                    conn_name, conn_type = parts[0], parts[1]
                    if "wireless" in conn_type or "wifi" in conn_type:
                        status["connected"] = True
                        status["type"] = "wifi"
                        status["name"] = conn_name
                        break
                    elif "ethernet" in conn_type:
                        status["connected"] = True
                        status["type"] = "ethernet"
                        status["name"] = conn_name

        # Get IP address
        ip_res = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
        if ip_res.returncode == 0 and ip_res.stdout.strip():
            status["ip"] = ip_res.stdout.strip().split()[0]
    except Exception:
        pass

    return status


def scan_wifi_networks() -> List[Dict[str, any]]:
    """
    Scans nearby Wi-Fi networks using nmcli.
    Returns list of dicts:
    [{'ssid': str, 'signal': int, 'security': str, 'in_use': bool}]
    """
    networks = []
    if not has_nmcli():
        return networks

    try:
        # Request rescan
        subprocess.run(["nmcli", "device", "wifi", "rescan"], capture_output=True, timeout=5)
    except Exception:
        pass

    try:
        res = subprocess.run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,BARS", "device", "wifi", "list"],
                             capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            seen_ssids = set()
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split(":")
                if len(parts) >= 4:
                    in_use = (parts[0].strip() == "*")
                    ssid = parts[1].strip()
                    if not ssid or ssid in seen_ssids:
                        continue
                    seen_ssids.add(ssid)

                    try:
                        signal = int(parts[2].strip())
                    except ValueError:
                        signal = 50

                    security = parts[3].strip() if len(parts) > 3 else ""
                    is_secured = bool(security and security != "--")

                    networks.append({
                        "ssid": ssid,
                        "signal": signal,
                        "security": security,
                        "is_secured": is_secured,
                        "in_use": in_use
                    })
    except Exception:
        pass

    # Sort: in_use first, then by signal strength descending
    networks.sort(key=lambda n: (not n["in_use"], -n["signal"]))
    return networks


def connect_wifi(ssid: str, password: Optional[str] = None) -> tuple[bool, str]:
    """
    Connect to a Wi-Fi network.
    Returns (success: bool, message: str)
    """
    if not has_nmcli():
        return False, "NetworkManager CLI (nmcli) is not available."

    try:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            return True, f"Successfully connected to {ssid}"
        else:
            err = res.stderr.strip() or res.stdout.strip() or "Connection failed"
            return False, err
    except subprocess.TimeoutExpired:
        return False, "Connection attempt timed out."
    except Exception as e:
        return False, str(e)
