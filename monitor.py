import argparse
import csv
import os
import re
import subprocess
import time
from datetime import datetime

from roteador import Roteador, carregar_credenciais


def pingar_internet() -> int | None:
    try:
        resultado = subprocess.run(
            ["ping", "-n", "1", "-w", "2000", "8.8.8.8"],
            capture_output=True,
            text=True,
        )
        m = re.search(r"tempo[=<](\d+)ms", resultado.stdout)
        if m:
            return int(m.group(1))
        return None
    except Exception:
        return None


def coletar(roteador: Roteador, usuario: str, senha: str):
    rx = tx = ""
    ppp = ""
    obs = ""
    fibra = None
    try:
        try:
            fibra = roteador.status_fibra()
        except Exception:
            fibra = None
        if fibra is None or fibra["rx_dbm"] is None or fibra["ppp"] is None:
            roteador.entrar(usuario, senha)
            fibra = roteador.status_fibra()
        if fibra["rx_dbm"] is not None:
            rx = f"{fibra['rx_dbm']:.2f}"
            tx = f"{fibra['tx_dbm']:.2f}"
        else:
            obs = "Rx/Tx nao encontrados na pagina"
        ppp = fibra["ppp"] or "?"
    except Exception as erro:
        obs = f"ERRO: {erro}"
    ms = pingar_internet()
    return rx, tx, ppp, ms, obs


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de sinal da fibra")
    parser.add_argument("--intervalo", type=int, default=30, help="segundos entre medicoes")
    parser.add_argument("--saida", default="log_fibra.csv")
    parser.add_argument("--uma-vez", action="store_true", help="coleta uma medida e sai")
    args = parser.parse_args()

    usuario, senha = carregar_credenciais()
    roteador = Roteador()
    try:
        roteador.entrar(usuario, senha)
    except Exception as erro:
        print(f"Login inicial falhou ({erro}); tentando novamente a cada ciclo.")

    novo = not os.path.exists(args.saida)
    arquivo = open(args.saida, "a", newline="", encoding="utf-8-sig")
    escritor = csv.writer(arquivo, delimiter=";")
    if novo:
        escritor.writerow(["data_hora", "rx_dbm", "tx_dbm", "ppp", "ping_ms", "observacao"])

    try:
        while True:
            rx, tx, ppp, ms, obs = coletar(roteador, usuario, senha)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            alertas = []
            if rx:
                valor_rx = float(rx)
                if valor_rx <= -28:
                    alertas.append("Rx CRITICO (sinal muito fraco, <= -28 dBm)")
                elif valor_rx > -25:
                    pass
                else:
                    alertas.append("Rx em ATENCAO (sinal fraco; ideal e melhor que -25 dBm)")
            if ppp not in ("Conectado", ""):
                alertas.append(f"PPP {ppp}")
            if ms is None:
                alertas.append("internet sem resposta")
            if obs:
                alertas.append(obs)

            marcador = "[ALERTA] " if alertas else ""
            detalhe = " | " + "; ".join(alertas) if alertas else ""
            print(
                f"{marcador}{agora} Rx={rx or '?'} dBm Tx={tx or '?'} dBm "
                f"PPP={ppp or '?'} ping={ms if ms is not None else 'sem resp'}ms{detalhe}"
            )

            escritor.writerow([agora, rx, tx, ppp, "" if ms is None else ms, "; ".join(alertas)])
            arquivo.flush()

            if args.uma_vez:
                break
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("Monitor interrompido pelo usuario.")
    finally:
        arquivo.close()


if __name__ == "__main__":
    main()
