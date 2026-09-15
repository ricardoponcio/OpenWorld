/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): interação (mouse, roda, zoom) do mapa
 * em canvas — extraído de mapa_composto.js.
 */
import { Modo } from './constantes.js';
import { canvas, estado, img } from './mapa_composto_estado.js';
import { draw } from './mapa_composto_desenho.js';
import { fetchTerrainInfo } from './mapa_composto_inspetor.js';

// Zoom calculations
export function adjustZoom(amount, zoomX, zoomY) {
    const oldScale = estado.scale;
    estado.scale = Math.min(8.0, Math.max(estado.minScale, estado.scale + amount));

    estado.offsetX = zoomX - (zoomX - estado.offsetX) * (estado.scale / oldScale);
    estado.offsetY = zoomY - (zoomY - estado.offsetY) * (estado.scale / oldScale);

    draw();
}

// Sem chamador hoje (R-B10 do 10_PLANO_REFATORACAO.md já deixou funções assim de
// propósito em outros módulos) — mantida, não apagada.
export function isClickInCity(x, y, cityX, cityY) {
    const cx = estado.offsetX + cityX * estado.scale;
    const cy = estado.offsetY + cityY * estado.scale;
    const distance = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
    return distance <= 10 * estado.scale; // Area clicável da cidade
}

// Panning listeners
function aoPressionarBotaoCanvas(e) {
    estado.isDragging = true;
    estado.startX = e.clientX - estado.offsetX;
    estado.startY = e.clientY - estado.offsetY;
}

function aoSoltarBotaoJanela() {
    estado.isDragging = false;
}

function aoMoverMouseCanvas(e) {
    if (estado.isDragging) {
        estado.offsetX = e.clientX - estado.startX;
        estado.offsetY = e.clientY - estado.startY;
        draw();
    } else {
        // Interactive Land Inspection
        const rect = canvas.getBoundingClientRect();
        const canvasX = e.clientX - rect.left;
        const canvasY = e.clientY - rect.top;

        estado.mouseX = canvasX;
        estado.mouseY = canvasY;

        // Map coordinates back to actual image space
        const originalX = Math.floor((canvasX - estado.offsetX) / estado.scale);
        const originalY = Math.floor((canvasY - estado.offsetY) / estado.scale);

        // Tooltip logic for the aggregated city marker (D7 do DIAGNOSTICO_V3: um marcador
        // só, não mais um hit-test por local/NPC individual — eles são sub-pixel aqui).
        estado.hoveredTooltip = null;
        if (estado.currentMode === Modo.CIDADE && estado.cityAggregateMarker) {
            const m = estado.cityAggregateMarker;
            const dist = Math.hypot(canvasX - m.x, canvasY - m.y);
            if (dist < m.raio + 4) {
                estado.hoveredTooltip = `🏰 ${estado.currentCityNome}\n${m.locais} locais · ${m.npcs} NPCs\nVeja o Mapa Live (🗾) pra ruas e edifícios`;
            }
        }

        // Validate boundaries
        if (originalX >= 0 && originalX < img.width && originalY >= 0 && originalY < img.height) {
            if (originalX !== estado.lastInspectedX || originalY !== estado.lastInspectedY) {
                estado.lastInspectedX = originalX;
                estado.lastInspectedY = originalY;
                fetchTerrainInfo(originalX, originalY);
            }
        }
    }
}

// Wheel Zoom Listener
function aoRodarRodaCanvas(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const zoomX = e.clientX - rect.left;
    const zoomY = e.clientY - rect.top;
    const delta = e.deltaY < 0 ? 0.5 : -0.5;
    adjustZoom(delta, zoomX, zoomY);
}

// Control buttons
function aoClicarZoomIn() {
    adjustZoom(0.5, canvas.width / 2, canvas.height / 2);
}

function aoClicarZoomOut() {
    adjustZoom(-0.5, canvas.width / 2, canvas.height / 2);
}

function aoClicarZoomReset() {
    estado.scale = estado.minScale;
    estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
    estado.offsetY = (canvas.height - img.height * estado.scale) / 2;
    draw();
}

// F01/F05 (docs/16_PLANO_PAINEL_E_IA.md): registra os listeners — chamado por
// iniciarMapaComposto() (mapa_composto.js), nada de efeito colateral por importar.
export function iniciarInteracaoMapaComposto() {
    canvas.addEventListener('mousedown', aoPressionarBotaoCanvas);
    window.addEventListener('mouseup', aoSoltarBotaoJanela);
    canvas.addEventListener('mousemove', aoMoverMouseCanvas);
    canvas.addEventListener('wheel', aoRodarRodaCanvas, { passive: false });

    document.getElementById('btnZoomIn').addEventListener('click', aoClicarZoomIn);
    document.getElementById('btnZoomOut').addEventListener('click', aoClicarZoomOut);
    document.getElementById('btnZoomReset').addEventListener('click', aoClicarZoomReset);
}
