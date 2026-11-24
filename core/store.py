"""Armazenamento do estado do Core: arquivos JSON versionados com concorrência otimista (sha), em disco (testes/local)
ou no branch órfão `bot-control` do repositório (produção). Mudou no meio do caminho => Conflito => relê e refaz."""
import base64
import hashlib
import json
import os

import httpx

BRANCH = "bot-control"


class Conflito(Exception):
    pass


def atualizar(store, caminho: str, fn, padrao, mensagem: str, tentativas: int = 6):
    """Lê-modifica-grava com retry em caso de conflito. `fn(dados)` recebe o conteúdo atual (ou `padrao()`), altera/retorna.
    Não grava se nada mudou. Retorna o conteúdo final."""
    for _ in range(tentativas):
        atual, versao = store.ler(caminho)
        dados = atual if atual is not None else padrao()
        antes = json.dumps(dados, sort_keys=True, ensure_ascii=False)
        novo = fn(dados)
        novo = dados if novo is None else novo
        if atual is not None and json.dumps(novo, sort_keys=True, ensure_ascii=False) == antes:
            return novo
        try:
            store.gravar(caminho, novo, versao, mensagem)
            return novo
        except Conflito:
            continue
    raise Conflito(f"não consegui gravar {caminho} após {tentativas} tentativas")


class ArquivoStore:
    def __init__(self, pasta: str):
        self.pasta = pasta

    def _p(self, caminho):
        return os.path.join(self.pasta, caminho)

    def ler(self, caminho):
        p = self._p(caminho)
        if not os.path.exists(p):
            return None, None
        raw = open(p, "rb").read()
        return json.loads(raw.decode("utf-8")), hashlib.sha1(raw, usedforsecurity=False).hexdigest()

    def gravar(self, caminho, dados, versao, mensagem=""):
        atual = self.ler(caminho)[1]
        if atual != versao:
            raise Conflito(caminho)
        p = self._p(caminho)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(json.dumps(dados, ensure_ascii=False, indent=1))


class GitHubStore:
    """Arquivos em `control/` no branch `bot-control` (criado órfão: sem código nem dados, só o estado do Core)."""

    def __init__(self, repo: str, token: str, client=None, branch: str = BRANCH):
        self.repo, self.branch = repo, branch
        self.c = client or httpx.Client(base_url="https://api.github.com", timeout=30)
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self._pronto = False

    def _req(self, metodo, caminho, **kw):
        return self.c.request(metodo, f"/repos/{self.repo}{caminho}", headers=self.h, **kw)

    def garantir_branch(self):
        if self._pronto:
            return
        r = self._req("GET", f"/git/ref/heads/{self.branch}")
        if r.status_code == 404:
            t = self._req("POST", "/git/trees", json={"tree": [{"path": "control/LEIA-ME.txt", "mode": "100644", "type": "blob",
                                                                 "content": "Estado do Core do TURIZ (gerado automaticamente; edite pelo painel).\n"}]})
            t.raise_for_status()
            cm = self._req("POST", "/git/commits", json={"message": "core: início", "tree": t.json()["sha"], "parents": []})
            cm.raise_for_status()
            self._req("POST", "/git/refs", json={"ref": f"refs/heads/{self.branch}", "sha": cm.json()["sha"]}).raise_for_status()
        else:
            r.raise_for_status()
        self._pronto = True

    def ler(self, caminho):
        r = self._req("GET", f"/contents/{caminho}", params={"ref": self.branch})
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        d = r.json()
        return json.loads(base64.b64decode(d["content"]).decode("utf-8")), d["sha"]

    def gravar(self, caminho, dados, versao, mensagem=""):
        self.garantir_branch()
        corpo = {"message": mensagem or f"core: {caminho}", "branch": self.branch,
                 "content": base64.b64encode(json.dumps(dados, ensure_ascii=False, indent=1).encode()).decode()}
        if versao:
            corpo["sha"] = versao
        r = self._req("PUT", f"/contents/{caminho}", json=corpo)
        if r.status_code in (409, 422):
            raise Conflito(caminho)
        r.raise_for_status()
