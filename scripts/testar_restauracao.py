#!/usr/bin/env python3
"""Teste REAL de restauração: reconstrói um banco do zero a partir dos snapshots versionados (data/) e confere a integridade.
Um backup só conta como funcional depois deste teste passar. Usa um banco temporário (nunca toca em dados de produção).
Saída: JSON com contagens e resultado; código 1 se algo não bater.  Uso: python scripts/testar_restauracao.py [pasta_data]"""
import gzip
import json
import os
import sys
import tempfile
import time

pasta = sys.argv[1] if len(sys.argv) > 1 else "data"
tmp = tempfile.mkdtemp(prefix="turiz-restauracao-")
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/restaurado.db"
sys.path.insert(0, os.getcwd())

from sqlalchemy import func, select, text  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Evento, Lugar  # noqa: E402
from app.restaurar import restaurar  # noqa: E402

t0 = time.time()
falhas = []
saida = {"pasta": pasta}
restaurar(pasta)
with SessionLocal() as db:
    saida["lugares_restaurados"] = db.scalar(select(func.count(Lugar.id)))
    saida["eventos_restaurados"] = db.scalar(select(func.count(Evento.id)))
    saida["integridade_sqlite"] = db.execute(text("PRAGMA integrity_check")).scalar()
    saida["chaves_estrangeiras_quebradas"] = len(db.execute(text("PRAGMA foreign_key_check")).fetchall())
# esperado = o que está nos arquivos
esperado_lugares = len(json.load(open(f"{pasta}/lugares.json", encoding="utf-8")))
rec = f"{pasta}/lugares_receita.json.gz"
if os.path.exists(rec):
    with gzip.open(rec, "rt", encoding="utf-8") as f:
        ids_rec = {r["fonte_id"] for r in json.load(f)}
    ids_json = {r["fonte_id"] for r in json.load(open(f"{pasta}/lugares.json", encoding="utf-8")) if r["fonte"] == "receita"}
    esperado_lugares += len(ids_rec - ids_json)
saida["lugares_esperados"] = esperado_lugares
if saida["lugares_restaurados"] < esperado_lugares * 0.99:
    falhas.append(f"lugares: restaurou {saida['lugares_restaurados']} de {esperado_lugares}")
if saida["integridade_sqlite"] != "ok":
    falhas.append("PRAGMA integrity_check falhou")
if saida["chaves_estrangeiras_quebradas"]:
    falhas.append("chaves estrangeiras quebradas")
if saida["eventos_restaurados"] == 0 and os.path.exists(f"{pasta}/eventos_v2.json.gz"):
    falhas.append("nenhum evento restaurado")
saida["segundos"] = round(time.time() - t0, 1)
saida["ok"] = not falhas
saida["falhas"] = falhas
print(json.dumps(saida, ensure_ascii=False, indent=1))
sys.exit(0 if not falhas else 1)
