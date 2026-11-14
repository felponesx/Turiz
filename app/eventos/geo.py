"""Utilidades geográficas: distância e geohash (o Ticketmaster filtra por `geoPoint`, que é um geohash)."""
from math import asin, cos, radians, sin, sqrt

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def distancia_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * r * asin(sqrt(a))


def geohash(lat: float, lon: float, precisao: int = 9) -> str:
    """Codifica latitude/longitude em geohash (algoritmo padrão)."""
    lat_i, lon_i = [-90.0, 90.0], [-180.0, 180.0]
    h, bits, bit, par = "", 0, 0, True
    while len(h) < precisao:
        faixa, v = (lon_i, lon) if par else (lat_i, lat)
        meio = (faixa[0] + faixa[1]) / 2
        if v >= meio:
            bits = (bits << 1) | 1
            faixa[0] = meio
        else:
            bits <<= 1
            faixa[1] = meio
        par = not par
        bit += 1
        if bit == 5:
            h += _BASE32[bits]
            bits, bit = 0, 0
    return h
