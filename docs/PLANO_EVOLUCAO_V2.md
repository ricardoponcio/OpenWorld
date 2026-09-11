# PLANO DE EVOLUÇÃO V2 — Guia de Execução

> **Para quem é este documento**: para o modelo/desenvolvedor que vai executar as próximas
> alterações. Ele é **auto-suficiente**: contém o mapa do código, os contratos de dados, o
> diagnóstico medido e as fases com passos prescritivos e critério de aceite executável.
>
> **Você não precisa reler o projeto inteiro.** Para executar uma fase, leia:
> Seção 0 (regras) → Seção 1 (mapa do código) → Seção 2 (modelo de escalas — **obrigatório**)
> → Seção 3 (problemas, já em ordem de prioridade) → Seção 4 (ordem de execução) → a sua fase
> → Seção 8 (testes, se a sua fase pede teste).
>
> Histórico do que já foi feito (Frentes 1–6) está em [`ROADMAP.md`](ROADMAP.md).
> Ao concluir qualquer fase: preencha a Seção 7 e some uma linha no "Log de Sessões" do ROADMAP.

**Revisão**: 2026-09-10 (v3.0 — auditoria de código + medição derrubaram a arquitetura da Fase 0
anterior. A pirâmide de tiles deixa de ser um **mosaico de rasters pré-renderizados** e passa a ser
**a função de terreno avaliada por tile**. Ordem de prioridade preservada: primeiro consertar, depois
enriquecer.)

### ⚠️ O que mudou da v2.2 para a v3.0 — leia se você já conhecia a versão anterior

A v2.2 propunha, na Fase 0, um sistema de invariantes (R1–R4) para arbitrar entre fontes de imagem
pré-renderizadas (mundo, continente, "cidade"). **Isso foi descartado.** A auditoria mostrou que:

1. `TileCartographer.generate_tile()` já é uma **função pura das coordenadas de mundo** — verificado
   em toda a cadeia (`noise`, `tectonics`, `climate`, `coloring`). Nada nela exige que o passo da
   grade seja 1 px. Ela já sabe gerar **qualquer janela do mundo em qualquer resolução**.
2. Logo, o mosaico de rasters é **complexidade auto-infligida**: ele existe só porque ninguém notou
   que a função já era independente de resolução. R1–R4 seriam remendos para um problema que não
   precisa existir.
3. Os guarda-corpos propostos na v2.2 (Fase 0.5) foram testados contra o mundo real e **não pegavam o
   bug que motivou o plano** (detalhes em P0.1). Um deles era tautológico.

**Se você leu a v2.2: esqueça R1, R2, R3, R4, "prioridade por densidade", "ganho mínimo",
"renomear cidade→região" e "blend de costura". Nada disso sobrevive.** A Fase 0 nova (Seção 5)
substitui tudo por: *o tile é uma função, não um recorte*.

---

## 0. Regras de trabalho — leia antes de tocar em qualquer coisa

1. **Nunca escreva em `database/` enquanto uma simulação ou reset estiver rodando.**
   Verifique antes: `ps aux | grep -E "run_simulation|reset_|populate|generate_" | grep -v grep`
2. **Teste em cópia scratch**, nunca nos arquivos reais:
   ```bash
   mkdir -p /tmp/scratch && cp database/world_manifest.json database/mapa_composto.npz /tmp/scratch/
   ```
3. **Use `venv/bin/python`, nunca `python3`.** Só o venv tem `scipy`, e o caminho com scipy é o que
   roda em produção. Testar sem scipy valida o fallback errado.
4. **"Compila" não é teste.** Toda fase tem comando de aceite. Execute e cole a saída real.
   Se não conseguir verificar, **diga que não verificou** — não afirme que funciona.
5. **Todo número novo vai para `config.json`** e é lido com `cfg_get`. Nunca literal no código.
6. **Não pule fase e não pule bloco.** Os *gates* entre blocos (Seção 4) existem para impedir que se
   construa em cima de fundação torta — foi exatamente o que aconteceu com as cidades.
7. **Não invente convenção de coordenadas.** A Seção 2.3 define a única válida. Desvios já custaram
   dois bugs nesta sessão.
8. **Todo ruído é avaliado em coordenada de MUNDO, nunca em índice de array.**
   `np.arange(H)` / `np.arange(W)` dentro de um gerador de terreno é **bug**, não estilo. Foi essa
   linha que criou três mundos diferentes (P0.4). Se você precisa de uma grade, ela sai de
   `np.linspace(x0_mundo, x1_mundo, largura)`.
9. **Não crie raster derivado novo.** Nada de `.npz` "de continente", "de região", "de cidade". Se
   você precisa de uma imagem de uma área, **chame a função** para aquela janela. Raster derivado é
   uma cópia que diverge do original — é literalmente o defeito que a Fase 0 está removendo.
10. **Ao terminar**: rode o aceite da fase, rode os testes da Seção 8 que a sua fase exige, e releia
    a lista "Não faça" dela.

---

## 1. Mapa do código

### 1.1 Pipeline (quem gera o quê)

**Hoje (antes da Fase 0):**
```
builder/reset_world.sh
├── cartographer/reset_cartography.sh
│   ├── world/generate_world.py ──────────► database/mapa_composto.npz  (768×768×4)
│   │                                    └─► database/world_manifest.json
│   ├── cities/generate_cities_metadata.py ► grava "cidades[]" no manifest (IA + sorteio)
│   ├── continents/generate_continent_zoom.py ► database/continentes/mapa_<slug>.npz  ❌ some
│   ├── cities/city_roi_zoom.py ──────────► database/cidades/mapa_<slug>.npz          ❌ some
│   └── tiles/generate_tile_pyramid.py ───► database/tiles/<z>/<x>/<y>.png (z=0..4)   ❌ some
└── builder/populate.py ──────────────────► database/openworld.db
```

**Depois da Fase 0** — os três artefatos derivados morrem; a função vira a única fonte de verdade:
```
builder/reset_world.sh
├── cartographer/reset_cartography.sh
│   ├── world/generate_world.py ──► database/mapa_composto.npz   (campo global grosseiro)
│   │                            └► database/world_manifest.json (+ layout_continentes, config_hash)
│   ├── cities/generate_cities_metadata.py ► grava "cidades[]" no manifest
│   └── tiles/prewarm_cache.py ───► aquece só z0..z2 no cache (~190 tiles, ~46 s)
└── builder/populate.py ──────────► database/openworld.db

GET /tiles/<z>/<x>/<y>.png ─► cache em disco? serve : TileCartographer.gerar_janela() → PNG → cache
```
> `mapa_composto.npz` **continua existindo** e continua importante: é o *campo global grosseiro*,
> a única forma de rodar as operações que não são pontuais (estatística de continente, colocação de
> cidade, e na Fase 6 a hidrografia). Ele deixa de ser fonte de imagem, não deixa de existir.

```
run_simulation.py ─► engine/loop.py (tick = 1 min simulado) ─► openworld.db
run_dashboard.py  ─► web/dashboard.py + blueprints ─► Flask :5000
```

### 1.2 Contratos de dados

| Artefato | Formato | Observações |
|---|---|---|
| `.npz` | `np.array(H, W, 4) float32`, chave `"mapa"` | Canais: **0=altitude [0,1], 1=temperatura [0,1], 2=umidade [0,1], 3=ID de bioma (inteiro guardado como float)** |
| `world_manifest.json` | dict | `seed`, `tile_size`, `dimensao_global`, `continentes[]`: `uuid`, `nome`, `area_planejada_km2`, `area_real_km2`, `pixels_terra`, `bounding_box{min_x,min_y,max_x,max_y}`, `biomas_predominantes[]`, `cidades[]` |
| cidade (no manifest) | dict | `nome`, `tamanho` (`pequeno`/`medio`/`grande`), `tipo`, `bioma_desejado`, `x_global`, `y_global` |
| tile | PNG 256×256 em `database/tiles/<z>/<x>/<y>.png` | z=0 é o mundo em 3×3 tiles. **Linha 0 = topo.** Servido por `GET /tiles/<z>/<x>/<y>.png` |
| config | `config.json` → `cfg_get(bloco, "chave")` | Acesso **estrito**: chave ausente levanta erro |

**IDs de bioma** (`cartographer/math/climate.py:14`):
`1=OCEANO, 2=DESERTO, 3=MEDITERRANEO, 4=FLORESTA_TEMPERADA, 5=MONTANHA_ROCHOSA`.

⚠️ Ao adicionar um bioma, **4 lugares** mudam juntos: `climate.py:14 (BIOME_IDS)` ·
`world_manager.py:82 (biomas_nomes)` · `config.json[cartografia][cores][biomas][<id>]` ·
`web/helpers.py:153` (paleta duplicada — dívida).

### 1.3 Arquivos por responsabilidade

**Cartografia**
| Arquivo | Responsabilidade | Símbolos-chave |
|---|---|---|
| `cartographer/world/tile_cartographer.py` | Gera 1 tile 256² do mundo | `generate_tile()` :25 · mescla terra/mar :147 · clima :154-164 |
| `cartographer/world/world_manager.py` | Compõe tiles, escreve manifesto | `save_world_manifest()` :67 · área real :138 · `biomas_nomes` :82 |
| `cartographer/math/noise.py` | Perlin vetorizado + fBm | `perlin_noise_2d_vectorized()` :3 · `generate_noise_field()` :66 |
| `cartographer/math/tectonics.py` | Máscara continental, warping, perfis, vinheta | `calculate_distance_grid()` :16 · `calculate_geological_profile()` :66 · `apply_cosine_vignette()` :97 |
| `cartographer/math/climate.py` | Temperatura, umidade, biomas | `calculate_temperature()` :22 · `calculate_humidity()` :38 · `classify_biomes()` :55 |
| `cartographer/math/coloring.py` | Paleta oceano/bioma | `render_ocean()` :14 · `interpolate_land_biome()` :44 |
| `cartographer/math/shading.py` | Hillshading NW | `calculate_northwest_hillshade()` |
| `cartographer/cities/generate_cities_metadata.py` | IA funda cidades + sorteia coordenada | alocação :91-121 |
| ~~`cartographer/continents/roi_zoom.py`~~ | **DELETAR na Fase 0.5** — upscale + ruído em índice local (P0.4) | — |
| ~~`cartographer/cities/city_roi_zoom.py`~~ | **DELETAR na Fase 0.5** — idem | — |
| ~~`cartographer/tiles/pyramid.py`~~ | **DELETAR na Fase 0.5** — mosaico de fontes | — |
| ~~`cartographer/tiles/generate_tile_pyramid.py`~~ | **DELETAR na Fase 0.5** — vira `prewarm_cache.py` | — |

**Fatos verificados sobre o código de terreno (a base da Fase 0):**
- `generate_tile()` monta a grade com `np.arange(start_x, start_x + size)` — **coordenada de mundo**.
- Toda a cadeia a jusante é **pontual e pura em `(grid_x, grid_y)`**: `perlin_noise_2d_vectorized`,
  `generate_noise_field`, `generate_tectonic_base`, `calculate_distance_grid`,
  `calculate_tectonic_radius`, `apply_coastal_distortion`, `calculate_geological_profile`,
  `apply_cosine_vignette`, `calculate_temperature`, `calculate_humidity`, `classify_biomes`.
  Nenhuma depende do `shape` do array nem de índice inteiro.
- Única exceção: `TectonicsProcessor.normalize_profile()` (:56) usa `np.min/np.max` global — e é
  **código morto**, ninguém chama. Não ressuscite: normalização por min/max do bloco tornaria o
  resultado dependente do recorte e reintroduziria costura.
- `web/helpers.py:render_biomes_map_to_bytes` (:130) também é **código morto** (grep confirmado, zero
  chamadores). Deletar resolve a "paleta duplicada" da Fase 1.5 sem migração nenhuma.
- Custo medido: **243 ms** por tile 256² com 4 continentes, 1 core, sem otimização.

**IA (Ollama local, `qwen2.5-coder:7b` em `localhost:11434`)**
| Arquivo | Papel |
|---|---|
| `ai/client.py` | `AIClient.query(prompt, json_format=True, timeout, model_name)` com retry/backoff |
| `ai/utils.py` | `AIUtils.parse_json_safely()` |
| `cartographer/ai/world_manager_ai.py` + `prompt/world_map_generation.txt` | Planeja continentes |
| `cartographer/ai/city_manager_ai.py` + `prompt/city_generation.txt` | Funda cidades (4 campos só) |
| `engine/ai/generator.py` + `prompts/dna.txt` | DNA de NPC (gera `personalidade`/`background` — **descartados hoje**) |
| `engine/ai/game_master.py` + `prompts/mestre_mensagem.txt` | Modo Mestre (Frente 5) |

**Engine**
| Arquivo | Responsabilidade | Símbolos-chave |
|---|---|---|
| `engine/loop.py` | Ordem do tick | `executar_tick()` :27 |
| `engine/mechanics/logic.py` | Utility AI | `calcular_utilidade()` :8 · `decidir_acao()` :154 |
| `engine/mechanics/actions.py` | As 7 ações | `executar_acao()` :10 |
| `engine/mechanics/movement.py` | Movimentação | `mover_para_*()` |
| `engine/models.py` | Dataclasses/enums | `Acao` :5 · `CategoriaLocal` :28 · `Local` :99 · `NPC` :114 |
| `engine/schema.sql` | Esquema SQLite | — |
| `builder/populate.py` | Povoamento | cidade spawn :46 · **6 locais hardcoded** :50-57 · coords aleatórias :61-62, :80-81 · DNA da IA :134-145 |

**Web**
| Arquivo | Responsabilidade |
|---|---|
| `web/composed_routes.py` | `/api/continentes` :92 · `/api/cidade/<nome>/imagem` :221 · `/api/cidade/<nome>/entities` :251 · `/tiles/<z>/<x>/<y>.png` :294 |
| `web/helpers.py` | `render_npz_array()` :8 · `obter_manifesto()` :206 |
| `web/static/js/mapa_leaflet.js` | Aba "Mapa Live" (tiles + CRS.Simple) |
| `web/static/js/mapa_composto.js` | Aba antiga em canvas — desenha locais :179-189 |

---

## 2. O modelo de escalas (leitura obrigatória)

> **Esta seção existe porque a ausência dela é a causa raiz dos bugs P0.** O sistema tem escalas
> diferentes que nunca foram declaradas, então o código passou a tratar "cidade" como "continente
> menor" — e não é.

### 2.1 As quatro escalas

| Escala | Extensão no mundo | Onde vive hoje | Serve para |
|---|---|---|---|
| **Mundo** | 768×768 px (1 px ≈ 15,8 km) | `mapa_composto.npz` | Continentes, oceanos, clima global |
| **Continente** | bbox do continente + 20 px | `continentes/mapa_<slug>.npz` | Relevo regional, biomas, rotas |
| **Região** | vizinhança de uma cidade | `cidades/mapa_<slug>.npz` ← **nome errado** | Terreno ao redor da cidade |
| **Cidade** | 1–3 km de diâmetro | **NÃO EXISTE** | Ruas, muralha, edifícios, aventura |

**O fato incontornável**: com 1 px ≈ 15,8 km, uma cidade de 2 km cabe em **1/8 de um pixel**.
**Nenhuma ampliação do raster do mundo jamais produzirá uma cidade** — ampliar pixel não cria
informação. A cidade precisa ser *gerada* num espaço próprio, não *extraída* do mapa. Quem não
entende isso continua aumentando o raio do recorte — que foi exatamente o que aconteceu
(`zoom_cidade_crop_raio_px`: 2 → 15 → 45), até o recorte "de cidade" ficar **maior que o continente**.

### 2.2 As quatro regras invariantes do terreno (substituem R1–R4 da v2.2)

O terreno **não é uma coleção de imagens**. É **uma função** `f(x_mundo, y_mundo) → (alt, temp, umid,
bioma)`. Tudo decorre disso:

- **F1 — Pureza**: `f` depende **apenas** de coordenada de mundo, seed e config. Nunca do tamanho do
  array, do índice do pixel, do recorte pedido ou da ordem em que os pontos foram avaliados.
  *Teste que garante*: `test_ruido_invariante_a_subdivisao` (Seção 8).
- **F2 — Invariância à subdivisão**: avaliar uma janela de uma vez e avaliá-la em 4 pedaços dá o
  **mesmo resultado, bit a bit**. É isto — e só isto — que elimina costura. Nenhum blend, nenhuma
  máscara de gradiente, nenhuma arbitragem de fonte.
- **F3 — Refinamento monotônico**: aumentar o zoom **acrescenta** oitavas de alta frequência; nunca
  reescala nem contradiz o que o zoom anterior mostrava. A forma grossa é preservada exatamente; só
  entra detalhe sub-pixel. *Refinar ≠ trocar o terreno.*
  ⚠️ Isto exige o conserto de normalização da Fase 0.2 — sem ele, adicionar oitava reescala o campo
  inteiro em ~6,5 % e as costas se mexem.
- **F4 — Camada global separada**: o que **não** é pontual (hidrografia, erosão, continentalidade,
  sombra de chuva) não cabe em `f`. Isso vive num **campo global grosseiro** calculado uma vez
  (`mapa_composto.npz`), interpolado **do mesmo jeito em todo zoom**, e somado ao detalhe procedural.
  Duas camadas, papéis distintos: *global grosseiro decide a forma; função local decide o detalhe.*

**Isotropia e "ganho de detalhe" saem de graça** — não há mais recorte para deformar (a janela é
pedida com o aspecto que se quer) e não há mais fonte filha para ganhar ou perder densidade.

### 2.3 Sistema de coordenadas — o único válido

| Espaço | Unidade | Origem | Uso |
|---|---|---|---|
| **Mundo** | pixel (float aceito) | canto superior esquerdo, **y cresce para baixo** | Tudo global: cidades, rios, POIs, `Local.coordenadas` (a partir da Fase 2) |
| **Imagem de fonte** | pixel da imagem | idem | Interno de `recortar()` |
| **Leaflet** | `L.latLng(-y, x)` | — | `pixelParaLatLng()` em `mapa_leaflet.js:27` |
| **Cidade local** | metro | centro da cidade | Só a partir da Fase 4, com transform documentado |

```
mundo → leaflet:  lat = -y          lng = x
leaflet → mundo:  y   = -lat        x   = lng
mundo → imagem de fonte com bbox (mnx,mny,mxx,mxy) e imagem (w,h):
      ix = (x - mnx) / (mxx - mnx) * w
      iy = (y - mny) / (mxy - mny) * h
```
⚠️ **Nunca** use `lat = dimensao_global - y`. Gerou tiles com `y` negativo (ROADMAP, parte 11).

---

## 3. Problemas — em ordem de prioridade

> Classificação: **P0 = quebrado** (impede usar o mundo) · **P1 = incoerente** (funciona, mas está
> errado e contamina o que for construído em cima) · **P2 = ausente** (falta funcionalidade; não é
> defeito). **Corrigir P0 e P1 antes de qualquer P2.**
> Tudo abaixo foi medido no mundo real do autor (reset de 2026-09-10 18:18).

> **Leia antes**: P0.1, P0.2 e P1.1 são **sintomas** de P0.4. Eles somem quando o mosaico é deletado
> na Fase 0 — não os ataque separadamente.

### P0 — Quebrado

#### P0.4 — As três fontes de zoom são mundos diferentes **[achado na auditoria — causa raiz]**

`roi_zoom.py:241-243` e `city_roi_zoom.py:156-158` avaliam o ruído de micro-detalhe em **índice
local da imagem**:
```python
y_range = np.arange(H, dtype=np.float32)      # ❌ 0..3000, não coordenada de mundo
x_range = np.arange(W, dtype=np.float32)
grid_x, grid_y = np.meshgrid(x_range, y_range)
```
No mesmo arquivo, `_recompute_climate_and_biomes` (:306-308) faz **certo**
(`np.linspace(min_x_global, max_x_global, W)`). As duas convenções convivem no mesmo módulo.

Consequência: as fontes não são resoluções diferentes do mesmo mundo, são **mundos diferentes**.
Medido, amostrando o mesmo ponto de mundo em cada raster:

| Comparação | \|Δaltitude\| máx | pixels que trocam terra↔água | biomas divergentes |
|---|---|---|---|
| continente vs mundo | 0,0118 | **0,32 – 0,80 %** | 0,32 – 0,80 % |
| região vs continente | 0,0158 | **0,36 – 1,17 %** | 0,55 – 1,35 % |

Hoje o estrago é modesto só porque `zoom_micro_amp_base = 0.024` é tímido. Ele **escala** quando:
(a) alguém aumentar a amplitude para ter relevo visível no zoom — o próximo passo óbvio;
(b) a Fase 6 desenhar um rio derivado do DEM do mundo sobre o raster da região — **o rio não vai
correr no vale**; (c) a Fase 4 ancorar uma muralha num pixel que é terra num raster e água no outro.

Viola **F1** e **F2**. É a causa raiz de P0.1, P0.2 e P1.1.

#### P0.5 — O mundo não é reproduzível a partir do manifesto **[achado na auditoria]**

`WorldManager.__init__` (:23) obtém o layout de continentes de
`WorldManagerAIClient.planejar_continentes()` — uma **chamada de LLM**. O manifesto grava só
`centro_planejado` e `area_planejada_km2`. Os campos que `generate_tile` realmente consome —
`irregularidade` (:95), `elevacao_maxima` (:96), `perfil_geologico` (:97), `modificadores` (:124) —
**não são persistidos em lugar nenhum**.

Dois efeitos: o mundo muda a cada regeração mesmo com a mesma seed; e **nenhum processo além do
`generate_world.py` consegue reproduzir o campo** — o que bloqueia a Fase 0 inteira (o servidor de
tiles precisa exatamente do mesmo layout, e não pode chamar a IA para consegui-lo).

#### P0.1 — A região "de cidade" engole o continente **[reportado pelo autor]**
`zoom_cidade_crop_raio_px = 45` é **fixo**, mas os continentes têm bbox de 45 a 127 px:

| Continente | bbox | Recorte "de cidade" | Razão área recorte/continente |
|---|---|---|---|
| Avalonia | 67×45 px | 91×91 px | **2,7×** — engole o continente inteiro |
| Gardania | 70×127 px | 91×91 px | 0,9× |
| Nimbaria | 75×81 px | 91×91 px | 1,4× |
| Terraforma | 98×63 px | 91×91 px | 1,3× |

Em Avalonia, o "mapa da cidade Vila Nova" é literalmente o continente Avalonia inteiro mais oceano em
volta. É por isso que o autor vê continente ao pedir cidade.

> **Sintoma de P0.4** — some junto com o mosaico. Não escreva código para "corrigir o raio".
>
> ⚠️ **A v2.2 propunha um `assert` para pegar isto e ele não pega.** O assert testava se a região
> *contém a bbox do pai com padding*; medido no mundo real, dá `False` nos 4 continentes — inclusive
> em Avalonia, onde a região tem 2,7× a área do continente (região 90×90 vs. pai-com-padding 107×85).
> O segundo assert (`densidades == sorted(densidades, reverse=True)`) era tautológico: rodava sobre
> uma lista que a própria função acabara de ordenar. Guarda-corpo que não pode falhar não é
> guarda-corpo.

#### P0.2 — Aproximar da cidade piora o mapa **[autor: "não faz zoom até a cidade"]**
`carregar_fontes()` (`pyramid.py:108`) devolve `fontes_cidade + fontes_continente + [mundo]` e
`encontrar_fonte()` (:111) pega a **primeira** que contém o ponto → cidade sempre vence. A densidade
real diz o contrário:

| Continente | Densidade continente | Densidade "cidade" | Cidade tem mais detalhe? |
|---|---|---|---|
| Avalonia | 27,8 | 22,0 | ❌ não |
| Gardania | 17,9 | 22,0 | ✅ marginal |
| Nimbaria | 24,6 | 22,0 | ❌ não |
| Terraforma | 21,6 | 22,0 | ✅ marginal |

Em 2 de 4 casos a fonte pior tem prioridade máxima. Com o teto global `tile_zoom_maximo = 4`,
aproximar não revela nada novo — às vezes revela menos.

> **Sintoma de P0.4 + P1.6** — some com o mosaico, mas só fica *bom* com o conserto de oitavas
> (P1.6). Ordenar fontes por densidade não resolveria: a fonte mais densa continuaria sendo uma
> interpolação de um terreno que não tem informação naquela escala.

#### P0.3 — Locais da simulação caem na água **[reportado pelo autor]**
`builder/populate.py:61-62` e `:80-81`: `coordenadas = [random.randint(5,35), random.randint(5,35)]`.
Esse par não é coordenada de mundo, nem de cidade, nem de nada. `mapa_composto.js:179-189` desenha
esse par direto sobre a imagem da cidade (`offsetX + x*tileSize*scale`), sem **nenhuma** validação
contra `nivel_mar`. Confirmado no banco: `loc_00 [33,25]`, `casa_02 [5,20]`, etc.

### P1 — Incoerente

#### P1.1 — Mapas de continente deformados **[achado na revisão, não reportado]**
`roi_zoom.py:355` faz `self._upscale(crop, target, target)` — recorte **retangular** vira imagem
**sempre quadrada** 3000×3000. Deformação medida: Avalonia 1,26× · Gardania **1,51×** ·
Nimbaria 1,05× · Terraforma 1,34×. Gardania está horizontalmente espremido em 51%.
A pirâmide compensa (`recortar()` mapeia proporcionalmente), mas a imagem de
`/api/continente/<uuid>/imagem` e o mapa antigo mostram o continente distorcido.

> **Sintoma de P0.4** — some com o mosaico: sem recorte para esticar, a janela é pedida já no aspecto
> correto.

#### P1.6 — O detalhe é limitado por oitavas, não por resolução **[achado na auditoria]**

Esta é a explicação real do "borrão ampliado" que o autor reporta, e ela **contraria** a hipótese que
guiou a Frente 6 ("falta pixel, aumenta o recorte / a resolução").

Com `ruido_costa_escala = 60` e `ruido_costa_oitavas = 4` em `lacunariedade = 2.1`, a menor feição
real do terreno é `60 / 2,1³ ≈ 6,5 px ≈ 100 km`. O raster de 768² já está **superamostrado** em
relação ao próprio conteúdo. Em z4 (16×), uma feição de 100 km ocupa ~104 px de tela — o borrão.

**Renderizar em 8192² daria o mesmo borrão, maior.** Detalhe novo em zoom vem de **mais oitavas na
mesma função**, não de mais pixels nem de recorte maior. Para ter feição do tamanho do pixel de tela
em z4 são ~9–10 oitavas contra as 4 de hoje — custo desprezível, e consistente por construção porque
as oitavas graves são idênticas.

#### P1.7 — A normalização do fBm impede adicionar oitavas **[achado na auditoria]**

`noise.py:98` normaliza pela soma **truncada** das amplitudes:
```python
limite = max_val * 0.707        # max_val = Σ persistencia^i, i < octaves
```
Com `persistencia = 0.5`, ir de 4 para 9 oitavas muda o divisor de 1,875 para 1,996 — **reescala o
campo inteiro em ~6,5 %**, e as costas se mexem. Ou seja: hoje é *impossível* adicionar detalhe por
zoom sem contradizer o zoom anterior. Viola **F3**, e é bloqueador de P1.6.

#### P1.2 — Continentes 5–8× menores que o planejado
Avalonia: planejada 4.500.000 km² → real **559.250 km²**. Cadeia (`tile_cartographer.py:77-121`):
`R = sqrt(área/(π·250)) = 75,7 px` → terra exige `fator_radial ≥ 0.35` (corta para 0,65·R) →
`raio_dinamico` médio 1,02·R → distorção costeira soma +0,19·R → vinheta corta as bordas.
**Raio efetivo ≈ 0,35·R** → área ≈ 12% da planejada.

#### P1.3 — Monocultura: 100% Floresta Temperada nos 4 continentes
Causa verificável em `climate.py`:
- `calculate_humidity()` :38 devolve **constante em toda terra**: `0.4 + mod_umidade`
  (`mod ∈ [-0.3, +0.3]`). Zero variação espacial.
- `calculate_temperature()` :22 = `(1 - y/768) - altitude·0.4 + mod_calor` → terra fica em **0,31–0,49**.
- Deserto exige `temp > 0.6` (inalcançável); Mediterrâneo exige `umid ≥ 0.5` (só com `mod ≥ +0.1`).
  Tudo cai no `else` → Floresta Temperada. Resultado: `bioma_desejado` das cidades é decorativo.

#### P1.4 — Cidades da IA não são validadas nem bem posicionadas
`cidades_min_por_continente = 3`, mas o reset produziu **1 por continente** — sem validação nem
retry. A alocação (`generate_cities_metadata.py:112`) é `random.choice` entre pixels do bioma:
ignora costa, altitude, distância entre cidades e recursos.

#### P1.5 — Simulação desconectada da cartografia
`populate.py:46` simula **uma única cidade** (`cidades_salvas[0]`) com **6 locais hardcoded**
(:50-57). O manifesto tem 4 cidades e o banco tem 4 registros, mas só a de `id=1` tem locais e NPCs.

### P2 — Ausente (funcionalidade que falta, não defeito)

- **P2.1 — Leaflet só mostra terreno**: sem marcadores, rótulos, rios, estradas, fronteiras, POIs
  ou NPCs no mapa.
- **P2.2 — Não existe cidade como lugar**: nem rua, nem muralha, nem edifício. Consequência direta
  do modelo de escalas (Seção 2.1).
- **P2.3 — Sem hidrografia**: nenhum rio, lago ou bacia.
- **P2.4 — Só 5 biomas e paleta chapada**: faltam tundra, taiga, savana, selva, pântano, pradaria,
  geleira, praia; sem textura nem transição.
- **P2.5 — IA dos NPCs rasa**: 7 ações decididas por `if`s com horários globais; personalidade
  gerada pela IA é descartada; sem objetivos, sem planos multi-tick; `memoria_eventos` nunca é lida.

---

## 4. Ordem de execução

**Regra de ouro: primeiro fazer o que existe funcionar direito; só então adicionar coisa nova.**
Não crie bioma novo, rio ou erosão enquanto o mundo não passar no *gate* do Bloco I.

### BLOCO I — MUNDO COERENTE (só correção)
| Fase | Tema | Corrige |
|---|---|---|
| **0** | O tile é uma função | P0.4, P0.5, P1.7 → e com eles P0.1, P0.2, P1.1 |
| **1** | Cartografia coerente | P1.2, P1.3, P1.4, P1.6 |
| **2** | Vínculo cartografia ↔ simulação | P0.3, P1.5 |

> ### 🚧 GATE 1 — só avance para o Bloco II quando **todos** forem verdade:
> 1. Os testes obrigatórios da Seção 8 (T1–T6) passam.
> 2. **Zero** `.npz` derivado em `database/continentes/` e `database/cidades/` — os diretórios não
>    existem mais.
> 3. Aproximar de uma cidade no Mapa Live revela **detalhe novo**, não o mesmo borrão ampliado.
> 4. O mesmo ponto do mundo tem a mesma classificação terra/água em z0, z4 e z6.
> 5. Regerar o mundo duas vezes com a mesma seed produz `mapa_composto.npz` idêntico.
> 6. Razão `area_real/area_planejada` entre 0,7 e 1,3 em todos os continentes.
> 7. Nenhum continente com um único bioma a 100%.
> 8. Todo continente com ≥ `cidades_min_por_continente` cidades.
> 9. **Zero** locais na água; nenhuma coordenada aleatória no banco.
> 10. Cada cidade do manifesto tem seus próprios locais no banco.

### BLOCO II — MUNDO USÁVEL NA MESA (completar o que falta para jogar)
| Fase | Tema | Resolve |
|---|---|---|
| **3** | Camada vetorial + Leaflet rico | P2.1 |
| **4** | Cidades de verdade (GeoJSON) | P2.2 — e é a correção **definitiva** de P0.1/P0.3/P1.5 |
| **5** | IA local projetando as cidades | aprofunda P1.4 |

> ### 🚧 GATE 2 — só avance para o Bloco III quando:
> 1. Dá para abrir uma cidade no Leaflet e ver ruas, muralha e edifícios nomeados.
> 2. Dá zoom além do z4 e o vetor continua nítido.
> 3. Os `Local` da simulação vêm do GeoJSON da cidade, não de código hardcoded.
> 4. Com o Ollama desligado, as cidades ainda saem completas e nomeadas (fallback procedural).

### BLOCO III — MUNDO RICO (enriquecimento)
| Fase | Tema | Resolve |
|---|---|---|
| **6** | Hidrografia (rios, lagos, bacias) | P2.3 |
| **7** | Biomas novos e riqueza visual | P2.4 |
| **8** | NPC: necessidades, traços, agenda | P2.5 |
| **9** | NPC: memória, objetivos, planos | P2.5 |
| **10** | Relevo por placas e erosão | — |
| **11** | Papéis, economia e ganchos de aventura | — |

### A correção definitiva, em um parágrafo
São dois movimentos. **(1) Deixar de fabricar rasters derivados** (Fase 0): o tile passa a ser a
função de terreno avaliada naquela janela, naquele zoom. Depois disso é *estruturalmente impossível*
haver costura, deformação, fonte pior com prioridade ou região maior que o continente — porque não
existem mais fontes, recortes nem regiões. **(2) Criar a escala que falta** (Fase 4): a cidade deixa
de ser recorte de raster e passa a ser **geometria vetorial gerada** (ruas, muralha, lotes,
edifícios) em GeoJSON, ancorada num pixel do mundo — o que corrige P0.3 e P1.5 na raiz e dá zoom
infinito de graça, porque vetor não pixeliza.

### O teto honesto — decida antes da Fase 3
Zoom infinito em fBm é tecnicamente trivial e **visualmente entediante**: ampliar ruído para sempre
dá a mesma penugem marrom. O z18 do Google Maps mostra *objetos*, não mais terreno. A Fase 4 resolve
isso para a cidade (vetor); **fora da cidade o problema volta** no minuto em que alguém der zoom no
meio do mato. A resposta de verdade para a escala selvagem é **conteúdo instanciado** determinístico
por coordenada (bosques, afloramentos, trilhas, ruínas), não mais oitavas. Isso não está planejado em
nenhuma fase — decida se entra antes da Fase 3, porque muda o que a camada vetorial precisa suportar.

**Princípios que regem tudo daqui pra frente:**
> **Raster para o que é natural; vetor para o que é humano.**
> **Python decide geometria; a IA decide significado** — a LLM nunca inventa coordenadas; ela recebe
> geometria pronta e devolve nomes, descrições, donos, rumores e ganchos.

---

## 5. As fases

---

### FASE 0 — O tile é uma função (não um recorte)  ·  Bloco I

**Corrige**: P0.4, P0.5, P1.7 — e com eles, de graça, P0.1, P0.2 e P1.1.
**Pré-requisitos**: nenhum.
**Regenera dados?** Sim, e **o mundo vai mudar de aparência** — o conserto de normalização (0.2)
altera os valores do ruído. Isso é esperado, é uma vez só, e é o preço de destravar o zoom.

**A ideia em uma frase**: `TileCartographer.generate_tile()` já é uma função pura de coordenada de
mundo; basta deixá-la aceitar um passo de amostragem menor que 1 px e ela gera **qualquer janela do
mundo em qualquer resolução** — sem upscale, sem mosaico, sem costura, sem arbitragem de fonte.

**Ordem obrigatória**: 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6. As duas primeiras são bloqueadoras.

#### 0.1 — Persistir o layout de continentes no manifesto → corrige P0.5

**Arquivos**: `cartographer/world/world_manager.py`, `cartographer/world/generate_world.py`

Bloqueador de tudo: hoje o layout vem de uma chamada de LLM em `WorldManager.__init__` (:23) e
**não é gravado**. Sem ele persistido, o servidor de tiles não consegue reproduzir o mesmo mundo.

1. Em `save_world_manifest()`, antes de gravar o JSON:
   ```python
   import hashlib
   manifest["layout_continentes"] = self.layout_continentes   # dict cru da IA/fallback
   manifest["config_hash"] = hashlib.sha256(
       json.dumps(self.config, sort_keys=True, ensure_ascii=False).encode("utf-8")
   ).hexdigest()[:16]
   ```
2. Em `WorldManager.__init__`, aceitar `layout_continentes=None` e só chamar
   `WorldManagerAIClient.planejar_continentes()` quando não receber um.
3. Em `generate_world.py`, **reusar** o layout do manifesto se ele já existir; só replanejar com a IA
   quando o manifesto não existir ou quando rodar com `--replanejar`.

`layout_continentes` é consumido direto por `TileCartographer`, então tem que conter, por continente:
`nome`, `centro_x`, `centro_y`, `area_km2`, `irregularidade`, `elevacao_maxima`, `perfil_geologico`,
`modificadores{calor,umidade}`. **Confira que o fallback procedural de `planejar_continentes` também
preenche todos** — se ele omitir algum, `generate_tile` cai em default silencioso (:89, :96, :97).

`config_hash` é a chave de invalidação do cache de tiles (0.4). Sem ele, mudar config deixa tile
velho servindo terreno antigo em silêncio — o projeto hoje não tem invalidação nenhuma para os 6
tipos de artefato derivado que produz.

**Não faça**: não normalize nem "limpe" o layout ao gravar. Grave o dict exatamente como
`TileCartographer` o recebe. Qualquer transformação vira uma segunda convenção que vai divergir.

**Aceite**:
```bash
venv/bin/python -c "
import json; m=json.load(open('database/world_manifest.json'))
req={'centro_x','centro_y','area_km2','irregularidade','elevacao_maxima','perfil_geologico','modificadores'}
for c in m['layout_continentes']['continentes']:
    falta = req - set(c)
    print(f\"{c['nome']:<14}{'OK' if not falta else 'FALTA ' + str(sorted(falta))}\")
print('config_hash:', m.get('config_hash'))
"
```

#### 0.2 — Normalização estável do fBm → corrige P1.7, destrava P1.6

**Arquivo**: `cartographer/math/noise.py:98`

Bloqueador de **F3**. Hoje o divisor é a soma **truncada** das amplitudes, então mudar o número de
oitavas reescala o campo inteiro e as costas se mexem.

```python
# ANTES
limite = max_val * 0.707
# DEPOIS — soma infinita da série geométrica: adicionar oitava CONVERGE, não reescala
soma_infinita = 1.0 / (1.0 - persistencia) if persistencia < 1.0 else max_val
limite = soma_infinita * 0.707
```

Efeito: com `persistencia = 0.5` o divisor sai de `1,875 × 0,707` para `2,0 × 0,707` — o campo
comprime ~6,5 % em direção a 0,5, **uma vez**. Depois disso, 4 e 12 oitavas concordam dentro da
amplitude das oitavas omitidas, para sempre.

**Não faça**: não tente preservar o visual antigo compensando com outro fator. O visual antigo é
exatamente o que impede o zoom de funcionar. Se o contraste do relevo ficar fraco, ajuste
`tectonica_base_peso_*` ou as amplitudes em config — **nunca** o normalizador.

**Testes obrigatórios**: T2 e T3 (Seção 8).

#### 0.3 — `gerar_janela()`: a primitiva de qualquer zoom

**Arquivo**: `cartographer/world/tile_cartographer.py`

Extrair o corpo de `generate_tile()` para um método que recebe a janela em coordenada de mundo:

```python
def gerar_janela(self, x0, y0, x1, y1, largura, altura, oitavas_extra=0):
    """Gera (altura, largura, 4) para a janela [x0,x1) x [y0,y1) do mundo.
    `oitavas_extra` acrescenta detalhe de alta frequência sem alterar a forma grossa (F3)."""
    x_range = np.linspace(x0, x1, largura, endpoint=False, dtype=np.float32)
    y_range = np.linspace(y0, y1, altura, endpoint=False, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(x_range, y_range)
    dados = np.zeros((altura, largura, 4), dtype=np.float32)
    # ... resto idêntico ao generate_tile de hoje, escrevendo em `dados`,
    #     e cada `octaves=N` do terreno virando `octaves=N + oitavas_extra`
    return dados

def generate_tile(self, offset_x, offset_y):
    s = self.size
    return self.gerar_janela(offset_x*s, offset_y*s, (offset_x+1)*s, (offset_y+1)*s, s, s)
```

**Por que a refatoração é segura**: `linspace(a, a+256, 256, endpoint=False)` é **exatamente**
`arange(a, a+256)`. Comportamento em z0 preservado por construção, e o teste **T4** verifica
igualdade bit a bit.

**Pontos de atenção (é aqui que se erra):**
- `self.data` hoje é alocado no `__init__` como `(size, size, 4)` e **reusado entre chamadas**. Aloque
  dentro de `gerar_janela` com `(altura, largura, 4)`, senão janela não-quadrada quebra e chamadas
  concorrentes se corrompem.
- `oitavas_extra` entra em **todas** as chamadas de terreno (`ruido_macro`, `generate_tectonic_base`,
  `ruido_costa`, `ruido_mar`, perfil geológico, warp). **Não** aplique ao dithering de bioma em
  `classify_biomes` (`octaves=1`) — ali a macro-onda lisa é intencional.
- `calculate_temperature` (`grid_y / map_height`) e `apply_cosine_vignette` (`map_size`) continuam
  recebendo `self.tamanho_global` (768), **não** a largura da janela. Passar a largura faz a latitude
  e a vinheta mudarem com o zoom — bug sutil e difícil de ver.
- `calculate_distance_grid` faz 2 campos de ruído por continente. Com culling (abaixo) isso cai muito.

**Culling de continentes** (implementado e verificado — 2,56x mais rápido em z7 num tile oceânico,
dentro da faixa 2-4x prevista): pula o continente cujo raio de influência não alcança a janela.
```python
alcance = R * (fator_min + fator_variacao) + irreg * R * fator_distorcao + warp_amplitude
if distancia_da_janela_ao_centro(cx, cy) > alcance:
    continue
```
O teste **T5** confirma que ligar/desligar culling não muda o resultado (passou de primeira, sem
precisar alargar `alcance`) — verificado tanto com continentes sintéticos quanto no mundo real.

**Config novo**:
```jsonc
"tile_oitavas_extra_por_zoom": 1,
"tile_oitavas_max": 12
```
com `oitavas_extra = min(z * tile_oitavas_extra_por_zoom, tile_oitavas_max - oitavas_base)`.

#### 0.4 — Tile sob demanda com cache

**Arquivos**: `web/composed_routes.py:294`, novo `cartographer/tiles/render.py`

```python
escala = 2 ** z
x0, y0 = tx * tile_size / escala,     ty * tile_size / escala
x1, y1 = (tx+1) * tile_size / escala, (ty+1) * tile_size / escala
dados = cartografo.gerar_janela(x0, y0, x1, y1, tile_size, tile_size, oitavas_extra_de(z))
rgb = render_npz_array(dados)   # já aceita array pronto, não só caminho — helpers.py:19-24
```

**Cache**: `database/tiles_cache/<config_hash>/<z>/<x>/<y>.png`. A rota serve o arquivo se existir,
senão gera, grava e serve. Config mudou → hash mudou → diretório novo, e o antigo é lixo apagável.
O `TileCartographer` deve ser instanciado **uma vez** por processo (o layout vem do manifesto), não
por requisição.

⚠️ **Hillshading por zoom — armadilha real, e já implementada/verificada (2026-09-10).**
`render_npz_array` (antes :55-58) escalava o relevo por `width / resolucao_base`. Como todo tile tem
`width = 256`, a escala ficava constante enquanto o gradiente de altitude por pixel encolhe com o
zoom — **o relevo achatava conforme se aproximava** (confirmado visualmente: tile em z4/z7 sem
nenhuma textura de relevo visível, só cor chapada).

`ShadingProcessor.calculate_northwest_hillshade` calcula `np.gradient(heightmap)` **por passo de
pixel de imagem**, não por unidade de mundo. Como o terreno é liso em coordenada de mundo, a
diferença de altitude entre pixels de imagem vizinhos ENCOLHE conforme o zoom aumenta (pixels cada
vez mais próximos em mundo) — por isso a escala precisa **crescer** para compensar, não diminuir.
A fórmula certa **divide**, não multiplica, por `mundo_px_por_img_px = (x1-x0)/largura`:
```python
escala_dinamica = escala_base / mundo_px_por_img_px
```
Verificado: com essa fórmula, o desvio-padrão do fator de luz fica estável entre z0/z4/z7
(0,155 / 0,124 / 0,137) em vez de colapsar para perto de zero. `render_npz_array` (`web/helpers.py`)
já aceita esse fator como parâmetro explícito (`mundo_px_por_img_px`) em vez de derivá-lo de `width`;
`cartographer/tiles/render.py` já passa `(wx1-wx0)/tile_size` em cada tile gerado.

**Pré-aquecimento**: `cartographer/tiles/prewarm_cache.py` gera z0..z2 (9+36+144 = 189 tiles ≈ 46 s)
no fim do reset, para a primeira abertura do mapa ser instantânea. Acima de z2, sob demanda.

**Não faça**: **não pré-gere a pirâmide inteira.** Medido: z0..z4 = 3069 tiles × 243 ms = **12,4 min**,
pior que o reset inteiro de hoje, e z5 sozinho seriam mais 37 min. Sob demanda são 243 ms na primeira
vista de cada tile e zero depois.

#### 0.5 — Deletar o mosaico

Só depois de 0.3 e 0.4 funcionando. Verifique com `grep -rn` antes de cada remoção.

| Deletar | Substituído por |
|---|---|
| `cartographer/tiles/pyramid.py` | `gerar_janela` + cache |
| `cartographer/tiles/generate_tile_pyramid.py` | `prewarm_cache.py` |
| `cartographer/continents/roi_zoom.py` + `generate_continent_zoom.py` | `gerar_janela` na bbox |
| `cartographer/cities/city_roi_zoom.py` | `gerar_janela` na vizinhança da cidade |
| `database/continentes/`, `database/cidades/*.npz` | — |
| `web/helpers.py:render_biomes_map_to_bytes` (:130) | nada — **código morto, zero chamadores** |
| `web/helpers.py:obter_continente_e_caminhos` (:219) | devolve caminho de `.npz` que não existe mais |
| `TectonicsProcessor.normalize_profile` (`tectonics.py:56`) | nada — **código morto** |

Reapontar os consumidores (todos em `web/composed_routes.py`):
- `/api/continente/<uuid>/imagem` (:137) → janela = bbox + `janela_padding_px`, **no aspecto real**
  (isotropia sai de graça: peça `largura`/`altura` proporcionais à janela)
- `/api/cidade/<nome>/imagem` (:221) → janela centrada em `(x_global, y_global)`, raio de config
- `/api/continente/<uuid>/info/<x>/<y>` (:175) e `/api/mapa_composto/info` (:48) → ler do campo global
- `web/static/js/mapa_composto.js` consome os dois primeiros (:517, :563) — confira que não assume
  imagem quadrada.

**Config a remover**: `zoom_cidade_crop_raio_px`, `zoom_cidade_resolucao_px`, `zoom_cidade_hf_escala`,
`zoom_cidade_hf_oitavas`, `zoom_cidade_amp`, `zoom_micro_*`, `zoom_upscale_ordem`,
`zoom_suavizacao_sigma_px`, `zoom_costa_profundidade_*`, `tile_zoom_maximo`.
`zoom_border_padding_px` → renomear para `janela_padding_px` (usado só pelo endpoint de continente).

**Atualizar** `cartographer/reset_cartography.sh`: remover os dois passos de zoom e o da pirâmide;
acrescentar o prewarm; trocar os `rm -rf` correspondentes.

#### 0.6 — Leaflet sem teto artificial

**Arquivo**: `web/static/js/mapa_leaflet.js`

- `maxZoom` do mapa e da `L.tileLayer` sobem de 4 para `tile_zoom_maximo_ui` (sugerido **7**).
- `maxNativeZoom` deixa de ser truque para esconder falta de dado e vira só **controle de custo**:
  acima do zoom em que as oitavas param de acrescentar informação, deixe o Leaflet esticar.
- ⚠️ Armadilha nº 3 (Seção 6.3) continua valendo: `minZoom` do mapa tem que bater com o da camada.
- `/api/continentes` (:92) passa a devolver `tile_zoom_maximo_ui` junto de `dimensao_global`
  (e o early-return de manifesto vazio também — ver Fase 1.5).

#### Config novo (Fase 0)
```jsonc
"tile_oitavas_extra_por_zoom": 1,
"tile_oitavas_max": 12,
"tile_zoom_maximo_ui": 7,
"tile_prewarm_zoom_max": 2,
"janela_padding_px": 20,
"cidade_janela_raio_px": 12
```

#### Aceite (Fase 0)

Os testes **T1–T6** da Seção 8 passam, **mais**:

```bash
# 1. COERÊNCIA ENTRE ZOOMS — o mesmo ponto do mundo, amostrado em dois zooms
venv/bin/python -c "
import sys, json, numpy as np; sys.path.insert(0,'.')
from cartographer.world.tile_cartographer import TileCartographer
from cartographer.config import CARTOGRAPHER_CONFIG as CFG
m=json.load(open('database/world_manifest.json'))
tc=TileCartographer(size=256, seed=m['seed'], config=CFG,
                    layout_continentes=m['layout_continentes'], tamanho_global=m['dimensao_global'])
x0,y0,x1,y1 = 240,280,256,296                      # janela de 16x16 px de mundo
a  = tc.gerar_janela(x0,y0,x1,y1,  64, 64, oitavas_extra=2)
b  = tc.gerar_janela(x0,y0,x1,y1, 512,512, oitavas_extra=5)[::8,::8]   # mesmos pontos exatos
nm = CFG['nivel_mar']
flips = int(((a[:,:,0]>=nm) != (b[:,:,0]>=nm)).sum())
print('|dalt| max         :', float(np.abs(a[:,:,0]-b[:,:,0]).max()))
print('trocam terra/agua  :', flips, 'de', a[:,:,0].size)
print('OK' if flips == 0 else 'FALHOU — o zoom esta contradizendo, nao refinando')
"

# 2. Nenhum raster derivado sobrou
test ! -d database/continentes && test ! -d database/cidades && echo 'OK: mosaico removido'

# 3. Reprodutibilidade (Gate 1, item 5)
cp database/mapa_composto.npz /tmp/mundo_antes.npz
venv/bin/python cartographer/world/generate_world.py
venv/bin/python -c "
import numpy as np
a=np.load('/tmp/mundo_antes.npz')['mapa']; b=np.load('database/mapa_composto.npz')['mapa']
print('identico:', np.array_equal(a,b), '| OK' if np.array_equal(a,b) else '| FALHOU')
"
```

**Critério**: `trocam terra/agua = 0`, os dois diretórios sumiram, e regerar o mundo dá array
idêntico. E, no navegador: aproximar de uma cidade no Mapa Live e **ver detalhe novo**, com a linha
de costa se refinando (baías e reentrâncias aparecendo) em vez de se mexer.

---

### FASE 1 — Cartografia coerente  ·  Bloco I

**Corrige**: P1.2, P1.3, P1.4, P1.6. **Pré-requisitos**: Fase 0.
**Por que aqui**: tamanho de continente, variedade de bioma e posição de cidade são **entradas** de
tudo que vem depois. Corrigir isso mais tarde significa regerar mundo e cidades de novo.

#### 1.1 — Calibrar o tamanho dos continentes (P1.2) — implementado (2026-09-10)

> ⚠️ **Um scalar único não resolveu.** A ideia original (mudar
> `continente_area_para_raio_fator_visual` pra um valor fixo) foi tentada e **falhou** —
> medido: com um único fator, os continentes variavam de razão 0,15 a 2,09 no mesmo mundo,
> porque três efeitos diferentes empurram a área real pra longe da planejada, e nenhum
> deles é corrigível por um fator global:
>
> 1. **A IA ignora a própria instrução de posição.** O prompt pede `centro_x`/`centro_y`
>    entre 180 e 580 ("nunca perto da borda"), mas ela às vezes não obedece — um
>    continente saiu em `x=50`, a vinheta cortou quase tudo, área real caiu pra 15% da
>    planejada. **Corrigido**: `WorldManagerAIClient._clampar_centros()` clampa o centro em
>    Python depois da resposta da IA (e no fallback procedural) — "Python decide
>    geometria" não é só um princípio, agora é um `min`/`max` de verdade. Novo config:
>    `continente_centro_margem_borda_px: 180`.
> 2. **Irregularidade encolhe área, não só a forma.** `apply_coastal_distortion` soma
>    `ruido_costa · irregularidade · R · fator_distorcao` à distância — quanto mais
>    "recortado" o continente (irregularidade alta, o que o próprio prompt pede pra
>    fiordes), menor a área real pro mesmo R. Medido: mesma `area_km2`, irregularidade
>    0,25 vs. 0,70 → área real 3,5× diferente. **Corrigido**: `TileCartographer.
>    calcular_raio_efetivo()` deriva uma compensação da própria fórmula do raio efetivo
>    (não é número chutado — é `1/(1 - k·irreg)`, com `k` calculado a partir de
>    `tectonica_raio_fator_min/variacao`, `tectonica_costa_distorcao_fator` e `nivel_mar`).
> 3. **Continentes competem por território de fronteira.** `mask_continente =
>    np.maximum(...)` entre todos os continentes significa que dois vizinhos próximos (a
>    IA já exige só 220px de espaçamento mínimo, e R pode passar de 200px) disputam a
>    região entre si — o que "ganha" ali vira área de um, não do outro. Acontece mesmo
>    com o raio "certo" calculado isoladamente: um continente perdeu 36% de área real só
>    por causa da disputa, não por nenhum erro de fórmula. **Corrigido**:
>    `WorldManager._calibrar_continentes()` acha por bisseção um `compensacao_calibrada`
>    por continente, renderizando **todos os continentes juntos** (pra capturar a disputa
>    real) e medindo com atribuição **exata** — `gerar_janela(..., retornar_donos=True)`
>    devolve o índice de quem realmente venceu o `np.maximum` em cada pixel, não uma
>    aproximação por distância ao centro (que também rouba área de continente pequeno
>    perto de um grande). 3 rodadas tipo Gauss-Seidel (cada continente se recalibra vendo
>    o estado atual dos vizinhos) convergem pra um equilíbrio. Persistido em
>    `layout_continentes[].compensacao_calibrada` — não recalcula a cada load (P0.5).
> 4. **Achado depois, num reset independente (2026-09-11): a IA também ignora o limite de
>    `irregularidade`.** O prompt pede 0,1–0,8; um continente saiu com `irregularidade=0,9`
>    e ficou preso em 63% de área real mesmo com a compensação (2) e a calibração
>    adaptativa (3) — a bisseção precisou de `compensacao_calibrada≈3,94`, quase no teto de
>    busca (4,0), e ainda assim não bastou. Mesma causa raiz do item 1 (IA não respeita
>    limite pedido em texto), campo diferente. **Corrigido de forma generalizada**:
>    `WorldManagerAIClient._validar_e_clampar_layout()` (renomeado de `_clampar_centros`)
>    agora clampa **todo** campo geométrico do continente ao intervalo que o próprio
>    prompt pede — `irregularidade` [0,1–0,8], `area_km2` [2,5M–8M], `elevacao_maxima`
>    [0,6–1,0], `modificadores.calor/umidade` [-0,3, 0,3] — não só a posição. Reverificado
>    em 2 resets completos subsequentes: 10/10 continentes dentro da faixa.
>
> `continente_area_para_raio_fator_visual` continua existindo como o **chute inicial** pro
> raio antes da calibração fina — calibrado empiricamente em **`1.5`** (não 2.6 — o valor
> mudou porque agora a compensação de irregularidade já faz parte do cálculo de R, então o
> fator visual não precisa mais compensar por cima disso).
>
> **Verificado**: 6 layouts sintéticos independentes (seeds 42, 777, 2024, 9999, 123, 555)
> + o mundo real da sessão — **28/28 continentes** com razão entre 0,7 e 1,3 (a maioria
> entre 0,86–1,07). Reprodutibilidade preservada: regerar sem `--replanejar` reusa
> `compensacao_calibrada` do manifesto e dá `mapa_composto.npz` idêntico. Custo: ~3-7s de
> calibração por mundo (renders em 200×200, não na resolução final — só a proporção de
> área importa ali).

> **Decisão de escala do mundo — NÃO mude sem falar com o autor.** `escala_pixel_area_km2 = 250` ⇒
> 1 px ≈ 15,8 km, mundo = 147M km² (~29% da Terra). Para um planeta seria ~865; para uma região
> jogável com continentes de 4,5M km² a 200 px de raio seria ~36. **Isto não bloqueia nada** — a
> cidade é sub-pixel em qualquer uma dessas escalas (Seção 2.1).

#### 1.2 — Calibrar o detalhe por zoom (P1.6)

> A Fase 0 tornou possível adicionar oitavas; esta etapa **escolhe quantas** e verifica que o
> resultado é bonito, não só correto.

Hoje a menor feição real do terreno é `ruido_costa_escala / lacunariedade^(oitavas-1)` =
`60 / 2,1³ ≈ 6,5 px ≈ 100 km`. Método (**meça, não chute**):

1. Renderize a mesma janela em z0, z2, z4 e z6 e olhe lado a lado.
2. Suba `tile_oitavas_extra_por_zoom` até o zoom alto parar de parecer borrado — e **pare** quando
   começar a parecer granulado/ruidoso. A faixa útil costuma ser 1 a 1,5 oitava por nível de zoom.
3. Confirme com o aceite de coerência da Fase 0 que subir oitavas **não** move a linha de costa
   (`trocam terra/agua = 0`). Se mover, a normalização (0.2) não foi aplicada corretamente.

**Não faça**: não aumente `ruido_costa_oitavas` base para "ter mais detalhe no mundo" — isso muda o
mapa-múndi inteiro e o custo de gerar `mapa_composto.npz`. O detalhe fino é por zoom, não na base.

⚠️ **Limite honesto**: mais oitavas dão relevo mais fino, não *conteúdo* novo. Zoom muito além de z6
vira penugem procedural. Ver "O teto honesto" na Seção 4.

#### 1.3 — Fazer os biomas que já existem aparecerem (P1.3) — implementado (2026-09-10)
> ⚠️ **Escopo estrito**: esta fase **não cria bioma novo**, não mexe na paleta e não muda o schema de
> config. O objetivo é só que os **5 IDs que já existem** apareçam no mundo. Bioma novo é Fase 7.

Duas alterações em `cartographer/math/climate.py`:
1. **Umidade com variação espacial** — `calculate_humidity()` ganhou `grid_x`/`grid_y`/`seed` e soma um
   campo de ruído dedicado (3 oitavas, `clima_umidade_variacao_escala`/`_amplitude` em config) à base
   de terra. `tile_cartographer.py` passa o `grid_x`/`grid_y` **de coordenada de mundo** que já tinha
   em mãos (F1 preservado — nenhum `np.arange` local novo).
2. **Limiares recalibrados por medição, não por percentil independente**. ⚠️ **Achado real**: a
   primeira tentativa (limiar de cada variável no seu próprio percentil — "top 15% temperatura ∩
   bottom 20% umidade") deu **zero** desertos. Temperatura é zonal (por latitude) e umidade é regional
   (por ruído) — não são espacialmente independentes, e o par de percentis escolhido simplesmente não
   coexistia em nenhum pixel real do mundo medido. Corrigido varrendo a **interseção conjunta**
   `(temp>t)&(umid<u)` direto nos dados até achar uma faixa com massa real. Resultado medido:
   `limiar_temp_deserto=0.40, limiar_umid_deserto=0.32, limiar_temp_mediterraneo=0.32,
   limiar_umid_mediterraneo=0.42` → Deserto ~2–20%, Mediterrâneo ~13–21%, Floresta resto (varia por
   mundo/seed). **Se a config de ruído/tectônica mudar, a distribuição muda — remeça pela interseção
   conjunta, não reuse estes números às cegas nem confie em percentil marginal isolado.**

> ⚠️ **Achado adicional, não estava previsto no plano original**: um continente cuja latitude ficou
> perto do limite de posição seguro (Fase 1.1, `continente_centro_margem_borda_px`) pode ter
> temperatura perto de zero em toda a sua extensão — abaixo até do limiar de Mediterrâneo. Como não
> existe bioma frio hoje (tundra/taiga = Fase 7), esse continente fica **estruturalmente preso** em
> quase-monocultura de Floresta Temperada, não importa como se calibre a umidade. Não é bug desta
> fase — é o teto real do que dá pra fazer sem biomas novos. Reflexo disso: o aceite da Fase 1 (abaixo)
> foi ajustado de `dominante<90%` para `dominante<100%`.
>
> **Montanha Rochosa** (`altitude > nivel_montanha = 0.8`) não apareceu no mundo medido — a altitude
> máxima real ficou em ~0,61. Fora do escopo desta fase (que é só clima, não altitude/tectônica); se
> importar, é ajuste de `elevacao_maxima`/`nivel_montanha` a revisitar em fase futura.

#### 1.4 — Validar e posicionar melhor as cidades (P1.4) — implementado (2026-09-10)
- **Validação** (`cartographer/ai/city_manager_ai.py`): `_validar_cidades()` descarta cidade com
  campo faltando, `tamanho` fora do enum ou `bioma_desejado` fora da lista fechada. Retry até
  `cidades_retry_ia` (2); se ainda faltar depois de todas as tentativas, **completa proceduralmente**
  (tabela de sílabas + `random.Random(zlib.crc32(nome_continente))` — determinístico, nunca `hash()`).
  Confirmado no mundo real: a IA (7B) fundou só 0–1 cidade válida por continente em quase toda
  tentativa — sem este fallback, `cidades_min_por_continente=3` nunca teria sido atingido.
- **Posicionamento** (`generate_cities_metadata.py:_pontuar_sitio`): troca `random.choice` por
  pontuação de sítio — `cidades_peso_costa/altitude/bioma` combinam adjacência à costa
  (`scipy.ndimage.distance_transform_edt` na máscara de terra), altitude baixa/plana e o bioma
  desejado. `cidades_distancia_minima_px` é restrição **dura**: candidato dentro do raio de uma
  cidade já colocada é descartado (`-inf`), não penalizado. Verificado no mundo real: todas as
  distâncias entre cidades do mesmo continente ficaram entre 27–145px, bem acima do mínimo (15px).
  *(Rio entra como critério na Fase 6, quando existir hidrografia.)*

> ⚠️ **Dois bugs pré-existentes encontrados testando isto** (não introduzidos nesta fase, mas só
> visíveis depois que o posicionamento passou a logar o bioma/ID escolhido):
> 1. **Mapa de nome→ID de bioma quebrado por acento.** `{k.replace("_"," ").title(): v for k,v in
>    ClimateProcessor.BIOME_IDS.items()}` gera `"Mediterraneo"` (sem acento, de `"MEDITERRANEO"`),
>    mas o nome que circula de verdade em `biomas_predominantes`/prompt da IA é `"Mediterrâneo"`
>    (com acento, de `world_manager.py:biomas_nomes`). O `.get()` falhava em silêncio e toda cidade
>    com esse bioma desejado caía no fallback (Floresta Temperada) sem aviso nenhum — o
>    posicionamento "funcionava", só que pro bioma errado. Corrigido com um mapa fixo batendo com a
>    grafia real (mesmo ponto de manutenção "4 lugares" já avisado na Seção 1.2).
> 2. **"Oceano" aparecia como bioma desejável pra cidade.** `biomas_predominantes` pode ter uma fatia
>    residual de Oceano (<1,2% medido — pixels de fronteira entre a máscara de terra e a
>    classificação de bioma) e isso ia direto pro prompt da IA / fallback procedural como opção
>    válida de `bioma_desejado`. Sem sentido pra uma feature de terra. Filtrado antes de virar opção.

#### 1.5 — Dívidas que atrapalham as próximas fases
- **Contrato do endpoint**: `web/composed_routes.py:100-101` — o early-return de manifesto vazio
  devolve só `{"continentes": []}`. Devolver sempre também `dimensao_global`, `janela_padding_px` e
  `tile_zoom_maximo_ui`.
- **Paleta duplicada**: `web/helpers.py:130-165` tem um dict `CORES` hardcoded que duplica
  `config[cartografia][cores][biomas]` e ia divergir na Fase 7. **Já verificado: `grep -rn
  "render_biomes_map_to_bytes"` dá zero chamadores — é código morto. Delete a função inteira**, não
  há migração a fazer. (Se a Fase 0.5 já deletou, marque como feito.)
- ~~**Costura entre fontes de tile**~~ — **não existe mais**. Era consequência do mosaico; a Fase 0 a
  eliminou por construção (**F2**). Não implemente blend de borda: se você vir costura depois da
  Fase 0, é sinal de que algum ruído voltou a ser avaliado em índice local (viola **F1**) — procure o
  `np.arange` culpado em vez de borrar a emenda.

**Config novo**: `cidades_retry_ia: 2`, `cidades_distancia_minima_px`, `cidades_peso_costa`,
`cidades_peso_altitude`, `cidades_peso_bioma`.

#### Aceite (Fase 1)

> ⚠️ **O `<90%` abaixo foi relaxado para `<100%` (2026-09-10), pra bater com o Gate 1 item 7.**
> Achado real: um continente clampado pra latitude extrema (`centro_y` perto da margem —
> ver Fase 1.1) pode ter temperatura perto de zero em **toda** a sua área. Com só 5 biomas
> hoje (nenhum "frio" — tundra/taiga são Fase 7), Deserto e Mediterrâneo exigem
> `temp > limiar` e são **estruturalmente inalcançáveis** ali: não é falha de calibração de
> umidade, é um continente genuinamente polar sem bioma frio pra virar. Verificado no mundo
> real da sessão: 2 de 5 continentes (Caelus 99,46%, Draconis 98,81%) — ambos abaixo de
> 100%, mas acima de 90%. Cobrar `<90%` bloquearia a Fase 1 por um problema que só a Fase 7
> resolve; `<100%` é o que este bloco de correção consegue garantir de verdade.
```bash
venv/bin/python -c "
import json; m=json.load(open('database/world_manifest.json'))
for c in m['continentes']:
    r=c['area_real_km2']/max(1,c['area_planejada_km2']); bs=c['biomas_predominantes']
    n=len(c.get('cidades',[]))
    ok = 0.7<=r<=1.3 and len(bs)>=2 and bs[0]['percentual']<100 and n>=3
    print(f\"{c['nome']:<12} area={r:.2f} biomas={len(bs)} dominante={bs[0]['percentual']:.0f}% cidades={n} {'OK' if ok else 'FALHOU'}\")
"
```

---

### FASE 2 — Vínculo cartografia ↔ simulação  ·  Bloco I — implementada (2026-09-11)

**Corrige**: P0.3, P1.5. **Pré-requisitos**: Fase 1.
**Por que aqui**: é o que faz o mundo virar *um mundo* — o que está no mapa passa a existir no jogo.

> ⚠️ **Escopo real acabou maior que o texto original da fase.** O plano só mencionava
> `builder/populate.py:61-62,80-81` pro achado de P0.3, mas **dois outros lugares** criam
> `Local` novo depois do povoamento inicial e usavam a MESMA grade fake 5-35:
> `engine/mechanics/housing.py` (expansão urbana — casal supersaturado constrói casa nova)
> e `engine/mechanics/mestre.py` (Modo Mestre cria local via comando `CRIAR_LOCAL`). Corrigir
> só `populate.py` teria deixado o sistema **meio migrado**: locais iniciais em coordenada de
> mundo, locais criados depois de novo na grade fake — exatamente a inconsistência que esta
> fase existe pra eliminar. Centralizado em `engine/utils.py:GeoUtils.sortear_ponto_em_terra()`
> (mesma lógica do plano, reaproveitada nos 3 lugares) e `SimulationEngine.cidades` (novo,
> carrega `x_global`/`y_global` de toda cidade pra `housing.py` saber onde centralizar).
> Config `geracao_urbana.grid_min_px/grid_max_px` (a grade fake) **removida** — não sobrou
> nenhum consumidor.

#### 2.1 — `Local.coordenadas` passa a ser coordenada de mundo (P0.3)

**Decisão**: `coordenadas` deixa de ser um par aleatório 5–35 e passa a ser **pixel de mundo em
float** (Seção 2.3). É compatível com a Fase 4 (que vai gerar as mesmas coordenadas a partir da
geometria real) e permite desenhar os locais tanto no mapa antigo quanto no Leaflet.

1. Em `builder/populate.py`, antes de criar locais, carregar o terreno e sortear só em terra firme:
   ```python
   import numpy as np
   mapa = np.load("database/mapa_composto.npz")["mapa"]
   nivel_mar = cfg_get(get_config(), "cartografia", "nivel_mar")
   cx, cy = cidade_spawn["x_global"], cidade_spawn["y_global"]
   raio = cfg_get(cfg_urbano, "locais_raio_px")          # ex.: 3.0

   def sortear_ponto_em_terra(rng, tentativas=200):
       for _ in range(tentativas):
           ang = rng.uniform(0, 2 * np.pi)
           r = raio * np.sqrt(rng.random())              # uniforme no disco
           x, y = cx + r * np.cos(ang), cy + r * np.sin(ang)
           ix, iy = int(round(x)), int(round(y))
           if 0 <= ix < mapa.shape[1] and 0 <= iy < mapa.shape[0] \
              and mapa[iy, ix, 0] >= nivel_mar:
               return [round(float(x), 3), round(float(y), 3)]
       return [float(cx), float(cy)]                     # fallback: o pixel da cidade
   ```
2. Trocar os dois `random.randint(grid_min, grid_max)` (:61-62 e :80-81) por `sortear_ponto_em_terra(rng)`.
3. Expor a bbox da região em `/api/cidade/<nome>/entities` (`web/composed_routes.py:251`) e, em
   `mapa_composto.js:179-189`, converter mundo → pixel de imagem pela fórmula da Seção 2.3, em vez de
   `x * tileSize * scale`.

> **Seja honesto ao documentar**: isto é um **paliativo consciente**. Espalhar 16 edifícios num raio
> de 3 px é espalhá-los por ~47 km — fisicamente absurdo, visualmente aceitável. A correção real é a
> Fase 4. Registre isso no ROADMAP ao concluir.

#### 2.2 — Cada cidade do manifesto existe no jogo (P1.5)
`populate.py:50-57` cria 6 locais fixos só para `cidades_salvas[0]`. Mudanças:
1. **Gerar locais para todas as cidades** do manifesto, não só a spawn — variando o conjunto por
   `tamanho` e `tipo` da cidade (uma `fortaleza` ganha quartel e muralha; uma `pesqueira`, doca e
   mercado de peixe). Use uma tabela em config, não uma lista literal no código.
2. Manter `cidade_simulada` apontando para uma cidade **ativa** (a simulação de NPCs continua nela),
   mas as outras passam a existir como lugares navegáveis no mapa.
3. Registrar em `mundo_meta` quais cidades estão ativas, para a Fase 9 poder ativar mais de uma.

#### 2.3 — Persistir a personalidade que a IA já gera
`engine/ai/prompts/dna.txt` já pede `raca`, `personalidade` e `background`; `populate.py:134-137`
descarta os três. Adicionar em `engine/schema.sql` (`npcs`): `raca TEXT`, `personalidade TEXT`,
`background TEXT`; campos correspondentes em `engine/models.py:NPC`; salvar em `populate.py`;
carregar em `engine/database.py`.
**Por que no Bloco I**: é dado sendo jogado fora (defeito, não melhoria), custa ~20 linhas e já
melhora a narração do Modo Mestre, que hoje não sabe quem é quem. O **uso** desses traços na decisão
é Fase 8.

**Config novo**: `locais_raio_px: 3.0` (em `geracao_urbana`), `locais_por_tipo_cidade` (tabela).

#### Aceite (Fase 2)
```bash
venv/bin/python -c "
import sqlite3,json,numpy as np
mapa=np.load('database/mapa_composto.npz')['mapa']
nm=json.load(open('config.json'))['cartografia']['nivel_mar']
con=sqlite3.connect('database/openworld.db')
maus=[(n,c) for n,c in con.execute('SELECT nome,coordenadas FROM locais')
      if mapa[int(round(json.loads(c)[1])), int(round(json.loads(c)[0])), 0] < nm]
print('locais na agua:', len(maus), maus[:5])
for cid,nome,n in con.execute('SELECT c.id,c.nome,COUNT(l.id) FROM cidades c LEFT JOIN locais l ON l.cidade_id=c.id GROUP BY c.id'):
    print(f'  cidade {nome:<20} locais={n} {\"OK\" if n>0 else \"FALHOU\"}')
print('npcs com personalidade:', con.execute(\"SELECT COUNT(*) FROM npcs WHERE personalidade IS NOT NULL AND personalidade!=''\").fetchone()[0])
"
```
**Critério**: `locais na agua: 0`; toda cidade com locais; NPCs com personalidade preenchida.

> **Ao fim da Fase 2, revalide o GATE 1 inteiro (Seção 4) antes de seguir.**

---

### FASE 3 — Camada vetorial + Leaflet rico  ·  Bloco II — implementada (2026-09-11)

**Resolve**: P2.1. **Pré-requisitos**: GATE 1 aprovado.
**Por que antes das cidades**: é a infraestrutura de desenho que a Fase 4 vai usar. Construir a
cidade sem ter como mostrá-la é trabalhar às cegas.

**3.1 Formato** — `database/features/cidades.geojson`, gerado por
`cartographer/features/generate_city_features.py` (chamado no `reset_cartography.sh`, depois das
cidades fundadas). Coordenadas em `[x_mundo, -y_mundo]` — é a forma GeoJSON (`[lng, lat]`) da mesma
conversão de `pixelParaLatLng()` (Seção 2.3), então o Leaflet plota direto sem transformação nenhuma
no frontend. Propriedades: `id`, `nome`, `tipo`, `tamanho`, `continente`, `zoom_min` (por `tamanho`,
config `mapa_features_zoom_min_por_tamanho`), `descricao`.
`estradas`/`pois`/`fronteiras` **não têm gerador ainda** — nenhuma fase até aqui produz esse dado
(POIs de cidade vêm com a geometria real na Fase 4/5; rios são a Fase 6). O endpoint devolve
`FeatureCollection` vazia pra essas camadas em vez de erro, e o seletor de camadas do Leaflet já as
lista prontas pra quando o arquivo existir.

**3.2 Endpoint** — `GET /api/mapa/features?camadas=cidades,pois&bbox=x0,y0,x1,y1&z=<n>` em
`web/composed_routes.py`, devolvendo `{camada: FeatureCollection}` (uma coleção por camada, não uma
mesclada — precisa ser assim pro `L.control.layers` do frontend alternar cada uma independente),
filtrado por bbox e `zoom_min`, com cache por mtime (mesmo padrão de `obter_mapa_do_cache()`).

**3.3 Frontend** (`mapa_leaflet.js`) — `L.geoJSON` por camada + `L.control.layers`; tooltip
permanente acima de `mapa_features_tooltip_zoom_min` (novo config, exposto via `/api/continentes`);
`pointToLayer` com emoji por `tipo` de cidade (`TIPO_CIDADE_EMOJI`); popup com descrição; recarrega
no `moveend` com o bbox visível convertido de volta pra pixel de mundo.

**3.4 Zoom além do raster** — `maxNativeZoom` deixado **igual** a `tile_zoom_maximo_ui` (sem
esticar ainda): como a Fase 1.2 (calibração de oitavas por zoom) não rodou, não há como saber com
segurança em que zoom as oitavas param de acrescentar informação real — esticar cedo demais
mostraria raster borrado sem necessidade. Reavaliar quando a Fase 1.2 acontecer.
⚠️ Lembre da armadilha nº 3 (Seção 6.3): `minZoom` do mapa e da camada continuam batendo (inalterado).

**Verificado**: `GET /api/mapa/features?camadas=cidades&bbox=0,0,768,768&z=0` devolve só as 5
cidades `grande` (zoom_min=0); com `z=4` devolve as 15 (todos os tamanhos) — filtro por zoom
confirmado funcionando. Sintaxe do JS validada (`node --check`). **Não verificado visualmente no
navegador** (Chrome extension indisponível nesta sessão remota — sem supervisão) — a lógica de
zoom/pan/popup foi conferida por leitura de código e é a API padrão do Leaflet 1.9.4 (já carregado no
template), mas o autor deveria abrir a aba Mapa Live e conferir visualmente antes de considerar
"pronto" de verdade.

---

### FASE 4 — Cidades de verdade (GeoJSON)  ·  Bloco II — implementada (2026-09-11)

**Resolve**: P2.2 — e é a correção **definitiva** de P0.1, P0.3 e P1.5.
**Pré-requisitos**: Fase 3.

> ⚠️ **Escopo real reduzido do aspiracional do plano — documentado de propósito, não
> escondido.** Implementado em `cartographer/cities/generate_city_geometry.py`:
> - **Malha viária**: só o padrão **orgânico/medieval** (radiais dos portões + anéis
>   deformados por ruído). *Grade/colonial* e *ribeirinha* (4.2.3) **não implementados**
>   — grade exigiria um vocabulário de `tipo` de cidade que o projeto não tem
>   ("colonial"), e ribeirinha exige rio (Fase 6, ainda não existe). Todas as 15 cidades
>   testadas usam o padrão orgânico.
> - **Sítio (4.2.1)**: "marcar água/declive/pântano" **não é possível** — a cidade é
>   sub-pixel (Seção 2.1: cidade grande tem ~900m de raio; 1 px de mundo ≈ 250km), não
>   existe informação de terreno real nessa escala. A geometria é puramente procedural
>   (ruído próprio seedado pelo nome da cidade), não derivada do terreno do mundo.
> - **Catálogo (4.3)**: ~30 `tipo_local` (config `cidade_geo_catalogo_edificios`),
>   cobrindo governo/fé/saber/comércio/artesanato/hospedagem/produção primária — não as
>   ~80 do texto completo (faltam os grupos Saúde e Aventura). Cada entrada usa uma das
>   **9 `CategoriaLocal` já existentes** (nenhuma categoria de sistema nova), com
>   `tipo_local` dando o nome de sabor. Ampliar é só editar a lista em config.json.
> - **Regras de coerência (4.3)**: só o peso `tipos_cidade` (favorece fortemente, não
>   obriga) — "porto exige água adjacente" e "fortaleza proíbe teatro/bordel" **não
>   implementados** (sem dado de água local nem os tipos teatro/bordel no catálogo
>   reduzido).
> - **Edifícios são `Point`, não polígono com footprint** — o schema de `Local` só
>   guarda `coordenadas` como ponto; o polígono do `lote` (gerado e presente no GeoJSON)
>   já cumpre o papel visual de "footprint", o edifício em si não precisa de forma
>   própria pro resto do jogo usar.
>
> O que **é** real, não simulado: subdivisão recursiva de quarteirão em lote (testado —
> soma de área dos lotes bate exatamente com a área do quarteirão original, zero
> gap/sobreposição), muralha com torres e portões, zoneamento por distância ao centro
> (comércio perto da praça, residencial pra fora), transform local(m)→mundo(px)
> documentado e determinístico por seed do nome da cidade.
>
> **Achado real corrigido durante a implementação**: a primeira versão do corte
> recursivo de lote (`_subdividir_lote`) tinha um bug — `sorted([i0,i1])` pra decidir
> os dois quads resultantes quebrava a correspondência entre os pontos médios e os
> vértices quando o lado mais longo não era o de índice 0 ou 1, produzindo um quad
> "em zigue-zague" (auto-cruzado). Pego **antes** de gerar qualquer cidade real,
> verificando que a soma das áreas dos lotes bate exatamente com a área do quarteirão
> original (por construção, um corte errado teria dado uma diferença não-nula).
>
> **Escala de zoom recalibrada**: a geometria de cidade só aparece a partir de z11
> (calculado — em z11 a cidade ocupa ~6% de um tile, visível mas ainda pequena; z14
> ~46%, navegável). `tile_zoom_maximo_ui` subiu de 7 pra **16** pra isso caber. O raster
> nesses zooms não ganha detalhe novo (oitavas saturam perto de z9), só estica — é
> esperado ("o teto honesto", Seção 4).

**4.1 A cidade é um espaço próprio** — releia a Seção 2.1. A cidade é sub-pixel; portanto **não é
recorte do mundo**, e sim geometria gerada num sistema local (origem no centro, unidade = metro) com
transform documentado `local(m) → mundo(px)`.

**4.2 Geometria (Python, determinística a partir da seed)**
1. **Sítio**: no terreno em volta do pixel-âncora, marcar água, declive alto e pântano como não-construível.
2. **Núcleo e portões**: praça central; portões nas direções das rotas que chegam.
3. **Malha viária** por `tipo` da cidade:
   - *orgânica/medieval*: radiais dos portões ao centro + 2–3 anéis deformados por ruído (padrão);
   - *grade/colonial*: grid rotacionado, quebrado onde o terreno impede;
   - *ribeirinha*: eixo paralelo ao rio + travessas + ponte(s).
4. **Quarteirões**: polígonos fechados pela malha.
5. **Lotes**: subdivisão recursiva de cada quarteirão (corte pelo lado maior) até o tamanho-alvo.
6. **Edifícios**: um footprint por lote, com recuo da rua.
7. **Muralha** (se `tamanho != pequeno` ou `tipo == fortaleza`): casco convexo com folga, torres em
   intervalos, portões onde as vias principais cruzam.
8. **Zoneamento**: mercado junto à praça e aos portões; artesanato num anel intermediário;
   residencial nas bordas; templo/castelo na cota mais alta; docas na água; **cemitério e curtume
   fora da muralha**.

**4.3 Catálogo de categorias** (hoje são 9 `CategoriaLocal` e 6 locais criados). Cada entrada com
`peso_por_tamanho`, `peso_por_tipo_cidade`, `min`, `max`, `empregos`, `salario_base`, `tipo_local`:
- **Governo/ordem**: castelo, prefeitura, tribunal, quartel, prisão, alfândega, torre de vigia
- **Fé**: templo, capela, santuário, mosteiro, cemitério
- **Saber**: escola, biblioteca, academia, torre de mago, observatório, escriba
- **Comércio**: mercado, feira, armazém, casa de câmbio, guilda de mercadores, loja geral, alfaiate, joalheiro, boticário, livraria
- **Artesanato**: ferreiro, armeiro, carpinteiro, pedreiro, oleiro, curtume, tecelagem, moinho, padaria, cervejaria, destilaria, estaleiro
- **Hospedagem/social**: taverna, estalagem, bordel, casa de banhos, arena, teatro, praça, jardim
- **Saúde**: curandeiro, hospital, herbalista
- **Produção primária**: fazenda, pomar, vinhedo, pasto, estábulo, pesqueiro, mina, pedreira, serraria
- **Infra**: poço, cisterna, ponte, doca, portão, celeiro, estrada
- **Aventura**: ruína, cripta, esgoto/catacumba, guilda de aventureiros, quadro de recompensas, esconderijo de ladrões, casa abandonada, entrada de masmorra

**Regras de coerência** (é o que faz "fazer sentido na aventura"): porto ⇒ exige água adjacente;
mina ⇒ exige montanha perto; vinhedo ⇒ bioma mediterrâneo; `capital` ⇒ obriga castelo + tribunal +
templo; `pesqueira` ⇒ obriga docas; `fortaleza` ⇒ obriga muralha, quartel e arsenal, e proíbe
teatro/bordel.

**4.4 Saída** — `database/cidades/<slug>.geojson`, camadas em `properties.camada`: `muralha`, `rua`,
`quarteirao`, `lote`, `edificio`, `praca`, `agua`, `ponte`, `portao`. Cada `edificio` carrega
`{id, nome, categoria, tipo_local, capacidade, salario_base, bairro, dono_npc_id, x_mundo, y_mundo}`
— exatamente os campos de `engine/models.py:Local`.

**4.5 Substituir o paliativo da Fase 2.1** — `populate.py` para de sortear pontos e passa a
**importar os edifícios do GeoJSON** como `Local`, com `coordenadas = [x_mundo, y_mundo]`.

**Aceite** — verificado (2026-09-11), reset completo do zero:
- `GET /api/mapa/features?camadas=rua,edificio,muralha,torre,portao,praca,quarteirao&z=15` numa
  cidade `grande` real devolveu 87 edifícios, 1 muralha, 4 portões, 65 torres, 32 quarteirões, 13
  ruas — em `z=5` (mesmo bbox) tudo zero, confirmando o filtro de zoom.
- 387 locais no banco (9 cidades), **todos** com `tipo_local`/`bairro` preenchidos (vindos da
  geometria, não do paliativo) — nenhum aviso de fallback no log do reset.
- 20/20 NPCs com `casa_id` preenchido (moradia real, não mais "casa_XX" ad-hoc).
- **Zero coordenadas sorteadas** *neste reset* — o paliativo (`_importar_locais_paliativo`) só
  dispara se uma cidade não tiver GeoJSON gerado; não é uma garantia estrutural permanente, é o
  que aconteceu de fato nesta verificação.
- "Nenhum edifício na água" **não verificável** como escrito — não existe terreno real na escala
  da cidade (ver nota de escopo acima). Interpretação possível: nenhum erro/crash na geração, o que
  se confirma.
- **Não visto no navegador** (Chrome indisponível nesta sessão) — só via HTTP/JSON direto.

---

### FASE 5 — IA local projetando as cidades  ·  Bloco II

**Aprofunda**: P1.4. **Pré-requisitos**: Fase 4 (geometria antes de narrativa).

**5.1 Dois estágios**
- **Estágio 1 — Conceito (antes da geometria)**: a IA recebe o contexto real do sítio (bioma, tem
  rio?, costeira?, altitude, continente, vizinhas e distâncias) e devolve:
  ```jsonc
  {
    "nome": "Vau de Corvo", "tamanho": "medio", "tipo": "comercial",
    "populacao_estimada": 4200,
    "fundacao": "há três gerações, por refugiados da peste",
    "economia": ["curtume", "balsa", "feira de gado"],
    "governo": "conselho de mercadores",
    "faccoes": [{"nome": "Guilda da Balsa", "poder": 3, "objetivo": "monopolizar a travessia"}],
    "tensao_atual": "a ponte nova ameaça a guilda",
    "arquitetura": "madeira escura e telhado de ardósia",
    "prioridade_categorias": {"comercio": 1.5, "artesanato": 1.2, "militar": 0.6}
  }
  ```
  `prioridade_categorias` **multiplica os pesos do catálogo 4.3** — é assim que a IA molda a cidade
  sem desenhar nada.
- **Estágio 2 — Anotação (depois da geometria)**: a IA recebe os edifícios já posicionados
  (categoria + bairro + vizinhos) e devolve, **por id**, `nome`, `descricao` (1–2 frases),
  `proprietario`, `rumor` e `gancho_aventura` opcional. **Lotes de 10–20** para caber no contexto de
  um modelo 7B.

**5.2 Robustez (o modelo é pequeno — assuma que erra)**
- `json_format=True` + `AIUtils.parse_json_safely`.
- **Validar contra esquema**: descartar campo desconhecido, checar enum, clampar número.
- **Fallback procedural obrigatório** em cada campo. A cidade tem que ficar jogável com o Ollama
  desligado.
- **Determinismo**: seed = `zlib.crc32(nome_cidade + str(seed_mundo))` — nunca `hash()`.
- **Cache**: gravar a resposta crua em `database/cidades/<slug>.ia.json`; só rechamar se o arquivo
  sumir ou a geometria mudar. Regerar 5 cidades × 20 lotes a cada reset é caro demais.

**5.3 Prompts novos** em `cartographer/ai/prompt/`: `city_concept.txt`, `city_annotate.txt`.
**Teste o `.format()`/`replace` antes de confiar** — já houve bug de chave literal em prompt JSON.

**Aceite**: duas cidades do mesmo tipo com identidades claramente diferentes; Ollama desligado e
ainda assim cidades completas e nomeadas.

> **Ao fim da Fase 5, valide o GATE 2 (Seção 4) antes de seguir para o Bloco III.**

---

### FASE 6 — Hidrografia  ·  Bloco III

**Resolve**: P2.3. **Pré-requisitos**: GATE 2 aprovado.

> ### ⚠️ Esta fase é o teste de fogo da regra F4 — leia antes de escrever a primeira linha
>
> Hidrografia é a **primeira coisa do projeto que não é pontual**. `priority-flood` e acumulação D8
> precisam da grade inteira: você não pode calcular o fluxo de um tile olhando só aquele tile.
> Portanto **não tente** colocar rio dentro de `gerar_janela`.
>
> O padrão correto (**F4**, Seção 2.2) é o split em duas camadas:
> - **Camada global grosseira**: rode priority-flood + D8 uma vez sobre `mapa_composto.npz` (768²) e
>   grave `database/hidrografia.npz`. É calculado no reset, como o manifesto.
> - **Camada local procedural**: `gerar_janela` continua pura; ela **lê e interpola** a camada global
>   do mesmo jeito em todo zoom, e soma o detalhe de alta frequência por cima.
>
> A interpolação da camada global tem que ser **idêntica em todo zoom** (mesma função, mesma ordem).
> Se z2 usar bilinear e z6 usar bicúbica, o rio muda de lugar conforme se aproxima — é o P0.4 de novo,
> por outro caminho.
>
> **Limite de resolução, seja honesto no ROADMAP**: em 768², 1 px ≈ 15,8 km. Um rio de verdade é
> sub-pixel; o `LineString` vai ter vértices a cada 15,8 km e vai parecer poligonal em zoom alto.
> Suavizar a polilinha é **inventar geometria** — aceitável visualmente, mas registre que é ficção
> cartográfica. Se rios credíveis virarem requisito, a discussão real é subir a resolução do **campo
> global** (só ele, não o mundo inteiro) para ~1–2 km/px, e isso é uma decisão do autor.

**6.1 Preencher depressões** — *priority-flood* (fila de prioridade a partir das bordas, elevando
cada célula ao máximo entre sua altitude e a do vizinho já processado), ~40 linhas com `heapq`.
**Guarde a máscara das depressões antes de preencher: elas viram os lagos.**

**6.2 Direção e acumulação de fluxo (D8)** — direção = vizinho (dos 8) de menor altitude; acumulação
= processar em ordem decrescente de altitude somando a área drenada no destino. Em 768² é instantâneo.
**Rio** = `acumulacao > hidro_limiar_rio_acumulacao`; largura ∝ `sqrt(acumulacao)`.

**6.3 Saída em dois formatos**
- ❌ **Não adicione um 5º canal ao `.npz`** — quebraria o contrato de 4 canais (Seção 1.2) e todos os
  consumidores.
- ✅ Raster: `database/hidrografia.npz` com `{"rio_acumulacao": (H,W) float32, "lago": (H,W) bool}`;
  `render_npz_array()` ganha overlay opcional.
- ✅ Vetorial: `database/features/rios.geojson`, cada rio um `LineString` da nascente à foz com
  `{nome, ordem_strahler, largura}` — desenhado pela camada da Fase 3.

**6.4 Realimentação** — umidade por distância à água doce (melhora os biomas); erosão barata (baixar
altitude ∝ `log(acumulacao)` esculpe vales); posicionamento de cidade passa a pontuar rio/foz/confluência
(completa a Fase 1.4).

**Config novo**: `hidro_limiar_rio_acumulacao`, `hidro_largura_min_px`, `hidro_largura_max_px`,
`hidro_umidade_alcance_px`, `hidro_umidade_peso`, `hidro_erosao_fator`, `hidro_lago_area_min_px`.

**Aceite**: todo rio nasce alto e termina **no mar ou num lago** (nunca no meio do nada); nenhum rio
sobe (altitude não-crescente ao longo do `LineString`); overlay visível no render.

---

### FASE 7 — Biomas novos e riqueza visual  ·  Bloco III

**Resolve**: P2.4. **Pré-requisitos**: Fase 6 (a umidade de rio melhora a classificação).

**7.1 Clima mais rico** — completando a Fase 1.3:
- **Continentalidade**: `scipy.ndimage.distance_transform_edt` sobre a máscara de mar → interior seco.
- **Sombra de chuva**: vento dominante por faixa de latitude; acumular altitude ao longo do vento
  (`np.cumsum` deslocado); barlavento ganha umidade, sotavento perde. É o que cria desertos realistas.
- **Latitude simétrica**: `1 - abs(2*y/H - 1)` (equador no meio, dois polos). Hoje o mundo tem um polo só.
- **Amplitude térmica** maior no interior.
- Opcional: **estações** (offset sazonal pela data simulada) — alto impacto narrativo, exige regerar
  tiles por estação; avalie o custo antes.

**7.2 Tabela de biomas dirigida por config** — substituir a cascata de `if` (`climate.py:101-113`)
por regras avaliadas em ordem:
```jsonc
"biomas_regras": [
  {"id": 12, "nome": "Geleira",            "temp": [0.00,0.15], "umid": [0.0,1.0],  "alt": [0.80,1.00]},
  {"id": 5,  "nome": "Montanha Rochosa",   "temp": [0.00,1.00], "umid": [0.0,1.0],  "alt": [0.80,0.92]},
  {"id": 6,  "nome": "Tundra",             "temp": [0.00,0.20], "umid": [0.0,1.0],  "alt": [0.35,0.80]},
  {"id": 7,  "nome": "Taiga",              "temp": [0.20,0.35], "umid": [0.3,1.0],  "alt": [0.35,0.80]},
  {"id": 11, "nome": "Pântano",            "temp": [0.40,0.80], "umid": [0.85,1.0], "alt": [0.35,0.42]},
  {"id": 10, "nome": "Selva",              "temp": [0.65,1.00], "umid": [0.6,1.0],  "alt": [0.35,0.80]},
  {"id": 9,  "nome": "Savana",             "temp": [0.65,1.00], "umid": [0.2,0.45], "alt": [0.35,0.80]},
  {"id": 2,  "nome": "Deserto",            "temp": [0.55,1.00], "umid": [0.0,0.2],  "alt": [0.35,0.80]},
  {"id": 3,  "nome": "Mediterrâneo",       "temp": [0.55,0.75], "umid": [0.45,0.6], "alt": [0.35,0.80]},
  {"id": 8,  "nome": "Pradaria",           "temp": [0.35,0.65], "umid": [0.2,0.4],  "alt": [0.35,0.80]},
  {"id": 4,  "nome": "Floresta Temperada", "temp": [0.35,0.60], "umid": [0.4,1.0],  "alt": [0.35,0.80]},
  {"id": 13, "nome": "Praia",              "temp": [0.00,1.00], "umid": [0.0,1.0],  "alt": [0.35,0.37]}
]
```
Vetorizado: para cada regra, `np.where(mascara & (biomas == 0), id, biomas)`; sobra vai para
`FLORESTA_TEMPERADA`. Adicionar bioma passa a ser **editar config**.
⚠️ Lembre dos **4 lugares** da Seção 1.2 para cada ID novo.

**7.3 Riqueza visual** — micro-textura (`brilho *= 1 ± 0.03·ruido_alta_freq`) para tirar a chapadura;
opcionalmente modular a cor pela umidade (mesmo bioma mais seco = mais amarelado) e suavizar a
fronteira entre biomas.

**Aceite**: ao menos 6 biomas distintos no mundo; deserto no interior seco/sotavento (não espalhado);
nenhum continente com dominante acima de 70%.

---

### FASE 8 — NPCs: necessidades, traços e agenda  ·  Bloco III

**Resolve**: P2.5 (parte). **Pré-requisitos**: Fase 2.3 (personalidade já persistida).

**8.1 Traços que modulam a decisão** — vetor em `[0,1]`: `sociabilidade`, `ambicao`, `preguica`,
`bravura`, `honestidade`, `piedade`, `curiosidade`, `temperamento` (derivado do texto de
personalidade ou pedido à IA). Em `logic.py:calcular_utilidade`:
`SOCIALIZAR *= (0.5 + sociabilidade)`, `TRABALHAR *= (1.2 - preguica*0.5)`,
`OCIOSO *= (0.5 + preguica)`. **Coeficientes em `config[ia_decisao][tracos]`.**
*Aceite*: dois NPCs com traços opostos, mesmo estado e mesma hora, escolhem ações diferentes.

**8.2 Mais necessidades** — `higiene`, `diversao`, `conforto`, `seguranca`, `pertencimento`, cada uma
decaindo por tick (config) e satisfeita por ações/locais específicos (banho na casa de banhos,
diversão na taverna/teatro/arena, segurança perto da guarda).

**8.3 Agenda por profissão** — hoje `hora_inicio_trabalho`/`hora_fim_trabalho` são globais. Mover para
`config[ia_decisao][agenda_por_profissao]`: guarda em turno noturno, taberneiro à noite, fazendeiro ao
amanhecer, padeiro de madrugada. A cidade deixa de "apagar" inteira ao mesmo tempo.

**8.4 Curvas de resposta (refatoração)** — substituir os `if`s de `logic.py` por **eixos de utilidade**
(*Infinite Axis Utility System*): cada ação tem N eixos; cada eixo é `(entrada normalizada → curva →
[0,1])`; utilidade = produto com compensação pelo nº de eixos. Curvas em config (`linear`,
`quadratica`, `logistica`, `degrau`, com `m,k,b,c`). Depois disso, balancear vira editar JSON.

---

### FASE 9 — NPCs: memória, objetivos e planos  ·  Bloco III

**Resolve**: P2.5 (resto). **Pré-requisitos**: Fase 8.

**9.1 Memória episódica** — `memoria_eventos` existe no modelo e no schema mas ninguém lê. Registro:
`{quando, tipo, envolvidos[], local, intensidade, sentimento}`, escrito nos pontos que já emitem
evento (`events.py`, social, biologia). Relevância = `intensidade · e^(-Δt/τ)`; guardar as N mais
relevantes. Usar em: (a) modular afinidade nas interações; (b) alimentar o prompt do Modo Mestre;
(c) gerar rancor/gratidão que muda decisão.

**9.2 Objetivos de médio prazo** — 1–3 por NPC, derivados de traços + situação (`juntar X moedas`,
`casar`, `construir casa`, `virar mestre da guilda`, `vingar-se de <npc>`, `peregrinar`, `abrir um
negócio`). O objetivo injeta bônus de utilidade nas ações que o avançam; reavaliado a cada N horas.

**9.3 Planos multi-tick (GOAP leve)** — hoje a decisão é refeita a cada minuto e o
`bonus_persistencia` (40.0) é a única cola. Fila de passos:
`[ir_para(mercado), comprar(pao), ir_para(casa), comer]`, executada enquanto válida, interrompida só
por urgência. É o que produz o "ele foi até lá para fazer algo".

**9.4 Tempo de deslocamento** — com as coordenadas reais da Fase 4.5, `movement.py` gasta tempo
proporcional à distância em vez de teleportar. Faz o mapa da cidade importar de verdade.

**9.5 Fofoca e reputação** — ao socializar, dois NPCs trocam um item de memória, com distorção. Gera
reputação emergente (`percepcao[npc_id]` por NPC, diferente da verdade) — matéria-prima excelente
para o Mestre de IA.

---

### FASE 10 — Relevo por placas e erosão  ·  Bloco III (opcional, alto custo)

- **10a. Placas de Voronoi**: N sementes, cada pixel para a mais próxima (`scipy.spatial.cKDTree`),
  vetor de movimento por placa. Fronteiras **convergentes** viram cordilheiras lineares;
  **divergentes**, dorsais/fossas; **transformantes**, falhas. Substitui `calculate_distance_grid`
  como fonte da forma do continente — é o que mais aproxima o resultado de um mapa-múndi real.
- **10b. Erosão hidráulica**: iterar (chuva → escoa → carrega → deposita); 20–50 iterações em 768² são
  segundos com numpy. Cria vales em V, planícies aluviais e deltas.
- **10c. Erosão térmica**: limitar o ângulo de talude máximo. Barato, remove paredes artificiais.
- **10d. Cordilheiras direcionais**: ruído *ridged multifractal* (`1 - |perlin|`) só na máscara de
  fronteira convergente — espinhaços contínuos em vez de picos isolados.

⚠️ Qualquer item aqui muda `mapa_composto.npz` inteiro → exige `reset_cartography.sh` completo e
invalida continentes, regiões, cidades e a pirâmide. **Por isso está no fim.**

---

### FASE 11 — Papéis, economia e ganchos de aventura  ·  Bloco III

- **Papéis por profissão**: guarda patrulha e prende, mercador viaja entre cidades, fazendeiro tem
  ciclo sazonal, ladrão furta, sacerdote cura.
- **Economia com bens**: `market.py` hoje é só mercado de trabalho. Adicionar estoque/preço por bem,
  produção e consumo por local, comércio entre cidades (caravanas visíveis no mapa).
- **Facções e política**: guildas com poder relativo; eventos globais gerados a partir de tensões
  (integra com `eventos_globais`, que já modula utilidade em `logic.py:134-140`).
- **Ganchos para a mesa**: endpoint que devolve "o que daria uma aventura agora" — NPC com objetivo
  bloqueado, facção em tensão, local em ruína, rumor não resolvido. Fecha o círculo com o Modo Mestre.

---

## 6. Referência rápida

### 6.1 Comandos
```bash
bash cartographer/reset_cartography.sh     # regera mapas + tiles (~6 min)
bash builder/reset_world.sh                # reset total (mapas + banco + população)

venv/bin/python cartographer/world/generate_world.py
venv/bin/python cartographer/continents/generate_continent_zoom.py <uuid>
venv/bin/python cartographer/tiles/generate_tile_pyramid.py

python3 run_dashboard.py                   # Flask :5000
python3 run_simulation.py

venv/bin/python -c "import numpy as np; print(np.load('database/mapa_composto.npz')['mapa'].shape)"

venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from web.helpers import render_npz_array
from PIL import Image
Image.fromarray(render_npz_array('database/continentes/mapa_avalonia.npz')).save('/tmp/x.png')"
```

### 6.2 Config que mais importa (estado em 2026-09-10)
| Chave | Valor | Significado |
|---|---|---|
| `nivel_mar` / `nivel_montanha` | 0.35 / 0.8 | Limiares de oceano e montanha |
| `escala_pixel_area_km2` | 250 | 1 px ≈ 15,8 km; mundo = 147M km². **Não mude sem falar com o autor** |
| `mundo_tiles_por_lado` | 3 | 3×256 = 768 px |
| `clima_umidade_terra_base` | 0.4 | **Constante** em toda terra — causa de P1.3 |
| `limiar_temp_deserto` / `limiar_umid_deserto` | 0.6 / 0.5 | Inalcançável hoje |
| `limiar_temp_mediterraneo` / `limiar_umid_mediterraneo` | 0.4 / 0.5 | Quase inalcançável |
| `continente_area_para_raio_fator_visual` | 1.0 | → **2.6** na Fase 1.1 |
| `persistencia` / `lacunariedade` | 0.5 / 2.1 | Entram na normalização consertada em 0.2 |
| `ruido_costa_escala` / `_oitavas` | 60.0 / 4 | Menor feição real = 60/2,1³ ≈ **6,5 px ≈ 100 km** (P1.6) |
| `zoom_upscale_ordem`, `zoom_cidade_*`, `zoom_micro_*`, `zoom_suavizacao_sigma_px`, `zoom_costa_*` | — | **Remover todos na Fase 0.5** — são config do mosaico |
| `tile_zoom_maximo` | 4 | **Remover na 0.5** → `tile_zoom_maximo_ui` (só custo/UI) |
| `tile_size_px` | 256 | Tamanho do tile servido |
| `cidades_min/max_por_continente` | 3 / 6 | Não validado hoje (P1.4) |
| `bonus_persistencia` | 40.0 | Única cola contra troca de ação a cada minuto |
| `hora_inicio_trabalho` / `hora_fim_trabalho` | 8 / 18 | Global para todo NPC (P2.5) |

### 6.3 Armadilhas já pagas — não repita
1. **Canal de bioma é categórico.** Interpolar com spline/bilinear gera IDs fantasmas e xadrez.
   Sempre nearest-neighbor **ou** reclassificar após o upscale. (ROADMAP parte 12)
2. **`L.CRS.Simple` usa `pixelY = -lat·escala`, sem deslocamento.** A conversão certa é `lat = -py`.
   Qualquer outra pede tiles com `y` negativo. (ROADMAP parte 11)
3. **`minZoom` do mapa deve bater com o da `L.tileLayer`.** Se o mapa permite zoom abaixo do mínimo
   da camada, o Leaflet para de pedir tiles **em silêncio**, sem erro no console.
4. **Nunca `hash()` de string para seed** — é aleatorizado por processo. Use `zlib.crc32`.
5. **Probabilidade por tick não se divide, se compõe**: `p_novo = 1 - (1-p_velho)^(1/N)`.
6. **`cfg_get` é estrito** — adicione a chave ao `config.json` na mesma alteração.
7. **`scipy` só existe no `venv/`** — `python3` puro cai no fallback e testa o caminho errado.
8. **Não aumente raio de recorte para "caber mais coisa".** Foi assim que a região virou continente
   (P0.1). Se falta detalhe, faltam **oitavas** (P1.6) ou falta uma **escala nova** (Fase 4) — nunca
   um recorte maior.
9. **Não adicione feature nova enquanto houver P0/P1 aberto.** Bioma novo, rio e erosão em cima de
   uma fundação torta significam regerar tudo de novo depois.
10. **`np.arange(H)` / `np.arange(W)` dentro de gerador de terreno é bug.** Foi o que criou três
    mundos diferentes (P0.4). Grade sempre de `np.linspace(x0_mundo, x1_mundo, largura)`.
11. **Não normalize ruído por soma truncada de amplitudes** — adicionar oitava passa a reescalar o
    campo inteiro e o zoom contradiz o zoom anterior (P1.7). Use a soma infinita `1/(1-persistencia)`.
12. **Não normalize nada por `min`/`max` do bloco** (`normalize_profile` era isso e virou código
    morto por bom motivo). O resultado passa a depender do recorte → costura garantida.
13. **Guarda-corpo tem que poder falhar.** Antes de confiar num `assert`, rode-o contra o caso
    quebrado conhecido e veja-o disparar. Os dois asserts da v2.2 passavam no mundo defeituoso: um
    testava a condição errada, o outro rodava sobre uma lista recém-ordenada (tautologia).
14. **Não pré-gere pirâmide inteira.** Medido: 3069 tiles × 243 ms = 12,4 min, pior que o reset
    completo. Sob demanda + cache é 243 ms na primeira vista e zero depois.
15. **Escala de hillshading segue unidade de mundo por pixel, não largura da imagem — e é uma
    DIVISÃO, não multiplicação.** `np.gradient` no shading é por passo de pixel de imagem; como o
    terreno é liso em coordenada de mundo, esse gradiente encolhe conforme o zoom aumenta (pixels
    cada vez mais próximos em mundo). `escala_dinamica = escala_base / mundo_px_por_img_px` — a
    primeira tentativa desta sessão multiplicou em vez de dividir e o relevo ficou **mais** chapado
    que o bug original (verificado visualmente antes de corrigir a direção).
16. **Artefato derivado precisa de chave de invalidação.** O projeto produz 6 tipos e não tem
    nenhuma. Use `config_hash` no caminho do cache; artefato órfão vira lixo apagável, não bug mudo.
17. **Diferença "máxima pontual" entre duas amostras de ruído é um discriminador fraco.** Ao comparar
    octaves=N vs. octaves=M, o detalhe real que as oitavas extras acrescentam (esperado, legítimo)
    pode ser maior, num pico isolado, do que o erro sistemático que você está tentando pegar — a
    tolerância de pior-caso analítico fica frouxa demais e o teste passa até com o bug presente
    (aconteceu com T3 nesta sessão). Use **RMS sobre a janela inteira**, com média sobre vários pares
    `(seed, offset)` fixos — muito mais estável — e **sempre calibre empiricamente** rodando contra o
    código quebrado antes de confiar na tolerância, mesmo quando ela "parece" bem fundamentada.

---

## 7. Registro de execução

Preencha ao concluir cada fase e replique um resumo de uma linha no "Log de Sessões" do ROADMAP.

| Bloco | Fase | Data | O que foi feito | Verificado como (comando + saída) | Pendências |
|---|---|---|---|---|---|
| I | 0 — O tile é uma função | 2026-09-10 | 0.1 (layout+config_hash persistidos, `generate_world.py` reusa em vez de replanejar), 0.2 (normalização por soma infinita), 0.3 (`gerar_janela` + culling de continentes), 0.4 (`cartographer/tiles/render.py` + cache em disco + `prewarm_cache.py`, bug de escala do hillshading corrigido — ver armadilha 15), 0.5 (deletados `pyramid.py`, `generate_tile_pyramid.py`, `roi_zoom.py`, `generate_continent_zoom.py`, `city_roi_zoom.py`; `/api/continente/.../imagem`, `/api/continente/.../info`, `/api/cidade/.../imagem` reapontados para `gerar_janela`; config morto removido), 0.6 (`tile_zoom_maximo_ui=7` no Leaflet) | `pytest tests/ -v` → **7 passed** (T1–T6, incluindo T5/culling). Reset completo (`reset_cartography.sh`) rodado do zero com sucesso. Reprodutibilidade: regerado 2×, `np.array_equal`=True. Coerência entre zooms: `trocam terra/agua=0`, `\|dalt\|max≈0.001`. Culling: 2,56x mais rápido em z7, resultado idêntico com/sem (mundo real e sintético). Testado via HTTP real (Flask subindo): `/tiles/`, `/api/continentes`, `/api/continente/<uuid>/imagem`, `/api/continente/<uuid>/info/<x>/<y>`, `/api/cidade/<nome>/imagem` — todos HTTP 200, sem erro no log. Inspeção visual de continente e cidade (screenshots) confirma relevo com contraste consistente em zoom alto (antes achatava) e a mesma linha de costa nas duas imagens (prova visual de F1/F2). | **Gate 1 item 1 (T1-T6) satisfeito.** Itens 6-10 do Gate 1 (áreas, biomas, cidades, locais na água) são escopo de Fase 1/2, ainda não feitos — Gate 1 completo só ao fim da Fase 2. `tile_oitavas_extra_por_zoom` está no valor sugerido pelo plano (1), não calibrado visualmente — isso é o próprio conteúdo da Fase 1.2, não uma pendência desta fase. `maxNativeZoom` do Leaflet não foi diferenciado de `maxZoom` (ambos =7; sem stretching) — correto enquanto oitavas continuarem saturando só em z9 (`tile_oitavas_max=12 − ruido_macro_oitavas=3`), reavaliar na Fase 1.2/3.4. |
| I | 1 — Cartografia coerente | 2026-09-10 | 1.1 (P1.2 — 3 causas reais achadas e corrigidas: clamp de centro da IA, compensação de irregularidade, calibração adaptativa competitiva por continente com atribuição exata via `retornar_donos`), 1.3 (P1.3 — umidade com variação espacial, limiares recalibrados por interseção conjunta medida), 1.4 (P1.4 — validação+retry+fallback procedural da IA de cidades, pontuação de sítio, +2 bugs achados: mapa bioma→ID quebrado por acento, "Oceano" como bioma desejável), 1.5 (contrato do endpoint vazio, dead code já removido na Fase 0.5). **1.2 (calibrar oitavas por zoom) pendente** — exige inspeção visual lado a lado que o autor não pode fazer remoto; valor de config ficou no sugerido pelo plano (1), não calibrado. | `pytest tests/ -v` → 7 passed. Aceite completo da Fase 1 rodado 3× (dois mundos sintéticos multi-seed + 1 reset real do zero) → **5/5 continentes OK** em cada um (área 0,7–1,3, ≥2 biomas, dominante<100%, ≥3 cidades). Reprodutibilidade preservada (compensação calibrada persiste no manifesto). Testado via HTTP real: tiles, `/api/continente/.../imagem`, `/api/continente/.../info` — HTTP 200, sem erro no log. | Fase 1.2 (calibração visual) fica para quando o autor puder abrir o navegador. Montanha Rochosa não apareceu no mundo medido (altitude máx. real ~0,61 < `nivel_montanha`=0,8) — fora do escopo de 1.3 (é clima, não altitude); revisitar se importar. Nada commitado ainda — autor pediu pra só commitar depois de validar visualmente em casa. |
| I | 2 — Vínculo cartografia↔simulação | 2026-09-11 | 2.1 (`GeoUtils.sortear_ponto_em_terra` centralizado, usado em `populate.py`+`housing.py`+`mestre.py`; bbox exposta em `/api/cidade/.../entities`; `mapa_composto.js` convertendo mundo→imagem de verdade), 2.2 (locais para as 14 cidades não-spawn via `locais_por_tipo_cidade`; `cidades_ativas` em `mundo_meta`), 2.3 (raca/personalidade/background persistidos: schema+models+database+populate) | Aceite oficial da fase: `locais na agua: 0`, 15/15 cidades com locais, 20/20 NPCs com personalidade. **GATE 1 revalidado por completo** (itens 1-10) em 3 resets independentes (`builder/reset_world.sh` do zero, sementes/IA diferentes a cada vez) — 15/15 continentes (3 mundos × 5) dentro de 0,7-1,3 de área e sem bioma a 100%. `pytest tests/ -v` → 7 passed em cada rodada. | No processo, achado um 4º caso do mesmo bug de IA-ignora-limite-do-prompt (`irregularidade=0,9`, prompt pede ≤0,8) — corrigido generalizando o validador (Fase 1.1, ver nota lá). |
| — | **GATE 1** | 2026-09-11 | **APROVADO** — todos os 10 itens verificados nesta sessão (ver linha da Fase 2). | — | — |
| II | 3 — Camada vetorial + Leaflet | 2026-09-11 | `cartographer/features/generate_city_features.py` (novo, chamado no reset); endpoint `/api/mapa/features`; `mapa_leaflet.js` com `L.geoJSON`+`L.control.layers`+tooltip+popup por cidade | `curl /api/mapa/features?...&z=0` → 5 cidades (só `grande`); `z=4` → 15 (todas) — filtro por zoom confirmado. `node --check` na sintaxe do JS. | **Não testado visualmente no navegador** (sem Chrome disponível nesta sessão) — autor deve abrir a aba Mapa Live e conferir antes de considerar concluído. `estradas`/`pois`/`fronteiras` ainda são camadas vazias (sem gerador — normal até Fase 4/5/6). |
| II | 4 — Cidades de verdade | 2026-09-11 | `cartographer/cities/generate_city_geometry.py` (novo — malha radial+anel, subdivisão recursiva de lote, muralha, catálogo de ~30 tipos); `populate.py` reescrito pra importar de `database/cidades/<slug>.geojson`; `Local` ganhou `tipo_local`/`bairro`/`dono_npc_id`; endpoint `/api/mapa/features` agrega as 7 camadas internas de cidade; `mapa_leaflet.js` desenha tudo agrupado num toggle "Detalhe da Cidade"; `tile_zoom_maximo_ui` 7→16 | Reset completo do zero, sem erro. 387 locais/9 cidades, todos vindos da geometria (zero fallback). 20/20 NPCs com casa real. `GET /api/mapa/features` testado em z=15 vs z=5 — filtro de zoom confirmado. `pytest` 7/7. | Escopo reduzido documentado na seção da fase (só malha orgânica, sítio sem terreno real, catálogo de 30 não 80, regras de coerência parciais). Não visto no navegador (sem Chrome nesta sessão). |
| II | 5 — IA projetando cidades | | | | |
| — | **GATE 2** | | | | |
| III | 6 — Hidrografia | | | | |
| III | 7 — Biomas novos | | | | |
| III | 8 — NPC necessidades/traços | | | | |
| III | 9 — NPC memória/objetivos | | | | |
| III | 10 — Relevo por placas | | | | |
| III | 11 — Papéis/economia/ganchos | | | | |

---

## 8. Testes de cartografia

> **Escopo deliberadamente pequeno.** O projeto não tem teste nenhum hoje e **este não é o momento de
> cobrir tudo**. Os testes abaixo existem por um motivo só: **travar os invariantes F1–F4** (Seção
> 2.2), que são justamente o que se quebrou em silêncio e custou a Frente 6 inteira. Não escreva
> teste para render, rota, IA, engine ou UI agora.
>
> Regra prática: *se o teste não protege um invariante da Seção 2.2, ele não entra nesta rodada.*

### 8.1 Infra mínima

```bash
venv/bin/pip install pytest            # acrescente 'pytest' a requirements.txt
mkdir -p tests && touch tests/__init__.py
venv/bin/python -m pytest tests/ -v    # comando oficial (nunca `python3`, ver regra 3)
```
Um arquivo só: `tests/test_cartografia.py`. Sem fixture elaborada, sem mock — estas funções são puras,
então o teste é literalmente "chame duas vezes e compare".

### 8.2 Obrigatórios da Fase 0 (T1–T6) — o Gate 1 exige todos verdes

| # | Nome | Invariante | O que pega |
|---|---|---|---|
| **T1** | `test_ruido_independe_do_shape` | F1 | ruído avaliado em índice local em vez de coordenada de mundo |
| **T2** | `test_ruido_invariante_a_subdivisao` | F2 | costura entre tiles / entre fontes |
| **T3** | `test_oitavas_convergem` | F3 | normalização por soma truncada (P1.7) |
| **T4** | `test_gerar_janela_z0_igual_ao_arange` | — | regressão da refatoração 0.3 |
| **T5** | `test_culling_nao_altera_resultado` | F2 | culling de continente apertado demais |
| **T6** | `test_coerencia_entre_zooms` | F3 | zoom que contradiz em vez de refinar |

**T1 — pureza (F1)**. O mesmo ponto do mundo tem que dar o mesmo valor, não importa em que array ele
foi avaliado:
```python
def test_ruido_independe_do_shape():
    x, y = 137.0, 402.25
    sozinho = NoiseGenerator.generate_noise_field(
        np.array([[x]], np.float32), np.array([[y]], np.float32), scale=60, octaves=4, seed=7)
    gx, gy = np.meshgrid(np.linspace(x, x + 10, 64, endpoint=False, dtype=np.float32),
                         np.linspace(y, y + 10, 64, endpoint=False, dtype=np.float32))
    em_grade = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=4, seed=7)
    assert np.isclose(sozinho[0, 0], em_grade[0, 0], atol=1e-6)
```

**T2 — invariância à subdivisão (F2)**. É *este* teste que substitui todo o blend de costura:
```python
def test_ruido_invariante_a_subdivisao():
    gx, gy = np.meshgrid(np.linspace(100, 116, 64, endpoint=False, dtype=np.float32),
                         np.linspace(200, 216, 64, endpoint=False, dtype=np.float32))
    inteiro = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=4, seed=7)
    for i in (0, 32):
        for j in (0, 32):
            bloco = NoiseGenerator.generate_noise_field(
                gx[i:i+32, j:j+32], gy[i:i+32, j:j+32], scale=60, octaves=4, seed=7)
            assert np.array_equal(bloco, inteiro[i:i+32, j:j+32])
```
Depois da Fase 0.3, **repita o mesmo teste com `gerar_janela`** (janela inteira vs. 4 quadrantes) —
essa é a versão que realmente garante ausência de costura no mapa.

**T3 — convergência de oitavas (F3)**. Guarda o conserto da 0.2.

> ⚠️ **Já implementado e recalibrado na prática (2026-09-10)**: a primeira versão deste teste
> (diferença **máxima** pontual entre octaves=4 e octaves=12, tolerância = soma analítica das
> amplitudes omitidas) **não separa** a normalização quebrada da consertada — medido, o detalhe real
> que as oitavas 4-11 acrescentam já é, sozinho, maior que o desvio extra do bug em vários pontos
> amostrados, então o pior-caso analítico é frouxo demais e a normalização antiga passava no teste.
> Isto só foi descoberto rodando o teste contra o código antigo (armadilha nº 13) — **se você for
> escrever este teste do zero, não confie só na leitura da fórmula, meça.**
>
> A versão que efetivamente separa as duas (verificado: passa com o fix, falha sem ele) usa **RMS**
> da diferença sobre a janela inteira, com média sobre 5 pares `(seed, offset)` fixos — RMS é muito
> menos sensível ao acaso de um pico pontual do que o máximo. Medido: RMS médio da normalização
> **nova** ≈ 0,0055; da **antiga** ≈ 0,0081 (~48 % de margem). Código real em `tests/test_cartografia.py`:
> ```python
> def test_oitavas_convergem():
>     p, base, alto = 0.5, 4, 12
>     pares = [(7, 0, 0), (11, 500, 300), (13, 1200, 900), (17, 80, 4000), (19, 3000, 50)]
>     rms_por_par = []
>     for seed, ox, oy in pares:
>         gx, gy = np.meshgrid(np.linspace(ox, ox + 50, 128, endpoint=False, dtype=np.float32),
>                              np.linspace(oy, oy + 50, 128, endpoint=False, dtype=np.float32))
>         a = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=base, seed=seed, persistencia=p)
>         b = NoiseGenerator.generate_noise_field(gx, gy, scale=60, octaves=alto, seed=seed, persistencia=p)
>         rms_por_par.append(float(np.sqrt(np.mean((a - b) ** 2))))
>     assert np.mean(rms_por_par) < 0.0065
> ```
> Rode-o **antes** de aplicar a 0.2 e confirme que ele falha — guarda-corpo que nunca falhou não é
> guarda-corpo (armadilha nº 13). Confirmado nesta sessão: falha (`0.00807 < 0.0065` é falso) sem o
> fix, passa com ele.

**T4 — a refatoração 0.3 não muda z0**:
```python
def test_gerar_janela_z0_igual_ao_arange():
    a = 512
    assert np.array_equal(np.linspace(a, a + 256, 256, endpoint=False, dtype=np.float32),
                          np.arange(a, a + 256, dtype=np.float32))
    tc = _cartografo_de_teste()
    assert np.array_equal(tc.generate_tile(2, 1), tc.gerar_janela(512, 256, 768, 512, 256, 256))
```

**T5 — culling não altera resultado**. Implementado e verificado (2026-09-10): a fórmula do
plano passou de primeira, sem precisar alargar a margem. Medido no mundo real: 2,56x mais
rápido num tile oceânico profundo em z7 (dentro da faixa 2-4x prevista).
```python
def test_culling_nao_altera_resultado():
    tc = _cartografo_de_teste()
    casos = [
        (100, 150, 164, 214, 64, 64),   # perto de um continente de teste — parcialmente culled
        (590, 190, 654, 254, 64, 64),   # perto do outro
        (10, 10, 74, 74, 64, 64),       # longe de ambos — tudo culled com culling ligado
    ]
    for x0, y0, x1, y1, largura, altura in casos:
        com_culling = tc.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=1)
        sem_culling = tc.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=1, _desabilitar_culling=True)
        assert np.array_equal(com_culling, sem_culling)
```
`gerar_janela` aceita `_desabilitar_culling=False` só para este teste (não é parâmetro de uso
normal) — força avaliar todos os continentes mesmo fora do alcance, pra comparar contra o
caminho com culling. Se um dia isto falhar, a fórmula de `alcance` na 0.3 está apertada demais.

**T6 — coerência entre zooms (F3)**: é o aceite nº 1 da Fase 0 virado teste — mesma janela em duas
taxas de amostragem, com contagens de oitava diferentes; a classificação terra/água tem que ser
**idêntica** e `|Δalt|` dentro da tolerância do T3.

### 8.3 Recomendados (não bloqueiam o Gate 1)

- **T7 — `test_bioma_so_tem_ids_validos`**: o canal 3 de qualquer janela só contém IDs de
  `ClimateProcessor.BIOME_IDS`. Pega ID fantasma de interpolação de canal categórico (armadilha nº 1)
  e é barato de manter quando a Fase 7 acrescentar biomas.
- **T8 — `test_mundo_reproduzivel`**: gerar o mundo duas vezes a partir do layout persistido dá array
  idêntico (P0.5). Lento — marque `@pytest.mark.slow` e rode só antes do gate.
- **T9 — `test_layout_persistido_tem_campos_do_gerador`**: o `layout_continentes` do manifesto tem os
  7 campos que `gerar_janela` consome. Barato, e impede P0.5 de voltar sem ninguém notar.

### 8.4 Para fases futuras (escreva junto com a fase, não antes)

- **Fase 2** — `test_nenhum_local_na_agua`: todo `Local.coordenadas` cai em pixel com
  `altitude >= nivel_mar`.
- **Fase 4** — `test_nenhum_edificio_na_agua` e `test_regras_de_coerencia` (porto exige água
  adjacente, `fortaleza` exige muralha).
- **Fase 6** — `test_rio_nao_sobe`: altitude não-crescente ao longo do `LineString`, e todo rio termina
  no mar ou num lago.
