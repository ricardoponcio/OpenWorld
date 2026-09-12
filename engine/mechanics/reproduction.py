import time
import random
import threading
from dataclasses import dataclass
from ..models import NPC, Evento, EstagioVida, HumorNPC, TipoEvento, Acao, Genero
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils
from ..ai import AIBiographyClient
from ..config_loader import cfg_get
from ..tempo import RelogioMundo
from ..mundo import EstadoDoMundo


def _extrair_sobrenome(nome: str) -> str:
    """Último token do nome completo, ou o próprio nome se for de uma palavra só."""
    partes = nome.split()
    return partes[-1] if len(partes) > 1 else nome


# Rótulo de exibição do gênero do bebê no resumo do evento de nascimento — não entra
# no enum Genero (que é domínio/persistência), é só apresentação (R-B02).
_ROTULO_GENERO_BEBE = {Genero.MASCULINO.value: "menino", Genero.FEMININO.value: "menina"}


@dataclass(frozen=True)
class DadosBatizado:
    """Tudo que a thread de batizado precisa para pedir o nome à IA e reescrever o
    evento de nascimento. Existe para o método assíncrono não ter 8 parâmetros
    (limite do projeto é 5 — ARQUITETURA.md Seção 4)."""
    bebe_id: str
    genero: str
    sobrenome: str
    nome_mae: str
    nome_pai: str
    nome_temporario: str
    pais_str: str
    evento_id: str


class NPCReproductionManager:
    """Concepção, parto e batizado. Recebe o mundo e a config, não a engine (R-F01):
    precisa dos NPCs, dos locais (para superlotação) e dos repositórios de NPC e
    evento."""

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def processar_concepcao(self):
        """Varredura noturna para concepção em casais que dividem a mesma casa e têm alta afinidade."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        por_casa = NPCUtils.agrupar_por_casa(self._mundo.npcs)
            
        for casa_id, moradores in por_casa.items():
            # Verifica apenas quem está na mesma casa de madrugada, independente se estão dormindo ou ociosos
            presentes = [m for m in moradores if m.localizacao_atual_id == casa_id]
            if len(presentes) < 2:
                continue
            
            # Procurar pares (M/F) férteis e com alta afinidade
            homens = [m for m in presentes if m.genero == Genero.MASCULINO.value and m.pode_procriar()]
            mulheres = [m for m in presentes if m.genero == Genero.FEMININO.value and m.pode_procriar() and m.gravidez_ticks == 0]
            
            casa_superlotada = NPCUtils.is_casa_superlotada(self._mundo.locais, self._mundo.npcs, casa_id)
            
            for h in homens:
                for m in mulheres:
                    afinidade = h.relacionamentos.get(m.id, 0)
                    afinidade_minima = cfg_get(cfg_bio, "concepcao_afinidade_minima")
                    if afinidade >= afinidade_minima:
                        # Sorteio de probabilidade de gravidez dependendo da superlotação
                        chance_gravidez = cfg_get(cfg_bio, "concepcao_chance_superlotacao") if casa_superlotada else cfg_get(cfg_bio, "concepcao_chance")
                        if random.random() < chance_gravidez:
                            m.gravidez_ticks = cfg_get(cfg_bio, "gravidez_duracao_ticks")
                            self._mundo.db.npcs.salvar(m)
                            
                            # Registrar evento de concepção
                            timestamp_rpg = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
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
                            self._mundo.db.eventos.salvar(evento)
                            WorldLogger.info(f"🤰 [GESTANTE] {resumo}", npc=m)
                            
                            # Uma mulher só pode engravidar de um parceiro por vez
                            break

    def processar_parto(self, mae: NPC):
        """Processa o nascimento de um bebê de uma NPC gestante."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        # 1. Encontrar o pai (o morador masculino com quem a mãe tem maior afinidade)
        pai = None
        moradores = NPCUtils.obter_moradores_da_casa(self._mundo.npcs, mae.casa_id, apenas_vivos=True)
        # Excluir a própria mãe da lista
        moradores = [n for n in moradores if n.id != mae.id]
        homens = [m for m in moradores if m.genero == Genero.MASCULINO.value and m.is_adulto()]
        if homens:
            homens.sort(key=lambda h: mae.relacionamentos.get(h.id, 0), reverse=True)
            pai = homens[0]
            
        # 2. Gerar o nome temporário e gênero do bebê
        genero_bebe = random.choice([g.value for g in Genero])
        nome_mae = mae.nome
        nome_pai = pai.nome if pai else "Desconhecido"
        
        nome_mae_curto = nome_mae.split()[0]
        nome_pai_curto = nome_pai.split()[0] if pai else "Desconhecido"
        nome_temp_bebe = f"Bebê de {nome_mae_curto} e {nome_pai_curto}" if pai else f"Bebê de {nome_mae_curto}"
        
        sobrenome_mae = _extrair_sobrenome(nome_mae)
        sobrenome_pai = _extrair_sobrenome(nome_pai) if pai else ""
        sobrenome_bebe = sobrenome_pai if sobrenome_pai else sobrenome_mae
        if sobrenome_mae and sobrenome_pai and sobrenome_mae != sobrenome_pai:
            sobrenome_bebe = f"{sobrenome_pai} {sobrenome_mae}" if random.random() < 0.5 else sobrenome_pai
            
        # 3. Criar e salvar o bebê com nome temporário no banco
        timestamp_rpg = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
        
        bebe_id = f"npc_nac_{int(time.time())}_{random.randint(0, 999)}"
        
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
            data_nascimento=self._mundo.data_simulada.isoformat(),
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
        self._mundo.db.npcs.salvar(novo_bebe)
        self._mundo.db.npcs.salvar(mae)
        if pai:
            self._mundo.db.npcs.salvar(pai)
            
        # Recarregar os NPCs do mundo para incluir o novo bebê na memória
        self._mundo.npcs = self._mundo.db.npcs.carregar_todos()
        
        # Registrar evento de parto com nome temporário
        pais_str = f"{mae.nome} e {pai.nome}" if pai else mae.nome
        resumo_temp = f"Nascimento na Vila! Nasceu o bebê {nome_temp_bebe} ({_ROTULO_GENERO_BEBE[genero_bebe]}), filho de {pais_str}."
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
        self._mundo.db.eventos.salvar(evento)
        WorldLogger.info(f"👶 [PARTO] {resumo_temp}", npc=mae)

        # 5. Batizado Assíncrono via IA rodando em Thread isolada (Estratégia C)
        self._iniciar_batizado_assincrono(DadosBatizado(
            bebe_id=bebe_id, genero=genero_bebe, sobrenome=sobrenome_bebe,
            nome_mae=nome_mae, nome_pai=nome_pai, nome_temporario=nome_temp_bebe,
            pais_str=pais_str, evento_id=evento_id,
        ))

    def _iniciar_batizado_assincrono(self, dados: DadosBatizado):
        """
        Dispara uma thread separada para gerar o nome do bebê via IA
        e atualizar o banco de dados e a memória em execução de forma assíncrona.
        """
        mundo = self._mundo

        def batizar_bebe_thread():
            try:
                # 1. Consulta o LLM em background (sem travar os ticks principais)
                nome_gerado = AIBiographyClient.gerar_nome_bebe(
                    dados.genero, dados.sobrenome, dados.nome_mae, dados.nome_pai)

                # 2. Persiste o nome final no banco de dados (Thread-Safe)
                mundo.db.npcs.renomear(dados.bebe_id, nome_gerado)

                # 3. Atualiza a descrição do evento de nascimento
                resumo_final = f"Nascimento na Vila! Nasceu o bebê {nome_gerado} ({_ROTULO_GENERO_BEBE[dados.genero]}), filho de {dados.pais_str}."
                mundo.db.eventos.atualizar_resumo(dados.evento_id, resumo_final)

                # 4. Sincroniza o novo nome na lista ativa de NPCs do mundo
                for n in mundo.npcs:
                    if n.id == dados.bebe_id:
                        n.nome = nome_gerado
                        break

                WorldLogger.info(f"👶 [IA-NOME] O bebê '{dados.nome_temporario}' foi batizado com sucesso como: '{nome_gerado}'!")
            except Exception as e:
                WorldLogger.error(f"❌ Erro ao batizar bebê de forma assíncrona: {e}")

        # Disparar thread daemon
        threading.Thread(target=batizar_bebe_thread, daemon=True).start()
