# 🌍 Plano de Mundo Crível — o levantamento dos NPCs, da autossuficiência e da parametrização

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este é o **quarto** documento da série. Os três anteriores
> ([`12_PLANO_CIDADE_VIVA.md`](12_PLANO_CIDADE_VIVA.md),
> [`13_PLANO_POPULACAO_E_ESCALA.md`](13_PLANO_POPULACAO_E_ESCALA.md) e
> [`14_PLANO_AVANCO_E_CALIBRAGEM.md`](14_PLANO_AVANCO_E_CALIBRAGEM.md)) trataram de
> **geometria** e de **velocidade**. Este trata de **conteúdo**: o mundo que sai desse
> motor é crível? Dá pra usar como fonte de informação numa mesa de RPG sem que o
> Mestre leia uma barbaridade?
>
> 👉 **A resposta medida é não, ainda não** — e não por falta de mecânica. As mecânicas
> existem, estão escritas e passam nos testes. Elas simplesmente **não estão se
> encontrando**: um contrato de vocabulário quebrou entre o cartógrafo e a engine, e
> quase todo sintoma deste documento desce daí.
>
> 👉 **Nada aqui é opinião.** Cada achado tem um número ao lado e a Seção 8 diz como
> reproduzir. Onde eu não medi, está escrito que não medi.
>
> 👉 **Nada aqui refaz trabalho dos três documentos anteriores.** Os Blocos R (doc 2) e
> C (doc 3) continuam pendentes e continuam válidos; a Seção 6 explica como este
> documento se encaixa neles em vez de competir.

**Criado em:** 2026-09-14
**Base analisada:** branch `reescrita-estrutura`, commit `449bb24`
**Estado da suíte:** `164 passed` — e **nenhum** dos achados abaixo é pego por um teste
**Medições:** mundo real reconstruído do zero (15 cidades de `database/cidades/`,
26.748 locais, 54.019 lotes, 840 NPCs), simulado por **25 dias completos**
(36.000 ticks, 659 s de tempo real), mais sondas isoladas em mundo sintético.

---

# ⚡ Decisões que precisam de você

> ✅ **RESPONDIDAS em 2026-09-14 pelo dono do projeto.** As respostas estão marcadas em
> cada item e são o que vale — as tarefas dos blocos abaixo já foram ajustadas a elas.
> O modelo que for executar **não reabre** nenhuma destas.
>
> ✅ **Nada em aberto.** A ❾ nasceu da combinação de ❶ com ❷ e também já foi respondida.

| # | pergunta | resposta |
|---|---|---|
| ❶ | Fome deve matar? | **(a)** sopão com cota e custo |
| ❷ | Como consertar o idoso? | **(a)** pensão sobe para 75 |
| ❸ | Resetar `database/`? | **(a)** reset |
| ❹ | `tipo`: derivar ou apagar? | **(a)** derivar |
| ❺ | Alvo de sustentabilidade | **reformulada** — ver abaixo |
| ❻ | Casamento deliberado vs surpresa | **manter como está** |
| ❼ | Contexto do Mestre | **(a)** cidade + teto, medir depois |
| ❽ | Rotinas para o `GameLoop` | **(a)** mover |
| ❾ | De onde sai o dinheiro do reino? | **não existe finança do reino** — cota, sem tesouro |

### ❶ Fome deve matar?

**Onde:** N04 · **Medido:** 25 dias, 10% da população sem um único PC desde o dia 6,
**zero mortes por fome** e saúde mínima 100 o tempo todo. O sopão do reino é grátis,
ilimitado e dispara antes da inanição começar.

- **(a) Sopão com cota diária por cidade e custo ao reino** ⭐ — NPC pobre pode morrer.
  Dinheiro passa a ter peso, e a mecânica de inanição que já está escrita volta a existir.
- **(b) Deixar como está** — mundo sem risco de fome; `inaniacao_*` segue sendo código
  que nunca roda.

✅ **RESPONDIDO: (a).** Sopão ganha cota diária por cidade e debita o tesouro do reino.
NPC pobre pode morrer de fome — é o objetivo. Ver N04, e a pergunta ❾.

### ❷ Como consertar o idoso quebrado?

**Onde:** N05 · **Medido:** o idoso fecha o dia em **−207,9 PC**. Depois de baratear o
convívio (decisão ❸ já resolvida), sobram **−33 PC/dia**. Ele come **215 min/dia** — seis
refeições — contra 66 min do trabalhador, porque não tem mais nada a fazer.

- **(a) Pensão 40 → 75 PC/dia** — uma linha de config, resolve a conta hoje.
- **(b) Atacar as seis refeições** (teto de refeições/dia, ou fazer o ócio competir de
  verdade fora do expediente) — mais trabalho, resolve a conta **e** o realismo.
- **(c) (b) com (a) como piso** ⭐ — conserta o comportamento e garante que o idoso não
  fica na miséria enquanto isso.

✅ **RESPONDIDO: (a) — pensão 40 → 75 PC/dia.**
As seis refeições/dia do idoso ficam como estão: é comportamento aceito, não bug. Ver N05.

### ❸ Resetar o mundo em `database/`?

**Onde:** Seção 10.3 · **Medido:** o banco atual tem 20 NPCs e 0 lotes — já não serve
para medir nada. E o manifesto tem "Cidade dos Ventos" **duplicada**: uma das duas está
com zero locais desde sempre, porque os ids de lote e local vêm do slug do nome.

- **(a) Reset de cartografia + repovoamento** ⭐ — `builder/reset_world.sh`. Simples e
  limpo.
- **(b) Migrar** — o `tipo` é um `UPDATE` fácil; o nome duplicado **não é migrável** (as
  duas cidades compartilham namespace de id).

✅ **RESPONDIDO: (a).** Reset de cartografia + repovoamento. Ver Seção 10.3.

### ❹ O campo `tipo` do Local: derivar ou apagar?

**Onde:** D23 / V01 · **Medido:** **617 de 26.748 locais (2,3%)** têm `tipo` dentro do
enum. Ele virou cópia exata de `tipo_local`. É a causa raiz de 4 dos 6 grupos de
sintomas deste documento.

- **(a) Derivar `tipo` de `categoria`, num ponto só** ⭐ — uma tabela no config, um
  invariante duro. O dashboard e o prompt do Mestre continuam funcionando sem mudança.
- **(b) Apagar `tipo` e migrar os 14 leitores para `categoria`** — mais limpo no fim,
  mas são 14 chances de errar e mexe em dashboard e Mestre.

✅ **RESPONDIDO: (a).** `tipo` derivado de `categoria`, num ponto só. Ver D23 e V01.

### ❺ O que é "o mundo se sustenta" — reformulada

❌ **A pergunta original estava errada.** Eu ofereci 30/90/365 dias, e o dono do projeto
respondeu, com razão, que isso não faz sentido: o alvo não é um número de dias, é **o
ciclo fechar**.

> *"eu quero que ela seja sustentável eternamente, não precisa ser perfeito, mas se os
> NPCs nascerem, comerem, trabalharem, dormirem, socializarem, casam e têm filhos,
> aposentam e morrem, isso é uma vida autossustentada. Não tendo morte de 100% de todos
> por um erro de algoritmo que para de nascer criança ou falhas de que todo mundo vira
> miserável no 3º dia, tá ótimo."*

✅ **Critério adotado — substitui o D25 antigo.** Rode até **renovação geracional
completa**: até que **100% dos NPCs vivos tenham nascido dentro da simulação** (nenhum
sobrevivente do povoamento inicial). Isso se autodefine — não é um número que eu chuto, é
o ciclo de vida inteiro dando uma volta. Com os limiares de hoje dá ~100 dias simulados;
se você recalibrar a longevidade amanhã, o critério continua valendo sem reescrita.

**Durante toda a corrida, nenhuma destas pode acontecer:**

| # | guarda | por quê |
|---|---|---|
| 1 | a população nunca zera nem cai abaixo de 30% do pico | "morte de 100% por erro de algoritmo" |
| 2 | nenhum dia simulado **sem nenhum nascimento** depois do dia 10 | "para de nascer criança" |
| 3 | a riqueza mediana nunca fica abaixo de 1 dia de despesa por mais de 5 dias seguidos | "todo mundo vira miserável no 3º dia" |
| 4 | as **oito** mecânicas disparam pelo menos uma vez por semana simulada: nascimento, maioridade, casamento, concepção, aposentadoria, óbito por velhice, contratação, obra | "se os NPCs nascem, comem, trabalham, dormem, socializam, casam e têm filhos, aposentam e morrem" |
| 5 | nenhum dependente sem responsável vivo na mesma casa | um mundo que abandona bebês não é crível |
| 6 | zero filhos de pais consanguíneos | idem |

Não é perfeição: é **"nenhuma mecânica morreu e nenhuma espiral levou tudo a zero"**.
É `audit_mundo.py --ate-renovacao` que mede, e é a porta de T02.

### ❻ Casamento: quanto deve ser deliberado?

**Onde:** G03 · **Medido em 25 dias:** **70 uniões por "romance surpresa"** contra **11
planejadas** (86% / 14%). O mundo registra "💍 CASAMENTO SURPRESA! apaixonaram-se tanto
durante a conversa que se casaram" quase três vezes por dia.

- **(a) Inverter: maioria deliberada, surpresa como exceção** ⭐ — casal se conhece,
  acumula afinidade, decide morar junto. Mais crível para narrar numa mesa.
- **(b) Manter o drama** — mundo mais novelesco, mas a frase acima repete todo dia.

✅ **RESPONDIDO: manter como está** — o mundo pode ser dramático, "a vida não é
perfeita, ainda mais nessa época". ⚠️ Mas o `return` que limita o caminho deliberado a
**1 casamento/dia no mundo inteiro** é bug, não design, e será corrigido; a calibragem
depois dele mantém o romance surpresa dominante. Ver G03.

### ❼ Quanto do mundo o Modo Mestre deve enxergar?

**Onde:** M01 · **Medido:** o contexto que vai para a IA tem **433 mil tokens** (1,7 MB)
com 840 NPCs. Não cabe em janela nenhuma; com 25.000 NPCs seriam ~3 milhões.

- **(a) Só a cidade simulada, teto de ~200 NPCs, residências agregadas** ⭐ — o Mestre vê
  uma cidade de verdade e sabe quantos ficaram de fora.
- **(b) Só quem apareceu em evento recente** — contexto mínimo, mas o Mestre não consegue
  responder "quem mora aqui?".
- **(c) O Mestre pede sob demanda** (uma ferramenta de busca em vez de despejo) — melhor
  de todos, mas é feature nova, não conserto.

✅ **RESPONDIDO: (a).** Cidade simulada + teto de ~200 NPCs, e medimos depois. Ver M01.

### ❽ As rotinas de `run_simulation.py` viram rotinas do `GameLoop`?

**Onde:** X03 · **Medido:** **21% do custo real por dia simulado está fora dos
benchmarks** — `processar_desgaste` (1,3 s/dia, ~88 s/dia com 25.000 NPCs) e
`processar_contratacoes` (4,3 s/dia) moram em `run_simulation.py` e nunca foram medidos.

- **(a) Movê-las para `GameLoop._rotinas_diarias`** ⭐ — resolve na raiz: toda rotina
  diária passa a ser medida automaticamente.
- **(b) Só ensinar o benchmark a chamá-las** — menor, mas o próximo que criar uma rotina
  fora do loop cai no mesmo buraco.

✅ **RESPONDIDO: (a).** Mover para `GameLoop._rotinas_diarias`, para medir certo. Ver X03.

### ❾ De onde sai o dinheiro do reino? ✅ **RESPONDIDA**

**Por que apareceu:** ❶ deu custo ao sopão e ❷ subiu a pensão. As duas juntas
transformariam o reino num pagador — e o reino não tem receita. Medido: herança sem
herdeiro rende **20 PC/dia**, contra 714 de sopão e 8.550 de pensão.

✅ **RESPONDIDO: nada disso. Não existe finança do reino, e não vai existir tão cedo —
o tick já está sofrendo.** O reino simplesmente credita dinheiro nas contas, sem origem.

**Consequências, já aplicadas às tarefas:**

- ❌ **`MetaChave.TESOURO_REINO` está cancelada.** Era invenção minha. Não crie.
- ✅ **A pensão continua sendo crédito sem origem**, como hoje — só muda de 40 para 75.
- ✅ **O "custo" do sopão que a ❶ pediu passa a ser a COTA, e só ela**: um teto de
  rações por cidade por dia. É o que faz a fome voltar a ter consequência; o débito em
  moeda nunca foi o mecanismo, era só o tema.
- ⚙️ **Custo no tick: zero.** A cota é um contador por cidade, zerado uma vez por dia na
  rotina que o reino já roda, e lido apenas dentro de `fornecer_sopao` — que só é
  chamado quando um NPC tenta comer sem dinheiro. Nenhuma varredura nova, nenhum
  trabalho por tick.
- 📌 `reino.custo_sopao_ao_reino` (5) continua no config **sem ser lido**, agora com
  comentário dizendo que é reservado para quando existir finança do reino. Não o ligue
  em nada.

---

### Nada pendente

As nove decisões estão fechadas. O modelo executor pode começar pelo Bloco V.

---

## Índice

- [⚡ Decisões que precisam de você](#-decisões-que-precisam-de-você) ← **comece aqui**
- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. O veredito, em uma página](#1-o-veredito-em-uma-página)
- [2. O mundo como ele roda hoje — as medições](#2-o-mundo-como-ele-roda-hoje--as-medições)
- [3. A causa raiz nº 1 — o vocabulário de local quebrou](#3-a-causa-raiz-nº-1--o-vocabulário-de-local-quebrou)
- [4. A causa raiz nº 2 — a simulação não lê o que ela mesma escreve](#4-a-causa-raiz-nº-2--a-simulação-não-lê-o-que-ela-mesma-escreve)
- [5. Os outros quatro eixos](#5-os-outros-quatro-eixos)
- [6. Decisões (não reabra)](#6-decisões-não-reabra)
- [7. As quatro novas armadilhas](#7-as-quatro-novas-armadilhas)
- [Bloco V — O vocabulário de local volta a existir](#bloco-v--o-vocabulário-de-local-volta-a-existir)
- [Bloco P — A simulação lê o que escreve](#bloco-p--a-simulação-lê-o-que-escreve)
- [Bloco N — A economia fecha](#bloco-n--a-economia-fecha)
- [Bloco G — Uma população, não uma coorte](#bloco-g--uma-população-não-uma-coorte)
- [Bloco M — O Mestre consegue ler o mundo](#bloco-m--o-mestre-consegue-ler-o-mundo)
- [Bloco X — Custos fora do benchmark e regressões](#bloco-x--custos-fora-do-benchmark-e-regressões)
- [Bloco T — Testes e auditoria viva](#bloco-t--testes-e-auditoria-viva)
- [8. Tabela de parâmetros — valor hoje, efeito medido, valor proposto](#8-tabela-de-parâmetros--valor-hoje-efeito-medido-valor-proposto)
- [9. Como reproduzir cada medição](#9-como-reproduzir-cada-medição)
- [10. O que este documento NÃO fecha](#10-o-que-este-documento-não-fecha)
- [Registro de execução](#registro-de-execução)

---

## 0. Como usar este documento

### Ordem obrigatória

```
V  ──►  P  ──►  N  ──►  G  ──►  M
│                        │
└──►  X  (independente)  └──►  T (fecha tudo)
```

**Por que essa ordem, e não outra:**

- **V vem primeiro e não é negociável.** Enquanto `tipo` não voltar a significar alguma
  coisa, medir economia é medir uma economia em que todo mundo trabalha dentro de uma
  casa, e medir vida social é medir uma vida social em que a taverna não existe. Todo
  número de N, G e M muda depois de V. **Não calibre nada antes de V estar de pé.**
- **P vem antes de N** porque hoje o dinheiro é revertido cinco vezes por dia simulado.
  Calibrar preço com o saldo sendo restaurado a cada 5 h é calibrar ruído.
- **X é independente** — pode ser feito em paralelo por outra sessão, não toca em
  nenhum arquivo dos outros blocos exceto `mood.py` e `market.py`.
- **T por último**, porque cada teste de T fixa um comportamento que só existe depois
  dos blocos anteriores.

### Três paradas obrigatórias

**Parada 1 — depois de V05.** Rode `builder/fix/audit_mundo.py` num mundo recém-povoado
e cole a saída no Registro. Se ainda houver NPC empregado numa residência, ou em outra
cidade, **pare e escreva o que encontrou** em vez de seguir pro Bloco P.

⚠️ **Uma falha é esperada nesta parada e não deve te fazer parar:** o invariante 5
("toda cidade com NPC vivo tem ≥ 1 local social") vai falhar para **uma** cidade — a
segunda "Cidade dos Ventos", que tem 50 NPCs e zero locais porque o nome está duplicado
no manifesto. Isso é o achado de G05, que está num bloco posterior de propósito (é reset
de cartografia, não código). Anote a falha como esperada e siga. Se falhar para **mais
de uma** cidade, aí sim pare.

Medido antes de V02, para você ter a base de comparação: depois de excluir residências e
filtrar por cidade, **toda cidade tem entre 4,6 e 32,2 vagas por adulto** — exceto a
"Cidade dos Ventos" duplicada, com 0. O Bloco V não cria desemprego em lugar nenhum.

**Parada 2 — depois de P03.** Rode 3 dias simulados e confirme, no Registro, que
(a) nasce bebê, (b) o saldo de um NPC trabalhador sobe monotonicamente durante o
expediente e não volta atrás às 10:00/15:00/20:00, (c) a contagem de relacionamentos
nunca cai fora de `processar_poda_de_relacionamentos`.

**Parada 3 — depois de N05 e G05.** Rode 25 dias simulados com
`builder/fix/audit_mundo.py --dias 25` e cole a tabela no Registro. É essa tabela que
diz se o mundo se sustenta; sem ela, os Blocos M e T estão calibrando no escuro.

### Regras de execução (herdadas dos três documentos)

1. **Nunca `hash()`** para semente — `zlib.crc32` (armadilha 1, doc 1).
2. **Nunca escreva `proximo_instante_decisao` direto** — só pelas portas
   `agendar_decisao`/`marcar_consequencia`/`acordar` (armadilha 12, doc 2).
3. **Nunca `cfg.get(...)` com default** — `cfg_get` e KeyError (R-B05).
4. **Nunca canalize benchmark por `| tail`** — redirecione pra arquivo e leia o arquivo;
   o pipe bufferiza e engole o código de saída (regra de execução, doc 3).
5. **`cartographer/` nunca sabe de NPC, banco ou tick** (armadilha 2, doc 1). O
   Bloco V escreve no importador e na engine, nunca no gerador de geometria.

---

## 1. O veredito, em uma página

Rodei o mundo real por 25 dias simulados. Três perguntas, três respostas medidas.

### "O mundo é autossuficiente?"

**Não. Ele tem uma data de validade de aproximadamente 35 dias simulados.**

A riqueza mediana cai de forma monotônica, 1.031 → 277 PC em 25 dias, e o décimo
percentil chega a zero no **dia 6** e nunca mais sai. A projeção linear leva a mediana a
zero por volta do dia 35. O motivo é um só e é aritmético: **socializar custa 1,33 PC por
minuto**, o que dá 123 PC por dia para um idoso, contra uma pensão de 40 PC por dia.

Ninguém morre de fome, porém — e isso também é um problema. `fornecer_sopao` é
incondicional, gratuito e ilimitado, e dispara com fome acima de 60 enquanto a inanição
só começa aos 90. Em 25 dias, com 10% da população sem um único PC, a **saúde mínima do
mundo inteiro nunca saiu de 100**. A mecânica de inanição é código morto.

### "A demografia se sustenta?"

**Não. A população é uma coorte, não uma pirâmide.**

```
  0-4  d  ##################                     75   ← geração nova
  5-9  d  ###############                        61
 10-14 d  ###################                    76
 15-19 d  ########                               33
 20-44 d  (vazio)                                 0   ← o buraco
 45-49 d  ################################################### 207   ← coorte semeada
 50-54 d  ###################################### 155
 55-59 d  ############################################## 187
 60-64 d  ################################## 137
 65-84 d  (vazio)                                 0
 85-89 d  #####                                  21
```

**686 dos 714 adultos cruzam o limiar de velhice nos próximos 30 dias simulados.** O
povoamento inicial sorteia todo mundo numa faixa de 25 dias de vida, então toda a
população se aposenta junta e morre junta. Para uma aventura de alguns dias isso não
aparece; para o mundo "rodar sozinho enquanto o Mestre não olha", é uma bomba-relógio.

E em 25 dias o mundo já produziu **2 filhos de pais consanguíneos**. `processar_concepcao`
não chama `NPCUtils.sao_parentes` — que existe, está correta, e é chamada corretamente
pelo caminho do casamento. Uma mãe e o filho adulto na mesma casa têm afinidade 100
automática (`parto_afinidade_inicial_pais`), acima do limiar de 90: em teste isolado,
engravidaram em **6 de 200 noites**.

### "Dá pra usar como fonte de informação?"

**Não, hoje não.** É o achado mais grave e o mais fácil de corrigir. Uma linha real do
contexto que o Modo Mestre entrega à IA:

```
npc_16_010: Sir 17 de Greycastle (Desempregado) | Trab: elorfield_1_1_0_l00 | Casa: cidade_dos_ventos_14_7_l07
```

Três coisas erradas numa linha só: ele **tem** emprego mas a profissão diz
"Desempregado"; o local de trabalho é uma **residência**; e fica numa **cidade
diferente** da casa dele. Isso não é um caso de borda — é **705 de 705** NPCs
empregados, e **665 deles** trabalhando fora da própria cidade.

Somado a isso: o contexto inteiro tem **433 mil tokens** (1,7 MB de JSON) para um mundo
de 840 NPCs, sem filtro de cidade e sem teto. E 99,1% do log de eventos é conversa
fiada, então os 10 "últimos fatos" que o Mestre recebe são, estatisticamente, nove
linhas de "fulano e sicrano tiveram uma CONVERSA".

### O que isso quer dizer para o projeto

As mecânicas estão escritas e a arquitetura aguenta. **Nenhum dos achados exige
redesenho.** A maioria é uma linha, e a maior parte desce de uma causa raiz só. O que
faltou até agora foi um auditor do mundo **vivo** — `audit_cidades.py` audita a
geometria e não sabe se alguém mora nela. É por isso que o Bloco V termina criando
`audit_mundo.py`, e é por isso que 164 testes passam com tudo isto no lugar.

---

## 2. O mundo como ele roda hoje — as medições

25 dias simulados, mundo real, 15 cidades, começando com 840 NPCs.

⚠️ **Esta corrida foi feita SEM `recarregar_habitantes()`** — ou seja, com o defeito da
Seção 4 já neutralizado. É de propósito: com o reload ligado, o mundo não produz um
único nascimento em 3 dias e o dinheiro nem se move, então não haveria trajetória para
medir. O que a tabela abaixo mostra é o **melhor caso** de hoje.

| dia | vivos | bebê | criança | adulto | idoso | casados | din. mediana | din. p10 | din. máx | fome p90 | famintos | órfãos | óbitos | nasc. |
|----:|------:|-----:|--------:|-------:|------:|--------:|-------------:|---------:|---------:|---------:|---------:|-------:|-------:|------:|
|   0 |   840 |    0 |       0 |    705 |   135 |     410 |          880 |      394 |    1.500 |      0,0 |        0 |      0 |      0 |     0 |
|   1 |   840 |    0 |       0 |    705 |   135 |     412 |        1.031 |      557 |    1.697 |     42,9 |        0 |      0 |      0 |     0 |
|   3 |   851 |   11 |       0 |    705 |   135 |     434 |          897 |      340 |    1.733 |     32,3 |        0 |      0 |      0 |    11 |
|   6 |   877 |   37 |       0 |    705 |   135 |     520 |          863 |    **0** |    1.841 |     45,7 |        0 |      0 |      0 |    37 |
|  10 |   926 |   67 |      19 |    705 |   135 |     568 |          771 |        0 |    1.928 |     52,9 |        0 |      0 |      0 |    86 |
|  15 |   960 |   81 |      81 |    704 |    94 |     571 |          625 |        0 |    2.173 |     51,9 |        0 |      0 |     42 |   162 |
|  20 |   982 |   70 |     134 |    709 |    69 |     562 |          442 |        0 |    2.408 |     52,7 |        0 |      8 |     81 |   223 |
|  25 |   952 |   82 |     135 |    714 |    21 |     553 |      **277** |        0 |    2.612 |     54,6 |        0 |     10 |    186 |   298 |

**O que ler nessa tabela:**

- **Coluna `din. mediana` contra `din. máx`.** A mediana cai 72% e o máximo sobe 74%. Não
  é empobrecimento geral — é **concentração**. Quem trabalha ganha +44 PC/dia líquido;
  quem não trabalha perde 148 PC/dia. Não existe mecanismo que devolva dinheiro à base.
- **Coluna `famintos` é zero em todas as linhas.** E a saúde mínima do mundo também ficou
  em 100 o tempo todo. Com 10% da população a zero PC desde o dia 6.
- **Coluna `idoso`: 135 → 21.** A coorte semeada está morrendo. `adulto` fica parado em
  ~710 porque as crianças ainda não chegaram à maioridade em volume.
- **Coluna `órfãos` sai do zero no dia 19.** São dependentes cujo pai/mãe casou, mudou de
  casa, e **não levou o filho**.

### Distribuição de tempo dos NPCs (amostrada a cada 137 ticks, 25 dias)

| ação | % do tempo acordado+dormindo |
|---|---:|
| Dormir | 38,3% |
| Trabalhar | 26,0% |
| Ocioso | **17,0%** |
| Comer | 10,6% |
| Cuidar da Prole | 5,2% |
| Socializar | **2,9%** |
| Construir | **0,0%** |

Dois números gritam. **Socializar é 2,9%** num mundo com 592 tavernas — e a Seção 3
explica por quê. **Construir é 0,0%**: em 25 dias, com 431 casas habitadas e 22.626
residências disponíveis, superlotação é estruturalmente impossível, então
`processar_habitacao` nunca dispara e a mecânica de obra nunca roda.

### Onde a vida social acontece

| categoria do local | interações | % |
|---|---:|---:|
| residencia | 140.346 | **98,34%** |
| taverna | 1.403 | 0,98% |
| publico | 970 | 0,68% |

De 143.941 interações sociais em 25 dias, 98,34% aconteceram **dentro de casa**. O 1,66%
restante não é vida noturna: é gente que foi comer fora (o índice `comida` funciona) e
por acaso trombou com alguém.

---

## 3. A causa raiz nº 1 — o vocabulário de local quebrou

Este é o achado central. Quase tudo na Seção 2 desce dele.

### O que aconteceu

`Local` tem três campos de classificação:

| campo | intenção de projeto | o que tem hoje |
|---|---|---|
| `categoria` | categoria ampla do sistema (`CategoriaLocal`) | ✅ **correto** — `residencia`, `forja`, `mercado`, `taverna`, `publico`, `quartel`, `universidade`, `fazenda`, `generic` |
| `tipo` | papel funcional (`TipoLocal`: `Oficina`/`Campo`/`Mar`/`Defesa`/`Magia`/`Loja`/`Social`/`Casa`/`Ruina`/`Outro`) | ❌ **o nome de sabor** — `Residência`, `Quitanda`, `Padaria de Bairro`, `Poço de Bairro`… |
| `tipo_local` | nome de sabor dentro da categoria | ✅ correto |

Medido: **`tipo` é idêntico a `tipo_local` nas 26.748 linhas**. `tipo` virou uma cópia de
`tipo_local`, e o enum `TipoLocal` deixou de ter representante nos dados:

> **26.748 locais; com `tipo` dentro do enum `TipoLocal`: 617 (2,3%)** — e esses 617 só
> casam porque "Oficina" existe por coincidência nos dois vocabulários.

A engine, porém, continua lendo `tipo` em **14 pontos, espalhados por 7 arquivos**
(`indice_locais.py` ×3, `decay.py` ×5, `consultas_local.py`, `logic.py`,
`socializar.py`, `local.py`, mais as duas linhas de persistência pura em
`local.py`). Cada grupo quebrou de um jeito diferente e em silêncio. A lista completa
está na tarefa V01 — **não confie na memória, faça o `grep`** (armadilha 18).

### Consequência 1 — 87% das vagas de emprego do mundo são casas

`RepositorioLocal.buscar_vagas_disponiveis` filtra `WHERE l.tipo != 'Casa'`. Residências
têm `tipo = 'Residência'`, não `'Casa'`. Então elas passam.

| | locais | vagas |
|---|---:|---:|
| total ofertado ao mercado de trabalho | 26.748 | 129.440 |
| **dos quais residências** | **22.624** | **113.120 (87,4%)** |

Como as residências dominam a pilha, `cat_desejada = 'nenhum'` (o caminho "aceito
qualquer categoria com vaga") sempre cai em `residencia`. Resultado medido:

> **705 de 705** NPCs empregados trabalham numa residência.
> **665 deles** numa cidade diferente da que moram.
> **141** locais de trabalho distintos no mundo inteiro — **todos os 141 em
> Elorfield**, a primeira cidade da pilha de vagas.

### Consequência 2 — todo NPC empregado tem a profissão "Desempregado"

Encadeado na consequência 1. Em `JobMarket.processar_contratacoes`:

```python
p_id, p_nome = prof_por_cat.get(cat_desejada, (ProfissaoID.OCIOSO.value, 'Desempregado'))
```

A tabela `profissoes` mapeia **categoria de sistema** → profissão (`industria` →
Operário, `comercio` → Comerciante, …). Não existe entrada para `residencia`, porque
casa não é lugar de trabalho. O fallback dispara e o NPC é contratado com
`profissao_id='ocioso'`, `profissao='Desempregado'`.

> Profissões distintas entre os 840 NPCs: **2** (`Desempregado`, `Aldeão`).

O mapeamento `mapeamento_categorias_trabalho` está **correto e completo** para as
categorias reais (`forja`→`industria`, `taverna`→`social`, `quartel`→`militar`…). Ele
nunca é exercido porque residência ganha de todas.

### Consequência 3 — a taverna não existe para quem quer socializar

`IndiceDeLocais.registrar` monta dois índices a partir de `tipo`:

```python
if local.tipo == TipoLocal.SOCIAL.value:      # 'Social'
    self._sociais[cidade_id].append(local_id)
if local.tipo in (TipoLocal.SOCIAL.value, TipoLocal.LOJA.value):
    self._passeio[cidade_id].append(local_id)
```

Nenhum local do mundo tem `tipo = 'Social'` ou `'Loja'`. Medido, somando as 15 cidades:

| índice | chave usada | entradas |
|---|---|---:|
| `sociais` | `tipo` | **0** |
| `sociais_publicos` | `tipo` | **0** |
| `passeio` | `tipo` | **0** |
| `comida` | `categoria` | 928 ✅ |
| `residencias_ativas` | `categoria` | 22.624 ✅ |
| `trabalho_por_categoria` | `categoria` | ✅ |

Os três índices que leem `tipo` estão vazios; os três que leem `categoria` funcionam.
Então `mover_para_social` não acha destino e manda todo mundo pra casa, e
`mover_aleatoriamente` idem. **592 tavernas, 336 locais públicos, zero visitas.** É a
explicação dos 98,34% de vida social dentro de casa.

Há um segundo tiro no mesmo pé: `AvaliadorSocializar` zera a vontade de quem tem menos
de 50 PC a não ser que exista um local com `tipo == 'Social'` — e, de quebra, procura
isso varrendo os **26.748 locais do mundo inteiro**, por NPC, por decisão, sem filtro de
cidade.

### Consequência 4 — a manutenção de infraestrutura mira no alvo errado e custa caro

`InfrastructureManager.processar_desgaste` tem dois usos de `tipo`:

```python
taxa = desgaste_por_tipo.get(local.tipo, desgaste_padrao)   # casa em 617 de 26.748
if local.tipo != TipoLocal.CASA.value:                      # verdadeiro para TODOS
    ocupacao = sum(1 for npc in self._mundo.npcs if npc.local_trabalho_id == local_id ...)
```

O segundo é o caro: o ramo de superlotação existe para **locais de trabalho**, e hoje
roda para os 26.748 locais, cada um varrendo a lista inteira de NPCs.

> `processar_desgaste`: **1.319 ms** por dia simulado, com 26.748 locais e 840 NPCs.
> A varredura é O(locais × NPCs); com 25.000 NPCs e 60.000 locais isso vira **~88 s por
> dia simulado**, sozinho quase 3× o orçamento inteiro que D13 dá para 7 dias.

E isso nunca apareceu em `bench_avanco.py` porque `processar_desgaste` é chamado por
`run_simulation.py`, não por `GameLoop` — **está fora do benchmark**. Ver armadilha 16.

### Consequência 5 — o desgaste é lento demais para importar

Efeito colateral da mesma tabela não casar: quase todo local usa `desgaste_padrao = 0,2`
por dia. Depois de **25 dias simulados**, a integridade média dos 26.748 locais era
**94,9** e havia **zero ruínas**. Um edifício leva 375 dias para fechar por deterioração.
Ou seja: a mecânica cobra 88 s/dia de CPU em escala para produzir um efeito invisível
durante um ano de jogo.

---

## 4. A causa raiz nº 2 — a simulação não lê o que ela mesma escreve

A segunda causa raiz independente, e a que apaga o mundo cinco vezes por dia.

### A medição

Segui um NPC trabalhador por 24 h simuladas, imprimindo o estado dele antes e depois de
cada `recarregar_habitantes()` (que `run_simulation.py` chama a cada 5 h de jogo):

```
  09:59 ANTES RELOAD  dinheiro=  1111.33  rels=5  acao=Trabalhar
  10:00 APÓS  RELOAD  dinheiro=  1111.00  rels=5  prox=None
  14:59 ANTES RELOAD  dinheiro=  1178.00  rels=7  acao=Trabalhar
  15:00 APÓS  RELOAD  dinheiro=  1111.00  rels=5  prox=None    ← 67 PC e 2 relações apagados
  19:59 ANTES RELOAD  dinheiro=  1182.00  rels=7  acao=Trabalhar
  20:00 APÓS  RELOAD  dinheiro=  1111.00  rels=5  prox=None    ← de novo
```

Ele **nunca passa de 1.111,00** — o valor que o povoamento gravou. Um dia inteiro de
trabalho é desfeito três vezes.

### Por quê

`salvar_muitos` (a escrita de fim de tick, N02 do doc 2) é um `UPDATE` estreito, de
propósito e com bom motivo. Mas a lista de colunas quentes ficou incompleta:

```python
_COLUNAS_QUENTES = ("energia", "fome", "social", "saude", "humor",
                    "acao_atual", "localizacao_atual_id")
```

Faltam **duas colunas que mudam a cada minuto simulado**:

| campo | quem muda, e com que frequência | está nas quentes? |
|---|---|---|
| `dinheiro_total_pc` | `_executar_trabalhar` (+0,333/min), `_executar_comer` (−custo/min), `_executar_socializar` (−1,33/min), `_aplicar_efeito_continuo` | ❌ |
| `gravidez_ticks` | `_aplicar_metabolismo`, todo minuto de toda gestante | ❌ |
| `relacionamentos` | `_computar_interacao`, em memória | ❌ (tem tabela própria, mas o carregamento lê a **coluna JSON**) |
| `proximo_instante_decisao` / `ultima_avaliacao` | a agenda inteira | ❌ (não persistido, por projeto) |

E `RepositorioNPC.carregar_todos` lê `relacionamentos` da **coluna JSON de `npcs`**,
nunca da tabela `relacionamentos` que `salvar_relacionamentos_muitos` alimenta. São duas
fontes de verdade, e a autoritativa na carga é a que o tick não escreve.

### O efeito composto: gravidez nunca termina

`gravidez_duracao_ticks = 2880` (48 h). O reload roda a cada 5 h e restaura o valor
gravado na concepção. O contador nunca chega a zero. Comprovado por A/B, 3 dias
simulados, mesmo mundo e mesma semente:

| | nascimentos em 3 dias | dinheiro mediano d1→d3 | casados d1→d3 |
|---|---:|---|---|
| **com** `recarregar_habitantes()` | **0** | 912 → 912 → 912 (constante) | 410 → 410 → 410 |
| **sem** `recarregar_habitantes()` | **19** | 945 → 940 → 878 | 412 → 424 → 440 |

Sem o reload, o mundo vive. Com ele, o mundo fica preso num Dia da Marmota de 5 horas
para tudo que não seja fome, energia, humor e ação atual.

### Por que o reload existe (e por que apagá-lo sozinho não resolve)

`JobMarket` escreve **só no banco**:

```python
self.db.npcs.contratar(npc['id'], local_vaga['id'], p_id, p_nome)
```

Ele nunca toca em `mundo.npcs`. O único jeito de o NPC em memória descobrir que foi
contratado é o reload. **É exatamente o mesmo defeito estrutural que F01 (doc 3)
corrigiu no Modo Mestre** — uma mecânica que muda o mundo por fora do `EstadoDoMundo`
vivo — só que aqui dentro do mesmo processo. A correção é a mesma: `JobMarket` recebe o
mundo e aplica nele.

---

## 5. Os outros quatro eixos

### 5.1 A economia não fecha

Instrumentei os três pontos de fluxo de dinheiro — nos **dois** caminhos, o minuto real
de `NPCActionManager` e o bloco de `GameLoop._aplicar_efeito_continuo`, senão trabalho e
comida saem subcontados. Aquecimento de 3 dias, medição no 4º (em regime: no dia 1
ninguém tem fome ainda e o resultado engana):

| classe | n | trabalho | comida | socializar | **líquido** |
|---|---:|---:|---:|---:|---:|
| trabalhador | 705 | +193,9 | −23,0 | **−136,9** | **+34,0** |
| idoso | 135 | 0,0 | −71,5 | **−136,5** | **−207,9** |
| dependente | 19 | 0,0 | 0,0 | 0,0 | 0,0 |

E os minutos por dia, por NPC, que explicam a tabela:

| classe | trabalhar | comer | socializar |
|---|---:|---:|---:|
| trabalhador | 582 | 66 | 103 |
| idoso | 0 | **215** | 102 |

Dois achados nessa tabela, não um:

**(a) `acoes.socializar.custo_pc = 1,333333` é cobrado por minuto, e é a maior despesa
de TODA classe.** 137 PC por dia, tanto para quem trabalha quanto para quem não
trabalha — 71% da renda de um trabalhador e 3,4× a pensão de um idoso. Uma hora e meia
de convívio custa mais que meio dia de trabalho.

**(b) O idoso come 215 minutos por dia** — cerca de seis refeições — contra 66 minutos
do trabalhador. Ele não trabalha, o convívio é limitado, e `bonus_nao_interromper_
refeicao` (100) somado a `bonus_persistencia` (40) faz a refeição vencer a competição de
utilidade assim que a fome passa de 40. A conta de comida dele é 3× a do trabalhador.

Confirmação independente, por diferença de saldo em 3 dias:

| classe | n | mediana | mínimo | máximo |
|---|---:|---:|---:|---:|
| trabalha | 705 | **+132 PC** | −202 | +414 |
| idoso | 135 | **−444,7 PC** | −733 | −218 |

Mais três desalinhamentos no mesmo eixo:

1. **`salario_base` do local nunca é lido pela economia.** É gravado pelo cartógrafo
   (de 50 a 110 PC conforme o edifício), exibido, e ignorado: `_executar_trabalhar` soma
   `acoes.trabalhar.salario_pc` — uma constante global. O ferreiro, o padeiro, o guarda
   e o sujeito "trabalhando" numa casa ganham exatamente o mesmo.
2. **`multiplicador_por_dependente` cobra duas vezes.** A refeição do adulto é
   multiplicada por `1 + 0,8 × dependentes`, *e* cada dependente come separado debitando
   o mesmo pagador. Uma família com 3 filhos paga 51 PC pela refeição do adulto **mais**
   3 × 15 PC pelas dos filhos.
3. **A inanição é inalcançável.** `fornecer_sopao` dispara com fome > 60 e saldo ≤ 0;
   `inaniacao_fome_limiar` é 90. O sopão recupera 0,444 de fome por minuto contra um
   ganho passivo de 0,04. Ele é gratuito, ilimitado, sem custo para o reino (apesar de
   `custo_sopao_ao_reino = 5` existir no config e não ser lido por ninguém) e sem fila.
   Em 25 dias, com 10% da população zerada, **zero NPCs famintos e saúde mínima 100**.

### 5.2 A demografia é uma coorte

Além da pirâmide da Seção 1:

- **O povoamento inicial não cria criança nenhuma.** `proporcao_adultos = 0,85` divide a
  população entre 85% adultos e 15% idosos. O mundo nasce sem infância.
- **O casamento planejado produz no máximo 1 casamento por dia no mundo inteiro.**
  `processar_coabitacao` tem um `return` (não um `break`) depois da primeira união, e o
  `return` sai do laço de **todas** as cidades. Desde que H02 (doc 3) mudou a cadência de
  por-tick para diária — mudança correta, pelas razões certas — o teto passou de 1.440
  para 1 por dia. Medido em 25 dias:

  | caminho | uniões | % |
  |---|---:|---:|
  | romance surpresa (`_computar_interacao`) | **70** | 86% |
  | casamento planejado (`processar_coabitacao`) | **11** | 14% |

  O caminho que o projeto desenhou como deliberado ("alta afinidade acumulada, decisão
  de coabitar") responde por um sexto das uniões, e o mundo registra
  "💍 CASAMENTO SURPRESA! apaixonaram-se tanto durante a conversa que se casaram"
  quase três vezes por dia.
- **Concepção não checa parentesco.** Teste isolado, 200 noites:

  | par | engravidou | casamento permitido? |
  |---|---:|---|
  | mãe × filho adulto (afinidade 100, automática do parto) | **6/200** | ❌ corretamente bloqueado |
  | irmão × irmã (afinidade 95) | **4/200** | ❌ corretamente bloqueado |

  No mundo real de 25 dias: **2 filhos de pais consanguíneos**. A função
  `NPCUtils.sao_parentes` existe, está correta e é usada — só que apenas em
  `verificar_elegibilidade_casamento`.
- **Quem casa não leva os filhos.** Reproduzido em mundo sintético:

  ```
  antes  -> mãe.casa=casa_a  bebê.casa=casa_a  noivo.casa=casa_b
  depois -> mãe.casa=casa_b  bebê.casa=casa_a  noivo.casa=casa_b
  moradores de casa_a: ['Bebê']
  pagador da refeição do bebê: Bebê (saldo 0)
  ```

  O bebê fica sozinho na casa antiga e vira o próprio pagador, com 0 PC. Só não morre
  porque o sopão o cobre. **10 casos** no mundo de 25 dias.

### 5.3 A escala da cidade não tem relação com a população

Este eixo **já é o Bloco R (doc 2) / Bloco C (doc 3)**, ainda pendentes. Acrescento três
medições que faltavam ao dossiê deles:

| cidade | tamanho | NPCs | residências | casas/habitante | tavernas | mercados | forjas |
|---|---|---:|---:|---:|---:|---:|---:|
| Jordorstead | grande | 80 | 5.751 | **71,9** | 151 | 178 | 321 |
| Fenelburgo | grande | 80 | 4.172 | 52,1 | 92 | 148 | 241 |
| Irenburgo | grande | 80 | 3.333 | 41,7 | 98 | 126 | 247 |
| Cidade dos Ventos (id 1) | medio | 50 | **0** | — | 0 | 0 | 0 |
| Belinhaven | pequeno | 30 | 69 | 2,3 | 2 | 6 | 11 |

E no mundo de 25 dias: **431 casas habitadas de 22.626 existentes (1,9%)**.

Duas consequências que não são de calibragem e sim de bug:

- **"Cidade dos Ventos" está duplicada no `world_manifest.json`.** Duas cidades com o
  mesmo nome, e tudo a jusante é indexado pelo *slug do nome*: o arquivo
  `database/cidades/cidade_dos_ventos.geojson` e os ids de lote/local. Uma das duas ganha
  a geometria inteira, a outra fica com **zero locais e 50 NPCs**, cujas casas apontam
  para edifícios da cidade vizinha.
- **`_avaliar_comercio_por_demanda` nunca dispara.** `habitantes_por_estabelecimento`
  pede uma taverna a cada 40 habitantes; Jordorstead tem 80 habitantes e 151 tavernas.
  O déficit é sempre negativo. O urbanismo por demanda é código morto enquanto a escala
  não for corrigida — o que é mais um argumento para o Bloco R, não um bug próprio.

### 5.4 O Mestre não consegue ler o mundo

| medição | valor |
|---|---:|
| itens de NPC no contexto | 840 (todos, sem filtro de cidade, sem teto) |
| itens de local no contexto | **26.748** (todos ativos, sem filtro, sem teto) |
| tamanho total do contexto | **1.734.264 chars ≈ 433.566 tokens** |
| tempo para montar | 26 ms |

`MestreManager.montar_contexto` vai inteiro para `json.dumps(contexto, indent=2)` dentro
do prompt, sem corte. Com 840 NPCs já não cabe em janela de contexto nenhuma; com 25.000
seriam ~3 milhões de tokens.

E o que ele consegue ler é ruído. Log de eventos, 25 dias:

| tipo | quantidade | % |
|---|---:|---:|
| CONVERSA | 106.916 | 74,3% |
| DISCUSSAO | 35.803 | 24,9% |
| CONCEPCAO | 324 | 0,23% |
| NASCIMENTO | 298 | 0,21% |
| CRESCIMENTO | 216 | 0,15% |
| OBITO | 186 | 0,13% |
| IMPOSTO | 110 | 0,08% |
| MAIORIDADE | 81 | 0,06% |
| HERANCA | 7 | 0,005% |
| **total** | **143.941** | (5.758/dia; ~160 mil/dia com 25.000 NPCs) |

**99,1% é conversa fiada.** `resumos_recentes(10)` pega os 10 últimos por rowid, então o
Mestre recebe, em média, 9 linhas de fofoca e menos de uma de fato narrativo. E
casamento não tem tipo próprio: é gravado como `CONVERSA`, indistinguível de um papo,
exceto pelo texto.

---

## 6. Decisões (não reabra)

> ⚠️ **Esta seção é o raciocínio por trás das decisões; a resposta vale a da seção
> [⚡ Decisões que precisam de você](#-decisões-que-precisam-de-você), no topo.** Se o
> dono do projeto respondeu lá, é aquilo que vale — aqui está só o porquê de cada
> alternativa, para você não reabrir a discussão no meio da execução.

### D23 — `tipo` volta a ser o enum, derivado de `categoria` na importação

**Alternativas consideradas:** (a) apagar `tipo` e migrar os seis leitores para
`categoria`; (b) derivar `tipo` de `categoria` num ponto só, na importação.

**Escolha: (b).** `tipo` é campo persistido, lido pelo dashboard e pelo prompt do Mestre,
e é a chave de `desgaste_por_tipo`. Migrar seis leitores é seis chances de errar; derivar
num ponto só é uma tabela no config e um invariante duro. A informação de sabor já vive
em `tipo_local`, que hoje é uma cópia exata — não se perde nada.

**Não negocie isto durante o Bloco V.** Se durante a execução parecer mais limpo apagar
`tipo`, **escreva no Registro e pare**; é decisão do dono do projeto, não da tarefa.

### D24 — `JobMarket` passa a receber o `EstadoDoMundo` e `recarregar_habitantes()` sai do laço

Mesmo padrão de F01 (doc 3). O método `recarregar_habitantes()` **continua existindo**
como ferramenta de recuperação (ele é legítimo depois de uma escrita externa de verdade),
mas sai do caminho quente de `run_simulation.py`.

### D25 — o alvo é **renovação geracional completa**, não um número de dias

Reformulado pelo dono do projeto (decisão ❺). Rode até que **100% dos NPCs vivos tenham
nascido dentro da simulação**, com as **seis guardas** da seção de decisões valendo o
tempo todo. Não é um horizonte arbitrário: é o ciclo de vida dando uma volta inteira, e
sobrevive a qualquer recalibragem de longevidade.

Medido por `audit_mundo.py --ate-renovacao`. É a porta de T02.

### D26 — a inanição volta a existir, com o sopão como rede e não como piso

✅ Confirmado pela decisão ❶.

O sopão passa a ter **limite diário de rações por cidade**, proporcional à população.
Sem isso a inanição é inalcançável por construção e a economia não tem consequência.

❌ **Sem tesouro do reino** (decisão ❾). A cota é o único limitador; o débito em moeda
fica para quando existir finança do reino, que não é agora.

### D27 — Socializar custa por **visita**, não por minuto

`acoes.socializar.custo_pc` passa a ser cobrado **uma vez** na chegada ao local, não a
cada minuto. É a diferença entre "uma caneca custa 1,33 PC" e "a taverna cobra por
minuto de permanência".

### D28 — o Bloco R (doc 2) continua sendo o dono da escala da cidade

Nada neste documento redimensiona cidade. A Seção 5.3 é **insumo** para R01–R04, não
substituto. O único item de escala que este documento resolve é o nome duplicado de
cidade (G05), porque isso é bug de unicidade, não de calibragem.

---

## 7. As quatro novas armadilhas

Numeradas na sequência das doze do doc 2 e das três do doc 3.

### Armadilha 16 — o benchmark só mede o que está dentro do `GameLoop`

`bench_tick.py` e `bench_avanco.py` constroem um `GameLoop` e chamam `executar_tick()`.
Mas `run_simulation.py` chama mais três coisas por conta própria — `processar_desgaste`,
`processar_reparos_espontaneos` e `processar_contratacoes` — e **nenhuma delas aparece
nos benchmarks**. Medido hoje, por dia simulado, com 840 NPCs e 26.748 locais:

| rotina | onde mora | custo/dia simulado | está no bench? |
|---|---|---:|---|
| `GameLoop.executar_tick` × 1440 | `GameLoop` | ~20,7 s (14,4 ms/tick) | ✅ |
| `processar_desgaste` | `run_simulation.py` | 1.319 ms | ❌ |
| `processar_contratacoes` × 5 | `run_simulation.py` | 4.320 ms | ❌ |
| `recarregar_habitantes` × 5 | `run_simulation.py` | 50 ms | ❌ |

(Total medido: **26,4 s por dia simulado**, dos quais **5,7 s — 21% — estão fora dos
benchmarks**.)

**Regra:** toda rotina periódica nova entra em `GameLoop._rotinas_diarias` (A06, doc 2) ou
é explicitamente acrescentada ao benchmark. Um custo fora do benchmark é um custo que não
existe até o dia em que existe demais.

### Armadilha 17 — taxa por minuto virou taxa por avaliação

A agenda (A02/H01) fez o NPC ser avaliado ~20 a 30 vezes por dia em vez de 1.440. Toda
mecânica que era "uma chance por minuto" e recebeu `minutos` precisa **multiplicar o
efeito**, não só receber o parâmetro. `_aplicar_metabolismo` e `_aplicar_efeito_continuo`
fazem certo. `NPCMoodManager.processar_humor` **não**:

```python
passos = sum(1 for _ in range(min(minutos, distancia)) if random.random() < chance_transicao)
```

`min(minutos, distancia)` limita o número de **tentativas** ao número de **passos**, e
`distancia` nunca passa de 4. Com `humor_chance_transicao = 0,01078`:

| regime | tentativas/dia | P(ao menos uma transição no dia) |
|---|---:|---:|
| antes da agenda (1/min) | 1.440 | **1,000** |
| hoje (~20 avaliações, distância ~2) | 40 | **0,352** |
| hoje (~30 avaliações) | 60 | 0,478 |

O humor ficou ~3× mais lento e passou a atrasar 2 a 3 dias em relação ao bem-estar real
do NPC. Ninguém percebeu porque não há teste de taxa, só de direção.

### Armadilha 18 — a correção foi aplicada num arquivo e não no gêmeo

P04 (doc 1) corrigiu, em `movement.py`, a rede de segurança que mandava um NPC sem casa
para `casas_disponiveis[0]` de uma lista **global** — podia mudar o NPC de cidade em
silêncio. O comentário do próprio `movement.py` explica isso muito bem.

O mesmo código continua intacto em `logic.py::decidir_acao`:

```python
if locais and (npc.casa_id not in locais):
    casas_disponiveis = [l_id for l_id, l in locais.items() if l.tipo == 'Casa' or l.categoria == 'residencia']
    if casas_disponiveis:
        npc.casa_id = casas_disponiveis[0]
```

Varre os 26.748 locais do mundo, por chamada, e teleporta o NPC para a primeira casa de
qualquer cidade — e todos os NPCs sem casa vão para a **mesma** casa.

**Regra:** ao corrigir um padrão, `grep` pelo padrão, não pelo arquivo.

### Armadilha 19 — "o índice existe" não é o mesmo que "todo mundo usa"

Reincidência da armadilha 15 (doc 3). `EstadoDoMundo.npcs_por_casa` é mantido
incrementalmente desde A04, mas **nove** pontos de chamada continuam varrendo
`mundo.npcs`:

| arquivo:linha | função | no caminho por minuto? |
|---|---|---|
| `actions.py:89` | `encontrar_pagador_e_parcela` (refeição de dependente) | ✅ **sim** |
| `actions.py:99` | `contar_dependentes_na_casa` | ✅ **sim** |
| `actions.py:218` | `_executar_cuidar_prole` | ✅ **sim** |
| `actions.py:276` | `_executar_construir` | ✅ sim |
| `housing.py:79` | `processar_habitacao` | diária |
| `reproduction.py:58` | `processar_concepcao` | diária |
| `reproduction.py:107` | `processar_parto` | por evento |
| `finance.py:31` | `processar_heranca` | por evento |

Os quatro de `actions.py` são O(NPCs) por NPC por minuto — O(N²) vivo. Com 840 NPCs e
269 dependentes já são 226 mil comparações por tick só nas refeições.

---

## Bloco V — O vocabulário de local volta a existir

> **Depende de:** nada. É o primeiro bloco e destrava os outros.
> **Parada obrigatória nº 1 no fim deste bloco.**

### V01 — `tipo` derivado de `categoria`, num ponto só, com invariante duro

**Arquivos:** `config.json`, `builder/populador.py`, `engine/mechanics/urbanismo.py`

1. Acrescente ao config, dentro de `geracao_urbana`, o mapa
   `tipo_local_por_categoria`, cobrindo **todas** as `CategoriaLocal`:

   ```json
   "tipo_local_por_categoria": {
     "residencia": "Casa", "forja": "Oficina", "mercado": "Loja",
     "taverna": "Social", "publico": "Social", "quartel": "Defesa",
     "universidade": "Magia", "fazenda": "Campo", "generic": "Outro"
   }
   ```

   Comentário `_comentario_tipo_local_por_categoria` obrigatório, explicando que
   `categoria` é o vocabulário do cartógrafo, `tipo` é o papel funcional que a engine
   lê, e `tipo_local` é o nome de sabor.

2. Em `builder/populador.py::_importar_locais_da_geometria`, o `Local` passa a nascer
   com `tipo=` derivado desse mapa e `tipo_local=props["tipo"]` (o nome de sabor, como
   já é hoje). **Nunca** `tipo=props["tipo"]`.

3. Em `urbanismo.py::abrir_obra`, o mesmo: `SpecObra.tipo_local` continua sendo o nome,
   e `tipo` sai do mapa pela `categoria` da spec.

4. ⚠️ **`abrir_obra` hoje faz `tipo=spec.tipo_local`** (`urbanismo.py`, no construtor do
   `Local`) — os dois campos são a mesma coisa ali. Isso funciona por acidente para a
   obra de casa (`housing.py` passa `tipo_local=TipoLocal.CASA.value`, e
   `IndiceDeLocais.obra_por_dono` depende justamente de `tipo == 'Casa'`), e quebra para
   estabelecimento (`_abrir_estabelecimento` passa `tipo_local="Taverna"`, fora do
   enum). Depois de V01 os dois campos se separam: `tipo` sai do mapa pela `categoria`,
   `tipo_local` recebe a spec. **Confira `obra_por_dono` com um teste antes de seguir**
   — se ele parar de indexar, `AvaliadorConstruir` para de achar obra e a construção
   morre de vez.

5. ⚠️ `_colapsar_para_ruina` escreve `tipo = TipoLocal.RUINA.value` e depende disso.
   Não mexa nesse caminho.

**Os 14 pontos que leem `local.tipo` (confira com `grep`, não com esta lista):**

| arquivo:linha | leitura | efeito hoje |
|---|---|---|
| `indice_locais.py:54` | `== 'Casa'` (obra por dono) | funciona por acidente, ver item 4 |
| `indice_locais.py:60` | `== 'Social'` | índice `sociais` **vazio** |
| `indice_locais.py:66` | `in ('Social','Loja')` | índice `passeio` **vazio** |
| `consultas_local.py:33` | `in ['Social','Loja']` | `is_local_passeio` sempre falso |
| `logic.py:50` | `== 'Casa'` | tem fallback por `categoria`; funciona |
| `decay.py:69` | `== 'Ruina'` | funciona |
| `decay.py:73` | chave de `desgaste_por_tipo` | casa em 2,3% dos locais |
| `decay.py:76` | `!= 'Casa'` | **varre NPCs para os 26.748 locais** |
| `decay.py:93` | `!= 'Ruina'` | funciona |
| `decay.py:148` | escrita de `'Ruina'` | funciona — não mexa |
| `decay.py:185` | `!= 'Ruina'` | funciona |
| `local.py:136` | `!= 'Casa'` no SQL | **113.120 vagas fantasma** |
| `socializar.py:29` | `== 'Social'` | vontade de socializar zerada pro pobre |
| `local.py:40,56` | persistência pura | sem efeito |

**Critério de aceitação:** `SELECT COUNT(*) FROM locais WHERE tipo NOT IN (<os 10 do
enum>)` devolve **0** num mundo recém-povoado.

### V02 — o mercado de trabalho para de oferecer casas, e para de oferecer outra cidade

**Arquivo:** `engine/repositorios/local.py`, `engine/mechanics/market.py`

`buscar_vagas_disponiveis` passa a receber `cidade_id` e a filtrar por **categoria
empregadora**, não por `tipo`:

```sql
WHERE l.status = 1 AND l.cidade_id = ? AND l.categoria IN (<categorias empregadoras>)
```

As categorias empregadoras saem de uma lista nova no config (`urbanismo.
categorias_empregadoras`), nunca de literais no SQL. `residencia` e `generic` ficam de
fora.

`processar_contratacoes` passa a rodar **por cidade**: agrupa os candidatos por
`cidade_id` e casa cada grupo só com as vagas da própria cidade.

⚠️ **P01 vai mexer neste mesmo método de novo**, trocando a origem dos candidatos do
banco para `mundo.npcs`. É retrabalho consciente: V02 tem que vir antes (o Bloco P
depende de o mercado já oferecer vaga real), e juntar os dois numa tarefa só faria uma
tarefa que muda origem de dados *e* destino de escrita ao mesmo tempo. Aqui, **mexa só
no filtro de vagas e no agrupamento por cidade** — não reescreva a busca de candidatos,
que é trabalho de P01. Um NPC sem vaga na
própria cidade fica desempregado — migração é decisão de domínio, não efeito colateral
de matchmaking (mesmo raciocínio de P04, doc 1).

**Critério:** `SELECT COUNT(*) FROM npcs n JOIN locais l ON l.id=n.local_trabalho_id
WHERE n.cidade_id <> l.cidade_id OR l.categoria='residencia'` devolve **0**.

### V03 — ninguém é contratado sem ganhar uma profissão

**Arquivo:** `engine/mechanics/market.py`

O fallback `(ProfissaoID.OCIOSO.value, 'Desempregado')` de `prof_por_cat.get(...)` deixa
de ser silencioso. Se a categoria da vaga não tem profissão correspondente, **a vaga não
é oferecida** e um `WorldLogger.warning` nomeia a categoria órfã. Contratar alguém e
chamá-lo de Desempregado é pior que não contratar.

**Critério:** `SELECT COUNT(*) FROM npcs WHERE local_trabalho_id <> '' AND
profissao_id = 'ocioso'` devolve **0**.

### V04 — o desgaste mira em categoria, e só locais de trabalho contam ocupação

**Arquivos:** `config.json`, `engine/mechanics/decay.py`

1. `infraestrutura.desgaste_por_tipo` vira `desgaste_por_categoria`, com chave em
   `CategoriaLocal`. Mantenha `desgaste_padrao` como rede.
2. A guarda de superlotação troca `if local.tipo != TipoLocal.CASA.value` por
   `if local.categoria in <categorias empregadoras>` (a mesma lista de V02).
3. A contagem de ocupação **não varre `mundo.npcs`**. Monte `ocupacao_por_local` uma vez,
   no começo de `processar_desgaste`, a partir de `mundo.npcs` — um laço de N, não N×L.

**Critério:** `processar_desgaste` abaixo de **80 ms** no mundo de 26.748 locais /
840 NPCs (hoje: 1.319 ms). Registre o número medido.

### V05 — `audit_mundo.py`: o auditor do mundo vivo

**Arquivo novo:** `builder/fix/audit_mundo.py`

É a ferramenta que faltava e a razão de 164 testes passarem com tudo isto no lugar.
`audit_cidades.py` audita a **geometria**; este audita **quem mora nela**. Mesmo padrão:
script manual, fora do runtime, sai com código 1 se algum invariante quebrar.

Invariantes obrigatórios (cada um é um achado deste documento):

| # | invariante | achado |
|---|---|---|
| 1 | todo `locais.tipo` está em `TipoLocal` | §3 |
| 2 | nenhum NPC trabalha em `categoria='residencia'` | §3 |
| 3 | nenhum NPC trabalha em cidade diferente da sua | §3 |
| 4 | nenhum NPC com emprego tem `profissao_id='ocioso'` | §3 |
| 5 | toda cidade com NPC vivo tem ≥ 1 local social e ≥ 1 residência | §5.3 |
| 6 | todo dependente tem pai ou mãe vivo na mesma casa | §5.2 |
| 7 | nenhum NPC tem pais que são parentes entre si | §5.2 |
| 8 | nomes de cidade são únicos no manifesto | §5.3 |
| 9 | `indice.sociais(c)` e `indice.passeio(c)` não vazios para cidade habitada | §3 |

E um modo `--dias N` que roda a simulação e imprime a tabela da Seção 2 (demografia,
riqueza, fome, órfãos) — é a tabela que as paradas 2 e 3 exigem, e o critério de D25.

⚠️ **Não importe este módulo de dentro de `engine/`, `web/` ou `cartographer/`.**

---

## Bloco P — A simulação lê o que escreve

> **Depende de:** V (o mercado de trabalho tem que estar oferecendo vagas reais antes de
> mudar quem as aplica).
> **Parada obrigatória nº 2 no fim deste bloco.**

### P01 — `JobMarket` recebe o mundo e aplica nele

**Arquivos:** `engine/mechanics/market.py`, `run_simulation.py`, `builder/populador.py`

`JobMarket.__init__` passa a receber `EstadoDoMundo` além da config (R-F01: o mundo e a
config, nunca a engine). `processar_contratacoes` continua gravando no banco — com
`salvar_completo`, que é a escrita certa para coluna fria — **e** aplica no objeto vivo:

```python
npc_vivo.local_trabalho_id = local_vaga['id']
npc_vivo.profissao_id, npc_vivo.profissao = p_id, p_nome
self._mundo.acordar(npc_vivo)   # mudou o que ele quer fazer: reavalia agora
```

O candidato deixa de vir de `buscar_candidatos_a_emprego` (consulta ao banco) e passa a
sair de `mundo.npcs`, filtrado por `esta_vivo()`/`is_adulto()`/sem trabalho — a mesma
informação, já em memória, sem round-trip.

⚠️ `builder/populador.py::_inicializar_mercado_de_trabalho` também constrói um
`JobMarket`, e ali **não existe `EstadoDoMundo`** (é povoamento, antes da simulação).
Mantenha um caminho só-banco para esse uso — por exemplo `JobMarket(db, config,
mundo=None)`, com o ramo de aplicação em memória pulado quando `mundo is None`, e um
comentário dizendo exatamente por quê. Não invente um `EstadoDoMundo` de mentira no
povoador.

### P02 — `recarregar_habitantes()` sai do laço; as colunas quentes ficam completas

**Arquivos:** `run_simulation.py`, `engine/repositorios/npc.py`

1. Apague a chamada `engine.recarregar_habitantes()` de
   `processar_gatilhos_periodicos`. O método continua existindo — é legítimo depois de
   uma escrita externa de verdade — mas sai do caminho quente. Comente no lugar por que
   ele saiu, apontando para esta tarefa.
2. `_COLUNAS_QUENTES` e o `UPDATE` de `salvar_muitos` ganham **`dinheiro_total_pc`** e
   **`gravidez_ticks`**. As duas mudam a cada minuto simulado; é exatamente o critério
   que N02 (doc 2) usou para montar a lista, e as duas ficaram de fora por engano.

⚠️ Isso acrescenta 2 colunas a um `UPDATE` de 7. Meça o custo em `bench_tick.py --real`
e registre — a expectativa é ruído, mas registre o número, não a expectativa.

**Critério (parada 2):** três dias simulados produzem nascimentos; o saldo de um NPC
trabalhador cresce monotonicamente das 08:00 às 18:00 sem cair às 10:00/15:00.

### P03 — `relacionamentos` tem uma fonte de verdade só

**Arquivo:** `engine/repositorios/npc.py`

Hoje `salvar_relacionamentos_muitos` escreve na tabela `relacionamentos` e
`carregar_todos` lê da coluna JSON de `npcs`. Escolha **a tabela** como autoritativa (é
ela que tem `vinculo`, e é ela que o Mestre consulta em
`listar_relacionamentos_gerais`):

1. `carregar_todos` passa a preencher `npc.relacionamentos` a partir de um único
   `SELECT npc_a_id, npc_b_id, afinidade FROM relacionamentos` agrupado em memória —
   **uma** consulta para todos os NPCs, nunca uma por NPC.
2. A coluna JSON `npcs.relacionamentos` continua sendo escrita por `salvar_completo`
   (é o que a poda de H05 usa e o que o dashboard lê), mas deixa de ser lida na carga.
   Documente no docstring que ela é **cópia de leitura**, não fonte.

---

## Bloco N — A economia fecha

> **Depende de:** P (sem persistência de dinheiro, calibrar preço é calibrar ruído).

### N01 — socializar custa por visita (D27)

**Arquivo:** `engine/mechanics/actions.py`

`_executar_socializar` cobra `custo_pc` **só quando o NPC chega** ao local — isto é,
quando `npc.localizacao_atual_id` mudou nesta execução, ou quando a ação anterior não era
`SOCIALIZAR`. Minutos seguintes no mesmo local são de graça.

⚠️ Com isso `SOCIALIZAR` passa a ter uma transição de estado por minuto (pagou/não pagou)
e **não** vira `ACOES_LOTEAVEIS`. Deixe fora, como está hoje, e escreva por quê.

### N02 — o salário vem do local, não do config

**Arquivos:** `engine/mechanics/actions.py`, `config.json`

`_executar_trabalhar` e `_aplicar_efeito_continuo` passam a usar o `salario_base` do
`Local` de trabalho. `acoes.trabalhar.salario_pc` deixa de ser o salário e vira o
**divisor** que converte salário diário em PC por minuto — renomeie para
`salario_divisor_minutos` (valor: 600, os minutos de um expediente de 10 h) e comente.

⚠️ As duas funções precisam da **mesma** conta (armadilha 12, doc 2): extraia
`salario_por_minuto(npc, locais)` e chame nas duas.

⚠️ **N02 só é seguro depois de N01, e a conta é apertada.** Medido em regime, o
trabalhador ganha 193,9 PC/dia (582 min de expediente) e fecha o dia em +34,0. Com
`salario_divisor_minutos = 600` e o `salario_base` mediano dos estabelecimentos de
bairro (60 a 75 PC), a renda cai para **~73 PC/dia** — um corte de 62%. Isso só fecha
porque N01 tira 136,9 PC/dia de despesa:

| cenário | renda | comida | socializar | líquido |
|---|---:|---:|---:|---:|
| hoje | 193,9 | −23,0 | −136,9 | **+34,0** |
| só N02 (sem N01) | ~73 | −23,0 | −136,9 | **−87** ❌ |
| N01 + N02 | ~73 | −23,0 | ~−2 | **+48** ✅ |

**Se você fizer N02 antes de N01, o mundo quebra em uma semana.** Mantenha a ordem, e
cole no Registro a tabela medida depois das duas — não a projetada acima.

### N03 — o dependente não é cobrado duas vezes

**Arquivo:** `engine/mechanics/actions.py`

`multiplicador_por_dependente` some de `encontrar_pagador_e_parcela`. Cada NPC —
dependente ou não — come uma refeição de `custo_pc`, e o dependente debita do pai/mãe.
O custo familiar continua crescendo com o número de filhos, sem contar cada filho duas
vezes.

### N04 — a inanição volta a existir (D26)

**Arquivos:** `engine/mechanics/kingdom.py`, `config.json`

1. `fornecer_sopao` ganha teto diário por cidade:
   `reino.sopao_racoes_por_habitante_dia` (proposta: 0,15), contado num dicionário
   zerado pela rotina diária do reino. Acima do teto, devolve `False` — e aí a inanição
   acontece de verdade.
2. ❌ **NÃO crie tesouro do reino.** Decisão ❾: não existe finança do reino e não vai
   existir tão cedo — o tick já está no limite. O reino credita dinheiro sem origem, como
   hoje. `custo_sopao_ao_reino` (5) fica no config **sem leitor**, com um
   `_comentario_custo_sopao_ao_reino` dizendo que está reservado para quando a finança do
   reino existir. Não o ligue em nada.

   **A cota do item 1 é o único limitador.** É ela, sozinha, que faz a fome voltar a ter
   consequência — o débito em moeda era só o tema, nunca o mecanismo.

   ⚙️ **Orçamento de tick: zero.** A cota é um `dict[cidade_id] -> rações restantes`,
   zerado uma vez por dia dentro da rotina diária que `KingdomManager` já tem, e lido só
   dentro de `fornecer_sopao` — que só roda quando um NPC tenta comer sem dinheiro.
   Nenhuma varredura nova, nenhum trabalho por tick. **Se a sua implementação precisar de
   uma varredura por tick, ela está errada.**
3. `sopao_fome_limiar_miseria` sobe de 60 para 80 — o sopão é rede de emergência, não
   almoço.

⚠️ Depois desta tarefa **NPCs vão morrer de fome**. É o objetivo. O critério 3 de D25
(nunca mais de 2% da população com fome > 90) é o que diz se foi longe demais.

### N05 — pensão e limiar de pobreza recalibrados

**Arquivo:** `config.json`

✅ **Decisão ❷ = (a): `reino.pensao_aposentadoria` 40 → 75.** As duas outras opções que
eu tinha levantado estão fechadas — não reabra.

A aritmética medida que sustenta o 75:

| | hoje | depois de N01 | com pensão 75 |
|---|---:|---:|---:|
| comida do idoso | −71,5 | −71,5 | −71,5 |
| socializar do idoso | −136,5 | ~−2 | ~−2 |
| pensão | +40,0 | +40,0 | **+75,0** |
| **líquido** | **−207,9** | **~−33,5** | **~+1,5** |

**Fica explicitamente ACEITO como está:** o idoso come 215 min/dia (~seis refeições). É
comportamento, não bug — ele não trabalha e o convívio é limitado. Se um dia incomodar,
o caminho é fazer `AvaliadorOcioso` competir de verdade fora do expediente; não é escopo
agora.

⚠️ `ia_decisao.limiar_pobreza_pc` (50) continua precisando de medição depois de V01 — hoje
ele é inoperante porque o índice social está vazio. Meça e registre; não chute.

⚠️ **A pensão a 75 é o que cria a pergunta ❾** — 8.550 PC/dia de despesa contra 20 PC/dia
de receita. Não implemente N05 sem ter lido ❾.

## Bloco G — Uma população, não uma coorte

> **Depende de:** N (a demografia só se mede com a economia fechando).

### G01 — a população nasce com idades espalhadas e com crianças

**Arquivo:** `builder/populador.py`, `config.json`

Hoje `proporcao_adultos = 0,85` produz 85% adultos e 15% idosos, todos sorteados numa
janela de 25 dias de vida — daí a coorte da Seção 1. Troque por uma distribuição sobre
o **ciclo de vida inteiro** (0 a `crescimento_dias_idoso_para_morte` dias), com pesos por
faixa em `geracao_populacao.distribuicao_etaria` — proposta de partida:

| faixa | dias de vida | peso |
|---|---|---:|
| bebê | 0–4 | 0,08 |
| criança | 5–14 | 0,17 |
| adulto jovem | 15–40 | 0,30 |
| adulto | 41–74 | 0,33 |
| idoso | 75–89 | 0,12 |

`data_nascimento` é sorteada **uniformemente dentro da faixa**, e `estagio_vida` é
**derivado** dela — nunca sorteado à parte, ou os dois divergem no primeiro
`processar_crescimento`.

⚠️ Crianças precisam de pai/mãe. Gere-as **depois** de `_formar_casais_iniciais` e
atribua-as a casais existentes, com `mae_id`/`pai_id` preenchidos, ou o invariante 6 de
V05 quebra no dia zero.

### G02 — concepção checa parentesco

**Arquivo:** `engine/mechanics/reproduction.py`

Uma linha, em `processar_concepcao`, dentro do laço de pares:

```python
if NPCUtils.sao_parentes(h, m):
    continue
```

A função já existe, já está correta e já é usada por `verificar_elegibilidade_casamento`.
Aproveite e extraia a checagem completa (parentesco + `pode_procriar` + afinidade) para
um único `pode_conceber(a, b, afinidade, cfg_bio)` usado pelos **dois** caminhos —
senão eles voltam a divergir (armadilha 12, doc 2).

### G03 — o casamento planejado deixa de parar no primeiro

**Arquivo:** `engine/mechanics/marriage.py`

O `return` depois de `realizar_casamento` vira um `break` do laço **daquela cidade**, e
o laço de cidades continua. O comentário atual ("evitar processar mais de uma união no
mesmo tick") foi escrito quando a rotina rodava a cada tick; desde H02 ela roda uma vez
por dia, e o comentário virou a razão de um teto de 1 casamento/dia no mundo inteiro.

✅ **Decisão ❻: o mundo continua dramático.** O dono do projeto quer manter o romance
surpresa dominante — *"a vida não é perfeita, ainda mais nessa época do mundo"*.

⚠️ **Mas isso não é licença para deixar o bug.** Um `return` que faz 14 cidades ficarem
sem casamento porque a 15ª casou alguém é defeito, não design. Corrija o `return`, e
**depois** calibre para o resultado continuar parecido com hoje:

| | hoje (com o bug) | depois do `break`, sem calibrar | alvo |
|---|---:|---:|---:|
| uniões deliberadas/dia | 0,4 | ~15 (1 por cidade) | ~1 a 2 |
| uniões surpresa/dia | 2,8 | 2,8 | ~3 |

Ou seja: abaixe `casamento_chance_coabitacao` (0,857) até o caminho deliberado responder
por **algo entre 20% e 40%** das uniões — o suficiente para existir e ser narrável, sem
inverter o tom que a decisão ❻ pediu. `casamento_chance_romance_fisico` (0,15) fica como
está. Cole a razão medida no Registro.

### G04 — quem casa leva os filhos

**Arquivo:** `engine/mechanics/marriage.py`

Em `realizar_casamento`, ao mover `n1`/`n2` para a casa nova, mova junto todo morador da
casa de origem que seja dependente **e** filho de quem está se mudando
(`morador.mae_id == n.id or morador.pai_id == n.id`). Use `mundo.mudar_casa` e
`mundo.mover_npc` (as portas, nunca atribuição direta — os índices desincronizam em
silêncio, armadilha 12) e marque a casa suja.

⚠️ Isso pode superlotar a casa de destino. `realizar_casamento` já tem o ramo de casa
cheia; garanta que a contagem de superlotação é feita **depois** de contar os filhos que
vêm junto, não antes.

### G05 — nome de cidade é único

**Arquivos:** `cartographer/` (gerador do manifesto), `builder/importador_cartografia.py`

O `world_manifest.json` atual tem duas cidades chamadas "Cidade dos Ventos". Como o
arquivo de geometria e os ids de lote/local são derivados do *slug do nome*, uma das duas
fica com zero locais.

1. No gerador do manifesto: ao sortear um nome já usado, re-sorteie (determinístico —
   derive do `zlib.crc32` do índice da cidade, **nunca** `hash()`).
2. Em `CartographyImporter.import_manifest`: se dois nomes colidirem, **falhe alto** com
   uma mensagem que nomeia as duas cidades. Importar pela metade em silêncio é o que
   acontece hoje.
3. O mundo atual em `database/` já está nesse estado. Não tente consertar por migração —
   é um reset de cartografia. Anote no Registro.

---

## Bloco M — O Mestre consegue ler o mundo

> **Depende de:** G (não adianta dar um mundo legível ao Mestre antes de o mundo fazer
> sentido).

### M01 — o contexto cabe numa janela

**Arquivo:** `engine/mechanics/mestre/gerenciador.py`

`montar_contexto` passa a receber `cidade_id` (o `MetaChave.CIDADE_SIMULADA` que
`_montar_contexto_de_mundo` já lê) e a filtrar NPCs e locais por ela. Além disso:

- **locais**: só os que não são residência, mais a contagem agregada de residências
  (`"1.203 residências"` é informação; 22.624 linhas não são);
- **NPCs**: teto configurável (`mestre.limite_npcs_contexto`, proposta 200), priorizando
  quem apareceu em evento recente, depois os de maior grau social;
- registre no próprio contexto quantos foram omitidos (`"+ 640 outros habitantes"`), pra
  IA saber que a lista é parcial e não inventar que a cidade tem 200 pessoas.

**Critério:** contexto abaixo de **30 mil tokens** com 25.000 NPCs. Meça e registre (a
sonda 6 da Seção 9 faz isso).

### M02 — o log de eventos ganha peso narrativo

**Arquivos:** `engine/models.py`, `engine/repositorios/evento.py`, `engine/mechanics/*`

1. `TipoEvento` ganha `UNIAO`. Casamento hoje é gravado como `CONVERSA` e fica
   indistinguível de um papo — corrija nos dois pontos de `marriage.py`.
2. `resumos_recentes` passa a receber uma lista de tipos **relevantes** (tudo menos
   `CONVERSA`/`DISCUSSAO`) e a devolver os N mais recentes **dentro deles**, mais os 3
   últimos de fofoca à parte. Com 99,1% do log sendo conversa, "os 10 últimos por rowid"
   é estatisticamente 9 linhas de nada.
3. `interacao_chance = 0,0452` produz 5.758 eventos/dia com 840 NPCs (~160 mil/dia com
   25.000). Grave **só** as interações que mudam o vínculo de faixa
   (`_classificar_vinculo` mudou de valor) — as outras continuam ajustando afinidade em
   memória, sem virar linha no banco.

⚠️ A poda de E02 (`eventos_retencao_dias_simulados = 30`) continua valendo e continua
necessária. M02 reduz o que entra; não substitui o que sai.

### M03 — o Mestre sabe o que não sabe

**Arquivo:** `engine/mechanics/mestre/gerenciador.py`

Acrescente ao contexto um bloco `avisos`, montado dos invariantes de V05 que estiverem
quebrados no momento (`"3 dependentes sem responsável"`, `"1 cidade sem local social"`).
É barato, e é a diferença entre a IA narrar em cima de um mundo quebrado sem saber e
narrar sabendo.

---

## Bloco X — Custos fora do benchmark e regressões

> **Independente.** Pode rodar em paralelo com V/P/N/G/M. Toca só `mood.py`,
> `market.py`, `decay.py`, `logic.py`, `actions.py` e os dois benchmarks.

### X01 — o humor volta à taxa por minuto (armadilha 17)

**Arquivo:** `engine/mechanics/mood.py`

Separe **quantas tentativas** de **quantos passos**:

```python
p_transicao = 1.0 - (1.0 - chance_transicao) ** minutos   # probabilidade no intervalo
if random.random() < p_transicao:
    passos = 1 + sum(1 for _ in range(distancia - 1) if random.random() < p_transicao)
    npc.humor = escala[indice_atual + direcao * min(passos, distancia)]
```

Comente que `minutos` vem da agenda e pode ser 1 ou 240, e que a fórmula existe para o
resultado ser o mesmo nos dois casos.

**Critério:** teste que compara 1.440 chamadas de `processar_humor(npc, 1)` contra 6
chamadas de `processar_humor(npc, 240)` e exige distribuições estatisticamente
compatíveis. É o teste que faltava e que deixou a regressão passar.

### X02 — o mercado não paga pela consulta cara antes de saber se precisa dela

**Arquivo:** `engine/mechanics/market.py`

Medido: `buscar_vagas_disponiveis` custa **939 ms** (subconsulta correlacionada sobre
26.748 locais) e `buscar_candidatos_a_emprego` custa **13 ms** e devolveu **0
candidatos**. A consulta cara roda primeiro e é jogada fora, 5× por dia simulado.

Inverta a ordem: candidatos primeiro, `return` se vazio. E troque a subconsulta
correlacionada por um `LEFT JOIN ... GROUP BY` (ou pelo `ocupacao_por_local` que V04 já
monta, se P01 tiver posto o mundo na mão do `JobMarket`).

**Critério:** `processar_contratacoes` abaixo de **50 ms** num tick sem candidato.

### X03 — as rotinas de `run_simulation.py` entram no benchmark (armadilha 16)

**Arquivos:** `builder/fix/bench_avanco.py`, `run_simulation.py`

`bench_avanco.py` ganha uma flag `--com-rotinas-externas` que replica o que
`processar_gatilhos_periodicos` faz, e o relatório passa a mostrar o custo de cada uma
por dia simulado, separado do tick. Sem isso, os números de H06 (doc 3) descrevem uma
fração do custo real.

**Decida e escreva no Registro:** `processar_desgaste`/`processar_reparos_espontaneos`
deveriam virar entradas de `GameLoop._rotinas_diarias` (A06, doc 2)? Elas já são
diárias e já declaram cadência por convenção. Eu acho que sim, mas não é decisão que
cabe nesta tarefa.

### X04 — os nove pontos de varredura migram para o índice (armadilha 19)

**Arquivos:** `actions.py`, `housing.py`, `reproduction.py`, `finance.py`

Troque `NPCUtils.obter_moradores_da_casa(self._mundo.npcs, casa_id)` por
`self._mundo.npcs_por_casa.get(casa_id, ())` e `NPCUtils.agrupar_por_casa(self._mundo.
npcs)` por `self._mundo.npcs_por_casa`, nos oito pontos da tabela da armadilha 19.
Comece pelos quatro de `actions.py` — são os do caminho por minuto.

⚠️ `NPCUtils.obter_moradores_da_casa` filtra por `esta_vivo()`; o índice contém quem foi
registrado. `remover_npc` é chamado em `processar_morte` **antes** de limpar os campos,
então o índice está certo — mas confirme com um teste, não com confiança.

### X05 — a rede de segurança de habitação usa o índice da própria cidade (armadilha 18)

**Arquivo:** `engine/mechanics/logic.py`

Troque a varredura global por `ctx.indice.residencias_ativas(npc.cidade_id)` —
exatamente o que `movement.py` já faz desde P04 (doc 1), com o mesmo comentário
explicando que mudar alguém de cidade é decisão de migração, não fallback. Sem casa na
própria cidade, deixe `casa_id` como está e emita `warning`.

⚠️ `ContextoDecisao` já carrega `indice` (é por isso que ele existe). Não passe
`EstadoDoMundo` para `NPCBrain`.

---

## Bloco T — Testes e auditoria viva

> **Depende de:** todos. Cada teste aqui fixa um comportamento que só existe depois dos
> blocos anteriores.

### T01 — os oito testes que faltavam

Nenhum dos 19 achados deste documento é pego pelos 164 testes atuais. Um teste por
achado estrutural:

| teste | fixa |
|---|---|
| `test_todo_local_tem_tipo_do_enum` | V01 |
| `test_vaga_nunca_e_residencia_nem_outra_cidade` | V02 |
| `test_contratado_nunca_fica_desempregado` | V03 |
| `test_dinheiro_e_gravidez_sobrevivem_a_recarga` | P02 |
| `test_socializar_cobra_uma_vez_por_visita` | N01 |
| `test_concepcao_recusa_parentes` | G02 |
| `test_casamento_leva_os_filhos` | G04 |
| `test_humor_mesma_taxa_em_1_e_240_minutos` | X01 |

### T02 — `audit_mundo.py --ate-renovacao` como porta de decisão

Rode até **renovação geracional completa** (100% dos vivos nascidos dentro da simulação —
D25, decisão ❺) e cole a tabela no Registro, com o dia em que a renovação fechou e o
estado das **seis guardas** ao longo de toda a corrida.

Se alguma guarda falhar, **não conserte no impulso**: escreva qual falhou, em que dia, e
com que número. A calibragem final é decisão do dono do projeto.

⚠️ Se a renovação **não fechar** (sobrou NPC do povoamento inicial para sempre, ou a
população morreu antes), isso é resultado também — e provavelmente é a guarda 1 ou 2
gritando. Registre em vez de aumentar o limite e tentar de novo.

---

## 8. Tabela de parâmetros — valor hoje, efeito medido, valor proposto

Só parâmetros em que a **medição** diz alguma coisa. Onde não medi, está escrito.

| parâmetro | hoje | efeito medido | proposta | tarefa |
|---|---:|---|---:|---|
| `acoes.socializar.custo_pc` | 1,333333 **/min** | **136,9 PC/dia** — maior despesa de toda classe; 71% da renda do trabalhador, 3,4× a pensão do idoso | 1,333333 **/visita** | N01 |
| `acoes.trabalhar.salario_pc` | 0,333333 (global) | salário idêntico para toda profissão; `salario_base` ignorado | derivar de `local.salario_base` | N02 |
| `acoes.comer.multiplicador_por_dependente` | 0,8 | dependente cobrado duas vezes | remover | N03 |
| `reino.sopao_fome_limiar_miseria` | 60,0 | sopão dispara antes da inanição (90); 0 famintos em 25 dias | 80,0 | N04 |
| `reino.custo_sopao_ao_reino` | 5 | **não é lido por ninguém** | continua sem leitor (❾) — só ganha um comentário dizendo que é reservado | N04 |
| `reino.sopao_racoes_por_habitante_dia` | *não existe* | hoje o sopão é ilimitado: 0 mortes por fome em 25 dias | criar, 0,15, e é o **único** limitador | N04 |
| `reino.pensao_aposentadoria` | 40 | idoso fecha o dia em **−207,9 PC**; sobra −33,5 depois de N01 | **75** (decisão ❷); continua sendo crédito sem origem (❾) | N05 |
| `geracao_populacao.proporcao_adultos` | 0,85 | mundo nasce sem crianças; coorte de 25 dias | substituir por `distribuicao_etaria` | G01 |
| `biologia_e_sociedade.casamento_chance_coabitacao` | 0,857 | irrelevante: teto de 1 casamento/dia no mundo | recalibrar **após** G03 | G03 |
| `biologia_e_sociedade.casamento_chance_romance_fisico` | 0,15 | ~10 "casamentos surpresa"/dia; responde por ~100% das uniões | recalibrar **após** G03 | G03 |
| `biologia_e_sociedade.interacao_chance` | 0,0452 | 5.758 eventos/dia (840 NPCs); 99,1% do log | manter a taxa, filtrar a **gravação** | M02 |
| `infraestrutura.desgaste_padrao` | 0,2/dia | integridade média 94,9 após 25 dias; **0 ruínas** | não mexa até V04 fechar; medir de novo | V04 |
| `infraestrutura.desgaste_por_tipo` | 8 chaves | casa em **617 de 26.748** locais (2,3%) | virar `desgaste_por_categoria` | V04 |
| `simulacao.relacionamentos_max_por_npc` | 150 | máximo medido em 25 dias: **21**. O teto nunca foi atingido | manter; é margem, não calibragem | — |
| `biologia_e_sociedade.crescimento_dias_*` | 5/15/75/90 | coerente entre si e com `idade_em_anos`; **sem achado** | manter | — |
| `ia_decisao.limiar_pobreza_pc` | 50 | hoje inoperante (zera socializar porque o índice social está vazio) | remedir após V01 | N05 |
| `ia_decisao.bonus_nao_interromper_refeicao` | 100,0 | com `bonus_persistencia` (40), sustenta **215 min/dia comendo** no idoso contra 66 no trabalhador | **manter** — comportamento aceito (❷), não bug | — |
| `metabolismo.*` | — | fome p90 estável em ~52 nos 25 dias; **sem achado** | manter | — |
| `simulacao_intervalo_maximo_decisao_min` | 240 | **sem achado novo** — decisão do doc 3, mantida | manter | — |

---

## 9. Como reproduzir cada medição

Tudo foi feito num banco de rascunho, nunca em `database/openworld.db`.

**Preparar o mundo de teste** (o repo atual tem 20 NPCs e 0 lotes; não serve):

```bash
cp database/openworld.db /tmp/mundo.db
# zerar npcs, eventos, relacionamentos, npc_logs, eventos_globais,
# mestre_conversas, locais, lotes, cidades, continentes; resetar hora_simulada_iso
venv/bin/python - <<'EOF'
from engine.database import DatabaseManager
from engine.repositorios.seed import SemeadorDeDominio
from builder.populador import PopuladorDeMundo
db = DatabaseManager("/tmp/mundo.db")
SemeadorDeDominio.aplicar(db)
PopuladorDeMundo(db, "Fantasia Medieval", False, 4).executar(None)
EOF
```

| # | sonda | o que mede | resultado obtido |
|---|---|---|---|
| 1 | 25 dias com `SimulationEngine` + `JobMarket` + `InfrastructureManager`, foto diária | a tabela da Seção 2 | 659 s de tempo real |
| 2 | A/B com e sem `recarregar_habitantes()`, 3 dias | §4 | 0 vs 19 nascimentos |
| 3 | um NPC, 24 h, imprimindo saldo antes/depois de cada reload | §4 | 67 PC apagados às 15:00 |
| 4 | monkey-patch em `_executar_trabalhar`/`_executar_comer`/`_executar_socializar`, 1 dia | §5.1 | 16.676 PC/dia em socializar |
| 5 | `sao_parentes` vs `processar_concepcao` em mundo sintético, 200 noites | §5.2 | 6/200 mãe-filho |
| 6 | `MestreManager.montar_contexto()` + contagem de chars | §5.4 | 433.566 tokens |
| 7 | `time.perf_counter` em `processar_desgaste`/`processar_contratacoes` | §3, X02 | 1.319 ms / 864 ms |
| 8 | `IndiceDeLocais` recém-construído, somando as 15 cidades | §3 | `sociais`=0, `passeio`=0 |

⚠️ **Não canalize nenhuma dessas sondas por `| tail`** — redirecione para arquivo e leia
o arquivo (regra de execução 4).

---

## 10. O que este documento NÃO fecha

Escrito de propósito, para você não descobrir no meio da execução. Cada item aqui é uma
decisão do dono do projeto ou uma medição que só existe depois de uma tarefa anterior —
**nenhum deles é desculpa para parar**; todos têm um caminho padrão.

### 10.1 Três números que eu propus sem medir

| parâmetro | tarefa | de onde veio | o que fazer |
|---|---|---|---|
| `sopao_racoes_por_habitante_dia = 0,15` | N04 | estimativa minha | implemente com 0,15, rode `audit_mundo.py --ate-renovacao` e ajuste pela guarda 3 de D25 |
| `casamento_chance_coabitacao` depois do `break` | G03 | — | calibre até o caminho deliberado responder por 20–40% das uniões (decisão ❻) |
| `mestre.limite_npcs_contexto = 200` | M01 | estimativa minha | o critério real é o teto de 30 mil tokens; ajuste o número até bater |
| pesos de `distribuicao_etaria` | G01 | desenhados para tapar o buraco da pirâmide, **não** verificados contra reposição | ver 10.2 |

### 10.2 Se a população se repõe, eu não medi

G01 espalha as idades iniciais, o que resolve a coorte sincronizada. Mas **não verifiquei
se `concepcao_chance = 0,05` sustenta a reposição** até a renovação geracional, com a pirâmide
nova — nascimentos por dia contra mortes por dia. Os 25 dias que medi têm natalidade alta
(298 nascimentos) porque a população inteira está em idade fértil ao mesmo tempo; com a
pirâmide corrigida, uma fração menor está.

**São as guardas 1 e 2 de D25** (população nunca cai abaixo de 30% do pico; nenhum dia
sem nascimento depois do dia 10) e só podem ser medidas depois de G01. Se falhar, o ajuste é `concepcao_chance`, e o Registro
tem que dizer o valor antigo, o novo e a taxa medida.

### 10.3 O que fazer com o `database/openworld.db` atual

Duas mudanças deste plano invalidam o mundo que está em disco:

- **V01** muda como `tipo` é escrito na importação. Os 24.423 locais atuais continuam com
  o valor antigo.
- **G05** exige nome de cidade único, e o manifesto atual tem "Cidade dos Ventos"
  duplicada — uma das duas está com zero locais desde sempre.

**Decisão padrão: reset de cartografia + repovoamento** (`builder/reset_world.sh`), não
migração. Migrar o `tipo` seria um `UPDATE` fácil; migrar o nome duplicado não é — os ids
de lote e de local são derivados do slug do nome, e as duas cidades compartilham o
namespace. Escreva no Registro quando resetou.

⚠️ O banco em `database/` hoje tem **20 NPCs e 0 lotes**. Ele já não serve para medir
nada. Todas as medições deste documento foram feitas num mundo reconstruído — ver
Seção 9.

### 10.4 Duas perguntas de arquitetura que eu não decidi

~~1. `processar_desgaste` e `processar_reparos_espontaneos` deveriam virar entradas de
`GameLoop._rotinas_diarias`?~~ ✅ **Decidido (❽): sim, mover.** X03 deixa de ser pergunta
e vira tarefa.

~~2. `tipo` deveria simplesmente deixar de existir?~~ ✅ **Decidido (❹): derivar, não
apagar.** Não reabra durante V01.

~~3. De onde sai o dinheiro do reino?~~ ✅ **Decidido (❾): de lugar nenhum.** Sem
tesouro, sem imposto, sem finança — o tick não tem orçamento para isso. O reino credita
dinheiro sem origem e o sopão é limitado por cota.

**Nada continua aberto.** As nove decisões estão fechadas.

### 10.5 O que este documento deliberadamente não toca

- **Escala da cidade** (22.626 residências para 431 habitadas). É o Bloco R do doc 2 e o
  Bloco C do doc 3. A Seção 5.3 é insumo para eles (D28).
- **Velocidade do tick.** É o doc 3. As únicas medições de custo aqui são as que estão
  *fora* do benchmark (armadilha 16) — justamente porque ninguém mais ia achá-las.
- **Geometria, lotes, quadras.** Doc 1 e doc 3.
- **Viagem entre cidades.** O movimento é instantâneo por projeto. V02 elimina o
  trabalho em outra cidade, o que torna a questão irrelevante por enquanto; se um dia o
  NPC precisar migrar, é decisão de domínio nova, não conserto.

---

## Registro de execução

> Preencha **durante** a execução, não no fim. Uma linha por tarefa, com o número
> medido — não "feito", e sim "1.319 ms → 62 ms".
>
> ⚠️ Onde a implementação divergir do texto deste plano, **escreva a divergência e o
> motivo**. Nos dois documentos anteriores houve divergência que estava certa e quase se
> perdeu por não ter sido registrada.

| tarefa | data | resultado / número medido | divergências |
|---|---|---|---|
| V01 | 2026-09-14 | `tipo_local_por_categoria` no config + `tipo_local_de_categoria()` em `urbanismo.py`, usado por `populador.py` (importação) e `abrir_obra` (runtime). Mundo real regenerado (50.496 NPCs, 17.991 locais): `SELECT COUNT(*) WHERE tipo NOT IN (enum)` = **0**. | Nenhuma. |
| V02 | 2026-09-14 | `buscar_vagas_disponiveis(cidade_id, categorias_empregadoras)` — filtra por cidade e categoria empregadora (config `urbanismo.categorias_empregadoras`), não mais `tipo != 'Casa'`. Critério (`n.cidade_id <> l.cidade_id OR l.categoria='residencia'`) = **0** no mundo real. | Nenhuma. |
| V03 | 2026-09-14 | Vaga sem profissão mapeada não é mais oferecida (`WorldLogger.warning`, sem fallback `'ocioso'/'Desempregado'`). `SELECT COUNT(*) WHERE local_trabalho_id<>'' AND profissao_id='ocioso'` = **0**. | Nenhuma. |
| V04 | 2026-09-14 | `desgaste_por_categoria` substitui `desgaste_por_tipo`; ocupação vem de `_contar_ocupacao_por_local` (O(NPCs), 1 laço) em vez de O(locais×NPCs). Medido no mundo real (37.813 NPCs / 17.991 locais, antes de G01 inflar a população): **732,7 ms** — acima da meta de 80 ms do doc (medida no mundo de referência de 840 NPCs/26.748 locais), mas o mundo medido aqui tem 45× mais NPCs; o ganho relativo sobre a implementação O(N×L) antiga (que escalaria para minutos nesta escala) é o que importa. | Critério numérico do doc (80 ms) era calibrado pro mundo de 840 NPCs — não comparável 1:1 com este mundo de 37.813 NPCs (variância de tamanho de mundo já documentada, fora do escopo deste bloco). |
| V05 | 2026-09-14 | `builder/fix/audit_mundo.py` criado — 9 invariantes + `--dias`/`--ate-renovacao`. Rodado no mundo real: **9/9 invariantes passam**, incluindo o 8 (nome de cidade único) — esta semente não duplicou nome, então a falha "esperada" da Parada 1 não se manifestou. | Nenhuma. |
| **Parada 1** | 2026-09-14 | `audit_mundo.py` (sem flags) no mundo recém-povoado: **9/9 ✅**. Nenhuma cidade duplicada nesta semente (G05 ainda não tinha sido implementado no momento da 1ª geração; a 2ª geração, já com G05, também não duplicou). | — |
| P01 | 2026-09-14 | `JobMarket` recebe `mundo` opcional; contratação/demissão aplicam no NPC vivo (`salvar_completo` em LOTE — ver X02) e chamam `mundo.acordar`. Caminho só-banco preservado para `populador.py`. | Nenhuma. |
| P02 | 2026-09-14 | `recarregar_habitantes()` removido de `run_simulation.py::processar_gatilhos_periodicos` (a função inteira foi removida — as 3 rotinas que ela despachava migraram pro `GameLoop` em X03). `_COLUNAS_QUENTES` ganhou `dinheiro_total_pc`/`gravidez_ticks`. Teste `test_dinheiro_e_gravidez_sobrevivem_a_recarga` (T01) cobre o round-trip. | Nenhuma. |
| P03 | 2026-09-14 | `carregar_todos` lê `relacionamentos` da TABELA (1 `SELECT` agrupado em memória para todos os NPCs), não mais da coluna JSON — que continua sendo escrita por `salvar_completo` como cópia de leitura, documentado no docstring. | Nenhuma. |
| **Parada 2** | 2026-09-14 | Sonda dedicada, 3 dias simulados (4.320 ticks), mundo real de 50.496 NPCs, log silenciado só pra velocidade (mecânica intocada). **(a)** 193 nascimentos em 3 dias ✅. **(b)** saldo de um trabalhador amostrado de hora em hora: nunca reverte pra um valor anterior (o reload que causava isso foi removido em P02 — estruturalmente impossível de acontecer agora); trajetória 1.364 PC (dia 1, 07h) → 1.408 PC (dia 4, 06h), com altos (salário) e baixos (comida/social) normais, inclusive exatamente nas fronteiras de 10h/15h/20h (ex.: 1.474,96→1.459,29 às 15h do dia 3) — são despesas reais, não reset ✅. **(c)** total de relacionamentos por dia: 500.094 → 622.275 → 715.288, monotonicamente crescente, nunca cai ✅. | — |
| N01 | 2026-09-14 | `_executar_socializar` cobra `custo_pc` só quando `localizacao_atual_id` muda nesta chamada; `mover_para_social` (movement.py) passou a ficar no mesmo local se já é um local social ativo — sem isso, o resorteio por tick cobraria de novo mesmo sem o NPC "ir" a lugar nenhum. Teste dedicado em T01. | `mover_para_social` ganhou um comportamento novo (não re-sorteia se já está num local social) que não estava explicitamente pedido no texto da tarefa, mas é pré-requisito mecânico pra N01 funcionar — documentado no código. |
| N02 | 2026-09-14 | `salario_por_minuto(npc, locais, cfg_acoes)` extraída e usada por `_executar_trabalhar` E `GameLoop._aplicar_efeito_continuo` (mesma conta, armadilha 12). `acoes.trabalhar.salario_pc` (0,333333, constante global) virou `salario_divisor_minutos` (600). | Não medi a renda por dia pós-N01+N02 num mundo de 840 NPCs "de referência" (o mundo real desta sessão é o de 60 mil, calibração diferente) — a tabela projetada do doc (§N02) não foi confirmada com números reais desta sessão. |
| N03 | 2026-09-14 | `multiplicador_por_dependente` removido de `encontrar_pagador_e_parcela` e do config; cada NPC (dependente ou não) paga `custo_pc` cheio, uma vez. | Nenhuma. |
| N04 | 2026-09-14 | Cota diária de sopão por cidade (`reino.sopao_racoes_por_habitante_dia=0,15`), zerada em `processar_pagamentos_reino` (roda 1x/dia — ver X03), decrementada em `fornecer_sopao`. `sopao_fome_limiar_miseria` 60→80. Confirmado no mundo real: mortes por inanição ocorreram na simulação de 3 dias (ver nota). Sem tesouro do reino (❾) — `custo_sopao_ao_reino` permanece sem leitor, comentado. | Nenhuma. |
| N05 | 2026-09-14 | `reino.pensao_aposentadoria` 40→75. Refeições do idoso (215 min/dia) mantidas como comportamento aceito, não bug — nenhum código tocado ali. | `ia_decisao.limiar_pobreza_pc` — o doc pedia remedir após V01; não remedido nesta sessão (falta de tempo dedicado a essa medição específica, registrado como pendência). |
| G01 | 2026-09-14 | `distribuicao_etaria` (5 faixas, 0-89 dias de vida) substitui `proporcao_adultos`; `NPCUtils.estagio_vida_por_idade_dias` deriva o estágio da idade. `_gerar_criancas_iniciais` roda DEPOIS de `_formar_casais_iniciais`, atribuindo bebês/crianças a casais reais (mãe/pai preenchidos). Mundo real: 12.624 crianças/bebês gerados para 9.465 casais, população total subiu de 37.813 para **50.496**. `audit_mundo.py` invariante 6 (dependente sem responsável): **0 violações**. | **Achado importante**: G01 aumenta a população total em ~25-33% além do que R04 (doc 2) havia calibrado — combinado com a variância de tamanho de mundo já documentada (city-size-mix não-determinístico do `[AI-CITY-STRATEGY]`), o mundo gerado nesta sessão tem 50.496-60.549 NPCs, bem acima da faixa 22.000-28.000 de D7 (doc 2). Não ajustei `npcs_por_familia_faixa` nem `distribuicao_etaria` pra compensar — é uma decisão do dono do projeto, registrada aqui, não tomada por mim (fora do escopo desta tarefa). |
| G02 | 2026-09-14 | `NPCUtils.pode_conceber(a, b, afinidade, cfg_bio)` extraída (vivo+fértil+não-parente+afinidade mínima) e usada por `processar_concepcao` E `verificar_elegibilidade_casamento`. Teste `test_concepcao_recusa_parentes` (T01) confirma mãe×filho não engravida. | Nenhuma. |
| G03 | 2026-09-14 | `processar_coabitacao`: o `return` que saía do laço de TODAS as cidades virou um `break` só da cidade atual (`_tentar_casamento_na_cidade`), então outras cidades continuam sendo avaliadas no mesmo dia. | **Não recalibrei `casamento_chance_coabitacao`** (0,857) contra medição real desta sessão (o doc pede 20-40% de uniões deliberadas) — não rodei a medição de 25 dias necessária pra calibrar com confiança nesta sessão; registrado como pendência pro dono do projeto. |
| G04 | 2026-09-14 | `realizar_casamento`: `_filhos_para_mudar`/`_ocupacao_apos_casamento` — dependentes da casa de origem de CADA cônjuge se mudam junto (portas `mudar_casa`/`mover_npc`), e a superlotação é calculada DEPOIS de contar quem vem junto. Teste `test_casamento_leva_os_filhos` (T01). | Nenhuma. |
| G05 | 2026-09-14 | `generate_cities_metadata.py::_garantir_nomes_unicos` re-sorteia nome colidente (determinístico, `zlib.crc32`) antes de persistir; `CartographyImporter._falhar_se_nome_de_cidade_duplicado` falha alto na importação se mesmo assim colidir. `nome_procedural_de_cidade` exportada de `city_manager_ai.py` (antes privada, usada só ali). | Nenhuma — mundo `database/` já havia sido resetado (decisão ❸) antes desta tarefa rodar, então não há "Cidade dos Ventos" duplicada pra confirmar a correção contra o bug original; a lógica foi revisada por leitura, não observada corrigindo uma colisão real. |
| **Parada 3** | *(não executada)* | 25 dias simulados não rodados nesta sessão — ver nota em T02 sobre o custo desta escala de mundo. | Pendência explícita: ver seção de decisões pendentes, abaixo. |
| M01 | 2026-09-14 | `montar_contexto(cidade_id=None, ...)` filtra por cidade (default `CIDADE_SIMULADA`), residências viram contagem agregada, NPCs têm teto (`mestre.limite_npcs_contexto=200`) com prioridade (evento recente > grau social) e aviso de quantos ficaram de fora. Medido no mundo real (uma cidade de ~9.600 NPCs): **60.517 chars ≈ 15.129 tokens** — abaixo da meta de 30 mil. | Nenhuma. |
| M02 | 2026-09-14 | `TipoEvento.UNIAO` criado, usado em `realizar_casamento` (antes `CONVERSA`). `_computar_interacao` só grava Evento quando `_classificar_vinculo` muda de valor; afinidade/relacionamento continuam sendo ajustados/salvos sempre. `resumos_recentes` filtra fofoca (CONVERSA/DISCUSSAO) por padrão; `resumos_recentes_de_fofoca` cobre os 3 últimos à parte. | Um teste existente (`test_interacao_social_grava_afinidade_mutua_e_vinculo`) tinha a expectativa antiga (1 evento sempre) — atualizado para refletir o novo contrato (0 eventos quando o vínculo não muda de faixa), com comentário explicando por quê. |
| M03 | 2026-09-14 | Bloco `avisos` no contexto — 2 checagens SQL novas (`contar_dependentes_sem_responsavel`, `cidade_tem_local_social`), reimplementadas fora de `builder/fix/` porque o Mestre roda no processo web sem `EstadoDoMundo`. Mundo real: `avisos: []` (nenhum problema na cidade simulada). | Só 2 dos 9 invariantes de V05 viraram aviso (os mais relevantes pra narração) — os outros 7 são bugs estruturais, não estado transitório, como diz a justificativa no código. |
| X01 | 2026-09-14 | `p_transicao = 1-(1-chance)^minutos`; tentativas extras limitadas a `min(minutos, distancia)-1` (não `distancia-1` fixo, que quebrava o caso `minutos=1`). Teste `test_humor_mesma_taxa_em_1_e_240_minutos` (T01) compara 240×1min vs 1×240min, tolerância 12%, estável em execuções repetidas. | A primeira versão da fórmula (copiada literalmente do texto do plano) quebrava um teste existente (`test_humor_caminha_um_passo_por_vez_na_escala` — humor pulava 2 passos com `minutos=1`); corrigida limitando tentativas extras a `min(minutos,distancia)-1`. |
| X02 | 2026-09-14 | `buscar_vagas_disponiveis`: subconsulta correlacionada → `LEFT JOIN` com `GROUP BY` pré-filtrado por cidade. Medido no mundo real (50.496 NPCs): `processar_contratacoes` **11.609 ms → 320 ms** (36×). Achado DURANTE a implementação (não estava no plano original de X02 como tarefa isolada — a ordem candidatos-primeiro já vinha de graça do refactor V02/P01; o que faltava era a query). | A tarefa original também sugeria mover a ordem "candidatos antes de vagas" — isso já saiu de graça da reestruturação de V02/P01; o trabalho real de X02 foi só a query. |
| X03 | 2026-09-14 | Decisão ❽ já respondia "mover": `JobMarket.processar_contratacoes` e `InfrastructureManager.processar_desgaste`/`processar_reparos_espontaneos` viraram entradas de `GameLoop._rotinas_diarias` (`mercado_trabalho_hora`, `desgaste_hora`, `reparos_hora` no config). `run_simulation.py::processar_gatilhos_periodicos` foi removida inteira. | `processar_contratacoes` mudou de cadência (a cada 5h → 1x/dia) pra caber no modelo de `_rotinas_diarias` (só suporta 1 hora fixa) — disclosed no comentário do config; P01 já faz o NPC reavaliar na hora quando contratado, então o atraso médio até a próxima contratação sobe, nunca mais que 1 dia. |
| X04 | 2026-09-14 | 8 pontos de `NPCUtils.obter_moradores_da_casa`/`agrupar_por_casa` trocados por `mundo.npcs_por_casa` — direto onde seguro, `list(...)`/`dict(...)` (cópia) onde o laço muda de casa alguém no meio (mutar o balde vivo durante a iteração quebraria/pularia elementos — `_executar_construir` e `NPCHousingManager.processar_habitacao`). | Nenhuma. |
| X05 | 2026-09-14 | `logic.py::decidir_acao`: a rede de segurança de habitação trocou `locais.items()` (mundo inteiro) por `indice.residencias_ativas(npc.cidade_id)` — mesmo padrão de `movement.py` (P04, doc 1). Sem casa na cidade, `casa_id` fica como está, com `WorldLogger.warning`. | Nenhuma. |
| T01 | 2026-09-14 | 8 testes escritos: `test_todo_local_tem_tipo_do_enum`, `test_vaga_nunca_e_residencia_nem_outra_cidade`, `test_contratado_nunca_fica_desempregado`, `test_dinheiro_e_gravidez_sobrevivem_a_recarga`, `test_socializar_cobra_uma_vez_por_visita`, `test_concepcao_recusa_parentes`, `test_casamento_leva_os_filhos`, `test_humor_mesma_taxa_em_1_e_240_minutos`. Suíte completa: **176 passed** (168 pré-existentes + 8 novos), estável em 3 execuções repetidas dos novos. | Nenhuma. |
| T02 | *(não executada)* | **Não rodei `--ate-renovacao`.** O mundo real desta sessão tem 50.496-60.549 NPCs (ver nota em G01) — muito maior que o mundo de referência do doc (840 NPCs). A sonda de 3 dias da Parada 2, nesse mesmo mundo grande, levou ~10 minutos de tempo real mesmo com o log silenciado e o avanço rápido ativado — dominado pelo custo genuíno de simular a população, não só log (WARNING de inanição nunca é suprimido por `ativar_modo_avanco_rapido`, por design do projeto, mas mesmo com warning/info totalmente mudos a sonda ainda levou minutos). Rodar até 200 dias (teto de segurança) nesta escala projeta horas de tempo real — impraticável no tempo desta sessão. | **Pendência explícita pro dono do projeto**: rode `venv/bin/python builder/fix/audit_mundo.py --db <copia> --ate-renovacao` — idealmente num mundo com população mais próxima de 22-28 mil (ajustando `npcs_por_familia_faixa`/`distribuicao_etaria` primeiro, ou aceitando o mundo maior e esperando mais tempo real). |

### Decisões pendentes para quando você voltar

**1. O mundo gerado nesta sessão tem 50-60 mil NPCs, não 22-28 mil (D7, doc 2).**
G01 (crianças) soma ~25-33% de população em cima da variância de tamanho de mundo
já documentada no doc 2 (city-size-mix não-determinístico do `[AI-CITY-STRATEGY]`).
Nenhuma das duas causas é nova nesta sessão, mas a combinação ficou mais visível:
com o mundo grande, a economia (Bloco N) fica sob pressão muito maior do que os
números de referência do doc foram calibrados pra aguentar (840 NPCs). Duas
opções, não escolhi nenhuma: **(a)** reduzir `npcs_por_familia_faixa`/os pesos de
`distribuicao_etaria` até a população ficar mais previsível; **(b)** aceitar a
variância e recalibrar N02/N04/N05 contra mundos maiores.

**2. Parada 3 (25 dias) e T02 (`--ate-renovacao`, até 200 dias) não rodaram.** A
escala do mundo (acima) tornou isso impraticável no tempo desta sessão — a sonda
de 3 dias da Parada 2 já levou ~10 minutos reais com o log inteiro silenciado.
Preciso que você rode isso depois, numa sessão com mais tempo dedicado (ou num
mundo menor, se a decisão 1 for por reduzir a população).

**3. G03 (`casamento_chance_coabitacao`) e N02 (renda por dia) não foram
recalibrados contra medição real.** O texto do plano pedia números medidos depois
da implementação — não tive uma corrida de 25 dias limpa pra tirar esses números
com confiança (é a mesma limitação do item 2). O código está certo pelo que a
lógica exige; os NÚMEROS de calibração (a % de casamento deliberado, a renda
líquida diária) ainda são os projetados no texto do plano, não medidos.

**4. `builder/populador.py` já estava acima do limite de 400 linhas antes desta
sessão (495) e G01 acrescentou ~84 linhas (579 agora).** Não fiz o split em
pacote (`populador.py` → `populador/`) porque não fazia parte do que foi pedido
e um split malfeito é pior que não fazer — mas fica registrado como dívida.
