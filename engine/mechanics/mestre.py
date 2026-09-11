"""
MODULE: mestre.py
FUNÇÃO: Backend do Modo Mestre de IA (Frente 5).

DESCRIÇÃO:
    Extrai e generaliza a lógica que antes vivia só em `builder/storyteller.py`
    (um script batch de disparo único) para ser reutilizável por um processo
    web interativo: coleta de contexto do mundo, aplicação de ações de mundo
    propostas pela IA, e coleta de eventos ocorridos num intervalo (para
    narrar "o que aconteceu" depois de avançar o tempo).

    Nenhuma ação de mundo é aplicada automaticamente — `aplicar_acoes` só é
    chamada depois que o jogador confirma explicitamente (ver web/mestre_routes.py).
"""
import random
import json
from ..database import DatabaseManager
from ..models import MetaChave, HumorNPC
from ..config_loader import cfg_get, carregar_config_global
from ..geo import GeoUtils


class MestreManager:
    @staticmethod
    def montar_contexto(db: DatabaseManager, limite_eventos: int = 10) -> dict:
        """Coleta o retrato atual do mundo para alimentar o prompt da IA."""
        with db.connection() as conn:
            cursor = conn.cursor()
            npcs = cursor.execute(
                "SELECT id, nome, profissao, local_trabalho_id, casa_id FROM npcs WHERE saude > 0"
            ).fetchall()
            locais = cursor.execute(
                "SELECT id, nome, tipo FROM locais WHERE status = 1"
            ).fetchall()
            rels = cursor.execute(
                "SELECT npc_a_id, npc_b_id, afinidade, vinculo FROM relacionamentos WHERE afinidade != 0 LIMIT 10"
            ).fetchall()
            eventos = cursor.execute(
                "SELECT resumo_estruturado FROM eventos ORDER BY rowid DESC LIMIT ?", (limite_eventos,)
            ).fetchall()
            ativos = cursor.execute(
                "SELECT titulo FROM eventos_globais WHERE ticks_restantes > 0"
            ).fetchall()

        return {
            "npcs": [f"{n['id']}: {n['nome']} ({n['profissao']}) | Trab: {n['local_trabalho_id']} | Casa: {n['casa_id']}" for n in npcs],
            "locais": [f"{l['id']}: {l['nome']} ({l['tipo']})" for l in locais],
            "relacionamentos": [f"{r['npc_a_id']} e {r['npc_b_id']} são {r['vinculo']} (Af:{r['afinidade']})" for r in rels],
            "ultimos_fatos": [e['resumo_estruturado'] for e in eventos],
            "eventos_ativos": [a['titulo'] for a in ativos],
        }

    @staticmethod
    def ultimo_rowid_eventos(db: DatabaseManager) -> int:
        """Marca o ponto atual do histórico de eventos, para depois coletar só o que é novo."""
        with db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT MAX(rowid) AS m FROM eventos").fetchone()
            return row['m'] or 0

    @staticmethod
    def coletar_eventos_apos(db: DatabaseManager, ultimo_rowid: int) -> list:
        """Retorna os eventos gerados desde `ultimo_rowid` (uso: narrar o que aconteceu
        depois de um avanço de tempo). Usa rowid, não o timestamp em texto ('Dia N, HH:MM'),
        porque esse texto não ordena corretamente para uma consulta por intervalo."""
        with db.connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT timestamp, resumo_estruturado FROM eventos WHERE rowid > ? ORDER BY rowid ASC",
                (ultimo_rowid,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def aplicar_acoes(db: DatabaseManager, acoes: list) -> list:
        """Aplica uma lista de ações de mundo já confirmadas pelo jogador. Retorna uma
        lista de strings descrevendo o que foi feito (para log/exibição)."""
        config = carregar_config_global()
        cfg_urbano = cfg_get(config, "geracao_urbana")
        raio = cfg_get(cfg_urbano, "locais_raio_px")
        nivel_mar = cfg_get(config, "cartografia", "nivel_mar")

        resultados = []
        novo_id_criado = None

        with db.connection() as conn:
            cursor = conn.cursor()

            # Fase 2.1 (P0.3): novo local do Mestre nasce em coordenada de MUNDO, ao
            # redor da cidade atualmente simulada — não mais uma grade local fake.
            # `cidade_simulada` é a única cidade com NPCs vivos hoje (Fase 2.2), então é
            # a âncora natural até o Mestre ganhar consciência de mais de uma cidade.
            cidade_id_simulada = db.carregar_meta(MetaChave.CIDADE_SIMULADA)
            cx_cidade, cy_cidade = 0.0, 0.0
            if cidade_id_simulada:
                row_cidade = cursor.execute(
                    "SELECT x_global, y_global FROM cidades WHERE id = ?", (cidade_id_simulada,)
                ).fetchone()
                if row_cidade:
                    cx_cidade, cy_cidade = row_cidade["x_global"], row_cidade["y_global"]

            for acao in acoes:
                d = acao.get("dados", acao)
                cmd = acao.get("comando")

                if cmd == "CRIAR_LOCAL":
                    existentes = {tuple(json.loads(r["coordenadas"])) for r in cursor.execute("SELECT coordenadas FROM locais").fetchall()}
                    ponto = GeoUtils.sortear_ponto_em_terra(cx_cidade, cy_cidade, raio, nivel_mar)
                    tentativa = 0
                    while tuple(ponto) in existentes and tentativa < 10:
                        ponto = GeoUtils.sortear_ponto_em_terra(cx_cidade, cy_cidade, raio, nivel_mar)
                        tentativa += 1

                    novo_id_criado = f"loc_mestre_{random.randint(0, 999999)}"
                    cursor.execute(
                        "INSERT INTO locais (id, nome, tipo, cidade_id, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, 1, 100, 5, 100)",
                        (novo_id_criado, d.get("nome", "Local Indefinido"), d.get("tipo", "Social"),
                         int(cidade_id_simulada) if cidade_id_simulada else None,
                         d.get("categoria", "generic"), d.get("descricao", ""), json.dumps(ponto))
                    )
                    resultados.append(f"🏗️ Criado: {d.get('nome')} em ({ponto[0]}, {ponto[1]})")

                elif cmd == "REATRIBUIR_NPC":
                    alvo = acao.get("id")
                    trab_id = d.get("local_trabalho_id")
                    if trab_id == "NOVO_LOCAL":
                        trab_id = novo_id_criado
                    casa_id = d.get("casa_id")
                    if casa_id == "NOVO_LOCAL":
                        casa_id = novo_id_criado

                    if trab_id and cursor.execute("SELECT id FROM locais WHERE id = ?", (trab_id,)).fetchone():
                        cursor.execute("UPDATE npcs SET local_trabalho_id = ? WHERE id = ?", (trab_id, alvo))
                        resultados.append(f"💼 {alvo} agora trabalha em {trab_id}")
                    if casa_id and cursor.execute("SELECT id FROM locais WHERE id = ?", (casa_id,)).fetchone():
                        cursor.execute("UPDATE npcs SET casa_id = ? WHERE id = ?", (casa_id, alvo))
                        resultados.append(f"🏠 {alvo} mudou-se para {casa_id}")

                elif cmd == "DESTRUIR_LOCAL":
                    cursor.execute("UPDATE locais SET status = 0, integridade = 0 WHERE id = ?", (acao.get("id"),))
                    resultados.append(f"💥 {acao.get('id')} foi destruído")

                elif cmd == "AFETAR_NPC":
                    # Humor vem da IA — entrada não confiável, valida contra o enum
                    # antes de persistir (R-C04/ARQUITETURA.md Seção 9).
                    try:
                        humor = HumorNPC(d.get("humor")).value
                    except ValueError:
                        humor = HumorNPC.NEUTRO.value
                    cursor.execute(
                        "UPDATE npcs SET saude = MAX(0, MIN(100, saude + ?)), humor = ? WHERE id = ?",
                        (d.get("saude", 0), humor, acao.get("id"))
                    )
                    resultados.append(f"👤 {acao.get('id')} afetado (saúde {d.get('saude', 0):+}, humor {humor})")

        return resultados
