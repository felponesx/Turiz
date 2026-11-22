"""Cifra de segredos recuperáveis (TOTP) com Fernet. A chave vem de TURIZ_ENC_KEY (obrigatória em produção)."""
import os
from cryptography.fernet import Fernet, InvalidToken
from ..seguranca import config

_EFEMERA = None


def _fernet() -> Fernet:
    global _EFEMERA
    chave = os.getenv("TURIZ_ENC_KEY", "")
    if chave:
        return Fernet(chave.encode())
    if config.producao():
        raise RuntimeError("TURIZ_ENC_KEY é obrigatória em produção (gere com: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')")
    if _EFEMERA is None:
        _EFEMERA = Fernet(Fernet.generate_key())
    return _EFEMERA


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
