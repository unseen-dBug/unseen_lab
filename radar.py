

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

PORTA = 9090
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_LOGS = os.path.join(BASE_DIR, "access_logs.json")
CACHE_GEO = {}
GEO_GATEWAY = None

PORTAS_ALVO = {
    21: "FTP", 22: "SSH", 53: "DNS", 80: "HTTP",
    135: "RPC", 443: "HTTPS", 445: "SMB", 554: "RTSP",
    3000: "WebOS TV", 3389: "RDP", 8001: "Samsung TV",
    8008: "Chromecast", 8080: "HTTP-Alt", 62078: "iOS"
}

FABRICANTES = {
    "28:6C:07": "Xiaomi", "64:CC:2E": "Xiaomi", "F8:A4:5F": "Xiaomi",
    "BC:30:7E": "Samsung", "D0:22:BE": "Samsung", "A8:7C:01": "Samsung",
    "3C:22:FB": "Apple", "F0:18:98": "Apple", "AC:BC:32": "Apple",
    "40:78:6A": "Motorola", "E4:90:7E": "Motorola",
    "00:1E:75": "LG", "F4:F5:D8": "Google",
    "50:C7:BF": "TP-Link", "00:1E:42": "Intelbras",
    "00:E0:FC": "Huawei", "54:22:F8": "ZTE", "D4:37:D7": "Fiberhome",
    "24:0A:C4": "ESP32"
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


def consultar_geo(ip=""):
    try:
        url = f"http://ip-api.com{ip}?fields=status,query,country,countryCode,regionName,city,isp,as,lat,lon"
        dados = json.loads(urllib.request.urlopen(url, timeout=1.5).read().decode("utf-8"))
        if dados.get("status") == "success":
            return dados
    except Exception:
        pass
    return None


def obter_localizacao(ip):
    global GEO_GATEWAY
    if ip.startswith(("127.", "192.168.", "10.")) or re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", ip):
        if not GEO_GATEWAY:
            GEO_GATEWAY = consultar_geo("")
        if GEO_GATEWAY:
            return f"Wi-Fi Local ({GEO_GATEWAY.get('city')}, {GEO_GATEWAY.get('regionName')} - {GEO_GATEWAY.get('countryCode')})"
        return "Rede Local (Wi-Fi / LAN)"
    if ip in CACHE_GEO:
        return CACHE_GEO[ip]
    dados = consultar_geo(ip)
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


def salvar_log(reg):
    logs = carregar_logs()
    logs.insert(0, reg)
    try:
        with open(ARQUIVO_LOGS, "w", encoding="utf-8") as f:
            json.dump(logs[:300], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def analisar_ua(ua):
    disp = "Desktop"
    if "iPhone" in ua:
        disp = "Apple iPhone"
    elif "iPad" in ua:
        disp = "Apple iPad"
    elif "Samsung" in ua or "SM-" in ua:
        m = re.search(r"(SM-[A-Z0-9]+)", ua)
        disp = f"Samsung Galaxy ({m.group(1)})" if m else "Samsung Galaxy"
    elif any(k in ua for k in ["Redmi", "POCO", "Mi ", "Xiaomi"]):
        disp = "Xiaomi / Redmi"
    elif "Moto" in ua or "Motorola" in ua:
        disp = "Motorola"
    elif "Android" in ua:
        disp = "Smartphone Android"
    elif "Windows" in ua:
        disp = "PC Windows"
    elif "Mac OS" in ua:
        disp = "Apple Mac"
    elif "Linux" in ua:
        disp = "Linux"

    nav = "Navegador"
    if "Edg/" in ua:
        nav = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        nav = "Opera"
    elif "Chrome/" in ua:
        nav = "Chrome"
    elif "Firefox/" in ua:
        nav = "Firefox"
    elif "Safari/" in ua:
        nav = "Safari"
    return disp, nav


def obter_mac(ip_alvo):
    try:
        saida = subprocess.check_output("arp -a", shell=True).decode(errors="ignore")
        for ip, mac in re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida):
            if ip == ip_alvo:
                return mac.replace("-", ":").upper()
    except Exception:
        pass
    return "Externo / Oculto"


def ping_ip(ip):
    p = "-n" if platform.system().lower() == "windows" else "-c"
    w = ["-w", "200"] if platform.system().lower() == "windows" else ["-W", "1"]
    subprocess.run(["ping", p, "1", *w, ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def varredura_ativa(ip_local):
    if ip_local == "127.0.0.1":
        return
    base = ".".join(ip_local.split(".")[:3])
    with ThreadPoolExecutor(max_workers=80) as ex:
        ex.map(ping_ip, [f"{base}.{i}" for i in range(1, 255)])


def porta_aberta(ip, porta):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.15)
    ok = (s.connect_ex((ip, porta)) == 0)
    s.close()
    return ok


def listar_dispositivos(ip_local):
    res = []
    base = ".".join(ip_local.split(".")[:3]) + "."
    try:
        saida = subprocess.check_output("arp -a", shell=True).decode(errors="ignore")
        for ip, mac in re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida):
            if ip.startswith(base) and not ip.endswith((".255", ".0")):
                m = mac.replace("-", ":").upper()
                fab = FABRICANTES.get(m[:8], "MAC Privado (Celular)" if len(m) > 1 and m in "26AE" else "Genérico")
                res.append({"ip": ip, "mac": m, "fab": fab, "funcao": "Gateway" if ip.endswith(".1") else "Host LAN"})
    except Exception:
        pass
    return res


def obter_conexoes():
    conns = []
    try:
        saida = subprocess.check_output("netstat -ano -p TCP", shell=True).decode(errors="ignore")
        for linha in saida.splitlines():
            p = linha.split()
            if len(p) >= 5 and p == "ESTABLISHED" and not p.startswith(("127.", "192.168.", "10.", "[::1]")):
                conns.append({"remoto": p, "pid": p})
    except Exception:
        pass
    return conns[:15]


def investigar_osint(alvo):
    alvo = alvo.strip().replace("https://", "").replace("http://", "").split("/")
    try:
        ip = socket.gethostbyname(alvo)
    except Exception:
        return {"erro": f"Não foi possível resolver: {alvo}"}
    d = consultar_geo(ip)
    if not d:
        return {"erro": f"Sem dados públicos para {ip}"}
    return {
        "alvo": alvo,
        "ip": ip,
        "local": f"{d.get('city')}, {d.get('regionName')} - {d.get('country')} ({d.get('countryCode')})",
        "isp": d.get("isp"),
        "asn": d.get("as"),
        "coords": f"{d.get('lat')}, {d.get('lon')}"
    }


CSS = """<style>
:root{--bg:#09090b;--surf:#111114;--surf2:#18181c;--bdr:#27272a;--txt:#f4f4f5;--mut:#a1a1aa;--acc:#3b82f6;--ok:#10b981;--err:#ef4444}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px}
header{display:flex;justify-content:space-between;align-items:center;padding-bottom:20px;border-bottom:1px solid var(--bdr);margin-bottom:28px}
.brand{font-size:16px;font-weight:600;display:flex;align-items:center;gap:10px}
.dot{width:8px;height:8px;background:var(--ok);border-radius:50%;box-shadow:0 0 8px var(--ok)}
.nav{display:flex;gap:10px;flex-wrap:wrap}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:28px}
.card{background:var(--surf);border:1px solid var(--bdr);border-radius:10px;padding:20px;margin-bottom:24px}
.stats .card{margin-bottom:0}
.lbl{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.val{font-size:20px;font-weight:600;font-family:monospace}
.sh{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px;flex-wrap:wrap}
.st{font-size:15px;font-weight:600}
.sub{font-size:12px;color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--mut);font-weight:500;padding:10px 14px;border-bottom:1px solid var(--bdr);font-size:11px;text-transform:uppercase}
td{padding:13px 14px;border-bottom:1px solid var(--bdr)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surf2)}
.mono{font-family:monospace;font-size:12px}
.bdg{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:500;background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.25)}
.bdg-g{background:rgba(16,185,129,.12);color:#34d399;border:1px solid rgba(16,185,129,.25)}
.bdg-n{background:#27272a;color:var(--mut);border:1px solid #3f3f46}
.btn{display:inline-flex;align-items:center;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:500;text-decoration:none;cursor:pointer;border:1px solid transparent}
.btn-p{background:var(--txt);color:var(--bg)}
.btn-o{background:transparent;color:var(--txt);border-color:var(--bdr)}
.btn-o:hover{background:var(--surf2)}
.btn-d{background:rgba(239,68,68,.1);color:#f87171;border-color:rgba(239,68,68,.25)}
.sbar{display:flex;gap:10px;margin-bottom:16px}
.sbar input{flex:1;padding:9px 14px;background:var(--bg);border:1px solid var(--bdr);border-radius:6px;color:var(--txt);font-size:13px;outline:none}
.banner{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.25);color:#34d399;padding:12px 16px;border-radius:8px;font-size:13px;margin-bottom:20px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media(max-width:860px){.g2{grid-template-columns:1fr}}
</style>"""


class CoreHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def ip_cliente(self):
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",").strip()

        ip, _ = self.client_address
        return ip

    def is_admin(self):
        return self.ip_cliente() in ("127.0.0.1", "::1", obter_ip_local())

    def registrar(self, ip):
        disp, nav = analisar_ua(self.headers.get("User-Agent", ""))
        salvar_log({
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ip": ip,
            "dispositivo": disp,
            "navegador": nav,
            "mac": obter_mac(ip),
            "local": obter_localizacao(ip)
        })

    def send_html(self, html, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        ip = self.ip_cliente()
        admin = self.is_admin()

        if parsed.path == "/favicon.ico":
            return self.send_html("", 204)

        if parsed.path == "/api/logs":
            if not admin:
                return self.send_html("Negado", 403)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"logs": carregar_logs()}, ensure_ascii=False).encode("utf-8"))
            return

        if parsed.path == "/export" and admin:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=unseen_logs.json")
            self.end_headers()
            self.wfile.write(json.dumps(carregar_logs(), ensure_ascii=False, indent=2).encode("utf-8"))
            return

        if not admin:
            if parsed.path == "/":
                threading.Thread(target=self.registrar, args=(ip,), daemon=True).start()
                return self.send_html(self.page_publica())
            return self.send_html(self.page_publica(), 403)

        if parsed.path == "/preview":
            threading.Thread(target=self.registrar, args=(ip,), daemon=True).start()
            return self.send_html(self.page_publica(True))

        if "shutdown" in params:
            self.send_html(f"<!DOCTYPE html><html><head>{CSS}</head><body><div class='wrap'><div class='card'><h3>Servidor encerrado.</h3></div></div></body></html>")
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return

        if "clear_logs" in params:
            with open(ARQUIVO_LOGS, "w", encoding="utf-8") as f:
                json.dump([], f)
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        ip_local = obter_ip_local()
        alerta = ""
        osint = None

        if "sweep" in params:
            varredura_ativa(ip_local)
            alerta = "Varredura ativa concluída na rede local."

        if "scan" in params:
            alvo = params["scan"].pop(0)
            ab = [f"{p} ({n})" for p, n in PORTAS_ALVO.items() if porta_aberta(alvo, p)]
            alerta = f"Portas em <strong>{alvo}</strong>: {', '.join(ab) if ab else 'Nenhuma porta aberta'}"

        if "osint" in params and params["osint"]:
            osint = investigar_osint(params["osint"].pop(0))

        self.send_html(self.page_admin(ip_local, alerta, osint))

    def page_publica(self, preview=False):
        av = "<div class='banner'>Modo Pré-visualização (Visão do Visitante). <a href='/' style='color:#fff;margin-left:10px'>Voltar ao Admin</a></div>" if preview else ""
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>unseen-dBug</title>
  {CSS}
</head>
<body>
  <div class="wrap">
    <header>
      <div class="brand"><span class="dot"></span> unseen-dBug</div>
      <span class="bdg bdg-n">ONLINE</span>
    </header>
    {av}
    <div class="card" style="max-width:540px;margin:70px auto;text-align:center;padding:48px 24px">
      <p class="lbl">Infrastructure Node</p>
      <h1 style="font-size:22px;margin-bottom:10px">Serviço Ativo</h1>
      <p class="sub">Nó operacional. Conexões de entrada registradas para telemetria e segurança.</p>
    </div>
  </div>
</body>
</html>"""

    def page_admin(self, ip_local, alerta, osint):
        logs = carregar_logs()
        devs = listar_dispositivos(ip_local)
        conns = obter_conexoes()
        bn = f"<div class='banner'>{alerta}</div>" if alerta else ""

        osint_box = ""
        if osint:
            if "erro" in osint:
                osint_box = f"<p style='color:#f87171;font-size:13px'>{osint['erro']}</p>"
            else:
                osint_box = f"""<div style='background:var(--bg);border:1px solid var(--bdr);border-radius:8px;padding:14px;font-size:13px'>
                  <div><strong>Alvo:</strong> <span class='mono'>{osint['alvo']}</span> &rarr; <span class='mono'>{osint['ip']}</span></div>
                  <div style='margin-top:4px'><strong>Local:</strong> {osint['local']}</div>
                  <div style='margin-top:4px'><strong>Provedor:</strong> {osint['isp']} ({osint['asn']})</div>
                  <div style='margin-top:4px'><strong>Coordenadas:</strong> <span class='mono'>{osint['coords']}</span></div>
                </div>"""

        r_logs = "".join(
            f"<tr><td class='mono' style='color:var(--mut)'>{l['data_hora']}</td><td class='mono'><strong>{l['ip']}</strong></td><td>{l['dispositivo']} <span class='bdg bdg-n'>{l['navegador']}</span></td><td class='mono'>{l['mac']}</td><td><span class='bdg bdg-g'>{l['local']}</span></td></tr>"
            for l in logs
        ) or f"<tr><td colspan='5' style='color:var(--mut);text-align:center'>Aguardando visitas... Abra http://{ip_local}:{PORTA} no celular para testar.</td></tr>"

        r_devs = "".join(
            f"<tr><td class='mono'><strong>{d['ip']}</strong></td><td class='mono'>{d['mac']}</td><td>{d['fab']}</td><td><span class='bdg'>{d['funcao']}</span></td><td style='text-align:right'><a href='/?scan={d['ip']}' class='btn btn-o' style='padding:4px 10px;font-size:11px'>Auditar Portas</a></td></tr>"
            for d in devs
        ) or "<tr><td colspan='5' style='color:var(--mut);text-align:center'>Clique em 'Executar Varredura Ativa'.</td></tr>"

        r_conns = "".join(
            f"<tr><td class='mono'>{c['remoto']}</td><td class='mono' style='color:var(--mut)'>PID {c['pid']}</td><td><span class='bdg'>ATIVA</span></td></tr>"
            for c in conns
        ) or "<tr><td colspan='3' style='color:var(--mut);text-align:center'>Nenhuma conexão externa ativa.</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>unseen-dBug // Command Center</title>
  {CSS}
</head>
<body>
  <div class="wrap">
    <header>
      <div class="brand"><span class="dot"></span> unseen-dBug <span class="bdg">HOST ADMIN</span></div>
      <div class="nav">
        <a href="/preview" class="btn btn-o">Visão do Visitante</a>
        <a href="/export" class="btn btn-o">Exportar Logs</a>
        <a href="/?shutdown=1" class="btn btn-d">Desligar Servidor</a>
      </div>
    </header>
    {bn}
    <div class="stats">
      <div class="card"><div class="lbl">Link Visitantes (Wi-Fi)</div><div class="val" style="font-size:16px">http://{ip_local}:{PORTA}</div></div>
      <div class="card"><div class="lbl">Acessos Capturados</div><div class="val" id="st-logs">{len(logs)}</div></div>
      <div class="card"><div class="lbl">Aparelhos na Rede</div><div class="val">{len(devs)}</div></div>
      <div class="card"><div class="lbl">Conexões Externas PC</div><div class="val">{len(conns)}</div></div>
    </div>
    <div class="card">
      <div class="sh">
        <div><div class="st">Telemetria de Acessos ao Site (Ao Vivo)</div><div class="sub">Atualiza sozinho a cada 3s. Visível apenas neste PC.</div></div>
        <a href="/?clear_logs=1" class="btn btn-o">Limpar Histórico</a>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr><th>Data / Hora</th><th>Endereço IP</th><th>Dispositivo / Marca</th><th>MAC</th><th>Cidade / Estado / País</th></tr></thead>
          <tbody id="tb-logs">{r_logs}</tbody>
        </table>
      </div>
    </div>
    <div class="g2">
      <div class="card">
        <div class="sh"><div><div class="st">Rastreador OSINT (IP / Domínio)</div><div class="sub">Localização e provedor de qualquer IP ou site.</div></div></div>
        <form class="sbar" method="GET" action="/">
          <input type="text" name="osint" placeholder="Ex: 8.8.8.8 ou github.com" required>
          <button type="submit" class="btn btn-p">Rastrear</button>
        </form>
        {osint_box}
      </div>
      <div class="card">
        <div class="sh"><div><div class="st">Conexões Externas do PC</div><div class="sub">Servidores conectados ao Windows agora.</div></div><a href="/" class="btn btn-o">Atualizar</a></div>
        <div style="max-height:190px;overflow-y:auto">
          <table>
            <thead><tr><th>IP / Porta Remota</th><th>Processo</th><th>Estado</th></tr></thead>
            <tbody>{r_conns}</tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="sh"><div><div class="st">Dispositivos na Rede Wi-Fi (LAN)</div><div class="sub">Mapeamento local e auditoria de portas.</div></div><a href="/?sweep=1" class="btn btn-p">Executar Varredura Ativa</a></div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr><th>IP</th><th>MAC</th><th>Fabricante</th><th>Função</th><th style="text-align:right">Auditoria</th></tr></thead>
          <tbody>{r_devs}</tbody>
        </table>

            </table>
      </div>
    </div>
  </div>
  <script>
    setInterval(async () => {{
      try {{
        const r = await fetch('/api/logs');
        if (!r.ok) return;
        const d = await r.json();
        document.getElementById('st-logs').innerText = d.logs.length;
        if (d.logs.length) {{
          document.getElementById('tb-logs').innerHTML = d.logs.map(l => `<tr><td class="mono" style="color:var(--mut)">${{l.data_hora}}</td><td class="mono"><strong>${{l.ip}}</strong></td><td>${{l.dispositivo}} <span class="bdg bdg-n">${{l.navegador}}</span></td><td class="mono">${{l.mac}}</td><td><span class="bdg bdg-g">${{l.local}}</span></td></tr>`).join('');
        }}
      }} catch (e) {{}}
    }}, 3000);
  </script>
</body>
</html>"""


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORTA), CoreHandler)
    threading.Timer(0.4, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}/")).start()
    srv.serve_forever()
