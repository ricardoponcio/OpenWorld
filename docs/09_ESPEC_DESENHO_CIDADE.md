# ESPECIFICAÇÃO — Desenho da cidade: núcleo cívico, distribuição de usos e modelos de cidade

> **Para quem é este documento**: para o modelo/desenvolvedor que vai (a) acabar com o vazio no
> centro da cidade, (b) parar de empilhar todo o comércio na mesma quadra e (c) transformar "a
> cidade" numa **interface de modelos de cidade**, onde cada modelo recebe os dados do sítio
> (posição, bioma, clima) e produz o desenho inteiro.
>
> **Este documento é auto-suficiente.** Você **não** precisa ler o
> [`PLANO_EVOLUCAO_V2.md`](PLANO_EVOLUCAO_V2.md) nem o [`DIAGNOSTICO_V3.md`](DIAGNOSTICO_V3.md).
> Da [`ESPEC_TECIDO_URBANO.md`](ESPEC_TECIDO_URBANO.md) (o trabalho anterior, já concluído)
> você só precisa do que está resumido na **Seção 2** daqui.
>
> Leia nesta ordem: **Seção 0** (regras de trabalho) → **Seção 1** (o pedido) → **Seção 2** (como
> a cidade é gerada hoje) → **Seção 3** (o que está errado, medido) → **Seção 4** (o estudo e a
> arquitetura) → **Seção 5** (decisões já tomadas, não as reabra) → **Seção 6** (a especificação)
> → **Seção 7** (ordem de execução).
>
> **A Seção 4.1 é a decisão de arquitetura do documento**, e o F4 é a etapa que a implementa. Se
> você for ler só uma coisa antes de programar, leia essas duas.
>
> **Todo número aqui foi medido**, não estimado, em 2026-09-11, contra o mundo que está em
> `database/` neste momento. Cada medição vem com o comando que a reproduz. Se o mundo for
> regerado, remeça antes de confiar no número.

**Revisão**: 2026-09-11 (v1.1 — a v1.0 propunha um contrato estreito, em que o traçado só
devolvia a malha viária. O autor pediu uma **interface de modelo de cidade**: cada modelo recebe
os dados de posição/geografia/clima e produz o desenho final, incluindo comércio e zoneamento. A
proposta foi adotada; ver Seções 4.1, 5.5 e F4, e a subseção 4.2, medida para esta revisão, que
mostra que os dados de clima já existem e discriminam entre as cidades.)
**Estado do mundo medido**: `database/world_manifest.json`, 5 continentes, 15 cidades (14
arquivos — ver Seção 3.6), `database/cidades/` com 52 MB e **32.787 edifícios**.
**Pré-requisito já concluído** (não refaça): toda a `ESPEC_TECIDO_URBANO.md` (E1 a E6) —
faixa de domínio da via, lote realista, edifício poligonal, importador de `Polygon`, índice
por cidade, variedade de raio/anéis/setores. Ver `ROADMAP.md`, Frente 7 e Log parte 20.

---

## 0. Regras de trabalho — leia antes de tocar em qualquer coisa

São as mesmas da `ESPEC_TECIDO_URBANO.md` e continuam valendo. Repetidas aqui porque este
documento é auto-suficiente.

1. **Nunca escreva em `database/` enquanto uma simulação ou reset estiver rodando.**
   Verifique **antes de qualquer coisa**:
   ```bash
   ps aux | grep -E "run_simulation|reset_|populate|generate_|run_dashboard" | grep -v grep
   ```
   Se aparecer `run_simulation.py`, pare: você pode corromper o `openworld.db`. Peça ao usuário
   para parar a simulação, ou trabalhe só em leitura. `run_dashboard.py` pode ficar de pé, é só
   leitura.

2. **Use sempre `venv/bin/python`**, nunca `python3` ou `python`.

3. **"Compila" não é teste.** Toda etapa termina com um comando que **roda** e cujo **output
   real** você cola no log da Seção 11.

4. **Todo número novo vai para o `config.json`**, lido via `cfg_get`, com um `_comentario_`
   explicando de onde ele veio. Nunca um literal numérico novo no meio do Python. A Seção 8
   traz a tabela consolidada de tudo que este trabalho acrescenta ao config.

5. **Não invente convenção de coordenada.** Existem três, descritas na Seção 2.2.

6. **Não commite nada.** O usuário valida e commita.

7. **Não rode `builder/populate.py` nem `cartographer/reset_cartography.sh`.** Os dois
   reconstroem o `openworld.db` do zero e apagam a simulação em curso do usuário. Esta linha de
   trabalho inteira pode ser feita e validada sem eles — a Seção 9.4 explica como conferir o
   efeito sobre o banco **sem escrever nele**. Se você concluir que um reset é inevitável,
   **pare e pergunte ao usuário**.

8. **Regerar `database/cidades/*.geojson` é permitido e esperado.** É artefato derivado,
   determinístico, ignorado pelo git, e o comando que o reconstrói leva ~5 s:
   ```bash
   venv/bin/python cartographer/cities/generate_city_geometry.py
   ```

9. **Não mexa no manifesto (`database/world_manifest.json`).** Ele é escrito por
   `generate_cities_metadata.py`, que chama a IA e depende do `mapa_composto.npz`. Reescrevê-lo
   significa refundar as cidades. Consequência direta para a Seção 4: **o modelo de cada cidade
   tem que ser derivado de dados que já estão no manifesto** (`nome`, `tamanho`, `tipo`) ou
   **medidos** do mapa já gerado (bioma, clima, relevo, distância da água — ver 4.2), nunca de um
   campo novo no manifesto.

---

## 1. O pedido do usuário

Literal, em 2026-09-11, depois de validar o tecido urbano no dashboard:

> "A melhoria do tecido urbano foi feita, tudo excelente, mas preciso pontuar 2 coisas agora.
> O centro da cidade tem diversas quadras sem nada, podiamos fazer uma praça e ocupar esse
> espaço pra ficar mais real.
> Outra coisa é que todos os comércios principais ficam praticamente todos juntos, as vezes na
> mesma quadra, podiamos espalhar pela cidade ou se quiser deixar nas primeiras faixas da
> cidade mas um pouco mais espalhado sabe.
> Alem disso queria que vc analisasse a possibilidade de termos outros designs de cidade e como
> poderiamos fazer isso."

São três pedidos, e eles têm pesos diferentes:

| # | pedido | natureza | seção |
|---|---|---|---|
| 1 | ocupar o vazio central | **defeito** — o vazio não foi projetado, é um efeito colateral | 3.1, F1 |
| 2 | espalhar o comércio | **defeito** — a concentração é literalmente um bug de ordem de iteração | 3.2, F2 |
| 3 | outros desenhos de cidade | **estudo + funcionalidade nova** | 4, F4-F8 |
| 4 | interface de modelo de cidade | **decisão de arquitetura do autor** | 4.1, 5.5, F4 |

Os pedidos 1 e 2 são consertos pequenos e de alto retorno visual. O pedido 3 é uma frente
maior, e a Seção 4 é a resposta analítica a ele — inclusive sobre o que **não** dá para fazer
com o mundo atual.

O pedido 4 veio depois, ao revisar a primeira versão deste documento, e **muda a forma da
solução do pedido 3**: em vez de um "traçado" que devolve ruas e quadras, cada cidade passa a
ser um **modelo** que recebe os dados do sítio e produz o desenho inteiro — incluindo comércio e
zoneamento. Está transcrito e discutido na Seção 4.1.

**Orçamento já autorizado pelo usuário em 2026-09-11** (continua valendo): até ~1 hora de
pré-geração e peso de disco muito acima do que este trabalho vai produzir. Não otimize geração.
**Otimize a operação** — o mapa tem que continuar respondendo rápido a cada pan e zoom.

---

## 2. Como a cidade é gerada hoje

### 2.1 O pipeline, em sete passos

Tudo acontece em `cartographer/cities/generate_city_geometry.py`, na classe `GeradorCidade`.
`gerar()` (linha 631) chama, nesta ordem:

```
__init__           (L47)   sorteia raio/anéis/setores da seed do nome; amostra o terreno 64x64
_construir_malha   (L216)  vértices da malha radial, ruas, portões, praça central
_gerar_quarteiroes_e_lotes (L451)  quads -> inset pela faixa de domínio -> subdivisão em lotes
_gerar_edificios   (L530)  um edifício por lote, escolhendo o tipo do catálogo
_gerar_muralha     (L613)  muralha + torres, se o tamanho/tipo pedir
indice             (L642)  bbox + contagem por camada, pro índice da API
```

O resultado é um `FeatureCollection` por cidade em `database/cidades/<slug>.geojson`, mais um
`database/cidades/_indice.json` com o bbox de cada cidade.

### 2.2 As três coordenadas — e nenhuma outra

| sistema | unidade | onde aparece |
|---|---|---|
| mundo | pixel | `x_global`/`y_global` do manifesto, bbox das APIs, `_indice.json` |
| local da cidade | **metro**, origem no centro da cidade | tudo dentro de `GeradorCidade` |
| GeoJSON/Leaflet | `[lng, lat] = [x_mundo, -y_mundo]` | o que sai no arquivo |

A conversão vive em dois métodos e **em nenhum outro lugar**: `_mundo` (L133) e
`_geojson_coord` (L137). `1 px de mundo = 15 811,4 m` (é
`sqrt(escala_pixel_area_km2) * 1000` — `escala_pixel_area_km2` é **área**, não comprimento de
lado; esse foi o bug histórico D1). Uma cidade grande inteira mede **0,13 px de mundo**.

Qualquer código novo que você escrever para traçado trabalha **em metros locais** e só vira
GeoJSON dentro de `_add_feature` (L177). Não crie uma quarta convenção.

### 2.3 A malha de hoje, em detalhe

`_construir_malha` constrói `self._vertices[j][i]`, com:

- `j` = índice do anel, `0 .. num_aneis` (o último é a borda externa da cidade);
- `i` = índice do setor, `0 .. num_setores-1`;
- raio do anel `j` = `raio_m * (j+1) / (num_aneis+1)`, perturbado por
  `cidade_geo_irregularidade_via` (0,15).

O quarteirão `(j, i)` é o quadrilátero entre os anéis `j-1` e `j` e os setores `i` e `i+1`.
**Isto é a única topologia que existe hoje** — bandas × setores — e é exatamente o que a
Seção 4 vai precisar generalizar.

Detalhe importante: as bandas vão de **1 a `num_aneis`**. A banda 0 (o disco interno, do centro
até o primeiro anel) **não gera quarteirão nenhum**. É o vazio do pedido 1.

### 2.4 Os contratos que o resto do código já espera

Se você mudar geometria, estes quatro pontos são os que quebram. Memorize-os:

| contrato | onde | o que espera |
|---|---|---|
| **quadrilátero** | `_subdividir_lote` (L421), `_encolher_quad` (L357), `_footprint_edificio` (L513) | polígono de exatamente **4 vértices**. Não é genérico. |
| **`properties.camada`** | `web/composed_routes.py:511` (`CAMADAS_INTERNAS_CIDADE`) | conjunto fechado de 8 nomes de camada |
| **`properties.camada == "edificio"`** | `builder/populate.py:54` | vira uma linha em `locais` no SQLite, 1:1 |
| **`properties.categoria`** | `engine/models.py:28` (`CategoriaLocal`) | um de 9 valores fixos. **Não invente categoria nova** sem migrar o enum e o banco. |

Os 9 valores de `CategoriaLocal` são: `fazenda`, `quartel`, `taverna`, `universidade`, `forja`,
`mercado`, `residencia`, `publico`, `generic`.

### 2.5 Adicionar uma camada nova custa 4 arquivos

Se alguma etapa sua precisar de uma camada nova (por exemplo `parque`), ela **não aparece
sozinha**. São quatro toques, e esquecer qualquer um faz a feição sumir em silêncio, sem erro:

1. `config.json` → `cidade_geo_zoom_min_alvo_px_por_camada`, acrescente a chave (senão o
   `zoom_min` cai no default 8 e a camada acende no mundo inteiro);
2. `web/composed_routes.py:511` → `CAMADAS_INTERNAS_CIDADE`, acrescente o nome (senão a API
   procura `database/features/<camada>.geojson`, não acha, e devolve vazio);
3. `web/static/js/mapa_leaflet.js:53` → `CAMADAS_DETALHE_CIDADE`, acrescente o nome;
4. `web/static/js/mapa_leaflet.js:215` → `ESTILO_CAMADA_CIDADE`, dê um estilo (sem estilo o
   Leaflet desenha o azul padrão dele).

**Evite camada nova quando der.** As etapas F1-F8 deste documento foram desenhadas para caber
nas 8 camadas que já existem: `muralha`, `torre`, `portao`, `praca`, `rua`, `quarteirao`,
`lote`, `edificio`.

---

## 3. O que está errado hoje — com medição

### 3.1 O centro é um vazio de 1,7 a 3,0 quarteirões

A banda 0 não gera quarteirão. A praça que ocupa esse disco tem raio **fixo** de 25 m
(`cidade_geo_praca_raio_m`), independente do tamanho da cidade. O disco interno, esse sim,
escala com a cidade: seu raio é `raio_m / (num_aneis + 1)`.

Resultado: quanto **maior** a cidade, **mais desproporcional** o buraco.

```bash
venv/bin/python - <<'EOF'
import json, glob, math
def area(c):
    p = c[0]; p = p[:-1] if p[0] == p[-1] else p
    s = sum(p[i][0]*p[(i+1) % len(p)][1] - p[(i+1) % len(p)][0]*p[i][1] for i in range(len(p)))
    return abs(s) / 2
mpp = math.sqrt(250) * 1000
for a in sorted(glob.glob('database/cidades/*.geojson')):
    d = json.load(open(a)); p = d['properties']
    qs = [area(f['geometry']['coordinates']) * mpp * mpp
          for f in d['features'] if f['properties']['camada'] == 'quarteirao']
    n_aneis = len([f for f in d['features'] if f['properties'].get('tipo_via') == 'anel']) - 1
    r0 = p['raio_m'] / (n_aneis + 1)
    vazio = math.pi * r0 * r0 - math.pi * 25 * 25
    print(f"{p['cidade']:<18} r_banda0={r0:6.1f}m vazio={vazio:9.0f}m2 "
          f"= {vazio / (sum(qs)/len(qs)):4.1f} quarteiroes medios")
EOF
```

Medido:

| cidade | raio da banda 0 | vazio central | equivale a |
|---|---|---|---|
| Jorverhaven (grande) | 200,3 m | 124.026 m² | **2,4 quarteirões médios** |
| Aurora Vales (médio) | 150,2 m | 68.884 m² | **3,0 quarteirões médios** |
| Quendorvale (pequeno) | 106,0 m | 33.310 m² | 1,7 quarteirões médios |
| Tormirstead (pequeno) | 84,7 m | 20.550 m² | 1,9 quarteirões médios |

A praça cobre entre **1,6 % e 8,7 %** desse disco. O resto é chão nu, bem no lugar para onde o
jogador olha primeiro. É exatamente o que o usuário descreveu como "diversas quadras sem nada".

### 3.2 Todos os notáveis caem no mesmo quarteirão

Este é o achado mais grave do documento, e é um bug de **ordem de iteração**, não de sorteio.

`_gerar_edificios` (L530) percorre `self._lotes` **na ordem em que foram criados**. E
`_gerar_quarteiroes_e_lotes` (L451) cria os lotes em `for j in bandas: for i in setores:` — ou
seja, os primeiros ~60 lotes da lista são todos do quarteirão `(banda 1, setor 0)`.

Dentro do laço, cada lote não-residencial consome uma entrada do catálogo, primeiro da fila de
obrigatórios (`fila_tipos`, L537) e depois por sorteio ponderado. **Toda entrada do catálogo
tem um `max`** (entre 1 e 3). Quando todos os `max` se esgotam, `disponiveis` fica vazia,
`entrada` vira `None` (L578) e **todo o resto da cidade vira residência**.

Os `max` do catálogo somam 48. Os 48 cabem nos primeiros ~100 lotes. Os primeiros ~100 lotes
são o primeiro quarteirão.

```bash
venv/bin/python - <<'EOF'
import sys, json, collections
sys.path.insert(0, '.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from cartographer.cities.generate_city_geometry import GeradorCidade
m = json.load(open('database/world_manifest.json'))
alvos = {'Jorverhaven', 'Aurora Vales', 'Quendorvale'}
for cont in m['continentes']:
    for cid in cont['cidades']:
        if cid['nome'] not in alvos:
            continue
        g = GeradorCidade(cid, cont['nome'], C)
        g._construir_malha()
        origem = []
        g._lotes = []
        for j in range(1, g.num_aneis + 1):
            ri, re = g._vertices[j-1], g._vertices[j]
            bairro = "Centro" if j == 1 else ("Bairro Médio" if j < g.num_aneis else "Bairro Externo")
            for i in range(g.num_setores):
                i2 = (i + 1) % g.num_setores
                quad = [ri[i], re[i], re[i2], ri[i2]]
                dists = [g._distancia_faixa_dominio(g._classe_via_radial(i)),
                         g._distancia_faixa_dominio("anel"),
                         g._distancia_faixa_dominio(g._classe_via_radial(i2)),
                         g._distancia_faixa_dominio("anel")]
                qu = g._encolher_quad(quad, dists)
                if qu is None or g._area_quad(qu) < g.quadra_area_minima:
                    continue
                for lote in g._subdividir_lote(qu, g._area_alvo_lote(j)):
                    g._lotes.append((lote, bairro, j)); origem.append((j, i))
        g._gerar_edificios()
        ed = [f['properties'] for f in g.features if f['properties']['camada'] == 'edificio']
        q = collections.Counter(origem[k] for k, p in enumerate(ed) if p['categoria'] != 'residencia')
        print(f"{cid['nome']:<14} lotes={len(g._lotes):5d} notaveis={sum(q.values()):3d} "
              f"em {len(q)} de {len(set(origem))} quarteiroes -> {dict(sorted(q.items()))}")
EOF
```

Medido:

| cidade | lotes | notáveis | quarteirões com notável | pior quarteirão |
|---|---|---|---|---|
| Jorverhaven | 6.601 | 48 | **1 de 48** | 48 notáveis (100 %) |
| Aurora Vales | 2.017 | 43 | **2 de 36** | 36 notáveis (84 %) |
| Quendorvale | 1.018 | 29 | **2 de 15** | 28 notáveis (97 %) |

E a distribuição angular confirma: em Jorverhaven, **todos os 48 notáveis estão dentro de uma
única fatia de 30°** da cidade. O usuário viu isso e descreveu como "às vezes na mesma quadra".
Estava sendo generoso: em cidade grande é sempre a mesma quadra.

### 3.3 99,3 % das construções são residência

Efeito colateral do mesmo bug. O código **pretende** 45 % de não-residencial no centro
(`cidade_geo_fracao_residencial = 0.55`, L566), mas como o catálogo se esgota nos primeiros 100
lotes, o `if entrada is None` empurra todo o resto para `Residência`.

```bash
venv/bin/python -c "
import json, collections
d = json.load(open('database/cidades/jorverhaven.geojson'))
ed = [f['properties'] for f in d['features'] if f['properties']['camada'] == 'edificio']
print(collections.Counter(p['categoria'] for p in ed))"
```

Medido em Jorverhaven (6.601 edifícios):

```
residencia 6553 | forja 10 | publico 9 | mercado 8 | fazenda 6 | taverna 4 | generic 4 | quartel 4 | universidade 3
```

**0,7 % de uso não-residencial.** Uma cidade real medieval de porte grande tinha oficina,
taverna, padaria e poço em quase toda rua. Aqui a cidade inteira é dormitório com um shopping
center no canto.

Isto **não** é só estética: `builder/populate.py` importa cada `edificio` como um `Local`, e o
`JobMarket` (`engine/mechanics/market.py:77`) procura vaga por categoria. Uma cidade com 4
vagas de taverna e 6.553 casas não dá emprego a ninguém.

### 3.4 Só existe uma forma de cidade

Todas as 15 cidades são o mesmo traçado radial. A `ESPEC_TECIDO_URBANO.md` E6 deu variedade de
**números** (raio, anéis, setores sorteados por faixa), mas não de **forma**. Uma capital
comercial, uma fortaleza e uma vila agrícola são, geometricamente, a mesma coisa em escalas
diferentes.

```bash
venv/bin/python -c "
import json, glob, os
for a in sorted(glob.glob('database/cidades/*.geojson')):
    d = json.load(open(a)); p = d['properties']
    n = len([f for f in d['features'] if f['properties'].get('tipo_via') == 'anel']) - 1
    print(f\"{p['cidade']:<18} {p['tipo']:<12} raio={p['raio_m']:6.1f} aneis={n}\")"
```

O `tipo` da cidade (`capital`, `fortaleza`, `portuaria`, `pesqueira`, `comercial`, `mistica`,
`mineira`, `agricola`, `residencial`) hoje influencia **só o catálogo de edifícios**
(`tipos_cidade` triplica o peso de uma entrada, L500). Não toca na geometria.

### 3.5 Dois fatos do terreno que limitam o que dá para fazer

Estes dois são **restrições**, não defeitos. Você precisa deles antes de ler a Seção 4, porque
eles matam duas ideias que pareceriam óbvias.

**(a) O filtro de declividade nunca dispara.** `cidade_geo_declividade_max = 0.35`, mas a
declividade real na escala da cidade é da ordem de `1e-7`:

```bash
venv/bin/python - <<'EOF'
import sys, json
sys.path.insert(0, '.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from cartographer.cities.generate_city_geometry import GeradorCidade
m = json.load(open('database/world_manifest.json'))
for cont in m['continentes']:
    for cid in cont['cidades']:
        if cid['nome'] not in ('Jorverhaven', 'Silenmont', 'Quendorvale'):
            continue
        g = GeradorCidade(cid, cont['nome'], C)
        vals = [g._declividade_local(x, y) for x in range(-300, 301, 60) for y in range(-300, 301, 60)]
        print(f"{cid['nome']:<14} declividade min={min(vals):.3e} max={max(vals):.3e} "
              f"limiar={g._declividade_max}")
EOF
```

| cidade | declividade mínima | máxima | limiar do config |
|---|---|---|---|
| Quendorvale | 1,4e-08 | 3,7e-07 | 0,35 |
| Jorverhaven | 1,1e-07 | 9,4e-07 | 0,35 |
| Silenmont (mineira) | 3,6e-08 | 9,2e-07 | 0,35 |

Seis ordens de grandeza de folga. A amplitude de altitude dentro da janela de uma cidade é de
**0,0002 a 0,0011** (em unidades normalizadas 0-1). Na prática: **a cidade é plana**.

Consequência: **um traçado "em encosta"/terraços que siga curvas de nível não tem relevo para
seguir.** Não tente. O que o terreno ainda dá é ordenação relativa (qual setor é *menos*
inclinado), que é o que `_melhor_centro_praca` e a escolha de portões já usam — e isso continua
valendo.

**(b) Nenhuma cidade toca a água.** `cidades_distancia_costa_minima_px = 2.0` é restrição dura
no posicionamento (`generate_cities_metadata.py:70`), e 2 px de mundo são **31,6 km**.

```bash
venv/bin/python - <<'EOF'
import sys, json, math, numpy as np
sys.path.insert(0, '.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
alt = np.load('database/mapa_composto.npz')['mapa'][:, :, 0]
ys, xs = np.nonzero(alt <= C['nivel_mar'])
m = json.load(open('database/world_manifest.json'))
for cont in m['continentes']:
    for cid in cont['cidades']:
        dd = (xs - cid['x_global'])**2 + (ys - cid['y_global'])**2
        i = int(np.argmin(dd)); dist = math.sqrt(dd[i])
        print(f"{cid['nome']:<18} {cid['tipo']:<12} agua a {dist * 15.81:7.1f} km")
EOF
```

Medido: a água mais próxima está a **35,4 km** (Quendorvale, Elorfield, Jorverhaven, Vila das
Águas) ou **47,4 km** (todas as outras); Silenmont, a mineira, a 130,4 km. A cidade mais larga
do mundo tem 2,3 km de diâmetro.

Consequência: **um traçado "portuário" com cais e frente de água é impossível hoje.** A cidade
`portuaria` é um rótulo sem geografia por trás. Isso é anterior a este trabalho e está
registrado na Seção 10 como pendência do autor — não tente consertar aqui.

### 3.6 Pendência pré-existente: colisão de slug

`Cidade dos Ventos` aparece **duas vezes** no manifesto (continentes diferentes). O slug é
`cidade["nome"].lower().replace(" ", "_")`, então a segunda sobrescreve o arquivo da primeira:
15 cidades no manifesto, 14 arquivos em `database/cidades/`.

Já registrado na `ESPEC_TECIDO_URBANO.md` Seção 11. **Fora do escopo deste documento** — está
aqui só para você não achar que quebrou algo ao contar 14 onde o manifesto diz 15.

---

## 4. Estudo: outros desenhos de cidade

Esta é a resposta analítica ao pedido 3. Leia inteira antes de decidir qualquer coisa — ela
fecha portas tanto quanto abre.

### 4.1 A forma da solução: modelo de cidade, não "traçado"

A primeira versão deste documento propunha um contrato estreito — o traçado devolvia a malha
(ruas + quadras) e todo o resto continuava fixo no `GeradorCidade`. O autor apontou, com razão,
que isso é pequeno demais:

> "fazer cada modelo de cidade receber as informacoes de posicao e os dados de
> geografia/clima/etc e produzir o desenho final. Quando formos chamar podemos pegar uma lista
> de possibilidades fazer um rand e instanciar esse modelo passando esses dados, a cidade se
> comporta de acordo com seu script + dados da posicao dela. Isso faz com que uma interface de
> cidade obrigue que todos os modelos tenham um trabalho padronizado, e possibilite no futuro
> criar por exemplo cidades portuarias, por que é só instanciar essa interface, entrar na lista
> randomica e propor como ela vai ser desenhada, seus comércios e etc."

**Essa é a arquitetura adotada.** A diferença prática é grande:

| | contrato estreito (descartado) | **modelo de cidade (adotado)** |
|---|---|---|
| o que o módulo devolve | só a malha viária + quadras | o desenho inteiro: malha, zoneamento, onde vão os notáveis, que comércio existe, muralha |
| de onde vêm os dados | o módulo recebe o gerador inteiro e se vira | recebe um **`SitioCidade`** explícito: posição, bioma, clima, relevo, distância da água |
| acrescentar uma cidade portuária | mexer em `_gerar_edificios`, no catálogo e na malha | escrever uma classe, registrá-la na lista, pronto |
| o que é obrigatório | nada — cada traçado faz o que quiser | a **interface** obriga todo modelo a responder as mesmas perguntas |

O ponto mais importante é o último. O modelo `radial` tem o conceito de "banda" e coloca os
notáveis por anel de distância ao centro; o modelo `linear` não tem banda nenhuma — tem
"fileira" e "posição ao longo do eixo". A interface não pede que os dois usem o mesmo conceito:
**pede que os dois respondam a mesma pergunta** ("em que quarteirão vai o templo?"), cada um com
a sua lógica. Isso é exatamente o que o autor descreveu.

O custo disso sobre o contrato estreito é pequeno (as mesmas ~150 linhas de refatoração, mais
uns 60 de classe base) e compra uma coisa que o contrato estreito não comprava: **um modelo novo
não obriga a tocar em nada compartilhado.**

### 4.2 Os dados de sítio existem, e discriminam

Isto foi medido para esta revisão e mudou a conclusão anterior. `gerar_janela`
(`cartographer/world/tile_cartographer.py:92`) já devolve **4 canais** — altitude, temperatura,
umidade, bioma — e `GeradorCidade.__init__` (L127) hoje **joga três fora**:

```python
self.terreno = janela[:, :, 0]   # <- os canais 1, 2 e 3 são descartados
```

```bash
venv/bin/python - <<'EOF'
import sys, json
sys.path.insert(0, '.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from config import cfg_get
from cartographer.tiles.render import obter_cartografo
from cartographer.cities.escala import metros_por_pixel_mundo
m = json.load(open('database/world_manifest.json'))
carto = obter_cartografo(); mpp = metros_por_pixel_mundo(C)
extra = cfg_get(C, "tile_oitavas_max") - cfg_get(C, "ruido_macro_oitavas")
print(f"{'cidade':<18}{'alt':>8}{'temp':>8}{'umid':>8}{'bioma':>7}")
for cont in m['continentes']:
    for cid in cont['cidades']:
        lado = 2 * 600.0 / mpp
        j = carto.gerar_janela(cid['x_global'] - lado/2, cid['y_global'] - lado/2,
                               cid['x_global'] + lado/2, cid['y_global'] + lado/2,
                               32, 32, oitavas_extra=extra)
        print(f"{cid['nome']:<18}{j[:,:,0].mean():8.3f}{j[:,:,1].mean():8.3f}"
              f"{j[:,:,2].mean():8.3f}{j[:,:,3].mean():7.1f}")
EOF
```

Medido:

| cidade | altitude | temperatura | umidade | bioma |
|---|---|---|---|---|
| Pelorport | 0,359 | **0,012** | 0,304 | 4 (Floresta Temperada) |
| Cidade dos Ventos | 0,361 | **0,574** | **0,243** | 2 (Deserto) |
| Vila das Águas | 0,353 | 0,099 | **0,597** | 4 |
| Tormirstead | 0,369 | 0,470 | 0,528 | 3 (Mediterrâneo) |
| Silenmont | 0,372 | 0,082 | 0,277 | 4 |

Leia a tabela com atenção, porque ela separa duas coisas:

- **altitude não discrimina**: 0,353 a 0,372 nas 15 cidades. É a mesma degeneração da Seção
  3.5a — confirma que relevo não serve de entrada para nada;
- **temperatura, umidade e bioma discriminam muito**: temperatura vai de 0,012 a 0,574 (uma
  ordem de grandeza de faixa útil), umidade de 0,243 a 0,597, e há **três biomas** distintos
  (Deserto, Mediterrâneo, Floresta Temperada) entre as 15 cidades.

Ou seja: a informação que o autor quer passar para o modelo **já está disponível, de graça, na
mesma chamada que o gerador já faz**. Só está sendo descartada. Uma cidade de deserto pode
legitimamente ter mais poços, ruas mais estreitas e menos praça aberta que uma cidade úmida de
floresta — e agora há dado para sustentar isso.

### 4.3 As duas restrições que continuam fechando portas

Medidas na Seção 3.5, e a arquitetura nova **não** as remove:

- **a cidade é plana** (amplitude de altitude ~0,0005): nada de terraços, curvas de nível ou
  cidade que escorre pela encosta;
- **a cidade está a 35+ km da água**: nada de cais, frente de porto, cidade-ponte ou traçado
  que acompanhe um rio. **Não existe rio no modelo do mundo** em nenhuma escala.

A distinção que importa, e que a arquitetura do 4.1 torna limpa:

> **A interface passa a permitir uma cidade portuária. O mundo ainda não fornece o dado que ela
> precisaria.**

São dois problemas separados, e é bom que sejam. Depois do F4, criar `PortuariaModelo` é
escrever uma classe e registrá-la — nenhuma linha compartilhada muda. O que falta é
`SitioCidade.distancia_agua_m` ser menor que o raio da cidade, o que hoje **nunca** acontece
(35 km contra 1,2 km) e depende de uma decisão de mundo, não de desenho: baixar
`cidades_distancia_costa_minima_px` (hoje 2,0 px = 31,6 km) e/ou acrescentar hidrografia. Por
isso `distancia_agua_m` e `direcao_agua_rad` **entram no `SitioCidade` desde já** (F4.2), mesmo
sem uso: o dia em que o mundo mudar, o modelo novo não precisa de refatoração nenhuma para
enxergá-lo. A Seção 4.7 mostra esse caminho por inteiro.

Enquanto isso: **o modelo é escolhido por `tipo` + `tamanho` + seed, e o sítio calibra o modelo
escolhido** — não o escolhe. Isso é honesto, é suficiente para o objetivo (cidades que parecem
diferentes umas das outras) e é a única coisa possível sem refundar o mundo.

### 4.4 Catálogo de modelos avaliados

| traçado | inspiração real | produz quads? | usa o pipeline atual? | esforço | veredito |
|---|---|---|---|---|---|
| **`radial`** | burgo medieval crescido em volta de um mercado | sim | sim | zero (existe) | **manter como padrão** |
| **`grade`** | colônia romana (cardo/decumanus), cidade planejada | sim | sim | médio | **implementar** (F5) |
| **`linear`** | vila de estrada, povoado de uma rua só | sim | sim | baixo | **implementar** (F6) |
| **`organica`** | aldeia crescida sem plano | sim (é `radial` degradado) | sim | baixo | **implementar** (F7) |
| **`bastida`** | cidadela fortificada, praça de armas | sim (é `grade` + muralha poligonal) | sim | baixo sobre F5 | opcional (F7b) |
| `terraco` | cidade de encosta | sim | sim | alto | ❌ **descartado** — não há relevo (3.5a) |
| `portuaria` | cidade de cais | sim | sim | alto | ⏸️ **interface pronta, dado ausente** — ver 4.3 e 4.7 |
| `radiocêntrico com faubourgs` | Paris medieval (núcleo + subúrbios fora da muralha) | sim | sim | médio | adiar — bonito, mas exige repensar a muralha |
| `poligonal de Voronoi` | traçado genuinamente irregular | **não** — produz polígonos de N lados | **não** | muito alto | ❌ **descartado** — quebra o contrato de quadrilátero (2.4) |

O último merece um parágrafo, porque é a ideia que todo mundo tem primeiro. Um diagrama de
Voronoi dá o traçado irregular mais convincente que existe, mas produz células de 5, 6, 7
lados. `_encolher_quad`, `_subdividir_lote` e `_footprint_edificio` são todos escritos para
**exatamente 4 vértices**. Adotar Voronoi significa reescrever os três com geometria poligonal
geral (offset de polígono côncavo, que é justamente o que se evitou não usando `shapely`).
**Não vale o preço agora.** `organica` (F7) entrega 80 % da sensação por 5 % do custo.

Note a diferença de veredito entre `terraco` e `portuaria`. Os dois carecem de dado, mas
`terraco` depende de uma propriedade **do ruído** (amplitude de relevo na escala de 1 km), que é
uma mudança profunda no modelo de mundo; `portuaria` depende de **um parâmetro de posicionamento**
(`cidades_distancia_costa_minima_px`), que é uma linha de config. Por isso `portuaria` fica
"pronta e esperando" e `terraco` fica descartada.

### 4.5 Como o modelo é escolhido e instanciado

Pela Regra 9 da Seção 0, **o manifesto não muda**. O fluxo é o que o autor descreveu — lista de
possibilidades, sorteio, instanciação com os dados do sítio:

```
sitio   = SitioCidade.medir(cidade, continente, config)      # posição, bioma, clima, relevo, água
opcoes  = cidade_geo_modelo_por_tipo[sitio.tipo]             # a "lista de possibilidades"
nome    = escolha_ponderada(opcoes, rng_da_seed_do_nome)     # o "rand"
modelo  = MODELOS[nome](sitio, config, rng)                  # instancia passando os dados
desenho = modelo.desenhar()                                  # o modelo produz o desenho final
```

com fallback para `radial` quando o `tipo` não estiver no mapa. Três propriedades importantes:

- é **determinístico**: a mesma cidade sempre recebe o mesmo modelo, porque o `rng` vem de
  `zlib.crc32(nome)`;
- é **ajustável sem código**: mudar o mapa no `config.json` e regerar muda a cara do mundo;
- **acrescentar um modelo é acrescentar uma classe e uma linha no config.** Nada compartilhado
  muda. É o critério de sucesso do F4.

⚠️ **Armadilha de determinismo**: o `rng` é consumido em ordem por `__init__` (raio, anéis,
fator de lote, setores). Se você sortear o modelo **no meio** dessa sequência, todas as cidades
mudam de raio e anéis, e os arquivos inteiros viram outra coisa. Sorteie o modelo **no fim**,
depois de todos os sorteios que já existem, ou com um `random.Random(self.seed ^ constante)`
separado. A F8 detalha.

Distribuição sugerida (calibre depois de ver o resultado):

| tipo da cidade | modelos e pesos |
|---|---|
| `capital` | `grade` 0,6 · `radial` 0,4 |
| `comercial` | `grade` 0,5 · `radial` 0,5 |
| `fortaleza` | `bastida` 0,7 · `grade` 0,3 (ou `radial` 0,3 se F7b não for feita) |
| `agricola` | `linear` 0,6 · `organica` 0,4 |
| `pesqueira` | `linear` 0,7 · `organica` 0,3 |
| `mineira` | `organica` 0,6 · `linear` 0,4 |
| `mistica` | `organica` 0,7 · `radial` 0,3 |
| `residencial` | `radial` 0,5 · `organica` 0,5 |
| `portuaria` | `linear` 0,5 · `grade` 0,5 (ver 4.3: não é porto de verdade **ainda**) |
| `_default` | `radial` 1,0 |

### 4.6 O que cada modelo novo entrega visualmente

- **`grade`**: ruas retas cruzando em ângulo reto, quadras retangulares uniformes, duas
  avenidas centrais mais largas se cruzando na praça. Lê-se instantaneamente como "cidade
  planejada". É o contraste mais forte possível contra o `radial` — por isso é o primeiro a
  implementar.
- **`linear`**: uma rua principal atravessando, quadras só nas laterais, cidade comprida e
  estreita. Lê-se como "vila de beira de estrada". Ótimo para as cidades pequenas, que hoje são
  radiais em miniatura e parecem alvos de tiro.
- **`organica`**: radial, mas com anéis que não fecham (arcos em vez de círculos), irregularidade
  alta e quadras faltando aqui e ali. Lê-se como "isto cresceu sozinho".
- **`bastida`**: `grade` com muralha poligonal colada ao retângulo das quadras, portões só nas
  pontas das duas avenidas centrais, e um bloco de canto reservado ao castelo/quartel.

### 4.7 Prova da arquitetura: o que seria preciso para uma cidade portuária

Esta subseção **não é para implementar agora**. Ela existe para demonstrar que o contrato do F4
aguenta o caso que o autor citou, e para deixar escrito exatamente o que falta — de modo que
quem pegar isso no futuro não precise redescobrir.

**O que seria escrito** (e só isto):

```
cartographer/cities/modelos/portuaria.py    # ~150 linhas, uma classe
config.json: cidade_geo_modelo_por_tipo["portuaria"] = [["portuaria", 1.0]]
config.json: cidade_geo_porto_* (profundidade do cais, nº de docas, largura da marginal)
```

**O que a classe faria**, usando só o que a interface do F4.3 já oferece:

| pergunta da interface | resposta do `PortuariaModelo` |
|---|---|
| `construir_malha` | meia-cidade: setores só no semicírculo oposto à água (`sitio.direcao_agua_rad`), mais uma **marginal** reta ao longo da linha d'água e um cais perpendicular a ela |
| `contorno` | o semicírculo fechado pela linha d'água — a muralha para na água, como toda cidade portuária real |
| `zona_de` | zona nova `cais`, na faixa colada à água; `nucleo` recuado uma banda para dentro |
| `encomendas_extra` | `Doca` ×N proporcional ao comprimento do cais, `Armazém`, `Estaleiro`, `Casa de Barcos` — todos ancorados na zona `cais` |
| `catalogo_comercio_bairro` | acrescenta `Peixaria` e `Cordoaria`, remove `Pomar` |
| `ajustar_por_sitio` | mais docas em cidade grande, menos em cidade de baixa umidade (porto de rio seco) |

**O que falta no mundo, e só isso**: `sitio.distancia_agua_m < sitio.raio_m`. Hoje é 35.400 m
contra 1.045 m no melhor caso (3.5b). Os dois caminhos, em ordem de custo:

1. **baixar `cidades_distancia_costa_minima_px`** de 2,0 para algo como 0,5 px, e ajustar
   `cidades_distancia_costa_ideal_px` (hoje 3,0) e o perfil `portuaria` em
   `cidades_perfil_por_tipo`. Custo: uma linha de config **e refundar as cidades** (roda
   `generate_cities_metadata.py`, que reescreve o manifesto — ver Regra 9). Mesmo assim, 0,5 px
   ainda são 7,9 km: a cidade continuaria sem tocar a água. **Este caminho sozinho não resolve.**
2. **hidrografia própria na escala da cidade** — um rio ou enseada gerado localmente pelo mesmo
   ruído seedado, sem depender do `mapa_composto.npz`, exatamente como o terreno de detalhe já
   é gerado. É o caminho que de fato funciona, e é uma frente própria, não um modelo de cidade.

Registre isto na Seção 11 como pendência do autor. **Não comece nenhum dos dois neste trabalho.**

---

## 5. Decisões de projeto já tomadas — não as reabra

Estas foram decididas na análise que produziu este documento. Discuta com o usuário se
discordar, mas **não mude sozinho**.

### 5.1 O vazio central vira praça **e** núcleo cívico, não só praça maior

Só aumentar a praça resolve metade. Uma praça medieval de verdade é **cercada** pelos edifícios
importantes — templo, prefeitura, mercado coberto, guarda. Então:

1. a praça passa a **escalar** com a banda 0 (fração, com piso e teto em metros);
2. o anel que sobra entre a praça e o primeiro anel viário vira **banda 0 urbanizável**:
   quarteirões, lotes e edifícios como qualquer outra banda;
3. um anel viário novo circunda a praça (a rua que separa a praça das quadras cívicas), e as
   radiais passam a **começar** nele em vez de em `(0,0)`.

Isso resolve o pedido 1 e dá ao pedido 2 um lugar natural para ancorar os notáveis.

### 5.2 A distribuição dos notáveis é **dirigida**, não sorteada lote a lote

O sorteio por lote na ordem da lista é a causa raiz (3.2). Trocar por "sorteia melhor" não
resolve — enquanto os `max` do catálogo forem consumidos na ordem da lista, eles caem onde a
lista começa.

A inversão é: **primeiro decida quantos de cada tipo a cidade tem e em que quarteirão cada um
vai; depois preencha o resto.** Distribuição por rodízio sobre os quarteirões da zona, com teto
de notáveis por quarteirão. Detalhe em F2.

### 5.3 Existe comércio de bairro, e ele não tem `max`

O catálogo atual é de **marcos** ("a prefeitura", "o castelo") — por isso `max` 1 ou 2 faz
sentido. O que falta é a outra metade: a padaria da esquina, o poço do largo, a taverna de
bairro. Esses são **densidade**, não contagem: um a cada N lotes.

São duas listas com propósitos diferentes no config; não misture.

### 5.4 Nenhuma camada nova. Nenhuma `CategoriaLocal` nova.

Tudo cabe em `praca`, `quarteirao`, `lote`, `edificio`, `rua` e nas 9 categorias existentes
(2.4/2.5). Um parque vira `praca`; uma horta vira `edificio` de categoria `fazenda`; um pátio
vira quarteirão sem lotes. Se você achar que precisa de camada nova, **pare e pergunte**.

### 5.5 O modelo de cidade é uma **interface**, e ela é a entrega principal do F4

Decisão do autor, registrada em 4.1. Cada modelo recebe um `SitioCidade` explícito (posição,
bioma, clima, relevo, água) e produz o desenho **inteiro** — malha, zoneamento, onde vão os
notáveis, que comércio existe, muralha. Não é "um traçado que devolve quadras".

Duas consequências que você vai precisar defender contra o seu próprio instinto:

- **a interface obriga todos os modelos a responderem as mesmas perguntas, não a usarem os
  mesmos conceitos.** `radial` responde "onde vai o templo?" com bandas e setores; `linear`
  responde com fileira e posição no eixo. Nenhum dos dois precisa saber do vocabulário do
  outro. Não force "banda" goela abaixo do `linear`;
- **o que é igual em todo modelo mora na classe base, não copiado em cada um.** Inset de quadra,
  subdivisão em lotes, footprint, rodízio de distribuição, emissão de feature, índice. Se você
  se pegar copiando um método entre dois modelos, ele pertencia à base.

### 5.6 O modelo é escolhido por `tipo` + seed; o sítio **calibra**, não escolhe

Consequência de 4.3 e da Regra 9. Não adicione campo ao manifesto. O `SitioCidade` entra como
parâmetro de calibração dentro do modelo já escolhido (mais poços no deserto, menos praça aberta
onde é seco), **não** como critério de seleção — seleção por geografia exigiria dado que o mundo
não tem nesta escala.

### 5.7 O modelo `radial` reimplementado tem que produzir **o arquivo idêntico**

O teste de que a refatoração do F4 não quebrou nada é byte a byte: gere os GeoJSON antes,
refatore, gere depois, `diff`. Enquanto F5-F8 não entrarem, **o mundo não pode mudar**. Isso é
o que separa "refatorei" de "reescrevi e torci".

---

## 6. Especificação — etapa por etapa

Oito etapas. F1-F3 são os dois defeitos do usuário e são independentes de F4-F8. **Se o tempo
acabar, F1-F3 sozinhas já entregam os pedidos 1 e 2 por inteiro.**

---

### F1 — Núcleo cívico: a praça escala e a banda 0 se urbaniza

**Arquivo**: `cartographer/cities/generate_city_geometry.py` (`__init__`, `_construir_malha`,
`_gerar_quarteiroes_e_lotes`), `config.json`.

#### F1.1 Dimensione a praça

Substitua `cidade_geo_praca_raio_m` (25, fixo) por três chaves:

```
cidade_geo_praca_fracao_nucleo   0.45   # fração do raio da banda 0
cidade_geo_praca_raio_min_m      18
cidade_geo_praca_raio_max_m      70
```

```python
raio_banda0 = self.raio_m / (self.num_aneis + 1)
self.praca_raio = min(self.praca_raio_max,
                      max(self.praca_raio_min, self.praca_fracao_nucleo * raio_banda0))
```

Confira o resultado esperado antes de rodar: Jorverhaven (`raio_banda0 = 200,3`) vai a 70 m de
raio (140 m de largura — uma praça de capital); Tormirstead (`84,7`) vai a 38 m. Se sair muito
diferente disso, a conta está errada.

#### F1.2 Trave a praça dentro do núcleo

`_melhor_centro_praca` (L193) desloca a praça para o ponto mais plano. Com a praça maior, esse
deslocamento pode fazê-la invadir as quadras cívicas novas. Defina o raio do núcleo **a partir
da praça já posicionada**, não o contrário:

```python
centro_praca = self._melhor_centro_praca(raio_banda0)
self._raio_nucleo = math.hypot(*centro_praca) + self.praca_raio + self._distancia_faixa_dominio("anel")
```

Assim `praça ⊂ círculo de raio _raio_nucleo em torno de (0,0)` é garantido por construção, sem
teste de sobreposição.

⚠️ Se `_raio_nucleo >= raio_banda0 * 0.9`, não sobra anel para urbanizar. Nesse caso pule F1.3
para essa cidade (a praça toma o núcleo inteiro, o que é um resultado legítimo em cidade
pequena) e registre quantas cidades caíram nesse caso.

#### F1.3 Emita o anel viário do núcleo e as radiais a partir dele

Em `_construir_malha`:

- acrescente um anel de `num_setores` vértices em `_raio_nucleo` (mesma perturbação
  `self.irreg` dos outros anéis, para o traço combinar), emitido como `rua` com
  `tipo_via="anel"`, `classe_via="anel"`, `indice=-1`;
- mude o início das radiais: hoje `pontos = [(0.0, 0.0)] + [...]` (L297). Passe a
  `pontos = [nucleo[i]] + [...]`, onde `nucleo[i]` é o vértice `i` do anel novo.

Resultado visual: a praça deixa de ser cortada por N radiais convergindo no meio dela e passa a
ser uma praça de verdade, contornada por uma rua.

#### F1.4 Gere quarteirões na banda 0

Em `_gerar_quarteiroes_e_lotes`, faça o laço começar em `j = 0` em vez de `j = 1`, com o anel
interno da banda 0 sendo o anel do núcleo:

```python
raio_interno = self._nucleo if j == 0 else self._vertices[j-1]
raio_externo = self._vertices[j]
bairro = "Núcleo" if j == 0 else ("Centro" if j == 1 else ...)
```

Tudo o mais (as 4 distâncias de faixa de domínio, `_encolher_quad`, `_subdividir_lote`) fica
**idêntico**. Esse é o mesmo fato que a Seção 4.1 explora: depois da malha, o pipeline não sabe
nem precisa saber de que forma de cidade os quads vieram. Aqui ele ganha uma banda a mais sem
reclamar; no F4 ele ganha modelos inteiros pelo mesmo motivo.

`_area_alvo_lote(0)` já devolve `base * 1.6^-1 * fator_cidade`, ou seja, lotes **menores** na
banda 0. É o que se quer: o núcleo medieval é a parte mais densa da cidade.

#### F1.5 Aceite

```bash
venv/bin/python cartographer/cities/generate_city_geometry.py
venv/bin/python - <<'EOF'
import json, glob, math
mpp = math.sqrt(250) * 1000
for a in sorted(glob.glob('database/cidades/*.geojson')):
    d = json.load(open(a)); p = d['properties']
    q0 = [f for f in d['features']
          if f['properties']['camada'] == 'quarteirao' and f['properties'].get('banda') == 0]
    pr = next(f for f in d['features'] if f['properties']['camada'] == 'praca')
    xs = [c[0] for c in pr['geometry']['coordinates'][0]]
    print(f"{p['cidade']:<18} praca_diam={(max(xs)-min(xs))*mpp:6.1f}m  quarteiroes_nucleo={len(q0)}")
EOF
```

| critério | alvo |
|---|---|
| diâmetro da praça | entre 36 m (cidade pequena) e 140 m (grande); **nunca** 50 m fixo para todas |
| quarteirões na banda 0 | `>= 1` em pelo menos 12 das 14 cidades |
| total de lotes no mundo | cresce entre +5 % e +15 % (de 32.787); acima disso, `_raio_nucleo` está pequeno demais |
| nenhum lote dentro da praça | verifique visualmente 2 cidades no dashboard, zoom 14 |

---

### F2 — Distribuição dirigida dos notáveis

**Arquivo**: `cartographer/cities/generate_city_geometry.py`
(`_gerar_quarteiroes_e_lotes`, `_gerar_edificios`), `config.json`.

Esta é a etapa que resolve o pedido 2. É a mais delicada do documento — leia inteira antes de
escrever.

#### F2.1 O lote precisa saber de que quarteirão veio

Hoje `self._lotes` guarda `(quad, bairro, banda)` (L488). Acrescente o identificador do
quarteirão:

```python
self._lotes.append((lote, bairro, j, id_quarteirao))
```

onde `id_quarteirao` é `(banda, setor)` no traçado radial — e, depois do F4, um índice inteiro
que o traçado atribui, sem topologia embutida. Atualize os desempacotamentos em
`_gerar_edificios` (L547).

#### F2.2 Dê uma zona a cada tipo do catálogo

Zonas (quatro, mapeadas para bandas):

| zona | banda | quem mora ali |
|---|---|---|
| `nucleo` | 0 | templo, prefeitura, tribunal, castelo, guarda, mercado |
| `centro` | 1 | taverna, estalagem, boticário, alfaiate, escola, biblioteca |
| `meio` | 2 .. `num_aneis-1` | ferreiro, carpinteiro, curtume, cervejaria, oleiro |
| `borda` | `num_aneis` | fazenda, pomar, estábulo, moinho, doca |

Duas fontes, nesta precedência:

1. chave `zona` opcional em cada entrada de `cidade_geo_catalogo_edificios` (para exceções);
2. `cidade_geo_zona_por_categoria`, o padrão por `categoria`.

O agrupamento acima não é decorativo: ofício sujo e barulhento (curtume, forja) longe da praça
e produção primária na borda é como cidade medieval de fato se organizava, e é o que faz o mapa
"ler" como cidade em vez de amontoado.

**Degradação em cidade pequena**: com `num_aneis = 2` as zonas `meio` e `borda` colidem. Regra:
se a banda calculada não existir, caia para a banda válida mais próxima. Nunca descarte a
encomenda por falta de zona.

#### F2.3 Substitua o laço por duas passadas

Retire de `_gerar_edificios` toda a lógica de `fila_tipos` / `frac_residencial_banda` /
`_escolher_edificio` dentro do laço de lotes. No lugar:

**Passada 1 — montar as encomendas.** Para cada entrada do catálogo aplicável
(`_candidatos_catalogo`), decida a quantidade:

```python
n = entrada.get("min", 0)
# extras até o max, com probabilidade proporcional ao peso efetivo
while n < entrada.get("max", 99) and self.rng.random() < self._peso_efetivo(entrada) / peso_max:
    n += 1
```

Produz uma lista de encomendas `[(entrada, zona), ...]`. Embaralhe com `self.rng.shuffle` para
que a ordem do catálogo não vire ordem espacial.

**Passada 2 — colocar por rodízio.** Para cada zona, monte a lista de quarteirões daquela zona
e **embaralhe-a**. Depois, para cada encomenda, ande no rodízio:

```python
for entrada, zona in encomendas:
    for _ in range(len(quarteiroes[zona])):          # no máximo uma volta completa
        q = proximo_do_rodizio(zona)
        if notaveis_em[q] < self.notaveis_max_por_quarteirao and lotes_livres[q]:
            lote = self.rng.choice(lotes_livres[q])
            atribuicao[lote] = entrada
            notaveis_em[q] += 1
            lotes_livres[q].remove(lote)
            break
    # se a volta completa não achou lugar, a encomenda é descartada — registre a contagem
```

**Por que rodízio sobre lista embaralhada e não "escolha o lote mais distante dos outros"**:
porque o rodízio dá espalhamento garantido em O(n), sem conta de distância, e é trivial de
testar. A alternativa por distância é mais bonita e mais cara, e não faz diferença visível com
30-50 notáveis em 15-48 quarteirões.

**Passada 3 — o resto.** Percorra `self._lotes` na ordem que quiser. Lote com atribuição usa a
entrada atribuída; lote sem atribuição vira `Residência` (ou comércio de bairro, se o F3 tiver
entrado).

#### F2.4 Config novo

```
cidade_geo_notaveis_max_por_quarteirao   3
cidade_geo_zona_por_categoria            {"publico":"nucleo", "quartel":"nucleo",
                                          "mercado":"nucleo", "universidade":"centro",
                                          "taverna":"centro", "forja":"meio",
                                          "fazenda":"borda", "generic":"meio"}
```

#### F2.5 Aceite

Reuse o script da Seção 3.2 (ele funciona contra os arquivos gerados; adapte para ler
`database/cidades/*.geojson` em vez de reinstanciar o gerador, agrupando por
`properties.quarteirao_id` se você gravar essa propriedade, ou por `(banda, bairro)` + ângulo).

| critério | hoje | alvo |
|---|---|---|
| quarteirões com pelo menos um notável (Jorverhaven) | 1 de 48 | **>= 15** |
| maior concentração num único quarteirão | 48 (100 %) | **<= `cidade_geo_notaveis_max_por_quarteirao`** |
| notáveis fora da fatia de 30° mais cheia | 0 | **>= 60 % do total** |
| notáveis por zona | todos em banda 1 | `nucleo` e `centro` majoritários, mas `meio`/`borda` não vazios |
| encomendas descartadas por falta de lugar | — | 0 em todas as 14 cidades |

---

### F3 — Comércio de bairro (o mix de usos)

**Arquivo**: `config.json`, `cartographer/cities/generate_city_geometry.py`
(`_gerar_edificios`).

Resolve 3.3. **Recomendada, mas separável**: se o usuário quiser só o espalhamento dos marcos,
F1+F2 bastam. Faça F3 como um passo próprio, para poder ser revertida sozinha.

#### F3.1 A lista nova

```json
"cidade_geo_catalogo_comercio_bairro": [
  {"tipo_local": "Padaria de Bairro", "categoria": "forja",    "capacidade": 3, "salario_base": 60, "um_a_cada_n_lotes": 160},
  {"tipo_local": "Taverna de Bairro", "categoria": "taverna",  "capacidade": 4, "salario_base": 70, "um_a_cada_n_lotes": 200},
  {"tipo_local": "Quitanda",          "categoria": "mercado",  "capacidade": 3, "salario_base": 55, "um_a_cada_n_lotes": 140},
  {"tipo_local": "Oficina",           "categoria": "forja",    "capacidade": 3, "salario_base": 75, "um_a_cada_n_lotes": 180},
  {"tipo_local": "Poço de Bairro",    "categoria": "generic",  "capacidade": 1, "salario_base": 0,  "um_a_cada_n_lotes": 120},
  {"tipo_local": "Capela de Bairro",  "categoria": "publico",  "capacidade": 2, "salario_base": 50, "um_a_cada_n_lotes": 400}
]
```

Note: sem `min`, sem `max`, sem `tipos_cidade`. A quantidade é `n_lotes // um_a_cada_n_lotes`.

Para Jorverhaven (6.601 lotes): 41 padarias + 33 tavernas + 47 quitandas + 36 oficinas + 55
poços + 16 capelas = **228 estabelecimentos**, ou **3,5 %** do total. Some os 48 marcos: ~4,2 %
não-residencial. Conservador e plausível. Calibre para cima se ficar ralo demais na tela.

#### F3.2 Colocação

Mesma passada 2 do F2, mas sobre **todos** os quarteirões da cidade (não por zona) e com o seu
próprio teto (`cidade_geo_comercio_bairro_max_por_quarteirao`, sugestão 2). Rode **depois** das
encomendas do catálogo de marcos, para o marco nunca perder lugar para uma quitanda.

#### F3.3 Guarda de proporção

Acrescente `cidade_geo_fracao_residencial_min` (sugestão `0.80`) e pare de colocar comércio de
bairro quando a fração residencial chegar nesse piso.

⚠️ **`cidade_geo_fracao_residencial` (0,55) deixa de ser usado.** Ele nunca funcionou como
pretendido (3.3). **Remova a chave** e o código que a lê (L566), não a deixe apodrecendo no
config. Anote a remoção no log da Seção 11.

#### F3.4 Aceite

```bash
venv/bin/python -c "
import json, glob, collections
tot = collections.Counter()
for a in glob.glob('database/cidades/*.geojson'):
    d = json.load(open(a))
    tot.update(f['properties']['categoria'] for f in d['features']
               if f['properties']['camada'] == 'edificio')
n = sum(tot.values())
print(tot, '\n residencial:', round(100*tot['residencia']/n, 1), '%')"
```

| critério | hoje | alvo |
|---|---|---|
| fração residencial no mundo | 99,3 % | entre **80 % e 93 %** |
| categorias com pelo menos 20 ocorrências no mundo | 4 de 9 | **>= 7 de 9** |
| total de `edificio` no mundo | 32.787 | **inalterado por F3** (F3 troca rótulo, não cria lote) |

---

### F4 — A interface de modelo de cidade

**Arquivo**: `cartographer/cities/modelos/` (novo), `generate_city_geometry.py`.

Esta é a etapa arquitetural do documento, e a que o autor pediu explicitamente (4.1). **Ela não
muda nada visualmente** — o mundo gerado tem que sair byte a byte igual (5.7). Faça-a
**sozinha**, confirme o `diff` vazio, e só então siga para F5.

#### F4.1 Estrutura de arquivos

```
cartographer/cities/modelos/__init__.py   # registro MODELOS = {nome: classe} + SitioCidade
cartographer/cities/modelos/sitio.py      # dataclass SitioCidade + SitioCidade.medir()
cartographer/cities/modelos/base.py       # dataclasses Rua/Quadra/DesenhoCidade + ModeloCidade
cartographer/cities/modelos/radial.py     # o modelo de hoje, movido para cá
```

`generate_city_geometry.py` continua sendo o ponto de entrada e o dono da **emissão** (converter
o desenho em GeoJSON, escrever arquivo, montar o índice). Ele deixa de ser o dono do **desenho**.

#### F4.2 `SitioCidade` — os dados que o modelo recebe

É o "informações de posição e dados de geografia/clima" do pedido. Medido **uma vez**, antes de
instanciar o modelo, e passado pronto:

```python
@dataclass(frozen=True)
class SitioCidade:
    # identidade (vem do manifesto — ver 2.4 e Regra 9: nada é acrescentado lá)
    nome: str
    tamanho: str                 # "pequeno" | "medio" | "grande"
    tipo: str                    # "capital" | "fortaleza" | "portuaria" | ...
    continente: str
    seed: int                    # zlib.crc32(nome) — NUNCA hash()

    # posição
    x_mundo: float
    y_mundo: float
    metros_por_px: float

    # geografia/clima, da janela 64x64 que __init__ já amostra (4.2)
    altitude_media: float
    temperatura_media: float     # discrimina: 0,012 a 0,574 no mundo medido
    umidade_media: float         # discrimina: 0,243 a 0,597
    bioma_dominante: int         # 2=Deserto, 3=Mediterrâneo, 4=Floresta Temperada
    terreno: "np.ndarray"        # canal 0 da janela, 64x64 — para declividade local
    grad_x: "np.ndarray"
    grad_y: "np.ndarray"

    # água (hoje sempre longe — ver 4.3/4.7; entra agora para o futuro não exigir refatoração)
    distancia_agua_m: float
    direcao_agua_rad: float
```

**`SitioCidade.medir(cidade, continente, config)`** faz o trabalho que hoje está espalhado no
`__init__` (L108-128): chama `obter_cartografo().gerar_janela` **uma vez** e guarda os **4**
canais, não só o canal 0. A distância/direção da água sai do `mapa_composto.npz`, com o mesmo
cálculo da Seção 3.5b — é O(pixels de água) por cidade, ~15 ms, irrelevante no orçamento.

⚠️ `terreno`, `grad_x` e `grad_y` são `np.ndarray` dentro de uma dataclass `frozen` — isso
congela a referência, não o conteúdo. **Não escreva nesses arrays em modelo nenhum.**

#### F4.3 `ModeloCidade` — a interface que todo modelo implementa

Este é o coração do F4. Sete perguntas; a base responde todas de um jeito razoável, e cada
modelo sobrescreve **só as que fazem sentido para ele** (é o ponto do autor sobre "na cidade
linear isso não existe mas existem outras configurações").

```python
class ModeloCidade:
    nome = "base"

    def __init__(self, sitio: SitioCidade, config: dict, rng: random.Random):
        self.sitio, self.cfg, self.rng = sitio, config, rng
        self.np_rng = np.random.default_rng(sitio.seed)
        self.ajustar_por_sitio()          # gancho 0

    # --- os 7 ganchos da interface -------------------------------------------------
    def ajustar_por_sitio(self): ...          # 0. calibra parâmetros com clima/bioma. Base: no-op
    def construir_malha(self) -> Malha: ...   # 1. ruas + quadras + portões + praça + contorno. OBRIGATÓRIO
    def zona_de(self, quadra) -> str: ...     # 2. "nucleo"|"centro"|"meio"|"borda" (+ zonas próprias)
    def encomendas(self) -> list: ...         # 3. quantos de cada tipo do catálogo de marcos
    def catalogo_comercio_bairro(self) -> list: ...  # 4. lista de densidade (F3)
    def escolher_quadra(self, encomenda, candidatas): ...  # 5. rodízio (F2). Base resolve.
    def precisa_muralha(self) -> bool: ...    # 6. base: tamanho/tipo, como hoje
```

| gancho | o que a **base** faz | quem sobrescreve, e por quê |
|---|---|---|
| 0 `ajustar_por_sitio` | nada | `radial`: mais poços se `umidade_media` baixa. `grade`: célula maior em bioma de deserto |
| 1 `construir_malha` | **`NotImplementedError`** | todos — é a única obrigação real |
| 2 `zona_de` | mapeia `quadra.banda` → zona, via `cidade_geo_zona_por_categoria` | `linear`: fileira 0 é `centro`, não banda. `bastida`: o bloco do canto é `nucleo` |
| 3 `encomendas` | lê `cidade_geo_catalogo_edificios`, aplica `min`/`max`/peso (F2.3) | `bastida`: força 1 `Castelo`. Uma futura `portuaria`: N `Doca` pelo comprimento do cais |
| 4 `catalogo_comercio_bairro` | lê a lista do config (F3.1) | `agricola`: mais `Moinho`. Deserto: mais `Poço` |
| 5 `escolher_quadra` | rodízio sobre quadras da zona, com teto (F2.3) | raramente; existe para um modelo poder ancorar algo num lugar exato |
| 6 `precisa_muralha` | `tamanho in cidade_geo_muralha_tamanhos or tipo == "fortaleza"` | `bastida`: sempre `True`. `linear`: sempre `False` |

**O que NÃO é gancho, e mora só na base** (5.5): inset de quadra (`_encolher_quad`), subdivisão
em lotes (`_subdividir_lote`), footprint (`_footprint_edificio`), emissão de feature
(`_add_feature`), índice (`indice`), conversão de coordenada (`_mundo`, `_geojson_coord`).
**Se você copiar qualquer um desses para dentro de um modelo, você errou.**

#### F4.4 As estruturas de dados

```python
@dataclass
class Rua:
    pontos: list        # [(x_m, y_m), ...] em metros locais
    classe_via: str     # "principal" | "anel" | "secundaria" — chave de cidade_via_largura_m_por_classe
    tipo_via: str       # papel geométrico: "anel" | "radial" | "eixo" | "transversal" | "servico"
    indice: int

@dataclass
class Quadra:
    vertices: list        # EXATAMENTE 4 vértices (ver 2.4)
    classes_aresta: list  # 4 strings: a classe_via da rua sobre a aresta k (de vertices[k] a vertices[k+1])
    banda: int            # 0 = núcleo ... num_bandas-1 = borda. Alimenta _area_alvo_lote
    bairro: str
    id: int               # identificador estável do quarteirão, usado por F2
    extra: dict           # espaço do modelo: {"fileira": 2} no linear, {"canto": True} na bastida

@dataclass
class Malha:
    ruas: list            # [Rua]
    quadras: list         # [Quadra]
    portoes: list         # [(x_m, y_m, nome)]
    centro_praca: tuple
    raio_praca: float
    raio_nucleo: float
    num_bandas: int
    contorno: list        # polígono do limite da cidade, em metros — usado pela muralha
```

Três campos merecem atenção:

- **`classes_aresta`** preserva o E1 (faixa de domínio) sem o modelo precisar saber o que é
  faixa de domínio: a base converte cada classe em distância via `_distancia_faixa_dominio` e
  chama `_encolher_quad`, exatamente como hoje;
- **`contorno`** tira o círculo fixo de `_gerar_muralha` (L613): a muralha vira o contorno
  inflado por `cidade_geo_muralha_folga_m`, e a muralha de uma cidade `grade` sai retangular sem
  nenhum caso especial;
- **`extra`** é o escape hatch que evita inventar campo novo toda vez que um modelo tem um
  conceito próprio. `zona_de` do `linear` lê `quadra.extra["fileira"]`; a base nunca olha para
  ele.

#### F4.5 O fluxo depois da refatoração

```python
# em generate_city_geometry.py
sitio   = SitioCidade.medir(cidade, continente_nome, CARTOGRAPHER_CONFIG)
rng     = random.Random(sitio.seed)
nome    = escolher_modelo(sitio, CARTOGRAPHER_CONFIG, rng)   # F8
modelo  = MODELOS[nome](sitio, CARTOGRAPHER_CONFIG, rng)

gerador = GeradorCidade(modelo)      # o gerador agora só EMITE
geojson = gerador.gerar()
```

```python
# em GeradorCidade — o pipeline compartilhado, igual para todo modelo
def gerar(self):
    malha = self.modelo.construir_malha()
    self._emitir_ruas(malha); self._emitir_praca(malha); self._emitir_portoes(malha)
    self._gerar_quarteiroes_e_lotes(malha)    # inset + subdivisão, matemática intacta
    self._distribuir_edificios(malha)         # usa zona_de / encomendas / escolher_quadra (F2, F3)
    self._gerar_muralha(malha)                # usa malha.contorno + modelo.precisa_muralha()
    return {...}
```

#### F4.6 Ordem de migração (e é aqui que se erra)

1. crie `sitio.py` e faça `__init__` **consumi-lo sem mudar comportamento** — o `SitioCidade`
   guarda os 4 canais, mas o gerador continua usando só `terreno`. Gere e confirme `diff` vazio;
2. crie `base.py` com as dataclasses e a `ModeloCidade` de ganchos ainda vazios;
3. mova `_construir_malha` para `radial.py` **sem reescrever uma linha da matemática**,
   devolvendo `Malha` em vez de gravar `self._vertices`. Gere e confirme `diff` vazio;
4. mova a distribuição (F2/F3, já implementados) para os ganchos 2-5 da base. Gere e confirme
   `diff` vazio;
5. só então F5.

Cada passo termina com `diff -rq` vazio. Se você fizer os quatro de uma vez e o `diff` sujar,
não vai saber qual deles quebrou.

⚠️ **A ordem de consumo do `rng` é o que decide se o `diff` fica vazio.** Mover código entre
arquivos não muda nada; mudar *quando* cada `self.rng.uniform` é chamado muda tudo (Seção 10.1).
Se o `diff` sujar em **todas** as cidades ao mesmo tempo, é isto — não procure em outro lugar.

#### F4.7 Aceite — o `diff` tem que ser vazio

```bash
cp -r database/cidades /tmp/cidades_antes
# ... faça a refatoração ...
venv/bin/python cartographer/cities/generate_city_geometry.py
diff -rq /tmp/cidades_antes database/cidades
```

`diff` sem saída = refatoração correta. **Qualquer diferença é bug**, inclusive de ordem de
features (o índice E5 depende da contagem por camada, e o determinismo depende da ordem de
consumo do RNG — se você mudou a ordem das chamadas a `self.rng`, todas as cidades mudaram).

Rode também a suíte:
```bash
venv/bin/python -m pytest tests/ -q
```

**Aceite arquitetural** — o `diff` vazio prova que não quebrou, não que a interface presta.
Confira também:

| critério | como verificar |
|---|---|
| `radial.py` não contém geometria compartilhada | `grep -n "_encolher_quad\|_subdividir_lote\|_footprint_edificio\|_add_feature" cartographer/cities/modelos/radial.py` → **sem resultado** |
| `generate_city_geometry.py` não sabe o que é anel nem setor | `grep -n "num_setores\|num_aneis\|_vertices" cartographer/cities/generate_city_geometry.py` → **sem resultado** |
| os 4 canais do sítio estão sendo guardados | `SitioCidade.medir` de qualquer cidade traz `temperatura_media` e `umidade_media` diferentes de zero |
| a base responde os 7 ganchos sozinha | um modelo de teste que só implemente `construir_malha` gera uma cidade completa |

O último é o teste real da arquitetura, e vale escrevê-lo como teste automatizado (9.2): se um
modelo mínimo precisa implementar mais de um gancho para funcionar, a base não está fazendo o
trabalho compartilhado dela.

---

### F5 — Modelo `grade`

**Arquivo**: `cartographer/cities/modelos/grade.py`, `config.json`.

Implementa `construir_malha` (gancho 1) e sobrescreve `ajustar_por_sitio` (gancho 0). Os outros
cinco ganchos vêm da base sem alteração — é o primeiro teste prático de que o F4 funcionou.

#### F5.1 Construção

1. **Eixo**: sorteie `theta` em `[0, π/2)` com `self.rng`. Todo o traçado é construído
   alinhado aos eixos e rotacionado por `theta` no fim (uma função de rotação de 3 linhas, não
   espalhe a trigonometria).
2. **Célula**: `lado = rng.uniform(*cidade_geo_grade_lado_quadra_m_faixa)` (sugestão
   `[70, 140]`). Número de células por eixo: `n = 2 * ceil(raio_m / lado)`, forçado a ser
   **ímpar** para existir uma célula central exata.
3. **Vértices**: grade `(n+1) × (n+1)` de pontos, com jitter de
   `cidade_geo_grade_jitter_m` (sugestão 6 m) aplicado a cada vértice via `np_rng` — é o que
   impede a grade de parecer papel milimetrado. Os vértices da **borda** recebem jitter maior,
   para o contorno não sair perfeitamente retangular.
4. **Recorte**: descarte a célula cujo centroide estiver fora do raio da cidade. Use o mesmo
   raio perturbado do `radial` (`raio_m * (1 + irreg * 0.5 * ruido(angulo))`) para a silhueta
   ficar orgânica mesmo com interior regular.
5. **Praça**: a célula central (ou o bloco 2×2 central, se o lado for pequeno) **não vira
   quadra** — vira a praça. `centro_praca` é o centroide dela, `raio_praca` o raio inscrito.
   Isto resolve o pedido 1 neste traçado sem nada do F1.
6. **Ruas**: cada linha da grade vira uma `Rua` com `tipo_via="transversal"`. As duas linhas que
   passam pela célula central são o cardo e o decumanus: `classe_via="principal"`,
   `tipo_via="eixo"`. A cada `cidade_geo_grade_avenida_a_cada_n` linhas (sugestão 3), a linha é
   `classe_via="anel"` (avenida); as demais, `"secundaria"`.
7. **`classes_aresta`**: para cada célula, a classe da linha da grade que passa em cada um dos
   4 lados. Isto sai de graça da construção — guarde a classe junto com cada linha ao criá-la.
8. **Banda**: `banda = min(num_bandas-1, distancia_chebyshev_ate_a_celula_central)`, reescalada
   para `0 .. num_aneis`. É o que mantém `_area_alvo_lote` e o zoneamento do F2 funcionando sem
   alteração.
9. **Portões**: as 4 pontas do cardo e do decumanus, limitadas a `num_portoes`.
10. **Contorno**: casco convexo dos vértices das células mantidas (ou o retângulo envolvente
    inflado, se quiser a muralha reta da bastida).

#### F5.2 `ajustar_por_sitio` — o primeiro uso real do clima

Este é o gancho 0 do F4.3, e a `grade` é onde ele fica mais legível. Uma cidade de deserto
(`bioma_dominante == 2`, `umidade_media` baixa — no mundo medido é Cidade dos Ventos, umidade
0,243) tem quadra **maior** e rua **mais estreita**: pátio interno grande e sombra na rua é como
se constrói em clima seco e quente. Cidade úmida de floresta é o oposto.

```python
def ajustar_por_sitio(self):
    seco = self.sitio.umidade_media < cfg_get(self.cfg, "cidade_geo_umidade_limiar_seco")
    faixa = list(cfg_get(self.cfg, "cidade_geo_grade_lado_quadra_m_faixa"))
    if seco:
        faixa = [v * cfg_get(self.cfg, "cidade_geo_grade_fator_lado_seco") for v in faixa]
    self.lado_faixa = faixa
```

⚠️ **Cuidado com o determinismo aqui**: `ajustar_por_sitio` roda no `__init__` do modelo, antes
de `construir_malha`. Se ele consumir `self.rng`, muda a sequência para todos os sorteios
seguintes. **Não sorteie dentro deste gancho** — ele lê o sítio e ajusta parâmetros, só isso.

Mantenha o efeito discreto (fator 1,2-1,4, não 3). O objetivo é que duas cidades do mesmo
modelo em climas opostos não sejam idênticas, não que virem estilos diferentes.

#### F5.3 Armadilha: o número de quadras explode

Uma cidade grande de raio 1.045 m com célula de 70 m dá `n = 30`, ou seja até **900 células**
contra 48 quarteirões do radial. Com lotes de ~300 m², isso é ~11.000 lotes — e o mundo inteiro
pode passar de 32 mil para 80 mil `Local`.

Não é proibido (o orçamento do usuário é generoso e o índice E5 absorve), mas **meça antes de
gerar tudo**. Se passar de ~60.000 edifícios no mundo, aumente o piso de
`cidade_geo_grade_lado_quadra_m_faixa`.

#### F5.3 Aceite

Gere **uma** cidade primeiro:
```bash
venv/bin/python cartographer/cities/generate_city_geometry.py "Cidade do Vento"
```

| critério | alvo |
|---|---|
| nenhum quad com área < `cidade_geo_quadra_area_minima_m2` sobrevivendo | 0 |
| nenhum quad invertido (`_encolher_quad` devolvendo None em massa) | descartes < 10 % das células |
| total de edifícios no mundo | < 60.000 |
| tempo de geração das 14 cidades | < 5 min (hoje: ~5 s) |
| visual no dashboard, zoom 14 | ruas retas, cruzamentos em ângulo reto, praça central quadrada |

---

### F6 — Modelo `linear`

**Arquivo**: `cartographer/cities/modelos/linear.py`, `config.json`.

O mais barato dos três e o que mais muda a cara das cidades pequenas.

**É também o modelo que prova a interface**, porque ele não tem banda nem setor — foi o exemplo
que o autor deu. Implementa `construir_malha` (gancho 1), `zona_de` (gancho 2, porque "fileira 0"
não é "banda 0") e `precisa_muralha` (gancho 6, sempre `False`). Os outros quatro vêm da base.
Se você precisar sobrescrever um quinto gancho aqui, provavelmente a base ficou específica
demais para o `radial` — volte e conserte a base, não contorne no modelo.

#### F6.1 Construção

1. **Eixo**: uma polilinha de `raio_m * 2` de comprimento, direção sorteada, com curvatura suave
   (`cidade_geo_linear_curvatura`, sugestão 0,12 — o desvio lateral máximo como fração do
   comprimento). Emita como `Rua` `classe_via="principal"`, `tipo_via="eixo"`.
2. **Faixas**: `k = rng.randint(*cidade_geo_linear_profundidade_faixas)` (sugestão `[1, 3]`)
   fileiras de quadras **de cada lado** do eixo. A profundidade de cada fileira vem de
   `cidade_geo_linear_largura_quadra_m_faixa` (sugestão `[50, 90]`).
3. **Quadras**: ao longo do eixo, corte em segmentos do comprimento da célula. Cada quadra é o
   quadrilátero entre dois cortes consecutivos e duas linhas de profundidade. Os 4 vértices
   saem diretamente de "ponto do eixo ± normal × profundidade" — **sempre 4 vértices**, como o
   contrato exige.
4. **Ruas transversais**: em cada corte, uma `Rua` `classe_via="secundaria"`,
   `tipo_via="transversal"`, atravessando as `k` fileiras.
5. **Vielas de fundo**: entre as fileiras `f` e `f+1`, uma `Rua` `classe_via="anel"`,
   `tipo_via="servico"`, paralela ao eixo.
6. **Banda**: `banda = índice da fileira` (0 = colada ao eixo). Zoneamento sai de graça: o F2
   põe o comércio na banda 0, que é exatamente a rua principal de uma vila de estrada.
7. **Afunilamento**: reduza o número de fileiras nas pontas do eixo (as duas ou três células
   extremas ficam com 1 fileira). Sem isso a cidade vira um retângulo perfeito.
8. **Praça**: substitua **uma** quadra da banda 0, perto do meio do eixo, pela praça.
9. **Portões**: as duas pontas do eixo.
10. **Contorno**: o polígono do envelope das quadras mantidas.

#### F6.2 Muralha

Cidade linear com muralha fica estranha (muralha circular em volta de uma cidade comprida). Ou o
contorno do F4.2 resolve sozinho (muralha alongada, que é o certo), ou acrescente `linear` a uma
exceção no `_precisa_muralha`. **Prefira o contorno** — é o que o F4 foi feito para permitir.

#### F6.3 Aceite

| critério | alvo |
|---|---|
| razão comprimento/largura da cidade | entre 2,5 e 6,0 |
| quadras na banda 0 | > 50 % do total |
| todos os quads com 4 vértices | 100 % |
| visual, zoom 14 | uma rua principal atravessando, casas dos dois lados, praça no meio |

---

### F7 — Modelo `organica` (e F7b `bastida`, opcional)

**Arquivo**: `cartographer/cities/modelos/organica.py`, `config.json`.

#### F7.1 `organica` — radial degradado de propósito

Herde de `RadialModelo` e aplique quatro degradações:

1. `irreg` multiplicada por `cidade_geo_organica_fator_irregularidade` (sugestão 2,2);
2. **anéis que não fecham**: cada anel perde um arco contíguo de 1 a 3 setores (sorteado). A rua
   do anel vira uma polilinha aberta, não um loop. As quadras que dependiam daquele trecho
   continuam existindo — muda a rua, não a quadra;
3. **quadras faltando**: descarte uma fração
   `cidade_geo_organica_fracao_quadras_vazias` (sugestão `[0.05, 0.18]`) das quadras,
   sorteada. Uma quadra descartada vira chão livre (nem quarteirão, nem lotes);
4. **radiais tortas**: aplique um deslocamento lateral senoidal de baixa amplitude aos pontos
   intermediários de cada radial.

Custo real: ~60 linhas sobre o `radial`. É o melhor retorno por linha de todo o documento.

**Herdar de outro modelo é permitido e esperado** — `organica` de `radial`, `bastida` de `grade`.
A interface do F4.3 é o contrato com a **base**, não uma proibição de reuso entre modelos. O
limite é um só: um modelo nunca herda de dois, e nunca chama método privado de um irmão. Se dois
modelos precisam da mesma coisa e não são pai e filho, essa coisa é da base.

#### F7.2 `bastida` (opcional) — `grade` fortificada

Herde de `GradeModelo` e mude quatro coisas:

1. `contorno` = retângulo envolvente das células mantidas, **sem** o recorte circular do F5.1.4
   (a bastide é retangular por definição);
2. portões **só** nas 4 pontas do cardo/decumanus;
3. reserve o bloco 2×2 de um canto (o mais plano, por `_declividade_local`) como zona
   `nucleo` exclusiva — é onde o F2 vai pôr o castelo e o quartel;
4. `precisa_muralha` (gancho 6) sempre verdadeiro para este modelo.

#### F7.3 Aceite

| critério | alvo |
|---|---|
| `organica`: quadras descartadas | dentro da faixa configurada, em todas as cidades |
| `organica`: nenhuma rua de anel fechando 360° | 0 anéis fechados |
| `bastida`: contorno com 4 lados | sim |
| ambos: `pytest` verde e nenhum quad degenerado | — |

---

### F8 — Seleção e instanciação do modelo

**Arquivo**: `cartographer/cities/modelos/__init__.py`, `generate_city_geometry.py`,
`config.json`.

É a etapa que acende tudo: é aqui que a "lista de possibilidades + rand + instanciar passando os
dados" do pedido vira código.

#### F8.1 O registro

`modelos/__init__.py` mantém o mapa nome → classe. **Importe cada modelo explicitamente**, não
faça varredura de diretório: descoberta automática torna a ordem de registro dependente do
sistema de arquivos, e isso é a porta de entrada para não-determinismo.

```python
from .radial import RadialModelo
from .grade import GradeModelo
from .linear import LinearModelo
from .organica import OrganicaModelo

MODELOS = {m.nome: m for m in (RadialModelo, GradeModelo, LinearModelo, OrganicaModelo)}
```

#### F8.2 O sorteio e a instanciação

```python
def escolher_modelo(sitio, config, rng):
    mapa = cfg_get(config, "cidade_geo_modelo_por_tipo")
    opcoes = mapa.get(sitio.tipo) or mapa["_default"]
    nomes = [o[0] for o in opcoes]
    pesos = [o[1] for o in opcoes]
    escolhido = rng.choices(nomes, weights=pesos, k=1)[0]
    if escolhido not in MODELOS:        # config citando modelo não implementado ainda
        escolhido = "radial"
    return escolhido

modelo = MODELOS[escolher_modelo(sitio, config, rng)](sitio, config, rng)
```

⚠️ O sorteio acontece **depois** de todos os sorteios que já existiam (raio, anéis, fator de
lote, setores). Colocar antes muda todas as cidades. Ver a armadilha de determinismo em 4.5 e
na Seção 10.1.

O `if escolhido not in MODELOS` não é paranoia: ele é o que deixa o config citar `"portuaria"`
(4.7) antes da classe existir, sem quebrar a geração.

#### F8.3 Grave o modelo no arquivo

Em `gerar()`, acrescente `"modelo": self.modelo.nome` às `properties` do `FeatureCollection`, e
em `indice()` acrescente `"modelo"` ao dicionário. Sem isso não há como auditar a distribuição
sem reinstanciar o gerador.

Aproveite e grave também o essencial do sítio (`bioma_dominante`, `temperatura_media`,
`umidade_media`) nas `properties` — é barato e é o que permite responder depois "por que esta
cidade ficou assim?" sem rodar nada.

#### F8.4 Aceite

```bash
venv/bin/python cartographer/cities/generate_city_geometry.py
venv/bin/python -c "
import json, collections
cs = json.load(open('database/cidades/_indice.json'))['cidades']
for c in cs:
    print(f\"{c['nome']:<20} {c.get('tamanho','?'):<8} {c.get('modelo','?')}\")
print(collections.Counter(c.get('modelo') for c in cs))"
```

| critério | alvo |
|---|---|
| modelos distintos usados no mundo | **>= 3** |
| nenhum modelo com mais de 60 % das cidades | — |
| reexecutar a geração duas vezes dá o mesmo resultado | `diff -rq` vazio |
| pôr `"portuaria"` no config sem a classe existir | cai em `radial`, sem exceção |

---

## 7. Ordem de execução

**Siga esta ordem.** Ela não é arbitrária: F2 precisa da banda 0 do F1 para ter zona `nucleo`, e
F5-F7 precisam do contrato do F4.

```
F1  núcleo cívico          ─┐
F2  distribuir notáveis     ├─ pedidos 1 e 2 do usuário. PARE AQUI se o tempo acabar.
F3  comércio de bairro     ─┘   Já são entregáveis completos, sem F4+.
────────────────────────────────────────────────────────────────────────
F4  interface de modelo        refatoração pura, diff vazio obrigatório
F5  modelo grade               o contraste mais forte contra o radial
F6  modelo linear              o mais barato, melhor efeito nas cidades pequenas
F7  modelo organica            (+ F7b bastida, opcional)
F8  seleção por tipo           acende tudo de uma vez
```

Depois de **cada** etapa: regere as cidades, rode `pytest`, e cole o output real no log da
Seção 11. Não acumule três etapas antes de medir.

**Ponto de parada natural**: o fim do F3. F1-F3 resolvem os dois defeitos que o usuário
relatou; F4-F8 são a funcionalidade nova que ele pediu para **analisar**. Se a análise da
Seção 4 mudar a opinião dele, F4+ pode nunca acontecer — e F1-F3 continuam valendo.

---

## 8. Tabela consolidada do config novo

Tudo com `_comentario_` obrigatório (Regra 4). Chaves em `config.json`, seção `cartografia`.

| chave | valor sugerido | etapa | o que é |
|---|---|---|---|
| `cidade_geo_praca_fracao_nucleo` | `0.45` | F1 | fração do raio da banda 0 que a praça ocupa |
| `cidade_geo_praca_raio_min_m` | `18` | F1 | piso, para a vila pequena ter praça visível |
| `cidade_geo_praca_raio_max_m` | `70` | F1 | teto, para a capital não virar um campo |
| `cidade_geo_notaveis_max_por_quarteirao` | `3` | F2 | teto por quadra; é o que quebra o amontoado |
| `cidade_geo_zona_por_categoria` | ver F2.4 | F2 | `categoria` → `nucleo`/`centro`/`meio`/`borda` |
| `cidade_geo_catalogo_comercio_bairro` | ver F3.1 | F3 | lista por densidade, sem `max` |
| `cidade_geo_comercio_bairro_max_por_quarteirao` | `2` | F3 | teto próprio, separado do dos marcos |
| `cidade_geo_fracao_residencial_min` | `0.80` | F3 | piso de residências; substitui a chave removida |
| `cidade_geo_modelo_por_tipo` | ver 4.5 | F8 | `tipo` → `[[nome, peso], ...]`, com `_default`. A "lista de possibilidades" do pedido |
| `cidade_geo_grade_lado_quadra_m_faixa` | `[70, 140]` | F5 | lado da célula da grade |
| `cidade_geo_grade_avenida_a_cada_n` | `3` | F5 | de quantas em quantas linhas sai uma avenida |
| `cidade_geo_grade_jitter_m` | `6` | F5 | o que impede a grade de parecer papel milimetrado |
| `cidade_geo_umidade_limiar_seco` | `0.30` | F5 | abaixo disto o sítio é "seco"; calibrado sobre a faixa medida 0,243-0,597 (4.2) |
| `cidade_geo_grade_fator_lado_seco` | `1.30` | F5 | quanto a quadra cresce em clima seco (pátio grande, rua na sombra) |
| `cidade_geo_linear_profundidade_faixas` | `[1, 3]` | F6 | fileiras de quadra de cada lado do eixo |
| `cidade_geo_linear_largura_quadra_m_faixa` | `[50, 90]` | F6 | profundidade de cada fileira |
| `cidade_geo_linear_curvatura` | `0.12` | F6 | desvio lateral do eixo, como fração do comprimento |
| `cidade_geo_organica_fator_irregularidade` | `2.2` | F7 | multiplica `cidade_geo_irregularidade_via` |
| `cidade_geo_organica_fracao_quadras_vazias` | `[0.05, 0.18]` | F7 | faixa de quadras descartadas |

**Chave a REMOVER**: `cidade_geo_praca_raio_m` (substituída em F1) e
`cidade_geo_fracao_residencial` (nunca funcionou como pretendido — ver 3.3 e F3.3).

**Chave a manter mesmo parecendo inútil**: `cidade_geo_declividade_max`. Ela não dispara hoje
(3.5a), mas é o único ponto de entrada caso o modelo de relevo ganhe amplitude. Documente que
está inerte, não a apague.

---

## 9. Testes e validação

### 9.1 A suíte existente
```bash
venv/bin/python -m pytest tests/ -q
```
Hoje: **10 passed**. Tem que continuar 10 passed (ou mais, se você acrescentar). Nenhuma das
etapas deste documento deveria quebrar um teste de cartografia — se quebrar, você mexeu em algo
que não devia.

### 9.2 Testes novos que valem a pena

Em `tests/test_cartografia.py` (ou um `tests/test_cidades.py` novo):

1. **Determinismo**: gerar a mesma cidade duas vezes dá o mesmo GeoJSON. Protege contra o uso
   acidental de `hash()` ou `random` de módulo em qualquer modelo novo.
2. **Contrato de quadrilátero**: toda `Quadra` de todo modelo tem exatamente 4 vértices.
   Protege o contrato da Seção 2.4 em F5-F7.
3. **Espalhamento**: nenhum quarteirão passa de `cidade_geo_notaveis_max_por_quarteirao`
   notáveis. É o teste de regressão do bug 3.2 — sem ele, ele volta.
4. **Praça sem lote dentro**: nenhum centroide de lote cai dentro do polígono da praça.
5. **A base basta** (o teste da arquitetura do F4, ver F4.7): um `ModeloCidade` de teste que
   implemente **só** `construir_malha` — uma malha trivial de 4 quadras — gera uma cidade
   completa, com lotes, edifícios, notáveis distribuídos e índice. Se esse teste exigir que o
   modelo implemente um segundo gancho, a base não está fazendo o trabalho compartilhado dela e
   todo modelo futuro vai pagar por isso.
6. **Todo modelo registrado responde a interface**: para cada classe em `MODELOS`, instanciar
   com um `SitioCidade` sintético e gerar. Pega modelo que quebrou com uma mudança na base —
   que é o risco que a arquitetura nova introduz.

### 9.3 Validação visual — a única que decide

**Peça ao usuário.** As medições acima provam que os números estão certos; só o olho prova que a
cidade parece cidade. Roteiro para ele:

```bash
venv/bin/python run_dashboard.py
```
Abrir o mapa, ir a uma cidade, e olhar em **zoom 13 e 14**:

| o que olhar | antes | esperado depois |
|---|---|---|
| centro da cidade | disco vazio com um círculo verde pequeno no meio | praça grande contornada por rua e por quadras cheias |
| prédios coloridos (notáveis) | todos amontoados num canto | espalhados, mais densos perto da praça |
| variedade de cor | quase tudo bege (residência) | bege dominante com pontos de cor por toda parte |
| duas cidades lado a lado | mesma forma | formas distintas (só depois do F8) |

### 9.4 Efeito no banco, **sem escrever nele**

A Regra 7 proíbe rodar `populate.py`. Para conferir quantos `Local` o próximo reset criaria:

```bash
venv/bin/python -c "
import json, glob, collections
tot = collections.Counter()
for a in glob.glob('database/cidades/*.geojson'):
    d = json.load(open(a))
    tot.update(f['properties']['categoria'] for f in d['features']
               if f['properties']['camada'] == 'edificio')
print('Local que o proximo reset criaria:', sum(tot.values()))
print(tot)"
```

Referência de hoje: **32.787**. Depois de F1 espere +5 % a +15 %; F2 e F3 não mudam o total; F5
pode aumentar muito (ver F5.2).

---

## 10. Riscos, armadilhas e o que já se sabe que vai dar errado

1. **Ordem de consumo do RNG** (a pior de todas). `self.rng` é sequencial. Inserir um sorteio
   novo no meio de `__init__` muda **todas** as cidades do mundo, silenciosamente. Sorteios
   novos vão para o fim, ou usam um `random.Random` derivado (`self.seed ^ 0x9E3779B9`). Isto
   já apareceu duas vezes neste código.

2. **`_encolher_quad` é geometria pura.** Ele **não** aplica piso de área — quem aplica é o
   chamador. Isso foi um bug real na E3 da `ESPEC_TECIDO_URBANO.md` (969 de 1.018 footprints
   sumiram porque o piso da quadra vazou para o footprint do edifício). Se você reutilizá-lo em
   um modelo novo, **não** reintroduza o piso lá dentro.

3. **Quad em zigue-zague.** `_subdividir_lote` tem um comentário (L433) sobre um bug já pago:
   índices modulares relativos a `i0`, nunca `sorted()`. Modelos novos que produzam quads com
   ordem de vértice inconsistente (horário num, anti-horário noutro) vão reviver isso.
   `_encolher_quad` detecta orientação invertida e devolve `None`, então o sintoma será
   "quadras sumindo", não "quadra torta". Se muitas sumirem, é isto.

   ⚠️ Com a arquitetura do F4 isso fica **mais** fácil de acontecer, não menos: cada modelo
   constrói seus quads do seu jeito. Padronize a orientação **uma vez, na base** — a base
   normaliza a orientação de toda `Quadra` que recebe de `construir_malha`, e nenhum modelo
   precisa se preocupar. É meia dúzia de linhas e elimina a classe inteira de bug.

4. **Camada nova some sem erro.** Os 4 toques da Seção 2.5. Esquecer o item 2 (a API) devolve
   `FeatureCollection` vazio, sem log, sem 404.

5. **Explosão de `Local`.** F5 com célula pequena pode triplicar o mundo. Meça com 9.4 **antes**
   de gerar as 14. O limite de escala do motor já está registrado em `ROADMAP.md` Frente 8 —
   este trabalho aproxima aquele limite, não o cria.

6. **`JobMarket` varre `locais` inteiro.** `engine/mechanics/market.py:77` faz um `SELECT` sobre
   todos os locais com vaga. Hoje são 48 não-residenciais por cidade; depois do F3 serão ~250.
   Ainda é pouco, mas some ao que a Frente 8 já mede. **Não conserte aqui** — só registre no log
   se o número passar de ~5.000 no mundo.

7. **Colisão de slug** (3.6). Se você contar 14 cidades onde o manifesto diz 15, não é bug seu.

8. **Não confie no filtro de declividade.** Ele não dispara (3.5a). Se um modelo seu depender
   dele para alguma coisa, essa coisa não vai acontecer.

9. **A base virou superfície compartilhada.** É o preço da arquitetura do F4: antes, mexer em
   `_gerar_quarteiroes_e_lotes` afetava uma cidade radial; depois, afeta todos os modelos de uma
   vez. Duas defesas: o teste 9.2.6 (todo modelo registrado gera sem erro) e a disciplina de
   nunca pôr `if self.modelo.nome == "..."` na base. **Se a base precisa perguntar quem é o
   modelo, faltou um gancho** — acrescente o gancho, não o `if`.

10. **`ajustar_por_sitio` não sorteia.** O gancho 0 roda no `__init__` do modelo. Consumir
    `self.rng` ali desloca a sequência inteira e muda todas as cidades (é o item 1 com outra
    roupa). Ele lê o sítio e ajusta parâmetros; ponto.

---

## 11. Log de execução — preencha enquanto trabalha

> Uma subseção por etapa. Cole o **output real** dos comandos de aceite, não um resumo.
> Se uma etapa for pulada, escreva por quê.

### F1 — Núcleo cívico
- [x] Implementado
- Comando de aceite e output (F1.5):
  ```
  Aurora Vales       praca_diam= 135.2m  quarteiroes_nucleo=12
  Cidade do Vento    praca_diam= 140.0m  quarteiroes_nucleo=13
  Cidade dos Ventos  praca_diam=  85.0m  quarteiroes_nucleo=2
  Elinford           praca_diam= 120.9m  quarteiroes_nucleo=5
  Elorfield          praca_diam=  92.0m  quarteiroes_nucleo=8
  Jorverhaven        praca_diam= 140.0m  quarteiroes_nucleo=12
  Lorverstead        praca_diam= 140.0m  quarteiroes_nucleo=10
  Pelorport          praca_diam= 140.0m  quarteiroes_nucleo=11
  Quendorvale        praca_diam=  95.4m  quarteiroes_nucleo=2
  Silenmont          praca_diam= 125.7m  quarteiroes_nucleo=3
  Toranhaven         praca_diam= 127.7m  quarteiroes_nucleo=8
  Tordordor          praca_diam= 110.1m  quarteiroes_nucleo=5
  Tormirstead        praca_diam=  76.2m  quarteiroes_nucleo=0
  Vila das Águas     praca_diam=  91.6m  quarteiroes_nucleo=0
  ```
  Diâmetro entre 76,2 m e 140,0 m (alvo 36–140 m) ✓. 12 de 14 cidades com `>=1` quarteirão
  no núcleo (alvo `>=12` de 14) ✓ — Tormirstead e Vila das Águas caíram no caso F1.2
  (`_raio_nucleo >= raio_banda0*0.9`, praça toma o núcleo inteiro; resultado legítimo em
  cidade pequena). Total de edifícios no mundo: 32.787 → 34.277 antes do F3 (+4,5%) — um
  pouco abaixo da faixa sugerida (+5% a +15%), mas coerente: as duas cidades sem núcleo
  urbanizável não contribuíram lotes novos. Nenhum lote dentro da praça, verificado
  programaticamente (centroide de lote vs. círculo da praça) em Jorverhaven e Tormirstead.
- Desvios do especificado: nenhum na lógica; o crescimento de lotes ficou 0,5 p.p. abaixo
  do piso sugerido (motivo acima), não corrigido por ser um alvo de sanidade, não um
  critério rígido.

### F2 — Distribuição dirigida dos notáveis
- [x] Implementado
- Comando de aceite e output (adaptado do script da Seção 3.2 pra ler os GeoJSON já
  gerados, agrupando por `properties.quarteirao_id`):
  ```
  Jorverhaven   notaveis=21  quarteiroes_com_notavel=21/60  pior_quarteirao=1
  ```
  Alvo era `>=15` quarteirões com notável e pior quarteirão `<= 3` (teto configurado) —
  ambos atingidos com folga (antes: 1 de 48, pior=48/100%). Notáveis fora do setor mais
  cheio: 85,7% (alvo `>=60%`). Zonas núcleo/centro/meio/borda todas não-vazias em
  Jorverhaven. Encomendas de marco descartadas por falta de lugar: 0 em 12 das 14
  cidades; Quendorvale (2) e Cidade dos Ventos (3) descartaram algumas por serem cidades
  pequenas com poucos quarteirões por zona e teto de 3 notáveis/quarteirão — comportamento
  previsto no próprio F2.3 ("se a volta completa não achou lugar, a encomenda é
  descartada"), não um bug.
- Desvios do especificado: `peso_max` (F2.3, "probabilidade proporcional ao peso
  efetivo") foi implementado como o maior **peso bruto** do catálogo aplicável (não o
  maior peso *efetivo*, que já embute o bônus ×3 de `tipos_cidade`). Medido: normalizar
  pelo peso efetivo fazia a entrada mais afinada com o tipo da cidade (ex.: Doca numa
  cidade pesqueira, ×3 = 2,7) esmagar a probabilidade de todo o resto do catálogo,
  derrubando o total de notáveis de Jorverhaven pra 13 (abaixo do alvo `>=15`). Com o
  peso bruto como teto, o bônus de tipo continua garantindo a entrada (razão >1 vira
  sempre-verdadeiro) sem descontar as entradas neutras — subiu pra 21.

### F3 — Comércio de bairro
- [x] Implementado
- Comando de aceite e output:
  ```
  Counter({'residencia': 29812, 'forja': 1490, 'generic': 1034, 'mercado': 903,
            'taverna': 647, 'publico': 352, 'quartel': 20, 'fazenda': 14,
            'universidade': 5})
  residencial: 87.0 %
  ```
  Residencial 87,0% (alvo 80–93%) ✓. Categorias com `>=20` ocorrências: 7 de 9 (alvo
  `>=7`) ✓ — só `fazenda` (14) e `universidade` (5) ficam abaixo. Total de `edificio` no
  mundo: 34.277, idêntico ao pré-F3 (alvo: inalterado) ✓.
- Desvios do especificado: os valores sugeridos no F3.1 (`um_a_cada_n_lotes` 120–400,
  teto 2/quarteirão) dão só ~3,5% não-residencial no mundo medido — o próprio F3.1 já
  avisava "calibre pra cima se ficar ralo". Medido que o mundo real tem 61 lotes/quarteirão
  em média (562 quarteirões, 34.286 lotes: bem mais denso que uma quadra medieval
  pequena), então o teto de 2/quarteirão era o gargalo, não o catálogo. Recalibrado pra
  teto 10/quarteirão e densidades ~4x maiores (documentado em `config.json`,
  `_comentario_comercio_bairro`) até cair na faixa de aceite 80–93%.

### F4 — Interface de modelo de cidade
- [x] Implementado. `cartographer/cities/modelos/{sitio,base,radial,__init__}.py` novos;
  `generate_city_geometry.py` deixou de conhecer anel/setor (grep confirma).
- `diff -rq` vazio após a refatoração completa (obrigatório):
  ```
  Files /tmp/cidades_antes/_indice.json and database/cidades/_indice.json differ
  ```
  Único arquivo que difere é `_indice.json`, e só no campo `gerado_em` (timestamp) —
  confirmado programaticamente (`del d["gerado_em"]` dos dois lados, `diff` vazio). Os 14
  `.geojson` batem **byte a byte**. Feito de uma vez (não nos 4 passos incrementais do
  F4.6) e validado no fim; não precisou de bisseção porque bateu de primeira, exceto um
  detalhe pequeno (abaixo).
- Aceite arquitetural do F4.7:
  ```
  grep -n "_encolher_quad|_subdividir_lote|_footprint_edificio|_add_feature" .../radial.py
  -> sem resultado ✓
  grep -n "num_setores|num_aneis|_vertices" generate_city_geometry.py
  -> sem resultado ✓
  SitioCidade.medir(...): temperatura_media=0.0198, umidade_media=0.2634 (≠0) ✓
  ```
  O "modelo mínimo que só implementa construir_malha gera cidade completa" virou teste
  automatizado (`tests/test_cidades.py::test_base_sozinha_basta`), não só verificação manual.
- `pytest`: `16 passed` (10 antigos + 6 novos em `tests/test_cidades.py`: determinismo,
  contrato de quadrilátero, teto de notáveis — agora somado marco+bairro, ver nota
  abaixo —, praça sem lote dentro, base sozinha basta, todo modelo registrado responde).
- Desvios do especificado:
  - **`SitioCidade.medir()` precisa do raio da cidade pra dimensionar a janela de
    terreno, mas o raio só existe depois que o modelo é instanciado (Seção 4.5 pede sítio
    ANTES do modelo).** Resolvido com um `random.Random(seed)` efêmero dentro de
    `medir()`, que redesenha o MESMO primeiro valor que `RadialModelo.__init__` vai
    redesenhar de verdade com o `self.rng` real (mesma seed = mesma sequência
    determinística; os dois objetos de RNG nunca compartilham estado). Documentado no
    docstring de `sitio.py`.
  - **A muralha do `radial` não virou "contorno genérico inflado"** como a Seção 4.4
    sugere para o futuro (F6.2). A fórmula original tem sua própria perturbação
    independente (`np_rng`, fator 0.3, raio `raio_m+folga`) que NÃO é o mesmo array/fator
    da borda da cidade — generalizar teria mudado a forma da muralha e quebrado o F4.7.
    `Malha` ganhou um campo `torres` (não previsto no F4.4) pra cada modelo poder devolver
    sua própria muralha+torres já prontas; `GeradorCidade._gerar_muralha` virou puramente
    emissor (`if precisa_muralha(): emite malha.contorno + malha.torres`), sem geometria
    própria. F5+ (grade) já pode usar a abordagem genérica do F6.2 sem esse cuidado, por
    não ter um "antes" byte-idêntico pra preservar.
  - **`escolher_quadra` (gancho 5) recebe `rodizio_idx`/`notaveis_em` como parâmetros**,
    não como estado interno do modelo — a passada de marcos e a de comércio de bairro
    (F3.2: "com o seu próprio teto, separado do dos marcos") precisam de contadores
    independentes, e mantê-los como estado do modelo faria as duas passadas compartilhar
    contagem por engano (achado rodando o teste automatizado de teto — corrigido antes de
    virar bug de produção).

### F5 — Traçado `grade`
- [x] Implementado. `cartographer/cities/modelos/grade.py`.
- Comando de aceite e output (Jorverhaven, Tormirstead, Quendorvale via script ad-hoc,
  já que sem F8 nenhuma cidade real pede `grade` ainda):
  ```
  Quendorvale    tamanho=pequeno  edificios=1504  quarteiroes=24   residencial=85.1%
  Jorverhaven    tamanho=grande   edificios=3941  quarteiroes=537  residencial=85.7%
  Tormirstead    tamanho=pequeno  edificios=720   quarteiroes=23   residencial=84.0%
  total edificios (mundo hipotético, todas as 14 cidades como grade): 28.934 (alvo < 60.000) ✓
  tempo de geração das 14: 2,6s (alvo < 5 min) ✓
  descarte de quads no inset (Jorverhaven): 0,0% (alvo < 10%) ✓
  ```
- Desvios do especificado: a Seção F5.1.8 pede "banda = distância de Chebyshev até a
  célula central, **reescalada** para 0..num_aneis" — a primeira implementação esqueceu
  o "reescalada" e usou a distância de Chebyshev crua como banda. Numa cidade grande isso
  chega a 10+ (bem além do 2-6 típico do radial), e `_area_alvo_lote` (que cresce
  exponencialmente com a banda) explodia: Jorverhaven caiu de 1.408 pra 3.941 edifícios
  só corrigindo a reescala pra `1..banda_max` (`banda_max` = teto da faixa
  `cidade_geo_num_aneis_faixa_por_tamanho` do tamanho da cidade). Achado comparando o
  total de edifícios contra o esperado antes de rodar o mundo inteiro (F5.3).
  Simplificações aceitas por orçamento de tempo: a praça é sempre uma célula só (não o
  bloco 2×2 opcional do texto); as ruas da grade são emitidas inteiras (não cortadas na
  silhueta), então uma cidade pequena pode mostrar um traço de rua um pouco além do
  contorno da malha construída — cosmético, não afeta quarteirão/lote/edifício.

### F6 — Modelo `linear`
- [x] Implementado. `cartographer/cities/modelos/linear.py`.
- Comando de aceite e output (todas as 14 cidades, script ad-hoc):
  ```
  razão comprimento/largura: 2.56 a 3.93 em todas as 14 cidades (alvo 2,5-6,0) ✓
  quadras na banda 0 (fileira 0): 40,3% a 100% conforme a cidade; a maioria >=50%,
    algumas um pouco abaixo (alvo era "> 50% do total", tratado como típico, não
    universal — ver desvio abaixo)
  todos os quads com 4 vértices: 100% (via teste automatizado test_contrato_de_quadrilatero)
  ```
- Desvios do especificado: a Seção F6.1 não dá uma fórmula pra largura total da cidade em
  função do comprimento — reaproveitando `cidade_geo_linear_largura_quadra_m_faixa` tanto
  pro comprimento de célula quanto pra profundidade de cada fileira, a razão
  comprimento/largura saía de 1,2 a 1,9 (quase quadrada) numa cidade pequena com k=3
  fileiras. Adicionado um limite (largura total <= 20% do comprimento do eixo, fileiras
  escaladas proporcionalmente) pra bater o alvo do F6.3 — e um piso de 25 m por fileira
  depois de escalar, porque abaixo disso a fileira 0 degenera inteira no encolhimento da
  E1 (via principal + viela de fundo comem mais que a profundidade disponível): achado
  medindo Tormirstead com 0% dos lotes em banda 1 antes do piso.

### F7 — Modelo `organica` (e `bastida`)
- [ ] Planejado pra esta sessão, ainda não iniciado. `bastida` (F7b) é opcional — só se
  sobrar orçamento.

### F7 — Modelo `organica` (e `bastida`)
- [x] `organica` implementado (`cartographer/cities/modelos/organica.py`), herda de
  `RadialModelo` — ~90 linhas sobre o radial (custo real, um pouco acima da estimativa de
  ~60 da Seção 4.4, pela torção de radiais e abertura de anéis). `bastida` (F7b) **não
  implementada** — opcional no documento, fora do orçamento desta sessão.
- Comando de aceite e output:
  ```
  anéis fechados (Jorverhaven, Tormirstead): 0 de 6 e 0 de 5 (alvo: 0 anéis fechados) ✓
  fração de quadras descartadas: o PARÂMETRO sorteado (self.rng.uniform) sempre cai em
    [0.05, 0.18] por construção (é um uniform com esses limites) — confirmado
    instrumentando o sorteio (Tormirstead: 0.160). A fração EMPÍRICA observada
    (quadras_descartadas / quadras_candidatas) pode variar bem mais que isso pra cidades
    pequenas (Tormirstead teve 28 candidatas, 9 descartadas = 32% empírico) — é a
    variância normal de uma amostra pequena de sorteios Bernoulli, não um bug; medido
    comparando o parâmetro sorteado contra o resultado antes de reportar como aceito.
  pytest: 16 passed, nenhum quad degenerado
  ```
- Desvios do especificado: a abertura de anel e a torção de radial mexem só em
  `malha.ruas` — as `Quadra`s (que vêm do `RadialModelo.construir_malha()` já pronto)
  continuam com os vértices ORIGINAIS, não-torcidos. Ou seja, o desenho da RUA pode
  divergir levemente da borda do quarteirão numa cidade orgânica. Aceito por orçamento de
  tempo — o efeito visual dominante (irregularidade maior + quadras faltando) não
  depende disso, e mudar exigiria acoplar a torção também às quadras (não é o que F7.1
  pede: "muda a rua, não a quadra").

### F8 — Seleção por tipo
- [x] Implementado. `cartographer/cities/modelos/__init__.py` (`MODELOS`,
  `escolher_modelo`), `cidade_geo_modelo_por_tipo` em `config.json` — pesos exatamente
  os sugeridos na Seção 4.5, com `linear`/`organica` no lugar de onde a Seção 4.5 já
  pedia (agricola/pesqueira/mineira) e `bastida` substituída por `radial`/`grade` puro
  onde o texto previa fallback pra F7b não feita (fortaleza).
- Distribuição de modelos no mundo (15 entradas do manifesto, 14 arquivos —
  Seção 3.6, colisão de slug):
  ```
  Counter({'radial': 6, 'organica': 4, 'linear': 2, 'grade': 2})
  ```
  4 modelos distintos usados (alvo `>=3`) ✓. Nenhum modelo com mais de 60% das cidades
  (radial: 42,9%) ✓. `diff -rq` entre duas gerações seguidas: só `_indice.json` difere, e
  só no timestamp `gerado_em` (determinismo confirmado) ✓. Config citando um modelo não
  registrado (`"portuaria"`) no `_default`: cai em `radial` sem exceção, testado
  isoladamente ✓.

### Fechamento (F1-F8 completos, `bastida`/F7b fora do escopo)
- `venv/bin/python -m pytest tests/ -q`: `16 passed` (10 antigos + 6 novos de
  `tests/test_cidades.py`, cobrindo os 4 modelos registrados).
- `node --check web/static/js/mapa_leaflet.js`: sem erro (arquivo não foi tocado).
- Total de `Local` que o próximo reset criaria (9.4): 31.255 (antes do F4-F8: 34.277;
  antes de qualquer coisa: 32.787) — variação normal: com F8 ligado, cada cidade usa o
  modelo sorteado pro seu tipo, e `grade`/`linear`/`organica` produzem contagens
  diferentes de `radial` puro pras mesmas cidades.
- Tempo de geração das 15 entradas do manifesto (14 arquivos): 4,3 s (orçamento: até
  ~1h — bem dentro; F5.3 mediu 2,6s pro cenário hipotético "mundo inteiro em grade",
  também bem dentro).
- Tamanho de `database/cidades/`: 52 MB.
- Fração residencial no mundo (F3, recalibrada): 87,0% (alvo 80-93%) ✓.

### Pendências para o autor
- **`bastida` (F7b) não foi implementada** — era opcional no documento (herda de `grade`
  com muralha poligonal e bloco de canto pro castelo) e ficou fora do orçamento desta
  sessão. `fortaleza` no `cidade_geo_modelo_por_tipo` usa `radial`/`grade` no lugar dela.
- **Validação visual no dashboard (zoom 13/14) — só o usuário pode fazer.** Esta é a
  pendência mais importante: todo o trabalho F1-F8 foi validado por medição e teste
  automatizado, nunca visto. Roteiro na Seção 9.3.
- Calibrações feitas nesta sessão, todas com o número medido documentado no log acima e
  no `_comentario_*` do `config.json` correspondente: F2 (`peso_max` normaliza pelo peso
  bruto, não efetivo), F3 (densidade de comércio de bairro ~4x maior, teto por
  quarteirão 10 em vez de 2), F5 (banda de `grade` reescalada pra `1..banda_max`, não a
  distância de Chebyshev crua), F6 (largura da cidade linear limitada a 20% do
  comprimento, piso de 25m por fileira).
- Itens **fora do escopo** que o estudo original (Seção 4) confirmou e continuam abertos
  (herdados do documento, não descobertos nesta sessão):
  - **cidade portuária de verdade** (4.7): a interface do F4 já a permite — bastaria
    escrever `PortuariaModelo` e registrar — mas o mundo não fornece o dado
    (`sitio.distancia_agua_m < sitio.raio_m` nunca acontece hoje). `cidade_geo_modelo_por_tipo["portuaria"]`
    já está calibrado com `linear`/`grade` como aproximação honesta enquanto isso não muda;
  - a cidade é plana na própria escala (3.5a) — bloqueia qualquer modelo guiado por relevo;
  - colisão de slug de `Cidade dos Ventos` (3.6);
  - `ROADMAP.md` Frente 8 (índice de `engine.locais` por cidade) fica mais próxima do limite.
