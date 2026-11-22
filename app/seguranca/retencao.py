"""Retenção (LGPD: guardar só o necessário, pelo tempo necessário). Rode periodicamente (cron/agendador do provedor):
    python -m app.seguranca.retencao
Apaga: trilha de auditoria > 12 meses; sessões expiradas/revogadas há > 90 dias; tokens de conta usados/expirados há > 30 dias."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, or_
from sqlalchemy.orm import Session
from .modelos import Auditoria, Sessao, TokenConta

AUDITORIA = timedelta(days=365)
SESSOES = timedelta(days=90)
TOKENS = timedelta(days=30)


def limpar(db: Session, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    r = {}
    r["auditoria"] = db.execute(delete(Auditoria).where(Auditoria.quando < agora - AUDITORIA)).rowcount
    r["sessoes"] = db.execute(delete(Sessao).where(or_(Sessao.expira_em < agora - SESSOES, Sessao.revogada_em < agora - SESSOES))).rowcount
    r["tokens"] = db.execute(delete(TokenConta).where(or_(TokenConta.expira_em < agora - TOKENS, TokenConta.usado_em < agora - TOKENS))).rowcount
    db.commit()
    return r


if __name__ == "__main__":
    from ..db import SessionLocal
    from ..migrar import upgrade_head
    upgrade_head()
    with SessionLocal() as db:
        print(limpar(db))
