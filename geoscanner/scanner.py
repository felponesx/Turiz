"""Núcleo do Geo Scanner. Funções puras + uma função `executar` com `post` injetável (testável sem rede)."""
import gzip
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.sources import osm
from cobertura import execucao, geo
from cobertura.categorias import categorias_do_lugar
from revisao import dedup

ID_DISTRITO = re.compile(r"^\d{1,3}$")
ID_CATEGORIA = re.compile(r"^[a-z_]{1,40}$")
CELULA = dedup.CELULA


def consulta(bbox, filtros, timeout=120) -> str:
    s, w, n, e = bbox
    corpo = "".join(f"nwr{f}({s:.5f},{w:.5f},{n:.5f},{e:.5f});" for f in filtros)
    return f"[out:json][timeout:{timeout}];({corpo});out center tags;"


def bbox_distrito(d, folga=0.0005):
    x0, y0, x1, y1 = d["bbox"]
    return (y0 - folga, x0 - folga, y1 + folga, x1 + folga)       # sul, oeste, norte, leste


def indice_lugares(lugares):
    celulas = defaultdict(list)
    for l in lugares:
        if isinstance(l.get("lat"), (int, float)) and isinstance(l.get("lon"), (int, float)):
            celulas[(round(l["lat"] / CELULA), round(l["lon"] / CELULA))].append(l)
    return celulas


def vizinhos(celulas, lat, lon):
    cx, cy = round(lat / CELULA), round(lon / CELULA)
    return [l for dx in (-1, 0, 1) for dy in (-1, 0, 1) for l in celulas.get((cx + dx, cy + dy), ())]


def classificar(cand, existentes_ids, celulas, rede):
    """-> (status, relacionado_a). 'existente' e 'duplicado' não viram descoberta; 'novo' e 'possivel_duplicado' viram."""
    if cand["fonte_id"] in existentes_ids:
        return "existente", existentes_ids[cand["fonte_id"]]
    pior = None
    for l in vizinhos(celulas, cand["lat"], cand["lon"]):
        r = dedup.comparar(cand, l, rede)
        if not r:
            continue
        if r[0] == dedup.CONFIRMADO:
            return "duplicado", l["id"]
        if r[0] == dedup.POSSIVEL and pior is None:
            pior = l["id"]
    return ("possivel_duplicado", pior) if pior is not None else ("novo", None)


def escolher_tarefas(prioridades, metricas, buscas, cfg, agora, max_tarefas, filtros, forcar=False, distrito=None, categoria=None):
    """Seleciona (distrito, categoria) por prioridade, pulando buscas recentes. Intervalo adaptativo: dobra a cada busca sem novidades."""
    gs = cfg["geo_scanner"]
    status = {m["id"]: m["status"] for m in metricas}
    por_par = defaultdict(list)
    for b in buscas:
        if b.get("status") == "concluida":
            por_par[(b["neighborhood_id"], b["category"])].append(b)
    out = []
    for p in sorted(prioridades, key=lambda x: (-x["priority_score"], x["id"])):
        cat, cod = p["category"], p["neighborhood_id"]
        if not cat or cat not in filtros or (distrito and cod != distrito) or (categoria and cat != categoria):
            continue
        hist = sorted(por_par.get((cod, cat), []), key=lambda b: b["search_started_at"])
        if hist:
            ultima = datetime.fromisoformat(hist[-1]["search_started_at"])
            if ultima.tzinfo is None:
                ultima = ultima.replace(tzinfo=timezone.utc)
            vazias = 0
            for b in reversed(hist):
                if b.get("new_places", 0) == 0:
                    vazias += 1
                else:
                    break
            base = cfg["intervalos_dias"].get(status.get(cod, "desconhecida"), 7)
            espera = timedelta(days=base * 2 ** min(vazias, gs["backoff_sem_novidade_max"]))
            if forcar:
                espera = timedelta(hours=gs["minimo_horas_entre_buscas"])
            if agora - ultima < espera:
                continue
        out.append({"distrito": cod, "categoria": cat, "prioridade": p["priority_score"]})
        if len(out) >= max_tarefas:
            break
    return out


def processar_resposta(elementos, d, cat, lugares_ids, celulas, rede, agora_iso, termo):
    """Converte elementos do Overpass em candidatos classificados. Descarta o que cai fora do polígono oficial do distrito."""
    cont = {"encontrados": 0, "fora_do_distrito": 0, "existentes": 0, "duplicados": 0, "novos": 0, "possiveis": 0, "sem_nome": 0}
    achados = []
    for el in elementos:
        r = osm.normalizar(el)
        if not r:
            cont["sem_nome"] += 1
            continue
        if not isinstance(r["lat"], (int, float)) or not isinstance(r["lon"], (int, float)) or not geo.contem(d, r["lon"], r["lat"]):
            cont["fora_do_distrito"] += 1
            continue
        cont["encontrados"] += 1
        status, rel = classificar(r, lugares_ids, celulas, rede)
        if status == "existente":
            cont["existentes"] += 1
        elif status == "duplicado":
            cont["duplicados"] += 1
        else:
            cont["novos" if status == "novo" else "possiveis"] += 1
            tag = next((f"{k}={el['tags'][k]}" for k in ("shop", "amenity", "craft", "microbrewery") if k in el.get("tags", {})), "")
            achados.append({"id": f"osm:{r['fonte_id']}", "fonte": "osm", "fonte_id": r["fonte_id"], "nome": r["nome"], "tipo": r["tipo"], "culinaria": r["culinaria"], "lat": r["lat"], "lon": r["lon"],
                            "endereco": r["endereco"], "bairro_declarado": r["bairro"] or None, "cep": r["cep"], "telefone": r["telefone"], "site": r["site"], "horario": r["horario"], "extra": r["extra"],
                            "osm_tag": tag, "distrito": d["codigo"], "zona": d["zona"], "categoria_buscada": cat, "categorias": sorted(set(categorias_do_lugar(r, _DEFS) + [cat])),
                            "status": status, "relacionado_a": rel, "bot": "geo_scanner", "termo": termo, "descoberto_em": agora_iso, "visto_em": agora_iso,
                            "publicavel": False, "motivo_nao_publicavel": "aguardando validação do Revisor"})
    return cont, achados


_DEFS = {}


def mesclar(descobertas, novos):
    """Idempotente: mesmo id só atualiza visto_em; descoberto_em e status já definidos (inclusive decisões futuras) são preservados."""
    por_id = {x["id"]: x for x in descobertas}
    criados = 0
    for n in novos:
        if n["id"] in por_id:
            por_id[n["id"]]["visto_em"] = n["visto_em"]
        else:
            por_id[n["id"]] = n
            criados += 1
    return sorted(por_id.values(), key=lambda x: x["id"]), criados


def executar(dados, cfg, post, agora=None, max_tarefas=None, distrito=None, categoria=None, forcar=False, rep=None, dormir=time.sleep, relogio=time.monotonic, max_minutos=60):
    """Roda as buscas selecionadas. Retorna dicionário-resumo. Nunca altera lugares.json."""
    agora = agora or datetime.now(timezone.utc)
    gs = cfg["geo_scanner"]
    _DEFS.clear(); _DEFS.update(cfg["categorias"])
    filtros = gs["filtros"]
    if distrito and not ID_DISTRITO.match(distrito):
        raise ValueError("distrito inválido")
    if categoria and (not ID_CATEGORIA.match(categoria) or categoria not in filtros):
        raise ValueError("categoria inválida ou sem filtro do OpenStreetMap")
    g = geo.carregar(f"{dados}/geo/distritos_sp.json.gz")
    dist = {d["codigo"]: d for d in g["distritos"]}
    lugares = execucao.ler(dados, "lugares", [])
    prios = (execucao.ler(dados, "coverage_priorities", {}) or {}).get("prioridades", [])
    mets = (execucao.ler(dados, "coverage_metrics", {}) or {}).get("metricas", [])
    if not prios:
        raise RuntimeError("Sem fila de prioridades: rode a cobertura geográfica antes.")
    if distrito or categoria:       # alvo manual: a fila pública guarda só as 400 maiores prioridades; aqui vale toda lacuna do distrito
        ja = {p["id"] for p in prios}
        for c in (execucao.ler(dados, "coverage_categories", {}) or {}).get("categorias", []):
            if c["id"] not in ja and c["place_count"] < c["expected_count"] and (not distrito or c["neighborhood_id"] == distrito) and (not categoria or c["category"] == categoria):
                prios.append({"id": c["id"], "neighborhood_id": c["neighborhood_id"], "category": c["category"], "priority_score": round(100 * (1 - c["place_count"] / c["expected_count"]))})
    hist = execucao.ler(dados, "coverage_history", {}) or {"snapshots": [], "buscas": []}
    descobertas = execucao.ler(dados, "descobertas", {}) or {"descobertas": []}
    tarefas = escolher_tarefas(prios, mets, hist.get("buscas", []), cfg, agora, max_tarefas or gs["max_tarefas"], filtros, forcar or bool(distrito or categoria), distrito, categoria)
    existentes = {l["fonte_id"]: l["id"] for l in lugares if l.get("fonte") == "osm"}
    celulas = indice_lugares(lugares)
    marcas = {}
    for l in lugares:
        marcas[dedup.nome_chave(l["nome"])] = marcas.get(dedup.nome_chave(l["nome"]), 0) + 1
    rede = {k for k, v in marcas.items() if v >= dedup.MIN_UNIDADES_FRANQUIA and k}
    # a cobertura usa a mesma regra de franquia; aqui basta o conjunto
    total = {"tarefas": len(tarefas), "feitas": 0, "falhas": 0, "encontrados": 0, "novos": 0, "possiveis": 0, "existentes": 0, "duplicados": 0, "fora_do_distrito": 0}
    novos_total, seguidas, inicio = [], 0, relogio()
    for i, t in enumerate(tarefas):
        if relogio() - inicio > max_minutos * 60:
            if rep:
                rep.aviso("tempo máximo atingido; o restante continua na próxima execução")
            break
        d, cat = dist[t["distrito"]], t["categoria"]
        rotulo = f"{d['nome']} · {cfg['categorias'].get(cat, {}).get('rotulo', cat)}"
        if rep:
            rep.progresso(i, len(tarefas), atual=rotulo)
        ini = datetime.now(timezone.utc) if agora is None else agora + timedelta(seconds=relogio() - inicio)
        termo = " | ".join(filtros[cat])
        busca = {"neighborhood_id": d["codigo"], "category": cat, "scanner": "geo", "source": "osm_overpass", "search_started_at": ini.isoformat(timespec="seconds")}
        try:
            resp = post(consulta(bbox_distrito(d), filtros[cat]))
            cont, achados = processar_resposta(resp.get("elements", []), d, cat, existentes, celulas, rede, ini.isoformat(timespec="seconds"), termo)
            fim = ini + timedelta(seconds=max(0, relogio() - inicio))
            execucao.registrar_busca(hist, **busca, search_completed_at=fim.isoformat(timespec="seconds"), results_found=cont["encontrados"], new_places=cont["novos"], duplicates=cont["duplicados"] + cont["existentes"],
                                     rejected=cont["fora_do_distrito"] + cont["sem_nome"], pending_review=cont["novos"] + cont["possiveis"], status="concluida", metadata={"possiveis_duplicados": cont["possiveis"], "existentes": cont["existentes"], "filtros": filtros[cat]})
            novos_total += achados
            seguidas = 0
            total["feitas"] += 1
            for k in ("encontrados", "novos", "possiveis", "existentes", "duplicados", "fora_do_distrito"):
                total[k] += cont[k]
            if rep:
                rep.contar(captados=cont["encontrados"], novos=cont["novos"], duplicados=cont["duplicados"] + cont["existentes"])
                for a in achados[:3]:
                    rep.item(f"Descoberta: {a['nome']} ({d['nome']})")
        except Exception as exc:  # noqa: BLE001 - uma busca ruim não derruba as outras; o erro vai para o histórico
            seguidas += 1
            total["falhas"] += 1
            execucao.registrar_busca(hist, **busca, status="falhou", error=str(exc)[:200])
            if rep:
                rep.aviso(f"{rotulo}: {str(exc)[:120]}")
            if seguidas >= gs["max_falhas_seguidas"]:
                if rep:
                    rep.aviso("Overpass sem resposta várias vezes seguidas; parando para não insistir")
                break
        dormir(gs["pausa_s"])
    lista, criados = mesclar(descobertas["descobertas"], novos_total)
    execucao.gravar(dados, "descobertas", {"descobertas": lista})
    execucao.gravar(dados, "coverage_history", {"snapshots": hist.get("snapshots", []), "buscas": hist["buscas"][-2000:]})
    total["descobertas_criadas"] = criados
    total["descobertas_total"] = len(lista)
    return total
