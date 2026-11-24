"""Orquestra a análise de cobertura: lê arquivos, roda analise.calcular, grava os coverage_* (idempotente)."""
import os
from datetime import datetime, timezone

from . import analise, execucao, geo
from .categorias import config

DADOS = os.environ.get("TURIZ_DADOS", "data")
CONFIG = os.environ.get("TURIZ_COBERTURA_CONFIG", "cobertura_config.yml")


def rodar(rep=None, dados=DADOS, agora=None):
    agora = agora or datetime.now(timezone.utc)
    p = (lambda *a, **k: rep.progresso(*a, **k)) if rep else (lambda *a, **k: None)
    cfg = config(CONFIG)
    soma = sum(cfg["pesos_cobertura"].values()), sum(cfg["pesos_prioridade"].values())
    if soma != (100, 100):
        raise ValueError(f"os pesos precisam somar 100 (cobertura {soma[0]}, prioridade {soma[1]})")
    p(0, 0, atual="Lendo distritos oficiais e lugares")
    g = geo.carregar(f"{dados}/geo/distritos_sp.json.gz")
    lugares = execucao.ler(dados, "lugares", [])
    rev = (execucao.ler(dados, "revisao", {}) or {}).get("lugares", [])
    eventos = execucao.ler(dados, "eventos", [])
    p(1, 6, atual="Associando lugares aos distritos")
    terr = analise.associar(lugares, g["distritos"], cfg)
    erros = terr.pop("_erros")
    p(2, 6, atual="Calculando cobertura e diversidade")
    hist_ant = execucao.ler(dados, "coverage_history", {}) or {}
    res = analise.calcular(lugares, terr, rev, eventos, g, cfg, agora, hist_ant.get("buscas", []))
    p(4, 6, atual="Gerando prioridades e histórico")
    data_str = agora.astimezone(execucao.TZ).date().isoformat()
    hist = execucao.atualizar_historico(hist_ant, execucao.fazer_snapshot(res, data_str))
    resumo = execucao.resumo(res, g, cfg, terr, rev, lugares, agora)
    resumo["comparacao"] = execucao.comparar(hist)
    resumo["distritos_pesquisados"] = sum(1 for m in res["metricas"] if m["last_search_at"])
    desc = (execucao.ler(dados, "descobertas", {}) or {}).get("descobertas", [])
    resumo["descobertas"] = {"total": len(desc), "novas": sum(1 for x in desc if x["status"] == "novo"), "possiveis_duplicados": sum(1 for x in desc if x["status"] == "possivel_duplicado")}
    resumo["buscas"] = {"total": len(hist["buscas"]), "falhas": sum(1 for b in hist["buscas"] if b.get("status") == "falhou")}
    resumo["erros_de_registro"] = len(erros)
    bairros = [{"id": d["codigo"], "name": d["nome"], "normalized_name": d["nome_norm"], "district": d["nome"], "zone": d["zona"], "subprefecture": geo.nome_bonito(d["subprefeitura"]) if d.get("subprefeitura") else None,
                "city": "São Paulo", "state": "SP", "area_km2": d.get("area_km2"), "neighborhood": None, "neighborhood_status": "unknown", "geometry": d["poligonos"], "source": "GeoSampa/Prefeitura de São Paulo",
                "source_updated_at": g["baixado_em"]} for d in g["distritos"]]
    execucao.gravar(dados, "coverage_neighborhoods", {"fonte": g["fonte"], "baixado_em": g["baixado_em"], "distritos": bairros})
    execucao.gravar(dados, "coverage_metrics", {"meta_densidade_por_km2": res["meta_densidade"], "metricas": res["metricas"]})
    execucao.gravar(dados, "coverage_categories", {"categorias_cidade": res["categorias_cidade"], "categorias": res["categorias"]})
    execucao.gravar(dados, "coverage_priorities", {"prioridades": res["prioridades"]})
    execucao.gravar(dados, "coverage_history", hist)
    execucao.gravar(dados, "coverage_places", {"lugares": [{"id": i, "d": t["distrito"], "s": t["status"], "p": t["precisao"], "o": t["origem"], "bd": t["bairro_declarado"]} for i, t in sorted(terr.items())]})
    execucao.gravar(dados, "coverage_summary", resumo, gz=False)
    p(6, 6)
    if rep:
        rep.definir(distritos=len(res["metricas"]), lugares_analisados=len(lugares), score_medio=resumo["score_medio"] or 0, prioridades=len(res["prioridades"]))
        for m in sorted(res["prioridades"], key=lambda x: -x["priority_score"])[:3]:
            rep.item(f"Prioridade {m['priority_score']} — {m['priority_reason']}")
        for i, e in erros[:10]:
            rep.aviso(f"registro {i} com erro ({e}); marcado como localização desconhecida")
    print(f"faixas: {resumo['faixas']}; score médio: {resumo['score_medio']}; território: {resumo['territorio']}; prioridades: {len(res['prioridades'])}")
    return resumo
