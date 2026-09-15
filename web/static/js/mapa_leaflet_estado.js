/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado compartilhado do Mapa Live e
 * conversão de coordenadas — extraído de mapa_leaflet.js pra este arquivo próprio
 * (não listado na tabela original do plano) porque mapa_leaflet.js precisa importar
 * de mapa_leaflet_camadas.js (criarCamadasVetoriaisLeaflet/
 * carregarFeaturesVisiveisLeaflet), e mapa_leaflet_camadas.js precisa do `estado` —
 * as duas coisas num arquivo só criariam um import circular entre mapa_leaflet.js e
 * mapa_leaflet_camadas.js. Mesmo padrão que mapa_composto_estado.js já usa.
 *
 * Conversão de coordenadas: a transformação padrão do L.CRS.Simple é
 * pixelY = -lat * escala (sem nenhum deslocamento) — ou seja, lat precisa ser
 * NEGATIVO para que o pixel resultante seja positivo e bata com o endereçamento
 * y/0..N dos tiles pré-gerados (linha 0 = topo). Por isso lat = -py (não
 * dimensaoGlobal - py, que geraria pixelY negativo e pediria tiles y<0 ao Leaflet).
 * Só o clique do usuário (que chega como lat/lng do Leaflet) precisa ser
 * convertido de volta pra pixel de mundo (Y crescendo pra baixo) pra consultar a
 * API de inspeção. Ver pixelParaLatLng/latLngParaPixel.
 */

// F01: estado do módulo num objeto só, não dezenas de `let` soltos (ARQUITETURA §10
// regra 4).
export const estado = {
    leafletMap: null,
    leafletTileLayer: null,
    leafletDimensaoGlobal: 768,
    leafletZoomMaximo: 15,
    leafletMaxNativeZoom: 11,
    leafletContinentesCache: [],
    leafletPopupAtual: null,
    // Fase 3 (P2.1): camada vetorial GeoJSON — nome -> L.geoJSON. "estradas"/"pois"/
    // "fronteiras" ainda não têm gerador (nenhuma fase até aqui produz esse dado); ficam
    // no seletor de camadas já prontas pra quando uma fase futura escrever o arquivo.
    leafletCamadasVetoriais: {},
    leafletControlCamadas: null,
    leafletTooltipZoomMin: 5,
    // `{tamanho: {camada: zoom_min}}` vindo de /api/continentes — a mesma tabela que o
    // gerador gravou nas features. Serve pra contar ao usuário a que zoom cada camada
    // acende, em vez de repetir números aqui (que já divergiram do config uma vez).
    leafletZoomMinCidade: {},
    // Escala do mundo e largura das vias, servidas por /api/continentes. São o que
    // permite desenhar em METRO em vez de px de tela — ver estiloRua.
    leafletMetrosPorPixelMundo: 15811.4,
    leafletViaLarguraM: { principal: 11, anel: 7, secundaria: 5 },
    leafletViaLarguraMinPx: 1.5,
};

export function pixelParaLatLng(px, py) {
    return L.latLng(-py, px);
}

// Pixel de mundo FRACIONÁRIO. É o que vale pra qualquer conta de geometria: uma cidade
// inteira mede 0,076 px de mundo (1 px = 15,81 km), então arredondar aqui apaga a cidade.
export function latLngParaPixelExato(latlng) {
    return { x: latlng.lng, y: -latlng.lat };
}

// Versão inteira, só pra consultar o mapa mundi por pixel (/api/mapa_composto/info/x/y,
// que indexa um array). NÃO use pra montar bbox — ver latLngParaPixelExato.
export function latLngParaPixel(latlng) {
    const p = latLngParaPixelExato(latlng);
    return { x: Math.round(p.x), y: Math.round(p.y) };
}

export function bboxParaBounds(bbox) {
    const sw = pixelParaLatLng(bbox.min_x, bbox.max_y);
    const ne = pixelParaLatLng(bbox.max_x, bbox.min_y);
    return L.latLngBounds(sw, ne);
}
