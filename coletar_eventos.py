#!/usr/bin/env python3
"""CLI da coleta de eventos (sistema inteligente de eventos do TURIZ).

  python coletar_eventos.py sincronizar                   # lê fontes_eventos.yml -> tabela evento_fontes
  python coletar_eventos.py rodar [--fonte SLUG ...] [--forcar] [--limite N]
  python coletar_eventos.py fontes                        # saúde de cada fonte
  python coletar_eventos.py validar-ticketmaster          # consulta REAL mínima (precisa de TICKETMASTER_API_KEY)
  python coletar_eventos.py duplicatas                    # fila de revisão
Depois de rodar, exporta o snapshot (data/eventos_v2.json.gz + data/eventos.json legado). Nenhuma chave é impressa."""
import argparse
import json
import sys
from app.db import SessionLocal
from app.migrar import upgrade_head
from app.eventos import agendador, snapshot
from app.eventos.modelos import EventoDuplicata
from bots.status import bot
from sqlalchemy import select


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sincronizar")
    r = sub.add_parser("rodar")
    r.add_argument("--fonte", nargs="*")
    r.add_argument("--forcar", action="store_true")
    r.add_argument("--limite", type=int)
    r.add_argument("--sem-exportar", action="store_true")
    sub.add_parser("fontes")
    sub.add_parser("validar-ticketmaster")
    sub.add_parser("duplicatas")
    a = ap.parse_args(argv)
    if a.cmd == "validar-ticketmaster":
        from app.eventos.conectores.ticketmaster import validar_credencial
        res = validar_credencial()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["ok"] or res["status"] == "aguardando_credencial" else 1
    if a.cmd == "rodar":
        with bot("eventos") as rep:
            return _executar(a, rep)
    return _executar(a, None)


def _executar(a, rep):
    upgrade_head()
    with SessionLocal() as db:
        print("sincronizar:", agendador.sincronizar_fontes(db))
        if rep:
            for f in agendador.painel(db):   # todas as fontes aparecem no painel, mesmo as que não estão devidas agora
                rep.fonte(f["slug"], f["nome"], f["saude"], conector=f["conector"], ultimo_sucesso=str(f["ultimo_sucesso_em"] or ""), mensagem=f["ultimo_erro"] or "")
        if a.cmd == "fontes":
            for f in agendador.painel(db):
                print(f"{f['slug']:<22} {f['conector']:<12} saúde={f['saude']:<22} autorização={f['autorizacao']:<10} último_sucesso={f['ultimo_sucesso_em']} {f['ultimo_erro']}")
        elif a.cmd == "rodar":
            def andamento(momento, feitas, total, f, lg):
                if momento == "inicio":
                    rep.progresso(feitas, total, atual=f.nome, etapa=f"Fonte {feitas + 1} de {total}")
                    rep.fonte(f.slug, f.nome, "rodando", conector=f.conector)
                    return
                rep.progresso(feitas, total, atual=f.nome)
                rep.fonte(f.slug, f.nome, lg.status, conector=f.conector, coletados=lg.coletados, novos=lg.novos, atualizados=lg.atualizados,
                          duplicados=lg.duplicados, descartados=lg.descartados, mensagem=lg.mensagem or "")
                rep.contar(captados=lg.coletados, novos=lg.novos, atualizados=lg.atualizados, duplicados=lg.duplicados)
                if lg.novos:
                    rep.item(f"{f.nome}: {lg.novos} eventos novos")
                if lg.status in ("erro", "parcial"):
                    rep.aviso(f"{f.nome}: {lg.status} {lg.mensagem or ''}".strip())
            logs = agendador.executar_devidas(db, apenas=a.fonte, forcar=a.forcar, limite=a.limite, progresso=andamento if rep else None)
            for l in logs:
                print(f"{l.fonte:<22} {l.status:<22} coletados={l.coletados} novos={l.novos} atualizados={l.atualizados} duplicados={l.duplicados} revisão={l.revisao} descartados={l.descartados} {l.mensagem}")
            if not logs:
                print("nenhuma fonte devida")
            from app.sources import vincular
            print("vínculo evento->lugar:", vincular.vincular_eventos(db))
            if not a.sem_exportar:
                print("snapshot:", snapshot.exportar(db))
                import coletar
                coletar.exportar(db)
            if rep:
                from sqlalchemy import func
                from app.models import Evento as EventoV2
                rep.total_no_sistema(eventos=db.scalar(select(func.count()).select_from(EventoV2)) or 0, fontes=len(agendador.painel(db)))
        elif a.cmd == "duplicatas":
            for d in db.scalars(select(EventoDuplicata).where(EventoDuplicata.status == "pendente")):
                print(d.id, d.evento_a_id, d.evento_b_id, d.score, d.motivos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
