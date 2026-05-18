from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum

class Acao(Enum):
    DORMIR = "Dormir"
    TRABALHAR = "Trabalhar"
    SOCIALIZAR = "Socializar"
    COMER = "Comer"
    OCIOSO = "Ocioso"
    CUIDAR_PROLE = "Cuidar da Prole"
    CONSTRUIR = "Construindo"

class EstagioVida(Enum):
    BEBE = "bebe"
    CRIANCA = "crianca"
    ADULTO = "adulto"
    IDOSO = "idoso"
    MORTO = "morto"

class EstadoCivil(Enum):
    SOLTEIRO = "solteiro"
    CASADO = "casado"
    VIUVO = "viuvo"

class CategoriaLocal(Enum):
    PUBLICO = "publico"
    COMERCIAL = "comercial"
    RESIDENCIA = "residencia"
    GENERIC = "generic"

class HumorNPC(Enum):
    NEUTRO = "Neutro"
    ALEGRE = "Alegre"
    CONTENTE = "Contente"
    TRISTE = "Triste"
    ANGUSTIADO = "Angustiado"
    PANICO = "Em Pânico"
    MEDO = "Amedrontado"

class TipoEvento(Enum):
    NASCIMENTO = "NASCIMENTO"
    CONCEPCAO = "CONCEPCAO"
    OBITO = "OBITO"
    HERANCA = "HERANCA"
    IMPOSTO = "IMPOSTO"
    CRESCIMENTO = "CRESCIMENTO"
    MAIORIDADE = "MAIORIDADE"
    CONVERSA = "CONVERSA"
    DISCUSSAO = "DISCUSSAO"

@dataclass
class Local:
    id: str
    nome: str
    tipo: str
    categoria: str = "generic"
    descricao: str = ""
    coordenadas: List[float] = field(default_factory=lambda: [0.0, 0.0])
    status: int = 1  # 1 = Ativo, 0 = Inativo/Destruído
    integridade: int = 100 # 0 a 100
    capacidade: int = 5
    salario_base: int = 100


@dataclass
class NPC:
    id: str
    nome: str
    profissao: str
    casa_id: str

    local_trabalho_id: str
    localizacao_atual_id: str
    profissao_id: str = "ocioso"
    acao_atual: Acao = Acao.OCIOSO
    
    # Necessidades e Estado
    energia: float = 100.0
    dinheiro_total_pc: int = 500
    social: float = 100.0
    fome: float = 0.0
    saude: int = 100 # 0 a 100
    humor: str = "Neutro"
    
    # Atributos Biológicos e Ciclo de Vida
    genero: str = "M"  # 'M' ou 'F'
    estagio_vida: str = "adulto" # 'bebe', 'crianca', 'adulto', 'idoso'
    estado_civil: str = EstadoCivil.SOLTEIRO.value
    conjuge_id: str = ""
    data_nascimento: str = ""
    pai_id: str = ""
    mae_id: str = ""
    gravidez_ticks: int = 0  # 0 = não gestante, >0 = gestante
    
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

    def is_adulto(self) -> bool:
        return self.estagio_vida == EstagioVida.ADULTO.value or self.estagio_vida == EstagioVida.ADULTO

    def is_idoso(self) -> bool:
        return self.estagio_vida == EstagioVida.IDOSO.value or self.estagio_vida == EstagioVida.IDOSO

    def pode_procriar(self) -> bool:
        return self.is_adulto() and self.saude > 0

    def esta_vivo(self) -> bool:
        return self.saude > 0 and self.estagio_vida != EstagioVida.MORTO.value and self.estagio_vida != EstagioVida.MORTO

@dataclass
class Evento:
    id: str
    timestamp: str
    local_id: str
    envolvidos: List[str]
    tipo_evento: str
    modificador_afinidade: int
    resumo_estruturado: str
