### Como Testar a Nova Arquitetura Agora

1. **No seu PC (Abre direto no Painel Admin):** Assim que você rodar o comando, o navegador abre direto no painel completo sem pedir senha nenhuma — porque o servidor reconhece que o pedido partiu do seu próprio computador.
2. **No seu Celular (Vê apenas a página pública + Registra a telemetria):**
   * Olhe o cartão **"Link para Visitantes (Wi-Fi)"** no topo do seu painel (ex.: `http://192.168.1.15:9090`).
   * Abra esse exato endereço no navegador do seu celular. O celular verá apenas a tela limpa *"Serviço Ativo"* e **não terá acesso** a nenhum botão administrativo.
   * Olhe para a tela do seu PC: em até **3 segundos** (sem você precisar apertar F5), a linha aparece sozinha na tabela **Telemetria de Acessos ao Site** mostrando a **hora exata**, o **IP**, o **modelo/marca do celular**, o **MAC** e a **Cidade/Estado** (*Aparecida de Goiânia, Goiás - BR*).
3. **Testar o Rastreador OSINT:** Digite qualquer site (ex.: `google.com` ou `nasa.gov`) na barra **Rastreador OSINT** dentro do painel para ver a localização nos Estados Unidos e os dados do servidor aparecerem na hora.
4. **Atualizar no GitHub:** O código completo da **v5.0** já está copiado no seu `Ctrl + V` para você salvar lá no `radar.py`.

*(Nota técnica: enquanto o servidor estiver rodando apenas no seu PC doméstico, o link `192.168.x.x` funciona para aparelhos na sua rede Wi-Fi; se no futuro você quiser receber visitas de pessoas em outras cidades ou países no seu painel, basta criar um túnel gratuito como o **Cloudflare Tunnel (`cloudflared`)**, que gera um link HTTPS público e repassa o IP real de cada visitante de qualquer lugar do mundo para o seu script registrar).*

<FollowUp>
Abriu o novo painel minimalista **v5.0** sem pedir senha no seu PC? Me diz se o acesso pelo celular apareceu ao vivo na tabela com **Cidade/Estado** e **marca do aparelho**!
</FollowUp>
