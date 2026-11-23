import json
import os
import subprocess
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
SCRIPT = os.path.join(RAIZ, "scripts", "atualizar_app_turiz.py")
DADOS = os.path.join(RAIZ, "data")

def _bloco(nome, ident, conteudo):
    return f'<!--{nome}--><script type="application/json" id="{ident}">{conteudo}</script><!--/{nome}-->'


# mesma estrutura da página real: todos os blocos já existem (a atualização só troca o conteúdo deles)
PAGINA = ('<!doctype html><html><body><h1>Turiz visual</h1>'
          + _bloco("API-DATA", "api-lugares", "[]") + _bloco("API-IMAGENS", "api-imagens", "{}") + _bloco("API-REDES", "api-redes", "{}")
          + _bloco("API-CARDAPIOS", "api-cardapios", "{}") + _bloco("API-FOTOS-EX", "api-fotos-ex", "{}") + _bloco("API-EVENTOS", "api-eventos", '{"gerado":"","itens":[]}')
          + '<p>conteúdo visual que não pode mudar</p></body></html>')


def rodar(tmp_path, pagina):
    a, b = tmp_path / "atual.html", tmp_path / "nova.html"
    a.write_text(pagina, encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, str(a), str(b), "--dados", DADOS], capture_output=True, text=True)
    return r, b


def test_atualiza_so_os_blocos_de_dados(tmp_path):
    r, b = rodar(tmp_path, PAGINA)
    assert r.returncode == 0, r.stdout + r.stderr
    nova = b.read_text(encoding="utf-8")
    assert "<h1>Turiz visual</h1>" in nova and "<p>conteúdo visual que não pode mudar</p>" in nova
    assert "lugares=" in r.stdout and int(r.stdout.split("lugares=")[1].split()[0]) > 0
    # rodar de novo sobre o resultado não muda nada
    r2 = subprocess.run([sys.executable, SCRIPT, str(b), str(tmp_path / "n2.html"), "--dados", DADOS], capture_output=True, text=True)
    assert r2.returncode == 3 and "sem_mudancas=1" in r2.stdout


def test_recusa_pagina_sem_blocos(tmp_path):
    r, _ = rodar(tmp_path, "<html><body>outra coisa</body></html>")
    assert r.returncode == 2 and "blocos de dados" in r.stdout
