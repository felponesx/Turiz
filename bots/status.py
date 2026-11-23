"""Relatório de progresso dos bots, lido pelo painel do celular.

Cada bot usa `with bot("osm") as rep:` e chama `rep.progresso(feitos, total, atual=...)`, `rep.item("o que captou")`,
`rep.contar(novos=1)`. O Reporter guarda tudo num JSON (`status/<id>.json`) e, quando `TURIZ_STATUS_PUBLICAR=1` e há token do
GitHub, publica esse JSON no branch `bot-status` (a cada ~20 s e no fim). Falha de publicação NUNCA derruba o bot.

Segurança: tudo que vai para o JSON passa por `redigir` (chaves/tokens/e-mails viram ***), o branch é público.
Estados: rodando | concluido | avisos | erro | aguardando_credencial | aguardando_config | ocioso."""
import base64
import contextlib
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone

import httpx

from . import registry

BRANCH = "bot-status"
MAX_ITENS, MAX_LOG, MAX_AVISOS, MAX_HIST = 40, 80, 12, 12
_PADROES = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(api[_-]?key|apikey|token|secret|senha|password|authorization|bearer)\s*[=:]\s*\S+"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
]


def redigir(txt) -> str:
    t = str(txt)
    for p in _PADROES:
        t = p.sub("***", t)
    return t


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Pular(Exception):
    """Encerra o bot sem erro (ex.: falta credencial). O estado vira `estado` e o job continua verde."""

    def __init__(self, estado, mensagem):
        super().__init__(mensagem)
        self.estado, self.mensagem = estado, mensagem


def aguardar_credencial(*nomes):
    raise Pular("aguardando_credencial", "Falta o secret " + " e ".join(nomes) + " (GitHub: Settings → Secrets → Actions).")


class Publicador:
    """Publica arquivos JSON no branch `bot-status` pela API de conteúdo do GitHub."""

    def __init__(self, repo, token, client=None, branch=BRANCH):
        self.repo, self.branch = repo, branch
        self.c = client or httpx.Client(base_url="https://api.github.com", timeout=20)
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self._shas, self._pronto = {}, False

    def _req(self, metodo, caminho, **kw):
        return self.c.request(metodo, f"/repos/{self.repo}{caminho}", headers=self.h, **kw)

    def garantir_branch(self):
        if self._pronto:
            return
        r = self._req("GET", f"/git/ref/heads/{self.branch}")
        if r.status_code == 404:  # branch órfão só com status (não carrega o código nem os dados)
            t = self._req("POST", "/git/trees", json={"tree": [{"path": "status/LEIA-ME.txt", "mode": "100644", "type": "blob",
                                                                 "content": "Status dos bots do Turiz (gerado automaticamente; não edite).\n"}]})
            t.raise_for_status()
            cm = self._req("POST", "/git/commits", json={"message": "status: início", "tree": t.json()["sha"], "parents": []})
            cm.raise_for_status()
            self._req("POST", "/git/refs", json={"ref": f"refs/heads/{self.branch}", "sha": cm.json()["sha"]}).raise_for_status()
        else:
            r.raise_for_status()
        self._pronto = True

    def ler(self, caminho):
        r = self._req("GET", f"/contents/{caminho}", params={"ref": self.branch})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        d = r.json()
        self._shas[caminho] = d["sha"]
        return json.loads(base64.b64decode(d["content"]).decode("utf-8"))

    def gravar(self, caminho, dados, mensagem):
        self.garantir_branch()
        corpo = base64.b64encode(json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        for tentativa in range(2):
            payload = {"message": mensagem, "content": corpo, "branch": self.branch}
            if caminho in self._shas:
                payload["sha"] = self._shas[caminho]
            r = self._req("PUT", f"/contents/{caminho}", json=payload)
            if r.status_code in (409, 422) and tentativa == 0:  # sha desatualizado: busca de novo
                g = self._req("GET", f"/contents/{caminho}", params={"ref": self.branch})
                if g.status_code == 200:
                    self._shas[caminho] = g.json()["sha"]
                else:
                    self._shas.pop(caminho, None)
                continue
            r.raise_for_status()
            self._shas[caminho] = r.json()["content"]["sha"]
            return


class Reporter:
    def __init__(self, bot_id, publicador=None, pasta="status", intervalo=20, relogio=time.monotonic):
        meta = registry.por_id(bot_id) or {}
        self.id, self.pasta, self.intervalo, self._rel = bot_id, pasta, intervalo, relogio
        self.pub = publicador
        self.nome, self.descricao = meta.get("nome", bot_id), meta.get("descricao", "")
        self.estado, self.percentual, self.etapa, self.atual, self.mensagem = "ocioso", 0, "", "", ""
        self.feitos = self.total = 0
        self.contagem, self.totais, self.itens, self.log_, self.avisos, self.fontes = {}, {}, [], [], [], []
        self.iniciado_em = self.finalizado_em = self.ultimo_sucesso = ""
        self.historico = []
        self.run_url = ""
        self._faixa = (0, 100)
        self._ultimo_push = -1e9
        self._aviso_pub = False
        if os.getenv("GITHUB_RUN_ID") and os.getenv("GITHUB_REPOSITORY"):
            self.run_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

    # ---- ciclo de vida
    def iniciar(self):
        if self.pub:
            try:
                ant = self.pub.ler(f"status/{self.id}.json")
                if ant:
                    self.historico, self.ultimo_sucesso = ant.get("historico", []), ant.get("ultimo_sucesso", "")
                    self.totais = ant.get("totais", {})
            except Exception as exc:  # noqa: BLE001 - publicar é opcional
                self._avisar_pub(exc)
        self.estado, self.iniciado_em, self.finalizado_em, self.percentual = "rodando", agora(), "", 0
        self.log("início")
        self._salvar(forcar=True)

    def finalizar(self, estado="concluido", mensagem=""):
        if estado == "concluido" and self.avisos:
            estado = "avisos"
        self.estado, self.mensagem, self.finalizado_em, self.atual = estado, redigir(mensagem)[:300], agora(), ""
        if estado in ("concluido", "avisos"):
            self.percentual, self.ultimo_sucesso = 100, self.finalizado_em
        self.log(f"fim: {estado}" + (f" — {self.mensagem}" if self.mensagem else ""))
        self.historico = ([{"inicio": self.iniciado_em, "fim": self.finalizado_em, "estado": estado, "mensagem": self.mensagem[:140],
                            "contagem": dict(self.contagem), "run_url": self.run_url}] + self.historico)[:MAX_HIST]
        self._salvar(forcar=True)

    # ---- o que o bot informa
    @contextlib.contextmanager
    def faixa(self, de, ate):
        """Mapeia o progresso das etapas seguintes para de%..ate% do total (bots com várias etapas)."""
        ant, self._faixa = self._faixa, (de, ate)
        try:
            yield
        finally:
            self._faixa = ant

    def progresso(self, feitos, total, atual=None, etapa=None):
        self.feitos, self.total = feitos, total
        if atual is not None:
            self.atual = redigir(atual)[:140]
        if etapa is not None:
            self.etapa = redigir(etapa)[:80]
        if total and total > 0:
            de, ate = self._faixa
            pct = int(de + (ate - de) * min(feitos, total) / total)
            self.percentual = max(self.percentual, min(pct, 99))
        self._salvar()

    def contar(self, **kw):
        for k, v in kw.items():
            self.contagem[k] = self.contagem.get(k, 0) + v
        self._salvar()

    def definir(self, **kw):
        self.contagem.update(kw)
        self._salvar()

    def total_no_sistema(self, **kw):
        """Totais já guardados no sistema Turiz (aparecem na tela inicial)."""
        self.totais.update(kw)
        self._salvar()

    def item(self, texto):
        self.itens = ([{"t": agora(), "txt": redigir(texto)[:140]}] + self.itens)[:MAX_ITENS]
        self._salvar()

    def log(self, msg):
        for linha in str(msg).splitlines() or [""]:
            if linha.strip():
                self.log_ = (self.log_ + [{"t": agora(), "txt": redigir(linha)[:240]}])[-MAX_LOG:]

    def callback(self):
        """Função `progresso(feitos, total, atual="", itens=(), **contagem)` para passar às fontes."""
        def f(feitos, total, atual=None, itens=(), **conta):
            for i in itens:
                self.item(i)
            if conta:
                self.contar(**conta)
            self.progresso(feitos, total, atual=atual)
        return f

    def aviso(self, msg):
        self.avisos = (self.avisos + [redigir(msg)[:200]])[-MAX_AVISOS:]
        self.log(f"AVISO: {msg}")

    def fonte(self, slug, nome, estado, **info):
        """Sub-itens de um bot (ex.: cada fonte de eventos)."""
        novo = {"slug": slug, "nome": redigir(nome)[:80], "estado": estado, **{k: (redigir(v)[:160] if isinstance(v, str) else v) for k, v in info.items()}}
        self.fontes = [f for f in self.fontes if f["slug"] != slug] + [novo]
        self._salvar()

    # ---- saída
    def como_dict(self):
        return {"id": self.id, "nome": self.nome, "estado": self.estado, "percentual": self.percentual, "etapa": self.etapa, "atual": self.atual,
                "feitos": self.feitos, "total": self.total, "contagem": self.contagem, "totais": self.totais, "mensagem": self.mensagem,
                "itens": self.itens, "log": self.log_, "avisos": self.avisos, "fontes": self.fontes, "historico": self.historico,
                "iniciado_em": self.iniciado_em, "atualizado_em": agora(), "finalizado_em": self.finalizado_em,
                "ultimo_sucesso": self.ultimo_sucesso, "run_url": self.run_url}

    def _salvar(self, forcar=False):
        d = self.como_dict()
        try:
            os.makedirs(self.pasta, exist_ok=True)
            with open(os.path.join(self.pasta, f"{self.id}.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except OSError:
            pass
        if self.pub and (forcar or self._rel() - self._ultimo_push >= self.intervalo):
            self._ultimo_push = self._rel()
            try:
                self.pub.gravar(f"status/{self.id}.json", d, f"status: {self.id} {self.estado} {self.percentual}%")
            except Exception as exc:  # noqa: BLE001
                self._avisar_pub(exc)

    def batimento(self):
        """Renova `atualizado_em` sem mudar mais nada (o painel só chama de "sem sinal" quem para de bater)."""
        if self.estado == "rodando":
            try:
                self._salvar()
            except Exception:  # noqa: BLE001 - corrida inofensiva com a thread principal
                pass

    def _avisar_pub(self, exc):
        if not self._aviso_pub:
            self._aviso_pub = True
            print(f"[status] não foi possível publicar o status: {type(exc).__name__}", file=sys.__stderr__)


class _Tee:
    """Copia o que o bot imprime para o log do painel (já com segredos redigidos)."""

    def __init__(self, destino, rep):
        self.destino, self.rep, self.buf = destino, rep, ""

    def write(self, s):
        self.destino.write(s)
        self.buf += s
        while "\n" in self.buf:
            linha, self.buf = self.buf.split("\n", 1)
            if linha.strip():
                self.rep.log(linha)
        return len(s)

    def flush(self):
        self.destino.flush()

    def __getattr__(self, nome):
        return getattr(self.destino, nome)


def criar_publicador():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if os.getenv("TURIZ_STATUS_PUBLICAR") == "1" and token:
        repo = os.getenv("GITHUB_REPOSITORY") or os.getenv("TURIZ_STATUS_REPO") or "felponesx/Turiz"
        return Publicador(repo, token)
    return None


@contextlib.contextmanager
def bot(bot_id, publicador="auto", pasta="status", espelhar_saida=True, batimento_s=60, **kw):
    """Contexto de um bot: inicia, captura a saída, finaliza com o estado certo e propaga erros reais."""
    rep = Reporter(bot_id, criar_publicador() if publicador == "auto" else publicador, pasta=pasta, **kw)
    rep.iniciar()
    original = sys.stdout
    if espelhar_saida:
        sys.stdout = _Tee(original, rep)
    parar = threading.Event()
    if batimento_s:
        def bater():
            while not parar.wait(batimento_s):
                rep.batimento()
        threading.Thread(target=bater, daemon=True).start()
    try:
        yield rep
    except Pular as p:
        rep.finalizar(p.estado, p.mensagem)
    except KeyboardInterrupt:
        rep.finalizar("erro", "interrompido")
        raise
    except BaseException as exc:  # noqa: BLE001 - registra e repropaga
        if isinstance(exc, SystemExit) and not exc.code:
            rep.finalizar("avisos" if rep.avisos else "concluido")
        else:
            rep.finalizar("erro", f"{type(exc).__name__}: {exc}")
            raise
    else:
        rep.finalizar("concluido")
    finally:
        parar.set()
        sys.stdout = original
