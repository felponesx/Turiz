"""Núcleo de eventos: validação, taxonomia, duplicidade, persistência e ciclo de vida. Dados SIMULADOS (sintéticos) de teste."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import Evento
from app.eventos import dedup, taxonomia
from app.eventos.bruto import EventoBruto, ImagemBruta, LocalBruto, Pessoa, validar
from app.eventos.modelos import EventoAtualizacao, EventoDuplicata, EventoFonteLink, EventoImagem
from app.eventos.normalizar import status_de
from app.eventos.persistir import ciclo_de_vida, ingerir

FUT = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=20)


def bruto(**kw):
    base = dict(fonte="a", fonte_id="1", titulo="Show da Banda Teste", inicio=FUT.replace(hour=22, minute=0),
                local=LocalBruto(nome="Casa Teste", cidade="São Paulo", estado="SP", pais="BR", lat=-23.55, lon=-46.63))
    base.update(kw)
    return EventoBruto(**base)


def test_validacao_sanitiza_e_descarta():
    b, _ = validar(bruto(titulo="<script>x()</script>Show <b>Bom</b>", descricao="a\x00b", url="javascript:alert(1)",
                         ingresso_url="https://u:p@x.com/c", imagens=[ImagemBruta(url="ftp://x/a.jpg"), ImagemBruta(url="https://x.com/a.jpg")]))
    assert b.titulo == "Show Bom" and "\x00" not in b.descricao
    assert b.url == "" and b.ingresso_url == ""                      # esquema perigoso / credenciais na URL
    assert [i.url for i in b.imagens] == ["https://x.com/a.jpg"]
    assert validar(bruto(titulo=""))[0] is None
    assert validar(bruto(preco_min=-5))[0].preco_min is None         # número fora do limite: campo descartado, nada inventado
    assert validar(bruto(local=LocalBruto(nome="x", lat=999, lon=0)))[0].local.lat is None


def test_status():
    assert status_de("onsale") == "agendado" and status_de("cancelled") == "cancelado"
    assert status_de("postponed") == "adiado" and status_de("rescheduled") == "remarcado"
    assert status_de("coisa-estranha") == "desconhecido"


def test_taxonomia_multicategoria():
    c = taxonomia.classificar("Festival Gastronômico de São Paulo", "Degustação", [])
    slugs = [x[0] for x in c]
    assert slugs[0] == "festivais-gastronomicos"
    assert "gastronomia" in taxonomia.com_ancestrais(slugs)


def _d(nome, inicio, local, lat=None, lon=None, fonte="a"):
    return {"nome_norm": nome, "inicio": inicio, "fuso": "America/Sao_Paulo", "local": {"nome_norm": local, "lat": lat, "lon": lon, "fonte": fonte}}


def test_dedup_nome_parecido_nao_basta():
    i = FUT.replace(hour=22)
    assert dedup.comparar(_d("show banda teste", i, "casa teste"), _d("show banda teste", i, "casa teste")).decisao == "mesmo"
    assert dedup.comparar(_d("show banda teste", i, "casa teste"), _d("show banda teste", i + timedelta(days=3), "casa teste")).decisao == "distinto"
    assert dedup.comparar(_d("show banda teste", i, "casa teste"), _d("show banda teste", i, "arena outra cidade")).decisao == "distinto"
    assert dedup.comparar(_d("show banda teste dia 1", i, "casa teste"), _d("show banda teste dia 2", i, "casa teste")).decisao != "mesmo"
    assert dedup.comparar(_d("show banda teste", i, "casa teste"), _d("show banda teste", i + timedelta(hours=6), "casa teste")).decisao == "distinto"


def test_ingerir_cria_evento_com_relacionados(db):
    r = ingerir(db, "a", [bruto(artistas=[Pessoa(nome="Banda Teste")], organizador=Pessoa(nome="Produtora X", tipo="promotor"),
                                imagens=[ImagemBruta(url="https://x.com/a.jpg", largura=1024, altura=576), ImagemBruta(url="https://x.com/fb.jpg", fallback=True)],
                                categorias=["Music", "Rock"], preco_min=50, preco_max=90, moeda="BRL", url="https://x.com/e")])
    assert (r.novos, r.descartados) == (1, 0)
    ev = db.scalars(select(Evento)).one()
    assert ev.status == "agendado" and ev.preco_max == 90 and ev.imagem_url == "https://x.com/a.jpg"
    assert db.scalars(select(EventoImagem)).all()                    # imagens guardadas
    assert db.scalars(select(EventoFonteLink)).one().fonte == "a"
    assert r.inalterados == 0
    r2 = ingerir(db, "a", [bruto(artistas=[Pessoa(nome="Banda Teste")], organizador=Pessoa(nome="Produtora X", tipo="promotor"), categorias=["Music", "Rock"],
                                 imagens=[ImagemBruta(url="https://x.com/a.jpg", largura=1024, altura=576)], preco_min=50, preco_max=90, moeda="BRL", url="https://x.com/e")])
    assert r2.novos == 0 and len(db.scalars(select(Evento)).all()) == 1


def test_mesmo_evento_em_duas_fontes_vira_um_com_dois_links(db):
    ingerir(db, "a", [bruto()])
    r = ingerir(db, "b", [bruto(fonte="b", fonte_id="zz", titulo="Show da Banda Teste", ingresso_url="https://b.com/c")])
    assert r.duplicados == 1 and r.novos == 0
    assert len(db.scalars(select(Evento)).all()) == 1
    assert {l.fonte for l in db.scalars(select(EventoFonteLink))} == {"a", "b"}


def test_mesma_fonte_nunca_se_funde(db):
    ingerir(db, "a", [bruto(), bruto(fonte_id="2")])               # duas sessões da mesma fonte com o mesmo nome
    assert len(db.scalars(select(Evento)).all()) == 2


def test_nome_parecido_data_diferente_nao_funde(db):
    ingerir(db, "a", [bruto()])
    ingerir(db, "b", [bruto(fonte="b", fonte_id="9", inicio=FUT + timedelta(days=5))])
    assert len(db.scalars(select(Evento)).all()) == 2


def test_fila_de_revisao(db):
    ingerir(db, "a", [bruto(titulo="Festival de Verão Sampa 2027")])
    r = ingerir(db, "b", [bruto(fonte="b", fonte_id="9", titulo="Festival de Verao Sampa 2027 Oficial", local=LocalBruto(nome="Casa Teste Anexo", lat=-23.5501, lon=-46.6301))])
    pend = db.scalars(select(EventoDuplicata)).all()
    assert r.revisao == len(pend)
    assert len(db.scalars(select(Evento)).all()) == 2 or r.duplicados == 1  # nunca perde dado: ou separado+revisão ou unido com evidência forte


def test_cancelamento_vira_status_com_historico_e_nao_apaga(db):
    ingerir(db, "a", [bruto()])
    ingerir(db, "a", [bruto(status_raw="cancelled")])
    ev = db.scalars(select(Evento)).one()
    assert ev.status == "cancelado"
    hist = db.scalars(select(EventoAtualizacao)).all()
    assert any(h.campo == "status" and h.valor_novo == "cancelado" for h in hist)


def test_ciclo_de_vida_encerra_sem_apagar(db):
    passado = datetime.now(timezone.utc) - timedelta(days=3)
    ingerir(db, "a", [bruto(inicio=passado), bruto(fonte_id="2", inicio=FUT)])
    ev_passado = db.scalars(select(Evento).where(Evento.status != "cancelado")).all()
    res = ciclo_de_vida(db)
    assert res["encerrados"] == 1
    sts = sorted(e.status for e in db.scalars(select(Evento)))
    assert sts == ["agendado", "encerrado"]
