import { Modo } from './constantes.js';

const canvas = document.getElementById('mapaCanvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('canvasContainer');

// F01 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado do módulo num objeto só, não
// dezenas de `let` soltos (ARQUITETURA §10 regra 4).
const estado = {
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
const apiCache = {};

// Animation State
function lerp(start, end, amt) {
    return (1 - amt) * start + amt * end;
}

// Load the terrain image — o `src`/`onload` de verdade só é atribuído dentro de
// iniciarMapaComposto() (F01, docs/16_PLANO_PAINEL_E_IA.md): nenhum efeito colateral
// no topo do módulo, app.js decide quando iniciar.
const img = new Image();

// Render pipeline
function draw() {
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

function drawCityLegend() {
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

function drawTooltip() {
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

function animateLoop() {
    draw();
    if (estado.isAnimating) {
        requestAnimationFrame(animateLoop);
    }
}

// Fase 2.1 (P0.3): `loc.coordenadas` é pixel de MUNDO (Seção 2.3), não mais um índice
// de grade 0-40. Converte mundo -> pixel da imagem da região devolvida por
// `/api/regiao/<nome>/entities` (mesma janela que gerou a imagem em si — D7).
function mundoParaImagemCidade(x, y) {
    const bbox = estado.cityEntities.bbox;
    if (!bbox) return { x: 0, y: 0 };
    const ix = (x - bbox.min_x) / Math.max(1e-6, bbox.max_x - bbox.min_x) * bbox.largura_img;
    const iy = (y - bbox.min_y) / Math.max(1e-6, bbox.max_y - bbox.min_y) * bbox.altura_img;
    return { x: ix, y: iy };
}

// D7 do DIAGNOSTICO_V3 (2026-09-11), Seção 9.5 Passo 4: nesta janela REGIONAL (~190km de
// raio) todos os locais de uma cidade caem no mesmo punhado de pixels de imagem — a
// cidade inteira é sub-pixel na escala do mundo (Seção 2.4). Desenhar cada local como um
// marcador próprio empilhava 85 retângulos no mesmo lugar (era literalmente o "1px" que o
// usuário reportou). Agora é UM marcador agregado com a contagem; o layout de verdade
// (ruas/edifícios/lotes individuais) é a camada vetorial do Mapa Live (D3), que não é
// sub-pixel porque é desenhada em coordenada de mundo exata, não amostrada num raster.
function drawCityGridAndEntities() {
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

window.updateMapEntities = function(liveNpcs) {
    if (estado.currentMode === Modo.CIDADE) {
        const cityLocIds = new Set(estado.cityEntities.locais.map(l => l.id));
        estado.cityEntities.npcs = liveNpcs.filter(npc => cityLocIds.has(npc.loc_id));
        // Note: The animateLoop is constantly drawing, so no need to call draw() explicitly here.
    }
}

// Zoom calculations
function adjustZoom(amount, zoomX, zoomY) {
    const oldScale = estado.scale;
    estado.scale = Math.min(8.0, Math.max(estado.minScale, estado.scale + amount));

    estado.offsetX = zoomX - (zoomX - estado.offsetX) * (estado.scale / oldScale);
    estado.offsetY = zoomY - (zoomY - estado.offsetY) * (estado.scale / oldScale);

    draw();
}

// Panning listeners — F01 (docs/16_PLANO_PAINEL_E_IA.md): viram declarações nomeadas
// aqui (sem efeito colateral) e são registradas dentro de iniciarMapaComposto().
function aoPressionarBotaoCanvas(e) {
    estado.isDragging = true;
    estado.startX = e.clientX - estado.offsetX;
    estado.startY = e.clientY - estado.offsetY;
}

function aoSoltarBotaoJanela() {
    estado.isDragging = false;
}

function isClickInCity(x, y, cityX, cityY) {
    const cx = estado.offsetX + cityX * estado.scale;
    const cy = estado.offsetY + cityY * estado.scale;
    const distance = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
    return distance <= 10 * estado.scale; // Area clicável da cidade
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

// Asynchronous details pipeline
function fetchTerrainInfo(x, y) {
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

        const url = estado.currentMode === Modo.GLOBAL 
            ? `/api/mapa_composto/info/${x}/${y}` 
            : `/api/continente/${estado.currentContinentUuid}/info/${x}/${y}`;

        fetch(url, { signal })
            .then(res => res.json())
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
function updateSidebar(data) {
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

// Load Continents from API
function loadContinents() {
    fetch('/api/continentes')
        .then(res => res.json())
        .then(data => {
            estado.cachedContinents = data.continentes || [];
            estado.cachedBiomas = data.biomas || {};
            draw(); // Redraw map to show markers

            const container = document.getElementById('continents-list-container');
            container.innerHTML = '';
            
            data.continentes.forEach(c => {
                const wrapper = document.createElement('div');
                wrapper.className = 'continent-wrapper';

                const btn = document.createElement('button');
                btn.className = 'continent-btn';
                btn.id = `btn-c-${c.uuid}`;
                
                const emoji = c.area_real_km2 > 50000 ? '🏔️' : '🏝️';
                const statusText = c.gerado ? 'Zoom Pronto' : 'Gerar Zoom';
                
                btn.innerHTML = `
                    <span class="continent-emoji">${emoji}</span>
                    <span class="continent-details">
                        <span class="continent-name">${c.nome}</span>
                        <span class="continent-info-small">${c.area_real_km2.toLocaleString()} km²</span>
                    </span>
                    <span class="continent-status">${statusText}</span>
                `;
                
                btn.addEventListener('click', () => selectContinent(c.uuid, c.nome, btn));
                wrapper.appendChild(btn);

                // Cidades Nested
                if (c.cidades && c.cidades.length > 0) {
                    const citiesDiv = document.createElement('div');
                    citiesDiv.className = 'cities-list';
                    citiesDiv.style.paddingLeft = '20px';
                    citiesDiv.style.borderLeft = '2px solid rgba(255,255,255,0.1)';
                    citiesDiv.style.marginLeft = '12px';
                    citiesDiv.style.marginBottom = '10px';
                    
                    c.cidades.forEach(cid => {
                        const cidBtn = document.createElement('button');
                        cidBtn.className = 'continent-btn city-btn';
                        cidBtn.style.padding = '0.4rem 0.6rem';
                        cidBtn.style.marginTop = '4px';
                        cidBtn.innerHTML = `
                            <span class="continent-emoji">🏰</span>
                            <span class="continent-details">
                                <span class="continent-name" style="font-size: 0.85rem">${cid.nome}</span>
                                <span class="continent-info-small">${cid.tamanho} | ${cid.tipo}</span>
                            </span>
                        `;
                        cidBtn.addEventListener('click', () => selectCity(cid.nome, cidBtn, c.nome));
                        citiesDiv.appendChild(cidBtn);
                    });
                    wrapper.appendChild(citiesDiv);
                }

                container.appendChild(wrapper);
            });
        })
        .catch(err => console.error("Erro ao carregar continentes:", err));
}

// Select Continent Action
function selectContinent(uuid, nome, btnElement) {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-global-map').classList.remove('active');
    btnElement.classList.add('active');
    btnElement.classList.add('loading');
    
    const statusSpan = btnElement.querySelector('.continent-status');
    const originalStatus = statusSpan.innerText;
    statusSpan.innerText = 'Processando...';

    estado.currentMode = Modo.CONTINENTE;
    estado.currentContinentUuid = uuid;

    document.getElementById('status-mapa').innerText = `⏳ Gerando/Carregando ${nome}...`;
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = `/api/continente/${uuid}/imagem`;
    
    img.onload = function() {
        btnElement.classList.remove('loading');
        statusSpan.innerText = 'Zoom Pronto';
        
        canvas.width = 600;
        canvas.height = 600;
        
        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;
        
        draw();

        // UI adjustments for Continent Mode
        document.getElementById('status-mapa').innerText = `🟢 Continente: ${nome} (Zoom)`;
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';
        
        document.getElementById('lblInspectorTitle').innerText = `🔍 Relevo - ${nome}`;
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'block';

        document.getElementById('lblInstructionTitle').innerText = `🏔️ Alta Resolução (ROI Zoom):`;
        document.getElementById('lblInstructionTip1').innerText = `• Mapa ampliado dinamicamente para 1200x1200px.`;
        document.getElementById('lblInstructionTip2').innerText = `• Processamento avançado de micro-fraturas e detalhes costeiros.`;
    };
}

// Select City Action
function selectCity(nome, btnElement, continenteNome) {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-global-map').classList.remove('active');
    btnElement.classList.add('active');
    btnElement.classList.add('loading');
    
    estado.currentMode = Modo.CIDADE;
    estado.currentCityNome = nome;
    estado.currentContinentUuid = null;

    document.getElementById('status-mapa').innerText = `⏳ Gerando/Carregando ${nome}...`;
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    // D7 do DIAGNOSTICO_V3 (2026-09-11): renomeado de /api/cidade/ para /api/regiao/ —
    // esta view mostra ONDE a cidade fica no continente (~190km de raio), não o que tem
    // dentro dela. A vista urbana de verdade (ruas/edifícios/lotes) é a camada vetorial
    // do Mapa Live (aba 🗾, corrigida no D3) — ela não perde qualidade ao ampliar.
    img.src = `/api/regiao/${nome}/imagem`;

    img.onload = function() {
        btnElement.classList.remove('loading');

        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        estado.npcAnimations = {};
        if (!estado.isAnimating) {
            estado.isAnimating = true;
            animateLoop();
        }

        fetch(`/api/regiao/${nome}/entities`)
            .then(res => res.json())
            .then(data => {
                if (!data.error) {
                    estado.cityEntities = data;
                    draw();
                }
            });

        document.getElementById('status-mapa').innerText = `🌍 Região de ${nome} (a cidade é o ponto no centro — veja o Mapa Live pra ruas e edifícios)`;
        document.getElementById('status-mapa').style.borderColor = '#00ffcc';
        document.getElementById('status-mapa').style.color = '#00ffcc';

        document.getElementById('lblInspectorTitle').innerText = `🔍 Relevo Regional - ${nome}`;
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'none';

        document.getElementById('lblInstructionTitle').innerText = `🏰 Alta Resolução (City Zoom):`;
        document.getElementById('lblInstructionTip1').innerText = `• Mapa focado ampliado dinamicamente.`;
        document.getElementById('lblInstructionTip2').innerText = `• Preparado para receber marcadores e construções da Engine.`;
    };
}

// Global Map select
function aoClicarMapaGlobal() {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');

    estado.currentMode = Modo.GLOBAL;
    estado.currentContinentUuid = null;
    estado.currentCityNome = null;
    estado.cityEntities = { locais: [], npcs: [], bbox: null };

    document.getElementById('status-mapa').innerText = '⏳ Sincronizando Mapa Mundi...';
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = '/api/mapa_composto/imagem';

    img.onload = function() {
        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        estado.isAnimating = false;
        draw();

        document.getElementById('status-mapa').innerText = '🟢 Mapa Mundi Global (768x768)';
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';

        document.getElementById('lblInspectorTitle').innerText = '🔍 Inspetor do Mapa Mundi';
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'block';

        document.getElementById('lblInstructionTitle').innerText = '💡 Visualização do Mapa Mundi:';
        document.getElementById('lblInstructionTip1').innerText = '• Cada tile do mapa composto possui tamanho fixo de 256x256 pixels.';
        document.getElementById('lblInstructionTip2').innerText = '• Ao passar o mouse, a grade acima acende mostrando qual tile você está inspecionando.';
    };
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

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// app.js — nada de efeito colateral disparado só por importar este módulo.
export function iniciarMapaComposto() {
    canvas.addEventListener('mousedown', aoPressionarBotaoCanvas);
    window.addEventListener('mouseup', aoSoltarBotaoJanela);
    canvas.addEventListener('mousemove', aoMoverMouseCanvas);
    canvas.addEventListener('wheel', aoRodarRodaCanvas, { passive: false });

    document.getElementById('btn-global-map').addEventListener('click', aoClicarMapaGlobal);
    document.getElementById('btnZoomIn').addEventListener('click', aoClicarZoomIn);
    document.getElementById('btnZoomOut').addEventListener('click', aoClicarZoomOut);
    document.getElementById('btnZoomReset').addEventListener('click', aoClicarZoomReset);

    img.onload = function() {
        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;

        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        draw();
    };
    img.src = '/api/mapa_composto/imagem';

    loadContinents();
}

function drawGlobalMarkers() {
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

function drawContinentMarkers() {
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
