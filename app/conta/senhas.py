"""Senhas: hash Argon2id (parâmetros acima do mínimo recomendado pela OWASP), política NIST (tamanho, sem regras de composição),
verificação em tempo equalizado para contas inexistentes (evita enumeração por tempo)."""
import re
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)   # Argon2id (padrão da biblioteca)
_DUMMY = _ph.hash("turiz-hash-de-equalizacao-de-tempo")
MIN, MAX = 10, 128
COMUNS = {"1234567890", "123456789012", "senha12345", "senhasenha", "password123", "qwertyuiop", "1q2w3e4r5t", "turiz12345", "turizturiz",
          "abc1234567", "brasil12345", "mudar12345", "admin12345", "0123456789", "senha123456", "passw0rd123", "letmein1234", "iloveyou12"}


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar(senha: str, hash_: str | None) -> bool:
    """Sempre faz o mesmo trabalho, exista a conta ou não."""
    try:
        return _ph.verify(hash_ or _DUMMY, senha) and hash_ is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def precisa_rehash(hash_: str) -> bool:
    return _ph.check_needs_rehash(hash_)


def validar_politica(senha: str, email: str = "") -> str | None:
    """None se aceita; senão a mensagem (para o usuário). Não revela nada sobre contas existentes."""
    if not isinstance(senha, str) or len(senha) < MIN:
        return f"A senha precisa ter pelo menos {MIN} caracteres."
    if len(senha) > MAX:
        return f"A senha pode ter no máximo {MAX} caracteres."
    baixa = senha.lower()
    if baixa in COMUNS or re.fullmatch(r"(.)\1+", senha) or re.fullmatch(r"\d+", senha) and len(set(senha)) < 4:
        return "Essa senha é fácil demais de adivinhar. Use uma frase longa ou um gerenciador de senhas."
    local = email.split("@")[0].lower() if email else ""
    if local and len(local) >= 4 and local in baixa:
        return "A senha não pode conter o seu e-mail."
    return None
