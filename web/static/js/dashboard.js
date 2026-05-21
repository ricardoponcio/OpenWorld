let staticData = null;
let activeView = 'map-view';
let npcFilter = 'vivos';
let allNpcs = [];
let allRels = [];
let activeModalTab = 'profile';
let activeNpcId = null;

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
        // Old map generation removed

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
        
        if (data.npcs) allNpcs = data.npcs;
        if (data.rels) allRels = data.rels;

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

        // Markers rendering logic removed because mapa_composto.js handles it now
        if (typeof window.updateMapEntities === 'function' && data.npcs) {
            window.updateMapEntities(data.npcs);
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

            grid.innerHTML = filteredNpcs.map(n => {
                const avatar = getNPCAvatar(n.bio.g, n.bio.ev);
                const stageLabel = n.bio.ev === 'bebe' ? '🍼 Bebê' : (n.bio.ev === 'crianca' ? '🧸 Criança' : n.profissao);
                const pregnantBadge = n.bio.gr > 0 ? `
                    <div style="margin-top: 0.5rem; font-size: 0.65rem; color: #ff007f; background: rgba(255,0,127,0.08); border: 1px dashed #ff007f; padding: 2px 8px; border-radius: 6px; display: inline-block;">
                        🤰 Gestante (${n.bio.gr} ticks)
                    </div>
                ` : '';

                return `
                    <div class="npc-card" style="${n.status.h <= 0 ? 'opacity: 0.6; filter: grayscale(50%);' : ''}">
                        <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                            <h3 style="font-family:'Outfit'">${avatar} ${n.nome} ${n.status.h <= 0 ? '💀' : ''}</h3>
                            <span style="font-size:0.7rem; background:rgba(56,189,248,0.1); padding:2px 8px; border-radius:10px; color:var(--accent)">${n.status.h <= 0 ? 'FALECIDO' : n.acao}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.2rem;">
                            <span style="font-size:0.8rem; color:var(--text-dim)">${stageLabel}</span>
                            <span style="font-size:0.7rem; color:var(--warning)">${n.status.h <= 0 ? 'Sem Humor' : n.status.m}</span>
                        </div>
                        ${pregnantBadge}

                        <div class="health-bar" style="margin-top:0.8rem;">
                            <div class="health-fill" style="width:${n.status.h}%; background:${n.status.h > 30 ? 'var(--success)' : 'var(--danger)'}"></div>
                        </div>
                        <p style="font-size:0.6rem; color:var(--text-dim); margin-bottom:1rem; text-align:right">SAÚDE: ${n.status.h}%</p>
                        <div class="status-row">
                            ${renderStatus('⚡', n.status.e, 'var(--accent)')}
                            ${renderStatus('🍗', n.status.f, 'var(--danger)')}
                            ${renderStatus('💬', n.status.s, 'var(--success)')}
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem;">
                            <div style="font-weight:bold; color:var(--warning)">💰 ${n.status.d}</div>
                            <button class="filter-btn" style="padding: 0.2rem 0.6rem; font-size: 0.7rem; border-color: rgba(56,189,248,0.3); color: var(--accent);" onclick="abrirHistorico('${n.id}', '${n.nome.replace(/'/g, "\\'")}')">👤 Perfil</button>
                        </div>
                    </div>
                `;
            }).join('');
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

function getNPCAvatar(genero, estagio_vida) {
    if (estagio_vida === 'bebe') return '👶';
    if (estagio_vida === 'crianca') return genero === 'M' ? '👦' : '👧';
    if (estagio_vida === 'idoso') return genero === 'M' ? '👴' : '👵';
    if (estagio_vida === 'morto') return '💀';
    return genero === 'M' ? '👨' : '👩';
}

function getNPCNameById(npcId) {
    if (!npcId) return null;
    const found = allNpcs.find(n => n.id === npcId);
    return found ? found.nome : "Desconhecido";
}

function getNPCChildren(npcId) {
    return allNpcs.filter(n => n.bio.pai === npcId || n.bio.mae === npcId);
}

function getNPCRelationships(npcId) {
    return allRels.filter(r => r.a === npcId);
}

function switchModalNPC(newNpcId) {
    const found = allNpcs.find(n => n.id === newNpcId);
    if (found) {
        abrirHistorico(found.id, found.nome);
    }
}

function switchModalTab(tab) {
    activeModalTab = tab;
    
    // Atualizar UI dos botões das abas
    document.getElementById('tab-profile-btn').classList.toggle('active', tab === 'profile');
    document.getElementById('tab-logs-btn').classList.toggle('active', tab === 'logs');
    
    // Atualizar exibição dos blocos de conteúdo
    document.getElementById('modal-tab-profile').style.display = tab === 'profile' ? 'block' : 'none';
    document.getElementById('modal-tab-logs').style.display = tab === 'logs' ? 'block' : 'none';
}

function renderNPCProfile(npc) {
    const avatar = getNPCAvatar(npc.bio.g, npc.bio.ev);
    const generoStr = npc.bio.g === 'M' ? 'Masculino ♂️' : 'Feminino ♀️';
    const estagioStr = npc.bio.ev === 'bebe' ? 'Bebê 👶' : 
                       (npc.bio.ev === 'crianca' ? 'Criança 👦' : 
                       (npc.bio.ev === 'idoso' ? 'Idoso(a) 👴👵' : 
                       (npc.bio.ev === 'morto' ? 'Falecido(a) 💀' : 'Adulto(a) 🧑')));
    
    // Pais
    const maeNome = getNPCNameById(npc.bio.mae);
    const paiNome = getNPCNameById(npc.bio.pai);
    
    const maeLink = npc.bio.mae ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" onclick="switchModalNPC('${npc.bio.mae}')">👩 ${maeNome}</a>` : '<span style="color: var(--text-dim)">Desconhecida</span>';
    const paiLink = npc.bio.pai ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" onclick="switchModalNPC('${npc.bio.pai}')">👨 ${paiNome}</a>` : '<span style="color: var(--text-dim)">Desconhecido</span>';
    
    // Cônjuge
    let conjugeLink = '<span style="color: var(--text-dim)">Nenhum</span>';
    if (npc.bio.ec === 'casado' && npc.bio.cj) {
        const conjugeNome = getNPCNameById(npc.bio.cj);
        conjugeLink = `<a href="#" style="color: var(--success); text-decoration: none; font-weight: 600;" onclick="switchModalNPC('${npc.bio.cj}')">💍 ${conjugeNome}</a>`;
    }
    
    // Filhos
    const filhos = getNPCChildren(npc.id);
    const filhosList = filhos.length > 0 ? filhos.map(f => `
        <li style="list-style: none; margin-bottom: 0.3rem;">
            <a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" onclick="switchModalNPC('${f.id}')">👶 ${f.nome} (${f.bio.ev === 'bebe' ? 'Bebê' : 'Criança'})</a>
        </li>
    `).join('') : '<span style="color: var(--text-dim)">Nenhum filho registrado.</span>';
    
    // Círculo Social
    const rels = getNPCRelationships(npc.id);
    const relsList = rels.length > 0 ? rels.map(r => {
        const outroNome = getNPCNameById(r.b);
        const afinidadeCor = r.af > 60 ? 'var(--success)' : (r.af < 30 ? 'var(--danger)' : 'var(--warning)');
        return `
            <div style="display:flex; justify-content:space-between; padding: 0.5rem; background: rgba(255,255,255,0.02); border-radius: 6px; margin-bottom: 0.4rem; font-size: 0.8rem; border-left: 3px solid ${afinidadeCor};">
                <span style="font-weight: 600; color: var(--text);">${outroNome}</span>
                <span style="color: var(--text-dim)">${r.v} (<strong style="color: ${afinidadeCor}">${r.af} afinidade</strong>)</span>
            </div>
        `;
    }).join('') : '<span style="color: var(--text-dim)">Sem conexões sociais expressivas.</span>';

    // Gestão de gravidez
    const gravidezHtml = npc.bio.gr > 0 ? `
        <div style="background: rgba(255,0,127,0.08); border: 1px dashed #ff007f; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #ff007f; display:flex; align-items:center; gap: 0.8rem;">
            <span style="font-size: 1.5rem;">🤰</span>
            <div>
                <strong style="display:block">Período de Gestação Ativo</strong>
                <span style="font-size: 0.75rem; color: var(--text-dim);">Faltam ${npc.bio.gr} ticks virtuais para o nascimento do bebê!</span>
            </div>
        </div>
    ` : '';

    return `
        ${gravidezHtml}
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.5rem;">
            <!-- Informações Básicas -->
            <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">👤 Identidade</h4>
                <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.8rem;">
                    <div><span style="color: var(--text-dim)">Gênero:</span> <strong>${generoStr}</strong></div>
                    <div><span style="color: var(--text-dim)">Fase da Vida:</span> <strong>${estagioStr}</strong></div>
                    <div><span style="color: var(--text-dim)">Estado Civil:</span> <strong style="text-transform: capitalize;">${npc.bio.ec || 'solteiro'}</strong></div>
                    <div><span style="color: var(--text-dim)">Idade Biológica:</span> <strong style="color: var(--accent)">${npc.bio.idade || 0} anos</strong></div>
                    <div><span style="color: var(--text-dim)">Profissão:</span> <strong>${npc.profissao}</strong></div>
                    <div><span style="color: var(--text-dim)">Ação Atual:</span> <strong>${npc.acao}</strong></div>
                    <div><span style="color: var(--text-dim)">Saúde:</span> <strong style="color: ${npc.status.h > 40 ? 'var(--success)' : 'var(--danger)'}">${npc.status.h}%</strong></div>
                    <div><span style="color: var(--text-dim)">Humor:</span> <strong style="color: var(--warning)">${npc.status.m}</strong></div>
                    <div><span style="color: var(--text-dim)">Finanças:</span> <strong style="color: var(--success)">💰 ${npc.status.d}</strong></div>
                    <div><span style="color: var(--text-dim)">Data Nascimento:</span> <span>${npc.bio.dn.split('T')[0] || "Era Inicial"}</span></div>
                </div>
            </div>
            
            <!-- Família e Árvore Genealógica -->
            <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">👨‍👩‍👧 Árvore Genealógica</h4>
                <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.8rem;">
                    <div><span style="color: var(--text-dim)">Mãe:</span> ${maeLink}</div>
                    <div><span style="color: var(--text-dim)">Pai:</span> ${paiLink}</div>
                    <div><span style="color: var(--text-dim)">Cônjuge:</span> ${conjugeLink}</div>
                    <div style="margin-top: 0.4rem;">
                        <span style="color: var(--text-dim); display:block; margin-bottom:0.3rem">Filhos:</span>
                        <ul style="padding-left: 0; margin: 0;">${filhosList}</ul>
                    </div>
                </div>
            </div>
            
            <!-- Relações Sociais -->
            <div style="grid-column: 1 / -1; background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">💬 Círculo de Relacionamentos</h4>
                <div style="max-height: 140px; overflow-y: auto; padding-right: 0.3rem;">
                    ${relsList}
                </div>
            </div>
        </div>
    `;
}

async function abrirHistorico(npcId, npcNome) {
    activeNpcId = npcId;
    const modal = document.getElementById('npc-log-modal');
    const title = document.getElementById('modal-npc-nome');
    const profileContainer = document.getElementById('modal-profile-details');
    const list = document.getElementById('modal-log-list');

    title.innerText = `Ficha de ${npcNome}`;
    list.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando logs...</p>`;
    profileContainer.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando ficha...</p>`;
    modal.classList.add('active');
    
    // Resetar aba padrão para Perfil
    switchModalTab('profile');

    try {
        const resRels = await fetch(`/api/npc_rels/${npcId}`);
        const dataRels = await resRels.json();
        if (dataRels.rels) {
            allRels = dataRels.rels.map(r => ({...r, a: npcId})); // Populate 'a' field to match old logic
        }

        const foundNpc = allNpcs.find(n => n.id === npcId);
        if (foundNpc) {
            profileContainer.innerHTML = renderNPCProfile(foundNpc);
        }
    } catch (e) {
        console.error("Error loading relationships:", e);
    }

    try {
        const res = await fetch(`/api/npc_logs/${npcId}`);
        const data = await res.json();
        if (data.error) {
            list.innerHTML = `<p style="color: var(--danger); text-align: center;">Erro: ${data.error}</p>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            list.innerHTML = `<p style="color: var(--text-dim); text-align: center;">Nenhum registro de crônica encontrado para este habitante.</p>`;
            return;
        }

        list.innerHTML = data.logs.map(log => {
            const levelClass = `level-${log.l.toLowerCase()}`;
            return `
                <div class="npc-log-item ${levelClass}">
                    <div class="npc-log-meta">
                        <span>[${log.l}]</span>
                        <span>${log.t}</span>
                    </div>
                    <div>${log.m}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error("Error loading NPC logs:", e);
        list.innerHTML = `<p style="color: var(--danger); text-align: center;">Falha ao carregar os dados.</p>`;
    }
}

function fecharHistorico(event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('npc-log-modal');
    modal.classList.remove('active');
    activeNpcId = null;
}

init();

