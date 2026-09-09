"""
SCRIPT: storyteller.py
FUNÇÃO: Arquiteto Narrativo e de Construção (evento global de disparo único).
DESCRIÇÃO: Utiliza IA para descrever e criar um evento mundial pontual (afeta a Utility
           AI via modificadores), enriquecendo o lore. Reaproveita a coleta de contexto
           e a aplicação de ações de mundo de engine/mechanics/mestre.py (MestreManager)
           — a mesma base usada pelo Modo Mestre de IA interativo (Frente 5), em vez de
           duplicar essa lógica aqui.
"""
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.ai import AIStorytellerClient
from engine.database import DatabaseManager
from engine.mechanics.mestre import MestreManager

DB_PATH = "database/openworld.db"
TEMA_PADRAO = "Fantasia Medieval"  # mesmo tema usado em builder/populate.py


def run_storyteller(tema=TEMA_PADRAO):
    print(f"🎬 Storyteller: Analisando o estado de {tema}...")

    db = DatabaseManager(DB_PATH)
    contexto = MestreManager.montar_contexto(db)

    print("🧠 Consultando a Mente do Mundo...")
    try:
        evento = AIStorytellerClient.gerar_evento_global(tema, contexto)

        with db.connection() as conn:
            cursor = conn.cursor()
            ev_id = f"glob_{int(datetime.now().timestamp())}"
            cursor.execute(
                "INSERT INTO eventos_globais VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (ev_id, evento['titulo'], evento['descricao'], evento['tipo'],
                 evento.get('afeta_local_id'), json.dumps(evento['modificadores']),
                 evento['duracao_ticks'])
            )

        resultados = MestreManager.aplicar_acoes(db, evento.get('acoes_mundo', []))
        for r in resultados:
            print(f"  {r}")

        print(f"✨ EVENTO LANÇADO: {evento['titulo']}!")
        print(f"📜 {evento['descricao']}")
        print(f"⚙️ Modificadores: {evento['modificadores']}")

    except Exception as e:
        print(f"❌ Erro ao gerar evento: {e}")


if __name__ == "__main__":
    tema_arg = sys.argv[1] if len(sys.argv) > 1 else TEMA_PADRAO
    run_storyteller(tema_arg)
