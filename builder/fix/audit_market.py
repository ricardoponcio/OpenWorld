"""
SCRIPT: audit_market.py
OBJETIVO: Auditoria de Compatibilidade e Saúde da Economia Urbana.
MOMENTO DE USO: Use este script para verificar por que NPCs continuam desempregados mesmo havendo vagas, 
                ou para identificar categorias de prédios que ainda não existem no mapa.
MOTIVAÇÃO: Desenvolvido para diagnosticar o 'Mismatch de Categorias', onde NPCs tinham profissões (ex: Alquimista)
           mas o mundo não possuía locais compatíveis (ex: Laboratório), resultando em desemprego estrutural.

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine, com conexão SQLite própria e
caminho relativo à raiz do projeto. Não importe estes módulos de dentro de engine/,
web/ ou cartographer/ — eles não fazem parte do runtime.
"""
import sqlite3

def audit():
    conn = sqlite3.connect('database/openworld.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("📊 --- AUDITORIA DE MERCADO --- 📊\n")

    # Carregar Mapeamento
    cursor.execute("SELECT termo, categoria_sistema FROM mapeamento_categorias_trabalho")
    mapeamento = {row[0]: row[1] for row in cursor.fetchall()}

    # 1. Locais e Vagas
    locais = cursor.execute("""
        SELECT categoria, COUNT(*) as qtd, SUM(capacidade) as cap_total,
        (SELECT COUNT(*) FROM npcs WHERE local_trabalho_id IN (SELECT id FROM locais WHERE categoria = l.categoria)) as ocupados
        FROM locais l WHERE status = 1 AND tipo != 'Casa' GROUP BY categoria
    """).fetchall()
    
    cat_vagas = {}
    for loc in locais:
        cat_sistema = mapeamento.get(loc['categoria'].lower(), loc['categoria'].lower())
        vagas = loc['cap_total'] - loc['ocupados']
        cat_vagas[cat_sistema] = cat_vagas.get(cat_sistema, 0) + vagas

    # 2. Desempregados
    demandas = cursor.execute("""
        SELECT p.categoria_local_id, COUNT(*) as qtd
        FROM npcs n JOIN profissoes p ON n.profissao_id = p.id
        WHERE n.local_trabalho_id IS NULL GROUP BY p.categoria_local_id
    """).fetchall()

    for dem in demandas:
        cat = dem['categoria_local_id']
        qtd = dem['qtd']
        vagas = cat_vagas.get(cat, 0)
        status = "✅ OK" if vagas >= qtd else "❌ MISMATCH"
        print(f" - [{cat.upper()}]: {qtd} NPCs sem emprego | Vagas disponíveis: {vagas} -> {status}")

    conn.close()

if __name__ == "__main__":
    audit()
