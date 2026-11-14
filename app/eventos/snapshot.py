"""Snapshot versionado dos eventos (data/eventos_v2.json.gz): todas as tabelas de eventos com os ids preservados.
O banco é reconstruível a partir daqui (snapshot-first). Só é restaurado em banco SEM eventos (nunca sobrescreve)."""
import gzip
import json
import os
from datetime import datetime, timezone
from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import Session
from ..models import Evento
from .modelos import (EventoArtista, EventoArtistaLink, EventoAtualizacao, EventoCategoria, EventoCategoriaLink, EventoColetaLog, EventoDuplicata,
                      EventoFonte, EventoFonteLink, EventoImagem, EventoLocal, EventoOrganizador)

ARQUIVO = "eventos_v2.json.gz"
# ordem respeita as chaves estrangeiras
TABELAS = [("fontes", EventoFonte), ("locais", EventoLocal), ("organizadores", EventoOrganizador), ("artistas", EventoArtista), ("categorias", EventoCategoria),
           ("eventos", Evento), ("fonte_links", EventoFonteLink), ("imagens", EventoImagem), ("artista_links", EventoArtistaLink),
           ("categoria_links", EventoCategoriaLink), ("atualizacoes", EventoAtualizacao), ("duplicatas", EventoDuplicata), ("coletas_log", EventoColetaLog)]
LIMITE_LOG = 1000


def _iso(v: datetime) -> str:
    """SQLite devolve datas sem fuso; nós sempre gravamos em UTC, então o snapshot declara o UTC explicitamente."""
    return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()


def _linha(o):
    return {c.name: (_iso(v) if isinstance(v := getattr(o, c.name), datetime) else v) for c in o.__table__.columns}


def exportar(db: Session, pasta: str = "data") -> dict:
    saida, cont = {}, {}
    for nome, modelo in TABELAS:
        st = select(modelo).order_by(modelo.id)
        if modelo is EventoColetaLog:
            st = select(modelo).order_by(modelo.id.desc()).limit(LIMITE_LOG)
        linhas = [_linha(o) for o in db.scalars(st)]
        saida[nome] = list(reversed(linhas)) if modelo is EventoColetaLog else linhas
        cont[nome] = len(linhas)
    os.makedirs(pasta, exist_ok=True)
    with gzip.open(os.path.join(pasta, ARQUIVO), "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
    return cont


def restaurar(db: Session, pasta: str = "data") -> dict | None:
    """None se não há snapshot ou se o banco já tem eventos."""
    p = os.path.join(pasta, ARQUIVO)
    if not os.path.exists(p) or db.scalar(select(func.count(Evento.id))):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        dados = json.load(f)
    cont = {}
    for nome, modelo in TABELAS:
        regs = dados.get(nome) or []
        datas = [c.name for c in modelo.__table__.columns if isinstance(c.type, DateTime)]
        for r in regs:
            for k in datas:
                if r.get(k):
                    r[k] = datetime.fromisoformat(r[k])
        if regs:
            db.bulk_insert_mappings(modelo, regs)
        cont[nome] = len(regs)
    db.commit()
    return cont
