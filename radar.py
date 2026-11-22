import os
import re
import json
import socket
import platform
import threading
import subprocess
import webbrowser
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORTA_SERVIDOR = 9090
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_LOGS = os.path.join(BASE_DIR, "access_logs.json")
CACHE_GEO = {}
GEO_GATEWAY_CACHE = None

PORTAS_ALVO = {
    21: "FTP", 22: "SSH", 53: "DNS", 80: "HTTP",
    135: "RPC", 443: "HTTPS", 445: "SMB", 554: "RTSP",
    3000: "WebOS TV", 3389: "RDP", 8001: "Samsung TV",
    8008: "Chromecast", 8080: "HTTP-Alt", 62078: "iOS Sync"
}

FABRICANTES = {
    "28:6C:07": "Xiaomi", "64:CC:2E": "Xiaomi", "F8:A4:5F": "Xiaomi", "50:EC:50": "Xiaomi",
    "BC:30:7E": "Samsung", "D0:22:BE": "Samsung", "A8:7C:01": "Samsung", "8C:71:F8": "Samsung",
    "3C:22:FB": "Apple", "F0:18:98": "Apple", "AC:BC:32": "Apple", "DC:2B:2A": "Apple",
    "40:78:6A": "Motorola", "E4:90:7E": "Motorola", "9C:D9:17": "Motorola",
    "00:1E:75": "LG", "64:99:5D": "LG", "F4:F5:D8": "Google",
    "50:C7:BF": "TP-Link", "C0:25:E9": "TP-Link", "00:1E:42": "Intelbras",
    "00:E0:FC": "Huawei", "54:22:F8": "ZTE", "D4:37:D7": "Fiberhome",
    "24:0A:C4": "Espressif (ESP32)", "30:AE:A4": "Espressif (ESP32)"
}

def obter_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip, _ = s.getsockname()
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def consultar_geo_api(ip=""):
    try:
        alvo = f"/{ip}" if ip else ""
        url = f"http://ip-api.com{alvo}?fields=status,query,country,countryCode,regionName,city,isp,as,lat,lon"
        req = urllib.request.urlopen(url, timeout=1.5)
        dados = json.loads(req.read().decode("utf-8"))
        if dados.get("status") == "success":
            return dados
    except Exception:
        pass
    return None

def obter_localizacao_completa(ip):
    global GEO_GATEWAY_CACHE
    eh_local = ip.startswith(("127.", "192.168.", "10.")) or bool(re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", ip))

    if eh_local:
        if not GEO_GATEWAY_CACHE:
            GEO_GATEWAY_CACHE = consultar_geo_api("")
        if GEO_GATEWAY_CACHE:
            cidade = GEO_GATEWAY_CACHE.get("city", "Local")
            estado = GEO_GATEWAY_CACHE.get("regionName", "")
            pais = GEO_GATEWAY_CACHE.get("countryCode", "BR")
            return f"Wi-Fi Local ({cidade}, {estado} - {pais})"
        return "Rede Local (Wi-Fi / LAN)"

    if ip in CACHE_GEO:
        return CACHE_GEO[ip]

    dados = consultar_geo_api(ip)
    if dados:
        loc = f"{dados.get('city')}, {dados.get('regionName')} - {dados.get('country')} ({dados.get('isp')})"
        CACHE_GEO[ip] = loc
        return loc

    return "Origem Externa"

def carregar_logs():
    if os.path.exists(ARQUIVO_LOGS):
        try:
            with open(ARQUIVO_LOGS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_log(registro):
    logs = carregar_logs()
    logs.insert(0, registro)
    logs = logs[:300]
    try:
        with open(ARQUIVO_LOGS, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def analisar_user_agent(ua):
    if not ua:
        return "Dispositivo Desconhecido", "Cliente HTTP"

    dispositivo = "Computador Desktop"
    if "iPhone" in ua:
        dispositivo = "Apple iPhone"
    elif "iPad" in ua:
        dispositivo = "Apple iPad"
    elif "Samsung" in ua or "SM-" in ua:
        match = re.search(r"(SM-[A-Z0-9]+)", ua)
        modelo = f" ({match.group(1)})" if match else ""
        dispositivo = f"Samsung Galaxy{modelo}"
    elif any(k in ua for k in ["Redmi", "POCO", "Mi ", "Xiaomi"]):
        dispositivo = "Xiaomi / Redmi"
    elif "Moto" in ua or "Motorola" in ua:
        dispositivo = "Motorola"
    elif "Android" in ua:
        dispositivo = "Smartphone Android"
    elif "Windows" in ua:
        dispositivo = "PC Windows"
    elif "Macintosh" in ua or "Mac OS" in ua:
        dispositivo = "Apple Mac"
    elif "Linux" in ua:
        dispositivo = "Sistema Linux"

    navegador = "Navegador"
    if "Edg/" in ua:
        navegador = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        navegador = "Opera"
    elif "Chrome/" in ua and "Safari/" in ua:
        navegador = "Chrome"
    elif "Firefox/" in ua:
        navegador = "Firefox"
    elif "Safari/" in ua and "Chrome/" not in ua:
        navegador = "Safari"

    return dispositivo, navegador

def obter_mac_por_ip(ip_alvo):
    try:
        saida = subprocess.check_output("arp -a", shell=True).decode(errors="ignore")
        for ip, mac in re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida):
            if ip == ip_alvo:
                return mac.replace("-", ":").upper()
    except Exception:
        pass
    return "Externo / Oculto"

def ping_ip(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout = ["-w", "200"] if platform.system().lower() == "windows" else ["-W", "1"]
    subprocess.run(["ping", param, "1", *timeout, ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def varredura_ativa(ip_local):
    if ip_local == "127.0.0.1":
        return
    base = ".".join(ip_local.split(".")[:3])
    ips = [f"{base}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=80) as executor:
        executor.map(ping_ip, ips)

def porta_aberta(ip, porta):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.15)
    aberta = (sock.connect_ex((ip, porta)) == 0)
    sock.close()
    return aberta

def identificar_fabricante(mac):
    prefixo = mac[:8]
    if prefixo in FABRICANTES:
        return FABRICANTES[prefixo]
    if len(mac) > 1 and mac in ["2", "6", "A", "E"]:
        return "MAC Privado (Celular)"
    return "Genérico"

def listar_dispositivos(ip_local):
    dispositivos = []
    base = ".".join(ip_local.split(".")[:3]) + "."
    try:
        saida = subprocess.check_output("arp -a", shell=True).decode(errors="ignore")
        for ip, mac in re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida):
            if ip.startswith(base) and not ip.endswith((".255", ".0")):
                mac_fmt = mac.replace("-", ":").upper()
                fab = identificar_fabricante(mac_fmt)
                funcao = "Gateway / Roteador" if ip.endswith(".1") else "Host LAN"
                dispositivos.append({"ip": ip, "mac": mac_fmt, "fab": fab, "funcao": funcao})
    except Exception:
        pass
    return dispositivos

def obter_conexoes_externas():
    conexoes = []
    try:
        saida = subprocess.check_output("netstat -ano -p TCP", shell=True).decode(errors="ignore")
        for linha in saida.splitlines():
            partes = linha.split()
            if len(partes) >= 5 and partes == "ESTABLISHED":
                remoto_addr = partes
                pid = partes
                if not remoto_addr.startswith(("127.", "192.168.", "10.", "[::1]")):
                    conexoes.append({"remoto": remoto_addr, "pid": pid})
    except Exception:
        pass
    return conexoes[:15]

def investigar_alvo_osint(alvo):
    alvo = alvo.strip().replace("https://", "").replace("http://", "").split("/")
    try:
        ip_resolvido = socket.gethostbyname(alvo)
    except Exception:
        return {"erro": f"Não foi possível resolver: {alvo}"}

    dados = consultar_geo_api(ip_resolvido)
    if not dados:
        return {"erro": f"Sem dados públicos para {ip_resolvido}"}

    return {
        "alvo": alvo,
        "ip": ip_resolvido,
        "local": f"{dados.get('city')}, {dados.get('regionName')} - {dados.get('country')} ({dados.get('countryCode')})",
        "isp": dados.get("isp"),
        "asn": dados.get("as"),
        "coords": f"{dados.get('lat')}, {dados.get('lon')}"
    }

CSS_BASE = """
<style>
  :root {
    --bg: #09090b; --surface: #111114; --surface-2: #18181c;
    --border: #27272a; --text: #f4f4f5; --muted: #a1a1aa;
    --accent: #3b82f6; --success: #10b981; --danger: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }
  .container { max-width: 1180px; margin: 0 auto; padding: 28px 24px; }
  header {
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 28px;
  }
  .brand { font-size: 16px; font-weight: 600; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px; }
  .dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success); }
  .nav-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .grid-stats .card { margin-bottom: 0; }
  .card-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
  .card-value { font-size: 20px; font-weight: 600; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; }
  .section-title { font-size: 15px; font-weight: 600; }
  .sub-text { font-size: 12px; color: var(--muted); }

