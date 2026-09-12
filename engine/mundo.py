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
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class EstadoDoMundo:
    npcs: List
    locais: Dict
    cidades: Dict
    data_simulada: datetime
    db: object
    tick_count: int = 0
