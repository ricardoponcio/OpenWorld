"""
MODULE: populador.py
FUNÇÃO: Povoamento Avançado do Mundo com Inteligência Artificial.

DESCRIÇÃO:
    Orquestra o povoamento inicial: importa cartografia, elege a cidade de spawn,
    importa a geometria de cada cidade como `Local`, gera NPCs (IA + fallback
    procedural), forma casais e laços sociais, e inicializa o mercado de trabalho.

    Cada fase é um método; o estado compartilhado entre fases é atributo da instância,
    não variável local de uma função de 227 linhas (R-D03 do PLANO_REFATORACAO.md).

    ⚠️ Limitação conhecida (Anexo 3, bug #5): `nomes_gerados` (passado à IA pra evitar
    nomes repetidos) só é atualizado DEPOIS que o `ThreadPoolExecutor` termina o lote
    inteiro — durante a geração paralela, cada chamada de IA vê a lista ainda vazia
    (ou incompleta). A deduplicação de nomes não é confiável dentro do mesmo lote de
    geração. Corrigir de verdade exigiria serializar as chamadas de IA (perde o
    paralelismo) ou sincronização mais cara pra um ganho pequeno (nomes duplicados
    ocasionais não quebram nada, só soam repetitivos) — não vale o custo agora.
"""
import os
import json
import random
import concurrent.futures
from datetime import timedelta

from engine.database import DatabaseManager
from engine.models import (
    Local, NPC, EstadoCivil, CategoriaLocal, ProfissaoID, VinculoSocial, Genero, EstagioVida,
    MetaChave, Lote, LoteEstado,
)
from engine.tempo import RelogioMundo
from engine.mechanics.market import JobMarket
from engine.ai import AIGeneratorClient, AIFallbacks
from engine.logger import WorldLogger
from engine.geo import GeoUtils
from builder.importador_cartografia import CartographyImporter
from config import get_config, cfg_get

MANIFEST_PATH = "database/world_manifest.json"
CIDADES_GEOJSON_DIR = "database/cidades"


def _centroide_mundo(geom):
    """[lng, lat] = [x_mundo, -y_mundo] (Seção 2.3 do docs/PLANO_CIDADE_VIVA.md) — desfaz
    de volta pra pixel de mundo. Um Polygon (edifício, lote — E4/Q01) usa o centroide do
    anel externo; um Point (GeoJSON antigo em disco, ou o paliativo abaixo, que ainda
    produz ponto) usa a coordenada direto. Extraído pra não copiar a mesma conta pra
    edifício e pra lote (T02)."""
    if geom["type"] == "Point":
        lng, lat = geom["coordinates"]
    else:
        anel_externo = geom["coordinates"][0]
        pontos = anel_externo[:-1] if len(anel_externo) > 1 and anel_externo[0] == anel_externo[-1] else anel_externo
        lng = sum(p[0] for p in pontos) / len(pontos)
        lat = sum(p[1] for p in pontos) / len(pontos)
    return lng, -lat


def _importar_locais_da_geometria(db, cidade):
    """
    Fase 4.5 (P2.2): importa os edifícios do GeoJSON gerado por
    `cartographer/cities/generate_city_geometry.py` como `Local` — substitui de vez o
    paliativo da Fase 2.1/2.2 (sortear ponto aleatório num raio ao redor do
    pixel-âncora) pela geometria real da cidade (ruas, quarteirões, lotes, muralha).

    T02 (docs/PLANO_CIDADE_VIVA.md): na mesma passada, importa também os LOTES (camada
    "lote", Q01) como `Lote` — o terreno que ainda não tem edifício em cima entra como
    'livre', pronto pra Bloco O reservar. `estado` inicial é 'ocupado' quando existe um
    edifício com o MESMO id (armadilha 3: o edifício É o lote onde está, mesmo id) —
    um `set` de ids, não busca geométrica.

    Retorna a lista de ids de `Local` com categoria "residencia" (housing de NPC), ou
    `None` se a cidade não tem geometria gerada — o chamador decide o fallback.
    """
    slug = cidade['nome'].lower().replace(" ", "_")
    caminho = os.path.join(CIDADES_GEOJSON_DIR, f"{slug}.geojson")
    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    locais = []
    edificio_ids = set()
    casas_ids = []
    lotes_crus = []  # (props, x_mundo, y_mundo) — vira Lote só depois de fechar edificio_ids

    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        camada = props.get("camada")
        if camada == "edificio":
            x_mundo, y_mundo = _centroide_mundo(feat["geometry"])
            locais.append(Local(
                id=props["id"],
                nome=props["nome"],
                tipo=props.get("tipo_local", "Edifício"),
                cidade_id=cidade['db_id'],
                categoria=props.get("categoria", "generic"),
                descricao=f"{props.get('tipo_local', 'Edifício')} em {cidade['nome']} ({props.get('bairro', '')}).",
                coordenadas=[round(x_mundo, 6), round(y_mundo, 6)],
                capacidade=props.get("capacidade", 5),
                salario_base=props.get("salario_base", 0),
                tipo_local=props.get("tipo_local", ""),
                bairro=props.get("bairro", ""),
                dono_npc_id=props.get("dono_npc_id", ""),
            ))
            edificio_ids.add(props["id"])
            if props.get("categoria") == CategoriaLocal.RESIDENCIA.value:
                casas_ids.append(props["id"])
        elif camada == "lote":
            lotes_crus.append((props, *_centroide_mundo(feat["geometry"])))

    db.locais.salvar_em_lote(locais)

    lotes = []
    for props, x_mundo, y_mundo in lotes_crus:
        lote_id = props["id"]
        ocupado = lote_id in edificio_ids
        # T05: estado_inicial é o mesmo valor de estado NESTE instante — congelado, é a
        # base de comparação do "o que mudou desde que o GeoJSON foi desenhado".
        estado = LoteEstado.OCUPADO.value if ocupado else LoteEstado.LIVRE.value
        lotes.append(Lote(
            id=lote_id, cidade_id=cidade['db_id'], quarteirao_id=props.get("quarteirao_id", ""),
            bairro=props.get("bairro", ""), banda=props.get("banda", 0),
            classe_frente=props.get("classe_frente", ""), area_m2=props.get("area_m2", 0.0),
            x=round(x_mundo, 6), y=round(y_mundo, 6),
            estado=estado, estado_inicial=estado,
            local_id=lote_id if ocupado else "",
        ))
    db.lotes.salvar_em_lote(lotes)

    print(f"  🏙️  {cidade['nome']} -> {len(locais)} edifício(s) importados da geometria "
          f"({len(casas_ids)} residências), {len(lotes)} lote(s)")
    return casas_ids


def _importar_locais_paliativo(db, cidade, raio_locais, nivel_mar, cfg_urbano):
    """Fallback só pra cidade sem geometria gerada (reset parcial, ou geração de
    cidade falhou) — o mesmo espalhamento em raio da Fase 2.1/2.2, sem fingir ser
    geometria real. Loga um aviso; não deveria disparar no fluxo normal do reset."""
    cx, cy = cidade.get("x_global", 0), cidade.get("y_global", 0)
    locais_base = [
        {"nome": f"Taverna de {cidade['nome']}", "categoria": CategoriaLocal.TAVERNA.value},
        {"nome": "Praça Central", "categoria": CategoriaLocal.PUBLICO.value},
        {"nome": "Mercado", "categoria": CategoriaLocal.MERCADO.value},
    ]
    for i, l_data in enumerate(locais_base):
        x_local, y_local = GeoUtils.sortear_ponto_em_terra(cx, cy, raio_locais, nivel_mar)
        db.locais.salvar(Local(
            id=f"loc_{cidade['db_id']}_pal_{i:02d}", nome=l_data['nome'], tipo="Social",
            cidade_id=cidade['db_id'], categoria=l_data['categoria'],
            descricao=f"Estabelecimento provisório de {cidade['nome']} (sem geometria gerada).",
            coordenadas=[x_local, y_local]
        ))

    num_casas = cfg_get(cfg_urbano, "casas_paliativas")
    casas_ids = []
    for i in range(num_casas):
        c_id = f"casa_{cidade['db_id']}_pal_{i:02d}"
        casas_ids.append(c_id)
        x_local, y_local = GeoUtils.sortear_ponto_em_terra(cx, cy, raio_locais, nivel_mar)
        db.locais.salvar(Local(
            id=c_id, nome=f"Residência {i:02d}", tipo="Casa", cidade_id=cidade['db_id'],
            categoria=CategoriaLocal.RESIDENCIA.value, descricao="Moradia provisória.",
            coordenadas=[x_local, y_local]
        ))
    return casas_ids


class PopuladorDeMundo:
    """Orquestra o povoamento inicial. Cada fase é um método; o estado compartilhado
    entre fases é atributo da instância, não variável local de uma função de 227
    linhas (R-D03)."""

    def __init__(self, db: DatabaseManager, tema: str, usar_ia: bool, ia_max_thread: int):
        self.db = db
        self.tema = tema
        self.usar_ia = usar_ia
        self.ia_max_thread = ia_max_thread

        config = get_config()
        self.cfg_pop = cfg_get(config, "geracao_populacao")
        self.cfg_urbano = cfg_get(config, "geracao_urbana")
        self.nivel_mar = cfg_get(config, "cartografia", "nivel_mar")
        self.raio_locais = cfg_get(self.cfg_urbano, "locais_raio_px")
        self.limiar_morte = cfg_get(config, "biologia_e_sociedade", "crescimento_dias_idoso_para_morte")

        self.cidades_salvas = []
        self.cidades_ativas = []
        self.cidade_foco = None
        self.casas_por_cidade = {}
        self.locais_trabalho_por_cidade = {}
        self.npcs_gerados = []

    def executar(self, num_npcs: int = None) -> None:
        """`num_npcs`, quando informado, SUBSTITUI `npcs_por_cidade` do config como a
        base per-cidade (ainda escalada por `npcs_por_cidade_por_tamanho`) — é o que
        permite `--npcs 5` num reset rápido de teste sem editar o config.json."""
        print(f"🏗️  Iniciando Povoamento Dinâmico de Mundo (Tema: {self.tema})")
        base_npcs = num_npcs if num_npcs is not None else cfg_get(self.cfg_pop, "npcs_por_cidade")

        self._importar_cartografia()
        if not self.cidades_salvas:
            return

        self._eleger_cidades_ativas()
        self._importar_geometria_das_cidades()
        self._coletar_locais_de_trabalho()

        dnas = self._gerar_dnas_em_paralelo(base_npcs)
        self._criar_npcs(dnas)
        self._formar_casais_iniciais(base_npcs)
        self._estabelecer_lacos_sociais()
        self._inicializar_mercado_de_trabalho()

        print("\n✨ POVOAMENTO COM IA CONCLUÍDO COM SUCESSO!")
        print(f"🏰 {len(self.cidades_ativas)} cidade(s) ativa(s), {len(self.npcs_gerados)} "
              f"habitante(s) no total prontos para simular.")

    # ------------------------------------------------------------------
    def _importar_cartografia(self) -> None:
        self.cidades_salvas = CartographyImporter.import_manifest(self.db, MANIFEST_PATH)

    def _eleger_cidades_ativas(self) -> None:
        """P07 (docs/PLANO_CIDADE_VIVA.md, D1): população em TODAS as cidades ativas,
        não só a de spawn — `cidades_ativas` no config aceita 'todas' (literal, não
        `None`, pra intenção ficar escrita) ou uma lista de nomes.

        A PRIMEIRA da lista continua sendo a cidade em FOCO do dashboard/Modo Mestre
        (`MetaChave.CIDADE_SIMULADA`) — não é a mesma coisa que "todas com simulação
        ativa" (`MetaChave.CIDADES_ATIVAS`, que agora leva TODOS os ids, não só um)."""
        filtro = cfg_get(self.cfg_pop, "cidades_ativas")
        if filtro == "todas":
            self.cidades_ativas = list(self.cidades_salvas)
        else:
            nomes = set(filtro)
            self.cidades_ativas = [c for c in self.cidades_salvas if c['nome'] in nomes]
            if not self.cidades_ativas:
                WorldLogger.warning(
                    f"[POPULATE] Nenhuma cidade do manifesto bate com cidades_ativas={filtro!r} "
                    f"— usando todas as {len(self.cidades_salvas)} cidades.")
                self.cidades_ativas = list(self.cidades_salvas)

        self.cidade_foco = self.cidades_ativas[0]
        print(f"🏰 Cidades ativas ({len(self.cidades_ativas)}): "
              f"{', '.join(c['nome'] for c in self.cidades_ativas)}")
        print(f"🔎 Cidade em foco (dashboard/Modo Mestre): {self.cidade_foco['nome']} "
              f"(ID: {self.cidade_foco['db_id']})")
        self.db.meta.salvar(MetaChave.CIDADE_SIMULADA, str(self.cidade_foco['db_id']))
        self.db.meta.salvar(MetaChave.CIDADES_ATIVAS,
                            json.dumps([c['db_id'] for c in self.cidades_ativas]))

    def _importar_geometria_das_cidades(self) -> None:
        """Fase 4.5 (P2.2): importa os edifícios da geometria REAL de cada cidade do
        MANIFESTO (não só as ativas — o mapa mostra todas) como `Local`. Cidade sem
        geometria gerada cai no paliativo de espalhamento em raio."""
        print(f"🏙️  Importando geometria de {len(self.cidades_salvas)} cidade(s) do manifesto...")
        for cid in self.cidades_salvas:
            resultado = _importar_locais_da_geometria(self.db, cid)
            if resultado is None:
                WorldLogger.warning(
                    f"[POPULATE] '{cid['nome']}' sem geometria gerada em {CIDADES_GEOJSON_DIR} "
                    f"— rode cartographer/cities/generate_city_geometry.py antes do reset completo. "
                    f"Usando paliativo temporário pra não travar o povoamento."
                )
                resultado = _importar_locais_paliativo(self.db, cid, self.raio_locais, self.nivel_mar, self.cfg_urbano)
            self.casas_por_cidade[cid['db_id']] = resultado
            if not resultado:
                WorldLogger.warning(f"[POPULATE] '{cid['nome']}' não tem nenhuma residência — NPCs dela ficarão sem casa.")

    def _coletar_locais_de_trabalho(self) -> None:
        """Candidatos a "local de trabalho" pra dar contexto de flavor à IA de DNA do
        NPC, por cidade ATIVA. Exclui categorias sociais (o NPC não "trabalha" na
        praça)."""
        locais_por_id = self.db.locais.carregar_por_id()
        for cid in self.cidades_ativas:
            candidatos = [
                l for l in locais_por_id.values()
                if l.cidade_id == cid['db_id']
                and l.categoria not in (CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value, CategoriaLocal.RESIDENCIA.value)
            ]
            if not candidatos:
                candidatos = [Local(id="_fallback", nome="Praça", tipo="Social", categoria=CategoriaLocal.PUBLICO.value)]
            self.locais_trabalho_por_cidade[cid['db_id']] = candidatos

    def _populacao_da_cidade(self, cidade: dict, base_npcs: int) -> int:
        """P07/D1: multiplicador por tamanho (a capital parece capital) sobre a base
        configurada (`npcs_por_cidade`, ou o override de `--npcs`)."""
        multiplicadores = cfg_get(self.cfg_pop, "npcs_por_cidade_por_tamanho")
        fator = multiplicadores.get(cidade.get('tamanho', 'medio'), 1.0)
        return max(1, round(base_npcs * fator))

    def _gerar_dnas_em_paralelo(self, base_npcs: int) -> list:
        """P07: itera TODAS as cidades ativas, cada uma com sua própria população
        (`_populacao_da_cidade`). Custo de IA: só a cidade em FOCO recebe geração de
        DNA por IA de verdade — as outras usam fallback procedural direto, sem
        nenhuma chamada de IA (de 20 pra 750 NPCs seriam 750 chamadas; sem isto o
        custo aparece na fatura, não numa decisão consciente)."""
        npc_params = []
        for cid in self.cidades_ativas:
            cidade_id = cid['db_id']
            n = self._populacao_da_cidade(cid, base_npcs)
            casas = self.casas_por_cidade.get(cidade_id) or []
            locais_trabalho = self.locais_trabalho_por_cidade.get(cidade_id) or []
            for i in range(n):
                genero_alvo = Genero.MASCULINO.value if i % 2 == 0 else Genero.FEMININO.value
                casa = random.choice(casas) if casas else ""
                loc_trabalho = random.choice(locais_trabalho) if locais_trabalho else \
                    Local(id="_fallback", nome="Praça", tipo="Social", categoria=CategoriaLocal.PUBLICO.value)
                npc_params.append((cidade_id, i, genero_alvo, loc_trabalho, casa))

        print(f"👥 Povoando {len(self.cidades_ativas)} cidade(s) com {len(npc_params)} "
              f"habitante(s) no total (IA: Workers {self.ia_max_thread}, só na cidade em foco)...")
        nomes_gerados = []
        foco_id = self.cidade_foco['db_id']

        def gerar_um_npc(params):
            cidade_id, idx, genero, loc, casa = params
            dna = None
            if self.usar_ia and cidade_id == foco_id:
                try:
                    dna = AIGeneratorClient.gerar_dna_npc(self.tema, loc.nome, loc.tipo, genero, nomes_gerados)
                except Exception as e:
                    print(f"⚠️ Falha na geração IA para NPC {cidade_id}/{idx}: {e}. Ativando Fallback.")
            return (params, dna)

        if self.usar_ia and self.ia_max_thread > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.ia_max_thread) as executor:
                resultados = list(executor.map(gerar_um_npc, npc_params))
        else:
            resultados = [gerar_um_npc(p) for p in npc_params]

        return resultados

    def _criar_npcs(self, resultados: list) -> None:
        """P05: acumula e grava em UMA transação (executemany) em vez de um commit
        por NPC — com centenas de NPCs em várias cidades, isso deixou de ser barato."""
        novos = []
        for params, dna in resultados:
            cidade_id, idx, genero_alvo, loc_trabalho, casa = params

            if dna:
                nome = dna.get('nome', f"Habitante {idx}")
                profissao = dna.get('cargo', "Aldeão")
                genero = dna.get('genero', genero_alvo)
                # Fase 2.3: dna.txt já pedia raca/personalidade/background — antes eram
                # gerados pela IA e jogados fora aqui. Persistidos agora (uso na decisão
                # é Fase 8; por ora só melhora a narração do Modo Mestre).
                raca = dna.get('raca', '')
                personalidade = dna.get('personalidade', '')
                background = dna.get('background', '')
            else:
                # Fallback procedural de alta fidelidade
                raca, personalidade, background = '', '', ''
                prefixo = "Sir" if genero_alvo == Genero.MASCULINO.value else "Lady"
                nome = f"{prefixo} {random.randint(10, 99)} de {AIFallbacks.sortear_sobrenome()}"
                profissao = "Aldeão"
                genero = genero_alvo

            # Distribuir idades proporcionalmente (adultos reprodutores vs. idosos)
            if random.random() < cfg_get(self.cfg_pop, "proporcao_adultos"):
                idade_inicial_anos = random.randint(cfg_get(self.cfg_pop, "idade_adulto_min"), cfg_get(self.cfg_pop, "idade_adulto_max"))
                estagio_vida = EstagioVida.ADULTO.value
            else:
                idade_inicial_anos = random.randint(cfg_get(self.cfg_pop, "idade_idoso_min"), cfg_get(self.cfg_pop, "idade_idoso_max"))
                estagio_vida = EstagioVida.IDOSO.value

            idade_inicial_dias = int((idade_inicial_anos / RelogioMundo.ANOS_DE_VIDA_DE_REFERENCIA) * self.limiar_morte)
            dt_nasc = RelogioMundo.EPOCA - timedelta(days=idade_inicial_dias)

            npc = NPC(
                # P07/armadilha 3: id namespaced por cidade — f"npc_{idx:03d}" sozinho
                # colidiria entre cidades (cada uma reinicia idx em 0).
                id=f"npc_{cidade_id:02d}_{idx:03d}",
                nome=nome,
                profissao=profissao,
                profissao_id=ProfissaoID.OCIOSO.value,
                cidade_id=cidade_id,
                casa_id=casa,
                local_trabalho_id="",
                localizacao_atual_id=casa,
                dinheiro_total_pc=random.randint(cfg_get(self.cfg_pop, "dinheiro_inicial_min"), cfg_get(self.cfg_pop, "dinheiro_inicial_max")),
                genero=genero,
                data_nascimento=dt_nasc.isoformat(),
                estagio_vida=estagio_vida,
                raca=raca,
                personalidade=personalidade,
                background=background
            )
            novos.append(npc)
            print(f"  ✅ Gerado: {nome} ({genero}) | Cidade: {cidade_id} | Idade: {idade_inicial_anos} anos | Cargo IA: {profissao}")

        self.db.npcs.salvar_muitos(novos)
        self.npcs_gerados.extend(novos)

    def _npcs_por_cidade(self) -> dict:
        agrupado = {}
        for n in self.npcs_gerados:
            agrupado.setdefault(n.cidade_id, []).append(n)
        return agrupado

    def _formar_casais_iniciais(self, base_npcs: int) -> None:
        """P07: casais só entre habitantes da MESMA cidade — roda por cidade ativa, não
        sobre a população global (casamento entre cidades diferentes não faz sentido,
        mesmo raciocínio de P04)."""
        print("\n❤️  Estabelecendo casais iniciais casados e coabitantes nas cidades...")
        npcs_por_cidade = self._npcs_por_cidade()
        alterados = []

        for cid in self.cidades_ativas:
            cidade_id = cid['db_id']
            habitantes = npcs_por_cidade.get(cidade_id, [])
            adultos_m = [n for n in habitantes if n.genero == Genero.MASCULINO.value and n.estagio_vida == EstagioVida.ADULTO.value]
            adultos_f = [n for n in habitantes if n.genero == Genero.FEMININO.value and n.estagio_vida == EstagioVida.ADULTO.value]
            casas_cidade = self.casas_por_cidade.get(cidade_id) or [""]

            n_populacao = self._populacao_da_cidade(cid, base_npcs)
            num_casais = min(len(adultos_m), len(adultos_f),
                             n_populacao // cfg_get(self.cfg_pop, "casal_divisor_por_npc"))
            for idx in range(num_casais):
                m, f = adultos_m[idx], adultos_f[idx]

                casa_comum = m.casa_id or f.casa_id or casas_cidade[0]
                m.casa_id = f.casa_id = casa_comum
                m.localizacao_atual_id = f.localizacao_atual_id = casa_comum

                m.estado_civil = f.estado_civil = EstadoCivil.CASADO.value
                m.conjuge_id, f.conjuge_id = f.id, m.id

                sobrenome_m = m.nome.split()[-1] if len(m.nome.split()) > 1 else ""
                if sobrenome_m and sobrenome_m not in f.nome:
                    f.nome = f"{f.nome} {sobrenome_m}"

                af = random.randint(cfg_get(self.cfg_pop, "casal_afinidade_min"), cfg_get(self.cfg_pop, "casal_afinidade_max"))
                m.relacionamentos[f.id] = af
                f.relacionamentos[m.id] = af

                alterados.extend((m, f))
                self.db.npcs.salvar_relacionamento(m.id, f.id, af, VinculoSocial.CONJUGE.value)
                print(f"  ❤️  CASAL FORMADO: {m.nome} e {f.nome} morando na {casa_comum} (Afinidade: {af})!")

        self.db.npcs.salvar_muitos(alterados)

    def _estabelecer_lacos_sociais(self) -> None:
        """P07: laço social só entre habitantes da MESMA cidade — por cidade ativa,
        não O(N²) sobre a população global (que não faz sentido: um NPC não conhece
        alguém que nunca viu, do outro lado do mundo)."""
        print("\n💞 Estabelecendo laços sociais e amizades prévias na comunidade...")
        amigos_min, amigos_max = cfg_get(self.cfg_pop, "amigos_min"), cfg_get(self.cfg_pop, "amigos_max")
        amigo_af_min, amigo_af_max = cfg_get(self.cfg_pop, "amigo_afinidade_min"), cfg_get(self.cfg_pop, "amigo_afinidade_max")
        amigo_vinculo_limiar = cfg_get(self.cfg_pop, "amigo_vinculo_limiar")

        alterados_por_id = {}
        for habitantes in self._npcs_por_cidade().values():
            for npc_a in habitantes:
                candidatos = [n for n in habitantes if n.id != npc_a.id]
                if not candidatos:
                    continue
                qtd_amigos = random.randint(amigos_min, min(amigos_max, len(candidatos)))
                alvos = random.sample(candidatos, k=qtd_amigos)

                for npc_b in alvos:
                    if npc_b.id in npc_a.relacionamentos:
                        continue

                    af = random.randint(amigo_af_min, amigo_af_max)
                    npc_a.relacionamentos[npc_b.id] = af
                    npc_b.relacionamentos[npc_a.id] = af
                    alterados_por_id[npc_a.id] = npc_a
                    alterados_por_id[npc_b.id] = npc_b

                    vinculo = (VinculoSocial.AMIGO if af >= amigo_vinculo_limiar else VinculoSocial.CONHECIDO).value
                    self.db.npcs.salvar_relacionamento(npc_a.id, npc_b.id, af, vinculo)

        self.db.npcs.salvar_muitos(list(alterados_por_id.values()))

    def _inicializar_mercado_de_trabalho(self) -> None:
        print("\n💼 Inicializando mercado de trabalho e preenchendo vagas...")
        market = JobMarket(self.db, get_config())
        market.bootstrap_market()
        market.processar_contratacoes()
