/**
 * M02 (docs/16_PLANO_PAINEL_E_IA.md): decide se o Mapa Live precisa buscar
 * features vetoriais de novo depois de um `moveend` — extraído de
 * mapa_leaflet_camadas.js pra manter os dois arquivos abaixo de 250 linhas.
 *
 * A ideia: pedir sempre uma bbox um pouco MAIOR que a visível (expandida) e
 * lembrar qual foi a última bbox/zoom pedidos — um pan pequeno dentro da área
 * já buscada não dispara requisição nova nenhuma.
 */

// 50% de cada lado — constante nomeada (não um número solto no meio do código).
const MARGEM_EXPANSAO = 0.5;

let ultimaBusca = null; // { x0, y0, x1, y1, z } — já são os valores EXPANDIDOS

export function bboxExpandida(x0, y0, x1, y1) {
    const margemX = (x1 - x0) * MARGEM_EXPANSAO;
    const margemY = (y1 - y0) * MARGEM_EXPANSAO;
    return { x0: x0 - margemX, y0: y0 - margemY, x1: x1 + margemX, y1: y1 + margemY };
}

// `x0,y0,x1,y1` aqui são a bbox VISÍVEL (não expandida) — só busca de novo se ela
// não cabe mais inteira dentro da última bbox expandida buscada, ou se o zoom
// (arredondado pra baixo) mudou.
export function precisaBuscarDeNovo(x0, y0, x1, y1, z) {
    if (!ultimaBusca) return true;
    if (Math.floor(z) !== Math.floor(ultimaBusca.z)) return true;
    return x0 < ultimaBusca.x0 || y0 < ultimaBusca.y0 || x1 > ultimaBusca.x1 || y1 > ultimaBusca.y1;
}

export function registrarBuscaFeita(x0, y0, x1, y1, z) {
    ultimaBusca = { x0, y0, x1, y1, z };
}
