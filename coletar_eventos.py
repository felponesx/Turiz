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
    upgrade_head()
    with SessionLocal() as db:
        print("sincronizar:", agendador.sincronizar_fontes(db))
        if a.cmd == "fontes":
            for f in agendador.painel(db):
                print(f"{f['slug']:<22} {f['conector']:<12} saúde={f['saude']:<22} autorização={f['autorizacao']:<10} último_sucesso={f['ultimo_sucesso_em']} {f['ultimo_erro']}")
        elif a.cmd == "rodar":
            logs = agendador.executar_devidas(db, apenas=a.fonte, forcar=a.forcar, limite=a.limite)
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
        elif a.cmd == "duplicatas":
            for d in db.scalars(select(EventoDuplicata).where(EventoDuplicata.status == "pendente")):
                print(d.id, d.evento_a_id, d.evento_b_id, d.score, d.motivos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
