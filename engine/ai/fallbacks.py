"""
MODULE: fallbacks.py
FUNÇÃO: Conteúdo de fallback procedural quando o LLM local (Ollama) está offline.

DESCRIÇÃO:
    Nomes, personalidades, backgrounds e eventos globais do fallback viviam como ~60
    strings de conteúdo criativo escritas dentro de código Python, em 3 arquivos
    diferentes (biography.py, generator.py, storyteller.py) — mudar o tema do mundo
    exigia editar código, não só dado (R-B12). Agora moram em `fallbacks.json`, carregado
    uma vez e servido por sorteios nomeados.
"""
import json
import os
import random
from typing import Dict, List

CAMINHO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fallbacks.json")


class AIFallbacks:
    _dados = None

    @classmethod
    def _carregar(cls) -> Dict:
        if cls._dados is None:
            with open(CAMINHO_JSON, "r", encoding="utf-8") as f:
                cls._dados = json.load(f)
        return cls._dados

    @classmethod
    def sortear_nome_bebe(cls, genero: str) -> str:
        return random.choice(cls._carregar()["nomes_bebe"][genero])

    @classmethod
    def sortear_nome_npc(cls, genero: str, nomes_excluidos: List[str]) -> str:
        """Sorteia primeiro+sobrenome, redesenhando enquanto colidir com um nome já
        usado nesta leva (mesma tolerância a colisão que o código anterior tinha)."""
        d = cls._carregar()["nomes_npc"]
        while True:
            nome_completo = f"{random.choice(d[genero])} {random.choice(d['sobrenomes'])}"
            if nome_completo not in nomes_excluidos:
                return nome_completo

    @classmethod
    def sortear_sobrenome(cls) -> str:
        return random.choice(cls._carregar()["nomes_npc"]["sobrenomes"])

    @classmethod
    def sortear_raca(cls) -> str:
        """Sorteio ponderado — os pesos já são probabilidade (somam 1.0)."""
        racas = cls._carregar()["racas"]
        return random.choices(list(racas.keys()), weights=list(racas.values()), k=1)[0]

    @classmethod
    def sortear_personalidade(cls) -> str:
        return random.choice(cls._carregar()["personalidades"])

    @classmethod
    def sortear_background(cls, profissao: str) -> str:
        template = random.choice(cls._carregar()["backgrounds"])
        return template.format(profissao=profissao)

    @classmethod
    def sortear_local_oficina(cls) -> str:
        return random.choice(cls._carregar()["locais_oficina"])

    @classmethod
    def sortear_local_social(cls) -> str:
        return random.choice(cls._carregar()["locais_sociais"])

    @classmethod
    def sortear_evento_global(cls) -> Dict:
        """Sorteia o OBJETO inteiro, não um índice — antes o índice sorteado
        (`random.randint(0, 3)`) estava acoplado ao tamanho da lista escrita à mão, e um
        evento a mais ou a menos exigia acertar o range à mão junto (R-B12 item 4)."""
        return dict(random.choice(cls._carregar()["eventos_globais"]))
