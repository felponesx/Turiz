"""Base dos conectores: contrato, erros tipados e cliente HTTP seguro (limite de requisições, retentativas, sem vazar segredos)."""
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator
import httpx
from ..bruto import EventoBruto


class ErroFonte(Exception):
    """Falha de uma fonte. `status` vira o status do registro de coleta e a saúde da fonte."""
    status = "erro"


class SemCredencial(ErroFonte):
    status = "aguardando_credencial"


class CredencialInvalida(ErroFonte):
    status = "erro"


class FonteBloqueada(ErroFonte):
    """O site bloqueou o acesso ou exige autorização. Não contornamos: registramos e seguimos."""
    status = "bloqueada"


class LimiteExcedido(ErroFonte):
    status = "parcial"


_SEGREDO_URL = re.compile(r"(?i)\b(api[_-]?key|apikey|key|token|access_token|secret)=([^&\s'\"]+)")


def redigir(texto: str, segredos=()) -> str:
    """Troca valores de chaves/tokens por *** (em URLs de erro, mensagens e logs)."""
    t = _SEGREDO_URL.sub(lambda m: f"{m.group(1)}=***", str(texto))
    for s in segredos:
        if s:
            t = t.replace(s, "***")
    return t


@dataclass
class Estatisticas:
    paginas: int = 0
    requisicoes: int = 0
    erros: int = 0
    parcial: bool = False
    mensagem: str = ""
    quota_restante: int | None = None
    avisos: list = field(default_factory=list)


class Requisitor:
    """GET JSON com intervalo mínimo entre chamadas, retentativas com espera crescente e tratamento de limite (429)."""

    def __init__(self, client: httpx.Client | None = None, intervalo: float = 0.25, tentativas: int = 4, espera_base: float = 1.0,
                 espera_max: float = 60.0, segredos=(), stats: Estatisticas | None = None):
        self.client = client or cliente_http()
        self.intervalo, self.tentativas, self.espera_base, self.espera_max = intervalo, tentativas, espera_base, espera_max
        self.segredos, self.stats = tuple(segredos), stats or Estatisticas()
        self._ultimo = 0.0

    def _esperar_intervalo(self):
        falta = self.intervalo - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        ultimo = ""
        for i in range(self.tentativas):
            self._esperar_intervalo()
            self.stats.requisicoes += 1
            try:
                r = self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:                      # rede/timeout: tenta de novo
                ultimo = f"{type(exc).__name__}: {redigir(exc, self.segredos)}"
                self.stats.erros += 1
                time.sleep(min(self.espera_max, self.espera_base * 2 ** i))
                continue
            if r.status_code == 429:
                try:
                    espera = min(self.espera_max, float(r.headers.get("retry-after") or self.espera_base * 2 ** (i + 1)))
                except ValueError:
                    espera = self.espera_base * 2 ** (i + 1)
                ultimo = "limite de requisições (429)"
                self.stats.erros += 1
                time.sleep(espera)
                continue
            if r.status_code >= 500:
                ultimo = f"HTTP {r.status_code}"
                self.stats.erros += 1
                time.sleep(min(self.espera_max, self.espera_base * 2 ** i))
                continue
            restante = r.headers.get("rate-limit-available")
            if restante and restante.isdigit():
                self.stats.quota_restante = int(restante)
            if r.status_code in (401, 407):
                raise CredencialInvalida(f"credencial recusada (HTTP {r.status_code})")
            if r.status_code == 403:
                raise FonteBloqueada("acesso negado (HTTP 403)")
            if r.status_code >= 400:
                raise ErroFonte(f"HTTP {r.status_code}")
            try:
                return r.json()
            except ValueError:
                raise ErroFonte("resposta que não é JSON")
        if "429" in ultimo:
            raise LimiteExcedido(f"limite de requisições persistente: {ultimo}")
        raise ErroFonte(f"fonte indisponível após {self.tentativas} tentativas: {ultimo}")


def cliente_http(timeout: float = 30.0) -> httpx.Client:
    """IPv4 (o runner do Actions não tem IPv6) e User-Agent identificável."""
    return httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "TurizEventosBot/1.0 (+https://github.com/felponesx/Turiz)"},
                        transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1))


@dataclass
class Contexto:
    slug: str
    config: dict
    requisitor: Requisitor
    stats: Estatisticas
    agora: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    limite: int | None = None      # máximo de eventos a devolver (testes/amostras)


class Conector(ABC):
    tipo = ""                       # ticketmaster | jsonld | feed_json | feed_xml | rss | navegador | planilha
    descricao = ""
    requer_credencial = False

    def credencial_ok(self, config: dict) -> bool:
        return True

    @abstractmethod
    def coletar(self, ctx: Contexto) -> Iterator[EventoBruto]:
        ...


REGISTRO: dict[str, type[Conector]] = {}


def registrar(cls):
    REGISTRO[cls.tipo] = cls
    return cls
