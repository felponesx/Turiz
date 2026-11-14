"""Rotas de eventos. Públicas: consulta (com limite de requisições por IP). Administrativas: exigem X-API-Key (mesma regra do restante da API)."""
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Evento
from . import agendador, busca, consulta
from .conectores import REGISTRO
from .conectores.base import redigir
from .consulta import Filtros
from .modelos import EventoAtualizacao, EventoColetaLog, EventoDuplicata, EventoFonte, EventoFonteLink

TZ = ZoneInfo("America/Sao_Paulo")
JANELA_S, MAX_REQ = 60, 120
_hist: dict[str, deque] = defaultdict(deque)


def limite_de_requisicoes(request: Request):
    """Janela deslizante por IP (em memória): protege a consulta pública contra excesso de chamadas."""
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?"))
    agora = time.monotonic()
    h = _hist[ip]
    while h and agora - h[0] > JANELA_S:
        h.popleft()
    if len(h) >= MAX_REQ:
        raise HTTPException(429, "Muitas requisições; tente novamente em instantes", headers={"Retry-After": str(JANELA_S)})
    h.append(agora)
    if len(_hist) > 5000:
        for k in [k for k, v in _hist.items() if not v or agora - v[-1] > JANELA_S][:2500]:
            _hist.pop(k, None)


def _dia_local(s: str | None, fim: bool = False) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, "data inválida (use AAAA-MM-DD)")
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
        if len(s) <= 10 and fim:
            d += timedelta(days=1)
    return d.astimezone(timezone.utc)


def criar_router(exigir_chave) -> APIRouter:
    r = APIRouter(dependencies=[Depends(limite_de_requisicoes)])

    @r.get("/eventos")
    def listar(q: str | None = None, categoria: str | None = None, cidade: str | None = None, estado: str | None = None, pais: str | None = None,
               data_de: str | None = None, data_ate: str | None = None, a_partir_de: datetime | None = None, preco_max: float | None = Query(None, ge=0),
               gratuito: bool | None = None, tipo_local: str | None = Query(None, pattern="^(restaurante|bar)$"), local: str | None = None, lugar_id: int | None = None,
               fonte: str | None = None, com_imagem: bool | None = None, incluir_cancelados: bool = False, incluir_encerrados: bool = False, incluir_sem_data: bool = False,
               ordem: str = Query("data", pattern="^(data|preco|recentes)$"), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
        f = Filtros(q=q, categoria=categoria, cidade=cidade, estado=estado, pais=pais, data_de=_dia_local(data_de) or a_partir_de, data_ate=_dia_local(data_ate, True),
                    preco_max=preco_max, gratuito=gratuito, tipo_local=tipo_local, local=local, lugar_id=lugar_id, fonte=fonte, com_imagem=com_imagem,
                    incluir_cancelados=incluir_cancelados, incluir_encerrados=incluir_encerrados, incluir_sem_data=incluir_sem_data, ordem=ordem)
        return consulta.listar(db, f, limit, offset)

    @r.get("/eventos/categorias")
    def categorias(db: Session = Depends(get_db)):
        return consulta.categorias_com_contagem(db)

    @r.get("/eventos/busca")
    def busca_natural(q: str = Query(..., min_length=2, max_length=200), limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
        f, info = busca.interpretar(db, q)
        res = consulta.listar(db, f, limit)
        return {"interpretacao": info, **res}

    @r.get("/eventos/{evento_id}")
    def detalhe(evento_id: int, db: Session = Depends(get_db)):
        e = db.get(Evento, evento_id)
        if not e:
            raise HTTPException(404, "evento não encontrado")
        return consulta.serializar(db, [e], completo=True)[0]       # cancelados/encerrados continuam acessíveis, com o status

    # ----------------------------------------------------------------- administração
    adm = APIRouter(prefix="/admin/eventos", dependencies=[Depends(exigir_chave)])

    @adm.get("/fontes")
    def fontes(db: Session = Depends(get_db)):
        return agendador.painel(db)

    class FonteIn(BaseModel):
        slug: str = Field(pattern="^[a-z0-9][a-z0-9-]{1,58}$")
        nome: str = Field(default="", max_length=200)
        conector: str
        config: dict = {}
        ativo: bool = True
        intervalo_horas: int = Field(default=24, ge=1, le=24 * 30)
        prioridade: int = Field(default=50, ge=0, le=100)
        autorizacao: str = Field(default="pendente", pattern="^(autorizada|pendente|bloqueada|nao_requer)$")
        observacao: str = Field(default="", max_length=500)

    @adm.put("/fontes")
    def salvar_fonte(b: FonteIn, db: Session = Depends(get_db)):
        if b.conector not in REGISTRO:
            raise HTTPException(422, f"conector desconhecido; use um de {sorted(REGISTRO)}")
        if any(k.lower() in ("apikey", "api_key", "token", "secret", "password", "senha", "chave") for k in b.config):
            raise HTTPException(422, "não guarde chaves/tokens na configuração: use variável de ambiente e `chave_env`")
        f = db.scalar(select(EventoFonte).where(EventoFonte.slug == b.slug)) or EventoFonte(slug=b.slug, origem="admin")
        for k, v in b.model_dump().items():
            setattr(f, k, v)
        if not f.ativo:
            f.saude = "desativada"
        db.add(f)
        db.commit()
        return {"slug": f.slug, "saude": f.saude}

    @adm.post("/fontes/{slug}/executar")
    def executar(slug: str, limite: int | None = Query(None, ge=1, le=1000), db: Session = Depends(get_db)):
        f = db.scalar(select(EventoFonte).where(EventoFonte.slug == slug))
        if not f:
            raise HTTPException(404, "fonte não encontrada")
        l = agendador.executar_fonte(db, f, limite=limite)
        return {"status": l.status, "coletados": l.coletados, "novos": l.novos, "atualizados": l.atualizados, "duplicados": l.duplicados, "revisao": l.revisao,
                "descartados": l.descartados, "mensagem": l.mensagem}

    @adm.get("/coletas")
    def coletas(fonte: str | None = None, limit: int = Query(50, le=500), db: Session = Depends(get_db)):
        st = select(EventoColetaLog).order_by(EventoColetaLog.id.desc()).limit(limit)
        if fonte:
            st = st.where(EventoColetaLog.fonte == fonte)
        return [{c.name: getattr(x, c.name) for c in EventoColetaLog.__table__.columns} for x in db.scalars(st)]

    @adm.get("/duplicatas")
    def duplicatas(status: str = Query("pendente", pattern="^(pendente|mesclado|distinto)$"), db: Session = Depends(get_db)):
        itens = db.scalars(select(EventoDuplicata).where(EventoDuplicata.status == status).order_by(EventoDuplicata.score.desc()).limit(200)).all()
        evs = {e.id: e for e in db.scalars(select(Evento).where(Evento.id.in_([i for d in itens for i in (d.evento_a_id, d.evento_b_id)] or [-1])))}
        return [{"id": d.id, "score": d.score, "motivos": d.motivos, "a": consulta.serializar(db, [evs[d.evento_a_id]])[0], "b": consulta.serializar(db, [evs[d.evento_b_id]])[0]} for d in itens]

    @adm.post("/duplicatas/{dup_id}/resolver")
    def resolver(dup_id: int, decisao: str = Query(..., pattern="^(mesmo|distinto)$"), db: Session = Depends(get_db)):
        """mesmo: o evento B vira link do A (todas as fontes/links são mantidos); distinto: marca como revisado."""
        d = db.get(EventoDuplicata, dup_id)
        if not d or d.status != "pendente":
            raise HTTPException(404, "par não encontrado ou já resolvido")
        if decisao == "mesmo":
            from .persistir import mesclar_eventos
            mesclar_eventos(db, d.evento_a_id, d.evento_b_id)
        d.status = "mesclado" if decisao == "mesmo" else "distinto"
        d.resolvido_em = datetime.now(timezone.utc)
        db.commit()
        return {"id": d.id, "status": d.status}

    @adm.get("/{evento_id}/historico")
    def historico(evento_id: int, db: Session = Depends(get_db)):
        return [{c.name: getattr(h, c.name) for c in EventoAtualizacao.__table__.columns}
                for h in db.scalars(select(EventoAtualizacao).where(EventoAtualizacao.evento_id == evento_id).order_by(EventoAtualizacao.id))]

    r.include_router(adm)
    return r
