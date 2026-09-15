"""
MODULE: serializadores.py
FUNÇÃO: Serialização de payloads HTTP com mais de 3 campos (ARQUITETURA §14.3) —
    fora das rotas, para manter cada rota em ≤ 10 linhas.
"""
import json
from datetime import datetime

from config import cfg_get, get_config
from engine.models import Acao, EstagioVida, MetaChave, SituacaoHabitante
from engine.tempo import RelogioMundo


def formatar_moeda(total_pc):
    """Movido de `web/dashboard.py` (P01, docs/16_PLANO_PAINEL_E_IA.md) — usado
    por `/api/estado` e, a partir de P02, também por `/api/habitantes`."""
    # Arredonda só na exibição — dinheiro é fracionário desde a Frente 4 (pago a cada tick de 1 min)
    total_pc = int(total_pc)
    po = total_pc // 1000
    resto_pp = total_pc % 1000
    pp = resto_pp // 100
    pc = resto_pp % 100
    parts = []
    if po > 0: parts.append(f"{po}po")
    if pp > 0: parts.append(f"{pp}pp")
    if pc > 0 or not parts: parts.append(f"{pc}pc")
    return ", ".join(parts)


def serializar_estado(db) -> dict:
    """P01 (docs/16_PLANO_PAINEL_E_IA.md): payload enxuto de `/api/estado` — nunca
    a lista de NPCs/locais (Armadilha 24), só o que o relógio, o botão de pausa,
    o banner de evento e o log de crônicas do topo precisam."""
    velocidade_raw = db.meta.carregar(MetaChave.VELOCIDADE)
    pausado_raw = db.meta.carregar(MetaChave.SIMULACAO_PAUSADA)
    hora_formatada = db.meta.carregar(MetaChave.HORA_FORMATADA)

    evg = db.eventos.buscar_global_ativo()
    evento_global = {"titulo": evg["titulo"], "descricao": evg["descricao"], "tipo": evg["tipo"]} if evg else None

    cronicas = [{"timestamp": r["timestamp"], "resumo": r["resumo_estruturado"]}
                for r in db.eventos.listar_recentes(15)]
    cronicas += [{"timestamp": r["timestamp_criacao"], "resumo": f"📢 EVENTO: {r['titulo']}"}
                 for r in db.eventos.listar_globais_recentes(5)]
    cronicas = sorted(cronicas, key=lambda c: c["timestamp"], reverse=True)[:20]

    # O03 (docs/16_PLANO_PAINEL_E_IA.md): velocidade EFETIVA vem do retrato que
    # run_simulation.py grava em MetaChave.ESTATISTICAS — null se ainda não houve
    # nenhuma medição (mundo recém-aberto, painel só lê, nunca mede por conta própria).
    estatisticas_raw = db.meta.carregar(MetaChave.ESTATISTICAS)
    desempenho = json.loads(estatisticas_raw).get("desempenho") if estatisticas_raw else None

    return {
        "hora": hora_formatada or "Sincronizando...",
        "pausado": pausado_raw == "1" if pausado_raw is not None else False,
        "velocidade_pedida": float(velocidade_raw) if velocidade_raw else 1.0,
        "velocidade_efetiva": desempenho["velocidade_efetiva"] if desempenho else None,
        "evento_global": evento_global,
        "cronicas": cronicas,
        # P02 (docs/16_PLANO_PAINEL_E_IA.md): estado.js lê isto pra armar o
        # próprio polling — ARQUITETURA §10 regra 6, nenhum número de config
        # repetido no JS.
        "polling_ms": cfg_get(get_config(), "painel", "estado_polling_ms"),
    }


def serializar_habitante(r) -> dict:
    """P02 (docs/16_PLANO_PAINEL_E_IA.md): uma linha da grade de habitantes —
    mesmo formato enxuto (chaves curtas) que `/api/update` já usava, pra não
    reescrever `painel_npcs.js`/`formatacao.js` além do necessário nesta tarefa."""
    return {
        "id": r["id"], "nome": r["nome"], "profissao": r["profissao"], "acao": r["acao_atual"],
        "status": {
            "e": r["energia"], "f": r["fome"], "s": r["social"],
            "d": formatar_moeda(r["dinheiro_total_pc"]), "h": r["saude"], "m": r["humor"],
        },
        "bio": {
            "g": r["genero"], "ev": r["estagio_vida"], "dn": r["data_nascimento"],
            "pai": r["pai_id"], "mae": r["mae_id"], "ec": r["estado_civil"],
            "cj": r["conjuge_id"], "gr": r["gravidez_ticks"],
        },
    }


def serializar_ficha_habitante(db, ficha: dict) -> dict:
    """P03 (docs/16_PLANO_PAINEL_E_IA.md): mesmo formato de `serializar_habitante`
    (reaproveitado), mais os nomes de mãe/pai/cônjuge e a lista de filhos que a
    ficha do modal precisa — todos resolvidos no servidor (`buscar_ficha`), nunca
    mais varrendo `allNpcs` no JS."""
    npc = ficha["npc"]
    limiar_morte = cfg_get(get_config(), "biologia_e_sociedade", "crescimento_dias_idoso_para_morte")
    data_simulada_iso = db.meta.carregar(MetaChave.HORA_ISO) or RelogioMundo.HORA_INICIAL_PADRAO_ISO
    data_simulada = datetime.fromisoformat(data_simulada_iso)

    resultado = serializar_habitante(npc)
    resultado["bio"]["idade"] = RelogioMundo.idade_em_anos(npc["data_nascimento"], data_simulada, limiar_morte)
    resultado["mae_nome"] = npc["mae_nome"]
    resultado["pai_nome"] = npc["pai_nome"]
    resultado["conjuge_nome"] = npc["conjuge_nome"]
    resultado["filhos"] = [{"id": f["id"], "nome": f["nome"], "estagio_vida": f["estagio_vida"]}
                            for f in ficha["filhos"]]
    return resultado


def serializar_filtros_habitantes(db) -> dict:
    """P02: catálogo de valores válidos pros filtros da aba Habitantes — servido,
    não copiado no JS (ARQUITETURA §10 regra 6). `FiltroNpc` (F03) sai de
    `constantes.js` em P04, substituído pelas `situacoes` daqui."""
    cidades = db.mundo.carregar_cidades_por_id()
    return {
        "cidades": [{"id": cid, "nome": c.nome} for cid, c in cidades.items()],
        "estagios": [e.value for e in EstagioVida],
        "acoes": [a.value for a in Acao],
        "situacoes": [s.value for s in SituacaoHabitante],
        "painel": cfg_get(get_config(), "painel"),
    }
