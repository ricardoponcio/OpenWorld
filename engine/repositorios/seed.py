"""
MODULE: seed.py
FUNÇÃO: Aplica os dados de domínio (profissões mestras, mapeamento categoria->sistema)
        num `DatabaseManager` já existente.

DESCRIÇÃO:
    Antes, esses dois conjuntos viviam escritos em Python dentro de
    `DatabaseManager._init_db` (mapeamento) e `JobMarket.bootstrap_market`
    (profissões) — regra de negócio dentro de duas classes de infraestrutura (R-E04).
    Os dados agora moram em `database/seed_dominio.json`; `SemeadorDeDominio.aplicar`
    é chamado explicitamente por `builder/populate.py`, não mais como efeito colateral
    de abrir uma conexão.
"""
import json
import os

CAMINHO_SEED = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "seed_dominio.json")


class SemeadorDeDominio:
    @staticmethod
    def aplicar(db) -> None:
        with open(CAMINHO_SEED, "r", encoding="utf-8") as f:
            seed = json.load(f)

        profissoes = [(p["id"], p["nome"], p["categoria"]) for p in seed["profissoes"]]
        db.npcs.seed_profissoes(profissoes)

        mapeamento = list(seed["mapeamento_categorias"].items())
        db.locais.seed_mapeamento_categorias(mapeamento)
