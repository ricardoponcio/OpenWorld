"""
Testes das ações de mundo do Modo Mestre — docs/PLANO_REFATORACAO.md, R-F03.

O que estes testes protegem: o despacho de comandos deixou de ser um if/elif sobre
strings cruas vindas do LLM. Os invariantes são (a) um comando que não existe no enum é
descartado em vez de cair num ramo errado, (b) todo comando registrado responde ao
contrato, e (c) o marcador NOVO_LOCAL continua ligando CRIAR_LOCAL a REATRIBUIR_NPC na
mesma lista de ações — é esse encadeamento que permite "cria um quartel e manda o Brom
trabalhar nele" numa tacada só.

Nenhum banco real: o dublê registra as chamadas, como em tests/test_mecanicas.py.
"""
import pytest

from engine.config_loader import carregar_config_global
from engine.models import ComandoMestre, HumorNPC, MetaChave
from engine.mechanics.mestre import MestreManager, ACOES, POR_COMANDO
from engine.mechanics.mestre.acoes import AcaoDeMundo, AcaoProposta
from engine.mechanics.mestre.acoes.reatribuir_npc import MARCADOR_NOVO_LOCAL


class LocaisFalso:
    def __init__(self, existentes=()):
        self.criados = []
        self.desativados = []
        self._existentes = set(existentes)

    def coordenadas_ocupadas(self):
        return set()

    def criar(self, **campos):
        self.criados.append(campos)
        self._existentes.add(campos["id"])

    def existe(self, local_id):
        return local_id in self._existentes

    def desativar(self, local_id):
        self.desativados.append(local_id)


class _LoteFalso:
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y


class LotesFalso:
    """M02 (docs/PLANO_POPULACAO_E_ESCALA.md): dublê de `RepositorioLote` — só o
    suficiente pra `CriarLocal` reservar um lote real em vez de sortear um ponto em
    terra firme qualquer."""

    def __init__(self, livres=()):
        self._livres = list(livres)  # [(id, x, y), ...]
        self._por_id = {lote_id: (x, y) for lote_id, x, y in livres}
        self.reservados = []
        self.concluidos = []

    def reservar_livre(self, cidade_id, npc_id, perto_de=None, classe_frente=None):
        if not self._livres:
            return None
        lote_id, x, y = self._livres.pop(0)
        self.reservados.append(lote_id)
        return lote_id

    def buscar_por_id(self, lote_id):
        x, y = self._por_id[lote_id]
        return _LoteFalso(lote_id, x, y)

    def concluir(self, lote_id, local_id):
        self.concluidos.append((lote_id, local_id))


class NpcsFalso:
    def __init__(self):
        self.trabalhos = []
        self.casas = []
        self.afetados = []

    def atualizar_local_trabalho(self, npc_id, local_id):
        self.trabalhos.append((npc_id, local_id))

    def atualizar_casa(self, npc_id, local_id):
        self.casas.append((npc_id, local_id))

    def ajustar_saude_e_humor(self, npc_id, delta_saude, humor):
        self.afetados.append((npc_id, delta_saude, humor))


class MetaFalso:
    def __init__(self, cidade_simulada=None):
        self._cidade_simulada = cidade_simulada

    def carregar(self, chave):
        if chave == MetaChave.CIDADE_SIMULADA:
            return self._cidade_simulada
        return None


class MundoFalso:
    def coordenadas(self, cidade_id):
        return (100.0, 100.0)

    def carregar_cidades_por_id(self):
        return {}


class BancoFalso:
    def __init__(self, locais_existentes=(), lotes_livres=(), cidade_simulada=None):
        self.locais = LocaisFalso(locais_existentes)
        self.lotes = LotesFalso(lotes_livres)
        self.npcs = NpcsFalso()
        self.meta = MetaFalso(cidade_simulada)
        self.mundo = MundoFalso()


@pytest.fixture(scope="module")
def config():
    return carregar_config_global()


# ----------------------------------------------------------------------
# Contrato do registro
# ----------------------------------------------------------------------

def test_todo_comando_do_enum_tem_uma_acao_registrada():
    assert set(POR_COMANDO) == set(ComandoMestre)


def test_toda_acao_registrada_responde_a_interface():
    for acao in ACOES:
        assert isinstance(acao, AcaoDeMundo)
        assert isinstance(acao.comando, ComandoMestre)
        assert callable(acao.aplicar)


# ----------------------------------------------------------------------
# Validação do payload da IA
# ----------------------------------------------------------------------

def test_comando_inventado_pela_ia_e_descartado():
    assert AcaoProposta.de_payload({"comando": "INVOCAR_DRAGAO"}) is None
    assert AcaoProposta.de_payload({"comando": None}) is None


def test_payload_sem_bloco_dados_usa_a_propria_acao():
    proposta = AcaoProposta.de_payload({"comando": "DESTRUIR_LOCAL", "id": "loc_7"})
    assert proposta.comando == ComandoMestre.DESTRUIR_LOCAL
    assert proposta.alvo_id == "loc_7"


def test_acoes_desconhecidas_nao_impedem_as_validas(config):
    db = BancoFalso(locais_existentes=["loc_1"])
    resultados = MestreManager(db, config).aplicar_acoes([
        {"comando": "FAZER_CHOVER_SAPOS"},
        {"comando": "DESTRUIR_LOCAL", "id": "loc_1"},
    ])
    assert db.locais.desativados == ["loc_1"]
    assert len(resultados) == 1


# ----------------------------------------------------------------------
# Encadeamento CRIAR_LOCAL -> REATRIBUIR_NPC
# ----------------------------------------------------------------------

def test_novo_local_liga_a_criacao_a_reatribuicao(config):
    db = BancoFalso(cidade_simulada="1", lotes_livres=[("lote_1", 10.0, 20.0)])
    resultados = MestreManager(db, config).aplicar_acoes([
        {"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel do Norte", "tipo": "Trabalho",
                                             "categoria": "quartel", "descricao": "..."}},
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": MARCADOR_NOVO_LOCAL}},
    ])

    assert len(db.locais.criados) == 1
    id_criado = db.locais.criados[0]["id"]
    assert id_criado == "lote_1"  # M02: o id do Local É o id do lote (armadilha 3)
    assert db.lotes.concluidos == [("lote_1", "lote_1")]
    assert db.npcs.trabalhos == [("npc_1", id_criado)]
    assert len(resultados) == 2


def test_criar_local_sem_cidade_simulada_nao_cria_nada(config):
    """M02: sem cidade não há em que lote reservar — nada nasce fora de um lote."""
    db = BancoFalso(lotes_livres=[("lote_1", 10.0, 20.0)])
    resultados = MestreManager(db, config).aplicar_acoes([
        {"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel do Norte"}},
    ])

    assert db.locais.criados == []
    assert resultados == []


def test_criar_local_sem_lote_livre_dispara_avaliar_expansao(config, monkeypatch):
    """M02/X01: cidade saturada — a mesma avaliação de auto-expansão da simulação é
    chamada daqui de fora; sem lote nem depois disso, nada é criado."""
    from engine.mechanics.mestre.acoes import criar_local as modulo

    chamadas = []
    monkeypatch.setattr(modulo, "_avaliar_expansao_fora_do_processo",
                         lambda db, cidade_id: chamadas.append(cidade_id))

    db = BancoFalso(cidade_simulada="1", lotes_livres=())
    resultados = MestreManager(db, config).aplicar_acoes([
        {"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel do Norte"}},
    ])

    assert chamadas == [1]
    assert db.locais.criados == []
    assert len(resultados) == 1  # aviso de "sem lote mesmo após avaliar expansão"


def test_marcador_sem_criacao_antes_nao_reatribui_nada(config):
    db = BancoFalso()
    resultados = MestreManager(db, config).aplicar_acoes([
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": MARCADOR_NOVO_LOCAL}},
    ])

    assert db.npcs.trabalhos == []
    assert resultados == []


def test_reatribuicao_para_local_inexistente_e_ignorada(config):
    db = BancoFalso(locais_existentes=["loc_real"])
    MestreManager(db, config).aplicar_acoes([
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": "loc_fantasma", "casa_id": "loc_real"}},
    ])

    assert db.npcs.trabalhos == []
    assert db.npcs.casas == [("npc_1", "loc_real")]


# ----------------------------------------------------------------------
# AFETAR_NPC e a validação do humor vindo do LLM
# ----------------------------------------------------------------------

def test_humor_invalido_da_ia_vira_neutro(config):
    db = BancoFalso()
    MestreManager(db, config).aplicar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_1", "dados": {"saude": -10, "humor": "Eufórico"}},
    ])

    assert db.npcs.afetados == [("npc_1", -10, HumorNPC.NEUTRO.value)]


def test_humor_valido_da_ia_e_preservado(config):
    db = BancoFalso()
    MestreManager(db, config).aplicar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_1",
         "dados": {"saude": 5, "humor": HumorNPC.PANICO.value}},
    ])

    assert db.npcs.afetados == [("npc_1", 5, HumorNPC.PANICO.value)]
