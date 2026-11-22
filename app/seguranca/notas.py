"""Validação de nota fiscal (NFC-e/NF-e) SEM guardar o documento nem o CNPJ.

O app lê o QR Code no aparelho; o servidor recebe só o link/chave. Aqui: extraímos a chave de acesso (44 dígitos), conferimos o dígito
verificador (módulo 11), e devolvemos apenas HASHES com segredo (HMAC): um para impedir a mesma nota duas vezes e outro do emitente.
A chave de acesso contém o CNPJ do emitente: por isso ela NUNCA é gravada nem registrada em log. Decisão do projeto: CNPJ não aparece
no site, na API, no banco nem no GitHub."""
import hashlib
import hmac
import re
from dataclasses import dataclass
from . import config

_CHAVE = re.compile(r"(?<!\d)(\d{44})(?!\d)")


def _dv(base43: str) -> int:
    peso, soma = 2, 0
    for d in reversed(base43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    r = soma % 11
    return 0 if r in (0, 1) else 11 - r


def extrair_chave(texto: str) -> str | None:
    """Acha a chave de 44 dígitos no texto/URL do QR (aceita espaços e a forma 'p=CHAVE|...')."""
    compacto = re.sub(r"[\s.-]", "", texto or "")
    for m in _CHAVE.finditer(compacto):
        c = m.group(1)
        if _dv(c[:43]) == int(c[43]):
            return c
    return None


@dataclass(frozen=True)
class NotaValidada:
    hash_nota: str           # HMAC da chave inteira: identifica a nota sem revelá-la (dedupe)
    hash_emitente: str       # HMAC do CNPJ do emitente: permite agrupar notas do mesmo estabelecimento sem guardar o CNPJ
    uf: str
    ano_mes: str             # AAMM de emissão (para regras de validade)


_UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE",
       "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


def validar(texto: str) -> NotaValidada | None:
    chave = extrair_chave(texto)
    if not chave or chave[:2] not in _UF:
        return None
    seg = config.segredo_hmac()
    h = lambda rotulo, v: hmac.new(seg, f"{rotulo}:{v}".encode(), hashlib.sha256).hexdigest()
    return NotaValidada(h("nota", chave), h("emitente", chave[6:20]), _UF[chave[:2]], chave[2:6])
