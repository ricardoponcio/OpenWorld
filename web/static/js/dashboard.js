let staticData = null;
let activeView = 'map-view';
let npcFilter = 'vivos';

function switchView(btn, id) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
    activeView = id;
    
    const eventLog = document.getElementById('event-log');
    if (id === 'npc-view') {
        eventLog.style.display = 'none';
    } else {
        eventLog.style.display = 'block';
    }
    
    update();
}

function setNpcFilter(filter) {
    npcFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        const text = btn.innerText.toLowerCase();
        let isMatch = false;
        if (filter === 'vivos' && text.includes('vivos')) isMatch = true;
        if (filter === 'mortos' && text.includes('falecidos')) isMatch = true;
        if (filter === 'todos' && text.includes('todos')) isMatch = true;
        btn.classList.toggle('active', isMatch);
    });
    update();
}

function toggleEventLog() {
    const log = document.getElementById('event-log');
    log.classList.toggle('collapsed');
}

async function init() {
    try {
        const res = await fetch('/api/init');
        staticData = await res.json();
        
        const mapEl = document.getElementById('world-map');
        mapEl.innerHTML = '';
        staticData.mapa.forEach(row => {
            row.forEach(tile => {
                const div = document.createElement('div');
                div.className = `tile tile-${tile}`;
                mapEl.appendChild(div);
            });
        });

        update();
        setInterval(update, 1000);
    } catch (e) { console.error("Init Error:", e); }
}

async function setSpeed(v) {
    try {
        await fetch(`/api/set_speed/${v}`);
        document.querySelectorAll('.speed-btn').forEach(b => {
            b.classList.toggle('active', parseInt(b.innerText) == v);
        });
    } catch (e) { console.error("Speed Error:", e); }
}

async function update() {
    const statusMsg = document.getElementById('status-msg');
    const statusIcon = document.getElementById('status-icon');
    const statusBar = document.getElementById('status-bar');

    try {
        const res = await fetch('/api/update');
        const data = await res.json();

        if (data.error) {
            statusMsg.innerText = data.error;
            statusIcon.innerText = "🔴";
            statusBar.className = "status-error";
            return;
        }

        if (data.warnings && data.warnings.length > 0) {
            statusMsg.innerText = "⚠️ " + data.warnings.join(' | ');
            statusIcon.innerText = "🟡";
            statusBar.className = "status-warn";
        } else {
            statusMsg.innerText = "Sistema Online | Sincronizado";
            statusIcon.innerText = "🟢";
            statusBar.className = "status-ok";
        }

        updatePauseUI(data.p);
        document.getElementById('clock').innerText = data.h || "Sincronizando...";
        
        document.querySelectorAll('.speed-btn').forEach(b => {
            b.classList.toggle('active', parseFloat(b.innerText) == data.v);
        });

        const banner = document.getElementById('event-banner');
        if (data.evg) {
            banner.style.display = 'block';
            document.getElementById('ev-title').innerText = data.evg.t;
            document.getElementById('ev-desc').innerText = data.evg.d;
            banner.style.background = data.evg.tp === 'CATASTROFE' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)';
        } else {
            banner.style.display = 'none';
        }

        const mapContainer = document.getElementById('map-container');
        
        if (data.locs) {
            Object.entries(data.locs).forEach(([id, loc]) => {
                let b = document.getElementById(`b-${id}`);
                if (!b) {
                    b = document.createElement('div');
                    b.id = `b-${id}`;
                    mapContainer.appendChild(b);
                }
                const isHome = loc.t === 'Casa';
                b.className = `building-marker ${isHome ? 'b-home' : 'b-work'}`;
                b.style.left = `${(loc.c[0] * 5) + 2.5}%`;
                b.style.top = `${(loc.c[1] * 5) + 2.5}%`;
                b.style.opacity = loc.s === 1 ? '1' : '0.3';
                b.style.filter = loc.s === 1 ? 'none' : 'grayscale(100%) brightness(0.5)';
                b.innerHTML = `<span class="marker-label">${loc.n}${loc.s === 0 ? ' (DESTRUÍDO)' : ''}</span>`;
            });
        }

        if (activeView === 'map-view' && data.npcs) {
            const locationCounts = {};
            const vivos = data.npcs.filter(npc => npc.status.h > 0);
            
            // Ocultar marcadores de NPCs mortos ou inativos na visualização
            document.querySelectorAll('.npc-marker').forEach(m => {
                const npcId = m.id.replace('m-', '');
                const isAlive = vivos.some(n => n.id === npcId);
                if (!isAlive) {
                    m.style.display = 'none';
                }
            });

            vivos.forEach(npc => {
                let m = document.getElementById(`m-${npc.id}`);
                if (!m) {
                    m = document.createElement('div');
                    m.id = `m-${npc.id}`;
                    m.className = 'npc-marker';
                    mapContainer.appendChild(m);
                }
                m.style.display = 'block';
                m.innerHTML = `<span class="marker-label">${npc.nome}</span>`;

                const key = `${npc.coords[0]},${npc.coords[1]}`;
                locationCounts[key] = (locationCounts[key] || 0) + 1;
                const offset = (locationCounts[key] - 1) * 6;

                m.style.left = `calc(${(npc.coords[0] * 5) + 2.5}% + ${offset}px)`;
                m.style.top = `calc(${(npc.coords[1] * 5) + 2.5}% + ${offset}px)`;
            });
        } else {
            document.querySelectorAll('.npc-marker').forEach(m => m.style.display = 'none');
        }

        if (activeView === 'npc-view' && data.npcs) {
            const grid = document.getElementById('npc-grid');
            
            // Aplicar o filtro na lista de habitantes
            let filteredNpcs = data.npcs;
            if (npcFilter === 'vivos') {
                filteredNpcs = data.npcs.filter(n => n.status.h > 0);
            } else if (npcFilter === 'mortos') {
                filteredNpcs = data.npcs.filter(n => n.status.h <= 0);
            }

            grid.innerHTML = filteredNpcs.map(n => `
                <div class="npc-card" style="${n.status.h <= 0 ? 'opacity: 0.6; filter: grayscale(50%);' : ''}">
                    <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                        <h3 style="font-family:'Outfit'">${n.nome} ${n.status.h <= 0 ? '💀' : ''}</h3>
                        <span style="font-size:0.7rem; background:rgba(56,189,248,0.1); padding:2px 8px; border-radius:10px; color:var(--accent)">${n.status.h <= 0 ? 'FALECIDO' : n.acao}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                        <span style="font-size:0.8rem; color:var(--text-dim)">${n.profissao}</span>
                        <span style="font-size:0.7rem; color:var(--warning)">${n.status.h <= 0 ? 'Sem Humor' : n.status.m}</span>
                    </div>

                    <div class="health-bar">
                        <div class="health-fill" style="width:${n.status.h}%; background:${n.status.h > 30 ? 'var(--success)' : 'var(--danger)'}"></div>
                    </div>
                    <p style="font-size:0.6rem; color:var(--text-dim); margin-bottom:1rem; text-align:right">SAÚDE: ${n.status.h}%</p>
                    <div class="status-row">
                        ${renderStatus('⚡', n.status.e, 'var(--accent)')}
                        ${renderStatus('🍗', n.status.f, 'var(--danger)')}
                        ${renderStatus('💬', n.status.s, 'var(--success)')}
                    </div>
                    <div style="margin-top:1rem; font-weight:bold; color:var(--warning)">💰 ${n.status.d}</div>
                </div>
            `).join('');
        }

        if (data.evs) {
            const logInner = document.getElementById('event-log-inner');
            if (logInner) {
                logInner.innerHTML = `<h4 style="margin-bottom:1rem; color:var(--accent); font-family:'Outfit'">📜 Crônicas Recentes</h4>` + 
                    data.evs.map(e => `<div class="event-item"><small>${e.t}</small><br>${e.r}</div>`).join('');
            }
        }

    } catch (e) { console.error("Update Error:", e); }
}

function renderStatus(icon, val, color) {
    return `
        <div class="status-item">
            <span style="font-size:0.8rem">${icon}</span>
            <div class="status-bar"><div class="status-fill" style="width:${val}%; background:${color}"></div></div>
        </div>
    `;
}

async function togglePause() {
    try {
        const res = await fetch('/api/toggle_pause', { method: 'POST' });
        const data = await res.json();
        updatePauseUI(data.pausado);
    } catch (e) { console.error("Pause Error:", e); }
}

function updatePauseUI(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (!btn) return;
    btn.innerText = isPaused ? "▶️" : "⏸️";
    btn.style.background = isPaused ? "var(--success)" : "var(--accent)";
    btn.style.boxShadow = `0 0 10px ${isPaused ? "var(--success)" : "var(--accent)"}`;
}

init();
