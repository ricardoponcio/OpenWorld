/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): início do Mapa Live, carregamento do
 * mundo, clique no mapa mundi e lista/salto de continentes — o estado e a
 * conversão de coordenadas foram extraídos pra mapa_leaflet_estado.js, os estilos
 * pra mapa_leaflet_estilos.js e as camadas vetoriais pra mapa_leaflet_camadas.js
 * (era 517 linhas, acima do limite de 250).
 *
 * Mapa Interativo estilo Leaflet (Frente 6, reescrito na Fase 0) — "Google Maps da
 * aventura". Cada tile é gerado SOB DEMANDA por TileCartographer.gerar_janela() na
 * primeira vista e cacheado em disco depois (cartographer/tiles/render.py), servido
 * em /tiles/<z>/<x>/<y>.png (web/composed_routes.py). Não existe mais pirâmide
 * pré-gerada nem mosaico de rasters — o terreno é uma função pura de coordenada de
 * mundo, então qualquer zoom pode ser avaliado, e refina (nunca contradiz) o que o
 * zoom anterior mostrava. O Leaflet cuida nativamente do carregamento parcial (só
 * os tiles visíveis são baixados) e do zoom contínuo de verdade via L.tileLayer.
 */
import { registrarAcoes } from './acoes.js';
import { estado, pixelParaLatLng, latLngParaPixel, bboxParaBounds } from './mapa_leaflet_estado.js';
import { criarCamadasVetoriaisLeaflet, carregarFeaturesVisiveisLeaflet } from './mapa_leaflet_camadas.js';
import { obterContinentes, obterInfoMapaMundi } from './api.js';
import { escaparHtml } from './formatacao.js';

export function initMapaLeaflet() {
    if (estado.leafletMap) {
        // Já inicializado — só garante que o tamanho renderiza certo ao trocar de aba
        setTimeout(() => estado.leafletMap.invalidateSize(), 50);
        return;
    }

    estado.leafletMap = L.map('mapa-leaflet-container', {
        crs: L.CRS.Simple,
        // Tem que bater com o minZoom da tile layer (não existe tile pré-gerado abaixo do
        // zoom 0 — é o mundo inteiro em 3x3 tiles de 256px). Se o mapa permitisse zoom
        // negativo e o fitBounds calculasse um zoom abaixo do minZoom da camada (container
        // um pouco menor que 768px), o Leaflet marca a camada como "fora de alcance" e para
        // de pedir tiles silenciosamente — mapa em branco, sem erro nenhum no console.
        minZoom: 0,
        zoomSnap: 0.25,
        attributionControl: false,
    });

    estado.leafletMap.on('click', onMapaLeafletClick);
    carregarMundoLeaflet();
    // Garante dimensões corretas mesmo na primeira inicialização (a aba pode ainda não ter
    // sofrido reflow síncrono em alguns navegadores/timings).
    setTimeout(() => estado.leafletMap.invalidateSize(), 50);
}

// F04 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estas 7 chaves são config do servidor
// (escala do mundo, zoom, largura de via) — nenhum valor duplicado aqui como
// fallback (ARQUITETURA §10 regra 6). Se /api/continentes não trouxer uma delas, o
// Mapa Live mostra erro em vez de desenhar com um número escrito à mão que já
// divergiu do config uma vez.
const CHAVES_OBRIGATORIAS_CONTINENTES = [
    'dimensao_global', 'tile_zoom_maximo_ui', 'tile_max_native_zoom',
    'mapa_features_tooltip_zoom_min', 'cidade_via_largura_m_por_classe',
    'cidade_via_largura_min_px', 'metros_por_pixel_mundo',
];

function mostrarErroMapaLeaflet(mensagem) {
    console.error(`[Mapa Live] ${mensagem}`);
    const container = document.getElementById('mapa-leaflet-container');
    if (container) {
        container.innerHTML = `<p class="mapa-live-erro">🔴 ${mensagem}</p>`;
    }
}

async function carregarMundoLeaflet() {
    try {
        const data = await obterContinentes();

        const faltando = CHAVES_OBRIGATORIAS_CONTINENTES.filter(chave => data[chave] === undefined);
        if (faltando.length > 0) {
            mostrarErroMapaLeaflet(`/api/continentes não trouxe: ${faltando.join(', ')}.`);
            return;
        }

        estado.leafletDimensaoGlobal = data.dimensao_global;
        // Fase 0.6: não é mais teto técnico (faltava tile pré-gerado acima disso) — o
        // raster agora pode ser gerado em qualquer zoom (gerar_janela é resolução-livre).
        // tile_zoom_maximo_ui é decisão de custo/UI, calibrada na Fase 1.2.
        estado.leafletZoomMaximo = data.tile_zoom_maximo_ui;
        // D5/D2 do DIAGNOSTICO_V3: acima deste zoom o raster não tem detalhe novo — o
        // Leaflet estica o último tile renderizado em vez de pedir um novo ao servidor.
        estado.leafletMaxNativeZoom = data.tile_max_native_zoom;
        estado.leafletContinentesCache = data.continentes || [];
        estado.leafletTooltipZoomMin = data.mapa_features_tooltip_zoom_min;
        estado.leafletZoomMinCidade = data.cidade_zoom_min_por_tamanho || {};
        estado.leafletMetrosPorPixelMundo = data.metros_por_pixel_mundo;
        estado.leafletViaLarguraM = data.cidade_via_largura_m_por_classe;
        estado.leafletViaLarguraMinPx = data.cidade_via_largura_min_px;

        const bounds = L.latLngBounds(pixelParaLatLng(0, estado.leafletDimensaoGlobal), pixelParaLatLng(estado.leafletDimensaoGlobal, 0));

        estado.leafletMap.setMaxZoom(estado.leafletZoomMaximo);
        if (estado.leafletTileLayer) estado.leafletMap.removeLayer(estado.leafletTileLayer);
        estado.leafletTileLayer = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
            tileSize: 256,
            minZoom: 0,
            maxZoom: estado.leafletZoomMaximo,
            // D5/D2 do DIAGNOSTICO_V3: acima deste nível o raster não ganha detalhe NOVO
            // (medido: o gradiente da imagem satura ali), então o Leaflet estica o tile
            // desse zoom em vez de pedir um tile novo ao servidor — mesma imagem, custo
            // zero. tile_zoom_maximo_ui continua maior porque as camadas VETORIAIS de
            // cidade (rua/edifício/etc) precisam de zoom alto e não perdem qualidade.
            maxNativeZoom: estado.leafletMaxNativeZoom,
            noWrap: true,
            bounds: bounds,
        }).addTo(estado.leafletMap);

        estado.leafletMap.setMaxBounds(bounds.pad(0.2));
        estado.leafletMap.fitBounds(bounds);

        // Fase 3: camadas vetoriais criadas uma vez; dados recarregam a cada
        // moveend/zoomend (bbox+zoom visíveis), não no load inicial só.
        if (Object.keys(estado.leafletCamadasVetoriais).length === 0) {
            criarCamadasVetoriaisLeaflet();
            estado.leafletMap.on('moveend', carregarFeaturesVisiveisLeaflet);
        }
        carregarFeaturesVisiveisLeaflet();

        renderizarListaContinentesLeaflet();
    } catch (e) { mostrarErroMapaLeaflet(`Falha ao carregar /api/continentes: ${e}`); }
}

function renderizarListaContinentesLeaflet() {
    const container = document.getElementById('leaflet-continent-list');
    if (!container) return;
    if (estado.leafletContinentesCache.length === 0) {
        container.innerHTML = '<span class="leaflet-lista-vazia">Nenhum continente no manifesto — gere o mundo primeiro.</span>';
        return;
    }
    container.innerHTML = estado.leafletContinentesCache.map((c, i) => `
        <button class="filter-btn" data-acao="ir-para-continente-leaflet" data-indice="${i}">
            🏔️ ${escaparHtml(c.nome)} <span class="continente-area">(${Math.round((c.area_real_km2 || 0) / 1000)}k km²)</span>
        </button>
    `).join('') + `<button class="filter-btn" data-acao="voltar-mundo-leaflet">🌍 Ver mundo inteiro</button>`;
}

function pularParaContinenteLeaflet(indice) {
    const cont = estado.leafletContinentesCache[indice];
    if (!cont || !cont.bounding_box || !cont.bounding_box.max_x) {
        alert('Este continente não tem bounding box válido (0 pixels de terra?).');
        return;
    }
    estado.leafletMap.flyToBounds(bboxParaBounds(cont.bounding_box), { maxZoom: estado.leafletZoomMaximo, duration: 0.6 });
}

function voltarMundoLeaflet() {
    const bounds = L.latLngBounds(pixelParaLatLng(0, estado.leafletDimensaoGlobal), pixelParaLatLng(estado.leafletDimensaoGlobal, 0));
    estado.leafletMap.flyToBounds(bounds, { duration: 0.6 });
}

async function onMapaLeafletClick(e) {
    const { x, y } = latLngParaPixel(e.latlng);
    if (x < 0 || y < 0 || x >= estado.leafletDimensaoGlobal || y >= estado.leafletDimensaoGlobal) return;

    // Sempre consulta a informação "oficial" do mapa mundi pra essa coordenada, independente
    // do quão fundo o zoom está — o tile visível pode vir de um recorte de cidade/continente,
    // mas o dado de bioma/altitude de referência é o do mapa mundi (ground truth).
    try {
        const data = await obterInfoMapaMundi(x, y);
        if (data.error) return;

        if (estado.leafletPopupAtual) estado.leafletMap.closePopup(estado.leafletPopupAtual);
        estado.leafletPopupAtual = L.popup()
            .setLatLng(e.latlng)
            .setContent(`
                <strong>${escaparHtml(data.bioma_nome)}</strong><br>
                Altitude: ${(data.altitude * 100).toFixed(1)}%<br>
                Temperatura: ${(data.temperatura * 100).toFixed(1)}%<br>
                Umidade: ${(data.umidade * 100).toFixed(1)}%<br>
                <span class="popup-coord">px (${x}, ${y})</span>
            `)
            .openOn(estado.leafletMap);
    } catch (err) { console.error('Erro ao consultar info do mapa:', err); }
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): cada módulo registra as próprias ações.
registrarAcoes({
    'ir-para-continente-leaflet': (alvo) => pularParaContinenteLeaflet(parseInt(alvo.dataset.indice, 10)),
    'voltar-mundo-leaflet': () => voltarMundoLeaflet(),
});
