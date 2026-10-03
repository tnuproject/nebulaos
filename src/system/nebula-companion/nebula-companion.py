#!/usr/bin/env python3
"""
Nebula Companion Daemon
Manages device pairing with the MyNebula Android app, PetalDrop peer-to-peer file transfers,
and Cloud photo gallery access from the user's Pictures directory.
"""

import os
import sys
import json
import time
import socket
import select
import threading
import hashlib
import mimetypes
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 53317
BEACON_PORT = 53318

CONFIG_DIR = os.path.expanduser("~/.config/nebula")
PAIRING_FILE = os.path.join(CONFIG_DIR, "companion_pairing.json")
CACHE_DIR = os.path.expanduser("~/.cache/nebula/thumbnails")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Screen Mirroring State
# ─────────────────────────────────────────────────────────────────────────────
mirror_lock = threading.Lock()
mirror_condition = threading.Condition(mirror_lock)
latest_mirror_frame = None
mirror_active = False
mirror_client_proc = None

# ─────────────────────────────────────────────────────────────────────────────
# Helper: Get primary local IP address
# ─────────────────────────────────────────────────────────────────────────────
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# ─────────────────────────────────────────────────────────────────────────────
# Pairing State
# ─────────────────────────────────────────────────────────────────────────────
class PairingManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        if os.path.exists(PAIRING_FILE):
            try:
                with open(PAIRING_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        token = f"NB-{int(time.time()) % 1000000:06d}"
        return {
            "device_name": socket.gethostname(),
            "pairing_token": token,
            "paired_device": None
        }

    def save(self):
        with self.lock:
            with open(PAIRING_FILE, "w") as f:
                json.dump(self.data, f, indent=2)

    def get_status(self):
        with self.lock:
            return {
                "device_name": self.data.get("device_name", socket.gethostname()),
                "local_ip": get_local_ip(),
                "port": PORT,
                "pairing_token": self.data.get("pairing_token"),
                "is_paired": self.data.get("paired_device") is not None,
                "paired_device_name": (self.data.get("paired_device") or {}).get("name"),
                "paired_device_id": (self.data.get("paired_device") or {}).get("id")
            }

    def pair(self, token, device_name, device_id, client_ip=None, phone_secret=None):
        with self.lock:
            current = self.data.get("paired_device")
            if current:
                # If already paired with this device_id or secret, acknowledge and refresh IP permanently
                if current.get("id") == device_id or (phone_secret and current.get("secret") == phone_secret):
                    current["last_ip"] = client_ip
                    if device_name:
                        current["name"] = device_name
                    self.save()
                    return True, current["secret"]
                else:
                    return False, "Already paired with another device. Unpair it first from that device."

            if token and token != self.data.get("pairing_token"):
                return False, "Invalid pairing token"

            sec = phone_secret or hashlib.sha256(f"{device_id}-{time.time()}".encode()).hexdigest()[:32]
            self.data["paired_device"] = {
                "name": device_name,
                "id": device_id,
                "secret": sec,
                "paired_at": time.time(),
                "last_ip": client_ip
            }
        self.save()
        return True, sec

    def unpair(self, phone_secret=None, is_local=False):
        with self.lock:
            current = self.data.get("paired_device")
            if not current:
                return True, "No device paired"
            if not is_local and phone_secret and current.get("secret") != phone_secret:
                return False, "Unauthorized unpair request"
            self.data["paired_device"] = None
            self.data["pairing_token"] = f"NB-{int(time.time()) % 1000000:06d}"
        self.save()
        return True, "Unpaired successfully"

pairing_mgr = PairingManager()

phone_events = []
phone_events_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Pictures / Cloud Gallery Scanner
# ─────────────────────────────────────────────────────────────────────────────
def get_pictures_dir():
    # Check XDG user dir or fallback to ~/Pictures / ~/Immagini
    user_dirs = os.path.expanduser("~/.config/user-dirs.dirs")
    if os.path.exists(user_dirs):
        try:
            with open(user_dirs, "r") as f:
                for line in f:
                    if line.startswith("XDG_PICTURES_DIR"):
                        raw = line.split("=", 1)[1].strip().strip('"')
                        path = raw.replace("$HOME", os.path.expanduser("~"))
                        if os.path.isdir(path):
                            return path
        except Exception:
            pass
    for candidate in [os.path.expanduser("~/Pictures"), os.path.expanduser("~/Immagini")]:
        if os.path.isdir(candidate):
            return candidate
    p = os.path.expanduser("~/Pictures")
    os.makedirs(p, exist_ok=True)
    return p

def scan_pictures():
    pics_dir = get_pictures_dir()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".svg"}
    items = []
    try:
        for root, _, files in os.walk(pics_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in allowed_exts:
                    full_path = os.path.join(root, file)
                    try:
                        stat = os.stat(full_path)
                        rel_path = os.path.relpath(full_path, pics_dir)
                        file_id = hashlib.md5(rel_path.encode()).hexdigest()
                        items.append({
                            "id": file_id,
                            "filename": file,
                            "rel_path": rel_path,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "mime": mimetypes.guess_type(file)[0] or "image/jpeg"
                        })
                    except Exception:
                        pass
    except Exception:
        pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items

def get_picture_by_id(file_id):
    pics = scan_pictures()
    for p in pics:
        if p["id"] == file_id:
            full_path = os.path.join(get_pictures_dir(), p["rel_path"])
            if os.path.exists(full_path):
                return full_path, p
    return None, None

# ─────────────────────────────────────────────────────────────────────────────
# Peer Discovery (PetalDrop)
# ─────────────────────────────────────────────────────────────────────────────
discovered_peers = {}
peers_lock = threading.Lock()

def start_discovery():
    def broadcaster():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while True:
            try:
                status = pairing_mgr.get_status()
                msg = json.dumps({
                    "type": "petaldrop_beacon",
                    "device_name": status["device_name"],
                    "ip": status["local_ip"],
                    "port": PORT,
                    "is_laptop": True,
                    "pairing_token": status.get("pairing_token"),
                    "is_paired": status.get("is_paired"),
                    "paired_device_id": status.get("paired_device_id")
                }).encode()
                sock.sendto(msg, ('<broadcast>', BEACON_PORT))
            except Exception:
                pass
            time.sleep(3)

    def listener():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', BEACON_PORT))
        except Exception:
            return
        while True:
            try:
                data, addr = sock.recvfrom(2048)
                payload = json.loads(data.decode())
                if payload.get("type") == "petaldrop_beacon":
                    peer_ip = payload.get("ip") or addr[0]
                    # Don't list ourselves
                    if peer_ip == get_local_ip() and payload.get("port") == PORT:
                        continue
                    with peers_lock:
                        discovered_peers[peer_ip] = {
                            "name": payload.get("device_name", "Unknown Device"),
                            "ip": peer_ip,
                            "port": payload.get("port", PORT),
                            "is_laptop": payload.get("is_laptop", False),
                            "last_seen": time.time()
                        }
            except Exception:
                pass

    t1 = threading.Thread(target=broadcaster, daemon=True)
    t2 = threading.Thread(target=listener, daemon=True)
    t1.start()
    t2.start()

start_discovery()

MOBILE_CLIENT_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>MyNebula — Android Companion</title>
  <style>
    :root {
      --bg: #1e1e1e;
      --card-bg: #27272a;
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #3584e4;
      --accent-hover: #1c71d8;
      --text: #ffffff;
      --text-dim: rgba(255, 255, 255, 0.65);
      --danger: #e01b24;
      --success: #33d17a;
      --nav-bg: #222225;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Poppins", sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: var(--nav-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .badge {
      width: 32px; height: 32px; border-radius: 999px;
      background: linear-gradient(135deg, #3584e4, #62a0ea);
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 12px rgba(53, 132, 228, 0.35);
    }
    .badge svg { width: 18px; height: 18px; fill: #fff; }
    h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
    .status-badge {
      font-size: 12px; font-weight: 500; padding: 4px 10px; border-radius: 999px;
      background: rgba(255, 255, 255, 0.08); color: var(--text-dim);
      display: flex; align-items: center; gap: 6px;
    }
    .status-badge.online { background: rgba(51, 209, 122, 0.15); color: var(--success); }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
    main { flex: 1; padding: 18px; max-width: 580px; margin: 0 auto; width: 100%; padding-bottom: 90px; }
    .tab-view { display: none; }
    .tab-view.active { display: block; animation: fadeIn 0.18s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 20px;
      margin-bottom: 16px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
    .card-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .card-sub { font-size: 13px; color: var(--text-dim); line-height: 1.4; margin-bottom: 16px; }
    .form-group { margin-bottom: 14px; }
    label { display: block; font-size: 12px; font-weight: 500; color: var(--text-dim); margin-bottom: 6px; }
    input[type="text"] {
      width: 100%;
      background: rgba(0,0,0,0.3);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 12px 14px;
      color: #fff;
      font-size: 14px;
      outline: none;
    }
    input[type="text"]:focus { border-color: var(--accent); }
    .btn {
      width: 100%;
      padding: 12px 18px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 600;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background 0.15s, transform 0.05s;
    }
    .btn:active { transform: scale(0.98); }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-danger { background: rgba(224, 27, 36, 0.18); color: #ff6b6b; border: 1px solid rgba(224, 27, 36, 0.3); margin-top: 14px; }
    .btn-danger:hover { background: var(--danger); color: #fff; }
    .info-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px; }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: var(--text-dim); }
    .info-val { font-weight: 500; }
    .drop-box {
      border: 2px dashed rgba(255, 255, 255, 0.22);
      border-radius: 18px;
      padding: 30px 16px;
      text-align: center;
      cursor: pointer;
      background: rgba(255, 255, 255, 0.02);
      transition: all 0.2s;
      margin-bottom: 14px;
    }
    .drop-box:hover { border-color: var(--accent); background: rgba(53, 132, 228, 0.08); }
    .drop-icon svg { width: 44px; height: 44px; fill: var(--accent); margin-bottom: 10px; }
    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      gap: 10px;
    }
    .gallery-thumb {
      aspect-ratio: 1;
      border-radius: 12px;
      overflow: hidden;
      background: rgba(0,0,0,0.3);
      border: 1px solid var(--card-border);
      position: relative;
      cursor: pointer;
    }
    .gallery-thumb img { width: 100%; height: 100%; object-fit: cover; }
    .gallery-caption {
      position: absolute; bottom: 0; left: 0; right: 0;
      background: linear-gradient(transparent, rgba(0,0,0,0.85));
      font-size: 10px; padding: 4px 6px; color: #fff;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    nav {
      position: fixed;
      bottom: 0; left: 0; right: 0;
      background: var(--nav-bg);
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: space-around;
      padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
      z-index: 50;
    }
    .nav-btn {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      background: none;
      border: none;
      color: var(--text-dim);
      cursor: pointer;
      font-size: 11px;
      font-weight: 500;
      padding: 6px 0;
    }
    .nav-btn svg { width: 22px; height: 22px; fill: currentColor; }
    .nav-btn.active { color: var(--accent); }
    .lightbox {
      display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.92);
      z-index: 100; flex-direction: column; align-items: center; justify-content: center; padding: 16px;
    }
    .lightbox.open { display: flex; }
    .lightbox img { max-width: 95%; max-height: 75vh; border-radius: 12px; object-fit: contain; }
    .lightbox-actions { display: flex; gap: 12px; margin-top: 14px; }
    .toast {
      position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
      background: rgba(30, 30, 34, 0.95); border: 1px solid var(--card-border);
      padding: 10px 18px; border-radius: 999px; font-size: 13px; font-weight: 500;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5); pointer-events: none; opacity: 0;
      transition: opacity 0.2s; z-index: 150;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="badge">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
      </div>
      <h1>MyNebula</h1>
    </div>
    <div id="status-badge" class="status-badge">
      <span class="dot"></span>
      <span id="status-text">Searching...</span>
    </div>
  </header>

  <main>
    <!-- TAB 1: DEVICE PAIRING -->
    <div id="tab-device" class="tab-view active">
      <!-- Not Paired Card -->
      <div id="unpaired-card" class="card">
        <div class="card-title">
          <svg style="width:20px;height:20px;fill:var(--accent)" viewBox="0 0 24 24"><path d="M17 1.01L7 1c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-1.99-2-1.99zM17 19H7V5h10v14z"/></svg>
          Pair with NebulaOS
        </div>
        <p class="card-sub">Enter the PIN generated by your device to pair this phone with NebulaOS.</p>
        <div class="form-group">
          <label>Pairing PIN (e.g. NB-123456)</label>
          <input type="text" id="pair-token" placeholder="NB-000000" maxlength="12">
        </div>
        <div class="form-group">
          <label>Your Phone Name</label>
          <input type="text" id="device-name" placeholder="Android Phone">
        </div>
        <button class="btn btn-primary" onclick="pairWithLaptop()">Pair Device</button>
      </div>

      <!-- Paired Card -->
      <div id="paired-card" class="card" style="display:none">
        <div class="card-title">
          <svg style="width:20px;height:20px;fill:var(--success)" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
          Device Paired
        </div>
        <p class="card-sub">This smartphone is connected to your NebulaOS device.</p>
        <div class="info-row">
          <span class="info-label">Device:</span>
          <span id="laptop-name" class="info-val">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">IP Address:</span>
          <span id="laptop-ip" class="info-val">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">Cloud Photos:</span>
          <span id="laptop-pics-count" class="info-val">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">PetalDrop Status:</span>
          <span class="info-val" style="color:var(--success)">Active & Ready</span>
        </div>
        <button class="btn btn-danger" onclick="unpairFromLaptop()">Unpair Device</button>
      </div>
    </div>

    <!-- TAB 2: PETALDROP -->
    <div id="tab-drop" class="tab-view">
      <div class="card">
        <div class="card-title">
          <svg style="width:20px;height:20px;fill:var(--accent)" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          PetalDrop — File Transfer
        </div>
        <p class="card-sub">Instantly send photos, videos, and files from your phone directly to your NebulaOS device.</p>

        <div class="drop-box" onclick="document.getElementById('file-input').click()">
          <div class="drop-icon">
            <svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
          </div>
          <div style="font-weight:600;font-size:14px;margin-bottom:4px;">Select media to send</div>
          <div style="font-size:12px;color:var(--text-dim)">Tap to choose a file or take a photo</div>
          <input type="file" id="file-input" style="display:none" onchange="handleFileSelected(event)">
        </div>

        <div id="selected-file-info" style="display:none;margin-bottom:14px;" class="info-row">
          <span id="selected-file-name" class="info-val" style="color:var(--accent)">—</span>
          <span id="selected-file-size" class="info-label">—</span>
        </div>

        <button id="send-drop-btn" class="btn btn-primary" style="display:none" onclick="sendSelectedFile()">Send to NebulaOS via PetalDrop</button>
      </div>
    </div>

    <!-- TAB 3: CLOUD GALLERY -->
    <div id="tab-gallery" class="tab-view">
      <div class="card">
        <div class="card-title">
          <svg style="width:20px;height:20px;fill:var(--accent)" viewBox="0 0 24 24"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
          Device Cloud Gallery
        </div>
        <p class="card-sub">Browse, view, and download offline photos from your device's Pictures folder.</p>
        <button class="btn btn-secondary" style="margin-bottom:14px;" onclick="fetchGallery()">Refresh Gallery</button>
        <div id="gallery-container" class="gallery-grid">
          <!-- Dynamically populated -->
        </div>
      </div>
    </div>
  </main>

  <nav>
    <button class="nav-btn active" onclick="switchTab('tab-device', this)">
      <svg viewBox="0 0 24 24"><path d="M17 1.01L7 1c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-1.99-2-1.99zM17 19H7V5h10v14z"/></svg>
      Device
    </button>
    <button class="nav-btn" onclick="switchTab('tab-drop', this)">
      <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      PetalDrop
    </button>
    <button class="nav-btn" onclick="switchTab('tab-gallery', this)">
      <svg viewBox="0 0 24 24"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
      Cloud
    </button>
  </nav>

  <!-- Lightbox Modal -->
  <div id="lightbox" class="lightbox" onclick="closeLightbox(event)">
    <img id="lightbox-img" src="" alt="Preview">
    <div class="lightbox-actions" onclick="event.stopPropagation()">
      <a id="lightbox-download" class="btn btn-primary" style="padding:10px 18px;" download>Download Offline</a>
      <button class="btn btn-secondary" style="padding:10px 18px;" onclick="closeLightbox()">Close</button>
    </div>
  </div>

  <div id="toast" class="toast"></div>

  <script>
    let currentFile = null;

    function showToast(msg) {
      const t = document.getElementById("toast");
      t.innerText = msg;
      t.classList.add("show");
      setTimeout(() => t.classList.remove("show"), 2800);
    }

    function switchTab(tabId, btn) {
      document.querySelectorAll(".tab-view").forEach(el => el.classList.remove("active"));
      document.querySelectorAll(".nav-btn").forEach(el => el.classList.remove("active"));
      document.getElementById(tabId).classList.add("active");
      if (btn) btn.classList.add("active");
      if (tabId === "tab-gallery") fetchGallery();
    }

    function getDeviceId() {
      let id = localStorage.getItem("mynebula_device_id");
      if (!id) {
        id = "android-" + Math.random().toString(36).substring(2, 10);
        localStorage.setItem("mynebula_device_id", id);
      }
      return id;
    }

    async function checkStatus() {
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const badge = document.getElementById("status-badge");
        const statusText = document.getElementById("status-text");

        const secret = localStorage.getItem("mynebula_secret");
        const myId = getDeviceId();

        if (data.is_paired && (data.paired_device_id === myId || secret)) {
          badge.classList.add("online");
          statusText.innerText = "Connected";
          document.getElementById("unpaired-card").style.display = "none";
          document.getElementById("paired-card").style.display = "block";
          document.getElementById("laptop-name").innerText = data.device_name || "NebulaOS Device";
          document.getElementById("laptop-ip").innerText = data.local_ip || window.location.hostname;
          document.getElementById("laptop-pics-count").innerText = data.pictures_count + " photos";
        } else {
          badge.classList.remove("online");
          statusText.innerText = "Not paired";
          document.getElementById("unpaired-card").style.display = "block";
          document.getElementById("paired-card").style.display = "none";
        }
      } catch (e) {
        document.getElementById("status-text").innerText = "Offline";
      }
    }

    async function pairWithLaptop() {
      const token = document.getElementById("pair-token").value.trim().toUpperCase();
      let devName = document.getElementById("device-name").value.trim();
      if (!token) { showToast("Please enter the pairing PIN"); return; }
      if (!devName) devName = "Android Phone";

      const devId = getDeviceId();
      try {
        const res = await fetch("/api/pair", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, device_name: devName, device_id: devId })
        });
        const data = await res.json();
        if (data.success) {
          localStorage.setItem("mynebula_secret", data.phone_secret);
          localStorage.setItem("mynebula_device_name", devName);
          showToast("Device paired successfully!");
          checkStatus();
        } else {
          showToast("Error: " + (data.error || "Invalid PIN"));
        }
      } catch (e) {
        showToast("Connection error with device");
      }
    }

    async function unpairFromLaptop() {
      if (!confirm("Are you sure you want to unpair this phone from your NebulaOS device?")) return;
      const secret = localStorage.getItem("mynebula_secret") || "";
      try {
        const res = await fetch("/api/unpair", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone_secret: secret })
        });
        const data = await res.json();
        if (data.success) {
          localStorage.removeItem("mynebula_secret");
          showToast("Device unpaired.");
          checkStatus();
        } else {
          showToast("Error during unpairing");
        }
      } catch (e) {
        showToast("Connection error");
      }
    }

    function handleFileSelected(e) {
      const file = e.target.files[0];
      if (!file) return;
      currentFile = file;
      document.getElementById("selected-file-name").innerText = file.name;
      document.getElementById("selected-file-size").innerText = (file.size / 1024 / 1024).toFixed(2) + " MB";
      document.getElementById("selected-file-info").style.display = "flex";
      document.getElementById("send-drop-btn").style.display = "block";
    }

    async function sendSelectedFile() {
      if (!currentFile) return;
      const btn = document.getElementById("send-drop-btn");
      btn.innerText = "Sending...";
      btn.disabled = true;

      try {
        const buffer = await currentFile.arrayBuffer();
        const res = await fetch("/api/drop/receive", {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-File-Name": currentFile.name
          },
          body: buffer
        });
        const data = await res.json();
        if (data.success) {
          showToast("✓ File sent successfully to NebulaOS!");
          document.getElementById("file-input").value = "";
          document.getElementById("selected-file-info").style.display = "none";
          btn.style.display = "none";
          currentFile = null;
        } else {
          showToast("Error sending file");
        }
      } catch (e) {
        showToast("Transfer error");
      } finally {
        btn.innerText = "Send to NebulaOS via PetalDrop";
        btn.disabled = false;
      }
    }

    async function fetchGallery() {
      const container = document.getElementById("gallery-container");
      container.innerHTML = "<div style='color:var(--text-dim);grid-column:1/-1;text-align:center;'>Loading photos...</div>";
      try {
        const res = await fetch("/api/gallery");
        const data = await res.json();
        const pics = data.pictures || [];
        container.innerHTML = "";
        if (pics.length === 0) {
          container.innerHTML = "<div style='color:var(--text-dim);grid-column:1/-1;text-align:center;padding:20px;'>No pictures found in your device's Pictures folder.</div>";
          return;
        }
        pics.forEach(p => {
          const div = document.createElement("div");
          div.className = "gallery-thumb";
          div.onclick = () => openLightbox(`/api/gallery/file?id=${p.id}`, p.filename);
          div.innerHTML = `
            <img src="/api/gallery/file?id=${p.id}" loading="lazy" alt="${p.filename}">
            <div class="gallery-caption">${p.filename}</div>
          `;
          container.appendChild(div);
        });
      } catch (e) {
        container.innerHTML = "<div style='color:var(--danger);grid-column:1/-1;text-align:center;'>Errore caricamento galleria.</div>";
      }
    }

    function openLightbox(url, filename) {
      const lb = document.getElementById("lightbox");
      const img = document.getElementById("lightbox-img");
      const dl = document.getElementById("lightbox-download");
      img.src = url;
      dl.href = url;
      dl.download = filename;
      lb.classList.add("open");
    }

    function closeLightbox() {
      document.getElementById("lightbox").classList.remove("open");
    }

    // Auto-fill token from URL query string if provided (?pair=NB-XXXXXX or ?token=NB-XXXXXX)
    window.addEventListener("DOMContentLoaded", () => {
      const urlParams = new URLSearchParams(window.location.search);
      const pairToken = urlParams.get("pair") || urlParams.get("token");
      if (pairToken) {
        document.getElementById("pair-token").value = pairToken.toUpperCase();
      }
      const savedName = localStorage.getItem("mynebula_device_name");
      if (savedName) document.getElementById("device-name").value = savedName;
      checkStatus();
      setInterval(checkStatus, 5000);
    });
  </script>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────────────────────
# HTTP Request Handler
# ─────────────────────────────────────────────────────────────────────────────
class CompanionHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence verbose logging
        pass

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-File-Name")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ["", "/", "/index.html", "/mynebula", "/pair"]:
            for html_path in [
                "/usr/share/mynebula/app/src/main/assets/web/index.html",
                "/usr/share/mynebula/web/index.html",
                os.path.join(os.path.dirname(__file__), "../../apps/mynebula-android/app/src/main/assets/web/index.html")
            ]:
                if os.path.exists(html_path):
                    try:
                        with open(html_path, "rb") as f:
                            content = f.read()
                        self.send_response(200)
                        self._send_cors()
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    except Exception:
                        pass
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(MOBILE_CLIENT_HTML.encode("utf-8"))
            return


        elif path in ["/mynebula.apk", "/app.apk"]:
            for apk_path in [
                "/usr/share/mynebula/mynebula.apk",
                "/usr/share/mynebula/app/build/outputs/apk/debug/app-debug.apk",
                os.path.join(os.path.dirname(__file__), "../../apps/mynebula-android/mynebula.apk"),
                os.path.join(os.path.dirname(__file__), "../../apps/mynebula-android/app/build/outputs/apk/debug/app-debug.apk")
            ]:
                if os.path.exists(apk_path):
                    self.send_response(200)
                    self._send_cors()
                    self.send_header("Content-Type", "application/vnd.android.package-archive")
                    self.send_header("Content-Length", str(os.path.getsize(apk_path)))
                    self.send_header("Content-Disposition", 'attachment; filename="mynebula.apk"')
                    self.end_headers()
                    with open(apk_path, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                    return
            self.send_error(404, "APK not found")
            return

        elif path == "/api/status":
            if pairing_mgr.data.get("paired_device"):
                pairing_mgr.data["paired_device"]["last_ip"] = self.client_address[0]
            status = pairing_mgr.get_status()
            status["pictures_count"] = len(scan_pictures())
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())

        elif path == "/api/gallery":
            pics = scan_pictures()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"pictures": pics}).encode())

        elif path == "/api/gallery/file":
            file_id = query.get("id", [""])[0]
            file_path, pic_info = get_picture_by_id(file_id)
            if not file_path or not os.path.exists(file_path):
                self.send_error(404, "File not found")
                return

            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", pic_info["mime"])
            self.send_header("Content-Length", str(os.path.getsize(file_path)))
            self.send_header("Content-Disposition", f'inline; filename="{pic_info["filename"]}"')
            self.end_headers()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)

        elif path == "/api/drop/peers":
            now = time.time()
            with peers_lock:
                # Remove peers not seen in last 12 seconds
                active = [p for p in discovered_peers.values() if now - p["last_seen"] < 12]
            
            # If a phone is paired, always prioritize / include it
            status = pairing_mgr.get_status()
            if status["is_paired"]:
                active.insert(0, {
                    "name": f"{status['paired_device_name']} (Paired)",
                    "ip": "paired",
                    "is_paired": True
                })

            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"peers": active}).encode())

        elif path == "/api/contacts":
            contacts_file = os.path.expanduser("~/.config/nebula/contacts.json")
            contacts = []
            if os.path.exists(contacts_file):
                try:
                    with open(contacts_file) as f:
                        contacts = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"contacts": contacts}).encode())

        elif path == "/api/call/status":
            call_file = "/run/nebula-active-call.json"
            call_info = {"active": False}
            if os.path.exists(call_file):
                try:
                    with open(call_file) as f:
                        call_info = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(call_info).encode())

        elif path == "/api/phone/events":
            with phone_events_lock:
                events = list(phone_events)
                phone_events.clear()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"events": events}).encode())

        elif path == "/api/mirror/status":
            with mirror_lock:
                status = {"active": mirror_active}
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())

        elif path == "/api/mirror/stream":
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--frame")
            self.end_headers()
            last_sent_frame = None
            try:
                while True:
                    with mirror_condition:
                        # Wait for a new frame
                        mirror_condition.wait_for(lambda: (latest_mirror_frame is not None and latest_mirror_frame != last_sent_frame) or not mirror_active, timeout=2.0)
                        if not mirror_active and latest_mirror_frame is None:
                            break
                        frame_data = latest_mirror_frame
                    if frame_data and frame_data != last_sent_frame:
                        last_sent_frame = frame_data
                        header = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame_data)).encode() + b"\r\n\r\n"
                        self.wfile.write(header)
                        self.wfile.write(frame_data)
                        self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError, Exception):
                pass
            return

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        global mirror_active, mirror_client_proc, latest_mirror_frame
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        if path == "/api/pair":
            try:
                data = json.loads(body.decode())
                token = data.get("token", "").strip().upper()
                dev_name = data.get("device_name", "Android Phone")
                dev_id = data.get("device_id", "phone-default")
                client_ip = self.client_address[0]
                phone_sec = data.get("phone_secret")
                ok, res = pairing_mgr.pair(token, dev_name, dev_id, client_ip, phone_secret=phone_sec)
                self.send_response(200 if ok else 400)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if ok:
                    self.wfile.write(json.dumps({"success": True, "phone_secret": res}).encode())
                    # Notify desktop that a device was paired!
                    try:
                        subprocess.Popen(["notify-send", "-a", "Nebula Companion",
                                          "Device Paired", f"{dev_name} paired successfully with NebulaOS!"])
                    except Exception:
                        pass
                else:
                    self.wfile.write(json.dumps({"success": False, "error": res}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/unpair":
            try:
                data = json.loads(body.decode())
                secret = data.get("phone_secret", "")
                is_local = (self.client_address[0] in ["127.0.0.1", "localhost", "::1"])
                ok, res = pairing_mgr.unpair(secret, is_local=is_local)
                self.send_response(200 if ok else 403)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": ok, "message": res}).encode())
                if ok:
                    try:
                        subprocess.Popen(["notify-send", "-a", "Nebula Companion",
                                          "Device Unpaired", "The mobile device has been unpaired."])
                    except Exception:
                        pass
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/drop/receive":
            # Receiving a file from PetalDrop
            filename = self.headers.get("X-File-Name", f"received_{int(time.time())}.bin")
            save_dir = os.path.expanduser("~/Downloads")
            ext = os.path.splitext(filename)[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp", ".svg"]:
                save_dir = get_pictures_dir()
            os.makedirs(save_dir, exist_ok=True)
            target_path = os.path.join(save_dir, filename)

            # Avoid overwrite
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(save_dir, f"{base}_{counter}{ext}")
                counter += 1

            with open(target_path, "wb") as f:
                f.write(body)

            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "saved_path": target_path}).encode())

            # Notify user
            try:
                subprocess.Popen(["notify-send", "-a", "PetalDrop", "-i", "document-send-symbolic",
                                  "File received via PetalDrop", f"Saved: {os.path.basename(target_path)}"])
            except Exception:
                pass

        elif path == "/api/drop/push":
            # PC wants to send a file to a remote peer
            try:
                data = json.loads(body.decode())
                file_path = data.get("file_path", "")
                target_ip = data.get("target_ip", "")
                target_port = data.get("target_port", PORT)

                if target_ip == "paired" or not target_ip:
                    paired_dev = pairing_mgr.data.get("paired_device") or {}
                    target_ip = paired_dev.get("last_ip")
                    if not target_ip:
                        self.send_response(400)
                        self._send_cors()
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": "Paired device IP unknown. Open MyNebula on phone to sync."}).encode())
                        return

                if not os.path.exists(file_path):
                    self.send_error(404, "Local file not found")
                    return

                filename = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                # Send HTTP POST to target peer's /api/drop/receive
                import urllib.request
                req = urllib.request.Request(
                    f"http://{target_ip}:{target_port}/api/drop/receive",
                    data=file_bytes,
                    headers={"X-File-Name": filename, "Content-Type": "application/octet-stream"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_body = resp.read()

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "remote_resp": json.loads(res_body)}).encode())
            except Exception as e:
                self.send_response(500)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())

        elif path == "/api/contacts":
            try:
                data = json.loads(body.decode())
                contacts_list = data.get("contacts", [])
                contacts_file = os.path.expanduser("~/.config/nebula/contacts.json")
                with open(contacts_file, "w") as f:
                    json.dump(contacts_list, f, indent=2)
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "count": len(contacts_list)}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/call/dial":
            try:
                data = json.loads(body.decode())
                num = data.get("number", "")
                nm = data.get("name", num)
                call_file = "/run/nebula-active-call.json"
                call_info = {"active": True, "state": "calling", "number": num, "name": nm, "start_time": time.time()}
                with open(call_file, "w") as f:
                    json.dump(call_info, f)

                # Queue dial event for mobile client
                with phone_events_lock:
                    phone_events.append({"action": "dial", "number": num, "name": nm, "timestamp": time.time()})

                # Direct notify phone if IP is known
                paired_dev = pairing_mgr.data.get("paired_device") or {}
                phone_ip = paired_dev.get("last_ip")
                if phone_ip:
                    def _notify_phone(ip, payload):
                        try:
                            import urllib.request
                            req = urllib.request.Request(f"http://{ip}:53319/dial", data=payload, headers={"Content-Type": "application/json"})
                            urllib.request.urlopen(req, timeout=2)
                        except Exception:
                            pass
                    threading.Thread(target=_notify_phone, args=(phone_ip, json.dumps({"number": num}).encode()), daemon=True).start()

                # Launch Call HUD if not already open
                subprocess.Popen(["python3", "/usr/share/nebula-dialer/nebula-call-hud.py", json.dumps(call_info)])

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/call/incoming":
            try:
                data = json.loads(body.decode())
                num = data.get("number", "Unknown")
                nm = data.get("name", num)
                call_file = "/run/nebula-active-call.json"
                call_info = {"active": True, "state": "incoming", "number": num, "name": nm, "start_time": time.time()}
                with open(call_file, "w") as f:
                    json.dump(call_info, f)

                # Launch Call HUD for incoming call
                subprocess.Popen(["python3", "/usr/share/nebula-dialer/nebula-call-hud.py", json.dumps(call_info)])

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/call/accept":
            try:
                call_file = "/run/nebula-active-call.json"
                if os.path.exists(call_file):
                    try:
                        with open(call_file) as f:
                            c = json.load(f)
                        c["state"] = "connected"
                        with open(call_file, "w") as f:
                            json.dump(c, f)
                    except Exception:
                        pass

                with phone_events_lock:
                    phone_events.append({"action": "accept", "timestamp": time.time()})

                paired_dev = pairing_mgr.data.get("paired_device") or {}
                phone_ip = paired_dev.get("last_ip")
                if phone_ip:
                    def _notify_accept(ip):
                        try:
                            import urllib.request
                            req = urllib.request.Request(f"http://{ip}:53319/accept", data=b"{}", headers={"Content-Type": "application/json"})
                            urllib.request.urlopen(req, timeout=2)
                        except Exception:
                            pass
                    threading.Thread(target=_notify_accept, args=(phone_ip,), daemon=True).start()

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/call/hangup":
            try:
                call_file = "/run/nebula-active-call.json"
                if os.path.exists(call_file):
                    os.remove(call_file)

                with phone_events_lock:
                    phone_events.append({"action": "hangup", "timestamp": time.time()})

                paired_dev = pairing_mgr.data.get("paired_device") or {}
                phone_ip = paired_dev.get("last_ip")
                if phone_ip:
                    def _notify_hangup(ip):
                        try:
                            import urllib.request
                            req = urllib.request.Request(f"http://{ip}:53319/hangup", data=b"{}", headers={"Content-Type": "application/json"})
                            urllib.request.urlopen(req, timeout=2)
                        except Exception:
                            pass
                    threading.Thread(target=_notify_hangup, args=(phone_ip,), daemon=True).start()

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))


        elif path == "/api/notify":
            try:
                data = json.loads(body.decode()) if body else {}
                paired = pairing_mgr.data.get("paired_device")
                if paired is None:
                    self.send_error(403, "No paired device")
                    return
                app_name = data.get("app", "Phone")
                title = data.get("title", "")
                text = data.get("text", "")
                notif_args = ["notify-send", "-a", app_name, "-t", "8000", "-i", "phone-symbolic"]
                if title:
                    notif_args.append(title)
                if text:
                    notif_args.append(text)
                subprocess.Popen(notif_args)
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/ping":
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"pong": True}).encode())

        elif path == "/api/mirror/start":
            try:
                data = json.loads(body.decode()) if body else {}
                dev_name = data.get("device_name", "Android Phone")
                with mirror_lock:
                    mirror_active = True
                # Launch Desktop Screen Mirroring Viewer window
                try:
                    subprocess.Popen(["python3", "/usr/share/mynebula-screen-mirror/screen-mirror.py", dev_name])
                except Exception as e:
                    print(f"[Companion] Failed to launch screen mirror viewer: {e}")

                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error(400, str(e))

        elif path == "/api/mirror/frame":
            # Raw JPEG bytes in body
            if body:
                with mirror_condition:
                    latest_mirror_frame = body
                    mirror_condition.notify_all()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())

        elif path == "/api/mirror/stop":
            with mirror_condition:
                mirror_active = False
                latest_mirror_frame = None
                mirror_condition.notify_all()
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())

        else:
            self.send_error(404, "Not Found")

def main():
    server = HTTPServer(("0.0.0.0", PORT), CompanionHandler)
    print(f"Nebula Companion daemon running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
