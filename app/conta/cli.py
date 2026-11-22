"""Cria o primeiro administrador (ou promove uma conta). A senha é pedida no terminal (não vai para histórico nem para argumentos).
O administrador ainda precisa configurar a verificação em duas etapas no primeiro login: sem MFA ele não acessa nada administrativo.
Uso: python -m app.conta.cli admin@exemplo.com"""
import getpass
import sys
from sqlalchemy import select
from ..db import SessionLocal
from ..migrar import upgrade_head
from ..seguranca.modelos import Usuario
from . import senhas


def criar_usuario(db, email: str, senha: str, papel: str = "usuario", nome: str = "") -> Usuario:
    email = email.strip().lower()
    erro = senhas.validar_politica(senha, email)
    if erro:
        raise ValueError(erro)
    u = db.scalar(select(Usuario).where(Usuario.email_norm == email))
    if u is None:
        u = Usuario(email_norm=email, senha_hash=senhas.hash_senha(senha), nome=nome, papel=papel, mfa_recuperacao=[], email_verificado=True)
        db.add(u)
    else:
        u.papel = papel
    db.commit()
    return u


def main():
    if len(sys.argv) != 2:
        sys.exit("uso: python -m app.conta.cli <email-do-admin>")
    upgrade_head()
    senha = getpass.getpass("Senha do administrador (mín. 10 caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")
    with SessionLocal() as db:
        u = criar_usuario(db, sys.argv[1], senha, "admin")
    print(f"Administrador {u.email_norm} pronto. Entre e configure a verificação em duas etapas (obrigatória).")


if __name__ == "__main__":
    main()
