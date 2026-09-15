import json
from dataclasses import dataclass
from typing import Optional

from ..models import NPC, Acao, EstadoCivil, SituacaoHabitante
from ..logger import WorldLogger


def _safe_json_load(data, default):
    try:
        return json.loads(data) if data else default
    except (json.JSONDecodeError, TypeError) as e:
        WorldLogger.warning(f"JSON corrompido em coluna de NPC, usando default {default!r}: {e}")
        return default


@dataclass
class FiltroHabitantes:
    """P02 (docs/16_PLANO_PAINEL_E_IA.md): agrupa os parâmetros de
    `RepositorioNPC.contar_habitantes`/`listar_habitantes` num objeto só — os dois
    métodos continuam com 1 parâmetro (ARQUITETURA §4), não 7."""
    cidade_id: Optional[int] = None
    busca_nome: str = ""
    estagio_vida: Optional[str] = None   # EstagioVida.X.value
    acao: Optional[str] = None           # Acao.X.value
    situacao: str = SituacaoHabitante.VIVOS.value
    pagina: int = 1
    por_pagina: int = 50


# Colunas do cartão da grade de habitantes — o mesmo conjunto que
# `listar_projecao_dashboard` já usava, sem o dataclass NPC completo.
_COLUNAS_CARTAO_HABITANTE = (
    "id, nome, profissao, acao_atual, localizacao_atual_id, energia, fome, social, "
    "dinheiro_total_pc, saude, humor, genero, estagio_vida, data_nascimento, "
    "pai_id, mae_id, estado_civil, conjuge_id, gravidez_ticks"
)


def _montar_where_habitantes(filtro: "FiltroHabitantes"):
    """Monta a cláusula WHERE e os parâmetros na MESMA ordem — nunca f-string com
    valor do usuário (ARQUITETURA §15 item 4), sempre `?`."""
    condicoes = []
    parametros = []

    if filtro.cidade_id is not None:
        condicoes.append("cidade_id = ?")
        parametros.append(filtro.cidade_id)
    if filtro.busca_nome:
        condicoes.append("nome LIKE ?")
        parametros.append(f"%{filtro.busca_nome}%")
    if filtro.estagio_vida is not None:
        condicoes.append("estagio_vida = ?")
        parametros.append(filtro.estagio_vida)
    if filtro.acao is not None:
        condicoes.append("acao_atual = ?")
        parametros.append(filtro.acao)

    if filtro.situacao == SituacaoHabitante.VIVOS.value:
        condicoes.append("saude > 0")
    elif filtro.situacao == SituacaoHabitante.MORTOS.value:
        condicoes.append("saude <= 0")
    # TODOS: sem condição de saúde.

    clausula = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    return clausula, parametros


class RepositorioNPC:
    """SQL de NPCs, vínculos sociais e profissões (R-E01) — antes espalhado entre
    `DatabaseManager`, `engine/mechanics/market.py` e `engine/mechanics/mestre.py`."""

    def __init__(self, db):
        self.db = db

    def _carregar_relacionamentos_por_npc(self, conn) -> dict:
        """P03 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco P): a tabela `relacionamentos` (tem
        `vinculo`, e é o que `listar_relacionamentos_gerais`/o Mestre consultam) é a
        fonte de verdade — não mais a coluna JSON de `npcs`, que `salvar_muitos` (fim
        de tick) nunca escreve. UMA consulta pra todos os NPCs, agrupada em memória —
        nunca uma por NPC."""
        cursor = conn.cursor()
        cursor.execute('SELECT npc_a_id, npc_b_id, afinidade FROM relacionamentos')
        por_npc = {}
        for row in cursor.fetchall():
            por_npc.setdefault(row['npc_a_id'], {})[row['npc_b_id']] = row['afinidade']
        return por_npc

    def carregar_todos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            try:
                relacionamentos_por_npc = self._carregar_relacionamentos_por_npc(conn)
                cursor.execute('SELECT * FROM npcs')
                rows = cursor.fetchall()
                npcs = []
                for r in rows:
                    npc = NPC(
                        id=r['id'], nome=r['nome'], profissao=r['profissao'],
                        profissao_id=r['profissao_id'] or 'ocioso',
                        cidade_id=r['cidade_id'],
                        casa_id=r['casa_id'],
                        local_trabalho_id=r['local_trabalho_id'], localizacao_atual_id=r['localizacao_atual_id'],
                        acao_atual=Acao(r['acao_atual']) if r['acao_atual'] else Acao.OCIOSO,
                        energia=float(r['energia']) if r['energia'] is not None else 100.0,
                        dinheiro_total_pc=float(r['dinheiro_total_pc']) if r['dinheiro_total_pc'] is not None else 500.0,
                        social=float(r['social']) if r['social'] is not None else 100.0,
                        fome=float(r['fome']) if r['fome'] is not None else 0.0,
                        saude=int(r['saude']) if r['saude'] is not None else 100,
                        humor=r['humor'] or 'Neutro',
                        genero=r['genero'] or 'M',
                        estagio_vida=r['estagio_vida'] or 'adulto',
                        raca=r['raca'] or '',
                        personalidade=r['personalidade'] or '',
                        background=r['background'] or '',
                        data_nascimento=r['data_nascimento'] or '',
                        estado_civil=r['estado_civil'] or EstadoCivil.SOLTEIRO.value,
                        conjuge_id=r['conjuge_id'] or '',
                        pai_id=r['pai_id'] or '',
                        mae_id=r['mae_id'] or '',
                        genealogia=_safe_json_load(r['genealogia'], []),
                        relacionamentos=relacionamentos_por_npc.get(r['id'], {}),
                        memoria_eventos=_safe_json_load(r['memoria_eventos'], []),
                        gravidez_ticks=r['gravidez_ticks'] if r['gravidez_ticks'] is not None else 0)

                    npcs.append(npc)
                return npcs
            except Exception as e:
                WorldLogger.error(f"Erro ao carregar NPCs: {e}")
                return []

    def salvar(self, npc: NPC):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO npcs                           (id, nome, profissao, profissao_id, cidade_id, casa_id, local_trabalho_id, localizacao_atual_id,
                               acao_atual, energia, dinheiro_total_pc, social, fome, saude, humor,
                               genero, estagio_vida, raca, personalidade, background, data_nascimento, estado_civil, conjuge_id, pai_id, mae_id, genealogia, relacionamentos, memoria_eventos, gravidez_ticks)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                npc.id, npc.nome, npc.profissao, npc.profissao_id, npc.cidade_id, npc.casa_id, npc.local_trabalho_id,
                npc.localizacao_atual_id, npc.acao_atual.value, npc.energia, npc.dinheiro_total_pc,
                npc.social, npc.fome, npc.saude, npc.humor,
                npc.genero, npc.estagio_vida, npc.raca, npc.personalidade, npc.background,
                npc.data_nascimento, npc.estado_civil, npc.conjuge_id, npc.pai_id, npc.mae_id,
                json.dumps(npc.genealogia), json.dumps(npc.relacionamentos), json.dumps(npc.memoria_eventos),
                npc.gravidez_ticks
            ))

    # Colunas que mudam a cada minuto simulado, para todo NPC vivo — o que
    # `salvar_muitos` (a escrita de fim de tick) de fato precisa regravar.
    # P02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco P): `dinheiro_total_pc` e `gravidez_ticks`
    # mudam a cada minuto simulado (trabalhar/comer/socializar; gestação) e ficaram de
    # fora por engano quando N02 (doc 2) montou esta lista — o sintoma era o reload de
    # `run_simulation.py` (a cada 5h) restaurar o dinheiro gravado no povoamento e
    # travar toda gravidez em 0% (§4 do documento: um dia inteiro de trabalho desfeito
    # três vezes, gravidez nunca chega aos 2880 ticks porque o reload some antes).
    _COLUNAS_QUENTES = ("energia", "fome", "social", "saude", "humor", "acao_atual",
                        "localizacao_atual_id", "dinheiro_total_pc", "gravidez_ticks")

    def salvar_completo(self, npcs: list) -> None:
        """N02 (docs/13_PLANO_POPULACAO_E_ESCALA.md): a linha INTEIRA, numa transação só —
        o que `salvar_muitos` fazia antes desta tarefa (P05). Para as colunas FRIAS,
        que só mudam num evento de verdade: nascimento, morte, casamento, mudança de
        casa, contratação, crescimento de estágio de vida. Chame este método NESSES
        pontos, nunca no corpo do tick — é também o único caminho correto para um NPC
        que ainda não existe no banco (`salvar_muitos`, por ser `UPDATE`, não cria
        linha: ver o aviso no docstring dele).

        P03 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco P): a coluna `relacionamentos` gravada
        aqui é CÓPIA DE LEITURA (a poda de H05 e o dashboard leem ela), não fonte —
        `carregar_todos` lê da tabela `relacionamentos` (que tem `vinculo`, e é o que
        o Mestre consulta), nunca mais desta coluna."""
        if not npcs:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                '''INSERT OR REPLACE INTO npcs
                   (id, nome, profissao, profissao_id, cidade_id, casa_id, local_trabalho_id, localizacao_atual_id,
                    acao_atual, energia, dinheiro_total_pc, social, fome, saude, humor,
                    genero, estagio_vida, raca, personalidade, background, data_nascimento, estado_civil, conjuge_id, pai_id, mae_id, genealogia, relacionamentos, memoria_eventos, gravidez_ticks)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [(npc.id, npc.nome, npc.profissao, npc.profissao_id, npc.cidade_id, npc.casa_id, npc.local_trabalho_id,
                  npc.localizacao_atual_id, npc.acao_atual.value, npc.energia, npc.dinheiro_total_pc,
                  npc.social, npc.fome, npc.saude, npc.humor,
                  npc.genero, npc.estagio_vida, npc.raca, npc.personalidade, npc.background,
                  npc.data_nascimento, npc.estado_civil, npc.conjuge_id, npc.pai_id, npc.mae_id,
                  json.dumps(npc.genealogia), json.dumps(npc.relacionamentos), json.dumps(npc.memoria_eventos),
                  npc.gravidez_ticks)
                 for npc in npcs])

    def salvar_muitos(self, npcs: list) -> None:
        """N02 (docs/13_PLANO_POPULACAO_E_ESCALA.md): escrita de FIM DE TICK — um `UPDATE`
        estreito, só das colunas que mudam todo minuto simulado (`_COLUNAS_QUENTES`).
        Medido com 25.000 NPCs/150 relações cada: 944 ms com o `INSERT OR REPLACE` da
        linha inteira (o que hoje é `salvar_completo`), 84% disso só serializando
        `relacionamentos`/`genealogia`/`memoria_eventos` que não mudaram; 40,6 ms neste
        `UPDATE` estreito. `relacionamentos` já tem tabela própria
        (`salvar_relacionamento`) — a coluna JSON em `npcs` é cópia.

        ⚠️ Isto é um `UPDATE`, não um `INSERT OR REPLACE`: numa linha que ainda não
        existe ele NÃO FALHA, só não faz nada — o NPC viveria o tick inteiro em
        memória e sumiria no próximo carregamento, em silêncio. Todo NPC novo (parto,
        Modo Mestre) tem que passar por `salvar_completo` ANTES de entrar em
        `mundo.npcs`; é isso que garante que, quando o laço do tick chegar aqui, a
        linha já existe."""
        if not npcs:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                '''UPDATE npcs SET energia = ?, fome = ?, social = ?, saude = ?, humor = ?,
                   acao_atual = ?, localizacao_atual_id = ?, dinheiro_total_pc = ?, gravidez_ticks = ?
                   WHERE id = ?''',
                [(npc.energia, npc.fome, npc.social, npc.saude, npc.humor,
                  npc.acao_atual.value, npc.localizacao_atual_id, npc.dinheiro_total_pc,
                  npc.gravidez_ticks, npc.id)
                 for npc in npcs])

    def renomear(self, npc_id: str, novo_nome: str):
        with self.db.connection() as conn:
            conn.cursor().execute("UPDATE npcs SET nome = ? WHERE id = ?", (novo_nome, npc_id))

    def salvar_relacionamento(self, a_id: str, b_id: str, afinidade: int, vinculo: str):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                           (a_id, b_id, afinidade, vinculo))
            cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                           (b_id, a_id, afinidade, vinculo))

    def salvar_relacionamentos_muitos(self, pares: list) -> None:
        """E01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): uma transação pra TODOS os pares
        de relacionamento do tick — `pares` é uma lista de `(a_id, b_id, afinidade,
        vinculo)`; cada par grava as DUAS direções, como `salvar_relacionamento`."""
        if not pares:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                'INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                [linha for (a_id, b_id, afinidade, vinculo) in pares
                 for linha in ((a_id, b_id, afinidade, vinculo), (b_id, a_id, afinidade, vinculo))])

    def listar_relacionamentos(self, npc_id: str) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT npc_b_id, afinidade, vinculo FROM relacionamentos WHERE npc_a_id = ? AND afinidade != 0', (npc_id,))
            return cursor.fetchall()

    def listar_relacionamentos_gerais(self, limite: int) -> list:
        """Amostra de vínculos não-neutros de qualquer par de NPCs (não filtrado por um
        NPC específico) — usada pelo contexto do Modo Mestre, que só precisa de um
        retrato geral da teia social, não da lista completa."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT npc_a_id, npc_b_id, afinidade, vinculo FROM relacionamentos WHERE afinidade != 0 LIMIT ?", (limite,))
            return cursor.fetchall()

    def listar_logs(self, npc_id: str, limite: int = 100) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp, level, message FROM npc_logs WHERE npc_id = ? ORDER BY id DESC LIMIT ?', (npc_id, limite))
            return cursor.fetchall()

    def buscar_por_cidade(self, cidade_id) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nome, profissao, genero, localizacao_atual_id, acao_atual FROM npcs WHERE cidade_id = ?', (cidade_id,))
            return cursor.fetchall()

    def listar_projecao_dashboard(self) -> list:
        """Projeção (não o dataclass `NPC` completo) usada só pelo payload polling do
        dashboard — enxuta de propósito, os campos são os que a UI consome."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nome, profissao, acao_atual, localizacao_atual_id, energia, fome, social, dinheiro_total_pc, saude, humor, genero, estagio_vida, data_nascimento, pai_id, mae_id, estado_civil, conjuge_id, gravidez_ticks FROM npcs')
            return cursor.fetchall()

    def contar_habitantes(self, filtro: FiltroHabitantes) -> int:
        clausula, parametros = _montar_where_habitantes(filtro)
        with self.db.connection() as conn:
            row = conn.cursor().execute(f"SELECT COUNT(*) AS n FROM npcs {clausula}", parametros).fetchone()
            return row["n"] if row else 0

    def listar_habitantes(self, filtro: FiltroHabitantes) -> list:
        """P02 (docs/16_PLANO_PAINEL_E_IA.md): paginação e filtro FEITOS NO SQL —
        antes a aba Habitantes recebia todos os NPCs do mundo e filtrava/paginava
        em JS."""
        clausula, parametros = _montar_where_habitantes(filtro)
        offset = (filtro.pagina - 1) * filtro.por_pagina
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT {_COLUNAS_CARTAO_HABITANTE} FROM npcs {clausula} "
                f"ORDER BY nome LIMIT ? OFFSET ?",
                (*parametros, filtro.por_pagina, offset))
            return cursor.fetchall()

    def listar_resumo_vivos(self, cidade_id) -> list:
        """M01 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco M): filtra por cidade — o
        contexto do Mestre listava os 840 NPCs do mundo inteiro sem filtro."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, profissao, local_trabalho_id, casa_id FROM npcs WHERE saude > 0 AND cidade_id = ?",
                (cidade_id,))
            return cursor.fetchall()

    def contar_dependentes_sem_responsavel(self, cidade_id) -> int:
        """M03 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco M): quantos bebês/crianças da
        cidade não têm pai NEM mãe vivo na MESMA casa — o invariante 6 de V05
        (audit_mundo.py, fora do runtime), reimplementado aqui como consulta SQL
        porque o Mestre roda no processo web, sem `EstadoDoMundo` vivo pra
        reaproveitar a checagem em memória do script de diagnóstico."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                """SELECT COUNT(*) AS n FROM npcs d
                   WHERE d.cidade_id = ? AND d.saude > 0
                     AND d.estagio_vida IN ('bebe', 'crianca')
                     AND NOT EXISTS (
                       SELECT 1 FROM npcs p
                       WHERE p.saude > 0 AND p.casa_id = d.casa_id
                         AND p.id IN (d.mae_id, d.pai_id)
                     )""",
                (cidade_id,)).fetchone()
            return row["n"] if row else 0

    def grau_social_por_ids(self, ids: list) -> dict:
        """M01: quantos vínculos não-neutros cada NPC tem — desempate pra priorizar
        quem entra no contexto do Mestre quando a cidade tem mais gente que o teto
        (`mestre.limite_npcs_contexto`)."""
        if not ids:
            return {}
        with self.db.connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in ids)
            rows = cursor.execute(
                f"SELECT npc_a_id, COUNT(*) AS grau FROM relacionamentos "
                f"WHERE npc_a_id IN ({placeholders}) AND afinidade != 0 GROUP BY npc_a_id",
                ids).fetchall()
            return {row["npc_a_id"]: row["grau"] for row in rows}


    # ------------------------------------------------------------------
    # Profissões (mercado de trabalho) — tabela `profissoes`, sempre referenciada a
    # partir de um NPC (quem ocupa a vaga), por isso vive no mesmo repositório.
    # ------------------------------------------------------------------

    def seed_profissoes(self, profissoes: list):
        with self.db.connection() as conn:
            conn.cursor().executemany(
                "INSERT OR IGNORE INTO profissoes (id, nome, categoria_local_id) VALUES (?, ?, ?)", profissoes)

    def listar_profissoes(self, excluir_id: str) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, categoria_local_id FROM profissoes WHERE id != ?", (excluir_id,))
            return cursor.fetchall()

    def buscar_candidatos_a_emprego(self, estagios_excluidos: list, profissao_excluida: str) -> list:
        """NPCs vivos, fora dos estágios de vida excluídos (bebê/criança/idoso/morto,
        Anexo 3#6), sem `profissao_excluida` (dependente), e sem trabalho válido
        (`local_trabalho_id` nulo ou apontando pra um local destruído/inexistente)."""
        placeholders = ",".join("?" for _ in estagios_excluidos)
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT n.id, n.nome, n.cidade_id, n.profissao_id, p.categoria_local_id
                FROM npcs n
                JOIN profissoes p ON n.profissao_id = p.id
                WHERE n.saude > 0
                  AND n.estagio_vida NOT IN ({placeholders})
                  AND n.profissao != ?
                  AND (
                    n.local_trabalho_id IS NULL
                    OR n.local_trabalho_id NOT IN (SELECT id FROM locais WHERE status = 1 AND tipo != 'Casa')
                  )
            """, (*estagios_excluidos, profissao_excluida))
            return cursor.fetchall()

    def contratar(self, npc_id: str, local_id: str, profissao_id: str, profissao_nome: str):
        with self.db.connection() as conn:
            conn.cursor().execute("""
                UPDATE npcs
                SET local_trabalho_id = ?,
                    profissao_id = ?,
                    profissao = ?
                WHERE id = ?
            """, (local_id, profissao_id, profissao_nome, npc_id))

    def demitir(self, npc_id: str, profissao_ociosa_id: str):
        with self.db.connection() as conn:
            conn.cursor().execute("""
                UPDATE npcs
                SET local_trabalho_id = NULL,
                    profissao_id = ?,
                    profissao = 'Desempregado'
                WHERE id = ?
            """, (profissao_ociosa_id, npc_id))
