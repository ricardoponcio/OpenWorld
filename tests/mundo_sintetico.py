"""
MODULE: mundo_sintetico.py
FUNÇÃO: Mundo de teste em memória para os gerenciadores de mecânica.

DESCRIÇÃO:
    Os dublês e as fábricas que tests/test_mecanicas.py usa para montar um
    `EstadoDoMundo` sem banco, sem schema e sem pool de conexões. Vive fora do arquivo
    de teste porque ele passou do limite de 400 linhas do projeto (11_ARQUITETURA.md
    Seção 4) — e porque "o mundo de teste" é um assunto só, com uma razão para mudar.

    Não é um arquivo de teste: o nome não começa com `test_`, então o pytest não o
    coleta.
"""
from datetime import datetime

from engine.models import (
    NPC, Local, Lote, EstagioVida, TipoLocal, CategoriaLocal, LoteEstado,
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
        docs/12_PLANO_CIDADE_VIVA.md). Com 1 argumento guarda o valor cru, pra
        `entidade in db.X.salvos` continuar funcionando sem mudança nos testes."""
        self.salvos.append(args[0] if len(args) == 1 else args)

    def salvar_muitos(self, entidades):
        """P05: `GameLoop.executar_tick` salva os NPCs do tick numa única chamada em
        lote — o dublê só estende `salvos`, pra `entidade in db.npcs.salvos` continuar
        funcionando sem mudança nos testes que já usam esse padrão."""
        self.salvos.extend(entidades)

    def salvar_completo(self, entidades):
        """N02/H05: escrita de linha inteira em lote (ex.: `processar_poda_de_
        relacionamentos`) — mesmo dublê de `salvar_muitos`, nome espelhando o
        repositório real."""
        self.salvos.extend(entidades)

    def salvar_relacionamento(self, a_id, b_id, afinidade, vinculo):
        self.relacionamentos.append((a_id, b_id, afinidade, vinculo))

    def salvar_relacionamentos_muitos(self, pares):
        """E01: dublê do batch de `RepositorioNPC.salvar_relacionamentos_muitos` —
        só estende `relacionamentos`, um item por par (não duplica pelas duas
        direções como o repositório real; nenhum teste daqui depende de contagem de
        linha, só do conteúdo)."""
        self.relacionamentos.extend(pares)

    def renomear(self, npc_id, nome):
        self.renomeados.append((npc_id, nome))

    def carregar_todos(self):
        return []

    def carregar_globais_ativos(self):
        return []

    def carregar(self, chave):
        """Meta: devolve o valor da última `salvar(chave, valor)` — procura de trás
        pra frente em `self.salvos` (tuplas `(chave, valor)`). `None` se nunca foi
        salva, mesma semântica do repositório real (F01, docs/
        14_PLANO_AVANCO_E_CALIBRAGEM.md: `MestreManager._montar_contexto_de_mundo` lê
        `MetaChave.CIDADE_SIMULADA` assim)."""
        for item in reversed(self.salvos):
            if isinstance(item, tuple) and len(item) == 2 and item[0] == chave:
                return item[1]
        return None

    def atualizar_ticks_restantes(self, eventos):
        pass

    def atualizar_resumo(self, evento_id, resumo):
        pass

    def podar_por_idade(self, dia_de_corte):
        """E02: dublê de `RepositorioEvento.podar_por_idade` — este dublê não guarda
        timestamp nenhum de verdade, então não há o que podar."""
        return 0


class RepositorioLoteFalso:
    """T04/O01 (docs/12_PLANO_CIDADE_VIVA.md): dublê em memória de RepositorioLote — um
    dict de `Lote` por id, o bastante pra `InfrastructureManager` (decay.py) liberar
    terreno e `NPCHousingManager` (housing.py) reservar lote real, sem banco."""

    def __init__(self):
        self.lotes = {}
        # Compat: `estados` era o dublê original (só T04) — mantido como VIEW sobre
        # `self.lotes`, pra `db.lotes.estados["x"]` continuar funcionando nos testes
        # que só se importam com o estado, não com o Lote inteiro.
        self.estados = _EstadosView(self.lotes)

    def adicionar(self, lote_id, cidade_id=1, x=0.0, y=0.0, bairro="", banda=1,
                  estado=LoteEstado.LIVRE.value):
        """Helper só de teste — semeia um lote no dublê (RepositorioLote de verdade
        recebe isso via `salvar_em_lote` na importação, T02)."""
        self.lotes[lote_id] = Lote(id=lote_id, cidade_id=cidade_id, quarteirao_id="",
                                    bairro=bairro, banda=banda, classe_frente="",
                                    area_m2=0.0, x=x, y=y, estado=estado)

    def definir_estado(self, lote_id, estado):
        if lote_id not in self.lotes:
            self.adicionar(lote_id, estado=estado)
        else:
            self.lotes[lote_id].estado = estado

    def reservar_livre(self, cidade_id, npc_id, perto_de=None, classe_frente=None):
        candidatos = [l for l in self.lotes.values()
                     if l.cidade_id == cidade_id and l.estado == LoteEstado.LIVRE.value
                     and (classe_frente is None or l.classe_frente == classe_frente)]
        if not candidatos:
            return None
        if perto_de is not None:
            px, py = perto_de
            candidatos.sort(key=lambda l: (l.x - px) ** 2 + (l.y - py) ** 2)
        else:
            candidatos.sort(key=lambda l: l.id)
        escolhido = candidatos[0]
        escolhido.estado = LoteEstado.OBRA.value
        escolhido.dono_npc_id = npc_id
        return escolhido.id

    def buscar_por_id(self, lote_id):
        return self.lotes.get(lote_id)

    def concluir(self, lote_id, local_id):
        if lote_id in self.lotes:
            self.lotes[lote_id].estado = LoteEstado.OCUPADO.value
            self.lotes[lote_id].local_id = local_id

    def liberar(self, lote_id):
        lote = self.lotes.get(lote_id)
        if lote and lote.estado == LoteEstado.OCUPADO.value:
            lote.estado = LoteEstado.LIVRE.value
            lote.local_id = ""
            lote.dono_npc_id = ""

    def contar_por_estado(self, cidade_id):
        """X01: gatilho de auto-expansão — `{estado: contagem}` só dos lotes da cidade."""
        contagem = {}
        for lote in self.lotes.values():
            if lote.cidade_id == cidade_id:
                contagem[lote.estado] = contagem.get(lote.estado, 0) + 1
        return contagem

    def salvar_em_lote(self, lotes):
        """X03: importação inicial (T02) e arrabalde novo (X03) inserem em lote."""
        for lote in lotes:
            self.lotes[lote.id] = lote


class _EstadosView:
    """Só pra compatibilidade com testes antigos que faziam
    `db.lotes.estados[lote_id]` diretamente (T04) — lê/escreve o `.estado` do Lote
    guardado em `self.lotes`, criando um lote mínimo se o id ainda não existir."""

    def __init__(self, lotes: dict):
        self._lotes = lotes

    def __setitem__(self, lote_id, estado):
        if lote_id not in self._lotes:
            self._lotes[lote_id] = Lote(id=lote_id, cidade_id=1, quarteirao_id="",
                                        bairro="", banda=1, classe_frente="",
                                        area_m2=0.0, estado=estado)
        else:
            self._lotes[lote_id].estado = estado

    def __getitem__(self, lote_id):
        return self._lotes[lote_id].estado

    def get(self, lote_id, default=None):
        lote = self._lotes.get(lote_id)
        return lote.estado if lote else default


class RepositorioMundoFalso:
    """Dublê de `RepositorioMundo` — só o que `MestreManager._montar_contexto_de_
    mundo` lê (F01, docs/14_PLANO_AVANCO_E_CALIBRAGEM.md)."""

    def coordenadas(self, cidade_id):
        return (100.0, 100.0)

    def carregar_cidades_por_id(self):
        return {}


class RepositorioMestreFalso:
    """F01: dublê da fila de ações do Mestre — `enfileirar_acoes` só anota (uso do
    lado do Flask); `drenar_acoes_pendentes` devolve e ESVAZIA (mesma semântica do
    repositório real: uma ação só é devolvida uma vez)."""

    def __init__(self):
        self.enfileiradas = []
        self._pendentes = []

    def enfileirar_acoes(self, payloads):
        self.enfileiradas.extend(payloads)
        self._pendentes.extend(payloads)

    def drenar_acoes_pendentes(self):
        pendentes, self._pendentes = self._pendentes, []
        return pendentes

    def ha_fila_nao_drenada(self, segundos):
        return False


class BancoFalso:
    def __init__(self):
        self.npcs = RepositorioFalso()
        self.locais = RepositorioFalso()
        self.lotes = RepositorioLoteFalso()
        self.eventos = RepositorioFalso()
        self.meta = RepositorioFalso()
        self.mundo = RepositorioMundoFalso()
        self.mestre = RepositorioMestreFalso()


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
