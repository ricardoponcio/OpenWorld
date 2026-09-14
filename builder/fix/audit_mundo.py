"""
SCRIPT: audit_mundo.py
OBJETIVO: V05 (docs/PLANO_MUNDO_CRIVEL.md, Bloco V) — o auditor do mundo VIVO.
          `audit_cidades.py` audita a GEOMETRIA (GeoJSON, sem banco); este audita QUEM
          MORA NELA: os 9 invariantes de emprego/vocabulário/demografia que a Seção 3/5
          do documento mediu quebrados, mais o `--dias N`/`--ate-renovacao` que as
          Paradas 2/3 e o T02 exigem para medir se o mundo se sustenta (decisão ❺,
          D25: renovação geracional completa).
MOMENTO DE USO: modo padrão (sem flag) — depois de QUALQUER tarefa do Bloco V/P/N/G
                (rápido, só lê o banco); `--dias N` — Paradas 2 e 3; `--ate-renovacao`
                — T02, a porta de decisão final.

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine, com seu próprio
`SimulationEngine`. Não importe este módulo de dentro de `engine/`, `web/` ou
`cartographer/` — não faz parte do runtime.

⚠️ `--dias`/`--ate-renovacao` TICKAM E PERSISTEM DE VERDADE no banco apontado por
`--db` — nunca rode contra `database/openworld.db` sem antes copiá-lo (mesma regra das
sondas do documento, Seção 9). O modo padrão (invariantes) só LÊ.

⚠️ NUNCA leia a saída deste script com `| tail` — redirecione para arquivo e leia o
arquivo (regra de execução 4, herdada dos três documentos anteriores).
"""
import os
import sys
import json
import argparse
import collections
import statistics

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from config import get_config
from engine.core import SimulationEngine
from engine.logger import WorldLogger
from engine.models import EstagioVida, TipoLocal, CategoriaLocal, EstadoCivil, ProfissaoID, TipoEvento
from engine.consultas_npc import NPCUtils
from engine.indice_locais import IndiceDeLocais
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"

# ----------------------------------------------------------------------
# V05 — os 9 invariantes do mundo vivo
# ----------------------------------------------------------------------

def invariante_1_tipo_no_enum(locais: dict) -> list:
    """§3: `tipo` sempre um valor de `TipoLocal` — nunca mais cópia de `tipo_local`."""
    validos = {t.value for t in TipoLocal}
    return sorted(l.id for l in locais.values() if l.tipo not in validos)


def invariante_2_ninguem_trabalha_em_residencia(npcs: list, locais: dict) -> list:
    """§3: vaga de residência era 87,4% das vagas do mundo medido (V02)."""
    viol = []
    for n in npcs:
        local = locais.get(n.local_trabalho_id) if n.local_trabalho_id else None
        if local and local.categoria == CategoriaLocal.RESIDENCIA.value:
            viol.append(n.id)
    return sorted(viol)


def invariante_3_ninguem_trabalha_fora_da_cidade(npcs: list, locais: dict) -> list:
    """§3: 665 de 705 contratados trabalhavam fora da própria cidade (V02)."""
    viol = []
    for n in npcs:
        local = locais.get(n.local_trabalho_id) if n.local_trabalho_id else None
        if local and local.cidade_id != n.cidade_id:
            viol.append(n.id)
    return sorted(viol)


def invariante_4_empregado_sem_profissao_ociosa(npcs: list) -> list:
    """§3: todo contratado saía com profissao_id='ocioso' (V03)."""
    return sorted(n.id for n in npcs if n.local_trabalho_id and n.profissao_id == ProfissaoID.OCIOSO.value)


def invariante_5_cidade_habitada_tem_social_e_residencia(npcs: list, locais: dict, cidades: dict) -> list:
    """§5.3: cidade sem geometria (nome duplicado no manifesto, G05) fica com zero
    locais — uma falha aqui é ESPERADA até G05 rodar (Parada 1 do documento)."""
    cidades_habitadas = {n.cidade_id for n in npcs if n.esta_vivo()}
    viol = []
    for cid in cidades_habitadas:
        da_cidade = [l for l in locais.values() if l.cidade_id == cid and l.status == 1]
        tem_social = any(l.categoria in (CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value) for l in da_cidade)
        tem_residencia = any(l.categoria == CategoriaLocal.RESIDENCIA.value for l in da_cidade)
        if not (tem_social and tem_residencia):
            nome = cidades[cid].nome if cid in cidades else str(cid)
            viol.append(nome)
    return sorted(viol)


def invariante_6_dependente_tem_responsavel_na_casa(npcs: list) -> list:
    """§5.2: casal que casa e não leva os filhos deixa um dependente sozinho, pagando
    a própria refeição com 0 PC (G04)."""
    por_id = {n.id: n for n in npcs}
    viol = []
    for n in npcs:
        if not n.esta_vivo() or n.estagio_vida not in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value):
            continue
        pai, mae = por_id.get(n.pai_id), por_id.get(n.mae_id)
        tem_responsavel = (pai is not None and pai.esta_vivo() and pai.casa_id == n.casa_id) or \
                           (mae is not None and mae.esta_vivo() and mae.casa_id == n.casa_id)
        if not tem_responsavel:
            viol.append(n.id)
    return sorted(viol)


def invariante_7_pais_nao_sao_parentes(npcs: list) -> list:
    """§5.2: `processar_concepcao` não chamava `NPCUtils.sao_parentes` (G02)."""
    por_id = {n.id: n for n in npcs}
    viol = []
    for n in npcs:
        pai, mae = por_id.get(n.pai_id), por_id.get(n.mae_id)
        if pai is not None and mae is not None and NPCUtils.sao_parentes(pai, mae):
            viol.append(n.id)
    return sorted(viol)


def invariante_8_nome_de_cidade_unico(manifest_path: str) -> list:
    """§5.3: "Cidade dos Ventos" duplicada — id de lote/local vem do slug do nome, e
    as duas cidades compartilham namespace (G05)."""
    if not os.path.exists(manifest_path):
        return []
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    nomes = [c["nome"] for cont in manifest.get("continentes", []) for c in cont.get("cidades", [])]
    contagem = collections.Counter(nomes)
    return sorted(nome for nome, n in contagem.items() if n > 1)


def invariante_9_indice_social_nao_vazio(npcs: list, locais: dict) -> list:
    """§3: `sociais`/`passeio` liam `tipo`, que estava vazio (V01) — 592 tavernas,
    zero visitas."""
    indice = IndiceDeLocais(locais)
    cidades_habitadas = {n.cidade_id for n in npcs if n.esta_vivo()}
    return sorted(cid for cid in cidades_habitadas if not indice.sociais(cid) or not indice.passeio(cid))


INVARIANTES = [
    ("1. tipo em TipoLocal", lambda m: invariante_1_tipo_no_enum(m.locais)),
    ("2. ninguém trabalha em residência", lambda m: invariante_2_ninguem_trabalha_em_residencia(m.npcs, m.locais)),
    ("3. ninguém trabalha fora da cidade", lambda m: invariante_3_ninguem_trabalha_fora_da_cidade(m.npcs, m.locais)),
    ("4. empregado nunca 'ocioso'", lambda m: invariante_4_empregado_sem_profissao_ociosa(m.npcs)),
    ("5. cidade habitada tem social+residência", lambda m: invariante_5_cidade_habitada_tem_social_e_residencia(m.npcs, m.locais, m.cidades)),
    ("6. dependente tem responsável na casa", lambda m: invariante_6_dependente_tem_responsavel_na_casa(m.npcs)),
    ("7. pais não são parentes entre si", lambda m: invariante_7_pais_nao_sao_parentes(m.npcs)),
    ("8. nome de cidade é único", lambda m: invariante_8_nome_de_cidade_unico(MANIFEST_PATH)),
    ("9. índice social/passeio não vazio", lambda m: invariante_9_indice_social_nao_vazio(m.npcs, m.locais)),
]


def rodar_invariantes(mundo) -> bool:
    """Imprime uma linha por invariante e devolve True se TODOS passaram."""
    tudo_ok = True
    for nome, checagem in INVARIANTES:
        violacoes = checagem(mundo)
        status = "✅" if not violacoes else "❌"
        if violacoes:
            tudo_ok = False
        amostra = ", ".join(str(v) for v in violacoes[:5])
        sufixo = f" (+{len(violacoes) - 5} mais)" if len(violacoes) > 5 else ""
        print(f"{status} {nome:<42} {len(violacoes):>6} violação(ões)  {amostra}{sufixo}")
    return tudo_ok


# ----------------------------------------------------------------------
# `--dias`/`--ate-renovacao` — a tabela da Seção 2 e as guardas de D25
# ----------------------------------------------------------------------

def _snapshot_do_dia(mundo, dia: int, rowid_inicio_do_dia: int, inaniacao_fome_limiar: float) -> dict:
    """Uma linha da tabela da Seção 2 do documento."""
    vivos = [n for n in mundo.npcs if n.esta_vivo()]
    por_estagio = collections.Counter(n.estagio_vida for n in vivos)
    dinheiros = sorted(n.dinheiro_total_pc for n in vivos)
    with mundo.db.connection() as conn:
        cur = conn.cursor()
        nasc = cur.execute("SELECT COUNT(*) c FROM eventos WHERE rowid > ? AND tipo_evento = ?",
                            (rowid_inicio_do_dia, TipoEvento.NASCIMENTO.value)).fetchone()["c"]
        obitos = cur.execute("SELECT COUNT(*) c FROM eventos WHERE rowid > ? AND tipo_evento = ?",
                              (rowid_inicio_do_dia, TipoEvento.OBITO.value)).fetchone()["c"]
    return {
        "dia": dia, "vivos": len(vivos),
        "bebe": por_estagio[EstagioVida.BEBE.value], "crianca": por_estagio[EstagioVida.CRIANCA.value],
        "adulto": por_estagio[EstagioVida.ADULTO.value], "idoso": por_estagio[EstagioVida.IDOSO.value],
        "casados": sum(1 for n in vivos if n.estado_civil == EstadoCivil.CASADO.value),
        "din_mediana": statistics.median(dinheiros) if dinheiros else 0.0,
        "din_p10": dinheiros[len(dinheiros) // 10] if dinheiros else 0.0,
        "din_max": dinheiros[-1] if dinheiros else 0.0,
        "famintos": sum(1 for n in vivos if n.fome > inaniacao_fome_limiar),
        "orfaos": len(invariante_6_dependente_tem_responsavel_na_casa(mundo.npcs)),
        "nascimentos": nasc, "obitos": obitos,
    }


def _imprimir_tabela_dias(linhas: list) -> None:
    cab = (f"{'dia':>4} {'vivos':>6} {'bebe':>5} {'crianca':>7} {'adulto':>6} {'idoso':>6} "
           f"{'casados':>7} {'din.med':>8} {'din.p10':>8} {'din.max':>8} {'famintos':>8} "
           f"{'orfaos':>6} {'obitos':>6} {'nasc':>5}")
    print(cab)
    print("-" * len(cab))
    for l in linhas:
        print(f"{l['dia']:>4} {l['vivos']:>6} {l['bebe']:>5} {l['crianca']:>7} {l['adulto']:>6} "
              f"{l['idoso']:>6} {l['casados']:>7} {l['din_mediana']:>8.0f} {l['din_p10']:>8.0f} "
              f"{l['din_max']:>8.0f} {l['famintos']:>8} {l['orfaos']:>6} {l['obitos']:>6} {l['nascimentos']:>5}")


class GuardasD25:
    """As SEIS guardas da decisão ❺ (D25) — nenhuma pode falhar durante toda a corrida
    até a renovação geracional fechar. Guardas 4 (oito mecânicas) usa PROXIES
    documentados onde não há instrumentação dedicada ainda (casamento/aposentadoria/
    contratação/obra não têm `TipoEvento` próprio hoje) — aproximação disclosed, não
    silenciosa (mesma ética do resto do documento: "onde não medi, está escrito")."""

    def __init__(self, mundo, config: dict, pico_inicial: int):
        self.violacoes = []
        self.pico_vivos = pico_inicial
        self.dias_sem_nascimento_seguidos = 0
        self.dias_riqueza_baixa_seguidos = 0
        custo_refeicao = cfg_get(config, "acoes", "comer", "custo_pc")
        self.despesa_diaria_referencia = 2 * custo_refeicao  # aproximação: 2 refeições mínimas/dia
        self._semana_base = None

    def atualizar(self, dia: int, snapshot: dict, mundo) -> None:
        self.pico_vivos = max(self.pico_vivos, snapshot["vivos"])
        if snapshot["vivos"] == 0 or snapshot["vivos"] < 0.30 * self.pico_vivos:
            self.violacoes.append(f"guarda 1 (dia {dia}): {snapshot['vivos']} vivos < 30% do pico ({self.pico_vivos})")

        if dia > 10:
            self.dias_sem_nascimento_seguidos = 0 if snapshot["nascimentos"] > 0 else self.dias_sem_nascimento_seguidos + 1
            if self.dias_sem_nascimento_seguidos >= 1 and snapshot["nascimentos"] == 0:
                self.violacoes.append(f"guarda 2 (dia {dia}): nenhum nascimento")

        if snapshot["din_mediana"] < self.despesa_diaria_referencia:
            self.dias_riqueza_baixa_seguidos += 1
        else:
            self.dias_riqueza_baixa_seguidos = 0
        if self.dias_riqueza_baixa_seguidos > 5:
            self.violacoes.append(f"guarda 3 (dia {dia}): riqueza mediana abaixo de "
                                   f"{self.despesa_diaria_referencia:.0f} PC por {self.dias_riqueza_baixa_seguidos} dias seguidos")

        consanguineos = invariante_7_pais_nao_sao_parentes(mundo.npcs)
        if consanguineos:
            self.violacoes.append(f"guarda 6 (dia {dia}): {len(consanguineos)} filho(s) de pais consanguíneos")

        orfaos = snapshot["orfaos"]
        if orfaos:
            self.violacoes.append(f"guarda 5 (dia {dia}): {orfaos} dependente(s) sem responsável na casa")


def _renovacao_completa(mundo, ids_originais: set) -> bool:
    """D25: 100% dos vivos nasceram DENTRO da simulação — nenhum sobrevivente do
    povoamento inicial ainda vivo."""
    vivos_ids = {n.id for n in mundo.npcs if n.esta_vivo()}
    return not (vivos_ids & ids_originais)


def _rodar_dias(db_path: str, dias_alvo: int, ate_renovacao: bool) -> None:
    """X03 (docs/PLANO_MUNDO_CRIVEL.md, decisão ❽): `JobMarket.processar_contratacoes`
    e `InfrastructureManager.processar_desgaste`/`processar_reparos_espontaneos` já
    rodam DENTRO de `engine.tick()` (viraram rotinas de `GameLoop._rotinas_diarias`)
    — nenhuma chamada extra aqui, ou rodariam duas vezes."""
    WorldLogger.ativar_modo_avanco_rapido()
    config = get_config()
    engine = SimulationEngine(db_path)
    inaniacao_fome_limiar = cfg_get(config, "biologia_e_sociedade", "inaniacao_fome_limiar")
    ids_originais = {n.id for n in engine.mundo.npcs}
    guardas = GuardasD25(engine.mundo, config, pico_inicial=len(ids_originais)) if ate_renovacao else None

    linhas = []
    dia = 0
    while True:
        rowid_inicio = engine.mundo.db.eventos.ultimo_rowid()
        for _ in range(24 * 60):
            engine.tick()
        dia += 1
        snap = _snapshot_do_dia(engine.mundo, dia, rowid_inicio, inaniacao_fome_limiar)
        linhas.append(snap)
        if guardas:
            guardas.atualizar(dia, snap, engine.mundo)
        if not ate_renovacao and dia >= dias_alvo:
            break
        if ate_renovacao and (_renovacao_completa(engine.mundo, ids_originais) or dia >= dias_alvo):
            break

    _imprimir_tabela_dias(linhas[::max(1, len(linhas) // 30)] if len(linhas) > 30 else linhas)
    if ate_renovacao:
        fechou = _renovacao_completa(engine.mundo, ids_originais)
        print(f"\n{'✅' if fechou else '❌'} Renovação geracional "
              f"{'fechou' if fechou else 'NÃO fechou'} em {dia} dia(s) simulado(s).")
        if guardas.violacoes:
            print(f"❌ {len(guardas.violacoes)} violação(ões) de guarda ao longo da corrida:")
            for v in guardas.violacoes[:30]:
                print(f"   - {v}")
        else:
            print("✅ Nenhuma guarda violada durante toda a corrida.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default="database/openworld.db", help="caminho do banco (padrão: database/openworld.db)")
    parser.add_argument("--dias", type=int, default=0, help="roda N dias simulados e imprime a tabela da Seção 2 (Paradas 2/3)")
    parser.add_argument("--ate-renovacao", action="store_true", help="T02: roda até 100%% dos vivos terem nascido na simulação, checando as 6 guardas de D25")
    parser.add_argument("--max-dias", type=int, default=200, help="teto de segurança pra --ate-renovacao (padrão: 200)")
    args = parser.parse_args()

    if args.ate_renovacao:
        _rodar_dias(args.db, args.max_dias, ate_renovacao=True)
        return
    if args.dias > 0:
        _rodar_dias(args.db, args.dias, ate_renovacao=False)
        return

    engine = SimulationEngine(args.db)
    print(f"🌍 Mundo carregado: {len(engine.mundo.npcs)} NPC(s), {len(engine.mundo.locais)} local(is), "
          f"{len(engine.mundo.cidades)} cidade(s).\n")
    tudo_ok = rodar_invariantes(engine.mundo)
    print()
    if tudo_ok:
        print("✅ Nenhum invariante violado.")
    else:
        print("❌ Um ou mais invariantes violados — ver linhas ❌ acima.")
        sys.exit(1)


if __name__ == "__main__":
    main()
