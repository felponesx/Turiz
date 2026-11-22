"""Contas de usuário: cadastro, login, sessões, MFA, recuperação, troca de e-mail/senha, favoritos, exportação e exclusão (LGPD).

Regras: autorização no SERVIDOR em toda rota; o dono dos dados vem sempre da sessão (nunca de id na URL/corpo → sem IDOR);
respostas genéricas contra enumeração de e-mails; bloqueio progressivo (temporário) por conta e por IP; administradores exigem MFA."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..seguranca import config, limites
from ..seguranca.auditoria import registrar
from ..seguranca.entrada import IdPositivo, email_valido, ref_valida, texto_limpo
from ..seguranca.ip import cliente_ip, ip_hash
from ..seguranca.modelos import Auditoria, FavoritoUsuario, Sessao, TokenConta, Usuario
from . import cripto, email as correio, senhas, sessoes
from .sessoes import Autenticado, agora, utc

router = APIRouter(prefix="/conta")
GENERICA = {"mensagem": "Se os dados forem válidos, a solicitação foi processada."}
BLOQUEIO_BASE, BLOQUEIO_MAX = timedelta(seconds=30), timedelta(minutes=15)


def _norm(email: str) -> str:
    return email.strip().lower()


def _usuario_dict(u: Usuario) -> dict:
    return {"id": u.id, "email": u.email_norm, "nome": u.nome, "papel": u.papel, "email_verificado": u.email_verificado, "mfa_ativo": u.mfa_ativo}


def _token_unico() -> tuple[str, str]:
    t = secrets.token_urlsafe(32)
    return t, hashlib.sha256(t.encode()).hexdigest()


def _auditar(db, request, u: Usuario | int | None, acao: str, resultado: str = "ok", detalhe: str = ""):
    uid = u.id if isinstance(u, Usuario) else u
    registrar(db, request, ator=f"usuario:{uid}" if uid else "anonimo", escopo="conta", resultado=resultado, detalhe=f"{acao} {detalhe}".strip(), rota=request.url.path)


class Cadastro(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=200)
    nome: str = Field(default="", max_length=80)


class Login(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=200)
    codigo: str = Field(default="", max_length=32)
    retornar_token: bool = False


@router.post("/cadastro", status_code=202)
def cadastro(b: Cadastro, request: Request, db: Session = Depends(get_db)):
    ip = cliente_ip(request)
    ok, espera = limites.CADASTRO.verificar(ip)
    if not ok:
        raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(espera)})
    email = _norm(b.email)
    if not email_valido(email):
        raise HTTPException(422, "E-mail inválido")
    erro = senhas.validar_politica(b.senha, email)
    if erro:
        raise HTTPException(422, erro)
    h = senhas.hash_senha(b.senha)                    # sempre calcula (mesmo tempo para e-mail novo ou já cadastrado)
    if db.scalar(select(Usuario.id).where(Usuario.email_norm == email)) is None:
        u = Usuario(email_norm=email, senha_hash=h, nome=texto_limpo(b.nome, 80), mfa_recuperacao=[])
        db.add(u)
        db.commit()
        _auditar(db, request, u, "cadastro")
        token, th = _token_unico()
        db.add(TokenConta(usuario_id=u.id, tipo="verificar_email", token_hash=th, expira_em=agora() + timedelta(days=2)))
        db.commit()
        correio.enviar("verificar_email", email, token)
    return {"mensagem": "Se o e-mail puder ser usado, a conta foi criada. Você já pode entrar."}      # resposta idêntica nos dois casos


def _falha_login(db: Session, u: Usuario | None):
    if u is None:
        return
    u.falhas_login += 1
    if u.falhas_login >= 5:                            # a partir da 5ª falha: bloqueio crescente (30 s, 60 s, ... até 15 min), nunca permanente
        passos = u.falhas_login - 5
        u.bloqueado_ate = agora() + min(BLOQUEIO_MAX, BLOQUEIO_BASE * (2 ** passos))
    db.commit()


@router.post("/login")
def login(b: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = cliente_ip(request)
    espera = limites.AUTH_FALHA.bloqueado(ip)
    if espera:
        raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(espera)})
    email = _norm(b.email)
    u = db.scalar(select(Usuario).where(Usuario.email_norm == email))
    bloqueada = u is not None and u.bloqueado_ate is not None and utc(u.bloqueado_ate) > agora()
    senha_ok = senhas.verificar(b.senha, u.senha_hash if u else None)     # mesmo custo exista ou não a conta
    erro = HTTPException(401, "E-mail ou senha incorretos")                # uma única mensagem para qualquer falha
    if bloqueada or not senha_ok:
        permitido, esp = limites.AUTH_FALHA.verificar(ip)                   # conta a falha por IP
        if senha_ok is False and not bloqueada:
            _falha_login(db, u)
        _auditar(db, request, u, "login", "falha", "bloqueada" if bloqueada else "credenciais")
        if not permitido:
            raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(esp)})
        raise erro
    mfa_ok = False
    if u.mfa_ativo:
        if not b.codigo:
            raise HTTPException(401, "Código de verificação necessário", headers={"X-MFA": "necessario"})
        if not _validar_codigo_mfa(db, u, b.codigo):
            limites.AUTH_FALHA.verificar(ip)
            _falha_login(db, u)
            _auditar(db, request, u, "login", "falha", "mfa")
            raise erro
        mfa_ok = True
    anteriores = {x for (x,) in db.execute(select(Sessao.ip_hash).where(Sessao.usuario_id == u.id))}
    u.falhas_login, u.bloqueado_ate, u.ultimo_login_em = 0, None, agora()
    if senhas.precisa_rehash(u.senha_hash):
        u.senha_hash = senhas.hash_senha(b.senha)
    db.commit()
    token = sessoes.criar(db, u, request, mfa_ok)
    novo = bool(anteriores) and ip_hash(ip) not in anteriores
    _auditar(db, request, u, "login", "alerta" if novo else "ok", "novo_dispositivo" if novo else "")
    if novo:
        correio.enviar("alerta_login", u.email_norm)
    corpo = {"usuario": _usuario_dict(u), "mfa_configuracao_necessaria": u.papel == "admin" and not u.mfa_ativo}
    if b.retornar_token:
        corpo["token"] = token                         # clientes não-navegador (app nativo): usam Authorization: Bearer
    else:
        sessoes.definir_cookies(response, request, token)
        corpo["csrf"] = sessoes.csrf_de(token)
    return corpo


@router.post("/logout")
def logout(request: Request, response: Response, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    a.sessao.revogada_em = agora()
    db.commit()
    sessoes.limpar_cookies(response)
    return {"ok": True}


@router.post("/logout-todos")
def logout_todos(request: Request, response: Response, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    for s in db.scalars(select(Sessao).where(Sessao.usuario_id == a.usuario.id, Sessao.revogada_em.is_(None))):
        s.revogada_em = agora()
    db.commit()
    _auditar(db, request, a.usuario, "logout_todos")
    sessoes.limpar_cookies(response)
    return {"ok": True}


@router.get("/eu")
def eu(a: Autenticado = Depends(sessoes.sessao_atual)):
    return _usuario_dict(a.usuario)


class Perfil(BaseModel):
    nome: str = Field(max_length=80)


@router.patch("/eu")
def atualizar_eu(b: Perfil, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    a.usuario.nome = texto_limpo(b.nome, 80)
    db.commit()
    return _usuario_dict(a.usuario)


@router.get("/sessoes")
def listar_sessoes(a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    ss = db.scalars(select(Sessao).where(Sessao.usuario_id == a.usuario.id, Sessao.revogada_em.is_(None)).order_by(Sessao.criado_em.desc())).all()
    return [{"id": s.id, "dispositivo": s.dispositivo, "criado_em": utc(s.criado_em), "ultimo_uso_em": utc(s.ultimo_uso_em), "atual": s.id == a.sessao.id} for s in ss]


@router.delete("/sessoes/{sessao_id}")
def encerrar_sessao(sessao_id: IdPositivo, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    s = db.get(Sessao, sessao_id)
    if s is None or s.usuario_id != a.usuario.id:          # sessão de outra pessoa = "não existe" (sem vazar nada)
        raise HTTPException(404, "Não encontrada")
    s.revogada_em = agora()
    db.commit()
    return {"ok": True}


class Senha(BaseModel):
    senha: str = Field(max_length=200)


@router.post("/reautenticar")
def reautenticar(b: Senha, request: Request, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    permitido, esp = limites.LOGIN_CONTA.verificar(f"reauth:{a.usuario.id}")
    if not permitido or not senhas.verificar(b.senha, a.usuario.senha_hash):
        _auditar(db, request, a.usuario, "reautenticar", "falha")
        raise HTTPException(401 if permitido else 429, "Senha incorreta" if permitido else "Muitas tentativas")
    a.sessao.reauth_em = agora()
    db.commit()
    return {"ok": True}


class TrocaSenha(BaseModel):
    senha_atual: str = Field(max_length=200)
    senha_nova: str = Field(max_length=200)


@router.post("/senha")
def trocar_senha(b: TrocaSenha, request: Request, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    permitido, esp = limites.LOGIN_CONTA.verificar(f"senha:{a.usuario.id}")
    if not permitido:
        raise HTTPException(429, "Muitas tentativas", headers={"Retry-After": str(esp)})
    if not senhas.verificar(b.senha_atual, a.usuario.senha_hash):
        _auditar(db, request, a.usuario, "trocar_senha", "falha")
        raise HTTPException(401, "Senha atual incorreta")
    erro = senhas.validar_politica(b.senha_nova, a.usuario.email_norm)
    if erro:
        raise HTTPException(422, erro)
    a.usuario.senha_hash = senhas.hash_senha(b.senha_nova)
    for s in db.scalars(select(Sessao).where(Sessao.usuario_id == a.usuario.id, Sessao.revogada_em.is_(None), Sessao.id != a.sessao.id)):
        s.revogada_em = agora()                          # trocou a senha: todos os outros dispositivos saem
    db.commit()
    _auditar(db, request, a.usuario, "trocar_senha")
    return {"ok": True}


class Recuperar(BaseModel):
    email: str = Field(max_length=254)


@router.post("/recuperar", status_code=202)
def recuperar(b: Recuperar, request: Request, db: Session = Depends(get_db)):
    permitido, esp = limites.RECUPERACAO.verificar(cliente_ip(request))
    if not permitido:
        raise HTTPException(429, "Muitas tentativas. Tente novamente mais tarde.", headers={"Retry-After": str(esp)})
    u = db.scalar(select(Usuario).where(Usuario.email_norm == _norm(b.email)))
    if u is not None:
        for t in db.scalars(select(TokenConta).where(TokenConta.usuario_id == u.id, TokenConta.tipo == "recuperar_senha", TokenConta.usado_em.is_(None))):
            t.usado_em = agora()                          # só o pedido mais recente vale
        token, th = _token_unico()
        db.add(TokenConta(usuario_id=u.id, tipo="recuperar_senha", token_hash=th, expira_em=agora() + timedelta(hours=1)))
        db.commit()
        correio.enviar("recuperar_senha", u.email_norm, token)
        _auditar(db, request, u, "recuperar_senha_pedido")
    return GENERICA                                        # mesma resposta exista ou não o e-mail


class ConfirmarRecuperacao(BaseModel):
    token: str = Field(max_length=100)
    senha_nova: str = Field(max_length=200)


def _consumir_token(db: Session, token: str, tipo: str) -> TokenConta | None:
    t = db.scalar(select(TokenConta).where(TokenConta.token_hash == hashlib.sha256(token.encode()).hexdigest(), TokenConta.tipo == tipo))
    if t is None or t.usado_em is not None or utc(t.expira_em) < agora():
        return None
    t.usado_em = agora()
    return t


@router.post("/recuperar/confirmar")
def recuperar_confirmar(b: ConfirmarRecuperacao, request: Request, db: Session = Depends(get_db)):
    permitido, esp = limites.RECUPERACAO.verificar("conf:" + cliente_ip(request))
    if not permitido:
        raise HTTPException(429, "Muitas tentativas", headers={"Retry-After": str(esp)})
    t = _consumir_token(db, b.token, "recuperar_senha")
    if t is None:
        raise HTTPException(400, "Código inválido ou expirado")
    u = db.get(Usuario, t.usuario_id)
    erro = senhas.validar_politica(b.senha_nova, u.email_norm)
    if erro:
        db.rollback()
        raise HTTPException(422, erro)
    u.senha_hash, u.falhas_login, u.bloqueado_ate = senhas.hash_senha(b.senha_nova), 0, None
    for s in db.scalars(select(Sessao).where(Sessao.usuario_id == u.id, Sessao.revogada_em.is_(None))):
        s.revogada_em = agora()                          # recuperar senha derruba todas as sessões (conta pode estar comprometida)
    db.commit()
    _auditar(db, request, u, "recuperar_senha_concluida")
    return {"ok": True}


class TrocaEmail(BaseModel):
    senha: str = Field(max_length=200)
    novo_email: str = Field(max_length=254)


@router.post("/email", status_code=202)
def trocar_email(b: TrocaEmail, request: Request, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    permitido, esp = limites.LOGIN_CONTA.verificar(f"email:{a.usuario.id}")
    if not permitido or not senhas.verificar(b.senha, a.usuario.senha_hash):
        _auditar(db, request, a.usuario, "trocar_email", "falha")
        raise HTTPException(401 if permitido else 429, "Senha incorreta" if permitido else "Muitas tentativas")
    novo = _norm(b.novo_email)
    if not email_valido(novo):
        raise HTTPException(422, "E-mail inválido")
    if db.scalar(select(Usuario.id).where(Usuario.email_norm == novo)) is None:     # se já existe, silêncio: não revela quem tem conta
        token, th = _token_unico()
        db.add(TokenConta(usuario_id=a.usuario.id, tipo="trocar_email", token_hash=th, alvo=novo, expira_em=agora() + timedelta(hours=2)))
        db.commit()
        correio.enviar("trocar_email", novo, token)
    return GENERICA


class Codigo(BaseModel):
    token: str = Field(max_length=100)


@router.post("/email/confirmar")
def confirmar_email(b: Codigo, request: Request, db: Session = Depends(get_db)):
    permitido, esp = limites.RECUPERACAO.verificar("econf:" + cliente_ip(request))
    if not permitido:
        raise HTTPException(429, "Muitas tentativas", headers={"Retry-After": str(esp)})
    for tipo in ("trocar_email", "verificar_email"):
        t = _consumir_token(db, b.token, tipo)
        if t is not None:
            u = db.get(Usuario, t.usuario_id)
            if tipo == "trocar_email":
                if db.scalar(select(Usuario.id).where(Usuario.email_norm == t.alvo)) is not None:
                    db.rollback()
                    raise HTTPException(400, "Código inválido ou expirado")
                u.email_norm = t.alvo
            u.email_verificado = True
            db.commit()
            _auditar(db, request, u, tipo)
            return {"ok": True}
    raise HTTPException(400, "Código inválido ou expirado")


# ----------------------------------------------------------------------------- MFA (TOTP)
def _validar_codigo_mfa(db: Session, u: Usuario, codigo: str) -> bool:
    codigo = codigo.strip().replace(" ", "")
    segredo = cripto.decifrar(u.mfa_segredo) if u.mfa_segredo else None
    if segredo and codigo.isdigit() and len(codigo) == 6:
        totp = pyotp.TOTP(segredo)
        agora_ = int(datetime.now(timezone.utc).timestamp())
        for deslocamento in (-1, 0, 1):
            passo = agora_ // 30 + deslocamento
            if passo > u.mfa_ultimo_passo and totp.at(passo * 30) == codigo:       # cada passo só vale uma vez (anti-replay)
                u.mfa_ultimo_passo = passo
                db.commit()
                return True
        return False
    h = hashlib.sha256(codigo.lower().encode()).hexdigest()                          # código de recuperação (uso único)
    if h in (u.mfa_recuperacao or []):
        u.mfa_recuperacao = [x for x in u.mfa_recuperacao if x != h]
        db.commit()
        return True
    return False


@router.post("/mfa/iniciar")
def mfa_iniciar(request: Request, a: Autenticado = Depends(sessoes.exigir_reauth), db: Session = Depends(get_db)):
    if a.usuario.mfa_ativo:
        raise HTTPException(409, "A verificação em duas etapas já está ativa")
    segredo = pyotp.random_base32()
    a.usuario.mfa_segredo = cripto.cifrar(segredo)
    db.commit()
    return {"segredo": segredo, "otpauth_uri": pyotp.TOTP(segredo).provisioning_uri(name=a.usuario.email_norm, issuer_name="TURIZ")}


class CodigoMfa(BaseModel):
    codigo: str = Field(max_length=32)


@router.post("/mfa/confirmar")
def mfa_confirmar(b: CodigoMfa, request: Request, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    permitido, esp = limites.LOGIN_CONTA.verificar(f"mfa:{a.usuario.id}")
    if not permitido:
        raise HTTPException(429, "Muitas tentativas", headers={"Retry-After": str(esp)})
    if a.usuario.mfa_ativo or not a.usuario.mfa_segredo:
        raise HTTPException(409, "Inicie a configuração primeiro")
    segredo = cripto.decifrar(a.usuario.mfa_segredo)
    if not segredo or not pyotp.TOTP(segredo).verify(b.codigo.strip(), valid_window=1):
        raise HTTPException(401, "Código incorreto")
    codigos = [secrets.token_hex(5) for _ in range(8)]
    a.usuario.mfa_ativo = True
    a.usuario.mfa_ultimo_passo = int(datetime.now(timezone.utc).timestamp()) // 30
    a.usuario.mfa_recuperacao = [hashlib.sha256(c.encode()).hexdigest() for c in codigos]
    a.sessao.mfa_ok = True
    db.commit()
    _auditar(db, request, a.usuario, "mfa_ativado")
    return {"codigos_de_recuperacao": codigos, "aviso": "Guarde estes códigos agora: eles não serão mostrados de novo."}


class DesativarMfa(BaseModel):
    senha: str = Field(max_length=200)
    codigo: str = Field(max_length=32)


@router.post("/mfa/desativar")
def mfa_desativar(b: DesativarMfa, request: Request, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    if a.usuario.papel == "admin":
        raise HTTPException(403, "Administradores não podem desativar a verificação em duas etapas")
    if not senhas.verificar(b.senha, a.usuario.senha_hash) or not _validar_codigo_mfa(db, a.usuario, b.codigo):
        _auditar(db, request, a.usuario, "mfa_desativar", "falha")
        raise HTTPException(401, "Senha ou código incorretos")
    a.usuario.mfa_ativo, a.usuario.mfa_segredo, a.usuario.mfa_recuperacao = False, "", []
    db.commit()
    _auditar(db, request, a.usuario, "mfa_desativado")
    return {"ok": True}


# ----------------------------------------------------------------------------- dados do próprio usuário (LGPD)
@router.get("/atividade")
def atividade(a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    """Eventos de segurança da própria conta (logins, falhas, trocas), para a pessoa perceber acessos suspeitos."""
    linhas = db.scalars(select(Auditoria).where(Auditoria.ator == f"usuario:{a.usuario.id}").order_by(Auditoria.id.desc()).limit(30)).all()
    return [{"quando": utc(l.quando), "acao": l.detalhe, "resultado": l.resultado} for l in linhas]


TIPOS_FAV = ("lugar", "evento", "prato")


def _tipo(tipo: str):
    if tipo not in TIPOS_FAV:
        raise HTTPException(422, "Tipo inválido")


@router.get("/favoritos")
def listar_favoritos(a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    return [{"tipo": f.tipo, "ref": f.ref, "criado_em": utc(f.criado_em)} for f in db.scalars(select(FavoritoUsuario).where(FavoritoUsuario.usuario_id == a.usuario.id).order_by(FavoritoUsuario.id))]


@router.put("/favoritos/{tipo}/{ref:path}")
def adicionar_favorito(tipo: str, ref: str, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    _tipo(tipo)
    if not ref_valida(ref):
        raise HTTPException(422, "Referência inválida")
    if db.scalar(select(func.count()).select_from(FavoritoUsuario).where(FavoritoUsuario.usuario_id == a.usuario.id)) >= 2000:
        raise HTTPException(409, "Limite de favoritos atingido")
    if db.scalar(select(FavoritoUsuario.id).where(FavoritoUsuario.usuario_id == a.usuario.id, FavoritoUsuario.tipo == tipo, FavoritoUsuario.ref == ref)) is None:
        db.add(FavoritoUsuario(usuario_id=a.usuario.id, tipo=tipo, ref=ref))
        db.commit()
    return {"ok": True}


@router.delete("/favoritos/{tipo}/{ref:path}")
def remover_favorito(tipo: str, ref: str, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    _tipo(tipo)
    db.execute(delete(FavoritoUsuario).where(FavoritoUsuario.usuario_id == a.usuario.id, FavoritoUsuario.tipo == tipo, FavoritoUsuario.ref == ref))
    db.commit()
    return {"ok": True}


@router.get("/exportar")
def exportar(a: Autenticado = Depends(sessoes.exigir_reauth), db: Session = Depends(get_db)):
    """Direito de acesso/portabilidade (LGPD art. 18): tudo o que guardamos sobre a pessoa, em JSON."""
    u = a.usuario
    return {"conta": {**_usuario_dict(u), "criado_em": utc(u.criado_em), "ultimo_login_em": utc(u.ultimo_login_em)},
            "favoritos": [{"tipo": f.tipo, "ref": f.ref} for f in db.scalars(select(FavoritoUsuario).where(FavoritoUsuario.usuario_id == u.id))],
            "sessoes": [{"dispositivo": s.dispositivo, "criado_em": utc(s.criado_em), "ativa": s.revogada_em is None} for s in db.scalars(select(Sessao).where(Sessao.usuario_id == u.id))],
            "atividade": [{"quando": utc(l.quando), "acao": l.detalhe, "resultado": l.resultado} for l in db.scalars(select(Auditoria).where(Auditoria.ator == f"usuario:{u.id}").order_by(Auditoria.id.desc()).limit(200))],
            "observacao": "Senhas são guardadas apenas como hash e não podem ser exportadas."}


@router.delete("")
def excluir_conta(b: Senha, request: Request, response: Response, a: Autenticado = Depends(sessoes.sessao_atual), db: Session = Depends(get_db)):
    """Direito de eliminação (LGPD art. 18, VI): apaga conta, sessões, tokens e favoritos. A trilha de segurança fica só com o
    identificador numérico, por até 12 meses (legítimo interesse: prevenção a fraudes), e depois é apagada."""
    if not senhas.verificar(b.senha, a.usuario.senha_hash):
        _auditar(db, request, a.usuario, "excluir_conta", "falha")
        raise HTTPException(401, "Senha incorreta")
    uid = a.usuario.id
    for modelo in (FavoritoUsuario, TokenConta, Sessao):
        db.execute(delete(modelo).where(modelo.usuario_id == uid))
    db.execute(delete(Usuario).where(Usuario.id == uid))
    db.commit()
    _auditar(db, request, uid, "conta_excluida")
    sessoes.limpar_cookies(response)
    return {"ok": True}


# ----------------------------------------------------------------------------- administração (MFA obrigatório)
@router.get("/admin/resumo")
def admin_resumo(a: Autenticado = Depends(sessoes.exigir_admin), db: Session = Depends(get_db)):
    return {"usuarios": db.scalar(select(func.count(Usuario.id))), "admins": db.scalar(select(func.count(Usuario.id)).where(Usuario.papel == "admin")),
            "sessoes_ativas": db.scalar(select(func.count(Sessao.id)).where(Sessao.revogada_em.is_(None)))}
