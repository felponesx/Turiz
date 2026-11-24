"""Motor da Cobertura Geográfica: função pura (dados → resultados). Não lê nem grava arquivos, não toca em lugares.json."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import geo
from .categorias import categorias_de_experiencia, categorias_do_lugar
from .metricas import (PESO_STATUS, ROTULO_FAIXA, diversidade, faixa, idade_dias, meta_densidade, percentil, prioridade, score_cobertura, scanners_recomendados)

PRIOR_PESOS = ("lacuna", "ausentes", "quantidade", "confiabilidade", "potencial", "tempo")


def associar(lugares, distritos, cfg) -> dict:
    """id do lugar -> localização territorial. Um erro num registro não derruba os demais."""
    out, erros = {}, []
    for l in lugares:
        try:
            out[l["id"]] = geo.localizar(distritos, l, cfg["margem_fronteira_m"])
        except Exception as e:      # registro malformado: fica 'unknown' e é contado
            out[l["id"]] = {"distrito": None, "status": geo.UNKNOWN, "precisao": "nenhuma", "origem": "erro", "bairro": None, "bairro_declarado": None}
            erros.append((l.get("id"), type(e).__name__))
    out["_erros"] = erros
    return out


def calcular(lugares, territorio, revisao, eventos, geo_dados, cfg, agora=None, buscas=()) -> dict:
    agora = agora or datetime.now(timezone.utc)
    distritos = geo_dados["distritos"]
    defs = cfg["categorias"]
    exp_cats = categorias_de_experiencia(defs)
    rev = {r["id"]: r for r in revisao}
    por_d = defaultdict(list)
    for l in lugares:
        t = territorio.get(l["id"])
        if t and t["distrito"]:
            por_d[t["distrito"]].append(l)
    ultima_busca, ultima_busca_cat = {}, {}
    for b in buscas:
        if b.get("status") == "concluida" and b.get("search_started_at"):
            k = b["neighborhood_id"]
            ultima_busca[k] = max(ultima_busca.get(k, ""), b["search_started_at"])
            ultima_busca_cat[(k, b["category"])] = max(ultima_busca_cat.get((k, b["category"]), ""), b["search_started_at"])
    cats_do = {l["id"]: categorias_do_lugar(l, defs) for l in lugares}
    # eventos gastronômicos por distrito (só os que têm coordenada)
    ev_d = Counter()
    for e in eventos or []:
        if isinstance(e.get("lat"), (int, float)) and isinstance(e.get("lon"), (int, float)):
            d = next((d for d in distritos if geo.contem(d, e["lon"], e["lat"])), None)
            if d:
                ev_d[d["codigo"]] += 1
    cidade = Counter(c for l in lugares for c in cats_do[l["id"]])
    if ev_d:
        cidade["eventos"] = sum(ev_d.values())
    minimo = cfg["potencial_categorias_ausentes_min_cidade"]
    cats_cidade = [c for c, n in cidade.items() if n >= minimo]
    area_max = cfg["densidade"]["area_max_km2"]
    base = {}
    for d in distritos:
        ls = por_d.get(d["codigo"], [])
        area = max(0.5, min(d.get("area_km2") or 1, area_max))
        base[d["codigo"]] = {"ls": ls, "area": area, "dens": len(ls) / area}
    meta = meta_densidade([b["dens"] for b in base.values() if len(b["ls"]) >= cfg["minimo_lugares_para_avaliar"]], cfg)
    todas_dens = [b["dens"] for b in base.values()]
    total_cidade = sum(len(b["ls"]) for b in base.values()) or 1
    metricas, categorias_linhas = [], []
    for d in distritos:
        cod, b = d["codigo"], base[d["codigo"]]
        ls, n = b["ls"], len(b["ls"])
        cont = Counter(c for l in ls for c in cats_do[l["id"]])
        if ev_d.get(cod):
            cont["eventos"] = ev_d[cod]
        st = Counter(territorio[l["id"]]["status"] for l in ls)
        scores = [rev[l["id"]]["s"] for l in ls if l["id"] in rev]
        conf = (sum(scores) / len(scores)) if scores else 0.0
        faixas = Counter(rev[l["id"]]["faixa"] for l in ls if l["id"] in rev)
        pub = sum(1 for l in ls if rev.get(l["id"], {}).get("p"))
        ate = lambda l: idade_dias(l.get("atualizado_em"), agora)
        fresco = sum((1.0 if (ate(l) is not None and ate(l) <= cfg["atualidade_dias"]["otima"]) else 0.5 if (ate(l) is not None and ate(l) <= cfg["atualidade_dias"]["aceitavel"]) else 0.1) for l in ls)
        ultima = max((l.get("atualizado_em") or "" for l in ls), default="") or None
        gen = set(cfg["diversidade"]["genericas"])
        espec = sum(1 for l in ls if set(cats_do[l["id"]]) - gen)
        div, riqueza, even, hhi, top = diversidade(Counter({c: v for c, v in cont.items() if c in cidade}), len(cats_cidade), cfg, n, espec)
        minimo_pres = cfg["diversidade"]["presenca_minima"]
        presentes_exp = sum(1 for c in exp_cats | {"eventos"} if cont.get(c, 0) >= (1 if c == "eventos" else minimo_pres))
        comp = {
            "densidade": min(1.0, __import__("math").log1p(b["dens"]) / __import__("math").log1p(meta)),
            "diversidade": div / 100,
            "confiabilidade": conf / 100,
            "precisao": (sum(PESO_STATUS[s] * v for s, v in st.items()) / n) if n else 0.0,
            "experiencias": min(1.0, presentes_exp / cfg["experiencias_alvo"]),
            "atualidade": (fresco / n) if n else 0.0,
        }
        avaliavel = n >= cfg["minimo_lugares_para_avaliar"]
        cov = score_cobertura(comp, cfg) if avaliavel else None
        status = faixa(cov, cfg) if avaliavel else "desconhecida"
        ausentes = [c for c in cats_cidade if cont.get(c, 0) < minimo_pres]
        esperado_total = max(1.0, meta * b["area"])
        m = {"id": cod, "neighborhood_id": cod, "total_places": n, "publishable_places": pub, "review_places": n - faixas["alta"] - faixas["confiavel"] if scores else 0,
             "low_confidence_places": faixas["baixa_confianca"] + faixas["nao_confirmado"], "approximate_location_places": st["approximate"] + st["boundary_conflict"],
             "unconfirmed_neighborhood_places": n, "territorial_status": dict(st), "category_count": len([c for c, v in cont.items() if v >= minimo_pres and c in cidade]), "specific_share": round(espec / n, 3) if n else 0.0,
             "diversity_score": div, "evenness": even, "concentration_index": hhi, "dominant_category": top,
             "quality_score": round(100 * (0.5 * comp["confiabilidade"] + 0.5 * comp["precisao"])), "location_score": round(100 * comp["precisao"]),
             "coverage_score": cov, "coverage_status": status, "componentes": {k: round(v, 3) for k, v in comp.items()},
             "density_per_km2": round(b["dens"], 2), "expected_places": round(esperado_total), "ausentes": len(ausentes), "missing_categories": sorted(ausentes),
             "confiabilidade_media": round(conf, 1), "last_data_update": ultima, "last_search_at": ultima_busca.get(cod), "status": status, "faixas_fase4": dict(faixas)}
        metricas.append(m)
        for c in cats_cidade:
            ls_c = [l for l in ls if c in cats_do[l["id"]]]
            nc = cont.get(c, 0)
            esp_c = max(1.0, cidade[c] / total_cidade * esperado_total)
            sc = [rev[l["id"]]["s"] for l in ls_c if l["id"] in rev]
            categorias_linhas.append({"id": f"{cod}:{c}", "neighborhood_id": cod, "category": c, "place_count": nc,
                                      "reliable_count": sum(1 for s in sc if s >= 75), "publishable_count": sum(1 for l in ls_c if rev.get(l["id"], {}).get("p")),
                                      "expected_count": round(esp_c, 1), "category_coverage_score": round(100 * min(1.0, nc / esp_c)),
                                      "mean_confidence": round(sum(sc) / len(sc), 1) if sc else None, "last_searched_at": ultima_busca_cat.get((cod, c))})
    dens_rank = [m["density_per_km2"] for m in metricas]
    prios = _prioridades(metricas, categorias_linhas, base, cfg, dens_rank, agora, distritos)
    return {"metricas": metricas, "categorias": categorias_linhas, "prioridades": prios, "meta_densidade": round(meta, 2), "categorias_cidade": dict(cidade), "cats_cidade": cats_cidade}


def _prioridades(metricas, cat_linhas, base, cfg, dens_rank, agora, distritos):
    dnome = {d["codigo"]: d for d in distritos}
    linhas = []
    for m in metricas:
        d = dnome[m["id"]]
        cov = m["coverage_score"]
        dias = idade_dias(m["last_data_update"], agora)
        dias_busca = idade_dias(m["last_search_at"], agora)       # tempo desde a última PESQUISA por distrito (nunca pesquisado = 100%)
        intervalo = cfg["intervalos_dias"][m["status"]]
        tempo = 1.0 if dias_busca is None else min(1.0, dias_busca / (3 * intervalo))
        esperado = max(1, m["expected_places"])
        n_cidade = max(1, len(set(m["missing_categories"])) + m["category_count"])
        comp = {"lacuna": 1.0 if cov is None else 1 - cov / 100, "ausentes": m["ausentes"] / n_cidade,
                "quantidade": 1 - min(1.0, m["total_places"] / esperado), "confiabilidade": 1 - m["confiabilidade_media"] / 100 if m["total_places"] else 1.0,
                "potencial": percentil(m["density_per_km2"], dens_rank), "tempo": tempo}
        sc = prioridade(comp, cfg)
        sc_rec = scanners_recomendados(m, cfg)
        motivo = _motivo(m, dias, d)
        linhas.append({"id": f"{m['id']}:*", "neighborhood_id": m["id"], "category": None, "priority_score": sc, "priority_reason": motivo, "recommended_scanners": sc_rec,
                       "objective": _objetivo(m), "current_places": m["total_places"], "review_places": m["review_places"], "last_data_update": m["last_data_update"],
                       "componentes": {k: round(v, 3) for k, v in comp.items()}, "status": "recomendada"})
        for c in [x for x in cat_linhas if x["neighborhood_id"] == m["id"] and x["place_count"] < x["expected_count"] and m["coverage_score"] is not None]:
            ausente = c["place_count"] == 0
            cc = {"lacuna": comp["lacuna"], "ausentes": 1.0 if ausente else 0.0, "quantidade": 1 - min(1.0, c["place_count"] / c["expected_count"]),
                  "confiabilidade": 1 - (c["mean_confidence"] or 0) / 100 if c["mean_confidence"] is not None else 1.0, "potencial": comp["potencial"], "tempo": tempo}
            pc = prioridade(cc, cfg)
            ids = ["web", "instagram"] + (["geo"] if ausente else [])
            linhas.append({"id": c["id"], "neighborhood_id": m["id"], "category": c["category"], "priority_score": pc,
                           "priority_reason": f"{'Nenhum lugar' if ausente else str(c['place_count']) + ' de cerca de ' + str(round(c['expected_count'])) + ' esperados'} em {cfg['categorias'].get(c['category'], {}).get('rotulo', c['category'])} no distrito {d['nome']}",
                           "recommended_scanners": [{"id": i, "nome": cfg["scanners"][i]["nome"], "disponivel": cfg["scanners"][i]["disponivel"]} for i in ids],
                           "objective": "descoberta de novos estabelecimentos desta categoria", "current_places": c["place_count"], "review_places": 0,
                           "last_data_update": m["last_data_update"], "componentes": {k: round(v, 3) for k, v in cc.items()}, "status": "recomendada"})
    linhas.sort(key=lambda x: (-x["priority_score"], x["id"]))
    dist = [x for x in linhas if x["category"] is None]
    cats = [x for x in linhas if x["category"] is not None][:400]
    return sorted(dist + cats, key=lambda x: (-x["priority_score"], x["id"]))


def _motivo(m, dias, d):
    partes = [ROTULO_FAIXA[m["status"]]]
    if m["status"] == "desconhecida":
        partes = [f"Poucos dados ({m['total_places']} lugares): falta informação, não é ausência de gastronomia"]
    if m["ausentes"]:
        partes.append(f"{m['ausentes']} categorias ausentes")
    if m["total_places"] and m["location_score"] < 50:
        partes.append("localização pouco precisa")
    if m["total_places"] and m["confiabilidade_media"] < 70:
        partes.append("confiabilidade média baixa")
    partes.append("dados nunca atualizados" if dias is None else f"dados atualizados há {dias} dias")
    partes.append("distrito ainda não pesquisado" if not m["last_search_at"] else "última pesquisa em " + m["last_search_at"][:10])
    return ", ".join(partes)


def _objetivo(m):
    if m["status"] in ("critica", "desconhecida"):
        return "descoberta inicial de estabelecimentos"
    if m["status"] == "baixa":
        return "ampliar fontes e descobrir estabelecimentos novos"
    if m["ausentes"]:
        return "pesquisa direcionada às categorias ausentes"
    return "atualizar e validar o que já existe"
