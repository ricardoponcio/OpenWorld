from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from enum import Enum

# Limite estrutural das necessidades do NPC (energia/fome/social/saúde) — R-B09. Não é
# parâmetro de balanceamento (não vai pro config): é a faixa que a própria escala 0-100
# da simulação define.
ESCALA_MINIMA = 0.0
ESCALA_MAXIMA = 100.0

class Acao(Enum):
    DORMIR = "Dormir"
    TRABALHAR = "Trabalhar"
    SOCIALIZAR = "Socializar"
    COMER = "Comer"
    OCIOSO = "Ocioso"
    CUIDAR_PROLE = "Cuidar da Prole"
    CONSTRUIR = "Construindo"

class Genero(Enum):
    """INVARIANTE: NPC.genero guarda sempre Genero.X.value (str) — é o que vai para a
    coluna TEXT do SQLite. Rótulos de exibição ('menino'/'menina', 'Masculino ♂️') não
    entram aqui — são apresentação, não domínio; ficam como constante no módulo que
    exibe."""
    MASCULINO = "M"
    FEMININO = "F"

class EstagioVida(Enum):
    BEBE = "bebe"
    CRIANCA = "crianca"
    ADULTO = "adulto"
    IDOSO = "idoso"
    MORTO = "morto"

# N03 (docs/PLANO_POPULACAO_E_ESCALA.md): `.value` num membro de Enum é um acesso de
# descritor (`__get__`), não uma leitura de atributo simples — medido em 9,1 milhões de
# chamadas por tick com 3.000 NPCs (1,23 s), maior item isolado do perfil depois do
# quadrático de casamento. `NPC.is_adulto`/`is_idoso`/`esta_vivo`/`eh_dependente` são
# chamados por NPC, várias vezes por tick: resolver o valor uma vez na importação e
# comparar contra a constante evita repetir o descritor a cada chamada.
_ESTAGIO_VIDA_BEBE = EstagioVida.BEBE.value
_ESTAGIO_VIDA_CRIANCA = EstagioVida.CRIANCA.value
_ESTAGIO_VIDA_ADULTO = EstagioVida.ADULTO.value
_ESTAGIO_VIDA_IDOSO = EstagioVida.IDOSO.value
_ESTAGIO_VIDA_MORTO = EstagioVida.MORTO.value

PROFISSAO_DEPENDENTE = "dependente"

class EstadoCivil(Enum):
    SOLTEIRO = "solteiro"
    CASADO = "casado"
    VIUVO = "viuvo"

class CategoriaLocal(Enum):
    FAZENDA      = "fazenda"
    QUARTEL      = "quartel"
    TAVERNA      = "taverna"
    UNIVERSIDADE = "universidade"
    FORJA        = "forja"
    MERCADO      = "mercado"
    RESIDENCIA   = "residencia"
    PUBLICO      = "publico"
    GENERIC      = "generic"

class ProfissaoID(Enum):
    FAZENDEIRO  = "fazendeiro"
    GUARDA      = "guarda"
    TABERNEIRO  = "taberneiro"
    PROFESSOR   = "professor"
    MEDICO      = "medico"
    COMERCIANTE = "comerciante"
    OPERARIO    = "operário"
    OCIOSO      = "ocioso"

class CategoriaSistema(Enum):
    AGRICULTURA = "agricultura"
    MILITAR     = "militar"
    SOCIAL      = "social"
    EDUCACAO    = "educacao"
    SAUDE       = "saude"
    COMERCIO    = "comercio"
    INDUSTRIA   = "industria"
    NENHUM      = "nenhum"

class TipoLocal(Enum):
    OFICINA  = "Oficina"
    CAMPO    = "Campo"
    MAR      = "Mar"
    DEFESA   = "Defesa"
    MAGIA    = "Magia"
    LOJA     = "Loja"
    SOCIAL   = "Social"
    CASA     = "Casa"
    RUINA    = "Ruina"
    OUTRO    = "Outro"

class EstadoInfraestrutura(Enum):
    """Estado qualitativo derivado do campo integridade (0–100)."""
    CONSERVADO  = "Conservado"   # 100–76
    DESGASTADO  = "Desgastado"   # 75–51
    DETERIORADO = "Deteriorado"  # 50–26
    CRITICO     = "Crítico"      # 25–11
    RUINA       = "Ruína"        # 10–0

class LoteEstado(Enum):
    """T01 (docs/PLANO_CIDADE_VIVA.md): estado do terreno urbano — a geometria do lote
    vem do GeoJSON do cartógrafo (imutável), o ESTADO vive só na tabela `lotes`
    (armadilha 2: `cartographer/` nunca escreve estado de simulação)."""
    LIVRE = "livre"
    OBRA = "obra"
    OCUPADO = "ocupado"

class HumorNPC(Enum):
    """`ordem` é a posição no "termômetro" de humor normal, do pior pro melhor — usado
    por `NPCMoodManager` pra decidir se o próximo passo de transição sobe ou desce um
    degrau. PANICO/MEDO ficam fora da escala normal (`ordem=None`): são forçados
    externamente (ex.: Modo Mestre) e não fazem parte da transição gradual (R-C04)."""
    ANGUSTIADO = ("Angustiado", 0)
    TRISTE     = ("Triste", 1)
    NEUTRO     = ("Neutro", 2)
    CONTENTE   = ("Contente", 3)
    ALEGRE     = ("Alegre", 4)
    PANICO     = ("Em Pânico", None)
    MEDO       = ("Amedrontado", None)

    def __init__(self, rotulo, ordem):
        self._value_ = rotulo
        self.ordem = ordem

    @classmethod
    def escala_normal(cls) -> list:
        """Os humores com posição na escala normal, do pior pro melhor."""
        return sorted((h for h in cls if h.ordem is not None), key=lambda h: h.ordem)

    @classmethod
    def _missing_(cls, value):
        """Permite `HumorNPC("Em Pânico")`, que é como o humor chega do banco e da IA.

        Era um bug silencioso: como `__init__` reatribui `_value_` para o rótulo, o mapa
        interno do Enum continua indexado pelas TUPLAS originais, então a busca por
        rótulo levantava ValueError para TODOS os humores. O efeito prático era que
        AFETAR_NPC, no Modo Mestre, caía sempre no fallback Neutro — o Mestre não
        conseguia assustar ninguém. Protegido por tests/test_mestre.py."""
        return next((h for h in cls if h.value == value), None)

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
    EXPANSAO_URBANA = "EXPANSAO_URBANA"

class VinculoSocial(Enum):
    """Classificação qualitativa de uma relação, derivada da afinidade acumulada
    entre dois NPCs (ver NPCSocialManager._classificar_vinculo)."""
    CONJUGE    = "Cônjuge"
    ALIADO     = "Aliado"
    AMIGO      = "Amigo"
    CONHECIDO  = "Conhecido"
    RIVAL      = "Rival"
    INIMIGO    = "Inimigo"

class MetaChave(Enum):
    """Chaves da tabela `mundo_meta` (sinalização entre run_simulation.py, o dashboard
    e o Modo Mestre — ver ARQUITETURA.md Seção 1: "Regra de processo"). Um erro de
    digitação numa string solta era silencioso: carregar_meta devolvia None e o
    sistema seguia com o default (R-B05)."""
    SIMULACAO_PAUSADA   = "simulacao_pausada"
    VELOCIDADE          = "velocidade_simulacao"
    AVANCAR_MINUTOS     = "mestre_avancar_minutos_restantes"
    HORA_FORMATADA      = "hora_simulada"
    HORA_ISO            = "hora_simulada_iso"
    CIDADE_SIMULADA     = "cidade_simulada"
    CIDADES_ATIVAS      = "cidades_ativas"
    MAPA_TERRENO        = "mapa_terreno"


class ComandoMestre(Enum):
    """Ações de mundo que o Modo Mestre aceita (R-F03). O valor é a string que a IA
    devolve no campo `comando` e que vai para a coluna `acoes_propostas` — resposta de
    LLM é entrada não confiável, então `AcaoProposta.de_payload` converte para este
    enum e descarta o que não existir, em vez de cair num `else` silencioso.

    O prompt do Mestre lista os comandos a partir daqui (`engine/ai/game_master.py`),
    nunca de uma cópia escrita à mão no .txt."""
    CRIAR_LOCAL    = "CRIAR_LOCAL"
    REATRIBUIR_NPC = "REATRIBUIR_NPC"
    DESTRUIR_LOCAL = "DESTRUIR_LOCAL"
    AFETAR_NPC     = "AFETAR_NPC"


@dataclass
class Local:
    id: str
    nome: str
    tipo: str
    cidade_id: int = None
    categoria: str = "generic"
    descricao: str = ""
    coordenadas: List[float] = field(default_factory=lambda: [0.0, 0.0])
    status: int = 1  # 1 = Ativo, 0 = Inativo/Destruído
    integridade: int = 100 # 0 a 100
    capacidade: int = 5
    salario_base: int = 100
    # Fase 4 (P2.2): campos que a geometria de cidade real (GeoJSON) carrega por
    # edifício. `tipo_local` é o nome de sabor dentro da categoria ampla de
    # `categoria` (ex.: categoria="forja", tipo_local="Ferreiro" ou "Oleiro") — dá
    # variedade narrativa sem precisar de um `CategoriaLocal` novo por profissão.
    tipo_local: str = ""
    bairro: str = ""
    dono_npc_id: str = ""


@dataclass
class Lote:
    """T01 (docs/PLANO_CIDADE_VIVA.md): terreno urbano como entidade de primeira classe.
    A GEOMETRIA (polígono, área, classe da frente) vem do GeoJSON do cartógrafo — aqui
    só o suficiente pra engine decidir "que terreno está livre nesta cidade" e onde ele
    fica. `id` é o mesmo id do lote gravado no GeoJSON (armadilha 3: posicional, estável
    — nunca um contador de emissão).

    `x`/`y` (não `coordenadas: List[float]` como `Local`) direto — O01 precisa ordenar
    lotes livres por distância ao quadrado (`(x-?)²+(y-?)²`) sem `sqrt`, e SQLite não
    tem função de distância; duas colunas REAL fazem isso com um ORDER BY simples,
    JSON não."""
    id: str
    cidade_id: int
    quarteirao_id: str
    bairro: str
    banda: int
    classe_frente: str
    area_m2: float
    x: float = 0.0
    y: float = 0.0
    estado: str = LoteEstado.LIVRE.value
    # T05: congelado no valor de `estado` na importação (T02) — nunca mais escrito
    # depois. É a base de comparação do "delta" que o mapa consome sem reabrir GeoJSON.
    estado_inicial: str = LoteEstado.LIVRE.value
    local_id: str = ""
    dono_npc_id: str = ""


@dataclass
class Cidade:
    """Uma cidade do mundo, importada de `world_manifest.json` (R-C06). Antes,
    `DatabaseManager.carregar_cidades()` devolvia `list[dict]` cru — a única forma de
    retorno crua entre `carregar_npcs`/`carregar_locais` (que já devolvem dataclass)."""
    id: int
    continente_uuid: str
    nome: str
    tamanho: str
    tipo: str
    x_global: int
    y_global: int


@dataclass
class NPC:
    id: str
    nome: str
    profissao: str
    local_trabalho_id: str
    localizacao_atual_id: str
    
    cidade_id: int = None
    casa_id: str = ""
    profissao_id: str = "ocioso"
    acao_atual: Acao = Acao.OCIOSO
    
    # Necessidades e Estado
    energia: float = 100.0
    dinheiro_total_pc: float = 500.0  # float desde a Frente 4: salário/custos pagos a cada tick de 1 min geram frações de PC
    social: float = 100.0
    fome: float = 0.0
    saude: int = 100 # 0 a 100
    humor: str = HumorNPC.NEUTRO.value
    
    # Atributos Biológicos e Ciclo de Vida
    # INVARIANTE (R-C05): genero/estagio_vida/humor guardam SEMPRE o .value do enum
    # correspondente (Genero/EstagioVida/HumorNPC) — é o que vai para a coluna TEXT do
    # SQLite. Nunca o membro do enum.
    genero: str = Genero.MASCULINO.value
    estagio_vida: str = EstagioVida.ADULTO.value
    estado_civil: str = EstadoCivil.SOLTEIRO.value
    conjuge_id: str = ""
    data_nascimento: str = ""
    pai_id: str = ""
    mae_id: str = ""
    gravidez_ticks: int = 0  # 0 = não gestante, >0 = gestante

    # Identidade gerada pela IA (Fase 2.3, dna.txt já pedia isso — só era jogado fora
    # em builder/populate.py). Uso na DECISÃO (traços modulando utilidade) é Fase 8;
    # por ora só persiste pra o Modo Mestre poder narrar quem cada NPC realmente é.
    raca: str = ""
    personalidade: str = ""
    background: str = ""

    genealogia: List[str] = field(default_factory=list)
    relacionamentos: Dict[str, int] = field(default_factory=dict)
    memoria_eventos: List[str] = field(default_factory=list)

    # Campo DERIVADO, recalculado por GameLoop a cada tick a partir dos moradores da
    # casa (R-C01). Não é persistido (ver DatabaseManager/RepositorioNPC) e não deve
    # ser escrito por nenhum outro módulo.
    num_dependentes: int = 0

    # A02 (docs/PLANO_POPULACAO_E_ESCALA.md): agenda de decisão — `None` significa
    # "nunca avaliado, processar agora". Como `num_dependentes`, NÃO é persistido: um
    # `recarregar_habitantes()` ou reinício do processo reseta os dois pra `None`, o
    # que só custa uma reavaliação a mais no próximo tick, nunca um NPC congelado.
    proximo_instante_decisao: datetime = None
    ultima_avaliacao: datetime = None


    @property
    def dinheiro_formatado(self) -> str:
        """Converte o total de PC para o formato PO, PP, PC. Arredonda só na exibição —
        o acúmulo fracionário (salário/custos pagos a cada tick de 1 min) fica intacto
        internamente."""
        total_inteiro = int(self.dinheiro_total_pc)
        po = total_inteiro // 1000
        resto_pp = total_inteiro % 1000
        pp = resto_pp // 100
        pc = resto_pp % 100

        parts = []
        if po > 0: parts.append(f"{po}po")
        if pp > 0: parts.append(f"{pp}pp")
        if pc > 0 or not parts: parts.append(f"{pc}pc")
        return ", ".join(parts)

    def is_adulto(self) -> bool:
        return self.estagio_vida == _ESTAGIO_VIDA_ADULTO

    def is_idoso(self) -> bool:
        return self.estagio_vida == _ESTAGIO_VIDA_IDOSO

    def pode_procriar(self) -> bool:
        return self.is_adulto() and self.saude > 0

    def esta_vivo(self) -> bool:
        return self.saude > 0 and self.estagio_vida != _ESTAGIO_VIDA_MORTO

    def eh_dependente(self) -> bool:
        """Bebê, criança ou adulto marcado como dependente — não trabalha, não
        socializa fora de casa e tem a conta paga por um responsável (R-B04). Antes
        desta unificação, a mesma expressão estava copiada em 6 lugares, e em
        movement.py a cópia já tinha divergido (só olhava 'bebe', não 'crianca')."""
        return (self.profissao == PROFISSAO_DEPENDENTE
                or self.estagio_vida in (_ESTAGIO_VIDA_BEBE, _ESTAGIO_VIDA_CRIANCA))

    def normalizar_necessidades(self) -> None:
        """Prende energia/fome/social/saúde na faixa válida (R-B09). Ponto único de
        clamp — as ações somam e subtraem livremente ao longo do tick e isto fecha a
        conta uma vez só, no fim. Antes, o mesmo clamp estava espalhado em `loop.py` (as
        4 necessidades) e de novo, parcialmente, em `actions.py` (só energia/social, em
        4 pontos diferentes)."""
        self.energia = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.energia))
        self.fome    = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.fome))
        self.social  = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.social))
        self.saude   = int(min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.saude)))

@dataclass
class Evento:
    id: str
    timestamp: str
    local_id: str
    envolvidos: List[str]
    tipo_evento: str
    modificador_afinidade: int
    resumo_estruturado: str
