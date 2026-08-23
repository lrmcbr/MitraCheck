import argparse
import os
import re
import socket
import subprocess
import sys

from roteador import Roteador, avaliar_sinal_rx, carregar_credenciais


def obter_ip_local() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def obter_ip_roteador() -> str | None:
    if sys.platform == "win32":
        resultado = subprocess.run(
            ["route", "print", "-4", "0.0.0.0"],
            capture_output=True,
            text=True,
        )
        for linha in resultado.stdout.splitlines():
            partes = linha.split()
            if len(partes) >= 5 and partes[0] == "0.0.0.0" and partes[1] == "0.0.0.0":
                gateway = partes[2]
                if gateway != "On-link":
                    return gateway
        return None
    if sys.platform == "darwin":
        resultado = subprocess.run(
            ["route", "-n", "get", "default"], capture_output=True, text=True
        )
        m = re.search(r"gateway:\s+(\d+\.\d+\.\d+\.\d+)", resultado.stdout)
        return m.group(1) if m else None
    resultado = subprocess.run(
        ["ip", "route", "show", "default"], capture_output=True, text=True
    )
    m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", resultado.stdout)
    return m.group(1) if m else None


def diagnostico_local() -> None:
    print("=== Diagnostico Local ===")
    print(f"IP local:     {obter_ip_local()}")
    print(f"IP roteador:  {obter_ip_roteador() or 'nao encontrado'}")


def diagnostico_roteador(base) -> None:
    usuario, senha = carregar_credenciais()
    r = Roteador(base)
    r.entrar(usuario, senha)

    disp = r.dispositivo()
    print("=== Roteador ===")
    print(f"Fabricante: {disp['fabricante']}")
    print(f"Modelo:     {disp['modelo']}")
    print(f"Firmware:   {disp['firmware']}")
    print(f"Serial:     {disp['serial']}")

    fibra = r.status_fibra()
    print("=== Fibra Optica (GPON) ===")
    if fibra["rx_dbm"] is not None:
        print(f"Potencia Rx: {fibra['rx_dbm']} dBm -> {avaliar_sinal_rx(fibra['rx_dbm'])}")
    else:
        print("Potencia Rx: nao encontrada")
    if fibra["tx_dbm"] is not None:
        print(f"Potencia Tx: {fibra['tx_dbm']} dBm")
    print(f"Sessao PPP:  {fibra['ppp']}")

    logs = r.logs()
    print("=== Logs do Sistema ===")
    print(f"Paginas de log: {logs['paginas']}")
    for entrada in logs["entradas"]:
        print(entrada)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostico da rede")
    parser.add_argument(
        "--base",
        default="http://192.168.15.1",
        help="URL base do roteador (padrao: http://192.168.15.1)",
    )
    args = parser.parse_args()

    diagnostico_local()
    print()
    try:
        diagnostico_roteador(args.base)
    except Exception as erro:
        print(f"Erro ao acessar o roteador: {erro}")


if __name__ == "__main__":
    main()
