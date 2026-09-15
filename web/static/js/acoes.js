/**
 * F01 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): registro e despacho de `data-acao`.
 * Fica num arquivo próprio (e não em app.js) para os módulos poderem registrar suas
 * próprias ações sem importar app.js — isso criaria import circular (app.js importa
 * os módulos, que precisariam importar app.js de volta).
 */
const ACOES = new Map();

export function registrarAcoes(mapa) {
    for (const [nome, fn] of Object.entries(mapa)) ACOES.set(nome, fn);
}

export function despachar(ev) {
    const alvo = ev.target.closest('[data-acao]');
    if (!alvo) return;
    ACOES.get(alvo.dataset.acao)?.(alvo, ev);
}
