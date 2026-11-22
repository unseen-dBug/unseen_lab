import socket
import subprocess
import platform
import re
import os
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORTAS_ALVO = {
    21: "FTP", 22: "SSH", 23: "Telnet", 53: "DNS",
    80: "HTTP (Painel Web)", 135: "RPC (Windows)", 139: "NetBIOS",
    443: "HTTPS", 445: "SMB (Arquivos PC)", 554: "RTSP (Camera)",
    3000: "LG WebOS TV", 3389: "RDP (Acesso Remoto)",
    5555: "ADB (Android/TV Box)", 8001: "Samsung Smart TV",
    8008: "Chromecast / Android TV", 8080: "HTTP-Alt",
    62078: "Apple iPhone/iPad"
}

FABRICANTES = {
    "28:6C:07": "Xiaomi", "64:CC:2E": "Xiaomi", "F8:A4:5F": "Xiaomi", "50:EC:50": "Xiaomi",
    "BC:30:7E": "Samsung", "D0:22:BE": "Samsung", "A8:7C:01": "Samsung", "8C:71:F8": "Samsung", "5C:49:7D": "Samsung",
    "3C:22:FB": "Apple", "F0:18:98": "Apple", "AC:BC:32": "Apple", "DC:2B:2A": "Apple", "A4:83:E7": "Apple",
    "40:78:6A": "Motorola", "E4:90:7E": "Motorola", "9C:D9:17": "Motorola", "CC:C3:EA": "Motorola",
    "00:1E:75": "LG Electronics", "64:99:5D": "LG Electronics", "AC:0D:1B": "LG Electronics",
    "F4:F5:D8": "Google/Chromecast", "54:60:09": "Google/Nest",
    "50:C7:BF": "TP-Link", "C0:25:E9": "TP-Link", "E8:48:B8": "TP-Link", "98:DA:C4": "TP-Link",
    "00:1E:42": "Intelbras", "38:6B:1C": "Intelbras", "78:98:E8": "D-Link",
    "00:E0:FC": "Huawei", "48:46:FB": "Huawei", "70:8C:B6": "Huawei",
    "54:22:F8": "ZTE", "74:A7:8E": "ZTE", "D4:37:D7": "Fiberhome", "4C:1B:86": "Nokia",
    "24:0A:C4": "Espressif (ESP32)", "30:AE:A4": "Espressif (ESP32)", "A4:CF:12": "Espressif (ESP32)",
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "D8:3A:DD": "Raspberry Pi",
    "00:50:56": "VMware", "08:00:27": "VirtualBox"
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

def ping_ip(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout = ["-w", "300"] if platform.system().lower() == "windows" else ["-W", "1"]
    subprocess.run(["ping", param, "1", *timeout, ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def varredura_ativa(ip_local):
    if ip_local == "127.0.0.1":
        return
    base = ".".join(ip_local.split(".")[:3])
    ips = [f"{base}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=60) as executor:
        executor.map(ping_ip, ips)

def porta_aberta(ip, porta):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.15)
    aberta = (sock.connect_ex((ip, porta)) == 0)
    sock.close()
    return aberta

def identificar_fabricante(mac):
    mac_norm = mac.replace("-", ":").upper()
    prefixo = mac_norm[:8]
    if prefixo in FABRICANTES:
        return FABRICANTES[prefixo], False
    if mac_norm[1:2] in ["2", "6", "A", "E"]:
        return "MAC Privado (Celular Moderno)", True
    return "Desconhecido", False

def obter_hostname(ip):
    try:
        nome, _, _ = socket.gethostbyaddr(ip)
        return nome.split(".").pop(0)
    except Exception:
        return "-"

def classificar_dispositivo(ip, host, fab, mac_privado):
    h = host.lower()
    f = fab.lower()

    if ip.endswith(".1"):
        return "ROTEADOR / GATEWAY"

    if any(k in h for k in ["tv", "bravia", "tizen", "webos", "roku", "fire", "chromecast", "miband", "stick"]):
        return "SMART TV / STREAMING"
    if any(k in h for k in ["iphone", "ipad", "galaxy", "redmi", "poco", "xiaomi", "moto", "android", "pixel"]):
        return "CELULAR / SMARTPHONE"
    if any(k in h for k in ["desktop", "laptop", "notebook", "pc", "win-", "macbook"]):
        return "COMPUTADOR / PC"
    if any(k in h for k in ["ps4", "ps5", "xbox", "nintendo"]):
        return "VIDEOGAME"

    if porta_aberta(ip, 8008) or porta_aberta(ip, 8001) or porta_aberta(ip, 3000):
        return "SMART TV / CAST"
    if porta_aberta(ip, 62078):
        return "CELULAR (iPhone)"
    if porta_aberta(ip, 445) or porta_aberta(ip, 135) or porta_aberta(ip, 3389):
        return "PC WINDOWS"
    if porta_aberta(ip, 554):
        return "CAMERA IP / DVR"
    if porta_aberta(ip, 5555):
        return "ANDROID / TV BOX"

    if "espressif" in f:
        return "ESP32 / IoT"
    if mac_privado or any(k in f for k in ["xiaomi", "motorola", "apple", "samsung"]):
        return "CELULAR (Provavel)"
    if any(k in f for k in ["huawei", "zte", "fiberhome", "tp-link", "intelbras", "d-link"]):
        return "REPETIDOR / ONU"

    return "DISPOSITIVO REDE"

def escanear_portas(ip):
    abertas = []
    for porta, nome in PORTAS_ALVO.items():
        if porta_aberta(ip, porta):
            abertas.append(f"Porta {porta} ({nome})")
    return abertas

def listar_dispositivos(ip_local):
    dispositivos = []
    base = ".".join(ip_local.split(".")[:3]) + "."
    try:
        saida = subprocess.check_output("arp -a", shell=True).decode(errors="ignore")
        padrao = re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida)
        for ip, mac in padrao:
            if ip.startswith(base) and not ip.endswith(".255") and not ip.endswith(".0"):
                mac_fmt = mac.replace("-", ":").upper()
                fab, mac_privado = identificar_fabricante(mac_fmt)
                host = obter_hostname(ip)
                tipo = classificar_dispositivo(ip, host, fab, mac_privado)
                dispositivos.append((ip, mac_fmt, host, fab, tipo))
    except Exception:
        pass
    return dispositivos

class RadarHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        ip_local = obter_ip_local()
        mensagem_scan = ""

        if "shutdown" in params:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<body style='background:#090c10;color:#ff5555;font-family:monospace;padding:30px;'><h1>[//] RADAR DESLIGADO.</h1><p>Pode fechar esta aba.</p></body>")
            threading.Timer(0.5, lambda: os._exit(0)).start()
            return

        if "sweep" in params:
            varredura_ativa(ip_local)
            mensagem_scan = "<div class='alert'>[+] Varredura ativa concluida e dispositivos classificados!</div>"

        if "scan" in params:
            alvo = params.get("scan", [""]).pop(0)
            portas = escanear_portas(alvo)
            lista_p = ", ".join(portas) if portas else "Nenhuma porta comum aberta (Firewall ativo)"
            mensagem_scan = f"<div class='alert'>[+] Scan de Portas em <b>{alvo}</b>: {lista_p}</div>"

        dispositivos = listar_dispositivos(ip_local)
        linhas = "".join(
            f"""<tr>
                <td><b>{ip}</b></td>
                <td>{host}</td>
                <td>{mac}</td>
                <td>{fab}</td>
                <td><span class='tag'>{tipo}</span></td>
                <td><a class='btn-sm' href='/?scan={ip}'>SCAN PORTAS</a></td>
            </tr>"""
            for ip, mac, host, fab, tipo in dispositivos
        ) or "<tr><td colspan='6'>Clique em 'VARREDURA ATIVA' acima para mapear e identificar os aparelhos.</td></tr>"

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>// unseen-dBug :: RADAR v3.0</title>
<style>
  body {{ background:#090c10; color:#00ff9c; font-family:monospace; padding:30px; }}
  h1 {{ border-bottom:1px solid #00ff9c44; padding-bottom:10px; letter-spacing:2px; }}
  .box {{ background:#0d1117; border:1px solid #00ff9c33; padding:20px; margin-top:20px; border-radius:6px; }}
  .alert {{ background:#00ff9c18; border:1px solid #00ff9c; padding:12px; margin-top:15px; border-radius:4px; color:#fff; }}
  table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
  th, td {{ text-align:left; padding:10px; border-bottom:1px solid #1f2937; }}
  th {{ color:#58a6ff; }}
  .tag {{ background:#00ff9c22; color:#00ff9c; padding:4px 8px; border-radius:4px; font-size:12px; font-weight:bold; }}
  .btn {{ background:#00ff9c; color:#090c10; padding:10px 18px; text-decoration:none; font-weight:bold; border-radius:4px; display:inline-block; }}
  .btn-sm {{ background:#1f2937; color:#58a6ff; padding:5px 10px; text-decoration:none; border:1px solid #58a6ff55; border-radius:4px; font-size:12px; }}
  .btn-sm:hover {{ background:#58a6ff; color:#090c10; }}
  .btn-red {{ background:#ff555522; color:#ff5555; padding:10px 18px; text-decoration:none; border:1px solid #ff5555; font-weight:bold; border-radius:4px; float:right; }}
  .btn-red:hover {{ background:#ff5555; color:#fff; }}
</style>
</head>
<body>
  <h1>// unseen-dBug :: SMART RECON v3.0 <a class="btn-red" href="/?shutdown=1">X DESLIGAR RADAR</a></h1>
  <div class="box">
    <p><strong>HOST IP:</strong> {ip_local} &nbsp;|&nbsp; <strong>OS:</strong> {platform.system()} &nbsp;|&nbsp; <strong>DISPOSITIVOS:</strong> {len(dispositivos)}</p>
    <a class="btn" href="/?sweep=1">VARREDURA ATIVA (IDENTIFICAR TODOS)</a>
    &nbsp;
    <a class="btn-sm" href="/">ATUALIZAR LISTA</a>
    {mensagem_scan}
  </div>
  <div class="box">
    <h3>MAPA INTELIGENTE DE DISPOSITIVOS</h3>
    <table>
      <tr><th>ENDERECO IP</th><th>HOSTNAME</th><th>ENDERECO MAC</th><th>FABRICANTE / MAC</th><th>TIPO IDENTIFICADO</th><th>ACAO</th></tr>
      {linhas}
    </table>
  </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 9090), RadarHandler)
