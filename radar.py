import socket
import subprocess
import platform
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

def obter_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def escanear_dispositivos():
    dispositivos = []
    comando = "arp -a"
    try:
        saida = subprocess.check_output(comando, shell=True).decode(errors="ignore")
        padrao = re.findall(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})", saida)
        for ip, mac in padrao:
            if not ip.endswith(".255") and not ip.startswith("224."):
                dispositivos.append((ip, mac.upper()))
    except Exception:
        pass
    return dispositivos

class RadarHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        ip_local = obter_ip_local()
        dispositivos = escanear_dispositivos()
        linhas = "".join(
            f"<tr><td>{ip}</td><td>{mac}</td><td><span class='tag'>ONLINE</span></td></tr>"
            for ip, mac in dispositivos
        ) or "<tr><td colspan='3'>Nenhum dispositivo mapeado no cache ARP ainda.</td></tr>"

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>// unseen-dBug :: RADAR</title>
<style>
  body {{ background:#090c10; color:#00ff9c; font-family:monospace; padding:30px; }}
  h1 {{ border-bottom:1px solid #00ff9c44; padding-bottom:10px; letter-spacing:2px; }}
  .box {{ background:#0d1117; border:1px solid #00ff9c33; padding:20px; margin-top:20px; border-radius:6px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
  th, td {{ text-align:left; padding:10px; border-bottom:1px solid #1f2937; }}
  th {{ color:#58a6ff; }}
  .tag {{ background:#00ff9c22; color:#00ff9c; padding:3px 8px; border-radius:4px; font-size:12px; }}
</style>
</head>
<body>
  <h1>// unseen-dBug :: LOCAL NETWORK RADAR</h1>
  <div class="box">
    <p><strong>HOST IP:</strong> {ip_local} &nbsp;|&nbsp; <strong>OS:</strong> {platform.system()} &nbsp;|&nbsp; <strong>STATUS:</strong> MONITORING</p>
  </div>
  <div class="box">
    <h3>DISPOSITIVOS DETECTADOS NA REDE ({len(dispositivos)})</h3>
    <table>
      <tr><th>ENDEREÇO IP</th><th>ENDEREÇO MAC</th><th>ESTADO</th></tr>
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
    print("[//] unseen-dBug Radar iniciado em: http://127.0.0.1:8080")
    HTTPServer(("127.0.0.1", 8080), RadarHandler).serve_forever()
