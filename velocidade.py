import argparse
import csv
import os
import time
from datetime import datetime

import requests

from monitor import pingar_internet


DOWNLOAD_URL = "https://speed.cloudflare.com/__down"
UPLOAD_URL = "https://speed.cloudflare.com/__up"


def medir_download(sessao: requests.Session, mb: int) -> float:
    inicio = time.perf_counter()
    recebidos = 0
    with sessao.get(
        DOWNLOAD_URL,
        params={"bytes": mb * 1_000_000, "cachebust": time.time_ns()},
        stream=True,
        timeout=(5, 30),
    ) as resposta:
        resposta.raise_for_status()
        for pedaco in resposta.iter_content(chunk_size=65536):
            recebidos += len(pedaco)
    duracao = time.perf_counter() - inicio
    if duracao <= 0 or recebidos == 0:
        raise RuntimeError("download nao retornou dados")
    return recebidos * 8 / duracao / 1_000_000


def medir_upload(sessao: requests.Session, mb: int) -> float:
    dados = os.urandom(mb * 1_000_000)
    inicio = time.perf_counter()
    resposta = sessao.post(UPLOAD_URL, data=dados, timeout=(5, 60))
    resposta.raise_for_status()
    duracao = time.perf_counter() - inicio
    if duracao <= 0:
        raise RuntimeError("upload falhou")
    return len(dados) * 8 / duracao / 1_000_000


def testar(mb_download: int, mb_upload: int) -> tuple[float, float, int | None, str]:
    obs = ""
    down = up = None
    ms = pingar_internet()
    try:
        with requests.Session() as sessao:
            sessao.headers["Cache-Control"] = "no-cache"
            down = medir_download(sessao, mb_download)
            up = medir_upload(sessao, mb_upload)
    except Exception as erro:
        obs = f"ERRO: {erro}"
    return down, up, ms, obs


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste de velocidade periodico")
    parser.add_argument("--intervalo", type=int, default=30, help="segundos entre testes (padrao: 30)")
    parser.add_argument("--saida", default="log_velocidade.csv", help="arquivo CSV de saida")
    parser.add_argument("--tamanho-download", type=int, default=25, help="MB baixados por teste")
    parser.add_argument("--tamanho-upload", type=int, default=5, help="MB enviados por teste")
    parser.add_argument("--uma-vez", action="store_true", help="roda um teste e sai")
    args = parser.parse_args()

    novo = not os.path.exists(args.saida)
    arquivo = open(args.saida, "a", newline="", encoding="utf-8-sig")
    escritor = csv.writer(arquivo, delimiter=";")
    if novo:
        escritor.writerow(["data_hora", "download_mbps", "upload_mbps", "ping_ms", "observacao"])

    try:
        while True:
            down, up, ms, obs = testar(args.tamanho_download, args.tamanho_upload)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            alertas = []
            if down is None:
                alertas.append("download falhou")
            if up is None:
                alertas.append("upload falhou")
            if ms is None:
                alertas.append("internet sem resposta")
            if obs:
                alertas.append(obs)

            marcador = "[ALERTA] " if alertas else ""
            detalhe = " | " + "; ".join(alertas) if alertas else ""
            print(
                f"{marcador}{agora} "
                f"down={f'{down:.1f} Mbps' if down is not None else '?'} "
                f"up={f'{up:.1f} Mbps' if up is not None else '?'} "
                f"ping={ms if ms is not None else 'sem resp'}ms{detalhe}"
            )

            escritor.writerow([
                agora,
                "" if down is None else f"{down:.2f}",
                "" if up is None else f"{up:.2f}",
                "" if ms is None else ms,
                "; ".join(alertas),
            ])
            arquivo.flush()

            if args.uma_vez:
                break
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("Teste interrompido pelo usuario.")
    finally:
        arquivo.close()


if __name__ == "__main__":
    main()
