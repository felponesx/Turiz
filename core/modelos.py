"""Constantes e formas dos dados do Core."""
from datetime import datetime, timezone

TZ_PADRAO = "America/Sao_Paulo"
PRIORIDADES = ["critica", "alta", "normal", "baixa"]          # a ordem é o ranking (0 = mais urgente)
ESTADOS = ["criada", "aguardando", "programada", "executando", "em_revisao", "concluida", "concluida_parcial",
           "falhou", "pausada", "cancelada", "expirada"]
ATIVOS = {"criada", "aguardando", "programada", "executando", "pausada"}      # contam para evitar duplicatas
EM_ESPERA = {"aguardando", "programada"}
FINAIS = {"concluida", "concluida_parcial", "falhou", "cancelada", "expirada"}
ORIGENS = {"agenda", "manual", "dependencia", "retry", "painel", "descoberta"}
TIPOS = ["executar", "descobrir_estabelecimento", "pesquisar_perfil", "investigar_restaurante", "encontrar_endereco", "buscar_cardapio",
         "buscar_fotos", "encontrar_site", "encontrar_redes", "verificar_localizacao", "validar_registro", "identificar_duplicidade",
         "classificar_estabelecimento", "atualizar_registro", "buscar_eventos", "revisar_dados", "publicar_dados", "reprocessar_registro"]


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(s):
    if not s:
        return None
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def config_global_padrao():
    return {"pausado": False, "max_concorrencia": 1, "timezone": TZ_PADRAO, "ttl_espera_horas": 24, "retencao_dias": 14,
            "retry": {"base_s": 120, "teto_s": 3600, "jitter": 0.25}}


def config_bot_padrao(meta: dict | None = None) -> dict:
    """Configuração inicial de um bot. Os bots que já rodam por cron/cadeia nascem `gerenciado: false` (o Core não os agenda,
    para não duplicar execução); novos bots podem nascer gerenciados."""
    meta = meta or {}
    return {"ativo": True, "gerenciado": bool(meta.get("gerenciado", False)), "prioridade": meta.get("prioridade", "normal"),
            "agenda": meta.get("agenda_core") or {"tipo": "manual"}, "depende_de": list(meta.get("depende_de", [])),
            "max_tentativas": 3, "limites": {"max_minutos": int(meta.get("max_minutos", 180)), "lote": None},
            "parametros": {}, "regiao": None, "categorias": [], "reprocessar": "ignorar_existentes", "regras_revisao": {}}
