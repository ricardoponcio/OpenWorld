const canvas = document.getElementById('mapaCanvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('canvasContainer');

// Mode & State variables
let currentMode = 'global'; // 'global' ou 'continent'
let currentContinentUuid = null;
let scale = 1.0;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let startX = 0;
let startY = 0;
let lastInspectedX = -1;
let lastInspectedY = -1;
let minScale = 1.0;

// Query memory cache
const apiCache = {};

// Load the terrain image
const img = new Image();
img.src = '/api/mapa_composto/imagem';

img.onload = function() {
    canvas.width = 600;
    canvas.height = 600;
    
    minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
    scale = minScale;
    
    offsetX = (canvas.width - img.width * scale) / 2;
    offsetY = (canvas.height - img.height * scale) / 2;
    
    draw();
};

// Render pipeline
function draw() {
    ctx.fillStyle = '#060810';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, offsetX, offsetY, img.width * scale, img.height * scale);
}

// Zoom calculations
function adjustZoom(amount, zoomX, zoomY) {
    const oldScale = scale;
    scale = Math.min(8.0, Math.max(minScale, scale + amount));

    offsetX = zoomX - (zoomX - offsetX) * (scale / oldScale);
    offsetY = zoomY - (zoomY - offsetY) * (scale / oldScale);

    draw();
}

// Panning listeners
canvas.addEventListener('mousedown', function(e) {
    isDragging = true;
    startX = e.clientX - offsetX;
    startY = e.clientY - offsetY;
});

window.addEventListener('mouseup', function() {
    isDragging = false;
});

canvas.addEventListener('mousemove', function(e) {
    if (isDragging) {
        offsetX = e.clientX - startX;
        offsetY = e.clientY - startY;
        draw();
    } else {
        // Interactive Land Inspection
        const rect = canvas.getBoundingClientRect();
        const canvasX = e.clientX - rect.left;
        const canvasY = e.clientY - rect.top;

        // Map coordinates back to actual image space
        const originalX = Math.floor((canvasX - offsetX) / scale);
        const originalY = Math.floor((canvasY - offsetY) / scale);

        // Validate boundaries
        if (originalX >= 0 && originalX < img.width && originalY >= 0 && originalY < img.height) {
            if (originalX !== lastInspectedX || originalY !== lastInspectedY) {
                lastInspectedX = originalX;
                lastInspectedY = originalY;
                fetchTerrainInfo(originalX, originalY);
            }
        }
    }
});

// Wheel Zoom Listener
canvas.addEventListener('wheel', function(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const zoomX = e.clientX - rect.left;
    const zoomY = e.clientY - rect.top;
    const delta = e.deltaY < 0 ? 0.5 : -0.5;
    adjustZoom(delta, zoomX, zoomY);
}, { passive: false });

// Asynchronous details pipeline
let hoverTimeout = null;
let abortController = null;

function fetchTerrainInfo(x, y) {
    const cacheKey = `${currentMode}_${currentContinentUuid || 'global'}_${x},${y}`;
    
    if (apiCache[cacheKey]) {
        updateSidebar(apiCache[cacheKey]);
        return;
    }

    if (hoverTimeout) {
        clearTimeout(hoverTimeout);
    }

    hoverTimeout = setTimeout(() => {
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();
        const signal = abortController.signal;

        const url = currentMode === 'global' 
            ? `/api/mapa_composto/info/${x}/${y}` 
            : `/api/continente/${currentContinentUuid}/info/${x}/${y}`;

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
    
    const biomeBadges = {
        1: { text: "🌊 Oceano", class: "biome-1" },
        2: { text: "🏜️ Deserto", class: "biome-2" },
        3: { text: "🌱 Mediterrâneo", class: "biome-3" },
        4: { text: "🌲 Floresta Temperada", class: "biome-4" },
        5: { text: "🏔️ Montanha", class: "biome-5" }
    };

    const badgeInfo = biomeBadges[data.bioma_id] || { text: `❓ ${data.bioma_nome}`, class: "biome-5" };
    const badge = document.getElementById('lblBiomeBadge');
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

    if (currentMode === 'global') {
        document.querySelectorAll('.tile-cell').forEach(cell => cell.classList.remove('active'));
        const activeCell = document.getElementById(`tile-${data.tile_x}-${data.tile_y}`);
        if (activeCell) activeCell.classList.add('active');
    }
}

// Load Continents from API
function loadContinents() {
    fetch('/api/continentes')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('continents-list-container');
            container.innerHTML = '';
            
            data.continentes.forEach(c => {
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
                container.appendChild(btn);
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

    currentMode = 'continent';
    currentContinentUuid = uuid;

    document.getElementById('status-mapa').innerText = `⏳ Gerando/Carregando ${nome}...`;
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = `/api/continente/${uuid}/imagem`;
    
    img.onload = function() {
        btnElement.classList.remove('loading');
        statusSpan.innerText = 'Zoom Pronto';
        
        canvas.width = 600;
        canvas.height = 600;
        
        minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        scale = minScale;
        offsetX = (canvas.width - img.width * scale) / 2;
        offsetY = (canvas.height - img.height * scale) / 2;
        
        draw();

        // UI adjustments for Continent Mode
        document.getElementById('status-mapa').innerText = `🟢 Continente: ${nome} (Zoom)`;
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';
        
        document.getElementById('lblInspectorTitle').innerText = `🔍 Relevo - ${nome}`;
        document.getElementById('tileGridContainer').style.display = 'none';

        document.getElementById('lblInstructionTitle').innerText = `🏔️ Alta Resolução (ROI Zoom):`;
        document.getElementById('lblInstructionTip1').innerText = `• Mapa ampliado dinamicamente para 1200x1200px.`;
        document.getElementById('lblInstructionTip2').innerText = `• Processamento avançado de micro-fraturas e detalhes costeiros.`;
    };
}

// Global Map select
document.getElementById('btn-global-map').addEventListener('click', function() {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');

    currentMode = 'global';
    currentContinentUuid = null;

    document.getElementById('status-mapa').innerText = '⏳ Sincronizando Mapa Mundi...';
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = '/api/mapa_composto/imagem';

    img.onload = function() {
        canvas.width = 600;
        canvas.height = 600;
        
        minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        scale = minScale;
        offsetX = (canvas.width - img.width * scale) / 2;
        offsetY = (canvas.height - img.height * scale) / 2;
        
        draw();

        document.getElementById('status-mapa').innerText = '🟢 Mapa Mundi Global (768x768)';
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';

        document.getElementById('lblInspectorTitle').innerText = '🔍 Inspetor do Mapa Mundi';
        document.getElementById('tileGridContainer').style.display = 'flex';

        document.getElementById('lblInstructionTitle').innerText = '💡 Visualização do Mapa Mundi:';
        document.getElementById('lblInstructionTip1').innerText = '• Cada tile do mapa composto possui tamanho fixo de 256x256 pixels.';
        document.getElementById('lblInstructionTip2').innerText = '• Ao passar o mouse, a grade acima acende mostrando qual tile você está inspecionando.';
    };
});

// Control buttons
document.getElementById('btnZoomIn').addEventListener('click', function() {
    adjustZoom(0.5, canvas.width / 2, canvas.height / 2);
});

document.getElementById('btnZoomOut').addEventListener('click', function() {
    adjustZoom(-0.5, canvas.width / 2, canvas.height / 2);
});

document.getElementById('btnZoomReset').addEventListener('click', function() {
    scale = minScale;
    offsetX = (canvas.width - img.width * scale) / 2;
    offsetY = (canvas.height - img.height * scale) / 2;
    draw();
});

// Start initialization
loadContinents();
