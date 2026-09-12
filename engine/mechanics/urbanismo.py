"""
MODULE: urbanismo.py
FUNÇÃO: A cidade se preenche por necessidade — comércio por demanda (O02) e o gatilho
        de auto-expansão (X01), docs/PLANO_CIDADE_VIVA.md, Bloco O/X.

DESCRIÇÃO:
    Antes, o comércio de bairro era decidido UMA VEZ, na geração da cidade, por uma
    tabela de densidade (`um_a_cada_n_lotes`) — uma cidade que dobra de população
    continua com a mesma padaria. `GerenciadorUrbanismo` roda uma vez por dia
    simulado, por cidade com gente, e abre no máximo um estabelecimento novo por
    cidade por dia — sempre o de maior déficit (habitantes / habitantes_por_estabelecimento
    menos os já ativos).

    Recebe o mundo e a config, não a engine (R-F01) — mesmo padrão de
    `engine/mechanics/housing.py`.
"""
from ..models import Local, NPC
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo


class GerenciadorUrbanismo:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def processar_urbanismo(self) -> None:
        """Chamado uma vez por dia simulado (GameLoop._executar_rotinas_agendadas,
        junto de habitacao_hora) — uma passada por cidade COM GENTE (não por
        MetaChave.CIDADES_ATIVAS: aqui só importa onde há habitante vivo pra sentir
        falta de comércio, e isso já está em `mundo.npcs`, sem round-trip no banco)."""
        for cidade_id in self._cidades_com_gente():
            self._avaliar_comercio_por_demanda(cidade_id)

    def _cidades_com_gente(self) -> set:
        return {n.cidade_id for n in self._mundo.npcs if n.esta_vivo()}

    # ------------------------------------------------------------------
    # O02 — comércio por demanda
    # ------------------------------------------------------------------
    def _avaliar_comercio_por_demanda(self, cidade_id) -> None:
        cfg_urb = cfg_get(self._config, "urbanismo")
        habitantes_por_estabelecimento = cfg_get(cfg_urb, "habitantes_por_estabelecimento")
        habitantes = sum(1 for n in self._mundo.npcs if n.esta_vivo() and n.cidade_id == cidade_id)
        if habitantes == 0:
            return

        maior_deficit = 0
        categoria_escolhida = None
        for categoria, por_estabelecimento in habitantes_por_estabelecimento.items():
            ativos = len(self._mundo.indice.trabalho_por_categoria(cidade_id, categoria))
            deficit = (habitantes // por_estabelecimento) - ativos
            if deficit > maior_deficit:
                maior_deficit = deficit
                categoria_escolhida = categoria

        if categoria_escolhida is not None:
            self._abrir_estabelecimento(cidade_id, categoria_escolhida)

    def _abrir_estabelecimento(self, cidade_id, categoria: str) -> None:
        """Quem paga: o NPC adulto vivo da cidade com mais `dinheiro_total_pc`, acima
        do custo. Sem tesouro no projeto (KingdomManager só paga pensão/sopão), isso é
        uma regra econômica real, de graça: sem ninguém rico o bastante, a cidade
        simplesmente não cresce naquele dia."""
        cfg_urb = cfg_get(self._config, "urbanismo")
        custo = cfg_get(cfg_urb, "custo_estabelecimento_pc")

        candidatos = [n for n in self._mundo.npcs
                      if n.esta_vivo() and n.cidade_id == cidade_id
                      and n.is_adulto() and n.dinheiro_total_pc >= custo]
        if not candidatos:
            return
        empreendedor = max(candidatos, key=lambda n: n.dinheiro_total_pc)

        lote_id = self._reservar_lote_comercial(cidade_id, empreendedor)
        if lote_id is None:
            return

        lote = self._mundo.db.lotes.buscar_por_id(lote_id)
        nome_padrao = cfg_get(cfg_urb, "nome_padrao_por_categoria").get(categoria, categoria.capitalize())
        capacidade = cfg_get(cfg_urb, "capacidade_padrao_estabelecimento")
        salario = cfg_get(cfg_urb, "salario_padrao_estabelecimento")
        cidade = self._mundo.cidades.get(cidade_id)
        nome_cidade = cidade.nome if cidade else str(cidade_id)

        empreendedor.dinheiro_total_pc -= custo
        self._mundo.db.npcs.salvar(empreendedor)

        novo = Local(
            id=lote_id,
            nome=f"{nome_padrao} de {nome_cidade}",
            tipo=nome_padrao,
            categoria=categoria,
            cidade_id=cidade_id,
            descricao=f"{nome_padrao}, em construção — erguida por demanda da população.",
            dono_npc_id=empreendedor.id,
            coordenadas=[lote.x, lote.y],
            status=0,
            integridade=0,
            capacidade=capacidade,
            salario_base=salario,
            bairro=lote.bairro,
        )
        self._mundo.registrar_local(novo)
        WorldLogger.info(
            f"🏪 [URBANISMO] {empreendedor.nome} investiu {custo} PC e abriu {novo.nome} "
            f"(déficit de {categoria}) — obra em andamento.",
            npc=empreendedor,
        )

    def _reservar_lote_comercial(self, cidade_id, empreendedor: NPC):
        """Loja quer frente pra via de movimento (principal/anel) — tenta essas
        classes primeiro, cai pra qualquer lote livre se não houver."""
        casa_atual = self._mundo.locais.get(empreendedor.casa_id)
        perto_de = tuple(casa_atual.coordenadas) if casa_atual and casa_atual.coordenadas else None

        for classe in ("principal", "anel"):
            lote_id = self._mundo.db.lotes.reservar_livre(
                cidade_id=cidade_id, npc_id=empreendedor.id, perto_de=perto_de, classe_frente=classe)
            if lote_id is not None:
                return lote_id
        return self._mundo.db.lotes.reservar_livre(
            cidade_id=cidade_id, npc_id=empreendedor.id, perto_de=perto_de)
