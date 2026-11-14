"""Configuração comum: banco de testes limpo e único para toda a sessão (criado antes de qualquer import de `app`)."""
import os
if os.path.exists("teste.db"):
    os.remove("teste.db")
os.environ["DATABASE_URL"] = "sqlite:///./teste.db"
os.environ["API_KEY"] = "k"
os.environ.pop("TICKETMASTER_API_KEY", None)      # testes nunca usam chave real
