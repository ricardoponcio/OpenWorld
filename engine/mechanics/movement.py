"""
MODULE: movement.py
FUNÇÃO: Deslocamento dos NPCs entre os locais da cidade.

DESCRIÇÃO:
    Resolve o destino de cada NPC e aplica o deslocamento, com as salvaguardas que
    impedem um NPC de parar num local inativo ou um dependente de sair de casa.

    Recebe o mundo e a config, não a engine (R-F01): só precisa do dicionário de
    locais e de alguns limiares de decisão, e é isso que permite exercitá-lo com um
    mundo sintético em memória.
"""
import random
from ..models import NPC, Acao
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo


class NPCMovementManager:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def mover_para(self, npc: NPC, local_id: str):
        """Move o NPC para um local específico com validação de segurança."""
        locais = self._mundo.locais

        # Se for bebê ou dependente, ele deve SEMPRE ficar em sua própria residência!
        if npc.eh_dependente():
            local_id = npc.casa_id

        # Se o local de destino não existe ou está inativo (status=0), volta para casa
        local_destino = locais.get(local_id) if locais else None
        if not local_destino or local_destino.status != 1:
            local_id = npc.casa_id

        # Garante que a casa existe, caso contrário tenta a primeira casa ativa DA
        # PRÓPRIA CIDADE (P04, docs/PLANO_CIDADE_VIVA.md): `casas_disponiveis[0]` de
        # uma lista GLOBAL podia mudar o NPC de cidade silenciosamente — mover alguém
        # de cidade é decisão de migração, não de fallback. Sem casa na cidade dele,
        # ele fica onde está (com um warning), não teleporta pro primeiro lar livre
        # do mundo.
        if local_id not in locais:
            casas_disponiveis = self._mundo.indice.residencias_ativas(npc.cidade_id)
            if casas_disponiveis:
                local_id = casas_disponiveis[0]
            else:
                WorldLogger.warning(
                    f"⚠️ [MOVIMENTO] {npc.nome} não tem casa válida na própria cidade "
                    f"(cidade_id={npc.cidade_id}) — permanecendo em {npc.localizacao_atual_id}.",
                    npc=npc)
                return

        # Se mudou de localização, atualiza
        if npc.localizacao_atual_id != local_id:
            nome_local = locais[local_id].nome if local_id in locais else local_id
            WorldLogger.debug(f"🚶 {npc.nome} deslocou-se para {nome_local}.", npc=npc)
            self._mundo.mover_npc(npc, local_id)

    def mover_para_casa(self, npc: NPC):
        """Move o NPC para sua residência oficial."""
        self.mover_para(npc, npc.casa_id)

    def mover_para_obra(self, npc: NPC, obra_id: str):
        """Move o NPC para uma obra em andamento (status 0)."""
        locais = self._mundo.locais
        if npc.eh_dependente():
            local_id = npc.casa_id
        else:
            local_id = obra_id

        if npc.localizacao_atual_id != local_id:
            nome_local = locais[local_id].nome if locais and local_id in locais else local_id
            WorldLogger.debug(f"🚶 {npc.nome} deslocou-se para a {nome_local}.", npc=npc)
            self._mundo.mover_npc(npc, local_id)

    def mover_para_trabalho(self, npc: NPC):
        """Move o NPC para seu local de trabalho se ativo, senão vai para casa e fica ocioso."""
        locais = self._mundo.locais
        loc_trab = locais.get(npc.local_trabalho_id) if locais else None

        if loc_trab and loc_trab.status == 1:
            self.mover_para(npc, npc.local_trabalho_id)
        else:
            self.mover_para_casa(npc)
            npc.acao_atual = Acao.OCIOSO

    def mover_para_social(self, npc: NPC):
        """Move o NPC para um local social ativo ou para casa se tiver dependentes/nenhum local.

        P01 (docs/PLANO_CIDADE_VIVA.md): consulta o índice por cidade em vez de varrer
        `mundo.locais` inteiro (Seção 1.6 — este era um dos laços mais caros do tick)."""
        sociais = self._mundo.indice.sociais(npc.cidade_id)

        num_dep = npc.num_dependentes
        chance_ficar_em_casa = cfg_get(self._config, "ia_decisao", "chance_ficar_em_casa_com_dependentes")
        if num_dep > 0 and random.random() < chance_ficar_em_casa:
            self.mover_para_casa(npc)
        elif sociais:
            # NPCs com menos de limiar_pobreza dão preferência a locais públicos/gratuitos (praças, parques, arenas, etc.)
            cfg_dec = cfg_get(self._config, "ia_decisao")
            limiar_pobreza = cfg_get(cfg_dec, "limiar_pobreza_pc")

            if npc.dinheiro_total_pc < limiar_pobreza:
                sociais_gratuitos = self._mundo.indice.sociais_publicos(npc.cidade_id)
                if sociais_gratuitos:
                    self.mover_para(npc, random.choice(sociais_gratuitos))
                    return

            self.mover_para(npc, random.choice(sociais))
        else:
            self.mover_para_casa(npc)

    def mover_para_restaurante(self, npc: NPC):
        """Move o NPC para uma taverna/praça ativa, ou casa em último caso."""
        locais_comida = self._mundo.indice.comida(npc.cidade_id)

        # Chance de comer fora (restaurante/taverna) em vez de em casa — o resto vai pra
        # casa, o que reduz superlotação de restaurantes.
        chance_comer_fora = cfg_get(self._config, "ia_decisao", "chance_comer_fora_de_casa")
        if locais_comida and random.random() < chance_comer_fora:
            self.mover_para(npc, random.choice(locais_comida))
        else:
            self.mover_para_casa(npc)

    def mover_aleatoriamente(self, npc: NPC):
        """Move o NPC aleatoriamente entre locais públicos/sociais ou sua casa. A
        própria casa do NPC sempre é uma opção válida (LocationUtils.is_local_passeio
        antes tratava isso caso a caso; o índice só sabe do que é compartilhado, então a
        casa entra à parte aqui) — evita que ociosos invadam quartéis e fazendas."""
        locais_permitidos = list(self._mundo.indice.passeio(npc.cidade_id))
        if npc.casa_id and npc.casa_id not in locais_permitidos:
            locais_permitidos.append(npc.casa_id)

        if locais_permitidos:
            self.mover_para(npc, random.choice(locais_permitidos))
        else:
            self.mover_para_casa(npc)
