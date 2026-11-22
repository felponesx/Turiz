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
    imgs = [i for i in json.load(open("data/imagens.json", encoding="utf-8")) if i.get("status") == "aprovada"]
    os.makedirs(PASTA, exist_ok=True)
    indice_p = os.path.join(PASTA, "indice.json")
    indice = json.load(open(indice_p, encoding="utf-8")) if os.path.exists(indice_p) else {}
    ok = falhas = pulados = 0
    motivos = {}
    with httpx.Client(timeout=25, follow_redirects=True, transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1)) as c:
        for i in imgs[: a.limite]:
            arq = f"{i['id']}.jpg"
            url = re.sub(r"^http://", "https://", (i["url"] or "").strip()).replace(" ", "%20")
            if indice.get(str(i["id"]), {}).get("url") == url and os.path.exists(os.path.join(PASTA, arq)):
                pulados += 1
                continue
            ref = i.get("creditos_url") or ""
            ref = f"{urlparse(ref).scheme}://{urlparse(ref).netloc}/" if ref.startswith("http") else ""
            try:
                dados = miniatura(baixar(c, url, ref))
            except Exception as exc:
                falhas += 1
                k = type(exc).__name__ + (f" {exc.response.status_code}" if hasattr(exc, "response") and exc.response is not None else "")
                motivos[k] = motivos.get(k, 0) + 1
                continue
            open(os.path.join(PASTA, arq), "wb").write(dados)
            indice[str(i["id"])] = {"arquivo": arq, "url": url, "bytes": len(dados)}
            ok += 1
            time.sleep(0.3)
    json.dump(indice, open(indice_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"fotos: baixadas={ok} já_existiam={pulados} falhas={falhas} {motivos}")
    print(f"total no índice: {len(indice)} ({sum(v['bytes'] for v in indice.values())//1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
