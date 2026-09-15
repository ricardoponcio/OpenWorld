/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): desenho do mapa em canvas — extraído
 * de mapa_composto.js.
 */
import { Modo } from './constantes.js';
import { canvas, ctx, estado, img, mundoParaImagemCidade } from './mapa_composto_estado.js';

// Animation State (sem chamador hoje — mantido, R-B10 do 10_PLANO_REFATORACAO.md já
// deixou funções assim de propósito em outros módulos).
export function lerp(start, end, amt) {
    return (1 - amt) * start + amt * end;
}

// Render pipeline
export function draw() {
    ctx.fillStyle = '#060810';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, estado.offsetX, estado.offsetY, img.width * estado.scale, img.height * estado.scale);

    if (estado.currentMode === Modo.GLOBAL) {
        drawGlobalMarkers();
    }

    if (estado.currentMode === Modo.CONTINENTE) {
        drawContinentMarkers();
    }

    if (estado.currentMode === Modo.CIDADE) {
        drawCityGridAndEntities();
        drawCityLegend();
    }

    drawTooltip();
}

export function drawCityLegend() {
    const legendX = 10;
    const legendY = 10;

    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(legendX, legendY, 150, 100);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.strokeRect(legendX, legendY, 150, 100);

    ctx.font = '12px Outfit, sans-serif';

    // Male
    ctx.beginPath(); ctx.arc(legendX + 15, legendY + 20, 4, 0, 2*Math.PI);
    ctx.fillStyle = '#4169E1'; ctx.fill();
    ctx.fillStyle = '#fff'; ctx.fillText('Habitante (M)', legendX + 30, legendY + 24);

    // Female
    ctx.beginPath(); ctx.arc(legendX + 15, legendY + 40, 4, 0, 2*Math.PI);
    ctx.fillStyle = '#FF69B4'; ctx.fill();
    ctx.fillStyle = '#fff'; ctx.fillText('Habitante (F)', legendX + 30, legendY + 44);

    // House
    ctx.fillStyle = '#8B4513'; ctx.fillRect(legendX + 10, legendY + 55, 10, 10);
    ctx.fillStyle = '#fff'; ctx.fillText('Residência', legendX + 30, legendY + 64);

    // Work/Social
    ctx.fillStyle = '#D2691E'; ctx.fillRect(legendX + 10, legendY + 75, 10, 10);
    ctx.fillStyle = '#fff'; ctx.fillText('Comércio/Social', legendX + 30, legendY + 84);
}

export function drawTooltip() {
    if (!estado.hoveredTooltip) return;

    ctx.font = '12px Outfit, sans-serif';
    const lines = estado.hoveredTooltip.split('\n');
    let maxWidth = 0;
    lines.forEach(l => {
        const w = ctx.measureText(l).width;
        if (w > maxWidth) maxWidth = w;
    });

    const boxW = maxWidth + 20;
    const boxH = lines.length * 16 + 10;

    let tx = estado.mouseX + 15;
    let ty = estado.mouseY + 15;
    if (tx + boxW > canvas.width) tx = estado.mouseX - boxW - 5;
    if (ty + boxH > canvas.height) ty = estado.mouseY - boxH - 5;

    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(tx, ty, boxW, boxH);
    ctx.strokeStyle = 'var(--accent)';
    ctx.lineWidth = 1;
    ctx.strokeRect(tx, ty, boxW, boxH);

    ctx.fillStyle = '#fff';
    lines.forEach((l, i) => {
        ctx.fillText(l, tx + 10, ty + 20 + (i * 16));
    });
}

export function animateLoop() {
    draw();
    if (estado.isAnimating) {
        requestAnimationFrame(animateLoop);
    }
}

// D7 do DIAGNOSTICO_V3 (2026-09-11), Seção 9.5 Passo 4: nesta janela REGIONAL (~190km de
// raio) todos os locais de uma cidade caem no mesmo punhado de pixels de imagem — a
// cidade inteira é sub-pixel na escala do mundo (Seção 2.4). Desenhar cada local como um
// marcador próprio empilhava 85 retângulos no mesmo lugar (era literalmente o "1px" que o
// usuário reportou). Agora é UM marcador agregado com a contagem; o layout de verdade
// (ruas/edifícios/lotes individuais) é a camada vetorial do Mapa Live (D3), que não é
// sub-pixel porque é desenhada em coordenada de mundo exata, não amostrada num raster.
export function drawCityGridAndEntities() {
    if (!estado.cityEntities.bbox) return; // ainda carregando /entities
    if (estado.cityEntities.locais.length === 0 && estado.cityEntities.npcs.length === 0) return;

    // Centroide de todos os locais (ou dos NPCs, se não houver locais) em pixel de imagem.
    const pontos = estado.cityEntities.locais.length > 0
        ? estado.cityEntities.locais.map(l => mundoParaImagemCidade(l.coordenadas[0], l.coordenadas[1]))
        : [mundoParaImagemCidade(estado.cityEntities.bbox.min_x + (estado.cityEntities.bbox.max_x - estado.cityEntities.bbox.min_x) / 2,
                                   estado.cityEntities.bbox.min_y + (estado.cityEntities.bbox.max_y - estado.cityEntities.bbox.min_y) / 2)];
    const centroX = pontos.reduce((s, p) => s + p.x, 0) / pontos.length;
    const centroY = pontos.reduce((s, p) => s + p.y, 0) / pontos.length;

    const px = estado.offsetX + centroX * estado.scale;
    const py = estado.offsetY + centroY * estado.scale;
    const raio = Math.max(6, 9 * estado.scale);

    ctx.beginPath();
    ctx.arc(px, py, raio, 0, 2 * Math.PI);
    ctx.fillStyle = '#d4a017';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#fff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🏰', px, py);

    estado.cityAggregateMarker = { x: px, y: py, raio, locais: estado.cityEntities.locais.length, npcs: estado.cityEntities.npcs.length };
}

export function drawGlobalMarkers() {
    if (!estado.cachedContinents || estado.cachedContinents.length === 0) return;

    estado.cachedContinents.forEach(c => {
        // Label do Continente
        if (c.bounding_box) {
            const centerX = (c.bounding_box.min_x + c.bounding_box.max_x) / 2;
            const centerY = (c.bounding_box.min_y + c.bounding_box.max_y) / 2;

            const px = estado.offsetX + centerX * estado.scale;
            const py = estado.offsetY + centerY * estado.scale;

            ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
            ctx.font = `bold ${Math.max(12, 16 * estado.scale)}px sans-serif`;
            const textWidth = ctx.measureText(c.nome).width;

            // Fundo do texto do continente
            ctx.fillRect(px - textWidth/2 - 6, py - 16 * estado.scale, textWidth + 12, 22 * estado.scale);

            // Texto do continente
            ctx.fillStyle = '#FFD700'; // Dourado
            ctx.textAlign = 'center';
            ctx.fillText(c.nome, px, py - 2 * estado.scale);
        }

        // Marcadores das Cidades
        if (c.cidades) {
            c.cidades.forEach(city => {
                const cx = estado.offsetX + city.x_global * estado.scale;
                const cy = estado.offsetY + city.y_global * estado.scale;

                // Pin point minúsculo da cidade no mapa mundi
                ctx.beginPath();
                ctx.arc(cx, cy, 1.5 * estado.scale, 0, 2 * Math.PI);
                ctx.fillStyle = '#ff4444';
                ctx.fill();

            });
        }
    });
}

export function drawContinentMarkers() {
    if (!estado.cachedContinents || !estado.currentContinentUuid) return;

    const cont = estado.cachedContinents.find(c => c.uuid === estado.currentContinentUuid);
    if (!cont || !cont.cidades) return;

    const minX = Math.max(0, cont.bounding_box.min_x - 20);
    const minY = Math.max(0, cont.bounding_box.min_y - 20);
    const maxX = Math.min(767, cont.bounding_box.max_x + 20);
    const maxY = Math.min(767, cont.bounding_box.max_y + 20);

    const globW = maxX - minX;
    const globH = maxY - minY;

    cont.cidades.forEach(city => {
        const relX = (city.x_global - minX) / globW;
        const relY = (city.y_global - minY) / globH;

        const cx = estado.offsetX + (relX * img.width * estado.scale);
        const cy = estado.offsetY + (relY * img.height * estado.scale);

        // Pin point da cidade
        ctx.beginPath();
        ctx.arc(cx, cy, Math.max(4, 5 * estado.scale), 0, 2 * Math.PI);
        ctx.fillStyle = '#ff4444';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = Math.max(1.5, 2 * estado.scale);
        ctx.stroke();

        // Sombra do texto da cidade
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.font = `bold ${Math.max(12, 14 * estado.scale)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText(city.nome, cx + 1, cy - 10 * estado.scale + 1);

        // Texto da cidade
        ctx.fillStyle = '#ffffff';
        ctx.fillText(city.nome, cx, cy - 10 * estado.scale);
    });
}
