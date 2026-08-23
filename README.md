# Monitor da Fibra

Vigilância contínua do sinal óptico (GPON) e da velocidade real da conexão, com painel web local.

Compatível com **Windows**, **Linux** e **macOS**.

## Requisitos

- Python **3.10 ou superior**
- Pacote Python: `requests` (`pip install requests`)
- [Speedtest CLI oficial da Ookla](https://www.speedtest.net/pt-BR/apps/cli)

## Instalação do Speedtest CLI

| Sistema | Como instalar |
|---|---|
| Windows | `winget install Ookla.Speedtest.CLI` |
| macOS | baixe em speedtest.net/pt-BR/apps/cli (`arm64` para Apple Silicon) ou `brew install --cask speedtest` |
| Linux | repositório oficial da Ookla: `curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh \| sudo bash` e depois `sudo apt install speedtest` (ou `.rpm`) |

O script encontra o binário automaticamente pelo PATH; use `--binario` para indicar outro caminho.

## Como usar

```bash
pip install requests
python servidor.py
```

Abra `http://localhost:8000/index.html`:

1. Em **Administração**, informe o IP do modem, usuário e senha.
2. Em **Gráficos**, use os botões Monitor/Velocidade para ligar os coletores.

Credenciais são guardadas de forma protegida: DPAPI (Windows), Keychain (macOS) ou
secret-tool/gnome-keyring (Linux). Sem cofre disponível no Linux, cai para texto claro
com aviso — restrinja então as permissões do arquivo.

## Componentes

| Arquivo | Papel |
|---|---|
| `monitor.py` | coleta Rx/Tx/PPP do modem + ping 8.8.8.8 a cada 30 s |
| `velocidade.py` | roda o Ookla Speedtest no intervalo configurado |
| `servidor.py` | painel web + APIs + controle dos coletores |
| `roteador.py` | raspagem da página interna do modem GPON |
| `segredos.py` | armazenamento protegido de credenciais por SO |
| `grafico.html` | gráficos em tempo real com filtro de período |
| `admin.html` | configurações, exclusão/exportação de dados |
| `index.html` | documentação visual do sistema |

## Dados medidos

- **Rx (dBm)**: potência óptica recebida. Ideal > −25; −25 a −28 atenção; ≤ −28 crítico.
- **Tx (dBm)**: potência transmitida pela ONU (típico +1 a +5).
- **PPP**: estado da sessão PPPoE.
- **Ping**: latência até 8.8.8.8.
- **Download/Upload**: capacidade medida contra servidor Ookla local.

## Privacidade

Tudo roda na sua rede local. Os resultados dos testes são enviados à base pública
da Ookla (condição de uso do serviço deles); nada mais sai da sua máquina.
