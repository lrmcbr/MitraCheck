import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BINARIO_WINGET = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\speedtest.exe")


def localizar_binario(caminho: str | None) -> str:
    if caminho:
        if os.path.isfile(caminho):
            return caminho
        raise FileNotFoundError(f"binario nao encontrado: {caminho}")
    achado = shutil.which("speedtest")
    if achado:
        return achado
    if os.path.isfile(BINARIO_WINGET):
        return BINARIO_WINGET
    raise FileNotFoundError(
        "speedtest.exe nao encontrado; instale com: winget install Ookla.Speedtest.CLI"
    )


def testar(binario: str) -> tuple[float, float, int | None, str]:
    comando = [binario, "--accept-license", "--accept-gdpr", "--format=json"]
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, None, None, "ERRO: speedtest excedeu 180s"

    saida = resultado.stdout.strip()
    if not saida:
        return None, None, None, f"ERRO: sem saida do speedtest ({resultado.stderr.strip()[:80]})"

    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        return None, None, None, f"ERRO: saida invalida ({saida[:80]})"

    if dados.get("type") == "error" or "error" in dados:
        mensagem = dados.get("errorMessage") or dados.get("error")
        return None, None, None, f"ERRO: {mensagem}"

    down = float(dados["download"]["bandwidth"]) * 8 / 1_000_000
    up = float(dados["upload"]["bandwidth"]) * 8 / 1_000_000
    ping_ms = round(float(dados["ping"]["latency"]), 1)

    servidor = dados.get("server", {})
    nome = servidor.get("name", "?")
    local = servidor.get("location", "?")
    info = f"servidor: {nome} ({local})"

    return down, up, ping_ms, info


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste de velocidade periodico via Ookla Speedtest CLI")
    parser.add_argument("--intervalo", type=int, default=1800, help="segundos entre testes (padrao: 1800 = 30 minutos)")
    parser.add_argument("--saida", default="log_velocidade.csv", help="arquivo CSV de saida")
    parser.add_argument("--binario", default=None, help="caminho do speedtest.exe (padrao: procura no PATH/winget)")
    parser.add_argument("--uma-vez", action="store_true", help="roda um teste e sai")
    args = parser.parse_args()

    if "--intervalo" not in sys.argv:
        try:
            cfg = json.loads(
                (Path(__file__).parent / "config_testador.json").read_text(encoding="utf-8")
            )
            args.intervalo = max(60, int(cfg.get("intervalo_min", 30)) * 60)
        except Exception:
            pass

    binario = localizar_binario(args.binario)

    novo = not os.path.exists(args.saida)
    arquivo = open(args.saida, "a", newline="", encoding="utf-8-sig")
    escritor = csv.writer(arquivo, delimiter=";")
    if novo:
        escritor.writerow(["data_hora", "download_mbps", "upload_mbps", "ping_ms", "observacao"])

    try:
        while True:
            down, up, ms, info = testar(binario)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            falhou = down is None or up is None or ms is None
            observacao = info if not falhou else ""
            alertas = []
            if falhou and info.startswith("ERRO"):
                alertas.append(info[5:].strip())
                observacao = ""

            marcador = "[ALERTA] " if alertas else ""
            detalhe = " | " + "; ".join(alertas) if alertas else ""
            print(
                f"{marcador}{agora} "
                f"down={f'{down:.1f} Mbps' if down is not None else '?'} "
                f"up={f'{up:.1f} Mbps' if up is not None else '?'} "
                f"ping={f'{ms:.0f}' if ms is not None else 'sem resp'}ms{detalhe}"
            )

            escritor.writerow([
                agora,
                "" if down is None else f"{down:.2f}",
                "" if up is None else f"{up:.2f}",
                "" if ms is None else ms,
                observacao,
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
