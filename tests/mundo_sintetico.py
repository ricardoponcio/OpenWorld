"""
MODULE: mundo_sintetico.py
FUNÇÃO: Mundo de teste em memória para os gerenciadores de mecânica.

DESCRIÇÃO:
    Os dublês e as fábricas que tests/test_mecanicas.py usa para montar um
    `EstadoDoMundo` sem banco, sem schema e sem pool de conexões. Vive fora do arquivo
    de teste porque ele passou do limite de 400 linhas do projeto (ARQUITETURA.md
    Seção 4) — e porque "o mundo de teste" é um assunto só, com uma razão para mudar.

    Não é um arquivo de teste: o nome não começa com `test_`, então o pytest não o
    coleta.
"""
from datetime import datetime

from engine.models import (
    NPC, Local, EstagioVida, TipoLocal, CategoriaLocal,
)
from engine.mundo import EstadoDoMundo


# ----------------------------------------------------------------------
# Dublês: um "banco" que só anota
# ----------------------------------------------------------------------

class RepositorioFalso:
    """Anota as escritas em vez de executá-las. Os métodos de leitura devolvem vazio —
    nenhum teste daqui depende de estado vindo do banco."""

    def __init__(self):
        self.salvos = []
        self.relacionamentos = []
        self.renomeados = []

    def salvar(self, *args):
        """Aceita tanto `salvar(entidade)` (npcs/locais/eventos) quanto
        `salvar(chave, valor)` (meta, usado por `GameLoop._avancar_relogio` — V03 do
        docs/PLANO_CIDADE_VIVA.md). Com 1 argumento guarda o valor cru, pra
        `entidade in db.X.salvos` continuar funcionando sem mudança nos testes."""
        self.salvos.append(args[0] if len(args) == 1 else args)

    def salvar_relacionamento(self, a_id, b_id, afinidade, vinculo):
        self.relacionamentos.append((a_id, b_id, afinidade, vinculo))

    def renomear(self, npc_id, nome):
        self.renomeados.append((npc_id, nome))

    def carregar_todos(self):
        return []

    def carregar_globais_ativos(self):
        return []

    def atualizar_ticks_restantes(self, eventos):
        pass

    def atualizar_resumo(self, evento_id, resumo):
        pass


class BancoFalso:
    def __init__(self):
        self.npcs = RepositorioFalso()
        self.locais = RepositorioFalso()
        self.eventos = RepositorioFalso()
        self.meta = RepositorioFalso()


def adulto(npc_id, nome, **campos):
    base = dict(
        id=npc_id, nome=nome, profissao="Ferreiro", local_trabalho_id="",
        localizacao_atual_id="casa_1", casa_id="casa_1", cidade_id=1,
        estagio_vida=EstagioVida.ADULTO.value,
    )
    base.update(campos)
    return NPC(**base)


def casa(local_id="casa_1", **campos):
    base = dict(
        id=local_id, nome="Casa dos Testes", tipo=TipoLocal.CASA.value,
        categoria=CategoriaLocal.RESIDENCIA.value, cidade_id=1, capacidade=2,
    )
    base.update(campos)
    return Local(**base)


def mundo_de(npcs=(), locais=(), cidades=()):
    return EstadoDoMundo(
        npcs=list(npcs),
        locais={l.id: l for l in locais},
        cidades={c.id: c for c in cidades},
        data_simulada=datetime(2026, 9, 12, 10, 0),
        db=BancoFalso(),
        tick_count=1,
    )


class MovimentoDuble:
    """Registra para onde o NPC foi mandado, sem mexer na localização."""

    def __init__(self):
        self.destinos = []

    def mover_para(self, npc, local_id):
        self.destinos.append(local_id)

    def mover_para_casa(self, npc):
        self.destinos.append("casa")

    def mover_para_obra(self, npc, obra_id):
        self.destinos.append(obra_id)

    def mover_para_trabalho(self, npc):
        self.destinos.append("trabalho")

    def mover_para_social(self, npc):
        self.destinos.append("social")

    def mover_para_restaurante(self, npc):
        self.destinos.append("restaurante")

    def mover_aleatoriamente(self, npc):
        self.destinos.append("aleatorio")
