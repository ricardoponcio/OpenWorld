// Mapa Interativo estilo Leaflet (Frente 6, reescrito na Fase 0) — "Google Maps da aventura".
//
// Cada tile é gerado SOB DEMANDA por TileCartographer.gerar_janela() na primeira vista e
// cacheado em disco depois (cartographer/tiles/render.py), servido em
// /tiles/<z>/<x>/<y>.png (web/composed_routes.py). Não existe mais pirâmide pré-gerada nem
// mosaico de rasters — o terreno é uma função pura de coordenada de mundo, então qualquer
// zoom pode ser avaliado, e refina (nunca contradiz) o que o zoom anterior mostrava.
// O Leaflet cuida nativamente do carregamento parcial (só os tiles visíveis são baixados)
// e do zoom contínuo de verdade via L.tileLayer.
//
// Conversão de coordenadas: a transformação padrão do L.CRS.Simple é
// pixelY = -lat * escala (sem nenhum deslocamento) — ou seja, lat precisa ser
// NEGATIVO para que o pixel resultante seja positivo e bata com o endereçamento
// y/0..N dos tiles pré-gerados (linha 0 = topo). Por isso lat = -py (não
// dimensaoGlobal - py, que geraria pixelY negativo e pediria tiles y<0 ao Leaflet).
// Só o clique do usuário (que chega como lat/lng do Leaflet) precisa ser
// convertido de volta pra pixel de mundo (Y crescendo pra baixo) pra consultar a
// API de inspeção. Ver pixelParaLatLng/latLngParaPixel.

let leafletMap = null;
let leafletTileLayer = null;
let leafletDimensaoGlobal = 768;
let leafletZoomMaximo = 16;
let leafletContinentesCache = [];
let leafletPopupAtual = null;

// Fase 3 (P2.1): camada vetorial GeoJSON — nome -> L.geoJSON. "estradas"/"pois"/
// "fronteiras" ainda não têm gerador (nenhuma fase até aqui produz esse dado); ficam
// no seletor de camadas já prontas pra quando uma fase futura escrever o arquivo.
//
// Fase 4 (P2.2): "detalhe_cidade" é um grupo com as 7 camadas internas de geometria de
// cidade (rua/quarteirao/muralha/torre/portao/praca/edificio — "lote" fica de fora,
// granular demais pra valer a pena desenhar) — um único toggle no control, não 7. Só
// aparece perto o bastante (zoom_min alto, calculado em generate_city_geometry.py a
// partir do tamanho real da cidade — a cidade é sub-pixel na escala do mundo, Seção 2.1).
let leafletCamadasVetoriais = {};
let leafletControlCamadas = null;
let leafletTooltipZoomMin = 5;
const CAMADAS_MUNDO = ['cidades', 'pois', 'estradas', 'fronteiras'];
const CAMADAS_DETALHE_CIDADE = ['muralha', 'torre', 'portao', 'praca', 'rua', 'quarteirao', 'edificio'];
const CAMADAS_VETORIAIS_DISPONIVEIS = [...CAMADAS_MUNDO, ...CAMADAS_DETALHE_CIDADE];
const CAMADAS_NOMES_AMIGAVEIS = { cidades: '🏰 Cidades', pois: '📍 Pontos de Interesse', estradas: '🛣️ Estradas', fronteiras: '🗺️ Fronteiras' };
const TIPO_CIDADE_EMOJI = { capital: '👑', fortaleza: '🏯', portuaria: '⚓', pesqueira: '🎣', comercial: '💰', mistica: '🔮', 'mística': '🔮', mineira: '⛏️', agricola: '🌾', 'agrícola': '🌾', residencial: '🏠' };
const CATEGORIA_EDIFICIO_COR = { residencia: '#8B4513', fazenda: '#228B22', quartel: '#4682B4', taverna: '#D2691E', publico: '#696969', mercado: '#FFD700', forja: '#A9A9A9', universidade: '#5D3FD3', generic: '#808080' };

function pixelParaLatLng(px, py) {
    return L.latLng(-py, px);
}

function latLngParaPixel(latlng) {
    return { x: Math.round(latlng.lng), y: Math.round(-latlng.lat) };
}

function bboxParaBounds(bbox) {
    const sw = pixelParaLatLng(bbox.min_x, bbox.max_y);
    const ne = pixelParaLatLng(bbox.max_x, bbox.min_y);
    return L.latLngBounds(sw, ne);
}

function initMapaLeaflet() {
    if (leafletMap) {
        // Já inicializado — só garante que o tamanho renderiza certo ao trocar de aba
        setTimeout(() => leafletMap.invalidateSize(), 50);
        return;
    }

    leafletMap = L.map('mapa-leaflet-container', {
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

    leafletMap.on('click', onMapaLeafletClick);
    carregarMundoLeaflet();
    // Garante dimensões corretas mesmo na primeira inicialização (a aba pode ainda não ter
    // sofrido reflow síncrono em alguns navegadores/timings).
    setTimeout(() => leafletMap.invalidateSize(), 50);
}

async function carregarMundoLeaflet() {
    try {
        const res = await fetch('/api/continentes');
        const data = await res.json();
        leafletDimensaoGlobal = data.dimensao_global || 768;
        // Fase 0.6: não é mais teto técnico (faltava tile pré-gerado acima disso) — o
        // raster agora pode ser gerado em qualquer zoom (gerar_janela é resolução-livre).
        // tile_zoom_maximo_ui é decisão de custo/UI, calibrada na Fase 1.2.
        leafletZoomMaximo = data.tile_zoom_maximo_ui || 16;
        leafletContinentesCache = data.continentes || [];
        leafletTooltipZoomMin = data.mapa_features_tooltip_zoom_min || 5;

        const bounds = L.latLngBounds(pixelParaLatLng(0, leafletDimensaoGlobal), pixelParaLatLng(leafletDimensaoGlobal, 0));

        leafletMap.setMaxZoom(leafletZoomMaximo);
        if (leafletTileLayer) leafletMap.removeLayer(leafletTileLayer);
        leafletTileLayer = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
            tileSize: 256,
            minZoom: 0,
            maxZoom: leafletZoomMaximo,
            noWrap: true,
            bounds: bounds,
        }).addTo(leafletMap);

        leafletMap.setMaxBounds(bounds.pad(0.2));
        leafletMap.fitBounds(bounds);

        // Fase 3: camadas vetoriais criadas uma vez; dados recarregam a cada
        // moveend/zoomend (bbox+zoom visíveis), não no load inicial só.
        if (Object.keys(leafletCamadasVetoriais).length === 0) {
            criarCamadasVetoriaisLeaflet();
            leafletMap.on('moveend', carregarFeaturesVisiveisLeaflet);
        }
        carregarFeaturesVisiveisLeaflet();

        renderizarListaContinentesLeaflet();
    } catch (e) { console.error('Erro ao carregar mundo no Leaflet:', e); }
}

// Estilo de linha/polígono por camada de detalhe de cidade (Fase 4) — L.geoJSON aceita
// `style` (usado pra LineString/Polygon) e `pointToLayer` (usado pra Point) ao mesmo
// tempo; como cada camada só contém um tipo de geometria, cada uma usa só o que precisa.
const ESTILO_CAMADA_CIDADE = {
    muralha: { color: '#d4a017', weight: 3, opacity: 0.9 },
    rua: { color: '#ddd', weight: 1.5, opacity: 0.7 },
    quarteirao: { color: '#888', weight: 1, opacity: 0.4, fillOpacity: 0.04 },
    praca: { color: '#2ecc71', weight: 1, opacity: 0.6, fillOpacity: 0.25 },
};

function criarCamadasVetoriaisLeaflet() {
    const overlays = {};

    CAMADAS_MUNDO.forEach(nome => {
        const layer = L.geoJSON(null, { pointToLayer: criarMarcadorFeatureLeaflet });
        leafletCamadasVetoriais[nome] = layer;
        overlays[CAMADAS_NOMES_AMIGAVEIS[nome] || nome] = layer;
    });
    // Só "cidades" começa visível — as outras existem no seletor pra quando uma fase
    // futura escrever o GeoJSON correspondente (hoje ficam vazias, sem erro nenhum).
    leafletCamadasVetoriais['cidades'].addTo(leafletMap);

    // Fase 4: as 7 camadas de detalhe de cidade viram UM grupo — um toggle só
    // ("🏛️ Detalhe da Cidade"), não 7 checkboxes pra ligar/desligar juntos toda vez.
    const grupoDetalheCidade = L.layerGroup();
    CAMADAS_DETALHE_CIDADE.forEach(nome => {
        const opcoes = ESTILO_CAMADA_CIDADE[nome] ? { style: ESTILO_CAMADA_CIDADE[nome] } : {};
        opcoes.pointToLayer = (feature, latlng) => criarMarcadorDetalheCidade(feature, latlng, nome);
        const layer = L.geoJSON(null, opcoes);
        leafletCamadasVetoriais[nome] = layer;
        layer.addTo(grupoDetalheCidade);
    });
    overlays['🏛️ Detalhe da Cidade (zoom ~11+)'] = grupoDetalheCidade;

    if (leafletControlCamadas) leafletMap.removeControl(leafletControlCamadas);
    leafletControlCamadas = L.control.layers(null, overlays, { collapsed: false }).addTo(leafletMap);
}

function criarMarcadorDetalheCidade(feature, latlng, camada) {
    const props = feature.properties || {};

    if (camada === 'edificio') {
        const cor = CATEGORIA_EDIFICIO_COR[props.categoria] || CATEGORIA_EDIFICIO_COR.generic;
        const marker = L.circleMarker(latlng, { radius: 5, color: '#fff', weight: 1, fillColor: cor, fillOpacity: 0.9 });
        marker.bindPopup(`
            <strong>${props.nome || 'Edifício'}</strong><br>
            <span style="opacity:0.8">${props.tipo_local || ''}${props.bairro ? ' · ' + props.bairro : ''}</span>
        `);
        return marker;
    }
    if (camada === 'portao') {
        return L.circleMarker(latlng, { radius: 4, color: '#fff', weight: 1, fillColor: '#8B4513', fillOpacity: 1 })
            .bindPopup(props.nome || 'Portão');
    }
    if (camada === 'torre') {
        return L.circleMarker(latlng, { radius: 3, color: '#fff', weight: 1, fillColor: '#666', fillOpacity: 1 });
    }
    return L.circleMarker(latlng, { radius: 3, color: '#fff', weight: 1, fillColor: '#999', fillOpacity: 1 });
}

function criarMarcadorFeatureLeaflet(feature, latlng) {
    const props = feature.properties || {};
    const emoji = TIPO_CIDADE_EMOJI[(props.tipo || '').toLowerCase()] || '📍';

    const marker = L.marker(latlng, {
        icon: L.divIcon({
            html: `<div style="font-size:20px; line-height:1; text-align:center; filter:drop-shadow(0 0 2px #000);">${emoji}</div>`,
            className: 'leaflet-vector-icon',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        }),
    });

    if (props.nome) {
        marker.bindTooltip(props.nome, {
            permanent: leafletMap.getZoom() >= leafletTooltipZoomMin,
            direction: 'top',
            offset: [0, -12],
            className: 'leaflet-vector-tooltip',
        });
    }

    marker.bindPopup(`
        <strong>${props.nome || 'Sem nome'}</strong><br>
        <span style="opacity:0.8">${props.tipo || ''}${props.tamanho ? ' · ' + props.tamanho : ''}</span><br>
        ${props.continente ? `<span style="opacity:0.6; font-size:0.85rem;">${props.continente}</span><br>` : ''}
        ${props.descricao ? `<p style="margin-top:6px;">${props.descricao}</p>` : ''}
    `);

    return marker;
}

async function carregarFeaturesVisiveisLeaflet() {
    if (!leafletMap || Object.keys(leafletCamadasVetoriais).length === 0) return;

    const bounds = leafletMap.getBounds();
    const sw = latLngParaPixel(bounds.getSouthWest());
    const ne = latLngParaPixel(bounds.getNorthEast());
    const x0 = Math.min(sw.x, ne.x), x1 = Math.max(sw.x, ne.x);
    const y0 = Math.min(sw.y, ne.y), y1 = Math.max(sw.y, ne.y);
    const z = Math.round(leafletMap.getZoom());

    try {
        const camadas = CAMADAS_VETORIAIS_DISPONIVEIS.join(',');
        const res = await fetch(`/api/mapa/features?camadas=${camadas}&bbox=${x0},${y0},${x1},${y1}&z=${z}`);
        const data = await res.json();
        CAMADAS_VETORIAIS_DISPONIVEIS.forEach(nome => {
            const layer = leafletCamadasVetoriais[nome];
            if (!layer || !data[nome]) return;
            layer.clearLayers();
            layer.addData(data[nome]);
        });
    } catch (e) { console.error('Erro ao carregar camadas vetoriais do mapa:', e); }
}

function renderizarListaContinentesLeaflet() {
    const container = document.getElementById('leaflet-continent-list');
    if (!container) return;
    if (leafletContinentesCache.length === 0) {
        container.innerHTML = '<span style="color:var(--text-dim); font-size:0.8rem;">Nenhum continente no manifesto — gere o mundo primeiro.</span>';
        return;
    }
    container.innerHTML = leafletContinentesCache.map((c, i) => `
        <button class="filter-btn" onclick="pularParaContinenteLeaflet(${i})">
            🏔️ ${c.nome} <span style="opacity:0.7; font-size:0.75rem;">(${Math.round((c.area_real_km2 || 0) / 1000)}k km²)</span>
        </button>
    `).join('') + `<button class="filter-btn" onclick="voltarMundoLeaflet()">🌍 Ver mundo inteiro</button>`;
}

function pularParaContinenteLeaflet(indice) {
    const cont = leafletContinentesCache[indice];
    if (!cont || !cont.bounding_box || !cont.bounding_box.max_x) {
        alert('Este continente não tem bounding box válido (0 pixels de terra?).');
        return;
    }
    leafletMap.flyToBounds(bboxParaBounds(cont.bounding_box), { maxZoom: leafletZoomMaximo, duration: 0.6 });
}

function voltarMundoLeaflet() {
    const bounds = L.latLngBounds(pixelParaLatLng(0, leafletDimensaoGlobal), pixelParaLatLng(leafletDimensaoGlobal, 0));
    leafletMap.flyToBounds(bounds, { duration: 0.6 });
}

async function onMapaLeafletClick(e) {
    const { x, y } = latLngParaPixel(e.latlng);
    if (x < 0 || y < 0 || x >= leafletDimensaoGlobal || y >= leafletDimensaoGlobal) return;

    // Sempre consulta a informação "oficial" do mapa mundi pra essa coordenada, independente
    // do quão fundo o zoom está — o tile visível pode vir de um recorte de cidade/continente,
    // mas o dado de bioma/altitude de referência é o do mapa mundi (ground truth).
    try {
        const res = await fetch(`/api/mapa_composto/info/${x}/${y}`);
        const data = await res.json();
        if (data.error) return;

        if (leafletPopupAtual) leafletMap.closePopup(leafletPopupAtual);
        leafletPopupAtual = L.popup()
            .setLatLng(e.latlng)
            .setContent(`
                <strong>${data.bioma_nome}</strong><br>
                Altitude: ${(data.altitude * 100).toFixed(1)}%<br>
                Temperatura: ${(data.temperatura * 100).toFixed(1)}%<br>
                Umidade: ${(data.umidade * 100).toFixed(1)}%<br>
                <span style="opacity:0.6; font-size:0.75rem;">px (${x}, ${y})</span>
            `)
            .openOn(leafletMap);
    } catch (err) { console.error('Erro ao consultar info do mapa:', err); }
}
