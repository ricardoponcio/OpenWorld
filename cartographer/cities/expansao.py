"""
X02 (docs/PLANO_CIDADE_VIVA.md) — a geometria do arrabalde: função pura no cartógrafo.

`gerar_arrabalde` não abre banco, não escreve arquivo, não sabe o que é um NPC — só lê o
`GeoJSON` atual da cidade (dict já carregado) e o `SitioCidade` (terreno), e devolve
features novas + metadados de lote. Quem decide QUANDO chamar é
`engine/mechanics/urbanismo.py` (X01/X03); quem decide COMO fica a geometria é aqui
(armadilha 2: a camada de baixo nunca sabe de NPC, banco ou arquivo).
"""
import math
import random
import zlib

from config import cfg_get

from .escala import zoom_min_por_camada
from .geometria import lotes, quad
from .geometria.gerador import ARESTA_MINIMA_LOTE_M
from .modelos.base import distancia_faixa_dominio, gerar_fileiras_de_quadras

# Penalidades de pontuação de direção — internos do algoritmo, não config (mesmo
# precedente de PROFUNDIDADE_CORTE_MAXIMA em geometria/lotes.py e
# FRACAO_VAO_MAXIMA_SEGURA em modelos/radial.py: número de calibração de geometria, não
# de balanceamento de simulação — ARQUITETURA.md P3 é sobre o segundo).
PESO_AGUA = 5.0
PESO_SETOR_USADO = 2.0
N_AMOSTRAS_DECLIVIDADE = 5


def _centroide(poligono):
    xs = [p[0] for p in poligono]
    ys = [p[1] for p in poligono]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _quarteirao_id_str(quadra_id):
    return "_".join(str(p) for p in quadra_id)


def _ler_portoes_locais(geojson_atual, sitio):
    """Posição de cada portão em metros locais (centro da cidade = origem — a mesma
    convenção de todo `ModeloCidade`), na ordem em que aparecem no arquivo."""
    portoes = []
    for feat in geojson_atual["features"]:
        props = feat["properties"]
        if props.get("camada") != "portao":
            continue
        lng, lat = feat["geometry"]["coordinates"]
        x_m = (lng - sitio.x_mundo) * sitio.metros_por_px
        y_m = (-lat - sitio.y_mundo) * sitio.metros_por_px
        portoes.append((x_m, y_m))
    return portoes


def _quarteiroes_existentes_locais(geojson_atual, sitio):
    """Polígonos (metros locais, anel aberto) de todo quarteirão já existente — pra
    `_filtrar_quadras_sem_conflito` rejeitar qualquer quadra nova que invada uma
    existente (perto de um portão num canto de cidade `grade`, a extensão reta a partir
    do portão pode tangenciar a última banda vizinha — validado empiricamente contra as
    15 cidades reais)."""
    polys = []
    for feat in geojson_atual["features"]:
        if feat["properties"].get("camada") != "quarteirao":
            continue
        anel = feat["geometry"]["coordinates"][0]
        pontos = []
        for lng, lat in anel[:-1]:
            x_m = (lng - sitio.x_mundo) * sitio.metros_por_px
            y_m = (-lat - sitio.y_mundo) * sitio.metros_por_px
            pontos.append((x_m, y_m))
        polys.append(pontos)
    return polys


def _ponto_dentro_do_poligono(ponto, poligono):
    x, y = ponto
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1 or 1e-12)
            if x < x_int:
                dentro = not dentro
    return dentro


def _quadra_conflita_com_existentes(vertices, existentes):
    n = len(vertices)
    for existente in existentes:
        m = len(existente)
        for i in range(n):
            a0, a1 = vertices[i], vertices[(i + 1) % n]
            for j in range(m):
                b0, b1 = existente[j], existente[(j + 1) % m]
                if quad.segmentos_cruzam(a0, a1, b0, b1):
                    return True
        if _ponto_dentro_do_poligono(vertices[0], existente):
            return True
    return False


def _banda_maxima(geojson_atual):
    bandas = [feat["properties"].get("banda", 0) for feat in geojson_atual["features"]
              if feat["properties"].get("camada") == "quarteirao"]
    return max(bandas, default=0)


def numero_do_proximo_arrabalde(geojson_atual):
    """Pública (não `_privada`): X03 (`engine/mechanics/urbanismo.py`) precisa do MESMO
    número antes de chamar `gerar_arrabalde`, pra derivar `seed_expansao = sitio.seed ^
    (0xA53F * numero_do_arrabalde)` de um jeito reproduzível — nunca `time.time()`."""
    numeros = {feat["properties"]["arrabalde"] for feat in geojson_atual["features"]
               if feat["properties"].get("arrabalde") is not None}
    return (max(numeros) + 1) if numeros else 0


def _arrabaldes_por_portao(geojson_atual):
    """`{indice_do_portao: quantidade de arrabaldes que já saíram por ele}` — X02 item 2:
    penaliza a direção já usada, pra cidade crescer em leque, não numa língua só."""
    por_portao = {}
    for feat in geojson_atual["features"]:
        props = feat["properties"]
        n = props.get("arrabalde")
        idx = props.get("arrabalde_portao_idx")
        if n is not None and idx is not None:
            por_portao.setdefault(idx, set()).add(n)
    return {idx: len(ns) for idx, ns in por_portao.items()}


def _escolher_direcao(portoes, sitio, config, comprimento_m, arrabaldes_por_portao):
    """Pontua cada portão candidato (X02 item 2) e devolve `(idx, dx, dy)` do melhor, ou
    `None` se todos forem desclassificados (declividade fora da janela, ou acima do
    limite de `cidade_geo_declividade_max`)."""
    declividade_max = cfg_get(config, "cidade_geo_declividade_max")
    melhor = None
    melhor_custo = float("inf")
    for idx, (px, py) in enumerate(portoes):
        d = math.hypot(px, py) or 1.0
        dx, dy = px / d, py / d

        amostras = []
        desclassificado = False
        for k in range(1, N_AMOSTRAS_DECLIVIDADE + 1):
            s = comprimento_m * k / N_AMOSTRAS_DECLIVIDADE
            declividade = sitio.declividade_em(px + dx * s, py + dy * s)
            if declividade is None:
                desclassificado = True
                break
            amostras.append(declividade)
        if desclassificado:
            continue
        declividade_media = sum(amostras) / len(amostras)
        if declividade_media > declividade_max:
            continue

        penalidade_agua = 0.0
        if math.isfinite(sitio.distancia_agua_m):
            dir_agua = (math.cos(sitio.direcao_agua_rad), math.sin(sitio.direcao_agua_rad))
            alinhamento = max(0.0, dx * dir_agua[0] + dy * dir_agua[1])
            penalidade_agua = alinhamento * PESO_AGUA

        penalidade_setor = arrabaldes_por_portao.get(idx, 0) * PESO_SETOR_USADO

        custo = declividade_media + penalidade_agua + penalidade_setor
        if custo < melhor_custo:
            melhor_custo = custo
            melhor = (idx, dx, dy)
    return melhor


def _gerar_features_e_lotes(eixo_pontos, banda_arrabalde, bairro, numero_arrabalde,
                             portao_idx, slug, config, seed_expansao, sitio, raio_m_cidade,
                             existentes_locais):
    """Uma passada completa de geração pra um `comprimento_m` já decidido — reexecutada
    do zero (mesma seed) a cada tentativa de `gerar_arrabalde` até caber `lotes_alvo`
    (X02 item 6), pra determinismo não depender de estado incremental."""
    zoom_min_camada = zoom_min_por_camada(config, raio_m_cidade)
    profundidade_m = cfg_get(config, "cidade_geo_vao_anel_alvo_m")
    faixa_lado_quadra = cfg_get(config, "cidade_geo_grade_lado_quadra_m_faixa")
    comprimento_celula_m = (faixa_lado_quadra[0] + faixa_lado_quadra[1]) / 2.0
    quadras, ruas_transversais = gerar_fileiras_de_quadras(
        eixo_pontos, profundidade_m, comprimento_celula_m,
        classe_frente="principal", classe_fundo="servico", classe_lateral="secundaria",
        banda=banda_arrabalde, bairro=bairro, id_prefix=("arr", numero_arrabalde))

    rng = random.Random(seed_expansao)
    lote_fator_cidade = rng.uniform(*cfg_get(config, "cidade_geo_lote_fator_cidade_faixa"))
    quadra_area_minima = cfg_get(config, "cidade_geo_quadra_area_minima_m2")

    def _dist_faixa(classe):
        return distancia_faixa_dominio(config, classe)

    features = []
    lotes_meta = []

    def _geojson_coord(ponto_m):
        """[lng, lat] = [x_mundo, -y_mundo] — mesma conversão de `GeradorCidade._geojson_coord`
        (Seção 2.3 do plano); duplicada aqui porque `expansao.py` não tem uma instância de
        `GeradorCidade` (é função pura, sem estado de emissão), só o `sitio`."""
        x_m, y_m = ponto_m
        x_mundo = sitio.x_mundo + x_m / sitio.metros_por_px
        y_mundo = sitio.y_mundo + y_m / sitio.metros_por_px
        return [round(x_mundo, 6), round(-y_mundo, 6)]

    def _add(geom_type, pontos_m, camada, props):
        if geom_type == "Point":
            coords = _geojson_coord(pontos_m)
        else:
            coords = [_geojson_coord(p) for p in pontos_m]
            if geom_type == "Polygon":
                coords = [coords + [coords[0]]]
        p = dict(props)
        p["camada"] = camada
        p["zoom_min"] = zoom_min_camada.get(camada, 8)
        features.append({"type": "Feature", "geometry": {"type": geom_type, "coordinates": coords},
                          "properties": p})

    eixo_props = {"tipo_via": "radial", "classe_via": "principal", "indice": 1000 + numero_arrabalde,
                  "arrabalde": numero_arrabalde, "arrabalde_portao_idx": portao_idx}
    _add("LineString", eixo_pontos, "rua", eixo_props)
    for k, rua in enumerate(ruas_transversais):
        _add("LineString", rua.pontos, "rua",
             {"tipo_via": rua.tipo_via, "classe_via": rua.classe_via, "indice": rua.indice,
              "arrabalde": numero_arrabalde, "arrabalde_portao_idx": portao_idx})

    for quadra in quadras:
        if _quadra_conflita_com_existentes(quadra.vertices, existentes_locais):
            continue  # invadiria a última banda existente perto do portão — descarta
        quarteirao_id_str = _quarteirao_id_str(quadra.id)
        # L03 (docs/PLANO_POPULACAO_E_ESCALA.md): mesmo raciocínio de
        # `GeradorCidade._gerar_quarteiroes_e_lotes` — cada quadra do arrabalde sorteia
        # com um RNG PRÓPRIO, derivado do id do quarteirão, em vez de um `rng`
        # sequencial compartilhado entre todas. `zlib.crc32`, nunca `hash()`.
        semente_quadra = seed_expansao ^ zlib.crc32(quarteirao_id_str.encode("utf-8"))
        rng_quadra = random.Random(semente_quadra)
        preparo = lotes.preparar_quadra(
            quadra.vertices, quadra.classes_aresta, quadra.banda, config,
            lote_fator_cidade, rng_quadra, quadra_area_minima, _dist_faixa)
        if preparo is None:
            continue
        quad_urbanizavel, lotes_info, patios, vielas, _ = preparo

        _add("Polygon", quad_urbanizavel, "quarteirao",
             {"bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str,
              "arrabalde": numero_arrabalde, "arrabalde_portao_idx": portao_idx})

        for patio in patios:
            _add("Polygon", patio, "patio",
                 {"bairro": quadra.bairro, "quarteirao_id": quarteirao_id_str,
                  "arrabalde": numero_arrabalde})

        for k, (p0, p1) in enumerate(vielas):
            _add("LineString", [p0, p1], "rua",
                 {"tipo_via": "servico", "classe_via": "servico", "indice": 2000 + k,
                  "arrabalde": numero_arrabalde})

        for info in lotes_info:
            poligono = info["poligono"]
            if not quad.e_quad_simples(poligono):
                continue
            if quad.aresta_minima(poligono) < ARESTA_MINIMA_LOTE_M:
                continue  # C02 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): mesmo guard de gerador.py
            lote_id = f"{slug}_{quarteirao_id_str}_l{info['indice_no_anel']:02d}"
            _add("Polygon", poligono, "lote", {
                "bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str,
                "id": lote_id, "classe_frente": info["classe_frente"], "area_m2": info["area_m2"],
                "aresta": info["aresta"], "estado": "livre", "arrabalde": numero_arrabalde,
            })
            cx_m, cy_m = _centroide(poligono)
            lotes_meta.append({
                "id": lote_id, "quarteirao_id": quarteirao_id_str, "bairro": quadra.bairro,
                "banda": quadra.banda, "classe_frente": info["classe_frente"],
                "area_m2": info["area_m2"],
                "x": sitio.x_mundo + cx_m / sitio.metros_por_px,
                "y": sitio.y_mundo + cy_m / sitio.metros_por_px,
            })

    return features, lotes_meta


def gerar_arrabalde(sitio, geojson_atual, lotes_alvo, seed_expansao, config,
                     comprimento_inicial_m, comprimento_max_m):
    """Gera as features de um arrabalde NOVO, fora da muralha, dimensionado para caber
    ao menos `lotes_alvo` lotes. Devolve `(features_novas, lotes_novos_meta)` — listas
    vazias se nenhuma direção de saída for viável (todas fora da janela de terreno, ou
    acima da declividade máxima).

    Função pura: não abre banco, não escreve arquivo, não sabe o que é um NPC. Quem
    decide QUANDO chamar é `engine/mechanics/urbanismo.py`; quem decide COMO fica a
    geometria é aqui (armadilha 2 do docs/PLANO_CIDADE_VIVA.md).
    """
    slug = sitio.nome.lower().replace(" ", "_")
    portoes = _ler_portoes_locais(geojson_atual, sitio)
    if not portoes:
        return [], []

    arrabaldes_por_portao = _arrabaldes_por_portao(geojson_atual)
    escolha = _escolher_direcao(portoes, sitio, config, comprimento_inicial_m, arrabaldes_por_portao)
    if escolha is None:
        return [], []
    portao_idx, dx, dy = escolha
    px, py = portoes[portao_idx]

    banda_arrabalde = _banda_maxima(geojson_atual) + 1
    numero_arrabalde = numero_do_proximo_arrabalde(geojson_atual)
    bairro = f"Arrabalde {numero_arrabalde}"

    raio_m_cidade = geojson_atual["properties"]["raio_m"]
    existentes_locais = _quarteiroes_existentes_locais(geojson_atual, sitio)
    comprimento_m = comprimento_inicial_m
    features, lotes_meta = [], []
    while True:
        eixo_pontos = [(px, py), (px + dx * comprimento_m, py + dy * comprimento_m)]
        features, lotes_meta = _gerar_features_e_lotes(
            eixo_pontos, banda_arrabalde, bairro, numero_arrabalde, portao_idx, slug,
            config, seed_expansao, sitio, raio_m_cidade, existentes_locais)
        if len(lotes_meta) >= lotes_alvo or comprimento_m >= comprimento_max_m:
            break
        comprimento_m = min(comprimento_m + comprimento_inicial_m, comprimento_max_m)

    return features, lotes_meta
