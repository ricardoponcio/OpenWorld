/**
 * F03 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): vocabulário fechado do frontend, num
 * lugar só — antes comparado como texto solto ('map-view', 'vivos', 'global',
 * 'profile') espalhado pelos módulos (ARQUITETURA §10 regra 5: enums em JS são
 * Object.freeze).
 *
 * P04: `FiltroNpc` saiu — a lista de situações vem de `/api/habitantes/filtros`
 * (`SituacaoHabitante`, servida — não copiada aqui).
 */
export const Modo = Object.freeze({ GLOBAL: 'global', CONTINENTE: 'continente', CIDADE: 'cidade' });
export const Aba = Object.freeze({ MAPA: 'mapa', HABITANTES: 'habitantes', MESTRE: 'mestre', MAPA_LIVE: 'mapa-live' });
export const AbaModal = Object.freeze({ PERFIL: 'profile', LOGS: 'logs' });
