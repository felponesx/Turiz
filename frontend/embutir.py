"""Converte uma imagem local em data URI JPEG compacta (para caber no limite do artefato)."""
import base64, io
from PIL import Image

def data_uri(caminho, maxw=480, maxh=360, q=62):
    im = Image.open(caminho).convert("RGB")
    im.thumbnail((maxw, maxh))
    o = io.BytesIO(); im.save(o, "JPEG", quality=q, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(o.getvalue()).decode()
