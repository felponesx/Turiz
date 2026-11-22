"""Chaves de API com escopo, comparação em tempo constante, bloqueio de força bruta e trilha de auditoria.

Configuração (somente variáveis de ambiente):
  TURIZ_API_KEYS="coletor:ingest:<chave>,moderador:moderacao:<chave>,dono:admin:<chave>"   (várias, com escopo)
  API_KEY=<chave>                                                                            (legado = escopo admin)
Escopos: ingest (envio de lotes pelos bots) < moderacao (moderar avaliações/imagens) < admin (tudo, inclusive fontes de eventos).
Em produção, chaves com menos de 32 caracteres são recusadas."""
import hmac
import os
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from ..db import get_db
from . import config, limites
from .auditoria import registrar
from .ip import cliente_ip

NIVEL = {"ingest": 1, "moderacao": 2, "admin": 3}


@dataclass(frozen=True)
class Chave:
    nome: str
    escopo: str
    valor: str


def carregar() -> list[Chave]:
    chaves = []
    for item in os.getenv("TURIZ_API_KEYS", "").split(","):
        item = item.strip()
        if not item:
            continue
        nome, escopo, valor = (item.split(":", 2) + ["", "", ""])[:3]
        if escopo not in NIVEL or not valor:
            raise RuntimeError(f"TURIZ_API_KEYS inválida na entrada {nome!r}: use nome:escopo:chave com escopo em {sorted(NIVEL)}")
        chaves.append(Chave(nome, escopo, valor))
    legado = os.getenv("API_KEY", "")
    if legado:
        chaves.append(Chave("legado", "admin", legado))
    if config.producao():
        for c in chaves:
            if len(c.valor) < 32:
                raise RuntimeError(f"chave {c.nome!r} fraca: use pelo menos 32 caracteres em produção")
    return chaves


def identificar(valor: str | None) -> Chave | None:
    """Compara com TODAS as chaves em tempo constante (sem sair no primeiro acerto) para não vazar informação por tempo."""
    if not valor:
        return None
    achada = None
    for c in carregar():
        if hmac.compare_digest(valor.encode(), c.valor.encode()):
            achada = c
    return achada


def exigir_escopo(minimo: str):
    def dependencia(request: Request, x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> Chave:
        ip = cliente_ip(request)
        espera = limites.AUTH_FALHA.bloqueado(ip)          # bloqueio progressivo por IP depois de várias chaves erradas (temporário)
        if espera:
            registrar(db, request, ator="?", escopo=minimo, resultado="negado", detalhe="bloqueio temporário por tentativas")
            raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(espera)})
        chave = identificar(x_api_key)
        if chave is None or NIVEL[chave.escopo] < NIVEL[minimo]:
            permitido, espera = limites.AUTH_FALHA.verificar(ip)
            registrar(db, request, ator=chave.nome if chave else "?", escopo=minimo, resultado="negado",
                      detalhe="chave ausente/inválida" if chave is None else "escopo insuficiente")
            if not permitido:
                raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(espera)})
            raise HTTPException(401, "API key inválida")
        registrar(db, request, ator=chave.nome, escopo=chave.escopo, resultado="autorizado")
        return chave
    return dependencia


exigir_chave = exigir_escopo("admin")
