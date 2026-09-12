from ..models import Lote, LoteEstado


class RepositorioLote:
    """T01 (docs/PLANO_CIDADE_VIVA.md): SQL da tabela `lotes` — terreno urbano como
    entidade de primeira classe. A GEOMETRIA do lote vem do GeoJSON do cartógrafo
    (imutável); este repositório é o único lugar que muda o ESTADO (armadilha 2)."""

    def __init__(self, db):
        self.db = db

    def salvar_em_lote(self, lotes: list) -> None:
        """Importação inicial (T02) — uma transação pra cidade toda, não um commit por
        lote (uma cidade grande tem milhares)."""
        if not lotes:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                """INSERT OR REPLACE INTO lotes
                   (id, cidade_id, quarteirao_id, bairro, banda, classe_frente, area_m2,
                    x, y, estado, local_id, dono_npc_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(l.id, l.cidade_id, l.quarteirao_id, l.bairro, l.banda, l.classe_frente,
                  l.area_m2, l.x, l.y, l.estado, l.local_id, l.dono_npc_id) for l in lotes],
            )

    def contar_por_estado(self, cidade_id: int) -> dict:
        """`{estado: contagem}` — gatilho de auto-expansão (X01) e dashboard."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT estado, COUNT(*) as n FROM lotes WHERE cidade_id = ? GROUP BY estado",
                (cidade_id,))
            return {row["estado"]: row["n"] for row in cursor.fetchall()}

    def reservar_livre(self, cidade_id: int, npc_id: str, perto_de=None, classe_frente=None):
        """Reserva o lote livre mais adequado pra `npc_id`, como UMA sentença
        condicional — não um SELECT seguido de UPDATE. O pool tem várias conexões e o
        dashboard escreve no mesmo banco; leitura-depois-escrita entregaria o mesmo
        lote pra dois casais. Devolve o id do lote reservado, ou `None` quando não
        havia nenhum livre — estado normal da cidade saturada (ARQUITETURA.md P5:
        falhar alto é pra config ausente, não pra estado de jogo esperado), não uma
        exceção; `None` é o sinal que dispara a auto-expansão do Bloco X.

        `perto_de` (x, y) ordena pelo lote livre mais próximo por distância AO
        QUADRADO (SQLite não tem função de distância; ao quadrado basta pra ordenar, e
        evita sqrt). Sem `perto_de`, ordena por id (determinístico)."""
        filtros = ["cidade_id = ?", "estado = 'livre'"]
        params = [cidade_id]
        if classe_frente is not None:
            filtros.append("classe_frente = ?")
            params.append(classe_frente)
        if perto_de is not None:
            px, py = perto_de
            ordem_sql = "ORDER BY ((x - ?) * (x - ?) + (y - ?) * (y - ?)) ASC"
            ordem_params = [px, px, py, py]
        else:
            ordem_sql = "ORDER BY id ASC"
            ordem_params = []
        where_sql = " AND ".join(filtros)

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""UPDATE lotes SET estado = ?, dono_npc_id = ?
                     WHERE id = (SELECT id FROM lotes WHERE {where_sql} {ordem_sql} LIMIT 1)
                        AND estado = 'livre'
                    RETURNING id""",
                [LoteEstado.OBRA.value, npc_id] + params + ordem_params,
            )
            row = cursor.fetchone()
            return row["id"] if row else None

    def concluir(self, lote_id: str, local_id: str) -> None:
        with self.db.connection() as conn:
            conn.cursor().execute(
                "UPDATE lotes SET estado = ?, local_id = ? WHERE id = ?",
                (LoteEstado.OCUPADO.value, local_id, lote_id))

    def liberar(self, lote_id: str) -> None:
        """Ruína devolve o terreno (T04) — condicional a `estado = 'ocupado'`: se
        alguém já reservou o lote de novo antes desta chamada rodar, não atropela."""
        with self.db.connection() as conn:
            conn.cursor().execute(
                "UPDATE lotes SET estado = ?, local_id = '', dono_npc_id = '' "
                "WHERE id = ? AND estado = ?",
                (LoteEstado.LIVRE.value, lote_id, LoteEstado.OCUPADO.value))
