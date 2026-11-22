"""Validação e saneamento de entradas externas."""
import re

_ESCAPE = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})
LIKE_ESCAPE = "\\"


def like(valor: str, maximo: int = 100) -> str:
    """Padrão LIKE seguro: caracteres curinga digitados pelo usuário viram texto literal (evita varrer a tabela inteira com '%')."""
    return "%" + str(valor)[:maximo].translate(_ESCAPE) + "%"


_REF = re.compile(r"^[A-Za-z0-9._:/@+\-]{1,100}$")


def ref_valida(ref: str) -> bool:
    return bool(_REF.match(ref or ""))


EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def email_valido(e: str) -> bool:
    return len(e) <= 254 and bool(EMAIL.match(e))


def texto_limpo(s: str, maximo: int) -> str:
    """Remove caracteres de controle e corta. O escape para HTML é responsabilidade de quem exibe (o front escapa tudo)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(s or "")).strip()[:maximo]


from typing import Annotated
from fastapi import Path

IdPositivo = Annotated[int, Path(ge=1, le=2_147_483_647)]     # ids de caminho: cabem num INTEGER; valores absurdos viram 422, não erro de banco
