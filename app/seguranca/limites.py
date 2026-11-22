"""Limite de requisições (janela deslizante) com bloqueio PROGRESSIVO e temporário (nunca permanente).

Em memória, por processo: protege a aplicação e testes; atrás de vários processos/servidores o limite global deve ser feito
também na borda (CDN/WAF) — veja docs/seguranca/infraestrutura.md."""
import threading
import time
from collections import defaultdict, deque


class Limitador:
    def __init__(self, maximo: int, janela_s: int, bloqueio_base_s: int = 30, bloqueio_max_s: int = 900):
        self.maximo, self.janela, self.base, self.teto = maximo, janela_s, bloqueio_base_s, bloqueio_max_s
        self._h: dict[str, deque] = defaultdict(deque)
        self._ban: dict[str, tuple[float, int]] = {}        # chave -> (até quando, nº de reincidências)
        self._lock = threading.Lock()

    def reiniciar(self):
        with self._lock:
            self._h.clear(); self._ban.clear()

    def verificar(self, chave: str, agora: float | None = None) -> tuple[bool, int]:
        """-> (permitido, segundos até poder tentar de novo). Conta a tentativa quando permitida."""
        agora = agora if agora is not None else time.monotonic()
        with self._lock:
            ate, reinc = self._ban.get(chave, (0.0, 0))
            if ate > agora:
                return False, int(ate - agora) + 1
            h = self._h[chave]
            while h and agora - h[0] > self.janela:
                h.popleft()
            if len(h) >= self.maximo:
                reinc += 1                                       # reincidente: espera dobra a cada vez, até o teto
                espera = min(self.teto, self.base * 2 ** (reinc - 1))
                self._ban[chave] = (agora + espera, reinc)
                h.clear()
                return False, int(espera)
            h.append(agora)
            if reinc and not h:                                  # comportamento normal depois de um tempo zera a reincidência
                self._ban.pop(chave, None)
            self._limpar(agora)
            return True, 0

    def _limpar(self, agora: float):
        if len(self._h) > 20000:
            for k in [k for k, v in self._h.items() if not v or agora - v[-1] > self.janela][:10000]:
                self._h.pop(k, None)
        if len(self._ban) > 20000:
            for k in [k for k, (ate, _) in self._ban.items() if ate < agora - 3600][:10000]:
                self._ban.pop(k, None)

    def bloqueado(self, chave: str, agora: float | None = None) -> int:
        """Segundos restantes de bloqueio (0 = livre). Só consulta, não conta tentativa."""
        agora = agora if agora is not None else time.monotonic()
        with self._lock:
            ate, _ = self._ban.get(chave, (0.0, 0))
            return int(ate - agora) + 1 if ate > agora else 0

    def registrar_sucesso(self, chave: str):
        """Depois de uma operação legítima, perdoa a reincidência acumulada."""
        with self._lock:
            self._ban.pop(chave, None)


def _env_int(nome, padrao):
    import os
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


# classes de rota (valores por minuto, ajustáveis por variável de ambiente)
LEITURA = Limitador(_env_int("TURIZ_LIM_LEITURA", 240), 60)
CARA = Limitador(_env_int("TURIZ_LIM_CARA", 30), 60)               # buscas, mapa inteiro, listas grandes
ESCRITA = Limitador(_env_int("TURIZ_LIM_ESCRITA", 60), 60)
AUTH_FALHA = Limitador(_env_int("TURIZ_LIM_AUTH_FALHA", 8), 600, 60, 3600)   # chave/senha errada
LOGIN_CONTA = Limitador(_env_int("TURIZ_LIM_LOGIN_CONTA", 6), 600, 60, 1800)  # por conta (e-mail pseudonimizado)
CADASTRO = Limitador(_env_int("TURIZ_LIM_CADASTRO", 5), 3600, 120, 3600)
RECUPERACAO = Limitador(_env_int("TURIZ_LIM_RECUPERACAO", 5), 3600, 120, 3600)
UPLOAD = Limitador(_env_int("TURIZ_LIM_UPLOAD", 20), 3600, 60, 3600)
TODOS = (LEITURA, CARA, ESCRITA, AUTH_FALHA, LOGIN_CONTA, CADASTRO, RECUPERACAO, UPLOAD)


def reiniciar_todos():
    for l in TODOS:
        l.reiniciar()


# rotas caras: o custo está na consulta, não no verbo HTTP
ROTAS_CARAS = ("/lugares/geo", "/eventos/busca")


def classe_da_rota(metodo: str, caminho: str, tem_busca: bool) -> Limitador:
    if metodo in ("POST", "PUT", "PATCH", "DELETE"):
        return ESCRITA
    if caminho in ROTAS_CARAS or tem_busca:
        return CARA
    return LEITURA
