"""Uploads seguros (fotos de perfil/experiência/lugar e documentos). Biblioteca pronta para o endpoint de upload: o app ainda não
tem upload no servidor, então NADA aqui está exposto à internet hoje.

Regras: tamanho máximo; formato verificado pelos bytes (nunca pela extensão/Content-Type); proteção contra "bomba de descompressão";
imagem sempre REENCODADA (remove EXIF/GPS e qualquer carga escondida); nome de arquivo gerado pelo servidor; caminho confinado ao
diretório de uploads (sem path traversal); permissões 0600, nunca executável; cota por usuário; PDFs com JavaScript/ações são recusados."""
import io
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 40_000_000          # acima disso o Pillow recusa (bomba de descompressão)
MAX_IMAGEM_BYTES = 5_000_000
MAX_PDF_BYTES = 5_000_000
MAX_LADO = 8000
COTA_USUARIO_BYTES = 100_000_000
COTA_USUARIO_ARQUIVOS = 500

ASSINATURAS = {b"\xff\xd8\xff": ("image/jpeg", "jpg"), b"\x89PNG\r\n\x1a\n": ("image/png", "png")}


class UploadInvalido(ValueError):
    pass


@dataclass
class ArquivoValido:
    mime: str
    extensao: str
    dados: bytes            # já limpo/reencodado
    largura: int = 0
    altura: int = 0


def _tipo_por_bytes(dados: bytes) -> tuple[str, str] | None:
    for sig, tipo in ASSINATURAS.items():
        if dados.startswith(sig):
            return tipo
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp", "webp"
    if dados.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    return None                                  # SVG, GIF, HTML, executáveis, zip... tudo recusado


def validar_imagem(dados: bytes, max_bytes: int = MAX_IMAGEM_BYTES) -> ArquivoValido:
    if not dados or len(dados) > max_bytes:
        raise UploadInvalido("Arquivo vazio ou grande demais")
    tipo = _tipo_por_bytes(dados)
    if tipo is None or tipo[0] == "application/pdf":
        raise UploadInvalido("Formato não permitido (use JPEG, PNG ou WebP)")
    try:
        Image.open(io.BytesIO(dados)).verify()                       # estrutura íntegra
        im = Image.open(io.BytesIO(dados))
        im.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise UploadInvalido("Imagem corrompida ou inválida")
    if max(im.size) > MAX_LADO or min(im.size) < 16:
        raise UploadInvalido("Dimensões fora do permitido")
    im = ImageOps.exif_transpose(im)
    saida = io.BytesIO()
    if tipo[1] == "png" and im.mode in ("RGBA", "LA", "P"):
        im.convert("RGBA").save(saida, "PNG", optimize=True); mime, ext = "image/png", "png"
    else:
        im.convert("RGB").save(saida, "JPEG", quality=85, optimize=True); mime, ext = "image/jpeg", "jpg"     # sem EXIF/GPS, sem metadados
    return ArquivoValido(mime, ext, saida.getvalue(), im.size[0], im.size[1])


_PDF_PERIGOSO = re.compile(rb"/(JavaScript|JS|Launch|OpenAction|AA|EmbeddedFile|RichMedia|XFA)\b")


def validar_pdf(dados: bytes, max_bytes: int = MAX_PDF_BYTES) -> ArquivoValido:
    if not dados or len(dados) > max_bytes:
        raise UploadInvalido("Arquivo vazio ou grande demais")
    if _tipo_por_bytes(dados) != ("application/pdf", "pdf"):
        raise UploadInvalido("Não é um PDF")
    if _PDF_PERIGOSO.search(dados):
        raise UploadInvalido("PDF com conteúdo ativo não é permitido")
    return ArquivoValido("application/pdf", "pdf", dados)


def nome_seguro(extensao: str) -> str:
    """Nome gerado pelo servidor: o nome que o usuário enviou NUNCA é usado."""
    if extensao not in ("jpg", "png", "webp", "pdf"):
        raise UploadInvalido("Extensão não permitida")
    return secrets.token_hex(16) + "." + extensao


def caminho_confinado(base: Path, *partes: str) -> Path:
    base = base.resolve()
    destino = base.joinpath(*partes).resolve()
    if base != destino and base not in destino.parents:
        raise UploadInvalido("Caminho fora da área de uploads")
    return destino


def uso_do_usuario(base: Path, usuario_id: int) -> tuple[int, int]:
    pasta = caminho_confinado(base, str(int(usuario_id)))
    if not pasta.exists():
        return 0, 0
    arquivos = [p for p in pasta.rglob("*") if p.is_file()]
    return len(arquivos), sum(p.stat().st_size for p in arquivos)


def guardar(base: Path, usuario_id: int, arq: ArquivoValido) -> str:
    """Grava com cota por usuário; devolve a chave relativa (ex.: '42/ab/abcdef….jpg'). Nunca devolve caminho absoluto."""
    n, total = uso_do_usuario(base, usuario_id)
    if n >= COTA_USUARIO_ARQUIVOS or total + len(arq.dados) > COTA_USUARIO_BYTES:
        raise UploadInvalido("Limite de armazenamento do usuário atingido")
    nome = nome_seguro(arq.extensao)
    destino = caminho_confinado(base, str(int(usuario_id)), nome[:2], nome)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)       # O_EXCL: nunca sobrescreve; 0600: sem execução
    with os.fdopen(fd, "wb") as f:
        f.write(arq.dados)
    return str(destino.relative_to(base.resolve()))
