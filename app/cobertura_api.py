"""API da Cobertura Geográfica. Dados internos de planejamento: toda leitura exige chave com escopo 'moderacao' ou maior; o recálculo exige 'admin'.
Lê só os arquivos data/coverage_* (nunca altera lugares). Recálculo: uma execução por vez e intervalo mínimo entre execuções."""
import os
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from .seguranca.chaves import exigir_escopo

router = APIRouter(prefix="/coverage", tags=["cobertura"])
_trava = threading.Lock()
_ultimo = {"t": 0.0}
INTERVALO_MIN_S = 300
FAIXAS = "^(muito_boa|boa|moderada|baixa|critica|desconhecida)$"
ZONAS = "^(Centro|Norte|Sul|Leste|Oeste)$"


def _dados():
    return os.environ.get("TURIZ_DADOS", "data")


def _ler(nome):
    from cobertura.execucao import ler
    obj = ler(_dados(), nome)
    if obj is None:
        raise HTTPException(404, "A análise de cobertura ainda não foi gerada.")
    return obj


leitura = [Depends(exigir_escopo("moderacao"))]


@router.get("", dependencies=leitura)
def cobertura_geral():
    return _ler("coverage_summary")


@router.get("/neighborhoods", dependencies=leitura)
def bairros(zona: str | None = Query(None, pattern=ZONAS), status: str | None = Query(None, pattern=FAIXAS), limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0, le=1000)):
    ms = _ler("coverage_metrics")["metricas"]
    zonas = {d["id"]: d["zone"] for d in _ler("coverage_neighborhoods")["distritos"]}
    nomes = {d["id"]: d["name"] for d in _ler("coverage_neighborhoods")["distritos"]}
    ms = [{**m, "name": nomes[m["id"]], "zone": zonas[m["id"]]} for m in ms if (not zona or zonas[m["id"]] == zona) and (not status or m["status"] == status)]
    return {"total": len(ms), "itens": ms[offset:offset + limit]}


def _detalhe(codigo: str):
    if not codigo.isdigit() or len(codigo) > 4:
        raise HTTPException(422, "código de distrito inválido")
    d = next((x for x in _ler("coverage_neighborhoods")["distritos"] if x["id"] == codigo), None)
    if not d:
        raise HTTPException(404, "distrito não encontrado")
    m = next(x for x in _ler("coverage_metrics")["metricas"] if x["id"] == codigo)
    cats = [c for c in _ler("coverage_categories")["categorias"] if c["neighborhood_id"] == codigo]
    pri = [p for p in _ler("coverage_priorities")["prioridades"] if p["neighborhood_id"] == codigo]
    hist = [{"snapshot_date": s["snapshot_date"], **s["distritos"][codigo]} for s in _ler("coverage_history")["snapshots"] if codigo in s["distritos"]]
    return {"distrito": {k: v for k, v in d.items() if k != "geometry"}, "metricas": m, "categorias": cats, "prioridades": pri, "historico": hist}


router.add_api_route("/neighborhoods/{codigo}", _detalhe, methods=["GET"], dependencies=leitura)


@router.get("/categories", dependencies=leitura)
def categorias(categoria: str | None = Query(None, pattern="^[a-z_]{1,40}$"), limit: int = Query(200, ge=1, le=500)):
    obj = _ler("coverage_categories")
    cs = [c for c in obj["categorias"] if not categoria or c["category"] == categoria]
    return {"categorias_cidade": obj["categorias_cidade"], "itens": cs[:limit]}


@router.get("/priorities", dependencies=leitura)
def prioridades(limit: int = Query(50, ge=1, le=500), categoria: str | None = Query(None, pattern="^[a-z_]{1,40}$"), distrito: str | None = Query(None, pattern="^[0-9]{1,4}$")):
    ps = _ler("coverage_priorities")["prioridades"]
    ps = [p for p in ps if (not categoria or p["category"] == categoria) and (not distrito or p["neighborhood_id"] == distrito)]
    return {"total": len(ps), "itens": ps[:limit]}


@router.get("/history", dependencies=leitura)
def historico(limit: int = Query(30, ge=1, le=400)):
    h = _ler("coverage_history")
    return {"snapshots": h["snapshots"][-limit:], "buscas": h["buscas"][-limit:]}


@router.get("/comparison", dependencies=leitura)
def comparacao():
    from cobertura.execucao import comparar
    c = comparar(_ler("coverage_history"))
    if c is None:
        raise HTTPException(404, "É preciso ao menos dois snapshots para comparar.")
    return c


@router.post("/recalculate", dependencies=[Depends(exigir_escopo("admin"))])
def recalcular():
    agora = time.monotonic()
    if agora - _ultimo["t"] < INTERVALO_MIN_S and _ultimo["t"]:
        raise HTTPException(429, "Recálculo recente. Tente de novo em alguns minutos.", headers={"Retry-After": str(int(INTERVALO_MIN_S - (agora - _ultimo["t"])))})
    if not _trava.acquire(blocking=False):
        raise HTTPException(409, "Já existe um recálculo em andamento.")
    try:
        from cobertura.rodar import rodar
        resumo = rodar(dados=_dados())
        _ultimo["t"] = time.monotonic()
        return {"ok": True, "score_medio": resumo["score_medio"], "faixas": resumo["faixas"]}
    finally:
        _trava.release()
