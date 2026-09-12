from ..database import DatabaseManager
from ..logger import WorldLogger
from ..models import ProfissaoID, CategoriaLocal, EstagioVida, PROFISSAO_DEPENDENTE
from ..config_loader import cfg_get

class JobMarket:
    """Mercado de trabalho: vagas e contratação. Recebe o banco e a config de quem já
    os tem (R-F02) — antes abria seu próprio pool de conexões
    (`DatabaseManager(db_path)`), e `run_simulation.py` acabava com DOIS pools no mesmo
    processo (a `SimulationEngine` e o `JobMarket`), sem motivo nenhum."""
    def __init__(self, db: DatabaseManager, config: dict):
        self.db = db
        self.config = config

    def bootstrap_market(self):
        """Categoriza locais gerados pela IA que ainda não têm categoria de sistema.
        As profissões mestras e o mapeamento categoria->sistema são dado de domínio,
        aplicados uma vez por `SemeadorDeDominio.aplicar` (R-E04) — não mais um efeito
        colateral desta chamada."""
        locais = self.db.locais.buscar_genericos()
        if locais:
            WorldLogger.debug("🏠 Mapeando locais atuais para categorias...")
            for loc_id, nome, tipo in locais:
                nome_low = nome.lower()
                tipo_low = tipo.lower()

                cat = CategoriaLocal.GENERIC.value
                if 'fazenda' in nome_low or 'campo' in nome_low or 'agricultura' in nome_low:
                    cat = CategoriaLocal.FAZENDA.value
                elif 'quartel' in nome_low or 'guarda' in nome_low or 'elite' in nome_low or 'defesa' in tipo_low:
                    cat = CategoriaLocal.QUARTEL.value
                elif 'taverna' in nome_low or 'bar' in nome_low or 'dragão' in nome_low or 'social' in tipo_low:
                    cat = CategoriaLocal.TAVERNA.value
                elif 'escola' in nome_low or 'laboratório' in nome_low or 'alquimia' in nome_low or 'magia' in tipo_low or 'arcano' in nome_low:
                    cat = CategoriaLocal.UNIVERSIDADE.value
                elif 'forja' in nome_low or 'oficina' in tipo_low or 'porto' in nome_low or 'doca' in nome_low or 'mar' in tipo_low or 'mina' in nome_low:
                    cat = CategoriaLocal.FORJA.value
                elif 'comercio' in tipo_low or 'loja' in tipo_low or 'mercado' in nome_low:
                    cat = CategoriaLocal.MERCADO.value

                cfg_urbano = cfg_get(self.config, "geracao_urbana")
                capacidade_padrao = cfg_get(cfg_urbano, "capacidade_padrao_local")
                salario_padrao = cfg_get(cfg_urbano, "salario_padrao_local")
                self.db.locais.atualizar_categoria(loc_id, cat, capacidade_padrao, salario_padrao)

        WorldLogger.debug("✅ Mercado de Trabalho inicializado e configurado com sucesso!")

    def processar_contratacoes(self):
        """Varre o mundo em busca de vagas e NPCs desempregados."""
        WorldLogger.debug("🔍 Mercado de Trabalho: Verificando vagas...")

        # Carregar Mapeamento de Categorias de Trabalho (Tradução IA -> Sistema)
        mapeamento = self.db.locais.carregar_mapeamento_categorias_trabalho()

        # 1. Encontrar Locais com Vagas Abertas
        # Uma vaga está aberta se (capacidade - ocupacao atual) > 0
        locais = self.db.locais.buscar_vagas_disponiveis()

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
            return

        # 2. Encontrar NPCs Desempregados ou em locais destruídos
        # (local_trabalho_id IS NULL ou local de trabalho com status = 0)
        # Filtra bebês, crianças, dependentes, idosos e mortos para não entrarem no mercado de trabalho
        estagios_excluidos = [EstagioVida.BEBE.value, EstagioVida.CRIANCA.value, EstagioVida.IDOSO.value, EstagioVida.MORTO.value]
        desempregados = self.db.npcs.buscar_candidatos_a_emprego(estagios_excluidos, PROFISSAO_DEPENDENTE)

        # Carregar as profissões para mapear de volta quando contratado
        prof_rows = self.db.npcs.listar_profissoes(ProfissaoID.OCIOSO.value)
        prof_por_cat = {row['categoria_local_id']: (row['id'], row['nome']) for row in prof_rows}

        if not desempregados:
            return

        WorldLogger.debug(f"💼 Encontrados {len(desempregados)} NPCs buscando emprego.")

        # 3. Matchmaking
        contratacoes = 0
        for npc in desempregados:
            cat_desejada = npc['categoria_local_id']
            sucesso = False

            # Se for ocioso (Desempregado), aceita qualquer categoria com vagas
            if cat_desejada == 'nenhum':
                for cat_vaga, vagas_lista in vagas_por_categoria.items():
                    if vagas_lista:
                        cat_desejada = cat_vaga
                        break

            if cat_desejada in vagas_por_categoria and vagas_por_categoria[cat_desejada]:
                local_vaga = vagas_por_categoria[cat_desejada][0]
                p_id, p_nome = prof_por_cat.get(cat_desejada, (ProfissaoID.OCIOSO.value, 'Desempregado'))

                self.db.npcs.contratar(npc['id'], local_vaga['id'], p_id, p_nome)

                local_vaga['vagas'] -= 1
                if local_vaga['vagas'] <= 0:
                    vagas_por_categoria[cat_desejada].pop(0)
                WorldLogger.info(f"✅ CONTRATADO: {npc['nome']} começou a trabalhar em {local_vaga['id']} como {p_nome}!", npc=npc['id'])
                contratacoes += 1
                sucesso = True

            # Se não conseguiu emprego novo e o antigo era inválido, limpa o campo
            if not sucesso:
                self.db.npcs.demitir(npc['id'], ProfissaoID.OCIOSO.value)
                WorldLogger.info(f"🕵️  DESEMPREGADO: {npc['nome']} agora está buscando oportunidades.", npc=npc['id'])

        if contratacoes > 0:
            WorldLogger.info(f"📊 Total de novas contratações: {contratacoes}")
