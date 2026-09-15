/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): camadas vetoriais do Mapa Live
 * (criação, marcadores, carregamento por bbox/zoom, merge de lotes alterados) —
 * extraído de mapa_leaflet.js.
 */
import { TIPO_CIDADE_EMOJI, escaparHtml } from './formatacao.js';
import { estado, latLngParaPixelExato } from './mapa_leaflet_estado.js';
import { ESTILO_CAMADA_CIDADE } from './mapa_leaflet_estilos.js';
import { obterLotesAlterados, obterFeaturesMapa } from './api.js';
import { bboxExpandida, precisaBuscarDeNovo, registrarBuscaFeita } from './mapa_recorte.js';

// M02: o JSON cru da última resposta de cada camada — clearLayers()/addData() só
// roda de novo se o conteúdo mudou (comparação por string é barata comparada ao
// custo de reconstruir milhares de elementos de canvas à toa).
const ultimaFeatureCollectionPorCamada = {};

// Fase 4 (P2.2): "detalhe_cidade" é um grupo com as 8 camadas internas de geometria de
// cidade (rua/quarteirao/muralha/torre/portao/praca/edificio/lote) — um único toggle no
// control, não 8. O grupo entra LIGADO por padrão (D3 do DIAGNOSTICO_V3, 2026-09-11: as
// camadas internas já têm zoom_min, nada é desenhado em zoom baixo, então ligar por
// padrão não custa em performance e é a única forma do usuário descobrir que a cidade
// existe). Só aparece perto o bastante (zoom_min alto, calculado em
// generate_city_geometry.py a partir do tamanho real da cidade — a cidade é sub-pixel na
// escala do mundo, Seção 2.1).
const CAMADAS_MUNDO = ['cidades', 'pois', 'estradas', 'fronteiras'];
const CAMADAS_DETALHE_CIDADE = ['muralha', 'torre', 'portao', 'praca', 'rua', 'quarteirao', 'patio', 'lote', 'edificio'];
const CAMADAS_VETORIAIS_DISPONIVEIS = [...CAMADAS_MUNDO, ...CAMADAS_DETALHE_CIDADE];
const CAMADAS_NOMES_AMIGAVEIS = { cidades: '🏰 Cidades', pois: '📍 Pontos de Interesse', estradas: '🛣️ Estradas', fronteiras: '🗺️ Fronteiras' };

export function criarCamadasVetoriaisLeaflet() {
    const overlays = {};

    CAMADAS_MUNDO.forEach(nome => {
        const layer = L.geoJSON(null, { pointToLayer: criarMarcadorFeatureLeaflet });
        estado.leafletCamadasVetoriais[nome] = layer;
        overlays[CAMADAS_NOMES_AMIGAVEIS[nome] || nome] = layer;
    });
    // Só "cidades" começa visível — as outras existem no seletor pra quando uma fase
    // futura escrever o GeoJSON correspondente (hoje ficam vazias, sem erro nenhum).
    estado.leafletCamadasVetoriais['cidades'].addTo(estado.leafletMap);

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
                // G04 (docs/16_PLANO_PAINEL_E_IA.md): "Residência Bairro Médio 42" existe
                // em várias quadras da mesma cidade (o nome não é único) — a quadra
                // desambigua qual é qual.
                layer.bindPopup(`
                    <strong>${props.nome ? escaparHtml(props.nome) : 'Edifício'}</strong><br>
                    <span class="popup-sub">${escaparHtml(props.tipo_local || '')}${props.bairro ? ' · ' + escaparHtml(props.bairro) : ''}${props.quarteirao_id ? ' · quadra ' + escaparHtml(props.quarteirao_id) : ''}</span>
                `);
            };
        }
        const layer = L.geoJSON(null, opcoes);
        estado.leafletCamadasVetoriais[nome] = layer;
        layer.addTo(grupoDetalheCidade);
    });
    // O rótulo cita o menor zoom_min de todas as camadas e tamanhos — é o primeiro momento
    // em que QUALQUER cidade desenha alguma coisa. Calculado, não escrito à mão.
    const zoomsConhecidos = Object.values(estado.leafletZoomMinCidade).flatMap(t => Object.values(t));
    const zoomEntrada = zoomsConhecidos.length > 0 ? Math.min(...zoomsConhecidos) : 9;
    overlays[`🏛️ Detalhe da Cidade (zoom ${zoomEntrada}+)`] = grupoDetalheCidade;
    // D3 do DIAGNOSTICO_V3: o grupo entra LIGADO. As camadas internas já têm zoom_min
    // (nada é desenhado em zoom baixo), então ligar por padrão não custa nada em
    // performance e é a única forma do usuário descobrir que a cidade existe.
    grupoDetalheCidade.addTo(estado.leafletMap);

    if (estado.leafletControlCamadas) estado.leafletMap.removeControl(estado.leafletControlCamadas);
    estado.leafletControlCamadas = L.control.layers(null, overlays, { collapsed: false }).addTo(estado.leafletMap);
}

function criarMarcadorDetalheCidade(feature, latlng, camada) {
    const props = feature.properties || {};

    // `edificio` virou Polygon (E3) — este `pointToLayer` só é chamado pra geometrias
    // Point (portao, torre); o estilo/popup de edificio agora vive em
    // ESTILO_CAMADA_CIDADE.edificio e no onEachFeature de criarCamadasVetoriaisLeaflet.
    if (camada === 'portao') {
        return L.circleMarker(latlng, { radius: 4, color: '#fff', weight: 1, fillColor: '#8B4513', fillOpacity: 1 })
            .bindPopup(props.nome ? escaparHtml(props.nome) : 'Portão');
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
            html: `<div class="leaflet-icone-emoji">${emoji}</div>`,
            className: 'leaflet-vector-icon',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        }),
    });

    if (props.nome) {
        // Leaflet trata o conteúdo de tooltip/popup como HTML — nome/tipo/descrição
        // podem ter vindo de geração por IA (F05, docs/16_PLANO_PAINEL_E_IA.md).
        marker.bindTooltip(escaparHtml(props.nome), {
            permanent: estado.leafletMap.getZoom() >= estado.leafletTooltipZoomMin,
            direction: 'top',
            offset: [0, -12],
            className: 'leaflet-vector-tooltip',
        });
    }

    // Os zooms vêm da tabela do servidor, por tamanho de cidade — uma cidade grande abre
    // as ruas 2 níveis antes de uma pequena, então não existe um número único pra citar.
    const zoomsCidade = estado.leafletZoomMinCidade[props.tamanho] || {};
    const zoomRua = zoomsCidade.rua;
    const zoomEdificio = zoomsCidade.edificio;
    const dicaZoom = (zoomRua && zoomEdificio)
        ? `Zoom ${zoomRua}+ para ver as ruas · zoom ${zoomEdificio}+ para ver os edifícios (duplo-clique aqui pra ir direto)`
        : 'Aproxime para ver as ruas e os edifícios (duplo-clique aqui pra ir direto)';

    marker.bindPopup(`
        <strong>${props.nome ? escaparHtml(props.nome) : 'Sem nome'}</strong><br>
        <span class="popup-sub">${escaparHtml(props.tipo || '')}${props.tamanho ? ' · ' + escaparHtml(props.tamanho) : ''}</span><br>
        ${props.continente ? `<span class="popup-continente">${escaparHtml(props.continente)}</span><br>` : ''}
        ${props.descricao ? `<p class="popup-descricao">${escaparHtml(props.descricao)}</p>` : ''}
        <p class="popup-dica-zoom">${dicaZoom}</p>
    `);

    // D3 do DIAGNOSTICO_V3, Passo 3: nada no marcador indicava que aproximar revela uma
    // cidade inteira. Duplo-clique leva direto ao zoom onde os edifícios já aparecem —
    // antes era um 13 fixo, que para uma cidade pequena ainda mostrava só as ruas.
    marker.on('dblclick', (e) => {
        L.DomEvent.stopPropagation(e);
        estado.leafletMap.flyTo(latlng, Math.min(zoomEdificio || 13, estado.leafletZoomMaximo));
    });

    return marker;
}

// T05 (docs/12_PLANO_CIDADE_VIVA.md): o GeoJSON de cidade guarda o estado do lote NA
// IMPORTAÇÃO (T03); a partir daí o BANCO é a verdade (armadilha 2) — uma casa
// construída/uma ruína durante o jogo nunca apareceria no mapa se o frontend só lesse
// o arquivo. Busca o delta por cidade visível e reescreve `properties.estado` das
// features de lote JÁ CARREGADAS, antes delas virarem camada — o estilo (`estiloLote`)
// não precisa saber que existe um banco por trás.
function _cidadesVisiveisLeaflet(x0, y0, x1, y1) {
    const ids = new Set();
    for (const cont of estado.leafletContinentesCache) {
        for (const cid of (cont.cidades || [])) {
            if (cid.cidade_id == null) continue;
            if (cid.x_global >= x0 && cid.x_global <= x1 && cid.y_global >= y0 && cid.y_global <= y1) {
                ids.add(cid.cidade_id);
            }
        }
    }
    return [...ids];
}

// M03 (docs/16_PLANO_PAINEL_E_IA.md): 0,41 s por cidade visível, a cada moveend —
// um `Map` cidade_id -> { quando, lista } evita rebuscar dentro do TTL do
// servidor (painel.mapa_lotes_alterados_cache_ms, validado em mapa_leaflet.js).
const cacheLotesAlteradosPorCidade = new Map();

async function _lotesAlteradosComCache(cidadeId) {
    const cache = cacheLotesAlteradosPorCidade.get(cidadeId);
    const agora = Date.now();
    if (cache && (agora - cache.quando) < estado.leafletLotesAlteradosCacheMs) {
        return cache.lista;
    }
    const lista = await obterLotesAlterados(cidadeId).catch(() => []);
    cacheLotesAlteradosPorCidade.set(cidadeId, { quando: agora, lista });
    return lista;
}

async function mesclarLotesAlteradosLeaflet(loteFeatureCollection, x0, y0, x1, y1) {
    const idsCidade = _cidadesVisiveisLeaflet(x0, y0, x1, y1);
    if (idsCidade.length === 0) return;

    const respostas = await Promise.all(idsCidade.map(id => _lotesAlteradosComCache(id)));
    const estadoPorId = new Map();
    for (const lista of respostas) {
        for (const item of lista) estadoPorId.set(item.id, item.estado);
    }
    if (estadoPorId.size === 0) return;

    for (const feature of (loteFeatureCollection.features || [])) {
        const novoEstado = estadoPorId.get((feature.properties || {}).id);
        if (novoEstado) feature.properties.estado = novoEstado;
    }
}

export async function carregarFeaturesVisiveisLeaflet() {
    if (!estado.leafletMap || Object.keys(estado.leafletCamadasVetoriais).length === 0) return;

    // A bbox vai em px de mundo FRACIONÁRIO. Arredondar para inteiro (o que esta função
    // fazia) colapsava a janela num ponto de área zero assim que o zoom passava de ~10,
    // porque aí a viewport inteira cabe dentro de um px de mundo. Sobreviviam só as
    // feições cuja própria caixa englobava aquele ponto exato — muralha, praça e ruas —,
    // e nunca os edifícios, torres e portões, que são pontos em coordenada quebrada. Pior:
    // os dois filtros não tinham interseção, já que edifício pede zoom >= 13 e uma bbox
    // utilizável exigia zoom <= 9. Nenhum zoom mostrava a cidade construída.
    const bounds = estado.leafletMap.getBounds();
    const sw = latLngParaPixelExato(bounds.getSouthWest());
    const ne = latLngParaPixelExato(bounds.getNorthEast());
    const x0 = Math.min(sw.x, ne.x), x1 = Math.max(sw.x, ne.x);
    const y0 = Math.min(sw.y, ne.y), y1 = Math.max(sw.y, ne.y);
    // floor, não round: com zoomSnap 0.25, arredondar acendia a camada meio nível antes do
    // seu zoom_min, desenhando geometria numa escala em que ela ainda vira borrão.
    const z = Math.floor(estado.leafletMap.getZoom());

    // M02 (docs/16_PLANO_PAINEL_E_IA.md): um pan pequeno dentro da última bbox
    // (expandida em 50%) já buscada não dispara requisição nenhuma.
    if (!precisaBuscarDeNovo(x0, y0, x1, y1, z)) return;
    const pedido = bboxExpandida(x0, y0, x1, y1);

    try {
        const camadas = CAMADAS_VETORIAIS_DISPONIVEIS.join(',');
        const data = await obterFeaturesMapa(camadas, `${pedido.x0},${pedido.y0},${pedido.x1},${pedido.y1}`, z);
        registrarBuscaFeita(pedido.x0, pedido.y0, pedido.x1, pedido.y1, z);
        if (data.lote) await mesclarLotesAlteradosLeaflet(data.lote, pedido.x0, pedido.y0, pedido.x1, pedido.y1);
        CAMADAS_VETORIAIS_DISPONIVEIS.forEach(nome => {
            const layer = estado.leafletCamadasVetoriais[nome];
            if (!layer || !data[nome]) return;
            // M02: só reconstrói a camada se o conteúdo mudou de verdade — em
            // boa parte dos moveends a bbox nova ainda cobre as mesmas features.
            const bruto = JSON.stringify(data[nome]);
            if (ultimaFeatureCollectionPorCamada[nome] === bruto) return;
            ultimaFeatureCollectionPorCamada[nome] = bruto;
            layer.clearLayers();
            layer.addData(data[nome]);
        });
    } catch (e) { console.error('Erro ao carregar camadas vetoriais do mapa:', e); }
}
