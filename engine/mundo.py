"""
MODULE: mundo.py
FUNÇÃO: Estado do mundo simulado (R-F01).

DESCRIÇÃO:
    Antes, cada gerenciador de mecânica (`engine/mechanics/*`) recebia a
    `SimulationEngine` inteira só para ler `npcs`/`locais`/`cidades`/`data_simulada` —
    isso amarrava todo gerenciador a um banco real e impedia testar qualquer um deles
    isoladamente (um gerenciador "dependia de tudo" mesmo quando só usava uma fração).
    `EstadoDoMundo` agrupa só os dados que mudam durante a simulação; `SimulationEngine`
    passa a CONTER um `EstadoDoMundo` em vez de ser ele, e cada gerenciador recebe só
    isso (mais a `config`, que é estática e não faz parte do estado do mundo).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from .indice_locais import IndiceDeLocais


@dataclass
class EstadoDoMundo:
    npcs: List
    locais: Dict
    cidades: Dict
    data_simulada: datetime
    db: object
    tick_count: int = 0
    # P01 (docs/PLANO_CIDADE_VIVA.md): índices de leitura por cidade e por papel sobre
    # o MESMO dicionário `locais` — construído uma vez, aqui, a partir do estado inicial
    # (repr=False/compare=False: não é dado de identidade do mundo, é derivado dele).
    # `locais` continua sendo o acesso por id; o índice é a fonte pra consulta por
    # conjunto (mover_para_social, obter_obra_do_npc). ⚠️ P02: quem cria/desativa um
    # local por fora de `registrar_local`/`desativar_local` deixa isto desatualizado.
    indice: IndiceDeLocais = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.indice is None:
            self.indice = IndiceDeLocais(self.locais)
