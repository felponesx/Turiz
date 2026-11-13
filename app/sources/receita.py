"""Amplia a base de bares e restaurantes de São Paulo com os dados abertos da Receita Federal (CNPJ) + endereços do IBGE (CNEFE).

PRIVACIDADE (regra central deste módulo):
  * o CNPJ é usado só na MEMÓRIA, para ligar os arquivos da Receita entre si, e nunca é gravado: os registros de saída
    não têm campo de CNPJ, e `validar_privacidade` aborta se qualquer padrão de CNPJ/CPF/e-mail aparecer;
  * não usamos razão social (em MEI costuma conter o CPF da pessoa), e-mail, telefone (pode ser pessoal) nem sócios;
  * por padrão ficam de fora empresários individuais e MEIs: muitos funcionam na casa da própria pessoa, e o endereço
    seria o endereço residencial dela (`incluir_individuais=True` só para testes).
Guardamos apenas: nome fantasia, tipo, endereço comercial, bairro, CEP e a coordenada (IBGE CNEFE).

Fluxo: Estabelecimentos (filtro SP + CNAE 5611xxx + ativo) -> Empresas (natureza jurídica) -> Simples (MEI)
       -> CNEFE (CEP + número -> latitude/longitude) -> registros `Lugar` com fonte "receita".
"""
import csv
import hashlib
import io
import re
import zipfile
from math import cos, radians
import httpx

RECEITA = "https://arquivos.receitafederal.gov.br/public.php/webdav"
TOKEN = "YggdBLfdninEJX9"   # token do compartilhamento público oficial da Receita (não é segredo)
CNEFE_SP = ("https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/"
            "Arquivos_CNEFE/CSV/UF/35_SP.zip")
MUNICIPIO_SP_RFB = "7107"          # código da Receita para São Paulo
MUNICIPIO_SP_IBGE = "3550308"      # código do IBGE para São Paulo
CNAE_TIPO = {"5611201": ("restaurante", ""), "5611203": ("restaurante", "Lanchonete"),
             "5611202": ("bar", ""), "5611204": ("bar", ""), "5611205": ("bar", "")}
INDIVIDUAIS = {"2135"}             # natureza jurídica: Empresário (Individual)
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "na", "no", "para"}


def titulo(s: str) -> str:
    """'RUA AUGUSTA DO CENTRO' -> 'Rua Augusta do Centro'."""
    palavras = re.sub(r"\s+", " ", (s or "").strip()).lower().split(" ")
    return " ".join(p if (i and p in _MINUSCULAS) else p[:1].upper() + p[1:] for i, p in enumerate(palavras)).strip()


def cep_fmt(c: str) -> str:
    c = re.sub(r"\D", "", c or "")
    return f"{c[:5]}-{c[5:]}" if len(c) == 8 else ""


def _linhas_zip(caminho: str):
    """Linhas (bytes) do 1º arquivo de um .zip, em streaming (sem descompactar para o disco)."""
    z = zipfile.ZipFile(caminho)
    with z.open(z.namelist()[0]) as f:
        yield from f


def _campos(linha: bytes) -> list[str]:
    return next(csv.reader([linha.decode("latin-1")], delimiter=";", quotechar='"'))


def filtrar_estabelecimentos(caminho_zip: str) -> dict:
    """Estabelecimentos ativos de bares/restaurantes em São Paulo, com nome fantasia.
    Devolve {(basico, ordem): dados}. O CNPJ fica só como chave em memória."""
    achados = {}
    alvo = f';"SP";"{MUNICIPIO_SP_RFB}";'.encode()
    for linha in _linhas_zip(caminho_zip):
        if alvo not in linha:                       # filtro barato antes de interpretar o CSV
            continue
        c = _campos(linha)
        if len(c) < 20 or c[19] != "SP" or c[20] != MUNICIPIO_SP_RFB or c[5] != "02" or c[11] not in CNAE_TIPO:
            continue
        fantasia = c[4].strip()
        if not fantasia or re.search(r"\d{9,}", fantasia):   # sem nome comercial (ou nome com número de documento): descarta
            continue
        achados[(c[0], c[1])] = {"fantasia": fantasia, "cnae": c[11], "inicio": c[10][:4], "tipo_log": c[13], "logradouro": c[14],
                                 "numero": c[15], "bairro": c[17], "cep": c[18]}
    return achados


def anexar_natureza(caminho_zip: str, cands: dict) -> None:
    """Empresas: só a natureza jurídica. Razão social, capital etc. NÃO são lidos."""
    basicos = {k[0] for k in cands}
    nat = {}
    for linha in _linhas_zip(caminho_zip):
        b = linha[1:9].decode("latin-1")
        if b in basicos:
            c = _campos(linha)
            nat[b] = c[2]
    for (b, _), d in cands.items():
        if b in nat:
            d["natureza"] = nat[b]


def anexar_mei(caminho_zip: str, cands: dict) -> None:
    """Simples: marca MEI vigente (opção 'S' sem data de exclusão)."""
    basicos = {k[0] for k in cands}
    mei = set()
    for linha in _linhas_zip(caminho_zip):
        b = linha[1:9].decode("latin-1")
        if b in basicos:
            c = _campos(linha)
            if len(c) >= 7 and c[4] == "S" and c[6] in ("", "0", "00000000"):
                mei.add(b)
    for (b, _), d in cands.items():
        d["mei"] = b in mei


def _num(s: str):
    m = re.match(r"\s*(\d+)", s or "")
    return int(m.group(1)) if m else None


def indexar_cnefe(caminho_zip: str, ceps: set[str]):
    """CNEFE: para os CEPs pedidos, {(cep, numero): (lat, lon)} e {cep: (lat, lon)} (centro do CEP)."""
    z = zipfile.ZipFile(caminho_zip)
    pontos, por_cep = {}, {}
    with z.open(z.namelist()[0]) as f:
        txt = io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="")
        for r in csv.DictReader(txt, delimiter=";"):
            cep = r.get("CEP", "")
            if cep not in ceps or r.get("COD_MUNICIPIO") != MUNICIPIO_SP_IBGE:
                continue
            try:
                ll = (float(r["LATITUDE"]), float(r["LONGITUDE"]))
            except (KeyError, ValueError):
                continue
            n = _num(r.get("NUM_ENDERECO", ""))
            if n is not None:
                pontos.setdefault((cep, n), []).append(ll)
            por_cep.setdefault(cep, []).append(ll)
    media = lambda ps: (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
    return {k: media(v) for k, v in pontos.items()}, {k: media(v) for k, v in por_cep.items()}


def montar_registros(cands: dict, exato: dict, centro: dict, incluir_individuais: bool = False):
    """Candidatos -> registros `Lugar`. Sem CNPJ, sem razão social, sem telefone, sem e-mail. Retorna (registros, estatisticas)."""
    st = {"candidatos": len(cands), "individuais_excluidos": 0, "sem_coordenada": 0, "coord_exata": 0, "coord_aproximada": 0, "descartados_privacidade": 0}
    out, vistos = [], set()
    for d in cands.values():
        if not incluir_individuais and (d.get("natureza") in INDIVIDUAIS or d.get("mei")):
            st["individuais_excluidos"] += 1
            continue
        cep, n = d["cep"], _num(d["numero"])
        ll, aprox = (exato.get((cep, n)), False) if n is not None else (None, False)
        if ll is None:
            ll, aprox = centro.get(cep), True
        if ll is None:
            st["sem_coordenada"] += 1
            continue
        st["coord_aproximada" if aprox else "coord_exata"] += 1
        nome = titulo(d["fantasia"])
        rua = " ".join(x for x in (titulo(d["tipo_log"]), titulo(d["logradouro"])) if x)
        endereco = f"{rua}, {d['numero'].strip()}" if d["numero"].strip() and d["numero"].strip().upper() not in ("S/N", "SN") else rua
        fid = hashlib.sha1(f"{cep}|{n}|{nome.lower()}".encode()).hexdigest()[:16]   # derivado de dados públicos do endereço, NÃO do CNPJ
        if fid in vistos:
            continue
        vistos.add(fid)
        tipo, cul = CNAE_TIPO[d["cnae"]]
        reg = {"fonte": "receita", "fonte_id": fid, "tipo": tipo, "nome": nome, "culinaria": cul, "lat": round(ll[0], 6), "lon": round(ll[1], 6),
               "endereco": endereco, "bairro": titulo(d["bairro"]), "cep": cep_fmt(cep), "telefone": "", "site": "", "horario": "",
               "extra": {"cnae": d["cnae"], "inicio_atividade": d["inicio"], "coordenada_aproximada": aprox,
                         "origem": "Receita Federal (dados abertos) + IBGE CNEFE"}}
        if tem_dado_pessoal(reg):   # nome/endereço com '@', documento etc.: descarta o registro (e conta) em vez de derrubar a coleta
            st["descartados_privacidade"] += 1
            continue
        out.append(reg)
    return out, st


_PADROES = [("CNPJ", re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")),
            ("CPF", re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")),
            ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
            ("arroba (e-mail ou perfil)", re.compile(r"@")),
            ("número longo", re.compile(r"\d{9,}"))]


def validar_privacidade(registros: list[dict]) -> None:
    """Trava final: aborta (ValueError) se algum registro tiver CNPJ, CPF, e-mail ou número longo em QUALQUER campo."""
    chaves_proibidas = {"cnpj", "cnpj_basico", "razao_social", "email", "socios", "cpf"}
    for r in registros:
        achou = chaves_proibidas & {k.lower() for k in r} | chaves_proibidas & {k.lower() for k in (r.get("extra") or {})}
        if achou:
            raise ValueError(f"campo proibido no registro {r.get('fonte_id')}: {sorted(achou)}")
        # `fonte_id` é um hash hexadecimal do endereço (pode conter 10 dígitos seguidos por acaso): não entra na busca por números
        texto = " ".join(str(v) for k, v in r.items() if k not in ("fonte_id", "fonte") and not isinstance(v, (dict, float, int))) \
            + " " + " ".join(str(v) for v in (r.get("extra") or {}).values())
        for nome, rx in _PADROES:
            if nome == "número longo":
                texto_sem_cep = re.sub(r"\d{5}-\d{3}", "", texto)
                if rx.search(texto_sem_cep):
                    raise ValueError(f"número longo suspeito em {r.get('fonte_id')}")
            elif rx.search(texto):
                raise ValueError(f"possível {nome} no registro {r.get('fonte_id')}")


def tem_dado_pessoal(registro: dict) -> bool:
    try:
        validar_privacidade([registro])
        return False
    except ValueError:
        return True


def mesclar_com_osm(registros: list[dict], osm: list[dict]):
    """Remove da lista os que já existem no OSM (mesmo lugar: nome parecido e a menos de 60 m, ou mesmo CEP e nome quase igual).
    Devolve (novos, confirmados_do_osm: [fonte_id do OSM])."""
    from difflib import SequenceMatcher
    from .vincular import dist_m, norm
    grade = {}
    for l in osm:
        if l.get("lat") is not None:
            grade.setdefault((round(l["lat"], 3), round(l["lon"], 3)), []).append({**l, "_n": norm(l["nome"])})
    novos, confirmados = [], set()
    for r in registros:
        n = norm(r["nome"])
        casou = None
        for dx in (-0.001, 0, 0.001):
            for dy in (-0.001, 0, 0.001):
                for l in grade.get((round(r["lat"] + dx, 3), round(r["lon"] + dy, 3)), []):
                    sim = SequenceMatcher(None, n, l["_n"]).ratio()
                    d = dist_m(r["lat"], r["lon"], l["lat"], l["lon"])
                    if (d <= 60 and sim >= 0.6) or (r["cep"] and l.get("cep") == r["cep"] and sim >= 0.85):
                        casou = l
                        break
                if casou:
                    break
            if casou:
                break
        if casou:
            confirmados.add(casou["fonte_id"])
        else:
            novos.append(r)
    return novos, sorted(confirmados)


def baixar(url: str, destino: str, auth=None, timeout=600) -> int:
    """Baixa em streaming para o disco (IPv4). Retorna o tamanho em bytes."""
    total = 0
    cli = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "TurizBot/1.0 (+https://github.com/felponesx/Turiz)"},
                       transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=2))
    with cli.stream("GET", url, auth=auth) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for pedaco in r.iter_bytes(1 << 20):
                f.write(pedaco)
                total += len(pedaco)
    return total
