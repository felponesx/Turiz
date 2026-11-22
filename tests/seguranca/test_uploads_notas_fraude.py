import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PIL import Image
from app.seguranca import fraude, notas
from app.seguranca.uploads import UploadInvalido, caminho_confinado, guardar, nome_seguro, validar_imagem, validar_pdf


def _img(fmt="PNG", tamanho=(64, 64), exif=False):
    im = Image.new("RGB", tamanho, (200, 30, 30))
    b = io.BytesIO()
    if exif and fmt == "JPEG":
        ex = Image.Exif(); ex[0x010F] = "CameraSecreta"; ex[0x8825] = {1: "S", 2: (23.0, 33.0, 0.0), 3: "W", 4: (46.0, 38.0, 0.0)}
        im.save(b, fmt, exif=ex)
    else:
        im.save(b, fmt)
    return b.getvalue()


# ----------------------------------------------------------------- uploads
def test_imagem_valida_e_reencodada_sem_exif_gps():
    original = _img("JPEG", exif=True)
    assert b"CameraSecreta" in original
    ok = validar_imagem(original)
    assert ok.mime == "image/jpeg" and b"CameraSecreta" not in ok.dados and b"Exif" not in ok.dados      # localização/metadados removidos
    assert (ok.largura, ok.altura) == (64, 64)


@pytest.mark.parametrize("dados", [b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"GIF89a\x01\x00\x01\x00", b"MZ\x90\x00executavel", b"<?php system($_GET[0]); ?>",
                                   b"", b"\xff\xd8\xff" + b"lixo" * 20, b"PK\x03\x04zipcom\x00"])
def test_formatos_perigosos_ou_corrompidos_recusados(dados):
    with pytest.raises(UploadInvalido):
        validar_imagem(dados)


def test_extensao_e_content_type_nao_importam_so_os_bytes():
    php_como_jpg = b"<?php echo 1; ?>"                        # o nome 'foto.jpg' não muda nada: o conteúdo é analisado
    with pytest.raises(UploadInvalido):
        validar_imagem(php_como_jpg)


def test_limites_de_tamanho_e_dimensao():
    with pytest.raises(UploadInvalido):
        validar_imagem(_img(), max_bytes=100)
    with pytest.raises(UploadInvalido):
        validar_imagem(_img("PNG", (8, 8)))                   # pequena demais
    # PNG que descomprime para gigabytes (bomba): é recusado sem estourar memória
    bomba = io.BytesIO(); Image.new("L", (30000, 30000), 0).save(bomba, "PNG")
    assert len(bomba.getvalue()) < 5_000_000
    with pytest.raises(UploadInvalido):
        validar_imagem(bomba.getvalue())


def test_pdf_com_conteudo_ativo_recusado():
    assert validar_pdf(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF").mime == "application/pdf"
    for ativo in (b"/JavaScript", b"/JS ", b"/OpenAction", b"/Launch", b"/EmbeddedFile"):
        with pytest.raises(UploadInvalido):
            validar_pdf(b"%PDF-1.4\n<< " + ativo + b" (app.alert(1)) >>")
    with pytest.raises(UploadInvalido):
        validar_pdf(b"nao e pdf")


def test_nome_gerado_pelo_servidor_e_sem_path_traversal(tmp_path):
    assert nome_seguro("jpg") != nome_seguro("jpg") and nome_seguro("png").endswith(".png")
    with pytest.raises(UploadInvalido):
        nome_seguro("php")
    with pytest.raises(UploadInvalido):
        caminho_confinado(tmp_path, "..", "etc", "passwd")
    with pytest.raises(UploadInvalido):
        caminho_confinado(tmp_path, "/etc/passwd")
    assert caminho_confinado(tmp_path, "7", "ab", "x.jpg").is_relative_to(tmp_path.resolve())


def test_guardar_permissoes_cota_e_nao_sobrescreve(tmp_path, monkeypatch):
    arq = validar_imagem(_img())
    chave = guardar(tmp_path, 7, arq)
    destino = tmp_path / chave
    assert destino.exists() and (destino.stat().st_mode & 0o777) == 0o600 and not Path(chave).is_absolute()
    assert open(destino, "rb").read() == arq.dados
    import app.seguranca.uploads as up
    monkeypatch.setattr(up, "COTA_USUARIO_ARQUIVOS", 1)
    with pytest.raises(UploadInvalido, match="Limite"):
        guardar(tmp_path, 7, arq)
    assert guardar(tmp_path, 8, arq)                           # a cota é por usuário


# ----------------------------------------------------------------- nota fiscal (sem guardar CNPJ)
def _chave(uf="35", aamm="2611", cnpj="12345678000195", resto="55" + "001" + "000000123" + "1" + "12345678"):
    base = uf + aamm + cnpj + resto
    base = base[:43]
    return base + str(notas._dv(base))


def test_chave_de_acesso_valida_e_invalida():
    k = _chave()
    assert len(k) == 44 and notas.extrair_chave(f"https://www.nfce.fazenda.sp.gov.br/qrcode?p={k}|2|1|1|ABC") == k
    assert notas.extrair_chave(k[:-1] + str((int(k[-1]) + 1) % 10)) is None          # dígito verificador errado
    assert notas.extrair_chave("sem chave aqui") is None


def test_nota_validada_guarda_so_hashes_nunca_o_cnpj():
    k = _chave()
    n = notas.validar(k)
    assert n and n.uf == "SP" and n.ano_mes == "2611"
    texto = repr(n)
    assert k not in texto and "12345678000195" not in texto and "12345678" not in texto.replace(n.hash_nota, "").replace(n.hash_emitente, "")
    assert notas.validar(k).hash_nota == n.hash_nota                 # estável: serve para recusar a mesma nota duas vezes
    assert notas.validar(_chave(cnpj="99999999000191")).hash_emitente != n.hash_emitente
    assert notas.validar(_chave(uf="99")) is None


# ----------------------------------------------------------------- fraude
T0 = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def exp(uid=1, min=0, lugar="a", lat=-23.55, lon=-46.63, nota="", disp="d1"):
    return fraude.Experiencia(uid, T0 + timedelta(minutes=min), lugar, lat, lon, nota, disp)


def test_mesma_nota_duas_vezes_e_recusada_mesmo_por_outra_conta():
    p = fraude.avaliar(exp(uid=2, nota="h1"), [exp(uid=1, nota="h1")])
    assert p.acao == fraude.RECUSAR_DUPLICADA


def test_uso_normal_e_aceito():
    assert fraude.avaliar(exp(min=0, lugar="a"), [exp(min=-3000, lugar="b")]).acao == fraude.ACEITAR


def test_deslocamento_impossivel_vai_para_revisao_nao_para_banimento():
    p = fraude.avaliar(exp(min=10, lugar="rio", lat=-22.9, lon=-43.2), [exp(min=0, lugar="sp")])      # SP→RJ em 10 min
    assert p.acao == fraude.REVISAR and any("impossível" in m for m in p.motivos)
    assert p.acao != "banir"


def test_excesso_no_dia_e_mesmo_lugar_retem_xp():
    hist = [exp(min=-i * 30, lugar=f"l{i}", lat=-23.55 + i * 0.001) for i in range(1, 6)]
    assert fraude.avaliar(exp(min=0, lugar="novo"), hist).acao in (fraude.RETER_XP, fraude.REVISAR)
    assert fraude.avaliar(exp(min=60, lugar="a"), [exp(min=0, lugar="a")]).acao == fraude.RETER_XP


def test_varias_contas_no_mesmo_dispositivo_e_conta_nova():
    assert fraude.avaliar(exp(), [], outras_contas_no_dispositivo=4).acao == fraude.RETER_XP
    p = fraude.avaliar(exp(min=5), [exp(min=0), exp(min=1)], idade_conta=timedelta(minutes=10))
    assert any("conta muito nova" in m for m in p.motivos)


def test_avaliacoes_e_cadastros_em_massa():
    rajada = [(i, T0 + timedelta(minutes=i)) for i in range(10)]
    assert fraude.avaliacoes_em_massa(rajada) is True
    espacadas = [(i, T0 + timedelta(days=i)) for i in range(10)]
    assert fraude.avaliacoes_em_massa(espacadas) is False
    assert fraude.contas_em_massa([T0 + timedelta(minutes=i) for i in range(6)]) is True
