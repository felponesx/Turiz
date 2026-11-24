#!/usr/bin/env python3
"""TURIZ Review: roda deduplicador, location check e revisor (score) sobre data/lugares.json.
Ex.: python revisar.py [--etapa tudo|dedup|local|score]
Escreve: data/duplicados.json.gz, data/localizacao.json.gz, data/revisao.json.gz e data/revisao_resumo.json (pequeno, lido pelo painel).
Não altera data/lugares.json."""
import argparse
import gzip
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from bots.status import bot
from revisao import dedup, localizacao, score

DADOS = os.environ.get("TURIZ_DADOS", "data")
ETAPAS = {"dedup": "deduplicador", "local": "location_check", "score": "revisor"}


def _ler(nome, padrao):
    for arq, abrir in ((f"{DADOS}/{nome}.json", open), (f"{DADOS}/{nome}.json.gz", lambda p: gzip.open(p, "rt", encoding="utf-8"))):
        if os.path.exists(arq):
            with abrir(arq) as f:
                return json.load(f)
    return padrao


def _gravar(nome, obj, gz=True):
    caminho = f"{DADOS}/{nome}.json" + (".gz" if gz else "")
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    tmp = caminho + ".tmp"
    if gz:
        with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as f:   # mtime=0: arquivo igual → sem commit à toa
            f.write(txt.encode("utf-8"))
    else:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(txt)
    os.replace(tmp, caminho)


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def etapa_dedup(rep):
    lugares = _ler("lugares", [])
    rep.progresso(0, 0, atual=f"Comparando {len(lugares)} lugares vizinhos")
    pares = dedup.encontrar(lugares, progresso=lambda i, n: rep.progresso(i, n, atual="Comparando lugares próximos"))
    cont = Counter(p["tipo"] for p in pares)
    mapa = dedup.resolver(pares)
    _gravar("duplicados", {"gerado_em": agora(), "total_lugares": len(lugares), "resumo": dict(cont), "pares": pares})
    rep.definir(analisados=len(lugares), duplicados_confirmados=cont[dedup.CONFIRMADO], possiveis_duplicados=cont[dedup.POSSIVEL], unidades_diferentes=cont[dedup.UNIDADE])
    rep.contar(duplicados=len(mapa))
    for p in [x for x in pares if x["tipo"] == dedup.CONFIRMADO][:5]:
        rep.item(f"Duplicado confirmado: #{p['duplicado']} → #{p['canonico']} ({p['motivo']})")
    print(f"pares: {dict(cont)}; duplicados a relacionar: {len(mapa)}")


def etapa_local(rep):
    lugares = _ler("lugares", [])
    rep.progresso(0, 0, atual="Verificando endereços e coordenadas")
    res = localizacao.verificar(lugares)
    cont = Counter(f for fl in res.values() for f in fl)
    _gravar("localizacao", {"gerado_em": agora(), "total_lugares": len(lugares), "resumo": dict(cont), "lugares": {str(k): v for k, v in res.items()}})
    graves = sum(1 for fl in res.values() if localizacao.GRAVES & set(fl))
    rep.progresso(1, 1)
    rep.definir(analisados=len(lugares), com_problema_grave=graves, **{k: v for k, v in cont.items() if k in localizacao.GRAVES})
    print(f"flags: {dict(cont)}")


def etapa_score(rep):
    lugares = _ler("lugares", [])
    pares = (_ler("duplicados", {}) or {}).get("pares", [])
    loc = (_ler("localizacao", {}) or {}).get("lugares", {})
    por_chave = {(l["fonte"], l["fonte_id"]): l["id"] for l in lugares}
    def indice(nome):
        d = defaultdict(list)
        for x in _ler(nome, []):
            i = por_chave.get((x.get("lugar_fonte"), x.get("lugar_fonte_id")))
            if i is not None:
                d[i].append(x)
        return d
    imagens, redes, cardapios = indice("imagens"), indice("redes_sociais"), indice("cardapios")
    por_id = {l["id"]: l for l in lugares}
    mapa = dedup.resolver(pares)
    possivel = {x for p in pares if p["tipo"] == dedup.POSSIVEL for x in (p["a"], p["b"])}
    extras = defaultdict(set)     # canônico confirmado por OUTRA fonte independente
    for p in pares:
        if p["tipo"] == dedup.CONFIRMADO and p.get("fontes_distintas"):
            extras[p["canonico"]].add(por_id[p["duplicado"]]["fonte"])
    saida, n = {}, len(lugares)
    for i, l in enumerate(lugares):
        if i % 2000 == 0:
            rep.progresso(i, n, atual="Calculando score de confiabilidade")
        flags = loc.get(str(l["id"])) or localizacao.checar(l)
        im, rd, cd = imagens.get(l["id"], ()), redes.get(l["id"], ()), cardapios.get(l["id"], ())
        fam = score.familias(l, im, rd, cd, extras.get(l["id"], ()))
        saida[l["id"]] = score.avaliar(l, flags, fam, im, rd, cd, l["id"] in possivel and l["id"] not in mapa, mapa.get(l["id"]))
    faixas = Counter(v["faixa"] for v in saida.values())
    pub = sum(1 for v in saida.values() if v["p"])
    medias = {"confiabilidade": round(sum(v["s"] for v in saida.values()) / max(1, n), 1), "completude": round(sum(v["c"] for v in saida.values()) / max(1, n), 1)}
    por_fonte = defaultdict(Counter)
    for l in lugares:
        por_fonte[l["fonte"]][saida[l["id"]]["faixa"]] += 1
    resumo = {"gerado_em": agora(), "total": n, "faixas": dict(faixas), "publicaveis": pub, "duplicados_relacionados": len(mapa),
              "aguardando_revisao": faixas["necessita_revisao"] + faixas["baixa_confianca"] + faixas["nao_confirmado"],
              "medias": medias, "por_fonte": {k: dict(v) for k, v in por_fonte.items()},
              "flags": (_ler("localizacao", {}) or {}).get("resumo", {}), "duplicidade": (_ler("duplicados", {}) or {}).get("resumo", {}),
              "config": {"faixas": score.CONFIG["faixas"], "pesos": score.CONFIG["pesos"], "minimo_para_publicar": score.CONFIG["minimo_para_publicar"]}}
    _gravar("revisao", {"gerado_em": resumo["gerado_em"], "lugares": list(saida.values())})
    _gravar("revisao_resumo", resumo, gz=False)
    rep.progresso(n, n)
    rep.definir(analisados=n, publicaveis=pub, aguardando_revisao=resumo["aguardando_revisao"], score_medio=medias["confiabilidade"])
    print(f"faixas: {dict(faixas)}; publicáveis: {pub}; médias: {medias}")


FUNCOES = {"dedup": etapa_dedup, "local": etapa_local, "score": etapa_score}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", default="tudo", choices=["tudo", *FUNCOES])
    a = ap.parse_args()
    for nome in (list(FUNCOES) if a.etapa == "tudo" else [a.etapa]):
        try:
            with bot(ETAPAS[nome]) as rep:
                FUNCOES[nome](rep)
        except SystemExit as e:       # bot pausado no painel: segue para a próxima etapa
            if e.code not in (0, None):
                raise


if __name__ == "__main__":
    main()
