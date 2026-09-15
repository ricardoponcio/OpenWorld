import { registrarAcoes } from './acoes.js';
import { initMapaLeaflet } from './mapa_leaflet.js';
import { Aba, FiltroNpc, AbaModal } from './constantes.js';

// F01 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado do módulo num objeto só, não
// dezenas de `let` soltos (ARQUITETURA §10 regra 4).
const estado = {
    staticData: null,
    activeView: Aba.MAPA,
    npcFilter: FiltroNpc.VIVOS,
    allNpcs: [],
    allRels: [],
    activeModalTab: AbaModal.PERFIL,
    activeNpcId: null,
};

// F03: o mapeamento do valor curto de `data-aba` pro id de DOM da view — a view em
// si continua sendo um id de elemento HTML, não vocabulário de domínio, então fica
// como está (não é um enum).
const ABA_PARA_VIEW_ID = {
    [Aba.MAPA]: 'map-view',
    [Aba.HABITANTES]: 'npc-view',
    [Aba.MESTRE]: 'mestre-view',
    [Aba.MAPA_LIVE]: 'mapa-leaflet-view',
};

function switchView(btn, aba) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(ABA_PARA_VIEW_ID[aba]).classList.add('active');
    btn.classList.add('active');
    estado.activeView = aba;

    const eventLog = document.getElementById('event-log');
    if (aba === Aba.HABITANTES || aba === Aba.MESTRE || aba === Aba.MAPA_LIVE) {
        eventLog.style.display = 'none';
    } else {
        eventLog.style.display = 'block';
    }

    if (aba === Aba.MESTRE) {
        carregarHistoricoMestre();
    } else if (aba === Aba.MAPA_LIVE) {
        initMapaLeaflet();
    } else {
        update();
    }
}

function setNpcFilter(filter) {
    estado.npcFilter = filter;
    // F03 (docs/16_PLANO_PAINEL_E_IA.md, Armadilha 19): decidia o botão ativo lendo
    // o TEXTO VISÍVEL do botão — quebraria se o rótulo mudasse. Agora usa o mesmo
    // `data-filtro` que a ação já lê.
    document.querySelectorAll('.filter-btn[data-filtro]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filtro === filter);
    });
    update();
}

function toggleEventLog() {
    const log = document.getElementById('event-log');
    log.classList.toggle('collapsed');
}

export function iniciarDashboard() {
    // F01: o Enter no campo do Mestre era um `onkeydown` inline — vira um listener
    // de verdade, registrado aqui (uma vez), no próprio elemento.
    document.getElementById('mestre-input').addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') enviarMensagemMestre();
    });
    iniciarPolling();
}

async function iniciarPolling() {
    try {
        const res = await fetch('/api/init');
        estado.staticData = await res.json();
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

        if (data.npcs) estado.allNpcs = data.npcs;
        if (data.rels) estado.allRels = data.rels;

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

        if (estado.activeView === Aba.HABITANTES && data.npcs) {
            const grid = document.getElementById('npc-grid');

            // Aplicar o filtro na lista de habitantes
            let filteredNpcs = data.npcs;
            if (estado.npcFilter === FiltroNpc.VIVOS) {
                filteredNpcs = data.npcs.filter(n => n.status.h > 0);
            } else if (estado.npcFilter === FiltroNpc.MORTOS) {
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
                            <button class="filter-btn" style="padding: 0.2rem 0.6rem; font-size: 0.7rem; border-color: rgba(56,189,248,0.3); color: var(--accent);" data-acao="abrir-ficha" data-npc-id="${escaparHtml(n.id)}">👤 Perfil</button>
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
    const found = estado.allNpcs.find(n => n.id === npcId);
    return found ? found.nome : "Desconhecido";
}

function getNPCChildren(npcId) {
    return estado.allNpcs.filter(n => n.bio.pai === npcId || n.bio.mae === npcId);
}

function getNPCRelationships(npcId) {
    return estado.allRels.filter(r => r.a === npcId);
}

function switchModalTab(tab) {
    estado.activeModalTab = tab;

    // Atualizar UI dos botões das abas
    document.getElementById('tab-profile-btn').classList.toggle('active', tab === AbaModal.PERFIL);
    document.getElementById('tab-logs-btn').classList.toggle('active', tab === AbaModal.LOGS);

    // Atualizar exibição dos blocos de conteúdo
    document.getElementById('modal-tab-profile').style.display = tab === AbaModal.PERFIL ? 'block' : 'none';
    document.getElementById('modal-tab-logs').style.display = tab === AbaModal.LOGS ? 'block' : 'none';
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

    const maeLink = npc.bio.mae ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.mae)}">👩 ${maeNome}</a>` : '<span style="color: var(--text-dim)">Desconhecida</span>';
    const paiLink = npc.bio.pai ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.pai)}">👨 ${paiNome}</a>` : '<span style="color: var(--text-dim)">Desconhecido</span>';

    // Cônjuge
    let conjugeLink = '<span style="color: var(--text-dim)">Nenhum</span>';
    if (npc.bio.ec === 'casado' && npc.bio.cj) {
        const conjugeNome = getNPCNameById(npc.bio.cj);
        conjugeLink = `<a href="#" style="color: var(--success); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.cj)}">💍 ${conjugeNome}</a>`;
    }

    // Filhos
    const filhos = getNPCChildren(npc.id);
    const filhosList = filhos.length > 0 ? filhos.map(f => `
        <li style="list-style: none; margin-bottom: 0.3rem;">
            <a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(f.id)}">👶 ${f.nome} (${f.bio.ev === 'bebe' ? 'Bebê' : 'Criança'})</a>
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

async function abrirHistorico(npcId) {
    estado.activeNpcId = npcId;
    const npcEncontrado = estado.allNpcs.find(n => n.id === npcId);
    const npcNome = npcEncontrado ? npcEncontrado.nome : "Desconhecido";
    const modal = document.getElementById('npc-log-modal');
    const title = document.getElementById('modal-npc-nome');
    const profileContainer = document.getElementById('modal-profile-details');
    const list = document.getElementById('modal-log-list');

    title.innerText = `Ficha de ${npcNome}`;
    list.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando logs...</p>`;
    profileContainer.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando ficha...</p>`;
    modal.classList.add('active');

    // Resetar aba padrão para Perfil
    switchModalTab(AbaModal.PERFIL);

    try {
        const resRels = await fetch(`/api/npc_rels/${npcId}`);
        const dataRels = await resRels.json();
        if (dataRels.rels) {
            estado.allRels = dataRels.rels.map(r => ({...r, a: npcId})); // Populate 'a' field to match old logic
        }

        const foundNpc = estado.allNpcs.find(n => n.id === npcId);
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

function fecharHistorico() {
    const modal = document.getElementById('npc-log-modal');
    modal.classList.remove('active');
    estado.activeNpcId = null;
}

// --- Modo Mestre de IA (Frente 5) ---

// F01 (docs/16_PLANO_PAINEL_E_IA.md): renomeado de escapeHtmlMestre — passa a ser
// usado por qualquer texto do servidor que vá pro DOM, não só o chat do Mestre.
// F05 move isto pra formatacao.js.
function escaparHtml(str) {
    const div = document.createElement('div');
    div.innerText = str == null ? '' : String(str);
    return div.innerHTML;
}

function renderMestreChatLog(historico) {
    const log = document.getElementById('mestre-chat-log');
    log.innerHTML = historico.map(h => {
        const ehJogador = h.autor === 'jogador';
        return `
            <div style="align-self:${ehJogador ? 'flex-end' : 'flex-start'}; max-width: 80%; background: ${ehJogador ? 'var(--accent)' : 'rgba(255,255,255,0.06)'}; color: ${ehJogador ? '#04202e' : 'inherit'}; padding: 0.6rem 0.9rem; border-radius: 14px; font-size: 0.85rem; white-space: pre-wrap;">
                ${escaparHtml(h.mensagem)}
            </div>
        `;
    }).join('');
    log.scrollTop = log.scrollHeight;

    // Mostra o painel de confirmação se a última mensagem do Mestre tiver ações pendentes
    const ultima = historico[historico.length - 1];
    const painel = document.getElementById('mestre-acoes-pendentes');
    if (ultima && ultima.autor === 'mestre' && !ultima.aplicada && ultima.acoes_propostas && ultima.acoes_propostas.length > 0) {
        painel.style.display = 'block';
        painel.innerHTML = `
            <div class="info-card" style="border: 1px solid var(--accent);">
                <strong style="font-size:0.85rem;">⚡ O Mestre propôs ${ultima.acoes_propostas.length} ação(ões) no mundo:</strong>
                <ul style="font-size:0.8rem; color: var(--text-dim); margin: 0.4rem 0;">
                    ${ultima.acoes_propostas.map(a => `<li>${escaparHtml(a.comando)} ${escaparHtml(a.id || '')}</li>`).join('')}
                </ul>
                <button class="filter-btn active" data-acao="confirmar-acoes" data-conversa-id="${ultima.id}">✅ Confirmar</button>
                <button class="filter-btn" data-acao="ignorar-acoes">✋ Ignorar</button>
            </div>
        `;
    } else {
        painel.style.display = 'none';
    }
}

async function carregarHistoricoMestre() {
    try {
        const res = await fetch('/api/mestre/historico');
        const data = await res.json();
        if (data.historico) renderMestreChatLog(data.historico);
    } catch (e) { console.error("Erro ao carregar histórico do Mestre:", e); }
}

async function enviarMensagemMestre() {
    const input = document.getElementById('mestre-input');
    const mensagem = input.value.trim();
    if (!mensagem) return;
    input.value = '';
    input.disabled = true;
    try {
        const res = await fetch('/api/mestre/mensagem', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mensagem })
        });
        const data = await res.json();
        if (data.error) {
            alert('Erro: ' + data.error);
        } else {
            await carregarHistoricoMestre();
        }
    } catch (e) {
        console.error("Erro ao enviar mensagem ao Mestre:", e);
    } finally {
        input.disabled = false;
        input.focus();
    }
}

async function avancarTempoMestre(minutos) {
    const log = document.getElementById('mestre-chat-log');
    log.insertAdjacentHTML('beforeend', `<div id="mestre-aguardando" style="text-align:center; color: var(--text-dim); font-size:0.8rem;">⏳ Avançando ${minutos} minutos de jogo...</div>`);
    log.scrollTop = log.scrollHeight;
    try {
        const res = await fetch('/api/mestre/avancar_tempo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ minutos })
        });
        const data = await res.json();
        if (data.error) {
            alert('Erro: ' + data.error);
        }
        await carregarHistoricoMestre();
    } catch (e) {
        console.error("Erro ao avançar tempo:", e);
    }
}

async function confirmarAcoesMestre(conversaId) {
    try {
        const res = await fetch('/api/mestre/confirmar_acoes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversa_id: conversaId })
        });
        const data = await res.json();
        if (data.error) {
            alert('Erro: ' + data.error);
        } else {
            document.getElementById('mestre-acoes-pendentes').style.display = 'none';
            // F01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): a ação foi ENFILEIRADA, não
            // aplicada na hora — só vira efeito de verdade quando run_simulation.py
            // drenar a fila (próximo tick, ou próxima volta do laço se pausado).
            let texto = 'Enviado (será aplicado no próximo tick da simulação):\n' + (data.resultados || []).join('\n');
            if (data.aviso) texto += '\n\n⚠️ ' + data.aviso;
            alert(texto);
        }
    } catch (e) { console.error("Erro ao confirmar ações do Mestre:", e); }
}

function ignorarAcoesMestre() {
    document.getElementById('mestre-acoes-pendentes').style.display = 'none';
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'pausar': () => togglePause(),
    'velocidade': (alvo) => setSpeed(parseInt(alvo.dataset.valor, 10)),
    'trocar-aba': (alvo) => switchView(alvo, alvo.dataset.aba),
    'filtro-npc': (alvo) => setNpcFilter(alvo.dataset.filtro),
    'alternar-cronicas': () => toggleEventLog(),
    'abrir-ficha': (alvo) => abrirHistorico(alvo.dataset.npcId),
    // F01: só fecha quando o clique foi no próprio overlay/botão × — não quando um
    // clique dentro do conteúdo do modal borbulha até aqui (o conteúdo não tem
    // data-acao, então closest() sobe até o overlay; sem esta checagem qualquer
    // clique no modal inteiro o fecharia).
    'fechar-ficha': (alvo, ev) => { if (ev.target === alvo) fecharHistorico(); },
    'ficha-aba': (alvo) => switchModalTab(alvo.dataset.aba),
    'avancar-tempo': (alvo) => avancarTempoMestre(parseInt(alvo.dataset.minutos, 10)),
    'enviar-mensagem': () => enviarMensagemMestre(),
    'confirmar-acoes': (alvo) => confirmarAcoesMestre(alvo.dataset.conversaId),
    'ignorar-acoes': () => ignorarAcoesMestre(),
});
