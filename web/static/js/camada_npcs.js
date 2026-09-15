/**
 * M04 (docs/16_PLANO_PAINEL_E_IA.md): NPCs se locomovendo no Mapa Live — pedido
 * explícito do dono do projeto (Seção 1.1). Consulta /api/mapa/npcs por bbox
 * visível a cada `painel.mapa_npcs_polling_ms` e anima cada ponto da posição
 * anterior à nova (requestAnimationFrame) — só com a aba 🗾 visível e o zoom
 * acima do mínimo (painel.mapa_npcs_zoom_min).
 */
import { Aba } from './constantes.js';
import { COR_ACAO_PADRAO, COR_POR_ACAO, escaparHtml } from './formatacao.js';
import { obterPosicoesNpcs } from './api.js';
import { estado, latLngParaPixelExato, pixelParaLatLng } from './mapa_leaflet_estado.js';
import { estado as estadoDashboard } from './estado_dashboard.js';
import { abrirFicha } from './ficha_npc.js';

let grupo = null;
// id -> { marker, de: L.LatLng, para: L.LatLng, inicio: DOMHighResTimeStamp }
const marcadoresPorId = new Map();
let animando = false;

function corDaAcao(acao) {
    return COR_POR_ACAO[acao] || COR_ACAO_PADRAO;
}

function passoAnimacao() {
    const agora = performance.now();
    let algumEmTransicao = false;
    for (const entrada of marcadoresPorId.values()) {
        const t = Math.min(1, (agora - entrada.inicio) / estado.leafletMapaNpcsPollingMs);
        if (t < 1) algumEmTransicao = true;
        entrada.marker.setLatLng([
            entrada.de.lat + (entrada.para.lat - entrada.de.lat) * t,
            entrada.de.lng + (entrada.para.lng - entrada.de.lng) * t,
        ]);
    }
    if (algumEmTransicao) {
        requestAnimationFrame(passoAnimacao);
    } else {
        animando = false;
    }
}

function atualizarPosicoes(npcs) {
    const agora = performance.now();
    const idsVistos = new Set();

    npcs.forEach(n => {
        idsVistos.add(n.id);
        const novaLatLng = pixelParaLatLng(n.x, n.y);
        let entrada = marcadoresPorId.get(n.id);

        if (!entrada) {
            // Novo nasce já na posição — não anima do zero.
            const marker = L.circleMarker(novaLatLng, {
                radius: 5, weight: 1, color: '#000', fillColor: corDaAcao(n.acao), fillOpacity: 1,
            });
            marker.on('click', () => abrirFicha(n.id));
            marker.addTo(grupo);
            entrada = { marker, de: novaLatLng, para: novaLatLng, inicio: agora };
            marcadoresPorId.set(n.id, entrada);
        } else {
            entrada.de = entrada.marker.getLatLng(); // onde o ponto está visualmente AGORA
            entrada.para = novaLatLng;
            entrada.inicio = agora;
            entrada.marker.setStyle({ fillColor: corDaAcao(n.acao) });
        }
        entrada.marker.bindTooltip(escaparHtml(n.nome), { direction: 'top', offset: [0, -6] });
    });

    // NPC que sumiu da resposta (morreu, saiu da bbox, saiu do local) é removido.
    for (const [id, entrada] of marcadoresPorId) {
        if (!idsVistos.has(id)) {
            grupo.removeLayer(entrada.marker);
            marcadoresPorId.delete(id);
        }
    }

    if (!animando && marcadoresPorId.size > 0) {
        animando = true;
        requestAnimationFrame(passoAnimacao);
    }
}

function mostrarAvisoTruncado(mostrar) {
    const container = document.getElementById('mapa-leaflet-container');
    let aviso = document.getElementById('mapa-npcs-truncado');
    if (mostrar && !aviso) {
        aviso = document.createElement('div');
        aviso.id = 'mapa-npcs-truncado';
        aviso.className = 'mapa-npcs-aviso-truncado';
        aviso.innerText = '🚶 Mostrando os habitantes mais próximos — aproxime para ver o resto.';
        container.appendChild(aviso);
    } else if (!mostrar && aviso) {
        aviso.remove();
    }
}

function limparCamada() {
    marcadoresPorId.forEach(entrada => grupo.removeLayer(entrada.marker));
    marcadoresPorId.clear();
    mostrarAvisoTruncado(false);
}

async function consultarPosicoes() {
    if (!estado.leafletMap || estadoDashboard.activeView !== Aba.MAPA_LIVE) return;

    const zoom = estado.leafletMap.getZoom();
    if (zoom < estado.leafletMapaNpcsZoomMin) {
        if (marcadoresPorId.size > 0) limparCamada();
        return;
    }

    const bounds = estado.leafletMap.getBounds();
    const sw = latLngParaPixelExato(bounds.getSouthWest());
    const ne = latLngParaPixelExato(bounds.getNorthEast());
    const x0 = Math.min(sw.x, ne.x), x1 = Math.max(sw.x, ne.x);
    const y0 = Math.min(sw.y, ne.y), y1 = Math.max(sw.y, ne.y);

    try {
        const data = await obterPosicoesNpcs(`${x0},${y0},${x1},${y1}`, Math.floor(zoom));
        atualizarPosicoes(data.npcs || []);
        mostrarAvisoTruncado(!!data.truncado);
    } catch (e) { console.error('Erro ao carregar posições de NPCs:', e); }
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// mapa_leaflet.js (depois que o mapa e o control de camadas já existem).
export function iniciarCamadaNpcs() {
    grupo = L.layerGroup();
    grupo.addTo(estado.leafletMap); // ligada por padrão
    if (estado.leafletControlCamadas) {
        estado.leafletControlCamadas.addOverlay(grupo, '🚶 Habitantes');
    }
    setInterval(consultarPosicoes, estado.leafletMapaNpcsPollingMs);
}
