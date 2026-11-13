#!/usr/bin/env python3
"""Amplia a base com bares e restaurantes da Receita Federal (CNPJ) + coordenadas do IBGE (CNEFE).
PRIVACIDADE: o CNPJ nunca é gravado (veja app/sources/receita.py). Saída: data/lugares_receita.json.gz + data/receita_resumo.md.

Ex.: python coletar_receita.py                       # base completa, mês mais recente
     python coletar_receita.py --arquivos 1 --mes 2026-10   # só o Estabelecimentos1 (teste rápido)"""
import argparse
import gzip
import json
import os
import re
import tempfile
from datetime import datetime, timezone
import httpx
from app.sources import receita

SEM_INDIVIDUAIS_AVISO = "MEIs e empresários individuais excluídos (privacidade)."


def ultima_pasta(cliente=None) -> str:
    """Pasta mensal mais recente do compartilhamento da Receita (WebDAV público)."""
    import xml.etree.ElementTree as ET
    cliente = cliente or httpx.Client(timeout=60, transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=2))
    r = cliente.request("PROPFIND", f"{receita.RECEITA}/", auth=(receita.TOKEN, ""), headers={"Depth": "1"})
    r.raise_for_status()
    hrefs = (x.findtext("{DAV:}href", "") for x in ET.fromstring(r.content).findall("{DAV:}response"))
    pastas = sorted(h.replace("/public.php/webdav/", "").rstrip("/") for h in hrefs if re.search(r"/\d{4}-\d{2}/$", h))
    if not pastas:
        raise RuntimeError("nenhuma pasta mensal encontrada no compartilhamento da Receita")
    return pastas[-1]


def processar(est_zips, emp_zips, simples_zip, cnefe_zip, incluir_individuais=False):
    """Núcleo sem rede (testável): zips locais -> (registros, estatísticas). O CNPJ não sai desta função."""
    cands = {}
    for z in est_zips:
        cands.update(receita.filtrar_estabelecimentos(z))
    for z in emp_zips:
        receita.anexar_natureza(z, cands)
    if simples_zip:
        receita.anexar_mei(simples_zip, cands)
    ceps = {d["cep"] for d in cands.values()}
    exato, centro = receita.indexar_cnefe(cnefe_zip, ceps)
    regs, st = receita.montar_registros(cands, exato, centro, incluir_individuais)
    receita.validar_privacidade(regs)          # trava final: aborta se houver CNPJ/CPF/e-mail
    return regs, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", help="pasta da Receita, ex.: 2026-10 (padrão: a mais recente)")
    ap.add_argument("--arquivos", default="0,1,2,3,4,5,6,7,8,9", help="números dos arquivos Estabelecimentos/Empresas (padrão: todos)")
    ap.add_argument("--incluir-individuais", action="store_true", help="NÃO recomendado: inclui MEI e empresário individual")
    a = ap.parse_args()
    mes = a.mes or ultima_pasta()
    nums = [n.strip() for n in a.arquivos.split(",") if n.strip()]
    auth = (receita.TOKEN, "")
    print(f"Receita: pasta {mes}; arquivos {nums}")
    with tempfile.TemporaryDirectory() as tmp:
        def pegar(url, nome, auth=None):
            dest = os.path.join(tmp, nome)
            mb = receita.baixar(url, dest, auth) / 1e6
            print(f"  baixado {nome}: {mb:.0f} MB")
            return dest
        est = []
        for n in nums:  # um por vez, apagando em seguida (disco do runner é limitado)
            z = pegar(f"{receita.RECEITA}/{mes}/Estabelecimentos{n}.zip", f"est{n}.zip", auth)
            est.append(receita.filtrar_estabelecimentos(z))
            os.remove(z)
            print(f"  Estabelecimentos{n}: {len(est[-1])} bares/restaurantes ativos em SP com nome fantasia")
        cands = {}
        for e in est:
            cands.update(e)
        print(f"candidatos: {len(cands)}")
        for n in nums:
            z = pegar(f"{receita.RECEITA}/{mes}/Empresas{n}.zip", f"emp{n}.zip", auth)
            receita.anexar_natureza(z, cands)
            os.remove(z)
        z = pegar(f"{receita.RECEITA}/{mes}/Simples.zip", "simples.zip", auth)
        receita.anexar_mei(z, cands)
        os.remove(z)
        z = pegar(receita.CNEFE_SP, "cnefe.zip")
        exato, centro = receita.indexar_cnefe(z, {d["cep"] for d in cands.values()})
        os.remove(z)
        regs, st = receita.montar_registros(cands, exato, centro, a.incluir_individuais)
    receita.validar_privacidade(regs)
    with gzip.open("data/lugares_receita.json.gz", "wt", encoding="utf-8") as f:
        json.dump(regs, f, ensure_ascii=False, separators=(",", ":"))
    resumo = (f"# Resumo da coleta Receita + IBGE\n\nGerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} (UTC), pasta da Receita **{mes}**.\n\n"
              f"- Estabelecimentos candidatos (bar/restaurante/lanchonete ativos em São Paulo, com nome fantasia): {st['candidatos']}\n"
              f"- {'Incluídos MEI/individuais (modo de teste)' if a.incluir_individuais else SEM_INDIVIDUAIS_AVISO} Excluídos: {st['individuais_excluidos']}\n"
              f"- Sem coordenada (descartados): {st['sem_coordenada']}\n- Descartados pela trava de privacidade (nome/endereço com '@', documento etc.): {st['descartados_privacidade']}\n- Coordenada exata (CEP + número): {st['coord_exata']}\n"
              f"- Coordenada aproximada (centro do CEP): {st['coord_aproximada']}\n- **Registros gravados: {len(regs)}**\n\n"
              "Não são gravados: CNPJ, razão social, telefone, e-mail, sócios. A trava de privacidade passou.\n")
    open("data/receita_resumo.md", "w", encoding="utf-8").write(resumo)
    print(resumo)


if __name__ == "__main__":
    main()
