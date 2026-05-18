import time
import random
import threading
import sqlite3
from datetime import datetime
from ..models import NPC, Evento, EstagioVida, HumorNPC, TipoEvento, Acao
from ..logger import WorldLogger
from ..utils import NPCUtils
from ..ai import AIBiographyClient
from ..config_loader import cfg_get

class NPCReproductionManager:
    @staticmethod
    def processar_concepcao(engine):
        """Varredura noturna para concepção em casais que dividem a mesma casa e têm alta afinidade."""
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        por_casa = NPCUtils.agrupar_por_casa(engine.npcs)
            
        for casa_id, moradores in por_casa.items():
            # Verifica apenas quem está na mesma casa de madrugada, independente se estão dormindo ou ociosos
            presentes = [m for m in moradores if m.localizacao_atual_id == casa_id]
            if len(presentes) < 2:
                continue
            
            # Procurar pares (M/F) férteis e com alta afinidade
            homens = [m for m in presentes if m.genero == 'M' and m.pode_procriar()]
            mulheres = [m for m in presentes if m.genero == 'F' and m.pode_procriar() and m.gravidez_ticks == 0]
            
            for h in homens:
                for m in mulheres:
                    afinidade = h.relacionamentos.get(m.id, 0)
                    afinidade_minima = cfg_get(cfg_bio, "concepcao_afinidade_minima")
                    if afinidade >= afinidade_minima:
                        # Sorteio de probabilidade de gravidez
                        chance_gravidez = cfg_get(cfg_bio, "concepcao_chance")
                        if random.random() < chance_gravidez:
                            m.gravidez_ticks = cfg_get(cfg_bio, "gravidez_duracao_ticks")
                            engine.db.salvar_npc(m)
                            
                            # Registrar evento de concepção
                            dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
                            timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
                            resumo = f"Grande notícia em segredo: {m.nome} e {h.nome} estão esperando um bebê!"
                            
                            evento = Evento(
                                id=f"evt_concepcao_{int(time.time())}_{random.randint(0,999)}",
                                timestamp=timestamp_rpg,
                                local_id=casa_id,
                                envolvidos=[m.id, h.id],
                                tipo_evento=TipoEvento.CONCEPCAO.value,
                                modificador_afinidade=15,
                                resumo_estruturado=resumo
                            )
                            engine.db.salvar_evento(evento)
                            WorldLogger.info(f"🤰 [GESTANTE] {resumo}", npc=m)
                            
                            # Uma mulher só pode engravidar de um parceiro por vez
                            break

    @staticmethod
    def processar_parto(engine, mae: NPC):
        """Processa o nascimento de um bebê de uma NPC gestante."""
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        # 1. Encontrar o pai (o morador masculino com quem a mãe tem maior afinidade)
        pai = None
        moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, mae.casa_id, apenas_vivos=True)
        # Excluir a própria mãe da lista
        moradores = [n for n in moradores if n.id != mae.id]
        homens = [m for m in moradores if m.genero == 'M' and m.is_adulto()]
        if homens:
            homens.sort(key=lambda h: mae.relacionamentos.get(h.id, 0), reverse=True)
            pai = homens[0]
            
        # 2. Gerar o nome temporário e gênero do bebê
        genero_bebe = random.choice(['M', 'F'])
        nome_mae = mae.nome
        nome_pai = pai.nome if pai else "Desconhecido"
        
        nome_mae_curto = nome_mae.split()[0]
        nome_pai_curto = nome_pai.split()[0] if pai else "Desconhecido"
        nome_temp_bebe = f"Bebê de {nome_mae_curto} e {nome_pai_curto}" if pai else f"Bebê de {nome_mae_curto}"
        
        def extrair_sobrenome(nome):
            partes = nome.split()
            if len(partes) > 1:
                if "de" in partes:
                    return partes[-1]
                return partes[-1]
            return nome
            
        sobrenome_mae = extrair_sobrenome(nome_mae)
        sobrenome_pai = extrair_sobrenome(nome_pai) if pai else ""
        sobrenome_bebe = sobrenome_pai if sobrenome_pai else sobrenome_mae
        if sobrenome_mae and sobrenome_pai and sobrenome_mae != sobrenome_pai:
            sobrenome_bebe = f"{sobrenome_pai} {sobrenome_mae}" if random.random() < 0.5 else sobrenome_pai
            
        # 3. Criar e salvar o bebê com nome temporário no banco
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        bebe_id = f"npc_bebe_{int(time.time())}_{random.randint(0, 999)}"
        
        novo_bebe = NPC(
            id=bebe_id,
            nome=nome_temp_bebe,
            profissao="dependente",
            profissao_id="ocioso",
            casa_id=mae.casa_id,
            local_trabalho_id="",
            localizacao_atual_id=mae.casa_id,
            acao_atual=Acao.OCIOSO,
            energia=100.0,
            dinheiro_total_pc=0,
            social=100.0,
            fome=0.0,
            saude=100,
            humor=HumorNPC.ALEGRE.value,
            genero=genero_bebe,
            estagio_vida=EstagioVida.BEBE.value,
            data_nascimento=engine.data_simulada.isoformat(),
            pai_id=pai.id if pai else "",
            mae_id=mae.id,
            genealogia=list(set((pai.genealogia if pai else []) + mae.genealogia + ([pai.id, mae.id] if pai else [mae.id]))),
            relacionamentos={},
            memoria_eventos=[]
        )
        
        # 4. Atualizar relacionamentos dos pais com o bebê
        afinidade_inicial = cfg_get(cfg_bio, "parto_afinidade_inicial_pais")
        mae.relacionamentos[bebe_id] = afinidade_inicial
        novo_bebe.relacionamentos[mae.id] = afinidade_inicial
        if pai:
            pai.relacionamentos[bebe_id] = afinidade_inicial
            novo_bebe.relacionamentos[pai.id] = afinidade_inicial
            
        # Salvar pais e o novo bebê no banco
        engine.db.salvar_npc(novo_bebe)
        engine.db.salvar_npc(mae)
        if pai:
            engine.db.salvar_npc(pai)
            
        # Recarregar os NPCs na engine para incluir o novo bebê na memória
        engine.npcs = engine.db.carregar_npcs()
        
        # Registrar evento de parto com nome temporário
        pais_str = f"{mae.nome} e {pai.nome}" if pai else mae.nome
        resumo_temp = f"Nascimento na Vila! Nasceu o bebê {nome_temp_bebe} ({'menino' if genero_bebe == 'M' else 'menina'}), filho de {pais_str}."
        evento_id = f"evt_parto_{int(time.time())}_{random.randint(0,999)}"
        
        evento = Evento(
            id=evento_id,
            timestamp=timestamp_rpg,
            local_id=mae.casa_id,
            envolvidos=[mae.id, bebe_id] + ([pai.id] if pai else []),
            tipo_evento=TipoEvento.NASCIMENTO.value,
            modificador_afinidade=20,
            resumo_estruturado=resumo_temp
        )
        engine.db.salvar_evento(evento)
        WorldLogger.info(f"👶 [PARTO] {resumo_temp}", npc=mae)

        # 5. Batizado Assíncrono via IA rodando em Thread isolada (Estratégia C)
        NPCReproductionManager._iniciar_batizado_assincrono(
            engine, bebe_id, genero_bebe, sobrenome_bebe,
            nome_mae, nome_pai, nome_temp_bebe, pais_str, evento_id
        )

    @staticmethod
    def _iniciar_batizado_assincrono(engine, bebe_id: str, genero_bebe: str, sobrenome_bebe: str, 
                                     nome_mae: str, nome_pai: str, nome_temp_bebe: str, 
                                     pais_str: str, evento_id: str):
        """
        Dispara uma thread separada para gerar o nome do bebê via IA
        e atualizar o banco de dados e a memória em execução de forma assíncrona.
        """
        def batizar_bebe_thread():
            try:
                # 1. Consulta o LLM em background (sem travar os ticks principais)
                nome_gerado = AIBiographyClient.gerar_nome_bebe(genero_bebe, sobrenome_bebe, nome_mae, nome_pai)
                
                # 2. Persiste o nome final no banco de dados (Thread-Safe)
                conn = sqlite3.connect(engine.db.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE npcs SET nome = ? WHERE id = ?", (nome_gerado, bebe_id))
                
                # 3. Atualiza a descrição do evento de nascimento
                resumo_final = f"Nascimento na Vila! Nasceu o bebê {nome_gerado} ({'menino' if genero_bebe == 'M' else 'menina'}), filho de {pais_str}."
                cursor.execute("UPDATE eventos SET resumo_estruturado = ? WHERE id = ?", (resumo_final, evento_id))
                conn.commit()
                conn.close()
                
                # 4. Sincroniza o novo nome na lista ativa de NPCs da Engine
                for n in engine.npcs:
                    if n.id == bebe_id:
                        n.nome = nome_gerado
                        break
                        
                WorldLogger.info(f"👶 [IA-NOME] O bebê '{nome_temp_bebe}' foi batizado com sucesso como: '{nome_gerado}'!")
            except Exception as e:
                WorldLogger.error(f"❌ Erro ao batizar bebê de forma assíncrona: {e}")

        # Disparar thread daemon
        threading.Thread(target=batizar_bebe_thread, daemon=True).start()
