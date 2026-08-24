import base64
import ctypes
import platform
import subprocess
from ctypes import wintypes

SERVICO = "mitracheck-vivo"

PREFIXO_DPAPI = "dpapi:"
PREFIXO_KEYCHAIN = "keychain:"
PREFIXO_SECRET_TOOL = "secrettool:"
PREFIXO_PLANO = "plano:"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _blob(dados: bytes) -> _DATA_BLOB:
    buffer = ctypes.create_string_buffer(dados, len(dados))
    return _DATA_BLOB(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _proteger_dpapi(texto: str) -> str:
    entrada = _blob(texto.encode("utf-8"))
    saida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)
    ):
        raise OSError("CryptProtectData falhou")
    try:
        bruto = ctypes.string_at(saida.pbData, saida.cbData)
        return PREFIXO_DPAPI + base64.b64encode(bruto).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _desproteger_dpapi(texto: str) -> str:
    bruto = base64.b64decode(texto[len(PREFIXO_DPAPI):])
    entrada = _blob(bruto)
    saida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)
    ):
        raise OSError("CryptUnprotectData falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _proteger_keychain(texto: str) -> str:
    subprocess.run(
        [
            "security", "add-generic-password",
            "-s", SERVICO,
            "-a", "segredo",
            "-w", texto,
            "-U",
        ],
        check=True,
        capture_output=True,
    )
    return PREFIXO_KEYCHAIN


def _obter_keychain() -> str:
    resultado = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICO, "-a", "segredo", "-w"],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError("item nao encontrado no keychain")
    return resultado.stdout.strip()


def _proteger_secret_tool(texto: str) -> str:
    subprocess.run(
        [
            "secret-tool", "store",
            "--label=MitraCheck Vivo",
            "servico", SERVICO,
            "senha", texto,
        ],
        check=True,
        capture_output=True,
    )
    return PREFIXO_SECRET_TOOL


def _obter_secret_tool() -> str:
    resultado = subprocess.run(
        ["secret-tool", "lookup", "servico", SERVICO],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0 or not resultado.stdout.strip():
        raise RuntimeError("item nao encontrado no gnome-keyring")
    return resultado.stdout.strip()


def proteger(texto: str) -> str:
    sistema = platform.system()
    if sistema == "Windows":
        return _proteger_dpapi(texto)
    if sistema == "Darwin":
        try:
            return _proteger_keychain(texto)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    elif sistema == "Linux":
        try:
            return _proteger_secret_tool(texto)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    import sys
    print(
        "AVISO: nenhum cofre de senhas disponivel; senha armazenada em texto claro "
        "em config_testador.json. Restrinja as permissoes do arquivo.",
        file=sys.stderr,
    )
    return PREFIXO_PLANO + texto


def desproteger(token: str) -> str:
    if token.startswith(PREFIXO_DPAPI):
        return _desproteger_dpapi(token)
    if token.startswith(PREFIXO_KEYCHAIN):
        return _obter_keychain()
    if token.startswith(PREFIXO_SECRET_TOOL):
        return _obter_secret_tool()
    if token.startswith(PREFIXO_PLANO):
        return token[len(PREFIXO_PLANO):]
    return token
