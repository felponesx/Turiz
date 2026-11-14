"""Agendador de coletas por fonte: cada fonte tem seu intervalo, é executada isolada e deixa log + saúde.

Uma fonte que falha (chave ausente, bloqueio, queda, limite) NÃO interrompe as outras: o erro vira registro em `evento_coletas_log`
e a saúde da fonte (ok/erro/aguardando_credencial/bloqueada). Mensagens são redigidas (sem chaves/tokens)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session
from .conectores import REGISTRO
from .conectores.base import Contexto, ErroFonte, Estatisticas, Requisitor, redigir
from .modelos import EventoColetaLog, EventoFonte
from .persistir import ciclo_de_vida, ingerir

ARQUIVO_PADRAO = "fontes_eventos.yml"
REPETIR_APOS_ERRO_H = 2


def _agora():
    return datetime.now(timezone.utc)


def _utc(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def sincronizar_fontes(db: Session, caminho: str = ARQUIVO_PADRAO) -> dict:
    """Lê o cadastro em arquivo e cria/atualiza `evento_fontes` (fontes criadas pelo admin não são sobrescritas)."""
    if not Path(caminho).exists():
        return {"criadas": 0, "atualizadas": 0}
    cfg = yaml.safe_load(open(caminho, encoding="utf-8")) or {}
    criadas = atualizadas = 0
    for s in cfg.get("fontes") or []:
        slug = s["slug"]
        if s["conector"] not in REGISTRO:
            raise ValueError(f"fonte {slug}: conector desconhecido {s['conector']!r} (use {sorted(REGISTRO)})")
        f = db.scalar(select(EventoFonte).where(EventoFonte.slug == slug))
        novo = f is None
        if novo:
            f = EventoFonte(slug=slug, origem="arquivo")
            db.add(f)
        elif f.origem != "arquivo":
            continue
        f.nome, f.conector, f.config = s.get("nome", slug), s["conector"], s.get("config") or {}
        f.ativo, f.intervalo_horas, f.prioridade = bool(s.get("ativo", True)), int(s.get("intervalo_horas", 24)), int(s.get("prioridade", 50))
        f.autorizacao, f.observacao = s.get("autorizacao", "pendente"), s.get("observacao", "")[:500]
        if not f.ativo:
            f.saude = "desativada"
        elif f.saude == "desativada":
            f.saude = "nunca_executada"
        criadas, atualizadas = criadas + novo, atualizadas + (not novo)
    db.commit()
    return {"criadas": criadas, "atualizadas": atualizadas}


def esta_devida(f: EventoFonte, agora: datetime) -> bool:
    if not f.ativo or f.autorizacao == "bloqueada":
        return False
    if f.ultima_execucao_em is None:
        return True
    espera = REPETIR_APOS_ERRO_H if f.saude in ("erro", "parcial") else f.intervalo_horas
    return _utc(f.ultima_execucao_em) + timedelta(hours=espera) <= agora


def executar_fonte(db: Session, f: EventoFonte, client=None, limite: int | None = None, requisitor: Requisitor | None = None) -> EventoColetaLog:
    """Executa UMA fonte de ponta a ponta e registra o resultado. Nunca levanta exceção de fonte."""
    log = EventoColetaLog(fonte=f.slug, status="em_andamento")
    db.add(log)
    db.commit()
    st = Estatisticas()
    status, mensagem = "sucesso", ""
    try:
        if not f.ativo:
            raise ErroFonte("fonte desativada")
        if f.autorizacao == "bloqueada":
            status, mensagem = "ignorada", "fonte marcada como bloqueada (sem autorização de coleta)"
        else:
            cls = REGISTRO[f.conector]
            req = requisitor or Requisitor(client=client, stats=st)
            req.stats = st
            ctx = Contexto(slug=f.slug, config=dict(f.config or {}), requisitor=req, stats=st, limite=limite)
            r = ingerir(db, f.slug, cls().coletar(ctx), prioridade=f.prioridade)
            log.coletados, log.novos, log.atualizados, log.duplicados, log.revisao, log.descartados = r.coletados, r.novos, r.atualizados, r.duplicados, r.revisao, r.descartados
            if st.parcial:
                status, mensagem = "parcial", st.mensagem
            elif r.coletados == 0:
                status, mensagem = "sucesso", "nenhum evento retornado"
            if r.descartados:
                mensagem = (mensagem + "; " if mensagem else "") + "descartados: " + ", ".join(f"{k} x{v}" for k, v in r.motivos_descarte.most_common(3))
    except ErroFonte as exc:
        status, mensagem = exc.status, redigir(str(exc))
    except Exception as exc:                                    # falha inesperada também fica isolada
        db.rollback()
        status, mensagem = "erro", redigir(f"{type(exc).__name__}: {exc}")
    log = db.merge(log)
    log.status, log.mensagem, log.terminado_em = status, mensagem[:500], _agora()
    log.paginas, log.erros = st.paginas, st.erros
    f = db.merge(f)
    f.ultima_execucao_em = log.terminado_em
    f.saude = {"sucesso": "ok", "ignorada": "bloqueada"}.get(status, status)
    if status in ("sucesso", "parcial"):
        f.ultimo_sucesso_em, f.ultimo_erro = log.terminado_em, ""
    else:
        f.ultimo_erro = mensagem[:500]
    db.commit()
    return log


def executar_devidas(db: Session, agora: datetime | None = None, apenas: list[str] | None = None, forcar: bool = False, client=None,
                     limite: int | None = None) -> list[EventoColetaLog]:
    agora = agora or _agora()
    logs = []
    for f in db.scalars(select(EventoFonte).order_by(EventoFonte.prioridade.desc(), EventoFonte.slug)).all():
        if apenas and f.slug not in apenas:
            continue
        if not forcar and not esta_devida(f, agora):
            continue
        logs.append(executar_fonte(db, f, client=client, limite=limite))
    ciclo_de_vida(db, agora)
    return logs


def painel(db: Session) -> list[dict]:
    """Saúde de todas as fontes (para o admin e para o monitoramento)."""
    return [{"slug": f.slug, "nome": f.nome, "conector": f.conector, "ativo": f.ativo, "autorizacao": f.autorizacao, "saude": f.saude,
             "ultima_execucao_em": f.ultima_execucao_em, "ultimo_sucesso_em": f.ultimo_sucesso_em, "ultimo_erro": f.ultimo_erro, "intervalo_horas": f.intervalo_horas}
            for f in db.scalars(select(EventoFonte).order_by(EventoFonte.slug))]
