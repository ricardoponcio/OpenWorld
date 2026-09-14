from dataclasses import dataclass, field
from ..database import DatabaseManager
from ..logger import WorldLogger
from ..models import ProfissaoID, CategoriaLocal, EstagioVida, PROFISSAO_DEPENDENTE
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo

_ESTAGIOS_SEM_EMPREGO = (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value, EstagioVida.IDOSO.value, EstagioVida.MORTO.value)


@dataclass
class _ContextoContratacao:
    """O que o matchmaking de uma cidade precisa saber SOBRE O MUNDO — separado de
    qual cidade e quais candidatos (ARQUITETURA.md Seção 4, limite de 5 parâmetros
    por método). `alterados` é o acumulador de NPCs vivos que mudaram — X02
    (docs/PLANO_MUNDO_CRIVEL.md): um `salvar_completo` por NPC contratado/demitido
    virou 11,6 s medidos com ~34 mil candidatos; grava tudo numa transação só, no
    fim de `processar_contratacoes`."""
    mapeamento: dict
    prof_por_cat: dict
    categorias_empregadoras: list
    alterados: list = field(default_factory=list)


class JobMarket:
    """Mercado de trabalho: vagas e contratação. Recebe o banco e a config de quem já
    os tem (R-F02) — antes abria seu próprio pool de conexões
    (`DatabaseManager(db_path)`), e `run_simulation.py` acabava com DOIS pools no mesmo
    processo (a `SimulationEngine` e o `JobMarket`), sem motivo nenhum.

    P01 (docs/PLANO_MUNDO_CRIVEL.md, Bloco P): `mundo` é OPCIONAL. Com ele, os
    candidatos vêm de `mundo.npcs` (já em memória, sem round-trip) e a contratação
    aplica no objeto vivo — o NPC descobre que foi contratado NA HORA, sem depender
    de `recarregar_habitantes()` (P02 tirou essa muleta do caminho quente). Sem
    `mundo` (`builder/populador.py`, antes de existir um `EstadoDoMundo` — é
    povoamento, não simulação), os candidatos vêm do banco e a escrita é só-banco.

    X03 (docs/PLANO_MUNDO_CRIVEL.md, decisão ❽): `processar_contratacoes` morava em
    `run_simulation.py`, fora de qualquer benchmark, rodando a cada 5h — a cadência
    de `GameLoop._rotinas_diarias` só suporta 1x/dia; mudança de cadência disclosed
    no Registro, não um efeito colateral silencioso."""
    CADENCIA = "por_dia"
    CADENCIA_HORA_CONFIG = "mercado_trabalho_hora"

    def __init__(self, db: DatabaseManager, config: dict, mundo: EstadoDoMundo = None):
        self.db = db
        self.config = config
        self._mundo = mundo

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
        """Varre o mundo em busca de vagas e NPCs desempregados. V02
        (docs/PLANO_MUNDO_CRIVEL.md, Bloco V): por CIDADE — um candidato só compete
        pelas vagas da PRÓPRIA cidade; sem vaga lá, fica desempregado (migração é
        decisão de domínio, nunca efeito colateral de matchmaking — mesmo raciocínio
        de P04, doc 1)."""
        WorldLogger.debug("🔍 Mercado de Trabalho: Verificando vagas...")

        desempregados = self._candidatos()
        if not desempregados:
            return

        WorldLogger.debug(f"💼 Encontrados {len(desempregados)} NPCs buscando emprego.")
        prof_rows = self.db.npcs.listar_profissoes(ProfissaoID.OCIOSO.value)
        ctx = _ContextoContratacao(
            mapeamento=self.db.locais.carregar_mapeamento_categorias_trabalho(),
            prof_por_cat={row['categoria_local_id']: (row['id'], row['nome']) for row in prof_rows},
            categorias_empregadoras=cfg_get(self.config, "urbanismo", "categorias_empregadoras"),
        )

        candidatos_por_cidade = {}
        for candidato in desempregados:
            candidatos_por_cidade.setdefault(candidato['cidade_id'], []).append(candidato)

        contratacoes = sum(
            self._contratar_na_cidade(cidade_id, candidatos, ctx)
            for cidade_id, candidatos in candidatos_por_cidade.items()
        )
        # X02 (docs/PLANO_MUNDO_CRIVEL.md): UMA transação pra todos os NPCs vivos
        # que mudaram, não uma por NPC — ver o docstring de `_ContextoContratacao`.
        if ctx.alterados:
            self.db.npcs.salvar_completo(ctx.alterados)
        if contratacoes > 0:
            WorldLogger.info(f"📊 Total de novas contratações: {contratacoes}")

    def _candidatos(self) -> list:
        """P01: com `mundo`, sai de `mundo.npcs` (memória); sem `mundo`, do banco
        (`buscar_candidatos_a_emprego`) — usado hoje só por
        `builder/populador.py::_inicializar_mercado_de_trabalho`. As duas origens
        devolvem o mesmo formato: `id`/`nome`/`cidade_id`/`categoria_local_id` e
        `npc_vivo` (o objeto de `mundo.npcs`, ou `None` na origem-banco)."""
        if self._mundo is not None:
            return self._candidatos_do_mundo()
        rows = self.db.npcs.buscar_candidatos_a_emprego(list(_ESTAGIOS_SEM_EMPREGO), PROFISSAO_DEPENDENTE)
        return [{"id": r["id"], "nome": r["nome"], "cidade_id": r["cidade_id"],
                  "categoria_local_id": r["categoria_local_id"], "npc_vivo": None} for r in rows]

    def _candidatos_do_mundo(self) -> list:
        """Mesmo critério de `RepositorioNPC.buscar_candidatos_a_emprego`, mas sobre
        `mundo.npcs`/`mundo.locais` em memória: vivo, fora dos estágios sem emprego,
        não-dependente, e sem trabalho VÁLIDO (categoria empregadora, local ativo)."""
        categorias_empregadoras = cfg_get(self.config, "urbanismo", "categorias_empregadoras")
        categoria_por_profissao = {row['id']: row['categoria_local_id']
                                    for row in self.db.npcs.listar_profissoes("")}
        candidatos = []
        for npc in self._mundo.npcs:
            if not npc.esta_vivo() or npc.estagio_vida in _ESTAGIOS_SEM_EMPREGO or npc.profissao == PROFISSAO_DEPENDENTE:
                continue
            local_atual = self._mundo.locais.get(npc.local_trabalho_id) if npc.local_trabalho_id else None
            tem_trabalho_valido = (local_atual is not None and local_atual.status == 1
                                    and local_atual.categoria in categorias_empregadoras)
            if tem_trabalho_valido:
                continue
            candidatos.append({
                "id": npc.id, "nome": npc.nome, "cidade_id": npc.cidade_id,
                "categoria_local_id": categoria_por_profissao.get(npc.profissao_id, "nenhum"),
                "npc_vivo": npc,
            })
        return candidatos

    def _vagas_por_categoria_na_cidade(self, cidade_id, ctx: _ContextoContratacao) -> dict:
        """V02: vagas abertas da cidade, traduzidas pra categoria de SISTEMA
        (ex.: 'padaria' -> 'comercio'). V03: uma categoria sem profissão mapeada em
        `database/seed_dominio.json` não vira vaga — contratar e chamar de
        'Desempregado' é pior que não contratar (era o fallback silencioso da
        consequência 2 do documento)."""
        locais = self.db.locais.buscar_vagas_disponiveis(cidade_id, ctx.categorias_empregadoras)
        vagas_por_categoria = {}
        for loc in locais:
            cat_original = loc['categoria'].lower() if loc['categoria'] else 'generic'
            cat_sistema = ctx.mapeamento.get(cat_original, cat_original)
            if cat_sistema not in ctx.prof_por_cat:
                WorldLogger.warning(
                    f"[MERCADO] Local '{loc['id']}' (categoria '{cat_original}' -> "
                    f"'{cat_sistema}') não tem profissão mapeada em database/"
                    f"seed_dominio.json — vaga não oferecida.")
                continue
            vagas_livres = loc['capacidade'] - loc['ocupacao']
            if vagas_livres > 0:
                vagas_por_categoria.setdefault(cat_sistema, []).append({"id": loc['id'], "vagas": vagas_livres})
        return vagas_por_categoria

    def _contratar_na_cidade(self, cidade_id, candidatos: list, ctx: _ContextoContratacao) -> int:
        """O matchmaking de uma única cidade — a unidade que V02 introduziu. Devolve
        quantos candidatos foram contratados."""
        vagas_por_categoria = self._vagas_por_categoria_na_cidade(cidade_id, ctx)

        contratacoes = 0
        for candidato in candidatos:
            cat_desejada = candidato['categoria_local_id']
            sucesso = False

            # Se for ocioso (Desempregado), aceita qualquer categoria com vagas
            if cat_desejada == 'nenhum':
                for cat_vaga, vagas_lista in vagas_por_categoria.items():
                    if vagas_lista:
                        cat_desejada = cat_vaga
                        break

            if cat_desejada in vagas_por_categoria and vagas_por_categoria[cat_desejada]:
                local_vaga = vagas_por_categoria[cat_desejada][0]
                # V03: toda vaga em `vagas_por_categoria` já passou pelo filtro de
                # profissão mapeada acima — nunca cai no fallback 'Desempregado'.
                p_id, p_nome = ctx.prof_por_cat[cat_desejada]

                self._efetivar_contratacao(candidato, local_vaga['id'], p_id, p_nome, ctx.alterados)

                local_vaga['vagas'] -= 1
                if local_vaga['vagas'] <= 0:
                    vagas_por_categoria[cat_desejada].pop(0)
                WorldLogger.info(f"✅ CONTRATADO: {candidato['nome']} começou a trabalhar em {local_vaga['id']} como {p_nome}!", npc=candidato['id'])
                contratacoes += 1
                sucesso = True

            # Se não conseguiu emprego novo e o antigo era inválido, limpa o campo
            if not sucesso:
                self._efetivar_demissao(candidato, ctx.alterados)
                WorldLogger.info(f"🕵️  DESEMPREGADO: {candidato['nome']} agora está buscando oportunidades.", npc=candidato['id'])

        return contratacoes

    def _efetivar_contratacao(self, candidato: dict, local_id: str, profissao_id: str,
                               profissao_nome: str, alterados: list) -> None:
        """P01: grava a coluna fria no banco — `salvar_completo` (em lote, X02) se o
        candidato veio do mundo vivo, o `UPDATE` estreito de `contratar` se veio só
        do banco (populador, sem `EstadoDoMundo`) — e aplica no OBJETO VIVO, se
        existir: o NPC descobre que foi contratado na hora, sem depender de
        `recarregar_habitantes()` (P02)."""
        npc_vivo = candidato["npc_vivo"]
        if npc_vivo is not None:
            npc_vivo.local_trabalho_id = local_id
            npc_vivo.profissao_id = profissao_id
            npc_vivo.profissao = profissao_nome
            alterados.append(npc_vivo)
            self._mundo.acordar(npc_vivo)  # A03: mudou o que ele quer fazer, reavalia agora
        else:
            self.db.npcs.contratar(candidato["id"], local_id, profissao_id, profissao_nome)

    def _efetivar_demissao(self, candidato: dict, alterados: list) -> None:
        """Espelho de `_efetivar_contratacao` pro caminho "emprego antigo inválido,
        nenhum novo achado"."""
        npc_vivo = candidato["npc_vivo"]
        if npc_vivo is not None:
            npc_vivo.local_trabalho_id = None
            npc_vivo.profissao_id = ProfissaoID.OCIOSO.value
            npc_vivo.profissao = "Desempregado"
            alterados.append(npc_vivo)
            self._mundo.acordar(npc_vivo)
        else:
            self.db.npcs.demitir(candidato["id"], ProfissaoID.OCIOSO.value)
