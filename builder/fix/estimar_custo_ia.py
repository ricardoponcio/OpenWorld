"""
SCRIPT: estimar_custo_ia.py
OBJETIVO: Estimar o custo de uso de IA a partir de `logs/ia_uso.jsonl` (I07,
          docs/16_PLANO_PAINEL_E_IA.md) — uma tabela por cliente e o total,
          mais a projeção de gasto por dia real.
MOMENTO DE USO: depois de uma sessão com IA de verdade (ex.: Parada 3), ou
                periodicamente pra acompanhar o gasto real do OpenRouter.
USO:
    venv/bin/python builder/fix/estimar_custo_ia.py \
        [--arquivo logs/ia_uso.jsonl] [--desde 2026-09-14T00:00:00] \
        [--cliente mestre] [--precos-ao-vivo]

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine, só lê o JSONL de uso
(e, com --precos-ao-vivo, a API pública do OpenRouter). Não faz parte do runtime.

⚠️ AVISO OBRIGATÓRIO: tokens contados pelo tokenizer do modelo que RESPONDEU
(Gemma/Qwen), não pelo do DeepSeek (o modelo de referência do preço).
Tokenizers diferentes contam o mesmo texto com diferença típica de 10-20%
(não medido neste projeto). Trate a estimativa como ordem de grandeza. As
respostas do DeepSeek também podem ser mais longas ou mais curtas que as do
modelo medido.
"""
import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from config import cfg_get, get_config
from engine.caminhos import na_raiz

AVISO_TOKENIZER = (
    "⚠️ Tokens contados pelo tokenizer do modelo que RESPONDEU (Gemma/Qwen), não pelo\n"
    "do DeepSeek (o modelo de referência do preço). Tokenizers diferentes contam o\n"
    "mesmo texto com diferença típica de 10-20% (não medido neste projeto). Trate a\n"
    "estimativa como ordem de grandeza. As respostas do DeepSeek também podem ser\n"
    "mais longas ou mais curtas que as do modelo medido."
)

_RESULTADOS_QUE_CONTAM_TOKENS = ("sucesso", "sucesso_truncado")


def ler_linhas(caminho: str, desde: str = None, cliente: str = None) -> list:
    linhas = []
    with open(caminho, "r", encoding="utf-8") as f:
        for bruta in f:
            bruta = bruta.strip()
            if not bruta:
                continue
            registro = json.loads(bruta)
            if desde and registro["ts"] < desde:
                continue
            if cliente and registro["cliente"] != cliente:
                continue
            linhas.append(registro)
    return linhas


def calcular_estimativa(linhas: list, preco_entrada_por_milhao: float, preco_saida_por_milhao: float) -> dict:
    """Pura — sem I/O nenhum (arquivo, rede, print). `main()` cuida só de
    argumentos, leitura de arquivo, rede opcional e impressão."""
    por_cliente = defaultdict(lambda: {
        "ok": 0, "truncadas": 0, "falhas": 0, "tokens_entrada": [], "tokens_saida": [],
        "estimados": 0, "custo_informado_usd": 0.0, "tem_custo_informado": False,
    })

    for r in linhas:
        c = por_cliente[r["cliente"]]
        if r["resultado"] in _RESULTADOS_QUE_CONTAM_TOKENS:
            c["ok"] += 1
            if r["resultado"] == "sucesso_truncado":
                c["truncadas"] += 1
            c["tokens_entrada"].append(r.get("tokens_entrada") or 0)
            c["tokens_saida"].append(r.get("tokens_saida") or 0)
            if r.get("tokens_estimados"):
                c["estimados"] += 1
            if r.get("custo_informado_usd") is not None:
                c["custo_informado_usd"] += r["custo_informado_usd"]
                c["tem_custo_informado"] = True
        else:
            c["falhas"] += 1

    por_cliente_final = {}
    total = defaultdict(float)
    total["tem_custo_informado"] = False

    for cliente, c in por_cliente.items():
        soma_entrada, soma_saida = sum(c["tokens_entrada"]), sum(c["tokens_saida"])
        custo = (soma_entrada / 1_000_000) * preco_entrada_por_milhao + (soma_saida / 1_000_000) * preco_saida_por_milhao
        por_cliente_final[cliente] = {
            "ok": c["ok"], "truncadas": c["truncadas"], "falhas": c["falhas"],
            "tokens_entrada_soma": soma_entrada,
            "tokens_entrada_media": statistics.mean(c["tokens_entrada"]) if c["tokens_entrada"] else 0.0,
            "tokens_saida_soma": soma_saida,
            "tokens_saida_media": statistics.mean(c["tokens_saida"]) if c["tokens_saida"] else 0.0,
            "pct_estimados": 100.0 * c["estimados"] / c["ok"] if c["ok"] else 0.0,
            "custo_usd": custo,
            "custo_por_mil_chamadas": (custo / c["ok"] * 1000) if c["ok"] else 0.0,
            "custo_informado_usd": c["custo_informado_usd"],
            "tem_custo_informado": c["tem_custo_informado"],
        }
        for chave in ("ok", "truncadas", "falhas"):
            total[chave] += c[chave]
        total["tokens_entrada_soma"] += soma_entrada
        total["tokens_saida_soma"] += soma_saida
        total["estimados"] += c["estimados"]
        total["custo_usd"] += custo
        total["custo_informado_usd"] += c["custo_informado_usd"]
        total["tem_custo_informado"] = total["tem_custo_informado"] or c["tem_custo_informado"]

    total["custo_por_mil_chamadas"] = (total["custo_usd"] / total["ok"] * 1000) if total["ok"] else 0.0
    total["pct_estimados"] = 100.0 * total["estimados"] / total["ok"] if total["ok"] else 0.0
    return {"por_cliente": por_cliente_final, "total": dict(total)}


def obter_precos_ao_vivo(modelo_referencia: str):
    """`GET /api/v1/models`, acha `id == modelo_referencia`, devolve
    `(preco_entrada_por_milhao, preco_saida_por_milhao)` — a API manda USD
    POR TOKEN, multiplicado por 1.000.000 aqui pra comparar com o config.
    `None` (e um aviso impresso) em qualquer falha — quem chama usa o preço do
    config nesse caso."""
    try:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=10) as resp:
            dados = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠️ Falha ao buscar preços ao vivo: {e} — usando o preço do config.")
        return None

    for modelo in dados.get("data", []):
        if modelo.get("id") == modelo_referencia:
            pricing = modelo.get("pricing", {})
            return float(pricing["prompt"]) * 1_000_000, float(pricing["completion"]) * 1_000_000
    print(f"⚠️ Modelo de referência '{modelo_referencia}' não encontrado em /models — usando o preço do config.")
    return None


def _janela_temporal(linhas: list):
    tempos = [datetime.fromisoformat(r["ts"]) for r in linhas]
    return min(tempos), max(tempos)


def imprimir_relatorio(estimativa: dict, linhas: list, modelo_referencia: str) -> None:
    print(f"Modelo de referência para preço: {modelo_referencia}\n")
    cab = (f"{'cliente':<28} {'ok':>5} {'trunc':>6} {'falhas':>7} {'tok_in_soma':>12} "
           f"{'tok_in_med':>10} {'tok_out_soma':>13} {'tok_out_med':>11} {'%estim':>7} "
           f"{'custo_usd':>10} {'usd/1000':>9}")
    print(cab)
    print("-" * len(cab))
    for cliente, c in sorted(estimativa["por_cliente"].items()):
        print(f"{cliente:<28} {c['ok']:>5} {c['truncadas']:>6} {c['falhas']:>7} "
              f"{c['tokens_entrada_soma']:>12} {c['tokens_entrada_media']:>10.0f} "
              f"{c['tokens_saida_soma']:>13} {c['tokens_saida_media']:>11.0f} "
              f"{c['pct_estimados']:>6.1f}% {c['custo_usd']:>10.4f} {c['custo_por_mil_chamadas']:>9.4f}")
    t = estimativa["total"]
    print("-" * len(cab))
    print(f"{'TOTAL':<28} {t['ok']:>5.0f} {t['truncadas']:>6.0f} {t['falhas']:>7.0f} "
          f"{t['tokens_entrada_soma']:>12.0f} {'':>10} {t['tokens_saida_soma']:>13.0f} {'':>11} "
          f"{t['pct_estimados']:>6.1f}% {t['custo_usd']:>10.4f} {t['custo_por_mil_chamadas']:>9.4f}")

    if t["tem_custo_informado"]:
        print(f"\nCusto REAL informado pelo provedor (soma de custo_informado_usd): ${t['custo_informado_usd']:.4f}")

    inicio, fim = _janela_temporal(linhas)
    duracao_s = max(1.0, (fim - inicio).total_seconds())
    projecao_dia = t["custo_usd"] * 86400 / duracao_s
    print(f"\nJanela coberta: {inicio.isoformat()} até {fim.isoformat()} ({duracao_s:.0f}s reais)")
    print(f"Projeção por dia real: ${projecao_dia:.4f}")

    if t["truncadas"] > 0:
        print(f"\n⚠️ {t['truncadas']:.0f} chamada(s) com resultado 'sucesso_truncado' — os tokens de "
              "entrada dessas chamadas são o TETO do contexto do servidor, não o tamanho real do prompt.")


def main():
    parser = argparse.ArgumentParser(description="Estima o custo de uso de IA a partir de logs/ia_uso.jsonl.")
    parser.add_argument("--arquivo", default="logs/ia_uso.jsonl")
    parser.add_argument("--desde", default=None, help="ISO 8601, ex.: 2026-09-14T00:00:00")
    parser.add_argument("--cliente", default=None, help="Filtra por um ClienteIA.value (ex.: mestre)")
    parser.add_argument("--precos-ao-vivo", action="store_true", dest="precos_ao_vivo")
    args = parser.parse_args()

    caminho = args.arquivo if os.path.isabs(args.arquivo) else na_raiz(args.arquivo)
    if not os.path.exists(caminho):
        print(f"❌ Arquivo não encontrado: {caminho}")
        sys.exit(1)

    cfg_custo = cfg_get(get_config(), "ia", "estimativa_custo")
    preco_entrada = cfg_get(cfg_custo, "preco_entrada_usd_por_milhao_tokens")
    preco_saida = cfg_get(cfg_custo, "preco_saida_usd_por_milhao_tokens")
    modelo_referencia = cfg_get(cfg_custo, "modelo_referencia")

    if args.precos_ao_vivo:
        precos = obter_precos_ao_vivo(modelo_referencia)
        if precos:
            preco_entrada, preco_saida = precos

    linhas = ler_linhas(caminho, desde=args.desde, cliente=args.cliente)
    if not linhas:
        print("Nenhuma linha encontrada (arquivo vazio ou filtro não bateu com nada).")
        sys.exit(0)

    imprimir_relatorio(calcular_estimativa(linhas, preco_entrada, preco_saida), linhas, modelo_referencia)
    print()
    print(AVISO_TOKENIZER)
    sys.exit(0)


if __name__ == "__main__":
    main()
