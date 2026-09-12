"""
MODULE: mundo.py
FUNÇÃO: Estado do mundo simulado (R-F01).

DESCRIÇÃO:
    Antes, cada gerenciador de mecânica (`engine/mechanics/*`) recebia a
    `SimulationEngine` inteira só para ler `npcs`/`locais`/`cidades`/`data_simulada` —
    isso amarrava todo gerenciador a um banco real e impedia testar qualquer um deles
    isoladamente (um gerenciador "dependia de tudo" mesmo quando só usava uma fração).
    `EstadoDoMundo` agrupa só os dados que mudam durante a simulação; `SimulationEngine`
    passa a CONTER um `EstadoDoMundo` em vez de ser ele, e cada gerenciador recebe só
    isso (mais a `config`, que é estática e não faz parte do estado do mundo).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from .indice_locais import IndiceDeLocais


@dataclass
class EstadoDoMundo:
    npcs: List
    locais: Dict
    cidades: Dict
    data_simulada: datetime
    db: object
    tick_count: int = 0
    # P01 (docs/PLANO_CIDADE_VIVA.md): índices de leitura por cidade e por papel sobre
    # o MESMO dicionário `locais` — construído uma vez, aqui, a partir do estado inicial
    # (repr=False/compare=False: não é dado de identidade do mundo, é derivado dele).
    # `locais` continua sendo o acesso por id; o índice é a fonte pra consulta por
    # conjunto (mover_para_social, obter_obra_do_npc). ⚠️ P02: quem cria/desativa um
    # local por fora de `registrar_local`/`desativar_local` deixa isto desatualizado.
    indice: IndiceDeLocais = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.indice is None:
            self.indice = IndiceDeLocais(self.locais)

    # ------------------------------------------------------------------
    # P02 (docs/PLANO_CIDADE_VIVA.md): único caminho de escrita de Local — um índice
    # que alguém esquece de atualizar é pior que nenhum índice (o bug é intermitente e
    # invisível). Todo lugar que cria ou desativa um Local (housing, urbanismo, decay,
    # ações do Modo Mestre) passa por aqui, nunca por `db.locais.salvar` direto.
    # ------------------------------------------------------------------
    def registrar_local(self, local) -> None:
        """Cria um Local novo, ou reindexa um já existente cujo estado mudou (ex.:
        obra concluída, status 0->1) — idempotente: reindexar do zero em vez de tentar
        atualizar incrementalmente evita duplicata ou entrada órfã em `obra_por_dono`."""
        if local.id in self.locais:
            self.indice.remover(local.id)
        self.locais[local.id] = local
        self.indice.registrar(local.id, local)
        self.db.locais.salvar(local)

    def desativar_local(self, local_id: str) -> None:
        """Persiste e reindexa um Local cujos campos (status, e o que mais for o caso —
        nome, tipo, integridade) o CHAMADOR já ajustou. Sai de todo índice de
        "disponível agora"; `locais`/`indice.por_id` continuam com ele (narrativa,
        auditoria)."""
        local = self.locais.get(local_id)
        if local is None:
            return
        self.indice.remover(local_id)
        self.db.locais.salvar(local)

    # ------------------------------------------------------------------
    # A03 (docs/PLANO_POPULACAO_E_ESCALA.md): única porta pra "algo de fora da
    # decisão do próprio NPC mudou o que ele quer, reavalie agora" — a agenda de
    # decisões (A02) só é segura porque todo evento que precisa de reação imediata
    # passa por aqui, e o teto de segurança (`simulacao_intervalo_maximo_decisao_min`)
    # cobre o que alguém esquecer de chamar.
    # ------------------------------------------------------------------
    def acordar(self, npc) -> None:
        """Põe `proximo_instante_decisao` em agora — fura qualquer salto grande que
        `agenda.calcular_proximo_instante` (A02) tivesse computado. Chame sempre que
        algo muda o que o NPC quer por um motivo que NÃO é o próprio metabolismo dele:
        contratação/demissão, fechamento/colapso do local de trabalho, nascimento na
        casa, casamento, mudança de casa, evento global, ação do Modo Mestre."""
        npc.proximo_instante_decisao = self.data_simulada

    def acordar_cidade(self, cidade_id) -> None:
        """`acordar` pra todo NPC vivo de uma cidade — evento global (clima,
        economia). Ainda é O(NPCs): sem um índice por cidade mantido (A04, que este
        plano ainda não implementou nesta sessão) não tem como evitar a varredura.
        Trocar por uma consulta ao índice é um one-liner quando A04 existir."""
        for npc in self.npcs:
            if npc.cidade_id == cidade_id and npc.esta_vivo():
                self.acordar(npc)
