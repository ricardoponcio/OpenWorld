"""
SCRIPT: populate.py
FUNÇÃO: Povoamento Avançado com Inteligência Artificial.
DESCRIÇÃO: Setup inicial de cidades, locais, casas e geração assíncrona de NPCs
           com identidades geradas por IA (via Ollama) ou fallback procedural de alta fidelidade.
USO: python3 builder/populate.py --npcs 20 --ia-max-thread 4 --tema "Fantasia Medieval"
"""
import os
import sys
import json
import random
import argparse
import concurrent.futures
from datetime import datetime, timedelta

# Ajustar path para importar a engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.database import DatabaseManager
from engine.models import Local, NPC, EstadoCivil, Acao, CategoriaLocal, ProfissaoID
from engine.mechanics.market import JobMarket
from builder.generator import AIWorldGenerator
from engine.logger import WorldLogger
from engine.utils import CartographyImporter, GeoUtils
from config import get_config, cfg_get

MANIFEST_PATH = "database/world_manifest.json"
DB_PATH = "database/openworld.db"
CIDADES_GEOJSON_DIR = "database/cidades"


def _importar_locais_da_geometria(db, cidade):
    """
    Fase 4.5 (P2.2): importa os edifícios do GeoJSON gerado por
    `cartographer/cities/generate_city_geometry.py` como `Local` — substitui de vez o
    paliativo da Fase 2.1/2.2 (sortear ponto aleatório num raio ao redor do
    pixel-âncora) pela geometria real da cidade (ruas, quarteirões, lotes, muralha).

    Retorna a lista de ids de `Local` com categoria "residencia" (housing de NPC), ou
    `None` se a cidade não tem geometria gerada — o chamador decide o fallback.
    """
    slug = cidade['nome'].lower().replace(" ", "_")
    caminho = os.path.join(CIDADES_GEOJSON_DIR, f"{slug}.geojson")
    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    casas_ids = []
    total = 0
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        if props.get("camada") != "edificio":
            continue

        # E4 (ESPEC_TECIDO_URBANO.md Seção 6): `edificio` virou Polygon (footprint dentro
        # do lote, Seção 5.3) — o Local usa o centroide do anel externo. Mantém
        # compatibilidade com Point (GeoJSON antigo em disco, ou o paliativo abaixo, que
        # continua produzindo ponto) — desfaz [lng,lat] = [x_mundo, -y_mundo] (Seção 2.3)
        # de volta pra pixel de mundo, ponto a ponto se for polígono.
        geom = feat["geometry"]
        if geom["type"] == "Point":
            lng, lat = geom["coordinates"]
        else:
            anel_externo = geom["coordinates"][0]
            pontos = anel_externo[:-1] if len(anel_externo) > 1 and anel_externo[0] == anel_externo[-1] else anel_externo
            lng = sum(p[0] for p in pontos) / len(pontos)
            lat = sum(p[1] for p in pontos) / len(pontos)
        x_mundo, y_mundo = lng, -lat

        loc = Local(
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
        )
        db.salvar_local(loc)
        total += 1
        if props.get("categoria") == CategoriaLocal.RESIDENCIA.value:
            casas_ids.append(props["id"])

    print(f"  🏙️  {cidade['nome']} -> {total} edifício(s) importados da geometria ({len(casas_ids)} residências)")
    return casas_ids


def _importar_locais_paliativo(db, cidade, raio_locais, nivel_mar):
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
        db.salvar_local(Local(
            id=f"loc_{cidade['db_id']}_pal_{i:02d}", nome=l_data['nome'], tipo="Social",
            cidade_id=cidade['db_id'], categoria=l_data['categoria'],
            descricao=f"Estabelecimento provisório de {cidade['nome']} (sem geometria gerada).",
            coordenadas=[x_local, y_local]
        ))

    num_casas = 5
    casas_ids = []
    for i in range(num_casas):
        c_id = f"casa_{cidade['db_id']}_pal_{i:02d}"
        casas_ids.append(c_id)
        x_local, y_local = GeoUtils.sortear_ponto_em_terra(cx, cy, raio_locais, nivel_mar)
        db.salvar_local(Local(
            id=c_id, nome=f"Residência {i:02d}", tipo="Casa", cidade_id=cidade['db_id'],
            categoria=CategoriaLocal.RESIDENCIA.value, descricao="Moradia provisória.",
            coordenadas=[x_local, y_local]
        ))
    return casas_ids

def populate_world(num_npcs=20, tema="Fantasia Medieval", usar_ia=True, ia_max_thread=4):
    print(f"🏗️  Iniciando Povoamento Dinâmico de Mundo (Tema: {tema})")
    
    # 1. Garante Banco Inicializado
    db = DatabaseManager(DB_PATH)

    cfg_pop = cfg_get(get_config(), "geracao_populacao")
    cfg_urbano = cfg_get(get_config(), "geracao_urbana")
    nivel_mar = cfg_get(get_config(), "cartografia", "nivel_mar")
    raio_locais = cfg_get(cfg_urbano, "locais_raio_px")

    # 2. Lê e Importa Cartografia
    cidades_salvas = CartographyImporter.import_manifest(db, MANIFEST_PATH)
    if not cidades_salvas:
        return

    # 4. Elege a Cidade Principal (Spawn Point) — única com NPCs simulados por
    # enquanto (a simulação de agentes continua single-city até a Fase 9).
    cidade_spawn = cidades_salvas[0]
    print(f"🏰 Cidade Principal Selecionada: {cidade_spawn['nome']} (ID: {cidade_spawn['db_id']})")
    db.salvar_meta("cidade_simulada", str(cidade_spawn['db_id']))
    # Fase 2.2 (P1.5): registra quais cidades têm simulação ativa — hoje só a spawn,
    # mas a Fase 9 pode ativar mais de uma sem precisar inventar essa chave do zero.
    db.salvar_meta("cidades_ativas", json.dumps([cidade_spawn['db_id']]))

    cx_spawn, cy_spawn = cidade_spawn.get("x_global", 0), cidade_spawn.get("y_global", 0)

    # 5/6/6.1 Fase 4.5 (P2.2): importa os edifícios da geometria REAL de cada cidade
    # (gerada por cartographer/cities/generate_city_geometry.py — ruas, quarteirões,
    # lotes, muralha) como `Local`. Substitui de vez o paliativo da Fase 2.1/2.2
    # (espalhar ponto aleatório num raio ao redor do pixel-âncora) — cada edifício
    # agora tem posição, bairro e categoria de verdade, não um chute uniforme.
    print(f"🏙️  Importando geometria de {len(cidades_salvas)} cidade(s) do manifesto...")
    casas_ids = []
    for cid in cidades_salvas:
        resultado = _importar_locais_da_geometria(db, cid)
        if resultado is None:
            WorldLogger.warning(
                f"[POPULATE] '{cid['nome']}' sem geometria gerada em {CIDADES_GEOJSON_DIR} "
                f"— rode cartographer/cities/generate_city_geometry.py antes do reset completo. "
                f"Usando paliativo temporário pra não travar o povoamento."
            )
            resultado = _importar_locais_paliativo(db, cid, raio_locais, nivel_mar)
        if cid is cidade_spawn:
            casas_ids = resultado

    if not casas_ids:
        WorldLogger.warning(f"[POPULATE] '{cidade_spawn['nome']}' não tem nenhuma residência — NPCs ficarão sem casa.")

    # Candidatos a "local de trabalho" pra dar contexto de flavor à IA de DNA do NPC
    # (nome/tipo do prédio real, importado da geometria — não mais uma lista fixa de 6
    # locais hardcoded). Exclui categorias sociais (o NPC não "trabalha" na praça).
    todos_locais_spawn = [
        l for l in db.carregar_locais().values()
        if l.cidade_id == cidade_spawn['db_id']
        and l.categoria not in (CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value, CategoriaLocal.RESIDENCIA.value)
    ]
    if not todos_locais_spawn:
        todos_locais_spawn = [Local(id="_fallback", nome="Praça", tipo="Social", categoria=CategoriaLocal.PUBLICO.value)]

    # 7. Geração de NPCs com IA (Thread Pool paralela)
    print(f"👥 Povoando cidade com {num_npcs} habitantes usando IA (Workers: {ia_max_thread})...")
    nomes_gerados = []
    npc_params = []
    
    # Preparar parâmetros para cada thread
    for i in range(num_npcs):
        genero_alvo = 'M' if i % 2 == 0 else 'F'
        casa = random.choice(casas_ids) if casas_ids else ""
        # Seleciona local de trabalho base (apenas não sociais para inicialização) —
        # objeto `Local` real importado da geometria, acessado por atributo (não mais
        # um dict da lista fixa antiga).
        loc_trabalho = random.choice(todos_locais_spawn)
        npc_params.append((i, genero_alvo, loc_trabalho, casa))

    def generate_single_npc(params):
        idx, genero, loc, casa = params
        dna = None
        if usar_ia:
            try:
                dna = AIWorldGenerator.generate_npc_dna(tema, loc.nome, loc.tipo, genero, nomes_gerados)
            except Exception as e:
                print(f"⚠️ Falha na geração IA para NPC {idx}: {e}. Ativando Fallback.")
        return (params, dna)

    # Executar thread pool para chamadas rápidas
    resultados = []
    if usar_ia and ia_max_thread > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=ia_max_thread) as executor:
            resultados = list(executor.map(generate_single_npc, npc_params))
    else:
        for p in npc_params:
            resultados.append(generate_single_npc(p))

    # Carregar limites biológicos do config único (mesmo resolver da engine/dashboard —
    # antes este arquivo lia config.json por conta própria com seu próprio default (120),
    # divergente do default usado em web/dashboard.py (12), ver docs/AUDITORIA_HARDCODE.md)
    limiar_morte = cfg_get(get_config(), "biologia_e_sociedade", "crescimento_dias_idoso_para_morte")

    npcs_gerados = []
    for params, dna in resultados:
        idx, genero_alvo, loc_trabalho, casa = params
        
        if dna:
            nome = dna.get('nome', f"Habitante {idx}")
            profissao = dna.get('cargo', "Aldeão")
            genero = dna.get('genero', genero_alvo)
            # Fase 2.3: dna.txt já pedia raca/personalidade/background — antes eram
            # gerados pela IA e jogados fora aqui. Persistidos agora (uso na decisão é
            # Fase 8; por ora só melhora a narração do Modo Mestre).
            raca = dna.get('raca', '')
            personalidade = dna.get('personalidade', '')
            background = dna.get('background', '')
        else:
            # Fallback procedural de alta fidelidade
            raca, personalidade, background = '', '', ''
            prefixo = "Sir" if genero_alvo == 'M' else "Lady"
            sobrenomes = ["Blackwood", "Thorne", "Stormwind", "Ironfist", "Greycastle", "Oakheart"]
            nome = f"{prefixo} {random.randint(10, 99)} de {random.choice(sobrenomes)}"
            profissao = "Aldeão"
            genero = genero_alvo

        nomes_gerados.append(nome)

        # Distribuir idades proporcionalmente (adultos reprodutores vs. idosos)
        if random.random() < cfg_get(cfg_pop, "proporcao_adultos"):
            idade_inicial_anos = random.randint(cfg_get(cfg_pop, "idade_adulto_min"), cfg_get(cfg_pop, "idade_adulto_max"))
            estagio_vida = "adulto"
        else:
            idade_inicial_anos = random.randint(cfg_get(cfg_pop, "idade_idoso_min"), cfg_get(cfg_pop, "idade_idoso_max"))
            estagio_vida = "idoso"

        idade_inicial_dias = int((idade_inicial_anos / 80.0) * limiar_morte)
        data_inicio = datetime(1200, 1, 1, 0, 0)
        dt_nasc = data_inicio - timedelta(days=idade_inicial_dias)

        npc = NPC(
            id=f"npc_{idx:03d}",
            nome=nome,
            profissao=profissao,
            profissao_id=ProfissaoID.OCIOSO.value,
            cidade_id=cidade_spawn['db_id'],
            casa_id=casa,
            local_trabalho_id="",
            localizacao_atual_id=casa,
            dinheiro_total_pc=random.randint(cfg_get(cfg_pop, "dinheiro_inicial_min"), cfg_get(cfg_pop, "dinheiro_inicial_max")),
            genero=genero,
            data_nascimento=dt_nasc.isoformat(),
            estagio_vida=estagio_vida,
            raca=raca,
            personalidade=personalidade,
            background=background
        )
        db.salvar_npc(npc)
        npcs_gerados.append(npc)
        print(f"  ✅ Gerado: {nome} ({genero}) | Idade: {idade_inicial_anos} anos | Cargo IA: {profissao}")

    # 8. Formar Casais Iniciais Casados
    print("\n❤️  Estabelecendo casais iniciais casados e coabitantes na vila...")
    adultos_m = [n for n in npcs_gerados if n.genero == 'M' and n.estagio_vida == 'adulto']
    adultos_f = [n for n in npcs_gerados if n.genero == 'F' and n.estagio_vida == 'adulto']
    
    num_casais = min(len(adultos_m), len(adultos_f), num_npcs // cfg_get(cfg_pop, "casal_divisor_por_npc"))
    for idx in range(num_casais):
        m = adultos_m[idx]
        f = adultos_f[idx]
        
        # Escolher uma casa em comum para eles morarem
        casa_comum = m.casa_id or f.casa_id or casas_ids[0]
        m.casa_id = casa_comum
        m.localizacao_atual_id = casa_comum
        f.casa_id = casa_comum
        f.localizacao_atual_id = casa_comum
        
        # Formalizar casamento
        m.estado_civil = EstadoCivil.CASADO.value
        m.conjuge_id = f.id
        f.estado_civil = EstadoCivil.CASADO.value
        f.conjuge_id = m.id
        
        # Ajustar sobrenomes para combinar
        sobrenome_m = m.nome.split()[-1] if len(m.nome.split()) > 1 else ""
        if sobrenome_m and sobrenome_m not in f.nome:
            f.nome = f"{f.nome} {sobrenome_m}"
            
        # Definir afinidade muito alta para concepção imediata
        af = random.randint(cfg_get(cfg_pop, "casal_afinidade_min"), cfg_get(cfg_pop, "casal_afinidade_max"))
        m.relacionamentos[f.id] = af
        f.relacionamentos[m.id] = af
        
        db.salvar_npc(m)
        db.salvar_npc(f)
        
        db.salvar_relacionamento(m.id, f.id, af, "Cônjuge")
        print(f"  ❤️  CASAL FORMADO: {m.nome} e {f.nome} morando na {casa_comum} (Afinidade: {af})!")

    # 9. Relacionamentos Sociais Iniciais
    print("\n💞 Estabelecendo laços sociais e amizades prévias na comunidade...")
    amigos_min, amigos_max = cfg_get(cfg_pop, "amigos_min"), cfg_get(cfg_pop, "amigos_max")
    amigo_af_min, amigo_af_max = cfg_get(cfg_pop, "amigo_afinidade_min"), cfg_get(cfg_pop, "amigo_afinidade_max")
    amigo_vinculo_limiar = cfg_get(cfg_pop, "amigo_vinculo_limiar")
    for npc_a in npcs_gerados:
        qtd_amigos = random.randint(amigos_min, min(amigos_max, len(npcs_gerados) - 1))
        alvos = random.sample([n for n in npcs_gerados if n.id != npc_a.id], k=qtd_amigos)

        for npc_b in alvos:
            if npc_b.id in npc_a.relacionamentos:
                continue

            af = random.randint(amigo_af_min, amigo_af_max)
            npc_a.relacionamentos[npc_b.id] = af
            npc_b.relacionamentos[npc_a.id] = af

            db.salvar_npc(npc_a)
            db.salvar_npc(npc_b)

            vinculo = "Amigo" if af >= amigo_vinculo_limiar else "Conhecido"
            db.salvar_relacionamento(npc_a.id, npc_b.id, af, vinculo)

    # 10. Bootstrap de Vagas e Contratação imediata
    print("\n💼 Inicializando mercado de trabalho e preenchendo vagas...")
    market = JobMarket()
    market.bootstrap_market()
    market.processar_contratacoes()

    print("\n✨ POVOAMENTO COM IA CONCLUÍDO COM SUCESSO!")
    print(f"🏰 Cidade '{cidade_spawn['nome']}' ativa com {len(npcs_gerados)} habitantes prontos para simular.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=20, help="Quantidade de NPCs para gerar")
    parser.add_argument("--tema", type=str, default="Fantasia Medieval", help="Tema criativo da simulação")
    parser.add_argument("--ia-max-thread", type=int, default=4, help="Threads simultâneas de IA via ThreadPool")
    parser.add_argument("--desativar-ia", action="store_true", help="Gera NPCs apenas via fallback procedural rápido")
    args = parser.parse_args()
    
    usar_ia = not args.desativar_ia
    populate_world(args.npcs, args.tema, usar_ia, args.ia_max_thread)
