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


def candidatos():
    c = []
    for m in meses(3):
        c += [("receita (arquivos) Estabelecimentos0", f"https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/{m}/Estabelecimentos0.zip"),
              ("receita (dadosabertos) Estabelecimentos0", f"https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/{m}/Estabelecimentos0.zip")]
    c += [("receita (pasta raiz, antigo)", "https://dadosabertos.rfb.gov.br/CNPJ/Estabelecimentos0.zip"),
          ("receita (nextcloud)", "https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9"),
          ("ibge CNEFE 2022 - SP", "https://ftp.ibge.gov.br/Censo_Demografico_2022/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/35_SP.zip"),
          ("ibge CNEFE 2022 - pasta", "https://ftp.ibge.gov.br/Censo_Demografico_2022/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/"),
          ("espelho casadosdados", "https://dados-abertos-rf-cnpj.casadosdados.com.br/"),
          ("brasilapi (lista de CNAE)", "https://brasilapi.com.br/api/cnae/v1/5611201")]
    return c


def mascarar(txt: str) -> str:
    return re.sub(r"\d", "#", txt)


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


def main():
    out = [f"# Sondagem de dados abertos\n\nGerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} (UTC). Amostras mascaradas (dígitos = #).\n",
           "| Fonte | Resultado | Tamanho | Observação |", "|---|---|---|---|"]
    detalhes = []
    cli = httpx.Client(timeout=40, headers={"User-Agent": UA}, follow_redirects=True,
                       transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1))
    for nome, url in candidatos():
        try:
            with cli.stream("GET", url, headers={"Range": "bytes=0-2000000"}) as r:
                tam = r.headers.get("content-range", "").split("/")[-1] or r.headers.get("content-length", "?")
                tipo = r.headers.get("content-type", "")[:40]
                ok = r.status_code in (200, 206)
                obs = f"HTTP {r.status_code}, {tipo}" + (", aceita Range" if r.status_code == 206 else "")
                if ok and url.endswith(".zip"):
                    info, erro = espiar_zip(r)
                    if info:
                        l = info["linhas"]
                        n = len(re.findall(r'"?;"?', l[0])) + 1 if l else 0
                        detalhes.append(f"### {nome}\n\n- URL: `{url}`\n- 1º arquivo do zip: `{info['arquivo']}`\n- colunas na 1ª linha (separador `;`): {n}\n"
                                        + "\n".join(f"- amostra: `{mascarar(x)[:300]}`" for x in l) + "\n")
                    else:
                        obs += f", {erro}"
                elif ok and "html" in tipo:
                    obs += ", html"
            out.append(f"| {nome} | {'ok' if ok else 'falhou'} | {tam} | {obs} |")
        except Exception as exc:
            out.append(f"| {nome} | inacessível | - | {type(exc).__name__}: {str(exc)[:70]} |")
    texto = "\n".join(out) + "\n\n" + "\n".join(detalhes)
    open("data/receita_sondagem.md", "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
