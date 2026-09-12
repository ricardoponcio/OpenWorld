"""
MODULE: social.py
FUNÇÃO: Gerenciamento de Interações Sociais Gerais.

DESCRIÇÃO:
    Gerencia encontros físicos dinâmicos entre NPCs e calcula os ticks de
    interação ativa do simulador.

    Recebe o mundo e a config, não a engine (R-F01). O gerenciador de casamento entra
    pelo construtor: um teste de interação social pode passar um dublê e medir só a
    afinidade, sem que um romance surpresa altere o resultado.
"""
import time
import random
from ..models import NPC, Evento, TipoEvento, VinculoSocial
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils
from ..config_loader import cfg_get
from ..tempo import RelogioMundo
from ..mundo import EstadoDoMundo
from .marriage import NPCMarriageManager


class NPCSocialManager:
    def __init__(self, mundo: EstadoDoMundo, config: dict, casamento: NPCMarriageManager = None):
        self._mundo = mundo
        self._config = config
        self._casamento = casamento or NPCMarriageManager(mundo, config)

    def processar_interacoes(self):
        """
        Varre todos os locais do mapa à procura de NPCs presentes e gera eventos
        de interação social ativa e romance dinâmico entre eles.
        """
        # Utiliza o helper para agrupar NPCs por localização
        por_local = NPCUtils.agrupar_npcs_por_localizacao(self._mundo.npcs, ignorar_dormindo=True)
            
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        chance_interacao = cfg_get(cfg_bio, "interacao_chance")
            
        for loc_id, lista in por_local.items():
            if len(lista) >= 2:
                if random.random() < chance_interacao:
                    n1, n2 = random.sample(lista, 2)
                    if n1.id != n2.id:
                        self.processar_interacao_social(n1, n2, loc_id)

        # Processar coabitação entre casais de alta afinidade no final do tick social
        self._casamento.processar_coabitacao()

    def processar_interacao_social(self, n1: NPC, n2: NPC, loc_id: str):
        """
        Processa um encontro físico e interação social ativa entre dois NPCs em um local.
        
        Calcula os ajustes de afinidade e relacionamentos, determina o vínculo RPG mútua,
        grava os eventos históricos da simulação e avalia a chance de romance físico surpresa
        se ambos forem solteiros e compatíveis.
        """
        local_nome = self._mundo.locais[loc_id].nome if loc_id in self._mundo.locais else loc_id
        
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        ganhos = cfg_get(cfg_bio, "interacao_afinidade_ganhos")
        mod = random.choice(ganhos)
        nova_afinidade = n1.relacionamentos.get(n2.id, 0) + mod
        
        n1.relacionamentos[n2.id] = nova_afinidade
        n2.relacionamentos[n1.id] = nova_afinidade
        
        # Determinar Vínculo
        vinculo = NPCSocialManager._classificar_vinculo(nova_afinidade, cfg_bio).value

        # Salvar na tabela oficial de relacionamentos
        self._mundo.db.npcs.salvar_relacionamento(n1.id, n2.id, nova_afinidade, vinculo)

        tipo = "CONVERSA" if mod >= 0 else "DISCUSSAO"
        resumo = f"{n1.nome} e {n2.nome} tiveram uma {tipo} em {local_nome}."
        timestamp_rpg = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
        
        evento = Evento(f"evt_{int(time.time())}_{random.randint(0,999)}", 
                        timestamp_rpg, loc_id, [n1.id, n2.id], tipo, mod, resumo)
        
        self._mundo.db.eventos.salvar(evento)
        WorldLogger.debug(f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})", npc=n1)
        WorldLogger.queue_db_log(n2, "DEBUG", f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})")

        # --- ROMANCE FÍSICO: Decisão de coabitação durante conversa real ---
        # Carrega a chance de romance surpresa físico de forma configurável
        chance_romance = cfg_get(cfg_bio, "casamento_chance_romance_fisico")
        
        if self._casamento.verificar_elegibilidade_casamento(n1, n2, nova_afinidade):
            if random.random() < chance_romance:
                casa_escolhida = n1.casa_id or n2.casa_id
                if casa_escolhida:
                    # Realizar casamento completo e atômico no gerenciador de casamentos
                    self._casamento.realizar_casamento(n1, n2, casa_escolhida, surpresa=True)

    @staticmethod
    def _classificar_vinculo(afinidade: float, cfg_bio: dict) -> VinculoSocial:
        """Classifica o vínculo pela afinidade acumulada. Testa os limiares negativos
        do mais extremo pro menos extremo (R-B01) — a ordem inversa deixava INIMIGO
        inalcançável: qualquer afinidade abaixo de -50 já satisfazia '< limiar_rival'
        (-20) primeiro e nunca chegava a checar '< limiar_inimigo'."""
        if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_aliado"):
            return VinculoSocial.ALIADO
        if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_amigo"):
            return VinculoSocial.AMIGO
        if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_inimigo"):
            return VinculoSocial.INIMIGO
        if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_rival"):
            return VinculoSocial.RIVAL
        return VinculoSocial.CONHECIDO
