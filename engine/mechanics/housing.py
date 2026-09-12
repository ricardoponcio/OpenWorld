"""
MODULE: housing.py
FUNÇÃO: Gerenciamento de Habitação e Expansão Urbana.

DESCRIÇÃO:
    Verifica diariamente casas superlotadas e inicia construção de novas moradias
    quando necessário. Regras de disparo são conservadoras para evitar cascatas
    de obras (Bug B corrigido).

CORREÇÕES APLICADAS:
    Bug B: O gatilho de nova obra agora verifica se QUALQUER morador da casa
           já possui uma obra em andamento — não apenas o casal escolhido.
    Bug C: A seleção de casais filtra explicitamente por is_adulto() antes de
           verificar tem_conjuge(), evitando que bebês/crianças sejam donos de obras.
"""
from ..models import Acao, TipoLocal, CategoriaLocal, NPC
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo
from .urbanismo import GerenciadorUrbanismo

class NPCHousingManager:
    """Expansão urbana: detecta casas superlotadas e inicia obras.

    Recebe o mundo (não a engine inteira) — precisa de locais, npcs, cidades e do
    repositório de locais, e de nada mais. Isso é o que permite testá-lo com um
    mundo sintético em memória (R-F01). `urbanismo` é colaborador de domínio (O03):
    dono da MECÂNICA de "como um edifício nasce" (`abrir_obra`); este gerenciador
    continua dono só da POLÍTICA — qual casal, quando."""

    def __init__(self, mundo: EstadoDoMundo, config: dict, urbanismo: GerenciadorUrbanismo = None):
        self._mundo = mundo
        self._config = config
        self._urbanismo = urbanismo or GerenciadorUrbanismo(mundo, config)

    def iniciar_obra_para_casal(self, n1: NPC, n2: NPC = None) -> bool:
        """
        Cria uma nova obra de residência num LOTE REAL (O01, docs/PLANO_CIDADE_VIVA.md)
        — reserva o lote livre mais próximo da casa atual do casal (armadilha 3: o id
        do Local É o id do lote), em vez de sortear um ponto qualquer em terra firme
        que podia cair no meio do mato, do outro lado do muro, ou em cima de outro
        edifício. Reutilizável para expansão urbana e novos casamentos.
        """
        # Evita duplicar se já possui obra ativa em andamento
        if NPCUtils.obter_obra_do_npc(self._mundo, n1) or (n2 and NPCUtils.obter_obra_do_npc(self._mundo, n2)):
            return False

        cfg_urbano = cfg_get(self._config, "geracao_urbana")
        sobrenome = n1.nome.split()[-1]

        # O03: abrir_obra (urbanismo.py) é o único caminho pra um edifício novo nascer
        # — housing.py escolhe o casal e monta o nome, urbanismo reserva o lote e cria
        # o Local em obra.
        # `abrir_obra` já dispara `avaliar_expansao` (X01) sozinho quando não há lote
        # livre — nada a fazer aqui além de esperar o próximo gatilho; o casal
        # simplesmente não constrói agora.
        obra = self._urbanismo.abrir_obra(
            n1.cidade_id, n1, CategoriaLocal.RESIDENCIA.value, TipoLocal.CASA.value,
            f"Obra de {sobrenome}", cfg_get(cfg_urbano, "capacidade_padrao_residencia"))
        return obra is not None

    def processar_habitacao(self):
        """
        Verifica diariamente casas superlotadas e inicia a construção de novos
        lotes para aliviar o espaço.

        Gatilho conservador:
        - A casa deve estar superlotada (moradores > capacidade).
        - Deve existir ao menos um casal de ADULTOS com cônjuge.
        - NENHUM morador da casa deve já ter uma obra em andamento.
        """
        por_casa = NPCUtils.agrupar_por_casa(self._mundo.npcs)

        for casa_id, moradores in por_casa.items():
            if casa_id not in self._mundo.locais:
                continue

            casa = self._mundo.locais[casa_id]
            if len(moradores) <= casa.capacidade:
                continue  # Casa não superlotada, nada a fazer

            # Impede a superlotação-nômade: Apenas constrói se houver mais de 2 adultos/idosos na casa.
            # Se houver 2 ou menos adultos, qualquer superlotação é decorrente de excesso de filhos dependentes
            # da única família residente, que se moveriam em bloco e causariam superlotação na nova casa.
            adultos_vivos = [m for m in moradores if m.is_adulto() or m.is_idoso()]
            if len(adultos_vivos) <= 2:
                continue

            # Bug C: filtrar apenas adultos com cônjuge
            casais = [
                m for m in moradores
                if m.is_adulto() and NPCUtils.tem_conjuge(m)
            ]
            if not casais:
                continue

            # Ordenar casais pelo mais jovem (data de nascimento mais recente) usando o helper centralizado
            casais.sort(key=NPCUtils.obter_data_nascimento_valida, reverse=True)

            # Escolhe o casal mais jovem disponível
            n1 = casais[0]
            n2 = next((m for m in moradores if m.id == n1.conjuge_id), None)

            # Bug B: se QUALQUER morador já tem obra em andamento, não disparar nova obra
            ja_ha_obra = any(
                NPCUtils.obter_obra_do_npc(self._mundo, m) is not None
                for m in moradores
            )
            if ja_ha_obra:
                continue

            # Iniciar a construção da obra usando a função utilitária
            sucesso = self.iniciar_obra_para_casal(n1, n2)
            if sucesso:
                WorldLogger.info(
                    f"🏗️ [EXPANSÃO URBANA] A família de {n1.nome} iniciou a construção de "
                    f"uma nova casa — superlotação em {casa.nome} "
                    f"({len(moradores)}/{casa.capacidade} moradores).",
                    npc=n1,
                )
