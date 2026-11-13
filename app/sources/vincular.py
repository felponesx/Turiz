"""Liga cada evento ao restaurante/bar onde acontece, por distância e semelhança de nome.

Conservador: prefere deixar sem vínculo a ligar ao lugar errado.
  com coordenadas: até 150 m do lugar e nome parecido (>= 0,6), ou até 40 m com nome minimamente parecido (>= 0,4);
  sem coordenadas: só nome praticamente idêntico (>= 0,92).
"""
import re
import unicodedata
from difflib import SequenceMatcher
from math import cos, hypot, radians
from sqlalchemy import select
from ..models import Evento, Lugar

_GENERICAS = re.compile(r"\b(bar|restaurante|casa|de|do|da|dos|das|e|the|cafe|pub|boteco|lanchonete)\b")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", _GENERICAS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", s))).strip()


def dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    k = 111_320
    return hypot((a_lat - b_lat) * k, (a_lon - b_lon) * k * cos(radians((a_lat + b_lat) / 2)))


def casar(ev: dict, lugares: list[dict]):
    """ev: {'local_nome','lat','lon'}; lugares: [{'fonte','fonte_id','nome','lat','lon','_n'}] -> lugar ou None."""
    n = norm(ev.get("local_nome", ""))
    if not n:
        return None
    melhor, melhor_score = None, 0.0
    tem_coord = ev.get("lat") is not None and ev.get("lon") is not None
    for l in lugares:
        sim = SequenceMatcher(None, n, l["_n"]).ratio()
        if tem_coord and l["lat"] is not None:
            d = dist_m(ev["lat"], ev["lon"], l["lat"], l["lon"])
            ok = (d <= 150 and sim >= 0.6) or (d <= 40 and sim >= 0.4)
        else:
            ok = sim >= 0.92
        if ok and sim > melhor_score:
            melhor, melhor_score = l, sim
    return melhor


def vincular_eventos(db) -> dict:
    lugares = [{"fonte": l.fonte, "fonte_id": l.fonte_id, "nome": l.nome, "lat": l.lat, "lon": l.lon, "_n": norm(l.nome)}
               for l in db.scalars(select(Lugar)) if norm(l.nome)]
    ligados = 0
    pendentes = list(db.scalars(select(Evento).where(Evento.lugar_fonte_id == "")))
    for e in pendentes:
        l = casar({"local_nome": e.local_nome, "lat": e.lat, "lon": e.lon}, lugares)
        if l:
            e.lugar_fonte, e.lugar_fonte_id = l["fonte"], l["fonte_id"]
            ligados += 1
    db.commit()
    return {"avaliados": len(pendentes), "vinculados": ligados}
