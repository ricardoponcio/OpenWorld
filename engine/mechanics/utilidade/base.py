"""
MODULE: utilidade/base.py
FUNÇÃO: Contrato de um avaliador de utilidade de ação (Utility AI).

DESCRIÇÃO:
    Cada ação do enum `Acao` tem UM avaliador, que responde uma pergunta só:
    "quanto este NPC quer fazer isto, agora?". O `NPCBrain` só soma as respostas e
    escolhe o máximo — ele não conhece a regra de nenhuma ação em particular (R-D01).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List
from ...models import NPC, Acao


@dataclass(frozen=True)
class ContextoDecisao:
    """Tudo que um avaliador pode consultar. Imutável de propósito: nenhum avaliador
    altera o estado do NPC — isso é trabalho de `NPCActionManager`.

    `indice` (P02, docs/12_PLANO_CIDADE_VIVA.md): mesmo atributo de `EstadoDoMundo`, de
    propósito — `NPCUtils.obter_obra_do_npc(ctx, npc)` funciona tanto com `ctx` quanto
    com `mundo` sem precisar de um wrapper, porque os dois têm `.indice`/`.locais`."""
    npc: NPC
    hora: int
    config: dict
    locais: Dict[str, 'Local']
    eventos_globais: List[dict]
    indice: object = None


class AvaliadorDeUtilidade(ABC):
    acao: Acao = None

    @abstractmethod
    def avaliar(self, ctx: ContextoDecisao) -> float:
        """Utilidade bruta desta ação. 0.0 = não quer / não pode."""
