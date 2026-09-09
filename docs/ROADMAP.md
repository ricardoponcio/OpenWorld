# 🗺️ Roadmap de Evolução do OpenWorld

> **Para quem retomar este projeto (humano ou IA): leia este arquivo primeiro.**
> Ele é o índice vivo de decisões, status e próximos passos de cada frente de trabalho.
> Os documentos irmãos em `docs/` guardam o detalhe técnico de cada frente — a visão de
> conjunto e o "em que pé estamos" vivem aqui. Não é preciso reler o código do zero a cada
> sessão: comece por aqui, e só desça ao código quando for efetivamente mexer em algo.

**Criado em:** 2026-09-09 — sessão de kickoff (revisão completa do projeto + declaração de vontades do autor).

## Como manter este documento vivo

- Cada **Frente** é uma área de trabalho. Estão ordenadas pela dependência sugerida entre elas.
- Cada Frente tem: **Objetivo**, **Situação Atual** (achados concretos, não suposições), **Decisões tomadas**, **Plano de fases** e **Status**.
- Toda vez que uma sessão de trabalho avançar (decidir algo, migrar algo, corrigir algo), atualize o status da Frente correspondente e some uma linha no **Log de Sessões** no final deste arquivo.
- Status possíveis: `🔴 Não iniciado` · `🟡 Em andamento` · `🟢 Concluído` · `⏸️ Bloqueado / aguardando decisão`

## Visão de conjunto

| # | Frente | Status | Detalhe em |
|---|--------|--------|------------|
| 1 | Parametrização única (engine + cartografia) | 🟢 Concluído | Seção 1 + [`AUDITORIA_HARDCODE.md`](AUDITORIA_HARDCODE.md) |
| 2 | Qualidade e variedade visual da cartografia | 🟡 Em andamento | Seção 2 |
| 3 | Comportamento dos NPCs (Utility AI) | 🟡 Em andamento | Seção 3 |
| 4 | Motor de tempo 1:1 real (Rebalanceamento Total) | 🟢 Concluído | Seção 4 (decisão revista: Abordagem 2, não 3 — ver [`ANALISE_REALTIME_1_1.md`](ANALISE_REALTIME_1_1.md)) |
| 5 | Modo Mestre de IA (2º modo temporal) | 🟢 Concluído (fase 1) | Seção 5 (design original em [`MODO_MESTRE_IA.md`](MODO_MESTRE_IA.md)) |
| 6 | Mapa interativo estilo Leaflet ("Google Maps da aventura") | 🔴 Não iniciado | [`MAPA_INTERATIVO.md`](MAPA_INTERATIVO.md) |

**Ordem sugerida de execução: 1 → 2 → 3 → 4 → 5 → 6.**
Motivo: a Frente 1 é fundação das Frentes 2 e 3 (não compensa retunar cartografia ou comportamento
enquanto os números continuam espalhados — você mexeria duas vezes no mesmo lugar). A Frente 5
depende arquiteturalmente da Frente 4 (o Modo Mestre pausa/avança o *mesmo* relógio que a Frente 4
vai reconstruir). A Frente 6 é a mais independente das seis e pode ser adiantada a qualquer momento
se surgir vontade, mas fica por último por ser a menos urgente para a simulação em si.

---

## Frente 1 — Parametrização única

### Objetivo (nas palavras do autor)
"Existem muitos valores jogados hardcode no código, na cartografia, em geral, e eu queria primeiro
garantir que tudo é parametrizável de um ponto único... deixar eles jogados deixa tudo muito confuso."

### Situação atual (achados verificados em 2026-09-09)

Hoje existem **três sistemas de configuração paralelos e desalinhados**, não um só:

1. **`config.json`** (raiz) — usado pela `engine/` via `cfg_get()` (filosofia *fail-fast*: erro
   explícito se faltar uma chave, sem defaults silenciosos). Cobre metabolismo, ações, decisão de
   IA, biologia/sociedade, reino e infraestrutura. **Bem feito**, mas só cobre a simulação social/econômica.
2. **`cartographer/config.py`** (`CARTOGRAPHER_CONFIG`) — dict Python com os parâmetros "oficiais"
   de geração de mapa (ruído, tectônica, clima, zoom). Não é JSON, não passa por `cfg_get`, não tem
   validação — é lido diretamente como dict com `.get()`/indexação solta pelo resto da cartografia.
3. **Dezenas de números soltos direto no código**, em três formas diferentes:
   - *Default de parâmetro de função* que na prática nunca recebe outro valor (ex.: `shading.py:
     escala_terreno=48.0`, `tectonics.py: scale=120.0, amplitude=65.0`).
   - *Constante de classe duplicada* que **ignora** `cartographer/config.py` mesmo quando os nomes
     e valores parecem "iguais" (ex.: `noise.py: NoiseGenerator.DEFAULT_TECTONIC_MACRO_SCALE = 220.0`
     coincide hoje com `CARTOGRAPHER_CONFIG["ruido_macro_escala"]`, mas é outra variável — editar uma
     não afeta a outra).
   - *Literal cru inline*, sem nome nem config (ex.: toda a paleta de cores em `coloring.py`, os
     thresholds de mistura por altitude `0.65`/`0.35`, os offsets de ruído `7777`/`9999`/`8888`/
     `11111`/`22222`, o clamp de raio `65.0`/`155.0`).

Essa dispersão já **causou inconsistências reais**, verificadas linha a linha (não hipóteses):

| # | Achado | Onde | Impacto observável |
|---|--------|------|---------------------|
| 1 | `nivel_montanha` tem **dois valores diferentes** coexistindo | `cartographer/config.py` = `0.8` **vs** `climate.py: ClimateProcessor.DEFAULT_NIVEL_MONTANHA` = `0.75` | O limiar de "Montanha Rochosa" muda dependendo de qual dos dois é efetivamente lido em cada chamada |
| 2 | `persistencia` e `lacunariedade` são **parâmetros mortos** | `CARTOGRAPHER_CONFIG` declara `"persistencia": 0.5, "lacunariedade": 2.1`, mas `noise.py: generate_noise_field()` hardcoda `amplitude *= 0.5` e `frequency *= 2.0` direto no loop de oitavas, sem nunca ler essas duas chaves | Editar essas chaves no config **não muda nada visualmente** — falsa sensação de controle |
| 3 | Tamanho do mundo (768×768, ou seja 3×3 tiles de 256px) está **hardcoded em pelo menos 2 lugares matemáticos** | `tile_cartographer.py`: `apply_cosine_vignette(..., map_size=768.0)` e `calculate_temperature(..., map_height=768.0)` | Mudar `WorldManager(tile_size=..., ...)` para gerar um mundo maior/menor quebra silenciosamente a vinheta de borda e o gradiente de latitude/temperatura |
| 4 | Raio visual dos continentes tem um **clamp duro que anula a variação de área vinda da IA** | `tile_cartographer.py`: `R = np.clip(R, 65.0, 155.0)` | A IA (ou o fallback) gera `area_km2` entre 1.000.000 e 6.000.000 (proporção 6×), mas depois do clamp o raio em pixels varia muito pouco. **Esta é a causa raiz mais provável de "mapas muito parecidos/limitados"** — ver comparação visual na Frente 2 |
| 5 | A conversão área→raio usa um fator **mágico e desacoplado** da escala oficial do projeto | `tile_cartographer.py`: `R = sqrt(area_km2 / pi) / 10.0` (o `/10.0` não vem de config nem é documentado), enquanto a escala "oficial" `escala_pixel_area_km2 = 250` (km² por pixel) só é usada depois, em `world_manager.py`, para *calcular estatísticas* do manifesto a partir da área **real** desenhada | As duas contas nunca foram unificadas: a área que a IA "pediu" e a área que o manifesto reporta no fim não descrevem geometricamente o mesmo raio |
| 6 | `raio_visual` gerado pela IA/fallback é **campo morto** na prática | `world_manager_ai.py` gera `"raio_visual": random.randint(150, 250)` | Só é lido se `area_km2 <= 0`, o que quase nunca acontece — o valor é gerado e descartado |
| 7 | Seed de ruído do zoom **não é determinístico entre execuções** | `roi_zoom.py`: `cont_seed_offset = abs(hash(cont_uuid)) % 40000` | `hash()` de string em Python é aleatorizado por processo (salvo `PYTHONHASHSEED=0`). Cada vez que o `.npz` de zoom de um continente é apagado e regenerado, o micro-relevo **muda**, contradizendo o próprio docstring do método ("relevo micro-detalhado único e **reprodutível**") |
| 8 | Paleta de biomas é fixa e sem variação por semente/tema | `coloring.py: CORES_BASE` + todos os breakpoints `0.65`/`0.35` cravados inline | Todo mundo gerado usa exatamente as mesmas 4 cores de bioma terrestre — contribui para "mapas limitados" |
| 9 | `nivel_mar` está hardcoded de forma redundante em pelo menos 3 lugares fora do config | `web/helpers.py: render_npz_map_to_bytes()` (`nivel_mar = 0.35`), `roi_zoom.py.__init__` (default dict), `climate.py: DEFAULT_NIVEL_MAR` | Três cópias do mesmo número; mudar o nível do mar no config não propaga para o renderer web |

Catálogo completo, item a item (arquivo, linha, valor atual, chave de config sugerida), está em
**[`AUDITORIA_HARDCODE.md`](AUDITORIA_HARDCODE.md)** — use-o como checklist de migração.

### Decisões tomadas
- ✅ **Formato do config único**: `config.json` na raiz, fundindo a cartografia sob uma nova seção
  `"cartografia": {...}`. Implementado via um pacote novo, **`config/`** (raiz do projeto), com duas
  peças separadas: `config/sources.py` (`ConfigSource`/`JsonFileConfigSource` — de onde os dados vêm)
  e `config/resolver.py` (`cfg_get`/`get_config` — como o código lê, sempre estrito/fail-fast, igual
  ao `cfg_get` original da engine). Trocar a fonte no futuro (YAML/env/banco) é escrever uma nova
  `ConfigSource` e chamar `configurar_fonte()` — nenhum call-site do projeto muda.
- ✅ Constantes puramente matemáticas do algoritmo (multiplicadores do hash de Perlin, curva
  quíntica) **não** viraram config — confirmado como decisão ao migrar `noise.py`.
- `engine/config_loader.py` e `cartographer/config.py` viraram **shims finos** que reexportam de
  `config/` (mantendo os nomes históricos `cfg_get`, `carregar_config_global`, `CARTOGRAPHER_CONFIG`)
  em vez de serem apagados — reduz o tamanho do diff de migração sem abrir uma segunda fonte de verdade.

### Progresso desta sessão (2026-09-09, parte 2)
- [x] Pacote `config/` criado (`sources.py`, `resolver.py`, `__init__.py`).
- [x] `engine/config_loader.py` migrado para shim de `config/`.
- [x] `cartographer/config.py` migrado para shim (`CARTOGRAPHER_CONFIG` agora vem de
      `config.json["cartografia"]`, não é mais um dict escrito à mão).
- [x] `web/dashboard.py` e `builder/populate.py` migrados do `json.load` próprio para o resolver
      compartilhado — **corrigido** o default divergente de `crescimento_dias_idoso_para_morte`
      (12 vs 120, achado da auditoria).
- [x] Bloco **ruído** (`cartographer/math/noise.py`) migrado: `generate_tectonic_base` agora exige
      `config` e lê tudo via `cfg_get`; `persistencia`/`lacunariedade` (antes parâmetros mortos) e o
      peso de mistura macro/detalhe agora vêm de config. *Mudança de aparência intencional*: a
      lacunaridade real da base tectônica passa a ser 2.1 (config) em vez de 2.0 hardcoded.
- [x] Bloco **tectônica** (`tectonics.py`) migrado por completo: warp de domínio, fator de raio
      dinâmico, distorção costeira, perfis geológicos (Platô/Arquipélago) e vinheta de borda.
      **Corrigido**: `map_size`/`map_height` (antes `768.0` fixo em 2 lugares) agora vêm de
      `WorldManager.tamanho_global`, calculado a partir de `mundo_tiles_por_lado × tile_size` — um
      único lugar define o tamanho do mundo, em vez de dois literais que podiam divergir.
- [x] Bloco **clima** (`climate.py`) migrado por completo. Resolvida a inconsistência do
      `nivel_montanha` (0.8 vs 0.75 morto) removendo as constantes de classe duplicadas.
- [x] Bloco **cor/shading** (`coloring.py`, `shading.py`) migrado por completo. `CORES_BASE` (dict
      morto, nunca usado) removido; os 4 blocos de código quase-idênticos de interpolação de cor por
      bioma foram unificados numa única função genérica dirigida por config.
- [x] Bloco **zoom** (`roi_zoom.py`, `city_roi_zoom.py`) migrado por completo. **Bug de determinismo
      corrigido**: `hash()` nativo (aleatorizado por processo) trocado por `zlib.crc32` — verificado
      nesta sessão que regenerar o mesmo continente duas vezes agora produz bytes idênticos.
- [x] Duplicações de config fora dos módulos de cartografia também corrigidas:
      `web/composed_routes.py` e `web/helpers.py` tinham cada um sua própria cópia de
      `nivel_mar`/`nivel_montanha`/`escala_terreno` — agora todos leem do mesmo `CARTOGRAPHER_CONFIG`.
- [x] Lado **engine** também migrado (a Frente 1 sempre incluiu engine, não só cartografia):
      pesos da Utility AI (`logic.py`), custos/ganhos de ações (`actions.py`), grade urbana
      (`housing.py`, `market.py`, `builder/populate.py`) e demografia inicial do povoamento
      (`builder/populate.py`). **2 bugs reais corrigidos**: `_executar_cuidar_prole` e
      `_executar_socializar` ignoravam chaves que já existiam no `config.json` (usavam números
      hardcoded diferentes dos valores configurados) — agora leem as chaves de verdade.
- [x] Catálogo completo (com todos os itens marcados) em `AUDITORIA_HARDCODE.md`.

### Plano de fases
1. ~~Consolidar `AUDITORIA_HARDCODE.md`~~ ✅
2. ~~Definir o formato final do config único~~ ✅
3. ~~Migrar cartografia para o config único, bloco por bloco~~ ✅ (ruído, tectônica, clima, cor/shading, zoom)
4. ~~Remover os `default=` de função que mascaravam parâmetros de config~~ ✅
5. ~~Corrigir as inconsistências já detectadas como parte da migração~~ ✅ (`nivel_montanha`,
   `persistencia`/`lacunariedade`, tamanho do mundo duplicado, `hash()` não determinístico, 2 bugs
   de config ignorado em `actions.py`)

**O que fica de propósito para a Frente 2** (não é pendência desta frente, é o objetivo dela): o
*valor* do clamp de raio continental e da fórmula área→raio foram centralizados mas não
redesenhados — decidir se/como tornar os continentes mais variados em tamanho e forma é trabalho de
qualidade visual, não de parametrização.

### Status: 🟢 Concluído (2026-09-09) — engine e cartografia inteiras lendo de um único `config.json` através do pacote `config/`. Ver `AUDITORIA_HARDCODE.md` para o registro completo do que foi migrado/corrigido.

---

## Frente 2 — Qualidade e variedade visual da cartografia

### Objetivo (nas palavras do autor)
"Os mapas geram sem problemas e são até bons, mas muito limitados e com defeitos visuais graves."

### Situação atual (evidência visual, 2026-09-09)

Inspecionei os prints existentes em `images/` (`webui-map-full.png`, `webui-map-continent.png`) e
encontrei defeitos concretos, não apenas hipotéticos:

**No mapa mundi (`webui-map-full.png` / `webui-map.png`):**
- Todos os continentes são "blobs" orgânicos isolados, de tamanho visualmente muito parecido —
  apesar de o painel lateral do dashboard mostrar áreas de 756.750 km² a 4.462.000 km² (quase 6× de
  diferença), a diferença visual entre eles é pequena. **Causa raiz identificada**: achado #4 e #5
  da Frente 1 (clamp de raio 65–155px + fórmula de conversão desacoplada da escala oficial).
- Continentes nunca se tocam nem formam massas maiores (nunca há um "supercontinente" ou baías
  compartilhadas entre dois continentes) — decorre de cada continente ser desenhado independente via
  `np.maximum` de máscaras radiais próprias. Isso limita estruturalmente a variedade geográfica.
- Há uma "auréola" ciano brilhante ao redor de cada continente, bem mais larga do que um recife raso
  razoável. **Causa provável**: `ColoringProcessor.render_ocean()` usa uma curva de potência 6 sobre
  `heightmap / nivel_mar`, e como a transição de altitude perto da costa é suave (por causa da
  vinheta e do raio dinâmico), a faixa de "água rasa" acaba muito mais larga do que o pretendido pela
  descrição do próprio README ("Glowing Reefs" deveria ser uma faixa fina perto da costa).

**No zoom de continente (`webui-map-continent.png`):**
- É visível um **padrão de grade/quadriculado** sutil sobre todo o terreno (mais visível em áreas
  planas) — um artefato de textura, não relevo real. É a pista mais forte de "defeito visual grave".
  Hipótese técnica a validar: interação entre a grade de amostragem do ruído Perlin de zoom
  (`_apply_micro_detail` em `roi_zoom.py`) e a interpolação bilinear do upscale (`_upscale`), possivelmente
  agravada pela falta de qualquer *dithering*/blur pós-processamento na costura dessas duas etapas.
- O terreno é visualmente **muito plano e monocromático** (um único tom de verde dominante), com
  pouquíssima variação perceptível de altitude apesar de o hillshading existir — reforça o achado #8
  da Frente 1 (paleta fixa de 4 biomas, sem gradiente perceptível de cor por elevação real).
- A auréola ciano ao redor da costa é, de novo, desproporcionalmente larga e domina a composição.

**Histórico relevante**: o commit `1dd6b9f`/`a475b01` ("Correção de papel amassado no zoom") e os
comentários em `cartographer/config.py` ("Suavização Anti 'Papel Amassado'") mostram que esse tipo de
artefato **já apareceu antes e foi parcialmente mitigado** (reduzindo peso/oitavas do ruído de alta
frequência), mas a grade visível no print sugere que o efeito não foi eliminado, só atenuado — ou
voltou por outra via (upscale bilinear).

### Investigação e causa raiz confirmada (2026-09-09)

Reproduzi o artefato de grade isoladamente (arquivos de scratch, sem tocar no mundo real) antes de
mudar qualquer número, seguindo o plano de fases original:

- **Causa raiz do "papel amassado" confirmada**: o recorte do continente vem do mapa global de baixa
  resolução (768×768 → um continente típico ocupa só ~100-170px) e é ampliado (*upscale*) para
  600-3000px — um fator de 3.5× a ~20×. `roi_zoom.py`/`city_roi_zoom.py` faziam esse upscale com
  interpolação **bilinear** (`scipy.ndimage.zoom order=1`) — e pior: **`scipy` nunca esteve em
  `requirements.txt`**, então na prática ninguém tinha o scipy instalado e todo mundo rodava o
  fallback manual (bilinear em numpy puro) sem saber. Bilinear preserva continuidade de valor mas não
  de curvatura — sobra uma estrutura de "célula" do pixel de origem, invisível na altitude crua, mas
  **amplificada num padrão de grade visível** pelas máscaras não-lineares de `_apply_micro_detail` e
  pelo gradiente do hillshading. Confirmei isolando o canal de altitude e subtraindo uma versão
  borrada — o padrão de grade aparece espaçado exatamente na proporção do fator de upscale.
- **Achado extra durante a investigação**: `city_roi_zoom.py` recortava um raio de **2 pixels**
  (janela 5×5!) do mapa global antes de ampliar — praticamente nenhum relevo real sobra pra desenhar,
  o mapa de cidade era essencialmente ruído sintético sobre uma altitude quase constante. Explica o
  visual "chapado" do `webui-map-city.png`.
- **Halo de água rasa**: confirmado nos prints, causa é a curva de `render_ocean` usar toda a coluna
  de profundidade (0 até nivel_mar) como domínio do gradiente de brilho, em vez de só a faixa mais
  próxima da costa.

### Decisões tomadas
- ✅ `scipy` promovido a dependência real do projeto (estava sendo usado oportunisticamente há tempos
  sem nunca ter sido declarado).
- ✅ Upscale trocado de bilinear (`order=1`) para spline cúbico (`order=3`), com suavização gaussiana
  leve pós-upscale antes de qualquer máscara/hillshading — elimina a estrutura de célula residual.
  Fallback manual (sem scipy) mantido funcional, mas agora **avisa no log** que a qualidade é inferior
  (antes o fallback era silencioso).
- ✅ Raio do continente agora vem da área real via `escala_pixel_area_km2` (a mesma escala "oficial"
  já usada para reportar estatísticas no manifesto), não mais de um clamp fixo que comprimia toda a
  variação. `continente_raio_min_px/max_px` viraram guarda-corpo de segurança, não a fonte do tamanho.
- ✅ `render_ocean` redesenhada: só a fração mais próxima do nível do mar (`faixa_rasa_amplitude`,
  nova chave) participa do gradiente de brilho; resto do oceano fica na cor profunda uniforme. Curva
  de potência também subiu de 6 para 10 para reforçar o efeito.
- ✅ `zoom_cidade_crop_raio_px` aumentado de 2 para 15px — achado extra corrigido junto.

**Verificado visualmente** (arquivos de scratch, mundo de teste): grade desapareceu completamente
(terreno liso e orgânico em close-up), halo ficou fino, e os 5 continentes de um mesmo mundo agora
têm tamanhos claramente diferentes entre si (variando de ~257k a ~1M km² reais no teste), proporcional
à área declarada — antes todos pareciam do mesmo tamanho.

### Fora de escopo desta rodada (fica para próxima sessão desta frente)
4. Ampliar a paleta de biomas/cores (hoje 5 IDs fixos) e/ou introduzir variação de matiz por semente —
   decisão de estilo, melhor avaliada depois que os defeitos estruturais acima forem revisados pelo
   autor, para não misturar "consertar bug" com "mudar de estilo" na mesma leva.
5. Avaliar se o mundo global (768×768, 3×3 tiles) comporta continentes encostando uns nos outros, ou
   se isso exige aumentar `mundo_tiles_por_lado` — mudança de escala de custo computacional maior.

### Status: 🟡 Em andamento — itens 1-3 do plano original concluídos e verificados visualmente; itens 4-5 (paleta/variedade de matiz, tamanho do mundo) pendentes de revisão visual do autor antes de prosseguir.

### Status: 🔴 Não iniciado

---

## Frente 3 — Comportamento dos NPCs (Utility AI)

### Objetivo (nas palavras do autor)
"O comportamento dos NPCs em geral não é muito correto, eles fazem o que é pra ser feito, mas
existem algumas coisas que podemos melhorar com parâmetros e outras que teremos que ajustar."

### Situação atual (achado concreto e verificado, 2026-09-09)

Ao inspecionar o print `images/webui-npcs.png`, **100% dos NPCs listados exibem humor "Alegre"**.
Investiguei o código e confirmei a causa — não é coincidência do print, é estrutural:

```
grep "humor\s*=\|HumorNPC\." em engine/:
  reproduction.py:119  → bebê nasce com humor = ALEGRE
  actions.py:164       → Socializar com sucesso: 20% de chance de virar ALEGRE
  actions.py:172       → Socializar sem dinheiro: 10% de chance de virar TRISTE
  logic.py:118         → só LEITURA: se humor ∈ {PANICO, MEDO, ANGUSTIADO}, ajusta utilidades
```

Ou seja:
- **Não existe nenhum caminho que decaia o humor de volta a "Neutro"** — uma vez Alegre, o NPC fica
  Alegre para sempre (a não ser que role o dado de Triste na próxima Socialização sem dinheiro).
  Isso é um "catraca" (ratchet) que empurra toda a população para Alegre ao longo do tempo, exatamente
  o que o print mostra.
- Os estados `Contente`, `Angustiado`, `Pânico`, `Amedrontado` do enum `HumorNPC` **nunca são
  atribuídos em nenhum lugar do loop de simulação** — são lidos (`logic.py:118`) mas nunca escritos
  pelo motor. O branch de "medo/pânico" na Utility AI é código morto hoje.
- A **única** via que consegue de fato escrever esses humores é `builder/storyteller.py` (comando
  `AFETAR_NPC`), que é um script manual e desconectado do loop principal (ver Frente 5 — é também a
  base do futuro Modo Mestre de IA).

Outros pontos observados durante a leitura de `logic.py`/`actions.py`/`movement.py`, ainda **não
endereçados** (candidatos para uma próxima rodada desta frente, não escolhidos pelo autor ainda):
- A movimentação é "teleporte" direto entre locais nomeados (sem trajeto/pathing contínuo) — pode ou
  não ser aceitável dependendo do quanto o 1:1 (Frente 4) vai deixar isso visualmente evidente.
- `num_dependentes` é recalculado do zero a cada tick, por NPC, iterando todos os moradores da casa
  duas vezes por tick (uma em `loop.py`, outra dentro de `actions.py:_executar_comer`) — não é um bug
  de comportamento, mas é redundância que vale revisar quando formos mexer nessa área.
- ~~Limiares de utilidade hardcoded~~ — **já migrados para config** na Frente 1 (ver
  `config.json["ia_decisao"]` e `AUDITORIA_HARDCODE.md`).

### Decisões tomadas (2026-09-09)
- Autor confirmou: começar pelo achado já identificado (humor), sem exemplos novos por enquanto —
  se notar algo mais, sinaliza depois.
- **Humor deixou de ser uma flag setada ad-hoc e virou um retrato contínuo do bem-estar** (energia +
  fome invertida + social, pesos configuráveis), recalculado a cada tick com transição gradual (não
  instantânea) em direção a um humor-alvo. Implementado em `engine/mechanics/mood.py`
  (`NPCMoodManager`), chamado a cada tick em `loop.py`. A lógica ad-hoc que existia em
  `actions.py::_executar_socializar` (setar Alegre/Triste direto) foi removida — socializar continua
  afetando `social` normalmente, que já alimenta o cálculo unificado.
- Pânico/Medo ficam fora do cálculo normal de bem-estar — continuam reservados para serem forçados
  externamente (hoje só via `AFETAR_NPC` do `builder/storyteller.py`, base da futura Frente 5). O
  mesmo mecanismo de transição gradual já traz o NPC de volta ao humor calculado quando ele deixa de
  estar em Pânico/Medo, sem precisar de código especial — **verificado** nesta sessão.

**Verificado**: rodei a engine por 200 ticks reais — humor deixou de convergir para 100% Alegre,
varia organicamente entre Neutro/Contente/Alegre (mundo com economia saudável, esperado ficar mais
pra cima). Forçando fome/energia/social ruins num NPC isolado, o humor degradou passo a passo
Alegre → Contente → Neutro → Triste → Angustiado ao longo de ~40 ticks, e se recuperou ao inverter as
condições — confirma que o "bug de catraca" está corrigido e o sistema reage a mudanças reais de
estado, não só a uma rolagem de dado isolada.

### Questões em aberto para decidir juntos
1. Quais comportamentos específicos de NPC o autor já percebeu como incorretos além do humor? Ainda
   em aberto — autor optou por não listar agora; retomar quando/se notar algo observando o jogo.

### Plano de fases
1. ~~Levantar achado concreto e corrigir o humor~~ ✅
2. Reavaliar os candidatos ainda não endereçados (teleporte de movimento, redundância de
   `num_dependentes`) quando o autor sinalizar mais comportamentos ou quiser voltar a esta frente.

### Status: 🟡 Em andamento — correção do humor concluída e verificada; demais candidatos aguardando
observação de jogo real do autor antes de seguir.

---

## Frente 4 — Motor de tempo 1:1 (Engrenagens Híbridas)

### Objetivo (nas palavras do autor)
Implementar a Abordagem 3 já desenhada em `docs/ANALISE_REALTIME_1_1.md` ("Engrenagens Híbridas"),
permitindo sair da velocidade fixa de 1 tick = 15 minutos simulados para **1 tick = 1 minuto**
simulado, com o tempo real também podendo variar de 1x até Nx (sem o piso atual de 15 minutos por
tick).

### Decisão revista nesta sessão (2026-09-09): Abordagem 2, não Abordagem 3

`docs/ANALISE_REALTIME_1_1.md` recomendava a Abordagem 3 ("Engrenagens Híbridas": tick fino de 1 min
só pra mover o relógio, com a física pesada presa a um portão interno de 15 em 15 minutos). Propus
essa abordagem primeiro; **o autor rejeitou** — objeção correta: isso seria "fingir" 1:1, o motor
continuaria amarrado a múltiplos de 15 por baixo dos panos, só escondido um nível abaixo, e voltaria
a causar problema mais tarde (ex.: o Modo Mestre de IA da Frente 5 querendo avançar um número de
minutos que não seja múltiplo de 15). A decisão final foi a **Abordagem 2 (Rebalanceamento Total)**:
o tick vira genuinamente 1 minuto e **tudo que hoje roda a cada tick continua rodando a cada tick**
— sem nenhum portão de N ticks escondido em lugar nenhum — com os números de `config.json`
recalculados para a nova escala.

### Implementado (2026-09-09)
- `engine/loop.py`: `timedelta(minutes=15)` → `timedelta(minutes=1)`. Resto do fluxo idêntico.
- `config.json` recalculado em 3 categorias (não é "dividir tudo por 15" ingenuamente):
  1. **Taxas por tick** (perda de energia, ganhos de fome/social, salário, custos de ação) → ÷15.
  2. **Probabilidades por tick** (`interacao_chance`, `casamento_chance_coabitacao`,
     `humor_chance_transicao` da Frente 3) → fórmula de probabilidade composta
     `p_min = 1-(1-p_15min)^(1/15)`, não divisão simples (dividir uma chance por 15 não preserva a
     frequência real do evento ao longo do tempo).
  3. **Contadores de duração** (`gravidez_duracao_ticks`, `acoes.comer.parcelas_refeicao`) → ×15.
  `concepcao_chance`/`concepcao_chance_superlotacao` **não mudaram** — são sorteadas 1x por noite,
  não por tick, então já eram independentes do tamanho do tick.
- **Dinheiro virou fracionário**: `NPC.dinheiro_total_pc` (`models.py`) e a coluna no
  `schema.sql`/`database.py` mudaram de inteiro para `float` — pagar salário a cada minuto (em vez
  de a cada 15) gera frações de PC. Formatação em po/pp/pc arredonda só na exibição
  (`dinheiro_formatado`, `web/dashboard.py::formatar_moeda`). **Bug pego durante a implementação**:
  `actions.py::_executar_comer` tinha dois `int()`/`max(1, ...)` que truncavam o custo por tick —
  com `parcelas_refeicao` 15× maior, isso teria forçado um piso de gasto 3x maior que o pretendido;
  removidos.
- `run_simulation.py`: espera real recalculada (`60.0/velocidade` — 1:1 de verdade em 1x). Os
  gatilhos `ticks % 20`/`ticks % 96` (que dependiam do tamanho do tick pra significar um intervalo
  real) viraram checagens de `engine.data_simulada.hour/minute`, no mesmo estilo já usado dentro do
  `loop.py` — elimina de vez qualquer contagem de ticks brutos do projeto.
- Botões de velocidade do dashboard (`web/templates/index.html`): **1x** (tempo real, padrão ao
  carregar — decisão do autor), **60x** ("pouco"), **360x** ("médio"), **1440x** ("muito"),
  **21600x** ("muito muito", ~15 dias de jogo por minuto real).

### Verificado (2026-09-09)
- 8h de trabalho contínuo = 160 PC ganhos, idêntico ao ritmo antigo (5 PC/tick de 15min).
- 1h de metabolismo base = fome sobe entre 1.6 e 3.2, mesma faixa de antes (4 ticks de 15min ×
  0.4-0.8).
- Uma gravidez completa (2880 ticks novos) dura exatamente 48h simuladas — igual a antes.
- Gatilhos de mercado (a cada 5h) e infraestrutura (1x/dia) disparam na cadência certa (testado com
  1440 ticks = 1 dia: 5 disparos de mercado, 1 de infraestrutura).
- Matemática de velocidade confirmada: a 600x, cada tick espera exatamente 0.1s real; 20 ticks
  avançam exatamente 20 minutos de jogo.
- **Custo de performance medido** (trade-off avisado no plano, não escondido): 1440 ticks (1 dia de
  jogo) levam ~1.76s de parede nesta máquina — extrapolando, "rodar 1 milhão de ticks" (≈ 694 dias de
  jogo) levaria ~20 minutos reais de CPU. Isso é 15× mais trabalho por hora de jogo do que antes
  (inclui 15× mais escritas por NPC no SQLite a cada tick). Não otimizado nesta fase — fica
  registrado como candidato a uma frente própria de performance/batching de escrita se um dia isso
  incomodar na prática.

### Fora de escopo desta fase
- Otimização de I/O para velocidades muito altas (medido, não resolvido).
- Movimentação visual contínua ("formigueiro" andando entre locais) — a engine não tem sistema de
  posição interpolada; é uma feature própria, não parte de "consertar o relógio". Candidata natural
  para quando a Frente 6 (mapa interativo) estiver em andamento.

### Status: 🟢 Concluído — tempo 1:1 real implementado e verificado quantitativamente (não just "parece certo").

---

## Frente 5 — Modo Mestre de IA (2º modo temporal)

### Objetivo (nas palavras do autor)
Um segundo "modo temporal" onde o tempo pausa, e um Mestre de IA usa o contexto atual do mundo para
narrar em tempo real, colaborando com o jogador na aventura; o jogador decide quanto tempo avançar, e
depois pode ver os efeitos desse avanço na narração.

### Situação atual — **achado importante: já existe um protótipo funcional deste conceito**
Durante a revisão encontrei `builder/storyteller.py` + `engine/ai/storyteller.py`, que hoje já fazem,
de forma manual/CLI (não integrada ao dashboard nem ao loop), quase todo o backend necessário:

1. **Coleta de contexto do mundo** (`storyteller.py: run_storyteller`): NPCs, locais ativos,
   relacionamentos com afinidade não-nula, últimos 10 eventos, eventos globais ativos — tudo
   serializado em JSON e injetado num prompt.
2. **Geração via LLM local** (`AIStorytellerClient.gerar_evento_global`, com fallback procedural
   determinístico se o Ollama estiver offline) de um evento estruturado: título, descrição, tipo,
   modificadores de utilidade por ação, duração em ticks, e uma lista de **ações de mundo**.
3. **Aplicação direta das ações de mundo no banco**: `CRIAR_LOCAL`, `DESTRUIR_LOCAL`,
   `REATRIBUIR_NPC` (muda emprego/casa de um NPC), `AFETAR_NPC` (altera saúde e **humor** — é o único
   lugar do sistema hoje que consegue de fato escrever Pânico/Medo/Angustiado, ver Frente 3).

O que falta para virar o "Modo Mestre" descrito pelo autor é essencialmente **orquestração e
interface**, não reconstruir a parte de IA:

- Hoje é um script batch de mão única (`python3 builder/storyteller.py Tema` → aplica e sai). Falta
  um ciclo interativo: pausar → conversar com a IA (ida e volta, não só um evento por chamada) →
  decidir quanto tempo avançar → rodar esse tanto de tempo → resumir para a IA (e para o
  usuário) o que aconteceu nesse intervalo, usando os eventos gravados em `eventos`/`eventos_globais`.
- Falta a integração com a pausa real da simulação (`mundo_meta.simulacao_pausada`, já existe e é
  usada pelo dashboard) — hoje o script roda independente de a simulação estar pausada ou não.
- Falta superfície no dashboard (uma aba/painel "Mestre de IA") para essa conversa acontecer, em vez
  de terminal.
- O tema hoje é hardcoded como "Cyberpunk" por padrão no `storyteller.py`, inconsistente com o tema
  "Fantasia Medieval" usado no resto do mundo (`populate.py`) — pequeno acerto necessário.
- Depende da Frente 4 (tempo 1:1) para a parte de "avançar o tempo o quanto for decidido" ser
  granular — hoje só dá para avançar em blocos de 15 minutos por tick.

### Decisões tomadas (2026-09-09)
- **Ações de mundo propostas pela IA exigem confirmação do jogador** antes de aplicar (não aplica
  direto como o script antigo fazia).
- **Esta fase entra com backend completo + uma aba simples de chat no dashboard** (não polida
  visualmente, mas funcional para uso real numa mesa).
- Arquitetura: o dashboard Flask **não** instancia uma segunda `SimulationEngine` — "avançar N
  minutos" sinaliza via `mundo_meta` (`mestre_avancar_minutos_restantes`), mesmo padrão já usado por
  pausa/velocidade, e o `run_simulation.py` (único dono da engine) consome esse contador.

### Implementado
- `engine/mechanics/mestre.py` (`MestreManager`): extrai a coleta de contexto e a aplicação das 4
  ações de mundo (`CRIAR_LOCAL`/`DESTRUIR_LOCAL`/`REATRIBUIR_NPC`/`AFETAR_NPC`) de
  `builder/storyteller.py` para uso compartilhado — o script antigo agora *chama* essas funções em
  vez de duplicar a lógica, e seu tema padrão foi corrigido de "Cyberpunk" para "Fantasia Medieval"
  (consistente com `builder/populate.py`).
- `engine/ai/game_master.py` (`AIGameMasterClient`): irmão de `AIStorytellerClient`, aceita
  histórico de conversa e devolve `{"narracao", "acoes_propostas"}` — narração sempre livre, ações
  sempre opcionais e nunca aplicadas sozinhas. Fallback determinístico se o Ollama estiver offline.
- Tabela `mestre_conversas` (`schema.sql`) + métodos em `database.py` para histórico persistente.
- `run_simulation.py`: enquanto pausado, se `mestre_avancar_minutos_restantes > 0`, tica e decrementa
  sem o sleep de ritmo normal (roda o mais rápido possível), voltando a respeitar a pausa ao chegar a 0.
- `web/mestre_routes.py` (novo blueprint): `POST /mensagem`, `POST /confirmar_acoes`,
  `POST /avancar_tempo` (espera o `run_simulation.py` consumir, coleta eventos do período via rowid
  — não pelo texto do timestamp, que não ordena corretamente —, narra o que aconteceu),
  `GET /historico`, `GET /estado`.
- Aba "🎭 Mestre" no dashboard (`index.html` + `dashboard.js`): chat, botões de avanço rápido
  (15min/1h/6h/1dia), painel de confirmar/ignorar ações propostas.

### Verificado (2026-09-09)
- Testado de ponta a ponta com Ollama real (não só o fallback): mensagens geram narração coerente
  em português; ações de mundo aplicam corretamente no banco (`CRIAR_LOCAL`, `AFETAR_NPC` testados
  diretamente); confirmar a mesma ação duas vezes é bloqueado (idempotência).
- Fallback testado forçando falha de conexão com o Ollama — devolve narração de aviso em vez de quebrar.
- Fluxo completo de `avancar_tempo` testado com um consumidor rodando em thread separada (simulando
  o `run_simulation.py` real): avançou exatamente os minutos pedidos, coletou os eventos do período e
  narrou com base neles.
- Testes rodados contra uma **cópia de scratch do banco**, não o banco de produção — nada foi
  aplicado no mundo real do autor durante o desenvolvimento desta frente.

### Fora de escopo desta fase
- IA agir sozinha durante avanços rápidos sem o jogador chamar.
- Troca do modelo de LLM (continua `qwen2.5-coder:7b`).
- Polimento visual da aba.

### Status: 🟢 Concluído (fase 1) — backend + aba funcional no ar; refinamento visual e eventos espontâneos ficam para depois.

---

## Frente 6 — Mapa interativo estilo Leaflet ("Google Maps da aventura")

### Objetivo (nas palavras do autor)
Portar/reaproveitar os `.npz` para algum formato de "Google Maps da aventura", com Leaflet.

### Situação atual
- Já existe toda a infraestrutura de dados necessária: mapas `.npz` em 3 escalas (mundo composto
  768×768, zoom de continente ~3000×3000 sob demanda, zoom de cidade ~800×800 sob demanda), com cache
  em memória por mtime (`composed_routes.py`) e um renderer NumPy→PNG (`web/helpers.py:
  render_npz_map_to_bytes`).
- **Gap principal**: o renderer atual gera **uma imagem única e inteira** por chamada, não o esquema
  de *tiles* em pirâmide (`{z}/{x}/{y}.png`, 256×256px cada) que o Leaflet espera nativamente. Adaptar
  isso é o núcleo técnico desta frente.
- Locais e NPCs já têm coordenadas em grade (`coordenadas: [x, y]`) que podem virar
  marcadores/overlays do Leaflet.

Rascunho de design, opções técnicas e perguntas em aberto em
**[`MAPA_INTERATIVO.md`](MAPA_INTERATIVO.md)**.

### Status: 🔴 Não iniciado

---

## Log de Sessões

> Ordem cronológica, mais recente no topo. Uma linha (ou poucas) por sessão: o que mudou de fato.

- **2026-09-09 (parte 7)** — **Frente 5 concluída (fase 1): Modo Mestre de IA.** Decisões tomadas
  com o autor: ações de mundo da IA sempre exigem confirmação (nunca aplicam sozinhas), e esta fase
  já entra com aba de chat no dashboard, não só backend. Reaproveitado o protótipo existente
  (`builder/storyteller.py`) extraindo sua lógica pra `engine/mechanics/mestre.py` (`MestreManager`),
  compartilhada agora pelo script antigo e pelo novo modo interativo — corrigida de passagem a
  inconsistência de tema ("Cyberpunk" → "Fantasia Medieval"). Novo `AIGameMasterClient` para diálogo
  contínuo com fallback determinístico. Resolvido o desafio de dois processos (dashboard Flask não é
  dono da `SimulationEngine`, que vive no `run_simulation.py`): "avançar tempo" sinaliza via
  `mundo_meta` como pausa/velocidade já faziam, em vez de instanciar uma engine paralela. Endpoints
  novos (`/api/mestre/mensagem`, `/confirmar_acoes`, `/avancar_tempo`, `/historico`, `/estado`) e aba
  "🎭 Mestre" funcional. **Tudo testado de ponta a ponta com Ollama real** contra uma cópia de
  scratch do banco (nunca o banco de produção): narração coerente, ações de mundo aplicando
  corretamente, confirmação idempotente, fallback funcionando com Ollama forçadamente offline, e o
  fluxo completo de avanço de tempo com um consumidor simulado em thread separada. Eventos
  espontâneos da IA e polimento visual ficam para depois.
- **2026-09-09 (parte 6)** — **Frente 4 concluída: tempo 1:1 real (não a Abordagem 3 originalmente
  planejada).** Autor rejeitou a ideia de esconder um portão de 15 minutos por baixo de um tick fino
  de 1 minuto ("fingir" 1:1) e pediu o rebalanceamento total de verdade. Tick virou 1 minuto;
  `config.json` recalculado em 3 categorias (taxas ÷15, 3 probabilidades por tick via fórmula
  composta, 2 contadores de duração ×15) — nenhuma migração ingênua. Dinheiro do NPC virou `float`
  (salário agora é pago em frações a cada minuto); pego e corrigido um bug de truncamento
  (`int()`/`max(1,...)`) em `_executar_comer` que teria inflado o custo de refeição 3x. Gatilhos de
  mercado/infraestrutura em `run_simulation.py` (antes contagem de ticks brutos) viraram checagem de
  hora do relógio, no mesmo estilo já usado no resto do motor — não sobra nenhuma contagem de tick
  bruto no projeto. Botões de velocidade do dashboard recalibrados (1x tempo real como padrão, até
  21600x). **Verificado quantitativamente** (não só rodou sem erro): salário/hora, taxa de fome/hora
  e duração de gravidez batem exatamente com o comportamento antigo; gatilhos de mercado/infra
  disparam na cadência certa; matemática de velocidade confere. Custo de performance da nova
  granularidade (15x mais ticks/hora) medido e documentado, não otimizado agora.
- **2026-09-09 (parte 5)** — **Frente 3 iniciada: sistema de humor corrigido.** Autor optou por
  seguir direto com o achado já confirmado (humor travando em "Alegre") em vez de levantar novos
  exemplos agora. Criado `engine/mechanics/mood.py` (`NPCMoodManager`): humor virou um retrato
  contínuo do bem-estar (energia/fome/social, pesos configuráveis) com transição gradual — resolve
  a catraca de mão única e reativa os estados antes mortos do enum (`Contente`, `Triste`,
  `Angustiado`). Removida a lógica ad-hoc de humor em `actions.py::_executar_socializar`. Pânico/Medo
  ficam reservados pra serem forçados externamente (futura Frente 5). Testado com 200 ticks reais
  (humor deixou de convergir a 100% Alegre) e com condições forçadas boas/ruins num NPC isolado
  (degradação e recuperação passo a passo confirmadas, incluindo saída de Pânico). Demais candidatos
  de comportamento (movimento teleporte, redundância de `num_dependentes`) ficam para quando o autor
  notar algo observando o jogo.
- **2026-09-09 (parte 4)** — **Frente 2 iniciada e itens 1-3 concluídos.** Investigação isolada
  (arquivos de scratch, sem tocar no mundo salvo) confirmou a causa raiz do "papel amassado":
  upscale bilinear de um recorte de baixa resolução (scipy nunca esteve em `requirements.txt`,
  todo mundo rodava o fallback manual sem saber), amplificado pelas máscaras não-lineares e pelo
  hillshading. Corrigido: `scipy` virou dependência real, upscale trocado para spline cúbico
  (`order=3`) + suavização gaussiana pós-upscale, fallback sem scipy agora avisa no log. Raio do
  continente reconectado à área real via `escala_pixel_area_km2` (antes um clamp fixo comprimia
  toda a variação). `render_ocean` redesenhada com faixa de brilho estreita. Achado extra corrigido:
  `zoom_cidade_crop_raio_px` era 2px (praticamente sem relevo real), subiu para 15px. Tudo
  verificado visualmente com prints gerados em scratch — grade sumiu, halo ficou fino, continentes
  de um mesmo mundo agora variam visivelmente de tamanho. Paleta de biomas/variedade de matiz e
  tamanho do mundo (itens 4-5) ficam para depois do autor revisar visualmente o que já mudou.
- **2026-09-09 (parte 3)** — **Frente 1 concluída.** Terminados os blocos que faltavam
  (tectônica, clima, cor/shading, zoom) e todo o lado engine (Utility AI, ações, geração
  urbana/demografia). Achados corrigidos nesta parte: tamanho do mundo duplicado (768 fixo em 2
  lugares → `mundo_tiles_por_lado` único), `hash()` não determinístico no zoom de continente/cidade
  (→ `zlib.crc32`, verificado com regeneração dupla dando resultado idêntico), 2 bugs de config
  ignorado em `engine/mechanics/actions.py` (`_executar_cuidar_prole` e `_executar_socializar` já
  tinham as chaves certas no `config.json` mas liam números hardcoded diferentes), e SQL de
  bootstrap do mercado (`market.py`) com capacidade/salário cravados na query. Testes: pipeline de
  cartografia completo (mundo → zoom de continente → render PNG) validado de ponta a ponta em
  arquivos de scratch (sem tocar nos dados reais), com preview visual comparado ao README e sem
  regressão perceptível; engine rodou 100+ ticks reais consecutivos sem exceção, cobrindo
  dormir/trabalhar/ocioso/pensão. `docs/AUDITORIA_HARDCODE.md` reescrito como registro final (tudo
  migrado ou explicitamente marcado como decisão de não migrar). Próxima frente sugerida: Frente 2.
- **2026-09-09 (parte 2)** — Início da execução da Frente 1, com `/plan` aprovado antes de codar
  (plano salvo em `~/.claude/plans/lazy-inventing-bubble.md`). Criado o pacote `config/` (fonte +
  resolver, arquitetura de wrapper para trocar a origem da configuração no futuro sem mexer em
  call-sites). Migrados para ele: `engine/config_loader.py`, `cartographer/config.py`,
  `web/dashboard.py`, `builder/populate.py`. `config.json` ganhou a seção `"cartografia"`. Bloco de
  **ruído** da cartografia totalmente migrado (`noise.py`), com 2 inconsistências da auditoria já
  corrigidas (`nivel_montanha` divergente; `persistencia`/`lacunariedade` mortos).
- **2026-09-09** — Sessão de kickoff. Revisão completa do projeto (engine, cartografia, builder, web,
  banco). Autor declarou as 5 vontades de evolução (parametrização única, qualidade da cartografia,
  comportamento dos NPCs, tempo 1:1 + Modo Mestre de IA, mapa Leaflet). Criado este roadmap e os
  documentos de apoio (`AUDITORIA_HARDCODE.md`, `MODO_MESTRE_IA.md`, `MAPA_INTERATIVO.md`), com
  achados concretos já levantados para as Frentes 1, 2 e 3, e descoberta de que `builder/storyteller.py`
  já é uma base funcional para a Frente 5. Nenhuma alteração de código feita ainda — esta sessão foi
  100% de investigação e documentação.
