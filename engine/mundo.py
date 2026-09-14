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
import collections
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from .indice_locais import IndiceDeLocais
from .models import ContadorMundo


@dataclass
class EstadoDoMundo:
    npcs: List
    locais: Dict
    cidades: Dict
    data_simulada: datetime
    db: object
    tick_count: int = 0
    # P01 (docs/12_PLANO_CIDADE_VIVA.md): índices de leitura por cidade e por papel sobre
    # o MESMO dicionário `locais` — construído uma vez, aqui, a partir do estado inicial
    # (repr=False/compare=False: não é dado de identidade do mundo, é derivado dele).
    # `locais` continua sendo o acesso por id; o índice é a fonte pra consulta por
    # conjunto (mover_para_social, obter_obra_do_npc). ⚠️ P02: quem cria/desativa um
    # local por fora de `registrar_local`/`desativar_local` deixa isto desatualizado.
    indice: IndiceDeLocais = field(default=None, repr=False, compare=False)

    # A04 (docs/13_PLANO_POPULACAO_E_ESCALA.md): agrupamentos de NPC mantidos, no mesmo
    # espírito do índice de locais acima — construídos uma vez aqui a partir do estado
    # inicial, e daí em diante atualizados incrementalmente pelos métodos abaixo, nunca
    # recomputados do zero no laço do tick (era 17,3 ms/tick com 25.000 NPCs).
    # `NPCUtils.agrupar_por_casa`/`agrupar_npcs_por_localizacao` continuam existindo
    # pra uso pontual/teste — só o laço do tick para de chamá-las.
    npcs_por_casa: Dict = field(default=None, repr=False, compare=False)
    npcs_por_localizacao: Dict = field(default=None, repr=False, compare=False)
    npcs_por_cidade: Dict = field(default=None, repr=False, compare=False)
    # D02 (docs/16_PLANO_PAINEL_E_IA.md): filhos por genitor (mãe OU pai — um NPC com
    # os dois entra nas duas listas). `NPCLegacyManager.processar_heranca` varria
    # `mundo.npcs` inteiro pra achar herdeiros: 12,6 ms por morte medidos. NÃO some
    # do índice na morte (o filho morto continua sendo filho pra quem consultar; o
    # consumidor filtra por `esta_vivo()`) — a lista é pequena, não vale a pena podar.
    filhos_por_genitor: Dict = field(default=None, repr=False, compare=False)

    # H02 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 15): casas cuja composição
    # (quem mora lá, quem é dependente de quem) mudou desde a última vez que
    # `GameLoop._atualizar_dependentes` rodou — substitui a assinatura calculada
    # sobre TODAS as casas todo tick (N04), que custava ~16% do piso medido com
    # 25.000 NPCs pra um número que quase nunca muda. `marcar_casa_suja` é a única
    # porta que escreve aqui; os métodos abaixo (mudar_casa/registrar_npc/
    # remover_npc/reindexar_casa_do_npc) já chamam sozinhos — quem mais mudar algo
    # que afete `NPC.eh_dependente()` fora daqui (ex.: crescimento em
    # `lifecycle.py`) precisa chamar `marcar_casa_suja` também.
    casas_sujas: set = field(default_factory=set, repr=False, compare=False)

    # Achado de A04: sinaliza pra `GameLoop._remover_falecidos` que existe falecido
    # pendente — sem isto, `_remover_falecidos` reconstruiria `self.npcs` (uma lista
    # NOVA) todo tick, mesmo sem morte nenhuma, e a troca de identidade faria
    # `_atualizar_dependentes` recalcular o mundo inteiro por engano.
    ha_falecidos_pendentes: bool = field(default=False, repr=False, compare=False)

    # H01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 13): a agenda de decisões
    # (A02) virou ESTRUTURA DE DADOS, não predicado — `GameLoop` não pergunta mais
    # "você está em dia?" a cada um dos NPCs vivos, todo tick (isso continuava sendo
    # O(NPCs), que é exatamente o que a agenda existia pra eliminar). Todo NPC vivo
    # está em EXATAMENTE um destes três lugares:
    #   - `baldes_decisao[instante]`: aguardando `instante` chegar;
    #   - `npcs_em_consequencia[npc.id]`: fome acima do limiar de inanição, reavaliado
    #     todo tick até sair de lá (armadilha 11, classe 2) — nunca num balde;
    #   - `npcs_sem_agenda[npc.id]`: `proximo_instante_decisao` ainda é `None` (recém
    #     carregado do banco, ou recém-nascido) — mesma semântica de antes de H01
    #     ("nunca avaliado" é sempre em dia), reavaliado todo tick até a primeira vez
    #     que sair daqui pra um dos dois de cima.
    # Nunca em dois ao mesmo tempo, nunca em nenhum. `agendar_decisao`/
    # `marcar_consequencia` (mais abaixo) são as únicas portas que movem um NPC entre
    # eles; `acordar` também usa `agendar_decisao`, por baixo.
    baldes_decisao: Dict = field(default=None, repr=False, compare=False)
    npcs_em_consequencia: Dict = field(default=None, repr=False, compare=False)
    npcs_sem_agenda: Dict = field(default=None, repr=False, compare=False)

    # O02 (docs/16_PLANO_PAINEL_E_IA.md): ocorrências do dia simulado corrente, por
    # ContadorMundo — substitui os warnings por NPC/por tick que inundavam o log
    # (42.476 linhas de inanição numa amostra). O coletor de estatísticas (O03) lê e
    # zera isto quando o dia simulado vira.
    contadores: collections.Counter = field(default_factory=collections.Counter, repr=False, compare=False)

    def __post_init__(self):
        if self.indice is None:
            self.indice = IndiceDeLocais(self.locais)
        if self.npcs_por_casa is None:
            self._reconstruir_indices_de_npc()

    # ------------------------------------------------------------------
    # P02 (docs/12_PLANO_CIDADE_VIVA.md): único caminho de escrita de Local — um índice
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
    # A03 (docs/13_PLANO_POPULACAO_E_ESCALA.md): única porta pra "algo de fora da
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
        casa, casamento, mudança de casa, evento global, ação do Modo Mestre.

        H01: quem já está em `npcs_em_consequencia` já é reavaliado todo tick — mover
        pra um balde em "agora" seria um efeito colateral (sairia do conjunto que
        NUNCA pula) sem ganhar nada, então isto vira um no-op nesse caso."""
        if npc.id in self.npcs_em_consequencia:
            return
        self.agendar_decisao(npc, self.data_simulada)

    def acordar_cidade(self, cidade_id) -> None:
        """`acordar` pra todo NPC vivo de uma cidade — evento global (clima,
        economia). Usa o índice mantido (A04): O(NPCs da cidade), não O(NPCs do
        mundo)."""
        for npc in self.npcs_por_cidade.get(cidade_id, ()):
            if npc.esta_vivo():
                self.acordar(npc)

    def contar(self, contador: ContadorMundo, quantidade: int = 1) -> None:
        """O02: única porta de incremento — nunca `mundo.contadores[...] += 1`
        direto (a mesma regra dos índices de NPC: uma porta só, pra não ter dois
        lugares divergindo de como contar a mesma coisa)."""
        self.contadores[contador] += quantidade

    # ------------------------------------------------------------------
    # A04 (docs/13_PLANO_POPULACAO_E_ESCALA.md): único caminho pra mudar
    # `casa_id`/`localizacao_atual_id` de um NPC vivo, e pra registrar/remover um NPC
    # do mundo — mesmo padrão de `registrar_local`/`desativar_local` (P02). Um índice
    # que alguém esquece de atualizar é pior que nenhum índice: o NPC some do lugar
    # onde deveria estar, ou aparece em dois, sem erro nenhum (armadilha 12).
    # ------------------------------------------------------------------
    def mover_npc(self, npc, local_id: str) -> None:
        """Único caminho pra mudar `localizacao_atual_id`. NÃO mexe em `casa_id` —
        chame `mudar_casa` também quando as duas mudarem juntas (ex.: mudança de
        casa)."""
        antiga = npc.localizacao_atual_id
        if antiga == local_id:
            return
        self._remover_de_bucket(self.npcs_por_localizacao, antiga, npc)
        npc.localizacao_atual_id = local_id
        if local_id:
            self.npcs_por_localizacao.setdefault(local_id, []).append(npc)

    def mudar_casa(self, npc, casa_id: str) -> None:
        """Único caminho pra mudar `casa_id`. NÃO mexe em `localizacao_atual_id` —
        chame `mover_npc` também quando as duas mudarem juntas."""
        antiga = npc.casa_id
        if antiga == casa_id:
            return
        self._remover_de_bucket(self.npcs_por_casa, antiga, npc)
        npc.casa_id = casa_id
        if casa_id:
            self.npcs_por_casa.setdefault(casa_id, []).append(npc)
        self.marcar_casa_suja(antiga)
        self.marcar_casa_suja(casa_id)

    def reindexar_casa_do_npc(self, npc, casa_id_antiga: str) -> None:
        """`NPCBrain.decidir_acao` tem uma rede de segurança que reatribui `casa_id`
        direto no NPC quando a casa dele não existe mais — não tem como passar por
        `mudar_casa` porque `NPCBrain` é estático e não conhece `EstadoDoMundo`. Chame
        isto logo depois, com o `casa_id` de ANTES da chamada, pra só reindexar (o
        campo já mudou; não mude de novo)."""
        self._remover_de_bucket(self.npcs_por_casa, casa_id_antiga, npc)
        if npc.casa_id:
            self.npcs_por_casa.setdefault(npc.casa_id, []).append(npc)
        self.marcar_casa_suja(casa_id_antiga)
        self.marcar_casa_suja(npc.casa_id)

    def marcar_casa_suja(self, casa_id: str) -> None:
        """H02: única porta que marca uma casa pra `GameLoop._atualizar_dependentes`
        recalcular `num_dependentes` dela no fim do tick. No-op pra `casa_id` vazio
        (NPC sem casa não tem composição pra recalcular)."""
        if casa_id:
            self.casas_sujas.add(casa_id)

    def registrar_npc(self, npc) -> None:
        """Um NPC novo (nascimento) entra nos três índices e na agenda de decisões
        (H01) — sem isto ficaria em nenhum balde e nenhum conjunto, e nunca mais
        seria reavaliado. `proximo_instante_decisao` nasce `None` (default do
        dataclass) — mesma semântica de "nunca avaliado ainda" que um NPC recém
        carregado do banco: entra em `npcs_sem_agenda`, reavaliado já no próximo
        tick."""
        self.npcs.append(npc)
        if npc.casa_id:
            self.npcs_por_casa.setdefault(npc.casa_id, []).append(npc)
        if npc.localizacao_atual_id:
            self.npcs_por_localizacao.setdefault(npc.localizacao_atual_id, []).append(npc)
        self.npcs_por_cidade.setdefault(npc.cidade_id, []).append(npc)
        # D02: entra na lista de filhos de cada genitor que tiver.
        for genitor_id in (npc.mae_id, npc.pai_id):
            if genitor_id:
                self.filhos_por_genitor.setdefault(genitor_id, []).append(npc)
        self.marcar_casa_suja(npc.casa_id)
        self.npcs_sem_agenda[npc.id] = npc

    def remover_npc(self, npc) -> None:
        """Um NPC que morreu sai dos três índices (mas continua em `self.npcs` até
        `GameLoop._remover_falecidos` filtrar a lista no fim do tick — narrativa e
        auditoria ainda podem precisar dele até lá). Marca `self.ha_falecidos_pendentes`
        pra `GameLoop` saber que precisa filtrar — sem isto ele filtraria (e
        recriaria a lista) todo tick, mesmo nos ~99% em que ninguém morreu (achado de
        A04: recriar `self.npcs` sem necessidade troca a IDENTIDADE do objeto e faz
        `_atualizar_dependentes` achar que TUDO mudou, e recalcular o mundo inteiro).

        H01: sai também da agenda de decisões — um morto esquecido num balde ou no
        conjunto de consequência violaria o invariante "soma dos baldes + consequência
        == população viva" pra sempre (ninguém nunca o remove de lá de novo)."""
        self._remover_de_bucket(self.npcs_por_casa, npc.casa_id, npc)
        self._remover_de_bucket(self.npcs_por_localizacao, npc.localizacao_atual_id, npc)
        self._remover_de_bucket(self.npcs_por_cidade, npc.cidade_id, npc)
        self._remover_da_agenda(npc)
        self.marcar_casa_suja(npc.casa_id)
        self.ha_falecidos_pendentes = True

    # ------------------------------------------------------------------
    # H01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): a agenda de decisões (A02) vira
    # estrutura de dados. `agendar_decisao`/`marcar_consequencia` são as únicas portas
    # que colocam um NPC num balde ou no conjunto de consequência; `_remover_da_agenda`
    # é o passo comum de "tire-o de onde estiver primeiro" que as duas usam por baixo
    # — o mesmo padrão de `mover_npc`/`mudar_casa` (armadilha 12: um índice que alguém
    # esquece de atualizar é pior que nenhum índice).
    # ------------------------------------------------------------------
    def agendar_decisao(self, npc, instante) -> None:
        """Único caminho pra colocar um NPC num balde de minuto. Remove de onde
        estiver antes (balde antigo ou conjunto de consequência) — nunca deixa um NPC
        em dois lugares ao mesmo tempo."""
        self._remover_da_agenda(npc)
        npc.proximo_instante_decisao = instante
        self.baldes_decisao.setdefault(instante, []).append(npc)

    def marcar_consequencia(self, npc) -> None:
        """Estado de CONSEQUÊNCIA (fome acima do limiar de inanição, armadilha 11
        classe 2): tira o NPC de qualquer balde e põe no conjunto reavaliado todo
        tick, até a fome cair — é aqui, e não mais numa varredura de `npc_esta_em_dia`
        sobre todo `mundo.npcs`, que a garantia de nunca pular passa a viver."""
        self._remover_da_agenda(npc)
        self.npcs_em_consequencia[npc.id] = npc

    def _remover_da_agenda(self, npc) -> None:
        if self.npcs_em_consequencia.pop(npc.id, None) is not None:
            return
        if self.npcs_sem_agenda.pop(npc.id, None) is not None:
            return
        instante = npc.proximo_instante_decisao
        if instante is None:
            return
        bucket = self.baldes_decisao.get(instante)
        if not bucket:
            return
        for i, n in enumerate(bucket):
            if n.id == npc.id:
                del bucket[i]
                break
        if not bucket:
            del self.baldes_decisao[instante]

    @staticmethod
    def _remover_de_bucket(indice: dict, chave, npc) -> None:
        """Remove por `npc.id` (chave de negócio), nunca por `==` de dataclass — dois
        NPCs com os mesmos valores em todo campo comparariam iguais e o `.remove()`
        certo apagaria o errado."""
        bucket = indice.get(chave)
        if not bucket:
            return
        for i, n in enumerate(bucket):
            if n.id == npc.id:
                del bucket[i]
                return

    def mudar_cidade(self, npc, cidade_id) -> None:
        """A05 (docs/13_PLANO_POPULACAO_E_ESCALA.md): SÓ A PORTA — nada na simulação
        chama isto ainda. P04 (docs/12_PLANO_CIDADE_VIVA.md) fixou que um NPC não
        atravessa cidade, e boa parte do ganho de performance do projeto depende
        disso continuar valendo dentro de um tick; esta porta existe pra quando uma
        mecânica de migração precisar existir (cidade que decai perde gente, cidade
        que prospera atrai), sem cada uma reinventar a atualização dos três índices.

        Casa, localização e trabalho pertencem à cidade de ORIGEM — não fazem sentido
        na cidade de destino, então saem junto. Uma mecânica de migração futura tem
        que resolver casa/trabalho no destino ANTES de chamar isto (ou logo depois,
        antes do NPC ser processado de novo); esta porta não tenta adivinhar.

        Quem escrever essa mecânica no futuro tem que respeitar, sem exceção: casal
        não se separa (os dois se mudam juntos, ou nenhum), dependente acompanha o
        responsável (nunca uma criança sozinha numa cidade nova), e o NPC precisa de
        lote ou vaga já reservados no destino ANTES de sair da origem — nunca um NPC
        "no limbo" entre cidades por um tick que seja.

        [Seção 5.2 do plano]: se um dia existir um processo por cidade, migração
        deixa de ser uma chamada de método e passa a ser uma mensagem entre
        processos — ter a operação isolada aqui, e não espalhada, é o que torna essa
        transição possível depois."""
        self._remover_de_bucket(self.npcs_por_cidade, npc.cidade_id, npc)
        self._remover_de_bucket(self.npcs_por_casa, npc.casa_id, npc)
        self._remover_de_bucket(self.npcs_por_localizacao, npc.localizacao_atual_id, npc)
        self.marcar_casa_suja(npc.casa_id)

        npc.cidade_id = cidade_id
        npc.casa_id = ""
        npc.localizacao_atual_id = ""
        npc.local_trabalho_id = None

        self.npcs_por_cidade.setdefault(cidade_id, []).append(npc)

    def _reconstruir_indices_de_npc(self) -> None:
        """(Re)constrói os três índices e a agenda de decisões (H01) do zero a partir
        de `self.npcs` — usado no carregamento inicial, e sempre que alguém substituir
        `self.npcs` por uma lista inteira nova (`recarregar_habitantes()`) sem passar
        pelos métodos acima. Só NPCs vivos entram, mesma semântica de
        `NPCUtils.agrupar_por_casa`.

        H01: `proximo_instante_decisao` não é persistido (fica `None` em todo NPC
        recém-carregado do banco) — nesse caso o NPC entra em `npcs_sem_agenda`, que é
        exatamente a semântica antiga de `npc_esta_em_dia` (`proximo_instante_decisao
        is None` => sempre em dia), reavaliado no próximo tick. Um teste pode
        pré-atribuir o campo antes de montar o mundo (simulando "já estava agendado
        pra X") — respeita esse valor, colocando o NPC direto no balde certo, em vez
        de sobrescrevê-lo (isso também evita depender de QUANDO, em relação a
        `self.data_simulada`, a construção aconteceu — um teste pode mudar o relógio
        do mundo logo depois de montá-lo)."""
        self.npcs_por_casa = {}
        self.npcs_por_localizacao = {}
        self.npcs_por_cidade = {}
        self.baldes_decisao = {}
        self.npcs_em_consequencia = {}
        self.npcs_sem_agenda = {}
        self.filhos_por_genitor = {}
        for npc in self.npcs:
            # D02 (docs/16_PLANO_PAINEL_E_IA.md): ANTES do `continue` de baixo —
            # um filho já falecido continua sendo filho do genitor pra quem
            # consultar (o consumidor filtra por `esta_vivo()`); só os índices de
            # localização/agenda são exclusivos de quem está vivo.
            for genitor_id in (npc.mae_id, npc.pai_id):
                if genitor_id:
                    self.filhos_por_genitor.setdefault(genitor_id, []).append(npc)
            if not npc.esta_vivo():
                continue
            if npc.casa_id:
                self.npcs_por_casa.setdefault(npc.casa_id, []).append(npc)
            if npc.localizacao_atual_id:
                self.npcs_por_localizacao.setdefault(npc.localizacao_atual_id, []).append(npc)
            self.npcs_por_cidade.setdefault(npc.cidade_id, []).append(npc)
            if npc.proximo_instante_decisao is None:
                self.npcs_sem_agenda[npc.id] = npc
            else:
                self.baldes_decisao.setdefault(npc.proximo_instante_decisao, []).append(npc)
