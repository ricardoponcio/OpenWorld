"""
MODULE: client.py
FUNÇÃO: Fachada estática de `AIClient.query` sobre um `RoteadorIA` de processo
    (I05, docs/16_PLANO_PAINEL_E_IA.md).
"""
import os
import threading
from typing import Optional

from config import cfg_get, get_config

from .clientes import ClienteIA
from .coleta_uso import RegistradorDeUsoIA
from .roteador import ErroIAIndisponivel, RoteadorIA

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

__all__ = ["AIClient", "ErroIAIndisponivel"]


class AIClient:
    """⚠️ Paliativo consciente (I05, docs/16_PLANO_PAINEL_E_IA.md): fachada
    estática sobre um `RoteadorIA` por processo, porque os 8 chamadores são
    estáticos e alguns rodam em thread. O substituto é injetar `RoteadorIA` nos
    gerenciadores (ARQUITETURA §7) quando eles forem convertidos em classes de
    instância — mesmo padrão que `config.configurar_fonte` já usa."""
    _roteador: Optional[RoteadorIA] = None
    _trava = threading.Lock()

    @classmethod
    def configurar(cls, roteador: RoteadorIA) -> None:
        """Usado por testes e pontos de entrada — sem chamar isto, o primeiro
        `query` constrói o roteador sozinho a partir de `get_config()`."""
        cls._roteador = roteador

    @classmethod
    def _obter_roteador(cls) -> RoteadorIA:
        if cls._roteador is None:
            with cls._trava:
                if cls._roteador is None:  # outra thread pode ter construído enquanto esta esperava a trava
                    cfg_ia = cfg_get(get_config(), "ia")
                    cfg_coleta = cfg_get(cfg_ia, "coleta_uso")
                    registrador = RegistradorDeUsoIA(
                        arquivo=cfg_get(cfg_coleta, "arquivo"),
                        gravar_texto=cfg_get(cfg_coleta, "gravar_texto"),
                        ativo=cfg_get(cfg_coleta, "ativa"))
                    cls._roteador = RoteadorIA(cfg_ia, registrador)
        return cls._roteador

    @classmethod
    def query(cls, prompt: str, cliente: ClienteIA, json_format: bool = False) -> str:
        """Levanta `ErroIAIndisponivel` quando a cadeia inteira falha — o
        chamador cai no fallback procedural que já existe."""
        return cls._obter_roteador().consultar(prompt, cliente, json_format)

    @staticmethod
    def read_prompt(filename: str) -> str:
        """Lê um template de prompt de `engine/ai/prompts/`, resolvido a partir do
        próprio arquivo (nunca subindo diretório) — antes, `ai/client.py` montava este
        caminho subindo um nível a partir de si mesmo até `engine/ai/prompts/`, frágil a
        qualquer um dos dois pacotes se mover (R-A07)."""
        path = os.path.join(PROMPTS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
