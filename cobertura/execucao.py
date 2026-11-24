"""Leitura/gravação dos arquivos coverage_* e geração do resumo. A análise (analise.py) é pura; aqui fica o I/O."""
import gzip
import json
import os
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import analise, geo
from .categorias import config
from .metricas import ROTULO_FAIXA

TZ = ZoneInfo("America/Sao_Paulo")
ARQ = {"bairros": "coverage_neighborhoods", "metricas": "coverage_metrics", "categorias": "coverage_categories", "prioridades": "coverage_priorities",
       "historico": "coverage_history", "lugares": "coverage_places"}
SNAPSHOTS_MAX = 400


def ler(dados, nome, padrao=None):
    for arq, abrir in ((f"{dados}/{nome}.json", lambda p: open(p, encoding="utf-8")), (f"{dados}/{nome}.json.gz", lambda p: gzip.open(p, "rt", encoding="utf-8"))):
        if os.path.exists(arq):
            with abrir(arq) as f:
                return json.load(f)
    return padrao


def gravar(dados, nome, obj, gz=True):
    """gzip com mtime=0: o mesmo conteúdo gera os mesmos bytes (reexecutar não gera commit nem diferença)."""
    caminho = f"{dados}/{nome}.json" + (".gz" if gz else "")
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    tmp = caminho + ".tmp"
    if gz:
        with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as f:
            f.write(txt.encode("utf-8"))
    else:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(txt)
    os.replace(tmp, caminho)


def registrar_busca(historico: dict, **b) -> dict:
    """Acrescenta uma pesquisa ao histórico (id estável = não duplica). Scanners chamarão isto ao terminar; a Fase 5 não ativa nenhum."""
    obrig = {"neighborhood_id", "category", "scanner", "source", "search_started_at"}
    if not obrig <= set(b):
        raise ValueError("faltam campos: " + ", ".join(sorted(obrig - set(b))))
    item = {"results_found": 0, "new_places": 0, "duplicates": 0, "rejected": 0, "pending_review": 0, "status": "concluida", "error": None, "metadata": {}, "search_completed_at": None, **b}
    item["id"] = b.get("id") or f"{b['neighborhood_id']}:{b['category']}:{b['scanner']}:{b['search_started_at']}"
    buscas = [x for x in historico.setdefault("buscas", []) if x["id"] != item["id"]]
    buscas.append(item)
    historico["buscas"] = buscas
    return item


def fazer_snapshot(res, data_str) -> dict:
    return {"snapshot_date": data_str, "distritos": {m["id"]: {"total_places": m["total_places"], "coverage_score": m["coverage_score"], "diversity_score": m["diversity_score"], "quality_score": m["quality_score"],
            "category_count": m["category_count"], "location_score": m["location_score"], "category_metrics": {c["category"]: c["place_count"] for c in res["categorias"] if c["neighborhood_id"] == m["id"] and c["place_count"]}} for m in res["metricas"]}}


def atualizar_historico(historico, snap):
    snaps = [s for s in (historico or {}).get("snapshots", []) if s["snapshot_date"] != snap["snapshot_date"]]   # mesma data = substitui (idempotente); datas antigas nunca são tocadas
    snaps.append(snap)
    snaps.sort(key=lambda s: s["snapshot_date"])
    return {"snapshots": snaps[-SNAPSHOTS_MAX:], "buscas": (historico or {}).get("buscas", [])}


def comparar(historico):
    s = (historico or {}).get("snapshots", [])
    if len(s) < 2:
        return None
    a, b = s[-2], s[-1]
    mud = []
    for cod, nb in b["distritos"].items():
        na = a["distritos"].get(cod)
        if na and nb["coverage_score"] is not None and na["coverage_score"] is not None:
            mud.append({"id": cod, "delta_cobertura": nb["coverage_score"] - na["coverage_score"], "delta_lugares": nb["total_places"] - na["total_places"]})
    return {"de": a["snapshot_date"], "para": b["snapshot_date"], "melhoraram": sorted([m for m in mud if m["delta_cobertura"] > 0], key=lambda m: -m["delta_cobertura"])[:10],
            "pioraram": sorted([m for m in mud if m["delta_cobertura"] < 0], key=lambda m: m["delta_cobertura"])[:10], "novos_lugares": sum(m["delta_lugares"] for m in mud)}


def resumo(res, geo_dados, cfg, terr, rev, lugares, agora):
    dn = {d["codigo"]: d for d in geo_dados["distritos"]}
    ms = res["metricas"]
    av = [m for m in ms if m["coverage_score"] is not None]
    st = Counter(m["status"] for m in ms)
    top = lambda lst: [{"id": m["id"], "nome": dn[m["id"]]["nome"], "zona": dn[m["id"]]["zona"], "score": m["coverage_score"], "lugares": m["total_places"], "status": m["status"]} for m in lst]
    melhores = sorted(av, key=lambda m: (-m["coverage_score"], m["id"]))[:5]
    piores = sorted(av, key=lambda m: (m["coverage_score"], m["id"]))[:5]
    por_zona = {}
    for z in ("Centro", "Norte", "Sul", "Leste", "Oeste"):
        mz = [m for m in av if dn[m["id"]]["zona"] == z]
        por_zona[z] = {"distritos": sum(1 for d in dn.values() if d["zona"] == z), "lugares": sum(m["total_places"] for m in ms if dn[m["id"]]["zona"] == z),
                       "score_medio": round(sum(m["coverage_score"] for m in mz) / len(mz), 1) if mz else None}
    falta = Counter(c for m in av for c in m["missing_categories"])
    rotulo = lambda c: cfg["categorias"].get(c, {}).get("rotulo", "Eventos gastronômicos" if c == "eventos" else c)
    cats_ausentes = [{"categoria": c, "rotulo": rotulo(c), "distritos_sem": n, "lugares_na_cidade": res["categorias_cidade"].get(c, 0)} for c, n in falta.most_common(8)]
    cidade_pouco = sorted(res["categorias_cidade"].items(), key=lambda kv: kv[1])[:6]
    dist_prior = [p for p in res["prioridades"] if p["category"] is None][:5]
    scanners = Counter(s["id"] for p in dist_prior for s in p["recommended_scanners"])
    st_terr = Counter(v["status"] for k, v in terr.items() if k != "_erros")
    revmap = {r["id"]: r for r in rev}
    confiaveis = sum(1 for r in revmap.values() if r["s"] >= 75)
    aguardando = sum(1 for r in revmap.values() if r["s"] < 75)
    media = round(sum(m["coverage_score"] for m in av) / len(av), 1) if av else None
    ruim = st["baixa"] + st["critica"]
    sit = (f"{len(av)} de {len(ms)} distritos têm dados suficientes para avaliar; score médio {str(media).replace('.', ',')}. "
           + (f"{ruim} com cobertura baixa ou crítica. " if ruim else "Nenhum distrito está em cobertura baixa ou crítica com os dados atuais. ")
           + (f"{st['desconhecida']} sem dados suficientes (falta informação, não ausência de gastronomia). " if st["desconhecida"] else "")
           + f"{round(100 * sum(1 for l in lugares if territorial_precisa(terr.get(l['id']))) / max(1, len(lugares)))}% dos lugares têm distrito confirmado por coordenada precisa; o restante é aproximado, provável ou está perto de divisa.")
    return {"gerado_em": agora.astimezone(TZ).isoformat(timespec="seconds"), "situacao": sit, "score_medio": media, "faixas": {k: st.get(k, 0) for k in ("muito_boa", "boa", "moderada", "baixa", "critica", "desconhecida")},
            "distritos_mapeados": len(ms), "distritos_pesquisados": 0, "lugares_total": len(lugares), "lugares_com_distrito": sum(m["total_places"] for m in ms), "lugares_confiaveis": confiaveis, "lugares_aguardando_revisao": aguardando,
            "territorio": dict(st_terr), "categorias_identificadas": len([c for c, n in res["categorias_cidade"].items() if n]), "melhores": top(melhores), "maiores_lacunas": top(piores),
            "categorias_menos_encontradas": [{"categoria": c, "rotulo": rotulo(c), "lugares": n} for c, n in cidade_pouco], "categorias_com_mais_distritos_sem": cats_ausentes,
            "regioes_para_explorar": [{"id": p["neighborhood_id"], "nome": dn[p["neighborhood_id"]]["nome"], "prioridade": p["priority_score"], "motivo": p["priority_reason"]} for p in dist_prior],
            "scanners_sugeridos": [{"id": i, "nome": cfg["scanners"][i]["nome"], "disponivel": cfg["scanners"][i]["disponivel"], "distritos": n} for i, n in scanners.most_common()],
            "categorias_rotulos": {**{k: v.get("rotulo", k) for k, v in cfg["categorias"].items()}, "eventos": "Eventos gastronômicos"}, "geo_categorias": sorted(cfg.get("geo_scanner", {}).get("filtros", {})), "por_zona": por_zona, "meta_densidade_por_km2": res["meta_densidade"], "fonte_geografica": geo_dados["fonte"], "fonte_baixada_em": geo_dados["baixado_em"],
            "config": {"pesos_cobertura": cfg["pesos_cobertura"], "pesos_prioridade": cfg["pesos_prioridade"], "faixas": cfg["faixas"], "intervalos_dias": cfg["intervalos_dias"]},
            "limites": ["Não existe malha oficial de bairros: a unidade é o distrito (96); o bairro permanece desconhecido e o nome escrito no cadastro é só 'declarado'.",
                        "Só o Geo Scanner (OpenStreetMap) pesquisa por distrito; Web, Instagram e Social ainda não existem. O que ele acha fica como descoberta aguardando validação e não entra nos números de cobertura.",
                        "As categorias vêm do cadastro (tipo, culinária, CNAE e palavras do nome); o que o cadastro não diz não é detectado."]}


def territorial_precisa(t):
    return bool(t) and t["status"] == geo.CONFIRMED
