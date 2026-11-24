"""Score de confiabilidade (0–100) e completude, calculados de forma transparente e configurável.
Fontes copiadas umas das outras NÃO contam em dobro: contam por família de evidência independente.
Ausência de Instagram, cardápio ou telefone NÃO penaliza (são bônus de completude, não obrigação)."""
from datetime import datetime, timezone

from .localizacao import GRAVES, checar
from .texto import normalizar_nome, PALAVRAS_GENERICAS

CONFIG = {
    "pesos": {"fontes": 40, "nome": 10, "geo": 20, "endereco": 15, "visual": 10, "atualidade": 5},
    "fontes_por_familias": {0: 0, 1: 20, 2: 32, 3: 40},
    "geo_aproximada": 9,
    "penalidade_possivel_duplicado": 8,
    "faixas": [(90, "alta"), (75, "confiavel"), (50, "necessita_revisao"), (25, "baixa_confianca"), (0, "nao_confirmado")],
    "minimo_para_publicar": 50,
}
FAIXA_ROTULO = {"alta": "Alta confiabilidade", "confiavel": "Confiável", "necessita_revisao": "Necessita revisão", "baixa_confianca": "Baixa confiança", "nao_confirmado": "Não confirmado"}


def faixa(score: int, config=CONFIG) -> str:
    return next(nome for corte, nome in config["faixas"] if score >= corte)


def familias(l, imagens=(), redes=(), cardapios=(), fontes_extras=()) -> set:
    """Famílias de evidência INDEPENDENTES. Site, redes e cardápio publicados pelo próprio lugar são uma só ('oficial')."""
    f = {l["fonte"]} if l.get("fonte") in ("receita", "osm", "google") else set()
    f.update(x for x in fontes_extras if x in ("receita", "osm", "google"))
    if l.get("fonte") == "sites":
        f.add("oficial")
    if (l.get("site") or "").strip() or any(r.get("origem") == "site" for r in redes) or any(c.get("origem") == "link_site" for c in cardapios) or any(i.get("fonte") == "site" for i in imagens):
        f.add("oficial")
    if any(i.get("fonte") == "commons" for i in imagens):
        f.add("commons")
    return f


def _nome_pts(nome, peso):
    n = normalizar_nome(nome)
    if len(n) < 3:
        return 0
    return peso if any(p not in PALAVRAS_GENERICAS for p in n.split()) else round(peso * 0.3)


def _idade_dias(iso):
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).days


def confiabilidade(l, fam, flags, imagens=(), possivel_duplicado=False, config=CONFIG) -> dict:
    p = config["pesos"]
    partes = {}
    tabela = config["fontes_por_familias"]
    partes["fontes"] = min(p["fontes"], tabela.get(min(len(fam), max(tabela)), 0))
    partes["nome"] = _nome_pts(l.get("nome"), p["nome"])
    if "coordenadas_invalidas" in flags or "fora_da_area" in flags:
        partes["geo"] = 0
    else:
        partes["geo"] = min(p["geo"], config["geo_aproximada"]) if "coordenada_aproximada" in flags else p["geo"]
    partes["endereco"] = (6 if "endereco_incompleto" not in flags else 0) + (4 if "sem_bairro" not in flags else 0) + (5 if not {"sem_cep", "cep_invalido", "cep_fora_de_sp"} & set(flags) else 0)
    aprovadas = [i for i in imagens if i.get("status") == "aprovada"]
    rastreada = any(i.get("licenca") and (i.get("creditos_url") or i.get("autor")) for i in aprovadas)
    partes["visual"] = p["visual"] if rastreada else (3 if aprovadas else 0)
    idade = _idade_dias(l.get("atualizado_em"))
    partes["atualidade"] = 0 if idade is None else p["atualidade"] if idade <= 90 else 3 if idade <= 365 else 1
    if possivel_duplicado:
        partes["duplicidade"] = -config["penalidade_possivel_duplicado"]
    total = max(0, min(100, sum(partes.values())))
    return {"score": total, "faixa": faixa(total, config), "partes": partes}


def completude(l, redes=(), imagens=(), cardapios=()) -> int:
    """0–100. Núcleo (80 pts) = o que todo lugar precisa ter. Opcionais (20 pts) só SOMAM; faltar não penaliza."""
    nucleo = [bool((l.get("nome") or "").strip()), bool(l.get("tipo")), bool((l.get("endereco") or "").strip()), bool((l.get("bairro") or "").strip()),
              bool((l.get("cep") or "").strip()), l.get("lat") is not None and l.get("lon") is not None, bool(l.get("culinaria")), bool(l.get("fonte"))]
    pts = sum(nucleo) / len(nucleo) * 80
    opc = [bool((l.get("site") or "").strip()), bool((l.get("telefone") or "").strip()), bool((l.get("horario") or "").strip()),
           bool(redes), any(i.get("status") == "aprovada" for i in imagens), bool(cardapios)]
    return round(pts + sum(opc) / len(opc) * 20)


def avaliar(l, flags, fam, imagens=(), redes=(), cardapios=(), possivel_duplicado=False, canonico=None, config=CONFIG) -> dict:
    c = confiabilidade(l, fam, flags, imagens, possivel_duplicado, config)
    grave = bool(GRAVES & set(flags))
    publicavel = canonico is None and not grave and c["score"] >= config["minimo_para_publicar"]
    return {"id": l["id"], "s": c["score"], "faixa": c["faixa"], "c": completude(l, redes, imagens, cardapios), "f": list(flags),
            "fam": sorted(fam), "p": publicavel, **({"dup_de": canonico} if canonico else {}), **({"pd": 1} if possivel_duplicado else {})}
