# 🗺️ Roadmap de Evolução do OpenWorld

> **Para quem retomar este projeto (humano ou IA): leia este arquivo primeiro.**
> Ele é o índice vivo de decisões, status e próximos passos de cada frente de trabalho.
> Os documentos irmãos em `docs/` guardam o detalhe técnico de cada frente — a visão de
> conjunto e o "em que pé estamos" vivem aqui. Não é preciso reler o código do zero a cada
> sessão: comece por aqui, e só desça ao código quando for efetivamente mexer em algo.
>
> 👉 **Vai executar as próximas melhorias?** O plano de trabalho a partir daqui está em
> [`06_PLANO_EVOLUCAO_V2.md`](06_PLANO_EVOLUCAO_V2.md) — mapa do código, contratos de dados, o **modelo de
> escalas** (mundo → continente → região → cidade), o diagnóstico medido em ordem de prioridade
> (P0 quebrado · P1 incoerente · P2 ausente) e 12 fases em 3 blocos com *gates* de verificação:
> **Bloco I = corrigir** (Fases 0–2), **Bloco II = tornar usável na mesa** (3–5),
> **Bloco III = enriquecer** (6–11). Regra: nada de bioma novo, rio ou erosão antes do GATE 1.
> Este ROADMAP continua sendo o histórico do que já foi feito (Frentes 1–6); o PLANO_EVOLUCAO_V2 é
> o que ainda vai ser feito.

**Criado em:** 2026-09-09 — sessão de kickoff (revisão completa do projeto + declaração de vontades do autor).

## Como manter este documento vivo

- Cada **Frente** é uma área de trabalho. Estão ordenadas pela dependência sugerida entre elas.
- Cada Frente tem: **Objetivo**, **Situação Atual** (achados concretos, não suposições), **Decisões tomadas**, **Plano de fases** e **Status**.
- Toda vez que uma sessão de trabalho avançar (decidir algo, migrar algo, corrigir algo), atualize o status da Frente correspondente e some uma linha no **Log de Sessões** no final deste arquivo.
- Status possíveis: `🔴 Não iniciado` · `🟡 Em andamento` · `🟢 Concluído` · `⏸️ Bloqueado / aguardando decisão`

## Visão de conjunto

| # | Frente | Status | Detalhe em |
|---|--------|--------|------------|
| 1 | Parametrização única (engine + cartografia) | 🟢 Concluído | Seção 1 + [`02_AUDITORIA_HARDCODE.md`](02_AUDITORIA_HARDCODE.md) |
| 2 | Qualidade e variedade visual da cartografia | 🟡 Em andamento | Seção 2 |
| 3 | Comportamento dos NPCs (Utility AI) | 🟡 Em andamento | Seção 3 |
| 4 | Motor de tempo 1:1 real (Rebalanceamento Total) | 🟢 Concluído | Seção 4 (decisão revista: Abordagem 2, não 3 — ver [`01_ANALISE_REALTIME_1_1.md`](01_ANALISE_REALTIME_1_1.md)) |
| 5 | Modo Mestre de IA (2º modo temporal) | 🟢 Concluído (fase 1) | Seção 5 (design original em [`03_MODO_MESTRE_IA.md`](03_MODO_MESTRE_IA.md)) |
| 6 | Mapa interativo estilo Leaflet ("Google Maps da aventura") | 🟡 Pirâmide de tiles real implementada, falta rodar no mundo do autor | Seção 6 (design original em [`04_MAPA_INTERATIVO.md`](04_MAPA_INTERATIVO.md)) |

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
**[`02_AUDITORIA_HARDCODE.md`](02_AUDITORIA_HARDCODE.md)** — use-o como checklist de migração.

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
- [x] Catálogo completo (com todos os itens marcados) em `02_AUDITORIA_HARDCODE.md`.

### Plano de fases
1. ~~Consolidar `02_AUDITORIA_HARDCODE.md`~~ ✅
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

### Status: 🟢 Concluído (2026-09-09) — engine e cartografia inteiras lendo de um único `config.json` através do pacote `config/`. Ver `02_AUDITORIA_HARDCODE.md` para o registro completo do que foi migrado/corrigido.

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
  `config.json["ia_decisao"]` e `02_AUDITORIA_HARDCODE.md`).

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
Implementar a Abordagem 3 já desenhada em `docs/01_ANALISE_REALTIME_1_1.md` ("Engrenagens Híbridas"),
permitindo sair da velocidade fixa de 1 tick = 15 minutos simulados para **1 tick = 1 minuto**
simulado, com o tempo real também podendo variar de 1x até Nx (sem o piso atual de 15 minutos por
tick).

### Decisão revista nesta sessão (2026-09-09): Abordagem 2, não Abordagem 3

`docs/01_ANALISE_REALTIME_1_1.md` recomendava a Abordagem 3 ("Engrenagens Híbridas": tick fino de 1 min
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

### Versão 1 (superada) — `L.imageOverlay`
Primeira tentativa: uma imagem única por nível (Mundo/Continente), trocada manualmente ao clicar
na lista lateral. O autor testou e apontou o problema de raiz: **isso não é zoom real** — é só
esticar/encolher uma imagem de resolução fixa ("zoom infinito na mesma imagem"), e trocar de nível
só no clique criava uma "colagem malfeita" nas bordas. Decisão do autor: refazer com pirâmide de
tiles de verdade, **mesmo que custasse a estrutura montada** — ver Versão 2 abaixo.

### Versão 2 (atual) — Pirâmide de tiles real, pré-gerada no reset
**Decisões tomadas com o autor**: gerar detalhe profundo só onde importa (continentes/cidades;
oceano vazio fica raso) — evita explosão de tempo/disco a cada nível de zoom. Cidades ganharam área
real de mundo (raio 15px → 45px) em vez de serem praticamente um ponto.

- **Arquitetura**: zoom 0 = mapa mundi nativo (768×768 = 3×3 tiles de 256px, dado real, sem síntese).
  Zoom 1-4 = pirâmide onde cada tile de 256×256 é recortado da fonte mais específica que cobre
  aquele ponto do mundo (**cidade > continente > mundo**), reaproveitando os `.npz` que o pipeline
  já gera (`ROIZoomGenerator`/`CityROIZoomGenerator`, sem duplicar a síntese de ruído/clima). Tiles
  de oceano profundo longe de qualquer terra reaproveitam um único "tile genérico" pré-computado,
  em vez de recortar/redimensionar centenas de tiles idênticos.
- `tile_zoom_maximo=4` não é arbitrário: é onde a densidade de pixel da pirâmide (2^zoom) se
  aproxima da densidade de detalhe real disponível nos recortes de continente (~3000px/~170px≈17x)
  e cidade (~2000px/~130px≈15x) — acima disso seria só esticar sem detalhe novo.
- **Novo**: `cartographer/tiles/pyramid.py` (núcleo: carregar fontes, decidir prioridade, recortar
  tile) + `cartographer/tiles/generate_tile_pyramid.py` (script CLI, chamado como último passo de
  `reset_cartography.sh`, depois que mundo/continentes/cidades já existem).
- `web/helpers.py`: extraído `render_npz_array()` de `render_npz_map_to_bytes()` (o núcleo do
  pipeline de cor/hillshading agora retorna o array RGB puro, reaproveitado pela pirâmide sem
  round-trip de codificar/decodificar PNG).
- `web/composed_routes.py`: nova rota `GET /tiles/<z>/<x>/<y>.png` (arquivo estático, sem
  processamento — os tiles já vêm prontos do reset); `/api/continentes` passou a expor também
  `tile_zoom_maximo`.
- `web/static/js/mapa_leaflet.js`: **reescrito** — troca `L.imageOverlay` por `L.tileLayer`
  genuíno. O Leaflet cuida nativamente do carregamento parcial (só os tiles visíveis são baixados) e
  do zoom contínuo — nenhuma lógica de auto-troca de camada foi necessária, ela deixou de fazer
  sentido com tiles de verdade. Lista de continentes virou um atalho de `flyToBounds`, não mais uma
  troca de camada.
- `config.json["cartografia"]`: `zoom_cidade_crop_raio_px` 15→45, novo `zoom_cidade_resolucao_px`
  (800→2000, pra manter a cidade com densidade de detalhe comparável à de um continente), novos
  `tile_size_px`/`tile_zoom_maximo`.

### Verificado (mundo de teste completo gerado do zero, não o mundo real do autor)
- Pipeline completo rodado ponta a ponta (mundo → cidades → zoom de continentes → zoom de cidades →
  pirâmide de tiles): **3.5s** para gerar 3069 tiles (246 renderizados de verdade + 2823
  reaproveitados do tile genérico de oceano — confirma que a "profundidade seletiva" está
  funcionando: só ~8% dos tiles precisaram de processamento real). ~21MB em disco.
- **Confirmado visualmente**: montando os 5 tiles do mesmo ponto do mundo em cada zoom lado a lado,
  aparece detalhe progressivo real a cada nível — não é mais a mesma imagem esticada.
- Tiles adjacentes do mesmo nível se encaixam sem costura dentro da mesma fonte (testado remontando
  os 9 tiles do zoom 0 — bate pixel a pixel com o mapa composto original).
- Rota Flask `/tiles/<z>/<x>/<y>.png` testada servindo os arquivos corretamente (200) e devolvendo
  404 pra tile inexistente.
- **Limitação encontrada e não corrigida** (a mesma que o plano já previa, mas mais visível do que
  esperado): no continente de teste (pequeno), o raio da cidade (45px) quase cobre o continente
  inteiro, e a costura entre a fonte "cidade" e "continente" aparece bem no meio da terra, não só
  numa borda discreta. Em continentes maiores (mais prováveis no mundo real) a cidade ocupa uma
  fração bem menor da área, então a costura tende a ficar mais discreta/periférica — mas fica
  registrado como algo a observar no mundo real do autor, não confirmado como "resolvido".
- **Não testado num navegador de verdade** nem contra o mundo real do autor (a pirâmide precisa ser
  gerada via `reset_cartography.sh` — o autor precisa rodar isso pra ter tiles reais disponíveis
  antes de abrir a aba).

### Bug pós-reset real: mapa em branco, sem erro no console, tiles com 200
Depois de rodar `reset_world.sh` de verdade, o autor reportou a aba "🗾 Mapa Live" completamente em
branco — sem erro no console, com respostas 200 nas requisições. Diagnóstico (confirmado por
inspeção do servidor real do autor: manifesto, tiles em disco e rota `/tiles/...` todos corretos —
**o backend estava 100% funcional**, o bug era só no frontend):

- **Causa raiz**: `initMapaLeaflet()` criava o mapa com `minZoom: -2`, mas a `L.tileLayer` foi criada
  com `minZoom: 0` (não existe tile pré-gerado abaixo do zoom 0 — o zoom 0 já é o mundo inteiro em
  3×3 tiles). `fitBounds()` calcula o zoom que faz o mundo (768×768 "px") caber no container real do
  navegador e clampa esse valor aos limites do **mapa** (-2 a 4), não aos da camada de tiles. Como
  `#mapa-leaflet-container` (altura `75vh` menos a barra lateral) pode facilmente ser um pouco menor
  que 768px numa tela comum, o zoom calculado cai abaixo de 0 (ex.: -0.25 a -1). Quando o zoom
  arredondado do mapa fica abaixo do `minZoom` da tile layer, o Leaflet internamente marca a camada
  como fora de alcance e **nunca chama `_update()`** — zero requisições de tile, zero erro, mapa
  permanentemente em branco. Isso bate exatamente com o sintoma relatado (as respostas 200 vistas
  pelo autor eram só de `/api/continentes`; nenhuma requisição de tile chegava a sair).
- **Correção**: `web/static/js/mapa_leaflet.js` — `minZoom` do mapa alinhado com o da tile layer
  (ambos `0`, já que não há dado real abaixo disso); adicionado `invalidateSize()` defensivo logo
  após a criação do mapa, cobrindo qualquer timing residual de reflow na primeira troca de aba.
- **Verificado**: tiles do mundo real do autor testados manualmente via `curl` contra o servidor
  Flask já em execução — `/api/continentes` retorna manifesto correto (`dimensao_global`,
  `tile_zoom_maximo`), `/tiles/0/0/0.png` e outros tiles retornam 200 com PNG 256×256 válido
  (confirmado visualmente: oceano genérico renderizado corretamente). Sintaxe do JS validada
  (`node --check`).
- **Segundo bug, revelado pelo primeiro fix**: com o `minZoom` corrigido, o Leaflet passou a pedir
  tiles de verdade — mas com **`y` negativo** (`/tiles/0/1/-2.png` etc, 404). Causa: a transformação
  padrão do `L.CRS.Simple` é `pixelY = -lat * escala` (sem nenhum deslocamento). `pixelParaLatLng`
  convertia pixel-Y de mundo pra `lat = dimensaoGlobal - py` (uma tentativa de "inverter e deslocar"
  a origem), o que resulta em `lat` sempre não-negativo e, por consequência, em `pixelY` interno do
  Leaflet **sempre não-positivo** (`-lat*escala`) — fora do endereçamento `0..N` dos tiles. A
  correção certa (convenção padrão do Leaflet pra mapas não-geográficos, tipo plantas baixas/mapas de
  jogo) é `lat = -py` (sem o deslocamento por `dimensaoGlobal`): aí `pixelY = -(-py)*escala =
  py*escala`, sempre não-negativo e alinhado com a linha 0 = topo dos tiles pré-gerados. Corrigido em
  `pixelParaLatLng`/`latLngParaPixel`; `bboxParaBounds` e o resto do arquivo não precisaram mudar
  (dependem só dessas duas funções).
- **Terceiro bug (visual, achado pelos prints do autor em `erros/`)**: com o mapa já visível, o autor
  reportou "zoom só vai até continente, não vai até cidades" e anexou capturas mostrando um padrão de
  **xadrez/mosaico** cobrindo continentes e cidades no zoom profundo — cores de bioma alternando em
  blocos, sem relação com o terreno real. Isolado comparando o render bruto do continente (liso, sem
  defeito) contra o render bruto de uma cidade (`database/cidades/mapa_*.npz`, com o defeito) — o bug
  está só na pipeline de cidade (`cartographer/cities/city_roi_zoom.py`), não na de continente.
  - **Causa raiz**: `city_roi_zoom.py` **não recalcula biomas** após o upscale (comentário no código
    já dizia a intenção: herdar o bioma via nearest-neighbor) — mas `_upscale()` de fato aplicava a
    mesma interpolação **spline bicúbica (`zoom_upscale_ordem=3`)** a **todos os 4 canais**, inclusive
    o canal de bioma (índice 3), que é um **ID categórico discreto** (1=oceano, 4=floresta, ...), não
    um valor contínuo. Interpolar categorias com spline produz overshoot clássico: entre um pixel
    oceano(1) e floresta(4) a curva passa por valores fracionários fora da faixa (confirmado
    empiricamente: canal de bioma da cidade tinha 136 mil valores fracionários, de 0.35 a 4.75, com
    IDs fantasmas 0/2/3/5 que não existem na fonte — o continente é 100% "Floresta Temperada"). Ao
    arredondar pra colorir, isso vira o mosaico em xadrez. `roi_zoom.py` (continente) não sofre disso
    porque **recalcula** o bioma do zero após o upscale, descartando esse canal corrompido — só a
    cidade herdava o canal interpolado diretamente.
  - **Correção**: `_upscale()` agora separa o canal de bioma dos demais — altitude/temperatura/
    umidade continuam na ordem configurada (bicúbica), mas o canal de bioma vai por
    **nearest-neighbor** (`order=0`, tanto no branch scipy quanto no fallback manual), preservando os
    IDs originais sem misturar categorias. Isso é exatamente o que o comentário original já dizia
    pretender fazer — só nunca tinha sido implementado de fato.
  - **Verificado**: regenerado `mapa_cidade_das_índias.npz` numa cópia scratch (não nos arquivos reais
    do autor) usando o `venv/` com scipy (mesmo caminho de código da produção). Antes: canal de bioma
    com valores fracionários e IDs 0/2/3/5 fantasmas. Depois: só IDs 1 (oceano) e 4 (floresta) —
    exatamente os dois biomas reais da região. Render visual confirmado: xadrez sumiu completamente,
    ficou uma silhueta de ilha única e coerente (com borda "serrilhada" em blocos — esperado, é o
    limite honesto do nearest-neighbor ampliando um recorte pequeno ~90px pra 2000px, bem menos grave
    que o xadrez).
  - **Ainda não confirmado**: se isso também resolve a percepção de "zoom não vai até cidades" — a
    hipótese é que o xadrez tornava o zoom profundo visualmente ilegível/quebrado, mas o
    `tile_zoom_maximo` (4) já é um teto intencional (Frente 6) baseado na densidade de detalhe
    disponível, não um bug por si só. Precisa reset real + confirmação visual do autor.
  - **Ação pendente do autor**: os arquivos `database/cidades/*.npz` reais ainda têm o canal de bioma
    corrompido (gerados antes do fix) — é necessário rodar `reset_cartography.sh` (ou o
    `reset_world.sh` completo) de novo para regenerar cidades e a pirâmide de tiles com a correção.
- **Não verificado ainda**: comportamento real no navegador do autor após todas as correções acima —
  a extensão de browser não estava conectada nesta sessão para testar ao vivo. Precisa confirmação do
  autor.

### Fora de escopo desta fase
- Corrigir a costura na fronteira entre fontes (aceito conscientemente, ver limitação acima).
- Conteúdo próprio de cidade (ruas, distritos, prédios) — esta fase só garante área/resolução
  suficiente pra isso existir depois.
- Substituir o canvas existente, NPCs em tempo real sobre o Leaflet.

### Status: 🟡 Implementado; três bugs pós-reset diagnosticados e corrigidos (mapa em branco, tiles
com y negativo, xadrez de bioma nas cidades) — **falta o autor rodar `reset_cartography.sh` de novo
(pra regenerar cidades/tiles com a correção) e confirmar visualmente no navegador**.

---

## Frente 7 — Tecido urbano (lotes, edificações e variedade entre cidades)

### Objetivo (nas palavras do autor)
> "Podemos 'engrossar' as ruas para não parecerem linhas imaginárias? E aumentar também ou
> desenhar as coisas preenchendo as quadras? por que atualmente é um ponto numa quadra
> grande." / "eu queria ter cidades variadas pequenas e grandes com numeros de lotes e
> areas variadas, mesmo que isso custe muito podemos prever uma pré-geração."

A parte das ruas (largura real por classe de via) já tinha sido feita na Frente 6/parte 18.
Esta frente é o resto, especificado em
[`08_ESPEC_TECIDO_URBANO.md`](08_ESPEC_TECIDO_URBANO.md) (parte 19) e implementado na parte 20.

### Implementado (2026-09-11, parte 20)
- **E1 — Faixa de domínio da via**: a quadra encolhe pra dentro, afastando-se da linha de
  centro de cada rua que a limita (`largura/2 + recuo`), via inset geométrico de
  quadrilátero convexo (`_encolher_quad`, sem `shapely`). Quadra que degenera vira espaço
  descartado, não polígono invertido.
- **E2 — Lote realista e variado**: alvo de área por banda (centro denso, borda folgada) e
  por cidade (fator sorteado da seed), substituindo o lote fixo de 2,4 ha por lotes de
  ~200-400 m² — o "ponto numa quadra grande" que o autor reportou.
- **E3 — Edificação poligonal**: `edificio` vira `Polygon` (footprint recuado da divisa do
  lote, com taxa de ocupação + jitter), não mais um `Point` de raio fixo em px de tela.
- **E4 — Importador do banco**: `builder/populate.py` aceita `Polygon` (centroide do anel
  externo), mantendo compatibilidade com `Point` (GeoJSON antigo, paliativo).
- **E5 — Índice por cidade + bbox cacheada**: `database/cidades/_indice.json` permite à API
  descartar cidade inteira sem abrir arquivo; bbox de cada feição calculada uma vez no
  carregamento, não por requisição.
- **E6 — Variedade entre cidades**: raio, nº de anéis e nº de setores sorteados por faixa
  (determinístico por nome), soltando a amarra `num_setores = max(6, num_portoes*2)` que
  forçava portões sempre com espaçamento perfeito.

### Verificado (2026-09-11)
Números completos, com o comando de cada medição, estão na Seção 11 de
`08_ESPEC_TECIDO_URBANO.md`. Resumo:
- Redução de área de quadra pela faixa de domínio (E1), isolada do efeito da E6: **15,7%**
  (dentro do alvo 10-25%).
- Lote mediano 243-380 m², 55-68 lotes por quadra (E2) — dentro do alvo (200-600 m² /
  20-120). Aurora Vales saiu com 2.017 lotes, 0,85% acima do teto de 2.000 do alvo — não
  recalibrado, decisão para o autor validar visualmente primeiro.
- `edificio` é `Polygon` em todas as 15 cidades (E3); perfil de categoria sadio — notáveis
  batendo exatamente o teto do catálogo (29/43/48 por tamanho), residência 98,3% (E4).
- `/api/mapa/features` em 24-27 ms no zoom 13 sobre Aurora Vales (E5, era 33 ms com a
  geometria 60x menor); z0 (mundo inteiro) não abre nenhuma cidade (1,2 ms).
- 15 cidades com raio/lotes/edifícios diferentes entre si, nenhuma repetida dentro do
  mesmo tamanho (E6).
- `pytest tests/ -q`: 10/10. `database/cidades/`: 1,2 MB -> 52 MB. Geração das 15 cidades:
  0,76s -> 4,37s (autor autorizou até 1h).
- **Bug achado e corrigido durante a implementação**: `_encolher_quad` reaproveitava o piso
  de área mínima da E1 (`cidade_geo_quadra_area_minima_m2`, 400 m²) como critério de
  degeneração também no recuo do footprint do edifício (E3) — como o lote mediano já é
  menor que isso, quase todo footprint saía `None` (969 de 1.018 edifícios sumiam em
  Quendorvale). Corrigido separando as responsabilidades: o inset geométrico só detecta
  degeneração de verdade (aresta zero, polígono invertido); o piso de área específico fica
  por conta de cada chamador.

### Não verificado / pendências para o autor
- **Validação visual no dashboard** (zoom 13/14, ruas como vazio, quadra ocupada) — a
  extensão do Chrome não conectou nesta sessão. Todo o resto foi verificado por medição.
- Overshoot de lotes em Aurora Vales (item acima) e a colisão de slug pré-existente entre
  duas cidades chamadas "Cidade do(s) Vento(s)" (ver E4 na Seção 11 do documento — mais
  visível agora que cada cidade pesa dezenas de milhares de locais).

### Fora de escopo desta frente
- Interior de edifício, andares, portas — a construção é só um footprint.
- Estradas entre cidades, rios, muralhas irregulares, emendas visíveis entre tiles.
- **Indexar `engine.locais` por cidade** — ver Frente 8, nova, aberta nesta sessão.

### Status: 🟡 Implementado e verificado por medição; falta o autor rodar o dashboard e
confirmar visualmente. Nada commitado.

---

## Frente 8 — Indexar `engine.locais` por cidade (limite de escala do motor)

### Achado (2026-09-11, durante a Frente 7)
Vários caminhos quentes da engine varrem `engine.locais` **inteiro**, uma vez por NPC por
tick, sem filtrar pela cidade do NPC: `movement.py:97` (`mover_para_restaurante`),
`movement.py:118`, `logic.py:86`, `movement.py:68`. Isto é **anterior** à Frente 7 e não foi
causado por ela — só ficou visível porque a Frente 7 leva o mundo a dezenas de milhares de
`Local`, o que torna o produto NPCs × locais grande o bastante pra importar.

Medido (`database/`, Python puro):

| locais no mundo | NPCs | por tick | veredito |
|---|---|---|---|
| 540 | 20 | 1 ms | ok (situação de hoje) |
| 21.000 | 20 | 8 ms | ok |
| 21.000 | 200 | 86 ms | ok |
| 21.000 | 2.000 | 935 ms | **inviável** — o tick é de 1 s |
| 21.000 | 2.000, varrendo só a cidade do NPC | 62 ms | ok |

Com os 20 NPCs de hoje (única cidade simulada — `cidade_spawn`) nada disto importa. O
objetivo declarado do projeto é um mundo cheio (ver citação do autor na Frente 7), e é o
**produto** NPCs × locais que estoura, não nenhum dos dois isolado.

### Conserto proposto (não implementado)
Indexar `engine.locais` por `cidade_id` (dict `cidade_id -> [Local]`, mantido junto com o
dict por id já existente) e trocar as varreduras dos 4 caminhos acima por lookup nesse
índice, filtrando pela cidade do NPC antes de iterar. Devolve ~15x (935 ms -> 62 ms no
cenário de 2.000 NPCs).

### Fora de escopo até aqui
Isto é **motor**, não cartografia — fora do escopo da Frente 7 e da
`08_ESPEC_TECIDO_URBANO.md` por decisão explícita (Seção 3.5.1/10 do documento). Registrado
aqui pra não virar descoberta de última hora quando o mundo for povoado de verdade
(múltiplas cidades simuladas, mais NPCs).

### Status: 🔴 Não iniciado — vira urgente quando (a) mais de uma cidade passar a ter
NPCs simulados, ou (b) o número de NPCs por cidade crescer na casa das centenas/milhares.

---

## Frente 9 — Desenho da cidade (núcleo cívico, distribuição de usos, modelos de cidade)

### Objetivo (nas palavras do autor, 2026-09-11, depois de validar a Frente 7)
> "O centro da cidade tem diversas quadras sem nada, podiamos fazer uma praça e ocupar esse
> espaço pra ficar mais real. Outra coisa é que todos os comércios principais ficam
> praticamente todos juntos, as vezes na mesma quadra, podiamos espalhar pela cidade (...).
> Alem disso queria que vc analisasse a possibilidade de termos outros designs de cidade e
> como poderiamos fazer isso."

E, ao revisar a primeira versão da especificação, a decisão de arquitetura:
> "fazer cada modelo de cidade receber as informacoes de posicao e os dados de
> geografia/clima/etc e produzir o desenho final. (...) Isso faz com que uma interface de
> cidade obrigue que todos os modelos tenham um trabalho padronizado, e possibilite no futuro
> criar por exemplo cidades portuarias, por que é só instanciar essa interface, entrar na lista
> randomica e propor como ela vai ser desenhada, seus comércios e etc."

Especificado em [`09_ESPEC_DESENHO_CIDADE.md`](09_ESPEC_DESENHO_CIDADE.md) (parte 21, v1.1). **Nada
implementado ainda** — a parte 21 produziu só o estudo e a especificação.

### Diagnóstico (2026-09-11, medido — comandos na Seção 3 do documento)
- **Vazio central**: a banda 0 não gera quarteirão nenhum e a praça tem raio **fixo** de 25 m
  enquanto o disco interno escala com a cidade. O vazio vale de **1,7 a 3,0 quarteirões
  médios** (20.550 a 124.026 m²); a praça cobre de 1,6% a 8,7% dele.
- **Notáveis amontoados**: bug de **ordem de iteração**, não de sorteio. `self._lotes` é
  preenchido em `for banda: for setor:`, e os `max` do catálogo (somam 48) se esgotam nos
  primeiros ~100 lotes — que são todos do quarteirão `(banda 1, setor 0)`. Medido:
  Jorverhaven põe **os 48 notáveis em 1 de 48 quarteirões**; Aurora Vales, 43 em 2 de 36;
  Quendorvale, 29 em 2 de 15.
- **Monocultura residencial**: consequência do mesmo bug (`entrada is None` -> `Residência`).
  Jorverhaven tem **99,3% de residências** (6.553 de 6.601), contra os 55% que o código
  pretende. Falta a camada de comércio de bairro (padaria, quitanda, poço), que é densidade e
  não contagem.
- **Uma forma só**: as 15 cidades são o mesmo traçado radial; o `tipo` da cidade influencia só
  o catálogo de edifícios, não a geometria.

### Arquitetura decidida: interface de modelo de cidade
Cada modelo (`radial`, `grade`, `linear`, `organica`, ...) recebe um **`SitioCidade`**
explícito — posição, bioma, clima, relevo, distância da água — e produz o desenho **inteiro**:
malha viária, zoneamento, onde vão os notáveis, que comércio existe, muralha. A escolha é
"lista de possibilidades no config → sorteio determinístico pela seed do nome → instancia
passando o sítio". Sete ganchos padronizados; a classe base responde todos, cada modelo
sobrescreve só os que fazem sentido para ele (o `linear` não tem banda nem setor, tem fileira —
e não precisa fingir que tem).

Achado que sustenta isso, medido nesta parte: `gerar_janela` já devolve **4 canais** (altitude,
temperatura, umidade, bioma) e o gerador **descarta três**. Altitude não discrimina (0,353 a
0,372 nas 15 cidades), mas temperatura vai de **0,012 a 0,574**, umidade de **0,243 a 0,597**, e
há **três biomas** distintos entre as cidades. O dado que o autor quer passar ao modelo já
existe, de graça, na chamada que o gerador já faz.

### Dois limites do mundo que o estudo confirmou (medidos, e fecham portas)
- **A cidade é plana na própria escala**: amplitude de altitude de 0,0002 a 0,0011 na janela
  de uma cidade, e a declividade local fica em ~1e-7 contra o limiar de 0,35 do config — seis
  ordens de grandeza. O filtro `cidade_geo_declividade_max` **nunca dispara**. Inviabiliza
  qualquer modelo guiado por relevo (terraços, curvas de nível).
- **Nenhuma cidade toca a água**: `cidades_distancia_costa_minima_px = 2.0` são 31,6 km, e a
  água mais próxima de qualquer cidade está a **35,4 a 130,4 km**. A cidade mais larga tem
  2,3 km. `portuaria` é hoje um rótulo sem geografia.

Sobre a cidade portuária, a distinção que a arquitetura torna limpa: **a interface passa a
permitir; o mundo ainda não fornece o dado.** Depois do F4, `PortuariaModelo` é uma classe nova
e uma linha de config, sem tocar em nada compartilhado. O que falta é `distancia_agua_m` menor
que o raio da cidade — e baixar `cidades_distancia_costa_minima_px` sozinho **não** resolve
(0,5 px ainda são 7,9 km). O caminho que funciona é hidrografia gerada na escala da cidade, pelo
mesmo ruído seedado que já gera o terreno de detalhe. É frente própria, não modelo de cidade.
Por isso `distancia_agua_m` e `direcao_agua_rad` entram no `SitioCidade` desde já, sem uso.

Consequência de projeto: **o modelo é escolhido por `tipo` + `tamanho` + seed, e o sítio
calibra o modelo escolhido, não o escolhe** — e o manifesto não muda (refundá-lo significaria
refundar as cidades).

### Plano (8 etapas, ver Seção 6/7 do documento)
`F1` núcleo cívico (praça escalada + banda 0 urbanizável) · `F2` distribuição dirigida dos
notáveis por zona com teto por quarteirão · `F3` comércio de bairro por densidade · `F4`
interface de modelo de cidade (refatoração pura, `diff` vazio obrigatório em cada um dos 4
passos) · `F5` modelo `grade` · `F6` modelo `linear` · `F7` modelo `organica` (+ `bastida`
opcional) · `F8` registro, sorteio e instanciação.

F1-F3 resolvem os dois defeitos relatados e são entregáveis sem F4+. Modelo por Voronoi foi
**descartado**: quebra o contrato de quadrilátero de `_encolher_quad`/`_subdividir_lote`/
`_footprint_edificio` e exigiria offset de polígono côncavo.

### Status: 🔴 Não iniciado — especificação pronta, aguardando decisão do autor sobre o
escopo (F1-F3 apenas, ou a frente inteira até F8).

---

## Log de Sessões

> Ordem cronológica, mais recente no topo. Uma linha (ou poucas) por sessão: o que mudou de fato.

- **2026-09-11 (parte 21, estudo e especificação do desenho de cidade)** — Depois da validação
  visual da parte 20, o autor apontou dois defeitos (centro vazio, comércio amontoado) e pediu
  um estudo sobre outros desenhos de cidade. Produzida a
  [`09_ESPEC_DESENHO_CIDADE.md`](09_ESPEC_DESENHO_CIDADE.md), auto-suficiente e escrita para um
  agente de menor senioridade executar (Frente 9, nova, ver acima). **Nenhuma linha de código
  mudou nesta sessão** — só medição e documento. Achado principal: a concentração dos notáveis
  é um bug de ordem de iteração (`self._lotes` preenchido banda a banda, setor a setor, e os
  `max` do catálogo esgotando nos primeiros ~100 lotes), que em Jorverhaven põe **os 48
  notáveis no mesmo quarteirão** e deixa a cidade com 99,3% de residências. Também medidos os
  dois limites do mundo que fecham portas para o estudo de desenhos: a cidade é plana na
  própria escala (declividade real ~1e-7 contra limiar 0,35) e está a 35-130 km da água, o que
  descarta desenho em encosta e porto de verdade. Plano em 8 etapas, com F1-F3 entregando os
  dois pedidos do autor independentemente das F4-F8. **Revisado para v1.1 na mesma sessão**:
  o autor pediu que o desenho fosse uma **interface de modelo de cidade** (cada modelo recebe
  posição + geografia/clima e produz o desenho final, incluindo comércio), não um "traçado" que
  só devolve ruas e quadras. Proposta adotada e especificada como F4 (`SitioCidade` +
  `ModeloCidade` com 7 ganchos padronizados). Medição que sustenta a mudança: `gerar_janela` já
  devolve 4 canais e o gerador descarta 3 — temperatura (0,012 a 0,574), umidade (0,243 a
  0,597) e bioma (3 distintos) discriminam entre as cidades, ao contrário da altitude.

- **2026-09-11 (parte 20, implementação do tecido urbano — E1 a E6)** — Executada a
  especificação da parte 19 ([`08_ESPEC_TECIDO_URBANO.md`](08_ESPEC_TECIDO_URBANO.md)), etapa por
  etapa, na ordem E1→E6 (Frente 7, nova, ver acima). Rua ganhou faixa de domínio real
  (quadra encolhe pra dentro via inset de quadrilátero convexo, sem `shapely`); lote passou
  de um valor fixo de 2,4 ha pra alvo por banda + fator por cidade (~200-400 m² reais);
  `edificio` virou `Polygon` (footprint recuado + taxa de ocupação com jitter) em vez de
  `Point` de raio fixo; `builder/populate.py` passou a importar `Polygon` calculando o
  centroide (mantendo compatibilidade com `Point`); API de features ganhou índice por
  cidade + bbox cacheada no carregamento (`/api/mapa/features` de 33ms pra 24-27ms com a
  geometria ~60x maior); raio/anéis/setores de cada cidade passaram a ser sorteados por
  faixa (determinístico por nome), soltando a amarra que forçava portões sempre
  perfeitamente espaçados. **Bug achado e corrigido no processo**: o inset geométrico
  (`_encolher_quad`) reaproveitava por engano o piso de área mínima da quadra (E1) também
  no recuo do footprint do edifício (E3) — quase todo footprint saía inválido porque o
  lote mediano já é menor que esse piso (969 de 1.018 edifícios sumiam numa cidade de
  teste). Corrigido separando as duas responsabilidades. 32.787 `Local` seriam criados no
  próximo `populate.py` (era 539) — perfil sadio, notáveis batendo exatamente o teto do
  catálogo por tamanho (29/43/48), residência 98,3%. `pytest` 10/10.
  `database/cidades/`: 1,2 MB -> 52 MB, geração das 15 cidades 0,76s -> 4,37s (autor
  autorizou até 1h). **Não verificado**: aparência real no navegador — a extensão do
  Chrome não conectou nesta sessão, fica pendente de confirmação visual do autor. Também
  aberta a Frente 8 (nova, backlog): indexar `engine.locais` por cidade, o limite de escala
  real do motor identificado (não corrigido) na parte 19. Nada commitado.

- **2026-09-11 (parte 19, especificação do tecido urbano)** — A pedido do autor, escrita a
  especificação [`08_ESPEC_TECIDO_URBANO.md`](08_ESPEC_TECIDO_URBANO.md) para outro modelo executar:
  quadras preenchidas de construções, faixa de domínio da via, e variedade real entre cidades.
  Nenhum código alterado nesta entrada. Descoberto e documentado um acoplamento que não estava
  escrito em lugar nenhum: `builder/populate.py` importa **cada** feature `edificio` como um
  `Local` do `openworld.db`, um para um (confirmado medindo: 539 features no disco, 539 linhas
  no banco). **A v1.0 do documento tratou isso como perigoso** e propunha uma camada de
  edificação decorativa que não viraria `Local`. O autor questionou a premissa ("nao entendi a
  necessidade de edificacao decorativa"), a medição deu razão a ele — 21.000 locais custam
  2 MB de banco, 25 ms de carga e 9 ms por tick, menos de 1% do orçamento — e a proposta foi
  **retirada na v1.1**: toda construção é um `Local` de verdade, o que também é o que o nome
  OpenWorld pede. O catálogo de edifícios **já** limita os prédios notáveis a 29/43/48 por
  tamanho de cidade e já cai em "Residência" quando esgota, então o perfil realista sai do
  código atual sem nada novo. Duas coisas reais sobraram: (a) `edificio` virando `Polygon`
  quebra o importador, que faz `lng, lat = coordinates`; (b) **o limite de escala verdadeiro**,
  medido agora, é que as varreduras por tick são O(NPCs × locais do **mundo inteiro**), não da
  cidade do NPC — aguenta 200 NPCs (86 ms) e não aguenta 2.000 (935 ms, com tick de 1 s).
  Indexar `engine.locais` por cidade devolve isso a 62 ms. **É frente de motor, anterior a este
  trabalho, e continua em aberto.** Também medido: o gargalo de servir feições é
  `_bbox_geometria` recalculada a cada requisição, inclusive para cidades fora da tela (1,6 µs
  por feição, projetando ~150 ms por pan no cenário mais denso), resolvido por índice por
  cidade e bbox cacheada no carregamento. Nada commitado.

- **2026-09-11 (parte 18, ruas com largura real)** — Pedido do autor depois de ver a cidade
  funcionando: "engrossar as ruas para não parecerem linhas imaginárias". A espessura era
  `weight: 1.5` fixo em px de TELA, então a largura real da via era inversamente proporcional
  ao zoom: 11,6 m no z11 e 0,7 m no z15, encolhendo justo quando você chega perto. Agora a
  largura é em METROS por classe de via (`cidade_via_largura_m_por_classe`, servida por
  `/api/continentes`) e o frontend converte a cada zoom em `estiloRua`, com piso em px pra
  via não sumir no zoom em que a camada acende. O gerador passou a gravar `classe_via`: a
  radial que termina num portão é `principal` (11 m), os anéis são `anel` (7 m), as demais
  radiais são `secundaria` (5 m) — hierarquia viária de verdade, com tom e opacidade
  próprios e junta arredondada pro cruzamento fechar. `cartographer/cities/zoom_levels.py`
  virou `escala.py` e ganhou `metros_por_pixel_mundo`, agora o único lugar onde metro, px de
  mundo e px de tela se convertem (o `math.sqrt(...)` inline sumiu do gerador).
  **Bug achado no caminho**: o espaçamento mínimo entre portões era
  `num_setores // (num_portoes * 2)`, e como `num_setores` nunca passa de `num_portoes * 2`
  isso dava sempre 1 — a guarda não guardava nada. 12 das 14 cidades tinham portões colados
  (Aurora Vales com os três nos setores 3, 4 e 5). Invisível enquanto a rua era um fio, mas
  com a principal a 11 m viraria três avenidas grudadas. Corrigido para o espaçamento ideal,
  com queda pra rotação uniforme mais plana quando o guloso se encurrala. As 14 cidades agora
  saem com vãos perfeitos. Geometria confirmada idêntica fora isso (bbox da muralha de Aurora
  Vales inalterada). **Próximo passo combinado**: lotes menores e variados, com pré-geração
  cara aceita pelo autor. 10/10 testes passam. Nada commitado.

- **2026-09-11 (parte 17, D9 — a cidade construída nunca aparecia)** — O autor reportou, com
  print, que depois do D1/D3 o zoom ia mais fundo e a muralha aparecia, mas os prédios não.
  Não era render nem geração: `carregarFeaturesVisiveisLeaflet` montava a bbox da consulta
  com `latLngParaPixel`, que **arredonda para inteiro** (ela existe pra consulta de clique,
  que indexa um array por pixel). Como a cidade mede 0,076 px de mundo, acima do zoom ~10 a
  viewport inteira cabe num pixel, os dois cantos arredondavam para o mesmo inteiro e a bbox
  virava um **ponto de área zero**. Sobreviviam só as feições cuja caixa englobava aquele
  ponto exato (muralha, praça, ruas); edifício, torre e portão são pontos em coordenada
  quebrada e nunca cruzavam. Pior, os dois filtros não tinham interseção: edifício pedia
  `z >= 14` e uma bbox utilizável exigia `z <= 9`, então **nenhum zoom** mostrava a cidade
  construída. Corrigido com `latLngParaPixelExato` (fracionário) para a bbox, mantendo a
  versão inteira só para o clique; `z` passou a ser `Math.floor`, não `Math.round` (com
  `zoomSnap` 0,25 a camada acendia meio nível cedo). Junto: a tabela
  `cidade_geo_zoom_min_por_camada_tamanho` (escrita à mão) virou
  `cartographer/cities/escala.py`, que **deriva** `{tamanho: {camada: zoom_min}}` da
  fórmula `ceil(log2(alvo_px_de_tela / diametro_px_de_mundo))` — só os alvos ficam no
  config (`cidade_geo_zoom_min_alvo_px_por_camada`), e foram recalibrados de 120/350/700/1400
  para 48/200/400/800, porque os antigos só acendiam o edifício quando a cidade já era maior
  que a tela. Medido depois: cidade média com 622 px na tela e os 32 edifícios no z13,
  contra nada em zoom nenhum antes. `/api/continentes` passou a devolver a mesma tabela, e o
  popup/duplo-clique/rótulo do seletor pararam de repetir números escritos à mão (já
  divergiam do config). 10/10 testes passam. Nada commitado.

- **2026-09-11 (parte 16, correção dos achados do DIAGNOSTICO_V3)** — Implementadas as 5 primeiras
  etapas da ordem de execução do diagnóstico (Seção 11): **D1** (`generate_city_geometry.py`
  corrigido pra `metros_por_px = sqrt(escala_pixel_area_km2)*1000`; `ZOOM_MIN_POR_CAMADA` virou
  config-driven por camada+tamanho, recalibrado; muralha de Pelamont mede 0,1158 px de mundo, na
  faixa esperada ~0,1138±5%); **D3** (`lote` registrado e estilizado no Leaflet, grupo de detalhe
  de cidade ligado por padrão, afordância de zoom + duplo-clique no marcador); **D5** (`maxNativeZoom`
  calibrado direto pro valor final — 11 — combinado com D2, `tile_zoom_maximo_ui` 16→15); **D4**
  (`_pontuar_sitio` reescrita: `score_costa` e `score_altitude` ganharam pico interno em vez de
  monótono, mais restrição dura por distância mínima da costa e perfil por tipo de cidade —
  medição dry-run no continente Grendalia real: percentil de altitude do melhor sítio subiu de
  0,00-0,07% pra 10-58%, água nos vizinhos 3x3 zerou); **D2/Caminho B** (campo de detalhe local
  implementado exatamente como especificado na Seção 13 — `NoiseGenerator.generate_detail_field`
  com limite de banda por Nyquist, injetado em `gerar_janela` entre a mesclagem terra-mar e o
  clima, cidade passou a amostrar o terreno real pra posicionar praça/portões/rejeitar lote
  íngreme e gravar `properties.altitude` em cada edifício). 10/10 testes passam (7 antigos + T7/T8/T9
  novos). Reprodução da tabela de textura da Seção 13.6 no mundo real (não só no protótipo):
  estável de z4 (28,6) a z14 (32,5) em vez de despencar, e z0/z2 idênticos ao comportamento sem
  detalhe. Invariante da costa (0 flips) confirmado no mundo real, não só na fixture de teste.
  **D4 não foi aplicado de verdade** (só a medição dry-run, sem escrita): rodar o aceite oficial
  chamaria a IA pra fundar cidades NOVAS, substituindo as 15 atuais — e `database/openworld.db`
  já tem `npcs`/`locais`/`eventos` referenciando essas cidades por nome, então isso quebraria esse
  vínculo. Devolvido ao usuário como decisão antes de agir — confirmou **não aplicar por agora**,
  o fix fica pronto no código. **Validação visual (print no navegador) pedida pelos critérios de
  aceite de D2/D3/D5 não foi feita** — a extensão Claude in Chrome não estava conectada neste
  ambiente; validação ficou só no nível de API/backend. Depois do checkpoint da Etapa 6, o usuário
  decidiu **D7: as duas vistas (regional + urbana), telas separadas**. Vista regional corrigida:
  `/api/cidade/<nome>/imagem` virou `/api/regiao/<nome>/imagem` (mesmo pra `/entities`),
  `cidade_janela_raio_px` virou `regiao_janela_raio_px`, e o canvas do `mapa_composto.js` parou de
  empilhar 85 marcadores de local no mesmo pixel — agora é um marcador agregado com contagem.
  Vista urbana: em vez do Caminho C literal (mapa Leaflet novo com CRS próprio em metros),
  reaproveitada a aba Mapa Live já corrigida pelo D3 — decisão de escopo sinalizada explicitamente
  no diagnóstico pra revisão do usuário, não é o que a Seção 9.5 pedia ao pé da letra. D6 e D8 não
  iniciados. Nada commitado.

- **2026-09-11 (parte 15, validação humana + diagnóstico)** — O usuário validou o mapa e apontou
  três sintomas (zoom borrado/infinito, "a cidade não existe / é 1px", "cidade na água"). A
  investigação virou [`docs/07_DIAGNOSTICO_V3.md`](07_DIAGNOSTICO_V3.md): **8 achados medidos**, sendo o
  principal um **erro de unidade** — `generate_city_geometry.py` usava `escala_pixel_area_km2`
  (que é **área**, km²/px) como se fosse escala **linear**, desenhando toda a cidade **15,81×
  menor** que o projetado (`sqrt(250)`). Outros achados: as 15 cidades caem no pixel exato da
  linha d'água (a função de pontuação de sítio tem dois termos que maximizam no mesmo ponto); a
  camada "Detalhe da Cidade" nunca é ligada por padrão no Leaflet (e `lote` nem está registrada),
  o que explica "a cidade não existe"; falta `maxNativeZoom` (o raster para de ganhar detalhe no
  z6, medido por gradiente, mas o Leaflet pede tile real até o z16 a 0,19–0,55 s cada); e a "vista
  de cidade" renderiza 380 km de lado, onde os 85 locais colapsam em 0,3 px.
  Em seguida o usuário escolheu o **Caminho B do D2** (campo de detalhe local, o mais custoso
  dos três) e pediu a especificação de implementação. Ela virou a **Seção 13 do
  DIAGNOSTICO_V3**: campo de ruído dedicado somado à altitude de terra, com **limite de banda
  por oitava** (antialiasing por Nyquist) — é isso que permite ter detalhe sub-pixel sem
  serrilhar o mapa-múndi e sem violar a pureza F1. Foi **prototipado e medido** antes de ser
  escrito: T2 passa bit a bit, T6 dá 0 flips, a costa fica idêntica à do mundo atual (nenhum
  reset necessário), 0,00% dos pixels mudam de bioma, o custo sobe 4% no z4 e 10% no z12, e a
  textura da imagem no z14 vai de 11,8 para 39,6 e passa a ser **constante do z4 ao z14** em vez
  de despencar. Duas descobertas baratearam o trabalho: o hillshading já compensa o zoom, e a
  decisão terra/água usa `mask_continente`, não o relevo, então somar detalhe não move a costa.
  **Nenhum código do projeto foi alterado nesta sessão — só documentação.** Nada commitado.

- **2026-09-11 (parte 14, sessão autônoma)** — **Plano V2/V3 executado até o fim do Bloco II core:
  Fases 0, 1, 2, 3 e 4 implementadas, testadas e verificadas** (docs/06_PLANO_EVOLUCAO_V2.md tem o
  detalhe completo de cada uma, incluindo achados de bug reais no caminho). Resumo do que mudou de
  fato no mundo: o tile do Mapa Live deixou de ser mosaico pré-renderizado e virou
  `TileCartographer.gerar_janela()` sob demanda (zoom refina em vez de contradizer, F1-F4
  garantidos por 7 testes em `tests/test_cartografia.py`); tamanho de continente, biomas e
  posicionamento de cidade recalibrados por medição (não chute); `Local.coordenadas` é pixel de
  mundo de verdade em todo o pipeline (populate.py, expansão urbana, Modo Mestre); Leaflet ganhou
  camada vetorial (`/api/mapa/features`) com cidades, e cada cidade agora tem geometria real
  (ruas, muralha, quarteirões, lotes, ~387 edifícios nomeados em 9 cidades testadas) gerada por
  `cartographer/cities/generate_city_geometry.py` e importada como `Local` de verdade — zero
  coordenada sorteada no fluxo normal. `tile_zoom_maximo_ui` 4→16. **Gate 1 revalidado em 3 mundos
  independentes** (10/10 continentes na faixa). **Fase 5 (narrativa de cidade por IA) não iniciada**
  — próximo passo natural. Nada commitado (autor pediu pra validar em casa antes).

- **2026-09-10 (parte 13)** — **Diagnóstico do "cartógrafo confunde continente com cidade" + plano de
  execução V2.** Autor reportou, após o reset: mapa não faz zoom até a cidade, e clicar na cidade
  mostra o continente com locais espalhados na água. Medido e confirmado: (a) `zoom_cidade_crop_raio_px=45`
  é fixo enquanto os continentes têm bbox de 45–127px, então o recorte "de cidade" é 0,9× a **2,7×** a
  área do continente (em Avalonia engole o continente inteiro); (b) `carregar_fontes()` prioriza
  cidade > continente por tipo hardcoded, mas a densidade real da cidade é **menor** que a do
  continente em 2 de 4 casos — aproximar piora o mapa; (c) `populate.py` grava
  `coordenadas = random.randint(5,35)`, um espaço de coordenadas que não é nem mundo nem cidade, e o
  mapa antigo desenha esse par sem validar `nivel_mar` — daí edifícios no oceano; (d) **achado extra
  não reportado**: `roi_zoom.py` renderiza recorte retangular em imagem quadrada 3000×3000,
  deformando os continentes de 1,05× a **1,51×** (Gardania espremido em 51%). Causa raiz comum: o
  projeto nunca declarou um modelo de escalas — "cidade" virou "continente menor", e o raio foi sendo
  aumentado (2 → 15 → 45) até ultrapassar o continente. Nenhuma correção de código nesta sessão:
  o resultado é [`06_PLANO_EVOLUCAO_V2.md`](06_PLANO_EVOLUCAO_V2.md), com as 4 regras invariantes de fonte
  de zoom (contenção, prioridade por densidade, isotropia, ganho mínimo) e 12 fases em 3 blocos,
  ordenadas para consertar tudo antes de adicionar qualquer coisa nova.
- **2026-09-09 (parte 12)** — **Bug: xadrez de biomas nas cidades do Mapa Live.** Autor anexou prints
  em `erros/` mostrando um mosaico em xadrez cobrindo continentes/cidades no zoom profundo, e reportou
  que o zoom não chegava a mostrar detalhe de cidade. Isolado renderizando o `.npz` bruto de um
  continente (liso) vs. de uma cidade (com o defeito) — bug exclusivo de
  `cartographer/cities/city_roi_zoom.py`. Causa: o canal de bioma (categórico, IDs 1-5) era
  interpolado com a mesma spline bicúbica (`ordem=3`) dos canais contínuos, gerando overshoot
  (valores fracionários, IDs fantasmas 0/2/3/5) — confirmado empiricamente antes do fix. `roi_zoom.py`
  (continente) não tem esse bug porque recalcula bioma do zero pós-upscale; a cidade herdava o canal
  corrompido direto. Corrigido: bioma agora vai por nearest-neighbor, canais contínuos continuam
  bicúbicos. Verificado numa cópia scratch com o `venv/` de produção (scipy): xadrez sumiu, só sobrou
  o bioma real (1 e 4). **Autor precisa rodar `reset_cartography.sh` de novo** pra regenerar os
  `.npz` de cidade reais (os atuais foram gerados antes do fix) e confirmar visualmente.
- **2026-09-09 (parte 11)** — **Bug: mapa Leaflet em branco após reset real, sem erro no console.**
  Diagnosticado: `minZoom` do mapa (-2) e da tile layer (0) descasados — `fitBounds` podia calcular
  um zoom abaixo do mínimo da camada de tiles quando o container era um pouco menor que 768px,
  deixando o Leaflet silenciosamente sem pedir nenhum tile. Backend confirmado 100% funcional
  (tiles e `/api/continentes` testados via `curl` contra o servidor real do autor já em execução)
  antes de concluir que o bug era só no frontend. Corrigido: minZoom unificado em 0 +
  `invalidateSize()` defensivo. Esse fix revelou um **segundo bug**: tiles passaram a ser pedidos,
  mas com `y` negativo (404) — a conversão pixel→latLng usava `lat = dimensaoGlobal - py`, incompatível
  com a transformação padrão do `L.CRS.Simple` (`pixelY = -lat*escala`, sem deslocamento); corrigido
  para `lat = -py`. Ver detalhes na Frente 6 acima. **Aguardando confirmação visual do autor**
  (extensão de browser não disponível nesta sessão para testar ao vivo).
- **2026-09-09 (parte 10)** — **Frente 6 refeita do zero: pirâmide de tiles real.** Autor testou a
  v1 (parte 9 abaixo) e rejeitou a base: "zoom infinito" que só ampliava a mesma imagem, e colagem
  malfeita ao trocar de continente, não é "Google Maps real". Pediu pra estudar a arquitetura de
  verdade mesmo que custasse refazer tudo, com a pirâmide pré-gerada no reset (não sob demanda) e
  cidades maiores. Decisões tomadas via pergunta direta: profundidade só onde importa (continentes/
  cidades; oceano raso) e cidade "pequena" (raio 45px, era 15px). Implementado
  `cartographer/tiles/pyramid.py`+`generate_tile_pyramid.py` reaproveitando os `.npz` de continente/
  cidade que o pipeline já gera (sem duplicar síntese de ruído), com atalho de tile oceânico
  genérico pra regiões vazias. `mapa_leaflet.js` reescrito pra `L.tileLayer` de verdade — o Leaflet
  passou a cuidar do carregamento parcial nativamente, eliminando toda a lógica manual de troca de
  camada da v1. Testado com um mundo completo gerado do zero num diretório isolado: pipeline inteiro
  (mundo→cidades→zooms→pirâmide) em 3.5s, 3069 tiles (só 246 renderizados de verdade, resto
  reaproveitado do tile de oceano), detalhe progressivo real confirmado visualmente montando os 5
  níveis de zoom do mesmo ponto lado a lado. **Achado honesto**: a costura entre fonte "cidade" e
  "continente" (limitação já aceita no plano) ficou bem visível no continente pequeno de teste,
  porque a cidade quase cobre o continente inteiro nesse caso — registrado para o autor observar no
  mundo real, não assumido como resolvido. Ainda falta rodar `reset_cartography.sh` de verdade e
  testar num navegador.
- **2026-09-09 (parte 9)** — **Frente 6 corrigida (bug) antes da reformulação.** Autor reportou dois
  problemas testando a v1: (a) overlay de continente malposicionado ("colagem", "corte abrupto") —
  bug real, corrigido (o overlay não considerava a margem `zoom_border_padding_px` que a imagem do
  continente já inclui); (b) zoom no próprio mapa não trocava de camada, e não tinha cidades — isso
  levou à conversa que resultou na parte 10 acima.
- **2026-09-09 (parte 8)** — **Frente 6 implementada: mapa "Google Maps da aventura" via Leaflet.**
  Enquanto o autor rodava um reset completo do mundo pra avaliar as frentes anteriores, montei e já
  implementei o plano em paralelo (autorizado explicitamente pra economizar tempo). Achado que
  simplificou bastante o trabalho: não precisa de tiles em pirâmide — o zoom aqui é discreto
  (Mundo→Continente→Cidade, cada um já uma imagem única), então `L.imageOverlay` do Leaflet resolve
  direto, sem servidor de tiles. Nova aba "🗾 Mapa Live" ao lado do canvas existente (não substitui),
  reaproveitando 100% dos endpoints de imagem/inspeção que já existiam — só uma adição pequena de
  backend (`dimensao_global` no `/api/continentes`, pra não hardcodar 768 no JS). Achado de bônus:
  o recorte quadrado forçado do `ROIZoomGenerator` (Frente 2) se autocorrige visualmente ao ser
  posicionado de volta no bounding_box retangular original. Validado com matemática de conversão de
  coordenadas conferida à mão e testes via cliente Flask contra dados de scratch — **não testado
  visualmente num navegador real** nem contra o mundo do autor (que estava sendo regenerado durante
  a sessão) — fica pro autor abrir a aba e confirmar. Nenhum arquivo de `engine/`/`cartographer/`
  tocado, só `web/`.
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
  dormir/trabalhar/ocioso/pensão. `docs/02_AUDITORIA_HARDCODE.md` reescrito como registro final (tudo
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
  documentos de apoio (`02_AUDITORIA_HARDCODE.md`, `03_MODO_MESTRE_IA.md`, `04_MAPA_INTERATIVO.md`), com
  achados concretos já levantados para as Frentes 1, 2 e 3, e descoberta de que `builder/storyteller.py`
  já é uma base funcional para a Frente 5. Nenhuma alteração de código feita ainda — esta sessão foi
  100% de investigação e documentação.
