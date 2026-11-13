import json
import zipfile
import pytest
import coletar_receita
from app.sources import receita


def _zip(tmp_path, nome, conteudo, interno="DADOS.CSV", enc="latin-1"):
    p = tmp_path / nome
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(interno, conteudo.encode(enc))
    return str(p)


def est(basico, ordem="0001", fantasia="", sit="02", cnae="5611201", tipo="RUA", logr="AUGUSTA", num="1000", bairro="CONSOLACAO",
        cep="01310100", uf="SP", mun="7107", email="dono@exemplo.com", tel="991234567"):
    # 30 colunas, igual ao arquivo real
    c = [basico, ordem, "91", "1", fantasia, sit, "20200101", "00", "", "", "20190315", cnae, "", tipo, logr, num, "", bairro, cep, uf, mun,
         "11", tel, "", "", "", "", email, "", ""]
    assert len(c) == 30
    return ";".join(f'"{x}"' for x in c)


EST = "\n".join([
    est("11111111", fantasia="RESTAURANTE DO ZE"),                                  # válido (exato: CEP + número)
    est("22222222", fantasia="BAR DA MARIA", cnae="5611204"),                        # MEI -> excluído
    est("33333333", fantasia="LANCHONETE ESQUINA", cnae="5611203", num="S/N"),       # válido (só centro do CEP)
    est("44444444", fantasia=""),                                                    # sem nome fantasia -> fora
    est("55555555", fantasia="BAR FECHADO", sit="08"),                               # inativo -> fora
    est("66666666", fantasia="PIZZARIA DE CAMPINAS", mun="6291"),                    # outra cidade -> fora
    est("77777777", fantasia="LOJA DE ROUPAS", cnae="4781400"),                      # outro ramo -> fora
    est("88888888", fantasia="BAR 12345678901"),                                     # nome com número de documento -> fora
    est("99999999", fantasia="BAR DO INDIVIDUAL", cnae="5611204"),                   # natureza 2135 -> excluído
]) + "\n"
EMP = "\n".join(f'"{b}";"EMPRESA {b} LTDA 12345678901";"{n}";"49";"1000,00";"01";""' for b, n in
                [("11111111", "2062"), ("22222222", "2135"), ("33333333", "2062"), ("99999999", "2135")]) + "\n"
SIMPLES = '"22222222";"S";"20200101";"00000000";"S";"20200101";"00000000"\n"11111111";"S";"20200101";"00000000";"N";"";""\n'
CNEFE = ("COD_UNICO_ENDERECO;COD_UF;COD_MUNICIPIO;COD_DISTRITO;COD_SUBDISTRITO;COD_SETOR;NUM_QUADRA;NUM_FACE;CEP;DSC_LOCALIDADE;"
         "NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;NUM_ENDERECO;LATITUDE;LONGITUDE\n"
         "1;35;3550308;1;1;1;1;1;01310100;SP;RUA;;AUGUSTA;1000;-23.553000;-46.650000\n"
         "2;35;3550308;1;1;1;1;1;01310100;SP;RUA;;AUGUSTA;1002;-23.553200;-46.650200\n"
         "3;35;3550308;1;1;1;1;1;99999999;SP;RUA;;OUTRA;5;-23.000000;-46.000000\n"
         "4;35;3509502;1;1;1;1;1;01310100;CAMPINAS;RUA;;X;1000;-22.900000;-47.000000\n")


def _arquivos(tmp_path):
    return (_zip(tmp_path, "est.zip", EST), _zip(tmp_path, "emp.zip", EMP), _zip(tmp_path, "simples.zip", SIMPLES),
            _zip(tmp_path, "cnefe.zip", CNEFE, "35_SP.csv", "utf-8"))


def test_filtra_so_bares_e_restaurantes_ativos_de_sp_com_nome_fantasia(tmp_path):
    e, *_ = _arquivos(tmp_path)
    c = receita.filtrar_estabelecimentos(e)
    assert sorted(k[0] for k in c) == ["11111111", "22222222", "33333333", "99999999"]


def test_pipeline_completo_exclui_individuais_e_nao_vaza_dados(tmp_path):
    e, emp, sim, cnefe = _arquivos(tmp_path)
    regs, st = coletar_receita.processar([e], [emp], sim, cnefe)
    assert sorted(r["nome"] for r in regs) == ["Lanchonete Esquina", "Restaurante do Ze"]
    assert st["individuais_excluidos"] == 2 and st["coord_exata"] == 1 and st["coord_aproximada"] == 1
    r1 = next(r for r in regs if r["nome"] == "Restaurante do Ze")
    assert (r1["lat"], r1["lon"]) == (-23.553, -46.65) and r1["extra"]["coordenada_aproximada"] is False
    assert r1["endereco"] == "Rua Augusta, 1000" and r1["bairro"] == "Consolacao" and r1["cep"] == "01310-100" and r1["tipo"] == "restaurante"
    r2 = next(r for r in regs if r["nome"] == "Lanchonete Esquina")
    assert r2["culinaria"] == "Lanchonete" and r2["extra"]["coordenada_aproximada"] is True and r2["endereco"] == "Rua Augusta"
    blob = json.dumps(regs)
    for proibido in ("11111111", "33333333", "dono@exemplo.com", "991234567", "12345678901", "EMPRESA", "cnpj"):
        assert proibido.lower() not in blob.lower(), proibido          # nada do CNPJ, razão social, e-mail ou telefone
    assert all(r["telefone"] == "" and r["site"] == "" for r in regs)


def test_incluir_individuais_so_quando_pedido(tmp_path):
    e, emp, sim, cnefe = _arquivos(tmp_path)
    regs, _ = coletar_receita.processar([e], [emp], sim, cnefe, incluir_individuais=True)
    assert len(regs) == 4


def test_id_nao_e_derivado_do_cnpj_e_e_estavel(tmp_path):
    e, emp, sim, cnefe = _arquivos(tmp_path)
    a, _ = coletar_receita.processar([e], [emp], sim, cnefe)
    b, _ = coletar_receita.processar([e], [emp], sim, cnefe)
    assert [r["fonte_id"] for r in a] == [r["fonte_id"] for r in b] and all(len(r["fonte_id"]) == 16 for r in a)
    import hashlib
    assert a[0]["fonte_id"] != hashlib.sha1(b"11111111").hexdigest()[:16]


@pytest.mark.parametrize("campo,valor", [("nome", "Bar 12.345.678/0001-95"), ("endereco", "CPF 123.456.789-09"), ("bairro", "x@y.com"),
                                         ("nome", "Bar 12345678000195"), ("extra", {"cnpj": "x"}), ("extra", {"email": "x"})])
def test_trava_de_privacidade_bloqueia(campo, valor):
    base = {"fonte": "receita", "fonte_id": "abc", "tipo": "bar", "nome": "Bar", "endereco": "Rua A, 1", "bairro": "Centro", "cep": "01310-100", "extra": {}}
    receita.validar_privacidade([base])                                  # o normal passa
    with pytest.raises(ValueError):
        receita.validar_privacidade([{**base, campo: valor}])


def test_titulo_e_cep():
    assert receita.titulo("  RUA  AUGUSTA DO CENTRO ") == "Rua Augusta do Centro"
    assert receita.cep_fmt("01310100") == "01310-100" and receita.cep_fmt("123") == ""


def test_mesclar_com_osm_remove_duplicados():
    osm = [{"fonte": "osm", "fonte_id": "node/1", "nome": "Restaurante do Zé", "lat": -23.5530, "lon": -46.6500, "cep": ""}]
    regs = [{"nome": "Restaurante do Ze", "lat": -23.55301, "lon": -46.65001, "cep": "01310-100"},     # mesmo lugar (a poucos metros)
            {"nome": "Padaria Nova", "lat": -23.5600, "lon": -46.6600, "cep": "01310-200"}]            # lugar diferente
    novos, conf = receita.mesclar_com_osm(regs, osm)
    assert [r["nome"] for r in novos] == ["Padaria Nova"] and conf == ["node/1"]


def test_restaurar_carrega_base_da_receita_em_bloco(tmp_path, monkeypatch):
    import gzip
    import os
    from sqlalchemy import select
    from app.db import Base, SessionLocal, engine
    from app.models import Lugar
    from app.restaurar import restaurar
    e, emp, sim, cnefe = _arquivos(tmp_path)
    regs, _ = coletar_receita.processar([e], [emp], sim, cnefe)
    with gzip.open(tmp_path / "lugares_receita.json.gz", "wt", encoding="utf-8") as f:
        json.dump(regs, f)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.query(Lugar).filter(Lugar.fonte == "receita").delete()
        db.commit()
    assert restaurar(str(tmp_path))["lugares_receita"] == {"novos": 2, "atualizados": 0}
    assert restaurar(str(tmp_path))["lugares_receita"] == {"novos": 0, "atualizados": 2}   # segunda carga: upsert idempotente
    with SessionLocal() as db:
        assert db.scalar(select(Lugar.nome).where(Lugar.fonte == "receita", Lugar.nome == "Lanchonete Esquina")) == "Lanchonete Esquina"


def test_ultima_pasta_le_o_webdav_da_receita():
    import httpx
    xml = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">'
           + "".join(f"<d:response><d:href>/public.php/webdav/{h}</d:href></d:response>" for h in ("", "2026-08/", "2026-10/", "2026-09/", "leiame.txt"))
           + "</d:multistatus>")
    def h(req):
        assert req.method == "PROPFIND" and req.headers["authorization"].startswith("Basic ")
        return httpx.Response(207, content=xml.encode())
    assert coletar_receita.ultima_pasta(httpx.Client(transport=httpx.MockTransport(h))) == "2026-10"
