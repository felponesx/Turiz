import copy
import gzip
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone

import pytest

from cobertura import analise, execucao, geo, metricas
from cobertura.categorias import categorias_do_lugar, config
from cobertura.rodar import rodar

CFG = config()
AGORA = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)


def quadrado(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def mundo():
    """Dois distritos vizinhos (A à esquerda, B à direita) divididos em lon=-46.60."""
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


# ---------- configuração ----------
def test_pesos_somam_100_e_faixas_ordenadas():
    assert sum(CFG["pesos_cobertura"].values()) == 100 and sum(CFG["pesos_prioridade"].values()) == 100
    assert [c for c, _ in CFG["faixas"]] == sorted((c for c, _ in CFG["faixas"]), reverse=True)


def test_pesos_invalidos_sao_recusados(tmp_path, monkeypatch):
    import cobertura.rodar as r
    ruim = copy.deepcopy(CFG); ruim["pesos_cobertura"]["densidade"] = 50
    monkeypatch.setattr(r, "config", lambda c: ruim)
    with pytest.raises(ValueError, match="somar 100"):
        r.rodar(dados=str(tmp_path))


# ---------- geografia ----------
def test_ponto_preciso_no_meio_do_distrito_e_confirmado_e_bairro_fica_desconhecido():
    t = geo.localizar(mundo()["distritos"], L(1, lat=-23.55, lon=-46.65, bairro="Vila Inventada"), CFG["margem_fronteira_m"])
    assert t["distrito"] == "1" and t["status"] == geo.CONFIRMED and t["precisao"] == "precisa"
    assert t["bairro"] is None and t["bairro_declarado"] == "Vila Inventada"      # distrito não é bairro; nome do cadastro é só 'declarado'


def test_coordenada_aproximada_nunca_e_confirmed():
    t = geo.localizar(mundo()["distritos"], L(1, extra={"coordenada_aproximada": True}), CFG["margem_fronteira_m"])
    assert t["status"] == geo.APPROXIMATE and t["precisao"] == "aproximada"
    t2 = geo.localizar(mundo()["distritos"], L(1, bairro="Alfa", extra={"coordenada_aproximada": True}), CFG["margem_fronteira_m"])
    assert t2["status"] == geo.PROBABLE          # só com evidência extra (nome do bairro confere com o distrito)


def test_perto_da_divisa_e_boundary_conflict_e_nao_atribui_com_seguranca():
    perto = geo.localizar(mundo()["distritos"], L(1, lon=-46.60005), CFG["margem_fronteira_m"])      # ~5 m da divisa
    assert perto["status"] == geo.CONFLICT and perto["distrito"] == "1"
    longe = geo.localizar(mundo()["distritos"], L(2, lon=-46.605), CFG["margem_fronteira_m"])        # ~500 m
    assert longe["status"] == geo.CONFIRMED
    aprox = geo.localizar(mundo()["distritos"], L(3, lon=-46.6012, extra={"coordenada_aproximada": True}), CFG["margem_fronteira_m"])   # ~100 m: margem maior para aproximadas
    assert aprox["status"] == geo.CONFLICT


def test_sem_coordenada_ou_fora_de_sp_e_unknown():
    d = mundo()["distritos"]
    assert geo.localizar(d, L(1, lat=None), CFG["margem_fronteira_m"])["status"] == geo.UNKNOWN
    assert geo.localizar(d, L(2, lat=0, lon=0), CFG["margem_fronteira_m"])["status"] == geo.UNKNOWN
    f = geo.localizar(d, L(3, lat=-22.9, lon=-43.2), CFG["margem_fronteira_m"])
    assert f["status"] == geo.UNKNOWN and f["distrito"] is None and f["origem"] == "fora_dos_distritos_de_sp"


def test_distritos_reais_sao_96_com_zonas_oficiais():
    p = "data/geo/distritos_sp.json.gz"
    if not os.path.exists(p):
        pytest.skip("distritos oficiais ainda não baixados")
    g = geo.carregar(p)
    assert len(g["distritos"]) == 96 and Counter(d["zona"] for d in g["distritos"])["Centro"] == 8
    assert {d["zona"] for d in g["distritos"]} == {"Centro", "Norte", "Sul", "Leste", "Oeste"}
    sé = next(d for d in g["distritos"] if d["nome_oficial"] == "SE")
    assert geo.contem(sé, -46.6333, -23.5505)          # Praça da Sé está no distrito Sé


# ---------- categorias ----------
def test_categorias_multiplas_e_extensiveis():
    c = categorias_do_lugar(L(1, "Pizzaria e Chopperia Sol", tipo="bar", culinaria="pizza;burger"), CFG["categorias"])
    assert {"bar", "pizzaria", "hamburgueria"} <= set(c)
    defs = {**CFG["categorias"], "ramen_bar": {"rotulo": "Ramen bar", "nome": ["ramen"]}}
    assert "ramen_bar" in categorias_do_lugar(L(2, "Ramen do Zé"), defs)             # nova categoria sem mudar código
    assert categorias_do_lugar(L(3, "Casa", extra={"cnae": "5611203"}), CFG["categorias"]) == ["lanchonete"]


# ---------- score ----------
def _calc(lugares, rev=None, eventos=()):
    g = mundo()
    terr = analise.associar(lugares, g["distritos"], CFG)
    terr.pop("_erros")
    rev = rev if rev is not None else [R(l["id"]) for l in lugares]
    return analise.calcular(lugares, terr, rev, list(eventos), g, CFG, AGORA)


def variados(n, base=0, lon=-46.65):
    nomes = ["Pizzaria", "Sushi", "Padaria", "Churrascaria", "Cafe", "Hamburgueria", "Cantina", "Sorveteria", "Mercado Central", "Doceria", "Esfiha", "Tapioca"]
    return [L(base + i, f"{nomes[i % len(nomes)]} {i}", lat=-23.55 + (i % 9) * 0.004, lon=lon + (i % 7) * 0.004) for i in range(n)]


def test_scores_entre_0_e_100_e_reproduzivel():
    ls = variados(60) + variados(30, 1000, -46.55)
    r1, r2 = _calc(ls), _calc(ls)
    assert r1 == r2
    for m in r1["metricas"]:
        assert m["coverage_score"] is None or 0 <= m["coverage_score"] <= 100
        assert all(0 <= v <= 1 for v in m["componentes"].values())
    assert all(0 <= p["priority_score"] <= 100 for p in r1["prioridades"])


def test_pesos_aplicados_exatamente():
    comp = {"densidade": 1, "diversidade": 0, "confiabilidade": 0, "precisao": 0, "experiencias": 0, "atualidade": 0}
    assert metricas.score_cobertura(comp, CFG) == CFG["pesos_cobertura"]["densidade"]
    assert metricas.score_cobertura({k: 1 for k in comp}, CFG) == 100 and metricas.score_cobertura({}, CFG) == 0
    cfg2 = copy.deepcopy(CFG); cfg2["pesos_cobertura"].update({"densidade": 10, "diversidade": 35})
    assert metricas.score_cobertura({"diversidade": 1}, cfg2) == 35         # calibrar pesos não exige mexer no código
    assert metricas.prioridade({"lacuna": 1}, CFG) == CFG["pesos_prioridade"]["lacuna"]


def test_categorias_ausentes_reduzem_a_diversidade():
    var = Counter({f"c{i}": 5 for i in range(10)})
    pobre = Counter({"c0": 5, "c1": 5})
    a, b = metricas.diversidade(var, 12, CFG, 50, 40), metricas.diversidade(pobre, 12, CFG, 10, 8)
    assert a[0] > b[0] and b[1] == 2 and a[1] == 10


def test_concentracao_alta_numa_unica_categoria():
    conc = metricas.diversidade(Counter({"restaurante": 300, "hamburgueria": 100}), 20, CFG, 400, 100)
    esp = metricas.diversidade(Counter({f"c{i}": 25 for i in range(16)}), 20, CFG, 400, 400)
    assert conc[3] > esp[3] and esp[0] > conc[0]


def test_muitos_registros_nao_garantem_cobertura_alta():
    iguais = [L(i, f"Restaurante {i}", lat=-23.55 + (i % 30) * 0.0015, lon=-46.69 + (i // 30) * 0.002) for i in range(600)]    # 600 lugares, tudo igual e pouco confiável
    rev = [R(l["id"], 40, False) for l in iguais]
    bom = variados(60, 5000, -46.55)
    r = _calc(iguais + bom, rev + [R(l["id"], 85) for l in bom])
    a = next(m for m in r["metricas"] if m["id"] == "1"); b = next(m for m in r["metricas"] if m["id"] == "2")
    assert a["total_places"] == 600 and b["total_places"] == 60
    assert a["coverage_score"] < b["coverage_score"] or a["componentes"]["densidade"] <= 1 and a["diversity_score"] < b["diversity_score"]
    assert a["componentes"]["densidade"] * CFG["pesos_cobertura"]["densidade"] <= 20


def test_baixa_qualidade_e_localizacao_imprecisa_reduzem_a_cobertura():
    ls = variados(60)
    alto = _calc(ls, [R(l["id"], 90) for l in ls])["metricas"][0]
    baixo = _calc(ls, [R(l["id"], 30, False) for l in ls])["metricas"][0]
    assert baixo["coverage_score"] < alto["coverage_score"]
    aprox = [{**l, "extra": {"coordenada_aproximada": True}} for l in ls]
    assert _calc(aprox, [R(l["id"], 90) for l in ls])["metricas"][0]["coverage_score"] < alto["coverage_score"]


def test_distrito_com_poucos_dados_e_desconhecido_nao_critico():
    r = _calc(variados(2))
    m = next(x for x in r["metricas"] if x["id"] == "1")
    assert m["status"] == "desconhecida" and m["coverage_score"] is None
    assert "falta informação" in next(p for p in r["prioridades"] if p["neighborhood_id"] == "1" and p["category"] is None)["priority_reason"]


def test_prioridade_prefere_lacuna_e_aponta_scanner_sem_dispara_lo():
    ls = variados(80) + variados(6, 900, -46.55)
    r = _calc(ls)
    pri = {p["neighborhood_id"]: p for p in r["prioridades"] if p["category"] is None}
    assert pri["2"]["priority_score"] > pri["1"]["priority_score"]
    ids = [s["id"] for s in pri["2"]["recommended_scanners"]]
    assert "geo" in ids and all("disponivel" in s for s in pri["2"]["recommended_scanners"])
    assert len({p["id"] for p in r["prioridades"]}) == len(r["prioridades"])          # sem prioridades duplicadas


# ---------- execução, integridade, histórico ----------
def montar(tmp_path):
    d = tmp_path / "data"; (d / "geo").mkdir(parents=True)
    g = mundo()
    with gzip.open(d / "geo" / "distritos_sp.json.gz", "wt", encoding="utf-8") as f:
        json.dump({**g, "distritos": [{k: v for k, v in x.items() if k not in ("nome", "nome_norm", "bbox")} for x in g["distritos"]]}, f)
    ls = variados(40) + variados(20, 500, -46.55) + [L(900, lat=None), L(901, "Ruim", lat=0, lon=0)]
    (d / "lugares.json").write_text(json.dumps(ls), encoding="utf-8")
    (d / "eventos.json").write_text("[]")
    with gzip.open(d / "revisao.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"lugares": [R(l["id"]) for l in ls]}, f)
    return d


def sha(d, nomes):
    return {n: hashlib.sha256((d / n).read_bytes()).hexdigest() for n in nomes}


def test_integridade_idempotencia_e_historico(tmp_path):
    d = montar(tmp_path)
    protegidos = ["lugares.json", "revisao.json.gz", "eventos.json"]
    antes = sha(d, protegidos)
    r1 = rodar(dados=str(d), agora=AGORA)
    assert sha(d, protegidos) == antes                                # nada existente foi alterado (nem os scores da Fase 4)
    ls = json.loads((d / "lugares.json").read_text())
    assert len(ls) == 62 and [l["id"] for l in ls] == sorted(l["id"] for l in ls)
    arquivos = [f"coverage_{n}.json.gz" for n in ("neighborhoods", "metrics", "categories", "priorities", "history", "places")]
    s1 = sha(d, arquivos)
    r2 = rodar(dados=str(d), agora=AGORA)                              # reexecução no mesmo dia
    assert sha(d, arquivos) == s1 and r1["faixas"] == r2["faixas"]    # mesmos bytes: sem duplicar histórico nem prioridades
    h = execucao.ler(str(d), "coverage_history")
    assert len(h["snapshots"]) == 1
    rodar(dados=str(d), agora=datetime(2026, 11, 25, 12, tzinfo=timezone.utc))
    h = execucao.ler(str(d), "coverage_history")
    assert [s["snapshot_date"] for s in h["snapshots"]] == ["2026-11-24", "2026-11-25"]
    assert h["snapshots"][0]["distritos"] == json.loads(json.dumps(execucao.fazer_snapshot(analise.calcular(ls, {l["id"]: geo.localizar(geo.carregar(str(d / "geo/distritos_sp.json.gz"))["distritos"], l, CFG["margem_fronteira_m"]) for l in ls}, [R(l["id"]) for l in ls], [], geo.carregar(str(d / "geo/distritos_sp.json.gz")), CFG, AGORA), "2026-11-24")["distritos"]))
    pri = execucao.ler(str(d), "coverage_priorities")["prioridades"]
    assert len({p["id"] for p in pri}) == len(pri)
    places = execucao.ler(str(d), "coverage_places")["lugares"]
    assert len(places) == len(ls) and len({p["id"] for p in places}) == len(ls)       # nenhum lugar duplicado pela cobertura
    assert next(p for p in places if p["id"] == 900)["s"] == "unknown"


def test_gzip_nao_grava_timestamp(tmp_path):
    execucao.gravar(str(tmp_path), "x", {"a": 1})
    b = (tmp_path / "x.json.gz").read_bytes()
    assert b[4:8] == b"\x00\x00\x00\x00"                               # campo mtime do cabeçalho gzip = 0 (bug da Fase 4)
    import time; time.sleep(1.1)
    execucao.gravar(str(tmp_path), "x", {"a": 1})
    assert (tmp_path / "x.json.gz").read_bytes() == b


def test_historico_de_buscas_registra_e_nao_duplica():
    h = {}
    execucao.registrar_busca(h, neighborhood_id="1", category="pizzaria", scanner="geo", source="osm", search_started_at="2026-11-24T10:00:00", results_found=12, new_places=3, duplicates=9)
    execucao.registrar_busca(h, neighborhood_id="1", category="pizzaria", scanner="geo", source="osm", search_started_at="2026-11-24T10:00:00", results_found=12, new_places=4)
    assert len(h["buscas"]) == 1 and h["buscas"][0]["new_places"] == 4 and h["buscas"][0]["status"] == "concluida"
    with pytest.raises(ValueError):
        execucao.registrar_busca(h, neighborhood_id="1")


def test_comparacao_de_snapshots():
    s = lambda dt, cov, n: {"snapshot_date": dt, "distritos": {"1": {"coverage_score": cov, "total_places": n}, "2": {"coverage_score": 50, "total_places": 10}}}
    assert execucao.comparar({"snapshots": [s("a", 60, 10)]}) is None
    c = execucao.comparar({"snapshots": [s("2026-11-01", 60, 10), s("2026-11-02", 70, 25)]})
    assert c["melhoraram"][0]["id"] == "1" and c["melhoraram"][0]["delta_cobertura"] == 10 and c["novos_lugares"] == 15


def test_registro_malformado_nao_interrompe_o_processamento():
    ls = variados(30) + [{"id": 777, "nome": "Quebrado", "lat": "abc", "lon": [1]}]
    g = mundo()
    t = analise.associar(ls, g["distritos"], CFG)
    assert t[777]["status"] == "unknown" and len(t) >= 31            # registro ruim fica 'unknown'; o resto segue


def test_cobertura_nao_ativa_scanners():
    import sys
    sys.modules.pop("core.lancador", None)
    import cobertura.rodar  # noqa: F401
    src = open(cobertura.rodar.__file__, encoding="utf-8").read() + open("coletar_cobertura.py", encoding="utf-8").read()
    assert "lancador" not in src and "workflow run" not in src and "dispatches" not in src
    wf = open(".github/workflows/cobertura.yml", encoding="utf-8").read()
    assert "gh workflow" not in wf and "actions: write" not in wf


def test_no_repositorio_o_registro_do_bot_e_o_workflow_existem():
    from bots import registry
    b = registry.por_id("cobertura")
    assert b["workflow"] == "cobertura.yml" and b["grupo"] in registry.GRUPOS and os.path.exists(".github/workflows/cobertura.yml")


# ---------- API ----------
def test_api_exige_autenticacao_e_limita_recalculo(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.cobertura_api as api
    d = montar(tmp_path)
    rodar(dados=str(d), agora=AGORA)
    monkeypatch.setenv("TURIZ_DADOS", str(d))
    monkeypatch.setattr(api, "_ultimo", {"t": 0.0})
    c = TestClient(app)
    H = {"X-API-Key": "k"}
    for rota in ("/coverage", "/coverage/neighborhoods", "/coverage/neighborhoods/1", "/coverage/categories", "/coverage/priorities", "/coverage/history"):
        assert c.get(rota).status_code == 401, rota                    # dado interno: sem chave, nada
        assert c.get(rota, headers=H).status_code == 200, rota
    assert c.post("/coverage/recalculate").status_code == 401
    assert c.get("/coverage/neighborhoods/abc", headers=H).status_code == 422
    assert c.get("/coverage/neighborhoods/9999", headers=H).status_code == 404
    assert c.get("/coverage/neighborhoods?status=x", headers=H).status_code == 422
    assert c.get("/coverage/comparison", headers=H).status_code == 404
    det = c.get("/coverage/neighborhoods/1", headers=H).json()
    assert "geometry" not in det["distrito"] and det["metricas"]["id"] == "1"
    r1 = c.post("/coverage/recalculate", headers=H)
    assert r1.status_code == 200 and r1.json()["ok"] is True
    assert c.post("/coverage/recalculate", headers=H).status_code == 429        # intervalo mínimo
