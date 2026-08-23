import argparse
import json
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASTA = Path(__file__).parent

SCRIPTS = {
    "monitor": ["monitor.py"],
    "velocidade": ["velocidade.py"],
}

processos: dict[str, subprocess.Popen | None] = {nome: None for nome in SCRIPTS}
registros: dict[str, object] = {}


def esta_rodando(nome: str) -> bool:
    proc = processos.get(nome)
    return proc is not None and proc.poll() is None


def estados() -> dict:
    return {nome: esta_rodando(nome) for nome in SCRIPTS}


def iniciar(nome: str) -> str | None:
    if nome not in SCRIPTS:
        return "script desconhecido"
    if esta_rodando(nome):
        return None
    registro = open(PASTA / f"{nome}.saida.log", "ab")
    proc = subprocess.Popen(
        [sys.executable, "-u", *SCRIPTS[nome]],
        cwd=PASTA,
        stdout=registro,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    processos[nome] = proc
    registros[nome] = registro
    return None


def parar(nome: str) -> str | None:
    if nome not in SCRIPTS:
        return "script desconhecido"
    proc = processos.get(nome)
    if proc is None or proc.poll() is not None:
        return None
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    processo = registros.pop(nome, None)
    if processo is not None:
        processo.close()
    processos[nome] = None
    return None


class Manipulador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PASTA), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/status":
            self._json(estados())
            return
        super().do_GET()

    def do_POST(self):
        partes = self.path.strip("/").split("/")
        if len(partes) == 3 and partes[0] == "api" and partes[1] in ("iniciar", "parar"):
            nome = partes[2]
            erro = iniciar(nome) if partes[1] == "iniciar" else parar(nome)
            resposta = dict(estados())
            if erro:
                resposta["erro"] = erro
                self._json(resposta, 400)
            else:
                self._json(resposta)
            return
        self._json({"erro": "rota invalida"}, 404)

    def log_message(self, formato, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor do painel com controle dos scripts")
    parser.add_argument("--porta", type=int, default=8000, help="porta HTTP (padrao: 8000)")
    args = parser.parse_args()

    servidor = ThreadingHTTPServer(("0.0.0.0", args.porta), Manipulador)
    print(f"Painel em http://localhost:{args.porta}/grafico.html")
    print(f"Controles: /api/iniciar/<monitor|velocidade> , /api/parar/<...> , /api/status")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
