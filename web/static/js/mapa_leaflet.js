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
let leafletZoomMaximo = 15;
let leafletMaxNativeZoom = 11;
let leafletContinentesCache = [];
let leafletPopupAtual = null;

// Fase 3 (P2.1): camada vetorial GeoJSON — nome -> L.geoJSON. "estradas"/"pois"/
// "fronteiras" ainda não têm gerador (nenhuma fase até aqui produz esse dado); ficam
// no seletor de camadas já prontas pra quando uma fase futura escrever o arquivo.
//
// Fase 4 (P2.2): "detalhe_cidade" é um grupo com as 8 camadas internas de geometria de
// cidade (rua/quarteirao/muralha/torre/portao/praca/edificio/lote) — um único toggle no
// control, não 8. O grupo entra LIGADO por padrão (D3 do DIAGNOSTICO_V3, 2026-09-11: as
// camadas internas já têm zoom_min, nada é desenhado em zoom baixo, então ligar por
// padrão não custa em performance e é a única forma do usuário descobrir que a cidade
// existe). Só aparece perto o bastante (zoom_min alto, calculado em
// generate_city_geometry.py a partir do tamanho real da cidade — a cidade é sub-pixel na
// escala do mundo, Seção 2.1).
let leafletCamadasVetoriais = {};
let leafletControlCamadas = null;
let leafletTooltipZoomMin = 5;
// `{tamanho: {camada: zoom_min}}` vindo de /api/continentes — a mesma tabela que o gerador
// gravou nas features. Serve pra contar ao usuário a que zoom cada camada acende, em vez
// de repetir números aqui (que já divergiram do config uma vez).
let leafletZoomMinCidade = {};
// Escala do mundo e largura das vias, servidas por /api/continentes. São o que permite
// desenhar em METRO em vez de px de tela — ver estiloRua.
let leafletMetrosPorPixelMundo = 15811.4;
let leafletViaLarguraM = { principal: 11, anel: 7, secundaria: 5 };
let leafletViaLarguraMinPx = 1.5;
const CAMADAS_MUNDO = ['cidades', 'pois', 'estradas', 'fronteiras'];
const CAMADAS_DETALHE_CIDADE = ['muralha', 'torre', 'portao', 'praca', 'rua', 'quarteirao', 'patio', 'lote', 'edificio'];
const CAMADAS_VETORIAIS_DISPONIVEIS = [...CAMADAS_MUNDO, ...CAMADAS_DETALHE_CIDADE];
const CAMADAS_NOMES_AMIGAVEIS = { cidades: '🏰 Cidades', pois: '📍 Pontos de Interesse', estradas: '🛣️ Estradas', fronteiras: '🗺️ Fronteiras' };
const TIPO_CIDADE_EMOJI = { capital: '👑', fortaleza: '🏯', portuaria: '⚓', pesqueira: '🎣', comercial: '💰', mistica: '🔮', 'mística': '🔮', mineira: '⛏️', agricola: '🌾', 'agrícola': '🌾', residencial: '🏠' };
// A residência é massa construída, não informação — tom neutro único, sem cor de
// categoria (Seção 6/E3 do ESPEC_TECIDO_URBANO.md: com ~1.350 residências e ~48 prédios
// notáveis por cidade, dar cor de categoria a todas empasta a tela). A cor de categoria
// fica reservada pros notáveis, que são os que o jogador procura.
const CATEGORIA_EDIFICIO_COR = { residencia: '#9c8a76', fazenda: '#228B22', quartel: '#4682B4', taverna: '#D2691E', publico: '#696969', mercado: '#FFD700', forja: '#A9A9A9', universidade: '#5D3FD3', generic: '#808080' };

function pixelParaLatLng(px, py) {
    return L.latLng(-py, px);
}

// Pixel de mundo FRACIONÁRIO. É o que vale pra qualquer conta de geometria: uma cidade
// inteira mede 0,076 px de mundo (1 px = 15,81 km), então arredondar aqui apaga a cidade.
function latLngParaPixelExato(latlng) {
    return { x: latlng.lng, y: -latlng.lat };
}

// Versão inteira, só pra consultar o mapa mundi por pixel (/api/mapa_composto/info/x/y,
// que indexa um array). NÃO use pra montar bbox — ver latLngParaPixelExato.
function latLngParaPixel(latlng) {
    const p = latLngParaPixelExato(latlng);
    return { x: Math.round(p.x), y: Math.round(p.y) };
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
        leafletZoomMaximo = data.tile_zoom_maximo_ui || 15;
        // D5/D2 do DIAGNOSTICO_V3: acima deste zoom o raster não tem detalhe novo — o
        // Leaflet estica o último tile renderizado em vez de pedir um novo ao servidor.
        leafletMaxNativeZoom = data.tile_max_native_zoom || 11;
        leafletContinentesCache = data.continentes || [];
        leafletTooltipZoomMin = data.mapa_features_tooltip_zoom_min || 5;
        leafletZoomMinCidade = data.cidade_zoom_min_por_tamanho || {};
        leafletMetrosPorPixelMundo = data.metros_por_pixel_mundo || leafletMetrosPorPixelMundo;
        leafletViaLarguraM = data.cidade_via_largura_m_por_classe || leafletViaLarguraM;
        if (typeof data.cidade_via_largura_min_px === 'number') leafletViaLarguraMinPx = data.cidade_via_largura_min_px;

        const bounds = L.latLngBounds(pixelParaLatLng(0, leafletDimensaoGlobal), pixelParaLatLng(leafletDimensaoGlobal, 0));

        leafletMap.setMaxZoom(leafletZoomMaximo);
        if (leafletTileLayer) leafletMap.removeLayer(leafletTileLayer);
        leafletTileLayer = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
            tileSize: 256,
            minZoom: 0,
            maxZoom: leafletZoomMaximo,
            // D5/D2 do DIAGNOSTICO_V3: acima deste nível o raster não ganha detalhe NOVO
            // (medido: o gradiente da imagem satura ali), então o Leaflet estica o tile
            // desse zoom em vez de pedir um tile novo ao servidor — mesma imagem, custo
            // zero. tile_zoom_maximo_ui continua maior porque as camadas VETORIAIS de
            // cidade (rua/edifício/etc) precisam de zoom alto e não perdem qualidade.
            maxNativeZoom: leafletMaxNativeZoom,
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
// Quantos px de TELA vale um metro no zoom atual. No L.CRS.Simple 1 px de mundo ocupa
// 2^zoom px de tela, e 1 px de mundo são `leafletMetrosPorPixelMundo` metros.
function pxDeTelaPorMetro() {
    return Math.pow(2, leafletMap.getZoom()) / leafletMetrosPorPixelMundo;
}

// Tom de cada classe de via. Terra batida clara sobre o verde do terreno; a principal é a
// mais clara e opaca, que é como a hierarquia viária se lê num mapa de verdade.
const ESTILO_VIA_POR_CLASSE = {
    principal: { color: '#e8ddc8', opacity: 0.95 },
    anel: { color: '#dbd1bd', opacity: 0.85 },
    secundaria: { color: '#c6bda9', opacity: 0.75 },
};

// A rua é a única camada com estilo dinâmico: a espessura é uma largura REAL em metros,
// convertida a cada zoom. Antes era `weight: 1.5` fixo em px de tela, o que dava uma rua
// de 11,6 m no z11 e de 0,7 m no z15 — ela afinava conforme você se aproximava, e é daí
// que vinha a impressão de linha imaginária em cima do terreno em vez de rua.
// L.geoJSON aceita `style` como função e a reavalia a cada addData, que acontece em todo
// moveend (e zoom dispara moveend), então isto se reajusta sozinho ao navegar.
function estiloRua(feature) {
    const classe = (feature.properties || {}).classe_via || 'secundaria';
    const larguraM = leafletViaLarguraM[classe] || leafletViaLarguraM.secundaria || 5;
    return {
        ...(ESTILO_VIA_POR_CLASSE[classe] || ESTILO_VIA_POR_CLASSE.secundaria),
        // O piso existe porque no zoom em que a camada acende a cidade inteira ainda tem
        // ~310 px e a via de verdade daria 2 px de largura.
        weight: Math.max(leafletViaLarguraMinPx, larguraM * pxDeTelaPorMetro()),
        // Junta e ponta arredondadas fecham o cruzamento em vez de deixar o entalhe que
        // denuncia que aquilo são segmentos soltos.
        lineCap: 'round',
        lineJoin: 'round',
    };
}

// E3 do ESPEC_TECIDO_URBANO.md: `edificio` virou Polygon (footprint dentro do lote), não
// mais um Point desenhado por `criarMarcadorDetalheCidade` — passa a usar `style` como
// rua/quarteirao/lote. Preenchimento sólido (é massa construída), contorno bem discreto
// pra não competir com o traço do lote por baixo.
function estiloEdificio(feature) {
    const categoria = (feature.properties || {}).categoria;
    const cor = CATEGORIA_EDIFICIO_COR[categoria] || CATEGORIA_EDIFICIO_COR.generic;
    return {
        color: '#2b2b2b', weight: 0.5, opacity: 0.4,
        fillColor: cor, fillOpacity: categoria === 'residencia' ? 0.55 : 0.9,
    };
}

const ESTILO_CAMADA_CIDADE = {
    muralha: { color: '#d4a017', weight: 3, opacity: 0.9 },
    rua: estiloRua,
    quarteirao: { color: '#888', weight: 1, opacity: 0.4, fillOpacity: 0.04 },
    praca: { color: '#2ecc71', weight: 1, opacity: 0.6, fillOpacity: 0.25 },
    // Q01 (docs/PLANO_CIDADE_VIVA.md): o miolo da quadra que não é lote — horta, poço,
    // quintal comum. Sem contorno próprio (o do quarteirão já marca o limite).
    patio: { color: '#2ecc71', weight: 0, opacity: 0, fillOpacity: 0.18 },
    // D3 do DIAGNOSTICO_V3: lote nunca tinha estilo porque a camada nunca era registrada.
    // Mais fino que quarteirao (é o lote individual dentro dele).
    lote: { color: '#6a5acd', weight: 0.5, opacity: 0.35, fillOpacity: 0.06 },
    edificio: estiloEdificio,
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

    // Fase 4: as camadas de detalhe de cidade viram UM grupo — um toggle só
    // ("🏛️ Detalhe da Cidade"), não um checkbox por camada pra ligar/desligar toda vez.
    const grupoDetalheCidade = L.layerGroup();
    CAMADAS_DETALHE_CIDADE.forEach(nome => {
        const opcoes = ESTILO_CAMADA_CIDADE[nome] ? { style: ESTILO_CAMADA_CIDADE[nome] } : {};
        opcoes.pointToLayer = (feature, latlng) => criarMarcadorDetalheCidade(feature, latlng, nome);
        // E3: `edificio` é Polygon agora — pointToLayer não é chamado pra ele, então o
        // popup (nome/tipo/bairro) precisa vir de onEachFeature, o caminho que L.geoJSON
        // usa pra qualquer geometria, não só Point.
        if (nome === 'edificio') {
            opcoes.onEachFeature = (feature, layer) => {
                const props = feature.properties || {};
                layer.bindPopup(`
                    <strong>${props.nome || 'Edifício'}</strong><br>
                    <span style="opacity:0.8">${props.tipo_local || ''}${props.bairro ? ' · ' + props.bairro : ''}</span>
                `);
            };
        }
        const layer = L.geoJSON(null, opcoes);
        leafletCamadasVetoriais[nome] = layer;
        layer.addTo(grupoDetalheCidade);
    });
    // O rótulo cita o menor zoom_min de todas as camadas e tamanhos — é o primeiro momento
    // em que QUALQUER cidade desenha alguma coisa. Calculado, não escrito à mão.
    const zoomsConhecidos = Object.values(leafletZoomMinCidade).flatMap(t => Object.values(t));
    const zoomEntrada = zoomsConhecidos.length > 0 ? Math.min(...zoomsConhecidos) : 9;
    overlays[`🏛️ Detalhe da Cidade (zoom ${zoomEntrada}+)`] = grupoDetalheCidade;
    // D3 do DIAGNOSTICO_V3: o grupo entra LIGADO. As camadas internas já têm zoom_min
    // (nada é desenhado em zoom baixo), então ligar por padrão não custa nada em
    // performance e é a única forma do usuário descobrir que a cidade existe.
    grupoDetalheCidade.addTo(leafletMap);

    if (leafletControlCamadas) leafletMap.removeControl(leafletControlCamadas);
    leafletControlCamadas = L.control.layers(null, overlays, { collapsed: false }).addTo(leafletMap);
}

function criarMarcadorDetalheCidade(feature, latlng, camada) {
    const props = feature.properties || {};

    // `edificio` virou Polygon (E3) — este `pointToLayer` só é chamado pra geometrias
    // Point (portao, torre); o estilo/popup de edificio agora vive em
    // ESTILO_CAMADA_CIDADE.edificio e no onEachFeature de criarCamadasVetoriaisLeaflet.
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

    // Os zooms vêm da tabela do servidor, por tamanho de cidade — uma cidade grande abre
    // as ruas 2 níveis antes de uma pequena, então não existe um número único pra citar.
    const zoomsCidade = leafletZoomMinCidade[props.tamanho] || {};
    const zoomRua = zoomsCidade.rua;
    const zoomEdificio = zoomsCidade.edificio;
    const dicaZoom = (zoomRua && zoomEdificio)
        ? `Zoom ${zoomRua}+ para ver as ruas · zoom ${zoomEdificio}+ para ver os edifícios (duplo-clique aqui pra ir direto)`
        : 'Aproxime para ver as ruas e os edifícios (duplo-clique aqui pra ir direto)';

    marker.bindPopup(`
        <strong>${props.nome || 'Sem nome'}</strong><br>
        <span style="opacity:0.8">${props.tipo || ''}${props.tamanho ? ' · ' + props.tamanho : ''}</span><br>
        ${props.continente ? `<span style="opacity:0.6; font-size:0.85rem;">${props.continente}</span><br>` : ''}
        ${props.descricao ? `<p style="margin-top:6px;">${props.descricao}</p>` : ''}
        <p style="margin-top:6px; opacity:0.7; font-size:0.8rem;">${dicaZoom}</p>
    `);

    // D3 do DIAGNOSTICO_V3, Passo 3: nada no marcador indicava que aproximar revela uma
    // cidade inteira. Duplo-clique leva direto ao zoom onde os edifícios já aparecem —
    // antes era um 13 fixo, que para uma cidade pequena ainda mostrava só as ruas.
    marker.on('dblclick', (e) => {
        L.DomEvent.stopPropagation(e);
        leafletMap.flyTo(latlng, Math.min(zoomEdificio || 13, leafletZoomMaximo));
    });

    return marker;
}

async function carregarFeaturesVisiveisLeaflet() {
    if (!leafletMap || Object.keys(leafletCamadasVetoriais).length === 0) return;

    // A bbox vai em px de mundo FRACIONÁRIO. Arredondar para inteiro (o que esta função
    // fazia) colapsava a janela num ponto de área zero assim que o zoom passava de ~10,
    // porque aí a viewport inteira cabe dentro de um px de mundo. Sobreviviam só as
    // feições cuja própria caixa englobava aquele ponto exato — muralha, praça e ruas —,
    // e nunca os edifícios, torres e portões, que são pontos em coordenada quebrada. Pior:
    // os dois filtros não tinham interseção, já que edifício pede zoom >= 13 e uma bbox
    // utilizável exigia zoom <= 9. Nenhum zoom mostrava a cidade construída.
    const bounds = leafletMap.getBounds();
    const sw = latLngParaPixelExato(bounds.getSouthWest());
    const ne = latLngParaPixelExato(bounds.getNorthEast());
    const x0 = Math.min(sw.x, ne.x), x1 = Math.max(sw.x, ne.x);
    const y0 = Math.min(sw.y, ne.y), y1 = Math.max(sw.y, ne.y);
    // floor, não round: com zoomSnap 0.25, arredondar acendia a camada meio nível antes do
    // seu zoom_min, desenhando geometria numa escala em que ela ainda vira borrão.
    const z = Math.floor(leafletMap.getZoom());

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
