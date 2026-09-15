/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado compartilhado do mapa em
 * canvas — extraído de mapa_composto.js (era 723 linhas, acima do limite de 250).
 * Os outros módulos `mapa_composto_*` importam `estado`/`canvas`/`ctx`/`img` daqui;
 * nenhum deles cria o próprio estado.
 */
import { Modo } from './constantes.js';

export const canvas = document.getElementById('mapaCanvas');
export const ctx = canvas.getContext('2d');
export const container = document.getElementById('canvasContainer');

// F01: estado do módulo num objeto só, não dezenas de `let` soltos (ARQUITETURA §10
// regra 4).
export const estado = {
    currentMode: Modo.GLOBAL,
    currentContinentUuid: null,
    currentCityNome: null,
    scale: 1.0,
    offsetX: 0,
    offsetY: 0,
    isDragging: false,
    startX: 0,
    startY: 0,
    lastInspectedX: -1,
    lastInspectedY: -1,
    minScale: 1.0,
    mouseX: -1,
    mouseY: -1,
    hoveredTooltip: null,
    cityEntities: { locais: [], npcs: [], bbox: null },
    // D7 do DIAGNOSTICO_V3: posição do marcador agregado desenhado por
    // drawCityGridAndEntities (canvas em pixel de TELA, já com offset/scale
    // aplicados) — usado só pro hit-test do hover.
    cityAggregateMarker: null,
    cachedContinents: [],
    // R-B06/R-H04: tabela de biomas (id -> {rotulo, emoji}) servida por
    // /api/continentes — nunca copiada à mão aqui (já divergiu uma vez: um bioma
    // "Zona Urbana" inventado no JS que não existia no classificador Python).
    cachedBiomas: {},
    npcAnimations: {}, // id -> { x, y, tx, ty }
    isAnimating: false,
    hoverTimeout: null,
    abortController: null,
};

// Query memory cache
export const apiCache = {};

// Load the terrain image — o `src`/`onload` de verdade só é atribuído dentro de
// iniciarMapaComposto() (F01, docs/16_PLANO_PAINEL_E_IA.md): nenhum efeito colateral
// no topo do módulo, app.js decide quando iniciar.
export const img = new Image();

// Fase 2.1 (P0.3): `loc.coordenadas` é pixel de MUNDO (Seção 2.3), não mais um índice
// de grade 0-40. Converte mundo -> pixel da imagem da região devolvida por
// `/api/regiao/<nome>/entities` (mesma janela que gerou a imagem em si — D7).
export function mundoParaImagemCidade(x, y) {
    const bbox = estado.cityEntities.bbox;
    if (!bbox) return { x: 0, y: 0 };
    const ix = (x - bbox.min_x) / Math.max(1e-6, bbox.max_x - bbox.min_x) * bbox.largura_img;
    const iy = (y - bbox.min_y) / Math.max(1e-6, bbox.max_y - bbox.min_y) * bbox.altura_img;
    return { x: ix, y: iy };
}
