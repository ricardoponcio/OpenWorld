/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): todo `fetch` do painel, num lugar
 * só — antes espalhado por dashboard.js, mapa_composto.js e mapa_leaflet.js. Cada
 * função devolve o JSON já decodificado (`res.json()`); quem chama trata erro/rede
 * do jeito que já tratava antes (os `try/catch` não mudaram de lugar).
 */

// --- Painel geral (navegacao.js / painel_npcs.js) ---

export async function obterInit() {
    const res = await fetch('/api/init');
    return res.json();
}

// P01 (docs/16_PLANO_PAINEL_E_IA.md): substitui /api/update (23 MB/s) — relógio,
// pausa, velocidade, evento global e crônicas, nunca a lista de NPCs/locais.
export async function obterEstado() {
    const res = await fetch('/api/estado');
    return res.json();
}

export async function definirVelocidade(v) {
    return fetch(`/api/set_speed/${v}`);
}

export async function alternarPausa() {
    const res = await fetch('/api/toggle_pause', { method: 'POST' });
    return res.json();
}

// --- Ficha do habitante (ficha_npc.js) ---

export async function obterRelacoesNpc(npcId) {
    const res = await fetch(`/api/npc_rels/${npcId}`);
    return res.json();
}

export async function obterLogsNpc(npcId) {
    const res = await fetch(`/api/npc_logs/${npcId}`);
    return res.json();
}

// --- Modo Mestre (chat_mestre.js) ---

export async function obterHistoricoMestre() {
    const res = await fetch('/api/mestre/historico');
    return res.json();
}

export async function enviarMensagemAoMestre(mensagem) {
    const res = await fetch('/api/mestre/mensagem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensagem }),
    });
    return res.json();
}

export async function avancarTempoDoMestre(minutos) {
    const res = await fetch('/api/mestre/avancar_tempo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ minutos }),
    });
    return res.json();
}

export async function confirmarAcoesDoMestre(conversaId) {
    const res = await fetch('/api/mestre/confirmar_acoes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversa_id: conversaId }),
    });
    return res.json();
}

// --- Mapa em canvas e Mapa Live (mapa_composto*.js / mapa_leaflet*.js) ---

export async function obterContinentes() {
    const res = await fetch('/api/continentes');
    return res.json();
}

export async function obterInfoMapaMundi(x, y, signal) {
    const res = await fetch(`/api/mapa_composto/info/${x}/${y}`, { signal });
    return res.json();
}

export async function obterInfoContinente(uuid, x, y, signal) {
    const res = await fetch(`/api/continente/${uuid}/info/${x}/${y}`, { signal });
    return res.json();
}

export async function obterEntidadesRegiao(nome) {
    const res = await fetch(`/api/regiao/${nome}/entities`);
    return res.json();
}

export async function obterLotesAlterados(cidadeId) {
    const res = await fetch(`/api/cidade/${cidadeId}/lotes_alterados`);
    if (!res.ok) return [];
    return res.json();
}

export async function obterFeaturesMapa(camadas, bbox, z) {
    const res = await fetch(`/api/mapa/features?camadas=${camadas}&bbox=${bbox}&z=${z}`);
    return res.json();
}
