import hashlib
import html
import json
import re
import segredos
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "http://192.168.15.1"


def _base_do_config():
    try:
        cfg = json.loads(
            (Path(__file__).parent / "config_testador.json").read_text(encoding="utf-8")
        )
        ip = str(cfg.get("ip_modem") or "").strip()
        if ip:
            return ip if ip.startswith("http") else f"http://{ip}"
    except Exception:
        pass
    return BASE


def carregar_credenciais(caminho="config.txt"):
    try:
        cfg = json.loads(
            (Path(__file__).parent / "config_testador.json").read_text(encoding="utf-8")
        )
        usuario = str(cfg.get("usuario") or "").strip()
        senha = str(cfg.get("senha") or "")
        if usuario and senha:
            return usuario, segredos.desproteger(senha)
    except Exception:
        pass
    with open(caminho, encoding="utf-8") as arq:
        usuario, senha = arq.read().split()
    return usuario, senha


def avaliar_sinal_rx(rx_dbm):
    if rx_dbm > -25:
        return "OK (ideal: melhor que -25 dBm)"
    if rx_dbm >= -28:
        return "ATENCAO: sinal fraco, na faixa de -25 a -28 dBm"
    return "CRITICO: sinal abaixo de -28 dBm, fora da especificacao"


def _codificar_senha(senha):
    codificada = urllib.parse.quote(senha, safe="'()*-._~")
    return re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), codificada)


class Roteador:
    def __init__(self, base=None):
        self.base = base or _base_do_config()
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def _get(self, caminho):
        req = urllib.request.Request(self.base + caminho)
        resp = self.opener.open(req, timeout=10)
        return resp.read().decode("utf-8", errors="replace")

    def _post(self, caminho, dados):
        corpo = urllib.parse.urlencode(dados).encode()
        req = urllib.request.Request(self.base + caminho, data=corpo)
        resp = self.opener.open(req, timeout=10)
        return resp.read().decode("utf-8", errors="replace")

    def entrar(self, usuario, senha):
        pagina = self._get("/cgi-bin/login.cgi")
        m = re.search(r"sid\s*=\s*'([0-9a-fA-F]+)'", pagina)
        if not m:
            raise RuntimeError("sid nao encontrado na pagina de login")
        sid = m.group(1)
        hash_senha = hashlib.md5(
            f"{_codificar_senha(senha)}:{sid}".encode()
        ).hexdigest()
        self._post(
            "/cgi-bin/login.cgi",
            {
                "Loginuser": usuario,
                "LoginPasswordValue": hash_senha,
                "acceptLoginIndex": "1",
            },
        )
        nomes = {c.name for c in self.jar}
        if "COOKIE_SESSION_KEY" not in nomes:
            raise RuntimeError("falha no login: cookie de sessao nao recebido")

    def _buscar_pagina(self, caminho):
        return html.unescape(self._get(caminho))

    def dispositivo(self):
        pagina = self._buscar_pagina("/cgi-bin/about-power-box.cgi")
        campos = {}
        padroes = {
            "fabricante": r"Fabricante:</span></strong></td><td>([^<]+)</td>",
            "modelo": r"Modelo:</span></strong></td><td>([^<]+)</td>",
            "firmware": r"Software:</span></strong></td><td>([^<]+)</td>",
            "serial": r"MLG_Serial_Number'>[^<]*</span></strong></td><td>([^<]+)</td>",
        }
        for chave, padrao in padroes.items():
            m = re.search(padrao, pagina)
            campos[chave] = m.group(1).strip() if m else "?"
        return campos

    def status_fibra(self):
        pagina = self._buscar_pagina("/cgi-bin/sophia_info.cgi")
        rx_m = re.search(r"Potência Rx:</strong>\s*<br/>\s*(-?[\d.]+)\s*dBm", pagina)
        tx_m = re.search(r"Potência Tx:</strong>\s*<br/>\s*(-?[\d.]+)\s*dBm", pagina)
        ppp_m = re.search(r"PPP:</strong>\s*<br/>\s*<span>([^<]+)</span>", pagina)
        return {
            "rx_dbm": float(rx_m.group(1)) if rx_m else None,
            "tx_dbm": float(tx_m.group(1)) if tx_m else None,
            "ppp": ppp_m.group(1).strip() if ppp_m else None,
        }

    def logs(self):
        pagina = self._buscar_pagina("/cgi-bin/sophia_viewsyslog.cgi")
        m = re.search(r'gblpagenum" id="gblpagenum" value="(\d+)"', pagina)
        paginas = int(m.group(1)) if m else 0
        texto = re.sub(r"<script.*?</script>", "", pagina, flags=re.S)
        texto = re.sub(r"<[^>]+>", "\n", texto)
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        entradas = [
            l for l in linhas
            if re.match(r"\w{3}\s+\w{3}\s+\d+", l) or ":" in l and len(l.split()) > 4
        ]
        return {"paginas": paginas, "entradas": entradas}
