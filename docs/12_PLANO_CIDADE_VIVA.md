# 🏘️ Plano da Cidade Viva — malha correta, terreno livre e simulação multi-cidade

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este documento é uma **lista de tarefas fechadas**, no mesmo formato do
> [`10_PLANO_REFATORACAO.md`](10_PLANO_REFATORACAO.md). Cada tarefa tem arquivo alvo, o
> problema concreto (com número medido, não com opinião), a ação passo a passo e como
> validar. **Execute na ordem dos blocos.** Se uma tarefa não está aqui, não faça agora.
>
> 👉 **Antes de escrever qualquer linha**, leia [`11_ARQUITETURA.md`](11_ARQUITETURA.md) —
> especialmente a Seção 2 (regra de dependência entre camadas) e a Seção 4 (limites de
> tamanho). Este plano cria arquivos novos em três camadas diferentes e **a maior fonte
> de erro aqui vai ser colocar código na camada errada**, não errar a matemática.
>
> 👉 Leia também a Seção 5.5 de [`09_ESPEC_DESENHO_CIDADE.md`](09_ESPEC_DESENHO_CIDADE.md):
> "o que é gancho de modelo e o que é trabalho compartilhado". Metade das tarefas do
> Bloco Q dependem de você entender essa divisão.

**Criado em:** 2026-09-12
**Base analisada:** branch `reescrita-estrutura`, commit `66c5622`
**Medições:** feitas sobre as 15 cidades em `database/cidades/` e sobre o banco
`database/openworld.db` no estado atual (20 NPCs, 24.423 locais).

---

## Índice

- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. Diagnóstico: o que está errado e por quê](#1-diagnóstico-o-que-está-errado-e-por-quê)
- [2. Decisões já tomadas (não reabra)](#2-decisões-já-tomadas-não-reabra)
- [3. As cinco armadilhas deste plano](#3-as-cinco-armadilhas-deste-plano)
- [Bloco G — Malha geometricamente válida](#bloco-g--malha-geometricamente-válida)
- [Bloco Q — Quadra perimetral, pátio e escala da cidade](#bloco-q--quadra-perimetral-pátio-e-escala-da-cidade)
- [Bloco T — Terreno livre como entidade de primeira classe](#bloco-t--terreno-livre-como-entidade-de-primeira-classe)
- [Bloco O — Obra: quem constrói o quê, e quando](#bloco-o--obra-quem-constrói-o-quê-e-quando)
- [Bloco X — Auto-expansão da cidade](#bloco-x--auto-expansão-da-cidade)
- [Bloco P — Performance e simulação multi-cidade](#bloco-p--performance-e-simulação-multi-cidade)
- [Bloco V — Validação permanente](#bloco-v--validação-permanente)
- [Anexo 1 — Tabela de medições da base atual](#anexo-1--tabela-de-medições-da-base-atual)
- [Anexo 2 — Chaves de config novas e removidas](#anexo-2--chaves-de-config-novas-e-removidas)
- [Anexo 3 — Glossário de geometria urbana](#anexo-3--glossário-de-geometria-urbana)

---

## 0. Como usar este documento

### Regras de execução

1. **Uma tarefa por commit.** Título do commit = ID da tarefa + descrição curta.
   Ex.: `G01: perturba anel pelo vão, não pelo raio`.
2. **Este plano MUDA comportamento observável de propósito.** Diferente do
   `10_PLANO_REFATORACAO.md`, aqui o "diff de comportamento vazio" não se aplica: o
   traçado de todas as cidades vai mudar. Veja a armadilha #1 na Seção 3.
3. **Rode os testes antes e depois de cada tarefa:**
   ```
   venv/bin/python -m pytest tests/ -q
   ```
4. **Depois de cada tarefa do Bloco G ou Q, regenere e audite:**
   ```
   venv/bin/python cartographer/cities/generate_city_geometry.py
   venv/bin/python builder/fix/audit_cidades.py      # criado em V02
   ```
5. **Se uma tarefa parecer maior do que o descrito, pare e anote** no final do
   documento em vez de improvisar outra solução.
6. **Não renomeie nada além do que a tarefa pede.**

### Formato de cada tarefa

```
### G01 · Título
**Arquivos:** caminho(s)
**Problema:** o que está errado hoje, com o número medido
**Ação:** o que fazer, passo a passo
**Validar:** como provar que deu certo
**Risco:** baixo | médio | alto
```

### Ordem e dependências

Os blocos **não** são independentes. Esta é a ordem obrigatória e o motivo de cada seta:

```
V02, V03  (ferramentas de medida — faça primeiro, você vai usá-las em tudo)
    │
    ▼
Bloco G   (malha válida)                    ← resolve o que você já está vendo na tela
    │
    ▼
Q02 (pacote) → Q01 (anel perimetral) → Q03, Q04
    │
    ▼
Bloco T   (lote persistido, ocupação parcial)
    │
    ├──► Bloco O   (obra em lote real, comércio por demanda)
    │        │
    │        ▼
    │    Bloco X   (auto-expansão)  ← precisa de G06 e de Q01
    │
    └──► Bloco P   (performance, multi-cidade)  ← faça ANTES de ligar as 15 cidades
```

`Bloco P` e `Bloco O` podem andar em paralelo depois de `T`, se forem duas pessoas. Se for
uma só, faça `P` antes de `O`: é mais fácil depurar lógica nova num tick de 80 ms do que
num de 16 s.

**Parada obrigatória:** depois do Bloco G, regenere as 15 cidades e olhe o mapa. Se as
cidades contorcidas não sumiram, **não siga para Q** — algo do diagnóstico da Seção 1 não
se aplica ao que você tem, e continuar só empilha mudança sobre uma premissa errada.

---

## 1. Diagnóstico: o que está errado e por quê

Rodei cinco medições sobre as 15 cidades já geradas. **Todos os números abaixo são
medidos, não estimados.** A tabela completa está no [Anexo 1](#anexo-1--tabela-de-medições-da-base-atual).

### 1.1 A cidade contorcida: a perturbação dos anéis é proporcional ao raio errado

Esta é a causa raiz do problema que você relatou ("cidades contorcidas com ruas e quadras
se sobrepondo"), e **não é exclusiva do modelo orgânico** — o radial grande também sofre.

Em `cartographer/cities/modelos/radial.py`, cada vértice da malha nasce assim:

```python
raios_base = [self.raio_m * (j + 1) / (self.num_aneis + 1) for j in range(self.num_aneis)]
...
r = raios_base[j] * (1.0 + self.irreg * perturb[j, i])
```

A amplitude da perturbação do anel `j` é `irreg × raios_base[j]` — ela **cresce junto com
o raio do anel**. Mas a coisa que ela não pode atropelar é o **vão** entre dois anéis
vizinhos, que é constante: `raio_m / (num_aneis + 1)`.

Divida um pelo outro. Para o anel mais externo:

```
amplitude / vão  =  irreg × num_aneis
```

E como dois anéis vizinhos podem se mover **um na direção do outro**, o fechamento real é
a soma das duas amplitudes:

```
(amp_j + amp_{j+1}) / vão  =  irreg × (2j + 3)
```

Com `irreg = 0.15` (radial) e `j = 3`, isso já dá **1,35**. Maior que 1 significa: o anel
de fora passa para dentro do anel de dentro. A quadra entre eles inverte, o polígono vira
gravata-borboleta, a rua radial sai e volta, e a cidade fica **contorcida**.

Monte Carlo com 2.000 seeds por configuração, medindo a chance de a cidade ter pelo menos
um cruzamento de anéis:

| `irreg` | modelo | 2 anéis | 3 anéis | 4 anéis | 5 anéis | 6 anéis |
|---|---|---|---|---|---|---|
| 0,15 | `radial` | 0,0% | 0,0% | 1,3% | **43,5%** | **82,5%** |
| 0,33 | `organica` | 9,2% | **82,7%** | **99,1%** | **100%** | **100%** |

`cidade_geo_num_aneis_faixa_por_tamanho` hoje é `{"pequeno": [2,3], "medio": [3,4],
"grande": [4,6]}`. Ou seja: **toda cidade grande radial tem de 43% a 82% de chance de
nascer quebrada, e toda cidade orgânica nasce quebrada.** Confere com o que você viu.

Nas cidades geradas hoje, a razão amplitude/vão medida:

| Cidade | Modelo | Anéis | Vão | Amplitude | Razão | Cruzamentos reais |
|---|---|---|---|---|---|---|
| Fenelburgo | `organica` | 4 | 169 m | 223 m | **1,32** | 3 |
| Cidade das Flores | `organica` | 3 | 119 m | 118 m | **0,99** | 2 |
| Jordorstead | `radial` | 5 | 165 m | 124 m | 0,75 | 0 (seed com sorte) |
| Tordordor | `radial` | 4 | 122 m | 73 m | 0,60 | 0 |

> ⚠️ **Não conclua que radial está bom.** Jordorstead está em 0,75 e só escapou porque o
> sorteio não alinhou. É uma bomba armada, não um sistema correto. Corrija os dois.

### 1.2 O modelo orgânico degrada a RUA sem degradar a QUADRA

`organica.py` roda `super().construir_malha()` e depois mexe **só na lista de ruas**:

```python
malha.ruas = [self._torcer_radial(r) if r.tipo_via == "radial" else r for r in malha.ruas]
```

`_torcer_radial` desloca lateralmente os pontos da rua. Mas a quadra continua com os
vértices originais. Resultado medido: em Fenelburgo, a rua radial fica em **média 6,4 m e
até 12,7 m** de distância da aresta de quadra que ela deveria margear. A meia-largura de
uma via secundária mais o recuo é 5,5 m. Ou seja: **a rua invade a quadra, ou abre um vão
de terra de nada.** É literalmente "rua e quadra se sobrepondo".

O mesmo vale para `_abrir_anel`: ele remove um arco da rua-anel, mas as quadras dos dois
lados continuam achando que têm rua ali.

**A lição de engenharia aqui é a mais importante do documento:** rua e quadra não são duas
listas independentes, são **duas leituras da mesma grade de vértices**. Quem perturba a
cidade tem que perturbar a grade, nunca uma das leituras. Veja `G04`.

### 1.3 A muralha não envolve a cidade

O anel de borda usa `irreg * 0.5 * perturb[num_aneis, i]`. A muralha usa
`irreg * 0.3 * perturb_muralha[i]` — **um array de aleatórios diferente**. Não há
correlação nenhuma entre os dois, e a folga configurada é só 40 m.

Quadras para fora da muralha, medido por setor:

| Cidade | Modelo | Setores com quadra fora do muro | Pior invasão |
|---|---|---|---|
| Fenelburgo | `organica` | 2 de 11 | **103 m** |
| Jordorstead | `radial` | 3 de 12 | **62 m** |
| Keldorstead | `radial` | 3 de 12 | 21 m |
| Cidade das Flores | `organica` | 1 de 11 | 40 m |

Isso é acidente, não feature. E atrapalha a auto-expansão do Bloco X, que precisa do muro
como fronteira confiável entre "dentro" e "arrabalde".

### 1.4 A casa no meio da quadra: subdivisão recursiva não conhece rua

`GeradorCidade._subdividir_lote` corta o quadrilátero da quadra ao meio pelo lado mais
longo, recursivamente, até a área bater no alvo. **Essa função não tem a menor ideia de
onde estão as ruas.** Uma quadra de 180 × 180 m com alvo de 400 m² produz uma grade
6 × 7 de lotes, e os 20 lotes do miolo não têm frente para nada.

Medi, para cada lote, a distância do centroide até a rua mais próxima:

| Cidade | Modelo | Lotes | Lotes a mais de 25 m de qualquer rua | Pior caso |
|---|---|---|---|---|
| Fenelburgo | `organica` | 3.129 | **2.007 (64%)** | 223 m |
| Jordorstead | `radial` | 6.046 | **3.506 (58%)** | 140 m |
| Keldorstead | `radial` | 2.835 | 1.366 (48%) | 97 m |
| Irenburgo | `grade` | 2.474 | 930 (38%) | 42 m |
| Cidade da Lua | `grade` | 2.012 | 693 (34%) | 63 m |
| Corarfield | `linear` | 952 | 116 (12%) | 34 m |
| Belinhaven | `linear` | 72 | **0 (0%)** | 15 m |

Note que `linear` é o único modelo sadio — porque as quadras dele são **rasas por
construção** (uma fileira de profundidade), não porque ele tem lógica de frente. É a
prova de que a solução é geométrica, não estatística.

E o número absoluto de lotes por quarteirão é absurdo: mediana de **94 lotes por quadra**
em Jordorstead, máximo de **209**. Uma quadra medieval tem de 8 a 30 lotes.

### 1.5 A cidade nasce 100% construída, para 20 habitantes

Hoje `builder/populador.py` importa **todo** edifício do GeoJSON de **todas** as 15
cidades como `Local`. Estado do banco agora:

| Tabela | Contagem |
|---|---|
| `locais` | **24.423** |
| `locais` com `categoria = 'residencia'` | **21.008** |
| `npcs` | **20** |

Vinte e um mil casas prontas para vinte pessoas. Isso não é só feio: é a causa direta do
problema de performance do Bloco P, porque quase todo laço da engine varre `mundo.locais`
inteiro.

E a mecânica que você citou — casal recém-casado pega um terreno e constrói — hoje **não
usa a geometria da cidade para nada**:

```python
# engine/mechanics/housing.py, iniciar_obra_para_casal
x, y = GeoUtils.sortear_ponto_em_terra(cx, cy, raio, nivel_mar)
```

Sorteia um ponto qualquer em terra firme num raio ao redor da cidade. A casa nova nasce no
meio do mato, possivelmente do outro lado do muro, possivelmente sobre outro edifício.

### 1.6 O custo do tick é o produto NPCs × locais

Medi o tick com um mundo sintético, variando as duas dimensões:

| NPCs | Locais | ms por tick | ticks por segundo |
|---|---|---|---|
| 20 | 1.000 | 2,9 | 347 |
| 20 | 24.000 | **53,8** | 18,6 |
| 200 | 24.000 | 580 | 1,7 |
| 500 | 24.000 | 1.608 | 0,6 |
| 1.500 | 24.000 | 6.317 | 0,2 |
| 3.000 | 24.000 | **16.629** | 0,06 |

Perfeitamente linear no produto. Vinte NPCs custam 53,8 ms só porque há 24 mil locais — o
mesmo mundo com mil locais custa 2,9 ms. **O gargalo não é a quantidade de NPCs, é o
tamanho da lista que cada NPC varre.**

O profiler mostra exatamente onde:

| Função | O que ela faz |
|---|---|
| `NPCUtils.obter_obra_do_npc` | varre os 24.423 locais, **por NPC, por tick** |
| `NPCMovementManager.mover_aleatoriamente` | varre os 24.423 locais, **por NPC, por tick** |
| `LocationUtils.is_local_passeio` | 146.538 chamadas em 3 ticks com 20 NPCs |
| `LocationUtils.is_local_publico` | chama `carregar_config_global()` **dentro do laço** |
| `NPCUtils.contar_dependentes_na_casa` | varre a lista de NPCs, por NPC, por tick |

Nenhuma dessas varreduras precisa existir. Todas viram consulta a índice. **Isso é o
Bloco P, e ele vale mais do que qualquer paralelização** — veja a armadilha #5.

---

## 2. Decisões já tomadas (não reabra)

Foram decididas com o dono do projeto. Trate como requisito, não como sugestão.

| # | Decisão | Consequência prática |
|---|---|---|
| D1 | **População configurável, começando em 50 NPCs por cidade, em todas as 15.** | ~750 NPCs. Duas chaves novas de config (`P07`). |
| D2 | **Ocupação inicial por tamanho: ~25% (pequeno), ~40% (médio), ~60% (grande).** | O resto nasce terreno livre (`T03`). |
| D3 | **Quadra = um anel de lotes no perímetro, pátio no miolo.** Todo lote tem frente para rua, por construção. | `Q01`. O pátio é uma camada nova no mapa. |
| D4 | **Orçamento de performance: 1 segundo por tick, para sustentar velocidade 60×.** | Meta de `P06`. Não é 60 ms nem 60 s. |
| D5 | **Um float no config controla o tamanho global das cidades.** | `Q04`. |
| D6 | **Reset completo do mundo é aceitável.** Nenhuma migração de banco ou de GeoJSON antigo. | Simplifica `T01`, `T02`, `X03`. |

---

## 3. As cinco armadilhas deste plano

Leia esta seção duas vezes. São os cinco erros que um executor cuidadoso ainda comete,
porque o código atual **te convida** a cometê-los.

### Armadilha 1 · "Determinístico" não significa "igual ao de antes"

`radial.py` tem este aviso no `__init__`:

> ⚠️ Ordem de consumo do self.rng idêntica à do GeradorCidade de antes do F4
> (raio → anéis → fator de lote → setores) — mudar a ordem muda todas as cidades do
> mundo, silenciosamente.

Esse aviso foi escrito para proteger uma **refatoração**, onde a saída tinha que bater
byte a byte. **Este plano não é uma refatoração.** Ele vai mudar o traçado de todas as
cidades de propósito, e isso está aprovado (D6).

O que continua valendo, e é inegociável:

- **Mesma seed ⇒ mesma cidade.** Duas execuções de `generate_city_geometry.py` sobre o
  mesmo manifesto têm que produzir GeoJSON idêntico. O teste `test_determinismo` em
  `tests/test_cidades.py` protege isso — **nunca o afrouxe**.
- **Nada de `hash()`.** Sempre `zlib.crc32`. `hash()` de string em Python varia entre
  processos (`PYTHONHASHSEED`), o que faz a cidade mudar sozinha entre execuções.
- **Sorteio novo vai no fim do `__init__`, ou usa RNG derivado.** Se você precisa de um
  sorteio novo no meio da sequência, use `random.Random(sitio.seed ^ CONSTANTE)`, como
  `escolher_modelo` já faz. Assim o novo sorteio não desloca os que vêm depois, e o dia
  que outra tarefa mexer ali você não quebra tudo de novo.

Quando uma tarefa remove um sorteio (por exemplo `G05`, que passa a **calcular**
`num_aneis` em vez de sorteá-lo), a sequência do RNG inteira se desloca e todas as cidades
mudam. **Isso é esperado. Diga no commit, não tente compensar com um sorteio-fantasma.**

### Armadilha 2 · O cartógrafo não pode conhecer o NPC, e a engine não pode escrever GeoJSON

A regra de dependência da Seção 2 do `11_ARQUITETURA.md` diz: `cartographer/` não conhece
NPC. Este plano cria um sistema onde a simulação **constrói casas em lotes que o
cartógrafo desenhou**. Existe uma forma óbvia e errada de fazer isso: a engine reabre o
`.geojson` e reescreve `"estado": "ocupado"` no lote.

**Não faça.** Se você fizer, o arquivo de geometria passa a ser estado mutável de
simulação, o cache por mtime de `web/cache_mapa.py` invalida a cada tick, e `cartographer/`
vira dependência da engine.

A divisão correta:

| Coisa | Onde vive | Quem escreve |
|---|---|---|
| Geometria do lote (polígono, área, classe da frente) | `database/cidades/<slug>.geojson` | só `cartographer/` |
| Estado do lote (livre / obra / ocupado, dono, `local_id`) | tabela `lotes` no SQLite | só `engine/` |
| Ligação entre os dois | o **id do lote**, estável e determinístico | — |

A única exceção é a auto-expansão (`X03`), que **acrescenta** features novas ao arquivo.
Mesmo ali, quem gera a geometria é uma função pura em `cartographer/cities/expansao.py`,
e quem decide *quando* chamá-la é a engine. O cartógrafo recebe "preciso de espaço para
N lotes"; ele nunca pergunta quantos NPCs existem.

### Armadilha 3 · Id de lote precisa ser estável, e o `idx` global de hoje não é

Hoje o id do edifício é um contador global sobre a lista de features:

```python
idx_edificio += 1
slug_id = f"{self.nome.lower().replace(' ', '_')}_{idx_edificio:03d}"
```

Se qualquer coisa mudar antes dele — uma quadra descartada por ser íngreme, um lote a
mais em outra banda — **todos os ids depois daquele ponto deslocam**. Como
`NPC.casa_id` e `NPC.local_trabalho_id` guardam esse id, regenerar a cidade move todos os
NPCs para casas alheias, sem erro nenhum aparecendo.

A partir de `Q01`, o id vem da **posição na malha**, não da ordem de emissão:

```
lote:     "{slug}_{quarteirao_id}_l{indice_no_anel:02d}"
edificio: mesmo id do lote onde ele está
```

`quarteirao_id` já é derivado de `(banda, setor)` no radial e de `(row, col)` na grade —
posicional, estável. O `indice_no_anel` é a posição do lote no anel perimetral, contado
sempre a partir da aresta 0 da quadra, no mesmo sentido. Determinístico e independente do
resto da cidade.

**Um edifício é identificado pelo terreno que ele ocupa.** Essa única decisão elimina toda
uma classe de referência pendurada.

### Armadilha 4 · A janela de terreno tem o tamanho da cidade, e a expansão acontece fora dela

`SitioCidade.medir()` amostra o terreno assim:

```python
lado_px = 2.0 * raio_provisorio / metros_por_px
janela = cartografo.gerar_janela(..., 64, 64, ...)
```

Uma grade 64 × 64 cobrindo exatamente o diâmetro da cidade. E a leitura de terreno faz:

```python
ix = int(np.clip(fx * n, 0, n - 1))
```

`np.clip`. Quer dizer: **qualquer ponto fora da cidade lê a célula da borda, silenciosamente,
sem erro.** Hoje isso não importa porque nada é gerado fora do raio. A partir do Bloco X
importa muito: o arrabalde inteiro nasce fora do raio original, e toda checagem de
declividade ali vai ler o mesmo pixel da borda e devolver a mesma resposta.

`G06` resolve isso: a janela passa a ser amostrada com margem (`fator × raio`), e
`_indice_terreno` passa a usar **a meia-largura real da janela**, não `self.raio_m`. Se
você pular `G06`, o Bloco X vai construir arrabaldes em cima de penhascos e ninguém vai
ver o bug.

### Armadilha 5 · Não paralelize um laço quadrático. Conserte a complexidade primeiro

A ideia de "uma thread por cidade" é natural e, neste caso, errada — por três motivos
independentes, nesta ordem de importância:

1. **O problema é algorítmico, não de throughput.** O tick custa `NPCs × locais`
   (medido na Seção 1.6). Com índices por cidade e categoria (`P01`–`P05`), o mesmo
   trabalho passa a custar `NPCs × constante`. Isso é uma redução de duas ordens de
   grandeza. Vinte threads te dariam, no melhor caso, 20×. **Paralelizar primeiro é
   pagar caro por um ganho menor, e travar o código numa forma difícil de otimizar
   depois.**
2. **Thread não paralelisa CPU em Python aqui.** O interpretador deste projeto é
   `Python 3.14.4` com `Py_GIL_DISABLED: 0` — GIL ligado. O tick é Python puro, sem
   espera de I/O. Duas threads de tick não rodam em paralelo; elas se revezam, e você
   paga o custo do revezamento. (Máquina tem 20 CPUs, e nenhuma delas ajudaria.)
3. **Não existe fronteira entre cidades para cortar.** Casamento, herança, mercado de
   trabalho e o Modo Mestre leem a lista global de NPCs e de locais. Cortar por cidade
   exige antes definir o que é interação intercidade — e isso é outro plano.

**A regra é:** faça `P01`–`P05`, meça com `V03`, e só se ainda não couber no orçamento de
1 s por tick (D4) abra a conversa sobre `ProcessPoolExecutor` com uma cidade por
processo. Com 750 NPCs (D1), a projeção diz que vai caber com folga de mais de 10×.

---

# Bloco G — Malha geometricamente válida

> Objetivo: nenhuma cidade emite polígono inválido, anel invertido ou quadra fora do muro.
> **Nada neste bloco depende dos outros blocos.** Faça primeiro: é a fundação, e é o que
> resolve o problema visual que você já está vendo.

### G01 · Perturbar o anel pelo VÃO, não pelo raio
**Arquivos:** `cartographer/cities/modelos/radial.py`, `config.json`

**Problema:** Seção 1.1. A amplitude da perturbação é `irreg × raios_base[j]`, que cresce
com a banda, enquanto o espaço disponível (o vão entre anéis) é constante. Razão medida
até 1,32 em Fenelburgo; 82,5% das cidades radiais com 6 anéis nascem com anel invertido.

**Ação:**

1. Em `config.json`, sob `cartografia`, troque a semântica da irregularidade de anel.
   Adicione:
   ```json
   "cidade_geo_anel_perturbacao_fracao_vao": 0.22,
   ```
   Mantenha `cidade_geo_irregularidade_via` — ela continua servindo à silhueta da grade
   e da muralha, que são outra conta.

2. Em `radial.py`, crie uma constante de módulo (é limite estrutural, não parâmetro de
   balanceamento — `11_ARQUITETURA.md` P3):
   ```python
   # Dois anéis vizinhos podem se mover um na direção do outro, então a soma das duas
   # amplitudes tem que caber no vão: cada uma < metade. 0.45 dá 10% de margem de
   # segurança contra a soma chegar a 1.0 (que é o anel invertido — Seção 1.1 do
   # docs/12_PLANO_CIDADE_VIVA.md).
   FRACAO_VAO_MAXIMA_SEGURA = 0.45
   ```

3. No `__init__`, guarde a fração já saturada:
   ```python
   fracao = cfg_get(config, "cidade_geo_anel_perturbacao_fracao_vao")
   self.anel_fracao_vao = min(fracao, FRACAO_VAO_MAXIMA_SEGURA)
   ```

4. Em `construir_malha`, troque o cálculo do raio de cada vértice por **deslocamento
   absoluto em metros**:
   ```python
   vao = self.raio_m / (self.num_aneis + 1)
   amplitude_m = vao * self.anel_fracao_vao
   ...
   r = raios_base[j] + amplitude_m * perturb[j, i]
   ```
   Faça o mesmo para a borda (`vertices[-1]`) e para o anel do núcleo, usando a mesma
   `amplitude_m`. **Não deixe nenhum vértice de anel sendo calculado por multiplicação
   do raio** — grepe por `irreg *` no arquivo e converta todos os que perturbam raio de
   anel.

5. Acrescente uma asserção logo depois de montar `vertices`, porque isto é um invariante,
   não uma preferência:
   ```python
   for i in range(self.num_setores):
       raios_do_setor = [math.hypot(*vertices[j][i]) for j in range(len(vertices))]
       assert all(b > a for a, b in zip(raios_do_setor, raios_do_setor[1:])), (
           f"{self.sitio.nome}: anéis cruzados no setor {i} — "
           f"cidade_geo_anel_perturbacao_fracao_vao alto demais")
   ```

**Validar:**
- `venv/bin/python builder/fix/audit_cidades.py` (de `V02`): coluna de anéis cruzados
  zerada nas 15 cidades.
- Novo teste em `tests/test_cidades.py`: gerar as 4 combinações
  (`radial`/`organica` × `medio`/`grande`) com 200 seeds e afirmar monotonia radial.

**Risco:** baixo. A conta fica mais simples, não mais complexa.

---

### G02 · `_encolher_quad` tem que rejeitar polígono auto-intersectante
**Arquivos:** `cartographer/cities/generate_city_geometry.py`

**Problema:** o inset de quadra só rejeita dois casos: área quase zero, e orientação
invertida em relação ao original. Um quadrilátero com vértice muito obtuso produz, depois
do recuo, uma gravata-borboleta que **mantém o sinal da área** e passa pelo filtro.
Medido: 7 quarteirões auto-intersectantes em Fenelburgo, 7 em Cidade das Flores, 3 em
Tordordor, 2 em Jordorstead.

**Ação:**

1. Acrescente dois helpers estáticos. Para um quadrilátero, só existem **dois pares de
   arestas não adjacentes** — então o teste é exato e custa quase nada:
   ```python
   @staticmethod
   def _segmentos_cruzam(a, b, c, d):
       """Interseção própria de dois segmentos, por teste de orientação. Colinearidade
       conta como não-cruzamento: o caso degenerado já é pego pelo piso de área."""
       def orientacao(p, q, r):
           v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
           return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
       o1, o2 = orientacao(a, b, c), orientacao(a, b, d)
       o3, o4 = orientacao(c, d, a), orientacao(c, d, b)
       return o1 != o2 and o3 != o4

   @classmethod
   def _e_quad_simples(cls, quad):
       """Um quadrilátero é simples se os dois pares de arestas OPOSTAS não se cruzam
       (0-2 e 1-3). Arestas adjacentes sempre se tocam no vértice — não são cruzamento."""
       return not (cls._segmentos_cruzam(quad[0], quad[1], quad[2], quad[3])
                   or cls._segmentos_cruzam(quad[1], quad[2], quad[3], quad[0]))
   ```

2. Em `_encolher_quad`, junto dos dois filtros que já existem:
   ```python
   if not self._e_quad_simples(novo):
       return None
   ```

3. Aplique o mesmo teste ao quad **de entrada**, no começo da função. Um quad de entrada
   já inválido (vindo de um modelo com bug) tem que morrer ali, não gerar lote:
   ```python
   if len(quad) != 4 or not self._e_quad_simples(quad):
       return None
   ```

**Validar:** `audit_cidades.py` com coluna de gravata-borboleta zerada, em quarteirão
**e** em lote. Teste novo afirmando que `_encolher_quad` devolve `None` para um quad
côncavo conhecido.

**Risco:** baixo. Pode reduzir a contagem de quadras em alguma cidade — isso é o filtro
funcionando, não regressão.

---

### G03 · A muralha é derivada do contorno real, não de um sorteio paralelo
**Arquivos:** `cartographer/cities/modelos/radial.py`,
`cartographer/cities/modelos/base.py`

**Problema:** Seção 1.3. Borda e muralha usam arrays de aleatórios diferentes; medido até
103 m de quadra para fora do muro.

**Ação:**

1. Em `base.py`, acrescente um utilitário de geometria pura (é trabalho compartilhado,
   não gancho — vai junto de `pontos_ao_longo_do_poligono`):
   ```python
   def envolver_poligono(poligono, folga):
       """Infla um polígono radialmente em torno do próprio centroide, garantindo
       que todo vértice original fique DENTRO do resultado com ao menos `folga` de
       sobra. Usado pela muralha: ela tem que envolver a cidade por construção, não
       por sorte (Seção 1.3 do docs/12_PLANO_CIDADE_VIVA.md)."""
       cx = sum(p[0] for p in poligono) / len(poligono)
       cy = sum(p[1] for p in poligono) / len(poligono)
       envolvido = []
       for x, y in poligono:
           dx, dy = x - cx, y - cy
           d = math.hypot(dx, dy) or 1.0
           envolvido.append((cx + dx * (d + folga) / d, cy + dy * (d + folga) / d))
       return envolvido
   ```

2. Em `radial.py`, monte o contorno a partir da **linha de borda que as quadras usam**,
   não de um raio novo:
   ```python
   contorno = envolver_poligono(borda, folga)
   ```
   Se quiser manter variação orgânica na muralha, ela só pode **somar** folga, nunca
   subtrair:
   ```python
   folgas = [folga * (1.0 + self.irreg * 0.3 * abs(perturb_muralha[i]))
             for i in range(self.num_setores)]
   ```
   (note o `abs`) — e nesse caso infle vértice por vértice com a folga daquele setor.

3. As torres continuam sendo colocadas com `pontos_ao_longo_do_poligono(contorno, ...)`,
   que já existe em `base.py`. Remova o cálculo de torre por ângulo uniforme sobre
   `raio_muralha`: ele desalinha a torre da muralha exatamente pelo mesmo motivo.

4. Faça o mesmo em `grade.py` — ele já monta um retângulo envolvente das quadras retidas,
   o que está **certo**. Use-o como referência do padrão.

**Validar:** teste novo, para todo modelo registrado com `precisa_muralha()` verdadeiro:
todo vértice de toda quadra está dentro do polígono `malha.contorno` (teste de
ponto-em-polígono por ray casting). `audit_cidades.py` com "pior invasão" = 0 m.

**Risco:** baixo.

---

### G04 · O modelo orgânico perturba a GRADE, não as ruas prontas
**Arquivos:** `cartographer/cities/modelos/radial.py`,
`cartographer/cities/modelos/organica.py`

**Problema:** Seção 1.2. `_torcer_radial` desloca a rua e deixa a quadra parada;
desalinhamento medido de 6,4 m (mediana) a 12,7 m em Fenelburgo.

**Ação:**

1. **Extraia a grade de vértices de `RadialModelo.construir_malha` para um método
   próprio.** Hoje ela nasce no meio de um método de ~100 linhas (que também está acima
   do limite de 40 linhas do `11_ARQUITETURA.md` Seção 4 — aproveite):
   ```python
   def _grade_de_vertices(self, angulos, raios_base, perturb):
       """Devolve `vertices[j][i]` — a grade que TANTO as ruas TANTO as quadras leem.
       Ponto de extensão para modelos que deformam a malha (organica): deforme AQUI,
       nunca a lista de ruas depois de pronta (Seção 1.2 do
       docs/12_PLANO_CIDADE_VIVA.md)."""
   ```
   O corpo é o código que já existe, com a correção de `G01`. `construir_malha` passa a
   chamá-lo.

2. Em `organica.py`, **apague `_torcer_radial`** e sobrescreva `_grade_de_vertices`:
   ```python
   def _grade_de_vertices(self, angulos, raios_base, perturb):
       vertices = super()._grade_de_vertices(angulos, raios_base, perturb)
       return self._torcer_grade(vertices, angulos)

   def _torcer_grade(self, vertices, angulos):
       """F7.1.4 — radial torta. Desloca o vértice TANGENCIALMENTE (perpendicular ao
       raio), por banda, com fase própria por setor. Como rua e quadra leem esta mesma
       grade, as duas tortam juntas e continuam coincidindo."""
   ```
   O deslocamento tangencial de `vertices[j][i]`: gire o ponto em torno do centro por um
   ângulo pequeno `delta[j][i]`, em vez de deslocá-lo em linha reta. Girar preserva o raio
   e portanto **não pode reintroduzir o cruzamento de anéis que `G01` acabou de
   eliminar** — deslocar em linha reta pode.

   Limite de amplitude angular: `delta` tem que ser menor que metade do passo angular
   entre setores, senão dois setores se cruzam. Mesmo raciocínio de `G01`:
   ```python
   PASSO_ANGULAR_FRACAO_MAXIMA = 0.35   # constante de módulo
   passo = 2 * math.pi / self.num_setores
   delta_max = passo * PASSO_ANGULAR_FRACAO_MAXIMA
   ```

3. **Remova `cidade_geo_organica_fracao_quadras_vazias` e o filtro que a usa.** A partir
   do Bloco T, "quadra vazia" deixa de ser um sorteio do modelo orgânico e passa a ser
   consequência da ocupação inicial (`T03`), que vale para todos os modelos. Manter os
   dois é ter duas fontes para a mesma coisa — e a do modelo orgânico apaga a quadra
   *inteira*, inclusive as ruas em volta, que ficam servindo terra de ninguém.

4. `_abrir_anel` pode ficar. Mas documente no docstring que ele muda **só a rua**, e que
   as quadras adjacentes ao arco aberto passam a não ter frente naquela aresta. Para
   fechar o buraco, ao abrir o arco entre os setores `i` e `i+gap`, troque a
   `classes_aresta` dessas quadras naquela aresta de `"anel"` para `"servico"` — recuo
   menor, sem fingir que existe via.

**Validar:** teste novo, para todo modelo: para toda quadra e toda aresta cuja
`classes_aresta` não seja `"servico"`, existe uma rua a menos de
`largura_da_classe / 2 + 0.5 m` daquela aresta. `audit_cidades.py` com desalinhamento
p95 abaixo de 1 m.

**Risco:** médio. É o refactor mais estrutural do bloco. Faça depois de `G01` e `G02`.

---

### G05 · Número de anéis vem da profundidade de quadra desejada, não de uma tabela
**Arquivos:** `cartographer/cities/modelos/radial.py`, `config.json`

**Problema:** `num_aneis` é sorteado de uma faixa por tamanho, e `raio_m` é sorteado
independentemente. O vão resultante varia de 82 m (Pelvermont) a 169 m (Fenelburgo) — o
dobro. Como o vão **é** a profundidade da quadra, isso é o que produz o
outlier de 209 lotes por quadra. Uma quadra tem que ter a profundidade de dois lotes
costa a costa mais a rua; nada mais.

**Ação:**

1. Nova chave em `config.json`:
   ```json
   "cidade_geo_vao_anel_alvo_m": 95,
   ```
   O valor sai da conta de `Q01`: profundidade de lote alvo (~20 m) × 2, mais a
   largura de via do anel (7 m) e os recuos (2 × 3 m) — dá ~53 m no núcleo denso e
   ~95 m na borda, onde o lote é mais fundo. Comece em 95 e calibre com `V02`.

2. Substitua o sorteio por cálculo, respeitando a faixa existente como **limite**, não
   como fonte:
   ```python
   faixa_aneis = cfg_get(config, "cidade_geo_num_aneis_faixa_por_tamanho").get(
       sitio.tamanho, [2, 2])
   vao_alvo = cfg_get(config, "cidade_geo_vao_anel_alvo_m")
   aneis_ideais = round(self.raio_m / vao_alvo) - 1
   self.num_aneis = max(int(faixa_aneis[0]), min(int(faixa_aneis[1]), aneis_ideais))
   ```

3. ⚠️ **Isto remove um `self.rng.randint` da sequência.** Todas as cidades mudam. É
   esperado (armadilha 1) — registre no commit, não compense.

**Validar:** `audit_cidades.py` mostrando vão entre 70 e 120 m em todas as 15 cidades.

**Risco:** baixo.

---

### G06 · Janela de terreno com margem, e índice que conhece a própria janela
**Arquivos:** `cartographer/cities/modelos/sitio.py`,
`cartographer/cities/modelos/radial.py`,
`cartographer/cities/generate_city_geometry.py`, `config.json`

**Problema:** armadilha 4. A janela de terreno cobre exatamente `2 × raio`, e
`_indice_terreno` usa `self.raio_m` como meia-largura com `np.clip`. Qualquer leitura
fora da cidade devolve a célula da borda, sem erro. O Bloco X depende de ler terreno
fora do muro.

**Ação:**

1. Nova chave em `config.json`:
   ```json
   "cidade_geo_janela_terreno_fator": 3.0,
   ```
   Fator sobre o raio: a janela cobre `2 × 3.0 × raio`, dando espaço para a cidade
   crescer até o triplo do raio original antes de ficar sem dado de terreno.

2. `SitioCidade` ganha **dois campos novos**: `raio_janela_m` (a meia-largura real da
   janela, em metros) e mantém `terreno`/`grad_x`/`grad_y`. Em `medir()`:
   ```python
   fator = cfg_get(config, "cidade_geo_janela_terreno_fator")
   raio_janela_m = raio_provisorio * fator
   lado_px = 2.0 * raio_janela_m / metros_por_px
   ```
   Aumente também a resolução da grade de 64 para 128, senão a célula triplica de
   tamanho e a declividade perde sentido. Custo: 4× a amostragem, uma vez por cidade,
   em tempo de build. Irrelevante.

3. **Os dois `_indice_terreno` que existem hoje** (um em `radial.py`, outro em
   `generate_city_geometry.py` — cópia literal) passam a usar `sitio.raio_janela_m`:
   ```python
   lado_m = 2.0 * self.sitio.raio_janela_m
   ```
   Enquanto você está aí: **essas duas cópias são o mesmo código.** Mova para um método
   de `SitioCidade` (`altitude_em(x_m, y_m)` e `declividade_em(x_m, y_m)`) e apague as
   duas. O sítio é o dono do terreno; nem o modelo nem o gerador precisam saber como a
   grade é indexada. Isso é `11_ARQUITETURA.md` P1.

4. Troque o `np.clip` por um retorno explícito de "fora da janela":
   ```python
   def declividade_em(self, x_m, y_m):
       """None quando o ponto cai FORA da janela amostrada — o chamador decide. Antes
       isto era np.clip, que devolvia silenciosamente a célula da borda e fazia toda
       checagem de terreno fora da cidade dar a mesma resposta (armadilha 4 do
       docs/12_PLANO_CIDADE_VIVA.md)."""
   ```
   Quem chamar trata `None` como "não sei, rejeite o lote" — nunca como 0.

**Validar:** teste novo afirmando que `sitio.declividade_em` devolve `None` para um ponto
a `4 × raio` do centro, e um valor diferente da borda para um ponto a `1,5 × raio`.

**Risco:** médio. Toca três arquivos e muda assinatura. Mas sem isto o Bloco X é cego.

---

# Bloco Q — Quadra perimetral, pátio e escala da cidade

> Objetivo: todo lote tem frente para uma rua, por construção geométrica — não por
> filtro estatístico depois. Depende do Bloco G inteiro.

### Q01 · Substituir a subdivisão recursiva por anel perimetral + pátio
**Arquivos:** `cartographer/cities/generate_city_geometry.py` (vira pacote — ver `Q02`),
`config.json`

**Problema:** Seção 1.4. `_subdividir_lote` corta a quadra ao meio recursivamente e não
conhece rua. Até 64% dos lotes sem frente; mediana de 94 lotes por quadra.

**Ação:**

Esta é a tarefa central do plano. Leia o algoritmo inteiro antes de começar.

**Entrada:** `quad_urbanizavel` — o quadrilátero da quadra **depois** do inset pela faixa
de domínio (o que `_gerar_quarteiroes_e_lotes` já produz hoje). Os 4 lados dele são,
por construção, os 4 lados que encaram rua.

**Passo 1 — decidir a profundidade do lote.** Por banda, do config:
```json
"cidade_geo_lote_profundidade_m_por_banda": {"0": 14, "1": 16, "2": 18, "_default": 22},
"cidade_geo_lote_frente_m_faixa_por_banda": {"0": [6, 9], "1": [7, 10], "2": [8, 12], "_default": [9, 14]},
```
Multiplique a profundidade por `modelo.lote_fator_cidade` (o fator por cidade que já
existe), para duas cidades do mesmo tamanho não ficarem idênticas.

**Passo 2 — recuar para dentro pela profundidade, obtendo o pátio.**
```python
quad_interno = self._encolher_quad(quad_urbanizavel, [profundidade] * 4)
```
Três casos, e cada um tem tratamento próprio:

- `quad_interno is None` **ou** área menor que `cidade_geo_patio_area_minima_m2`
  (proponho 120): a quadra é rasa. **Não há pátio.** Vá para o Passo 4 com
  `quad_interno = None`, e os lotes ocupam a quadra inteira, divididos só pela frente
  (uma fileira de lotes atravessando a quadra de lado a lado).
- área de `quad_interno` maior que `cidade_geo_patio_area_maxima_m2` (proponho 2.500):
  a quadra é funda demais, ia sobrar um vazio enorme no meio. **Corte a quadra em duas**
  pelo eixo mais longo, abra uma viela de serviço no corte (uma `Rua` com
  `classe_via="servico"`, `tipo_via="servico"`), e **recomece o Passo 1 para cada
  metade**. Limite a recursão a 2 níveis com um parâmetro `profundidade_corte`.
  ⚠️ A viela é uma rua de verdade: ela precisa entrar em `malha.ruas` para aparecer no
  mapa e para `G04` continuar valendo. Como `_gerar_quarteiroes_e_lotes` roda **depois**
  de `_emitir_ruas`, colete as vielas numa lista e emita ao final de
  `_gerar_quarteiroes_e_lotes`. Não reordene `gerar()`.
- caso normal: siga.

**Passo 3 — emitir o pátio.** Camada nova `"patio"`:
```python
self._add_feature("Polygon", quad_interno + [quad_interno[0]], "patio",
                  {"bairro": quadra.bairro, "quarteirao_id": quarteirao_id_str})
```
Acrescente `"patio": 400` em `cidade_geo_zoom_min_alvo_px_por_camada` (mesmo alvo do
edifício) e `'patio'` em `CAMADAS_INTERNAS_CIDADE` (`web/rotas/features.py`) e em
`CAMADAS_DETALHE_CIDADE` (`web/static/js/mapa_leaflet.js`). Se você esquecer qualquer um
dos três, o pátio existe no arquivo e não aparece na tela, sem erro nenhum.

**Passo 4 — dividir o anel entre `quad_urbanizavel` e `quad_interno` em 4 faixas.**

Aqui está a parte que costuma sair errada. O anel entre dois quadriláteros onde o de
dentro é o recuo do de fora se decompõe em **exatamente 4 trapézios que se encaixam sem
sobrepor**, cortando nas diagonais canto-externo → canto-interno:

```python
ext = quad_urbanizavel        # [v0, v1, v2, v3]
ins = quad_interno            # [w0, w1, w2, w3], mesmo índice = mesmo canto
faixa_k = [ext[k], ext[(k+1) % 4], ins[(k+1) % 4], ins[k]]
```

Isso funciona **porque** `_encolher_quad` produz o interno reinterceptando as arestas
deslocadas — canto `k` do interno é o canto `k` do externo. Se você trocar o algoritmo de
inset, essa correspondência é a coisa a preservar.

Quando não há pátio (`quad_interno is None`), a faixa vira a quadra inteira e só as
faixas 0 e 2 (ou 1 e 3, o par mais longo) são usadas, cada uma indo até o eixo médio da
quadra. Escolha o par pela aresta mais longa.

**Passo 5 — cortar cada faixa em lotes, pela frente.**
```python
comprimento = math.dist(ext[k], ext[(k+1) % 4])
frente_alvo = self.rng.uniform(*faixa_frente_da_banda)
n_lotes = max(1, round(comprimento / frente_alvo))
```
Divida a aresta externa **e** a interna pelo **mesmo parâmetro `t`**, de 0 a 1 em
`n_lotes` passos. O lote `m` é:
```python
t0, t1 = m / n_lotes, (m + 1) / n_lotes
lote = [lerp(ext[k], ext[k+1], t0), lerp(ext[k], ext[k+1], t1),
        lerp(ins[k+1], ins[k], 1 - t1), lerp(ins[k+1], ins[k], 1 - t0)]
```
Usar o mesmo `t` nas duas arestas é o que garante que os lotes **tilam** a faixa sem vão
e sem sobreposição. Interpolar por distância absoluta em vez de fração não tila, porque as
duas arestas têm comprimentos diferentes.

**Passo 6 — gravar a classe da frente e o id estável.** Cada lote sabe qual rua ele
encara: é `quadra.classes_aresta[k]`. Isso é dado de domínio, não decoração — a loja quer
frente para via principal, a casa não se importa. Grave em `props`:
```python
{"bairro": ..., "banda": ..., "quarteirao_id": ...,
 "id": f"{slug}_{quarteirao_id_str}_l{indice_no_anel:02d}",
 "classe_frente": quadra.classes_aresta[k],
 "area_m2": round(self._area_quad(lote), 1),
 "aresta": k}
```
`indice_no_anel` é um contador que **começa em 0 a cada quadra** e percorre as faixas na
ordem `k = 0,1,2,3` e os lotes na ordem de `t`. Determinístico e local — armadilha 3.

**Passo 7 — apagar o que sobrou.** Remova `_subdividir_lote`,
`cidade_geo_lote_area_base_m2`, `cidade_geo_lote_fator_por_banda` e
`cidade_geo_lote_profundidade_max`. Remova `_area_alvo_lote`. Não deixe morto: esse é o
tipo de função que alguém religa por engano seis meses depois.

**Validar:**
- Teste novo, o invariante central deste plano: **para todo lote de toda cidade, ao menos
  uma aresta do lote está contida (com tolerância de 0,1 m) numa aresta do quarteirão que
  o contém.** Se esse teste passa, é geometricamente impossível existir casa no miolo.
- `audit_cidades.py`: coluna "lotes a mais de 25 m de rua" em 0% nas 15 cidades; lotes por
  quadra entre 4 e 30 (mediana esperada ~12).
- Olho no mapa: `web/` em zoom alto numa cidade `organica` e numa `grade`.

**Risco:** alto. É a mudança de maior superfície. Faça em cima do Bloco G já pronto e
validado, nunca junto.

---

### Q02 · `generate_city_geometry.py` vira pacote
**Arquivos:** `cartographer/cities/generate_city_geometry.py` →
`cartographer/cities/geometria/`

**Problema:** o arquivo já tem **638 linhas**, contra o limite de 400 do
`11_ARQUITETURA.md` Seção 4. `Q01` acrescenta ~120 linhas. Ignorar o limite aqui é o começo
do próximo `DIAGNOSTICO`.

**Ação:** quebre por assunto, seguindo o padrão que `web/rotas/` já usa:

```
cartographer/cities/geometria/__init__.py      # reexporta GeradorCidade e
                                               # gerar_geometria_para_manifesto
cartographer/cities/geometria/gerador.py       # a classe GeradorCidade: gerar(), indice()
cartographer/cities/geometria/quad.py          # geometria pura de quadrilátero:
                                               # area, inset, simples, lerp, subdividir anel
cartographer/cities/geometria/lotes.py         # Q01: anel perimetral, pátio, viela
cartographer/cities/geometria/distribuicao.py  # F2/F3 + ocupação inicial (T03)
cartographer/cities/geometria/manifesto.py     # o laço sobre o manifesto, escrita, índice
```

`quad.py` é **funções de módulo, não métodos estáticos de classe** — são utilidades puras
e solitárias (`11_ARQUITETURA.md` Seção 7). Elas hoje são `@staticmethod` de `GeradorCidade`
só por acidente histórico.

Mantenha um shim de um arquivo para não quebrar quem importa o caminho antigo:
`cartographer/cities/generate_city_geometry.py` com `from .geometria import *` e um
comentário dizendo que é compatibilidade. `tests/test_cidades.py` e
`builder/populador.py` importam pelo caminho antigo.

**Validar:** `pytest tests/ -q` verde sem tocar em nenhum teste; `wc -l` de cada arquivo
novo abaixo de 400.

**Risco:** baixo, mas o diff é grande. Commit separado, feito **antes** de `Q01` se você
preferir (recomendo: faça `Q02` primeiro, aí `Q01` já nasce no lugar certo).

---

### Q03 · `grade` e `linear` também produzem quadra rasa
**Arquivos:** `cartographer/cities/modelos/grade.py`,
`cartographer/cities/modelos/linear.py`, `config.json`

**Problema:** `Q01` garante frente para todo lote em qualquer modelo, mas a **proporção**
continua ruim se a quadra for muito funda. Na grade, `cidade_geo_grade_lado_quadra_m_faixa`
é `[70, 140]` e o fator de clima seco multiplica por 1,3 — quadra de 182 m de lado, com
lote de 20 m de profundidade, deixa um pátio de 142 × 142 m. Vai cair sempre no caso
"pátio grande demais" de `Q01` e gerar viela.

**Ação:**

1. `grade.py`: aperte a faixa para `[55, 95]` e deixe o fator seco em 1,3 (dá até 124 m,
   ainda dentro do teto de pátio). Note que `n = 2 * ceil(raio / lado)` — quadra menor
   significa **mais quadras**, então confira o custo: a maior cidade sai de 206 para
   ~450 quadras. Aceitável; são features de arquivo, não objetos de simulação.
2. `linear.py`: `cidade_geo_linear_largura_quadra_m_faixa` é `[50, 90]` e serve de
   profundidade de fileira **e** de comprimento de célula. São duas coisas diferentes com
   uma chave só. Separe:
   ```json
   "cidade_geo_linear_comprimento_celula_m_faixa": [50, 90],
   "cidade_geo_linear_profundidade_fileira_m_faixa": [22, 34],
   ```
   Com isso a fileira já nasce com a profundidade de um lote e `Q01` cai direto no caso
   "sem pátio" — que é o certo para vila de beira de estrada. O ajuste manual de
   `max(p * fator, 25.0)` que existe hoje para consertar a razão comprimento/largura pode
   sair.

**Validar:** `audit_cidades.py` com lotes por quadra entre 4 e 30 nos três modelos, e
mediana de área de lote entre 120 e 320 m².

**Risco:** baixo.

---

### Q04 · Um float para a escala global das cidades
**Arquivos:** `cartographer/cities/escala.py`,
`cartographer/cities/modelos/sitio.py`, os 4 modelos, `config.json`

**Problema:** D5. Hoje, para experimentar cidades menores, você editaria
`cidade_geo_raio_m_faixa_por_tamanho` (3 pares de números) **e** lembraria que
`SitioCidade.medir()` lê a mesma chave para dimensionar a janela de terreno. Se os dois
divergirem, a janela não cobre a cidade e o terreno é lido errado — silenciosamente, por
causa do `np.clip`.

**Ação:**

1. Nova chave em `config.json`:
   ```json
   "cidade_geo_escala": 1.0,
   ```
2. Em `escala.py` (que é o dono das conversões de escala — `11_ARQUITETURA.md` P1), uma
   função única:
   ```python
   def faixa_raio_m(config, tamanho):
       """Faixa de raio da cidade, em metros, JÁ multiplicada pela escala global
       (`cidade_geo_escala`). É o único lugar que lê
       `cidade_geo_raio_m_faixa_por_tamanho` — tanto SitioCidade (que dimensiona a
       janela de terreno) quanto os 4 modelos (que sorteiam o raio) passam por aqui,
       senão os dois divergem e a janela deixa de cobrir a cidade."""
       faixa = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(
           tamanho, [500.0, 500.0])
       escala = cfg_get(config, "cidade_geo_escala")
       return [faixa[0] * escala, faixa[1] * escala]
   ```
3. Troque **as cinco** ocorrências de
   `cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(...)` por
   `faixa_raio_m(config, ...)`: `sitio.py`, `radial.py`, `grade.py`, `linear.py`
   (`organica` herda de `radial`). Grepe para não deixar nenhuma.
4. `cidade_geo_vao_anel_alvo_m` (de `G05`) **não** escala — a profundidade de quadra é
   física, não relativa. Uma cidade com escala 0,5 tem metade dos anéis, não anéis pela
   metade. Isso é o comportamento certo e vale um comentário no config.

**Validar:** rodar com `cidade_geo_escala: 0.5` e conferir em `audit_cidades.py` que o
raio caiu pela metade, o vão de anel ficou igual, e o número de anéis caiu. Nenhum
polígono inválido aparece.

**Risco:** baixo.

---

# Bloco T — Terreno livre como entidade de primeira classe

> Objetivo: o lote existe na simulação, tem estado, e a cidade nasce parcialmente
> construída. Depende do Bloco Q.

### T01 · Tabela `lotes` e repositório
**Arquivos:** `engine/schema.sql`, `engine/repositorios/lote.py` (novo),
`engine/repositorios/__init__.py`, `engine/database.py`

**Problema:** o lote hoje só existe como feature de GeoJSON, sem estado. A mecânica de
obra não tem onde perguntar "que terreno está livre nesta cidade".

**Ação:**

1. Em `engine/schema.sql`:
   ```sql
   -- Lotes urbanos (geometria vem do GeoJSON do cartógrafo; ESTADO vive aqui — ver
   -- armadilha 2 do docs/12_PLANO_CIDADE_VIVA.md: cartographer/ nunca escreve estado de
   -- simulação, engine/ nunca escreve GeoJSON).
   CREATE TABLE IF NOT EXISTS lotes (
       id TEXT PRIMARY KEY,
       cidade_id INTEGER,
       quarteirao_id TEXT,
       bairro TEXT,
       banda INTEGER,
       classe_frente TEXT,
       area_m2 REAL,
       coordenadas TEXT,               -- centroide em px de mundo, JSON [x, y]
       estado TEXT DEFAULT 'livre',    -- LoteEstado: livre | obra | ocupado
       local_id TEXT DEFAULT '',
       dono_npc_id TEXT DEFAULT '',
       FOREIGN KEY(cidade_id) REFERENCES cidades(id)
   );
   CREATE INDEX IF NOT EXISTS idx_lotes_cidade_estado ON lotes(cidade_id, estado);
   ```
   O índice não é otimização prematura: `O01` consulta por `(cidade_id, estado)` a cada
   casamento e a cada checagem de habitação.

2. Em `engine/models.py`, o enum e o dataclass. `estado` é texto de domínio, logo enum
   (`11_ARQUITETURA.md` P4), e guarda sempre o `.value` na coluna (mesma invariante de
   `Genero`/`EstagioVida` — R-C05):
   ```python
   class LoteEstado(Enum):
       LIVRE = "livre"
       OBRA = "obra"
       OCUPADO = "ocupado"

   @dataclass
   class Lote:
       id: str
       cidade_id: int
       quarteirao_id: str
       bairro: str
       banda: int
       classe_frente: str
       area_m2: float
       coordenadas: List[float] = field(default_factory=lambda: [0.0, 0.0])
       estado: str = LoteEstado.LIVRE.value
       local_id: str = ""
       dono_npc_id: str = ""
   ```

3. `engine/repositorios/lote.py`, no padrão dos outros repositórios do pacote:

   | Método | Para quê |
   |---|---|
   | `salvar_em_lote(lotes)` | importação inicial, com `executemany` numa transação |
   | `contar_por_estado(cidade_id)` | gatilho de auto-expansão (`X01`) e dashboard |
   | `reservar_livre(cidade_id, npc_id, perto_de=None, classe_frente=None)` | `O01`, ver abaixo |
   | `concluir(lote_id, local_id)` | `estado='ocupado'`, guarda o `local_id` |
   | `liberar(lote_id)` | volta para `livre` quando o edifício vira ruína (`decay.py`) |
   | `alterados_por_cidade(cidade_id)` | `T05`, o delta que o mapa consome |

4. `reservar_livre` tem que ser **uma sentença condicional**, não um `SELECT` seguido de
   `UPDATE`. O pool tem 5 conexões e o dashboard escreve no mesmo banco; dois pedidos
   simultâneos com leitura-depois-escrita entregam o mesmo lote para dois casais:
   ```sql
   UPDATE lotes SET estado = 'obra', dono_npc_id = ?
    WHERE id = (SELECT id FROM lotes
                 WHERE cidade_id = ? AND estado = 'livre'
                 ORDER BY <critério> LIMIT 1)
      AND estado = 'livre'
   ```
   Devolva `None` quando `rowcount == 0` (não havia lote livre) — é o sinal que dispara a
   auto-expansão do Bloco X. **Não levante exceção:** ficar sem terreno é estado normal
   da cidade, não erro (`11_ARQUITETURA.md` P5 fala de falhar alto em *config ausente*, não
   em estado de jogo esperado).

5. Registre em `engine/repositorios/__init__.py` e em `DatabaseManager.__init__`
   (`self.lotes = RepositorioLote(self)`). **Não** acrescente nada a
   `COLUNAS_ESPERADAS` — essa lista existe para consertar bancos antigos (R-E03), e
   `lotes` é tabela nova num mundo que vai ser resetado (D6).

**Validar:** teste novo em `tests/test_mecanicas.py`: duas chamadas de
`reservar_livre` na mesma cidade com um único lote livre devolvem um id e `None`, nunca o
mesmo id duas vezes.

**Risco:** baixo.

---

### T02 · Importar lotes junto com os edifícios
**Arquivos:** `builder/populador.py`

**Problema:** `_importar_locais_da_geometria` lê só as features de camada `edificio`. Os
lotes vão para o lixo.

**Ação:**

1. Na mesma passada sobre as features, colete `camada == "lote"` numa lista de `Lote`.
   O centroide é o do anel externo, mesma conversão `[lng, lat] → [x_mundo, -lat]` que o
   edifício já faz. **Extraia essa conversão para uma função** em vez de copiá-la: ela
   já aparece duas vezes no arquivo hoje.
2. `estado` inicial: `'ocupado'` se existir uma feature `edificio` com o mesmo id (o
   edifício **é** o lote depois de `Q01`/armadilha 3), senão `'livre'`. Como o id é o
   mesmo, isso é um `set` de ids de edifício, não uma busca geométrica.
3. `local_id` = o próprio id quando ocupado.
4. Grave com `salvar_em_lote` — **uma transação para a cidade toda.** Hoje
   `_importar_locais_da_geometria` chama `db.locais.salvar(loc)` por edifício, e
   `DatabaseManager.connection()` faz `commit` na saída de cada `with`. São 24.423
   commits num reset. Passe a importação de locais para `executemany` também, no mesmo
   commit — é praticamente o mesmo trabalho e corta o tempo de reset em uma ordem de
   grandeza.
5. **Adote o id do lote como id do `Local`.** Em `Q01` o edifício já nasce com o id do
   lote; aqui é só não inventar outro.

**Validar:** depois de um reset completo,
`SELECT estado, count(*) FROM lotes GROUP BY estado` bate com a fração de `T03`, e
`SELECT count(*) FROM lotes WHERE estado='ocupado' AND local_id NOT IN (SELECT id FROM locais)`
devolve 0.

**Risco:** baixo.

---

### T03 · Ocupação inicial parcial, espacialmente coerente
**Arquivos:** `cartographer/cities/geometria/distribuicao.py`, `config.json`

**Problema:** Seção 1.5 e D2. Hoje **todo** lote sem marco e sem comércio de bairro vira
Residência — `_emitir_edificios` não tem noção de orçamento.

**Ação:**

1. Nova chave:
   ```json
   "cidade_geo_ocupacao_inicial_por_tamanho": {"pequeno": 0.25, "medio": 0.40, "grande": 0.60},
   ```

2. Ordem de prioridade — **marco nunca perde lugar para o orçamento**:
   1. Marcos do catálogo (castelo, mercado, prefeitura): sempre construídos. Uma capital
      sem castelo não é uma capital meio construída, é uma capital errada.
   2. Comércio de bairro: a quantidade de hoje **escalada pela fração**.
   3. Residências: preenchem até o orçamento total.
   4. O resto fica lote livre.

3. ⚠️ **Não sorteie os lotes residenciais uniformemente.** `rng.sample` sobre a lista
   global de lotes produz sal e pimenta: casa, vazio, casa, vazio, pela cidade inteira.
   Cidade real cresce do centro para fora e por quarteirão inteiro. Use probabilidade
   composta:
   ```python
   # peso por zona: o centro adensa primeiro
   PESO_ZONA = {"nucleo": 1.6, "centro": 1.3, "meio": 1.0, "borda": 0.55}
   # um ruído por QUADRA (não por lote) — é o que cria bolsão cheio e bolsão vazio
   ruido_quadra = self.rng.uniform(-0.25, 0.25)
   p = fracao_alvo * PESO_ZONA[zona] * (1.0 + ruido_quadra)
   ```
   Depois **normalize**: some as probabilidades, compare com o orçamento alvo, e escale
   todas por um fator único para a contagem final bater. Sem a normalização, a fração
   efetiva vira função dos pesos e você perde o controle do float que D2 pediu.

4. O lote não construído continua sendo emitido como feature `lote` com
   `"estado": "livre"` nas properties. **É o estado inicial gravado na geometria**, e a
   partir daí o banco é a verdade (armadilha 2).

5. Passe a **não emitir** a feature `edificio` para lote livre — hoje o gerador emite um
   footprint para todo lote. Mantenha o `_footprint_edificio` para quem é construído.

**Validar:**
- Contagem por cidade em `audit_cidades.py`: edifícios / lotes dentro de 3 pontos
  percentuais da fração configurada, nas 15 cidades.
- Olho no mapa: vazios em bolsões, não em xadrez.
- `SELECT count(*) FROM locais` depois do reset cai de 24.423 para algo em torno de
  10.000. O Bloco P cuida do resto.

**Risco:** médio. É a tarefa que mais muda a aparência do mundo.

---

### T04 · Ruína devolve o terreno
**Arquivos:** `engine/mechanics/decay.py`

**Problema:** `InfrastructureManager` já leva o edifício a `EstadoInfraestrutura.RUINA`.
Hoje isso não libera nada — o terreno fica travado para sempre num edifício morto.

**Ação:** quando um local chega a `RUINA` e é desativado, chame
`db.lotes.liberar(local.id)` (o id do local **é** o id do lote). Mantenha o `Local` com
`status=0` para a narrativa ("as ruínas da antiga forja"), mas o lote volta para `livre`
e pode receber obra nova.

⚠️ Cuidado com a ordem: se alguém já reservou aquele lote, `liberar` não pode atropelar.
Faça `liberar` condicional: `WHERE id = ? AND estado = 'ocupado'`.

**Validar:** teste em `tests/test_mecanicas.py` levando um local a integridade 0 e
afirmando que o lote voltou para `livre`.

**Risco:** baixo.

---

### T05 · O mapa precisa ver o terreno livre, e ver quando ele deixa de ser livre
**Arquivos:** `web/static/js/mapa_leaflet.js`, `web/rotas/features.py`,
`web/rotas/cidade.py` (novo), `web/cache_mapa.py`

**Problema:** duas coisas.

Primeiro, estilo: o lote hoje tem estilo único (`lote: { color: '#6a5acd', ... }`). Lote
livre e lote ocupado precisam se distinguir, senão a cidade parece igual à de antes.

Segundo, e mais sério: o GeoJSON guarda o estado **inicial**. A camada vetorial do mapa lê
arquivo, e o arquivo não muda. **Uma casa construída durante a simulação nunca apareceria
no mapa.** Um executor desatento resolve isso reescrevendo o GeoJSON da engine — que é
exatamente a armadilha 2.

**Ação:**

1. Estilo por estado, em `mapa_leaflet.js`. Lote livre: contorno tracejado, preenchimento
   terroso, sem ícone. Pátio: preenchimento verde translúcido, contorno nenhum. Lote
   ocupado: como hoje.
2. Rota nova `web/rotas/cidade.py`:
   `GET /api/cidade/<cidade_id>/lotes_alterados` → `[{"id": ..., "estado": ..., "local_id": ...}]`,
   lendo `db.lotes.alterados_por_cidade`. "Alterado" = estado diferente do que a geometria
   gravou. Guarde essa diferença numa coluna `estado_inicial` do lote, gravada na
   importação (`T02`) — é mais barato e mais claro que reabrir o GeoJSON para comparar.
3. O frontend busca os alterados junto com as features (mesmo `bbox`, mesmo zoom) e aplica
   o estilo em cima. Um `Map` de `id → estado` e um `setStyle` por feature afetada.
4. Edifício construído em jogo **não tem polígono no GeoJSON.** Duas opções, e a segunda
   é a certa:
   - ❌ gerar o footprint na engine e mandar como GeoJSON pela rota: põe geometria na
     engine.
   - ✅ o gerador **já emite o footprint de todo lote**, inclusive dos livres, numa
     camada nova `footprint_potencial` com `zoom_min` igual ao do edifício, e o frontend
     só desenha o footprint cujo lote está ocupado. A geometria continua toda do
     cartógrafo; a engine só diz "este lote está ocupado". Custo: ~40% mais features de
     polígono no arquivo, que o `bbox` + `zoom_min` do índice já filtram.

**Validar:** construir uma casa no jogo (ou forçar um `UPDATE lotes SET estado='ocupado'`)
e recarregar o mapa: o lote muda de aparência sem regenerar GeoJSON nenhum.

**Risco:** médio. A parte 4 é uma decisão de arquitetura — se você se pegar escrevendo
`json.dump` de geometria dentro de `engine/`, pare.

---

# Bloco O — Obra: quem constrói o quê, e quando

> Objetivo: a cidade se preenche por necessidade. Depende do Bloco T.

### O01 · A obra do casal ocupa um lote livre de verdade
**Arquivos:** `engine/mechanics/housing.py`, `engine/mechanics/marriage.py`

**Problema:** Seção 1.5. `iniciar_obra_para_casal` sorteia um ponto em terra firme num
raio ao redor da cidade — pode cair fora do muro, dentro de outro edifício, ou no meio de
uma rua.

**Ação:**

1. Substitua o sorteio de ponto por reserva de lote:
   ```python
   lote_id = self._mundo.db.lotes.reservar_livre(
       cidade_id=n1.cidade_id, npc_id=n1.id, perto_de=casa_atual.coordenadas)
   if lote_id is None:
       self._pedir_expansao(n1.cidade_id)   # X01
       return False
   ```

2. Critério de escolha (`ORDER BY` do `reservar_livre`): **lote livre mais próximo da
   casa atual do casal**, com desempate pela banda mais externa. Casal jovem não compra
   terreno no centro. SQLite não tem função de distância — grave `coordenadas` como duas
   colunas reais `x` e `y` em vez de JSON, e ordene por
   `((x - ?) * (x - ?) + (y - ?) * (y - ?))`. Distância ao quadrado basta para ordenar,
   e evita `sqrt`.
   > Ajuste `T01` para ter `x REAL, y REAL` em vez de `coordenadas TEXT` se você chegar
   > aqui antes de implementar `T01`. Se já implementou, é um `ALTER TABLE` num mundo que
   > vai ser resetado — barato.

3. O `Local` da obra nasce com `id = lote_id` e `coordenadas` = as do lote. Apague o
   `nova_obra_id = f"casa_obra_{int(time.time())}_{random.randint(0, 999)}"`: id baseado
   em relógio não é reproduzível, e duas obras no mesmo segundo com o mesmo
   `randint` colidem.

4. Em `actions.py`, no trecho que conclui a obra (`obra.integridade >= 100`), chame
   `db.lotes.concluir(obra.id, obra.id)`.

5. `marriage.py` também inicia obra para recém-casados — confira que ele passa pelo mesmo
   `iniciar_obra_para_casal` e não tem cópia da lógica de coordenada.

**Validar:** teste com um mundo sintético de 2 lotes livres e 3 casais: dois casais
conseguem obra, o terceiro recebe `False` e dispara o pedido de expansão. Nenhuma obra
com coordenada fora do conjunto de lotes.

**Risco:** médio.

---

### O02 · Comércio nasce por demanda, não por tabela
**Arquivos:** `engine/mechanics/urbanismo.py` (novo), `engine/loop.py`, `config.json`

**Problema:** o comércio de bairro é decidido **uma vez**, na geração da cidade, por uma
tabela de `um_a_cada_n_lotes`. A cidade que dobra de população continua com a mesma
padaria. E a partir de `T03` a cidade nasce com menos comércio do que precisa, de
propósito.

**Ação:**

1. Novo gerenciador `GerenciadorUrbanismo`, classe de instância recebendo
   `EstadoDoMundo` e `config` (R-F01, como todos os outros). Ele roda **uma vez por dia
   simulado, por cidade ativa** — acrescente o gatilho em
   `GameLoop._executar_rotinas_agendadas`, junto de `habitacao_hora`.

2. A conta de demanda, por cidade e por categoria de local:
   ```json
   "urbanismo_habitantes_por_estabelecimento": {
     "taverna": 40, "mercado": 35, "forja": 45, "universidade": 150, "quartel": 120
   },
   ```
   ```
   deficit(categoria) = floor(habitantes / habitantes_por_estabelecimento) - ativos(categoria)
   ```

3. **No máximo um estabelecimento por cidade por dia**, sempre o de maior déficit. Sem
   esse teto, uma cidade que cresce rápido dispara 20 obras num dia e o mercado de
   trabalho fica sem gente.

4. **Quem paga.** Não há tesouro no projeto (`KingdomManager` só paga pensão e sopão, não
   tem saldo). Use um empreendedor: o NPC adulto vivo da cidade com mais
   `dinheiro_total_pc`, acima de `urbanismo_custo_estabelecimento_pc`. Desconte o custo,
   reserve um lote (preferindo `classe_frente` em `("principal", "anel")` — loja quer
   movimento), crie o `Local` com `dono_npc_id` do empreendedor. Se ninguém tem dinheiro,
   a cidade simplesmente não cresce naquele dia. Isso é uma regra econômica real, de
   graça.

5. O estabelecimento novo nasce como **obra** (`status=0`, `integridade=0`), igual à casa.
   O mesmo `Acao.CONSTRUIR` que já existe termina o serviço. Não invente um segundo
   caminho de construção.

**Validar:** teste com um mundo sintético de 100 habitantes, 1 taverna e um NPC rico:
depois de uma chamada, existe exatamente uma obra nova de categoria `mercado` ou
`forja` (a de maior déficit), e o NPC rico ficou mais pobre.

**Risco:** médio. É lógica de jogo nova; vai precisar de calibragem.

---

### O03 · `urbanismo.py` é o único dono da decisão "construir o quê"
**Arquivos:** `engine/mechanics/urbanismo.py`, `engine/mechanics/housing.py`

**Problema (preventivo):** depois de `O01` e `O02` existem duas mecânicas criando
edifício: habitação (casa) e urbanismo (comércio). É o começo clássico de duas cópias da
regra de "achar lugar, criar local, marcar obra".

**Ação:** extraia para `urbanismo.py` o método compartilhado:
```python
def abrir_obra(self, cidade_id, dono_npc, categoria, tipo_local, nome, preferir_frente=None):
    """Reserva lote, cria o Local em obra e devolve ele — ou None se não houver
    terreno. É o ÚNICO caminho para um edifício novo nascer durante a simulação:
    habitação (casa de casal) e urbanismo (comércio por demanda) chamam este método,
    nenhum dos dois duplica a sequência reservar/criar/marcar."""
```
`housing.iniciar_obra_para_casal` passa a ser: escolher o casal, montar o nome, chamar
`abrir_obra`. Ele continua dono da **política** ("qual casal, quando"); `urbanismo` é dono
da **mecânica** ("como um edifício nasce").

**Validar:** grepe por `status=0` e por `integridade=0` fora de `urbanismo.py` — só deve
sobrar em `decay.py` (que lida com o fim, não com o começo).

**Risco:** baixo.

---

# Bloco X — Auto-expansão da cidade

> Objetivo: a cidade cria espaço novo quando precisa, sem nada pré-mapeado à mão.
> Depende dos Blocos G, Q, T e O.

### X01 · O gatilho: a cidade pede espaço
**Arquivos:** `engine/mechanics/urbanismo.py`, `config.json`

**Ação:**

1. Duas chaves de gatilho, e o `or` entre elas importa:
   ```json
   "urbanismo_lotes_livres_minimo": 8,
   "urbanismo_fracao_livre_minima": 0.03,
   ```
   A absoluta protege a vila pequena (3% de 40 lotes é 1); a fracionária protege a
   capital (8 lotes livres em 3.000 é saturação).

2. `GerenciadorUrbanismo.avaliar_expansao(cidade_id)`, na mesma varredura diária de
   `O02`: se `contar_por_estado` diz que os livres caíram abaixo do gatilho, chame a
   expansão. **No máximo um arrabalde por cidade por dia**, e registre um `Evento`
   (`TipoEvento` novo, `EXPANSAO_URBANA`) para o Modo Mestre poder narrar.

3. `abrir_obra` devolvendo `None` **também** dispara a avaliação, imediatamente — é o
   caso da cidade que saturou entre duas varreduras diárias.

**Risco:** baixo.

---

### X02 · A geometria do arrabalde: função pura no cartógrafo
**Arquivos:** `cartographer/cities/expansao.py` (novo), `config.json`

**Problema:** a expansão é geometria (camada `cartographer/`), mas o gatilho é simulação
(camada `engine/`). A camada de cima pode chamar a de baixo; o contrário, nunca
(armadilha 2).

**Ação:**

Uma função pura, sem estado, sem banco, sem NPC:

```python
def gerar_arrabalde(sitio, geojson_atual, lotes_alvo, seed_expansao):
    """Gera as features de um arrabalde NOVO, fora da muralha, dimensionado para caber
    ao menos `lotes_alvo` lotes. Devolve (features_novas, lotes_novos_meta).

    Função pura: não abre banco, não escreve arquivo, não sabe o que é um NPC. Quem
    decide QUANDO chamar é engine/mechanics/urbanismo.py; quem decide COMO fica a
    geometria é aqui (armadilha 2 do docs/12_PLANO_CIDADE_VIVA.md).
    """
```

Algoritmo, passo a passo:

1. **Ler o estado atual do arquivo:** o polígono `muralha` (ou o envelope dos
   quarteirões, se a cidade não tem muro), os pontos `portao`, e as ruas com
   `tipo_via` em `("radial", "eixo")`.

2. **Escolher a direção.** Para cada portão, a direção de saída é do centro para o
   portão. Pontue cada candidata e escolha a melhor:
   - declividade média ao longo do eixo de saída, via
     `sitio.declividade_em` (`G06` — é aqui que aquela tarefa se paga);
   - `None` de `declividade_em` (fora da janela de terreno) **desclassifica** a direção;
   - penalize a direção que aponta para a água (`sitio.direcao_agua_rad` e
     `distancia_agua_m` já existem em `SitioCidade`);
   - penalize direção já usada por arrabalde anterior, para a cidade crescer em leque e
     não numa língua só. "Já usada" sai da contagem de arrabaldes por setor, que você lê
     do próprio GeoJSON (`props.arrabalde`).

3. **Estender a via de saída.** Continue a rua radial daquele portão por
   `urbanismo_arrabalde_comprimento_m` (proponho 180) além da muralha, mantendo a
   `classe_via` dela. Essa via é a espinha do arrabalde.

4. **Duas fileiras de quadras flanqueando a via**, uma de cada lado, com profundidade de
   uma quadra (`cidade_geo_vao_anel_alvo_m` de `G05`) e largura cortada a cada
   ~`lado_quadra` ao longo da via. Emita `Rua` transversal em cada corte. É exatamente a
   estrutura do `LinearModelo` — **reuse a ideia, e se der, o código**: se você extrair de
   `linear.py` a função "dada uma polilinha de eixo, produza fileiras de quadras dos dois
   lados", ela serve aos dois. Coloque-a em `base.py` junto de
   `pontos_ao_longo_do_poligono`.

5. **Marcar as quadras novas.** `banda` = a banda máxima da cidade + 1 (é a borda da
   borda), `bairro` = `f"Arrabalde {n}"`, `id` = `("arr", n, k)`. Todas as properties
   ganham `"arrabalde": n`.

6. **Repetir se não couber.** Se as duas fileiras não chegam a `lotes_alvo`, estenda a
   espinha e acrescente mais cortes, até um teto de
   `urbanismo_arrabalde_comprimento_max_m`. Se ainda não couber, devolva o que conseguiu —
   `X01` vai chamar de novo amanhã.

7. **Não gere muralha nova.** É arrabalde: casa fora do muro é justamente o sinal visual
   de que a cidade transbordou. Se um dia você quiser um muro novo englobando os
   arrabaldes, é outra tarefa, e `envolver_poligono` de `G03` já está lá.

8. **Emissão dos lotes.** Chame o **mesmo** código de `Q01` (`geometria/lotes.py`). O
   arrabalde não pode ter uma segunda implementação de subdivisão de quadra, senão as duas
   divergem. Isso é o motivo de `Q02` (pacote) existir: `expansao.py` importa
   `geometria.lotes`, não copia.

9. **Ocupação inicial do arrabalde: zero.** Tudo nasce livre. A expansão cria espaço; é a
   simulação que o preenche.

**Validar:** teste chamando `gerar_arrabalde` com um GeoJSON de cidade pequena e
`lotes_alvo=20`: as features novas não intersectam nenhum quarteirão existente (teste de
bbox mais teste de polígono), todo lote novo tem frente para rua (o invariante de `Q01`),
e chamar duas vezes com a mesma `seed_expansao` dá o mesmo resultado.

**Risco:** alto. É a tarefa mais nova do plano. Faça por último.

---

### X03 · Persistir o arrabalde: acrescentar ao GeoJSON e ao banco
**Arquivos:** `engine/mechanics/urbanismo.py`, `engine/repositorios/lote.py`,
`web/cache_mapa.py`

**Problema:** a função de `X02` é pura, então alguém tem que gravar. E é a única vez em
que a engine toca o arquivo do cartógrafo.

**Ação:**

1. Um serviço fino em `urbanismo.py`:
   ```python
   def _aplicar_arrabalde(self, cidade):
       """Única escrita da engine num arquivo do cartógrafo, e ela é ACRESCENTAR
       features geradas por cartographer/cities/expansao.py — nunca editar feature
       existente, nunca gravar estado de simulação no arquivo (armadilha 2)."""
   ```
   Sequência: ler o `.geojson`, chamar `gerar_arrabalde`, **estender** a lista de
   features, escrever em arquivo temporário e `os.replace` (atômico — o dashboard lê esse
   arquivo a qualquer momento), inserir os lotes novos com `salvar_em_lote`, atualizar a
   entrada da cidade em `_indice.json` (bbox e contagem por camada).

2. `seed_expansao` tem que ser reproduzível: `sitio.seed ^ (0xA53F * numero_do_arrabalde)`.
   Nunca `time.time()`, nunca `random` sem seed.

3. **Confira a invalidação do cache.** `web/cache_mapa.py` cacheia por `mtime`, e
   `os.replace` muda o `mtime` — então funciona. Mas `carregar_indice_cidades` também
   cacheia, e se o índice não for reescrito, o bbox antigo da cidade corta o arrabalde
   fora do retorno da API. Reescreva o índice sempre, e verifique no navegador.

4. O `_indice.json` ganha uma chave `arrabaldes: n` por cidade. É o que `X02` lê para
   saber quantos já existem, sem varrer as features.

**Validar:** forçar saturação num mundo de teste (um `UPDATE lotes SET estado='ocupado'`),
rodar um dia simulado, e ver o arrabalde aparecer no mapa sem reiniciar o dashboard.

**Risco:** alto.

---

# Bloco P — Performance e simulação multi-cidade

> Objetivo: 750 NPCs em 15 cidades dentro de 1 s por tick (D1, D4). **Faça este bloco
> antes de ligar as outras 14 cidades**, senão você vai depurar lentidão e lógica ao
> mesmo tempo. Releia a armadilha 5.

### P01 · Índice de locais por cidade e por papel
**Arquivos:** `engine/indice_locais.py` (novo), `engine/mundo.py`, `engine/core.py`

**Problema:** Seção 1.6. `mover_para_social`, `mover_para_restaurante` e
`mover_aleatoriamente` varrem os 24.423 locais **por NPC, por tick**. Medido: 20 NPCs
custam 53,8 ms com 24 mil locais e 2,9 ms com mil.

**Ação:**

1. Nova classe `IndiceDeLocais`, na camada de modelo (é vocabulário e estrutura, não
   regra de simulação). Construída uma vez, a partir do mesmo dicionário que
   `EstadoDoMundo.locais` já tem:
   ```python
   class IndiceDeLocais:
       """Índices de leitura sobre os locais, por cidade e por papel. Existe porque
       cada consulta de movimento varria a lista inteira de locais, por NPC, por tick —
       o que fazia o custo do tick ser NPCs × locais (Seção 1.6 do
       docs/12_PLANO_CIDADE_VIVA.md: 53,8 ms com 20 NPCs e 24 mil locais, contra 2,9 ms
       com mil locais).

       Quem muda um local (criar, desativar, concluir obra) é obrigado a avisar o
       índice — por isso `registrar` e `remover` são públicos e `EstadoDoMundo` expõe
       o índice, não os dicionários crus."""
   ```

2. Índices a manter (todos `dict[cidade_id, list[local_id]]`):
   `sociais`, `comida`, `passeio`, `residencias_ativas`, `trabalho_por_categoria`.
   Mais dois globais: `obra_por_dono: dict[npc_id, str]` e `por_id`.

3. Calcule os predicados **uma vez, na inserção**, não a cada consulta.
   `LocationUtils.is_local_publico` hoje chama `carregar_config_global()` **dentro do
   laço** — a lista de palavras-chave é reconstruída 24 mil vezes por NPC por tick.
   No índice, o predicado roda uma vez por local, na carga.

4. `EstadoDoMundo` ganha o campo `indice: IndiceDeLocais`. **Mantenha `locais` também**,
   por enquanto: metade do código usa `mundo.locais[x]`, e trocar tudo num commit é
   diff demais. O índice é a fonte para **consulta por conjunto**; `locais` continua
   sendo o acesso por id.

**Validar:** `bench_tick.py` (`V03`) com 20 NPCs e 24 mil locais abaixo de 5 ms
(hoje: 53,8 ms).

**Risco:** médio. O risco real é índice desatualizado — cubra com `P02`.

---

### P02 · Todo caminho de mudança de local passa pelo índice
**Arquivos:** `engine/mechanics/urbanismo.py`, `engine/mechanics/housing.py`,
`engine/mechanics/decay.py`, `engine/mechanics/mestre/acoes/*.py`

**Problema (preventivo):** um índice que alguém esquece de atualizar é pior que nenhum
índice — o bug é intermitente e invisível. Hoje existem **quatro** lugares que inserem ou
desativam local: `housing`, `urbanismo` (novo), `decay`, e as ações do Modo Mestre
(`criar_local.py`, `destruir_local.py`).

**Ação:**

1. Faça `EstadoDoMundo` o único caminho:
   ```python
   def registrar_local(self, local): ...   # grava no dict, no índice e no banco
   def desativar_local(self, local_id): ...
   ```
2. Troque nos quatro lugares. Grepe por `self._mundo.locais[` do lado esquerdo de um `=`
   e por `db.locais.salvar(` fora de `EstadoDoMundo` — não deve sobrar nenhum em
   `mechanics/`.
3. `NPCUtils.obter_obra_do_npc` (a varredura mais caro do profiler) vira
   `mundo.indice.obra_por_dono.get(npc.id)`. Mantenha a assinatura antiga como
   deprecada por um commit, ou troque as 3 chamadas de uma vez — são poucas
   (`housing.py`, `actions.py`, `utilidade/construir.py`).

**Validar:** teste que cria local via `registrar_local`, consulta pelo índice, desativa e
confirma que saiu do índice. `bench_tick.py` sem regressão.

**Risco:** médio.

---

### P03 · Agrupamentos por tick, calculados uma vez
**Arquivos:** `engine/loop.py`, `engine/consultas_npc.py`

**Problema:** `NPCUtils.contar_dependentes_na_casa` é chamada por NPC, por tick, e varre
a lista de NPCs por dentro. É O(NPCs²). Com 750 NPCs são 562 mil comparações por tick,
para produzir um número que uma única passada resolveria.

**Ação:**

1. No começo de `executar_tick`, monte uma vez:
   ```python
   npcs_por_casa = NPCUtils.agrupar_por_casa(self._mundo.npcs)
   ```
2. Passe esse dicionário para quem precisa. **Não** guarde como atributo do `GameLoop`
   entre ticks: ele fica velho, e um cache velho de parentesco é um bug de família
   inteira. Ou é parâmetro, ou é recalculado.
3. `contar_dependentes_na_casa` ganha uma sobrecarga que recebe os moradores já
   agrupados. Marque a antiga como "só para teste/uso pontual" no docstring.
4. Mesma coisa para `obter_casas_vazias`, que é O(locais × NPCs): ela virou consulta ao
   índice (`residencias_ativas` da cidade) cruzada com `npcs_por_casa`.

**Validar:** `bench_tick.py` com 750 NPCs: a curva tem que ser linear em NPCs, não
quadrática. Compare 375 e 750 — o tempo tem que dobrar, não quadruplicar.

**Risco:** baixo.

---

### P04 · NPC não atravessa o mundo para ir à taverna
**Arquivos:** `engine/mechanics/movement.py`

**Problema:** `movement.py` não filtra por cidade em nenhum lugar. Um pixel de mundo são
**15,81 km** (`escala.py`) — hoje um NPC pode ir socializar numa taverna a centenas de
quilômetros, instantaneamente. Com uma cidade viva isso não aparecia. Com 15, é a primeira
coisa que você vai ver no dashboard.

**Ação:**

1. Toda consulta de destino passa a ser `mundo.indice.<papel>(npc.cidade_id)`. É o mesmo
   commit que `P01` torna possível, e é simultaneamente **correção de bug e o maior ganho
   de constante do bloco**: a lista cai de 24 mil para algumas centenas.
2. O fallback de `mover_para` ("garante que a casa existe, senão a primeira casa ativa")
   pega `casas_disponiveis[0]` da lista global — pode mudar o NPC de cidade
   silenciosamente. Restrinja à cidade dele, e se não houver nenhuma, **logue warning** e
   deixe o NPC onde está. Mover alguém de cidade é decisão de migração, não de fallback.

**Validar:** teste com dois NPCs em cidades diferentes e locais sociais nas duas:
`mover_para_social` nunca coloca um NPC num local de `cidade_id` diferente do dele.
Asserção nova em `test_mecanicas.py`.

**Risco:** baixo. Alto valor.

---

### P05 · Uma transação por tick, não uma por NPC
**Arquivos:** `engine/repositorios/npc.py`, `engine/loop.py`, `engine/database.py`

**Problema:** `GameLoop` chama `db.npcs.salvar(npc)` por NPC, e
`DatabaseManager.connection()` faz `commit()` na saída de cada `with`. Com 750 NPCs são
750 commits por tick. O profiler mostrou 7 ms só em `commit` com 20 NPCs.

**Ação:**

1. `RepositorioNPC.salvar_muitos(npcs)` com `executemany`, num único `with
   self._db.connection()`.
2. `GameLoop.executar_tick` acumula os NPCs alterados numa lista e chama `salvar_muitos`
   uma vez, no fim. ⚠️ **Cuidado com a ordem:** `_processar_partos` e
   `processar_morte` criam e removem NPCs; garanta que o salvamento em lote acontece
   depois deles, e que o NPC morto não é regravado como vivo.
3. Não mexa em `PRAGMA synchronous=NORMAL` nem em WAL — já estão certos.

**Validar:** `bench_tick.py` com banco real (não o dublê) e 750 NPCs: tempo de escrita por
tick abaixo de 30 ms.

**Risco:** médio. Bug aqui é perda de estado, não lentidão. Teste com cuidado.

---

### P06 · Medir contra o orçamento, e só então decidir sobre processo
**Arquivos:** `builder/fix/bench_tick.py` (de `V03`)

**Ação:**

1. Rode a matriz de `V03` depois de `P01`–`P05` e preencha esta tabela:

   | Cenário | ms por tick medido | Cabe em 1 s (D4)? |
   |---|---|---|
   | 750 NPCs, ~10 mil locais, 15 cidades | | |
   | 1.500 NPCs, ~10 mil locais, 15 cidades | | |
   | 3.000 NPCs, ~15 mil locais, 15 cidades | | |

2. Projeção, para você saber o que esperar: o custo hoje é dominado pelas varreduras, que
   somem. Sobra o trabalho por NPC (metabolismo, decisão, ação, humor), que era ~2,9 ms
   para 20 NPCs com uma lista pequena — algo como **0,10 ms por NPC**. Para 750 NPCs isso
   dá **~75 ms por tick**, com folga de 13× contra o orçamento de 1 s.

3. **Se couber (esperado): pare aqui.** Escreva o número medido no final deste documento
   e não introduza thread nem processo. Releia a armadilha 5.

4. **Se não couber**, a ordem de investigação é esta, e não outra:
   1. profile de novo (`cProfile`, ordenado por `cumulative`) — provavelmente sobrou uma
      varredura;
   2. baixe a frequência do que não precisa ser por minuto (humor, social, dependentes
      podem ser a cada 5 ou 15 minutos de jogo, sem ninguém notar);
   3. **só então** `ProcessPoolExecutor` com uma cidade por processo — e isso exige antes
      definir o contrato de interação intercidade (casamento, mercado, migração), que
      hoje não existe. É outro plano, não uma tarefa deste.

**Risco:** nenhum. É medição.

---

### P07 · Ligar as 15 cidades, com a população no config
**Arquivos:** `builder/populador.py`, `config.json`, `engine/models.py`

**Problema:** `_eleger_cidade_spawn` elege `cidades_salvas[0]` e só ela recebe NPCs
(`_criar_npcs` usa `self.cidade_spawn['db_id']` para todos). D1 pede população
configurável em todas as cidades.

**Ação:**

1. Chaves novas, em `config.json` sob `geracao_populacao`:
   ```json
   "npcs_por_cidade": 50,
   "cidades_ativas": "todas",
   "npcs_por_cidade_por_tamanho": {"pequeno": 0.6, "medio": 1.0, "grande": 1.6}
   ```
   O multiplicador por tamanho é o que faz a capital parecer capital. `cidades_ativas`
   aceita `"todas"` ou uma lista de nomes — o valor `"todas"` é literal, não `None`, para
   a intenção ficar escrita.

2. `PopuladorDeMundo`:
   - `_eleger_cidade_spawn` → `_eleger_cidades_ativas`, que devolve a **lista**, grava
     `MetaChave.CIDADES_ATIVAS` com todos os ids (a chave já existe, só nunca teve mais de
     um) e mantém `CIDADE_SIMULADA` como a cidade **focada no dashboard** (primeira da
     lista). Não são a mesma coisa e a diferença precisa ficar clara no docstring.
   - `_criar_npcs` passa a iterar cidades, e dentro de cada cidade os NPCs. `casas_ids`
     vira `casas_por_cidade: dict[int, list[str]]` — um NPC nunca pode receber casa de
     outra cidade (é o bug que `P04` acabou de consertar no movimento; não reintroduza no
     povoamento).
   - `id` do NPC: `f"npc_{cidade_id:02d}_{idx:03d}"`. `f"npc_{idx:03d}"` colide entre
     cidades.
   - `_formar_casais_iniciais` e `_estabelecer_lacos_sociais` passam a rodar **por
     cidade**. Laço social entre NPCs de cidades diferentes, no povoamento, não faz
     sentido e ainda é O(N²) sobre a população global.

3. ⚠️ **Custo de IA.** `_gerar_dnas_em_paralelo` faz uma chamada de LLM por NPC. De 20
   para 750 NPCs são 750 chamadas. Deixe `--desativar-ia` como o caminho padrão do
   povoamento em massa e documente no `--help`: IA para a cidade focada, fallback
   procedural para as outras. Ou aceite o custo consciente. **Não descubra isso na
   fatura.**

4. `run_simulation.py` e o dashboard já leem `CIDADES_ATIVAS`? Confira — `mestre_routes`
   e `web/dashboard.py` usam `CIDADE_SIMULADA` em vários lugares, e alguns deles querem
   dizer "a cidade toda" e outros "a cidade em foco".

**Validar:** reset completo, e `SELECT cidade_id, count(*) FROM npcs GROUP BY cidade_id`
com 15 linhas. Dashboard abre sem erro. `bench_tick.py` com o banco real dentro do
orçamento.

**Risco:** médio.

---

# Bloco V — Validação permanente

> Objetivo: nenhum dos bugs deste documento pode voltar sem alguém ver. Estas três
> ferramentas são o que transforma este plano num estado estável em vez de um conserto.

### V01 · Invariantes de geometria em `tests/test_cidades.py`
**Arquivos:** `tests/test_cidades.py`

**Ação:** acrescente, todos rodando sobre **os 4 modelos registrados** (itere `MODELOS`,
não escreva o nome de nenhum modelo — modelo novo entra e o teste já cobre):

| Teste | Invariante |
|---|---|
| `test_aneis_nao_cruzam` | em 200 seeds, raio estritamente crescente por setor (`G01`) |
| `test_nenhum_poligono_auto_intersectante` | toda feature `Polygon` emitida é simples (`G02`) |
| `test_quadra_dentro_da_muralha` | todo vértice de quadra está dentro de `malha.contorno` (`G03`) |
| `test_rua_coincide_com_aresta_de_quadra` | toda aresta não-`servico` tem rua a menos de meia largura (`G04`) |
| `test_todo_lote_tem_frente` | **o invariante central**: toda aresta de lote… ao menos uma coincide com aresta de quarteirão (`Q01`) |
| `test_lotes_por_quadra_em_faixa` | entre 4 e 30 (`Q01`, `Q03`) |
| `test_ocupacao_inicial_respeita_fracao` | edifícios/lotes dentro de 3 pp da fração (`T03`) |
| `test_id_de_lote_estavel` | descartar uma quadra do meio não muda o id dos outros lotes (armadilha 3) |

O último é o menos óbvio e o mais valioso: monte uma malha, gere, remova uma quadra do
meio, gere de novo, e afirme que os ids dos lotes que sobraram **não mudaram**.

**Risco:** baixo.

---

### V02 · Auditor de cidades, para olhar as 15 de uma vez
**Arquivos:** `builder/fix/audit_cidades.py` (novo)

**Problema:** os testes provam invariantes em seeds sintéticas. Eles não te dizem se
*Fenelburgo* ficou boa. A tabela da Seção 1 deste documento foi produzida por scripts
descartáveis — ela precisa virar ferramenta.

**Ação:** um script no padrão de `builder/fix/` (ferramenta manual, fora do runtime,
documentada como tal — R-A11). Lê `database/cidades/*.geojson` e imprime uma linha por
cidade:

```
cidade          modelo    aneis vao_m lotes livres% bowtie l/quadra sem_frente fora_muro
Fenelburgo      organica      4   169  3129     40%      0     12         0%        0 m
```

Colunas obrigatórias: cruzamentos de anel, polígonos auto-intersectantes (quarteirão e
lote), lotes por quadra (mediana e máximo), percentual de lotes a mais de 25 m de rua,
pior invasão de muralha, fração ocupada, vão de anel, área mediana de lote.

Faça o script **sair com código 1** se qualquer invariante estiver violado. Assim ele
serve de porta antes de um commit, não só de relatório.

**Risco:** baixo.

---

### V03 · Bench do tick, com o orçamento escrito nele
**Arquivos:** `builder/fix/bench_tick.py` (novo)

**Ação:** monta um `EstadoDoMundo` sintético (reaproveite `tests/mundo_sintetico.py`, mas
com um dublê de banco que aceite `meta.salvar(chave, valor)` — o `RepositorioFalso` atual
tem `salvar` de 1 argumento e quebra no `_avancar_relogio`), varre uma matriz de
(NPCs × locais × cidades) e imprime ms por tick.

Imprima o orçamento na saída, não num comentário:

```
ORÇAMENTO: 1000 ms/tick (velocidade 60x, D4 do docs/12_PLANO_CIDADE_VIVA.md)
  npcs  locais  cidades   ms/tick   veredito
   750   10000       15      78.4   OK (12.8x de folga)
  3000   15000       15     412.1   OK (2.4x de folga)
```

Aceite `--real` para rodar contra `database/openworld.db` em vez do sintético, com
`--ticks N`. É assim que `P06` é respondido.

**Risco:** baixo.

---

## Anexo 1 — Tabela de medições da base atual

Estado em 2026-09-12, 15 cidades em `database/cidades/`, banco com 20 NPCs.

| Cidade | Modelo | Tam. | Raio | Quadras | Lotes | Edif. | Gravata-borboleta | Máx. lotes/quadra | Mediana lotes/quadra | Sem frente (>25 m) |
|---|---|---|---|---|---|---|---|---|---|---|
| Jordorstead | organica→radial | grande | 992 m | 72 | 6.046 | 6.046 | 2 | **209** | **94** | **58%** |
| Fenelburgo | organica | grande | 844 m | 39 | 3.129 | 3.125 | 7 | **220** | **64** | **64%** |
| Keldorstead | radial | medio | 716 m | 59 | 2.835 | 2.835 | 0 | 94 | 55 | 48% |
| Tordordor | radial | medio | 612 m | 37 | 2.540 | 2.537 | 3 | 124 | 72 | 49% |
| Irenburgo | grade | grande | 791 m | 206 | 2.474 | 2.474 | 0 | 32 | 8 | 38% |
| Cidade da Lua | grade | grande | 765 m | 151 | 2.012 | 2.012 | 0 | 32 | 16 | 34% |
| Cidade dos Sonhos | grade | medio | 593 m | 187 | 1.689 | 1.689 | 0 | 16 | 8 | 9% |
| Cidade dos Ventos | grade | medio | 472 m | 106 | 1.168 | 1.168 | 0 | 16 | 8 | 16% |
| Corarfield | linear | grande | 846 m | 87 | 952 | 952 | 0 | 16 | 8 | 12% |
| Cidade das Flores | organica | medio | 478 m | 28 | 696 | 695 | 7 | 70 | 26 | 41% |
| Pelvermont | radial | pequeno | 329 m | 15 | 386 | 386 | 0 | 32 | 26 | 23% |
| Elorfield | linear | medio | 511 m | 67 | 268 | 268 | 0 | 4 | 4 | 0% |
| Kelandor | linear | pequeno | 394 m | 52 | 164 | 164 | 0 | 4 | 4 | 0% |
| Belinhaven | linear | pequeno | 293 m | 23 | 72 | 72 | 0 | 4 | 4 | 0% |

Banco: 24.423 locais (21.008 residências) para 20 NPCs, todos na cidade 1.

Tick medido (mundo sintético, `Python 3.14.4`, GIL ligado, 20 CPUs):

| NPCs | Locais | ms/tick |
|---|---|---|
| 20 | 1.000 | 2,9 |
| 20 | 24.000 | 53,8 |
| 200 | 24.000 | 580 |
| 500 | 24.000 | 1.608 |
| 1.500 | 24.000 | 6.317 |
| 3.000 | 24.000 | 16.629 |

---

## Anexo 2 — Chaves de config novas e removidas

### Novas, em `config.json["cartografia"]`

| Chave | Valor proposto | Tarefa |
|---|---|---|
| `cidade_geo_anel_perturbacao_fracao_vao` | `0.22` | `G01` |
| `cidade_geo_vao_anel_alvo_m` | `95` | `G05` |
| `cidade_geo_janela_terreno_fator` | `3.0` | `G06` |
| `cidade_geo_lote_profundidade_m_por_banda` | `{"0":14,"1":16,"2":18,"_default":22}` | `Q01` |
| `cidade_geo_lote_frente_m_faixa_por_banda` | `{"0":[6,9],"1":[7,10],"2":[8,12],"_default":[9,14]}` | `Q01` |
| `cidade_geo_patio_area_minima_m2` | `120` | `Q01` |
| `cidade_geo_patio_area_maxima_m2` | `2500` | `Q01` |
| `cidade_geo_escala` | `1.0` | `Q04` |
| `cidade_geo_ocupacao_inicial_por_tamanho` | `{"pequeno":0.25,"medio":0.40,"grande":0.60}` | `T03` |
| `cidade_geo_linear_comprimento_celula_m_faixa` | `[50,90]` | `Q03` |
| `cidade_geo_linear_profundidade_fileira_m_faixa` | `[22,34]` | `Q03` |
| `cidade_geo_zoom_min_alvo_px_por_camada.patio` | `400` | `Q01` |

### Novas, em `config.json["urbanismo"]` (bloco novo)

| Chave | Valor proposto | Tarefa |
|---|---|---|
| `habitantes_por_estabelecimento` | `{"taverna":40,"mercado":35,"forja":45,"universidade":150,"quartel":120}` | `O02` |
| `custo_estabelecimento_pc` | a calibrar | `O02` |
| `lotes_livres_minimo` | `8` | `X01` |
| `fracao_livre_minima` | `0.03` | `X01` |
| `arrabalde_comprimento_m` | `180` | `X02` |
| `arrabalde_comprimento_max_m` | `520` | `X02` |

### Novas, em `config.json["geracao_populacao"]`

| Chave | Valor proposto | Tarefa |
|---|---|---|
| `npcs_por_cidade` | `50` | `P07` |
| `npcs_por_cidade_por_tamanho` | `{"pequeno":0.6,"medio":1.0,"grande":1.6}` | `P07` |
| `cidades_ativas` | `"todas"` | `P07` |

### Removidas

| Chave | Por que sai | Tarefa |
|---|---|---|
| `cidade_geo_lote_area_base_m2` | lote passa a ser frente × profundidade | `Q01` |
| `cidade_geo_lote_fator_por_banda` | idem | `Q01` |
| `cidade_geo_lote_profundidade_max` | não há mais recursão de subdivisão | `Q01` |
| `cidade_geo_organica_fracao_quadras_vazias` | vazio agora é ocupação inicial, para todo modelo | `G04` |
| `cidade_geo_linear_largura_quadra_m_faixa` | separada em duas chaves | `Q03` |

### Mantidas, mas precisam de recalibragem

| Chave | Valor hoje | Por que recalibrar | Tarefa |
|---|---|---|---|
| `cidade_geo_quadra_area_minima_m2` | `400` | é o piso para a quadra ser urbanizável. Com quadra rasa (`Q03`) e pátio, `400` passa a descartar quadra que cabe lote — suspeito que o valor certo fique perto de `150` | `Q01` |
| `cidade_geo_grade_lado_quadra_m_faixa` | `[70, 140]` | aperte para `[55, 95]`: com pátio, 140 m de lado sempre cai no caso "pátio grande demais" e gera viela | `Q03` |
| `cidade_geo_num_aneis_faixa_por_tamanho` | `{"pequeno":[2,3],...}` | deixa de ser a fonte e passa a ser só o teto/piso do cálculo por vão | `G05` |
| `cidade_geo_irregularidade_via` | `0.15` | continua valendo para silhueta de grade e muralha, mas **não** para raio de anel | `G01` |
| `cidade_geo_organica_fator_irregularidade` | `2.2` | passa a multiplicar a fração do vão, e é saturada em `0.45` no código | `G01` |

---

## Anexo 3 — Glossário de geometria urbana

Os termos abaixo aparecem no código e no plano. Estão em português e têm significado
técnico preciso — não os troque por sinônimos.

| Termo | O que é |
|---|---|
| **Quadra** / **quarteirão** | o bloco de terra cercado por ruas em todos os lados. No código, `Quadra` (malha, sem inset) e a camada `quarteirao` (emitida, com inset). |
| **Faixa de domínio** | a largura que a via ocupa de fato: meia largura da pista mais o recuo. É o que o inset de quadra desconta. |
| **Inset** | encolher um polígono deslocando cada aresta para dentro e reinterceptando. `_encolher_quad`. |
| **Lote** | a unidade de propriedade. Depois de `Q01`, **sempre** com uma aresta na rua. |
| **Frente** | a aresta do lote que encara a rua. `classe_frente` diz que tipo de rua. |
| **Profundidade** | a dimensão do lote perpendicular à frente. |
| **Pátio** | o miolo da quadra que não é lote. Horta, poço, quintal comum. Camada `patio`. |
| **Viela** | rua de serviço estreita, dentro da quadra, quando o pátio ficaria grande demais. |
| **Footprint** | o polígono do edifício construído, dentro do lote, recuado das divisas. |
| **Banda** | o anel concêntrico de quadras. 0 = núcleo, `num_bandas - 1` = borda. Alimenta a zona. |
| **Vão** | a distância radial entre dois anéis vizinhos. **É** a profundidade da quadra. |
| **Arrabalde** | o bairro que cresce fora da muralha, quando a cidade satura. Bloco X. |
| **Sítio** | os dados de lugar (posição, terreno, clima, água) medidos antes do traçado. `SitioCidade`. |
| **Malha** | o resultado de `construir_malha`: ruas, quadras, portões, praça, contorno. |

---

## Registro de execução

> ✅ **As quatro decisões pendentes registradas nesta tabela foram respondidas, com
> medição, em [`13_PLANO_POPULACAO_E_ESCALA.md`](13_PLANO_POPULACAO_E_ESCALA.md) (Seção 1).**
> Resumo: `num_setores` fixo é mesmo a causa raiz das quadras de 150 lotes (Bloco S);
> os lotes cegos do `organica` têm duas causas concretas e consertáveis, e a tolerância
> rígida de `audit_cidades.py` estava certa (Bloco L); o RNG derivado por quadra vale a
> pena e custa uma linha e meia (L03); e a lacuna entre o processo do Modo Mestre e o da
> simulação se resolve com um contador de versão em `mundo_meta` (Bloco M).

> Anote aqui o que você encontrou e o que ficou diferente do planejado. Uma linha por
> tarefa concluída, com o número medido quando houver.

| Tarefa | Data | Observação / número medido |
|---|---|---|
| V02 | 2026-09-12 | `builder/fix/audit_cidades.py` criado. Números batem com a Seção 1 (Fenelburgo 4 anéis/169m antes de G01, 7 bowtie; Jordorstead 209 lotes/quadra). |
| V03 | 2026-09-12 | `builder/fix/bench_tick.py` criado. 20 NPCs/24 mil locais: 56,1 ms medido (doc: 53,8 ms). `RepositorioFalso.salvar` passou a aceitar `*args` pra cobrir `meta.salvar(chave, valor)`. |
| G01 | 2026-09-12 | Perturbação por vão em vez de raio. Achado não previsto pelo texto: o anel do NÚCLEO usava a mesma amplitude sem considerar que seu vão até raios_base[0] pode ser bem menor que `vao` — `nucleo_urbanizavel` precisou de margem extra (2×amplitude_m), não só o `*0.9` original. Bowtie/anéis cruzados: de vários por cidade para 0 em todas as 15. |
| G02 | 2026-09-12 | `_segmentos_cruzam`/`_e_quad_simples` adicionados. Sem mudança nas 15 cidades pós-G01 (o bowtie já tinha sumido) — invariante defensivo pra modelos/casos futuros. |
| G03 | 2026-09-12 | `envolver_poligono` em base.py. `grade.py` já seguia o padrão certo (envelope das quadras), sem mudança. Pior invasão de muralha: 0,0 m em todas as cidades com muro. |
| G04 | 2026-09-12 | `_grade_de_vertices` extraído; organica torce a grade (giro, não deslocamento). Achado durante a auditoria: a checagem de "servico" nos dois lados do vão (`i` OU `i2`) era necessária — só checar `i` deixava passar um caso real. |
| G05 | 2026-09-12 | `num_aneis` calculado, não sorteado. Vão caiu de 82–169 m pra 96–143 m nas 15 cidades. 4 cidades grande (Fenelburgo, Jordorstead, Keldorstead, Tordordor) ainda passam de 120 m — capadas pelo teto de `cidade_geo_num_aneis_faixa_por_tamanho`, não recalibrado (decisão de balanceamento visual, não bug). |
| G06 | 2026-09-12 | Janela de terreno com margem (fator 3.0, resolução 128×128). `SitioCidade` ganhou `raio_janela_m`/`altitude_em`/`declividade_em`. |
| Q01 | 2026-09-12 | Anel perimetral + pátio. **Achado maior que o esperado**: "lotes por quadra" ficou bem acima do alvo (4-30, mediana ~12) em radial/organica — mediana de 70 a 151 nalgumas cidades. Investigado a fundo: NÃO é bug do algoritmo (grade/linear, mesmo código, ficam dentro do alvo). É `num_setores` (fora do escopo deste plano) produzindo quadras com largura tangencial de 200-400 m nas bandas externas de cidades radiais — muito maior que a profundidade (~95-140 m de G05). Testado aumentar `PROFUNDIDADE_CORTE_MAXIMA` (0, 2, 5 níveis): mais corte PIORA (cada corte soma frente de viela nova). 2 (valor do plano) é o melhor equilíbrio sem mexer em `num_setores`. **Decisão pendente pro dono do projeto**: vale a pena calibrar `num_setores` em função da banda pra aproximar do alvo visual? |
| Q02 | 2026-09-12 | Pacote `cartographer/cities/geometria/` criado. Zero mudança de comportamento (mesma contagem de edifícios antes/depois do split). |
| Q03 | 2026-09-12 | Faixas de grade/linear reapertadas. Confirma o diagnóstico de Q01: grade/linear ficaram com 9-21 lotes/quadra (mediana), dentro do alvo. |
| Q04 | 2026-09-12 | `escala.py:faixa_raio_m`. Validado com escala 0.5 (raio caiu à metade, vão de anel não mudou, como esperado) e revertido pra 1.0. |
| T01 | 2026-09-12 | Tabela `lotes` + `RepositorioLote`. `x`/`y` como REAL (não JSON) desde já, adiantando o que O01 pediria. |
| T02 | 2026-09-12 | Importação de lotes. Jordorstead real: 8491 locais + 8775 lotes, 0 lotes "ocupado" sem Local correspondente. |
| T03 | 2026-09-12 | Ocupação inicial por zona/quadra. **Achado e corrigido dentro do escopo**: sortear sem saber quais lotes têm footprint viável (recuo degenera lote estreito) fazia a ocupação real ficar bem abaixo do alvo (31% numa cidade configurada pra 60%). `_precomputar_footprints` + `_indexar_lotes` filtrando por viabilidade resolveu — a maioria das cidades ficou a 1-2 pp do alvo. Duas cidades (`grade`/`grande`: Cidade da Lua, Irenburgo) continuam ~10 pp abaixo — teto de lotes com footprint viável abaixo de 100%, pré-existente a T03 (não é regressão, mas mereceria investigação própria). |
| T04 | 2026-09-12 | Colapso pra ruína libera o lote. Sem desvio do planejado. |
| T05 | 2026-09-12 | Rota `/api/cidade/<id>/lotes_alterados` + estilo de lote por estado. **Escopo reduzido conscientemente**: a Parte 4 (camada `footprint_potencial` pra edifício novo aparecer no mapa) não foi implementada — geometria nova cara, o próprio plano chama de "decisão de arquitetura" à parte. Por ora o mapa reflete a mudança de ESTADO do lote; o polígono do edifício em si só aparece na próxima regeração de GeoJSON. |
| P01 | 2026-09-12 | `IndiceDeLocais` criado. 20 NPCs/24 mil locais: 56,1 ms → 31,6 ms (ainda falta P02 pra obter_obra_do_npc). |
| P02 | 2026-09-12 | `EstadoDoMundo.registrar_local`/`desativar_local`. 20 NPCs/24 mil locais: 31,6 ms → 1,5 ms (bate o alvo de <5ms). **Achado, não corrigido**: ações do Modo Mestre rodam no processo do dashboard, sem acesso a `EstadoDoMundo`/`indice` do processo de simulação — não existe um "recarregar_locais" equivalente a `recarregar_habitantes`. Lacuna de sincronização entre processos, maior que o escopo de P02; anotada pro dono do projeto decidir. |
| P03 | 2026-09-12 | Agrupamentos por tick. **Achado fora do arquivo do plano**: `NPCMarriageManager.processar_coabitacao` fazia todos-contra-todos sobre TODOS os solteiros do mundo, todo tick — o verdadeiro motivo da curva continuar quadrática depois de P01-P02. Agrupado por cidade (mesmo raciocínio de P04): 375→750→1500 NPCs foi de 128/521/2082 ms pra 15/46/163 ms. Ainda não é perfeitamente linear (o double loop continua O(N²) por cidade), mas a matriz inteira do bench_tick passou a caber no orçamento — incluindo o cenário de 3000 NPCs que antes estourava. |
| P04 | 2026-09-12 | Fallback de `mover_para` restrito à cidade do NPC. Sem desvio do planejado. |
| P05 | 2026-09-12 | `salvar_muitos` com executemany. Ordem ajustada: salva DEPOIS de partos/mortes (não antes), pra pegar mutações de `processar_parto` em mãe/pai. |
| P06 | 2026-09-12 | **Coube.** Matriz completa (bench_tick.py, 5 ticks): 750 NPCs/10k locais/15 cidades = 46,9 ms (21,3× de folga); 1500/10k/15 = 161,9 ms (6,2×); 1500/15k/15 = 162,3 ms (6,2×); 3000/15k/15 = 595,8 ms (1,7×). Todos dentro do orçamento de 1000 ms (D4). Decisão: PAROU AQUI — nenhuma thread nem processo introduzidos (armadilha 5). |
| P07 | 2026-09-12 | 15 cidades ligadas de vez. `_eleger_cidade_spawn` → `_eleger_cidades_ativas` (lista, respeita `geracao_populacao.cidades_ativas`), população por cidade escalada por `npcs_por_cidade_por_tamanho`, IDs `npc_{cidade:02d}_{idx:03d}`, IA de biografia só na cidade foco (`MetaChave.CIDADE_SIMULADA`). Validado ponta a ponta com as 15 cidades reais + `--desativar-ia --npcs 5`: 84 NPCs, sem colisão de id, casais sempre na mesma cidade. |
| O01 | 2026-09-12 | Obra do casal ocupa lote real. `reservar_livre`/`buscar_por_id` novos em `RepositorioLote`; id da obra = id do lote (armadilha 3), fim do `casa_obra_{time.time()}_{randint}` não reproduzível. |
| O02 | 2026-09-12 | Comércio nasce por demanda, não por tabela de densidade fixada na geração. `GerenciadorUrbanismo` (novo), roda 1x/dia por cidade com gente; no máximo um estabelecimento por cidade por dia, sempre o de maior déficit; quem paga é o NPC mais rico da cidade acima do custo — sem tesouro no projeto, cidade sem ninguém rico simplesmente não cresce naquele dia. |
| O03 | 2026-09-12 | `abrir_obra` extraído como o único caminho pra um edifício nascer — `housing.py` (casa de casal) e `urbanismo.py` (comércio) chamam o mesmo método; nenhum duplica reservar/criar/marcar. Validado por grep: `status=0`/`integridade=0` como CRIAÇÃO só existem em `urbanismo.py` (o resto são comentários ou as mutações de decay.py pro colapso em ruína). |
| X01/X03 | 2026-09-12 | Gatilho de auto-expansão (`avaliar_expansao`, piso absoluto OU fracionário) + persistência (`_aplicar_arrabalde` — única escrita da engine num arquivo do cartógrafo: acrescenta, nunca edita; `_indice.json` reescrito também, senão o bbox velho corta o arrabalde fora da API do mapa). `abrir_obra` sem lote dispara a avaliação na hora, não espera a varredura diária. Validado com uma cidade real de teste saturada artificialmente: arquivo cresce, lotes novos entram livres no banco, evento registrado, no máximo um arrabalde por dia. |
| X02 | 2026-09-12 | `cartographer/cities/expansao.py` (novo): geometria pura do arrabalde — escolhe o portão por declividade média do eixo (penaliza água e direção já usada), estende a rua radial, gera fileiras de quadra dos dois lados reusando o MESMO código de subdivisão de Q01. **Achado rodando contra as 15 cidades reais**: perto de um canto de cidade `grade`, a extensão reta a partir do portão tangenciava a última banda existente — adicionado um filtro que descarta qualquer quadra nova que cruce geometria já existente (não estava no texto original do plano, mas é necessário pra "não intersecta nenhum quarteirão existente" ser verdade de fato, não só na maioria dos casos). Validado nas 15 cidades reais: 14/14 sem cruzamento, sem lote sem frente, determinístico. |
| V01 | 2026-09-12 | Dois invariantes que faltavam: `test_lotes_por_quadra_em_faixa` (parametrizado pelos 4 modelos — grade/linear passam de verdade, radial/organica são xfail não-strict, confirmando em código o achado de Q01). `test_id_de_lote_estavel` **não foi escrito como o texto original pede** ("remova uma quadra do meio, gere de novo"): achado novo — a malha usa um rng compartilhado sequencial entre quadras, e `n_lotes = round(comprimento/frente_alvo)` pode arredondar diferente quando o fluxo de sorteios upstream muda (uma quadra removida antes desloca o que vem depois). O id continua vindo de quarteirao_id + índice local (nunca um contador global — a garantia original da armadilha 3 segue de pé), mas a CONTAGEM exata de lotes de uma quadra downstream não é garantida estável a uma remoção de quadra vizinha com o rng atual (compartilhado, sequencial). Testar isso do jeito literal seria flaky, ou exigiria rng derivado por quadra (mudança de arquitetura, fora de "escrever teste"). Reforcei em vez disso o teste que cobre o que ACONTECE de verdade neste projeto (X02/X03 só ACRESCENTAM, nunca removem/editam): toda feature original sobrevive intacta, byte a byte, depois de um arrabalde. **Decisão pendente pro dono do projeto**: vale a pena dar a cada quadra um rng derivado do próprio id (ex. `seed ^ hash(quadra.id)`), pra eliminar esse acoplamento de sequência entre quadras vizinhas? |
| — | 2026-09-12 | **Achado ao rodar `audit_cidades.py` no fim da sessão (não introduzido agora — confirmado via regeração byte a byte idêntica de antes/depois de O03/X01-X03/V01)**: o script sai com código 1 porque `sem_frente_pct` > 0 em duas cidades `organica` (Cidade das Flores 4,6%; Fenelburgo 3,3%) — `TOLERANCIA_SEM_FRENTE_PCT` é `0.0`, invariante RÍGIDO, não o "soft target" que o histórico da sessão vinha assumindo. bowtie/anéis cruzados/muro continuam 0 em todas as 15. Como está, `audit_cidades.py` nunca sai 0 pro conjunto completo das 15 cidades reais — não serve de porta de commit sem ajuste. **Decisão pendente pro dono do projeto**: investigar a origem exata desses lotes sem frente em `organica` (provável interação entre `_torcer_grade`, de G04, e o corte de pátio de Q01 num canto), afrouxar a tolerância pra essas duas cidades, ou aceitar o número documentado como o piso real do modelo `organica`? |
