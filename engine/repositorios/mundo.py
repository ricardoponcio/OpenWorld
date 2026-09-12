from typing import Dict
from ..models import Cidade


class RepositorioMundo:
    """Continentes e cidades (`continentes`, `cidades`) — geografia/geopolítica global,
    importada uma vez do manifesto do Cartógrafo (R-E01)."""

    def __init__(self, db):
        self.db = db

    def salvar_continente(self, uuid: str, nome: str, area_real_km2: float):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO continentes (uuid, nome, area_real_km2) VALUES (?, ?, ?)',
                           (uuid, nome, area_real_km2))

    def salvar_cidade(self, continente_uuid: str, nome: str, tamanho: str, tipo: str, x_global: int, y_global: int) -> int:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO cidades (continente_uuid, nome, tamanho, tipo, x_global, y_global) VALUES (?, ?, ?, ?, ?, ?)',
                           (continente_uuid, nome, tamanho, tipo, x_global, y_global))
            return cursor.lastrowid

    def carregar_cidades_por_id(self) -> Dict[int, Cidade]:
        """R-C06: antes devolvia `list[dict]` cru — única forma de retorno crua entre os
        três carregadores (`carregar_npcs`/`carregar_locais_por_id` já devolviam
        dataclass). Os chamadores reindexavam por `id` na mão (`engine/core.py`)."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cidades')
            rows = cursor.fetchall()
            return {
                row['id']: Cidade(
                    id=row['id'], continente_uuid=row['continente_uuid'], nome=row['nome'],
                    tamanho=row['tamanho'], tipo=row['tipo'],
                    x_global=row['x_global'], y_global=row['y_global'],
                )
                for row in rows
            }

    def coordenadas(self, cidade_id):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT x_global, y_global FROM cidades WHERE id = ?", (cidade_id,)).fetchone()
            return (row["x_global"], row["y_global"]) if row else None

    def buscar_id_por_nome(self, nome: str):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute('SELECT id FROM cidades WHERE nome = ?', (nome,)).fetchone()
            return row['id'] if row else None
