#!/usr/bin/env python3
"""Sondagem (sem coletar) das fontes de dados abertos para ampliar a base: Receita Federal (CNPJ) e IBGE (CNEFE).

PRIVACIDADE: os logs do Actions são públicos. Este script NUNCA imprime linhas reais: só o número de colunas
e uma amostra com todos os dígitos trocados por '#'. Gera data/receita_sondagem.md."""
import re
import zlib
from datetime import date, datetime, timezone
import httpx

UA = "TurizBot/1.0 (+https://github.com/felponesx/Turiz; sondagem de dados abertos)"


def meses(n=3):
    h = date.today()
    for i in range(n):
        m = h.month - i
        y = h.year + (m - 1) // 12
        yield f"{y}-{(m - 1) % 12 + 1:02d}"


RECEITA = "https://arquivos.receitafederal.gov.br/public.php/webdav"
TOKEN = "YggdBLfdninEJX9"
IBGE_SP = "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/35_SP.zip"


def ultima_pasta(cli) -> str:
    pastas = sorted(h for h, _ in webdav(cli, "https://arquivos.receitafederal.gov.br", TOKEN) if h.endswith("/") and h[:4].isdigit())
    return pastas[-1].rstrip("/")


def candidatos(mes: str):
    """(nome, url, auth): Estrutura de cada arquivo que o pipeline vai ler."""
    return [("Receita: Estabelecimentos0", f"{RECEITA}/{mes}/Estabelecimentos0.zip", (TOKEN, "")),
            ("Receita: Empresas0", f"{RECEITA}/{mes}/Empresas0.zip", (TOKEN, "")),
            ("Receita: Simples", f"{RECEITA}/{mes}/Simples.zip", (TOKEN, "")),
            ("IBGE: CNEFE 2022 - SP", IBGE_SP, None)]


def referencias(cli, mes: str) -> str:
    """Tabelas de referência pequenas e públicas (códigos), para achar o código de São Paulo e os CNAEs de bares/restaurantes."""
    import io
    import zipfile
    out = ["\n## Tabelas de referência\n"]
    for arq, filtro in (("Municipios.zip", "SAO PAULO"), ("Cnaes.zip", "5611")):
        r = httpx.get(f"{RECEITA}/{mes}/{arq}", auth=(TOKEN, ""), timeout=60, headers={"User-Agent": UA})
        z = zipfile.ZipFile(io.BytesIO(r.content))
        linhas = z.read(z.namelist()[0]).decode("latin-1").splitlines()
        achados = [l for l in linhas if filtro in l.upper()]
        out.append(f"### {arq} (linhas com '{filtro}')\n\n" + "\n".join(f"- `{l}`" for l in achados[:12]) + "\n")
    return "\n".join(out)


def mascarar(txt: str) -> str:
    """Só a forma do dado: dígitos viram #, letras viram x (nada real vai para o log público)."""
    return re.sub(r"[A-Za-zÀ-ÿ]", "x", re.sub(r"\d", "#", txt))


def espiar_zip(r: httpx.Response, nlinhas=2, limite=2_000_000):
    """Lê o início do 1º arquivo de um .zip (deflate) em streaming e devolve as primeiras linhas, já mascaradas."""
    buf = b""
    for pedaco in r.iter_raw():
        buf += pedaco
        if len(buf) >= limite:
            break
    if buf[:4] != b"PK\x03\x04":
        return None, "não é zip"
    nome_len, extra_len = int.from_bytes(buf[26:28], "little"), int.from_bytes(buf[28:30], "little")
    metodo = int.from_bytes(buf[8:10], "little")
    dados = buf[30 + nome_len + extra_len:]
    nome = buf[30:30 + nome_len].decode("latin-1")
    texto = zlib.decompressobj(-15).decompress(dados, 400_000) if metodo == 8 else dados[:400_000]
    linhas = texto.decode("latin-1", "replace").splitlines()[:nlinhas]
    return {"arquivo": nome, "linhas": linhas}, ""


def links(cli, url, n=60):
    """Nomes dos links de uma página de listagem (autoindex/HTML). Só nomes de arquivos/pastas públicos."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    r = cli.get(url)
    if r.status_code != 200:
        return [f"HTTP {r.status_code}"]
    nomes = []
    for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
        h = a["href"]
        if h.startswith(("?", "#", "/", "..", "http")) and not h.startswith(("http",)):
            continue
        nomes.append(urljoin(url, h))
    return nomes[:n]


def webdav(cli, base, token, caminho=""):
    """PROPFIND em um compartilhamento público do Nextcloud (usuário = token, senha vazia) -> [(caminho, bytes|None)]."""
    import xml.etree.ElementTree as ET
    r = cli.request("PROPFIND", f"{base}/public.php/webdav/{caminho}", auth=(token, ""), headers={"Depth": "1"})
    if r.status_code not in (200, 207):
        return [(f"HTTP {r.status_code}", None)]
    ns = {"d": "DAV:"}
    out = []
    for resp in ET.fromstring(r.content).findall("d:response", ns):
        h = resp.findtext("d:href", "", ns).replace("/public.php/webdav/", "")
        t = resp.findtext(".//d:getcontentlength", None, ns)
        out.append((h, int(t) if t else None))
    return out


def descobrir(cli):
    sec = ["\n## Descoberta de caminhos (listagens públicas)\n"]
    def bloco(titulo, linhas):
        sec.append(f"### {titulo}\n\n" + "\n".join(f"- `{x}`" for x in linhas) + "\n")
    for url in ("https://ftp.ibge.gov.br/", "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/",
                "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/",
                "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/",
                "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/"):
        try:
            bloco(f"IBGE: {url.removeprefix('https://ftp.ibge.gov.br')}", links(cli, url, n=45))
        except Exception as exc:
            bloco(f"IBGE: {url}", [f"{type(exc).__name__}: {exc}"[:120]])
    try:
        base, tok = "https://arquivos.receitafederal.gov.br", "YggdBLfdninEJX9"
        raiz = [h for h, _ in webdav(cli, base, tok) if h.rstrip("/")]
        pastas = sorted(h for h in raiz if h.endswith("/"))
        bloco("Receita (Nextcloud): pastas mensais mais recentes", pastas[-6:])
        ult = pastas[-1]
        arqs = webdav(cli, base, tok, ult)
        bloco(f"Receita: arquivos em {ult}", [f"{h} ({(t or 0) / 1e6:.0f} MB)" for h, t in arqs if t is not None])
    except Exception as exc:
        bloco("Receita (Nextcloud)", [f"{type(exc).__name__}: {exc}"[:120]])
    return "\n".join(sec)


def main():
    out = [f"# Sondagem de dados abertos\n\nGerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} (UTC). Amostras sem dados reais (dígitos=#, letras=x).\n",
           "| Fonte | Resultado | Tamanho | Observação |", "|---|---|---|---|"]
    detalhes = []
    cli = httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=True,
                       transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1))
    mes = ultima_pasta(cli)
    out.insert(2, f"Pasta mais recente da Receita: **{mes}**\n")
    for nome, url, auth in candidatos(mes):
        try:
            with cli.stream("GET", url, auth=auth, headers={"Range": "bytes=0-3000000"}) as r:
                tam = r.headers.get("content-range", "").split("/")[-1] or r.headers.get("content-length", "?")
                ok = r.status_code in (200, 206)
                obs = f"HTTP {r.status_code}" + (", aceita Range" if r.status_code == 206 else "")
                if ok:
                    info, erro = espiar_zip(r)
                    if info:
                        l = info["linhas"]
                        sep = ";" if l and l[0].count(";") >= l[0].count(",") else ","
                        n = (l[0].count(sep) + 1) if l else 0
                        cab = l[0] if nome.startswith("IBGE") else ""   # o cabeçalho do IBGE só tem nomes de colunas
                        detalhes.append(f"### {nome}\n\n- 1º arquivo do zip: `{info['arquivo']}`\n- colunas (separador `{sep}`): {n}\n"
                                        + (f"- cabeçalho: `{cab}`\n" if cab else "")
                                        + "\n".join(f"- forma da linha {i}: `{mascarar(x)[:260]}`" for i, x in enumerate(l)) + "\n")
                    else:
                        obs += f", {erro}"
            out.append(f"| {nome} | {'ok' if ok else 'falhou'} | {tam} | {obs} |")
        except Exception as exc:
            out.append(f"| {nome} | inacessível | - | {type(exc).__name__}: {str(exc)[:70]} |")
    try:
        ref = referencias(cli, mes)
    except Exception as exc:
        ref = f"\n(referências falharam: {type(exc).__name__}: {str(exc)[:80]})\n"
    texto = "\n".join(out) + "\n\n" + "\n".join(detalhes) + ref
    open("data/receita_sondagem.md", "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
