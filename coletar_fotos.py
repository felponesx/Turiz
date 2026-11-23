#!/usr/bin/env python3
"""Baixa as fotos APROVADAS (data/imagens.json) e guarda miniaturas locais em data/fotos/<id>.jpg (máx. 640 px, JPEG).
Motivo: a página do app não pode depender do site de cada estabelecimento (bloqueio de hotlink, https, CSP). Decisão do dono do projeto:
usar as fotos mesmo antes da autorização formal de uso de imagem (veja politicas.yml). Créditos continuam em imagens.json.
Sem dados pessoais. Uso: python coletar_fotos.py [--limite N]"""
import argparse
import io
import json
import os
import re
import sys
import time
from urllib.parse import urlparse
import httpx
from PIL import Image, ImageOps
from bots.status import bot

PASTA = "data/fotos"
UA = "Mozilla/5.0 (compatible; TurizFotosBot/1.0; +https://github.com/felponesx/Turiz)"


def baixar(client, url, referer):
    h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
    if referer:
        h["Referer"] = referer
    r = client.get(url, headers=h)
    r.raise_for_status()
    if len(r.content) > 12_000_000:
        raise ValueError("arquivo grande demais")
    return r.content


def miniatura(dados: bytes) -> bytes:
    im = Image.open(io.BytesIO(dados))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        fundo.paste(im, mask=im.split()[-1])
        im = fundo
    else:
        im = im.convert("RGB")
    im.thumbnail((640, 640))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=72, optimize=True, progressive=True)
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int)
    a = ap.parse_args()
    with bot("fotos") as rep:
        return _executar(a, rep)


def _executar(a, rep):
    import gzip
    imgs = [i for i in json.load(open("data/imagens.json", encoding="utf-8")) if i.get("status") == "aprovada"]
    snap = "data/eventos_v2.json.gz"
    evs = json.load(gzip.open(snap, "rt", encoding="utf-8"))["eventos"] if os.path.exists(snap) else []
    alvo_total = len(imgs[: a.limite]) + len(evs)
    feitas = 0
    rep.definir(para_processar=alvo_total)
    os.makedirs(PASTA, exist_ok=True)
    indice_p = os.path.join(PASTA, "indice.json")
    indice = json.load(open(indice_p, encoding="utf-8")) if os.path.exists(indice_p) else {}
    ok = falhas = pulados = 0
    motivos = {}
    with httpx.Client(timeout=25, follow_redirects=True, transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1)) as c:  # nosec B104 - é o endereço LOCAL de saída (força IPv4), não um servidor escutando
        for i in imgs[: a.limite]:
            feitas += 1
            rep.progresso(feitas, alvo_total, atual=f"Foto de lugar {i['id']}")
            arq = f"{i['id']}.jpg"
            url = re.sub(r"^http://", "https://", (i["url"] or "").strip()).replace(" ", "%20")
            if indice.get(str(i["id"]), {}).get("url") == url and os.path.exists(os.path.join(PASTA, arq)):
                pulados += 1
                rep.contar(ja_existiam=1)
                continue
            ref = i.get("creditos_url") or ""
            ref = f"{urlparse(ref).scheme}://{urlparse(ref).netloc}/" if ref.startswith("http") else ""
            try:
                dados = miniatura(baixar(c, url, ref))
            except Exception as exc:
                falhas += 1
                k = type(exc).__name__ + (f" {exc.response.status_code}" if hasattr(exc, "response") and exc.response is not None else "")
                motivos[k] = motivos.get(k, 0) + 1
                rep.contar(falhas=1)
                continue
            open(os.path.join(PASTA, arq), "wb").write(dados)
            indice[str(i["id"])] = {"arquivo": arq, "url": url, "bytes": len(dados)}
            ok += 1
            rep.contar(baixadas=1)
            rep.item(f"miniatura {arq} ({len(dados)//1024} KB)")
            time.sleep(0.3)
        # imagens dos eventos (snapshot v2): ev-<id>.jpg
        for e in evs:
            feitas += 1
            rep.progresso(feitas, alvo_total, atual=f"Foto do evento {(e.get('nome') or e['id'])}")
            url = re.sub(r"^http://", "https://", (e.get("imagem_url") or "").strip()).replace(" ", "%20")
            if not url.startswith("https://"):
                continue
            chave, arq = f"ev-{e['id']}", f"ev-{e['id']}.jpg"
            if indice.get(chave, {}).get("url") == url and os.path.exists(os.path.join(PASTA, arq)):
                pulados += 1
                rep.contar(ja_existiam=1)
                continue
            ref = e.get("url") or ""
            ref = f"{urlparse(ref).scheme}://{urlparse(ref).netloc}/" if ref.startswith("http") else ""
            try:
                dados = miniatura(baixar(c, url, ref))
            except Exception as exc:
                falhas += 1
                k = "evento " + type(exc).__name__
                motivos[k] = motivos.get(k, 0) + 1
                rep.contar(falhas=1)
                continue
            open(os.path.join(PASTA, arq), "wb").write(dados)
            indice[chave] = {"arquivo": arq, "url": url, "bytes": len(dados)}
            ok += 1
            rep.contar(baixadas=1)
            rep.item(f"miniatura {arq} ({len(dados)//1024} KB)")
            time.sleep(0.3)
    json.dump(indice, open(indice_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"fotos: baixadas={ok} já_existiam={pulados} falhas={falhas} {motivos}")
    print(f"total no índice: {len(indice)} ({sum(v['bytes'] for v in indice.values())//1024} KB)")
    rep.total_no_sistema(fotos=len(indice), tamanho_kb=sum(v["bytes"] for v in indice.values()) // 1024)


if __name__ == "__main__":
    sys.exit(main())
