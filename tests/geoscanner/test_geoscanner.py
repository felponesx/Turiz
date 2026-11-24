import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from cobertura import execucao, rodar
from cobertura.categorias import config
from geoscanner import scanner


def quadrado(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def mundo():
    ds = [{"codigo": "1", "nome_oficial": "ALFA", "nome": "Alfa", "nome_norm": "alfa", "zona": "Centro", "subprefeitura": "SUB A", "area_km2": 4.0, "poligonos": [quadrado(-46.70, -23.60, -46.60, -23.50)]},
          {"codigo": "2", "nome_oficial": "BETA", "nome": "Beta", "nome_norm": "beta", "zona": "Leste", "subprefeitura": "SUB B", "area_km2": 4.0, "poligonos": [quadrado(-46.60, -23.60, -46.50, -23.50)]}]
    for d in ds:
        xs = [p[0] for p in d["poligonos"][0][0]]; ys = [p[1] for p in d["poligonos"][0][0]]
        d["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return {"fonte": "teste", "baixado_em": "2026-01-01T00:00:00+00:00", "distritos": ds}


def L(i, nome="Casa", lat=-23.55, lon=-46.65, **kw):
    return {"id": i, "fonte": "osm", "fonte_id": f"n/{i}", "tipo": "restaurante", "nome": nome, "culinaria": "", "lat": lat, "lon": lon, "endereco": "Rua A, 1", "bairro": "", "cep": "01000-000",
            "telefone": "", "site": "", "extra": {}, "atualizado_em": "2026-11-20T00:00:00", **kw}


def R(i, s=80, p=True):
    return {"id": i, "s": s, "faixa": "confiavel" if s >= 75 else "necessita_revisao", "p": p}

CFG = config()
AGORA = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)


def el(i, nome, lat, lon, **tags):
    return {"type": "node", "id": i, "lat": lat, "lon": lon, "tags": {"name": nome, **tags}}


def montar(tmp_path, extra_lugares=()):
    d = tmp_path / "data"; (d / "geo").mkdir(parents=True)
    g = mundo()
    with gzip.open(d / "geo" / "distritos_sp.json.gz", "wt", encoding="utf-8") as f:
        json.dump({**g, "distritos": [{k: v for k, v in x.items() if k not in ("nome", "nome_norm", "bbox")} for x in g["distritos"]]}, f)
    ls = [L(i, f"Restaurante {i}", lat=-23.55 + (i % 9) * 0.004, lon=-46.65 + (i % 7) * 0.004) for i in range(1, 40)] + [L(500, "Cafe Existente", lat=-23.56, lon=-46.66, fonte_id="node/777")] + list(extra_lugares)
    (d / "lugares.json").write_text(json.dumps(ls), encoding="utf-8")
    (d / "eventos.json").write_text("[]")
    with gzip.open(d / "revisao.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"lugares": [R(l["id"]) for l in ls]}, f)
    rodar.rodar(dados=str(d), agora=AGORA)
    linhas = [{"id": f"{c}:{k}", "neighborhood_id": c, "category": k, "priority_score": sc, "priority_reason": "teste", "recommended_scanners": [], "objective": "", "current_places": 0, "review_places": 0, "last_data_update": None, "componentes": {}, "status": "recomendada"}
              for c, k, sc in (("1", "padaria", 90), ("1", "doceria", 85), ("1", "cafeteria", 80), ("2", "coreana", 70))]
    execucao.gravar(str(d), "coverage_priorities", {"prioridades": linhas})        # fila conhecida para o teste
    return d


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def post_ok(elementos):
    return lambda q: {"elements": elementos}


def rodar_geo(d, post, **kw):
    return scanner.executar(str(d), CFG, post, agora=kw.pop("agora", AGORA), dormir=lambda s: None, **kw)


def test_consulta_overpass_formatada():
    q = scanner.consulta((-23.6, -46.7, -23.5, -46.6), ['["shop"="bakery"]', '["amenity"="cafe"]'])
    assert q.startswith("[out:json]") and 'nwr["shop"="bakery"](-23.60000,-46.70000,-23.50000,-46.60000);' in q and q.endswith("out center tags;")


def test_classificacao_existente_duplicado_novo_possivel_e_fora_do_distrito(tmp_path):
    d = montar(tmp_path)
    geo_ = __import__("cobertura.geo", fromlist=["x"]).carregar(str(d / "geo/distritos_sp.json.gz"))["distritos"][0]
    lugares = json.loads((d / "lugares.json").read_text())
    existentes = {l["fonte_id"]: l["id"] for l in lugares}
    celulas = scanner.indice_lugares(lugares)
    escanner = scanner
    escanner._DEFS.update(CFG["categorias"])
    base = lugares[0]
    els = [el(1, "Padaria Nova", -23.52, -46.62, shop="bakery"),                            # novo
           el(777, "Cafe Existente", -23.56, -46.66, amenity="cafe"),                       # mesmo id OSM já cadastrado
           el(2, base["nome"], base["lat"] + 0.00001, base["lon"], amenity="restaurant"),   # mesmo nome no mesmo ponto: duplicado
           el(3, "Padaria Longe", -22.0, -43.0, shop="bakery"),                             # fora do distrito
           {"type": "node", "id": 4, "lat": -23.52, "lon": -46.63, "tags": {"shop": "bakery"}},   # sem nome
           el(5, "Casa de Pao Mineira", -23.5201, -46.6201, shop="bakery")]                 # perto do "novo" mas nome diferente: novo também
    cont, ach = scanner.processar_resposta(els, geo_, "padaria", existentes, celulas, set(), AGORA.isoformat(), "t")
    assert cont["existentes"] == 1 and cont["duplicados"] == 1 and cont["fora_do_distrito"] == 1 and cont["sem_nome"] == 1
    assert {a["nome"] for a in ach} == {"Padaria Nova", "Casa de Pao Mineira"}
    a = next(x for x in ach if x["nome"] == "Padaria Nova")
    assert a["status"] == "novo" and a["publicavel"] is False and "padaria" in a["categorias"] and a["osm_tag"] == "shop=bakery" and a["distrito"] == "1" and "email" not in json.dumps(a).lower()


def test_selecao_por_prioridade_ignora_categorias_sem_filtro_e_buscas_recentes():
    prios = [{"id": "1:restaurante", "neighborhood_id": "1", "category": "restaurante", "priority_score": 99}, {"id": "1:padaria", "neighborhood_id": "1", "category": "padaria", "priority_score": 80},
             {"id": "1:*", "neighborhood_id": "1", "category": None, "priority_score": 95}, {"id": "2:coreana", "neighborhood_id": "2", "category": "coreana", "priority_score": 70}]
    mets = [{"id": "1", "status": "moderada"}, {"id": "2", "status": "boa"}]
    f = CFG["geo_scanner"]["filtros"]
    t = scanner.escolher_tarefas(prios, mets, [], CFG, AGORA, 5, f)
    assert [(x["distrito"], x["categoria"]) for x in t] == [("1", "padaria"), ("2", "coreana")]            # 'restaurante' não tem filtro; linha de distrito não é busca
    recente = [{"neighborhood_id": "1", "category": "padaria", "search_started_at": (AGORA - timedelta(days=2)).isoformat(), "status": "concluida", "new_places": 3}]
    assert [x["categoria"] for x in scanner.escolher_tarefas(prios, mets, recente, CFG, AGORA, 5, f)] == ["coreana"]
    antiga = [{**recente[0], "search_started_at": (AGORA - timedelta(days=20)).isoformat()}]
    assert len(scanner.escolher_tarefas(prios, mets, antiga, CFG, AGORA, 5, f)) == 2                      # moderada = 14 dias, já passou
    assert len(scanner.escolher_tarefas(prios, mets, recente, CFG, AGORA, 5, f, distrito="1", categoria="padaria", forcar=True)) == 1   # manual: só espera a hora mínima
    assert len(scanner.escolher_tarefas(prios, mets, [], CFG, AGORA, 1, f)) == 1                          # limite de tarefas


def test_intervalo_adaptativo_dobra_quando_busca_nao_acha_nada():
    prios = [{"id": "1:padaria", "neighborhood_id": "1", "category": "padaria", "priority_score": 80}]
    mets = [{"id": "1", "status": "moderada"}]
    f = CFG["geo_scanner"]["filtros"]
    vazias = [{"neighborhood_id": "1", "category": "padaria", "status": "concluida", "new_places": 0, "search_started_at": (AGORA - timedelta(days=30 + i)).isoformat()} for i in range(2)]
    assert scanner.escolher_tarefas(prios, mets, vazias, CFG, AGORA, 5, f) == []                          # 2 vazias → intervalo 14×4 = 56 dias; faz 30 dias: não repete
    assert len(scanner.escolher_tarefas(prios, mets, [{**vazias[0], "new_places": 2}], CFG, AGORA, 5, f)) == 1  # achou algo: volta ao intervalo normal


def test_execucao_completa_historico_idempotencia_e_lugares_intactos(tmp_path):
    d = montar(tmp_path)
    antes = {n: sha(d / n) for n in ("lugares.json", "revisao.json.gz", "eventos.json")}
    resp = [el(10, "Padaria Do Bairro", -23.52, -46.62, shop="bakery"), el(11, "Padaria Alfa", -23.53, -46.63, shop="bakery")]
    r = rodar_geo(d, post_ok(resp), max_tarefas=1, distrito="1", categoria="padaria")
    assert r["feitas"] == 1 and r["novos"] == 2 and r["descobertas_total"] == 2
    assert {n: sha(d / n) for n in antes} == antes                                                    # lugares, revisão da Fase 4 e eventos intactos
    h = execucao.ler(str(d), "coverage_history")
    b = h["buscas"][0]
    assert b["scanner"] == "geo" and b["neighborhood_id"] == "1" and b["category"] == "padaria" and b["status"] == "concluida" and b["new_places"] == 2 and b["results_found"] == 2
    desc1 = execucao.ler(str(d), "descobertas")["descobertas"]
    r2 = rodar_geo(d, post_ok(resp), max_tarefas=1, distrito="1", categoria="padaria", forcar=True, agora=AGORA + timedelta(hours=3))
    desc2 = execucao.ler(str(d), "descobertas")["descobertas"]
    assert len(desc2) == 2 and r2["descobertas_criadas"] == 0                                          # mesma descoberta não duplica
    assert [x["descoberto_em"] for x in desc2] == [x["descoberto_em"] for x in desc1] and desc2[0]["visto_em"] != desc1[0]["visto_em"]
    # a cobertura passa a saber que o distrito foi pesquisado
    res = rodar.rodar(dados=str(d), agora=AGORA + timedelta(hours=4))
    assert res["distritos_pesquisados"] == 1 and res["descobertas"]["total"] == 2 and res["buscas"]["total"] == 2
    m = next(x for x in execucao.ler(str(d), "coverage_metrics")["metricas"] if x["id"] == "1")
    assert m["last_search_at"] is not None


def test_falha_do_overpass_e_registrada_sem_derrubar_e_para_apos_falhas_seguidas(tmp_path):
    d = montar(tmp_path)
    chamadas = []

    def post(q):
        chamadas.append(q)
        if len(chamadas) == 1:
            raise RuntimeError("Overpass indisponível: 504")
        return {"elements": [el(20, "Padaria Z", -23.52, -46.62, shop="bakery")]}
    r = rodar_geo(d, post, max_tarefas=3)
    assert r["falhas"] == 1 and r["feitas"] == 2 and r["novos"] >= 1                                      # uma falha não impede as outras
    h = execucao.ler(str(d), "coverage_history")["buscas"]
    assert sorted(b["status"] for b in h)[:1] == ["concluida"] and any(b["status"] == "falhou" and "504" in b["error"] for b in h)
    d2 = montar(tmp_path / "x")
    def sempre_falha(q):
        raise RuntimeError("fora do ar")
    r2 = rodar_geo(d2, sempre_falha, max_tarefas=6)
    assert r2["falhas"] == CFG["geo_scanner"]["max_falhas_seguidas"] and r2["feitas"] == 0               # não fica insistindo


def test_entradas_invalidas_sao_recusadas(tmp_path):
    d = montar(tmp_path)
    for kw in ({"distrito": "1;rm -rf"}, {"distrito": "abc"}, {"categoria": "x y"}, {"categoria": "restaurante"}, {"categoria": "../etc"}):
        with pytest.raises(ValueError):
            rodar_geo(d, post_ok([]), **kw)


def test_sem_fila_de_prioridades_pede_para_rodar_a_cobertura(tmp_path):
    d = montar(tmp_path)
    (d / "coverage_priorities.json.gz").unlink()
    with pytest.raises(RuntimeError, match="cobertura"):
        rodar_geo(d, post_ok([]))


def test_descobertas_nunca_entram_em_lugares_nem_sao_publicaveis(tmp_path):
    d = montar(tmp_path)
    rodar_geo(d, post_ok([el(30, "Doceria X", -23.52, -46.62, shop="pastry")]), max_tarefas=1, distrito="1", categoria="doceria")
    assert all(x["publicavel"] is False for x in execucao.ler(str(d), "descobertas")["descobertas"])
    src = open(scanner.__file__, encoding="utf-8").read()
    assert "lugares.json" in src and 'gravar(dados, "lugares"' not in src


def test_workflow_e_registro_do_geo_scanner():
    from bots import registry
    b = registry.por_id("geo_scanner")
    assert b["workflow"] == "geo-scanner.yml" and set(b["parametros_entrada"]) == {"distrito", "categoria", "max_tarefas"}
    wf = open(".github/workflows/geo-scanner.yml", encoding="utf-8").read()
    assert "gh workflow" not in wf and "actions: write" not in wf and "${{ inputs.distrito }}" in wf and "run: python coletar_geo.py" not in wf   # entradas passam por env, nunca interpoladas no shell


def test_alvo_manual_usa_toda_lacuna_do_distrito_mesmo_fora_das_400_maiores(tmp_path):
    d = montar(tmp_path)
    execucao.gravar(str(d), "coverage_priorities", {"prioridades": [{"id": "9:*", "neighborhood_id": "9", "category": None, "priority_score": 50}]})   # fila sem linhas do distrito 1
    cats = [{"id": "1:padaria", "neighborhood_id": "1", "category": "padaria", "place_count": 0, "expected_count": 5.0}, {"id": "1:doceria", "neighborhood_id": "1", "category": "doceria", "place_count": 1, "expected_count": 5.0},
            {"id": "1:bar", "neighborhood_id": "1", "category": "bar", "place_count": 9, "expected_count": 5.0}]
    execucao.gravar(str(d), "coverage_categories", {"categorias_cidade": {}, "categorias": cats})
    r = rodar_geo(d, post_ok([]), distrito="1", max_tarefas=2)
    assert r["tarefas"] == 2 and r["feitas"] == 2
    assert rodar_geo(d, post_ok([]), max_tarefas=2)["tarefas"] == 0                       # sem alvo manual, a fila pública vazia não gera busca
