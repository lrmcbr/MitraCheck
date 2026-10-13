# Diretrizes do MitraCheck Vivo

Guia para o opencode trabalhar neste repositório. Leia antes de alterar qualquer código.

## O que é o projeto

Ferramenta de diagnóstico de rede (foco em GPON/Vivo Fibra): vigia o sinal óptico
(Rx/Tx/PPP), o ping e a velocidade real da conexão, com painel web local.
Alvo: **Windows**, **Linux** e **macOS**. Veja `README.md` e `info.md`.

## Arquitetura

| Arquivo | Papel |
|---|---|
| `servidor.py` | Painel web (`http.server`) + APIs `/api/*` + controle dos coletores |
| `monitor.py` | Coleta Rx/Tx/PPP do modem + ping, grava `log_fibra.csv` |
| `velocidade.py` | Roda o Ookla Speedtest, grava `log_velocidade.csv` |
| `roteador.py` | Raspagem da página interna do modem (login + regex) |
| `segredos.py` | Armazenamento protegido de credenciais por SO |
| `main.py` | Diagnóstico por linha de comando |
| `grafico.html`, `admin.html`, `index.html` | Frontend (Chart.js vendorado em `chart.umd.js`) |

Os coletores rodam como processos separados, controlados pelo `servidor.py` via
`.pid` (ver `SCRIPTS` e `EXPORTACOES` em `servidor.py:38`).

## Convenções de código

- **Idioma**: nomes de funções, variáveis, colunas e mensagens em **pt-BR**;
  sem acentos em identificadores/strings de console (ex.: `observacao`, `saida`).
- **Python 3.10+**. Use type hints no estilo do projeto: `str | None`, `int | None`,
  `tuple[float, float, int | None, str]`.
- Apenas **biblioteca padrão** nos `.py` (apesar do `requests` citado no README, o
  código usa `urllib`). Não introduza dependências novas sem confirmar.
- **Não adicione comentários** no código, exceto quando explicitamente pedido.
- Mantenha o estilo das funções existentes: retornos por tupla/dict, poucas
  abstrações, nomes curtos e descritivos.
- Frontend: HTML + JS puro, sem build. Não reescreva `chart.umd.js` (vendor).

## Dados e formatos

- CSVs usam delimitador `;` e codificação `utf-8-sig`, com cabeçalho.
- `log_fibra.csv`: `data_hora;rx_dbm;tx_dbm;ppp;ping_ms;observacao`
- `log_velocidade.csv`: `data_hora;download_mbps;upload_mbps;ping_ms;observacao`
- Faixas de Rx (ver `avaliar_sinal_rx` em `roteador.py:49`): ideal > −25 dBm;
  atenção −25 a −28 dBm; crítico ≤ −28 dBm.

## Segurança e dados sensíveis

- Credenciais **nunca** em texto claro: sempre via `segredos.proteger()` /
  `segredos.desproteger()`.
- **Nunca** faça commit de `config_testador.json`, `config.txt`, `cookies.txt`,
  `problema.txt`, `*.pid`, `*.saida.log`, `*.bak`, `log_*.csv`. Já estão no
  `.gitignore` — mantenha.
- Não registre senhas em logs, prints ou mensagens de erro.

## Comandos

```bash
pip install requests          # dependência declarada no README
python servidor.py            # inicia o painel (http://localhost:8000)
python monitor.py --uma-vez    # uma coleta de sinal
python velocidade.py --uma-vez # um teste de velocidade
python main.py                 # diagnóstico por CLI
```

## Verificação antes de finalizar

- Não há suíte de testes automatizados. Valide alterações assim:
  - `python -m py_compile *.py` para checagem de sintaxe.
  - Quando possível, exercite a função alterada com `--uma-vez` ou um pequeno
    trecho, já que o acesso real ao modem depende da rede local.
- Não deixe processos (`monitor.py`/`velocidade.py`) rodando após testes.

## Git

- Só faça commit quando explicitamente solicitado.
- Preserve o estilo de mensagens existente no repositório.
