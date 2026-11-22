#!/usr/bin/env python3
"""Fotos ILUSTRATIVAS (modo de exemplo do protótipo) vindas do Wikimedia Commons, com autor e licença livres.
Servem para preencher os blocos sem foto real enquanto os dados de exemplo estão ligados; o app as marca como "foto ilustrativa".
Saída: data/fotos_exemplo/<tema>-<n>.jpg + indice.json. Uso: python coletar_fotos_exemplo.py [--por-tema 6]"""
import argparse, io, json, os, re, time
import httpx
from PIL import Image, ImageOps

API = "https://commons.wikimedia.org/w/api.php"
UA = "TurizFotosExemplo/1.0 (https://github.com/felponesx/Turiz)"
PASTA = "data/fotos_exemplo"
LIVRES = re.compile(r"^(CC0|CC BY(-SA)?( \d\.\d)?|Public domain|PD|Attribution)", re.I)
# tema -> buscas no Commons (pt/en). O app escolhe o tema pela culinária/tipo do lugar ou pela categoria do evento.
TEMAS = {
    "restaurante": ["restaurant interior São Paulo", "restaurant dining room"],
    "bar": ["bar São Paulo boteco", "bar counter drinks"],
    "lanchonete": ["lanchonete Brasil", "coxinha salgado"],
    "hamburguer": ["hamburger burger"],
    "pizzaria": ["pizza margherita", "pizzeria"],
    "japonesa": ["sushi platter", "japanese restaurant sushi"],
    "cafeteria": ["coffee cappuccino cafe", "café coffee shop"],
    "padaria": ["padaria pão francês", "bakery bread"],
    "churrasco": ["churrasco picanha", "churrascaria"],
    "brasileira": ["feijoada", "prato feito arroz feijão"],
    "italiana": ["pasta spaghetti dish", "lasagna"],
    "arabe": ["esfiha", "kebab shawarma"],
    "doces": ["brigadeiro", "cake dessert"],
    "acai": ["açaí bowl"],
    "pastel": ["pastel de feira"],
    "sorveteria": ["ice cream gelato"],
    "show": ["concert stage crowd", "live music band stage"],
    "festa": ["party dance floor", "nightclub dj"],
    "gastronomia_evento": ["food festival", "street food market"],
    "cultura": ["museum exhibition", "theatre stage"],
}


def buscar(client, termo, n):
    p = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{termo} filetype:bitmap",
         "gsrlimit": n * 3, "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 640}
    r = client.get(API, params=p)
    r.raise_for_status()
    pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 0))
    for pg in pages:
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        lic = (md.get("LicenseShortName") or {}).get("value", "")
        if not LIVRES.match(lic) or ii.get("width", 0) < 500:
            continue
        autor = re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", "")).strip()[:120]
        yield {"thumb": ii.get("thumburl") or ii.get("url"), "pagina": ii.get("descriptionurl", ""), "licenca": lic, "autor": autor or "Wikimedia Commons"}


def miniatura(b):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(b))).convert("RGB")
    w, h = im.size
    alvo = 16 / 10                       # recorte 16:10, igual aos cards
    if w / h > alvo:
        nw = int(h * alvo); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / alvo); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im.thumbnail((640, 400))
    o = io.BytesIO(); im.save(o, "JPEG", quality=70, optimize=True, progressive=True)
    return o.getvalue()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--por-tema", type=int, default=5); a = ap.parse_args()
    os.makedirs(PASTA, exist_ok=True)
    indice, stats = {}, {}
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": UA}) as c:
        for tema, termos in TEMAS.items():
            lista, vistos = [], set()
            for t in termos:
                try:
                    for f in buscar(c, t, a.por_tema):
                        if len(lista) >= a.por_tema or f["pagina"] in vistos:
                            break
                        try:
                            b = c.get(f["thumb"]); b.raise_for_status()
                            arq = f"{tema}-{len(lista)+1}.jpg"
                            open(os.path.join(PASTA, arq), "wb").write(miniatura(b.content))
                            vistos.add(f["pagina"]); lista.append({**f, "arquivo": arq})
                        except Exception:
                            pass
                        time.sleep(0.4)
                except Exception as exc:
                    print(f"::warning::{tema}/{t}: {type(exc).__name__}")
                if len(lista) >= a.por_tema:
                    break
            indice[tema] = lista; stats[tema] = len(lista)
    json.dump(indice, open(os.path.join(PASTA, "indice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("fotos ilustrativas por tema:", stats, "total:", sum(stats.values()))


if __name__ == "__main__":
    main()
