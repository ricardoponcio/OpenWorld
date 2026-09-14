"""
MODULE: gerenciador.py
FUNÇÃO: Backend do Modo Mestre de IA (Frente 5).

DESCRIÇÃO:
    Extrai e generaliza a lógica que antes vivia só em `builder/storyteller.py`
    (um script batch de disparo único) para ser reutilizável por um processo
    web interativo: coleta de contexto do mundo, aplicação de ações de mundo
    propostas pela IA, e coleta de eventos ocorridos num intervalo (para
    narrar "o que aconteceu" depois de avançar o tempo).

    Nenhuma ação de mundo é aplicada automaticamente — `aplicar_acoes` só é
    chamada depois que o jogador confirma explicitamente (ver web/mestre_routes.py).

    Recebe o banco e a config pelo construtor (R-F01/R-F03): os quatro métodos tomavam
    `db` como primeiro argumento, o que é um `self` disfarçado, e `aplicar_acoes` ainda
    chamava `carregar_config_global()` por conta própria no meio da regra.

    F01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): `aplicar_acoes` (chamado do processo do
    Flask) deixou de aplicar na hora — o Modo Mestre não tem o `EstadoDoMundo` vivo
    da simulação ali (11_ARQUITETURA.md, "regra de processo") — e passou a ENFILEIRAR
    (`mestre_acoes_pendentes`). `drenar_e_aplicar` é o lado oposto: só
    `run_simulation.py` chama, com o mundo vivo, a cada volta do laço."""
from typing import List

from ...database import DatabaseManager
from ...mundo import EstadoDoMundo
from ...models import MetaChave
from ...config_loader import cfg_get
from .acoes import POR_COMANDO, AcaoProposta, ContextoMestre


class MestreManager:
    def __init__(self, db: DatabaseManager, config: dict):
        self._db = db
        self._config = config

    def montar_contexto(self, cidade_id=None, limite_eventos: int = 10) -> dict:
        """Coleta o retrato atual do mundo para alimentar o prompt da IA.

        M01 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco M): filtrado pela CIDADE simulada
        (`cidade_id=None` usa `MetaChave.CIDADE_SIMULADA`) — sem filtro nem teto,
        840 NPCs já produziam 433.566 tokens medidos; com 25.000 seriam ~3 milhões.
        Residências entram como contagem agregada, não lista (22.624 linhas não são
        informação). M03: um bloco `avisos` com os invariantes de V05 quebrados
        agora — barato (2 consultas), e evita a IA narrar um mundo que ela não
        sabe que está quebrado."""
        if cidade_id is None:
            cidade_id = self._db.meta.carregar(MetaChave.CIDADE_SIMULADA)

        npcs_todos = self._db.npcs.listar_resumo_vivos(cidade_id)
        locais = self._db.locais.listar_ativos_resumo(cidade_id)
        n_residencias = self._db.locais.contar_residencias_ativas(cidade_id)
        rels = self._db.npcs.listar_relacionamentos_gerais(limite=10)
        eventos = self._db.eventos.resumos_recentes(limite_eventos)
        fofoca = self._db.eventos.resumos_recentes_de_fofoca(3)
        ativos = self._db.eventos.titulos_globais_ativos()

        npcs, n_omitidos = self._selecionar_npcs_do_contexto(npcs_todos, cidade_id)
        locais_txt = [f"{l['id']}: {l['nome']} ({l['tipo']})" for l in locais]
        if n_residencias:
            locais_txt.append(f"{n_residencias} residência(s)")

        return {
            "npcs": [f"{n['id']}: {n['nome']} ({n['profissao']}) | Trab: {n['local_trabalho_id']} | Casa: {n['casa_id']}" for n in npcs]
                    + ([f"+ {n_omitidos} outro(s) habitante(s) não listado(s)"] if n_omitidos else []),
            "locais": locais_txt,
            "relacionamentos": [f"{r['npc_a_id']} e {r['npc_b_id']} são {r['vinculo']} (Af:{r['afinidade']})" for r in rels],
            "ultimos_fatos": [e['resumo_estruturado'] for e in eventos],
            "fofoca_recente": [f['resumo_estruturado'] for f in fofoca],
            "eventos_ativos": [a['titulo'] for a in ativos],
            "avisos": self._avisos_do_mundo(cidade_id),
        }

    def _selecionar_npcs_do_contexto(self, npcs_todos: list, cidade_id) -> tuple:
        """M01: sem teto, devolve todo mundo. Acima do teto, prioriza quem
        apareceu num evento recente da cidade, depois quem tem mais grau social —
        devolve `(npcs_selecionados, quantos_ficaram_de_fora)`."""
        limite = cfg_get(self._config, "mestre", "limite_npcs_contexto")
        if len(npcs_todos) <= limite:
            return npcs_todos, 0

        recentes = self._db.eventos.ids_envolvidos_recentes_na_cidade(cidade_id, limite * 3)
        grau = self._db.npcs.grau_social_por_ids([n['id'] for n in npcs_todos])

        prioritarios = [n for n in npcs_todos if n['id'] in recentes]
        resto = sorted((n for n in npcs_todos if n['id'] not in recentes),
                        key=lambda n: grau.get(n['id'], 0), reverse=True)

        selecionados = (prioritarios + resto)[:limite]
        return selecionados, len(npcs_todos) - len(selecionados)

    def _avisos_do_mundo(self, cidade_id) -> list:
        """M03: invariantes de V05 quebrados AGORA, nesta cidade — as duas
        checagens mais baratas e mais relevantes pra narração (dependente
        abandonado, cidade sem vida social); as outras 7 de V05 são bugs
        estruturais, não estado transitório que a IA precisa saber pra narrar."""
        avisos = []
        sem_responsavel = self._db.npcs.contar_dependentes_sem_responsavel(cidade_id)
        if sem_responsavel:
            avisos.append(f"{sem_responsavel} dependente(s) sem responsável vivo na mesma casa.")
        if not self._db.locais.cidade_tem_local_social(cidade_id):
            avisos.append("Esta cidade não tem nenhum local social ativo (taverna/praça).")
        return avisos

    def ultimo_rowid_eventos(self) -> int:
        """Marca o ponto atual do histórico de eventos, para depois coletar só o que é novo."""
        return self._db.eventos.ultimo_rowid()

    def coletar_eventos_apos(self, ultimo_rowid: int) -> list:
        """Retorna os eventos gerados desde `ultimo_rowid` (uso: narrar o que aconteceu
        depois de um avanço de tempo). Usa rowid, não o timestamp em texto ('Dia N, HH:MM'),
        porque esse texto não ordena corretamente para uma consulta por intervalo."""
        return self._db.eventos.coletar_apos_rowid(ultimo_rowid)

    def aplicar_acoes(self, acoes: list) -> List[str]:
        """F01: ENFILEIRA as ações já confirmadas pelo jogador — não aplica na hora.
        `run_simulation.py` drena a fila a cada volta do laço, mesmo pausado, e
        aplica com o `EstadoDoMundo` vivo (`drenar_e_aplicar`). Devolve uma
        confirmação de envio, não o resultado da aplicação (que só existe depois).

        Comandos que não existem em `ComandoMestre` são descartados em silêncio: a
        lista vem de um LLM, e um comando inventado não é erro do jogador nem do
        sistema — mas ainda assim precisam ser filtrados ANTES de enfileirar, senão
        `drenar_e_aplicar` (que roda no laço quente da simulação) teria que validar
        de novo a cada payload."""
        payloads_validos = [p for p in acoes if AcaoProposta.de_payload(p) is not None]
        if not payloads_validos:
            return ["⚠️ Nenhuma ação reconhecida para enviar."] if acoes else []
        self._db.mestre.enfileirar_acoes(payloads_validos)
        return [f"📨 {len(payloads_validos)} ação(ões) enviada(s) — aplicadas no próximo tick da simulação."]

    def drenar_e_aplicar(self, mundo: EstadoDoMundo) -> List[str]:
        """F01: o lado da SIMULAÇÃO — só `run_simulation.py` chama isto, a cada volta
        do laço (inclusive pausado, mesmo padrão de `AVANCAR_MINUTOS`). Lê a fila,
        aplica cada ação com o `mundo` vivo (as classes em `acoes/` ganham
        `mundo.acordar`/`mundo.mover_npc`/`abrir_obra`, tudo que a simulação já usa),
        e devolve as descrições pra log."""
        payloads = self._db.mestre.drenar_acoes_pendentes()
        if not payloads:
            return []
        contexto = self._montar_contexto_de_mundo()

        resultados = []
        for payload in payloads:
            proposta = AcaoProposta.de_payload(payload)
            if proposta is None:
                continue
            resultados.extend(POR_COMANDO[proposta.comando].aplicar(mundo, contexto, proposta))
        return resultados

    def _montar_contexto_de_mundo(self) -> ContextoMestre:
        """Âncora geográfica e parâmetros que toda ação de criação precisa.

        `cidade_simulada` é a única cidade com NPCs vivos hoje (Fase 2.2), então é a
        âncora natural até o Mestre ganhar consciência de mais de uma cidade."""
        cidade_id = self._db.meta.carregar(MetaChave.CIDADE_SIMULADA)
        cx, cy = 0.0, 0.0
        if cidade_id:
            coords = self._db.mundo.coordenadas(cidade_id)
            if coords:
                cx, cy = coords

        return ContextoMestre(
            cidade_id_simulada=cidade_id,
            cx_cidade=cx,
            cy_cidade=cy,
            raio_px=cfg_get(self._config, "geracao_urbana", "locais_raio_px"),
            nivel_mar=cfg_get(self._config, "cartografia", "nivel_mar"),
            config=self._config,
        )
