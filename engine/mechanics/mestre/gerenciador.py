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
"""
from typing import List

from ...database import DatabaseManager
from ...models import MetaChave
from ...config_loader import cfg_get
from .acoes import POR_COMANDO, AcaoProposta, ContextoMestre


class MestreManager:
    def __init__(self, db: DatabaseManager, config: dict):
        self._db = db
        self._config = config

    def montar_contexto(self, limite_eventos: int = 10) -> dict:
        """Coleta o retrato atual do mundo para alimentar o prompt da IA."""
        npcs = self._db.npcs.listar_resumo_vivos()
        locais = self._db.locais.listar_ativos_resumo()
        rels = self._db.npcs.listar_relacionamentos_gerais(limite=10)
        eventos = self._db.eventos.resumos_recentes(limite_eventos)
        ativos = self._db.eventos.titulos_globais_ativos()

        return {
            "npcs": [f"{n['id']}: {n['nome']} ({n['profissao']}) | Trab: {n['local_trabalho_id']} | Casa: {n['casa_id']}" for n in npcs],
            "locais": [f"{l['id']}: {l['nome']} ({l['tipo']})" for l in locais],
            "relacionamentos": [f"{r['npc_a_id']} e {r['npc_b_id']} são {r['vinculo']} (Af:{r['afinidade']})" for r in rels],
            "ultimos_fatos": [e['resumo_estruturado'] for e in eventos],
            "eventos_ativos": [a['titulo'] for a in ativos],
        }

    def ultimo_rowid_eventos(self) -> int:
        """Marca o ponto atual do histórico de eventos, para depois coletar só o que é novo."""
        return self._db.eventos.ultimo_rowid()

    def coletar_eventos_apos(self, ultimo_rowid: int) -> list:
        """Retorna os eventos gerados desde `ultimo_rowid` (uso: narrar o que aconteceu
        depois de um avanço de tempo). Usa rowid, não o timestamp em texto ('Dia N, HH:MM'),
        porque esse texto não ordena corretamente para uma consulta por intervalo."""
        return self._db.eventos.coletar_apos_rowid(ultimo_rowid)

    def aplicar_acoes(self, acoes: list) -> List[str]:
        """Aplica uma lista de ações de mundo já confirmadas pelo jogador. Retorna uma
        lista de strings descrevendo o que foi feito (para log/exibição).

        Comandos que não existem em `ComandoMestre` são descartados em silêncio: a lista
        vem de um LLM, e um comando inventado não é erro do jogador nem do sistema."""
        contexto = self._montar_contexto_de_mundo()

        resultados = []
        for payload in acoes:
            proposta = AcaoProposta.de_payload(payload)
            if proposta is None:
                continue
            resultados.extend(POR_COMANDO[proposta.comando].aplicar(self._db, contexto, proposta))
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
        )
