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
from ..models import Acao, Local, TipoLocal, CategoriaLocal
from ..logger import WorldLogger
from ..utils import NPCUtils


class NPCHousingManager:
    @staticmethod
    def processar_habitacao(engine):
        """
        Verifica diariamente casas superlotadas e inicia a construção de novos
        lotes para aliviar o espaço.

        Gatilho conservador:
        - A casa deve estar superlotada (moradores > capacidade).
        - Deve existir ao menos um casal de ADULTOS com cônjuge.
        - NENHUM morador da casa deve já ter uma obra em andamento.
        """
        por_casa = NPCUtils.agrupar_por_casa(engine.npcs)

        for casa_id, moradores in por_casa.items():
            if casa_id not in engine.locais:
                continue

            casa = engine.locais[casa_id]
            if len(moradores) <= casa.capacidade:
                continue  # Casa não superlotada, nada a fazer

            # Bug C: filtrar apenas adultos com cônjuge
            casais = [
                m for m in moradores
                if m.is_adulto() and NPCUtils.tem_conjuge(m)
            ]
            if not casais:
                continue

            # Bug B: se QUALQUER morador já tem obra em andamento, não disparar nova obra
            ja_ha_obra = any(
                NPCUtils.obter_obra_do_npc(engine.locais, m) is not None
                for m in moradores
            )
            if ja_ha_obra:
                continue

            # Escolhe o primeiro casal adulto disponível
            n1 = casais[0]
            n2 = next((m for m in moradores if m.id == n1.conjuge_id), None)

            # Requer o cartógrafo para alocar coordenadas no mapa
            from ..world.cartographer import Cartographer
            import json

            grid_json = engine.db.carregar_meta("mapa_terreno")
            if not grid_json:
                continue

            carto = Cartographer()
            carto.grid = json.loads(grid_json)

            nova_obra_id = f"casa_obra_{int(time.time())}_{random.randint(0, 999)}"
            coords = carto.assign_coordinates([nova_obra_id])
            if nova_obra_id not in coords:
                continue

            engine.db.salvar_meta("mapa_terreno", carto.export_map())

            obra = Local(
                id=nova_obra_id,
                nome=f"Obra de {n1.nome.split()[-1]}",
                tipo=TipoLocal.CASA.value,
                categoria=CategoriaLocal.RESIDENCIA.value,
                descricao=f"Dono: {n1.id}",
                coordenadas=coords[nova_obra_id],
                status=0,
                integridade=0,
                capacidade=5,
            )
            engine.locais[nova_obra_id] = obra
            engine.db.salvar_local(obra)

            WorldLogger.info(
                f"🏗️ [EXPANSÃO URBANA] A família de {n1.nome} iniciou a construção de "
                f"uma nova casa — superlotação em {casa.nome} "
                f"({len(moradores)}/{casa.capacidade} moradores).",
                npc=n1,
            )
