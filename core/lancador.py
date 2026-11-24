"""Ações no GitHub Actions: iniciar um workflow, achar a execução criada, consultar/cancelar execuções e saber se há bot rodando."""
import time

import httpx


class Lancador:
    def __init__(self, repo: str, token: str, client=None, ref: str = "main", dormir=time.sleep):
        self.repo, self.ref, self.dormir = repo, ref, dormir
        self.c = client or httpx.Client(base_url="https://api.github.com", timeout=30)
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    def _req(self, metodo, caminho, **kw):
        return self.c.request(metodo, f"/repos/{self.repo}{caminho}", headers=self.h, **kw)

    def execucoes_recentes(self, workflow: str, n: int = 8):
        r = self._req("GET", f"/actions/workflows/{workflow}/runs", params={"per_page": n})
        r.raise_for_status()
        return r.json().get("workflow_runs", [])

    def disparar(self, workflow: str, inputs: dict | None = None, esperas=(3, 5, 8, 12)) -> int | None:
        """Dispara e devolve o id da execução criada (ou None se não deu para identificar; o despachante tenta achar depois)."""
        conhecidos = {r["id"] for r in self.execucoes_recentes(workflow)}
        corpo = {"ref": self.ref}
        if inputs:
            corpo["inputs"] = {k: str(v) for k, v in inputs.items()}
        r = self._req("POST", f"/actions/workflows/{workflow}/dispatches", json=corpo)
        if r.status_code != 204:
            raise RuntimeError(f"GitHub recusou iniciar {workflow}: HTTP {r.status_code}")
        for e in esperas:
            self.dormir(e)
            novas = [x for x in self.execucoes_recentes(workflow) if x["id"] not in conhecidos and x.get("event") == "workflow_dispatch"]
            if novas:
                return max(novas, key=lambda x: x["id"])["id"]
        return None

    def achar_execucao(self, workflow: str, desde_iso: str) -> int | None:
        for x in self.execucoes_recentes(workflow, 10):
            if x.get("event") == "workflow_dispatch" and x["created_at"] >= desde_iso.replace("+00:00", "Z"):
                return x["id"]
        return None

    def estado(self, run_id: int):
        """('em_andamento'|'sucesso'|'falha'|'cancelado'|'desconhecido', execução)"""
        r = self._req("GET", f"/actions/runs/{run_id}")
        if r.status_code == 404:
            return "desconhecido", {}
        r.raise_for_status()
        x = r.json()
        if x["status"] != "completed":
            return "em_andamento", x
        return {"success": "sucesso", "cancelled": "cancelado"}.get(x.get("conclusion"), "falha"), x

    def cancelar(self, run_id: int) -> bool:
        return self._req("POST", f"/actions/runs/{run_id}/cancel").status_code == 202

    def ocupado(self, workflows: set[str], ignorar: set[int] = frozenset()) -> list[str]:
        """Nomes (arquivos) dos workflows de dados que estão rodando/na fila agora, exceto as execuções em `ignorar`."""
        achados = []
        for status in ("in_progress", "queued"):
            r = self._req("GET", "/actions/runs", params={"status": status, "per_page": 50})
            r.raise_for_status()
            for x in r.json().get("workflow_runs", []):
                arq = x.get("path", "").rsplit("/", 1)[-1]
                if arq in workflows and x["id"] not in ignorar:
                    achados.append(arq)
        return sorted(set(achados))
