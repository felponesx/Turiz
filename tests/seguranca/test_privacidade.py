import gzip
import json
import subprocess
import sys


def _rodar(tmp_path, registros, nome="lugares.json"):
    d = tmp_path / "data"; d.mkdir(exist_ok=True)
    (d / nome).write_text(json.dumps(registros), encoding="utf-8")
    return subprocess.run([sys.executable, "scripts/verificar_privacidade.py"], cwd=tmp_path, capture_output=True, text=True, env={"PYTHONPATH": ""}), d


def _script_em(tmp_path):
    import shutil
    (tmp_path / "scripts").mkdir(exist_ok=True)
    shutil.copy("scripts/verificar_privacidade.py", tmp_path / "scripts")


def test_achados_cnpj_cpf_email_sao_detectados_sem_imprimir_o_valor(tmp_path):
    _script_em(tmp_path)
    for rotulo, valor in (("CNPJ", "12.345.678/0001-95"), ("CNPJ(14", "12345678000195"), ("CPF", "123.456.789-09"), ("e-mail", "pessoa@exemplo.com")):
        r, _ = _rodar(tmp_path, [{"nome": f"Bar {valor}"}])
        assert r.returncode == 1 and rotulo in r.stdout
        assert valor not in r.stdout + r.stderr                       # o dado encontrado nunca vai para o log
    r, d = _rodar(tmp_path, [{"nome": "Bar Limpo", "fonte_id": "12345678000195", "site": "https://loja.com/12345678901234"}])
    assert r.returncode == 0                                         # hash de fonte_id e id numérico em URL não são CNPJ


def test_detecta_em_arquivo_gz(tmp_path):
    _script_em(tmp_path)
    d = tmp_path / "data"; d.mkdir()
    with gzip.open(d / "x.json.gz", "wt") as f:
        json.dump([{"extra": {"obs": "contato dono@exemplo.com"}}], f)
    r = subprocess.run([sys.executable, "scripts/verificar_privacidade.py"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1 and "e-mail" in r.stdout


def test_dados_reais_do_repositorio_estao_limpos():
    r = subprocess.run([sys.executable, "scripts/verificar_privacidade.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
