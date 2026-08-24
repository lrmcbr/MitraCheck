import ctypes
import json
import os
import segredos
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from roteador import (
    LOGIN_PADRAO,
    DADOS_PADRAO,
    PADRAO_RX_PADRAO,
    PADRAO_TX_PADRAO,
    PADRAO_PPP_PADRAO,
)
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASTA = Path(__file__).parent
CONFIG_PATH = PASTA / "config_testador.json"

CONFIG_PADRAO = {
    "ip_modem": "192.168.15.1",
    "usuario": "",
    "senha": "",
    "intervalo_min": 30,
    "porta": 8000,
    "login_path": LOGIN_PADRAO,
    "dados_path": DADOS_PADRAO,
    "padrao_rx": PADRAO_RX_PADRAO,
    "padrao_tx": PADRAO_TX_PADRAO,
    "padrao_ppp": PADRAO_PPP_PADRAO,
    "velocidade_contratada": 0,
}

SCRIPTS = {
    "monitor": ["monitor.py"],
    "velocidade": ["velocidade.py"],
}

EXPORTACOES = {
    "fibra": "log_fibra.csv",
    "velocidade": "log_velocidade.csv",
}

processos = {}
registros = {}
pids_adotados = {}
estado_servidor = {"porta": 8000, "servidor": None}


def processo_vivo(pid):
    if os.name == "nt":
        h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def matar_pid(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def pid_de_orfao(nome):
    caminho = PASTA / f"{nome}.pid"
    try:
        pid = int(caminho.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    return pid if processo_vivo(pid) else None


def limpar_pidfile(nome):
    try:
        (PASTA / f"{nome}.pid").unlink()
    except FileNotFoundError:
        pass


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    for campo in ("login_path", "dados_path", "padrao_rx", "padrao_tx", "padrao_ppp"):
        if not str(cfg.get(campo) or "").strip():
            cfg[campo] = CONFIG_PADRAO[campo]
    cfg["porta"] = int(cfg["porta"])
    cfg["intervalo_min"] = int(cfg["intervalo_min"])
    try:
        cfg["velocidade_contratada"] = float(cfg["velocidade_contratada"])
    except (TypeError, ValueError):
        cfg["velocidade_contratada"] = 0
    return cfg


def salvar_config(cfg):
    dados = {
        k: cfg[k]
        for k in (
            "ip_modem", "usuario", "senha", "intervalo_min", "porta",
            "login_path", "dados_path", "padrao_rx", "padrao_tx", "padrao_ppp",
            "velocidade_contratada",
        )
    }
    CONFIG_PATH.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def esta_rodando(nome):
    proc = processos.get(nome)
    if proc is not None and proc.poll() is None:
        return True
    pid = pid_de_orfao(nome)
    if pid is not None:
        pids_adotados[nome] = pid
        return True
    pids_adotados.pop(nome, None)
    return False


def estados():
    return {nome: esta_rodando(nome) for nome in SCRIPTS}


def argumentos_extra(nome):
    if nome == "velocidade":
        return ["--intervalo", str(carregar_config()["intervalo_min"] * 60)]
    return []


def iniciar(nome):
    if nome not in SCRIPTS:
        return "script desconhecido"
    if esta_rodando(nome):
        return None
    registro = open(PASTA / f"{nome}.saida.log", "ab")
    opcoes = {}
    if os.name == "nt":
        opcoes["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [sys.executable, "-u", *SCRIPTS[nome], *argumentos_extra(nome)],
        cwd=PASTA,
        stdout=registro,
        stderr=subprocess.STDOUT,
        **opcoes,
    )
    processos[nome] = proc
    registros[nome] = registro
    return None


def parar(nome):
    if nome not in SCRIPTS:
        return "script desconhecido"
    proc = processos.get(nome)
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    registro = registros.pop(nome, None)
    if registro is not None:
        registro.close()
    processos[nome] = None
    pid = pids_adotados.pop(nome, None) or pid_de_orfao(nome)
    if pid is not None:
        matar_pid(pid)
    limpar_pidfile(nome)
    return None


def escrever_credenciais(usuario, senha):
    cfg = carregar_config()
    cfg["usuario"] = usuario
    cfg["senha"] = segredos.proteger(senha)
    salvar_config(cfg)


def apagar_dados(limite=None):
    apagados = {}
    for chave, nome_arquivo in EXPORTACOES.items():
        caminho = PASTA / nome_arquivo
        if not caminho.exists():
            continue
        backup = caminho.with_suffix(".bak")
        backup.write_bytes(caminho.read_bytes())
        linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
        cabecalho = linhas[0]
        corpo = [l for l in linhas[1:] if l.strip()]
        if limite:
            corpo = [l for l in corpo if l.split(";")[0].strip() >= limite]
        caminho.write_text("\r\n".join([cabecalho] + corpo) + "\r\n", encoding="utf-8-sig")
        apagados[chave] = len(corpo)
    return apagados


def configuracao_publica():
    cfg = carregar_config()
    return {
        "ip_modem": cfg["ip_modem"],
        "usuario": cfg["usuario"],
        "intervalo_min": cfg["intervalo_min"],
        "porta": cfg["porta"],
        "senha_definida": bool(cfg["senha"]),
        "login_path": cfg["login_path"],
        "dados_path": cfg["dados_path"],
        "padrao_rx": cfg["padrao_rx"],
        "padrao_tx": cfg["padrao_tx"],
        "padrao_ppp": cfg["padrao_ppp"],
        "velocidade_contratada": cfg["velocidade_contratada"],
    }


def diagnostico_modem():
    import re
    from roteador import (
        Roteador,
        LOGIN_PADRAO, DADOS_PADRAO,
        PADRAO_RX_PADRAO, PADRAO_TX_PADRAO, PADRAO_PPP_PADRAO,
    )

    cfg = carregar_config()
    if not cfg.get("senha"):
        return {"erro": "credenciais nao definidas"}
    r = Roteador()
    try:
        r.entrar(cfg.get("usuario", ""), segredos.desproteger(cfg.get("senha", "")))
    except Exception as erro:
        return {"erro": f"login falhou: {erro}"}
    try:
        pagina = r._buscar_pagina(r.dados_caminho)
    except Exception as erro:
        return {"erro": f"falha ao abrir {r.dados_caminho}: {erro}"}

    achados = {}
    for nome, padrao_salvo, padrao_padrao in (
        ("rx", cfg.get("padrao_rx"), PADRAO_RX_PADRAO),
        ("tx", cfg.get("padrao_tx"), PADRAO_TX_PADRAO),
        ("ppp", cfg.get("padrao_ppp"), PADRAO_PPP_PADRAO),
    ):
        try:
            expressao = padrao_salvo or padrao_padrao
            if not expressao:
                continue
            m = re.search(expressao, pagina)
            if m:
                grupo = next((g for g in m.groups() if g is not None), m.group(0))
                achados[nome] = str(grupo)[:40]
        except re.error:
            achados[nome] = "REGEX INVALIDA"

    caminho = PASTA / "diagnostico_modem.html"
    caminho.write_text(pagina, encoding="utf-8")
    return {
        "ok": True,
        "bytes": len(pagina.encode("utf-8")),
        "arquivo": caminho.name,
        "achados": achados,
    }


class Manipulador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PASTA), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo_json(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        if tamanho == 0:
            return {}
        try:
            return json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):
        if self.path == "/api/status":
            resposta = estados()
            resposta["porta"] = estado_servidor["porta"]
            self._json(resposta)
            return
        if self.path == "/api/config":
            self._json(configuracao_publica())
            return
        partes = self.path.strip("/").split("/")
        if len(partes) == 3 and partes[0] == "api" and partes[1] == "exportar":
            qual = partes[2]
            if qual not in EXPORTACOES:
                self._json({"erro": "exportacao desconhecida"}, 404)
                return
            caminho = PASTA / EXPORTACOES[qual]
            if not caminho.exists():
                self._json({"erro": "arquivo inexistente"}, 404)
                return
            dados = caminho.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition", f'attachment; filename="{caminho.name}"'
            )
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(dados)))
            super().end_headers()
            self.wfile.write(dados)
            return
        super().do_GET()

    def do_POST(self):
        partes = self.path.strip("/").split("/")
        if len(partes) == 3 and partes[0] == "api" and partes[1] in ("iniciar", "parar"):
            nome = partes[2]
            erro = iniciar(nome) if partes[1] == "iniciar" else parar(nome)
            resposta = estados()
            if erro:
                resposta["erro"] = erro
                self._json(resposta, 400)
            else:
                self._json(resposta)
            return
        if self.path == "/api/config":
            return self._configurar()
        if self.path == "/api/dados/apagar":
            return self._apagar_dados()
        if self.path == "/api/diagnostico":
            self._json(diagnostico_modem())
            return
        if self.path == "/api/porta":
            return self._mudar_porta()
        self._json({"erro": "rota invalida"}, 404)

    def _configurar(self):
        dados = self._corpo_json()
        if dados is None:
            self._json({"erro": "json invalido"}, 400)
            return
        cfg = carregar_config()
        reiniciados = []
        if "ip_modem" in dados and str(dados["ip_modem"]).strip():
            ip = str(dados["ip_modem"]).strip()
            if not ip.startswith("http"):
                ip = f"http://{ip}"
            if ip != cfg["ip_modem"]:
                cfg["ip_modem"] = ip
                if esta_rodando("monitor"):
                    parar("monitor")
                    iniciar("monitor")
                    reiniciados.append("monitor")
        for campo in ("login_path", "dados_path"):
            if campo in dados and str(dados[campo]).strip():
                caminho_novo = str(dados[campo]).strip()
                if not caminho_novo.startswith("/"):
                    self._json({"erro": f"{campo} deve comecar com /"}, 400)
                    return
                cfg[campo] = caminho_novo
        padroes = {}
        for campo in ("padrao_rx", "padrao_tx", "padrao_ppp"):
            if campo not in dados:
                continue
            bruto = str(dados[campo] or "").strip()
            padroes[campo] = bruto
            if bruto:
                import re as _re
                try:
                    _re.compile(bruto)
                except _re.error as erro:
                    self._json({"erro": f"regex invalida em {campo}: {erro}"}, 400)
                    return
                cfg[campo] = bruto
        mudou_leitura = bool(padroes) or "login_path" in dados or "dados_path" in dados
        intervalo_novo = None
        if "intervalo_min" in dados:
            try:
                intervalo_novo = max(1, int(dados["intervalo_min"]))
            except (TypeError, ValueError):
                self._json({"erro": "intervalo_min invalido"}, 400)
                return
            if intervalo_novo != cfg["intervalo_min"]:
                cfg["intervalo_min"] = intervalo_novo
                if esta_rodando("velocidade"):
                    parar("velocidade")
                    iniciar("velocidade")
                    reiniciados.append("velocidade")
        if "velocidade_contratada" in dados:
            try:
                cfg["velocidade_contratada"] = max(0.0, float(dados["velocidade_contratada"] or 0))
            except (TypeError, ValueError):
                self._json({"erro": "velocidade_contratada invalida"}, 400)
                return
        usuario = str(dados.get("usuario") or "").strip()
        senha = str(dados.get("senha") or "")
        if usuario or senha:
            if not usuario or not senha:
                self._json({"erro": "informe usuario e senha juntos"}, 400)
                return
            cfg["usuario"] = usuario
            cfg["senha"] = senha
            escrever_credenciais(usuario, senha)
            if esta_rodando("monitor") and "monitor" not in reiniciados:
                parar("monitor")
                iniciar("monitor")
                reiniciados.append("monitor")
        if mudou_leitura and esta_rodando("monitor") and "monitor" not in reiniciados:
            parar("monitor")
            iniciar("monitor")
            reiniciados.append("monitor")
        salvar_config(cfg)
        resposta = configuracao_publica()
        resposta["reiniciados"] = reiniciados
        self._json(resposta)

    def _apagar_dados(self):
        dados = self._corpo_json()
        if dados is None:
            self._json({"erro": "json invalido"}, 400)
            return
        modo = str(dados.get("modo") or "")
        limite = None
        if modo == "antes":
            data = str(dados.get("data") or "").strip()
            if not data:
                self._json({"erro": "informe a data"}, 400)
                return
            limite = data.replace("T", " ")
            if len(limite) == 16:
                limite += ":00"
        elif modo != "tudo":
            self._json({"erro": "modo deve ser 'tudo' ou 'antes'"}, 400)
            return
        restantes = apagar_dados(limite)
        self._json({"ok": True, "restantes": restantes})

    def _mudar_porta(self):
        dados = self._corpo_json()
        if dados is None:
            self._json({"erro": "json invalido"}, 400)
            return
        try:
            nova = int(dados.get("porta"))
        except (TypeError, ValueError):
            nova = 0
        if not 1024 <= nova <= 65535:
            self._json({"erro": "porta deve estar entre 1024 e 65535"}, 400)
            return
        cfg = carregar_config()
        cfg["porta"] = nova
        salvar_config(cfg)
        self._json({"ok": True, "porta": nova})
        threading.Thread(target=_trocar_porta, args=(nova,), daemon=True).start()

    def log_message(self, formato, *args):
        pass


def _trocar_porta(nova):
    antigo = estado_servidor["servidor"]
    if antigo is None:
        return
    novo = ThreadingHTTPServer(("0.0.0.0", nova), Manipulador)
    estado_servidor.update(porta=nova, servidor=novo)
    threading.Thread(target=antigo.shutdown, daemon=True).start()


def main():
    cfg = carregar_config()
    srv = ThreadingHTTPServer(("0.0.0.0", int(cfg["porta"])), Manipulador)
    estado_servidor.update(porta=int(cfg["porta"]), servidor=srv)
    print(f"Painel em http://localhost:{estado_servidor['porta']}/grafico.html")
    print(f"Administracao em http://localhost:{estado_servidor['porta']}/admin.html")
    try:
        while True:
            srv.serve_forever()
            novo = estado_servidor["servidor"]
            if novo is srv:
                break
            srv = novo
            print(f"Porta alterada para {estado_servidor['porta']}")
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
