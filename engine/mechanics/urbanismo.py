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

        nome_padrao = cfg_get(cfg_urb, "nome_padrao_por_categoria").get(categoria, categoria.capitalize())
        cidade = self._mundo.cidades.get(cidade_id)
        nome_cidade = cidade.nome if cidade else str(cidade_id)
        capacidade = cfg_get(cfg_urb, "capacidade_padrao_estabelecimento")
        salario = cfg_get(cfg_urb, "salario_padrao_estabelecimento")

        # O03: abrir_obra é o ÚNICO caminho pra um edifício novo nascer durante a
        # simulação — o mesmo que housing.py usa pra casa de casal.
        novo = self.abrir_obra(
            cidade_id, empreendedor, categoria, nome_padrao, f"{nome_padrao} de {nome_cidade}",
            capacidade, salario, preferir_frente=("principal", "anel"))
        if novo is None:
            return

        empreendedor.dinheiro_total_pc -= custo
        self._mundo.db.npcs.salvar(empreendedor)
        WorldLogger.info(
            f"🏪 [URBANISMO] {empreendedor.nome} investiu {custo} PC e abriu {novo.nome} "
            f"(déficit de {categoria}) — obra em andamento.",
            npc=empreendedor,
        )

    # ------------------------------------------------------------------
    # O03 — o único caminho pra um edifício nascer durante a simulação
    # ------------------------------------------------------------------
    def abrir_obra(self, cidade_id, dono_npc: NPC, categoria: str, tipo_local: str, nome: str,
                    capacidade: int, salario_base: int = 0, preferir_frente=None):
        """Reserva lote, cria o `Local` em obra (status=0, integridade=0) e devolve
        ele — ou `None` se não houver terreno (T01: `reservar_livre` já devolve
        `None` nesse caso, sem exceção; é o sinal de auto-expansão, X01).

        É o ÚNICO caminho pra um edifício novo nascer durante a simulação
        (armadilha 3, docs/PLANO_CIDADE_VIVA.md: o id do Local É o id do lote onde
        nasce) — `housing.py` (casa de casal) e `urbanismo.py` (comércio por demanda)
        chamam este método; nenhum dos dois duplica a sequência reservar/criar/marcar.
        `housing.py` continua dono da POLÍTICA ("qual casal, quando"); aqui é dono só
        da MECÂNICA ("como um edifício nasce").

        `preferir_frente`: sequência de classes de frente tentadas em ordem antes do
        fallback "qualquer lote livre" (loja quer frente pra via de movimento; casa
        não se importa, passa `None`)."""
        casa_atual = self._mundo.locais.get(dono_npc.casa_id)
        perto_de = tuple(casa_atual.coordenadas) if casa_atual and casa_atual.coordenadas else None

        lote_id = None
        for classe in (preferir_frente or ()):
            lote_id = self._mundo.db.lotes.reservar_livre(
                cidade_id=cidade_id, npc_id=dono_npc.id, perto_de=perto_de, classe_frente=classe)
            if lote_id is not None:
                break
        if lote_id is None:
            lote_id = self._mundo.db.lotes.reservar_livre(
                cidade_id=cidade_id, npc_id=dono_npc.id, perto_de=perto_de)
        if lote_id is None:
            return None

        lote = self._mundo.db.lotes.buscar_por_id(lote_id)
        obra = Local(
            id=lote_id,
            nome=nome,
            tipo=tipo_local,
            categoria=categoria,
            cidade_id=cidade_id,
            descricao=f"{nome}, em construção.",
            dono_npc_id=dono_npc.id,
            coordenadas=[lote.x, lote.y],
            status=0,
            integridade=0,
            capacidade=capacidade,
            salario_base=salario_base,
            bairro=lote.bairro,
        )
        self._mundo.registrar_local(obra)
        return obra
