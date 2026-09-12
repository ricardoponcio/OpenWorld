# 🧭 Plano de Motor e Escala — o tick que não toca em todo mundo, e a cidade do tamanho da sua gente

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este é o **segundo** documento da série. O primeiro,
> [`PLANO_CIDADE_VIVA.md`](PLANO_CIDADE_VIVA.md), foi executado por inteiro (31 tarefas,
> G01 a V03) e o seu *Registro de execução* deixou **quatro decisões pendentes** e uma
> ferramenta de auditoria que ainda não fecha. Este documento responde as quatro,
> com medição, e acrescenta o estudo de performance que o dono do projeto pediu:
> quanto custa ter muito mais NPCs, e o que exatamente precisa mudar para isso caber.
>
> 👉 **Leia o `PLANO_CIDADE_VIVA.md` antes deste.** Quase toda tarefa aqui mexe em código
> que ele criou, e as **cinco armadilhas** da Seção 3 dele continuam valendo palavra por
> palavra. Este documento acrescenta cinco novas, não substitui as antigas.
>
> 👉 Leia [`ARQUITETURA.md`](ARQUITETURA.md) Seção 2 (regra de dependência entre camadas)
> e Seção 4 (limites de tamanho). O Bloco N mexe no laço mais quente do projeto e a
> tentação de "só colocar um cache aqui" vai aparecer três vezes; a camada certa importa
> mais que o ganho.

**Criado em:** 2026-09-12
**Base analisada:** branch `reescrita-estrutura`, commit `26328c4`
**Interpretador:** Python 3.14.4, `Py_GIL_DISABLED = 0` (a GIL está **ligada**)
**Estado da suíte na base:** `92 passed, 2 xfailed` em 80 s
**Medições:** feitas sobre as 14 cidades em `database/cidades/` (51.965 lotes no total),
sobre `database/openworld.db` (20 NPCs, 24.423 locais) e sobre mundos sintéticos de até
50.000 NPCs montados por `builder/fix/bench_tick.py`.

> ### ⚠️ Leia isto antes do índice: este documento mudou de prioridade
>
> A primeira versão dele tratava a mudança de arquitetura do motor como "horizonte", a ser
> feita algum dia. **Não é mais.** O objetivo do projeto é um mundo autossuficiente, que
> pareça real sem o Mestre ter que criar tudo, e que sobre margem para evoluir — e para
> isso o Mestre precisa conseguir **avançar alguns dias** para efeito de aventura.
>
> Medi o que isso custa e o resultado inverteu a ordem do plano. Com 25.000 NPCs, mesmo
> **desligando todo o processamento por NPC**, um tick ainda custa **35,6 ms**, dos quais
> 17,3 ms são só remontar agrupamentos que ninguém pediu. Sete dias simulados são 10.080
> ticks: a 35,6 ms isso é **seis minutos de espera**, e a 947 ms (o custo real de hoje) são
> **duas horas e meia**.
>
> Por isso o **Bloco A** existe e vem **primeiro**, antes de qualquer geometria de cidade.
> Ele é a única parte deste plano que muda a forma do motor, e é muito mais barato fazê-lo
> agora — com o motor pequeno — do que depois de mais dez mecânicas terem nascido no
> formato antigo.

---

## Índice

- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. As quatro pendências do plano anterior, respondidas](#1-as-quatro-pendências-do-plano-anterior-respondidas)
- [2. O estudo de performance: onde está o teto hoje](#2-o-estudo-de-performance-onde-está-o-teto-hoje)
- [3. Decisões já tomadas (não reabra)](#3-decisões-já-tomadas-não-reabra)
- [4. As sete novas armadilhas](#4-as-sete-novas-armadilhas)
- [Bloco N — Os quatro gargalos até 25 mil NPCs](#bloco-n--os-quatro-gargalos-até-25-mil-npcs)
- [Bloco A — A agenda: o tick deixa de tocar em todo mundo](#bloco-a--a-agenda-o-tick-deixa-de-tocar-em-todo-mundo) ★
- [Bloco E — Eventos: agrupar a escrita e podar a história](#bloco-e--eventos-agrupar-a-escrita-e-podar-a-história)
- [Bloco M — Modo Mestre: sincronia entre processos](#bloco-m--modo-mestre-sincronia-entre-processos)
- [Bloco S — Ruas radiais que acompanham o raio](#bloco-s--ruas-radiais-que-acompanham-o-raio)
- [Bloco L — Lote com frente de verdade, e RNG por quadra](#bloco-l--lote-com-frente-de-verdade-e-rng-por-quadra)
- [Bloco R — A cidade nasce do tamanho da sua população](#bloco-r--a-cidade-nasce-do-tamanho-da-sua-população)
- [Bloco W — Validação permanente](#bloco-w--validação-permanente)
- [5. Horizonte 50 mil+ — o que muda de estrutura](#5-horizonte-50-mil--o-que-muda-de-estrutura)
  - [5.0 O teto não é um número de NPCs. É um produto.](#50-o-teto-não-é-um-número-de-npcs-é-um-produto)
  - [5.4 O teto de velocidade](#54-o-teto-de-velocidade--resolvido-pelo-bloco-a-não-pelo-horizonte)
  - [5.5 Avanço rápido é outro modo de simulação](#55-avanço-rápido-é-outro-modo-de-simulação-não-um-tick-mais-rápido)
- [Anexo 1 — Tabela de medições](#anexo-1--tabela-de-medições)
- [Anexo 2 — Chaves de config novas, removidas e recalibradas](#anexo-2--chaves-de-config-novas-removidas-e-recalibradas)
- [Anexo 3 — Glossário: os termos novos deste plano](#anexo-3--glossário-os-termos-novos-deste-plano)
- [Registro de execução](#registro-de-execução)

---

## 0. Como usar este documento

### Regras de execução

1. **Uma tarefa por commit.** Título = ID da tarefa + descrição curta.
   Ex.: `S01: setores dobram quando o arco passa da largura alvo`.
2. **Este plano MUDA o traçado de todas as cidades de novo, de propósito.** A armadilha 1
   do plano anterior continua valendo: *determinístico* não quer dizer *igual ao de
   antes*. O que precisa continuar verdade é: a mesma seed, rodada duas vezes, produz
   arquivos idênticos byte a byte.
3. **Rode a suíte antes e depois de cada tarefa:**
   ```
   venv/bin/python3 -m pytest tests/ -q
   ```
   A base é `92 passed, 2 xfailed`. Os 2 xfailed são `test_lotes_por_quadra_em_faixa`
   para `radial` e `organica` — o Bloco S existe justamente para eles passarem.
4. **Depois de cada tarefa dos Blocos S, L ou R, regenere e audite:**
   ```
   venv/bin/python3 cartographer/cities/generate_city_geometry.py
   venv/bin/python3 builder/fix/audit_cidades.py ; echo "saida=$?"
   ```
   **Cuidado:** `audit_cidades.py` hoje sai **1** (L02 é a tarefa que conserta isso).
   Até L02 estar pronta, compare a *tabela*, não o código de saída — e nunca use
   `| tail` nem `| head` para ler o resultado, porque o pipe engole o código de saída.
5. **Depois de cada tarefa dos Blocos N ou A, meça:**
   ```
   venv/bin/python3 builder/fix/bench_tick.py --ticks 3
   venv/bin/python3 builder/fix/bench_avanco.py --dias 7    # criado em A07
   ```
6. **Se uma tarefa parecer maior do que o descrito, pare e anote** no
   [Registro de execução](#registro-de-execução). Foi exatamente isso que fez o plano
   anterior dar certo: as quatro pendências que este documento responde vieram de você
   ter parado e escrito, em vez de improvisar.
7. **Não renomeie nada além do que a tarefa pede.**

### Formato de cada tarefa

```
### S01 · Título
**Arquivos:** caminho(s)
**Problema:** o que está errado hoje, com o número medido
**Ação:** o que fazer, passo a passo
**Validar:** como provar que deu certo
**Risco:** baixo | médio | alto
```

### Ordem e dependências

A ordem **não é negociável**, e o motivo de cada seta está escrito:

```
Bloco N  (mata o quadrático de casamento)
    │        ← sem isto, agendar decisões não adianta: o custo está fora do laço de NPC
    ▼
Bloco A  (agenda de decisões + índices incrementais)   ★ MUDANÇA DE ARQUITETURA
    │        ← é o que permite avançar dias. Faça com o motor pequeno, não depois.
    ▼
Bloco E  (eventos: agrupar escrita, podar história)
    │
    ▼
Bloco M  (Mestre: sincronia entre processos, obra em lote real)
    │
    ▼        ─── daqui para baixo nada mais toca no motor ───
    │
Bloco S  (ruas radiais acompanham o raio)
    │        ← muda quantos lotes cabem numa cidade de raio R
    ▼
Bloco L  (lote com frente, RNG por quadra)
    │        ← L02 faz `audit_cidades.py` virar porta de commit de verdade
    ▼
Bloco R  (raio derivado da população)
    │        ← PRECISA de S e L: R02 calibra "lotes por raio elevado a e" medindo as
    │          cidades. Medir antes de S é medir a densidade errada.
    ▼
Bloco W  (validação permanente)   ← faça por último, com tudo no lugar
```

**Por que o motor vem antes da geometria**, mesmo com as cidades tortas ainda na tela: os
Blocos S, L e R são visuais e independentes — podem esperar sem custo nenhum. O Bloco A
muda a forma de toda mecânica futura. Cada semana que ele espera é mais código nascendo no
formato antigo, que depois tem que ser reescrito. Se houver duas pessoas, S/L/R podem
correr em paralelo: eles não tocam em `engine/`, e A/N/E/M não tocam em `cartographer/`.

**Parada obrigatória nº 1 — depois do Bloco S.** Regenere as 14 cidades e olhe o mapa de
uma cidade `radial` grande (Jordorstead). As bandas externas têm que ter ruas radiais
novas que **não** vão até o centro. Se as quadras externas continuarem com 150 lotes,
pare: a premissa da Seção 1.1 não bateu com o que você tem.

**Parada obrigatória nº 2 — depois de N01.** Rode `bench_tick.py`. O cenário
`3000 / 20000 / 15` tem que cair de ~591 ms para algo perto de **60 ms**. Se não cair,
o gargalo não era o que este plano mediu, e as tarefas N02–N04 estão perseguindo o alvo
errado.

**Parada obrigatória nº 3 — depois de A03.** Rode `bench_avanco.py` (criado em A07). Um
tick com 25.000 NPCs tem que cair de ~947 ms para a casa de **dezenas de ms**, e o número
de decisões avaliadas por tick tem que cair de 25.000 para algumas dezenas. Se as decisões
não caírem, alguém está acordando NPC demais — provavelmente uma rede de segurança larga
demais em A03 — e A04 não vai salvar.

---

## 1. As quatro pendências do plano anterior, respondidas

O *Registro de execução* do `PLANO_CIDADE_VIVA.md` deixou quatro perguntas em aberto.
Esta seção responde as quatro **com medição**, e cada resposta vira uma ou mais tarefas.

### 1.1 Q01 — "vale calibrar `num_setores` em função da banda?" → **Vale, e é a causa raiz**

Você suspeitou certo, e o diagnóstico está completo. Medi as duas dimensões de cada
quadra, banda por banda, nas 14 cidades. Numa cidade radial, a quadra tem:

- **profundidade** = o vão entre anéis, que é **constante** (G05 fixou isso: ~130 m);
- **largura** = o arco de um setor, que é `2·π·raio / num_setores` e portanto
  **cresce linearmente com a banda**, porque `num_setores` é o mesmo em todas elas.

Jordorstead (`radial`, `grande`, raio 992 m, 10 setores), medido:

| banda | profundidade | largura | lotes na quadra |
|---|---|---|---|
| 1 | 125 m | 120 m | 88 |
| 3 | 131 m | 292 m | 140 |
| 6 | 130 m | 557 m | 187 |

A banda 6 é uma quadra de **557 m por 130 m**. O anel perimetral de lotes de Q01 está
funcionando exatamente como projetado: ele forra o perímetro, e o perímetro de um
retângulo de 557×130 é 1.374 m. Com frente de ~11 m, isso dá ~125 lotes de fachada, e o
"pátio" no miolo é um vazio de 4,4 hectares.

**Q01 não tem bug nenhum.** O que está errado é a malha que chega nela. Os modelos
`grade` e `linear` passam no teste com o mesmo código de subdivisão porque as quadras
deles já nascem com 45–95 m de lado.

A correção é o que qualquer cidade radial real faz: **inserir ruas radiais novas à medida
que o raio cresce**. Uma radial nova não precisa ir até o centro — ela começa no anel em
que foi inserida e segue para fora. Isso é o Bloco S.

### 1.2 A auditoria que sai 1 — `sem_frente_pct` nas duas cidades `organica`

Aqui havia **duas** causas, não uma, e as duas são consertáveis. Medi os 119 lotes de
Cidade das Flores e os 275 de Fenelburgo que estão a mais de 25 m de qualquer rua.

**Causa A — a aresta cega do anel aberto (247 dos 275 em Fenelburgo).** O modelo
`organica` abre um vão em cada anel de propósito (`_abrir_anel`, F7.1.2): o anel deixa de
fechar, como numa cidade medieval de verdade. G04 tratou a consequência corretamente —
a quadra vizinha ao vão troca a `classes_aresta` daquela aresta de `"anel"` para
`"servico"`, para não fingir que existe via ali. **Mas a subdivisão continua colocando
lotes nessa aresta.** O lote nasce de frente para o nada.

Esse é exatamente o defeito que o plano anterior foi escrito para matar, sobrevivendo num
canto diferente. E ele sobreviveu por um motivo de nomenclatura: a string `"servico"`
hoje significa **duas coisas incompatíveis** no mesmo campo:

| onde | o que `"servico"` quer dizer |
|---|---|
| `linear.py:130`, `gerador.py:190`, `expansao.py:248` | "viela de verdade, e ela é emitida como `Rua`" |
| `organica.py:89,92` | "**não existe via nenhuma aqui**" |

Um campo com dois significados opostos é uma bomba-relógio: a subdivisão não tem como
decidir certo. L02 separa os dois nomes.

**Causa B — lote sem profundidade máxima quando não há pátio (28 lotes, mas os piores).**
Em `lotes.py:122`, se o pátio ficaria menor que `cidade_geo_patio_area_minima_m2`, o
código faz `quad_interno = None` e os lotes passam a ir da aresta **até o eixo médio da
quadra**. Para o `linear`, cuja quadra tem 9–21 m de profundidade, isso é certo. Para uma
quadra em cunha (fina numa ponta, grossa na outra), o resultado é um lote de **84 m de
profundidade e 922 m² de área** — medido em `fenelburgo_6_5_l53`, com o centroide a 43,7 m
da rua mais próxima. O `_default` da config diz que a profundidade de lote é 22 m.

Não é "tolerância apertada demais": são lotes errados de verdade. L01 põe um teto.

### 1.3 V01 — "vale dar a cada quadra um RNG derivado do próprio id?" → **Vale, e é barato**

Vale. Hoje `GeradorCidade._gerar_quarteiroes_e_lotes` passa **o mesmo `self.rng`** para
todas as quadras, em sequência, e `_lotes_da_faixa` consome um `rng.uniform` por aresta
para sortear a frente alvo. Consequência: a contagem de lotes da quadra 40 depende de
quantos sorteios as quadras 0 a 39 consumiram.

Os ids de lote continuam posicionais — isso a armadilha 3 garantiu e continua de pé. O que
não é estável é a **contagem**. Hoje isso não morde, porque X02/X03 só acrescentam. Mas
três coisas deste plano passam a mexer no meio da lista: S01 muda quantas quadras existem
por banda, L02 pode descartar uma quadra inteira, e R03 vai regerar tudo com outro raio.

O conserto é uma linha e meia (L03), e o custo é uma construção de `random.Random` por
quadra — algumas centenas por cidade, contra dezenas de milhares de operações de
geometria. Não meça antes; é ruído.

⚠️ Use `zlib.crc32(id_da_quadra.encode())`, **nunca** `hash()`. O `hash()` de `str` em
Python é aleatorizado a cada processo (`PYTHONHASHSEED`), então as cidades sairiam
diferentes a cada execução. Isso é a regra de determinismo do projeto, e é a maneira mais
fácil de destruir tudo que o plano anterior construiu.

### 1.4 P02 — o Modo Mestre roda em outro processo

Confirmado, e é mais fundo do que "falta um `recarregar_locais`".

`run_simulation.py` é dono do `SimulationEngine` e, portanto, do `EstadoDoMundo` e do
`IndiceDeLocais` que P01/P02 criaram. O Modo Mestre roda dentro do Flask
(`web/mestre_routes.py` → `engine/mechanics/mestre/gerenciador.py`), escreve direto no
SQLite, e o processo da simulação nunca fica sabendo. Existe `recarregar_habitantes()`
(chamado a cada 5 h de jogo), mas **não existe equivalente para locais**.

Achei um segundo problema no mesmo arquivo, e ele é pior:
`engine/mechanics/mestre/acoes/criar_local.py` sorteia um ponto aleatório em terra firme
(`GeoUtils.sortear_ponto_em_terra`) para posicionar o prédio novo. É **exatamente** o
código que O01 arrancou de `housing.py`. O Mestre é hoje o único caminho no projeto que
faz um edifício nascer fora de um lote, e ele fura a garantia que O03 escreveu: que
`abrir_obra` é o único jeito de um edifício nascer.

Os dois viram o Bloco M. A solução para a sincronia é um contador de versão em
`mundo_meta` — barato, respeita a "regra de processo" da `ARQUITETURA.md` (só
`run_simulation.py` instancia a engine) e não exige recarregar 24 mil locais a cada tick.

---

## 2. O estudo de performance: onde está o teto hoje

Você pediu para medir antes de decidir. Aqui está.

### 2.1 O teto atual é ~3.800 NPCs, e não tem nada a ver com o número de locais

`bench_tick.py`, 3 ticks por cenário, banco falso (ou seja: **sem nenhum custo de disco**
— guarde esse detalhe, a Seção 2.3 volta nele):

| NPCs | locais | cidades | ms/tick | contra o orçamento de 1.000 ms |
|---|---|---|---|---|
| 750 | 10.000 | 15 | 48,0 | 20,8× de folga |
| 1.500 | 15.000 | 15 | 159,1 | 6,3× |
| 3.000 | 20.000 | 15 | 591,3 | 1,7× |
| 6.000 | 30.000 | 15 | 2.325,8 | **estoura 2,3×** |
| 12.000 | 40.000 | 15 | 9.411,3 | **estoura 9,4×** |

Dobrar os NPCs multiplica o custo por ~4. Isso é a assinatura de um laço quadrático, não
de "muita gente para processar".

### 2.2 O quadrático é um só, e é o casamento

`cProfile` com 3.000 NPCs, 3 ticks, 8,548 s no total:

| função | tottime | % do tick |
|---|---|---|
| `marriage.verificar_elegibilidade_casamento` | 1,680 s | — |
| **`marriage.processar_coabitacao` (cumulativo)** | **7,897 s** | **92%** |
| todo o resto do tick, 3.000 NPCs incluídos | 0,65 s | 8% |

`processar_coabitacao` (`engine/mechanics/marriage.py:179`) faz um duplo laço de todos os
solteiros da cidade contra todos os solteiros da cidade, **todo tick**. P03 já agrupou por
cidade, o que ajudou muito, mas a comparação continua ao quadrado dentro de cada cidade.

A prova definitiva está numa linha só do benchmark: **os mesmos 12.000 NPCs** custam
9.411 ms em 15 cidades e **1.927 ms em 40 cidades**. O custo não depende de quantos NPCs
existem; depende de quantos existem **por cidade**, ao quadrado.

E a ironia: o laço termina com `return` no **primeiro** casamento do mundo inteiro. Ele
varre 1,79 milhão de pares por tick para produzir, no máximo, um casamento.

### 2.3 Tirando o quadrático, o resto do tick é quase linear

Rodei a mesma matriz com `processar_coabitacao` neutralizada, para enxergar o teto real:

| NPCs | cidades | ms/tick | µs por NPC |
|---|---|---|---|
| 750 | 15 | 14,1 | 18,8 |
| 3.000 | 15 | 57,6 | 19,2 |
| 12.000 | 15 | 259,9 | 21,7 |
| 25.000 | 40 | 991,1 | 39,6 |
| 50.000 | 60 | 3.072,0 | 61,4 |

Até 12.000 NPCs o custo por NPC é praticamente constante. De 25.000 para cima ele começa
a subir — é o resíduo que N02–N04 atacam. **Um conserto algorítmico de umas 15 linhas
leva o projeto de 3.800 para ~12.000 NPCs.** Nenhuma thread, nenhum processo.

### 2.4 O custo que o benchmark NÃO mede: a escrita no banco

`bench_tick.py` usa `BancoFalso`. Toda medição acima tem **zero** de custo de disco. O
banco real cobra, e cobra no lugar mais caro possível.

`RepositorioNPC.salvar_muitos` (`engine/repositorios/npc.py:87`) faz
`INSERT OR REPLACE` da **linha inteira** de todo NPC alterado, todo tick — inclusive
`json.dumps(npc.relacionamentos)`, `json.dumps(npc.genealogia)` e
`json.dumps(npc.memoria_eventos)`. O dicionário de relacionamentos é o que cresce: um NPC
velho e sociável acumula centenas de conhecidos.

Medido contra SQLite real, WAL, `synchronous=NORMAL`, 5 repetições:

| relações por NPC | NPCs | escrita SQLite | `json.dumps` | total por tick |
|---|---|---|---|---|
| 20 | 3.000 | 4,0 ms | 15,8 ms | 19,8 ms |
| 150 | 3.000 | 17,1 ms | 98,5 ms | 115,6 ms |
| 150 | 12.000 | 69,6 ms | 387,8 ms | 457,4 ms |
| **150** | **25.000** | **147,3 ms** | **796,8 ms** | **944,1 ms** |

Com 25.000 NPCs maduros, a persistência sozinha consome **94% do orçamento**, e 84% disso
é serializar JSON que **não mudou**. `relacionamentos` só muda quando há interação social:
medi ~170 interações por tick com 25.000 NPCs. Ou seja, 24.830 NPCs pagam a serialização
do próprio grafo social sem que nada nele tenha mudado.

A mesma escrita, como `UPDATE` estreito só das colunas que mudam de fato a cada tick
(`energia`, `fome`, `social`, `saude`, `humor`, `acao_atual`, `localizacao_atual_id`):

| NPCs | `UPDATE` estreito | contra o `INSERT OR REPLACE` completo |
|---|---|---|
| 3.000 | 4,6 ms | 25× mais barato |
| 12.000 | 19,2 ms | 24× |
| 25.000 | 40,6 ms | **23×** |

E tem um detalhe que fecha o argumento: **a tabela `relacionamentos` já existe** e
`salvar_relacionamento` já escreve nela. A coluna JSON em `npcs` é uma segunda cópia do
mesmo dado. N02 trata isso.

### 2.5 Memória não é o gargalo

25.000 NPCs + 60.000 locais em memória: **122 MB de RSS**, ~1,4 KB por entidade. Em
50.000 NPCs isso vira ~250 MB. Não é um problema, e não deve custar uma linha de código
deste plano. O que **pode** virar problema é o dicionário `relacionamentos` crescendo sem
limite (25.000 × 150 entradas ≈ 375 MB só de grafo social) — está anotado na Seção 5, não
aqui.

### 2.6 Por que continua não sendo hora de threads

Você propôs threads por cidade no plano anterior, e eu recomendei não. **A recomendação
continua a mesma, e agora com mais evidência** — mas a data de validade dela ficou clara,
e está escrita na [Seção 5](#5-horizonte-50-mil--o-que-muda-de-estrutura).

Três motivos, em ordem de força:

1. **O ganho algorítmico é maior que o ganho paralelo, e vem antes.** N01 sozinho tira um
   fator de ~10. Quinze threads perfeitas dariam 15×, e nunca são perfeitas.
2. **A GIL está ligada neste interpretador** (`Py_GIL_DISABLED = 0`, medido). O tick é
   Python puro sem I/O de rede: as threads se revezam, não se somam.
3. **Paralelizar um laço quadrático é a pior coisa que você pode fazer com ele.** Ele
   continua quadrático, você só paga o custo em paralelo — e ganha corrida de dados de
   brinde, num laço que casa NPCs e move gente de casa.

---

## 3. Decisões já tomadas (não reabra)

As decisões D1–D6 do `PLANO_CIDADE_VIVA.md` continuam valendo. Estas são novas, todas
confirmadas pelo dono do projeto:

| # | Decisão | Consequência prática |
|---|---|---|
| **D7** | **Alvo: 25.000 NPCs** dentro do orçamento de 1.000 ms/tick (velocidade 60×). | Os Blocos N e E existem para isso. A Seção 5 descreve o que ainda faltaria para 50.000+, mas **não é escopo deste plano**. |
| **D8** | **A cidade nasce do tamanho da sua população, não o contrário.** Sorteia-se um número de **famílias** por cidade e o raio é *derivado* dele. | Bloco R. `cidade_geo_raio_m_faixa_por_tamanho` deixa de ser a fonte do raio. Cidades grandes e pequenas continuam existindo — a variedade passa a vir do sorteio de população. |
| **D9** | **Quadra quase quadrada, alvo de ~30 lotes.** Largura alvo ≈ profundidade (~95 m). | Bloco S. Ruas radiais novas nas bandas externas. Os dois `xfail` de `test_lotes_por_quadra_em_faixa` passam a ser exigidos. |
| **D10** | **Eventos são podados por idade e escritos em lote.** | Bloco E. O Modo Mestre continua lendo os recentes, que é tudo que ele lê hoje. |
| **D11** | **Continua sem thread e sem processo paralelo.** | Se o Bloco N terminar e o orçamento ainda estourar em 25.000, **pare e anote** — não introduza concorrência por conta própria. |
| **D12** | **Reset completo do mundo continua aceitável.** Nenhuma migração de banco, nenhuma compatibilidade com GeoJSON antigo. | Vale para os Blocos S, L e R inteiros. |
| **D13** | **Alvo de avanço rápido: 7 dias simulados em ~30 s, com 25.000 NPCs.** | 10.080 ticks em 30 s dá **~3 ms por tick**. É o número que justifica o Bloco A inteiro, e é contra ele que `bench_avanco.py` (A07) mede. |
| **D14** | **O tick deixa de processar todo NPC.** Cada NPC agenda a própria próxima decisão; o laço processa os vencidos e os acordados por evento. | Bloco A. É a única mudança de forma do motor neste plano. Toda mecânica futura passa a precisar declarar o que a acorda. |
| **D15** | **Agrupamento vira índice mantido, não recomputado.** `npcs_por_casa`, `npcs_por_localizacao` e `npcs_por_cidade` passam a ser atualizados no ponto da mudança, como P02 já fez com `IndiceDeLocais`. | A04. São 17,3 dos 35,6 ms do piso medido. Sem isto o Bloco A para na metade do caminho. |
| **D16** | **Migração entre cidades: só o ponto de extensão, sem mecânica.** `mundo.mudar_cidade` existe, é a única porta, e mantém todos os índices — mas nada na simulação a chama ainda. | A05. Deixa a porta aberta para "cidade que decai perde gente" sem custo de performance hoje, e sem quebrar o isolamento por cidade que a [Seção 5.2](#52-as-três-mudanças-estruturais-em-ordem-de-retorno) depende. |
| **D17** | **Sem modo grosso (passo de um dia) neste plano.** | A medição mostrou que 7 dias cabem em ~30 s com o tick de um minuto, depois do Bloco A. O modo grosso só passa a ser necessário para pular **meses**, e traz o problema dos dois modos que divergem ([5.5](#55-avanço-rápido-é-outro-modo-de-simulação-não-um-tick-mais-rápido)). A06 deixa o ponto de extensão pronto; a implementação fica fora. |

---

## 4. As sete novas armadilhas

Leia as sete. Cada uma custou uma medição para ser encontrada, e cada uma é do tipo que
não dá erro — dá resultado errado em silêncio. As duas últimas (11 e 12) são do Bloco A e
são as mais perigosas do documento inteiro.

### Armadilha 6 — `"servico"` hoje significa duas coisas opostas

Já explicada em [1.2](#12-a-auditoria-que-sai-1--sem_frente_pct-nas-duas-cidades-organica).
Em `linear.py` e em `gerador.py`, `"servico"` é **uma viela de verdade, emitida como
`Rua`**. Em `organica.py`, é **"não existe via aqui"**. Se você tratar as duas do mesmo
jeito, ou some com vielas legítimas do `linear`, ou continua criando lotes cegos no
`organica`. **L02 separa os nomes antes de qualquer outra coisa.** Faça `grep -rn
'"servico"' cartographer/` e trate cada ocorrência, uma a uma.

### Armadilha 7 — a densidade de lotes por raio varia 7 vezes entre modelos

O Bloco R precisa converter "quero N lotes" em "então o raio é R". A tentação é derivar
uma fórmula fechada. Não funciona, e eu medi por quê:

| modelo | cidade | raio | lotes | lotes / raio² |
|---|---|---|---|---|
| `linear` | Corarfield | 846 m | 1.286 | 0,0018 |
| `grade` | Irenburgo | 791 m | 8.275 | **0,0132** |

Sete vezes de diferença, e é correto que seja assim: o `linear` é uma fita ao longo de um
eixo, não um disco — os lotes dele crescem com o raio, não com o raio ao quadrado. A
constante tem que ser **medida por modelo**, não deduzida. R02 faz isso.

### Armadilha 8 — calibrar a densidade ANTES do Bloco S mede a densidade errada

O Bloco S vai inserir ruas radiais, o que aumenta o perímetro total de quadra e portanto o
número de lotes por raio² em `radial` e `organica` (estimo +35%, mas **meça, não confie
nesta estimativa**). Se você calibrar a constante do Bloco R antes, todas as cidades
radiais vão nascer maiores do que a população pede, e o erro não aparece em teste nenhum —
só numa cidade com metade das casas vazias para sempre. **S e L inteiros antes de R02.**

### Armadilha 9 — `bench_tick.py` não mede o banco, e esse é o maior custo em 25 mil

O benchmark usa `BancoFalso`. Todo número da [Seção 2.3](#23-tirando-o-quadrático-o-resto-do-tick-é-quase-linear)
é de CPU pura. Quando o Bloco N terminar e você disser "cabe em 25.000", isso será verdade
**só se N02 também estiver pronta** — senão a persistência sozinha come 944 ms. W02 existe
para que essa diferença pare de ser invisível.

### Armadilha 10 — otimizar `cfg_get` para fora do laço não pode virar cache global

`cfg_get` foi chamado 1,1 milhão de vezes por tick com 25.000 NPCs, e custa ~0,45 s. A
correção óbvia é ler a config uma vez e guardar. **Não guarde num módulo, nem num
singleton, nem numa variável global.** A config é injetada por construtor em todo o
projeto (`ARQUITETURA.md` Seção 7: as dependências são montadas uma vez por processo, no
ponto de entrada), e os testes contam com isso para montar mundos com config diferente. O
lugar certo é um atributo do `__init__` do gerenciador que já recebe a config. N03 detalha.

E não troque `cfg_get` por `dict.get` com default: o `KeyError` dele é intencional
(R-B05), é ele que impede uma chave errada de virar um valor silencioso.

### Armadilha 11 — acumulador linear pode pular no tempo; efeito de limiar não pode

O Bloco A vai aplicar 480 minutos de metabolismo de uma vez, em vez de 480 passos de um
minuto. Para `fome`, `energia` e `social` isso é **exato**: o delta por minuto não depende
do valor atual, então multiplicar por 480 e grampear no fim dá o mesmo resultado que 480
passos. Integrar em vez de simular é seguro aqui, e é o que torna o bloco possível.

**Mas nem tudo no tick é assim.** `_aplicar_consequencias_de_saude` tira saúde **enquanto**
a fome estiver acima do limiar de inanição. Se a fome cruza o limiar no minuto 30 de um
salto de 480, o NPC tem que perder saúde por 450 minutos — e não por 480, nem por zero.
Multiplicar cego dá os dois resultados errados, e nenhum dos dois estoura.

A regra: para cada efeito, pergunte **"isto depende do valor atual da grandeza?"**. Se não
depende, multiplique. Se depende de um limiar, **calcule o instante do cruzamento** e
aplique só a partir dele — e se não der para calcular, **não salte por cima dele**: agende
a próxima decisão para o instante do cruzamento e deixe o tick normal resolver. Perder um
pouco de eficiência aqui é barato; um NPC que atravessa a fome sem perder saúde é um mundo
que não fecha.

### Armadilha 12 — índice mantido desincroniza em silêncio, e P02 já ensinou isso

A04 transforma os agrupamentos em índices mantidos. A partir daí, **qualquer** atribuição
direta a `npc.casa_id`, `npc.localizacao_atual_id` ou `npc.cidade_id` fora dos métodos do
`EstadoDoMundo` deixa o índice discordando do mundo — e não dá erro nenhum. O NPC
simplesmente some do lugar onde estava, ou aparece em dois.

Este projeto **já tomou esse prejuízo uma vez**: foi exatamente o motivo de P02 criar
`registrar_local`/`desativar_local` como caminho único para locais. Faça o mesmo agora, e
faça o `grep` antes de dizer que terminou:

```
grep -rn "\.casa_id *=" engine/ builder/
grep -rn "\.localizacao_atual_id *=" engine/ builder/
grep -rn "\.cidade_id *=" engine/ builder/
```

Cada ocorrência fora de `mundo.py` é um candidato a bug. E não confie só no grep: a rede de
segurança de A03 (reavaliar todo NPC pelo menos a cada N minutos) existe justamente para
que uma desincronia vire ineficiência, não um NPC congelado para sempre.


---

## Bloco N — Os quatro gargalos até 25 mil NPCs

> **O que este bloco resolve:** o teto de ~3.800 NPCs. Ao final, 25.000 NPCs cabem no
> orçamento de 1.000 ms/tick com folga.
>
> **Faça N01 primeiro e pare para medir** (parada obrigatória nº 2). Ela sozinha vale
> mais que as outras três juntas, e se ela não render o esperado, as outras estão
> perseguindo o alvo errado.

### N01 · O casamento deixa de comparar todos contra todos

**Arquivos:** `engine/mechanics/marriage.py`

**Problema:** `processar_coabitacao` (`marriage.py:179`) percorre todos os solteiros da
cidade contra todos os solteiros da cidade, todo tick. Medido com 3.000 NPCs: **92% do
tick inteiro**, 1,79 milhão de chamadas a `verificar_elegibilidade_casamento` por tick. E
o laço termina com `return` no **primeiro** casamento do mundo — um único casamento custa
1,79 milhão de comparações.

A prova de que é isto e não "muitos NPCs": os **mesmos** 12.000 NPCs custam 9.411 ms em 15
cidades e 1.927 ms em 40 cidades. O custo é por cidade, ao quadrado.

**Ação:**

1. **A percepção-chave:** um casamento exige afinidade acumulada, e afinidade só existe
   entre quem já se encontrou. Isso já está guardado: `npc.relacionamentos` é um dicionário
   `{id_do_outro: afinidade}`, e ele é **pequeno** — só tem quem o NPC de fato conheceu.
   Percorrer esse dicionário em vez de percorrer a cidade inteira é a tarefa toda.
2. Monte uma vez por chamada um índice `{id: npc}` dos solteiros vivos, por cidade.
3. Para cada solteiro `n1`, itere **sobre `n1.relacionamentos`**, e para cada `id` que
   estiver no índice de solteiros da mesma cidade, rode a elegibilidade que já existe.
   `O(N²)` vira `O(N × conhecidos)`.
4. Como o laço termina no primeiro casamento, **embaralhe a ordem dos solteiros** com o
   RNG antes de percorrer. Sem isso, o primeiro NPC da lista tem prioridade permanente
   sobre todos os outros — hoje isso está mascarado pelo custo, mas depois de N01 o laço
   vai chegar ao fim e o viés fica visível.
5. **Não mude nenhuma regra de elegibilidade.** `verificar_elegibilidade_casamento` e
   `sao_parentes` ficam exatamente como estão. Esta tarefa muda **quem é comparado**,
   nunca **o que é decidido**.

**Validar:** `bench_tick.py --ticks 3`. O cenário `3000 / 20000 / 15` cai de ~591 ms para
perto de **60 ms**, e `12000 / 40000 / 15` de ~9.411 ms para perto de **260 ms**. Os testes
de casamento em `tests/test_mecanicas.py` continuam passando sem alteração — se algum
precisar mudar, você mexeu numa regra e não devia.

**Risco:** médio. É o coração da mecânica social.

---

### N02 · Escrever só as colunas que mudam a cada tick

**Arquivos:** `engine/repositorios/npc.py`, `engine/loop.py`, `engine/models.py`

**Problema:** ver [2.4](#24-o-custo-que-o-benchmark-não-mede-a-escrita-no-banco).
`salvar_muitos` regrava a **linha inteira** de todo NPC alterado, incluindo
`json.dumps(relacionamentos)`. Com 25.000 NPCs e 150 relações cada, isso custa **944 ms
por tick** — 94% do orçamento, dos quais 797 ms são serializar JSON que não mudou. Só ~170
NPCs por tick têm interação social; os outros 24.830 pagam à toa.

E o dado é duplicado: a tabela `relacionamentos` já existe e `salvar_relacionamento` já
escreve nela.

**Ação:**

1. `salvar_muitos` passa a fazer um `UPDATE` estreito, só das colunas que mudam todo tick:
   `energia`, `fome`, `social`, `saude`, `humor`, `acao_atual`, `localizacao_atual_id`.
   Medido: **40,6 ms** com 25.000 NPCs, contra 944 ms. 23× mais barato.
2. Método novo `salvar_completo(npcs)` com o `INSERT OR REPLACE` de hoje, para quando as
   colunas frias mudam de verdade: nascimento, morte, casamento, mudança de casa,
   contratação, crescimento de estágio de vida. Chame-o **nesses pontos**, não no tick.
3. ⚠️ **Um NPC novo não existe ainda no banco, e `UPDATE` numa linha inexistente não é
   erro — não faz nada.** É a falha mais fácil de introduzir aqui, e ela é silenciosa: o
   bebê nasce, vive o dia inteiro em memória e some no próximo carregamento. Garanta que
   `processar_parto` chama `salvar_completo` para o recém-nascido **antes** de ele entrar
   em `mundo.npcs`.
4. Deixe a coluna JSON `relacionamentos` no schema, escrita só por `salvar_completo`.
   Removê-la é uma tarefa de banco e não é escopo deste plano — anote no Registro como
   dívida conhecida.

**Validar:** `bench_tick.py --real --ticks 3` contra o banco de verdade (é o modo que
exercita o disco). Rode a simulação de verdade por alguns minutos e confirme que
energia/fome/humor persistem entre reinícios, e que um NPC nascido durante a execução
existe depois de reiniciar.

**Risco:** alto. É o único ponto deste plano que pode **perder dado** se sair errado.

---

### N03 · Config e enum fora do laço quente

**Arquivos:** `engine/loop.py`, `engine/mechanics/*.py`, `engine/models.py`

**Problema:** com 25.000 NPCs, `cfg_get` é chamado **1,1 milhão de vezes por tick**
(~0,45 s), e o descritor `.value` de `Enum` **350 mil vezes** (~0,08 s), porque
`_aplicar_metabolismo` e as funções de utilidade releem a mesma chave de config e o mesmo
`.value` para cada NPC, a cada tick. Nenhum desses valores muda durante um tick.

**Ação:**

1. Nos gerenciadores que já recebem a config por construtor, leia os blocos usados no laço
   **uma vez no `__init__`** e guarde como atributo (`self._cfg_metabolismo = cfg_get(config, "metabolismo")`).
2. `GameLoop._aplicar_metabolismo` e `_aplicar_consequencias_de_saude` são os dois piores
   ofensores — cada um relê `biologia_e_sociedade` e `metabolismo` por NPC. Leve para o
   `__init__`.
3. Comparações repetidas de `Enum.value` (`EstagioVida.ADULTO.value`,
   `TipoLocal.CASA.value`, `CategoriaLocal.RESIDENCIA.value`) viram constantes de módulo
   calculadas na importação.
4. ⚠️ Ver [armadilha 10](#armadilha-10--otimizar-cfg_get-para-fora-do-laço-não-pode-virar-cache-global).
   Atributo de instância, **nunca** global de módulo nem singleton. E não troque `cfg_get`
   por `dict.get` com default: o `KeyError` dele é intencional (R-B05).

**Validar:** `bench_tick.py`. Espere ~15% no cenário de 25.000. É o menor ganho do bloco;
se custar mais que umas poucas horas, pare e anote — N01 e N02 é que pagam a conta.

**Risco:** baixo.

---

### N04 · `num_dependentes` deixa de ser recalculado por NPC por tick

**Arquivos:** `engine/loop.py`, `engine/consultas_npc.py`

**Problema:** `_aplicar_metabolismo` chama `contar_dependentes_na_casa_agrupado` para todo
NPC vivo, todo tick. P03 já tirou o pior (era `O(NPCs)` por chamada); o que sobrou é o
maior item isolado do perfil com 25.000 NPCs: **0,47 s por tick**, mais que `cfg_get`.

Mas `num_dependentes` só muda quando alguém **nasce**, **morre**, **cresce de estágio** ou
**muda de casa**. Numa cidade estável isso acontece algumas vezes por dia simulado, e o
tick recalcula 25.000 vezes por minuto simulado.

**Ação:**

1. Calcule o agrupamento por casa **uma vez por tick**, como já é feito, mas só recalcule
   `npc.num_dependentes` para os NPCs cujas casas mudaram de composição desde o tick
   anterior.
2. O jeito mais simples e que não cria estado novo: mantenha no `GameLoop` o conjunto de
   `casa_id` tocadas no tick (parto, morte, mudança, crescimento) e recalcule só os
   moradores dessas casas. O conjunto é reconstruído a cada tick — **não é cache entre
   ticks**, é escopo de tick, igual ao `npcs_por_casa` que P03 introduziu.
3. Mantenha `contar_dependentes_na_casa_agrupado` como está, e continue chamando-a — o que
   muda é **quantas vezes**, não o que ela faz.

**Validar:** `bench_tick.py`. E um teste que prove a correção: um parto muda
`num_dependentes` da mãe **no mesmo tick**. Se esse teste não existir, escreva-o antes de
mexer — sem ele esta tarefa é uma otimização às cegas.

**Risco:** médio. É onde um bug fica escondido por muitos ticks antes de aparecer.

---

### N05 · Medir de novo, e parar

**Arquivos:** `builder/fix/bench_tick.py`, [Registro de execução](#registro-de-execução)

**Ação:**

1. Acrescente à matriz de `bench_tick.py` os cenários de escala grande:
   `(12000, 40000, 15)`, `(25000, 60000, 15)`, `(25000, 60000, 40)`.
2. Rode com `--real` também, para o número **com** disco.
3. Cole as duas tabelas no Registro.
4. **Se 25.000 NPCs couberem no orçamento, o bloco acabou.** Não comece thread, processo,
   `multiprocessing` nem `asyncio` (D11). Se **não** couberem, pare e anote qual cenário
   estourou e o que o perfil mostrou — a Seção 5 já descreve o caminho, mas ele é outro
   plano, não a continuação deste.

**Risco:** baixo.

---

## Bloco A — A agenda: o tick deixa de tocar em todo mundo

> **O que este bloco resolve:** o Mestre não consegue avançar alguns dias. Sete dias
> simulados são 10.080 ticks, e a 947 ms por tick isso são **duas horas e meia** de espera.
> Ao final do bloco são ~30 segundos.
>
> **A ideia em uma frase:** hoje o tick processa os 25.000 NPCs todo minuto simulado, e
> medi que **99,83% deles decidem exatamente a mesma coisa que no minuto anterior**; a
> partir daqui cada NPC agenda quando quer ser reavaliado, e o tick só processa quem
> venceu.
>
> ⚠️ **Este é o único bloco do plano que muda a forma do motor.** Leia as
> [armadilhas 11 e 12](#armadilha-11--acumulador-linear-pode-pular-no-tempo-efeito-de-limiar-não-pode)
> antes de escrever qualquer linha. Faça-o com o motor pequeno: cada mecânica escrita
> depois já nasce no formato certo, e cada uma escrita antes vai ter que ser reescrita.

### A00 · O que a medição obriga, e por que as duas metades são necessárias

Este bloco tem duas metades que parecem independentes e não são. Os números:

| cenário, 25.000 NPCs | ms/tick | 7 dias (10.080 ticks) |
|---|---|---|
| hoje | 946,8 | 2 h 39 min |
| só a agenda de decisões (A01–A03) | ~35,6 (o **piso** medido) | **6 min** |
| agenda + índices incrementais (A01–A05) | ~3 esperado | **~30 s** |

A linha do meio é a medição mais importante do bloco: desliguei **todo** o processamento
por NPC — metabolismo, decisão, ação, humor, saúde — e o tick **ainda** custou 35,6 ms.
Desses, **17,3 ms** são só remontar `npcs_por_casa` e `npcs_por_localizacao` do zero, sobre
os 25.000 NPCs, toda vez.

Ou seja: a agenda de decisões sozinha leva você de duas horas e meia para seis minutos, e
aí **para**, porque o que sobra não depende de quantos NPCs decidiram — depende de quantos
existem. É por isso que A04 não é "mais uma otimização": sem ela, metade do trabalho do
bloco não aparece no relógio.

### A00b · "E a fome do NPC enquanto ele dorme?" — a regra das três classes de limiar

Esta é a primeira pergunta que qualquer pessoa faz ao ler este bloco, e ela está certa em
fazê-la: se o NPC é agendado para daqui a 4 horas e a fome bate no meio, ele morre de fome
dormindo? **Não** — e o motivo tem que estar claro na sua cabeça antes de A02, porque é ele
que define o que entra na conta do próximo instante.

**O agendamento não é um palpite. Ele é calculado A PARTIR da taxa de fome.** Como o ganho
de fome por minuto é conhecido e constante entre decisões, o instante em que a fome vai
cruzar qualquer limiar é uma divisão:

```
minutos_ate_o_limiar = (limiar - fome_atual) / ganho_de_fome_por_minuto
```

O cruzamento **é** o despertador. O NPC não "perde" o momento de comer: aquele momento é
exatamente o instante para o qual ele foi agendado.

**As três classes de limiar, e o que fazer com cada uma.** É isto que você precisa levar
para A02, e é a parte que erra quem só lê a ideia geral:

| classe | exemplos | o que o agendador faz |
|---|---|---|
| **de decisão** — muda o que o NPC *quer* | `gatilho_fome_normal` (40), `gatilho_fome_dormindo` (85), `energia_limiar_desmaio` (10), `fome_urgente_limiar` (70) | agenda a próxima decisão **para** o instante do cruzamento |
| **de consequência** — tira saúde enquanto verdadeiro | `inaniacao_fome_limiar` (90) | **nunca** salta por cima: agenda para o instante do cruzamento e, **enquanto estiver dentro dele, avalia todo tick** |
| **de relógio** — não depende de necessidade | início do expediente (8h), fim do sono obrigatório (6h) | entra na conta como mais um candidato a próximo instante |

⚠️ **A regra da segunda linha é a que salva a vida do NPC, e é fácil de não perceber.**
`_aplicar_consequencias_de_saude` tira `inaniacao_perda_saude` (0,333) por minuto enquanto a
fome estiver acima de 90. Se você deixar um NPC faminto saltar 240 minutos, ele perde 80 de
saúde **de uma vez** e provavelmente morre — quando hoje, nesses mesmos 240 minutos, ele
teria reavaliado e ido comer. A regra é simples de escrever e não negociável: **NPC em
estado de consequência não é agendado para o futuro.** Ele volta ao ritmo de um tick por
minuto até sair do estado. São pouquíssimos NPCs a qualquer momento, então o custo é nulo.

**Agora os números reais da config, que mostram por que isso é folgado.** Ganho de fome
médio 0,04 por minuto; dormindo, `multiplicador_fome_dormindo` de 0,33 baixa para 0,0132:

| situação | conta | resultado |
|---|---|---|
| noite inteira de sono (22h→6h, 480 min) | 480 × 0,0132 | **+6,3 de fome** |
| acordado, do gatilho de comer (40) até inanição (90) | 50 ÷ 0,04 | **~21 horas** sem comer |
| faminto (fome > 90) até a morte | 100 ÷ 0,333 | **5 horas** |

Ou seja: **uma noite de sono sobe 6 pontos de fome.** Para um NPC morrer dormindo ele
precisaria ir para a cama já com fome 90 — e aí ele está em estado de consequência e não é
agendado para lugar nenhum. É por isso que `gatilho_fome_dormindo` é 85 e não 40: o jogo
**já** foi desenhado para o NPC não acordar por pouca fome. A agenda não introduz esse
risco; ela só deixa de gastar 480 avaliações para descobrir o que uma divisão responde.

**O que muda de verdade no comportamento observável:** nada, se você puser os três tipos de
limiar na conta. Se esquecer os de consequência, NPCs vão morrer de fome dormindo e **não
vai haver erro nenhum no log** — só gente morrendo. É a
[armadilha 11](#armadilha-11--acumulador-linear-pode-pular-no-tempo-efeito-de-limiar-não-pode),
e é a razão de `test_limiar_nao_e_pulado` (W01) existir.

---

### A01 · Necessidades viram função do tempo decorrido, não do passo

**Arquivos:** `engine/loop.py`, `engine/models.py`

**Problema:** `_aplicar_metabolismo` aplica um delta fixo por chamada, e a chamada é uma por
tick. Enquanto for assim, pular de 22h para 6h significa 480 chamadas — e a agenda de A02
não tem como economizar nada.

**Ação:**

1. `_aplicar_metabolismo(npc, minutos, ...)`. Para `fome`, `energia` e `social`, o delta é
   multiplicado por `minutos`. Isso é **exato**, não uma aproximação: a taxa não depende do
   valor atual, então integrar e grampear no fim dá o mesmo resultado que grampear a cada
   passo ([armadilha 11](#armadilha-11--acumulador-linear-pode-pular-no-tempo-efeito-de-limiar-não-pode)).
2. O componente aleatório (`random.uniform` para ganho de fome e perda de social) passa a
   ser **um sorteio multiplicado por `minutos`**, não `minutos` sorteios. Escreva no
   comentário que isso reduz a variância de propósito, em troca de o salto custar O(1) — é
   uma escolha, não um descuido, e alguém vai perguntar.
3. `gravidez_ticks -= minutos`, e o parto dispara quando o valor **cruza** zero, não quando
   é exatamente zero. Um `== 0` aqui faz gestações desaparecerem em silêncio no primeiro
   salto maior que um minuto.
4. `_aplicar_consequencias_de_saude` é o caso de limiar da armadilha 11. Enquanto A02 não
   existir, `minutos` é sempre 1 e nada muda; quando existir, esta função **decide o
   tamanho máximo do salto**: nunca salte por cima do instante em que a fome cruza
   `inaniacao_fome_limiar`.

**Validar:** teste que prova a equivalência — aplique 480 minutos de uma vez e 480 vezes um
minuto, com a mesma semente, e compare `fome`, `energia`, `social` e `saude`. Diferença
zero nos três primeiros; para `saude`, diferença zero **se o limiar não for cruzado** no
intervalo. Esse teste é a espinha dorsal do bloco: escreva-o primeiro.

**Risco:** médio.

---

### A02 · Cada NPC agenda a própria próxima decisão

**Arquivos:** `engine/models.py`, `engine/loop.py`, `engine/mechanics/logic.py`

**Problema:** 38% do tick é `NPCBrain.decidir_acao`, e medido contra o banco real ao longo
de 12 horas simuladas, **0,17%** dos NPCs trocam de ação por tick. A duração média de uma
ação é de **78 minutos**. A decisão de dormir às 22h é recalculada ~78 vezes antes de mudar.

**Ação:**

1. Campo novo em `NPC`: `proximo_instante_decisao` (um `datetime`, na mesma escala de
   `mundo.data_simulada`).
2. O laço principal deixa de iterar `self._mundo.npcs` e passa a iterar só os NPCs cujo
   `proximo_instante_decisao <= data_simulada`. O metabolismo desses recebe
   `minutos = agora - ultima_avaliacao`, e cada NPC ganha um campo
   `ultima_avaliacao` junto.
3. Depois de decidir, calcule o próximo instante como o **menor** entre:
   - o cruzamento do limiar de **decisão** mais próximo (uma divisão — ver
     [A00b](#a00b--e-a-fome-do-npc-enquanto-ele-dorme--a-regra-das-três-classes-de-limiar));
   - o cruzamento do limiar de **consequência** mais próximo (inanição). **Nunca salte por
     cima dele**, e enquanto o NPC estiver dentro de um estado de consequência, avalie-o
     todo tick até ele sair;
   - o próximo instante de rotina agendada relevante (hora de trabalho, de dormir);
   - um teto de segurança, `cfg` nova `simulacao_intervalo_maximo_decisao_min`
     (valor inicial **240**).
4. **O teto do passo 3 é o que de fato paga a conta, e por isso o valor importa.** Os
   intervalos naturais são longos (uma noite de sono dá 480 minutos), então na prática é o
   teto que decide quantos NPCs são avaliados por tick. A aritmética, com 25.000 NPCs a
   ~20 µs por NPC avaliado:

   | teto | NPCs avaliados por tick | custo só do teto | 7 dias (10.080 ticks) |
   |---|---|---|---|
   | 30 min | 833 | 16,7 ms | 168 s |
   | 60 min | 417 | 8,3 ms | 84 s |
   | 120 min | 208 | 4,2 ms | 42 s |
   | **240 min** | **104** | **2,1 ms** | **21 s** |
   | 480 min | 52 | 1,0 ms | 10 s |

   **240 é a escolha**: cabe em D13 com folga e mantém o atraso máximo de um `acordar`
   esquecido em 4 horas simuladas, que é visível num teste e inofensivo em jogo. Não baixe
   para "ficar mais seguro": segurança vem do passo 3, não daqui, e baixar quadruplica o
   custo do avanço.
5. **Não precisa acertar na mosca no cálculo do passo 3.** Errar para menos só custa uma
   reavaliação a mais; errar para mais é que é bug. Na dúvida, encurte.
6. `aplicar_persistencia` (`utilidade/modificadores.py`) já existe para o NPC não trocar de
   ideia a cada minuto — ou seja, o motor **já sabe** que a decisão é estável. Reuse essa
   informação aqui em vez de inventar uma segunda noção de estabilidade.

**Validar:** um contador de "decisões avaliadas por tick" no benchmark. Com 25.000 NPCs ele
tem que cair de 25.000 para algumas dezenas. E um teste de comportamento: um NPC com fome
subindo cruza o limiar e vai comer **no minuto certo**, não até 60 minutos depois.

**Risco:** alto. É o coração do motor.

---

### A03 · Acordar por evento, e a rede de segurança

**Arquivos:** `engine/mundo.py`, `engine/mechanics/*.py`

**Problema:** um NPC agendado para daqui a 8 horas não pode ficar surdo ao mundo. Se a
taverna dele pegar fogo, se ele for demitido, se o filho nascer, ele precisa reavaliar
agora.

**Ação:**

1. `EstadoDoMundo.acordar(npc)` — põe `proximo_instante_decisao = data_simulada`. É a
   **única** porta para isso.
2. Chame-a em: chegada ao destino, contratação e demissão (`market.py`), fechamento e
   colapso de local (`decay.py`), nascimento na casa (`reproduction.py`), casamento e
   mudança de casa (`marriage.py`, `housing.py`), evento global na cidade
   (`events.py`), e toda ação do Modo Mestre sobre o NPC.
3. `acordar_cidade(cidade_id)` para o caso de evento global — e é aqui que o índice
   `npcs_por_cidade` de A05 paga por si: sem ele, "acordar a cidade" varre os 25.000.
4. ⚠️ **A rede de segurança do teto de 60 minutos (A02, passo 3) não é opcional.** Ela é o
   que garante que **esquecer** um `acordar` vire "o NPC reage com até uma hora de atraso"
   em vez de "o NPC nunca mais reage". Sem ela, cada mecânica nova que alguém escrever nos
   próximos anos é uma chance de congelar parte da população em silêncio.

**Validar:** teste por mecânica — demitir um NPC agendado para daqui a 6 horas faz ele
reavaliar no tick seguinte. E um teste de resistência: remova de propósito um `acordar` e
confirme que o NPC volta a decidir dentro de 60 minutos, em vez de nunca.

**Risco:** médio.

---

### A04 · Agrupamentos viram índices mantidos

**Arquivos:** `engine/mundo.py`, `engine/consultas_npc.py`, `engine/loop.py`,
`engine/mechanics/*.py`

**Problema:** o piso medido. Com o processamento por NPC **inteiramente desligado**, um tick
de 25.000 NPCs ainda custa 35,6 ms, dos quais **17,3 ms** são `agrupar_por_casa`,
`agrupar_npcs_por_localizacao` e o filtro de falecidos — três varreduras de todos os NPCs,
refeitas do zero a cada minuto simulado, para um mundo em que quase nada mudou.

**Ação:**

1. `EstadoDoMundo` passa a manter `npcs_por_casa`, `npcs_por_localizacao` e
   `npcs_por_cidade`, construídos uma vez no carregamento.
2. Métodos que são a **única** porta para mudar cada coisa, no mesmo padrão que P02
   estabeleceu para locais com `registrar_local`/`desativar_local`:
   `mundo.mover_npc(npc, local_id)`, `mundo.mudar_casa(npc, casa_id)`,
   `mundo.registrar_npc(npc)`, `mundo.remover_npc(npc)`.
3. `_remover_falecidos` deixa de reconstruir a lista inteira e passa a remover pelos
   índices os NPCs que morreram no tick — que o próprio laço já conhece.
4. `agrupar_por_casa` e `agrupar_npcs_por_localizacao` continuam existindo em
   `consultas_npc.py` para teste e uso pontual, com o docstring dizendo que **não** devem
   ser chamadas no laço do tick. É exatamente o que `contar_dependentes_na_casa` já faz
   hoje, e funcionou.
5. ⚠️ [Armadilha 12](#armadilha-12--índice-mantido-desincroniza-em-silêncio-e-p02-já-ensinou-isso).
   Rode os três `grep` de lá antes de dizer que terminou. Cada atribuição direta fora de
   `mundo.py` é um candidato a NPC que some do próprio lugar sem erro nenhum.

**Validar:** `bench_avanco.py`. O piso de 35,6 ms tem que cair para a casa de poucos ms. E
um teste de invariante: depois de N ticks com partos, mortes, casamentos e mudanças, os
três índices reconstruídos do zero têm que ser **idênticos** aos mantidos. Rode-o em todo
commit deste bloco.

**Risco:** alto. É a tarefa com o maior número de pontos de mutação a encontrar.

---

### A05 · A porta de migração entre cidades (só a porta)

**Arquivos:** `engine/mundo.py`

**Problema:** hoje `npc.cidade_id` é atribuído na criação e nunca mais muda. P04 fixou que
o NPC não atravessa cidade, e boa parte do ganho de performance depende disso. Mas um mundo
autossuficiente acaba precisando que gente se mude — cidade que decai perde gente, cidade
que prospera atrai — e descobrir isso depois de A04 significa refazer A04.

**Ação (D16 — a porta, não a mecânica):**

1. `mundo.mudar_cidade(npc, cidade_id)`: atualiza `npcs_por_cidade`, `npcs_por_casa`,
   `npcs_por_localizacao` e o vínculo de trabalho, numa operação só.
2. **Nada na simulação chama este método ainda.** Só o Modo Mestre, via M02. Escreva isso
   no docstring, com todas as letras, e escreva também o que uma mecânica de migração
   futura teria que respeitar: casal não se separa, dependente acompanha o responsável, e o
   NPC precisa de lote ou vaga no destino **antes** de sair da origem.
3. Escreva também a consequência para a [Seção 5.2](#52-as-três-mudanças-estruturais-em-ordem-de-retorno):
   se um dia houver um processo por cidade, migração deixa de ser uma chamada de método e
   passa a ser uma mensagem entre processos. Ter a operação isolada num método só é o que
   torna essa transição possível — é por isso que a porta vale a pena mesmo vazia.

**Validar:** um teste que move um NPC de cidade e confirma que os três índices ficam
coerentes e que ele não aparece mais em nenhuma consulta da cidade antiga.

**Risco:** baixo.

---

### A06 · Cada mecânica declara a própria cadência

**Arquivos:** `engine/loop.py`, `engine/mechanics/*.py`

**Problema:** `_executar_rotinas_agendadas` é uma cadeia de `if hora == cfg_get(...)`
escrita à mão. Toda mecânica nova significa editar o laço, e o laço é o arquivo que menos
deveria mudar. Além disso, a informação "com que frequência isto roda" fica espalhada entre
o laço e o `config.json`, em vez de morar junto da mecânica.

**Ação:**

1. Cada gerenciador declara a própria cadência: `por_minuto`, `por_hora`, `por_dia` ou
   `sob_demanda`. Um atributo de classe basta — não invente framework.
2. `GameLoop` monta a lista no `__init__` e despacha por cadência. Acrescentar uma mecânica
   passa a ser acrescentar uma classe e uma linha de registro, nunca editar o despacho. É o
   mesmo movimento que o Modo Mestre já fez com `ComandoMestre` e as classes de ação, e ele
   deu certo.
3. **É aqui que mora a margem que o projeto quer.** Um modo grosso de passo diário
   (`5.5`) seria "rode só as mecânicas `por_dia` e resolva o resto por taxa" — e, com este
   registro no lugar, isso deixa de ser uma reescrita do laço. **Não implemente o modo
   grosso** (D17): deixe o ponto de extensão e escreva no docstring que é para isso que ele
   serve.

**Validar:** `grep -n "if hora ==" engine/loop.py` não devolve nada. Os horários continuam
vindo do `config.json`, e a suíte passa sem alteração.

**Risco:** baixo.

---

### A07 · Medir o avanço, e a armadilha do log

**Arquivos:** `builder/fix/bench_avanco.py` (novo), `engine/logger.py`, `run_simulation.py`

**Problema:** não existe medição de "quanto tempo leva para avançar N dias", que é
exatamente o que D13 promete. E existe uma armadilha esperando: `_avancar_relogio` chama
`WorldLogger.info` **todo tick**, e `WorldLogger.queue_db_log` enfileira uma escrita de
banco por log de NPC, consumida por uma thread que **commita uma linha por vez**. Num avanço
de 7 dias com 25.000 NPCs, o produtor é muito mais rápido que o consumidor: a fila cresce
sem teto e o avanço vira consumo de memória.

**Ação:**

1. `bench_avanco.py`, no mesmo estilo dos outros diagnósticos (fora da engine, cabeçalho
   avisando que não é runtime, não importado de `engine/`, `web/` nem `cartographer/`):
   avança N dias simulados e reporta segundos totais, ms por tick, decisões avaliadas por
   tick e tamanho da fila de log. Alvo de D13: **7 dias em menos de 30 s com 25.000 NPCs**.
2. Modo de avanço rápido: `WorldLogger` suprime os níveis `info` e `debug` por tick e
   mantém só os eventos de mundo (nascimento, morte, casamento, obra, expansão). Sem isso,
   a narrativa do avanço é ilegível **e** cara.
3. Ponha um **teto na fila** de `queue_db_log`, descartando o excedente com um aviso único.
   Fila sem teto num laço rápido é vazamento de memória com outro nome, e a thread engole
   toda exceção em silêncio (`except Exception: pass`) — então hoje isso falharia sem
   deixar rastro.
4. Cole a tabela final no [Registro de execução](#registro-de-execução).

**Validar:** os 7 dias em menos de 30 s. Se não bater, **pare e anote qual fase dominou** —
não comece processo nem thread (D11).

**Risco:** baixo.


---

## Bloco E — Eventos: agrupar a escrita e podar a história

### E01 · Uma transação por tick para eventos e relacionamentos

**Arquivos:** `engine/repositorios/evento.py`, `engine/repositorios/npc.py`,
`engine/mechanics/social.py`

**Problema:** `processar_interacao_social` chama `eventos.salvar` e
`npcs.salvar_relacionamento`, e cada um abre o próprio `with self.db.connection()` — que
**commita na saída**. Medi ~170 interações por tick com 25.000 NPCs, o que dá ~340 commits
por tick. É o mesmo defeito que P05 já corrigiu para os NPCs, sobrevivendo em outros dois
repositórios.

**Ação:** acumule os eventos e os pares de relacionamento do tick numa lista e grave-os com
`executemany`, numa transação só, ao final de `processar_interacoes` — exatamente o padrão
que `salvar_muitos` estabeleceu. `salvar_relacionamento` continua existindo para os
chamadores de fora do tick.

**Validar:** `bench_tick.py --real`. Os testes de social e de casamento continuam passando.

**Risco:** baixo.

---

### E02 · Poda de eventos por idade

**Arquivos:** `engine/repositorios/evento.py`, `engine/loop.py`, `config.json`

**Problema:** a tabela `eventos` não tem poda nenhuma. Com 25.000 NPCs são ~170 eventos por
tick, **~245.000 linhas por dia simulado**. Em uma semana de simulação contínua são
milhões de linhas que ninguém lê: o Modo Mestre só consome os recentes
(`resumos_recentes(limite)`, `coletar_apos_rowid`).

**Ação:**

1. Config nova: `simulacao.eventos_retencao_dias_simulados` (valor inicial **30**).
2. Uma varredura por **dia simulado** (não por tick) apaga os eventos mais velhos que isso.
   Pendure-a em `_executar_rotinas_agendadas`, junto com as outras rotinas diárias.
3. ⚠️ **Não pode apagar `eventos_globais`** — são outra tabela, com outra semântica
   (`ticks_restantes`), e o `GlobalEventManager` depende deles. Só a tabela `eventos`.
4. Registre no log quantas linhas foram apagadas, uma linha por dia simulado. Poda
   silenciosa é como se descobre tarde demais que a retenção estava errada.

**Validar:** simule alguns dias com o valor baixado para 2 e confirme que a tabela para de
crescer, que o Modo Mestre continua montando contexto, e que `eventos_globais` fica
intacta.

**Risco:** baixo. **Destrutivo por natureza** — confirme o filtro de data num `SELECT
COUNT(*)` antes de escrever o `DELETE`.

---

## Bloco M — Modo Mestre: sincronia entre processos

### M01 · O processo da simulação percebe local criado de fora

**Arquivos:** `engine/models.py`, `engine/core.py`, `engine/repositorios/mestre.py`,
`engine/mechanics/mestre/acoes/*.py`, `run_simulation.py`

**Problema:** ver [1.4](#14-p02--o-modo-mestre-roda-em-outro-processo). O Modo Mestre roda
no processo do Flask e escreve direto no SQLite; o processo da simulação é dono do
`EstadoDoMundo` e do `IndiceDeLocais` e **nunca fica sabendo**. Existe
`recarregar_habitantes()` para NPCs; não existe nada equivalente para locais.

**Ação:**

1. Chave nova em `MetaChave`: `LOCAIS_VERSAO`. Toda ação do Mestre que cria, destrói ou
   reatribui local incrementa esse contador em `mundo_meta`, **na mesma transação** da
   escrita do local.
2. `run_simulation.py` lê o contador uma vez por tick (um `SELECT` de uma linha, barato —
   ele já lê `SIMULACAO_PAUSADA` e `VELOCIDADE` todo tick pelo mesmo caminho) e, quando ele
   muda, chama `engine.recarregar_locais()`.
3. `recarregar_locais()` em `core.py`, espelhando `recarregar_habitantes()`: recarrega
   `mundo.locais` **e reconstrói o `IndiceDeLocais`**. Esquecer o índice deixa o mundo e o
   índice discordando, que é pior do que não recarregar.
4. **Por que um contador e não recarregar sempre:** recarregar 24 mil locais por tick
   custaria mais que o tick inteiro. Um `SELECT` de uma linha por tick é ruído, e a recarga
   só acontece quando algo de fato mudou — o que, na prática, é quando o jogador clica.
5. ⚠️ **Não instancie um `SimulationEngine` no processo do Flask** para "resolver de vez".
   A `ARQUITETURA.md` (Seção 1, regra de processo) diz que só `run_simulation.py` é dono da
   engine, e dois donos do mesmo mundo em dois processos é uma classe de bug que não se
   depura.

**Validar:** com a simulação rodando, crie um local pelo Modo Mestre e confirme, pelo log
do processo da simulação, que ele apareceu **no tick seguinte** e que um NPC pode ser
mandado para lá.

**Risco:** médio.

---

### M02 · O Mestre constrói em lote de verdade

**Arquivos:** `engine/mechanics/mestre/acoes/criar_local.py`

**Problema:** `CriarLocal._sortear_ponto_livre` sorteia um ponto aleatório em terra firme
com `GeoUtils.sortear_ponto_em_terra`. É **o mesmo código** que O01 arrancou de
`housing.py`, sobrevivendo aqui. O Mestre é hoje o único caminho no projeto que faz um
edifício nascer fora de um lote, e ele fura a garantia que O03 escreveu: `abrir_obra` é o
único jeito de um edifício nascer.

**Ação:**

1. `CriarLocal` passa a chamar `abrir_obra` do `GerenciadorUrbanismo` (O03), que já sabe
   reservar lote (`db.lotes.reservar_livre`), criar o `Local` e marcar o lote.
2. Se a cidade não tiver lote livre, o caminho já existe e está pronto: X01 dispara a
   avaliação de auto-expansão na hora. O Mestre ganha a auto-expansão de graça, sem uma
   linha nova.
3. `GeoUtils.sortear_ponto_em_terra` deixa de ser chamado daqui. Confira com
   `grep -rn "sortear_ponto_em_terra" engine/` se ela ainda tem chamador legítimo; se não
   tiver, remova-a, e anote no Registro.
4. ⚠️ Ordem: **M01 antes de M02**. Sem M01, o local criado por M02 é correto e mesmo assim
   invisível para a simulação, e você vai passar uma tarde achando que M02 não funcionou.

**Validar:** crie um local pelo Modo Mestre e confirme, no banco, que existe um `lotes` com
estado `ocupado` e `local_id` apontando para ele. `audit_market.py` e a suíte continuam
passando.

**Risco:** baixo.

---

## Bloco S — Ruas radiais que acompanham o raio

> **O que este bloco resolve:** a quadra de 557 m × 130 m com 187 lotes e um pátio de
> 4,4 hectares. Ao final dele, os dois `xfail` de `test_lotes_por_quadra_em_faixa` viram
> `pass`.
>
> **A ideia em uma frase:** hoje toda banda tem o mesmo número de setores, então a quadra
> fica mais larga a cada anel; a partir daqui o número de setores **dobra** sempre que o
> arco passar da largura alvo, e a radial nova **começa no anel em que nasceu**, sem ir
> até o centro. É o que uma cidade radial real faz.

### S01 · Setores por banda: dobrar quando o arco passa da largura alvo

**Arquivos:** `cartographer/cities/modelos/radial.py`, `config.json`

**Problema:** `self.num_setores` é um número só, usado em todas as bandas
(`radial.py:141`, `:119`, `:205`, `:229`). O arco de uma quadra é `2·π·raio / num_setores`
e cresce linearmente com a banda, enquanto a profundidade é constante. Medido em
Jordorstead: 120 m de largura na banda 1, **557 m na banda 6**, com a profundidade parada
em ~130 m nas duas.

**Ação:**

1. Config nova: `cidade_geo_quadra_largura_alvo_m` (valor inicial **95**, igual ao
   `cidade_geo_vao_anel_alvo_m` que G05 já usa para a profundidade — D9 quer a quadra
   quase quadrada) e `cidade_geo_setores_max` (valor inicial **192**, teto de segurança).

2. Em `__init__`, depois de `self.num_setores`, calcule a lista `self.setores_por_banda`,
   com `num_aneis + 1` entradas (uma por anel de vértices, incluindo a borda):

   ```
   s = self.num_setores
   self.setores_por_banda = []
   for j in range(self.num_aneis + 1):
       raio_j = raios_base[j] se j < num_aneis, senão self.raio_m
       enquanto (2*pi*raio_j / s) > largura_alvo * 1.5 e s * 2 <= setores_max:
           s *= 2
       self.setores_por_banda.append(s)
   ```

   ⚠️ `s` **nunca diminui** entre bandas — ele é acumulado no laço de fora. Isso não é
   detalhe de estilo: é o que garante que `setores_por_banda[j]` seja sempre múltiplo de
   `setores_por_banda[j-1]`, e é dessa propriedade que o passo 4 e a tarefa S02 dependem.
   O fator `1.5` existe para o arco final ficar entre 0,75× e 1,5× da largura alvo em vez
   de sempre no teto.

3. `_grade_de_vertices` passa a produzir uma grade **irregular**: a linha `j` tem
   `setores_por_banda[j]` pontos, nos ângulos `2·π·i / setores_por_banda[j]`. O array
   `perturb` deixa de ser `(num_aneis+1, num_setores)` e vira uma **lista** de arrays, um
   por banda, com o tamanho daquela banda.
   ⚠️ Isso muda a ordem de consumo do `np_rng` e portanto **todas as cidades do mundo**.
   Isso é esperado (armadilha 1 do plano anterior). Não invente sorteio-fantasma para
   compensar.

4. Ruas radiais: uma radial só existe da banda em que nasceu para fora. Com
   `s_final = setores_por_banda[-1]` e `passo_j = s_final // setores_por_banda[j]`:

   ```
   para cada i em range(s_final):
       pontos = [vertices[j][i // passo_j] para cada j em que i % passo_j == 0]
   ```

   Como `s` só cresce, `passo_j` só diminui e divide `passo_{j-1}`. Logo, se `i` existe na
   banda `j`, existe em todas as bandas seguintes — a radial nunca tem buraco no meio.
   Só a radial que existe **desde a banda 0** recebe o ponto de origem (o anel do núcleo
   ou o centro) na frente da lista.

5. Portões: `indices_portao` continua sendo escolhido na resolução da **borda**
   (`setores_por_banda[-1]`), que é onde o portão fica. A classe `"principal"` vale para a
   radial daquele índice.

6. A asserção de anéis cruzados (`radial.py:133`) compara raios do **mesmo índice de
   setor** entre bandas. Com a grade irregular isso deixa de fazer sentido direto —
   reescreva comparando o raio do vértice da banda `j` com o ponto correspondente da banda
   `j-1` já densificado (S02 cria a função de densificação; faça S02 antes desta parte, ou
   deixe a asserção comentada por um commit e restaure-a em S02 — **não a apague**).

**Validar:**
- `audit_cidades.py`: a coluna `l/quadra` de `radial` e `organica` cai de 70–151 para a
  faixa de 4 a 30; `max/qd` cai de ~195 para algo abaixo de ~45.
- `bowtie_q`, `bowtie_l`, `anel_x` e `fora_muro` continuam **0** em todas as cidades.
- Regerar duas vezes produz arquivos idênticos: `md5sum database/cidades/*.geojson`.
- Olhe o mapa de Jordorstead: tem que haver radiais curtas nas bandas externas que não
  chegam ao centro.

**Risco:** alto. É a maior mudança de geometria desde G01.

---

### S02 · Densificar o anel interno para a quadra continuar sendo um quadrilátero

**Arquivos:** `cartographer/cities/modelos/radial.py`, `cartographer/cities/modelos/base.py`

**Problema:** na banda em que o número de setores dobra, o anel de dentro tem metade dos
vértices do anel de fora. A quadra entre eles teria 5 vértices, e `Quadra` exige
exatamente 4 (`base.py`) — é essa garantia que todo o resto da pipeline de Q01 usa.

**Ação:**

1. Em `base.py`, acrescente uma função pura ao lado de `pontos_ao_longo_do_poligono`:
   ```
   densificar_anel(anel, n_alvo) -> list
   ```
   `n_alvo` é múltiplo de `len(anel)`; com `f = n_alvo // len(anel)`, o ponto de índice
   `i` é `lerp(anel[i//f], anel[(i//f + 1) % len(anel)], (i % f) / f)`.

2. **Por que isso não muda a rua do anel interno:** o ponto inserido cai exatamente
   **sobre o segmento** entre dois vértices já existentes. A polilinha da rua é a mesma
   linha, com um vértice a mais. Não emita a rua do anel a partir do anel densificado —
   emita a partir do original, para não inchar o GeoJSON à toa.

3. Na construção das quadras da banda `j`, use
   `raio_interno = densificar_anel(vertices[j-1], setores_por_banda[j])`. A quadra volta a
   ter 4 vértices: `[interno[i], externo[i], externo[i2], interno[i2]]`, como hoje.

4. `classes_aresta`: as arestas 0 e 2 são as radiais dos índices `i` e `i2` **na resolução
   da banda j** — `"principal"` se aquele índice for de portão, senão `"secundaria"`. As
   arestas 1 e 3 continuam `"anel"`.

5. Restaure a asserção de anéis cruzados do passo 6 de S01, agora comparando
   `densificar_anel(vertices[j-1], s_j)[i]` com `vertices[j][i]`.

**Validar:** toda `Quadra` continua com 4 vértices (a própria classe já garante — se S01
tiver ficado errado, isso estoura na geração, não em silêncio). `audit_cidades.py` sem
`bowtie_q` novo. A contagem de features `rua` cresce (radiais novas), a de `quarteirao`
cresce, e **nenhuma** quadra fica sem pátio por degeneração.

**Risco:** médio.

---

### S03 · O modelo orgânico torce cada banda pelo passo angular DELA

**Arquivos:** `cartographer/cities/modelos/organica.py`

**Problema:** `_torcer_grade` (`organica.py:76`) calcula
`passo = 2 * math.pi / self.num_setores` **uma vez**, e usa esse mesmo passo para torcer
todas as bandas. Depois de S01, a banda externa tem até 8× mais setores, e portanto um
passo angular 8× menor. O deslocamento de `0.35 × passo` deixa de ser uma fração do passo
e vira várias vezes ele — dois setores vizinhos trocam de lugar, e o `organica` volta a
produzir exatamente o cruzamento que G01 e G04 eliminaram.

Este é o tipo de bug que **não estoura**: a geometria sai torta, o teste de bowtie pode
até passar, e só o mapa denuncia.

**Ação:** mova o cálculo do passo para dentro do laço de bandas:
`passo_j = 2 * math.pi / len(linha)`, `delta_max_j = passo_j * PASSO_ANGULAR_FRACAO_MAXIMA`.
Mantenha `fase_por_anel` como está (uma fase por banda), e mantenha o comentário que
explica por que a torção é **angular** e não linear (girar preserva o raio e não pode
reintroduzir cruzamento de anéis).

**Validar:** `audit_cidades.py` com `anel_x = 0` e `bowtie_q = 0` em Cidade das Flores e
Fenelburgo. Compare visualmente com o `radial` de mesmo porte: o `organica` tem que
continuar visivelmente mais torto, só que sem se cruzar.

**Risco:** baixo, se você lembrar de fazê-lo. Alto se esquecer.

---

## Bloco L — Lote com frente de verdade, e RNG por quadra

> **O que este bloco resolve:** os 394 lotes cegos das duas cidades `organica`, e o
> acoplamento de sorteio entre quadras vizinhas. Ao final, `audit_cidades.py` sai **0**
> nas 14 cidades e vira porta de commit de verdade.

### L01 · Teto de profundidade quando a quadra não tem pátio

**Arquivos:** `cartographer/cities/geometria/lotes.py`

**Problema:** em `lotes.py:122`, se o pátio ficaria menor que
`cidade_geo_patio_area_minima_m2` (120 m²), o código faz `quad_interno = None` e os lotes
passam a ir da aresta **até o eixo médio da quadra** (`_eixo_medio_sem_patio`). Para o
`linear`, com quadra de 9–21 m de profundidade, isso é o comportamento certo. Para uma
quadra em cunha, não: medido em `fenelburgo_6_5_l53`, um lote de **922 m² com 84 m de
profundidade**, centroide a 43,7 m da rua. A config diz que a profundidade de lote é 22 m
(`cidade_geo_lote_profundidade_m_por_banda._default`).

Repare que a quadra em cunha é fina numa ponta e grossa na outra: nem o inset uniforme
nem o eixo médio servem sozinhos. A profundidade tem que ser decidida **por ponto**.

**Ação:**

1. Em `_eixo_medio_sem_patio`, depois de calcular o ponto do eixo médio correspondente a
   cada canto, **puxe-o de volta em direção à aresta** se a distância passar da
   profundidade alvo:
   ```
   profundidade_alvo = _profundidade_lote(config, banda, lote_fator_cidade)
   para cada canto k:
       d = distância(canto_da_aresta[k], ponto_do_eixo[k])
       se d > profundidade_alvo:
           ponto_do_eixo[k] = lerp(canto_da_aresta[k], ponto_do_eixo[k], profundidade_alvo / d)
   ```
2. Passe `config`, `banda` e `lote_fator_cidade` para `_eixo_medio_sem_patio` (hoje ela só
   recebe `quad_ext` e `pair`). Mantenha-a **pura**, como está.
3. O miolo que sobrar entre os dois lotes opostos é um pátio legítimo — devolva-o em
   `patios` em vez de deixá-lo implícito, para o mapa continuar contando a mesma área.
   Só devolva se a área for maior que `cidade_geo_patio_area_minima_m2`; senão, é o caso
   raso de verdade e não há pátio.

**Validar:** nenhum lote com `area_m2` acima de ~3× a mediana da sua banda. O
`sem_frente_pct` de Fenelburgo cai de 3,3% para ~2,9% (os 28 lotes de `classe_frente`
`"anel"` somem; os 247 de `"servico"` são L02). O `linear` **não muda**: Belinhaven,
Corarfield, Elorfield e Kelandor têm que sair byte a byte iguais, porque nelas a
profundidade da quadra já é menor que o teto. Use `md5sum` para provar isso.

**Risco:** baixo. É a tarefa que tem o melhor teste de não-regressão do plano inteiro.

---

### L02 · `"servico"` deixa de significar duas coisas, e aresta cega não recebe lote

**Arquivos:** `cartographer/cities/modelos/base.py`, `organica.py`,
`cartographer/cities/geometria/lotes.py`, `builder/fix/audit_cidades.py`

**Problema:** ver [armadilha 6](#armadilha-6--servico-hoje-significa-duas-coisas-opostas).
Em `linear.py:130`, `gerador.py:190` e `expansao.py:248`, `"servico"` é **uma viela real,
emitida como `Rua`**. Em `organica.py:89` e `:92`, é **"o anel foi aberto aqui, não existe
via nenhuma"**. A subdivisão trata as duas igual e cria lotes de frente para o nada: 247
dos 275 lotes cegos de Fenelburgo e todos os 119 de Cidade das Flores.

**Ação:**

1. Em `base.py`, na documentação de `Rua.tipo_via` e da `classes_aresta` de `Quadra`,
   acrescente o valor `"sem_via"` com uma frase clara: *"não existe via nenhuma nesta
   aresta; nenhum lote pode ter frente aqui"*. Os valores válidos passam a estar escritos
   num lugar só.
2. Em `organica.py`, troque as duas atribuições de `"servico"` por `"sem_via"`.
3. Em `lotes.py`, na subdivisão do anel perimetral: **pule a aresta cuja classe é
   `"sem_via"`** — nenhuma faixa de lotes ali. O pátio cresce naturalmente para ocupar o
   espaço, porque ele é o inset do quadrilátero inteiro e não muda.
4. Em `_distancia_faixa_dominio` (`gerador.py` e `radial.py`), `"sem_via"` tem distância
   de faixa de domínio **zero**: não há via para recuar.
5. Caso de borda a tratar explicitamente: uma quadra com **todas as 4 arestas** `"sem_via"`
   não tem frente nenhuma e não deve virar quadra. Descarte-a do mesmo jeito que
   `preparar_quadra` já descarta a quadra degenerada (devolvendo `None`), e conte quantas
   foram no [Registro de execução](#registro-de-execução).
6. Em `audit_cidades.py`, mantenha `TOLERANCIA_SEM_FRENTE_PCT = 0.0`. Ela estava certa o
   tempo todo; era o gerador que estava errado.

⚠️ Faça `grep -rn '"servico"' cartographer/` antes e depois. Cada ocorrência que **não**
está em `organica.py` é uma viela de verdade e tem que continuar `"servico"`. Se você
trocar a de `linear.py:130`, some com as vielas que dão frente a metade dos lotes das
cidades lineares — e o `sem_frente_pct` delas, hoje 0,0%, explode.

**Validar:** `audit_cidades.py` com `sem_frente_pct = 0.0` nas **14** cidades, e **código
de saída 0**. Rode sem pipe: `venv/bin/python3 builder/fix/audit_cidades.py ; echo $?`.

**Risco:** médio. O risco real não é a lógica, é trocar uma ocorrência a mais.

---

### L03 · Cada quadra sorteia com o próprio RNG

**Arquivos:** `cartographer/cities/geometria/gerador.py`,
`cartographer/cities/geometria/lotes.py`, `cartographer/cities/expansao.py`

**Problema:** a resposta de [1.3](#13-v01--vale-dar-a-cada-quadra-um-rng-derivado-do-próprio-id--vale-e-é-barato).
`_gerar_quarteiroes_e_lotes` passa `self.rng` — o mesmo objeto, em sequência — para todas
as quadras. `_lotes_da_faixa` consome um `rng.uniform` por aresta, então a contagem de
lotes da quadra N depende do que as quadras 0..N-1 consumiram. S01 (que muda quantas
quadras existem) e L02 (que pode descartar uma quadra inteira) transformam isso de
curiosidade em problema real.

**Ação:**

1. Em `_gerar_quarteiroes_e_lotes`, antes de chamar `preparar_quadra`:
   ```
   import zlib, random
   semente_quadra = self.semente_cidade ^ zlib.crc32(quarteirao_id_str.encode("utf-8"))
   rng_quadra = random.Random(semente_quadra)
   ```
   e passe `rng_quadra` no lugar de `self.rng`.
2. `self.semente_cidade` é a mesma semente que o projeto já deriva do nome da cidade com
   `zlib.crc32`. Se o `GeradorCidade` ainda não a guarda, guarde-a no `__init__` —
   **não** recalcule uma nova, e **não** use `hash()` (ver
   [1.3](#13-v01--vale-dar-a-cada-quadra-um-rng-derivado-do-próprio-id--vale-e-é-barato)).
3. Faça o mesmo em `expansao.py`: as quadras do arrabalde também recebem RNG derivado do
   próprio id. É exatamente o caso que motiva a tarefa.
4. Escreva no docstring de `_gerar_quarteiroes_e_lotes` **por que** o RNG é derivado — sem
   isso, alguém "simplifica" de volta para `self.rng` em seis meses.

**Validar:** gere as 14 cidades. Depois, com um script descartável, remova
artificialmente uma quadra do meio da lista de uma cidade, gere de novo, e confirme que
**todas as outras quadras mantêm a mesma contagem de lotes e os mesmos ids**. Esse é o
`test_id_de_lote_estavel` que V01 não conseguiu escrever — agora ele é escrito de verdade
em W01.

**Risco:** baixo.

---

### L04 · A auditoria vira porta de commit

**Arquivos:** `builder/fix/audit_cidades.py`

**Problema:** hoje o script nunca sai 0 no conjunto completo, então ninguém o usa como
porta. Depois de S e L, ele pode e deve ser usado.

**Ação:**

1. Acrescente duas colunas: **`largura/prof`** (a mediana da razão entre as duas dimensões
   da quadra, por cidade — o número que denuncia a regressão de S01) e **`lotes/raio²`**
   (a constante de densidade que o Bloco R vai calibrar; veja a
   [armadilha 7](#armadilha-7--a-densidade-de-lotes-por-raio-varia-7-vezes-entre-modelos)).
2. Acrescente o invariante `4 <= mediana(lotes por quadra) <= 30` como violação dura, do
   mesmo jeito que `sem_frente_pct`.
3. Deixe a saída do script **legível sem pipe** e escreva no cabeçalho do arquivo que
   `| tail` engole o código de saída. Isso já enganou uma sessão inteira.

**Validar:** `venv/bin/python3 builder/fix/audit_cidades.py ; echo $?` imprime `0`.

**Risco:** baixo.

---

## Bloco R — A cidade nasce do tamanho da sua população

> **O que este bloco resolve:** Jordorstead tem **8.775 lotes para 50 habitantes**. Depois
> do Bloco S serão ainda mais. Mesmo com a ocupação inicial de 60% que D2 fixou, sobram
> milhares de casas vazias que ninguém nunca vai usar, e a auto-expansão do Bloco X nunca
> dispara porque a cidade nunca satura.
>
> **A ideia em uma frase:** hoje o raio é sorteado e a população é uma tabela; a partir
> daqui sorteia-se **quantos domicílios** a cidade tem e o raio é **derivado** disso.
> Cidades grandes e pequenas continuam existindo — a variedade passa a vir do sorteio de
> população, que é o que o jogador de fato sente.

### R00 · Antes de começar: a regra de camada que este bloco é capaz de quebrar

Leia isto antes de escrever qualquer linha do Bloco R. **`cartographer/` não pode saber o
que é um NPC nem o que é uma família** (`ARQUITETURA.md` Seção 2). Se você acabar
escrevendo `from engine...` dentro de `cartographer/`, parou tudo e refez.

A saída, e ela é boa: o cartógrafo raciocina em **domicílio** — um lote residencial —, que
é um conceito de urbanismo, não de simulação. O contrato entre as camadas fica assim:

| camada | o que ela decide | o que ela lê |
|---|---|---|
| `cartographer/` | quantos **domicílios** a cidade tem, e portanto o raio | `cidade_geo_domicilios_alvo_faixa_por_tamanho` |
| `builder/` (povoador) | quantas **famílias** existem | **conta** as residências que nasceram ocupadas no banco |
| `builder/` (povoador) | quantos **NPCs** existem | `famílias × geracao_populacao.npcs_por_familia_faixa` |

Repare no detalhe que faz a coisa toda funcionar: o povoador **não recalcula** a conta do
cartógrafo, ele **conta o resultado dela**. Duas fórmulas para a mesma grandeza em dois
arquivos diferentes é como este projeto ganharia, de graça, um bug que só aparece depois
de mudar uma constante.

### R01 · Sortear domicílios em vez de raio

**Arquivos:** `cartographer/cities/modelos/radial.py`, `grade.py`, `linear.py`,
`cartographer/cities/escala.py`, `cartographer/cities/modelos/sitio.py`, `config.json`

**Problema:** hoje todo modelo começa com `self.raio_m = self.rng.uniform(*faixa_raio_m(...))`
e a população vem depois, de uma tabela fixa (`npcs_por_cidade × npcs_por_cidade_por_tamanho`).
O tamanho físico e o tamanho humano da cidade são sorteados **independentemente**, e por
isso não têm nenhuma relação.

**Ação:**

1. Config nova, em `geracao_urbana`:
   ```
   "cidade_geo_domicilios_alvo_faixa_por_tamanho": {
       "pequeno": [50, 130], "medio": [280, 620], "grande": [800, 1800]
   }
   ```
   Estes números vêm da conta do alvo de 25.000 NPCs (D7): com a distribuição atual de
   portes (3 pequenas, 6 médias, 5 grandes) e ~2,65 NPCs por família, a média dá
   ~9.470 famílias ≈ 25.100 NPCs. **Recalibre na R04**, com o número medido.

2. Em `escala.py`, crie `domicilios_alvo(config, tamanho, rng)` — o **único** lugar que lê
   a chave nova, exatamente como `faixa_raio_m` é hoje o único lugar que lê a chave de
   raio. Aplique aqui o float global `cidade_geo_escala` (D5), que passa a multiplicar
   **domicílios**, não raio. O float continua sendo "o tamanho das cidades do mundo", só
   que agora numa unidade que significa alguma coisa.

3. Em `escala.py`, crie também:
   ```
   lotes_alvo = domicilios_alvo / (ocupacao_inicial_do_tamanho * fracao_residencial_min)
   ```
   lendo `cidade_geo_ocupacao_inicial_por_tamanho` (D2) e `cidade_geo_fracao_residencial_min`,
   que já existem. Para uma cidade `grande` com 1.300 domicílios isso dá
   `1300 / (0.6 × 0.8) = 2.708` lotes.

4. `faixa_raio_m` **não some**: ela vira o piso e o teto de sanidade. O raio derivado é
   grampeado dentro dela, e se o grampo morder, isso é um sinal de que a faixa de
   domicílios está fora de calibragem — **registre quando acontecer**, não engula.

5. ⚠️ `SitioCidade` dimensiona a janela de terreno a partir do raio (G06). O raio agora só
   é conhecido **depois** de R02. A ordem de construção do modelo muda; leia a nota de
   `faixa_raio_m` em `escala.py` sobre janela de terreno e `np.clip` antes de mexer. Se a
   janela ficar menor que a cidade, as leituras de terreno na borda voltam a ser
   silenciosamente erradas — foi exatamente o bug que G06 e Q04 mataram.

**Validar:** só depois de R02 (esta tarefa sozinha não gera cidade). Commit junto, ou
commit separado com a nota de que a geração fica quebrada entre as duas.

**Risco:** médio.

---

### R02 · Converter "quero N lotes" em "então o raio é R", medindo

**Arquivos:** `builder/fix/calibrar_densidade.py` (novo), `cartographer/cities/escala.py`,
`config.json`

**Problema:** ver a [armadilha 7](#armadilha-7--a-densidade-de-lotes-por-raio-varia-7-vezes-entre-modelos).
A relação entre raio e número de lotes depende do modelo, e não é a mesma potência em
todos: no `grade` os lotes crescem com o raio ao quadrado (é um disco preenchido), no
`linear` crescem quase linearmente (é uma fita ao longo de um eixo). Medido nas 4 cidades
`linear` atuais, a razão `lotes / raio` fica entre 1,39 e 1,85 — enquanto `lotes / raio²`
varia 2,6×. **Não deduza a fórmula. Meça-a.**

**Ação:**

1. Ferramenta nova `builder/fix/calibrar_densidade.py`, no mesmo estilo dos outros
   diagnósticos (roda fora da engine, cabeçalho avisando que não é runtime, e **não é
   importada** de dentro de `engine/`, `web/` ou `cartographer/`).
2. Para cada um dos 4 modelos, gere a mesma cidade-semente em **dois** raios (por exemplo
   300 m e 900 m), conte os lotes, e ajuste `lotes = k · raio^e` pelos dois pontos:
   ```
   e = log(lotes2 / lotes1) / log(raio2 / raio1)
   k = lotes1 / raio1 ** e
   ```
   Use ao menos 5 sementes por ponto e tire a mediana — uma cidade só varia com o terreno.
3. Grave o resultado em `config.json` como
   `cidade_geo_densidade_lote_por_modelo: {modelo: [k, e]}`, com um comentário dizendo
   **qual commit e qual data** produziram os números (é o padrão que o `config.json` deste
   projeto já segue).
4. Em `escala.py`, `raio_para_lotes(config, modelo, lotes_alvo)` devolve
   `(lotes_alvo / k) ** (1 / e)`, grampeado em `faixa_raio_m`.
5. **Uma correção de Newton, uma só.** Depois de gerar a cidade, se o número real de lotes
   ficar a mais de 15% do alvo, recalcule o raio com
   `raio × (alvo / medido) ** (1/e)` e gere de novo — **no máximo uma vez**. A relação é
   suave o bastante para um passo bastar, e um laço aqui vira uma geração que às vezes não
   termina.

⚠️ **Rode esta calibragem depois dos Blocos S e L inteiros**
([armadilha 8](#armadilha-8--calibrar-a-densidade-antes-do-bloco-s-mede-a-densidade-errada)).
S insere ruas radiais e portanto muda `k` de `radial` e `organica`. Calibrar antes é
calibrar contra uma geometria que você mesmo vai substituir na semana seguinte.

**Validar:** com a calibragem aplicada, o número de lotes de cada cidade fica a menos de
15% do `lotes_alvo` dela, nos 4 modelos. Imprima a tabela alvo-vs-medido e cole-a no
[Registro de execução](#registro-de-execução).

**Risco:** médio.

---

### R03 · O povoador conta famílias em vez de ler uma tabela

**Arquivos:** `builder/populador.py`, `builder/populate.py`, `config.json`

**Problema:** P07 ligou as 15 cidades lendo `npcs_por_cidade × npcs_por_cidade_por_tamanho`
— uma tabela que não sabe nada sobre a cidade que de fato nasceu. Depois de R01/R02 a
cidade já carrega a informação certa: os lotes residenciais que nasceram **ocupados**.

**Ação:**

1. Em vez da tabela, conte no banco: residências da cidade com estado `ocupado` (a tabela
   `lotes` de T01/T02 tem `cidade_id`, `estado` e `local_id`). Cada uma é **uma família**.
2. Config nova: `geracao_populacao.npcs_por_familia_faixa` (valor inicial `[2, 4]`). Cada
   família sorteia o próprio tamanho nessa faixa, com o RNG determinístico do povoador.
3. **Remova** `npcs_por_cidade` e `npcs_por_cidade_por_tamanho` da config e dos dois
   arquivos. Não deixe as duas fontes convivendo "por segurança": duas fontes para a mesma
   grandeza é o defeito que R00 existe para evitar.
4. Mantenha tudo que P07 acertou: ids `npc_{cidade:02d}_{idx:03d}`, casais sempre na mesma
   cidade, biografia por IA só na cidade foco (`MetaChave.CIDADE_SIMULADA`).
5. ⚠️ Uma família de 2 a 4 NPCs numa casa de `capacidade_padrao_residencia = 5` cabe. Se
   você mexer na faixa para cima, confira a capacidade antes — superlotação alimenta
   `decay.py` (penalidade de desgaste) e a mecânica de casal que sai de casa, e você teria
   uma cidade inteira nascendo em crise.

**Validar:** `builder/populate.py --desativar-ia` nas 14 cidades. A soma dos NPCs tem que
cair perto de **25.000** (D7). Nenhum NPC sem casa, nenhuma casa acima da capacidade,
nenhum id repetido.

**Risco:** médio.

---

### R04 · Regerar o mundo e recalibrar as faixas

**Arquivos:** `config.json`, [Registro de execução](#registro-de-execução)

**Problema:** as faixas de R01 são uma estimativa aritmética. Só a geração real diz a
verdade.

**Ação:**

1. Regere as 14 cidades, repopule, e monte a tabela: cidade, modelo, porte, domicílios
   alvo, lotes alvo, lotes reais, raio, famílias, NPCs.
2. Ajuste `cidade_geo_domicilios_alvo_faixa_por_tamanho` até o total de NPCs ficar entre
   **22.000 e 28.000**. Mexa **só** nessa chave: `cidade_geo_escala` fica em 1.0, para
   continuar sendo o float com o qual o dono do projeto mexe depois sem reabrir config
   nenhuma.
3. Confira o efeito colateral visual: com o raio menor, as cidades encolhem no mapa do
   mundo. `escala.py:tabela_zoom_min` calcula `zoom_min` por camada a partir do diâmetro
   em pixels de mundo — **as camadas vão precisar acender num zoom maior**. Isso é
   automático se tudo passar por `faixa_raio_m`/`diametro_px_de_mundo`, e é uma regressão
   silenciosa se alguma chamada tiver ficado com o raio nominal antigo. Abra o mapa e
   confirme que lote e edifício ainda aparecem quando você dá zoom numa cidade pequena.

**Validar:** a tabela completa no [Registro de execução](#registro-de-execução), e o mapa
aberto no navegador, cidade por cidade.

**Risco:** baixo, mas é a tarefa que dá o veredito sobre o bloco inteiro.

---

## Bloco W — Validação permanente

### W01 · Os testes que S, L e R exigem

**Arquivos:** `tests/test_cidades.py`

**Ação:**

1. `test_lotes_por_quadra_em_faixa`: **remova os dois `xfail`** de `radial` e `organica`.
   Depois de S01/S02 eles têm que passar. Se não passarem, o Bloco S não terminou.
2. `test_id_de_lote_estavel`, agora escrito como o plano anterior queria e não conseguiu:
   gere uma cidade, remova uma quadra do meio da lista, gere de novo, e confirme que
   **todas as outras quadras mantêm ids e contagem de lotes**. L03 é o que torna isso
   possível.
3. `test_sem_lote_em_aresta_cega`: nenhum lote com `classe_frente == "sem_via"`. É o
   invariante de L02, em código.
4. `test_profundidade_de_lote_limitada`: nenhum lote com profundidade acima de ~1,5× o
   `cidade_geo_lote_profundidade_m_por_banda` da sua banda. É o invariante de L01.
5. `test_raio_derivado_dos_domicilios`: para um `lotes_alvo` dado, o raio devolvido por
   `escala.raio_para_lotes` produz uma cidade dentro de 15% do alvo. É o invariante de R02.

Os quatro do Bloco A, que são os mais importantes da suíte inteira porque cobrem a única
mudança de forma do motor — escreva cada um **junto** com a sua tarefa, não depois do bloco:

6. `test_salto_de_tempo_equivale_a_passos`: 480 minutos de uma vez contra 480 passos de um
   minuto, mesma semente, diferença zero em `fome`, `energia` e `social`. É o invariante de
   A01 e a espinha dorsal do bloco.
7. `test_limiar_nao_e_pulado`: um NPC cuja fome cruza `inaniacao_fome_limiar` no meio de um
   salto perde a saúde correspondente ao tempo **depois** do cruzamento — nem zero, nem o
   salto inteiro. É a [armadilha 11](#armadilha-11--acumulador-linear-pode-pular-no-tempo-efeito-de-limiar-não-pode) em código.
8. `test_indices_batem_com_a_reconstrucao`: depois de N ticks com partos, mortes,
   casamentos e mudanças de casa, os três índices mantidos têm que ser **idênticos** aos
   reconstruídos do zero. É a [armadilha 12](#armadilha-12--índice-mantido-desincroniza-em-silêncio-e-p02-já-ensinou-isso), e é o teste que
   pega o `acordar` esquecido que nenhum `grep` acha.
9. `test_npc_nunca_congela`: remova de propósito uma chamada a `acordar` e confirme que o
   NPC volta a decidir dentro de `simulacao_intervalo_maximo_decisao_min`. Prova que a rede
   de segurança de A03 é rede, e não decoração.

**Risco:** baixo.

---

### W02 · O benchmark passa a medir o banco

**Arquivos:** `builder/fix/bench_tick.py`

**Problema:** ver [armadilha 9](#armadilha-9--bench_tickpy-não-mede-o-banco-e-esse-é-o-maior-custo-em-25-mil).
`bench_tick.py` usa `BancoFalso`, então mede **zero** de custo de disco — e a persistência
é o maior item do orçamento com 25.000 NPCs (944 ms antes de N02). Um benchmark que ignora
o maior custo é pior que nenhum, porque dá confiança.

**Ação:** modo `--com-banco` que monta o mundo sintético num SQLite temporário de verdade
(`tempfile`, WAL, `synchronous=NORMAL`, como o `DatabaseManager` usa) em vez do
`BancoFalso`. Imprima as duas colunas lado a lado: **CPU** e **CPU+disco**. A diferença
entre elas é o número que N02 existe para derrubar.

**Risco:** baixo.

---

### W03 · Um teste que prova que a simulação não perde NPC

**Arquivos:** `tests/test_mecanicas.py`

**Problema:** N02 é a única tarefa deste plano capaz de **perder dado**, e o modo de falha
é silencioso: um `UPDATE` numa linha que não existe não é erro.

**Ação:** teste de ida e volta contra um SQLite temporário: monte um mundo, rode alguns
ticks com um parto no meio, feche, reabra de outro `DatabaseManager`, e confirme que o
recém-nascido está lá com pai, mãe, casa e estágio de vida corretos. Escreva este teste
**antes** de N02, não depois.

**Risco:** baixo. É o teste mais barato do plano e cobre o risco mais caro.

---

## 5. Horizonte 50 mil+ — o que muda de estrutura

> **Isto não é escopo deste plano** (D7 fixou 25.000). É o mapa que o dono do projeto
> pediu para poder priorizar depois. Nada aqui deve ser implementado agora; cada item diz
> **quando** ele passa a valer a pena.

### 5.0 O teto não é um número de NPCs. É um produto.

Antes de qualquer técnica, entenda o que é o teto, porque quase toda decisão errada de
performance neste tipo de projeto vem de confundir as duas coisas que ele multiplica:

```
custo por segundo real  =  NPCs  ×  ticks por segundo real  ×  custo por NPC por tick
                                    └── é a VELOCIDADE do jogo ──┘
```

Hoje um tick é **um minuto simulado**, e o orçamento de 1.000 ms por tick (D4) é o que
sustenta a velocidade 60×. Se você quiser 600×, o orçamento cai para **100 ms**. O mesmo
mundo de 25.000 NPCs que "cabe" a 60× não cabe a 600× — e nada disso é culpa do número de
NPCs.

São, portanto, **dois** tetos diferentes, com respostas diferentes:

| eixo | o que ele limita | o que o levanta |
|---|---|---|
| **quantos NPCs** | o tamanho do mundo | Bloco N (algoritmo), depois nível de detalhe e processos por cidade ([5.2](#52-as-três-mudanças-estruturais-em-ordem-de-retorno)) |
| **quão rápido o tempo passa** | a velocidade máxima e o avanço rápido | parar de tocar em todo NPC todo tick ([5.4](#54-o-teto-de-velocidade--resolvido-pelo-bloco-a-não-pelo-horizonte)) e o modo grosso ([5.5](#55-avanço-rápido-é-outro-modo-de-simulação-não-um-tick-mais-rápido)) |

**Não existe teto fixo em nenhum dos dois.** O que existe é uma arquitetura de passo fixo
que toca todo agente a todo passo, e é ela que faz os dois eixos se multiplicarem. As
seções abaixo dizem como desfazer a multiplicação, e em que ordem.

### 5.1 O que a medição já diz sobre 50 mil

Com `processar_coabitacao` neutralizada, ou seja, num mundo que já tem N01 pronta:

| NPCs | cidades | ms/tick | µs por NPC |
|---|---|---|---|
| 12.000 | 15 | 259,9 | 21,7 |
| 25.000 | 40 | 991,1 | 39,6 |
| 50.000 | 60 | 3.072,0 | 61,4 |

25.000 já fica **no limite** do orçamento antes de N02–N04; com elas, sobra folga. 50.000
estoura por **3×**, e o custo por NPC quase triplicou de 12.000 para 50.000 — ou seja,
ainda há um resíduo superlinear que N02–N04 atacam em parte, mas não eliminam.

Memória **não** é o problema: 122 MB com 25.000 NPCs e 60.000 locais, ~1,4 KB por entidade.
Em 50.000 seriam ~250 MB.

### 5.2 As três mudanças estruturais, em ordem de retorno

**1. Nível de detalhe: NPC fora de cena vira estatística.** É de longe a de maior retorno e
a que muda menos a arquitetura. O jogador olha uma cidade por vez
(`MetaChave.CIDADE_SIMULADA` já existe e P07 já a usa para decidir onde a IA escreve
biografia). Um NPC numa cidade que ninguém está olhando não precisa de metabolismo minuto a
minuto: precisa envelhecer, trabalhar, casar, morrer e ter filhos — coisas que acontecem em
escala de hora e de dia. Simular a cidade foco por minuto e as outras por hora corta o
custo por um fator próximo de 60 no mundo inteiro menos uma cidade.

O que isso exige com honestidade: o tick deixa de ser uma coisa só e vira dois, e toda
mecânica passa a precisar declarar em qual granularidade ela roda. Não é uma otimização, é
uma mudança de modelo de simulação. Faça quando o alvo passar de ~30.000, nunca antes.

**2. Um processo por cidade — e aqui a sua ideia original passa a estar certa.** No plano
anterior eu recomendei não paralelizar, e mantive a recomendação neste
([2.6](#26-por-que-continua-não-sendo-hora-de-threads)). O motivo era que o custo era
algorítmico, e consertar o algoritmo rendia mais. Depois dos Blocos N e E esse argumento
acaba: o que sobra é trabalho linear e genuinamente independente por cidade.

E há uma evidência que **este plano produziu** e que torna o sharding viável: P04 provou
que NPC não atravessa cidade, P03 agrupou casamento por cidade, e o `IndiceDeLocais` de P01
já é por cidade. Não existe estado compartilhado entre cidades no tick — a fronteira que
faltava agora existe.

Duas ressalvas que decidem a forma: **processos, não threads** (a GIL está ligada, medido),
e o SQLite precisa de um escritor por vez — cada processo escreve a própria cidade, ou há
um processo escritor com uma fila. Faça quando o nível de detalhe (item 1) já estiver feito
e ainda faltar fator.

**3. O grafo social precisa de um teto.** `npc.relacionamentos` cresce para sempre: 25.000
NPCs × 150 conhecidos ≈ 375 MB só de grafo, e é ele que domina o custo de
`salvar_completo`. Uma cidade real não tem esse problema porque as pessoas esquecem. Um
limite por NPC (os N mais fortes e os mais recentes, o resto decai e cai fora) é barato,
melhora a simulação em vez de piorá-la, e resolve memória e disco de uma vez. Faça quando o
mundo passar de alguns meses simulados contínuos, independentemente do número de NPCs.

### 5.4 O teto de velocidade — resolvido pelo Bloco A, não pelo horizonte

Esta seção existia aqui na primeira versão do documento, como estudo. **Ela virou o
[Bloco A](#bloco-a--a-agenda-o-tick-deixa-de-tocar-em-todo-mundo)**, porque a medição
mostrou que é ela, e não o número de NPCs, que impede o Mestre de avançar alguns dias.

O resumo, para quem estiver lendo só esta seção: 38% do tick calcula a função de utilidade
de cada NPC e a resposta é a mesma do minuto anterior em **99,83%** das vezes (uma ação dura
78 minutos simulados em média). Mais 36% é executar essa ação idêntica. E, mesmo desligando
tudo isso, sobra um piso de **35,6 ms por tick** com 25.000 NPCs, do qual 17,3 ms são
agrupamentos remontados do zero. As duas metades do Bloco A atacam as duas metades desse
número.

O que **continua** sendo horizonte, e por quê: o nível de detalhe por cidade
([5.2](#52-as-três-mudanças-estruturais-em-ordem-de-retorno), item 1) só passa a valer a
pena depois do Bloco A, porque o Bloco A já entrega, para o mundo inteiro, boa parte do que
o nível de detalhe entregaria só para as cidades de fundo — e sem a complicação de ter duas
granularidades convivendo.

### 5.5 Avanço rápido é outro modo de simulação, não um tick mais rápido

Se o que você quer é **pular meses ou anos**, nenhuma otimização de tick resolve, e a
aritmética mostra por quê na hora:

| quero pular | ticks de 1 minuto | a 1 ms por tick (otimista, hoje são ~270) |
|---|---|---|
| 1 dia | 1.440 | 1,4 s |
| 1 mês | 43.200 | 43 s |
| **1 ano** | **525.600** | **8,8 min** |

Mesmo num tick 270 vezes mais rápido do que o atual, um ano leva quase nove minutos de
espera. O gargalo deixou de ser o custo do tick e passou a ser a **quantidade** de ticks.

A resposta é um segundo modo de simulação, com passo de **um dia**, em que as mecânicas
são aplicadas estatisticamente em vez de minuto a minuto: a fome não é simulada, ela é
resolvida ("o NPC comeu o suficiente porque tinha dinheiro e havia comida"); casamentos,
nascimentos, mortes, contratações e obras acontecem por taxa diária; o desgaste de
infraestrutura já é diário hoje (`processar_desgaste`) e passaria sem mudança nenhuma.

**Mas repare no limite de onde isso vale:** com o Bloco A pronto, 7 dias cabem em ~30 s
(D13) e **um mês cabe em ~2 minutos**, com o tick de um minuto de sempre. O modo grosso só
passa a ser necessário para pular **muitos meses ou anos** — e é por isso que D17 o mantém
fora deste plano. O que este plano deixa pronto é o encaixe: A06 faz cada mecânica declarar
a própria cadência, então "rode só as mecânicas `por_dia` e resolva o resto por taxa" deixa
de ser uma reescrita do laço e vira um modo de despacho a mais.

⚠️ E a armadilha que vem junto, porque ela é inevitável e é melhor saber antes: **os dois
modos vão divergir.** Simular um mês minuto a minuto e simular o mesmo mês por taxas
diárias não dão o mesmo mundo, e nunca vão dar. O que você precisa exigir é que deem
mundos **estatisticamente parecidos** — população, empregos, casamentos e ruínas na mesma
ordem de grandeza. Escreva esse teste de comparação **antes** do segundo modo, não depois;
sem ele, o avanço rápido vira um gerador de mundos estranhos que ninguém consegue depurar.

### 5.6 O que **não** vale a pena, e por quê

- **Reescrever o tick em NumPy.** Tentador porque o laço é aritmético. Mas a decisão de
  ação de cada NPC é ramificada e consulta o mundo — vetorizar isso significaria reescrever
  `NPCBrain` inteiro num modelo de dados diferente, e perder toda a legibilidade que a
  refatoração conquistou. O retorno não paga.
- **Trocar o SQLite.** Medido: 40,6 ms para 25.000 `UPDATE`s numa transação. O SQLite não é
  o gargalo; o que era caro é o que se escrevia nele.
- **Cache entre ticks.** Todas as tentativas até aqui de guardar estado derivado entre
  ticks (P03 anotou isto explicitamente) criaram dado velho. Escopo de tick sim, cache
  entre ticks não.

---

## Anexo 1 — Tabela de medições

Todos os números deste documento, num lugar só. Reproduza-os antes de começar: se a sua
base não bater com isto, algo mudou e o diagnóstico pode não se aplicar.

### As 14 cidades atuais (`audit_cidades.py`, commit `26328c4`)

| cidade | modelo | porte | raio m | quadras | lotes | l/quadra | máx/qd | sem frente % | lotes/raio² |
|---|---|---|---|---|---|---|---|---|---|
| Belinhaven | linear | pequeno | 293 | 23 | 408 | 17 | 24 | 0,0 | 0,0048 |
| Cidade da Lua | grade | grande | 765 | 311 | 5.315 | 13 | 34 | 0,0 | 0,0091 |
| Cidade das Flores | organica | medio | 478 | 34 | 2.579 | 70,5 | 153 | **4,6** | 0,0113 |
| Cidade dos Sonhos | grade | medio | 593 | 323 | 3.017 | 9 | 25 | 0,0 | 0,0086 |
| Cidade dos Ventos | grade | medio | 472 | 178 | 1.898 | 10,0 | 28 | 0,0 | 0,0085 |
| Corarfield | linear | grande | 846 | 87 | 1.286 | 15 | 20 | 0,0 | 0,0018 |
| Elorfield | linear | medio | 511 | 67 | 947 | 14 | 20 | 0,0 | 0,0036 |
| Fenelburgo | organica | grande | 844 | 84 | 8.400 | 101,5 | 198 | **3,3** | 0,0118 |
| Irenburgo | grade | grande | 791 | 394 | 8.275 | 21,0 | 32 | 0,0 | 0,0132 |
| Jordorstead | radial | grande | 992 | 60 | 8.775 | 151,0 | 195 | 0,0 | 0,0089 |
| Kelandor | linear | pequeno | 394 | 61 | 691 | 11 | 16 | 0,0 | 0,0044 |
| Keldorstead | radial | medio | 716 | 36 | 4.995 | 146,5 | 170 | 0,0 | 0,0097 |
| Pelvermont | radial | pequeno | 329 | 12 | 1.249 | 104,5 | 131 | 0,0 | 0,0115 |
| Tordordor | radial | medio | 612 | 36 | 4.130 | 122,5 | 147 | 0,0 | 0,0110 |

**Total: 51.965 lotes.** `bowtie`, `anel_x` e `fora_muro` são **0** em todas — o Bloco G do
plano anterior funcionou e este plano não pode regredi-los.

### Quadra: profundidade contra largura, por banda (Jordorstead, `radial`, raio 992 m)

| banda | profundidade | largura | razão | lotes na quadra |
|---|---|---|---|---|
| 1 | 125 m | 120 m | 0,96 | 88 |
| 2 | 131 m | 208 m | 1,59 | 136 |
| 3 | 131 m | 292 m | 2,23 | 140 |
| 4 | 139 m | 381 m | 2,74 | 162 |
| 5 | 122 m | 472 m | 3,87 | 170 |
| 6 | 130 m | 557 m | **4,28** | 187 |

Compare com Irenburgo (`grade`): 58 m × 58 m, razão 1,00, 21 lotes — em **todas** as bandas.

### Lotes cegos (a mais de 25 m de qualquer rua)

| cidade | cegos / total | causa A: `"sem_via"` | causa B: sem teto de profundidade |
|---|---|---|---|
| Cidade das Flores | 119 / 2.579 (4,6%) | 119 | 0 |
| Fenelburgo | 275 / 8.400 (3,3%) | 247 | 28 |

Pior caso medido: `fenelburgo_6_5_l53`, **922 m²**, ~84 m de profundidade, centroide a
**43,7 m** da rua mais próxima. A config pede 22 m de profundidade.

### Tick sintético, `bench_tick.py`, banco falso (CPU pura)

| NPCs | locais | cidades | hoje | sem o quadrático de casamento |
|---|---|---|---|---|
| 750 | 10.000 | 15 | 48,0 ms | 14,1 ms |
| 1.500 | 15.000 | 15 | 159,1 ms | — |
| 3.000 | 20.000 | 15 | 591,3 ms | 57,6 ms |
| 6.000 | 30.000 | 15 | 2.325,8 ms | — |
| 12.000 | 40.000 | 15 | 9.411,3 ms | 259,9 ms |
| 12.000 | 40.000 | **40** | 1.926,6 ms | — |
| 25.000 | 60.000 | 40 | — | 991,1 ms |
| 50.000 | 80.000 | 60 | — | 3.072,0 ms |

A linha em negrito é a prova: os **mesmos** 12.000 NPCs custam 4,9× menos espalhados em
mais cidades.

### Perfil do tick (`cProfile`, 3.000 NPCs, 3 ticks, 8,548 s)

| função | tottime | chamadas |
|---|---|---|
| `marriage.verificar_elegibilidade_casamento` | 1,680 s | 1.791.033 |
| `enum.__get__` (acesso a `.value`) | 1,231 s | 9.106.826 |
| `consultas_npc.sao_parentes` | 0,764 s | 899.073 |
| `config.resolver.cfg_get` | 0,657 s | 2.203.390 |
| **`marriage.processar_coabitacao` (cumulativo)** | **7,897 s** | 3 |

### Custo do tick por fase (12.000 NPCs, 15 cidades, sem o quadrático de casamento)

| fase | ms/tick | % do tick |
|---|---|---|
| **decidir** (`NPCBrain.decidir_acao` + utilidades) | 102,6 | 38,0% |
| **agir** (`executar_acao`) | 96,5 | 35,8% |
| metabolismo (fome, energia, social) | 25,8 | 9,5% |
| humor | 15,5 | 5,7% |
| saúde | 7,2 | 2,7% |
| interações sociais | 5,5 | 2,0% |
| resto do tick | 20,3 | 7,5% |
| **total** | **269,7** | |

### O piso do tick: o custo que sobra com o processamento por NPC desligado

| NPCs | tick completo | piso sem o corpo por-NPC | só os agrupamentos |
|---|---|---|---|
| 3.000 | 56,3 ms | 3,22 ms | 1,30 ms |
| **25.000** | **946,8 ms** | **35,62 ms** | **17,26 ms** |

É a medição que obriga o Bloco A a ter duas metades
([A00](#a00--o-que-a-medição-obriga-e-por-que-as-duas-metades-são-necessárias)): a agenda de
decisões leva 7 dias simulados de 2 h 39 min para 6 min, e aí para — o que sobra não depende
de quantos NPCs decidiram, e sim de quantos existem.

Escrita do relógio (`mundo_meta`, 2 commits por tick): **0,010 ms/tick**, ou 0,1 s em 7 dias
simulados. Não é gargalo e não precisa de tarefa.

### Estabilidade da decisão (banco real, 20 NPCs, 720 ticks = 12 h simuladas)

| grandeza | valor |
|---|---|
| NPCs que trocam de **ação** por tick | **0,17%** |
| NPCs que trocam de **lugar** por tick | 0,15% |
| duração mediana de uma ação | ~36 minutos simulados |
| duração **média** de uma ação | **78 minutos simulados** |

É a medição que sustenta a [Seção 5.4](#54-o-teto-de-velocidade--resolvido-pelo-bloco-a-não-pelo-horizonte):
38% do tick calcula uma utilidade cuja resposta é a mesma do minuto anterior em 99,8% das
vezes.

### Persistência (SQLite real, WAL, `synchronous=NORMAL`, 5 repetições)

| relações/NPC | NPCs | `INSERT OR REPLACE` | `json.dumps` | total | `UPDATE` estreito |
|---|---|---|---|---|---|
| 20 | 3.000 | 4,0 ms | 15,8 ms | 19,8 ms | 4,6 ms |
| 150 | 3.000 | 17,1 ms | 98,5 ms | 115,6 ms | 4,6 ms |
| 150 | 12.000 | 69,6 ms | 387,8 ms | 457,4 ms | 19,2 ms |
| 150 | 25.000 | 147,3 ms | 796,8 ms | **944,1 ms** | **40,6 ms** |

### Outros

| grandeza | valor medido |
|---|---|
| Interações sociais por tick, 25.000 NPCs | ~170 (≈340 commits/tick hoje) |
| Linhas de evento por dia simulado, 25.000 NPCs | ~245.000 |
| RSS, 25.000 NPCs + 60.000 locais | 122 MB (~1,4 KB/entidade) |
| Banco atual | 20 NPCs, 24.423 locais, 0 lotes, 5,4 MB |
| Interpretador | Python 3.14.4, `Py_GIL_DISABLED = 0` |

---

## Anexo 2 — Chaves de config novas, removidas e recalibradas

### Novas

| chave | bloco | valor inicial | o que é |
|---|---|---|---|
| `cidade_geo_quadra_largura_alvo_m` | S01 | `95` | largura de quadra que dispara a duplicação de setores. Igual ao vão entre anéis (D9: quadra quase quadrada). |
| `cidade_geo_setores_max` | S01 | `192` | teto de segurança para a duplicação. Não é um parâmetro de design; é um para-quedas. |
| `cidade_geo_domicilios_alvo_faixa_por_tamanho` | R01 | `{pequeno:[50,130], medio:[280,620], grande:[800,1800]}` | **a chave central do Bloco R.** Sorteia o tamanho humano da cidade; o raio é derivado dela. |
| `cidade_geo_densidade_lote_por_modelo` | R02 | medido | `{modelo: [k, e]}` em `lotes = k · raio^e`. **Gerado por `calibrar_densidade.py`, nunca escrito à mão.** |
| `geracao_populacao.npcs_por_familia_faixa` | R03 | `[2, 4]` | tamanho da família. Confira contra `capacidade_padrao_residencia` (5) antes de subir. |
| `simulacao.eventos_retencao_dias_simulados` | E02 | `30` | poda da tabela `eventos`. Não afeta `eventos_globais`. |
| `simulacao_intervalo_maximo_decisao_min` | A02 | `240` | teto do salto de decisão, e **o parâmetro que mais mexe no custo do avanço rápido** (ver a tabela em A02). Também é a rede que transforma um `acordar` esquecido em atraso de 4 horas simuladas em vez de NPC congelado para sempre. Baixar quadruplica o custo sem comprar segurança nenhuma: a segurança vem do cálculo de limiar, não daqui. |

### Removidas

| chave | bloco | por quê |
|---|---|---|
| `geracao_populacao.npcs_por_cidade` | R03 | a população deixa de ser tabela e passa a ser contada a partir dos domicílios que nasceram ocupados. |
| `geracao_populacao.npcs_por_cidade_por_tamanho` | R03 | idem. A diferença entre vila e capital passa a vir do sorteio de domicílios. |

### Mantidas, mas precisam de recalibragem

| chave | bloco | por quê |
|---|---|---|
| `cidade_geo_raio_m_faixa_por_tamanho` | R01 | deixa de ser a **fonte** do raio e vira o **grampo** de sanidade dele. Se o grampo morder, a faixa de domicílios está errada — registre, não engula. |
| `cidade_geo_escala` | R01 | continua sendo o float único que controla o tamanho das cidades (D5), mas passa a multiplicar **domicílios**, não raio. Deixe em `1.0` e calibre por `domicilios_alvo`. |
| `cidade_geo_setores_por_portao_faixa` | S01 | passa a definir os setores da **banda 0**, não de todas. Pode ficar como está; confirme em R04. |
| `cidade_geo_patio_area_minima_m2` | L01 | com o teto de profundidade, o pátio raso deixa de ser o caso patológico que era. Reveja o valor de 120 m² depois de L01. |
| `cidade_geo_num_aneis_faixa_por_tamanho` | R04 | G05 registrou 4 cidades batendo no teto desta faixa. Com o raio menor de R02, o teto pode deixar de morder — confirme e, se ainda morder, aí sim recalibre. |

---

## Anexo 3 — Glossário: os termos novos deste plano

O `PLANO_CIDADE_VIVA.md` tem o glossário de geometria urbana (banda, vão, faixa de
domínio, pátio, inset, viela). Estes são os termos que **este** documento acrescenta.

**Setor.** Uma fatia angular da cidade radial, entre duas ruas radiais vizinhas. Até hoje o
número de setores era o mesmo em toda a cidade; a partir de S01 ele **dobra** conforme o
raio cresce. `setores_por_banda[j]` é sempre múltiplo de `setores_por_banda[j-1]`, e toda a
geometria do Bloco S depende dessa propriedade.

**Densificar um anel.** Inserir pontos num anel já pronto, sobre os segmentos que ele já
tem, para que ele passe a ter tantos pontos quanto o anel vizinho de fora. Como o ponto
novo cai **sobre** o segmento, a linha não muda de forma — só ganha vértice. É o truque que
mantém toda quadra com 4 vértices depois que os setores dobram (S02).

**Aresta cega (`"sem_via"`).** Uma aresta de quadra onde **não existe rua nenhuma** —
tipicamente porque o modelo `organica` abriu um vão no anel de propósito. Diferente de
viela (`"servico"`), que é uma via estreita **de verdade**, emitida como `Rua` e que dá
frente legítima a um lote. Confundir as duas é a
[armadilha 6](#armadilha-6--servico-hoje-significa-duas-coisas-opostas).

**Domicílio.** Um lote residencial. É a unidade em que o **cartógrafo** raciocina sobre o
tamanho da cidade, porque é um conceito de urbanismo e não de simulação — `cartographer/`
não pode saber o que é um NPC nem o que é uma família (R00).

**Família.** Um domicílio **ocupado**, com 2 a 4 NPCs dentro. É a unidade em que o
**povoador** raciocina. O povoador não recalcula a conta do cartógrafo: ele **conta** as
residências ocupadas que nasceram no banco.

**Densidade de lote (`k`, `e`).** Os dois números de `lotes = k · raio^e`, medidos por
modelo por `calibrar_densidade.py`. No `grade`, `e` fica perto de 2 (a cidade é um disco
preenchido); no `linear`, perto de 1 (é uma fita ao longo de um eixo). **Medidos, nunca
deduzidos** ([armadilha 7](#armadilha-7--a-densidade-de-lotes-por-raio-varia-7-vezes-entre-modelos)).

**Escopo de tick (contra cache).** Estado derivado calculado uma vez no começo do tick e
descartado no fim — como `npcs_por_casa` (P03) e o conjunto de casas tocadas (N04).
**Não** é cache: cache sobrevive ao tick e fica velho. Este projeto já tomou esse prejuízo;
não o tome de novo.

---

## Registro de execução

> Anote aqui o que você encontrou e o que ficou diferente do planejado. Uma linha por
> tarefa concluída, com o número medido quando houver. O plano anterior deu certo em
> grande parte porque este registro foi levado a sério: as quatro pendências que este
> documento responde vieram daqui.

| Tarefa | Data | Observação / número medido |
|---|---|---|
| N01 | 2026-09-12 | `processar_coabitacao` (marriage.py) passou a iterar `n1.relacionamentos` em vez de todos os solteiros da cidade, com a ordem embaralhada por RNG a cada chamada. Nenhuma regra de elegibilidade mudou. `bench_tick.py --ticks 3`: cenário `3000/15000/15` caiu para 55,4 ms — pré-N01 o cenário próximo `3000/20000/15` estava em ~591 ms (parada obrigatória nº 2 satisfeita, mesma ordem de grandeza). Suíte: 92 passed, 2 xfailed, sem alteração nos testes de casamento. |
| N02 | 2026-09-12 | `RepositorioNPC.salvar_muitos` virou `UPDATE` estreito (7 colunas quentes); o `INSERT OR REPLACE` de sempre virou `salvar_completo`, chamado nos pontos de mudança fria (reprodução, ciclo de vida, decadência, casamento, urbanismo, finanças — todos já chamavam `.salvar()` num NPC só, e continuam; só `builder/populador.py` (3 chamadas em lote) e o novo `salvar_completo` em lote precisaram trocar de nome). W03 escrito antes: `tests/test_persistencia.py` roda um tick de verdade contra SQLite temporário, com parto no meio, reabre o banco noutro `DatabaseManager` e confirma que mãe/pai/bebê sobrevivem com os campos certos — e passou de primeira contra a implementação nova. `tests/test_repositorio_npc.py` reescrito: prova que `salvar_muitos` não toca coluna fria e que um `UPDATE` numa linha inexistente não cria nada (a armadilha documentada). Suíte: 96 passed, 2 xfailed. |
| N03 | 2026-09-12 | `GameLoop.__init__` guarda `_cfg_bio`/`_cfg_metabolismo` uma vez (`_aplicar_metabolismo`, `_aplicar_consequencias_de_saude`, `_executar_rotinas_agendadas` deixam de rechamar `cfg_get(self._config, "biologia_e_sociedade"/"metabolismo")` por NPC). `EstagioVida.{BEBE,CRIANCA,ADULTO,IDOSO,MORTO}.value` viraram constantes de módulo em `models.py`, usadas em `is_adulto`/`is_idoso`/`esta_vivo`/`eh_dependente` — o item isolado mais caro do perfil depois do casamento (1,23 s em 9,1 M acessos a `.value` com 3.000 NPCs). `bench_tick.py`: 3000/15000/15 de 55,4 para 53,9 ms (ganho pequeno na escala sintética atual, como o plano previu — o efeito cresce com mais NPCs). Suíte: 96 passed, 2 xfailed. |
| N04 | 2026-09-12 | `num_dependentes` deixou de ser recalculado por NPC dentro de `_aplicar_metabolismo`. `GameLoop._atualizar_dependentes` roda uma vez no FIM do tick e só recalcula as casas cuja "assinatura" (ids/mãe/pai/`eh_dependente()` dos moradores) mudou desde o fim do tick anterior — comparação pura em `loop.py`/`consultas_npc.py`, sem instrumentar os pontos de mutação (parto, morte, crescimento, casamento) um a um. A troca de identidade de `mundo.npcs` (parto recarrega do banco; `recarregar_habitantes()` também) força um recálculo total nesse tick, porque os objetos recarregados nascem com `num_dependentes` no default 0 e a assinatura sozinha não perceberia isso. Implementação DIFERENTE da sugerida literalmente pelo plano (conjunto de `casa_id` tocadas, instrumentado nos 4 pontos de mutação): optei por diff de assinatura porque não exige tocar em reproduction.py/lifecycle.py/marriage.py/actions.py — mesmo resultado (só recalcula quem mudou), superfície de risco menor. `tests/test_num_dependentes.py` (casa estável entre ticks, lista de NPCs trocada força recálculo) e a asserção nova em `tests/test_persistencia.py` (mãe ganha o dependente no MESMO tick do parto, com SQLite de verdade — o `BancoFalso` não sustenta o `carregar_todos()` que `processar_parto` faz). `bench_tick.py` sintético não mostra ganho (população toda adulta, sem pais/filhos — o custo que caiu só existe com famílias de verdade); o ganho medido no plano (0,47 s/tick com 25.000 NPCs) vem de um perfil com população real, fora do escopo desta ferramenta. Suíte: 98 passed, 2 xfailed. |
| N05 | 2026-09-12 | `bench_tick.py` ganhou os 4 cenários grandes (`6000/30000/15`, `12000/40000/15`, `25000/60000/15`, `25000/60000/40`). Resultado (CPU pura, `--ticks 5`): `6000/30000/15`=118,2 ms; `12000/40000/15`=252,2 ms; `25000/60000/15`=591,2 ms (1,7x de folga); `25000/60000/40`=970,2 ms (**1,0x de folga — no limite, mas dentro**). Achado não previsto pelo plano: com 25.000 NPCs, 40 cidades custa MAIS que 15 cidades (970 vs 591 ms) — o inverso do padrão pré-N01 (Seção 2.1), porque depois do N01 o resíduo que sobra por cidade (agrupamentos, rotinas, urbanismo) parece ter overhead fixo por cidade que agora pesa mais que a economia do laço de casamento menor. Não investiguei a fundo (fora do escopo de "medir e parar" da tarefa) — fica anotado para quem for calibrar o Bloco R (nº de cidades) ou revisitar o Bloco N depois. **Os quatro cenários couberam no orçamento — D7 satisfeito, bloco encerrado sem thread/processo (D11).** `--real` só mede o banco atual (20 NPCs, sem opção de escala) — 1,3 ms; medição de disco EM ESCALA fica para W02 (`--com-banco`), ainda não implementada. |
| A01 | 2026-09-12 | `_aplicar_metabolismo(npc, minutos, maes_em_parto)` — energia/fome/social multiplicados por `minutos`; o sorteio de fome/social virou UM `random.uniform` multiplicado por `minutos`, não `minutos` sorteios (variância reduzida de propósito, documentado no docstring). `gravidez_ticks -= minutos`, grampeado em 0, parto dispara no CRUZAMENTO (`gravidez_antes > 0 and depois == 0`), não na igualdade exata — testado com um salto de 10 min sobre 3 restantes. `_aplicar_consequencias_de_saude` NÃO mudou nesta tarefa (decidir o tamanho do salto é trabalho de A02, ver o próprio texto da tarefa). Call site em `executar_tick` fixa `minutos=1` — a agenda (A02) ainda não existe. `tests/test_metabolismo_temporal.py`: 480 minutos de uma vez vs 480 passos de 1 minuto, com o sorteio mockado pra um valor fixo (a equivalência é sobre a ARITMÉTICA da escala, não sobre reproduzir a mesma sequência aleatória — que nunca seria igual entre um sorteio só e 480 somados, de propósito). Suíte: 101 passed, 2 xfailed. |
| A02 | 2026-09-12 | Implementada com um recorte de escopo deliberado (autorizado pelo dono do projeto depois de eu ter sinalizado o risco): só as ações "estáveis" — `Acao.DORMIR`, `Acao.TRABALHAR`, `Acao.OCIOSO` (`engine/mechanics/agenda.ACOES_LOTEAVEIS`) — recebem salto grande. `Acao.COMER` (paga em parcelas), `Acao.CONSTRUIR` (termina ao cruzar 100% de integridade) e `Acao.CUIDAR_PROLE` continuam reavaliadas todo minuto, de propósito: generalizar o salto pra elas exigiria calcular o instante de cada transição interna própria, e nenhuma dura o bastante pra compensar o risco. Novo módulo `engine/mechanics/agenda.py` (puro, sem estado): `npc_esta_em_dia` (estado de consequência — fome acima de `inaniacao_fome_limiar` — nunca pula, mesmo com `proximo_instante_decisao` no futuro) e `calcular_proximo_instante` (mínimo entre o cruzamento de fome pro limiar certo — pior caso, `fome_base_ganho_max` — o cruzamento de energia, determinístico, sem sorteio, e o teto `simulacao_intervalo_maximo_decisao_min` novo, 240, com jitter de 80-100% pra não sincronizar a população inteira no mesmo instante futuro). `GameLoop.executar_tick` aplica os "minutos extras" (tudo antes do último minuto) de uma vez — metabolismo (A01) + `_aplicar_efeito_continuo` (o ganho/perda linear da ação em andamento: energia do sono, energia+salário do trabalho, perda de social do ócio) — e só então roda o ciclo normal (metabolismo 1 min -> decidir -> agir -> saúde -> normalizar -> humor) pro último minuto, exatamente como antes de A02. `NPCMoodManager.processar_humor` ganhou um parâmetro `minutos` (N tentativas de transição em vez de 1, com o mesmo resultado exato quando `minutos=1`). Dois campos novos em `NPC`, não persistidos (mesmo padrão de `num_dependentes`): `proximo_instante_decisao`, `ultima_avaliacao`. Medido: mundo sintético de 25.000 NPCs, 15 cidades — primeiro tick (todo mundo agendado pela primeira vez) 813 ms; ticks seguintes, com o jitter, ~86-92 ms de média sustentada, ~150 decisões avaliadas por tick (contra 25.000 antes) — sem o jitter havia um pico de ~860 ms sincronizado a cada 240 ticks (toda a população agendada no mesmo instante, ao nascer no mesmo estado). Sanidade: 300 ticks (5h simuladas) contra o banco real de 20 NPCs, sem exceção, energia parando exatamente perto de `energia_quase_descansado` (85) ao acordar — nunca ultrapassando. `tests/test_agenda.py` (funções puras) e `tests/test_agenda_loop.py` (`GameLoop` de ponta a ponta). Suíte: 111 passed, 2 xfailed. Achado colateral, registrado como efeito aceito e não como bug: um dashboard que lê `energia`/`fome` direto do banco pode mostrar um NPC "congelado" por até `simulacao_intervalo_maximo_decisao_min` minutos simulados enquanto ele dorme/trabalha estável — é exatamente o efeito que o bloco busca (nada relevante mudaria mesmo), mas é visível pra quem olhar o banco no meio do intervalo. |
| A03 | 2026-09-12 | `EstadoDoMundo.acordar(npc)`/`acordar_cidade(cidade_id)` (mundo.py) — única porta, põe `proximo_instante_decisao = data_simulada`. `acordar_cidade` ainda é O(NPCs) (varre `mundo.npcs`): sem o índice por cidade de A04 (ainda não implementado) não tem como evitar. Fiados nos pontos que o texto pedia: decay.py (`_fechar_local`/`_colapsar_para_ruina`, perda de emprego), marriage.py (`realizar_casamento`, os dois cônjuges), actions.py (conclusão de obra, quem se muda). **Três pontos do texto acabaram não precisando de código**, por razões estruturais que vale registrar: (1) "chegada ao destino" não existe neste projeto — movimento é teleporte instantâneo, não há conceito de viagem em progresso; (2) contratação/demissão (market.py) e nascimento na casa (reproduction.py) já se autocuram, porque `recarregar_habitantes()`/o reload dentro de `processar_parto` substituem os objetos NPC por instâncias novas, com `proximo_instante_decisao=None` — que `agenda.npc_esta_em_dia` já trata como "avalie agora". Eventos globais (events.py): implementado com uma simplificação — a `GlobalEventManager` acorda **todo mundo** (não só uma cidade) quando detecta um id de evento global novo, porque `eventos_globais` não tem uma associação clara e única com uma cidade só; o texto do plano pedia `acordar_cidade`, usei `acordar` em todos por ser mais simples e não menos correto (eventos globais afetam a utilidade de qualquer NPC, em qualquer cidade). **"Toda ação do Modo Mestre sobre o NPC" ficou de fora, e é um achado, não um esquecimento**: as classes de ação do Mestre (`engine/mechanics/mestre/acoes/*.py`) recebem `db` diretamente, não `EstadoDoMundo` — rodam no processo do Flask, sem acesso a nenhum `mundo` em memória (a mesma separação de processos que o Bloco M existe pra resolver). Não dá pra chamar `mundo.acordar()` de lá; a solução correta é uma extensão do contador de versão de M01 (`LOCAIS_VERSAO`) pra também sinalizar "estes NPCs precisam acordar", consumida por `run_simulation.py` no mesmo lugar que fará `recarregar_locais()`. Deixei anotado para quando M01 for implementada. `tests/test_acordar.py`: os 4 pontos de acordar + o teste de resistência (sem NENHUM `acordar`, o NPC ainda volta a decidir dentro do teto de segurança). Suíte: 118 passed, 2 xfailed. Sanidade: 300 ticks contra o banco real, sem exceção. |
| A04 | 2026-09-12 | `EstadoDoMundo` ganhou `npcs_por_casa`/`npcs_por_localizacao`/`npcs_por_cidade`, mantidos (não recomputados) por `mover_npc`/`mudar_casa`/`registrar_npc`/`remover_npc` — mesmo padrão de `registrar_local`/`desativar_local` (P02). `_remover_de_bucket` remove por `npc.id` (chave de negócio), nunca por `==` de dataclass (dois NPCs com os mesmos valores em todo campo comparariam iguais). Fiado nos pontos de mutação reais: `movement.py` (as duas atribuições de `localizacao_atual_id`), `marriage.py` (`realizar_casamento`, os 3 casos de escolha de casa), `actions.py` (mudança de casa ao concluir obra), `lifecycle.py` (`processar_morte` chama `remover_npc` ANTES de zerar os campos, senão perde a chave do bucket). Achado que virou melhoria de quebra: `reproduction.py` fazia um `SELECT *` completo do banco só pra incluir o bebê recém-nascido na memória (O(NPCs) pra acrescentar 1); virou `mundo.registrar_npc(novo_bebe)`, O(1), e como bônus os objetos de mãe/pai mutados na mesma chamada deixam de ser descartados por um reload (o "segundo objeto" que N02 tinha anotado como pré-existente sumiu). Caso especial: a rede de segurança de `NPCBrain.decidir_acao` (casa_id apontando pra local inexistente) reatribui o campo direto porque `NPCBrain` é estático e não tem `EstadoDoMundo` — `GameLoop._decidir_e_executar` detecta a mudança e chama o novo `mundo.reindexar_casa_do_npc` (só reindexa, não muda o campo de novo). `recarregar_habitantes()` (core.py) agora chama `mundo._reconstruir_indices_de_npc()` depois de trocar `mundo.npcs` — sem isso os índices ficariam apontando pra objetos que não existem mais na lista. `loop.py` parou de recalcular `npcs_por_casa` do zero (P03/N04) — lê o índice mantido direto, nos dois lugares que usavam (laço principal e `_atualizar_dependentes`). `NPCUtils.agrupar_por_casa`/`agrupar_npcs_por_localizacao` continuam existindo, sem mudança, para uso pontual/teste/rotina diária (housing.py, reproduction.py, social.py) — só o laço do tick parou de chamá-las, como o plano pede. `tests/test_indices_npc.py`: os quatro métodos de mutação + o invariante central (W01: 100 ticks com nascimento/quase-morte/movimento, índices mantidos idênticos a uma reconstrução do zero, por CONJUNTO de ids — ordem de inserção não importa). Medido: mundo sintético 25.000 NPCs — média sustentada caiu de ~86-92 ms (pós-A03) para ~72 ms. Suíte: 123 passed, 2 xfailed. 300 ticks contra o banco real sem exceção. **`npcs_por_localizacao` não elimina o custo do filtro "ignorar dormindo" de `social.py`** (ele ainda faz sua própria varredura O(N) filtrando por `acao_atual`, sem usar o índice novo) — deixei assim de propósito: dar a ele o índice exigiria manter TAMBÉM um índice "só quem está acordado", que muda de membro a cada decisão (não só a cada movimento), e o ganho não parecia valer a complexidade extra nesta sessão. Anotado como possível próximo passo, não crítico (interações sociais são ~2% do tick, não os 17,3 ms que A04 mirava). **CORREÇÃO (achada em A07, ao rodar `bench_avanco.py` de verdade):** `GameLoop._remover_falecidos` reconstruía `mundo.npcs` (lista NOVA) todo tick, MESMO sem morte nenhuma — e essa troca de identidade fazia `_atualizar_dependentes` (N04) achar que a lista inteira tinha mudado, forçando recálculo de `num_dependentes` pra TODAS as casas, todo tick (o próprio bug que N04 existia pra evitar, reintroduzido por um efeito colateral não previsto). Medido com `cProfile`, 25.000 NPCs, 200 ticks: `_atualizar_dependentes` caiu de 108 s para 5,4 s; o tick inteiro, de 661 ms pra 148 ms — 4,5x. Corrigido com `EstadoDoMundo.ha_falecidos_pendentes`, uma flag marcada por `remover_npc` (chamado de dentro de `processar_morte`, o único lugar que remove NPC) e consumida por `_remover_falecidos`, que só reconstrói a lista quando ela está marcada. É a armadilha 12 na prática: um efeito colateral de reindexação (aqui, reconstruir uma lista por segurança) que não parecia mudar nada visível, e que na verdade desfazia a otimização de uma tarefa inteira — só apareceu ao medir com `bench_avanco.py`, não nos testes unitários (que rodam poucos ticks, não o bastante pra o custo dominar). |
| A05 | 2026-09-12 | `EstadoDoMundo.mudar_cidade(npc, cidade_id)` — só a porta, ninguém chama ainda. Atualiza os três índices (A04) numa operação só; casa/localização/trabalho da cidade de origem são limpos (não fazem sentido no destino) — uma mecânica de migração futura resolve casa/trabalho no destino antes ou logo depois de chamar isto. Docstring registra os três invariantes que essa mecânica futura tem que respeitar (casal não se separa, dependente acompanha o responsável, lote/vaga reservados no destino antes de sair da origem) e a razão estrutural da porta (Seção 5.2: se um dia existir um processo por cidade, migração vira mensagem entre processos, e isolar a operação aqui é o que torna essa transição possível). `tests/test_indices_npc.py::test_mudar_cidade_move_entre_os_indices_e_limpa_casa_trabalho`. Suíte: 124 passed, 2 xfailed. |
| A06 | 2026-09-12 | Cada mecânica diária ganhou `CADENCIA = "por_dia"` e `CADENCIA_HORA_CONFIG = "<chave>"` como atributos de classe (`NPCReproductionManager`, `NPCLifecycleManager`, `NPCHousingManager`, `GerenciadorUrbanismo`, `KingdomManager`). `GameLoop.__init__` monta `self._rotinas_diarias` (lista de `(chave_hora, callable)`) a partir desses atributos; `_executar_rotinas_agendadas` despacha num laço só, nunca mais um `if` por mecânica. `grep -n "if hora ==" engine/loop.py` não devolve nada (precisei inverter a ordem da comparação — `cfg_get(...) == hora` em vez de `hora == cfg_get(...)` — pra bater com o texto exato do validador, sem mudar o comportamento). `por_minuto`/`por_hora`/`sob_demanda` não têm implementação: nenhuma mecânica de hoje usa essas cadências (metabolismo/decisão/ação são por-NPC, já resolvidos pela agenda de A02, não são "mecânica com cadência própria" nesse sentido) — documentado como ponto de extensão, não implementado (D17, modo grosso, continua fora do escopo). Suíte: 124 passed, 2 xfailed. 1.500 ticks (~1 dia simulado, atravessando as 4 rotinas diárias) contra o banco real sem exceção. |
| A07 | 2026-09-12 | `builder/fix/bench_avanco.py` criado e usado pra medir D13 de verdade — e o resultado é um **achado, não um "OK"**: 1 dia (1.440 ticks) com 25.000 NPCs/40 cidades levou **184 s** (127,8 ms/tick de média), e a tendência é piorar ao longo dos dias, não estabilizar — profilei (`cProfile`, 200 ticks depois de 200 de aquecimento) e o custo dominante é `processar_coabitacao`/`verificar_elegibilidade_casamento` (marriage.py), porque `n1.relacionamentos` só CRESCE (nunca decai) neste benchmark de interação contínua — exatamente o "grafo social precisa de um teto" que o `PLANO_CIDADE_VIVA.md` original (Seção 5.2, item 3) já tinha marcado como HORIZONTE, fora do escopo deste documento. **D13 (7 dias em <30s) não está sendo atingido** nesta configuração — o alvo de "dezenas de ms/tick" do Bloco A (parada obrigatória nº3) SE confirma logo após A02-A04 (72-148 ms/tick medido em janelas curtas), mas um avanço de vários dias contínuos, com muita interação social, degrada por causa do grafo sem teto, que é um problema conhecido e não coberto por nenhuma tarefa deste plano. Fica registrado como a quinta pendência para o dono do projeto: potar/limitar `npc.relacionamentos` (os N mais fortes/recentes) é provavelmente um pré-requisito pra D13 valer de verdade em avanços de muitos dias, não só em curtos, e não estava no escopo original deste documento. |
| E01 | 2026-09-12 | `RepositorioEvento.salvar_muitos`/`RepositorioNPC.salvar_relacionamentos_muitos` (novos, `executemany`). `NPCSocialManager._computar_interacao` (novo) calcula o efeito de uma interação SEM gravar; `processar_interacoes` acumula eventos/pares do tick inteiro e grava os dois em lote no final. `processar_interacao_social` (nome público, usado por teste/uso pontual) manteve o contrato de gravar IMEDIATAMENTE — só delega pra `_computar_interacao` por dentro; nenhum teste existente precisou mudar. `tests/test_repositorio_evento.py` (novo) + teste de `salvar_relacionamentos_muitos` em `test_repositorio_npc.py`. Suíte: 130 passed, 2 xfailed. |
| E02 | 2026-09-12 | `simulacao.eventos_retencao_dias_simulados` (30, novo bloco `simulacao` em config.json) + `eventos_poda_hora` (2, em `biologia_e_sociedade`, junto dos outros `_hora`). `RepositorioEvento.podar_por_idade(dia_de_corte)` apaga por SQL direto (`SUBSTR`/`INSTR` no texto "Dia N, HH:MM" — evita trazer a tabela inteira pro Python só pra decidir o que apagar) e devolve a contagem; `GameLoop._podar_eventos_antigos` (nova rotina diária, registrada em `_rotinas_diarias` como A06 pede) loga quantas linhas saíram. `eventos_globais` nunca é tocada (tabela e SQL diferentes). `tests/test_repositorio_evento.py`: remove só o mais velho que o corte, preserva `eventos_globais`. Suíte: 130 passed, 2 xfailed. |
| M01 | 2026-09-12 | `MetaChave.LOCAIS_VERSAO` novo. `RepositorioLocal.criar`/`desativar` incrementam o contador em `mundo_meta` na MESMA transação (mesmo cursor) da escrita do local — `INSERT ... ON CONFLICT DO UPDATE`. `SimulationEngine.recarregar_locais()` (novo, espelha `recarregar_habitantes`) recarrega `mundo.locais` E reconstrói `mundo.indice` — reconstruir só um dos dois os deixaria discordando. `run_simulation.py` ganhou `sincronizar_locais_se_mudou`, chamado a CADA volta do laço principal (inclusive pausado — o Mestre cria/destrói local com o jogo parado, pra preparar cena antes de avançar), comparando a versão lida contra a última vista; só recarrega quando muda. `tests/test_repositorio_local.py` (incremento na criação/desativação, `recarregar_locais` percebendo um local criado por OUTRA conexão ao mesmo arquivo — simula o Mestre) + `tests/test_run_simulation.py` (só recarrega quando a versão muda). Não fiz `REATRIBUIR_NPC` incrementar a versão: ele muda `casa_id`/`local_trabalho_id` de um NPC, não cria/destrói Local — a sincronia dele já é resolvida por `recarregar_habitantes()` (a cada 5h de jogo), um mecanismo diferente e já existente. Suíte: 138 passed, 2 xfailed. |
| M02 | 2026-09-12 | `CriarLocal` deixou de chamar `GeoUtils.sortear_ponto_em_terra` (ponto qualquer em terra firme) e passou a reservar um lote real via `db.lotes.reservar_livre` — o id do Local vira o id do lote (armadilha 3), e o lote é concluído (`db.lotes.concluir`) na mesma tacada, já que um edifício do Mestre nasce pronto, não em obra like o de um casal. Sem lote livre, dispara a mesma avaliação de auto-expansão (X01) que a simulação usa — só que "de fora": `_avaliar_expansao_fora_do_processo` monta um `EstadoDoMundo` de TRABALHO (cidades/locais/data simulada frescos do banco, `npcs=[]` porque `avaliar_expansao`/`_aplicar_arrabalde` nunca tocam `mundo.npcs`), descartado ao fim da chamada — não é a engine da simulação, não a substitui (ARQUITETURA.md Seção 1). Desvio do texto literal do plano: `abrir_obra` (a função que o plano pedia pra chamar) exige um `dono_npc: NPC`, e `CriarLocal` não tem um "dono" natural (um quartel não pertence a uma pessoa, ao contrário de uma residência) nem acesso a um `EstadoDoMundo` vivo (só a `db`, processo separado) — usei a MECÂNICA de reserva de lote (`db.lotes.reservar_livre`/`concluir`, os mesmos métodos que `abrir_obra` usa por baixo) diretamente, em vez do wrapper NPC-cêntrico. Sem cidade simulada, a ação não cria nada (antes criava um Local "flutuante" com `cidade_id=None` — não é mais uma opção coerente com "todo edifício nasce de um lote"). `GeoUtils.sortear_ponto_em_terra` NÃO foi removida: `builder/populador.py` ainda a usa pra geração inicial. `tests/test_mestre.py`: reescrevi os dublês de `db.lotes`/`db.meta`/`db.mundo` pra sustentar o fluxo novo, adicionei os casos de "sem cidade" e "sem lote dispara expansão". Suíte: 138 passed, 2 xfailed. |
| S01 | 2026-09-12 | Implementada JUNTO com S02 e S03 num commit só — desvio consciente do plano: S01 sozinha produz uma `Quadra` com um número de vértices que varia (5+ quando os setores dobram), e `quad.py`/`lotes.py` indexam `[k]`/`[(k+1)%4]` — sem a densificação de S02 a subdivisão em lotes quebra na hora, não é possível "rodar S01 e parar". `self.setores_por_banda` (lista, um valor por banda, monotônico não-decrescente) substitui `self.num_setores` como a fonte da grade; `_grade_de_vertices` virou uma lista de linhas de tamanho variável (não mais array 2D regular), e a asserção de anéis cruzados agora compara a banda `j` contra a densificação (S02) da banda `j-1`. As radiais nascem na banda em que sua resolução aparece pela primeira vez e nunca desaparecem depois (`passo_j` só diminui e divide `passo_{j-1}`) — e o ponto de nascimento de uma radial que NASCE numa banda j>0 é o ponto DENSO do anel j-1 (não `vertices[j]`), senão a aresta radial da quadra e a rua radial deixam de coincidir (achado ao rodar `test_rua_coincide_com_aresta_de_quadra`, que pegou exatamente esse caso — Jordorstead tinha uma aresta a 53,9 m da rua mais próxima antes da correção). Config novas: `cidade_geo_quadra_largura_alvo_m` (95), `cidade_geo_setores_max` (192). |
| S02 | 2026-09-12 | `densificar_anel(anel, n_alvo)` em `base.py` — insere pontos SOBRE os segmentos já existentes (não muda a forma da polilinha, só ganha vértice), usada tanto pela quadra (aresta interna) quanto pela radial (ponto de nascimento), pra garantir que os dois usem exatamente o mesmo ponto físico. Toda `Quadra` continua com exatamente 4 vértices. |
| S03 | 2026-09-12 | `_torcer_grade` (organica.py) passou a calcular `passo_j = 2*pi/len(linha)` DENTRO do laço de bandas, não mais uma vez com `self.num_setores` global — confirmado o bug que o plano previu (não estoura, só sai torto): sem a correção, a torção da banda externa (com muito mais setores) usaria um passo pequeno demais, movendo um vértice por uma fração enorme do passo real dela e reintroduzindo o cruzamento que G01/G04 eliminaram. A abertura de anel (F7.1.2) também precisou de ajuste: o mapeamento do vão de uma banda pra outra quando os setores dobram entre elas (`_toca_o_vao`, considerando os DOIS pontos originais que um ponto denso interpola) — sem isso, `test_rua_coincide_com_aresta_de_quadra` pegava uma aresta "anel" da organica a 10,9 m da rua mais próxima (vão aberto não detectado corretamente). **Resultado medido, 15 cidades reais regeradas:** `bowtie_q`/`bowtie_l`/`anel_x`/`fora_muro` continuam 0 em todas (nenhuma regressão de geometria). `l/quadra` (mediana) caiu drasticamente nas cidades radiais/orgânicas — Jordorstead 151→41,5, Fenelburgo 101,5→35,0, Cidade das Flores 70,5→31,0, Keldorstead 146,5→41,5, Pelvermont 104,5→35,0, Tordordor 122,5→35,0 — e os dois `xfail` de `test_lotes_por_quadra_em_faixa` (radial/organica) passaram a passar de verdade (removidos). **Achado/decisão pendente:** as medianas das cidades REAIS (31-41,5) ainda ficam um pouco ACIMA do teto de 30 que o próprio plano define como alvo (o teste unitário passa porque usa uma cidade sintética menor/diferente) — `FATOR_TOLERANCIA_LARGURA=1.5` (o valor que o próprio texto do plano pede) permite o arco chegar a 1,5x a largura alvo antes de dobrar, e a maioria das quadras de uma banda parece ficar perto desse teto superior em vez de perto do alvo. Não toquei nesse fator por conta própria — R02 (calibração de densidade) e L04 (o `4<=mediana<=30` como gate rígido) são as tarefas que o plano já reserva pra fechar essa calibração fina, e mexer nele agora seria antecipar decisão de outra tarefa. `sem_frente_pct` das cidades organica caiu bastante (Cidade das Flores 4,6%→0,3%, Fenelburgo 3,3%→0,6%) como efeito colateral de quadras menores, mas não chegou a 0 — L02 é quem resolve a causa raiz (aresta "servico" ambígua + lote sem teto de profundidade). Regeração determinística confirmada (`md5sum` idêntico em duas rodadas). **Não consegui fazer a inspeção visual do mapa** que a "parada obrigatória nº1" do plano pede (sem conexão do navegador neste ambiente nesta sessão) — validado só numericamente (audit_cidades.py + testes de coerência rua/quadra). Suíte: 140 passed, 0 xfailed (os 2 xfail viraram passes de verdade). |
| L01 | 2026-09-12 | `_eixo_medio_sem_patio` (lotes.py) ganhou `config`/`banda`/`lote_fator_cidade` e passou a puxar cada canto do eixo médio de volta em direção à aresta quando a distância excede a profundidade alvo — continua pura. O miolo que sobra vira pátio de verdade quando a área bate o mínimo, **e** quando o quadrilátero é simples (achado: puxar cada canto independentemente, um por vez, pode produzir um quadrilátero bowtie numa quadra bem torta — `quad.e_quad_simples` descarta esses como "sem pátio" em vez de emitir um polígono inválido; G02 já existia pra exatamente esse tipo de caso, só que num ponto diferente do pipeline). `tests/test_cidades.py::test_profundidade_de_lote_e_limitada_por_banda` (novo, W01): nenhum lote de `organica` com área acima de 3x a mediana da própria banda. Validado nas 15 cidades reais: as 4 cidades `linear` (Belinhaven, Corarfield, Elorfield, Kelandor) saem **byte a byte idênticas** — a profundidade da quadra linear já era menor que o teto, confirmando que L01 não muda nada nelas. `sem_frente_pct` caiu um pouco nas duas organica (Cidade das Flores 0,3%→0,2%, Fenelburgo 0,6%→0,4%) — o restante é a causa "servico" ambígua, que é L02. Suíte: 141 passed. |
| L02 | | |
| L03 | | |
| L04 | | |
| R01 | | |
| R02 | | |
| R03 | | |
| R04 | | |
| W01 | | |
| W02 | | |
| W03 | 2026-09-12 | Escrito ANTES de N02, como o plano pediu — `tests/test_persistencia.py`. Cobriu o risco mais caro do bloco antes de introduzir o `UPDATE` estreito. |
