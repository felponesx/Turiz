"""Categorias gastronômicas por lugar. Multi-rótulo e extensível (cobertura_config.yml)."""
import re

import yaml

from revisao.texto import normalizar_nome

_CACHE = {}


def config(caminho="cobertura_config.yml"):
    if caminho not in _CACHE:
        with open(caminho, encoding="utf-8") as f:
            _CACHE[caminho] = yaml.safe_load(f)
    return _CACHE[caminho]


def _tem_palavra(nome_norm, palavras):
    for p in palavras:
        p = normalizar_nome(p)
        if p and re.search(r"(?<![a-z0-9])" + re.escape(p), nome_norm):
            return True
    return False


def categorias_do_lugar(lugar, defs) -> list:
    nome = normalizar_nome(lugar.get("nome"))
    extra = lugar.get("extra") or {}
    cnae = str(extra.get("cnae") or "")
    culs = {c.strip().lower() for c in re.split(r"[;,]", lugar.get("culinaria") or "") if c.strip()}
    achadas = []
    for chave, d in defs.items():
        ok = False
        if lugar.get("tipo") in d.get("tipos", ()) and cnae not in d.get("excluir_cnae", ()):
            ok = True
        elif cnae and cnae in d.get("cnae", ()):
            ok = True
        elif culs & {c.lower() for c in d.get("culinarias", ())}:
            ok = True
        elif any(str(extra.get(k)).lower() in ("yes", "only", "true") for k in d.get("extra", ())):
            ok = True
        elif d.get("nome") and _tem_palavra(nome, d["nome"]):
            ok = True
        if ok:
            achadas.append(chave)
    return achadas


def categorias_de_experiencia(defs) -> set:
    return {k for k, d in defs.items() if d.get("experiencia")}
