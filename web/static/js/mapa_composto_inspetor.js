/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): painel lateral de terreno (hover) do
 * mapa em canvas — extraído de mapa_composto.js.
 */
import { Modo } from './constantes.js';
import { apiCache, estado } from './mapa_composto_estado.js';
import { obterInfoMapaMundi, obterInfoContinente } from './api.js';

// Asynchronous details pipeline
export function fetchTerrainInfo(x, y) {
    const cacheKey = `${estado.currentMode}_${estado.currentContinentUuid || Modo.GLOBAL}_${x},${y}`;

    if (apiCache[cacheKey]) {
        updateSidebar(apiCache[cacheKey]);
        return;
    }

    if (estado.hoverTimeout) {
        clearTimeout(estado.hoverTimeout);
    }

    estado.hoverTimeout = setTimeout(() => {
        if (estado.abortController) {
            estado.abortController.abort();
        }
        estado.abortController = new AbortController();
        const signal = estado.abortController.signal;

        if (estado.currentMode === Modo.CIDADE) {
            // F04 (docs/16_PLANO_PAINEL_E_IA.md): dentro de uma cidade não há dado de
            // terreno por pixel de verdade (a cidade é sub-pixel na escala do mundo,
            // Seção 2.5/2.1) — nada de inventar um bioma_id/altitude/temperatura/
            // umidade (era `bioma_id: 6` "Zona Urbana", que não existe no
            // classificador Python — cartographer/math/climate.py só tem 1-5).
            updateSidebar({ x: x, y: y, zonaUrbana: true });
            return;
        }

        const promessa = estado.currentMode === Modo.GLOBAL
            ? obterInfoMapaMundi(x, y, signal)
            : obterInfoContinente(estado.currentContinentUuid, x, y, signal);

        promessa
            .then(data => {
                if (!data.error) {
                    apiCache[cacheKey] = data;
                    updateSidebar(data);
                }
            })
            .catch(err => {
                if (err.name !== 'AbortError') {
                    console.error("Erro ao inspecionar coordenada:", err);
                }
            });
    }, 30); // 30ms debounce
}

// Sidebar View Update
export function updateSidebar(data) {
    document.getElementById('lblCoord').innerText = `X: ${data.x}, Y: ${data.y}`;

    const badge = document.getElementById('lblBiomeBadge');
    if (data.zonaUrbana) {
        // F04: zona urbana não tem bioma nem métrica de terreno de verdade — mostra
        // isso, em vez de inventar números.
        badge.innerText = '🏰 Zona Urbana';
        badge.className = 'biome-badge';
        ['Altitude', 'Temperature', 'Humidity'].forEach(sufixo => {
            document.getElementById(`lbl${sufixo}`).innerText = '—';
            document.getElementById(`bar${sufixo}`).style.width = '0%';
        });
        return;
    }

    const bioma = estado.cachedBiomas[data.bioma_id];
    const badgeInfo = bioma
        ? { text: `${bioma.emoji} ${bioma.rotulo}`, class: `biome-${data.bioma_id}` }
        : { text: `❓ ${data.bioma_nome}`, class: "biome-5" };
    badge.innerText = badgeInfo.text;
    badge.className = `biome-badge ${badgeInfo.class}`;

    const altPct = Math.round(data.altitude * 100);
    const tempPct = Math.round(data.temperatura * 100);
    const humPct = Math.round(data.umidade * 100);

    document.getElementById('lblAltitude').innerText = `${altPct}%`;
    document.getElementById('barAltitude').style.width = `${altPct}%`;

    document.getElementById('lblTemperature').innerText = `${tempPct}%`;
    document.getElementById('barTemperature').style.width = `${tempPct}%`;

    document.getElementById('lblHumidity').innerText = `${humPct}%`;
    document.getElementById('barHumidity').style.width = `${humPct}%`;

    if (estado.currentMode === Modo.GLOBAL) {
        // Deprecated tile functionality removed
    }
}
