"""
MODULE: serializadores.py
FUNÇÃO: Serialização de payloads HTTP com mais de 3 campos (ARQUITETURA §14.3) —
    fora das rotas, para manter cada rota em ≤ 10 linhas.
"""
import json

from engine.models import MetaChave


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
    }
