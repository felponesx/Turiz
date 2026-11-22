"""Sinais de fraude para XP, visitas, experiências, avaliações e recompensas. Funções puras (sem banco): quem chama passa o histórico.

Princípio: SINALIZAR e RETER, nunca banir sozinho. A única ação automática "dura" é recusar a MESMA nota fiscal duas vezes (certeza
matemática). Todo o resto vira 'revisar' ou 'reter XP' até uma pessoa decidir, para não punir usuário legítimo por falso positivo."""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

ACEITAR, RETER_XP, REVISAR, RECUSAR_DUPLICADA = "aceitar", "reter_xp", "revisar", "recusar_duplicada"


@dataclass
class Experiencia:
    usuario_id: int
    quando: datetime
    lugar_id: str
    lat: float | None = None
    lon: float | None = None
    hash_nota: str = ""
    dispositivo: str = ""        # hash do dispositivo/navegador


@dataclass
class Parecer:
    acao: str = ACEITAR
    pontos_risco: int = 0
    motivos: list[str] = field(default_factory=list)


def _km(a: Experiencia, b: Experiencia) -> float:
    R, r = 6371.0, math.pi / 180
    x, y = (b.lat - a.lat) * r, (b.lon - a.lon) * r
    h = math.sin(x / 2) ** 2 + math.cos(a.lat * r) * math.cos(b.lat * r) * math.sin(y / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def avaliar(nova: Experiencia, historico: list[Experiencia], outras_contas_no_dispositivo: int = 0, idade_conta: timedelta = timedelta(days=30)) -> Parecer:
    """historico: experiências anteriores da MESMA conta e, para o teste de nota, de TODAS as contas (o chamador decide o recorte)."""
    p = Parecer()
    if nova.hash_nota and any(h.hash_nota == nova.hash_nota for h in historico):
        return Parecer(RECUSAR_DUPLICADA, 100, ["mesma nota fiscal já usada"])
    meus = [h for h in historico if h.usuario_id == nova.usuario_id]

    def somar(pontos, motivo):
        p.pontos_risco += pontos
        p.motivos.append(motivo)

    dia = [h for h in meus if abs((nova.quando - h.quando).total_seconds()) < 86400]
    if len(dia) >= 5:
        somar(40, f"{len(dia) + 1} experiências em 24 h")
    mesmo_lugar = [h for h in meus if h.lugar_id == nova.lugar_id and (nova.quando - h.quando) < timedelta(hours=12)]
    if mesmo_lugar:
        somar(30, "mesmo lugar em menos de 12 h")
    if nova.lat is not None and meus:
        ultima = max((h for h in meus if h.lat is not None and h.quando <= nova.quando), key=lambda h: h.quando, default=None)
        if ultima:
            horas = max((nova.quando - ultima.quando).total_seconds() / 3600, 1e-6)
            kmh = _km(ultima, nova) / horas
            if kmh > 900:
                somar(60, f"deslocamento impossível ({kmh:.0f} km/h)")
    if outras_contas_no_dispositivo >= 3:
        somar(35, f"{outras_contas_no_dispositivo + 1} contas no mesmo dispositivo")
    if idade_conta < timedelta(hours=1) and len(meus) >= 2:
        somar(25, "conta muito nova com muita atividade")
    p.acao = REVISAR if p.pontos_risco >= 60 else RETER_XP if p.pontos_risco >= 30 else ACEITAR
    return p


def avaliacoes_em_massa(avaliacoes_do_lugar: list[tuple[int, datetime]], janela: timedelta = timedelta(hours=1), limite: int = 8) -> bool:
    """True se muitas avaliações do mesmo lugar chegaram numa janela curta (possível manipulação): vira revisão do lugar, não punição."""
    ts = sorted(t for _, t in avaliacoes_do_lugar)
    return any(ts[i + limite - 1] - ts[i] <= janela for i in range(len(ts) - limite + 1)) if len(ts) >= limite else False


def contas_em_massa(cadastros_por_ip_hash: list[datetime], janela: timedelta = timedelta(hours=1), limite: int = 5) -> bool:
    return avaliacoes_em_massa([(0, t) for t in cadastros_por_ip_hash], janela, limite)
