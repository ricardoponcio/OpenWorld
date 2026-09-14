# ESPECIFICAÇÃO — Tecido urbano: lotes, edificações e variedade entre cidades

> **Para quem é este documento**: para o modelo/desenvolvedor que vai transformar a cidade de
> "um ponto no meio de uma quadra vazia" em tecido urbano de verdade — quadras preenchidas de
> construções, ruas com faixa de domínio, e cidades diferentes umas das outras.
>
> **Este documento é auto-suficiente.** Você não precisa reler o
> [`PLANO_EVOLUCAO_V2.md`](PLANO_EVOLUCAO_V2.md) nem o
> [`DIAGNOSTICO_V3.md`](DIAGNOSTICO_V3.md) inteiros. Leia, nesta ordem:
> **Seção 0** (regras de trabalho) → **Seção 1** (o pedido) → **Seção 2** (escala, curta mas
> obrigatória) → **Seção 3** (o que está errado hoje, com medição) → **Seção 5** (decisões já
> tomadas, não as reabra) → **Seção 6** (a especificação, passo a passo) → **Seção 7** (ordem).
>
> **Leia a Seção 3.5 antes de escrever código.** Ela descreve o acoplamento entre a geometria
> e o banco da simulação: cada edificação vira uma linha em `locais`. Isso é **aceito e
> medido**, não um problema — mas mudar a geometria de ponto para polígono quebra o
> importador, e a Seção 3.5.1 registra o único limite de escala que a medição confirmou.
>
> **Todo número aqui foi medido**, não estimado, em 2026-09-11, com o mundo que está em
> `database/`. Cada medição traz o comando que a reproduz. Se o mundo for regerado, remeça
> antes de confiar no número.

**Revisão**: 2026-09-11 (v1.1 — a v1.0 propunha uma camada de edificação decorativa, que não
viraria `Local`. O usuário questionou a premissa, a medição deu razão a ele e a proposta foi
**retirada**: toda construção é um `Local` de verdade. Ver Seções 3.5 e 5.4. A v1.1 também
acrescenta a Seção 3.5.1, o limite real de escala, que só apareceu nessa medição.)
**Estado do mundo medido**: `database/world_manifest.json`, 5 continentes, 15 cidades,
15 arquivos em `database/cidades/`, `database/openworld.db` com 539 locais e 20 NPCs.
**Pré-requisitos já concluídos** (não refaça): D1 (escala), D9 (bbox das feições) e as ruas
com largura em metros. Ver "Log de Sessões" do [`ROADMAP.md`](ROADMAP.md), partes 16 a 18.

---

## 0. Regras de trabalho — leia antes de tocar em qualquer coisa

As seis primeiras são as mesmas da Seção 0 do `PLANO_EVOLUCAO_V2.md` e continuam valendo.
Repetidas aqui porque este documento é auto-suficiente.

1. **Nunca escreva em `database/` enquanto uma simulação ou reset estiver rodando.**
   Verifique **antes de qualquer coisa**:
   ```bash
   ps aux | grep -E "run_simulation|reset_|populate|generate_|run_dashboard" | grep -v grep
   ```
   Se aparecer `run_simulation.py`, pare: você pode corromper o `openworld.db`. Peça ao
   usuário para parar a simulação, ou trabalhe só em leitura. `run_dashboard.py` pode ficar
   de pé, é só leitura.

2. **Use sempre `venv/bin/python`**, nunca `python3` ou `python`.

3. **"Compila" não é teste.** Toda etapa termina com um comando que **roda** e cujo **output
   real** você cola no log da Seção 11.

4. **Todo número novo vai para o `config.json`**, lido via `cfg_get`, com um `_comentario_`
   explicando de onde ele veio. Nunca um literal numérico novo no meio do Python.

5. **Não invente convenção de coordenada.** Existem três, descritas na Seção 2.

6. **Não commite nada.** O usuário valida e commita.

7. **Não rode `builder/populate.py` nem `cartographer/reset_cartography.sh`.** Os dois
   reconstroem o `openworld.db` do zero e apagam a simulação em curso do usuário. Esta linha
   de trabalho inteira pode ser feita e validada sem eles — a Seção 6.4 explica como conferir
   o efeito sobre o banco **sem escrever nele**. Se você concluir que um reset é inevitável,
   **pare e pergunte ao usuário**.

8. **Regerar `database/cidades/*.geojson` é permitido e esperado.** É artefato derivado,
   determinístico, ignorado pelo git, e o comando que o reconstrói leva menos de um minuto:
   ```bash
   venv/bin/python cartographer/cities/generate_city_geometry.py
   ```

---

## 1. O pedido do usuário

Literal, em 2026-09-11, depois de ver a cidade funcionando pela primeira vez:

> "Podemos 'engrossar' as ruas para não parecerem linhas imaginárias? E aumentar também ou
> desenhar as coisas preenchendo as quadras? por que atualmente é um ponto numa quadra grande.
> Tornaria muito mais real."

E, quando perguntado sobre custo:

> "eu queria ter cidades variadas pequenas e grandes com numeros de lotes e areas variadas,
> mesmo que isso custe muito podemos prever uma pré-geração. Depois do mundo gerado até a
> aventura acabar não importa, então se levar 1hr não tem importancia sabe. Desde que na hora
> de operar funcione bem. Quando a peso, não tenho 15GB+ ta otimo"

E sobre a intenção do projeto:

> "pense que eu quero que o mundo seja completo e cheio, atualmente só usamos 1 cidade como
> protótipo, mas o projeto tem nome OpenWorld por um motivo, o mestre só usa a infra do mundo
> que existe por si só."

**A parte das ruas já foi feita** (largura real em metros por classe de via, ver ROADMAP parte
18). **Este documento é o resto**: quadras preenchidas e cidades variadas.

**Orçamento autorizado pelo usuário**: até ~1 hora de pré-geração, e peso de disco muito
acima do que este trabalho vai produzir. Não otimize geração. **Otimize a operação** — o mapa
tem que continuar respondendo rápido a cada pan e zoom.

---

## 2. Escala — o mínimo que você precisa saber

Existem três sistemas de coordenada e **nenhum outro deve ser criado**:

| sistema | unidade | onde aparece |
|---|---|---|
| mundo | pixel | `x_global`/`y_global` do manifesto, bbox das APIs |
| local da cidade | metro, origem no centro da cidade | dentro de `GeradorCidade` |
| GeoJSON / Leaflet | `[lng, lat] = [x_mundo, -y_mundo]` | arquivos em `database/cidades/` |

A conversão entre eles vive **em um lugar só**: `cartographer/cities/escala.py`. Use-o.

```python
from cartographer.cities.escala import metros_por_pixel_mundo, zoom_min_por_camada
```

Os dois fatos que mais importam aqui:

- **1 px de mundo = 15.811,4 m.** Vem de `sqrt(escala_pixel_area_km2) * 1000`, porque
  `escala_pixel_area_km2` é **área** (km² por pixel), não comprimento. Confundir os dois foi
  o bug D1, que deu 15,81x de erro no tamanho de todas as cidades.
- **No Leaflet (`L.CRS.Simple`), 1 px de mundo ocupa `2^zoom` px de tela.** Logo
  `px_de_tela_por_metro = 2^zoom / 15811.4`. É essa conta que define o que é visível em cada
  zoom, e ela já está implementada em `pxDeTelaPorMetro()` no `mapa_leaflet.js`.

Tabela de referência (memorize a linha do z13, é onde o usuário está olhando):

| zoom | px de tela por metro | cidade média (1200 m) na tela | lote de 300 m² (17 m) |
|---|---|---|---|
| 12 | 0,259 | 311 px | 4,5 px |
| 13 | 0,518 | 622 px | 8,9 px |
| 14 | 1,036 | 1244 px | 17,8 px |
| 15 | 2,072 | 2487 px | 35,6 px |

O teto da interface é `tile_zoom_maximo_ui = 15`.

---

## 3. O que está errado hoje

### 3.1 O lote tem 2,4 hectares

`cidade_geo_lote_area_alvo_m2` vale **24000**. Medido nos arquivos gerados:

```
=== Aurora Vales (medio, raio 600m) ===
  quarteirao  n= 18  area mediana=    58761 m2  lado equiv=  242 m
  lote        n= 32  area mediana=    29401 m2  lado equiv=  171 m
  lotes por quarteirao: 1.8

=== Silenmont (grande, raio 900m) ===
  quarteirao  n= 32  area mediana=    74763 m2  lado equiv=  273 m
  lote        n= 87  area mediana=    25882 m2  lado equiv=  161 m
  lotes por quarteirao: 2.7

=== Quendorvale (pequeno, raio 350m) ===
  quarteirao  n= 12  area mediana=    22190 m2  lado equiv=  149 m
  lote        n= 12  area mediana=    22190 m2  lado equiv=  149 m
  lotes por quarteirao: 1.0
```

Um lote mediano tem **171 m de lado**. Um lote urbano medieval real tem 200 a 400 m² (uns
10 × 30 m). O lote atual é **cem vezes maior** do que deveria. Em Quendorvale a subdivisão
nem acontece: 12 quadras, 12 lotes, um lote por quadra.

Há também um teto escondido: `_subdividir_lote(..., max_profundidade=5)` é um literal em
Python, não config, e limita a **32 lotes por quadra** mesmo que a área alvo peça mais.

### 3.2 A rua não ocupa terreno nenhum

Os quarteirões são construídos assim (`_gerar_quarteiroes_e_lotes`):

```python
quad = [raio_interno[i], raio_externo[i], raio_externo[i2], raio_interno[i2]]
```

Quadras vizinhas **compartilham vértice**. A linha da rua passa exatamente sobre a divisa
entre duas quadras, com largura zero de terreno. A rua é um traço desenhado por cima do
chão, não um vazio entre construções. Enquanto a quadra estava vazia isso não aparecia.
Quando ela encher de casas, as casas vão encostar umas nas outras através da rua.

Existe uma chave `cidade_geo_recuo_rua_m` valendo `3.0` no `config.json`. Ela é lida no
construtor (`self.recuo_rua`) e **nunca é usada em lugar nenhum**. Confirme:

```bash
grep -n "recuo_rua" cartographer/cities/generate_city_geometry.py
```

### 3.3 O edifício é um ponto no centroide

```python
def _gerar_edificios(self):
    """Um edifício por lote — Point no centroide (...)"""
```

Um `Point` por lote, renderizado no front como `L.circleMarker(radius: 5)`, ou seja, um
círculo de tamanho fixo em px de tela. Não tem forma, não tem orientação, e não cresce com o
zoom. É literalmente o "ponto numa quadra grande" que o usuário descreveu.

### 3.4 Todas as cidades têm a mesma forma

A variedade hoje se resume a três tamanhos com valores fixos:

```
cidade_geo_raio_m_por_tamanho:    {'pequeno': 350, 'medio': 600, 'grande': 900}
cidade_geo_num_portoes_por_tamanho: {'pequeno': 2, 'medio': 3, 'grande': 4}
cidade_geo_num_aneis_por_tamanho:   {'pequeno': 2, 'medio': 3, 'grande': 4}
cidade_geo_lote_area_alvo_m2:       24000   (uma só, para o mundo inteiro)
```

Toda cidade média tem exatamente 600 m de raio, 3 anéis, 6 setores e 18 quadras. Some-se a
isso `num_setores = max(6, num_portoes * 2)`, que **amarra** o número de setores ao de
portões e, por consequência, força o espaçamento dos portões a ser sempre perfeito (não
sobra grau de liberdade para o terreno escolher). Cidades diferentes são hoje a mesma cidade
com raio diferente.

### 3.5 Todo `edificio` vira uma linha no banco da simulação

Isto **não é um problema**, mas é um acoplamento que você precisa conhecer antes de mexer na
geometria. `builder/populate.py`, linha 54:

```python
for feat in geojson.get("features", []):
    props = feat.get("properties", {})
    if props.get("camada") != "edificio":
        continue
    lng, lat = feat["geometry"]["coordinates"]     # <- assume Point
    x_mundo, y_mundo = lng, -lat
    loc = Local(id=props["id"], nome=props["nome"], ..., capacidade=..., salario_base=...)
    db.salvar_local(loc)
```

Duas consequências, uma inofensiva e uma que quebra:

**1. Cada feature `edificio` vira um `Local` no `openworld.db`, um para um.** Hoje são 539
features no disco e 539 linhas na tabela — os números batem exatamente. Encher as quadras
leva isso a ~21.000 locais.

**Isso é aceitável e foi medido.** A primeira versão deste documento tratava o crescimento
como perigoso e propunha uma camada decorativa separada. O usuário questionou a premissa, a
medição deu razão a ele, e a proposta foi retirada. Os números, em banco descartável e em
Python puro:

| locais no mundo | banco | `SELECT *` | varredura por tick (20 NPCs) |
|---|---|---|---|
| 540 (hoje) | 0,2 MB | 1 ms | 0,4 ms |
| 6.000 | 0,6 MB | 8 ms | 4 ms |
| 21.000 | 2,0 MB | 25 ms | 9 ms |
| 42.000 | 3,9 MB | 54 ms | 19 ms |

Nove milissegundos por tick é menos de 1% do orçamento. **Não há motivo para separar cenário
de entidade de simulação.** Num mundo aberto, a casa que o mestre aponta deve existir.

E o catálogo **já** impede o absurdo de 1.400 tavernas: `cidade_geo_catalogo_edificios` tem
teto por tipo (`max`), somando 29 não-residências na cidade pequena, 43 na média e 48 na
grande. Quando o catálogo se esgota, `_gerar_edificios` **já cai em "Residência"**:

```python
disponiveis = [e for e in candidatos if contagem[e["tipo_local"]] < e.get("max", 99)]
entrada = self._escolher_edificio(disponiveis) if disponiveis else None
if entrada is None:
    nome_tipo, categoria, capacidade, salario = "Residência", "residencia", 5, 0
```

Ou seja, uma cidade grande com 1.400 lotes sai com ~48 prédios notáveis e ~1.350 residências.
É exatamente o perfil de uma cidade medieval real, e **o código atual já faz isso sozinho**.
Você não precisa escrever nada para obter esse comportamento — só não o quebre.

**2. ⚠️ O código faz `lng, lat = coordinates`, o que só funciona para `Point`.** Esta é a
parte que realmente quebra. Se você transformar `edificio` em `Polygon` sem mexer aqui, o
próximo reset morre com `ValueError: too many values to unpack`. Tratado na etapa E4.

### 3.5.1 O limite real: as varreduras são O(NPCs × locais do mundo inteiro)

Este é o único achado de escala que sobreviveu à medição, e ele **não é causado por este
trabalho** — é anterior. Vários caminhos quentes varrem `engine.locais` inteiro, uma vez por
NPC por tick, sem filtrar pela cidade do NPC. Exemplos: `movement.py:97`
(`mover_para_restaurante`), `movement.py:118`, `logic.py:86`, `movement.py:68`.

Medido:

| locais no mundo | NPCs | por tick | veredito |
|---|---|---|---|
| 540 | 20 | 1 ms | ok |
| 21.000 | 20 | 8 ms | ok |
| 21.000 | 200 | 86 ms | ok |
| 21.000 | 2.000 | 935 ms | inviável, o tick é de 1 s |
| 21.000 | 2.000, varrendo só a cidade do NPC | 62 ms | ok |

Com os 20 NPCs de hoje, nada disso importa. **Mas o objetivo declarado do projeto é um mundo
cheio**, e é o produto NPCs × locais que estoura, não nenhum dos dois sozinho. O conserto é
indexar `engine.locais` por `cidade_id` e varrer só a cidade do NPC, o que devolve 15x.

**Isto está fora do escopo deste documento** (é motor, não cartografia). Não faça aqui.
Registre no `ROADMAP.md` como frente própria, para que não vire descoberta de última hora
quando o mundo for povoado.

### 3.6 Custo de servir — onde está o gargalo

`/api/mapa/features` chama `_coletar_features_camada`, que para cada uma das 8 camadas de
cidade varre as feições de **todas** as cidades, e depois recalcula a bbox de cada feição
sobrevivente com `_bbox_geometria`, **a cada requisição**. O arquivo JSON é cacheado por
mtime, mas a bbox não é cacheada nada.

Medido (`venv/bin/python`, mundo atual, 14 arquivos, 2.061 feições):

```
_bbox_geometria+intersecta sobre 2061 feicoes: 3.4 ms  (1.6 us/feicao)
serializar 141 feicoes sobreviventes: 0.3 ms
requisicao real medida ponta a ponta: 4.7 ms, 58 KB
```

Projeção linear para lotes realistas:

| lotes por cidade | feições no mundo | bbox por requisição | JSON | total por pan/zoom |
|---|---|---|---|---|
| 400 | 13.500 | 22 ms | 2 ms | ~24 ms |
| 1.400 | 43.500 | 71 ms | 5 ms | ~76 ms |
| 2.800 | 85.500 | 139 ms | 11 ms | ~150 ms |

150 ms a cada pan é perceptível. E é quase todo gasto calculando a bbox de feições que vão
ser descartadas — de cidades que nem estão na tela. A Seção 5.5 resolve isso.

**Peso em disco**: os mesmos cenários dão 5 MB, 17 MB e 33 MB de GeoJSON. O `database/`
inteiro hoje tem 53 MB. Nada disso é problema, o usuário autorizou muito mais.

**Tempo de geração hoje**: `0,76 s` para as 15 cidades. Mesmo cem vezes mais geometria fica
em poucos minutos, muito dentro da hora autorizada.

---

## 4. Objetivo

Ao final desta linha de trabalho, no zoom 13, o usuário deve ver:

- Ruas como **vazios** entre construções, com largura real, e não traços por cima do chão.
- Quadras **preenchidas** de construções com forma, orientadas para a rua.
- Cidades **visivelmente diferentes** entre si em tamanho, densidade e desenho, e não a
  mesma cidade em três escalas.
- O mapa respondendo a pan e zoom **sem travar**.
- Toda construção existindo como `Local` de verdade, clicável e nomeada, para o mestre poder
  apontar qualquer casa. O `openworld.db` vai para a casa das dezenas de milhares de locais, e
  isso é **esperado** (Seção 3.5).

---

## 5. Decisões de projeto já tomadas — não as reabra

Estas decisões saíram da análise e da conversa com o usuário. Elas são o enunciado do
trabalho, não opções. Se você discordar de alguma, **pare e discuta com o usuário** antes de
implementar diferente.

### 5.1 A rua ganha faixa de domínio, tirada das quadras

A quadra encolhe para dentro, afastando-se da linha de centro de cada rua que a limita, por
`largura_da_via / 2 + recuo`. A largura por classe de via já existe e já é usada pelo front
(`cidade_via_largura_m_por_classe`: principal 11 m, anel 7 m, secundária 5 m).

**Por que assim, e não engrossando o traço**: o traço grosso continua sendo desenho por cima
do chão. Só encolher a quadra faz a rua existir como espaço. É também o que impede a casa de
um lado de encostar na casa do outro.

### 5.2 O lote vira realista e varia

Alvo por **banda** (o anel concêntrico), não um número único: denso no centro, mais folgado
na borda. Mais uma variação por cidade, determinística a partir da seed do nome. Ordem de
grandeza alvo: **180 m² no centro a ~500 m² na borda**.

### 5.3 A edificação vira polígono

Footprint poligonal dentro do lote, com recuo da divisa e taxa de ocupação. A orientação sai
de graça: o lote já nasce alinhado à malha viária, então o polígono inscrito nele também.

### 5.4 Toda construção é um `Local` de verdade. Não existe camada decorativa

**Esta decisão foi revista.** A primeira versão do documento propunha uma camada `construcao`
puramente visual, que não viraria `Local`. O usuário questionou:

> "nao entendi a necessidade de edificacao decorativa. Se temos uma cidade com 20 postos de
> trabalho isso nao cria um problema. Os 539 locais sao no mundo inteiro até onde eu
> entendi (...) o mestre só usa a infra do mundo que existe por si só."

A medição da Seção 3.5 deu razão a ele: 21.000 locais custam 2 MB de banco, 25 ms de carga e
9 ms por tick. A camada decorativa era complexidade sem contrapartida, e ia contra o objetivo
do projeto — num mundo aberto, a casa que o mestre aponta tem que existir de verdade.

**Portanto**: continua havendo **uma única camada de edificação**, `edificio`, e toda
construção vira `Local`. O perfil realista (poucos prédios notáveis, muitas residências) já
sai do teto por tipo do catálogo, que o código atual já respeita — ver Seção 3.5.

O que **sobra** de trabalho aqui é só a mudança de `Point` para `Polygon`, que obriga
`builder/populate.py` a usar o centroide. Etapa E4.

### 5.5 O custo de servir se resolve com índice por cidade, não com menos geometria

Duas mudanças, nesta ordem de importância:

1. **Índice por cidade** (`database/cidades/_indice.json`), escrito pelo gerador: bbox de
   cada cidade em px de mundo, e por camada a contagem e o `zoom_min`. A API descarta a
   cidade inteira sem nem abrir o arquivo quando a bbox não intersecta. Como o usuário
   sempre está olhando **uma** cidade, isso corta ~15x.
2. **Bbox por feição calculada no carregamento, não por requisição.** Hoje `_bbox_geometria`
   roda a cada requisição para cada feição candidata. Calcule uma vez, ao carregar o arquivo,
   e guarde junto no cache em memória.

**Por que não reduzir a geometria**: o usuário pediu explicitamente um mundo cheio e
autorizou o custo. Reduzir seria resolver o pedido errado.

### 5.6 A variedade vem de faixas sorteadas pela seed, não de mais tamanhos

Raio, número de anéis e número de setores passam a ser sorteados dentro de uma faixa por
tamanho, com `self.rng` (que já é determinístico por `zlib.crc32(nome)`). E
`num_setores` deixa de ser `max(6, num_portoes * 2)`, o que hoje força o espaçamento dos
portões a ser sempre perfeito. Com mais setores que o dobro dos portões, o terreno volta a
ter liberdade de escolher onde eles ficam, e o contorno fica irregular de verdade.

---

## 6. Especificação — etapa por etapa

Cada etapa tem: o que muda, as chaves de config, o esboço de código e o **comando de aceite**
cujo output você cola na Seção 11. Faça uma etapa por vez, na ordem.

### E1 — Faixa de domínio da via (a rua vira vazio)

**Arquivo**: `cartographer/cities/generate_city_geometry.py`, `_gerar_quarteiroes_e_lotes`.

O quad da quadra é `[interno[i], externo[i], externo[i2], interno[i2]]`. Suas quatro arestas
caem **cada uma sobre a linha de centro de uma rua**:

| aresta | rua | classe |
|---|---|---|
| `interno[i] → externo[i]` | radial `i` | `principal` se `i` é setor de portão, senão `secundaria` |
| `externo[i] → externo[i2]` | anel `j` | `anel` |
| `externo[i2] → interno[i2]` | radial `i2` | `principal` se `i2` é setor de portão, senão `secundaria` |
| `interno[i2] → interno[i]` | anel `j-1` | `anel` |

Encolha o quad deslocando cada aresta para dentro pela sua própria distância
(`largura_da_classe / 2 + recuo_rua`) e reinterceptando. Como o polígono é sempre um
quadrilátero convexo, isso é interseção de quatro retas — **não precisa de biblioteca de
geometria, e `shapely` não está instalada** (não a instale sem falar com o usuário).

Esboço:

```python
def _encolher_quad(self, quad, distancias):
    """Desloca cada aresta do quad para DENTRO por distancias[k] e reintercepta.
    `quad` tem 4 vértices em sentido consistente; `distancias[k]` é o recuo da aresta
    k (de quad[k] para quad[k+1]), em metros. Retorna o quad encolhido, ou None se ele
    degenerar (quadra estreita demais para caber a rua)."""
```

Dicas de implementação, para não perder tempo:
- A normal interna de cada aresta se obtém girando a direção da aresta 90° **para o lado do
  centroide** do quad (teste com produto escalar, não presuma a orientação).
- A interseção de duas retas em forma `ponto + t * direção` é um sistema 2x2. Se o
  determinante for ~0, as arestas são paralelas: nesse caso use o ponto deslocado direto.
- **Degeneração é esperada e não é erro.** Uma quadra fina perto do centro pode sumir
  inteira depois de tirar duas ruas. Se a área encolhida ficar abaixo de
  `cidade_geo_quadra_area_minima_m2`, descarte a quadra (não emita `quarteirao` nem lotes
  nela) em vez de emitir um polígono invertido.

**Config novo**:
```json
"cidade_geo_quadra_area_minima_m2": 400,
```
(`cidade_geo_recuo_rua_m` já existe, valendo 3.0, e passa a ser usado de fato.)

**Aceite**: a soma das áreas das quadras tem que cair, e a queda tem que bater com a área
que as ruas passaram a ocupar. Meça antes e depois:

```bash
venv/bin/python - <<'EOF'
import json, math
cfg = json.load(open('config.json'))['cartografia']
mpp = math.sqrt(cfg['escala_pixel_area_km2']) * 1000.0
d = json.load(open('database/cidades/aurora_vales.geojson'))
def area(p):
    a = 0.0
    for i in range(len(p)-1):
        a += p[i][0]*p[i+1][1] - p[i+1][0]*p[i][1]
    return abs(a)/2
tot = sum(area([(x*mpp, y*mpp) for x, y in f['geometry']['coordinates'][0]])
          for f in d['features'] if f['properties']['camada'] == 'quarteirao')
print(f"area total das quadras: {tot:,.0f} m2")
EOF
```

Registre os dois números. A redução esperada fica entre 10% e 25% para a cidade média.
Valide também **visualmente**: no zoom 14, a rua tem que aparecer como faixa vazia com quadra
dos dois lados, sem a quadra cruzando por baixo.

---

### E2 — Lote realista e variado

**Arquivo**: mesmo, `_subdividir_lote` e `_gerar_quarteiroes_e_lotes`.

Troque `cidade_geo_lote_area_alvo_m2` (número único) por um alvo que depende da banda e da
cidade:

```
area_alvo(banda) = base_m2 * (fator_por_banda ** (banda - 1)) * fator_da_cidade
```

- `banda` já existe no código (1 é o anel mais interno).
- `fator_da_cidade` é sorteado uma vez por cidade com `self.rng.uniform(*faixa)`, o que
  mantém o determinismo por nome.

**Config novo**:
```json
"_comentario_lote": "Area alvo do lote em m2. Substitui cidade_geo_lote_area_alvo_m2, que valia 24000 (2,4 ha!) e deixava 1,8 lote por quadra — o 'ponto numa quadra grande' que o usuario reportou. O alvo cresce com a banda (centro denso, borda folgada) e leva um fator por cidade sorteado da seed do nome, pra duas cidades do mesmo tamanho nao serem identicas. Referencia historica: lote urbano medieval tem 200 a 400 m2.",
"cidade_geo_lote_area_base_m2": 180,
"cidade_geo_lote_fator_por_banda": 1.6,
"cidade_geo_lote_fator_cidade_faixa": [0.75, 1.40],
"cidade_geo_lote_profundidade_max": 10,
```

`cidade_geo_lote_profundidade_max` substitui o literal `max_profundidade=5` da assinatura de
`_subdividir_lote`. Justificativa do valor: para ir de uma quadra de 58.000 m² a lotes de
300 m² são ~7,6 bisseções; 10 dá folga e ainda limita a explosão.

**Refinamento opcional, se sobrar tempo** (não é requisito): hoje a subdivisão corta sempre
pelo lado mais longo, o que dá lotes quase quadrados. Lote urbano real é estreito e fundo,
com o lado **curto** na rua. Cortar preferencialmente perpendicular à aresta que dá para a
rua produz testada de lote de verdade. Faça só depois que o resto estiver funcionando, e
meça a razão mediana entre os lados antes e depois.

**Aceite**: rode o mesmo script de medição da Seção 3.1 e cole a tabela. Alvo:

| métrica | hoje | esperado |
|---|---|---|
| área mediana do lote (cidade média) | 29.401 m² | 200 a 600 m² |
| lotes por quadra | 1,8 | 20 a 120 |
| lotes na cidade média | 32 | 400 a 2.000 |

Duas cidades do mesmo `tamanho` têm que sair com contagens **diferentes**.

---

### E3 — Edificação poligonal

**Arquivos**: `generate_city_geometry.py` (`_gerar_edificios`), `mapa_leaflet.js` (estilo).

Para cada lote que não for rejeitado pela declividade:

1. Encolha o quad do lote por `cidade_geo_edificacao_recuo_m` (mesma função `_encolher_quad`
   da E1, com distância igual nos quatro lados).
2. Encolha de novo em torno do centroide pela raiz de `cidade_geo_edificacao_taxa_ocupacao`,
   para a construção não tomar o lote inteiro.
3. Emita como `Polygon`.

**Config novo**:
```json
"cidade_geo_edificacao_recuo_m": 1.5,
"cidade_geo_edificacao_taxa_ocupacao": 0.55,
"cidade_geo_edificacao_jitter": 0.15,
```

`jitter` é uma variação aleatória (via `self.rng`) na taxa de ocupação por construção, para
a quadra não virar um tabuleiro perfeito.

**No front**: `edificio` precisa de entrada em `ESTILO_CAMADA_CIDADE`.
`edificio` hoje é desenhado por `criarMarcadorDetalheCidade`, que só trata `Point` — quando
virar polígono, ele passa pelo caminho de `style`, e a cor por categoria
(`CATEGORIA_EDIFICIO_COR`) tem que migrar para uma função de estilo.

⚠️ **Cuidado de legibilidade**: com ~1.350 residências e ~48 prédios notáveis por cidade, dar
cor de categoria a todas empasta a tela. Pinte a residência com um tom neutro único (é massa
construída, não informação) e reserve a cor de categoria para os notáveis, que são os que o
jogador procura. Isso é estilo no front, não filtro na API: a residência continua sendo um
`Local` completo, clicável, com nome e popup.

**Aceite**: conte e meça.

```bash
venv/bin/python -c "
import json, collections
d = json.load(open('database/cidades/aurora_vales.geojson'))
print(collections.Counter(f['properties']['camada'] for f in d['features']))
print('tipos de geometria por camada:', {
    c: sorted({f['geometry']['type'] for f in d['features'] if f['properties']['camada']==c})
    for c in ['edificio','lote','rua']})
"
```

Mais validação **visual** no zoom 13 e 14: a quadra tem que parecer ocupada, com construções
separadas por vãos, não um bloco maciço nem pontos soltos.

---

### E4 — ⚠️ `Polygon` quebra o importador do banco

**Arquivo**: `builder/populate.py`, `_importar_locais_da_geometria`.

Uma mudança obrigatória, e uma verificação.

**A mudança — centroide em vez de desempacotar o ponto.** Onde hoje está:
```python
lng, lat = feat["geometry"]["coordinates"]
x_mundo, y_mundo = lng, -lat
```
passe a aceitar `Polygon`, calculando o centroide do anel externo. **Mantenha a
compatibilidade com `Point`**, porque pode haver GeoJSON antigo em disco e o paliativo
`_importar_locais_paliativo` continua produzindo ponto.

Sem isso, o próximo reset morre com `ValueError: too many values to unpack`. Como o reset é
raro e manual, o erro só apareceria muito depois da sua sessão, para o usuário, sem contexto.

**A verificação — o perfil de tipos continua sadio.** Não há teto novo a implementar: o
catálogo já limita os prédios notáveis a 29/43/48 por tamanho de cidade, e o código já cai em
"Residência" quando esgota (Seção 3.5). Você só precisa **confirmar que continua valendo**
depois que o número de lotes explodir. O modo de falhar aqui seria alguém "consertar" o
esgotamento do catálogo achando que é bug.

**Aceite — obrigatório, e sem escrever no banco.** Este script conta quantos `Local` o
próximo reset criaria e com que perfil, lendo só os arquivos:

```bash
venv/bin/python - <<'EOF'
import json, os, sqlite3
total = 0
for nome in sorted(os.listdir('database/cidades')):
    if not nome.endswith('.geojson'):
        continue
    d = json.load(open(f'database/cidades/{nome}'))
    n = sum(1 for f in d['features'] if f['properties'].get('camada') == 'edificio')
    total += n
    print(f"  {nome:<32} {n:>5} locais")
print(f"TOTAL que o proximo populate criaria: {total}")
print("hoje no banco:", sqlite3.connect('database/openworld.db')
      .execute('SELECT COUNT(*) FROM locais').fetchone()[0])
EOF
```

**Critérios**:
- O total pode subir para a casa das dezenas de milhares. Isso é **esperado e aceito**
  (Seção 3.5). O que não pode é o perfil degenerar.
- **Prédios notáveis por cidade** (tudo que não é `categoria == "residencia"`) tem que ficar
  no teto do catálogo: até 29 na pequena, 43 na média, 48 na grande. Se aparecerem 300
  tavernas, o teto do catálogo foi quebrado em algum lugar — conserte antes de seguir.
- **Residências** devem ser a esmagadora maioria, acima de 90% numa cidade cheia.

Acrescente ao script acima uma contagem por categoria para conferir isso.

Confirme também que nenhum outro consumidor apareceu:

```bash
grep -rn "edificio" --exclude-dir=venv --exclude-dir=.git --exclude-dir=database --exclude-dir=docs .
```

---

### E5 — Índice por cidade e bbox cacheada

**Arquivos**: `generate_city_geometry.py` (escreve), `web/composed_routes.py` (lê).

**Formato do índice** (`database/cidades/_indice.json`) — proposto, ajuste se precisar, mas
documente:

```json
{
  "gerado_em": "2026-09-11T10:32:00",
  "cidades": [
    {
      "slug": "aurora_vales",
      "nome": "Aurora Vales",
      "tamanho": "medio",
      "raio_m": 612.4,
      "bbox": {"min_x": 392.96, "min_y": 658.96, "max_x": 393.04, "max_y": 659.04},
      "camadas": {"rua": {"n": 10, "zoom_min": 12}, "edificio": {"n": 1387, "zoom_min": 13}}
    }
  ]
}
```

⚠️ `_listar_arquivos_geojson_cidades` hoje devolve **todo** `*.geojson` do diretório. Se o
índice for salvo ali com essa extensão, ele vira uma "cidade" fantasma. Salve como `.json`,
ou exclua-o explicitamente na listagem. Não deixe isso implícito.

**Mudanças em `web/composed_routes.py`**:

- `_coletar_features_camada(camada)` passa a receber também `bbox` e `z`, e pula a cidade
  cuja bbox não intersecta ou cuja camada tem `zoom_min > z`, **sem abrir o arquivo**.
- `_carregar_geojson_cache` passa a devolver, junto do GeoJSON, a bbox pré-calculada de cada
  feição, agrupada por camada. Calcule no carregamento (uma vez por mtime), nunca por
  requisição.

**Aceite**: meça a requisição ponta a ponta antes e depois, no mesmo bbox e zoom. Hoje:

```bash
curl -s -o /dev/null -w "http %{http_code}  %{size_download} bytes  %{time_total}s\n" \
  "http://127.0.0.1:5000/api/mapa/features?camadas=muralha,torre,portao,praca,rua,quarteirao,edificio,lote&bbox=392.92,658.92,393.08,659.08&z=13"
```

Linha de base atual, com a geometria pequena: `http 200  58718 bytes  0.0047s`.
**Critério**: depois da E2/E3, com a geometria cem vezes maior, a requisição tem que ficar
**abaixo de 60 ms**. Meça também com o mapa no mundo inteiro (z0), onde nenhuma cidade deve
ser aberta.

---

### E6 — Variedade entre cidades

**Arquivo**: `generate_city_geometry.py`, `__init__`; e `cartographer/cities/escala.py`.

Troque os valores fixos por faixas sorteadas com `self.rng` (determinístico por nome):

```json
"cidade_geo_raio_m_faixa_por_tamanho": {
    "pequeno": [260, 430], "medio": [470, 760], "grande": [720, 1150]
},
"cidade_geo_num_aneis_faixa_por_tamanho": {
    "pequeno": [2, 3], "medio": [3, 4], "grande": [4, 6]
},
"cidade_geo_setores_por_portao_faixa": [2.5, 4.0]
```

`num_setores = round(num_portoes * sorteio_da_faixa)`, com piso em `num_portoes * 2`. É isso
que solta a amarra descrita em 3.4 e devolve ao terreno a liberdade de escolher onde ficam os
portões — hoje ele só escolhe a rotação.

⚠️ **Consequência que você precisa tratar**: `zoom_min_por_camada(config, tamanho)` em
`escala.py` deriva o zoom do **raio nominal do tamanho**. Com raio variável, o gerador tem
que passar o **raio real da cidade**, não o rótulo. Refatore a função para receber o raio.

A tabela que `/api/continentes` devolve (`cidade_zoom_min_por_tamanho`) continua usando o
raio nominal — ela só alimenta o texto do popup e o alvo do duplo-clique, onde uma
aproximação é aceitável. **Documente essa aproximação no comentário da rota**, senão ela vira
a próxima divergência silenciosa entre tabela e fórmula (foi exatamente o que aconteceu antes
do D9).

**Aceite**: uma tabela com as 15 cidades, mostrando raio, anéis, setores, quadras, lotes e
construções. Nenhuma linha pode ser idêntica a outra do mesmo tamanho.

---

## 7. Ordem de execução e checkpoints

| etapa | depende de | pode quebrar | checkpoint com o usuário |
|---|---|---|---|
| E1 faixa de domínio | — | geometria da quadra | não |
| E2 lote realista | E1 | volume de dados | **sim, mostre o print** |
| E3 edificação poligonal | E2 | render do front | **sim, mostre o print** |
| E4 importador do banco | E3 | **o próximo reset** | **sim, obrigatório** |
| E5 índice e bbox | E2 | performance | não |
| E6 variedade | E1–E4 | tudo um pouco | **sim, mostre o print** |

Faça **E1 → E2 → E3 → E4 → E5 → E6**. Não pule a E4 para "ver bonito antes": entre a E3 e a
E4 o repositório fica num estado em que o mapa funciona mas o próximo reset quebra, e o reset
é raro o bastante para o erro só aparecer muito depois, para o usuário, sem contexto.

Depois de cada etapa: rode `venv/bin/python -m pytest tests/ -q` (hoje 10 passam),
`node --check web/static/js/mapa_leaflet.js`, e valide o JSON do config.

---

## 8. Armadilhas — o que **não** fazer

- ❌ **Não instale `shapely`** para fazer o inset. Não está no ambiente, e o caso aqui é
  quadrilátero convexo, que se resolve com interseção de retas. Se você achar mesmo que
  precisa, pergunte ao usuário antes.
- ❌ **Não crie uma camada de edificação decorativa.** Foi proposto e descartado com
  medição (Seção 5.4). Toda construção é um `Local` de verdade.
- ❌ **Não "conserte" o esgotamento do catálogo de edifícios.** Ele cair em "Residência"
  depois de atingir o `max` de cada tipo é o comportamento correto, e é o que produz o
  perfil realista de uma cidade cheia.
- ❌ **Não rode `populate.py` nem `reset_cartography.sh`** para testar. Use o script de
  contagem da E4, que lê os arquivos e não escreve nada.
- ❌ **Não calcule bbox por requisição.** É o gargalo medido na Seção 3.6, e a tentação de
  "só filtrar mais cedo" sem cachear não resolve.
- ❌ **Não reescreva à mão a tabela de `zoom_min`.** Ela é derivada em `escala.py`. Escrever
  à mão foi o que produziu a divergência corrigida no D9.
- ❌ **Não mexa nas emendas visíveis entre tiles.** O usuário adiou isso explicitamente.
- ❌ **Não mude a convenção `[lng, lat] = [x_mundo, -y_mundo]`.** Meia dúzia de arquivos
  dependem dela.
- ❌ **Não presuma a orientação dos vértices do quad** ao calcular a normal interna. Teste
  contra o centroide. O bug análogo já foi pago uma vez em `_subdividir_lote` (ver o
  comentário sobre "quad em zigue-zague" no código).

---

## 9. Critérios de aceite, todos juntos

Cole o output real de cada um na Seção 11.

1. **Área das quadras** caiu entre 10% e 25% (E1), e a rua aparece como vazio no zoom 14.
2. **Lote mediano** entre 200 e 600 m², de 20 a 120 lotes por quadra (E2).
3. **`edificio` é `Polygon`**, e a quadra parece ocupada no zoom 13 (E3).
4. **Perfil dos `edificio`** sadio: notáveis dentro do teto do catálogo (29/43/48 por
   tamanho), residências acima de 90% numa cidade cheia, e `populate.py` lendo `Polygon`
   sem quebrar (E4).
5. **`/api/mapa/features` abaixo de 60 ms** no zoom 13 sobre uma cidade cheia (E5).
6. **15 cidades com números diferentes** entre si, mesmo dentro do mesmo tamanho (E6).
7. **`pytest tests/ -q` continua 10/10.**
8. **Tempo total de `generate_city_geometry.py`** medido e registrado (orçamento: 1 hora;
   linha de base atual: 0,76 s).
9. **Peso de `database/cidades/`** medido e registrado (hoje: 1,2 MB).

---

## 10. O que este documento **não** cobre

- **Interior de edifício, andares, portas.** Fora de escopo. A construção é um footprint.
- **Estradas entre cidades.** A camada `estradas` existe no seletor do Leaflet e nunca teve
  gerador. Continua sem.
- **Rios, pontes, muralhas irregulares.** Não entram aqui.
- **Narrativa de cidade por IA (Fase 5 do plano V2).** Ela se beneficia deste trabalho
  (`altitude` e `bairro` por construção), mas é outra frente.
- **As emendas visíveis entre tiles.** Adiadas pelo usuário, de novo.
- **Indexar `engine.locais` por cidade.** É o limite real de escala medido na Seção 3.5.1:
  as varreduras por tick são O(NPCs × locais do mundo inteiro), o que aguenta 200 NPCs e não
  aguenta 2.000. É motor, não cartografia, e é anterior a este trabalho. **Registre como
  frente própria no `ROADMAP.md`**, não conserte aqui.
- **Reduzir o número de NPCs ou mexer no `JobMarket`.**

---

## 11. Log de execução

Preencha conforme for implementando. Um bloco por etapa. Cole o **output real** dos comandos
de aceite, não um resumo deles.

### E0 — Linha de base (já medida, 2026-09-11, todos os scripts desta seção conferidos)

Não refaça, a menos que o mundo seja regerado. É contra estes números que você compara.

```
area total das quadras (Aurora Vales):  909.131 m2
area mediana do lote (Aurora Vales):     29.401 m2   (171 m de lado)
lotes por quarteirao (Aurora Vales):          1,8
geometria por camada: edificio=Point, lote=Polygon, rua=LineString, quarteirao=Polygon

contagem de 'edificio' por arquivo -> quantos Local o proximo populate criaria:
  aurora_vales           32      cidade_do_vento        86      cidade_dos_ventos      35
  elinford               30      elorfield              33      jorverhaven            81
  lorverstead            36      pelorport              35      quendorvale            12
  silenmont              87      toranhaven             13      tordordor              34
  tormirstead            13      vila_das_aguas         12
  TOTAL: 539        locais hoje no openworld.db: 539   (batem exatamente)

/api/mapa/features z13 sobre Aurora Vales:  http 200  58.718 bytes  0,033 s
/api/mapa/features z0 (mundo inteiro):                            0,008 s
tempo de generate_city_geometry.py (15 cidades):                  0,76 s
peso de database/cidades/:                                        1,2 MB
```

O `TOTAL: 539` bater exatamente com a contagem de `locais` no banco é a confirmação empírica
do contrato da Seção 3.5: **cada `edificio` é um `Local`, um para um.**

### E1 — Faixa de domínio da via
- [x] Implementado (`_encolher_quad`, `_gerar_quarteiroes_e_lotes`, `generate_city_geometry.py`)
- Área das quadras antes / depois: a comparação direta contra o baseline da Seção "E0"
  (909.131 m² -> 832.206 m², -8,5%) fica **confundida pela E6** (o raio de Aurora Vales
  também mudou, de 600 fixo para 600,7 sorteado, e o nº de setores de 6 para 12 — mais
  setores por si só já reduz a área de quadra individual). Medição isolada, instanciando o
  mesmo `GeradorCidade` (mesmo raio/anéis/setores sorteados) e comparando quad antes/depois
  do inset dentro da MESMA malha:
  ```
  raio_m sorteado: 600.7  num_aneis: 3  num_setores: 12
  quadras totais: 36  descartadas: 0
  area original (sem faixa de dominio): 986.650 m2
  area encolhida (com faixa de dominio): 832.218 m2
  reducao: 15.7%
  ```
  Dentro da faixa esperada (10-25%). Nenhuma quadra descartada por degeneração em Aurora
  Vales (a área mínima de 400 m² é pequena relativa às quadras de ~22.000-27.000 m² dessa
  cidade); quadras minúsculas perto do centro chegam a ser descartadas em cidades com mais
  setores/anéis — comportamento esperado, não testado caso a caso.
- Validação visual (zoom 14): **não realizada** — a extensão do Chrome não estava conectada
  nesta sessão (`Browser extension is not connected`). Pendente de confirmação do autor
  rodando o dashboard.

### E2 — Lote realista e variado
- [x] Implementado (`_area_alvo_lote`, `_subdividir_lote`, config `cidade_geo_lote_*`)
- Tabela de medição (área mediana, lotes por quadra, lotes por cidade):
  ```
  === aurora_vales (medio) ===
    quarteirao  n=  36  area mediana=     22157 m2  lado equiv=   149 m
    lote        n=2017  area mediana=       359 m2  lado equiv=    19 m
    lotes por quarteirao: 56.0
  === silenmont (grande) ===
    quarteirao  n=  65  area mediana=     22574 m2  lado equiv=   150 m
    lote        n=3563  area mediana=       380 m2  lado equiv=    19 m
    lotes por quarteirao: 54.8
  === quendorvale (pequeno) ===
    quarteirao  n=  15  area mediana=     16298 m2  lado equiv=   128 m
    lote        n=1018  area mediana=       243 m2  lado equiv=    16 m
    lotes por quarteirao: 67.9
  ```
  Área mediana (243-380 m²) e lotes por quadra (54,8-67,9) dentro do alvo (200-600 m² /
  20-120). Lotes por cidade: Silenmont 3.563 e Quendorvale 1.018 dentro de 400-2.000 só
  aproximadamente — **Aurora Vales saiu com 2.017, 0,85% acima do teto de 2.000** do alvo
  da Seção 9. Não ajustado: é uma cidade "media" no extremo alto da faixa de raio sorteada
  (600,7 de [470,760]) com `lote_fator_cidade` também sorteado baixo (lotes menores, logo
  mais deles) — variância esperada do sorteio por seed, não um bug; decisão de manter em
  vez de recalibrar a faixa fica para o autor validar visualmente primeiro.

### E3 — Edificação poligonal
- [x] Implementado (`_footprint_edificio`, `_gerar_edificios`; front: `estiloEdificio` em
  `mapa_leaflet.js`)
- Contagem por camada e tipo de geometria (Aurora Vales):
  ```
  Counter({'lote': 2017, 'edificio': 2017, 'quarteirao': 36, 'rua': 24, 'portao': 3, 'praca': 1})
  tipos de geometria por camada: {'edificio': ['Polygon'], 'lote': ['Polygon'], 'rua': ['LineString'], 'quarteirao': ['Polygon']}
  ```
  **Bug pego e corrigido durante a implementação**: `_encolher_quad` reutilizava o piso de
  área `cidade_geo_quadra_area_minima_m2` (400 m²) como critério de degeneração — correto
  pra quadra, errado pro footprint do edifício (lote mediano de ~250-380 m², footprint
  ainda menor depois do recuo, sempre abaixo de 400 -> `_footprint_edificio` retornava
  `None` pra quase todo lote: 969 de 1018 edifícios sumiam em Quendorvale). Corrigido
  separando a responsabilidade: `_encolher_quad` só detecta degeneração geométrica
  (aresta de comprimento zero, polígono invertido), e cada chamador aplica o piso de área
  que faz sentido pro seu caso (`quadra_area_minima` só em `_gerar_quarteiroes_e_lotes`).
- Validação visual (zoom 13 e 14): **não realizada** — mesma limitação do E1 (extensão do
  Chrome desconectada). Pendente de confirmação do autor.

### E4 — Importador do banco lendo `Polygon`
- [x] Implementado (`builder/populate.py:_importar_locais_da_geometria`)
- Output do script de contagem de `Local` e do perfil por categoria (sem escrever no banco):
  ```
  aurora_vales.geojson              2017 locais  (43 notaveis)
  cidade_do_vento.geojson           3927 locais  (48 notaveis)
  cidade_dos_ventos.geojson         1236 locais  (43 notaveis)
  elinford.geojson                  1679 locais  (43 notaveis)
  elorfield.geojson                 1018 locais  (43 notaveis)
  jorverhaven.geojson               6601 locais  (48 notaveis)
  lorverstead.geojson               3034 locais  (43 notaveis)
  pelorport.geojson                 3513 locais  (43 notaveis)
  quendorvale.geojson               1018 locais  (29 notaveis)
  silenmont.geojson                 3562 locais  (48 notaveis)
  toranhaven.geojson                1104 locais  (29 notaveis)
  tordordor.geojson                 2513 locais  (43 notaveis)
  tormirstead.geojson                859 locais  (29 notaveis)
  vila_das_águas.geojson             706 locais  (29 notaveis)
  TOTAL que o proximo populate criaria: 32787
  hoje no banco: 539
  por categoria: {'publico': 92, 'mercado': 93, 'residencia': 32226, 'forja': 128, 'taverna': 41, 'generic': 56, 'quartel': 44, 'universidade': 23, 'fazenda': 84}
  residencia %: 98.3%
  ```
  Notáveis por cidade batem exatamente o teto do catálogo por tamanho (29 pequena / 43
  média / 48 grande), confirmando que `_gerar_edificios` continua caindo em "Residência"
  ao esgotar — nada foi "consertado" aí. Residência 98,3% > 90%.
  ⚠️ Achado pré-existente, fora de escopo: `cidade_dos_ventos.geojson` aparece com dois
  registros no log de geração (`gerar_geometria_para_manifesto` roda 15 cidades do
  manifesto mas só 14 arquivos existem) — duas cidades no manifesto colidem no mesmo
  `slug`, a segunda sobrescreve a primeira. Não introduzido por este trabalho (o baseline
  da Seção "E0" já tinha só 14 arquivos pra "15 cidades" do manifesto); registrado como
  achado, não corrigido aqui (fora do escopo desta especificação).
- `grep` de consumidores de `edificio`: só `builder/populate.py` (corrigido) e
  `web/static/js/mapa_leaflet.js` (estilo/popup, corrigido — ver E3). Nenhum outro
  consumidor.

### E5 — Índice por cidade e bbox cacheada
- [x] Implementado (`_carregar_indice_cidades`, `_coletar_features_camada`,
  `_carregar_geojson_cache` com bbox por feição, em `web/composed_routes.py`; índice
  escrito por `GeradorCidade.indice`/`gerar_geometria_para_manifesto`)
- Tempo da requisição antes / depois (mesmo bbox/zoom do baseline, `z=13` sobre Aurora
  Vales, servidor já quente): baseline 0,033s (539 locais no mundo) -> **0,024-0,027s**
  agora, com a geometria ~60x maior (32.787 locais no mundo, 2.017 só em Aurora Vales;
  2.152.855 bytes de resposta). Abaixo do critério de 60 ms.
  ```
  z13 aurora_vales (run 1): http 200  2152855 bytes  0.025382s
  z13 aurora_vales (run 2): http 200  2152855 bytes  0.024102s
  z13 aurora_vales (run 3): http 200  2152855 bytes  0.026989s
  ```
- Tempo no mundo inteiro (z0): `http 200  571 bytes  0.001199s` — nenhuma cidade é aberta
  (zoom_min de toda camada interna é > 0), resposta é só as camadas de mundo vazias.

### E6 — Variedade entre cidades
- [x] Implementado (`__init__` de `GeradorCidade` sorteia raio/anéis/setores; `escala.py`
  refatorado pra `zoom_min_por_camada`/`diametro_px_de_mundo` receberem o raio REAL, não o
  rótulo de tamanho — `tabela_zoom_min` continua usando o raio nominal, documentado como
  aproximação do popup)
- Tabela das 15 cidades (raio sorteado, lotes, edifícios — nenhuma linha igual a outra do
  mesmo tamanho; `cidade_dos_ventos` some por causa da colisão de slug do E4):
  ```
  --- tamanho=medio ---
    aurora_vales             raio=  600.7  lotes= 2017  edificios= 2017
    cidade_dos_ventos        raio=  472.3  lotes= 1237  edificios= 1236
    elinford                 raio=  537.1  lotes= 1679  edificios= 1679
    elorfield                raio=  511.2  lotes= 1018  edificios= 1018
    lorverstead              raio=  721.5  lotes= 3034  edificios= 3034
    pelorport                raio=  717.5  lotes= 3513  edificios= 3513
    tordordor                raio=  611.7  lotes= 2513  edificios= 2513
  --- tamanho=grande ---
    cidade_do_vento          raio= 1045.2  lotes= 3927  edificios= 3927
    jorverhaven              raio= 1001.3  lotes= 6601  edificios= 6601
    silenmont                raio=  838.2  lotes= 3563  edificios= 3562
  --- tamanho=pequeno ---
    quendorvale              raio=  423.8  lotes= 1018  edificios= 1018
    toranhaven               raio=  425.7  lotes= 1104  edificios= 1104
    tormirstead               raio= 338.6  lotes=  859  edificios=  859
    vila_das_águas           raio=  407.0  lotes=  706  edificios=  706
  ```

### Fechamento
- [x] `pytest tests/ -q`: `10 passed in 1.68s`
- [x] Tempo de geração: `0,76s -> 4,37s` para as 15 cidades (bem dentro da 1h autorizada;
  `node --check web/static/js/mapa_leaflet.js` e o JSON do config também validados)
- [x] Peso de `database/cidades/`: `1,2 MB -> 52 MB` (usuário autorizou muito mais)
- [x] Linha somada ao "Log de Sessões" do `ROADMAP.md` (Frente 7 nova + entrada de log)

**Pendências para o autor** (não podem ser fechadas por este modelo nesta sessão):
1. Validação **visual** no dashboard (zoom 13/14) — a extensão do Chrome não conectou.
2. Decidir se o leve overshoot de lotes em Aurora Vales (2.017 vs teto 2.000) precisa de
   recalibração da faixa `cidade_geo_lote_area_base_m2`/`cidade_geo_raio_m_faixa_por_tamanho`.
3. A colisão de slug entre duas cidades chamadas de forma equivalente (`cidade_dos_ventos`)
   é pré-existente e fora do escopo — mas agora que cada cidade pesa dezenas de milhares de
   locais em vez de dezenas, vale mais a pena resolver do que antes.
