# unseen-dBug // Network Recon & Telemetry Core (v5.1)

> *"Every system has a blind spot. I'm just looking where no one else does."*

Plataforma minimalista de monitoramento de rede local, telemetria de acessos em tempo real e inteligência OSINT desenvolvida em Python puro por **unseen-dBug**.

### Principais Funcionalidades
* **Controle de Acesso por Host (Zero-Login Admin):** O console administrativo completo é liberado automaticamente apenas para o computador anfitrião (`localhost` / Host IP), enquanto visitantes externos visualizam exclusivamente uma interface pública isolada.
* **Telemetria Ao Vivo (`access_logs.json`):** Captura automática de endereço IP, modelo/marca do dispositivo, navegador, endereço MAC e geolocalização (Cidade, Estado, País e Provedor) com atualização em tempo real sem recarregar a página.
* **Rastreador OSINT Integrado:** Consulta instantânea de domínios e IPs públicos (resolução DNS, ASN, operadora e coordenadas geográficas).
* **Auditoria de Rede Local (LAN):** Varredura ativa de sub-rede via threads e scanner de portas TCP expostas.
* **Monitor de Conexões Ativas:** Listagem em tempo real das conexões externas estabelecidas pelo sistema operacional.

### Como Executar
1. Certifique-se de ter o **Python 3** instalado.
2. Baixe o arquivo `radar.py` e execute no terminal:
   ```bash
   python radar.py
   ```
3. O painel administrativo será aberto automaticamente no navegador padrão (`http://127.0.0.1:9090`).

---
*Projeto desenvolvido para fins educacionais, diagnóstico de infraestrutura e auditoria em redes próprias.*
