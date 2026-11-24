import gzip
import json

import pytest

from revisao import dedup, localizacao, score
from revisao.texto import nome_chave, normalizar_nome

BASE = {"fonte": "osm", "tipo": "restaurante", "lat": -23.55, "lon": -46.63, "endereco": "Rua A, 10", "bairro": "Centro", "cep": "01000-000",
        "telefone": "", "site": "", "horario": "", "culinaria": "", "extra": {}, "atualizado_em": "2999-01-01T00:00:00"}


def L(i, nome, **kw):
    return {**BASE, "id": i, "fonte_id": f"n/{i}", "nome": nome, **kw}


def test_normalizacao_de_nomes():
    assert normalizar_nome("Café do Zé's!") == "cafe do zes"
    assert nome_chave("Pizzaria Mário") == nome_chave("Mario")
    assert nome_chave("Bar") == "bar"            # só palavra genérica: não vira vazio


def test_duplicado_confirmado_mesmo_nome_no_mesmo_ponto_e_canonico_prefere_osm():
    a = L(1, "Casa do Pão", fonte="receita", extra={"coordenada_aproximada": True}, cep="01000-000")
    b = L(2, "Casa do Pao", lat=-23.55001)
    pares = dedup.encontrar([a, b])
    assert [p["tipo"] for p in pares] == [dedup.CONFIRMADO]
    assert pares[0]["canonico"] == 2 and pares[0]["duplicado"] == 1 and pares[0]["fontes_distintas"] is True
    assert dedup.resolver(pares) == {1: 2}


def test_franquia_nunca_e_unida_e_unidades_proximas_sao_marcadas():
    rede = [L(i, "Burger Rei", lat=-23.55 + i * 0.01, endereco=f"Rua B, {i}") for i in range(1, 6)]
    perto = L(9, "Burger Rei", lat=-23.55 + 0.01 + 0.0004, endereco="Rua B, 99")   # a ~45 m da unidade 1... outro número
    pares = dedup.encontrar(rede + [perto])
    assert not [p for p in pares if p["tipo"] == dedup.CONFIRMADO]
    assert dedup.resolver(pares) == {}


def test_mesma_rua_numeros_diferentes_sao_unidades_diferentes():
    pares = dedup.encontrar([L(1, "Padaria Sol", endereco="Rua A, 10"), L(2, "Padaria Sol", endereco="Rua A, 500", lat=-23.5501)])
    assert pares and pares[0]["tipo"] == dedup.UNIDADE and "canonico" not in pares[0]


def test_nome_parecido_e_distante_nao_e_par():
    assert dedup.encontrar([L(1, "Padaria Sol"), L(2, "Padaria Sol", lat=-23.56)]) == []


def test_possivel_duplicado_quando_so_ha_nome_parecido():
    pares = dedup.encontrar([L(1, "Cantina Bella Napoli"), L(2, "Cantina Bela Napoli", lat=-23.5501, endereco="")])
    assert pares and pares[0]["tipo"] in (dedup.POSSIVEL, dedup.CONFIRMADO)


def test_localizacao_flags():
    assert localizacao.checar(L(1, "X")) == []
    assert "coordenadas_invalidas" in localizacao.checar(L(1, "X", lat=0, lon=0))
    assert "fora_da_area" in localizacao.checar(L(1, "X", lat=-22.9, lon=-43.2))
    f = localizacao.checar(L(1, "X", endereco="", bairro="", cep="20000-000", extra={"coordenada_aproximada": True}))
    assert {"endereco_incompleto", "sem_bairro", "cep_fora_de_sp", "coordenada_aproximada"} <= set(f)
    assert "sem_numero" in localizacao.checar(L(1, "X", endereco="Rua sem numero"))
    assert "cep_invalido" in localizacao.checar(L(1, "X", cep="123"))


def test_score_fontes_independentes_e_sem_penalidade_por_opcionais():
    l = L(1, "Casa Boa")
    so_osm = score.familias(l)
    assert so_osm == {"osm"}
    com_site = score.familias({**l, "site": "https://x.com"}, redes=[{"origem": "site"}], cardapios=[{"origem": "link_site"}], imagens=[{"fonte": "site"}])
    assert com_site == {"osm", "oficial"}             # site + rede + cardápio + imagem do site = UMA família
    assert score.familias(l, fontes_extras=["receita"]) == {"osm", "receita"}
    a = score.avaliar(l, [], so_osm)
    b = score.avaliar(l, [], score.familias(l, fontes_extras=["receita"]))
    assert b["s"] > a["s"]
    assert score.completude(l) == score.completude({**l, "telefone": ""})        # opcional ausente não penaliza
    assert score.completude({**l, "telefone": "11999999999"}) > score.completude(l)


def test_score_faixas_e_publicacao():
    l = L(1, "Casa Boa", culinaria="italiana", site="https://x.com")
    img = [{"status": "aprovada", "licenca": "CC", "creditos_url": "https://x"}]
    alto = score.avaliar(l, [], {"osm", "receita", "oficial"}, imagens=img)
    assert alto["s"] >= 90 and alto["faixa"] == "alta" and alto["p"] is True
    ruim = score.avaliar(L(2, "Bar", lat=0, lon=0, endereco="", bairro="", cep=""), ["coordenadas_invalidas", "endereco_incompleto", "sem_bairro", "sem_cep"], {"osm"})
    assert ruim["p"] is False and ruim["s"] < 50
    dup = score.avaliar(l, [], {"osm", "receita"}, canonico=7)
    assert dup["p"] is False and dup["dup_de"] == 7
    assert score.faixa(74) == "necessita_revisao" and score.faixa(75) == "confiavel" and score.faixa(24) == "nao_confirmado"
    assert 0 <= score.avaliar(l, ["coordenadas_invalidas"] * 3, set())["s"] <= 100


def test_pipeline_completa_nao_altera_lugares(tmp_path, monkeypatch):
    import revisar
    monkeypatch.setattr(revisar, "DADOS", str(tmp_path))
    lugares = [L(1, "Casa do Pão", fonte="receita", extra={"coordenada_aproximada": True}), L(2, "Casa do Pao", lat=-23.55001), L(3, "Outro Lugar", lat=-23.6, endereco="")]
    (tmp_path / "lugares.json").write_text(json.dumps(lugares), encoding="utf-8")
    original = (tmp_path / "lugares.json").read_bytes()
    monkeypatch.setenv("TURIZ_STATUS_PUBLICAR", "")
    monkeypatch.chdir(tmp_path)
    revisar.main.__globals__["bot"] = lambda b: __import__("bots.status", fromlist=["x"]).bot(b, publicador=None, pasta=str(tmp_path / "st"), verificar_pausa=False)
    monkeypatch.setattr("sys.argv", ["revisar.py"])
    revisar.main()
    assert (tmp_path / "lugares.json").read_bytes() == original
    res = json.loads((tmp_path / "revisao_resumo.json").read_text())
    assert res["total"] == 3 and res["duplicados_relacionados"] == 1
    rev = {x["id"]: x for x in json.load(gzip.open(tmp_path / "revisao.json.gz", "rt"))["lugares"]}
    assert rev[1]["dup_de"] == 2 and rev[1]["p"] is False and "receita" in rev[2]["fam"]      # confirmado por 2ª fonte independente
    assert "endereco_incompleto" in rev[3]["f"]
    # determinístico: rodar de novo gera arquivos idênticos (sem commit à toa)
    antes = (tmp_path / "revisao.json.gz").read_bytes()
    revisar.main()
    assert (tmp_path / "revisao.json.gz").read_bytes() == antes or json.load(gzip.open(tmp_path / "revisao.json.gz", "rt"))["lugares"] == list(rev.values())


def test_bots_de_revisao_no_registro_e_workflow_existe():
    import os
    from bots import registry
    for i, etapa in (("deduplicador", "dedup"), ("location_check", "local"), ("revisor", "score")):
        b = registry.por_id(i)
        assert b["workflow"] == "revisao.yml" and b["entradas"] == {"etapa": etapa} and b["grupo"] in registry.GRUPOS
    assert os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", ".github", "workflows", "revisao.yml"))
