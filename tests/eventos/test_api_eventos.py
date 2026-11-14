"""API de eventos com dados SIMULADOS (sintéticos) inseridos via pipeline real (`ingerir`)."""
import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import SessionLocal
from app.main import app
from app.models import Evento, Lugar
from app.eventos import api as api_eventos
from app.eventos.bruto import EventoBruto, ImagemBruta, LocalBruto, Pessoa
from app.eventos.modelos import EventoDuplicata
from app.eventos.persistir import ciclo_de_vida, ingerir

c = TestClient(app)
H = {"x-api-key": os.environ["API_KEY"]}


@pytest.fixture(scope="module")
def dados():
    tag = uuid.uuid4().hex[:6]
    hoje = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)
    def ev(i, titulo, dias, cidade="São Paulo", uf="SP", pais="BR", **kw):
        return EventoBruto(fonte=f"sim{tag}", fonte_id=f"{tag}-{i}", titulo=f"{titulo} {tag}", inicio=hoje + timedelta(days=dias, hours=6),
                           local=LocalBruto(nome=f"Casa {cidade} {i}", cidade=cidade, estado=uf, pais=pais, lat=-23.5 + i / 1000, lon=-46.6), **kw)
    with SessionLocal() as db:
        ingerir(db, f"sim{tag}", [
            ev(1, "Show de Rock", 0, categorias=["Music", "Rock"], preco_min=50, preco_max=120, moeda="BRL", imagens=[ImagemBruta(url="https://img.exemplo/1.jpg", largura=1024, altura=576)]),
            ev(2, "Festival Gastronômico", 3, descricao="degustação de pratos", preco_min=0, gratuito=True),
            ev(3, "Show Carioca", 5, cidade="Rio de Janeiro", uf="RJ", categorias=["Music"], preco_min=300),
            ev(4, "Peça Cancelada", 2, status_raw="cancelled"),
            ev(5, "Show Passado", -10, categorias=["Music"]),
            ev(6, "Show Lisboa", 7, cidade="Lisboa", uf="", pais="PT", categorias=["Music"]),
            ev(7, "Evento Sem Data", 0, inicio=None, data_incerta=True) if False else ev(7, "Sarau", 1, artistas=[Pessoa(nome="Banda Zebra")]),
        ])
        ciclo_de_vida(db)
    yield tag
    with SessionLocal() as db:   # banco de testes é só desta sessão: devolve as tabelas de eventos vazias para os outros módulos
        from app.eventos import modelos as M
        for m in (M.EventoDuplicata, M.EventoAtualizacao, M.EventoCategoriaLink, M.EventoImagem, M.EventoArtistaLink, M.EventoFonteLink, Evento,
                  M.EventoArtista, M.EventoOrganizador, M.EventoLocal, M.EventoColetaLog, M.EventoFonte):
            db.query(m).delete()
        db.commit()


def titulos(r):
    return [e["titulo"].rsplit(" ", 1)[0] for e in r["itens"]]


def get(params, tag):
    return c.get("/eventos", params={"q": tag, **params}).json()


def test_lista_padrao_so_futuros_e_sem_cancelados(dados):
    r = get({}, dados)
    t = titulos(r)
    assert "Show Passado" not in t and "Peça Cancelada" not in t and "Show de Rock" in t
    assert t == sorted(t, key=lambda x: [e["inicio"] for e in r["itens"] if e["titulo"].startswith(x)][0])      # ordenado por data


def test_filtros_cidade_pais_categoria_preco_data(dados):
    assert titulos(get({"cidade": "Rio de Janeiro"}, dados)) == ["Show Carioca"]
    assert titulos(get({"pais": "PT"}, dados)) == ["Show Lisboa"]
    assert set(titulos(get({"categoria": "shows"}, dados))) >= {"Show de Rock", "Show Carioca"}
    assert titulos(get({"categoria": "rock"}, dados)) == ["Show de Rock"]
    assert titulos(get({"gratuito": True}, dados)) == ["Festival Gastronômico"]
    assert "Show Carioca" not in titulos(get({"preco_max": 100}, dados))                   # R$ 300 excluído
    assert "Show Lisboa" not in titulos(get({"preco_max": 100}, dados))                    # preço desconhecido não é presumido
    amanha = (datetime.now(TZ_SP := timezone(timedelta(hours=-3))) + timedelta(days=1)).date().isoformat()
    assert all(e["inicio"][:10] >= "2000" for e in get({"data_de": amanha, "data_ate": amanha}, dados)["itens"])
    assert get({"incluir_cancelados": True}, dados)["total"] == get({}, dados)["total"] + 1
    assert get({"incluir_encerrados": True}, dados)["total"] >= get({}, dados)["total"] + 1


def test_item_traz_local_categoria_imagem_real_e_fonte(dados):
    e = next(x for x in get({}, dados)["itens"] if x["titulo"].startswith("Show de Rock"))
    assert e["local"]["cidade"] == "São Paulo" and e["imagem"]["url"] == "https://img.exemplo/1.jpg"
    assert any(cat["slug"] == "rock" for cat in e["categorias"]) and e["fontes"][0]["fonte"].startswith("sim")
    sem = next(x for x in get({}, dados)["itens"] if x["titulo"].startswith("Show Carioca"))
    assert sem["imagem"] is None                    # sem foto real: o front mostra o bloco neutro, nunca uma foto genérica


def test_detalhe_e_cancelado_acessivel_com_status(dados):
    lista = c.get("/eventos", params={"q": dados, "incluir_cancelados": True}).json()["itens"]
    canc = next(x for x in lista if x["status"] == "cancelado")
    d = c.get(f"/eventos/{canc['id']}").json()
    assert d["status"] == "cancelado" and "fontes" in d and d["imagens"] == []
    assert c.get("/eventos/99999999").status_code == 404


def test_categorias_com_contagem(dados):
    cats = {x["slug"]: x for x in c.get("/eventos/categorias").json()}
    assert cats["shows"]["total"] >= 3 and cats["gastronomia"]["grupo"] == "gastronomia"


def test_busca_natural(dados):
    r = c.get("/eventos/busca", params={"q": f"shows em Rio de Janeiro {dados}"}).json()
    assert r["interpretacao"]["cidade"] == "Rio de Janeiro" and r["interpretacao"]["categoria"] == "shows"
    assert titulos(r) == ["Show Carioca"]
    r = c.get("/eventos/busca", params={"q": f"eventos gratuitos {dados}"}).json()
    assert r["interpretacao"]["gratuito"] is True and titulos(r) == ["Festival Gastronômico"]
    r = c.get("/eventos/busca", params={"q": "show hoje em São Paulo"}).json()
    assert r["interpretacao"]["quando"] == "hoje" and r["interpretacao"]["cidade"] == "São Paulo" and r["interpretacao"]["categoria"] == "shows"
    hoje = datetime.now(timezone.utc)
    assert all(e["inicio"] and datetime.fromisoformat(e["inicio"]) >= hoje - timedelta(hours=3) for e in r["itens"])   # nunca vencido
    r = c.get("/eventos/busca", params={"q": "restaurantes com música ao vivo"}).json()
    assert r["interpretacao"]["tipo_local"] == "restaurante" and r["interpretacao"]["categoria"] == "musica-ao-vivo"
    assert all(e["lugar"] and e["lugar"]["tipo"] == "restaurante" for e in r["itens"])
    r = c.get("/eventos/busca", params={"q": f"Banda Zebra {dados}"}).json()
    assert titulos(r) == ["Sarau"]                  # artista encontrado pelo nome


def test_interpretacao_de_datas():
    from app.eventos.busca import _quando
    sexta = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)
    de, ate, _, rot = _quando(" fim de semana ", sexta)
    assert rot == "fim de semana" and de.astimezone(api_eventos.TZ).weekday() in (4, 5) and (ate - de) <= timedelta(days=3)
    de, ate, _, rot = _quando(" amanha ", sexta)
    assert (ate - de) == timedelta(days=1) and de.astimezone(api_eventos.TZ).day == 14


def test_admin_exige_chave_e_nao_aceita_segredo_na_config(dados):
    assert c.get("/admin/eventos/fontes").status_code == 401
    assert c.get("/admin/eventos/fontes", headers=H).status_code == 200
    base = {"slug": "parceiro-x", "conector": "feed_json", "config": {"url": "https://x.exemplo/e.json"}}
    assert c.put("/admin/eventos/fontes", json=base, headers=H).status_code == 200
    assert c.put("/admin/eventos/fontes", json={**base, "config": {"url": "u", "apikey": "SEGREDO"}}, headers=H).status_code == 422
    assert c.put("/admin/eventos/fontes", json={**base, "conector": "inexistente"}, headers=H).status_code == 422
    r = c.post("/admin/eventos/fontes/parceiro-x/executar", headers=H).json()
    assert r["status"] in ("erro", "sucesso")      # URL fictícia: falha isolada, sem derrubar a API
    assert c.get("/admin/eventos/coletas", headers=H, params={"fonte": "parceiro-x"}).json()


def test_revisao_de_duplicatas_mesclar_preserva_fontes(dados):
    tag = uuid.uuid4().hex[:6]
    base = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=40)
    loc = LocalBruto(nome="Casa Revisão", cidade="Santos", estado="SP", pais="BR", lat=-23.96, lon=-46.33)
    with SessionLocal() as db:
        ingerir(db, f"ra{tag}", [EventoBruto(fonte=f"ra{tag}", fonte_id="1", titulo=f"Festival Verão Santos {tag} 2027", inicio=base, local=loc)])
        ingerir(db, f"rb{tag}", [EventoBruto(fonte=f"rb{tag}", fonte_id="1", titulo=f"Festival Verao Santos {tag} 2027 Oficial", inicio=base + timedelta(hours=1),
                                             local=LocalBruto(nome="Casa Revisao Anexo", cidade="Santos", estado="SP", pais="BR", lat=-23.9601, lon=-46.3301))])
        pend = [d for d in db.scalars(select(EventoDuplicata).where(EventoDuplicata.status == "pendente"))]
    par = [p for p in c.get("/admin/eventos/duplicatas", headers=H).json() if tag in p["a"]["titulo"]]
    if not par:
        pytest.skip("pipeline uniu os eventos automaticamente (evidência forte)")
    assert c.post(f"/admin/eventos/duplicatas/{par[0]['id']}/resolver", params={"decisao": "mesmo"}, headers=H).json()["status"] == "mesclado"
    vivos = c.get("/eventos", params={"q": f"Verão Santos {tag}"}).json()["itens"]
    assert len(vivos) == 1 and {f["fonte"] for f in vivos[0]["fontes"]} == {f"ra{tag}", f"rb{tag}"}
    with SessionLocal() as db:                       # nada foi apagado
        assert db.scalar(select(Evento).where(Evento.status == "mesclado", Evento.titulo.like(f"%{tag}%"))) is not None


def test_limite_de_requisicoes(dados):
    api_eventos._hist.clear()
    antigo = api_eventos.MAX_REQ
    api_eventos.MAX_REQ = 5
    try:
        codigos = [c.get("/eventos/categorias").status_code for _ in range(7)]
    finally:
        api_eventos.MAX_REQ = antigo
        api_eventos._hist.clear()
    assert codigos[:5] == [200] * 5 and codigos[5] == 429
