# 📋 Auditoria de Valores Hardcoded

> **Status: Frente 1 concluída em 2026-09-09.** Este documento nasceu como checklist de migração
> e agora serve como **registro histórico** de onde cada valor morava antes e para onde foi. O
> pacote `config/` (raiz do projeto) é o ponto único de verdade hoje — `config/sources.py` (fonte
> intercambiável) + `config/resolver.py` (`cfg_get`/`get_config`, resolução estrita fail-fast).
> Toda a engine e toda a cartografia leem através dele; `cartographer/config.py` e
> `engine/config_loader.py` são shims finos que reexportam de lá.
>
> Ver [`05_ROADMAP.md`](05_ROADMAP.md) para o estado das demais frentes (2 a 6).

## Legenda
- ✅ Migrado para `config.json` e lido via `cfg_get`.
- 🔧 Corrigido como bug/inconsistência durante a migração (não é só "mudou de lugar").
- ⏸️ Deixado deliberadamente como constante de implementação (não é parâmetro de balanceamento — ver régua abaixo).

**Régua usada para decidir o que vira config**: *"se eu mudar esse número, o resultado
visível/comportamental muda de forma que alguém iria querer ajustar?"* Se sim → config. Se é só
matemática interna do algoritmo (curva quíntica de Perlin, multiplicadores de hash, offsets de
descorrelação entre oitavas) → fica como constante de implementação.

---

## Cartografia

### `cartographer/config.py` (antigo dict `CARTOGRAPHER_CONFIG`)
- ✅ Todas as ~34 chaves originais migradas para `config.json["cartografia"]`. O arquivo agora é um
  shim de 3 linhas.

### `cartographer/math/noise.py`
- 🔧 `DEFAULT_TECTONIC_MACRO_SCALE/OCTAVES/DETAIL_SCALE/OCTAVES` (constantes de classe duplicadas,
  nunca lidas do config) — removidas. `generate_tectonic_base` agora exige `config` e lê
  `ruido_macro_escala/oitavas`, `ruido_costa_escala/oitavas` via `cfg_get`.
- 🔧 `persistencia`/`lacunariedade` — antes hardcoded (`amplitude *= 0.5`, `frequency *= 2.0`) e
  **completamente ignorados** mesmo já existindo no config. Agora são parâmetros reais de
  `generate_noise_field` (defaults 0.5/2.0 preservados só para os chamadores que ainda passam scale/
  octaves "soltos" fora do caminho de `generate_tectonic_base`, ex.: `tectonics.py`,
  `climate.py`, `roi_zoom.py` — esses continuam com o comportamento histórico até serem
  revisitados na Frente 2, quando a variedade visual for o foco).
- ✅ `tectonica_base_peso_macro`/`tectonica_base_peso_detalhe` (antes `0.7`/`0.3` inline).
- ⏸️ `limite = max_val * 0.707` (normalização ~1/√2 do fBm) e offset por oitava `i * 100` —
  matemática interna do algoritmo, não balanceamento.

### `cartographer/math/tectonics.py`
- ✅ `tectonica_warp_escala`/`tectonica_warp_amplitude` (antes `scale=120.0, amplitude=65.0`).
- ✅ `tectonica_raio_fator_min`/`tectonica_raio_fator_variacao` (antes `0.65 + 0.75 * ruido`).
- ✅ `tectonica_costa_distorcao_fator` (antes `* 0.85`).
- ✅ `perfil_plato_limiar`/`perfil_plato_achatamento` (antes `0.6`/`0.08`).
- ✅ `perfil_arquipelago_escala`/`_inclinacao_sigmoide`/`_centro` (antes `18.0`/`-15.0`/`0.45`).
- ✅ `vinheta_margem_segura`/`vinheta_largura_fade` (antes `40.0`/`80.0`).
- 🔧 `map_size` da vinheta — antes `768.0` fixo; agora `self.tamanho_global` calculado por
  `WorldManager` (`mundo_tiles_por_lado × tile_size`) e passado explicitamente. Mudar o grid de
  tiles não quebra mais essa conta silenciosamente.
- ⏸️ Offsets de ruído `7777`/`9999`/`8888` (domain warping/perfil arquipélago) — descorrelação entre
  campos de ruído, não parâmetro de balanceamento.

### `cartographer/math/climate.py`
- 🔧 `DEFAULT_NIVEL_MAR`/`DEFAULT_NIVEL_MONTANHA` (0.35/0.75, este último **divergente** do
  `nivel_montanha=0.8` do config e nunca de fato atingível) — removidas. `nivel_mar`/
  `nivel_montanha` agora são parâmetros obrigatórios, sempre vindos de `config["cartografia"]`.
- ✅ `clima_damping_termico`, `clima_umidade_oceano`, `clima_umidade_terra_base`,
  `clima_dithering_escala/temp_amp/umid_amp`, `limiar_temp_deserto/umid_deserto/
  temp_mediterraneo/umid_mediterraneo` — todas migradas, funções recebem `config` e usam `cfg_get`.
- 🔧 `map_height` de `calculate_temperature` — antes `768.0` fixo; agora recebido do chamador
  (mesma correção do `map_size` da vinheta).

### `cartographer/math/shading.py`
- ✅ `shading_escala_terreno`, `shading_escala_terreno_resolucao_base`, `shading_luz_direcao`,
  `shading_contraste`, `shading_brilho_min/max` — antes defaults de função (`escala_terreno=48.0`,
  `luz_dir=(-1,-1,0.95)`) e literais inline (`1.85`, `0.45`, `1.55`).

### `cartographer/math/coloring.py`
- 🔧 `CORES_BASE` — dict declarado mas **nunca usado** em lugar nenhum do código. Removido (código morto).
- ✅ Toda a paleta agora vem de `config["cartografia"]["cores"]`: `oceano.raso/profundo/
  curva_potencia`, e `biomas.<id>.baixa/media/transicao`.
- 🔧 Simplificação: as 4 implementações por-bioma quase-idênticas de `interpolate_land_biome`
  viraram **uma função genérica** de interpolação em 3 pontos de controle, dirigida por config. A
  Montanha Rochosa (que antes era um gradiente único 0→1, sem parada intermediária) usa
  `transicao=0.0` para reproduzir exatamente o mesmo resultado sem precisar de um código especial.

### `cartographer/world/tile_cartographer.py`
- 🔧 (Frente 2) Raio do continente **redesenhado**, não só centralizado: `R = sqrt(area_km2 / (pi *
  escala_pixel_area_km2)) * continente_area_para_raio_fator_visual`, usando a mesma escala oficial
  já declarada em config em vez do antigo `/10.0` desacoplado. `continente_raio_min_px/max_px`
  (antes `[65,155]`, agora `[30,260]`) viraram guarda-corpo de segurança contra resposta absurda da
  IA, não mais a fonte principal da variação de tamanho.
- ✅ `continente_elevacao_maxima_padrao`/`continente_raio_visual_padrao` (defaults permissivos via
  `cfg_get(..., default=...)`, para quando a IA/fallback não informa o campo).
- 🔧 Todos os `self.config["chave"]` viraram `cfg_get(cfg, "chave")` (mesma coisa, mensagem de erro
  melhor) e todas as chamadas a `TectonicsProcessor`/`ClimateProcessor` passam `config=cfg` em vez
  de extrair valores individualmente antes de chamar.

### `cartographer/world/world_manager.py` + `generate_world.py`
- 🔧 `mundo_tiles_por_lado` (novo) — antes o "3" do grid 3×3 existia **duas vezes** e podia divergir
  (`world_manager.py: tamanho_global = 3 * self.tile_size` vs `generate_world.py:
  width_tiles=3, height_tiles=3`). Agora as duas leituras vêm da mesma chave de config.

### `cartographer/continents/roi_zoom.py`
- ✅ `zoom_border_padding_px` (antes `BORDER_PADDING = 20` como atributo de classe).
- ✅ `zoom_costa_profundidade_min`/`zoom_costa_profundidade_faixa` (antes `0.22`/`0.13`).
- 🔧 **Bug de determinismo corrigido**: `abs(hash(cont_uuid)) % 40000` → `zlib.crc32(...)`.
  `hash()` de string é aleatorizado por processo em Python (`PYTHONHASHSEED`); o micro-relevo do
  zoom mudava a cada regeneração do `.npz`, contradizendo o próprio docstring do método
  ("reprodutível"). **Verificado**: regerar o mesmo continente duas vezes agora produz bytes
  idênticos (testado nesta sessão).
- 🔧 `self.config` no `__init__` — antes um dict reduzido de 2 chaves hardcoded
  (`{"nivel_mar": 0.35, "nivel_montanha": 0.80}`) como default; agora usa o `CARTOGRAPHER_CONFIG`
  completo do projeto quando nenhum `config` é passado.

### `cartographer/cities/city_roi_zoom.py`
- ✅ `zoom_cidade_crop_raio_px`, `zoom_cidade_hf_escala`, `zoom_cidade_hf_oitavas`, `zoom_cidade_amp`
  — antes literais inline (`2`, `80.0`, `2`, `0.015`), duplicando com valores diferentes a mesma
  ideia de `roi_zoom.py`.
- 🔧 Mesmo bug de determinismo do `hash()` corrigido (usava `cid["nome"]` em vez do uuid, mesmo problema).

### `cartographer/ai/world_manager_ai.py`
- 🔧 `planejar_continentes(..., tamanho_global: int = 768)` — default nunca usado (o único
  chamador sempre passa o valor explícito); parâmetro tornado obrigatório.

### `web/helpers.py`
- ✅ `nivel_mar` — antes uma 3ª cópia hardcoded (`= 0.35`) independente do config; agora lido de
  `CARTOGRAPHER_CONFIG`.
- ✅ `escala_dinamica` — antes `48.0 * (width / 256.0)` com os dois números soltos; agora
  `shading_escala_terreno * (width / shading_escala_terreno_resolucao_base)`.
- ⚠️ `render_biomes_map_to_bytes()` (paleta própria `CORES`) — **função morta, não chamada em
  lugar nenhum do projeto**. Não migrada (não faz sentido gastar config em código não utilizado);
  considerar removê-la de vez numa limpeza futura.
- ⚠️ `Image.new("RGB", (768, 768), ...)` — placeholder para quando o `.npz` ainda não existe.
  Deixado como está (tamanho de imagem de placeholder, não parâmetro de simulação).

### `web/composed_routes.py`
- 🔧 `ROIZoomGenerator(..., config={"nivel_mar": 0.35, "nivel_montanha": 0.80})` — mais uma cópia
  hardcoded de 2 chaves; agora passa `CARTOGRAPHER_CONFIG` completo.

---

## Engine

### `engine/mechanics/logic.py` (Utility AI)
- ✅ Todos os pesos/limiares migrados para `config["ia_decisao"]`: `multiplicador_valor_fome`,
  `bonus_nao_interromper_refeicao`, `fator_fome_sem_dinheiro`, `energia_quase_descansado`,
  `energia_satisfacao_sono`, `utilidade_dormir_maxima`, `multiplicador_dormir_leve`,
  `utilidade_trabalhar`, `multiplicador_socializar_fora_happy_hour`,
  `fator_socializar_com_local_publico_pobre`, `fator_socializar_com_dependentes`,
  `multiplicador_vontade_cuidar_prole`, `bonus_cuidar_prole_fora_expediente`,
  `energia_minima_cuidar_prole`, `energia_minima_construir`, `hora_fim_construir_madrugada`,
  `utilidade_construir`, `utilidade_ociosa_base`, `bonus_dormir_medo`, `penalidade_socializar_medo`.
- 🔧 `decidir_acao`/`calcular_utilidade` agora recebem o `config.json` **completo** (antes só o
  sub-bloco `ia_decisao`), porque o gatilho "não tenho dinheiro pra comer" agora lê
  `acoes.comer.custo_pc` em vez de um `15` hardcoded solto — ligando semanticamente esse limiar ao
  custo real de uma refeição, em vez de duas constantes independentes que coincidiam por acaso.

### `engine/mechanics/actions.py`
- 🔧 `_executar_cuidar_prole`: usava `10.0`/`1.0` hardcoded para ganho social do filho / consumo de
  energia do adulto, **ignorando** as chaves `cuidar_prole_ganho_social` (15.0) e
  `cuidar_prole_consumo_energia` (2.0) que já existiam em `config.json` sem serem lidas. Corrigido.
- 🔧 `_executar_socializar`: ganho social pago usava `15.0` hardcoded, ignorando a chave
  `acoes.socializar.social_ganho` que já existia no config sem ser lida. Corrigido. Ganho gratuito
  (`5.0`) e as chances de mudar de humor (`0.2`/`0.1`) migradas para `social_ganho_gratis`/
  `chance_ficar_alegre`/`chance_ficar_triste`.
- ✅ `_executar_comer`: `multiplicador_por_dependente` (antes `0.8`), `parcelas_refeicao` (antes `3.0`).
- ✅ `_executar_ocioso`: `acoes.ocioso.social_perda` (antes `0.5`).
- ✅ `_executar_construir`: novo bloco `acoes.construir` (`energia_perda`, `fome_ganho`,
  `integridade_ganho_por_tick` — antes `1.5`/`0.5`/`10` inline).
- 🔧 Limiar de "energia quase descansada" (`85.0`) — antes duplicado independentemente aqui e em
  `logic.py`; agora ambos leem `ia_decisao.energia_quase_descansado`.

### `engine/mechanics/housing.py`
- ✅ `geracao_urbana.grid_min_px/grid_max_px` (antes `random.randint(5, 35)` — mesma faixa também
  hardcoded, separadamente, em `builder/populate.py`).
- ✅ `geracao_urbana.capacidade_padrao_residencia` (antes `capacidade=5` inline).

### `engine/mechanics/market.py`
- 🔧 SQL de bootstrap (`UPDATE locais SET categoria = ?, capacidade = 5, salario_base = 100 ...`)
  tinha `5`/`100` hardcoded direto na query. Migrado para `geracao_urbana.capacidade_padrao_local`/
  `salario_padrao_local`, lidos via `cfg_get` (JobMarket agora carrega `self.config` no `__init__`).

### `builder/populate.py`
- ✅ Novo bloco `config["geracao_populacao"]`: `casas_minimo`, `casas_divisor_por_npc`,
  `proporcao_adultos`, `idade_adulto_min/max`, `idade_idoso_min/max`, `dinheiro_inicial_min/max`,
  `casal_afinidade_min/max`, `casal_divisor_por_npc`, `amigos_min/max`, `amigo_afinidade_min/max`,
  `amigo_vinculo_limiar` — substituindo os literais que antes definiam toda a demografia inicial do
  mundo (idades, dinheiro, afinidades de casal/amizade).
- ✅ Grade de alocação de locais/casas migrada para `geracao_urbana.grid_min_px/grid_max_px`
  (mesma chave usada por `housing.py`).
- 🔧 (sessão anterior) `crescimento_dias_idoso_para_morte`: default divergente (120 aqui vs. 12 em
  `web/dashboard.py`) — corrigido, ambos usam `cfg_get` sem default próprio.

### `web/dashboard.py`
- 🔧 (sessão anterior) mesmo default divergente acima, corrigido; `json.load(config.json)` local
  substituído por `config.get_config()`.

---

## O que ficou fora de propósito (não é pendência, é decisão)
- Constantes puramente matemáticas de algoritmo (curva quíntica de Perlin, multiplicadores de hash,
  offsets de descorrelação entre oitavas/ruídos) — nunca farão sentido como config.
- `web/helpers.py: render_biomes_map_to_bytes()` — código morto, não chamado; não vale migrar
  paleta de cor para uma função que ninguém invoca.
- ~~O valor numérico do fator de conversão área→raio... não redesenhado~~ — **feito na Frente 2**
  (2026-09-09): o raio agora vem de `escala_pixel_area_km2`, ver seção de `tile_cartographer.py` acima.
