"""
MODULE: decay.py
FUNÇÃO: Sistema de Decadência e Manutenção de Infraestrutura.

DESCRIÇÃO:
    Gerencia o ciclo de vida físico das construções da vila.
    Toda parametrização numérica vem de config.json["infraestrutura"] via cfg_get.
    cfg_get lança KeyError se a chave estiver ausente — nenhum valor padrão silencioso.

    Fluxo (chamado uma vez por DIA simulado):
      1. processar_desgaste()  — erosão passiva + penalidade de superlotação
      2. _aplicar_consequencias() — efeitos estruturais por limiar
      3. processar_reparos_espontaneos() — manutenção informal por NPCs

    Recebe o mundo e a config, não a engine (R-F01): precisa dos locais, dos NPCs
    (para ocupação e reparo) e do repositório de locais, e de nada mais.
"""
import random
from ..models import Local, EstagioVida, TipoLocal, EstadoInfraestrutura
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo


class InfrastructureManager:
    """
    Gerenciador do ciclo de vida físico das construções.
    Toda parametrização lida via cfg_get — crash imediato se chave ausente no config.json.

    X03 (docs/PLANO_MUNDO_CRIVEL.md, decisão ❽): `processar_desgaste`/
    `processar_reparos_espontaneos` moravam em `run_simulation.py`, fora de
    qualquer benchmark — duas chaves de hora (cada método tem a própria) porque as
    outras mecânicas de `GameLoop._rotinas_diarias` só declaram uma.
    """
    CADENCIA = "por_dia"
    CADENCIA_HORA_CONFIG_DESGASTE = "desgaste_hora"
    CADENCIA_HORA_CONFIG_REPAROS = "reparos_hora"

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def _cfg(self) -> dict:
        """Retorna o bloco de configuração de infraestrutura (falha se ausente)."""
        return cfg_get(self._config, "infraestrutura")

    @staticmethod
    def estado_atual(local: Local, cfg: dict) -> EstadoInfraestrutura:
        """Classifica o estado qualitativo do local com base na integridade."""
        i = local.integridade
        if i <= cfg_get(cfg, "limiar_ruina"):
            return EstadoInfraestrutura.RUINA
        if i <= cfg_get(cfg, "limiar_critico"):
            return EstadoInfraestrutura.CRITICO
        if i <= cfg_get(cfg, "limiar_deteriorado"):
            return EstadoInfraestrutura.DETERIORADO
        if i <= cfg_get(cfg, "limiar_desgastado"):
            return EstadoInfraestrutura.DESGASTADO
        return EstadoInfraestrutura.CONSERVADO

    # ------------------------------------------------------------------
    # Pipeline principal (chamada diária)
    # ------------------------------------------------------------------

    def processar_desgaste(self):
        """
        Aplica desgaste passivo e por uso a todos os locais ativos.
        Deve ser chamado uma vez por dia simulado.

        V04 (docs/PLANO_MUNDO_CRIVEL.md, Bloco V): a penalidade de superlotação era
        O(locais × NPCs) — 1.319 ms medidos com 26.748 locais e 840 NPCs; ~88 s/dia
        projetado com 25.000 NPCs, sozinho quase 3× o orçamento de 7 dias de D13.
        `_contar_ocupacao_por_local` monta o mapa UMA vez (O(NPCs)), não por local.
        """
        cfg = self._cfg()
        desgaste_por_categoria: dict = cfg_get(cfg, "desgaste_por_categoria")
        desgaste_padrao: float   = cfg_get(cfg, "desgaste_padrao")
        desgaste_excedente: float = cfg_get(cfg, "desgaste_por_excedente")
        categorias_empregadoras = cfg_get(self._config, "urbanismo", "categorias_empregadoras")
        ocupacao_por_local = self._contar_ocupacao_por_local()

        for local_id, local in list(self._mundo.locais.items()):
            # Ruínas e obras em andamento não decaem
            if local.tipo == TipoLocal.RUINA.value or local.status == 0:
                continue

            # Desgaste passivo pela categoria de sistema; usa desgaste_padrao se
            # categoria não mapeada (V04: era por `tipo`, cobria só 2,3% dos locais)
            taxa = desgaste_por_categoria.get(local.categoria, desgaste_padrao)

            # Penalidade por superlotação (só categorias empregadoras — a mesma
            # lista de V02 — nunca residências)
            if local.categoria in categorias_empregadoras:
                excedente = max(0, ocupacao_por_local.get(local_id, 0) - local.capacidade)
                taxa += excedente * desgaste_excedente

            local.integridade = max(0.0, local.integridade - taxa)
            self._mundo.registrar_local(local)

            self._aplicar_consequencias(local, local_id, cfg)

    def _contar_ocupacao_por_local(self) -> dict:
        """V04: um laço de N NPCs (vivos, com trabalho), não N × locais."""
        ocupacao = {}
        for npc in self._mundo.npcs:
            if npc.esta_vivo() and npc.local_trabalho_id:
                ocupacao[npc.local_trabalho_id] = ocupacao.get(npc.local_trabalho_id, 0) + 1
        return ocupacao

    def _aplicar_consequencias(self, local: Local, local_id: str, cfg: dict):
        """Avalia o estado atual e aplica efeitos estruturais conforme os limiares."""
        estado = InfrastructureManager.estado_atual(local, cfg)

        if estado == EstadoInfraestrutura.RUINA and local.tipo != TipoLocal.RUINA.value:
            self._colapsar_para_ruina(local, local_id)

        elif estado == EstadoInfraestrutura.CRITICO and local.status == 1:
            self._fechar_local(local, local_id)

        elif estado == EstadoInfraestrutura.DETERIORADO:
            if random.random() < cfg_get(cfg, "chance_log_deteriorado"):
                WorldLogger.info(
                    f"⚠️  [INFRAESTRUTURA] {local.nome} está em estado "
                    f"{EstadoInfraestrutura.DETERIORADO.value} "
                    f"(Integridade: {local.integridade:.0f}%). Necessita de reparos urgentes!",
                )

        elif estado == EstadoInfraestrutura.DESGASTADO:
            if random.random() < cfg_get(cfg, "chance_log_desgastado"):
                WorldLogger.debug(
                    f"🔧 [INFRAESTRUTURA] {local.nome} mostra sinais de "
                    f"{EstadoInfraestrutura.DESGASTADO.value.lower()} "
                    f"(Integridade: {local.integridade:.0f}%).",
                )

    def _fechar_local(self, local: Local, local_id: str):
        """
        Fecha um local em estado crítico e desvincula seus trabalhadores.
        O JobMarket detectará os desempregados e os realocará no próximo ciclo.
        """
        local.status = 0
        self._mundo.desativar_local(local.id)
        WorldLogger.info(
            f"🚧 [INFRAESTRUTURA] {local.nome} foi FECHADO por condições estruturais "
            f"{EstadoInfraestrutura.CRITICO.value} "
            f"(Integridade: {local.integridade:.0f}%). Trabalhadores foram dispensados.",
        )
        for npc in self._mundo.npcs:
            if npc.local_trabalho_id == local_id and npc.esta_vivo():
                npc.local_trabalho_id = None
                self._mundo.db.npcs.salvar(npc)
                self._mundo.acordar(npc)  # A03: perdeu o emprego, reavalia agora
                WorldLogger.debug(
                    f"  └─ {npc.nome} ficou desempregado(a) — local fechado por deterioração.",
                    npc=npc,
                )

    def _colapsar_para_ruina(self, local: Local, local_id: str):
        """
        Transforma o local em Ruína: tipo=TipoLocal.RUINA, status=0, integridade=0.
        Ruínas são passíveis de reconstrução futura por NPCs com recursos suficientes.

        T04 (docs/PLANO_CIDADE_VIVA.md): o LOTE volta a 'livre' — o id do Local É o id
        do lote (armadilha 3), e `db.lotes.liberar` já é condicional a estado='ocupado'
        (não atropela se alguém já reservou o lote de novo antes desta chamada rodar).
        O Local em si continua com status=0 pra narrativa ("as ruínas da antiga forja").
        """
        nome_original = local.nome
        local.tipo        = TipoLocal.RUINA.value
        local.status      = 0
        local.integridade = 0
        local.capacidade  = 0
        local.nome        = f"Ruínas de {nome_original}"
        self._mundo.desativar_local(local.id)
        self._mundo.db.lotes.liberar(local_id)
        WorldLogger.info(
            f"💀 [COLAPSO] {nome_original} entrou em colapso total e se tornou uma "
            f"{EstadoInfraestrutura.RUINA.value}! Requer reconstrução completa.",
        )
        for npc in self._mundo.npcs:
            if npc.local_trabalho_id == local_id and npc.esta_vivo():
                npc.local_trabalho_id = None
                self._mundo.db.npcs.salvar(npc)
                self._mundo.acordar(npc)  # A03: perdeu o emprego, reavalia agora

    # ------------------------------------------------------------------
    # Reparos espontâneos (chamada diária, após processar_desgaste)
    # ------------------------------------------------------------------

    def processar_reparos_espontaneos(self):
        """
        NPCs adultos com energia e PC suficientes têm uma chance de realizar
        manutenção informal em locais danificados. Nenhum valor padrão — tudo do config.
        """
        cfg = self._cfg()
        custo:       int   = cfg_get(cfg, "custo_reparo_espontaneo")
        ganho:       int   = cfg_get(cfg, "reparo_integridade_ganho")
        chance:      float = cfg_get(cfg, "chance_reparo_espontaneo")
        energia_min: float = cfg_get(cfg, "energia_minima_reparo")
        limiar_deg:  int   = cfg_get(cfg, "limiar_desgastado")

        locais_danificados = [
            (l_id, l) for l_id, l in self._mundo.locais.items()
            if 0 < l.integridade < limiar_deg
            and l.status == 1
            and l.tipo != TipoLocal.RUINA.value
        ]
        if not locais_danificados:
            return

        for npc in self._mundo.npcs:
            if not npc.esta_vivo():
                continue
            if npc.estagio_vida != EstagioVida.ADULTO.value:
                continue
            if npc.energia < energia_min or npc.dinheiro_total_pc < custo:
                continue
            if random.random() >= chance:
                continue

            local_id, local = random.choice(locais_danificados)
            npc.dinheiro_total_pc -= custo
            local.integridade = min(100.0, local.integridade + ganho)
            self._mundo.registrar_local(local)
            self._mundo.db.npcs.salvar(npc)
            WorldLogger.debug(
                f"🔧 [REPARO ESPONTÂNEO] {npc.nome} realizou manutenção em {local.nome} "
                f"(Integridade: {local.integridade:.0f}% | Custo: {custo} PC)",
                npc=npc,
            )
