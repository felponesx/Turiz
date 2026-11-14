"""Conectores de eventos. Cada módulo se registra em `base.REGISTRO` por `tipo`; importar o pacote carrega todos."""
from .base import REGISTRO, Conector  # noqa: F401
from . import ticketmaster, feeds, navegador  # noqa: F401
