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
import time
import random
import json
from ..models import Acao, Local, TipoLocal, CategoriaLocal, NPC
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils
from ..geo import GeoUtils
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo

class NPCHousingManager:
    """Expansão urbana: detecta casas superlotadas e inicia obras.

    Recebe o mundo (não a engine inteira) — precisa de locais, npcs, cidades e do
    repositório de locais, e de nada mais. Isso é o que permite testá-lo com um
    mundo sintético em memória (R-F01)."""

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def iniciar_obra_para_casal(self, n1: NPC, n2: NPC = None) -> bool:
        """
        Cria uma nova obra de residência alocada no mapa para o casal especificado.
        Reutilizável para expansão urbana e novos casamentos.
        """
        # Evita duplicar se já possui obra ativa em andamento
        if NPCUtils.obter_obra_do_npc(self._mundo, n1) or (n2 and NPCUtils.obter_obra_do_npc(self._mundo, n2)):
            return False

        cfg_urbano = cfg_get(self._config, "geracao_urbana")
        raio = cfg_get(cfg_urbano, "locais_raio_px")
        nivel_mar = cfg_get(self._config, "cartografia", "nivel_mar")

        cidade = self._mundo.cidades.get(n1.cidade_id)
        cx, cy = (cidade.x_global, cidade.y_global) if cidade else (0, 0)

        nova_obra_id = f"casa_obra_{int(time.time())}_{random.randint(0, 999)}"
        # Fase 2.1 (P0.3): coordenada de MUNDO ao redor da própria cidade do NPC, não
        # mais uma grade local fake — mesma convenção de builder/populate.py.
        x, y = GeoUtils.sortear_ponto_em_terra(cx, cy, raio, nivel_mar)

        sobrenome = n1.nome.split()[-1]

        obra = Local(
            id=nova_obra_id,
            nome=f"Obra de {sobrenome}",
            tipo=TipoLocal.CASA.value,
            categoria=CategoriaLocal.RESIDENCIA.value,
            cidade_id=n1.cidade_id,
            descricao=f"Obra da família {sobrenome}, em construção.",
            dono_npc_id=n1.id,
            coordenadas=[x, y],
            status=0,
            integridade=0,
            capacidade=cfg_get(cfg_urbano, "capacidade_padrao_residencia"),
        )
        self._mundo.registrar_local(obra)
        return True

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
