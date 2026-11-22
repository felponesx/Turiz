"""Envio de e-mails transacionais (recuperação de senha, verificação, troca de e-mail, alertas).
Backends: `desligado` (padrão: nada é enviado), `teste` (só testes; guarda na memória, proibido em produção), `smtp` (TLS obrigatório).
O token NUNCA vai para log. Sem backend configurado, os fluxos que dependem de e-mail respondem normalmente, mas o e-mail não chega."""
import logging
import os
import smtplib
from email.message import EmailMessage
from ..seguranca import config

log = logging.getLogger("turiz.conta")
CAIXA_TESTE: list[tuple[str, str, str]] = []

ASSUNTOS = {"recuperar_senha": "Redefinir sua senha no TURIZ", "verificar_email": "Confirme seu e-mail no TURIZ", "trocar_email": "Confirme seu novo e-mail no TURIZ",
            "alerta_login": "Novo acesso à sua conta TURIZ"}
CORPOS = {"recuperar_senha": "Recebemos um pedido para redefinir sua senha. Se foi você, use o código abaixo em até 1 hora. Se não foi, ignore este e-mail.",
          "verificar_email": "Use o código abaixo para confirmar seu e-mail.", "trocar_email": "Use o código abaixo para confirmar este novo e-mail.",
          "alerta_login": "Detectamos um acesso à sua conta de um dispositivo novo. Se não foi você, troque sua senha e encerre as sessões."}


def enviar(tipo: str, destino: str, token: str = "") -> bool:
    backend = os.getenv("TURIZ_EMAIL_BACKEND", "desligado")
    if backend == "teste":
        if config.producao():
            raise RuntimeError("backend de e-mail 'teste' é proibido em produção")
        CAIXA_TESTE.append((tipo, destino, token))
        return True
    if backend == "smtp":
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = ASSUNTOS.get(tipo, "TURIZ"), os.environ["TURIZ_SMTP_DE"], destino
            msg.set_content(f"{CORPOS.get(tipo, '')}\n\n{token}\n\nTURIZ" if token else f"{CORPOS.get(tipo, '')}\n\nTURIZ")
            with smtplib.SMTP(os.environ["TURIZ_SMTP_HOST"], int(os.getenv("TURIZ_SMTP_PORTA", "587")), timeout=15) as s:
                s.starttls()
                s.login(os.environ["TURIZ_SMTP_USUARIO"], os.environ["TURIZ_SMTP_SENHA"])
                s.send_message(msg)
            return True
        except Exception as exc:                   # falha de envio não pode derrubar nem revelar nada ao cliente
            log.error("falha ao enviar e-mail tipo=%s: %s", tipo, type(exc).__name__)
            return False
    log.info("e-mail tipo=%s não enviado: backend desligado", tipo)
    return False
