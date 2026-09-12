"""
MODULE: urbanismo.py
FUNÇÃO: A cidade se preenche por necessidade — comércio por demanda (O02) e o gatilho
        de auto-expansão (X01/X03), docs/PLANO_CIDADE_VIVA.md, Bloco O/X.

DESCRIÇÃO:
    Antes, o comércio de bairro era decidido UMA VEZ, na geração da cidade, por uma
    tabela de densidade (`um_a_cada_n_lotes`) — uma cidade que dobra de população
    continua com a mesma padaria. `GerenciadorUrbanismo` roda uma vez por dia
    simulado, por cidade com gente, e abre no máximo um estabelecimento novo por
    cidade por dia — sempre o de maior déficit (habitantes / habitantes_por_estabelecimento
    menos os já ativos).

    X01/X03: quando os lotes livres de uma cidade caem abaixo do piso (absoluto ou
    fracionário), a cidade ganha um arrabalde novo — geometria pura em
    `cartographer/cities/expansao.py` (a camada de baixo nunca sabe de NPC/banco/
    arquivo, armadilha 2), aplicada aqui (a única escrita da engine num arquivo do
    cartógrafo).

    Recebe o mundo e a config, não a engine (R-F01) — mesmo padrão de
    `engine/mechanics/housing.py`.
"""
import json
import os
import random
import time

from ..models import Evento, Local, LoteEstado, Lote, NPC, TipoEvento
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo
from ..tempo import RelogioMundo

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.modelos import SitioCidade
from cartographer.cities.geometria.gerador import GeradorCidade
from cartographer.cities.expansao import gerar_arrabalde, numero_do_proximo_arrabalde

CIDADES_GEOJSON_DIR = "database/cidades"


class GerenciadorUrbanismo:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config
        # X01: "no máximo um arrabalde por cidade por dia" — guarda a DATA simulada
        # (não o tick) do último arrabalde aplicado por cidade; `avaliar_expansao` é
        # chamado tanto pela varredura diária quanto por `abrir_obra` devolvendo `None`
        # (item 3), e os dois compartilham este mesmo guarda.
        self._arrabalde_avaliado_em = {}

    def processar_urbanismo(self) -> None:
        """Chamado uma vez por dia simulado (GameLoop._executar_rotinas_agendadas,
        junto de habitacao_hora) — uma passada por cidade COM GENTE (não por
        MetaChave.CIDADES_ATIVAS: aqui só importa onde há habitante vivo pra sentir
        falta de comércio, e isso já está em `mundo.npcs`, sem round-trip no banco)."""
        for cidade_id in self._cidades_com_gente():
            self._avaliar_comercio_por_demanda(cidade_id)
            self.avaliar_expansao(cidade_id)

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
            # X01 item 3: a cidade saturou entre duas varreduras diárias — não espera
            # até amanhã pra reagir.
            self.avaliar_expansao(cidade_id)
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

    # ------------------------------------------------------------------
    # X01 — o gatilho: a cidade pede espaço
    # ------------------------------------------------------------------
    def avaliar_expansao(self, cidade_id) -> bool:
        """A cidade satura quando os lotes livres caem abaixo do piso ABSOLUTO ou do
        FRACIONÁRIO — o `or` importa: o absoluto protege a vila pequena (3% de 40
        lotes é 1, quase nunca dispara sozinho); o fracionário protege a capital (8
        lotes livres em 3.000 é saturação de verdade, não folga).

        No máximo um arrabalde por cidade por dia simulado — chamada de novo no mesmo
        dia (pela varredura diária OU por `abrir_obra` sem lote) é no-op."""
        hoje = self._mundo.data_simulada.date()
        if self._arrabalde_avaliado_em.get(cidade_id) == hoje:
            return False
        self._arrabalde_avaliado_em[cidade_id] = hoje

        cfg_urb = cfg_get(self._config, "urbanismo")
        contagem = self._mundo.db.lotes.contar_por_estado(cidade_id)
        total = sum(contagem.values())
        if total == 0:
            return False
        livres = contagem.get(LoteEstado.LIVRE.value, 0)
        satura_absoluto = livres < cfg_get(cfg_urb, "lotes_livres_minimo")
        satura_fracao = livres < cfg_get(cfg_urb, "fracao_livre_minima") * total
        if not (satura_absoluto or satura_fracao):
            return False
        return self._aplicar_arrabalde(cidade_id)

    # ------------------------------------------------------------------
    # X03 — persistir o arrabalde: acrescentar ao GeoJSON e ao banco
    # ------------------------------------------------------------------
    def _aplicar_arrabalde(self, cidade_id) -> bool:
        """Única escrita da engine num arquivo do cartógrafo, e ela é ACRESCENTAR
        features geradas por `cartographer/cities/expansao.py` — nunca editar feature
        existente, nunca gravar estado de simulação no arquivo (armadilha 2)."""
        cidade = self._mundo.cidades.get(cidade_id)
        if cidade is None:
            return False
        slug = cidade.nome.lower().replace(" ", "_")
        caminho = os.path.join(CIDADES_GEOJSON_DIR, f"{slug}.geojson")
        if not os.path.exists(caminho):
            return False
        with open(caminho, "r", encoding="utf-8") as f:
            geojson_atual = json.load(f)

        # O sítio (posição/tamanho/tipo/continente) já está gravado nas properties da
        # cidade (F8.3, `GeradorCidade.gerar`) — não precisa reabrir `world_manifest.json`.
        props_cidade = geojson_atual["properties"]
        sitio = SitioCidade.medir(
            {"nome": props_cidade["cidade"], "tamanho": props_cidade["tamanho"],
             "tipo": props_cidade["tipo"], "x_global": props_cidade["x_global"],
             "y_global": props_cidade["y_global"]},
            props_cidade["continente"], CARTOGRAPHER_CONFIG)

        cfg_urb = cfg_get(self._config, "urbanismo")
        numero_arrabalde = numero_do_proximo_arrabalde(geojson_atual)
        # Reproduzível — nunca `time.time()`, nunca `random` sem seed (Seção 10).
        seed_expansao = sitio.seed ^ (0xA53F * numero_arrabalde)
        lotes_alvo = cfg_get(cfg_urb, "lotes_livres_minimo") * 3

        features_novas, lotes_meta = gerar_arrabalde(
            sitio, geojson_atual, lotes_alvo, seed_expansao, CARTOGRAPHER_CONFIG,
            cfg_get(cfg_urb, "arrabalde_comprimento_m"), cfg_get(cfg_urb, "arrabalde_comprimento_max_m"))
        if not features_novas:
            WorldLogger.warning(
                f"[URBANISMO] {cidade.nome} saturou, mas nenhuma direção de expansão é "
                f"viável agora (terreno fora da janela, ou declividade acima do limite) "
                f"— tentará de novo amanhã.")
            return False

        geojson_atual["features"].extend(features_novas)
        self._escrever_atomico(caminho, geojson_atual)
        self._atualizar_indice_da_cidade(slug, geojson_atual)

        lotes_novos = [
            Lote(id=m["id"], cidade_id=cidade_id, quarteirao_id=m["quarteirao_id"],
                 bairro=m["bairro"], banda=m["banda"], classe_frente=m["classe_frente"],
                 area_m2=m["area_m2"], x=m["x"], y=m["y"], estado=LoteEstado.LIVRE.value,
                 estado_inicial=LoteEstado.LIVRE.value, local_id="", dono_npc_id="")
            for m in lotes_meta
        ]
        self._mundo.db.lotes.salvar_em_lote(lotes_novos)

        resumo = f"{cidade.nome} transbordou os muros — nasceu um arrabalde novo, com {len(lotes_novos)} lotes."
        evento = Evento(
            id=f"evt_expansao_{int(time.time())}_{random.randint(0, 999)}",
            timestamp=RelogioMundo.timestamp_rpg(self._mundo.data_simulada),
            local_id="", envolvidos=[], tipo_evento=TipoEvento.EXPANSAO_URBANA.value,
            modificador_afinidade=0, resumo_estruturado=resumo,
        )
        self._mundo.db.eventos.salvar(evento)
        WorldLogger.info(f"🏘️ [URBANISMO] {resumo}")
        return True

    @staticmethod
    def _escrever_atomico(caminho, dados) -> None:
        caminho_tmp = caminho + ".tmp"
        with open(caminho_tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(caminho_tmp, caminho)

    def _atualizar_indice_da_cidade(self, slug, geojson_atual) -> None:
        """`_indice.json` também precisa ser reescrito (não só o `.geojson` da cidade):
        `web/cache_mapa.py.carregar_indice_cidades` cacheia por mtime do ÍNDICE, e se
        ele não mudar, o bbox antigo corta o arrabalde fora do retorno da API mesmo
        depois do arquivo da cidade já ter o arrabalde dentro."""
        indice_path = os.path.join(CIDADES_GEOJSON_DIR, "_indice.json")
        if not os.path.exists(indice_path):
            return
        with open(indice_path, "r", encoding="utf-8") as f:
            indice = json.load(f)

        xs, ys = [], []
        camadas = {}
        arrabaldes = set()
        for feat in geojson_atual["features"]:
            props = feat["properties"]
            camada = props["camada"]
            info = camadas.setdefault(camada, {"n": 0, "zoom_min": props.get("zoom_min", 0)})
            info["n"] += 1
            for lng, lat in GeradorCidade._achatar_coords(feat["geometry"]["coordinates"]):
                xs.append(lng)
                ys.append(-lat)
            if props.get("arrabalde") is not None:
                arrabaldes.add(props["arrabalde"])
        bbox = {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)} if xs else None

        for entrada in indice.get("cidades", []):
            if entrada["slug"] == slug:
                entrada["bbox"] = bbox
                entrada["camadas"] = camadas
                entrada["arrabaldes"] = len(arrabaldes)
                break
        self._escrever_atomico(indice_path, indice)
