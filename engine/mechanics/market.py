import sqlite3
from ..database import DatabaseManager
from ..logger import WorldLogger

class JobMarket:
    def __init__(self, db_path="database/openworld.db"):
        self.db_path = db_path
        self.db = DatabaseManager(db_path)

    def processar_contratacoes(self):
        """Varre o mundo em busca de vagas e NPCs desempregados."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        WorldLogger.debug("🔍 Mercado de Trabalho: Verificando vagas...")
        
        # Carregar Mapeamento de Categorias de Trabalho (Tradução IA -> Sistema)
        mapeamento = self.db.carregar_mapeamento_categorias_trabalho()

        # 1. Encontrar Locais com Vagas Abertas
        # Uma vaga está aberta se (capacidade - ocupacao atual) > 0
        locais = cursor.execute("""
            SELECT l.id, l.categoria, l.capacidade, 
            (SELECT COUNT(*) FROM npcs WHERE local_trabalho_id = l.id) as ocupacao
            FROM locais l
            WHERE l.status = 1 AND l.tipo != 'Casa'
        """).fetchall()

        vagas_por_categoria = {}
        for loc in locais:
            # Tenta traduzir a categoria (ex: 'padaria' -> 'comercio')
            cat_original = loc['categoria'].lower() if loc['categoria'] else 'generic'
            cat_sistema = mapeamento.get(cat_original, cat_original)
            
            vagas_livres = loc['capacidade'] - loc['ocupacao']
            if vagas_livres > 0:
                if cat_sistema not in vagas_por_categoria:
                    vagas_por_categoria[cat_sistema] = []
                vagas_por_categoria[cat_sistema].append({
                    "id": loc['id'],
                    "vagas": vagas_livres
                })

        if not vagas_por_categoria:
            WorldLogger.debug("📭 Nenhuma vaga disponível no momento.")
            conn.close()
            return

        # 2. Encontrar NPCs Desempregados ou em locais destruídos
        # (local_trabalho_id IS NULL ou local de trabalho com status = 0)
        # Filtra bebês, crianças e dependentes para não entrarem no mercado de trabalho
        desempregados = cursor.execute("""
            SELECT n.id, n.nome, n.profissao_id, p.categoria_local_id
            FROM npcs n
            JOIN profissoes p ON n.profissao_id = p.id
            WHERE n.saude > 0 
              AND n.estagio_vida NOT IN ('bebe', 'crianca')
              AND n.profissao != 'dependente'
              AND (
                n.local_trabalho_id IS NULL 
                OR n.local_trabalho_id NOT IN (SELECT id FROM locais WHERE status = 1 AND tipo != 'Casa')
              )
        """).fetchall()

        if not desempregados:
            conn.close()
            return

        WorldLogger.debug(f"💼 Encontrados {len(desempregados)} NPCs buscando emprego.")

        # 3. Matchmaking
        contratacoes = 0
        for npc in desempregados:
            cat_desejada = npc['categoria_local_id']
            sucesso = False
            
            if cat_desejada in vagas_por_categoria and vagas_por_categoria[cat_desejada]:
                local_vaga = vagas_por_categoria[cat_desejada][0]
                cursor.execute("UPDATE npcs SET local_trabalho_id = ? WHERE id = ?", (local_vaga['id'], npc['id']))
                local_vaga['vagas'] -= 1
                if local_vaga['vagas'] <= 0:
                    vagas_por_categoria[cat_desejada].pop(0)
                WorldLogger.info(f"✅ CONTRATADO: {npc['nome']} começou a trabalhar em {local_vaga['id']}!", npc=npc['id'])
                contratacoes += 1
                sucesso = True
            
            # Se não conseguiu emprego novo e o antigo era inválido, limpa o campo
            if not sucesso:
                cursor.execute("UPDATE npcs SET local_trabalho_id = NULL WHERE id = ?", (npc['id'],))
                WorldLogger.info(f"🕵️  DESEMPREGADO: {npc['nome']} agora está buscando oportunidades.", npc=npc['id'])

        conn.commit()
        conn.close()
        if contratacoes > 0:
            WorldLogger.info(f"📊 Total de novas contratações: {contratacoes}")

if __name__ == "__main__":
    market = JobMarket()
    market.processar_contratacoes()
