"""
Testes de cartografia — travam os invariantes F1-F4 (docs/PLANO_EVOLUCAO_V2.md, Seção 2.2).

Escopo deliberadamente pequeno (ver Seção 8 do plano): protege só os invariantes do
terreno como função de coordenada de mundo. Não cobre render, rotas, IA ou engine.
"""
import sys
import os

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

import numpy as np
from cartographer.math import NoiseGenerator
from cartographer.world.tile_cartographer import TileCartographer
from cartographer.config import CARTOGRAPHER_CONFIG


def test_ruido_independe_do_shape():
    """T1 — F1 (pureza): o mesmo ponto de mundo dá o mesmo valor, não importa em que
    array ele foi avaliado (sozinho ou dentro de uma grade maior)."""
    x, y = 137.0, 402.25
    sozinho = NoiseGenerator.generate_noise_field(
        np.array([[x]], np.float32), np.array([[y]], np.float32), scale=60, octaves=4, seed=7)
    gx, gy = np.meshgrid(np.linspace(x, x + 10, 64, endpoint=False, dtype=np.float32),
                          np.linspace(y, y + 10, 64, endpoint=False, dtype=np.float32))
    em_grade = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=4, seed=7)
    assert np.isclose(sozinho[0, 0], em_grade[0, 0], atol=1e-6)


def test_ruido_invariante_a_subdivisao():
    """T2 — F2 (invariância à subdivisão): avaliar uma janela de uma vez e avaliá-la em
    4 pedaços dá o mesmo resultado, bit a bit. É este teste que substitui todo blend de
    costura entre tiles."""
    gx, gy = np.meshgrid(np.linspace(100, 116, 64, endpoint=False, dtype=np.float32),
                          np.linspace(200, 216, 64, endpoint=False, dtype=np.float32))
    inteiro = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=4, seed=7)
    for i in (0, 32):
        for j in (0, 32):
            bloco = NoiseGenerator.generate_noise_field(
                gx[i:i + 32, j:j + 32], gy[i:i + 32, j:j + 32], scale=60, octaves=4, seed=7)
            assert np.array_equal(bloco, inteiro[i:i + 32, j:j + 32])


def test_oitavas_convergem():
    """T3 — F3 (refinamento monotônico): guarda o conserto de normalização da Fase 0.2.
    Adicionar oitavas tem que CONVERGIR para o mesmo campo, nunca reescalá-lo.

    Nota de projeto do teste (medido, não chutado): a comparação ingênua "maior
    diferença pontual entre octaves=4 e octaves=12, com tolerância = soma das
    amplitudes omitidas" NÃO separa a normalização antiga (com bug, soma truncada)
    da nova (soma infinita) de forma confiável — o "detalhe novo" real que as
    oitavas 4-11 acrescentam já é, sozinho, maior que o desvio extra introduzido
    pelo bug em vários pontos amostrados, então o pior-caso analítico é frouxo
    demais e deixa passar a normalização quebrada (verificado empiricamente
    revertendo o fix e rodando este teste — ele passava).

    RMS (erro quadrático médio) sobre a janela inteira, com média sobre 5 pares
    (seed, offset) fixos, separa as duas de forma limpa e reprodutível: medido,
    RMS médio da normalização nova ≈ 0,0055 vs. ≈ 0,0081 da antiga (~48% de
    margem). O limiar abaixo fica no meio do vão observado entre as duas.
    """
    p, base, alto = 0.5, 4, 12
    pares = [(7, 0, 0), (11, 500, 300), (13, 1200, 900), (17, 80, 4000), (19, 3000, 50)]
    rms_por_par = []
    for seed, ox, oy in pares:
        gx, gy = np.meshgrid(np.linspace(ox, ox + 50, 128, endpoint=False, dtype=np.float32),
                              np.linspace(oy, oy + 50, 128, endpoint=False, dtype=np.float32))
        a = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=base, seed=seed, persistencia=p)
        b = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=alto, seed=seed, persistencia=p)
        rms_por_par.append(float(np.sqrt(np.mean((a - b) ** 2))))
    assert np.mean(rms_por_par) < 0.0065


def _cartografo_de_teste():
    layout = {"continentes": [
        {"nome": "TesteA", "centro_x": 300, "centro_y": 400, "area_km2": 3000000,
         "irregularidade": 0.4, "elevacao_maxima": 0.85, "perfil_geologico": "Alpino",
         "modificadores": {"calor": 0.05, "umidade": -0.1}},
        {"nome": "TesteB", "centro_x": 600, "centro_y": 200, "area_km2": 1500000,
         "irregularidade": 0.55, "elevacao_maxima": 0.75, "perfil_geologico": "Platô",
         "modificadores": {"calor": -0.1, "umidade": 0.15}},
    ]}
    return TileCartographer(size=256, seed=1337, config=CARTOGRAPHER_CONFIG,
                             layout_continentes=layout, tamanho_global=768)


def test_gerar_janela_z0_igual_ao_arange():
    """T4 — a refatoração 0.3 não muda z0: `linspace(a, a+N, N, endpoint=False)` é
    exatamente `arange(a, a+N)`, e `generate_tile` (wrapper) bate bit a bit com a
    chamada equivalente a `gerar_janela`."""
    a = 512
    assert np.array_equal(np.linspace(a, a + 256, 256, endpoint=False, dtype=np.float32),
                           np.arange(a, a + 256, dtype=np.float32))
    tc = _cartografo_de_teste()
    assert np.array_equal(tc.generate_tile(2, 1), tc.gerar_janela(512, 256, 768, 512, 256, 256))


def test_gerar_janela_invariante_a_subdivisao():
    """T2 (versão de `gerar_janela`, pós-0.3) — a mesma janela do mundo, pedida de uma
    vez ou em 4 quadrantes, dá o mesmo resultado bit a bit. É esta versão que garante
    ausência de costura no mapa de verdade (não só no ruído cru)."""
    tc = _cartografo_de_teste()
    x0, y0, x1, y1 = 100, 150, 164, 214   # janela 64x64 de mundo
    inteiro = tc.gerar_janela(x0, y0, x1, y1, 64, 64, oitavas_extra=1)
    meio_x, meio_y = (x0 + x1) / 2, (y0 + y1) / 2
    quadrantes = [
        tc.gerar_janela(x0, y0, meio_x, meio_y, 32, 32, oitavas_extra=1),
        tc.gerar_janela(meio_x, y0, x1, meio_y, 32, 32, oitavas_extra=1),
        tc.gerar_janela(x0, meio_y, meio_x, y1, 32, 32, oitavas_extra=1),
        tc.gerar_janela(meio_x, meio_y, x1, y1, 32, 32, oitavas_extra=1),
    ]
    fatias = [(slice(0, 32), slice(0, 32)), (slice(0, 32), slice(32, 64)),
              (slice(32, 64), slice(0, 32)), (slice(32, 64), slice(32, 64))]
    for quad, (sy, sx) in zip(quadrantes, fatias):
        assert np.array_equal(quad, inteiro[sy, sx])


def test_culling_nao_altera_resultado():
    """T5 — F2: culling de continentes (otimização de custo na 0.3) não pode mudar o
    resultado. Janela longe de todos os continentes de teste teria tudo culled; janela
    dentro do alcance de um continente exercita o caminho onde só ele é avaliado."""
    tc = _cartografo_de_teste()
    casos = [
        (100, 150, 164, 214, 64, 64),   # perto de TesteA (centro 300,400) — parcialmente culled
        (590, 190, 654, 254, 64, 64),   # perto de TesteB (centro 600,200)
        (10, 10, 74, 74, 64, 64),       # longe de ambos — tudo culled com culling ligado
    ]
    for x0, y0, x1, y1, largura, altura in casos:
        com_culling = tc.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=1)
        sem_culling = tc.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=1, _desabilitar_culling=True)
        assert np.array_equal(com_culling, sem_culling)


def test_coerencia_entre_zooms():
    """T6 — F3: a mesma janela do mundo, amostrada em duas taxas/oitavas diferentes,
    tem que dar a MESMA classificação terra/água — zoom refina, nunca contradiz."""
    tc = _cartografo_de_teste()
    x0, y0, x1, y1 = 240, 280, 256, 296
    a = tc.gerar_janela(x0, y0, x1, y1, 64, 64, oitavas_extra=2)
    b = tc.gerar_janela(x0, y0, x1, y1, 512, 512, oitavas_extra=5)[::8, ::8]
    nm = CARTOGRAPHER_CONFIG["nivel_mar"]
    flips = int(((a[:, :, 0] >= nm) != (b[:, :, 0] >= nm)).sum())
    assert flips == 0


def test_detalhe_nao_vaza_para_zoom_baixo():
    """T7 — D2/Caminho B (DIAGNOSTICO_V3 Seção 13.5): o campo de detalhe tem que ser
    invisível nos zooms onde a janela não o resolve. Se este teste falhar, o mapa-múndi
    ganhou ruído de amostragem (aliasing)."""
    tc = _cartografo_de_teste()
    # z0: passo de 1 px de mundo; a oitava mais grossa do detalhe tem 0,5 px.
    com = tc.gerar_janela(300, 300, 556, 556, 256, 256, oitavas_extra=0)
    cfg = CARTOGRAPHER_CONFIG
    amp = cfg["relevo_detalhe_amplitude"]
    cfg["relevo_detalhe_amplitude"] = 0.0
    try:
        sem = tc.gerar_janela(300, 300, 556, 556, 256, 256, oitavas_extra=0)
    finally:
        cfg["relevo_detalhe_amplitude"] = amp
    assert np.allclose(com[:, :, 0], sem[:, :, 0], atol=1e-6)


def test_detalhe_preserva_a_costa():
    """T8 — D2/Caminho B: somar detalhe não pode mover a linha d'água em nenhum zoom. É
    o que separa 'textura de relevo' de 'outro mundo'."""
    tc = _cartografo_de_teste()
    nm = CARTOGRAPHER_CONFIG["nivel_mar"]
    cfg = CARTOGRAPHER_CONFIG
    amp = cfg["relevo_detalhe_amplitude"]
    for z in (4, 8, 12):
        lado = 256 / (2 ** z)
        com = tc.gerar_janela(300, 300, 300 + lado, 300 + lado, 128, 128, oitavas_extra=min(z, 9))
        cfg["relevo_detalhe_amplitude"] = 0.0
        try:
            sem = tc.gerar_janela(300, 300, 300 + lado, 300 + lado, 128, 128, oitavas_extra=min(z, 9))
        finally:
            cfg["relevo_detalhe_amplitude"] = amp
        assert int(((com[:, :, 0] >= nm) != (sem[:, :, 0] >= nm)).sum()) == 0, f"costa mudou no z={z}"


def test_detalhe_produz_relevo_na_escala_da_cidade():
    """T9 — D2/Caminho B: o objetivo do campo. Numa janela do tamanho de uma cidade
    grande ainda tem que haver variação de altitude. Sem o campo, essa janela é um plano.
    Ponto de teste (300, 400) é o CENTRO do continente TesteA da fixture — INTERIOR,
    altitude ~0,45, margem de 0,099 acima do nível do mar (bem acima de
    relevo_detalhe_margem_costa=0,05, então o envelope de costa não atenua o detalhe
    aqui). Não usar um ponto perto da costa: o envelope zera o detalhe por design, e
    mediria "sem efeito" por engano (D4 do diagnóstico — mesma armadilha do protótipo)."""
    tc = _cartografo_de_teste()
    lado = 0.1138          # diâmetro de uma cidade grande, em px de mundo (Seção 2.3)
    j = tc.gerar_janela(300, 400, 300 + lado, 400 + lado, 128, 128, oitavas_extra=9)
    alt = j[:, :, 0]
    assert float(alt.max() - alt.min()) > 5e-4, "janela de cidade continua plana"
