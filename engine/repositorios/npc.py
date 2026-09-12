import json
from ..models import NPC, Acao, EstadoCivil
from ..logger import WorldLogger


def _safe_json_load(data, default):
    try:
        return json.loads(data) if data else default
    except (json.JSONDecodeError, TypeError) as e:
        WorldLogger.warning(f"JSON corrompido em coluna de NPC, usando default {default!r}: {e}")
        return default


class RepositorioNPC:
    """SQL de NPCs, vínculos sociais e profissões (R-E01) — antes espalhado entre
    `DatabaseManager`, `engine/mechanics/market.py` e `engine/mechanics/mestre.py`."""

    def __init__(self, db):
        self.db = db

    def carregar_todos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            try:
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
                        relacionamentos=_safe_json_load(r['relacionamentos'], {}),
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
    _COLUNAS_QUENTES = ("energia", "fome", "social", "saude", "humor", "acao_atual",
                        "localizacao_atual_id")

    def salvar_completo(self, npcs: list) -> None:
        """N02 (docs/PLANO_POPULACAO_E_ESCALA.md): a linha INTEIRA, numa transação só —
        o que `salvar_muitos` fazia antes desta tarefa (P05). Para as colunas FRIAS,
        que só mudam num evento de verdade: nascimento, morte, casamento, mudança de
        casa, contratação, crescimento de estágio de vida. Chame este método NESSES
        pontos, nunca no corpo do tick — é também o único caminho correto para um NPC
        que ainda não existe no banco (`salvar_muitos`, por ser `UPDATE`, não cria
        linha: ver o aviso no docstring dele)."""
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
        """N02 (docs/PLANO_POPULACAO_E_ESCALA.md): escrita de FIM DE TICK — um `UPDATE`
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
                   acao_atual = ?, localizacao_atual_id = ? WHERE id = ?''',
                [(npc.energia, npc.fome, npc.social, npc.saude, npc.humor,
                  npc.acao_atual.value, npc.localizacao_atual_id, npc.id)
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
        """E01 (docs/PLANO_POPULACAO_E_ESCALA.md): uma transação pra TODOS os pares
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

    def listar_resumo_vivos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, profissao, local_trabalho_id, casa_id FROM npcs WHERE saude > 0")
            return cursor.fetchall()

    def atualizar_local_trabalho(self, npc_id: str, local_id: str):
        with self.db.connection() as conn:
            conn.cursor().execute("UPDATE npcs SET local_trabalho_id = ? WHERE id = ?", (local_id, npc_id))

    def atualizar_casa(self, npc_id: str, casa_id: str):
        with self.db.connection() as conn:
            conn.cursor().execute("UPDATE npcs SET casa_id = ? WHERE id = ?", (casa_id, npc_id))

    def ajustar_saude_e_humor(self, npc_id: str, delta_saude, humor: str):
        with self.db.connection() as conn:
            conn.cursor().execute(
                "UPDATE npcs SET saude = MAX(0, MIN(100, saude + ?)), humor = ? WHERE id = ?",
                (delta_saude, humor, npc_id)
            )

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
                SELECT n.id, n.nome, n.profissao_id, p.categoria_local_id
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
