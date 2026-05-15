from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum

class Acao(Enum):
    DORMIR = "Dormir"
    TRABALHAR = "Trabalhar"
    SOCIALIZAR = "Socializar"
    COMER = "Comer"
    OCIOSO = "Ocioso"

@dataclass
class Local:
    id: str
    nome: str
    tipo: str
    descricao: str
    coordenadas: List[float] = field(default_factory=lambda: [0.0, 0.0])

@dataclass
class NPC:
    id: str
    nome: str
    profissao: str
    casa_id: str
    local_trabalho_id: str
    localizacao_atual_id: str
    acao_atual: Acao = Acao.OCIOSO
    
    # Necessidades (0 a 100)
    energia: float = 100.0
    dinheiro_total_pc: int = 500  # Começa com 500 peças de cobre
    social: float = 100.0
    fome: float = 0.0
    
    genealogia: List[str] = field(default_factory=list)
    relacionamentos: Dict[str, int] = field(default_factory=dict)
    memoria_eventos: List[str] = field(default_factory=list)

    @property
    def dinheiro_formatado(self) -> str:
        """Converte o total de PC para o formato PO, PP, PC."""
        po = self.dinheiro_total_pc // 1000
        resto_pp = self.dinheiro_total_pc % 1000
        pp = resto_pp // 100
        pc = resto_pp % 100
        
        parts = []
        if po > 0: parts.append(f"{po}po")
        if pp > 0: parts.append(f"{pp}pp")
        if pc > 0 or not parts: parts.append(f"{pc}pc")
        return ", ".join(parts)

@dataclass
class Evento:
    id: str
    timestamp: str
    local_id: str
    envolvidos: List[str]
    tipo_evento: str
    modificador_afinidade: int
    resumo_estruturado: str
