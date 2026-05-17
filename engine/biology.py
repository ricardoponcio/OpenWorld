import time
import random
import re
from datetime import datetime
from typing import List
from .models import NPC, Evento, EstagioVida, HumorNPC, TipoEvento
from .logger import WorldLogger

class NPCBiologyManager:
    @staticmethod
    def processar_concepcao(engine):
        """Varredura noturna para concepção em casais que dividem a mesma casa e têm alta afinidade."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        por_casa = {}
        for npc in engine.npcs:
            if not npc.casa_id:
                continue
            from .models import Acao
            if npc.acao_atual != Acao.DORMIR:
                continue
            if npc.casa_id not in por_casa:
                por_casa[npc.casa_id] = []
            por_casa[npc.casa_id].append(npc)
            
        for casa_id, moradores in por_casa.items():
            if len(moradores) < 2:
                continue
            
            # Procurar pares (M/F) férteis e com alta afinidade
            homens = [m for m in moradores if m.genero == 'M' and m.pode_procriar()]
            mulheres = [m for m in moradores if m.genero == 'F' and m.pode_procriar() and m.gravidez_ticks == 0]
            
            for h in homens:
                for m in mulheres:
                    afinidade = h.relacionamentos.get(m.id, 0)
                    afinidade_minima = cfg_bio.get("concepcao_afinidade_minima", 80)
                    if afinidade >= afinidade_minima:
                        # Sorteio de probabilidade de gravidez
                        chance_gravidez = cfg_bio.get("concepcao_chance", 0.20)
                        if random.random() < chance_gravidez:
                            m.gravidez_ticks = cfg_bio.get("gravidez_duracao_ticks", 192)
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
                            WorldLogger.info(f"🤰 [GESTANTE] {resumo}")
                            
                            # Uma mulher só pode engravidar de um parceiro por vez
                            break

    @staticmethod
    def processar_parto(engine, mae: NPC):
        """Processa o nascimento de um bebê de uma NPC gestante."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        # 1. Encontrar o pai (o morador masculino com quem a mãe tem maior afinidade)
        pai = None
        moradores = [n for n in engine.npcs if n.casa_id == mae.casa_id and n.id != mae.id]
        homens = [m for m in moradores if m.genero == 'M' and m.is_adulto()]
        if homens:
            homens.sort(key=lambda h: mae.relacionamentos.get(h.id, 0), reverse=True)
            pai = homens[0]
            
        # 2. Gerar o nome e gênero do bebê
        genero_bebe = random.choice(['M', 'F'])
        nome_mae = mae.nome
        nome_pai = pai.nome if pai else "Desconhecido"
        
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
            
        prompt = f"Um bebê do gênero {genero_bebe} nasceu. A mãe se chama {nome_mae} e o pai se chama {nome_pai}. Gere um nome próprio e sobrenome bonito e condizente (ex: Alistair {sobrenome_bebe}). Retorne apenas o nome completo final."
        
        nome_bebe = ""
        try:
            from builder.generator import AIWorldGenerator
            res_ia = AIWorldGenerator.ask_ai(prompt).strip()
            res_ia = re.sub(r'["\'`\n\r]', '', res_ia)
            if res_ia and len(res_ia) < 50 and "Erro" not in res_ia:
                nome_bebe = res_ia
        except Exception as e:
            pass
            
        if not nome_bebe:
            nomes_masculinos = ["Arthur", "Alistair", "Tristan", "Cedric", "Edric", "Kaelen", "Gareth", "Rowan", "Elian", "Lucas"]
            nomes_femininos = ["Lyra", "Elora", "Sylvia", "Aria", "Eliana", "Maeve", "Seraphina", "Isolde", "Clara", "Fiona"]
            primeiro_nome = random.choice(nomes_masculinos) if genero_bebe == 'M' else random.choice(nomes_femininos)
            nome_bebe = f"{primeiro_nome} {sobrenome_bebe}"
            
        # 3. Criar e salvar o bebê no banco
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        bebe_id = f"npc_bebe_{int(time.time())}_{random.randint(0, 999)}"
        from .models import Acao
        
        novo_bebe = NPC(
            id=bebe_id,
            nome=nome_bebe,
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
            genealogia=[pai.id, mae.id] if pai else [mae.id],
            relacionamentos={},
            memoria_eventos=[]
        )
        
        # 4. Atualizar relacionamentos dos pais com o bebê
        afinidade_inicial = cfg_bio.get("parto_afinidade_inicial_pais", 100)
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
        
        # Registrar evento de parto
        pais_str = f"{mae.nome} e {pai.nome}" if pai else mae.nome
        resumo = f"Nascimento na Vila! Nasceu o bebê {nome_bebe} ({'menino' if genero_bebe == 'M' else 'menina'}), filho de {pais_str}."
        
        evento = Evento(
            id=f"evt_parto_{int(time.time())}_{random.randint(0,999)}",
            timestamp=timestamp_rpg,
            local_id=mae.casa_id,
            envolvidos=[mae.id, bebe_id] + ([pai.id] if pai else []),
            tipo_evento=TipoEvento.NASCIMENTO.value,
            modificador_afinidade=20,
            resumo_estruturado=resumo
        )
        engine.db.salvar_evento(evento)
        WorldLogger.info(f"👶 [PARTO] {resumo}")

    @staticmethod
    def processar_crescimento(engine):
        """Varredura diária para processar o crescimento e transição de estágios de vida dos NPCs."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"

        for npc in engine.npcs:
            if not npc.esta_vivo() or not npc.data_nascimento:
                continue
            
            try:
                dt_str = npc.data_nascimento.replace(' ', 'T')
                birth = datetime.fromisoformat(dt_str)
                idade_dias = (engine.data_simulada - birth).days
            except Exception as e:
                continue

            # Bebê -> Criança
            limiar_crianca = cfg_bio.get("crescimento_dias_bebe_para_crianca", 1)
            if npc.estagio_vida == EstagioVida.BEBE.value and idade_dias >= limiar_crianca:
                npc.estagio_vida = EstagioVida.CRIANCA.value
                
                resumo = f"Crescimento: O pequeno bebê {npc.nome} deu seus primeiros passos e agora é uma linda criança!"
                WorldLogger.info(f"🌱 [CRESCIMENTO] {resumo}")
                
                evento = Evento(
                    id=f"evt_crescer_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.CRESCIMENTO.value,
                    modificador_afinidade=15,
                    resumo_estruturado=resumo
                )
                engine.db.salvar_evento(evento)
                engine.db.salvar_npc(npc)

            # Criança -> Adulto
            elif npc.estagio_vida == EstagioVida.CRIANCA.value and idade_dias >= cfg_bio.get("crescimento_dias_crianca_para_adulto", 3):
                npc.estagio_vida = EstagioVida.ADULTO.value
                
                # Procura emprego no mercado de trabalho
                locais_trabalho = [l_id for l_id, l in engine.locais.items() if l.tipo not in ('Casa', 'Social') and getattr(l, 'status', 1) == 1]
                if locais_trabalho:
                    npc.local_trabalho_id = random.choice(locais_trabalho)
                    loc_trab = engine.locais[npc.local_trabalho_id]
                    npc.profissao = f"Auxiliar de {loc_trab.nome}"
                else:
                    npc.local_trabalho_id = ""
                    npc.profissao = "Trabalhador Autônomo"

                resumo = f"Maioridade: {npc.nome} atingiu a maioridade, tornando-se adulto(a) e assumindo o papel de {npc.profissao}!"
                WorldLogger.info(f"🌱 [MAIORIDADE] {resumo}")

                evento = Evento(
                    id=f"evt_adulto_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.MAIORIDADE.value,
                    modificador_afinidade=20,
                    resumo_estruturado=resumo
                )
                engine.db.salvar_evento(evento)
                engine.db.salvar_npc(npc)
