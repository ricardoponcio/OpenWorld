# DIAGNÓSTICO V3 — Escala, Cidades e Zoom

> **Para quem é este documento**: para o modelo/desenvolvedor que vai corrigir os problemas
> encontrados na validação humana de 2026-09-11, depois que as Fases 0–4 do
> [`PLANO_EVOLUCAO_V2.md`](PLANO_EVOLUCAO_V2.md) foram concluídas.
>
> **Este documento é auto-suficiente para as correções que ele descreve.** Você não precisa
> reler o plano inteiro. Leia, nesta ordem:
> **Seção 0** (regras de trabalho) → **Seção 1** (resumo: o que o usuário viu × o que está errado)
> → **Seção 2** (modelo de escala — **obrigatório, é a raiz de quase tudo**) → o achado (D1…D8)
> que você vai corrigir → **Seção 11** (ordem de execução).
>
> **Se a sua tarefa é o campo de detalhe local** (o D2), vá direto para a
> **[Seção 13](#13-especificação-de-implementação--caminho-b-campo-de-detalhe-local)**: ela é
> uma especificação de implementação completa, com o código, os valores de config calibrados e
> os testes novos. Leia a Seção 2 antes, mesmo assim.
>
> **Todo número neste documento foi medido**, não estimado. Cada achado traz o comando que
> reproduz a medição. Se você mudar o mundo (novo reset), rode o comando de novo antes de
> confiar no número.

**Revisão**: 2026-09-11 (v1.1 — some a Seção 13, especificação do Caminho B do D2, prototipada
e medida a pedido do usuário. v1.0 era só o diagnóstico.)
**Estado do mundo medido**: `database/world_manifest.json`, seed do manifesto, 5 continentes,
15 cidades, 14 arquivos em `database/cidades/`.

---

## 0. Regras de trabalho — leia antes de tocar em qualquer coisa

Estas são as mesmas regras da Seção 0 do `PLANO_EVOLUCAO_V2.md`. Elas continuam valendo.
Repetidas aqui porque este documento é auto-suficiente:

1. **Nunca escreva em `database/` enquanto uma simulação ou reset estiver rodando.**
   Verifique **antes de qualquer coisa**:
   ```bash
   ps aux | grep -E "run_simulation|reset_|populate|generate_|run_dashboard" | grep -v grep
   ```
   Se aparecer `run_simulation.py`, pare: você pode corromper o `openworld.db`.
   Peça ao usuário para parar a simulação, ou trabalhe só em leitura.

2. **Use sempre `venv/bin/python`**, nunca `python3` ou `python`. As dependências
   (numpy, scipy, PIL) só existem dentro do venv.

3. **"Compila" não é teste.** Toda correção deve terminar com um comando que **roda** e cujo
   **output real** você cola no log da sua sessão. Um arquivo que importa sem erro não prova
   nada sobre geometria, escala ou renderização.

4. **Todo número novo vai para o `config.json`**, lido via `cfg_get`. Nunca deixe um literal
   numérico novo no meio do código Python. Se você precisa de uma constante, ela nasce no
   `config.json` com um `_comentario_` explicando de onde ela veio.

5. **Não invente uma nova convenção de coordenada.** O projeto já tem três sistemas
   (mundo em px, local da cidade em metros, GeoJSON/Leaflet em `[lng, lat]`). Eles estão
   descritos na Seção 2. Use os que existem.

6. **Não commite nada.** O usuário valida e commita. (Restrição vigente desde 2026-09-10.)

7. Ao concluir um achado: preencha a Seção 12 (log) deste documento e some uma linha no
   "Log de Sessões" do [`ROADMAP.md`](ROADMAP.md).

---

## 1. Resumo executivo — o que o usuário viu × o que está errado

O usuário validou o mapa e relatou **três** sintomas. A investigação encontrou **oito** defeitos,
porque alguns sintomas têm mais de uma causa e alguns defeitos ainda não tinham sido percebidos.

### 1.1 Mapa sintoma → achado

| Sintoma relatado pelo usuário | Achados responsáveis |
|---|---|
| *"zoom meio que infinito… chega a borrar a imagem de tão baixo"* | **D5** (sem `maxNativeZoom`), **D2** (o raster não tem detalhe abaixo de ~z6) |
| *"navegação um pouco lenta no zoom out"* | **D5** (17 níveis de tile real), **D6** (cada tile custa 0,19–0,55 s) |
| *"cidades não existem mais… ainda é 1px na cidade"* | **D3** (camada desligada por padrão), **D1** (cidade 15,8× menor que o projetado), **D7** (a "vista de cidade" mostra 380 km de lado), **D2** |
| *"não existe relação do que está na cidade × a posição no continente"* | **D1**, **D7**, **D2** |
| *"tem uma cidade na água"* | **D4** (na verdade **todas as 15** estão na linha d'água) |

### 1.2 Tabela de achados

| # | Achado | Severidade | Tipo | Arquivo principal |
|---|---|---|---|---|
| **D1** | Erro de unidade: área (km²/px) usada como escala linear (km/px). A cidade é desenhada **15,81× menor** que o projetado | 🔴 Crítico | Bug | `cartographer/cities/generate_city_geometry.py:78` |
| **D2** | O raster do mundo não produz detalhe novo abaixo de ~z6. Do z7 em diante é ampliação pura | 🟠 Estrutural | Limitação de design | `cartographer/tiles/render.py` + config de ruído |
| **D3** | A camada "Detalhe da Cidade" **não é ligada por padrão**, e a camada `lote` nunca é registrada no front | 🔴 Crítico | Bug | `web/static/js/mapa_leaflet.js:40,145` |
| **D4** | **Todas as 15 cidades** ficam no pixel exato da linha d'água (percentil 0,00–0,07% de altitude) | 🔴 Crítico | Bug de algoritmo | `cartographer/cities/generate_cities_metadata.py:24` |
| **D5** | Leaflet pede tile **real** em todos os 17 níveis de zoom; falta `maxNativeZoom` | 🟠 Alto | Bug de configuração | `web/static/js/mapa_leaflet.js:102` |
| **D6** | Cada tile custa 0,19–0,55 s de CPU; uma tela cheia são ~54 tiles | 🟠 Alto | Performance | `cartographer/tiles/render.py` |
| **D7** | `/api/cidade/<nome>/imagem` renderiza uma janela de **380 km de lado** e a chama de "cidade" | 🟠 Alto | Bug de escala | `config.json` (`cidade_janela_raio_px`) |
| **D8** | O cache de tiles é ilimitado e nunca limpa hashes de config antigos | 🟡 Baixo | Higiene | `cartographer/tiles/render.py` |

### 1.3 A frase que resume tudo

> **O projeto tem um mundo em escala continental e uma cidade em escala de pedestre, e a ponte
> entre as duas escalas está com um erro de unidade de 15,81×.** Corrigir D1 é o que destrava
> D3, D7 e boa parte da sensação de "a cidade não existe".

---

## 2. Modelo de escala — OBRIGATÓRIO ler antes de mexer em qualquer coisa

Esta seção é a que mais importa. Quase todos os achados são erro de escala. **Se você não
entender esta seção, você vai reintroduzir o bug D1 em outro lugar.**

### 2.1 As três escalas do projeto

| Sistema | Unidade | Origem | Onde vive |
|---|---|---|---|
| **Mundo** | pixel de mundo (`px`) | canto superior esquerdo do mapa global | `world_manifest.json`, `mapa_composto.npz`, `Local.coordenadas`, `TileCartographer.gerar_janela` |
| **Local da cidade** | metro (`m`) | **centro da cidade** | só dentro de `generate_city_geometry.py`, enquanto a geometria é construída |
| **GeoJSON / Leaflet** | `[lng, lat]` | igual ao mundo, mas com `lat` invertido | `database/cidades/*.geojson`, `database/features/*.geojson`, `mapa_leaflet.js` |

Conversão mundo → GeoJSON (já existe, **não mude**):
```
lng = x_mundo
lat = -y_mundo          # L.CRS.Simple: o eixo Y do Leaflet cresce para CIMA
```

### 2.2 A armadilha: `escala_pixel_area_km2` é ÁREA, não comprimento

No `config.json`:
```json
"escala_pixel_area_km2": 250
```

Isso significa: **1 pixel de mundo cobre 250 km² de área**. É uma área. Para virar comprimento
você **precisa tirar a raiz quadrada**:

```
lado_do_pixel_em_km = sqrt(250) = 15,811 km
metros_por_pixel    = sqrt(250) * 1000 = 15.811,4 m
```

O resto do projeto já faz isso certo. Veja `cartographer/world/tile_cartographer.py:59`:
```python
R = np.sqrt(area / (np.pi * escala_pixel_area_km2)) * fator_visual
```
A raiz está lá porque `area / (pi * escala)` é uma área em pixels e o raio é o lado.

**`generate_city_geometry.py` esqueceu a raiz.** Isso é o D1.

### 2.3 Tabela de referência (decorou isto, você não erra mais)

```
1 px de mundo            = 15,81 km        = 15.811 m
mundo inteiro (768 px)   = 12.143 km de lado
cidade pequena (r=350m)  = 0,0443 px de mundo de diâmetro
cidade média   (r=600m)  = 0,0759 px de mundo de diâmetro
cidade grande  (r=900m)  = 0,1138 px de mundo de diâmetro
```

Reproduza:
```bash
venv/bin/python - <<'EOF'
import math, sys; sys.path.insert(0,'.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from config import cfg_get
m_por_px = math.sqrt(cfg_get(C,'escala_pixel_area_km2')) * 1000
print('metros por pixel de mundo =', round(m_por_px,1))
for tam, r in cfg_get(C,'cidade_geo_raio_m_por_tamanho').items():
    print(f'  {tam:8} diametro = {2*r/m_por_px:.4f} px de mundo')
EOF
```

### 2.4 A consequência que você precisa aceitar

Mesmo **depois** de corrigir D1, **a cidade continua sendo sub-pixel no mapa do mundo**. Uma
cidade grande tem 0,11 px de diâmetro. Isso **não é um bug** — é o que acontece quando você
põe uma cidade de 1,8 km num mundo onde o pixel tem 15,8 km.

Portanto: **a cidade nunca vai "aparecer" no raster do mundo.** Ela só existe como geometria
vetorial, que o Leaflet desenha por cima em zooms altos. Qualquer solução que tente fazer a
cidade aparecer no PNG do tile está no caminho errado. Ver D2 e D7 para as duas saídas viáveis.

---

## 3. D1 — Erro de unidade: a cidade é desenhada 15,81× menor que o projetado

🔴 **Crítico. Corrija este primeiro — D3 e D7 dependem dele.**

### 3.1 Sintoma

O usuário chega no zoom máximo e a cidade ainda é um pontinho. A geometria (ruas, muralha,
85 edifícios) existe nos arquivos, o back-end serve tudo corretamente, mas tudo está amontoado
num espaço 15,8× menor do que a config diz.

### 3.2 Medição

A cidade Pelamont está configurada como `grande` → `cidade_geo_raio_m_por_tamanho.grande = 900 m`
→ diâmetro 1.800 m → **deveria** ocupar 0,1138 px de mundo (Seção 2.3).

```bash
venv/bin/python -c "
import json
d=json.load(open('database/cidades/pelamont.geojson'))
def flat(c):
    if isinstance(c[0],(int,float)): yield c
    else:
        for x in c: yield from flat(x)
for cam in ('edificio','muralha','rua'):
    pts=[p for f in d['features'] if f['properties']['camada']==cam for p in flat(f['geometry']['coordinates'])]
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    print(cam, 'n_pts', len(pts), 'largura', round(max(xs)-min(xs),6), 'altura', round(max(ys)-min(ys),6))
"
```

Saída real medida:
```
edificio n_pts 85 largura 0.006106 altura 0.006463
muralha  n_pts  9 largura 0.007326 altura 0.007350
rua      n_pts 93 largura 0.006914 altura 0.007287
```

A muralha inteira mede **0,0073 px** de largura. O esperado era 0,1138 px.

```
0,1138 / 0,0073 = 15,6   →   praticamente exatamente sqrt(250) = 15,81
```

O fator de erro **é** a raiz quadrada que está faltando. Não é coincidência.

### 3.3 Causa raiz

`cartographer/cities/generate_city_geometry.py`, linhas 12 (docstring) e 78:

```python
def _mundo(self, x_m, y_m):
    metros_por_px = self.escala_pixel_area_km2 * 1000.0     # ❌ 250 * 1000 = 250.000 m/px
    return self.cx_mundo + x_m / metros_por_px, self.cy_mundo + y_m / metros_por_px
```

`escala_pixel_area_km2 * 1000` trata 250 km² como se fosse 250 km. O valor correto é
`sqrt(250) * 1000 = 15.811,4`.

O comentário no `config.json:232` repete o mesmo erro em texto:
*"a cidade é sub-pixel na escala do mundo, 1 px_mundo ≈ 250km"*. **1 px de mundo é 15,8 km,
não 250 km.** Esse comentário precisa ser corrigido junto, senão o próximo modelo lê e repete
o erro.

### 3.4 Impacto no app

- Toda a geometria de cidade está 15,8× comprimida. Ruas, quarteirões, lotes e muralha ficam
  amontoados num espaço de ~116 m em vez de 1.800 m.
- Os `zoom_min` das camadas (`ZOOM_MIN_POR_CAMADA`, linha 94) foram calibrados **contra o bug**.
  Eles estão 4 níveis de zoom altos demais (`log2(15,81) ≈ 3,98`).
- Isso forçou `tile_zoom_maximo_ui` a subir para 16, o que causou D5 (lentidão) e a sensação
  de "zoom infinito borrado" que o usuário relatou. **O zoom infinito é sintoma deste bug.**
- As coordenadas dos `Local` no `openworld.db` (85 por cidade em Pelamont) estão todas no
  mesmo erro — os NPCs andam num mapa 15,8× menor do que a config afirma.

### 3.5 Solução

**Passo 1** — Crie a conversão correta em um único lugar. No `config.json`, adicione um
comentário explicando (o valor em si é derivado, não precisa de chave nova):

```json
"_comentario_escala_linear": "escala_pixel_area_km2 é ÁREA (km² por pixel). Para converter metro -> pixel de mundo use metros_por_px = sqrt(escala_pixel_area_km2) * 1000 = 15811,4. Erro histórico (D1 do DIAGNOSTICO_V3): generate_city_geometry.py usava escala*1000 e desenhava a cidade 15,81x menor."
```

**Passo 2** — Corrija `generate_city_geometry.py:78`:

```python
def _mundo(self, x_m, y_m):
    # escala_pixel_area_km2 é ÁREA (km²/px). O lado do pixel é a RAIZ dela.
    # Ver Seção 2.2 do docs/DIAGNOSTICO_V3.md — D1.
    metros_por_px = math.sqrt(self.escala_pixel_area_km2) * 1000.0
    return self.cx_mundo + x_m / metros_por_px, self.cy_mundo + y_m / metros_por_px
```

Corrija também a docstring da linha 12 e o `_comentario_cidade_geo` do `config.json:232`.

**Passo 3** — Recalibre `ZOOM_MIN_POR_CAMADA` (linha 94). Não chute: derive da fórmula

```
zoom_min = ceil( log2( alvo_px_de_tela / diametro_px_de_mundo ) )
```

onde `alvo_px_de_tela` é o tamanho que a cidade inteira precisa ter na tela para aquela camada
ficar legível. Valores calculados (já com a escala corrigida):

| camada | alvo px de tela | cidade pequena | cidade média | cidade grande |
|---|---|---|---|---|
| `muralha`, `praca`, `portao`, `torre` | 120 | 12 | 11 | 11 |
| `rua`, `quarteirao` | 350 | 13 | 13 | 12 |
| `edificio` | 700 | 14 | 14 | 13 |
| `lote` | 1400 | 15 | 15 | 14 |

Note que o `zoom_min` agora depende **do tamanho da cidade também**, não só da camada. Hoje
`ZOOM_MIN_POR_CAMADA` é um dicionário fixo. Transforme-o em função de `(camada, tamanho)` e
mova a tabela para o `config.json` (regra 4 da Seção 0).

**Passo 4** — Depois de regenerar, reveja `tile_zoom_maximo_ui`. Com a escala correta, o zoom
útil máximo é **z15** (cidade grande ocupando ~2 telas). Ver D5.

### 3.6 Critério de aceite

```bash
# 1. Regenerar a geometria (SÓ com a simulação parada!)
venv/bin/python cartographer/cities/generate_city_geometry.py

# 2. A muralha de uma cidade grande deve medir ~0,1138 px de mundo (±5%)
venv/bin/python -c "
import json
d=json.load(open('database/cidades/pelamont.geojson'))
pts=[p for f in d['features'] if f['properties']['camada']=='muralha' for p in f['geometry']['coordinates']]
xs=[p[0] for p in pts]
larg=max(xs)-min(xs)
print('largura da muralha:', round(larg,6), 'px de mundo')
assert 0.108 < larg < 0.120, f'FALHOU: esperado ~0.1138, veio {larg}'
print('OK')
"
```

### 3.7 Não faça

- ❌ **Não** "corrija" mudando `escala_pixel_area_km2` de 250 para outro valor. Essa chave está
  certa e é usada pelo cálculo de raio de continente (`tile_cartographer.py:59`) e pelo cálculo
  de área real (`world_manager.py:89`). Mudar ela quebra a calibração de continentes da Fase 1.
- ❌ **Não** introduza uma segunda chave de config tipo `escala_pixel_km_linear: 15.81`. Ela
  poderia dessincronizar da área. Derive sempre com `sqrt()`.
- ❌ **Não** aplique um "fator de correção" de 15,81 em cima do código errado. Corrija a fórmula.

---

## 4. D2 — O raster do mundo não tem detalhe abaixo de ~z6

🟠 **Estrutural. Não é um bug — é um limite de design que precisa ser assumido e comunicado.**

### 4.1 Sintoma

O usuário: *"chega até a borrar a imagem de tão baixo que chega"*. A partir de um certo zoom,
o terreno vira uma mancha de cor lisa. Não aparece mais nenhuma montanha, rio, textura.

### 4.2 Medição

Medimos o gradiente médio da imagem (quanto a altitude muda de um pixel de tela para o vizinho).
Se o terreno ganhasse detalhe novo a cada zoom, o gradiente ficaria estável. Se ele só estica,
o gradiente cai pela metade a cada nível.

```bash
venv/bin/python - <<'EOF'
import json, sys; sys.path.insert(0,'.')
import numpy as np
from cartographer.config import CARTOGRAPHER_CONFIG as C
from config import cfg_get
from cartographer.tiles.render import oitavas_extra_por_zoom
from cartographer.world.tile_cartographer import TileCartographer
m = json.load(open('database/world_manifest.json'))
ts = cfg_get(C,'tile_size_px')
tc = TileCartographer(size=ts, seed=m['seed'], config=C,
                      layout_continentes=m['layout_continentes'],
                      tamanho_global=m['dimensao_global'])
cx, cy = 507.0, 397.0   # Pelamont, em terra
for z in range(6, 17):
    oe = oitavas_extra_por_zoom(z); lado = ts / (2**z)
    a = tc.gerar_janela(cx, cy, cx+lado, cy+lado, ts, ts, oitavas_extra=oe)[:,:,0]
    print(f'z={z:>2} oitavas_extra={oe} janela={lado:8.4f}px grad={np.abs(np.diff(a,axis=1)).mean():.3e}')
EOF
```

Saída real medida:
```
z= 6 oitavas_extra=6 janela=  4.0000px grad=1.199e-04
z= 7 oitavas_extra=7 janela=  2.0000px grad=5.477e-05
z= 8 oitavas_extra=8 janela=  1.0000px grad=3.138e-05
z= 9 oitavas_extra=9 janela=  0.5000px grad=1.652e-05
z=10 oitavas_extra=9 janela=  0.2500px grad=6.378e-06
z=11 oitavas_extra=9 janela=  0.1250px grad=3.297e-06
z=12 oitavas_extra=9 janela=  0.0625px grad=1.532e-06
z=13 oitavas_extra=9 janela=  0.0312px grad=4.360e-07
z=14 oitavas_extra=9 janela=  0.0156px grad=1.355e-07
z=15 oitavas_extra=9 janela=  0.0078px grad=9.912e-08
z=16 oitavas_extra=9 janela=  0.0039px grad=4.953e-08
```

**O gradiente cai pela metade a cada nível desde o z6.** De z6 a z16 ele cai 2.400×. Do z10 em
diante as oitavas nem aumentam mais (travadas em 9 pelo teto `tile_oitavas_max: 12` menos as
3 de `ruido_macro_oitavas`).

### 4.3 Causa raiz

Duas causas somadas:

1. **Teto de oitavas.** `tile_oitavas_max: 12` com `ruido_macro_oitavas: 3` → no máximo 9
   oitavas extras. Do z10 em diante nenhuma oitava nova entra.
2. **Amplitude decai geometricamente.** `persistencia: 0.5` significa que a oitava *n* tem
   amplitude `0,5^n`. A 12ª oitava contribui com `0,5^12 ≈ 0,00024` do total. Mesmo que você
   **aumentasse** `tile_oitavas_max`, o detalhe novo teria amplitude perto de zero e continuaria
   invisível na rampa de cor (que mapeia altitudes de 0,35 a 0,80).

⚠️ Este é o ponto que o comentário do `config.json:339` erra: ele diz *"oitavas saturam perto
de z9"*. A medição mostra que o **detalhe visível** satura no **z6**, três níveis antes.
Corrija esse comentário.

### 4.4 Impacto no app

- O raster é honesto e útil de z0 a ~z6. De z7 a z16 ele é ampliação — bonito como fundo, mas
  não é informação.
- Como a geometria de cidade precisa de z11+ para aparecer (D1/D3), **a cidade sempre vai ser
  desenhada sobre um fundo liso e borrado**. Isso é exatamente o que o usuário descreveu: a
  cidade não tem relação visual com o terreno onde ela está.
- É por isso que a queixa *"não existe relação do que está na cidade × a posição no continente"*
  não se resolve só consertando D1. Mesmo com a escala certa, não há terreno para se relacionar.

### 4.5 Solução — três caminhos, escolha um (peça a decisão ao usuário)

**Caminho A — Assumir o limite (mais barato, recomendado como primeiro passo).**
Trave `maxNativeZoom` no z6 (ver D5) e deixe o Leaflet ampliar a imagem. O raster para de
consumir CPU inutilmente. A cidade continua sobre fundo liso, mas o app fica rápido e honesto.
Custo: ~1 hora. Não resolve a queixa da relação cidade↔terreno.

**Caminho B — Campo de detalhe local dedicado (resolve a queixa de verdade).**
Adicione ao `TileCartographer.gerar_janela` um **segundo campo de ruído**, independente do fBm
global, que só liga abaixo de uma certa escala de janela. Ele tem **amplitude própria** (não
herdada da persistência do fBm global), escala em metros, e é seedado pelas coordenadas de
mundo (para continuar sendo função pura — invariante F1 do plano V2).

Esboço do contrato:
```
detalhe_local(x_mundo, y_mundo, seed) -> [0,1]
  escala: cidade_detalhe_escala_m   (ex.: 200 m — colinas, bosques)
  amplitude: cidade_detalhe_amplitude (ex.: 0.04 da faixa de altitude)
  só é somado quando a janela pedida tem menos de N px de mundo de lado
```
⚠️ **Cuidado com a invariante F1 (pureza)**: ligar/desligar o campo por tamanho de janela
**viola** a pureza se feito ingenuamente — o mesmo ponto do mundo teria altitude diferente
em z5 e em z12. A forma correta é o campo **sempre** existir na função, mas ter amplitude tão
pequena que nos zooms baixos ele some por reamostragem naturalmente. Leia a Seção 2 do
`PLANO_EVOLUCAO_V2.md` (invariantes F1–F4) antes de implementar isto.
Custo: alto. É uma fase própria.

**Caminho C — Vista de cidade separada (resolve a queixa por outro ângulo).**
Em vez de esticar o mapa do mundo, faça a cidade ter **seu próprio mapa Leaflet**, com CRS
próprio em metros, alimentado por um raster gerado especificamente para a cidade (ruído local
seedado pelo nome da cidade, como a geometria já faz). O mapa do mundo mostra um marcador; o
clique abre a vista de cidade. Isto é o que a branch antiga fazia com `city_roi_zoom.py`, mas
feito certo. Ver D7. Custo: médio.

### ✅ DECISÃO DO USUÁRIO (2026-09-11): **Caminho B**

> *"sei que o caminho B do D2 é mais custoso, mas eu prefiro me preparar agora do que depois
> ter que mexer nisso"*

O Caminho B foi escolhido e **prototipado nesta sessão**. O protótipo foi medido contra as
invariantes do projeto e passou em todas. A especificação completa de implementação, com o
código, os valores de config calibrados por medição e os testes novos, está na
**[Seção 13](#13-especificação-de-implementação--caminho-b-campo-de-detalhe-local)**.

O Caminho A continua valendo como etapa independente: ele é a configuração de `maxNativeZoom`
do D5. Com o Caminho B implementado, o `maxNativeZoom` **sobe de 6 para 11**, porque aí passa a
existir informação real nessa faixa. O 11 não é chute: é o zoom em que a oitava mais fina do
campo de detalhe fica totalmente resolvida. A fórmula está na Seção 13.7.

### 4.6 Critério de aceite (para o Caminho A)

```bash
# Com maxNativeZoom=6, o Leaflet não deve pedir nenhum tile acima de z6.
# Abra o mapa, vá até o zoom máximo, e confira o log do Flask:
# não pode aparecer nenhuma linha "GET /tiles/7/..." ou superior.
```

---

## 5. D3 — A camada "Detalhe da Cidade" vem desligada, e `lote` nunca é registrada

🔴 **Crítico e barato de consertar. É a causa direta de "cidades não existem mais".**

### 5.1 Sintoma

O usuário: *"cidades não existem mais… eu nem sei se isso foi feito pois não consigo ver a cidade"*.
Ele não conseguia ver porque **a camada nunca é adicionada ao mapa**. Ela existe no controle
de camadas como uma caixinha desmarcada, no canto da tela, e nada indica que ela tem conteúdo.

### 5.2 Medição

O back-end está **perfeito**. Com o dashboard rodando:

```bash
curl -s "http://127.0.0.1:5000/api/mapa/features?camadas=muralha,rua,edificio,lote&bbox=506.9,396.9,507.1,397.1&z=14" \
  | venv/bin/python -c "import json,sys; [print(k, len(v['features'])) for k,v in json.load(sys.stdin).items()]"
```

Saída real medida:
```
edificio 85
lote 85
muralha 1
rua 13
```

Tudo está lá. O problema é 100% no front-end.

### 5.3 Causa raiz

`web/static/js/mapa_leaflet.js`:

**Linha 40** — a camada `lote` **não está na lista**:
```javascript
const CAMADAS_DETALHE_CIDADE = ['muralha', 'torre', 'portao', 'praca', 'rua', 'quarteirao', 'edificio'];
//                                                                                    ↑ falta 'lote'
```
Os 85 lotes de cada cidade são gerados, salvos e servidos pela API — e nunca desenhados.

**Linha 145** — só a camada `cidades` entra no mapa por padrão:
```javascript
leafletCamadasVetoriais['cidades'].addTo(leafletMap);
```
O grupo `grupoDetalheCidade` (linha 149) é registrado no controle (linha 157) mas **nunca**
recebe `.addTo(leafletMap)`.

### 5.4 Impacto no app

- Todo o trabalho da Fase 4 (geometria de cidade) fica invisível para quem não souber que
  existe uma caixinha para marcar. Foi exatamente o que aconteceu na validação.
- Os lotes são desperdício puro: ocupam espaço nos 14 arquivos GeoJSON, são filtrados e
  serializados a cada request da API, e nunca chegam à tela.

### 5.5 Solução

**Passo 1** — Inclua `lote` na linha 40:
```javascript
const CAMADAS_DETALHE_CIDADE = ['muralha', 'torre', 'portao', 'praca', 'rua', 'quarteirao', 'lote', 'edificio'];
```
Confirme que `ESTILO_CAMADA_CIDADE` tem uma entrada para `lote` (estilo de polígono). Se não
tiver, adicione — sem estilo o Leaflet desenha com o azul padrão e fica feio.

**Passo 2** — Ligue o grupo por padrão, logo depois da linha 157:
```javascript
// D3 do DIAGNOSTICO_V3: o grupo entra LIGADO. As camadas internas já têm zoom_min
// (nada é desenhado em zoom baixo), então ligar por padrão não custa nada em
// performance e é a única forma do usuário descobrir que a cidade existe.
grupoDetalheCidade.addTo(leafletMap);
```

**Passo 3 (o que realmente resolve a experiência)** — Afordância de zoom. Hoje, quando o
usuário está no z8 olhando um marcador de cidade, nada diz a ele *"continue aproximando, tem
uma cidade inteira aqui"*. Adicione, no popup/tooltip do marcador de cidade da camada `cidades`,
uma linha do tipo:
> *Zoom 11+ para ver as ruas · zoom 13+ para ver os edifícios*

E no `criarMarcadorFeatureLeaflet`, um duplo-clique que faça `leafletMap.flyTo(latlng, 13)`.

### 5.6 Critério de aceite

```bash
node --check web/static/js/mapa_leaflet.js && echo "sintaxe OK"
```
E, no navegador: abrir o mapa, dar duplo-clique numa cidade grande, e **ver muralha, ruas e
edifícios sem marcar nenhuma caixinha**. Tire um print e anexe ao log da sessão — este achado
só está fechado com verificação visual.

### 5.7 Não faça

- ❌ Não ligue as camadas do **mundo** (`pois`, `estradas`, `fronteiras`) por padrão junto. Elas
  ainda não têm conteúdo gerado; ligar só adiciona requests vazios.

---

## 6. D4 — Todas as 15 cidades estão na linha d'água

🔴 **Crítico. O usuário viu uma; na verdade são todas.**

### 6.1 Sintoma

O usuário: *"tem uma cidade inclusive na água, tá perto da margem mas está na água, acredito
que pode ser uma cidade portuária mas mesmo assim não é legal"*.

A intuição dele estava certa mas o escopo é maior: **não é uma cidade portuária mal colocada,
são as 15 cidades, incluindo as agrícolas, mineiras e místicas.**

### 6.2 Medição

Para cada cidade, medimos (a) a altitude do pixel dela, (b) em que percentil de altitude da
terra ela está, (c) quantos dos vizinhos dela são água.

```bash
venv/bin/python - <<'EOF'
import json, numpy as np
m = json.load(open('database/world_manifest.json'))
d = np.load('database/mapa_composto.npz')['mapa'][:,:,0]
nm = np.float32(0.35)   # nivel_mar
terra = d[d > nm]
print(f"{'cidade':22}{'alt':>10}{'percentil':>11}{'agua 3x3':>10}{'agua 5x5':>10}")
for c in m['continentes']:
    for ct in c['cidades']:
        x, y = ct['x_global'], ct['y_global']
        a = float(d[y, x]); p = float((terra < a).mean()*100)
        v3 = d[y-1:y+2, x-1:x+2]; v5 = d[y-2:y+3, x-2:x+3]
        print(f"{ct['nome']:22}{a:10.5f}{p:10.2f}%{int((v3<=nm).sum()):8}/9{int((v5<=nm).sum()):9}/25")
EOF
```

Saída real medida (recorte — as 15 têm o mesmo padrão):
```
cidade                       alt  percentil  agua 3x3  agua 5x5
Cidade dos Ventos        0.35000      0.00%       4/9     13/25
Elorfield                0.35003      0.05%       4/9     12/25
Tordordor                0.35005      0.07%       4/9     11/25
Vila das Flores          0.35001      0.01%       4/9     11/25
Pelamont                 0.35003      0.04%       3/9     10/25
Torinmont                0.35004      0.06%       5/9     15/25
...
```

Interpretação:
- `nivel_mar` = 0,35. **Todas as cidades têm altitude entre 0,35000 e 0,35005.** Elas estão
  literalmente *um epsilon de float* acima do nível do mar.
- **Percentil 0,00% a 0,07%**: de todos os pixels de terra do mundo, nenhuma cidade está acima
  do percentil 0,07 de altitude. O percentil 1% da terra já é 0,3508.
- **3 a 5 dos 9 vizinhos são água.** Metade da vizinhança imediata de toda cidade é oceano.

Quando o renderizador desenha o degradê de costa e o brilho de recife nesse pixel, ele sai
azulado. Por isso a cidade "parece estar na água" — e, para efeitos práticos, está.

### 6.3 Causa raiz

`cartographer/cities/generate_cities_metadata.py`, função `_pontuar_sitio` (linha 24). Ela soma
três notas, e **duas delas têm o máximo exatamente no mesmo lugar: o primeiro pixel de terra**.

```python
dist_costa = distance_transform_edt(is_terra)          # distância até a água mais próxima
score_costa = np.exp(-dist_costa / escala_costa)       # ❌ máximo quando dist_costa = 1 (beira d'água)

score_altitude = 1.0 - np.clip((sub_alt - nivel_mar) / (nivel_montanha - nivel_mar), 0.0, 1.0)
#                                                                                   ↑
#                              ❌ máximo (= 1.0) quando sub_alt = nivel_mar exatamente

score = peso_costa*score_costa + peso_altitude*score_altitude + peso_bioma*score_bioma
```

Com `cidades_peso_costa: 0.4` e `cidades_peso_altitude: 0.3`, **70% da pontuação é maximizada
no mesmo ponto**: o pixel mais baixo e mais próximo da água que existir. O `score_bioma` (0.3)
nunca tem força para mover a escolha para dentro do continente.

O erro conceitual: *"perto da costa"* foi modelado como *"o mais perto possível da costa"*, e
*"terreno baixo e plano é construível"* foi modelado como *"quanto mais baixo melhor, sem piso"*.
Nenhum dos dois tem um ponto ótimo interno — os dois são monótonos rumo à água.

### 6.4 Impacto no app

- Visualmente, as cidades parecem boiar. Quebra a credibilidade do mapa inteiro.
- Toda cidade é costeira, independente do `tipo` que a IA planejou. Uma cidade `mineira`
  (Iranvale) ou `agricola` (Vila das Flores) na beira d'água não faz sentido narrativo, e a
  Fase 5 (narrativa por IA) vai gerar texto incoerente em cima disso.
- Como a cidade é sub-pixel (Seção 2.4), **metade do "território" dela está sobre pixels de
  água**. Não dá nem para verificar se um edifício caiu no mar, porque na escala da cidade não
  existe informação de terreno. Este é o mesmo problema do D2 visto de outro ângulo.

### 6.5 Solução

**Passo 1 — `score_costa` deve ter um ótimo interno, não monótono.**
Troque a exponencial decrescente por uma curva com pico a uma distância-alvo da costa:

```python
# D4: antes era exp(-dist/escala), cujo máximo é a beira d'água literal.
# Agora o pico fica em `cidades_distancia_costa_ideal_px` e cai para os dois lados:
# perto demais = alagado/na água; longe demais = sem acesso marítimo.
ideal = cfg_get(cfg, "cidades_distancia_costa_ideal_px")
largura = cfg_get(cfg, "cidades_distancia_costa_largura_px")
score_costa = np.exp(-((dist_costa - ideal) ** 2) / (2 * largura ** 2))
```

**Passo 2 — `score_altitude` precisa de um piso.**
Terreno *baixo* é bom; terreno *no nível do mar* é pântano. Some uma margem mínima:

```python
# D4: altitude ideal fica ligeiramente acima do nível do mar, não NO nível do mar.
margem = cfg_get(cfg, "cidades_altitude_margem_mar")     # ex.: 0.01
alt_ideal = nivel_mar + margem
score_altitude = 1.0 - np.clip(np.abs(sub_alt - alt_ideal) / (nivel_montanha - alt_ideal), 0.0, 1.0)
```

**Passo 3 — Restrição dura: descarte pixels colados na água.**
Igual ao que `cidades_distancia_minima_px` já faz entre cidades (rejeita, não penaliza):

```python
# D4: restrição DURA. Um pixel cuja vizinhança já é metade água nunca é sítio de cidade,
# por melhor que a pontuação dele seja.
dist_min = cfg_get(cfg, "cidades_distancia_costa_minima_px")
score = np.where(dist_costa >= dist_min, score, -np.inf)
```

**Passo 4 — Diferencie por tipo de cidade.** `portuaria` e `pesqueira` devem ter
`cidades_distancia_costa_ideal_px` menor; `mineira` deve preferir altitude alta, não baixa.
Adicione ao `config.json` um bloco `cidades_perfil_por_tipo`, e passe `ct['tipo']` para
`_pontuar_sitio`. Hoje o `tipo` que a IA gera é ignorado no posicionamento.

**Novas chaves de config** (com `_comentario_` explicando, regra 4):
```json
"cidades_distancia_costa_ideal_px": 2.0,
"cidades_distancia_costa_largura_px": 1.5,
"cidades_distancia_costa_minima_px": 2.0,
"cidades_altitude_margem_mar": 0.01,
```
⚠️ Estes valores são **ponto de partida, não a resposta**. Calibre-os medindo (Passo 5).

**Passo 5 — Calibre medindo, não chutando.** Rode o script de medição da Seção 6.2 depois de
cada ajuste. A meta: **nenhuma cidade abaixo do percentil 10 de altitude, e no máximo 1 de 9
vizinhos em água** (0 de 9 para cidades não-portuárias).

### 6.6 Critério de aceite

```bash
venv/bin/python cartographer/cities/generate_cities_metadata.py   # para cada continente
venv/bin/python - <<'EOF'
import json, numpy as np, sys
m = json.load(open('database/world_manifest.json'))
d = np.load('database/mapa_composto.npz')['mapa'][:,:,0]
nm = np.float32(0.35); terra = d[d > nm]; falhas = 0
for c in m['continentes']:
    for ct in c['cidades']:
        x, y = ct['x_global'], ct['y_global']
        p = float((terra < float(d[y, x])).mean()*100)
        agua = int((d[y-1:y+2, x-1:x+2] <= nm).sum())
        lim = 2 if ct.get('tipo') in ('portuaria', 'pesqueira') else 0
        if p < 10 or agua > lim:
            print(f'FALHOU {ct["nome"]:20} percentil={p:.2f}% agua_3x3={agua}/9 tipo={ct.get("tipo")}')
            falhas += 1
print('falhas:', falhas)
sys.exit(1 if falhas else 0)
EOF
```

### 6.7 Não faça

- ❌ **Não** resolva só empurrando a cidade N pixels para dentro depois de escolher o sítio.
  Isso ignora a forma da costa e pode empurrar para dentro de outra baía ou de uma montanha.
  Corrija a **função de pontuação**, que é onde está o erro conceitual.
- ❌ **Não** zere `cidades_peso_costa`. Proximidade de água é um critério legítimo de sítio real
  (rio, porto). O problema é o formato da curva, não o critério.
- ❌ **Não** mexa em `nivel_mar`. Ele é usado pela calibração de continentes da Fase 1 e por
  todo o pipeline de bioma.

---

## 7. D5 — Zoom sem `maxNativeZoom`: 17 níveis de tile real

🟠 **Alto. Causa direta da lentidão e do "zoom infinito".**

### 7.1 Sintoma

O usuário: *"zoom meio que infinito (vai bem mais que antes, e chega a borrar a imagem)"* e
*"navegação um pouco lenta no zoom out"*.

### 7.2 Causa raiz

`web/static/js/mapa_leaflet.js:102`:
```javascript
leafletTileLayer = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
    tileSize: 256,
    minZoom: 0,
    maxZoom: leafletZoomMaximo,     // 16
    // ❌ falta maxNativeZoom
});
```

Sem `maxNativeZoom`, o Leaflet **pede um tile de verdade ao servidor em todos os 17 níveis**
(z0 a z16). Cada um desses pedidos dispara uma renderização procedural completa
(`TileCartographer.gerar_janela`), mesmo nos zooms onde — pela medição do D2 — o resultado é
indistinguível de ampliar o tile do nível anterior.

`maxNativeZoom` existe exatamente para isso: ele diz ao Leaflet *"acima deste nível, não peça
tile novo, só estique o último"*. É uma linha de configuração.

O comentário do `config.json:346` já admitia a pendência: *"maxNativeZoom continua igual a
tile_zoom_maximo_ui (não calibrado separadamente ainda)"*. Agora está calibrado: é **z6** (D2).

### 7.3 Impacto no app

Combinado com D6 (custo por tile), este é o gargalo. Ao navegar do zoom máximo até o mundo
inteiro, o Leaflet atravessa todos os níveis intermediários e dispara centenas de renderizações
que não produzem nenhuma informação nova.

### 7.4 Solução

**Passo 1** — Adicione `maxNativeZoom` na linha 102:
```javascript
leafletTileLayer = L.tileLayer('/tiles/{z}/{x}/{y}.png', {
    tileSize: 256,
    minZoom: 0,
    maxZoom: leafletZoomMaximo,
    // D5/D2 do DIAGNOSTICO_V3: o raster para de ganhar detalhe no z6 (medido: o gradiente
    // da imagem cai pela metade a cada nível a partir dali). Acima disso o Leaflet estica
    // o tile do z6 em vez de pedir um tile novo ao servidor — mesma imagem, custo zero.
    maxNativeZoom: leafletMaxNativeZoom,
});
```

**Passo 2** — Nova chave no `config.json`, exposta em `/api/continentes` junto de
`tile_zoom_maximo_ui`:
```json
"_comentario_maxnativezoom": "D5/D2 do DIAGNOSTICO_V3 (2026-09-11): acima deste zoom o raster não tem detalhe NOVO (medido via gradiente da imagem — satura no z6), então o Leaflet estica em vez de pedir tile ao servidor. tile_zoom_maximo_ui continua maior porque as camadas VETORIAIS de cidade precisam de zoom alto — elas são vetor, não perdem qualidade ao ampliar.",
"tile_max_native_zoom": 6,
```

**Passo 3** — Baixe `tile_zoom_maximo_ui` de 16 para **15** (Seção 3.5, passo 4). Depois da
correção do D1, z15 já põe uma cidade grande ocupando ~2 telas. Ir além disso não mostra nada
novo, nem vetor nem raster.

### 7.5 Critério de aceite

Com o dashboard rodando, navegue até o zoom máximo e observe o log do Flask. Não pode aparecer
nenhum `GET /tiles/7/...` ou acima. Antes da correção, apareciam pedidos até `/tiles/16/`.

Verificação estática do cache atual (mostra que hoje existem tiles até z16):
```bash
for z in $(ls database/tiles_cache/*/); do :; done
find database/tiles_cache -mindepth 2 -maxdepth 2 -type d | sed 's|.*/||' | sort -n | tail -5
```

---

## 8. D6 — Cada tile custa 0,19 a 0,55 s de CPU

🟠 **Alto. É o outro metade da lentidão.**

### 8.1 Medição

```bash
venv/bin/python - <<'EOF'
import json, sys, time; sys.path.insert(0,'.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from config import cfg_get
from cartographer.tiles.render import oitavas_extra_por_zoom
from cartographer.world.tile_cartographer import TileCartographer
m = json.load(open('database/world_manifest.json'))
ts = cfg_get(C,'tile_size_px')
tc = TileCartographer(size=ts, seed=m['seed'], config=C,
                      layout_continentes=m['layout_continentes'],
                      tamanho_global=m['dimensao_global'])
for z in [0,2,4,6,8,10,12,14,16]:
    oe = oitavas_extra_por_zoom(z); lado = ts/(2**z)
    t = time.perf_counter()
    tc.gerar_janela(384.0, 384.0, 384.0+lado, 384.0+lado, ts, ts, oitavas_extra=oe)
    print(f'z={z:>2} oitavas={oe} {(time.perf_counter()-t)*1000:6.1f} ms/tile')
EOF
```

Saída real medida:
```
z= 0 oitavas=0  184.9 ms/tile
z= 2 oitavas=2  250.2 ms/tile
z= 4 oitavas=4  329.1 ms/tile
z= 6 oitavas=6  393.2 ms/tile
z= 8 oitavas=8  488.8 ms/tile
z=10 oitavas=9  551.8 ms/tile
z=12 oitavas=9  536.3 ms/tile
z=14 oitavas=9  527.0 ms/tile
z=16 oitavas=9  514.1 ms/tile
```

Uma tela de 1920×1080 precisa de **54 tiles** (9×6, contando a borda). Em série isso é
**10 a 30 segundos** para preencher uma tela nova.

### 8.2 Causa raiz

Três fatores somados:

1. **Sem `maxNativeZoom`** (D5), zooms que não precisavam renderizar renderizam.
2. **O servidor é o Flask de desenvolvimento** (`app.run(debug=True)` em `run_dashboard.py:5`).
   Ele processa poucos requests em paralelo e reinicia sozinho a cada mudança de arquivo,
   descartando o `TileCartographer` de processo único e o cache em memória.
3. **`gerar_janela` é O(oitavas × continentes × pixels)** e não tem caminho rápido. Note pela
   medição que o z0 (zero oitavas extras) já custa 185 ms — o custo base, antes de qualquer
   oitava, já é alto.

### 8.3 Impacto no app

Primeira visita a qualquer região = espera de dezenas de segundos com tiles cinzas. O cache em
disco resolve a **segunda** visita, mas a primeira impressão é de app quebrado. É por isso que
o usuário percebeu como "lento no zoom out": zoom out revela área nunca visitada.

### 8.4 Solução — em ordem de custo/benefício

**1. Aplicar D5.** Corta a maior parte do trabalho inútil. Faça isto antes de qualquer otimização.

**2. Pré-aquecer o cache até o `maxNativeZoom`.** Já existe `cartographer/tiles/prewarm_cache.py`.
Com `maxNativeZoom=6`, o mundo inteiro até z6 são `3·2⁶ = 192` tiles de lado = 36.864 tiles,
o que é demais. Pré-aqueça **z0 a z4** (9+36+144+576+2304 = 3.069 tiles ≈ 15 min de CPU, ~250 MB)
e deixe z5–z6 sob demanda. Chame isso no final do `reset_cartography.sh`.

**3. Medir antes de otimizar `gerar_janela`.** Rode um profile para saber onde vão os 185 ms de
base:
```bash
venv/bin/python -m cProfile -s cumtime -c "
import json,sys; sys.path.insert(0,'.')
from cartographer.config import CARTOGRAPHER_CONFIG as C
from config import cfg_get
from cartographer.world.tile_cartographer import TileCartographer
m=json.load(open('database/world_manifest.json'))
tc=TileCartographer(size=256,seed=m['seed'],config=C,layout_continentes=m['layout_continentes'],tamanho_global=m['dimensao_global'])
for _ in range(5): tc.gerar_janela(384.,384.,640.,640.,256,256,oitavas_extra=0)
" 2>&1 | head -30
```
Só otimize o que o profile apontar. **Não** saia reescrevendo o gerador de ruído por intuição.

**4. Servidor de produção.** Trocar `app.run(debug=True)` por `waitress` ou `gunicorn` com
múltiplos workers dá paralelismo real. É uma mudança de infra, fora do escopo de cartografia —
proponha ao usuário, não faça por conta própria.

---

## 9. D7 — A "vista de cidade" mostra 380 km de lado

🟠 **Alto. É a causa mais direta de "ainda é 1px na cidade".**

### 9.1 Sintoma

O usuário: *"ainda é 1px na cidade, não existe uma relação do que está na cidade × a posição no
continente pra poder renderizar isso"*.

### 9.2 Medição

```bash
curl -s "http://127.0.0.1:5000/api/cidade/Pelamont/entities" | venv/bin/python -c "
import json,sys
d=json.load(sys.stdin); b=d['bbox']; L=d['locais']
xs=[l['coordenadas'][0] for l in L]; ys=[l['coordenadas'][1] for l in L]
larg=b['max_x']-b['min_x']; esc=b['largura_img']/larg
print('janela:', larg, 'px de mundo =', round(larg*15.81), 'km de lado')
print('n locais:', len(L))
print('espalhamento na imagem:', round((max(xs)-min(xs))*esc,3), 'x', round((max(ys)-min(ys))*esc,3), 'px')
"
```

Saída real medida:
```
janela: 24 px de mundo = 379 km de lado
n locais: 85
espalhamento na imagem: 0.305 x 0.323 px
```

**Os 85 locais de Pelamont ocupam 0,3 × 0,3 pixel numa imagem de 1200×1200.** Todos os 85 caem
no mesmo pixel. É literalmente o "1px" que o usuário descreveu.

### 9.3 Causa raiz

Duas causas independentes, que se somam:

1. **`cidade_janela_raio_px: 12`** no `config.json:343`. A rota `/api/cidade/<nome>/imagem`
   (`web/composed_routes.py:311`) renderiza um quadrado de raio 12 px de mundo ao redor da
   cidade. 12 px × 15,81 km = **190 km de raio**. É uma vista **regional**, não urbana. Um
   valor razoável para "ver a cidade inteira e um pouco de arredor" seria
   `raio ≈ diâmetro_da_cidade` = **0,11 px** (cidade grande), ou seja **100× menor**.

2. **D1**: como a geometria está 15,8× comprimida, mesmo corrigindo o raio o espalhamento
   continuaria errado por esse fator.

### 9.4 Impacto no app

- A tela que o usuário abre esperando "a cidade" mostra 380 km de terreno liso com um ponto.
- É a regressão que ele sentiu em relação à branch antiga: `city_roi_zoom.py` (deletado na
  Fase 0.5) também mostrava uma janela grande, mas pelo menos interpolava e injetava ruído
  para dar textura, o que dava a impressão de um terreno local.

### 9.5 Solução

**Passo 1** — Corrija D1 primeiro. Sem ele, nada aqui funciona.

**Passo 2** — `cidade_janela_raio_px` não pode ser um número fixo em px de mundo. Derive do
tamanho real da cidade:

```python
# D7: a janela da vista de cidade é proporcional à cidade, não um raio fixo em px de
# mundo (12 px = 190 km = uma vista REGIONAL, não urbana — ver DIAGNOSTICO_V3 D7).
raio_m = cfg_get(cfg, "cidade_geo_raio_m_por_tamanho")[cidade["tamanho"]]
folga = cfg_get(cfg, "cidade_janela_folga")          # ex.: 1.6 = 60% de margem em volta
metros_por_px = math.sqrt(cfg_get(cfg, "escala_pixel_area_km2")) * 1000.0
raio_px = (raio_m * folga) / metros_por_px
```

Renomeie `cidade_janela_raio_px` para `cidade_janela_folga` (adimensional) e marque a chave
antiga como removida no comentário, para o próximo modelo não procurar por ela.

**Passo 3 — Decida com o usuário o que essa vista deve ser.** Existem duas leituras:

- **(a) Vista regional** — "onde a cidade fica no continente". Aí o raio de 12 px está *certo*
  e o problema é só o nome. Renomeie a rota para `/api/regiao/<nome>/imagem` e desenhe a cidade
  como **um marcador**, não como 85 pontos sobrepostos.
- **(b) Vista urbana** — "o que tem dentro da cidade". Aí o raster do mundo é inútil (D2: não há
  terreno nessa escala) e a vista deve ser construída a partir do GeoJSON de cidade, com CRS
  próprio em metros. É o Caminho C do D2.

**Provavelmente o app precisa das duas**, e elas são telas diferentes. **Pergunte ao usuário
antes de implementar** — esta é uma decisão de produto, não técnica.

**Passo 4** — Conserte o desenho no `mapa_composto.js`. A função `drawCityGridAndEntities` hoje
converte mundo→imagem corretamente (foi corrigida na Fase 2), mas com 85 pontos no mesmo pixel
ela desenha 85 marcadores empilhados. Se a decisão for (a), agregue num marcador só com a
contagem; se for (b), ela deixa de ser usada.

---

## 10. D8 — Cache de tiles ilimitado e sem limpeza

🟡 **Baixo. Anote e resolva quando sobrar tempo.**

### 10.1 Problema

`cartographer/tiles/render.py` grava cada tile em
`database/tiles_cache/<config_hash>/<z>/<x>/<y>.png`. A chave por `config_hash` faz a
invalidação funcionar (mudou a config, muda o hash, tiles velhos não são servidos) — **mas
os diretórios antigos nunca são apagados.**

Estado atual medido:
```bash
du -sh database/tiles_cache/          # 15M
ls database/tiles_cache/ | wc -l      # 1
```

Hoje há 1 hash e 15 MB, então não é urgente. Mas cada alteração no `config.json` cria um
diretório novo. Numa sessão de calibração com 20 ajustes, são 20 árvores órfãs.

Também não há limite superior: em zoom alto o número de tiles possíveis é astronômico
(`3·2¹⁶ = 196.608` tiles de lado, ou seja 3,9×10¹⁰ tiles no z16). Nada impede o cache de
crescer indefinidamente conforme o usuário navega.

### 10.2 Solução

1. No início de `renderizar_tile_png`, ao detectar um `config_hash` novo, apague os diretórios
   de hash diferentes do atual (guarde o anterior, para não invalidar o cache num reload
   acidental do Flask em modo debug).
2. Adicione `cache_tiles_tamanho_max_mb` no `config.json` e uma limpeza LRU por mtime quando
   o limite for ultrapassado.
3. Aplicar D5 já limita o crescimento drasticamente: com `maxNativeZoom=6`, o máximo teórico
   do cache passa de 3,9×10¹⁰ para 49.149 tiles.

---

## 11. Ordem de execução recomendada

Faça nesta ordem. Cada etapa tem um critério de aceite executável — **rode e cole o output real
no log da Seção 12 antes de passar para a próxima.**

| # | Etapa | Achados | Esforço | Destrava |
|---|---|---|---|---|
| **1** | Corrigir a escala metro→pixel e recalibrar os `zoom_min` | **D1** | Baixo | Tudo |
| **2** | Ligar as camadas de cidade e registrar `lote` | **D3** | Trivial | A validação visual |
| **3** | Adicionar `maxNativeZoom` e baixar `tile_zoom_maximo_ui` para 15 | **D5** | Trivial | Performance |
| **4** | Corrigir a pontuação de sítio (curva com pico + piso de altitude + restrição dura) | **D4** | Médio | Credibilidade do mapa |
| **5** | **Campo de detalhe local — Caminho B, especificado na [Seção 13](#13-especificação-de-implementação--caminho-b-campo-de-detalhe-local)** | **D2** | Médio | Relação cidade↔terreno |
| **6** | ⏸️ **Parar e validar com o usuário.** Daqui em diante são decisões de produto, não consertos. | — | — | — |
| **7** | Decidir vista regional × vista urbana e refazer `/api/cidade/<nome>/imagem` | **D7** | Médio | A queixa do "1px" |
| **8** | Pré-aquecer cache até z4 no reset; profile de `gerar_janela` | **D6** | Médio | Primeira impressão |
| **9** | Limpeza do cache de tiles | **D8** | Baixo | Higiene |

⚠️ **Sobre a etapa 3 e a etapa 5.** O valor de `maxNativeZoom` depende de qual das duas você
fez primeiro: **6** sem o campo de detalhe, **11** com ele. Se você for fazer a etapa 5 na
mesma leva, pule direto para 11 e evite recalibrar duas vezes. A fórmula está na Seção 13.7.

⚠️ **A etapa 6 é obrigatória.** O D7 envolve uma decisão sobre o que o app *deve ser* (uma vista
ou duas?). Levar essa decisão ao usuário custa uma pergunta; adivinhar errado custa uma fase
inteira refeita.

### 11.1 Depois de mexer em qualquer coisa de cartografia

Regenere e revalide. **Sempre com a simulação parada:**
```bash
ps aux | grep -E "run_simulation|reset_" | grep -v grep     # tem que sair vazio
bash cartographer/reset_cartography.sh                       # regenera mundo + cidades + geometria
venv/bin/python -m pytest tests/ -v                          # 7/7 tem que passar
```

---

## 12. Log de execução

Preencha conforme for corrigindo. Um bloco por achado. Cole o **output real** dos comandos de
aceite, não um resumo deles.

### D1 — escala metro→pixel
- [x] Corrigido (`generate_city_geometry.py:_mundo`, docstring, `config.json` comentários,
  `ZOOM_MIN_POR_CAMADA` virou `cidade_geo_zoom_min_por_camada_tamanho` config-driven por
  (camada, tamanho))
- Output do aceite (`venv/bin/python cartographer/cities/generate_city_geometry.py` +
  medição da muralha de Pelamont):
  ```
  largura da muralha: 0.115835 px de mundo
  OK
  ```
  (esperado ~0,1138 ±5%; 0,115835 está dentro da faixa)

### D2 — detalhe local (Caminho B, decidido pelo usuário em 2026-09-11)
- [x] `generate_detail_field` em `noise.py` (Seção 13.5, passo 1)
- [x] Injeção em `gerar_janela` + chaves de config (passos 2 e 3)
- [x] Testes T7, T8, T9 (passo 4) — T9 usa (300,400), centro do continente de teste da
  fixture `_cartografo_de_teste()`, não (400,578) do mundo real (a fixture de teste é um
  layout sintético diferente do mundo em `database/`; o ponto do doc não é terra nela)
- [x] `tile_max_native_zoom` recalculado pela fórmula da Seção 13.7 (= 11, aplicado em
  `config.json` e servido por `/api/continentes`)
- [x] Amplitude calibrada (0,006, valor recomendado do diagnóstico), tabela da Seção 13.6
  reproduzida no mundo real (ponto interior (425,564), altitude 0,483 — diferente do
  ponto do protótipo porque é outra amostra do mesmo mundo)
- [x] Cidade lendo o terreno (passo 5) — amostra 64x64 via `obter_cartografo()`,
  `_altitude_local`/`_declividade_local`, praça no ponto mais plano do anel central,
  portões preferindo setores de menor declividade, lote rejeitado se declividade >
  `cidade_geo_declividade_max`, `properties.altitude` em todo edifício
- Output do `pytest` (10 testes):
  ```
  tests/test_cartografia.py::test_ruido_independe_do_shape PASSED
  tests/test_cartografia.py::test_ruido_invariante_a_subdivisao PASSED
  tests/test_cartografia.py::test_oitavas_convergem PASSED
  tests/test_cartografia.py::test_gerar_janela_z0_igual_ao_arange PASSED
  tests/test_cartografia.py::test_gerar_janela_invariante_a_subdivisao PASSED
  tests/test_cartografia.py::test_culling_nao_altera_resultado PASSED
  tests/test_cartografia.py::test_coerencia_entre_zooms PASSED
  tests/test_cartografia.py::test_detalhe_nao_vaza_para_zoom_baixo PASSED
  tests/test_cartografia.py::test_detalhe_preserva_a_costa PASSED
  tests/test_cartografia.py::test_detalhe_produz_relevo_na_escala_da_cidade PASSED
  10 passed in 1.68s
  ```
  Reprodução da tabela 13.6 no mundo real, ponto (425,564), `render_npz_array` (textura =
  desvio-padrão do brilho renderizado):
  ```
    z   textura(std brilho)
    0                 6.08
    2                14.05
    4                28.60
    6                31.94
    8                32.73
   10                33.10
   12                33.47
   14                32.51
  ```
  z0/z2 baixos (o filtro de banda ainda apaga o detalhe ali) e estável de z4 a z14 — mesmo
  padrão do protótipo, confirmado na implementação real.
  Invariante da costa checado direto no mundo real (não só na fixture de teste), janela
  (400,550)-(456,606), 128px vs 1024px/8: **0 flips**.
- Print da validação visual no zoom 11: **não realizado nesta sessão** — a extensão
  Claude in Chrome não estava conectada neste ambiente. Verificação estrutural feita via
  API/tile PNG (ver texto da sessão); falta o print visual pedido pelo critério de aceite.

### D3 — camadas de cidade no front
- [x] Corrigido (`lote` adicionado a `CAMADAS_DETALHE_CIDADE` e a `ESTILO_CAMADA_CIDADE`,
  `grupoDetalheCidade.addTo(leafletMap)`, afordância de zoom no popup + duplo-clique
  `flyTo` no marcador de cidade — Passo 3 também feito)
- Print da validação visual: **não realizado** — mesma limitação do D2 (sem browser
  conectado). Back-end confirmado via API: `edificio 85 / lote 85 / muralha 1 / rua 13`
  para Pelamont, e `node --check` passou na sintaxe do JS.

### D4 — cidades na linha d'água
- [x] Corrigido (`_pontuar_sitio` reescrita com pico interno de `score_costa`, piso de
  `score_altitude`, restrição dura por `cidades_distancia_costa_minima_px`, perfil por
  tipo em `cidades_perfil_por_tipo`)
- Output do aceite: **medição dry-run feita, aplicação real NÃO feita nesta sessão** —
  `generate_cities_metadata.py` substitui as cidades do continente (chama a IA/fallback
  procedural para FUNDAR cidades novas), e `database/openworld.db` já tem `npcs`/`locais`/
  `eventos` referenciando as 15 cidades atuais por nome. Rodar o aceite de verdade
  quebraria esse vínculo — ver texto da sessão, isto foi devolvido ao usuário como decisão.
  Medição dry-run (mesma função `_pontuar_sitio`, sobre o continente Grendalia real, sem
  escrever nada):
  ```
  agricola   melhor sitio: alt=0.3600 percentil=10.75% agua_3x3=0/9
  portuaria  melhor sitio: alt=0.3600 percentil=10.79% agua_3x3=0/9
  mineira    melhor sitio: alt=0.4134 percentil=57.58% agua_3x3=0/9
  ```
  Percentil pulou de 0,00-0,07% (achado original) para ~10-58%, água nos vizinhos 3x3
  zerou. `portuaria` não ficou visivelmente mais perto da costa que `agricola` neste
  continente específico — `cidades_distancia_costa_ideal_px` por tipo pode precisar de
  mais separação; sinalizado, não é bug de lógica (a restrição dura e o piso de altitude
  funcionam).

### D5 — maxNativeZoom
- [x] Corrigido (`maxNativeZoom` no `L.tileLayer`, `tile_max_native_zoom` no config e na
  API, `tile_zoom_maximo_ui` 16→15). Calibrado direto para o valor final com D2 aplicado
  (11), conforme a nota da Seção 11 (evita recalibrar duas vezes).
- Output do aceite:
  ```
  tile_zoom_maximo_ui: 15
  tile_max_native_zoom: 11
  ```
  (via `curl http://127.0.0.1:5000/api/continentes`). Tiles em z11/z12 renderizam sem erro
  (`renderizar_tile_png`); checagem de log do Flask por navegação real não feita — mesma
  limitação de browser do D2/D3.

### D6 — custo por tile
- [ ] Não iniciado nesta sessão (Etapa 8 da ordem de execução — depois do checkpoint da
  Etapa 6/D7). D5 (que é o passo 1 da solução do D6) está feito.

### D7 — vista de cidade
- [x] Decisão do usuário (2026-09-11): **as duas, telas separadas**
- [x] Corrigido — mas com uma reinterpretação da "vista urbana" que precisa de validação
  do usuário (ver abaixo)
- O que foi feito:
  - Vista REGIONAL: `/api/cidade/<nome>/imagem`→`/api/regiao/<nome>/imagem`,
    `/api/cidade/<nome>/entities`→`/api/regiao/<nome>/entities`; `cidade_janela_raio_px`
    renomeada pra `regiao_janela_raio_px` (mesmo valor, 12 px — Seção 9.5 Passo 3(a) diz
    que esse raio já está certo pra leitura regional, só o nome estava errado);
    `mapa_composto.js` atualizado pros novos endpoints; `drawCityGridAndEntities` não
    desenha mais 85 retângulos empilhados — agora é UM marcador agregado no centroide dos
    locais, com tooltip "N locais · M NPCs".
  - Vista URBANA: **não foi construído um mapa novo com CRS em metros (Caminho C)**. Em
    vez disso, decidi que a aba Mapa Live (🗾, `mapa-leaflet-view`) já cumpre esse papel
    depois do D3 — ela mostra a camada vetorial de detalhe de cidade (rua/edifício/lote/
    muralha) em coordenada de mundo exata, que não é sub-pixel e não perde qualidade ao
    ampliar até z15. Como `map-view` (vista regional) e `mapa-leaflet-view` (vista urbana)
    já são abas/telas diferentes na navegação, isso atende "as duas, telas separadas" sem
    duplicar a renderização vetorial que o D3 acabou de consertar.
    ⚠️ **Isto é uma reinterpretação minha do Caminho C, não o que a Seção 9.5 descreve
    literalmente** (um mapa Leaflet novo, com CRS próprio em metros, servido a partir do
    GeoJSON da cidade reprojetado). Fiz essa escolha pelo custo/risco de construir um
    terceiro subsistema de mapa redundante com o que o D3 já resolve, mas é uma decisão de
    produto — se você queria mesmo um mapa dedicado e independente do mundo, me avise que
    eu implemento o Caminho C literal.
- Output do aceite:
  ```
  GET /api/regiao/Pelamont/imagem -> 200
  GET /api/regiao/Pelamont/entities -> locais: 85 npcs: 0 bbox: {min_x:495 min_y:385 max_x:519 max_y:409 largura_img:1200 altura_img:1200}
  node --check web/static/js/mapa_composto.js -> sintaxe OK
  ```
  Validação visual (print) não feita — mesma limitação de browser das outras seções.

### D8 — cache de tiles
- [ ] Não iniciado nesta sessão (Baixa prioridade, Etapa 9)

### D9 — a cidade construída não aparecia em zoom nenhum (achado NOVO, 2026-09-11)

Não estava neste documento. Apareceu na validação visual do autor depois do D1/D3/D5: o zoom
ia mais fundo, a muralha e as ruas apareciam, mas os prédios não, em nenhum nível.

- [x] Diagnosticado e corrigido

**Causa raiz.** `carregarFeaturesVisiveisLeaflet` montava a bbox da consulta de feições com
`latLngParaPixel`, que **arredonda para inteiro**. Essa função existe para a consulta de
clique (`/api/mapa_composto/info/<x>/<y>` indexa um array por pixel, precisa de inteiro), e
foi reusada onde não podia. A cidade mede 0,076 px de mundo (1 px = 15,81 km), então a partir
do zoom ~10 a viewport inteira cabe dentro de um pixel de mundo, os dois cantos arredondam
para o mesmo inteiro e a bbox vira um **ponto de área zero**. `_bbox_intersecta` então só
deixa passar a feição cuja própria caixa engloba aquele ponto exato: muralha, praça e ruas,
que atravessam o centro. Edifício, torre e portão são `Point` em coordenada quebrada e nunca
cruzam. O servidor estava certo o tempo todo.

O agravante é que os dois filtros **não tinham interseção**: edifício exigia `z >= 14` e uma
bbox utilizável exigia `z <= 9`. Não existia zoom que mostrasse a cidade construída.

Medição do estado quebrado, simulando a bbox que o JS mandava (viewport 1190x520, Aurora
Vales em (393,659)):

```
  z bbox arredondada    largura   resultado
  8 (391,658,395,660)     4 x 2   NADA (zoom_min ainda barra)
  9 (392,658,394,660)     2 x 2   NADA (zoom_min ainda barra)
 10 (392,659,394,659)     2 x 0   NADA
 11 (393,659,393,659)     0 x 0   {'muralha': 1, 'praca': 1}
 12 (393,659,393,659)     0 x 0   {'muralha': 1, 'praca': 1}
 13 (393,659,393,659)     0 x 0   {'muralha': 1, 'praca': 1, 'rua': 10}
 14 (393,659,393,659)     0 x 0   {'muralha': 1, 'praca': 1, 'rua': 10}
 15 (393,659,393,659)     0 x 0   {'muralha': 1, 'praca': 1, 'rua': 10}
```

Bate exatamente com o print do autor: hexágono, praça e ruas, nada mais.

**Correção.**
1. `latLngParaPixelExato` (px de mundo fracionário) monta a bbox; `latLngParaPixel` (inteiro)
   fica só para a consulta de clique, com comentário dizendo para não usá-la em bbox.
2. `z` virou `Math.floor(getZoom())`, não `Math.round` — com `zoomSnap` 0,25, arredondar
   acendia a camada meio nível antes do `zoom_min` dela.
3. A tabela `cidade_geo_zoom_min_por_camada_tamanho` era escrita à mão, e já tinha divergido
   da fórmula que a gerou. Virou `cartographer/cities/escala.py`, que **deriva**
   `{tamanho: {camada: zoom_min}}` de `ceil(log2(alvo_px_de_tela / diametro_px_de_mundo))`.
   Só os alvos ficam no config (`cidade_geo_zoom_min_alvo_px_por_camada`). Recalibrados de
   120/350/700/1400 para 48/200/400/800: os antigos só acendiam o edifício quando a cidade já
   era **maior que a viewport**, ou seja, nunca dava para ver a cidade e os prédios juntos.
4. `/api/continentes` passou a devolver a mesma tabela, e o popup do marcador, o alvo do
   duplo-clique e o rótulo do seletor de camadas pararam de repetir números escritos à mão.

**Aceite** (mesma simulação, agora com a bbox corrigida):

```
  z  largura bbox (px mundo)  cidade na tela   feicoes devolvidas
  8                  4.6484            19px    nada
  9                  2.3242            39px    nada
 10                  1.1621            78px    {'muralha': 1, 'torre': 44, 'portao': 3, 'praca': 1}
 11                  0.5811           155px    {'muralha': 1, 'torre': 44, 'portao': 3, 'praca': 1}
 12                  0.2905           311px    {'muralha': 1, 'torre': 44, 'portao': 3, 'praca': 1, 'rua': 10, 'quarteirao': 18}
 13                  0.1453           622px    {'muralha': 1, 'torre': 26, 'portao': 1, 'praca': 1, 'rua': 10, 'quarteirao': 18, 'edificio': 32}
 14                  0.0726          1244px    {'muralha': 1, 'praca': 1, 'rua': 10, 'quarteirao': 16, 'edificio': 17, 'lote': 27}
 15                  0.0363          2487px    {'muralha': 1, 'praca': 1, 'rua': 10, 'quarteirao': 12, 'edificio': 4, 'lote': 10}
```

A cidade agora se monta em camadas conforme se aproxima, e no z13 a cidade média inteira
(622 px na tela) aparece com os 32 edifícios. Acima do z13 as contagens caem porque a
viewport já é menor que a cidade — isso é recorte correto, não filtro.

Tabela derivada, servida por `/api/continentes`:

```
camada       pequeno    medio   grande
muralha           11       10        9
torre             11       10        9
portao            11       10        9
praca             11       10        9
rua               13       12       11
quarteirao        13       12       11
edificio          14       13       12
lote              15       14       13
```

```
venv/bin/python -m pytest tests/ -q  ->  10 passed in 1.79s
node --check web/static/js/mapa_leaflet.js  ->  OK
GET /api/mapa_composto/info/393/659  ->  200 (rota de clique intacta)
```

Validação visual (print) não feita — mesma limitação de browser das outras seções.

**Pendência conhecida, não corrigida** (é dado do mundo, não código): o manifesto tem duas
cidades chamadas "Cidade dos Ventos", e as duas escrevem no mesmo
`database/cidades/cidade_dos_ventos.geojson` — a segunda sobrescreve a primeira. O gerador
deriva o nome do arquivo do nome da cidade, sem desempate. Uma das duas fica sem geometria
própria.

---

## 13. ESPECIFICAÇÃO DE IMPLEMENTAÇÃO — Caminho B: campo de detalhe local

> **Escopo desta seção**: resolve o D2. Depois dela, o terreno continua ganhando detalhe real
> do zoom 0 até o zoom 11, e a cidade passa a ser desenhada **sobre relevo**, não sobre uma
> mancha lisa.
>
> **Pré-requisito**: nenhum. Pode ser feito em paralelo com D1/D3/D4. Mas **só faz sentido
> entregar depois do D1**, porque antes disso a cidade está no lugar errado de qualquer jeito.
>
> **Tudo nesta seção foi prototipado e medido** em 2026-09-11, contra o mundo que está em
> `database/`. Os números são reais. O protótipo passou em T2 e T6 sem alteração.

---

### 13.1 O princípio, em uma frase

> **O detalhe fino sempre existe na função de terreno, em todo lugar do mundo, com amplitude
> fixa. O que muda com o zoom não é o terreno — é quantas oitavas a janela pedida consegue
> resolver sem serrilhar.**

Isso é diferente de "ligar detalhe quando o zoom é alto". Ligar por zoom **quebraria a
invariante F1** (pureza): o mesmo ponto do mundo teria altitudes diferentes em z5 e em z12.
O que fazemos é o contrário: o campo é sempre o mesmo, e cada oitava é **filtrada por
antialiasing** quando a janela não tem amostras suficientes para representá-la. É exatamente
o que um mipmap faz com uma textura.

### 13.2 Por que "aumentar `tile_oitavas_max`" não resolve

Esta é a tentação óbvia e ela **não funciona**. Entenda antes de implementar, senão você vai
tentar o atalho.

Num fBm com `persistencia = 0.5`, a oitava *n* tem amplitude `0,5ⁿ`. A 12ª oitava contribui
com `0,5¹² ≈ 0,00024` do campo. A faixa de altitude de terra do projeto vai de 0,35 a ~0,57.
A contribuição dessa oitava na altitude final é da ordem de `10⁻⁴`. Ela **existe**, é
matematicamente correta, e é invisível.

Foi isso que a medição do D2 mostrou: das oitavas 4 a 9, o gradiente da imagem já caía pela
metade a cada nível, mesmo com as oitavas **aumentando**.

O detalhe precisa de um campo **com amplitude própria**, desacoplada da cauda geométrica do
fBm global. É isso que esta seção implementa.

### 13.3 A descoberta que torna isso barato

Enquanto prototipava, encontrei duas coisas no código que já estão certas e que fazem o
trabalho pesado de graça. **Não mexa nelas.**

**Primeira: o hillshading já compensa o zoom.** Em `web/helpers.py`, linha ~76:
```python
escala_dinamica = escala_base / mundo_px_por_img_px
```
Conforme você aproxima, a diferença de altitude entre pixels vizinhos encolhe, e essa divisão
amplifica o gradiente na mesma proporção. Ou seja: **a inclinação aparente do relevo já é
constante em qualquer zoom.** Você não precisa escrever nenhum caminho de renderização novo.

**Segunda: num fBm com `persistencia × lacunaridade = 1`, toda oitava contribui a mesma
inclinação.** A inclinação da oitava *i* é `amplitude_i / comprimento_de_onda_i`, que dá
`(0,5 × 2)ⁱ / escala = 1 / escala`, constante. Com os valores do projeto (0,5 e 2,0) isso
vale exatamente.

Juntando as duas: **basta o campo ter as frequências certas e o pipeline de cor existente já
as torna visíveis.** É por isso que este trabalho é menor do que parece.

**Terceira: a linha d'água não passa pelo relevo.** Em `gerar_janela`, a decisão terra/água é
```python
data[:, :, 0] = np.where(mask_continente >= nivel_mar, relevo_continentes, ...)
```
A condição usa `mask_continente`, que é geometria de continente, **não** `relevo_continentes`.
Somar detalhe na altitude, portanto, não move a costa. É por isso que T6 passa por construção.

### 13.4 A parte difícil: aliasing

O protótipo ingênuo (campo de detalhe somado sem filtro) foi medido e **estraga o mapa-múndi**.
Medida de textura da imagem, desvio-padrão do brilho:

| configuração | z=2 | z=4 | z=6 |
|---|---|---|---|
| sem detalhe (hoje) | 17,41 | 16,25 | 12,35 |
| detalhe **sem** filtro, amp 0,02 | **27,11** | 31,24 | 31,00 |
| detalhe **com** filtro de banda, amp 0,02 | **17,41** | 30,01 | 27,63 |

Sem filtro, o z2 salta de 17,41 para 27,11: isso é ruído de amostragem, "sal e pimenta" no mapa
do mundo. Com o filtro, o z2 fica **idêntico** ao valor de hoje, bit a bit, e o ganho aparece
só onde deve.

O filtro é o critério de Nyquist aplicado oitava a oitava. Uma onda precisa de pelo menos duas
amostras por comprimento para ser representada. Se o passo da janela é maior que isso, a oitava
é apagada — suavemente, com um `smoothstep`, para não criar degrau entre níveis de zoom.

### 13.5 Implementação

#### Passo 1 — Nova função em `cartographer/math/noise.py`

Adicione à classe `NoiseGenerator`. **Não altere `generate_noise_field`** — ela é usada por
todo o resto e é guardada pelo teste T3.

```python
    @staticmethod
    def generate_detail_field(grid_x, grid_y, scale, octaves, seed, passo_mundo_px,
                              offset=0, persistencia=0.5, lacunaridade=2.0):
        """
        Campo de detalhe fino com LIMITE DE BANDA (D2/Caminho B do DIAGNOSTICO_V3).

        Diferença para `generate_noise_field`: cada oitava cujo comprimento de onda é menor
        que o dobro do passo de amostragem da janela (`passo_mundo_px`, em px de MUNDO por
        amostra) é apagada suavemente antes de entrar na soma. Sem isso, um campo de escala
        sub-pixel vira ruído de amostragem ("sal e pimenta") no mapa-múndi.

        Isto NÃO viola F1 (pureza). O campo é sempre o mesmo em todo ponto do mundo; o que o
        passo controla é quanto dele a janela consegue representar — é antialiasing, o mesmo
        papel de um mipmap. T2 (subdivisão) continua exata porque subdividir uma janela em
        quadrantes na mesma resolução preserva o passo.

        Normaliza pela soma da série INFINITA, como `generate_noise_field` (correção F3 da
        Fase 0.2): apagar oitavas nunca reescala o que sobrou.

        Retorna a faixa [-1, 1] (centrada em zero), não [0, 1] — este campo é uma PERTURBAÇÃO
        somada a uma altitude que já existe, não uma altitude por si.
        """
        grid_x = np.asarray(grid_x, dtype=np.float32)
        grid_y = np.asarray(grid_y, dtype=np.float32)
        scale = max(1e-6, float(scale))
        passo = max(1e-12, float(passo_mundo_px))

        total = np.zeros_like(grid_x, dtype=np.float32)
        amplitude = 1.0
        frequency = 1.0

        for i in range(octaves):
            comprimento_onda = scale / frequency
            # Nyquist: >1 significa que a janela tem amostras de sobra para esta oitava.
            razao = comprimento_onda / (2.0 * passo)
            t = float(np.clip(razao - 1.0, 0.0, 1.0))
            fade = t * t * (3.0 - 2.0 * t)          # smoothstep: sem degrau entre zooms
            if fade > 0.0:
                total += perlin_noise_2d_vectorized(
                    (grid_x / scale) * frequency,
                    (grid_y / scale) * frequency,
                    seed=seed + offset + i * 100,
                ) * amplitude * fade
            amplitude *= persistencia
            frequency *= lacunaridade

        soma_infinita = 1.0 / (1.0 - persistencia) if persistencia < 1.0 else 1.0
        limite = soma_infinita * 0.707
        return np.clip(total / limite, -1.0, 1.0)
```

⚠️ O `offset` precisa ser diferente dos que já existem em `gerar_janela`: hoje usam-se
`0` (macro), `9999` (ruído marinho) e `12345` (costa). Use uma chave de config nova.

#### Passo 2 — Injetar em `TileCartographer.gerar_janela`

O ponto de injeção é **logo depois da mesclagem terra-mar** do canal 0 e **antes** do bloco de
clima. Em `cartographer/world/tile_cartographer.py`, procure por:

```python
        # Mesclagem terra-mar final no canal 0 (Altitude)
        data[:, :, 0] = np.where(
            mask_continente >= nivel_mar,
            relevo_continentes,
            (1.0 - (mask_continente / nivel_mar)) * ruido_mar_suave + (mask_continente / nivel_mar) * nivel_mar
        )
```

E insira **imediatamente depois**:

```python
        # --- Campo de detalhe local (D2 / Caminho B do DIAGNOSTICO_V3) ---
        # A altitude SEM detalhe é preservada para alimentar clima e bioma: a classificação
        # de bioma é regional e foi calibrada na Fase 1 contra este campo. O detalhe é
        # textura sub-regional; deixá-lo entrar em `classify_biomes` reabriria a calibração
        # de limiares de deserto/mediterrâneo sem necessidade (medido: 0,00% dos pixels
        # mudariam de bioma com a amplitude recomendada, mas a margem não é estrutural).
        altitude_regional = data[:, :, 0].copy()

        amp_detalhe = cfg_get(cfg, "relevo_detalhe_amplitude")
        if amp_detalhe > 0.0:
            passo_mundo_px = (x1 - x0) / largura
            margem_costa = cfg_get(cfg, "relevo_detalhe_margem_costa")
            # Envelope: o detalhe nasce em zero na linha d'água e cresce terra adentro.
            # É o que garante T6 (a costa não pode mudar entre zooms) por construção.
            envelope = np.clip((data[:, :, 0] - nivel_mar) / max(1e-6, margem_costa), 0.0, 1.0)
            detalhe = NoiseGenerator.generate_detail_field(
                grid_x, grid_y,
                scale=cfg_get(cfg, "relevo_detalhe_escala_px"),
                octaves=cfg_get(cfg, "relevo_detalhe_oitavas"),
                seed=self.seed,
                passo_mundo_px=passo_mundo_px,
                offset=cfg_get(cfg, "relevo_detalhe_offset_ruido"),
            )
            # Piso de segurança: um pixel que é terra nunca pode virar água por causa do
            # detalhe, nem com envelope. Redundante com o envelope, mantido como rede.
            piso = np.where(data[:, :, 0] > nivel_mar, nivel_mar + 1e-6, data[:, :, 0])
            data[:, :, 0] = np.maximum(data[:, :, 0] + amp_detalhe * detalhe * envelope, piso)
```

E então, no bloco de clima logo abaixo, **troque `data[:, :, 0]` por `altitude_regional`** nas
três chamadas (`calculate_temperature`, `calculate_humidity`, `classify_biomes`). Não troque em
mais lugar nenhum.

Consequência aceita e documentada: um pico que só existe na escala de detalhe **não** vira
bioma "Montanha". A cor dele ainda acompanha o relevo, porque `render_npz_array` usa o canal 0,
que **tem** o detalhe. Só o ID do bioma usa a altitude regional.

#### Passo 3 — Chaves novas no `config.json`

Em `cartografia`, junto das outras chaves de ruído:

```json
"_comentario_relevo_detalhe": "D2/Caminho B do DIAGNOSTICO_V3 (2026-09-11): campo de detalhe fino somado à altitude de terra, com limite de banda por oitava (antialiasing por Nyquist). Resolve o teto de detalhe do raster, que saturava no z6 — sem ele, todo zoom acima disso é ampliação pura e a cidade fica desenhada sobre mancha lisa. NÃO tente obter o mesmo efeito subindo tile_oitavas_max: a cauda do fBm global tem amplitude ~1e-4 e é invisível (ver Seção 13.2 do diagnóstico). relevo_detalhe_escala_px é o comprimento de onda da oitava MAIS GROSSA, em px de mundo — 0.5 px = 7,9 km; abaixo de 0.5 o campo começa a vazar para o mapa-múndi. relevo_detalhe_oitavas define até onde o detalhe desce: a oitava mais fina tem escala/2^(oitavas-1), então 10 oitavas chegam a 0,00098 px = 15 m. relevo_detalhe_margem_costa é a faixa de altitude acima do nível do mar em que o detalhe entra em fade-in, preservando a linha d'água (T6).",
"relevo_detalhe_amplitude": 0.006,
"relevo_detalhe_escala_px": 0.5,
"relevo_detalhe_oitavas": 10,
"relevo_detalhe_margem_costa": 0.05,
"relevo_detalhe_offset_ruido": 31337,
```

Faixa útil medida para `relevo_detalhe_amplitude`: **0,005 a 0,010**. Acima de 0,020 a textura
satura e o terreno vira granulado. `0,006` é o ponto de partida recomendado.

#### Passo 4 — Três testes novos em `tests/test_cartografia.py`

Os testes T1 a T6 existentes **continuam passando sem alteração** — verificado no protótipo.
Some estes três, que guardam especificamente o campo novo:

```python
def test_detalhe_nao_vaza_para_zoom_baixo():
    """T7 — o campo de detalhe tem que ser invisível nos zooms onde a janela não o resolve.
    Se este teste falhar, o mapa-múndi ganhou ruído de amostragem (aliasing)."""
    tc = _cartografo_de_teste()
    # z0: passo de 1 px de mundo; a oitava mais grossa do detalhe tem 0,5 px.
    com = tc.gerar_janela(300, 300, 556, 556, 256, 256, oitavas_extra=0)
    cfg = CARTOGRAPHER_CONFIG
    amp = cfg["relevo_detalhe_amplitude"]
    cfg["relevo_detalhe_amplitude"] = 0.0
    try:
        sem = tc.gerar_janela(300, 300, 556, 556, 256, 256, oitavas_extra=0)
    finally:
        cfg["relevo_detalhe_amplitude"] = amp
    assert np.allclose(com[:, :, 0], sem[:, :, 0], atol=1e-6)


def test_detalhe_preserva_a_costa():
    """T8 — somar detalhe não pode mover a linha d'água em nenhum zoom. É o que separa
    'textura de relevo' de 'outro mundo'."""
    tc = _cartografo_de_teste()
    nm = CARTOGRAPHER_CONFIG["nivel_mar"]
    cfg = CARTOGRAPHER_CONFIG
    amp = cfg["relevo_detalhe_amplitude"]
    for z in (4, 8, 12):
        lado = 256 / (2 ** z)
        com = tc.gerar_janela(300, 300, 300 + lado, 300 + lado, 128, 128, oitavas_extra=min(z, 9))
        cfg["relevo_detalhe_amplitude"] = 0.0
        try:
            sem = tc.gerar_janela(300, 300, 300 + lado, 300 + lado, 128, 128, oitavas_extra=min(z, 9))
        finally:
            cfg["relevo_detalhe_amplitude"] = amp
        assert int(((com[:, :, 0] >= nm) != (sem[:, :, 0] >= nm)).sum()) == 0, f"costa mudou no z={z}"


def test_detalhe_produz_relevo_na_escala_da_cidade():
    """T9 — o objetivo do campo: numa janela do tamanho de uma cidade grande ainda tem que
    haver variação de altitude. Sem o campo, essa janela é um plano."""
    tc = _cartografo_de_teste()
    lado = 0.1138          # diâmetro de uma cidade grande, em px de mundo (Seção 2.3)
    j = tc.gerar_janela(400, 578, 400 + lado, 578 + lado, 128, 128, oitavas_extra=9)
    alt = j[:, :, 0]
    assert float(alt.max() - alt.min()) > 5e-4, "janela de cidade continua plana"
```

⚠️ Os testes T7 e T8 mexem no dicionário global de config. Se o projeto tiver uma fixture de
config, use ela. Se não tiver, mantenha o `try/finally` — sem ele, um teste que falhar deixa a
config zerada e derruba os outros.

#### Passo 5 — A cidade passa a enxergar o terreno

Este é o passo que responde à queixa original do usuário (*"não existe relação do que está na
cidade × a posição no continente"*). **Faça só depois do D1 e dos passos 1 a 4.**

Hoje `generate_city_geometry.py` usa ruído próprio, seedado por `zlib.crc32(nome)`, porque na
escala da cidade **não havia** informação de terreno. Depois do Caminho B, há. Medição do
protótipo, janela de 0,1138 px de mundo (uma cidade grande):

| | amplitude de altitude na janela |
|---|---|
| hoje | 0,000522 |
| com campo de detalhe | 0,001254 |

Implementação mínima, em `GeradorCidade`:

1. No `__init__`, amostre o terreno local uma vez:
   ```python
   # O terreno na escala da cidade passou a existir (D2/Caminho B). Amostrar aqui é o que
   # liga a geometria urbana ao relevo do mundo — antes isto era ruído inventado localmente.
   lado_px = 2.0 * self.raio_m / (math.sqrt(self.escala_pixel_area_km2) * 1000.0)
   self.terreno = cartografo.gerar_janela(
       self.cx_mundo - lado_px / 2, self.cy_mundo - lado_px / 2,
       self.cx_mundo + lado_px / 2, self.cy_mundo + lado_px / 2,
       64, 64, oitavas_extra=cfg_get(config, "tile_oitavas_max") - cfg_get(config, "ruido_macro_oitavas"),
   )[:, :, 0]
   ```
   O `TileCartographer` vem de `cartographer.tiles.render.obter_cartografo()`, que já é o de
   processo único montado a partir do manifesto. **Não instancie um novo** — instanciar com
   layout diferente geraria terreno diferente do que o mapa mostra.

2. Um helper `_altitude_local(x_m, y_m)` que converte metros locais para índice nessa grade
   de 64×64 e devolve a altitude, e um `_declividade_local(x_m, y_m)` a partir de
   `np.gradient` dela.

3. Use nos três lugares em que a decisão hoje é arbitrária:
   - **Praça**: em vez do centro geométrico, o ponto mais plano dentro do anel central.
   - **Edifícios**: rejeite o lote cuja declividade passa de `cidade_geo_declividade_max`
     (chave nova). Um lote rejeitado vira espaço vazio, não um edifício deslocado.
   - **Portões**: prefira os setores de menor declividade na muralha, que é por onde uma
     estrada real sairia.

4. Guarde a altitude em `properties.altitude` de cada `edificio`. Isso abre a porta para a
   Fase 5 gerar narrativa coerente ("a forja fica na parte alta da cidade").

⚠️ **Não** troque a malha viária inteira por um gerador guiado por terreno neste passo. A malha
radial atual funciona e foi testada por conservação de área. Mudar as duas coisas ao mesmo tempo
torna impossível saber qual quebrou.

### 13.6 Resultados medidos do protótipo

Textura da imagem renderizada, desvio-padrão do brilho. Ponto de teste `(400, 578)`, interior de
continente, altitude 0,567. Valores abaixo de ~8 são relevo ilegível.

| configuração | z=0 | z=2 | z=4 | z=6 | z=8 | z=10 | z=12 | z=14 |
|---|---|---|---|---|---|---|---|---|
| **sem detalhe (hoje)** | 7,14 | 13,86 | 18,08 | 14,33 | 15,34 | 17,95 | 13,44 | **11,76** |
| amp 0,005 | 7,14 | 13,86 | 29,43 | 30,72 | 33,00 | 29,64 | 33,89 | 34,61 |
| **amp 0,010 (recomendado ≈0,006)** | **7,14** | **13,86** | 35,42 | 35,75 | 37,16 | 32,72 | 38,43 | **39,57** |
| amp 0,020 | 7,14 | 13,86 | 38,11 | 37,47 | 38,28 | 32,95 | 39,48 | 40,97 |

Leia as duas colunas em negrito. Em **z0 e z2 o valor é idêntico ao de hoje**: o mapa-múndi não
muda em nada. Em **z14 a textura triplica**, e — o que mais importa — ela fica **estável de z4 a
z14** em vez de despencar. Relevo aparente constante em qualquer zoom é exatamente o
comportamento de mapa que o usuário pediu.

⚠️ Um aviso sobre como medir: o primeiro protótipo foi rodado sobre Pelamont, em `(507, 397)`,
e **não mostrou ganho nenhum**. O motivo é o D4: Pelamont está na linha d'água exata, onde o
envelope de costa zera o detalhe de propósito. **Meça sempre num ponto de interior.** Se você
medir numa cidade antes de corrigir o D4, vai concluir errado que o campo não funciona.

### 13.7 Invariantes — verificado, não presumido

Rodado contra o mundo real em `database/`:

| verificação | resultado |
|---|---|
| T2, subdivisão bit a bit | **PASSOU** |
| T6, terra/água entre taxas de amostragem | **0 flips** |
| costa idêntica ao mundo atual, z=4 | **0 flips** |
| costa idêntica ao mundo atual, z=10 | **0 flips** |
| pixels que mudam de bioma, z=4 e z=8 | **0,00%** |
| custo por tile, z=4 | 238 ms → 247 ms (**+4%**) |
| custo por tile, z=12 | 375 ms → 412 ms (**+10%**) |

**A costa não muda em nenhum zoom.** Isso significa que o mundo atual continua válido: você
não precisa regerar continentes, cidades ou o `openworld.db` por causa deste campo. Regere só
o cache de tiles, que o `config_hash` invalida sozinho.

**Fórmula do `maxNativeZoom`** (usada no D5). A oitava mais fina do campo tem comprimento de
onda `escala / 2^(oitavas-1)`. Ela fica totalmente resolvida quando o passo da janela é metade
disso. Como o passo no zoom *z* é `1/2^z`:

```
maxNativeZoom = ceil( log2( 2^oitavas / escala_px ) )
              = ceil( log2( 2^10 / 0,5 ) ) = ceil( log2(2048) ) = 11
```

Acima do z11 não há informação nova, e o Leaflet deve esticar. Se você mudar
`relevo_detalhe_oitavas` ou `relevo_detalhe_escala_px`, **recalcule `tile_max_native_zoom` com
esta fórmula** — deixá-los dessincronizados é desperdiçar CPU ou perder detalhe.

### 13.8 Ordem de trabalho e critério de aceite

| # | Passo | Aceite |
|---|---|---|
| 1 | `generate_detail_field` em `noise.py` | Testes T1–T6 existentes continuam passando |
| 2 | Injeção em `gerar_janela` + config | T7, T8, T9 novos passam |
| 3 | `tile_max_native_zoom` de 6 para 11 (D5) | Nenhum `GET /tiles/12/...` no log do Flask |
| 4 | Calibrar `relevo_detalhe_amplitude` | Tabela da Seção 13.6 reproduzida no mundo atual |
| 5 | Validação visual | Print do zoom 11 numa cidade, mostrando relevo sob a geometria |
| 6 | Cidade lê o terreno (Passo 5) | `properties.altitude` presente em todo `edificio` |

Comando de aceite dos passos 1–2:
```bash
venv/bin/python -m pytest tests/ -v          # 7 antigos + 3 novos = 10 passando
```

Reprodução da tabela 13.6 (adapte o ponto se você regerou o mundo — escolha um pixel com
altitude acima de 0,45):
```bash
venv/bin/python -c "
import numpy as np
d = np.load('database/mapa_composto.npz')['mapa'][:,:,0]
ys, xs = np.where(d > 0.45)
print('use um destes pontos de interior:', list(zip(xs[::len(xs)//5], ys[::len(ys)//5])))
"
```

### 13.9 Não faça

- ❌ **Não** ligue o detalhe por faixa de zoom com um `if z > N`. Isso quebra F1 e reintroduz
  o bug original do projeto, em que o zoom **contradizia** o zoom anterior em vez de refinar.
  O gate é o passo de amostragem, por oitava, com fade suave.
- ❌ **Não** normalize pela soma truncada das amplitudes que sobraram depois do fade. Isso
  reescalaria o campo conforme oitavas entram e saem, que é exatamente o bug que a Fase 0.2
  corrigiu em `generate_noise_field`. Use a soma da série infinita, como no código do Passo 1.
- ❌ **Não** alimente `classify_biomes` com a altitude detalhada sem medir. A calibração de
  limiares de bioma da Fase 1 foi trabalhosa, e reabri-la de graça não paga.
- ❌ **Não** remova o envelope de costa achando que o piso de segurança basta. O envelope é o
  que faz T8 passar **por construção**; o piso é só rede de proteção.
- ❌ **Não** use `escala` abaixo de 0,5 px sem remedir o z2. Foi medido: em 0,15 px o campo vaza
  para o mapa-múndi mesmo com o filtro, porque a oitava mais grossa já entra na faixa de
  aliasing dos zooms baixos.
- ❌ **Não** meça o efeito numa cidade antes de o D4 estar corrigido. Ver o aviso da Seção 13.6.

---

## 14. O que este documento NÃO cobre

Para não criar falsa sensação de completude:

- **Fase 5 do plano V2** (narrativa de cidade por IA) não foi iniciada e não é tratada aqui.
  Ela depende de D1 e D4 estarem corrigidos, senão a IA vai escrever descrições de cidades
  costeiras amontoadas que não correspondem ao mapa.
- **As linhas/emendas visíveis nos tiles**, relatadas pelo usuário na validação anterior
  (2026-09-11, antes desta) e adiadas por ele como melhoria futura. Continuam adiadas.
- **Fase 1.2 do plano V2** (calibração visual de oitavas por zoom) continua pendente. A medição
  do D2 dá o dado que faltava para ela: o detalhe satura no z6. Quem for executar a Fase 1.2
  deve começar por aí, e a Seção 13 provavelmente a substitui por inteiro.
- **Nenhum código foi alterado nesta sessão.** Este documento é diagnóstico e especificação.
  O Caminho B da Seção 13 foi **prototipado e medido**, mas o protótipo vive num arquivo
  descartável fora do projeto — nada dele foi aplicado em `cartographer/`. Todos os números
  descrevem o estado do código em 2026-09-11, com as Fases 0–4 concluídas e **nada commitado**.
