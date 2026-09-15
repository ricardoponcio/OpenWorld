# 🖥️ Plano Painel, Desempenho e IA — observar o mundo sem derrubá-lo

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este é o **quinto** plano da série (16º arquivo de `docs/`), depois de
> [`12_PLANO_CIDADE_VIVA.md`](12_PLANO_CIDADE_VIVA.md),
> [`13_PLANO_POPULACAO_E_ESCALA.md`](13_PLANO_POPULACAO_E_ESCALA.md),
> [`14_PLANO_AVANCO_E_CALIBRAGEM.md`](14_PLANO_AVANCO_E_CALIBRAGEM.md) e
> [`15_PLANO_MUNDO_CRIVEL.md`](15_PLANO_MUNDO_CRIVEL.md).
> Os quatro anteriores fizeram o mundo existir. Este trata de três coisas que quebraram
> quando o mundo ficou **grande** (30–50 mil NPCs):
>
> 1. **A simulação quebra** (um crash) e **anda a 153×** quando o painel pede 21600×.
> 2. **O painel não serve mais**: baixa o mundo inteiro por segundo, a lista de
>    habitantes é inutilizável, o mapa demora minutos e perdeu os NPCs andando.
> 3. **A IA está presa num Ollama local**, com URL e modelo escritos no código, sem
>    como usar o OpenRouter e sem nenhuma medição de quanto ela gasta.
>
> E um quarto, de geometria: **quadras e edifícios sobrepostos** nas cidades de traçado
> orgânico.
>
> 👉 **Nada aqui é opinião.** Cada achado tem o número medido ao lado, e o Anexo A diz
> como reproduzir. Onde algo **não** foi medido, está escrito "não medido".
>
> 👉 **Este documento é autossuficiente.** Você não precisa ler a conversa que o gerou.
> Precisa ler **este documento inteiro** e o [`11_ARQUITETURA.md`](11_ARQUITETURA.md), que é
> o padrão de código obrigatório — cada tarefa aqui cita a seção da ARQUITETURA que se
> aplica.

**Criado em:** 2026-09-14
**Base analisada:** branch `reescrita-estrutura`, commit `4eae1cd`
**Estado da suíte:** `176 passed` — e **nenhum** dos problemas abaixo é pego por teste
**Medições:** uma run real do dono do projeto (31.112 NPCs, 9 cidades, painel aberto) e
uma cópia de banco com 50.692 NPCs / 20.636 locais, simulada isoladamente.

---

# ⚡ Decisões já tomadas (não reabra)

> ✅ Todas respondidas pelo dono do projeto em 2026-09-14 (❾–⓭ numa segunda rodada, no mesmo dia). O modelo que executar **não
> reabre** nenhuma. Se achar que uma delas está errada, **termine a tarefa como está
> escrita** e registre a objeção na coluna "divergências" do Registro de execução.

| # | pergunta | resposta |
|---|---|---|
| ❶ | Implementar "modo grosso" (resolver dias por taxa em vez de minuto a minuto)? | **Não, por enquanto.** Dá trabalho demais. O dono do projeto **aceita que simular leve mais tempo** por enquanto: o teto de velocidade fica em ~700–1500× (Seção 1.3). |
| ❷ | Qual modelo gratuito do OpenRouter é o default? | **`google/gemma-4-31b-it:free`** |
| ❸ | Contra qual modelo pago a estimativa de custo é calculada? | **`deepseek/deepseek-v4-flash`** |
| ❹ | Quanto cada cliente de IA pode divergir do default? | **Provedor + modelo por cliente, com cadeia de fallback** (ex.: OpenRouter → Ollama local → fallback procedural que já existe) |
| ❺ | O que a coleta de uso de IA grava? | **Texto completo do prompt e da resposta + tokens, em JSONL** (`logs/ia_uso.jsonl`) |
| ❻ | Onde fica a chave do OpenRouter? | **Variável de ambiente** (`OPENROUTER_API_KEY`). **Nunca** no `config.json` — ele é versionado no git. O config guarda só o **nome** da variável. |
| ❼ | A economia quebrada (74% de desemprego, 804 mortes por fome em 3,5 dias) entra aqui? | **Em parte:** os empregos **aumentam um pouco** (Bloco E, tarefa E01). O resto (fome, sopão, renda de quem continua sem emprego) fica pendente, e **opções de empreendedorismo** entram num plano futuro. Fora do E01, **não mexa em nenhum parâmetro de balanceamento**. |
| ❽ | A correção de geometria (Bloco G) muda o mundo gerado? | **Sim, de propósito**: G02 muda a geometria só das cidades `organica`, e E01 muda a capacidade dos edifícios em todas. Exige regenerar a geometria e repovoar **uma vez só**, no último passo de E01, **mantendo o manifesto** (as mesmas cidades). ⚠️ **Não use `builder/reset_world.sh`**: ele apaga o manifesto e refunda as cidades pela IA, que não é determinística — o mundo inteiro mudaria. |
| ❾ | Quanto da IA vai para o OpenRouter? | **A divisão de I01 está aprovada:** volume (nome de bebê, DNA de NPC) no Ollama local; Mestre, evento global e geração de mundo no OpenRouter com fallback para o Ollama. O dono do projeto tem **US$ 5 em créditos** — abaixo dos 10 que liberam 1.000 req/dia nos modelos `:free`, então vale o teto de **50 req/dia**. |
| ❿ | Medir tokens de tudo? | **Sim, só para ter o número no planejamento** — Seção 2.7. Não muda o roteamento. |
| ⓫ | Apagar `gerar_background_npc` e `gerar_locais_cidade` (sem chamador hoje)? | **Não.** Vão ter uso. Continuam funcionando e ganham cliente próprio no config (I01/I05). |
| ⓬ | A refatoração de `.js` e `.html` do `10_PLANO_REFATORACAO.md` (Bloco H) entra? | **Sim — era para ter sido feita e não foi.** Vira o **Bloco F** deste documento, executado **antes** do Bloco P. |
| ⓭ | Renomear `engine/ai/utils.py` (nome proibido pela ARQUITETURA P1)? | **Sim.** Tarefa I10. |

---

## Índice

- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. O veredito, em uma página](#1-o-veredito-em-uma-página)
- [2. As medições](#2-as-medições)
- [3. As sete novas armadilhas](#3-as-sete-novas-armadilhas)
- [Bloco C — O crash](#bloco-c--o-crash)
- [Bloco O — Observabilidade: logs viram estatísticas](#bloco-o--observabilidade-logs-viram-estatísticas)
- [Bloco D — Desempenho do motor](#bloco-d--desempenho-do-motor)
- [Bloco F — Frontend: a refatoração de JS/HTML que ficou para trás](#bloco-f--frontend-a-refatoração-de-jshtml-que-ficou-para-trás)
- [Bloco P — Painel](#bloco-p--painel)
- [Bloco M — Mapa Live](#bloco-m--mapa-live)
- [Bloco G — Geometria: quadras sobrepostas](#bloco-g--geometria-quadras-sobrepostas)
- [Bloco E — Mais empregos](#bloco-e--mais-empregos)
- [Bloco I — IA configurável, OpenRouter e medição de custo](#bloco-i--ia-configurável-openrouter-e-medição-de-custo)
- [Bloco T — Validação final](#bloco-t--validação-final)
- [Decisões pendentes para o dono do projeto](#decisões-pendentes-para-o-dono-do-projeto)
- [Registro de execução](#registro-de-execução)
- [Anexo A — Como reproduzir cada medição](#anexo-a--como-reproduzir-cada-medição)
- [Anexo B — Fatos externos (OpenRouter e Ollama)](#anexo-b--fatos-externos-openrouter-e-ollama)

---

## 0. Como usar este documento

### Ordem obrigatória

```
C  ──►  O  ──►  D  ──►  F  ──►  P  ──►  M

G  ──►  E   (independentes de O/D/F/P/M — podem rodar depois de C; E logo depois de G)
I           (independente — pode rodar a qualquer momento depois de C)
T           (sempre por último)
```

- **C primeiro, sempre.** Sem C01 a simulação quebra sozinha em minutos; nenhuma
  medição dos outros blocos é confiável.
- **O antes de D:** D mede ms/tick, e o log atual distorce a medida (Seção 2.3).
- **P antes de M:** metade da lentidão do mapa é o polling de 23 MB do painel disputando
  o mesmo servidor (Seção 2.1). Medir o mapa antes de P01 é medir a coisa errada.
- **F antes de P:** P e M criam módulos JS novos. F converte o frontend atual (3 arquivos
  globais) para a estrutura da ARQUITETURA §10 **sem mudar comportamento**; P e M
  constroem em cima dela. Fazer P antes de F é escrever código novo no padrão errado.
- **E logo depois de G:** as duas mudam a cartografia e exigem regenerar e repovoar o
  mundo. Faça as duas e repovoe **uma vez só**, no fim de E01. G04 (popup) é frontend e
  espera F.
- **G/E e I** não dependem de O/D/F/P/M. Podem ser feitos por outra sessão em paralelo,
  desde que em commits separados.

### Três paradas obrigatórias

Pare, meça, registre no [Registro de execução](#registro-de-execução) e só então siga.

| parada | depois de | o que medir | critério pra seguir |
|---|---|---|---|
| **Parada 1** | Blocos C + O + D | Rode `run_simulation.py` com o painel **fechado** por 10 min reais em velocidade máxima. Leia a velocidade efetiva (O03) e o tamanho de `logs/world.log` e `database/openworld.db-wal`. | Nenhum crash. Velocidade efetiva **≥ 500×** num mundo de ~30 mil NPCs. `world.log` cresce **< 20 MB** em 10 min. WAL **< 128 MB**. |
| **Parada 2** | Blocos F + P | Mesma run, **com o painel aberto** na aba Habitantes. | `/api/estado` **< 5 KB** e **< 50 ms**. Velocidade efetiva cai **no máximo 15%** em relação à Parada 1. Nenhum erro no console do navegador em nenhuma aba. |
| **Parada 3** | Bloco I | Validação manual da cadeia de IA (I09). | As 3 situações de I09 produzem a linha JSONL esperada. |

### Regras de execução (herdadas dos documentos anteriores)

1. **Uma tarefa, um commit.** Mensagem começa com o código da tarefa (`C01: ...`).
2. **Rode a suíte inteira** antes de cada commit: `venv/bin/python -m pytest tests/ -q`.
   Nunca leia saída de teste ou auditoria com `| tail`/`| head` — o pipe engole o código
   de saída (já enganou uma sessão inteira).
3. **Todo bug corrigido ganha um teste que falha antes e passa depois**
   (ARQUITETURA §13). Escreva o teste **primeiro**, rode, veja falhar, depois corrija.
4. **Meça antes e depois.** O Registro pede o número, não "feito".
5. **Divergiu do texto? Escreva a divergência e o motivo** no Registro.
6. **Checklist da ARQUITETURA §16** antes de cada commit — em especial: `cfg_get` sem
   `default=` para parâmetro, nenhum SQL fora de `engine/repositorios/`, nenhum método
   com mais de 40 linhas ou 5 parâmetros, JS novo em módulo ES com no máximo 250 linhas.
7. **Nunca instancie `SimulationEngine` dentro do dashboard** (ARQUITETURA §1).
8. **Não altere parâmetros de balanceamento** (fome, salário, sopão, pensão, chances),
   **exceto** a capacidade de emprego em E01. Ver decisão ❼.
9. **Não mexa no `cartographer/` fora do Bloco G.** No Bloco G, siga o protocolo de md5
   da ARQUITETURA §11.

---

## 1. O veredito, em uma página

### 1.1 O que o dono do projeto viu, e o que causa cada coisa

| sintoma relatado | causa medida | tarefa |
|---|---|---|
| A run parou sozinha | `RuntimeError: dictionary changed size during iteration` em `engine/mechanics/social.py:60` — **2 crashes em 240 ticks** medidos | C01 |
| "21600× no painel, 10 min, só 3 dias" | Velocidade **efetiva medida: 153×** (392 ms/tick). O motor sozinho faz ~85–120 ms/tick; o resto é disputa com o painel, WAL de 1,19 GB e 725 MB de log | O01–O04, D01–D03, P01 |
| Tela de Habitantes inutilizável | `/api/update` manda **23 MB de JSON por segundo** (todos os NPCs e todos os locais); o navegador recria ~30 mil cartões via `innerHTML` a cada segundo; sem paginação, busca ou filtro por cidade | P01–P04 |
| Perdeu os NPCs andando no mapa | A animação foi **removida** no commit `e9cc059` (mapa regional em canvas, onde a cidade inteira cabe em menos de 1 pixel). O Mapa Live (Leaflet) **nunca ganhou** camada de NPCs | M04 |
| Mapa Live: 2 min na primeira vez, até 30 s por zoom | Servidor do painel a **136% de CPU / 2,3 GB** servindo o polling de 23 MB; cada pan/zoom apaga e recria as 13 camadas vetoriais em SVG (3,1 MB num recorte de Quenanfield no zoom 13) e refaz `lotes_alterados` por cidade | P01, M01–M03 |
| Quadra sobre quadra, casa sobre casa (Quenanfield) | Só no modelo `organica`: `OrganicaModelo.construir_malha` troca a aresta da quadra pra `"sem_via"` quando abre o anel, e `"sem_via"` tem recuo **zero** — as duas quadras vizinhas avançam sobre a faixa onde a rua passava. **Causa provada por experimento** (Seção 2.5) | G01, G02 |
| "Substituir os logs no output por estatísticas" | O console recebe 1 cabeçalho de tick **por minuto simulado** + 1 `print` de velocidade por tick + milhares de `warning` por NPC | O01–O03, P05 |
| "Colocar URL e modelo da IA na config, usar OpenRouter, medir custo" | `engine/ai/client.py:8-9` tem `OLLAMA_URL` e `MODEL_NAME` escritos no código; 8 pontos de chamada com `timeout` literal; nenhuma contagem de tokens | Bloco I |
| — (achado da análise) | **493 bebês com `cidade_id` nulo** na run real — todos os nascidos em jogo. `processar_parto` não copia a cidade da mãe (`engine/mechanics/reproduction.py:141-163`). Bebê sem cidade fica fora de `npcs_por_cidade`, do mercado de trabalho quando crescer, do contexto do Mestre e das estatísticas | C02 |
| — (achado da análise) | **3 bebês sobrescritos por outros:** 495 nascimentos, 492 ids distintos. O id é `npc_nac_{segundo_real}_{0..999}` e `RepositorioNPC.salvar` faz `INSERT OR REPLACE`. O mesmo padrão gera o id de 12 tipos de evento | C03 |
| "Pedi a refatoração de .js e .html e não foi feita" | O Bloco H do `10_PLANO_REFATORACAO.md` (R-H01 a R-H06) foi especificado e **nunca executado**: 24 `onclick` e 35 `style=""` no `index.html`; `dashboard.js` com 534 linhas, `mapa_composto.js` 687, `mapa_leaflet.js` 477 (limite 250); 57 variáveis de topo | F01–F06 |
| "Aumentar um pouco os empregos" | **5.205 vagas** para **19.209 adultos** (27%); 70% delas vêm de 5 tipos de comércio de bairro com capacidade 2 a 4 | E01 |
| — (achado da medição de tokens) | O prompt do **Mestre** e do **evento global** (~66 mil caracteres) é **truncado em 4.096 tokens** pelo Ollama local, que roda com a janela padrão — o modelo aceita 32.768 | I11 |

### 1.2 O que este documento **não** resolve

- **A economia, além dos empregos.** E01 aumenta um pouco as vagas (decisão ❼). As 804
  mortes por inanição em 3,5 dias (de 1.479 óbitos, incluindo adolescentes de 14 anos), o
  sopão e a renda de quem continua sem emprego ficam para o dono do projeto. **Opções de
  empreendedorismo** (NPC abrir o próprio negócio) são um plano futuro.
- **O modo grosso** (❶).

### 1.3 O teto de velocidade sem modo grosso

A simulação roda **um tick por minuto simulado**. Um dia = 1.440 ticks.

| ms/tick | ticks/s | velocidade efetiva máxima | 1 dia simulado leva |
|---|---|---|---|
| 392 (hoje, com painel e log) | 2,6 | 153× | 9,4 min |
| 100 (motor isolado, medido) | 10 | 600× | 2,4 min |
| 50 (meta depois de D01/D02) | 20 | 1.200× | 1,2 min |
| 2,8 | 360 | **21.600×** | 4 s |

👉 **21.600× não é alcançável sem modo grosso.** O painel deve **mostrar a velocidade
efetiva medida** ao lado da pedida (O03/P05), pra ninguém mais achar que está a 21.600×.

Decisão ❶: um tempo maior de simulação é aceito por enquanto.

---

## 2. As medições

### 2.1 O painel

Medido com `curl` contra o `run_dashboard.py` em execução, durante uma run de 31 mil NPCs.

| endpoint | tamanho | tempo |
|---|---|---|
| `GET /api/update` (polling a cada **1 s**, `web/static/js/dashboard.js:58`) | **23.049.050 B** | **0,74 s** |
| `GET /api/mapa/features?...&bbox=296.9,344.9,297.1,345.1&z=13` (Quenanfield) | 3.138.115 B | 0,026 s |
| `GET /api/mapa/features?...&bbox=290,340,305,350&z=11` | 37.620 B | 0,13 s |
| `GET /api/cidade/9/lotes_alterados` | 43.800 B | 0,41 s |
| `GET /tiles/12/1900/2208.png` | 761 B | 0,27 s |

Processo `run_dashboard.py`: **136% de CPU, 2,3 GB de RSS**.
Processo `run_simulation.py` na mesma hora: **60% de CPU** — ou seja, parado ~40% do
tempo esperando (disco, lock do SQLite, ou CPU tomada pelo painel).

`/api/update` (`web/dashboard.py:74-155`) monta, por requisição: todos os locais
(`db.locais.carregar_por_id()`), todos os NPCs (`db.npcs.listar_projecao_dashboard()`),
formata moeda e idade de cada um. O front (`dashboard.js:71-181`) guarda tudo em
`allNpcs` e, na aba Habitantes, faz `grid.innerHTML = filteredNpcs.map(...)` — ~30 mil
cartões, a cada segundo.

### 2.2 Disco

| arquivo | tamanho | por quê |
|---|---|---|
| `database/openworld.db-wal` | **1.190.049.672 B** (1,19 GB) | O SQLite só faz checkpoint do WAL quando nenhum leitor segura um snapshot antigo. O painel lê o banco inteiro a cada segundo → o checkpoint quase nunca completa (*checkpoint starvation*). O arquivo WAL nunca encolhe sozinho. |
| `logs/world.log` | **725.800.481 B** em ~25 min | `engine/logger.py:128-143`: o arquivo recebe **DEBUG**, sempre. `run_simulation.py` nunca ativa o modo rápido. |

Linhas mais frequentes do `world.log` (amostra dos últimos 300 MB):

| contagem | linha | origem |
|---|---|---|
| 161.971 + 110.578 + 94.518 | `[DEBUG] 🍔 [ALIMENTAÇÃO PROGRESSIVA ...]` | `engine/mechanics/actions.py:166,169` — **sem** `deve_logar_amostra` |
| ~25.000 por sobrenome (×17) | `[DEBUG] 🚶 ... deslocou-se para ...` | `engine/mechanics/movement.py:58,75` — **sem** amostragem |
| 20.241 + 15.585 + ... | `[WARNING] ⚠️ [ECONOMIA] ... sem dinheiro para comer!` | `actions.py:192` |
| 42.476 | `[WARNING] 💔 [INANIÇÃO] ...` | `engine/loop.py:357` — um por NPC faminto, por tick |

E no console: `engine/loop.py:207` loga um cabeçalho de tick em INFO por minuto
simulado, e `run_simulation.py:91` dá `print("⏩ Velocidade")` a cada tick.

Achado lateral: a "subnutrição parcial" loga pagamentos como `gastou
1.3739009929736312e-13 PC, reduziu fome em 0.0` — o saldo virou resíduo de ponto
flutuante e nunca chega a zero de verdade, então o NPC fica preso no ramo "parcial" em vez
de ir pro sopão (`actions.py:172-183`). Corrigido em O05.

### 2.3 O motor

**Run real, painel aberto** (amostra de 40 s no relógio do banco):
**102 min simulados em 40,0 s = 2,55 ticks/s = 392 ms/tick = 153× efetivo.**

**Cópia do banco, motor isolado** (50.692 NPCs, 20.636 locais, sem painel):

| cenário | média ms/tick | p50 | p95 | máx |
|---|---|---|---|---|
| log como na run real | 118,1 | 62,8 | 238,3 | 1.960,5 |
| modo rápido do logger (sem debug/info) | 84,4 | 99,1 | 117,5 | 125,2 |
| modo rápido + warnings silenciados | 92,1 | 106,3 | 134,1 | 136,0 |

(O "sem warning" não saiu mais rápido que o "modo rápido" porque a população e o número
de mortes mudam entre as janelas — o que vale aqui é a ordem de grandeza: **~85–120
ms/tick, e o p95/máx com log é 2–15× pior**.)

**Perfil** (cProfile, 60 ticks, 15,5 s com overhead do profiler — valores relativos):

| função | tempo acumulado | por tick | observação |
|---|---|---|---|
| `GameLoop._decidir_e_executar` | 4,84 s | 81 ms* | 77.528 decisões — o trabalho de verdade |
| **`GameLoop._atualizar_dependentes`** | **3,33 s** | **55 ms*** | **766.300 recálculos de casa em 60 ticks** — ver D01 |
| `config/resolver.py:cfg_get` | 2,29 s | — | 5,6 milhões de chamadas |
| `NPCSocialManager.processar_interacoes` | 1,89 s | 32 ms* | |
| **`NPCLegacyManager.processar_heranca`** | **0,92 s** | — | **73 mortes → 12,6 ms por morte**; varre `mundo.npcs` inteiro — ver D02 |
| `RepositorioNPC.salvar_muitos` | 0,63 s | 11 ms* | |

\* com overhead do profiler.

**Por que `_atualizar_dependentes` recalcula o mundo quase todo tick:**
`GameLoop._remover_falecidos` (`engine/loop.py:371`) cria uma **lista nova**
`self._mundo.npcs = [...]` sempre que alguém morreu no tick. `_atualizar_dependentes`
(`engine/loop.py:408`) compara a **identidade** da lista com a última vista e, se mudou,
marca **todas** as casas como sujas — essa checagem existe pra `recarregar_habitantes()`,
não pra morte. Com ~1 morte por tick (73 mortes em 60 ticks), o recálculo vira total
todo tick. A morte **já** marca a casa certa suja por conta própria
(`EstadoDoMundo.remover_npc`, `engine/mundo.py:~225`).

### 2.4 O crash

```
File "engine/loop.py", line 198, in executar_tick
    self._social.processar_interacoes()
File "engine/mechanics/social.py", line 60, in processar_interacoes
    for loc_id, moradores in self._mundo.npcs_por_localizacao.items():
RuntimeError: dictionary changed size during iteration
```

Sequência: `processar_interacoes` percorre o índice **vivo**
`mundo.npcs_por_localizacao` → `_computar_interacao` → romance surpresa
(`social.py:~135-140`, chance `biologia_e_sociedade.casamento_chance_romance_fisico` =
0,15) → `NPCMarriageManager.realizar_casamento` → `mundo.mover_npc(n, casa)`
(`marriage.py:148-162`) → `npcs_por_localizacao.setdefault(casa, [])`
(`mundo.py:162`). Se **ninguém nunca esteve** naquela casa, a chave não existia e o
dicionário cresce no meio da iteração. (`_remover_de_bucket` **não** apaga chave vazia,
por isso só quebra quando a casa de destino é uma chave nova.)

### 2.5 A geometria

**Sobreposição medida por ÁREA de interseção** (> 1 m²), nas cidades reais de
`database/cidades/`:

| cidade | modelo | quadras sobrepostas (pior área) | edifícios sobrepostos (pior área) |
|---|---|---|---|
| Quenanfield | organica | **2 (95,4 m²)** | **13 (23,2 m²)** |
| Cidade das Flores | organica | 0 | **5 (19,7 m²)** |
| Toranvale | organica | 0 | 0 |
| Kelanstead, Kelverstead, Tordordor | radial | 0 | 0 |
| Cidade da Sombra | grade | 0 | 0 |
| Elorfield, Vila Velha | linear | 0 | 0 |

⚠️ **Armadilha 21:** uma primeira medição contou "arestas que se cruzam" e achou
dezenas de pares em **todas** as cidades. Quase tudo era **borda encostando** em outra
(ruído numérico em arestas colineares). Só a medição por área separa encostar de
sobrepor. O invariante do G01 é por área.

**O experimento que isolou a causa** (cidades de teste `tamanho="grande"`, geradas em
memória com `GeradorCidade`, mesma semente por nome):

| variante do modelo | Quenanfield quadras / edifícios / lotes | Belmir quadras / edifícios / lotes |
|---|---|---|
| `radial` (controle) | 0 / 0 / 0 | 0 / 0 / 0 |
| `organica` (como está) | 2 / 6 / 78 | 2 / 5 / 71 |
| `organica` com recuo `sem_via` = 1,5 m | 2 / 5 / 37 | 1 / 5 / 56 |
| `organica` abrindo o anel **sem** trocar a aresta pra `sem_via` | **0 / 0 / 23** | **0 / 1 / 21** |
| **`organica` com recuo `sem_via` = recuo da classe `anel` (6,5 m)** | **0 / 0 / 18** | **0 / 1 / 3** |

Também testado e **descartado**: tirar a torção angular (`_torcer_grade`) — continua
com 4–12 sobreposições por cidade. Não é a torção.

👉 **Conclusão:** a causa é a aresta `"sem_via"` com recuo **zero**
(`cartographer/cities/modelos/base.py:79-80` e o gêmeo
`cartographer/cities/geometria/gerador.py:147-148`). Dar a ela o recuo que a via teria
(classe `anel`) zera as quadras e os edifícios sobrepostos **e mantém** a regra L02
(nenhum lote tem frente onde não há rua — isso é decidido em
`cartographer/cities/geometria/lotes.py:147-149,164-165`, que continua lendo
`"sem_via"`). A faixa onde o anel passaria vira chão vazio, o que é coerente com uma aldeia
orgânica. Sobra uma sobreposição residual pequena **entre lotes** (≤ 23,5 m²), registrada
em G03.

Achado lateral: o nome "Residência Bairro Médio 42" existe em **5 quadras diferentes** de
Quenanfield (a numeração é por quadra). Parte da impressão de "uma casa em cima de 3" é
isso. Ver G04.

### 2.6 A IA hoje

| onde | o que chama | timeout | modelo |
|---|---|---|---|
| `engine/ai/client.py:8-9` | `OLLAMA_URL = "http://localhost:11434/api/chat"`, `MODEL_NAME = "qwen2.5-coder:7b"` — **constantes no código** (viola ARQUITETURA P3) | — | — |
| `web/mestre_routes.py:75,166` → `AIGameMasterClient.gerar_resposta_mestre` | Mestre | 60 s | default |
| `engine/mechanics/reproduction.py:220` → `AIBiographyClient.gerar_nome_bebe` (em **thread**) | nome de bebê | 8 s | default |
| `builder/populador.py:347` → `AIGeneratorClient.gerar_dna_npc` (em **ThreadPool**, só a cidade em foco) | DNA de NPC | 120 s | default |
| `builder/storyteller.py:34` → `AIStorytellerClient.gerar_evento_global` | evento global | 60 s | default |
| `cartographer/world/world_manager.py:32` → `WorldManagerAIClient.planejar_continentes` | continentes | 120 s | default |
| `cartographer/cities/generate_cities_metadata.py:132` → `CityManagerAIClient.generate_cities_for_continent` | cidades | 120 s | **parâmetro `model_name="qwen2.5-coder:7b"` literal** (`city_manager_ai.py:66`) |
| `AIBiographyClient.gerar_background_npc` | — | 8 s | **sem nenhum chamador** |
| `AIGeneratorClient.gerar_locais_cidade` | — | 60 s | **sem nenhum chamador** |

- Todo `AIClient.query` usa a API **nativa** do Ollama (`/api/chat`, `"format": "json"`).
- Nenhuma contagem de tokens, nenhum registro de prompt/resposta.
- `AIClient.query` tenta **3 vezes com backoff 1 s → 2 s** antes do fallback: um nome de
  bebê com o Ollama desligado custa até 3×8 s + 3 s = **27 s** de thread presa.
- Ollama local tem instalados: `mistral:7b`, `qwen3-vl:latest`, `qwen3.5:4b-q4_K_M`,
  `qwen3.6:27B`, `qwen2.5-coder:14b-instruct-q4_K_M`, `qwen2.5:14b`, `llama3.1:latest`,
  `qwen2:0.5b`, `qwen2.5-coder:7b`.
- **Verificado:** o Ollama também responde no formato OpenAI em
  `http://localhost:11434/v1/chat/completions`, aceita
  `"response_format": {"type": "json_object"}` e devolve `usage` com `prompt_tokens`/
  `completion_tokens` (teste: 39 / 6 tokens). **Um único adaptador "compatível com
  OpenAI" serve pro Ollama e pro OpenRouter.**

### 2.7 Quanto de token a IA gasta

> Pedido do dono do projeto (decisão ❿): o número de tokens de entrada e saída de **tudo**
> que usa IA, só para o planejamento. Nada aqui muda o roteamento aprovado em ❾.

**Como foi medido** (Anexo A.7): cada prompt foi montado com o template real e dados
reais — o contexto do Mestre e do evento global saiu de `MestreManager.montar_contexto()`
sobre uma cópia do banco (teto de 200 NPCs, `mestre.limite_npcs_contexto`) — e enviado ao
Ollama local (`qwen2.5-coder:7b`). Os tokens são os que o próprio servidor reportou.
Amostras pequenas (1 a 3 chamadas por cliente): trate a saída como ordem de grandeza.

⚠️ **A primeira rodada mediu errado, e isso virou achado:** o Mestre e o evento global
voltaram com **exatamente 4.096** tokens de entrada para um prompt de ~66 mil caracteres.
É a janela de contexto padrão do Ollama cortando o prompt em silêncio (Armadilha 26,
tarefa I11). Os números abaixo foram medidos de novo com a janela em 32.768.

#### Tokens por chamada

| cliente | entrada | saída (faixa medida) | latência local | chamador hoje |
|---|---|---|---|---|
| `mestre` (sem histórico) | **27.748** | 125 (115–216) | 83 s | `web/mestre_routes.py:75`, e `:166` a cada "avançar tempo" |
| `mestre` (10 mensagens de histórico) | **28.482** (+~73 por mensagem) | 125 | 50 s | idem |
| `mestre`, contexto em JSON compacto (I11) | 26.278 (−5,3%) | 115 | 80 s | — |
| `evento_global` | **29.089** | 364 (74–581) | 187 s | `builder/storyteller.py` (manual) |
| `evento_global`, JSON compacto (I11) | 27.619 (−5,1%) | 581 | 262 s | — |
| `planejamento_continentes` | 743 | 628 | 34 s | gênese, 1× |
| `fundacao_cidades` | 290 | 46 (45–48) | 2,5 s | gênese, 1× por continente (até 3 tentativas) |
| `dna_npc` | 176 | 172 (120–206) | 8,8 s | gênese, 1× por adulto/idoso da **cidade em foco** |
| `nome_bebe` | 99 | 6 (5–8) | 0,3 s | 1× por nascimento |
| `background_npc` (sem chamador, ⓫) | 95 | 74 (58–91) | 3,9 s | — |
| `locais_cidade` (sem chamador, ⓫) | 157 | 367 | 18,4 s | — |

Observações:
- **Entrada domina.** No Mestre e no evento global, a entrada é ~99% dos tokens. O volume
  vem do **conteúdo** do contexto (até 200 NPCs com dados), não da formatação: tirar a
  indentação do JSON economiza só ~5%. Reduzir de verdade exigiria mexer no que o contexto
  inclui (`mestre.limite_npcs_contexto`) — **não medido** quanto cada NPC custa, e é decisão
  de produto.
- `dna_npc` tem entrada constante só porque `nomes_gerados` nunca recebe nomes (bug #5 de
  `builder/populador.py`, ver cabeçalho do arquivo). Se esse bug for corrigido passando a
  lista de nomes já usados, a entrada cresce a cada NPC e o total da gênese vira
  **quadrático**.
- Latência local com contexto de 32 mil: 50 a 262 s. Por isso I01 dá `timeout_s` maior ao
  `mestre` e ao `evento_global` — com o padrão de 60 s, o fallback para o Ollama falharia
  sempre.

#### Volume e totais

Preço de referência (❸): `deepseek/deepseek-v4-flash`, **US$ 0,08246** por milhão de
tokens de entrada e **US$ 0,16492** por milhão de saída.

| cenário | chamadas | entrada | saída | custo no DeepSeek v4-flash |
|---|---|---|---|---|
| **Gênese, como é hoje** (3 continentes, 1 tentativa cada; IA só na cidade em foco, Vila Velha: 103 adultos/idosos) | 1 + 3 + 103 | 19.741 | 18.482 | **US$ 0,005** |
| Gênese se a cidade em foco fosse a maior (Kelverstead, 7.367) | 1 + 3 + 7.367 | 1.298.205 | 1.267.890 | US$ 0,32 |
| Gênese com DNA por IA para **todas** as 9 cidades (26.012 adultos/idosos) | 1 + 3 + 26.012 | 4.579.725 | 4.474.830 | US$ 1,12 |
| **Por dia simulado** (nomes de bebê; 125 → 176 → 194 nascimentos/dia nos dias 4–6 da run de ~29 mil NPCs; usado 194) | 194 | 19.206 | 1.164 | **US$ 0,002** |
| **Por mensagem do Mestre** (ou por "avançar tempo") | 1 | ~28.000 | ~150 | **US$ 0,0023** |
| **Por evento global** | 1 | 29.089 | 364 | **US$ 0,0025** |
| Exemplo de sessão de jogo: 30 mensagens + 5 avanços de tempo + 2 eventos + 1 dia simulado | 231 | ~1.057.000 | ~7.100 | **~US$ 0,09** |

Leituras para o planejamento:
- **Com os US$ 5 de créditos**, pagando DeepSeek v4-flash, dá para ~2.100 mensagens do
  Mestre.
- **No plano gratuito** (50 req/dia, ❾), isso cobre ~40 mensagens do Mestre por dia mais
  a geração de mundo — nomes de bebê e DNA ficam no Ollama, como aprovado.
- **Ressalva de tokenizer:** os tokens foram contados pelo tokenizer do Qwen. O DeepSeek
  conta o mesmo texto com alguma diferença (**não medida**), e as respostas dele podem ser
  mais longas ou mais curtas. A coleta real de I06 + o script de I07 substituem esta
  tabela por números de uso de verdade.

---

## 3. As sete novas armadilhas

### Armadilha 20 — callback de domínio dentro de iteração de índice vivo

`mundo.npcs_por_localizacao`, `mundo.npcs_por_casa` e `mundo.npcs_por_cidade` são
**estruturas vivas**: toda porta de `EstadoDoMundo` (`mover_npc`, `mudar_casa`,
`registrar_npc`, `remover_npc`, `mudar_cidade`) as altera. Iterar um desses dicionários e,
**dentro do laço**, chamar qualquer coisa que possa mover, casar, matar, parir ou mudar
alguém de casa é um crash esperando a primeira chave nova.

**Regra:** laço sobre índice vivo cujo corpo pode chamar outra mecânica → itere
`list(indice.items())`. A lista de NPCs de cada balde também é viva: copie
(`list(moradores)`) se o corpo puder tirar alguém dela.

### Armadilha 21 — "arestas se cruzam" não é "polígonos se sobrepõem"

Duas quadras que só **encostam** numa aresta comum produzem cruzamentos numéricos
espúrios. Sobreposição de geometria se mede por **área de interseção** acima de um
limiar em m². Ver Seção 2.5.

### Armadilha 22 — velocidade pedida não é velocidade efetiva

`MetaChave.VELOCIDADE` é o que o **jogador pediu**. O laço de `run_simulation.py` só
consegue entregar `60 000 / ms_por_tick` vezes. O painel mostrava a pedida como se fosse
a real. Toda tela que mostra velocidade mostra **as duas**.

### Armadilha 23 — trocar a identidade de uma lista vigiada

`GameLoop._atualizar_dependentes` usa `self._mundo.npcs is not self._ultima_lista_de_npcs`
como sinal de "a lista foi recarregada do banco". Qualquer código que **reatribui**
`mundo.npcs` (em vez de mutar) dispara o recálculo total, mesmo que a mudança já tenha
passado pelas portas certas. Quem reatribui por motivo legítimo e já marcou as casas
sujas **tem que atualizar o marcador**.

### Armadilha 24 — polling do mundo inteiro

Endpoint consultado periodicamente devolve **o que a tela visível precisa**, nunca "tudo,
e o front filtra". Com 30 mil NPCs, "tudo" são 23 MB por segundo, um processo web a
136% de CPU e um WAL de 1 GB. Lista → paginada no SQL. Mapa → recortado por bbox.
Detalhe → endpoint por id.

### Armadilha 25 — id montado com relógio + sorteio pequeno

`f"npc_nac_{int(time.time())}_{random.randint(0, 999)}"` tem **1.000 valores possíveis
por segundo real**. O motor faz vários ticks por segundo e várias rotinas disparam tudo no
mesmo minuto simulado (concepção e parto têm hora fixa), então dois nascimentos caem no
mesmo segundo com frequência — e cada par colide com chance de 1 em 1.000.
`INSERT OR REPLACE` transforma a colisão em **sobrescrita silenciosa**. Medido: 3 de 495
bebês. Em eventos a perda **nem aparece na tabela**: a linha repetida some junto com a
sobrescrita. **Regra:** todo id gerado em runtime sai de `engine/identificadores.py` (C03).

### Armadilha 26 — contexto truncado sem erro

Um servidor de LLM com janela de contexto menor que o prompt **corta o texto em
silêncio** e responde normalmente, com uma resposta pior. O único sintoma é
`tokens_entrada` exatamente igual ao tamanho da janela (aqui, 4.096). A coleta de uso (I06)
marca esse caso (I11).

---

# Bloco C — O crash

## C01 — `processar_interacoes` não itera o índice vivo

**Problema:** Seção 2.4. 2 crashes em 240 ticks medidos; a run real parou.

**Onde:** `engine/mechanics/social.py:60`.

**Solução:** iterar uma cópia das entradas do índice (Armadilha 20).

**Passo a passo:**

1. **Teste primeiro**, em `tests/test_mecanicas.py` (siga o padrão dos testes vizinhos:
   fixture `config`, helpers de `tests/mundo_sintetico.py` — `adulto()`, `casa()`,
   `mundo_de()`):
   - `test_romance_surpresa_para_casa_nova_nao_quebra_a_iteracao(config)`.
   - Monte um mundo com: uma taverna `t1`; duas casas `c1` e `c2`; dois adultos elegíveis
     ao casamento (sexos opostos, não parentes, solteiros), **ambos com
     `localizacao_atual_id = "t1"`** e `casa_id = "c1"` / `"c2"`, com `acao_atual`
     diferente de `Acao.DORMIR`. **Nenhum NPC com `localizacao_atual_id` em `c1`** — é
     isso que faz `c1` ser chave nova no índice.
   - Numa cópia da config, ponha `biologia_e_sociedade.interacao_chance = 1.0` e
     `biologia_e_sociedade.casamento_chance_romance_fisico = 1.0`, e dê afinidade inicial
     suficiente para `verificar_elegibilidade_casamento` aceitar (leia
     `engine/mechanics/marriage.py::verificar_elegibilidade_casamento` pra saber o limiar;
     não invente número).
   - Construa `NPCMarriageManager(mundo, cfg)` e `NPCSocialManager(mundo, cfg,
     casamento=...)` e chame `processar_interacoes()`.
   - Afirme: não levanta exceção **e** os dois agora têm o mesmo `casa_id`.
   - Rode e **veja falhar** com `RuntimeError`. Se não falhar, o cenário não está
     criando chave nova — revise antes de corrigir.
2. Troque a linha 60 por `for loc_id, moradores in list(self._mundo.npcs_por_localizacao.items()):`
   e acrescente um comentário curto citando a Armadilha 20 deste documento (padrão da
   ARQUITETURA §12: dizer **por quê**).
3. Procure o mesmo padrão no resto da engine:
   `grep -rn "npcs_por_localizacao.items()\|npcs_por_casa.items()\|npcs_por_cidade.items()" engine/`.
   Para cada ocorrência: o corpo do laço pode chamar `mover_npc`/`mudar_casa`/
   `registrar_npc`/`remover_npc`/`mudar_cidade`, direta ou indiretamente? Se sim,
   aplique a mesma cópia. Se não, deixe como está (a cópia custa memória). Registre a
   lista revisada no Registro.
4. Suíte inteira passa.

**Pronto quando:** o teste novo passa; a sonda do Anexo A.4 roda 1.440 ticks sem
`RuntimeError`.

**Não faça:** envolver o laço em `try/except RuntimeError` — isso esconde o bug e perde a
interação daquele tick.

## C02 — o bebê nasce na cidade da mãe

**Problema:** 493 NPCs com `cidade_id` nulo na run real — **todos** com
`estagio_vida = 'bebe'`, ou seja, todos os nascidos em jogo.

**Onde:** `engine/mechanics/reproduction.py:141-163` (`processar_parto`): o `NPC(...)` do
recém-nascido recebe `casa_id` e `localizacao_atual_id` da mãe, mas não `cidade_id`.

**Passo a passo:**

1. **Teste primeiro**, em `tests/test_mecanicas.py`:
   `test_bebe_nasce_na_cidade_da_mae(config, monkeypatch)`.
   - Mundo sintético com uma mãe adulta de `cidade_id=2`, numa casa, com `gravidez_ticks=1`.
   - `processar_parto` dispara uma thread que chama a IA para batizar
     (`_iniciar_batizado_assincrono`). Desligue no teste:
     `monkeypatch.setattr(NPCReproductionManager, "_iniciar_batizado_assincrono", lambda self, dados: None)`.
   - Chame `NPCReproductionManager(mundo, config).processar_parto(mae)`.
   - Afirme: o NPC novo (em `mundo.npcs`, com `mae_id == mae.id`) tem `cidade_id == 2` **e**
     está em `mundo.npcs_por_cidade[2]`. Veja falhar.
2. Acrescente `cidade_id=mae.cidade_id,` ao `NPC(...)` do bebê.
3. Leia como `processar_parto` registra o bebê no mundo: se passar por
   `EstadoDoMundo.registrar_npc`, o índice por cidade já usa `npc.cidade_id` e fica certo
   com o campo preenchido. Se não passar, **pare** e registre — é outro bug.
4. `builder/fix/audit_mundo.py`: acrescente `invariante_10_todo_vivo_tem_cidade` (NPCs
   vivos com `cidade_id` nulo = 0), no mesmo formato dos 9 existentes, e inclua-o em
   `rodar_invariantes()`.
5. **Não** escreva migração para os bebês já gravados: o mundo é repovoado no fim de E01
   (decisão ❽).

**Pronto quando:** o teste passa; o invariante 10 dá 0 depois de 1 dia simulado.

## C03 — ids únicos de verdade

**Problema:** Armadilha 25. Medido: 495 nascimentos, 492 ids distintos, 3 bebês
sobrescritos.

**Onde** — os 13 pontos que montam id com relógio + sorteio (reproduza com
`grep -rn "int(time.time())\|datetime.now().timestamp())" engine builder web --include="*.py" | grep -v builder/fix`):

| arquivo:linha | id |
|---|---|
| `engine/mechanics/reproduction.py:93` | `evt_concepcao_...` |
| `engine/mechanics/reproduction.py:139` | `npc_nac_...` (o bebê) |
| `engine/mechanics/reproduction.py:189` | `evt_parto_...` |
| `engine/mechanics/finance.py:56` | `evt_heranca_...` |
| `engine/mechanics/finance.py:70` | `evt_reino_...` |
| `engine/mechanics/marriage.py:188` | `evt_uniao_...` |
| `engine/mechanics/lifecycle.py:51` | `evt_crescer_...` |
| `engine/mechanics/lifecycle.py:80` | `evt_adulto_...` |
| `engine/mechanics/lifecycle.py:103` | `evt_idoso_...` |
| `engine/mechanics/lifecycle.py:137` | `evt_morte_...` |
| `engine/mechanics/social.py:126` | `evt_...` (conversa/discussão — o mais frequente) |
| `engine/mechanics/urbanismo.py:314` | `evt_expansao_...` |
| `builder/storyteller.py:36` | `glob_...` (evento global, só segundos — pior ainda) |

**Solução:**

1. `engine/identificadores.py` (novo, infraestrutura, cabeçalho MODULE/FUNÇÃO/DESCRIÇÃO):
   ```python
   class PrefixoId(Enum):
       """C03 (docs/16_PLANO_PAINEL_E_IA.md): prefixo de cada tipo de id gerado em
       runtime. O valor é o começo do id gravado no banco — igual ao de hoje, para não
       mudar a leitura humana dos ids."""
       NPC_NASCIDO      = "npc_nac"
       EVENTO_CONCEPCAO = "evt_concepcao"
       EVENTO_PARTO     = "evt_parto"
       EVENTO_HERANCA   = "evt_heranca"
       EVENTO_REINO     = "evt_reino"
       EVENTO_UNIAO     = "evt_uniao"
       EVENTO_CRESCER   = "evt_crescer"
       EVENTO_ADULTO    = "evt_adulto"
       EVENTO_IDOSO     = "evt_idoso"
       EVENTO_MORTE     = "evt_morte"
       EVENTO_SOCIAL    = "evt"
       EVENTO_EXPANSAO  = "evt_expansao"
       EVENTO_GLOBAL    = "glob"

   def novo_id(prefixo: PrefixoId) -> str:
       """C03: `<prefixo>_<32 hex de uuid4>` — nunca relógio + sorteio pequeno
       (Armadilha 25). uuid4, e não um gerador seedado, porque o runtime da simulação já
       não é determinístico (usa `random` global e o relógio); o determinismo da
       ARQUITETURA §11 é exigência do `cartographer/`, que não gera estes ids."""
       return f"{prefixo.value}_{uuid.uuid4().hex}"
   ```
2. **Teste primeiro**, `tests/test_identificadores.py` (novo):
   - `test_ids_nao_colidem_com_relogio_e_sorteio_fixos(monkeypatch)` — fixe `time.time` e
     `random.randint` com `monkeypatch`, gere 100.000 ids, afirme que são todos distintos;
   - `test_dois_partos_no_mesmo_segundo_geram_bebes_distintos(config, monkeypatch)` —
     `time.time` e `random.randint` fixos, a thread de batizado desligada (como em C02),
     duas mães parindo; afirme 2 bebês distintos gravados no banco
     (`DatabaseManager` em `tmp_path`, nunca `:memory:`). **Veja falhar** antes do passo 3.
3. Troque os 13 pontos por `novo_id(PrefixoId.X)`. Remova `import time` onde deixar de
   ser usado.
4. Rode o `grep` de cima: 0 ocorrências fora de `builder/fix/`.

**Não faça:** trocar `INSERT OR REPLACE` por `INSERT` em `RepositorioNPC.salvar` — o
mesmo método serve para atualizar. O conserto é o id, não o SQL.

---

# Bloco O — Observabilidade: logs viram estatísticas

> Objetivo do bloco: o console mostra **uma linha de estado a cada N segundos**, o
> arquivo de log guarda **o que é narrativa e problema**, e as contagens por NPC viram
> **números agregados** que o painel lê. Referência: ARQUITETURA §9.

## O01 — níveis de log vêm do config, e o ruído por tick sai

**Problema:** Seção 2.2. 725 MB de log em 25 min; console com 1 linha por minuto simulado.

**Onde:**
- `engine/logger.py:128-143` (níveis fixos DEBUG/INFO), `engine/logger.py:70-89`
  (`is_npc_logging_enabled` **abre `config.json` à mão** a cada 5 s — viola ARQUITETURA §5).
- `engine/loop.py:207` (cabeçalho de tick em INFO).
- `run_simulation.py:90-91` (`print` por tick).
- `engine/mechanics/actions.py:166,169` e `engine/mechanics/movement.py:58,75` (DEBUG por
  minuto, sem amostragem).

**Solução:**

1. `config.json` → bloco `observabilidade`, adicione:
   ```json
   "_comentario_niveis": "O01 (docs/16_PLANO_PAINEL_E_IA.md): níveis mínimos por destino. Com 30 mil NPCs, DEBUG no arquivo gerava ~29 MB/min (725 MB em 25 min medidos). Valores aceitos: DEBUG, INFO, WARNING, ERROR.",
   "log_arquivo_nivel": "INFO",
   "log_console_nivel": "WARNING"
   ```
2. Crie o enum `NivelLog` em `engine/logger.py` (valores `"DEBUG"`, `"INFO"`,
   `"WARNING"`, `"ERROR"`) e converta o texto do config com `NivelLog(valor)` — valor
   inválido derruba na inicialização (ARQUITETURA P4/P5).
3. Em `WorldLogger.get_logger`, leia os dois níveis com
   `cfg_get(get_config(), "observabilidade", "log_arquivo_nivel")` (import de
   `config`, que é infraestrutura — permitido) e use-os nos `setLevel` dos dois handlers.
4. Em `is_npc_logging_enabled`, troque a leitura manual do arquivo por
   `cfg_get(get_config(), "salvar_logs_npc_no_banco", default=True)` (infraestrutura com
   ausência legítima — o `default=` é permitido aqui, e o comentário existente já explica).
   Remova o `import json`/`import time` de dentro da função (ARQUITETURA §15 #7).
5. `WorldLogger.debug`/`info`: além do `_modo_avanco_rapido`, retorne cedo quando o nível
   não estiver habilitado **e** o log por NPC no banco estiver desligado
   (`get_logger().isEnabledFor(logging.DEBUG)`), pra não pagar o handler.
6. `engine/loop.py:207`: `WorldLogger.info` → `WorldLogger.debug`.
7. `run_simulation.py:90-91`: apague o `print("⏩ Velocidade")`. O resumo periódico
   substitui (O03).
8. `actions.py:166,169` e `movement.py:58,75`: envolva cada `WorldLogger.debug` em
   `if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):` — mesmo
   padrão já usado em `actions.py:208,271,303`. Em `movement.py`, confira como a classe
   recebe mundo e config antes de escrever; se não tiver acesso ao `tick_count`, passe a
   decisão pelo construtor (injeção, ARQUITETURA §7) — **não** leia estado global.

**Teste:** `tests/test_observabilidade.py` (arquivo novo, docstring citando este
documento):
- `test_nivel_de_log_invalido_falha_alto` — config com `"log_arquivo_nivel": "VERBOSO"`
  levanta `ValueError` ao construir o logger. (Reset `WorldLogger._logger = None` no
  início e no fim do teste, pra não vazar estado entre testes.)

**Medir:** tamanho de `logs/world.log` após 10 min reais (Parada 1). Antes: ~290 MB em
10 min.

## O02 — avisos por NPC viram contadores do mundo

**Problema:** `[ECONOMIA]`, `[SUBNUTRIÇÃO]` e `[INANIÇÃO]` são emitidos **por NPC, por
tick** (42.476 linhas de inanição numa amostra). Com 30 mil NPCs isso não é "alerta" —
é uma estatística, e deve ser contada, não escrita.

**Solução:**

1. `engine/models.py` — enum novo, com docstring:
   ```python
   class ContadorMundo(Enum):
       """O02 (docs/16_PLANO_PAINEL_E_IA.md): ocorrências agregadas por dia simulado,
       lidas pelo coletor de estatísticas (O03) — substituem os warnings por NPC."""
       NASCIMENTO           = "nascimento"
       OBITO_VELHICE        = "obito_velhice"
       OBITO_SAUDE          = "obito_saude"        # inclui inanição
       CASAMENTO            = "casamento"
       REFEICAO_PARCIAL     = "refeicao_parcial"
       SEM_DINHEIRO_SEM_SOPAO = "sem_dinheiro_sem_sopao"
       MINUTO_EM_INANICAO   = "minuto_em_inanicao"
   ```
2. `engine/mundo.py` — `EstadoDoMundo` ganha o campo
   `contadores: collections.Counter = field(default_factory=Counter, repr=False, compare=False)`
   e a porta:
   ```python
   def contar(self, contador: ContadorMundo, quantidade: int = 1) -> None:
       """O02: única porta de incremento — nunca `mundo.contadores[...] += 1` direto."""
       self.contadores[contador] += quantidade
   ```
3. Incremente nos pontos:
   - `engine/loop.py:355-357` (`_aplicar_consequencias_de_saude`, ramo de inanição):
     `self._mundo.contar(ContadorMundo.MINUTO_EM_INANICAO)`. **Remova** o `warning` por
     NPC. (Continua morrendo; só não escreve uma linha por minuto.)
   - `engine/mechanics/actions.py:172-183` (ramo parcial): `REFEICAO_PARCIAL`; remova os
     dois `warning`.
   - `actions.py:188-192` (sem dinheiro e sopão negado): `SEM_DINHEIRO_SEM_SOPAO`; remova
     os dois `warning`.
   - `engine/mechanics/lifecycle.py::processar_morte`: `OBITO_VELHICE` no ramo
     `EstagioVida.IDOSO`, `OBITO_SAUDE` no outro (o texto do evento já separa os dois).
   - `engine/mechanics/reproduction.py::processar_parto`: `NASCIMENTO`.
   - `engine/mechanics/marriage.py::realizar_casamento`, quando o casamento de fato
     acontece: `CASAMENTO`.
4. **Não** mexa nos `evento_mundo` (nascimento, óbito, casamento): são narrativa e
   continuam indo pro log e pro banco.

**Teste:** em `tests/test_mecanicas.py`:
- `test_inanicao_conta_em_vez_de_logar(config)` — NPC com `fome` acima de
  `inaniacao_fome_limiar`, chame o caminho de consequência de saúde (via um tick de
  `GameLoop` num mundo sintético, como os testes vizinhos fazem) e afirme
  `mundo.contadores[ContadorMundo.MINUTO_EM_INANICAO] == 1`.

## O03 — coletor de estatísticas e linha de resumo no console

**Problema:** não existe nenhum número agregado do mundo; o dono do projeto lê o log pra
saber o que está acontecendo.

**Solução — o que é calculado** (tudo **da memória**, nunca SQL varrendo `npcs`):

Por cidade (`mundo.npcs_por_cidade`) e total:
- vivos por `estagio_vida`;
- adultos empregados (`local_trabalho_id` não vazio) e desempregados;
- famintos: `fome > biologia_e_sociedade.inaniacao_fome_limiar`;
- com saldo ≤ 0;
- mediana de `dinheiro_total_pc` dos adultos;
- os `ContadorMundo` do dia simulado corrente.

Desempenho (medido em `run_simulation.py`, ver D03):
- `ms_por_tick_medio` e `p95` da última janela;
- `velocidade_pedida` e `velocidade_efetiva`.

**Passo a passo:**

1. `engine/mechanics/estatisticas.py` (arquivo novo, cabeçalho MODULE/FUNÇÃO/DESCRIÇÃO):
   classe de instância `ColetorDeEstatisticas(mundo: EstadoDoMundo, config: dict)` com
   `montar() -> dict`. Métodos privados por etapa (`_por_cidade`, `_contadores_do_dia`) —
   ARQUITETURA P2, ≤ 40 linhas cada. Chaves do dict **legíveis** (`"desempregados"`, não
   `"d"`).
2. Zerar contadores por dia: no `ColetorDeEstatisticas`, guarde o dia simulado da última
   montagem (`RelogioMundo.dia_do_mundo`); quando o dia virar, grave os contadores do dia
   anterior em `resultado["dia_anterior"]` e chame `mundo.contadores.clear()`.
3. `engine/models.py` → `MetaChave`: acrescente `ESTATISTICAS = "estatisticas_json"`.
4. `config.json` → `observabilidade`:
   ```json
   "_comentario_estatisticas": "O03 (docs/16_PLANO_PAINEL_E_IA.md): o coletor roda no processo da simulação a cada N ticks e grava um JSON em mundo_meta (MetaChave.ESTATISTICAS) — o painel só lê essa linha, nunca agrega NPCs por conta própria. O console imprime uma linha de resumo a cada N segundos REAIS.",
   "estatisticas_a_cada_ticks": 60,
   "console_resumo_a_cada_s_reais": 10
   ```
5. `run_simulation.py`: construa o coletor uma vez (ponto de entrada — ARQUITETURA §7).
   A cada `estatisticas_a_cada_ticks` ticks, monte, acrescente o bloco de desempenho de
   D03 e grave com `engine.mundo.db.meta.salvar(MetaChave.ESTATISTICAS, json.dumps(...))`.
6. Linha de console a cada `console_resumo_a_cada_s_reais`: um `print` único, por
   exemplo
   `📊 Dia 4 14:07 | 153× efetivo (pedido 21600×) | 392 ms/tick | vivos 29.818 | desempregados 14.315 | famintos 58 | hoje: +12 nasc. / -31 óbitos`.
   Extraia a formatação para uma função `formatar_resumo_console(estatisticas) -> str`
   (pura, testável).

**Teste:** `tests/test_observabilidade.py`:
- `test_coletor_conta_desempregados_por_cidade` — mundo sintético com 2 cidades, 3
  adultos (2 empregados na cidade 1, 1 desempregado na cidade 2); afirme os números.
- `test_formatar_resumo_console_mostra_velocidade_pedida_e_efetiva`.

## O04 — o WAL volta a ser checkpointado

**Problema:** WAL de 1,19 GB (Seção 2.2).

**Onde:** `engine/database.py:80-87`.

**Solução:**

1. `engine/database.py`: constante de módulo documentada (é detalhe de infraestrutura,
   ARQUITETURA P3 — não é balanceamento):
   ```python
   # O04 (docs/16_PLANO_PAINEL_E_IA.md): teto do arquivo WAL depois de um checkpoint.
   # Sem isto o arquivo nunca encolhe — medido 1,19 GB com o painel aberto.
   LIMITE_WAL_BYTES = 64 * 1024 * 1024
   ```
   e, junto dos outros `PRAGMA` de cada conexão, `conn.execute(f"PRAGMA journal_size_limit={LIMITE_WAL_BYTES};")`.
2. Método novo em `DatabaseManager`:
   ```python
   def checkpoint_wal(self) -> tuple:
       """O04: força um checkpoint TRUNCATE. Devolve (ocupado, paginas_wal,
       paginas_copiadas) — `ocupado == 1` significa que um leitor segurou o snapshot e
       o checkpoint não completou; quem chama decide se loga."""
   ```
   Isto é infraestrutura (`DatabaseManager` cuida de WAL — ARQUITETURA §8), não SQL de
   domínio, então pode morar aqui.
3. `config.json` → `simulacao`:
   `"wal_checkpoint_a_cada_ticks": 60` com `_comentario_wal_checkpoint`.
4. `run_simulation.py`: a cada `wal_checkpoint_a_cada_ticks`, chame
   `engine.mundo.db.checkpoint_wal()`; se `ocupado == 1` três vezes seguidas, um único
   `WorldLogger.warning` dizendo que um leitor está segurando o WAL.

**Teste:** `tests/test_persistencia.py`:
`test_checkpoint_wal_devolve_tupla_de_tres_inteiros(tmp_path)` — `DatabaseManager` em
arquivo temporário (nunca `:memory:`), grave algo, chame e afirme o formato.

**Medir:** tamanho do `-wal` na Parada 1 e na Parada 2.

## O05 — resíduo de ponto flutuante no saldo

**Problema:** Seção 2.2, último parágrafo. Pagador com saldo `1,37e-13` fica no ramo
"parcial" pra sempre em vez de cair no sopão.

**Onde:** `engine/mechanics/actions.py:172` (`elif pagador.dinheiro_total_pc > 0:`).

**Solução:** o saldo abaixo de uma fração mínima conta como zero.

1. `config.json` → `acoes.comer`: `"saldo_residual_pc": 0.01` com comentário citando
   O05 e o valor medido `1.37e-13`.
2. Em `_executar_comer`, leia `saldo_residual = cfg_get(cfg, "saldo_residual_pc")` e troque
   a condição do ramo parcial por `pagador.dinheiro_total_pc > saldo_residual`. No ramo
   seguinte (sopão), zere o resíduo antes: `pagador.dinheiro_total_pc = 0` quando
   `0 < saldo <= saldo_residual`.
3. Confira `minutos_seguros_para_pular_comer` (`actions.py`, logo acima): ele usa
   `pagador.dinheiro_total_pc // custo_do_tick` e **não** precisa mudar — só confirme e
   registre.

**Teste:** `tests/test_mecanicas.py`:
`test_saldo_residual_vai_para_o_sopao_e_nao_para_refeicao_parcial(config)` — pagador com
`dinheiro_total_pc = 1e-13`; afirme que `ContadorMundo.REFEICAO_PARCIAL` não foi contado.

⚠️ Isto **não** é recalibração de economia: não muda preço, fome nem sopão. Só impede que
um número que é zero na prática seja tratado como dinheiro.

---

# Bloco D — Desempenho do motor

## D01 — morte não força mais o recálculo de dependentes do mundo inteiro

**Problema:** Seção 2.3 — 766.300 recálculos em 60 ticks (~55 ms/tick).

**Onde:** `engine/loop.py:362-372` (`_remover_falecidos`) e `engine/loop.py:408-416`.

**Solução:** depois de filtrar a lista, atualizar o marcador de identidade — as casas
afetadas já foram marcadas por `EstadoDoMundo.remover_npc` (Armadilha 23).

**Passo a passo:**

1. **Teste primeiro**, `tests/test_num_dependentes.py`:
   `test_morte_nao_recalcula_todas_as_casas(config, monkeypatch)`:
   - mundo sintético com 50 casas, 2 adultos por casa;
   - rode 1 tick pra estabilizar;
   - `monkeypatch.setattr(NPCUtils, "recalcular_dependentes_da_casa", contador)` onde
     `contador` conta chamadas;
   - mate 1 NPC pela porta real (`NPCLifecycleManager.processar_morte`) e rode mais 1 tick;
   - afirme `chamadas <= 2` (a casa do morto, e no máximo mais uma se o tick mudar alguém
     de casa). **Veja falhar** (hoje dá ≥ 50).
2. Em `_remover_falecidos`, logo depois de `self._mundo.npcs = [...]`, acrescente
   `self._ultima_lista_de_npcs = self._mundo.npcs` com comentário: a morte já marcou a
   casa suja em `remover_npc`; sem esta linha a troca de identidade faz
   `_atualizar_dependentes` recalcular o mundo inteiro (D01, Armadilha 23).
3. Rode `tests/test_num_dependentes.py` inteiro — os testes existentes provam que a
   contagem de dependentes continua certa depois de uma morte.

**Medir:** ms/tick médio na sonda do Anexo A.4, antes e depois. Esperado: queda de
**~40–55 ms** num mundo com ~1 morte por tick.

## D02 — herança não varre mais a população inteira

**Problema:** 12,6 ms por morte (Seção 2.3). `NPCLegacyManager.processar_heranca`
(`engine/mechanics/finance.py:24-27`) percorre `self._mundo.npcs` pra achar filhos.

**Solução:** índice mantido de filhos por genitor em `EstadoDoMundo`, atualizado pelas
mesmas portas dos outros índices (padrão A04).

**Passo a passo:**

1. `engine/mundo.py`:
   - campo `filhos_por_genitor: Dict = field(default=None, repr=False, compare=False)`;
   - em `_reconstruir_indices_de_npc` (`mundo.py:321`): para cada NPC com `mae_id`
     ou `pai_id`, `setdefault(genitor_id, []).append(npc)`;
   - em `registrar_npc`: o mesmo para o NPC novo;
   - **não** remova na morte: o consumidor filtra por `esta_vivo()`, e o filho morto
     continua sendo filho (a lista é pequena).
2. `finance.py::processar_heranca`: troque o laço por
   `herdeiros = [n for n in self._mundo.filhos_por_genitor.get(npc.id, ()) if n.esta_vivo()]`
   com comentário citando D02.
3. **Cuidado com gêmeo** (armadilha 18 do doc 4): procure outros laços "filhos de X" sobre
   `mundo.npcs`: `grep -rn "mae_id == \|pai_id == " engine/`. Para cada um num caminho
   quente (por tick ou por evento frequente), use o índice; registre os que ficaram.
4. Registre no Registro se `recarregar_habitantes()` (`engine/core.py`) ainda é chamado
   em algum lugar — se for, `_reconstruir_indices_de_npc` já cobre o índice novo.

**Teste:** `tests/test_indices_npc.py`:
- `test_filhos_por_genitor_inclui_recem_nascido` (via `registrar_npc`);
- `test_heranca_vai_para_filho_vivo_sem_varrer_populacao` — herança correta com o índice.

**Medir:** tempo de `processar_heranca` no cProfile (Anexo A.4). Esperado: < 1 ms por morte.

## D03 — o laço de `run_simulation.py` desconta o custo do tick e mede a velocidade real

**Problema:** `run_simulation.py:70,92` dorme `max(0.005, 60/velocidade)` **depois** do
tick, sem descontar quanto o tick levou — em velocidade alta, soma 5 ms inúteis por tick,
e ninguém mede a velocidade entregue.

**Solução:**

1. Extraia de `start_simulation` uma classe pequena `RitmoDoLaco` (no próprio
   `run_simulation.py`, ou em `engine/tempo.py` se preferir — é função de tempo real, não
   de domínio):
   - `registrar_tick(duracao_s: float)` — guarda numa janela das últimas N durações
     (`collections.deque(maxlen=...)`);
   - `espera_s(velocidade_pedida: float, duracao_ultimo_tick_s: float) -> float` →
     `max(0.0, 60.0 / velocidade_pedida - duracao_ultimo_tick_s)`;
   - `velocidade_efetiva() -> float` → `60.0 / media_das_duracoes_incluindo_espera`;
   - `ms_por_tick_medio()`, `ms_por_tick_p95()`.
2. `config.json` → `simulacao`: `"janela_medicao_ritmo_ticks": 120` com comentário.
3. No laço: meça `time.perf_counter()` em volta de `engine.tick()`, registre, durma
   `espera_s(...)` só se `> 0`. Entregue `velocidade_efetiva`, `ms_por_tick_medio` e `p95`
   ao bloco de desempenho das estatísticas (O03).
4. O `sleep` do modo pausado (`time.sleep(1.0)`) fica como está.

**Teste:** `tests/test_run_simulation.py`:
- `test_espera_desconta_duracao_do_tick` — pedida 60× (1 s/tick), tick de 0,3 s → espera 0,7 s;
- `test_espera_nunca_negativa` — pedida 21600×, tick de 0,1 s → 0,0;
- `test_velocidade_efetiva_com_ticks_de_100ms_sem_espera_e_600x`.

## D04 — índices SQL na tabela `npcs`

**Problema:** `engine/schema.sql` só tem 2 índices, nenhum em `npcs`. Os endpoints novos
de P02 (filtro por cidade) e M04 (NPCs por local) filtram por `cidade_id` e
`localizacao_atual_id`.

**Solução:** em `engine/schema.sql`, depois do `CREATE TABLE npcs`:
```sql
-- D04 (docs/16_PLANO_PAINEL_E_IA.md): filtros do painel paginado (P02) e da camada de
-- NPCs do mapa (M04). Sem índice, cada requisição varre a tabela inteira.
CREATE INDEX IF NOT EXISTS idx_npcs_cidade_saude ON npcs(cidade_id, saude);
CREATE INDEX IF NOT EXISTS idx_npcs_localizacao ON npcs(localizacao_atual_id);
```
`CREATE INDEX IF NOT EXISTS` roda em banco existente pelo `_init_db` sem migração extra.

**Medir:** `EXPLAIN QUERY PLAN` das consultas de P02 e M04 deve citar o índice (registre
a saída). Custo de escrita em `salvar_muitos` (que atualiza `localizacao_atual_id` todo
tick): meça ms/tick antes e depois na sonda do Anexo A.4. **Se o tick piorar mais de
5%**, remova `idx_npcs_localizacao` e registre a divergência — M04 continua funcionando
(consulta por `IN (...)` sobre dezenas de milhares de linhas ainda é aceitável a cada 2 s).

---

# Bloco F — Frontend: a refatoração de JS/HTML que ficou para trás

> **Por que está aqui:** o `10_PLANO_REFATORACAO.md` especificou o Bloco H (R-H01 a R-H06)
> — módulos ES, nenhum `onclick`, nenhum estilo inline, enums no JS, config servida pela
> API, `dashboard.js` dividido — e **nada disso foi executado** (não existe linha de R-H
> no registro daquele documento). A ARQUITETURA §10 é o padrão; este bloco é o caminho até
> ele, com os números de **hoje**.
>
> **Regra de ouro: é movimentação, não mudança de comportamento.** Toda aba funciona igual
> antes e depois de cada tarefa — a única exceção é o escape de HTML de F05, que corrige
> uma falha. As mudanças visíveis do painel vêm no Bloco P, **em cima** da estrutura nova.
>
> **Como verificar sem teste automatizado** (o projeto não tem teste de JS): antes de F01,
> tire capturas de tela de cada aba — Mapa (mundi, um continente, uma cidade), Habitantes
> (um filtro aplicado e uma ficha aberta nas duas abas do modal), Mestre (histórico
> carregado), Mapa Live (mundo, zoom numa cidade com edifícios, um popup aberto). Guarde em
> `/tmp/antes_F/`. Depois de **cada** tarefa: as mesmas telas, comparadas, e **nenhum erro
> vermelho no console** do DevTools.

**Estado medido em 2026-09-14:**

| arquivo | linhas | `onclick=` | `style="` | `let`/`const`/`var` de topo | `innerHTML` |
|---|---|---|---|---|---|
| `web/templates/index.html` | 221 | 24 | 35 | — | — |
| `web/static/js/dashboard.js` | 534 | 7 | 68 | 7 | 12 |
| `web/static/js/mapa_composto.js` | 687 | 0 | 1 | 28 | 3 |
| `web/static/js/mapa_leaflet.js` | 477 | 2 | 9 | 22 | 2 |

Reproduza com:
```bash
for f in web/templates/index.html web/static/js/*.js; do
  echo "$f linhas=$(wc -l <$f) onclick=$(grep -c 'onclick=' $f) style=$(grep -c 'style="' $f) topo=$(grep -cE '^(let|var|const) ' $f) innerHTML=$(grep -c innerHTML $f)"
done
```

## F01 + F02 — um ponto de entrada em módulo ES, e nenhum `onclick` (R-H01 + R-H02)

⚠️ **As duas tarefas são um commit só.** Script em módulo não expõe funções no escopo
global: no momento em que os arquivos virarem módulo, todo `onclick="funcao()"` do HTML
quebra. Converter sem trocar os `onclick` deixa o painel inteiro inoperante.

**Problema:** 3 tags `<script>` (`index.html:216-219`) que dependem da ordem para
funcionar; chamadas cruzadas por nome global (`dashboard.js` chama `initMapaLeaflet()`,
`carregarHistoricoMestre()` e `window.updateMapEntities()`); 24 `onclick` + 1 `onkeydown`
no HTML e 9 `onclick` gerados dentro de template strings (`dashboard.js`: 7;
`mapa_leaflet.js`: 2).

**Passo a passo:**

1. `index.html`: a tag do Leaflet (UMD, define o global `L`) continua **antes**. As três
   tags do projeto viram uma:
   `<script type="module" src="{{ url_for('static', filename='js/app.js') }}"></script>`.
2. `web/static/js/acoes.js` (novo): o registro de ações.
   ```js
   const ACOES = new Map();
   export function registrarAcoes(mapa) { for (const [nome, fn] of Object.entries(mapa)) ACOES.set(nome, fn); }
   export function despachar(ev) {
       const alvo = ev.target.closest('[data-acao]');
       if (!alvo) return;
       ACOES.get(alvo.dataset.acao)?.(alvo, ev);
   }
   ```
   Fica num arquivo próprio (e não em `app.js`) para os módulos poderem registrar suas
   ações sem importar `app.js` — o que criaria import circular.
3. `web/static/js/app.js` (novo): importa os módulos, chama a função de início de cada um,
   instala **um** `document.addEventListener('click', despachar)` e mantém o polling.
4. Troque cada `onclick` por `data-acao` (+ `data-*` para os argumentos). Exemplos:
   - `onclick="switchView(this, 'map-view')"` → `data-acao="trocar-aba" data-aba="mapa"`;
   - `onclick="setSpeed(60)"` → `data-acao="velocidade" data-valor="60"`;
   - `onclick="abrirHistorico('${n.id}', ...)"` (template string) →
     `data-acao="abrir-ficha" data-npc-id="${escaparHtml(n.id)}"`.
   - O overlay do modal usa `onclick="fecharHistorico(event)"` e o conteúdo usa
     `event.stopPropagation()`: com delegação, a ação `fechar-ficha` fecha só quando
     `ev.target` é o próprio overlay.
   - O `onkeydown` do campo do Mestre (Enter envia) vira um `addEventListener('keydown')`
     no próprio elemento, registrado pelo módulo do chat.
5. Código de topo que roda ao carregar (`mapa_composto.js:221-290` com os eventos do
   canvas, `:545` e `:587-595` com os botões) vai para dentro de uma função exportada
   `iniciarMapaComposto()`, chamada por `app.js`.
6. O estado de cada módulo vira **um** objeto (`const estado = { ... }`), não dezenas de
   `let` soltos (ARQUITETURA §10 regra 4).

**Validar:** `grep -rn "onclick=\|onkeydown=" web/templates web/static/js` → 0;
`grep -cE '^(let|var) ' web/static/js/*.js` ≤ 3 por arquivo; capturas iguais; console limpo.

## F03 — enums de estado no JS (R-H03)

**Problema:** modos e filtros comparados como texto solto (`'map-view'`, `'vivos'`,
`'global'`, `'profile'`), e `setNpcFilter` (`dashboard.js:33-44`) decide o botão ativo
**lendo o texto visível** (`btn.innerText.toLowerCase().includes('vivos')`).

**Passo a passo:**

1. `web/static/js/constantes.js` (novo):
   ```js
   export const Modo      = Object.freeze({ GLOBAL: 'global', CONTINENTE: 'continente', CIDADE: 'cidade' });
   export const Aba       = Object.freeze({ MAPA: 'mapa', HABITANTES: 'habitantes', MESTRE: 'mestre', MAPA_LIVE: 'mapa-live' });
   export const FiltroNpc = Object.freeze({ VIVOS: 'vivos', MORTOS: 'mortos', TODOS: 'todos' });
   export const AbaModal  = Object.freeze({ PERFIL: 'perfil', LOGS: 'logs' });
   ```
2. O botão ativo passa a ser decidido por `btn.dataset.filtro === filtro`.
3. `FiltroNpc` é **temporário**: em P02 a lista de situações passa a vir da API
   (`SituacaoHabitante`, ARQUITETURA §6 — enum que o JS precisa é servido, não copiado), e
   P04 remove `FiltroNpc`.

**Validar:** `grep -n "'vivos'\|'mortos'\|'global'\|'map-view'" web/static/js/*.js` só
encontra `constantes.js`.

## F04 — nenhum valor do config escrito no JS (R-H04)

**Problema:** `mapa_leaflet.js:22-51` repete valores do config como default
(`leafletDimensaoGlobal = 768`, `leafletZoomMaximo = 15`, `leafletMaxNativeZoom = 11`,
`leafletTooltipZoomMin = 5`, `leafletMetrosPorPixelMundo = 15811.4`,
`leafletViaLarguraM = {...}`, `leafletViaLarguraMinPx = 1.5`), e os repete de novo como
fallback em `carregarMundoLeaflet` (`:116-129`, `|| 768`, `|| 15`, ...) e em `estiloRua`
(`:189`, `|| 5`). Tudo já é servido por `/api/continentes` (`web/rotas/mapa.py:89-126`).

**Passo a passo:**

1. Os valores começam como `null`. Se `/api/continentes` falhar ou vier sem uma chave, o
   mapa **não desenha**: mostra a mensagem no `#status-bar` e loga `console.error` com a
   chave que faltou.
2. Apague os `|| número` dos fallbacks.
3. `grep -n "Zona Urbana\|biome" web/static/js/mapa_composto.js`: se existir tabela de
   biomas própria, troque pelo campo `biomas` de `/api/continentes`.
4. Cores e emojis por categoria (`CATEGORIA_EDIFICIO_COR`, `TIPO_CIDADE_EMOJI`) são
   **apresentação** e podem ficar no JS (vão para `formatacao.js` em F05) — mas registre no
   Registro que as chaves precisam bater com `CategoriaLocal`.

**Validar:** com o `run_dashboard.py` parado depois de a página carregar, recarregar a aba
Mapa Live mostra erro, e não um mundo desenhado com escala escrita à mão.

## F05 — um arquivo por assunto, e todo texto do servidor escapado (R-H05)

**Problema:** três arquivos acima do limite de 250 linhas; `dashboard.js` mistura abas,
polling, grade de NPCs, ficha, modal e o chat do Mestre. Texto gerado por LLM (nome,
personalidade, background) vai para `innerHTML` **sem escape** — só o chat usa
`escapeHtmlMestre`.

**Estrutura alvo** (todos em `web/static/js/`, módulo ES, ≤ 250 linhas cada):

| arquivo | vem de | responsabilidade |
|---|---|---|
| `app.js` | F01 | ponto de entrada, início dos módulos, polling (`/api/update` até P01) |
| `acoes.js` | F01 | registro e despacho de `data-acao` |
| `api.js` | todos os `fetch` dos três arquivos | um lugar só para chamadas HTTP |
| `constantes.js` | F03 | enums |
| `formatacao.js` | `dashboard.js`: `getNPCAvatar`, `renderStatus`, rótulos de estágio de vida (ternário duplicado em `update()` e em `renderNPCProfile()`); `escapeHtmlMestre` → **`escaparHtml`**; cores/emojis de `mapa_leaflet.js` | formatação e escape |
| `navegacao.js` | `dashboard.js`: `switchView`, `toggleEventLog`, pausa, velocidade, relógio, banner, crônicas | abas e barra superior |
| `painel_npcs.js` | `dashboard.js`: grade e filtro de habitantes | aba Habitantes (reescrita em P04) |
| `ficha_npc.js` | `dashboard.js`: `abrirHistorico`, `renderNPCProfile`, `switchModalTab`, `fecharHistorico`, `switchModalNPC` | modal do habitante (reescrito em P03/P04) |
| `chat_mestre.js` | `dashboard.js`: Modo Mestre inteiro | aba Mestre |
| `mapa_composto_estado.js` | `mapa_composto.js`: variáveis de estado, canvas/contexto, conversão de coordenadas | estado compartilhado do mapa em canvas |
| `mapa_composto.js` | `mapa_composto.js`: `loadContinents`, `selectContinent`, `selectCity`, mapa mundi | início e navegação do mapa em canvas |
| `mapa_composto_desenho.js` | `draw`, `drawCityLegend`, `drawTooltip`, `animateLoop`, `drawCityGridAndEntities`, `drawGlobalMarkers`, `drawContinentMarkers`, `lerp` | desenho |
| `mapa_composto_interacao.js` | eventos de mouse e roda, botões de zoom, `adjustZoom`, `isClickInCity` | interação |
| `mapa_composto_inspetor.js` | `fetchTerrainInfo`, `updateSidebar` | painel lateral de terreno |
| `mapa_leaflet.js` | `initMapaLeaflet`, `carregarMundoLeaflet`, `onMapaLeafletClick`, lista e salto de continentes | início do Mapa Live |
| `mapa_leaflet_estilos.js` | `estiloRua`, `estiloEdificio`, `estiloLote`, `ESTILO_CAMADA_CIDADE`, `pxDeTelaPorMetro` | estilos |
| `mapa_leaflet_camadas.js` | `criarCamadasVetoriaisLeaflet`, `criarMarcadorDetalheCidade`, `criarMarcadorFeatureLeaflet`, `carregarFeaturesVisiveisLeaflet`, `mesclarLotesAlteradosLeaflet`, `_cidadesVisiveisLeaflet` | camadas vetoriais (M02/M03 mexem aqui) |

Se algum arquivo ainda passar de 250 linhas, divida mais por assunto e registre.

**Passo a passo:**

1. Crie os arquivos e **mova** as funções (recortar, não copiar), exportando o que outro
   módulo usa. Renomeie só o necessário.
2. `escaparHtml(texto)` em **todo** texto vindo do servidor que vai para `innerHTML` ou
   para `bindPopup`/`bindTooltip` do Leaflet: nome, profissão, ação, humor, resumo de
   evento (crônicas), nome nos relacionamentos, mensagem de log, nome de cidade/continente,
   `tipo_local`, `bairro`. São 17 `innerHTML` hoje — revise cada um e registre a lista.
3. Apague `window.updateMapEntities` e a chamada em `update()` (a contagem de NPCs da
   região já vem de `/api/regiao/<nome>/entities`; ver P01).
4. No `10_PLANO_REFATORACAO.md`, logo abaixo do título do Bloco H, uma linha:
   `> ✅ Executado em 16_PLANO_PAINEL_E_IA.md, Bloco F (<data>).`

**Validar:**
- `wc -l web/static/js/*.js` → nenhum acima de 250;
- capturas iguais às de `/tmp/antes_F/`;
- **escape:** numa **cópia** do banco apontada pelo dashboard, renomeie um NPC para
  `<b>Teste</b>` (`UPDATE npcs SET nome='<b>Teste</b>' WHERE id=...`), abra a ficha dele:
  o texto aparece **literalmente**, com os sinais `<` e `>`, sem negrito.

## F06 — estilos inline para o CSS (R-H06)

**Problema:** 35 `style="..."` no `index.html`, 68 em `dashboard.js`, 9 em
`mapa_leaflet.js`, 1 em `mapa_composto.js` (contagem de antes de F05 — refaça a contagem
sobre os módulos novos).

**Passo a passo:**

1. Crie classes em `web/static/css/style.css` (ou `mapa_composto.css`, quando o estilo for
   do mapa em canvas), usando as variáveis que já existem (`--accent`, `--danger`,
   `--success`, `--warning`, `--text-dim`).
2. Valor calculado em tempo de execução (largura da barra de saúde, cor por faixa de
   valor) **não** vira `style="width:${x}%"` em template: use uma classe por faixa
   (`.saude-baixa`, `.saude-ok`) e, para o número contínuo, uma variável CSS definida por
   propriedade (`elemento.style.setProperty('--percentual', x + '%')`) consumida pela
   classe.
3. Os objetos de estilo do Leaflet (`{ color: ..., weight: ... }` em `estiloRua` etc.) são
   API do Leaflet, **não** estilo inline de HTML — ficam como estão.

**Validar:** `grep -rn 'style="' web/templates web/static/js` → 0; capturas iguais.

---

# Bloco P — Painel

> Referências: ARQUITETURA §10 (frontend), §14.3 (endpoint novo), Armadilha 24.
>
> **Pré-requisito: Bloco F concluído.** O frontend já é um conjunto de módulos ES
> (`app.js`, `api.js`, `navegacao.js`, `painel_npcs.js`, `ficha_npc.js`,
> `formatacao.js`, ...). As referências de linha a `dashboard.js` nas tarefas abaixo
> descrevem o código **de antes do F** — depois dele, procure a função pelo nome no módulo
> para onde F05 a moveu.
>
> **Regra do bloco:** todo JS novo segue a ARQUITETURA §10 e a estrutura de F05: ≤ 250
> linhas por arquivo, sem `onclick`, sem `style=""`, `escaparHtml` em todo texto do
> servidor, estado de UI em `dataset`, todo `fetch` em `api.js`.

## P01 — `/api/update` vira `/api/estado`, enxuto

**Problema:** 23 MB/s (Seção 2.1).

**Consumidores atuais de `/api/update`** (todos precisam ser migrados nesta tarefa ou em
P03/P04 — **não** deixe nenhum quebrado):

| consumidor | usa | vai passar a usar |
|---|---|---|
| `dashboard.js:100-115` relógio, pausa, velocidade, banner de evento | `h`, `p`, `v`, `evg` | `/api/estado` |
| `dashboard.js:172-178` crônicas | `evs` | `/api/estado` |
| `dashboard.js:118-120` → `mapa_composto.js:201` `updateMapEntities` | `npcs` (só conta quantos NPCs estão na cidade aberta) | contagem que já vem em `/api/regiao/<nome>/entities` (`cityEntities.npcs`), carregada uma vez ao abrir a região — apague `window.updateMapEntities` e a chamada |
| `dashboard.js:122-170` aba Habitantes | `npcs` | P02/P04 |
| `dashboard.js:216-235,371` ficha do NPC (`allNpcs`) | `npcs` | P03 |
| `web/dashboard.py:61-72` `/api/init` → `staticData` | `locais` (18 mil) e `mapa` | **ninguém usa** `staticData` (`dashboard.js:55` diz "Old map generation removed") — remova `locais` do `/api/init` |

**Passo a passo:**

1. `web/rotas/estado.py` (blueprint novo `estado_bp`, registrado em
   `web/rotas/__init__.py::registrar_blueprints`):
   `GET /api/estado` → `{"hora": ..., "pausado": ..., "velocidade_pedida": ...,
   "velocidade_efetiva": ..., "evento_global": {...}|null, "cronicas": [...]}`.
   - `velocidade_efetiva` vem de `MetaChave.ESTATISTICAS` (O03), `null` se ainda não houver.
   - Serialização em `web/serializadores.py` (arquivo novo), chaves legíveis (§14.3).
   - Sem `try/except` na rota; o blueprint usa `registrar_erro_handler` como os outros
     (`web/rotas/_erros.py`).
   - A rota tem ≤ 10 linhas.
2. `web/dashboard.py`: apague `get_update` e a função `formatar_moeda` **só depois** de
   movê-la para `web/serializadores.py` (P02 também usa). Em `get_init`, remova a montagem
   de `locais`.
3. `web/static/js/api.js` (criado em F05): acrescente `export async function obterEstado()`.
4. `web/static/js/estado.js` (módulo ES novo): polling de 1 s de `/api/estado`, atualiza
   relógio, botão de pausa, banner e crônicas. Mostra a velocidade como
   `153× (pedido 21600×)`. Remova de `app.js` o polling antigo de `/api/update`.
5. `app.js` importa e inicia `estado.js` — continua existindo **uma** tag de script (F01).

**Teste:** `tests/test_rotas_painel.py` (novo) com o `app.test_client()` do Flask:
- `test_api_estado_nao_devolve_npcs_nem_locais` — a resposta não tem as chaves `npcs`
  nem `locs` e tem menos de 5 KB num banco de teste com 500 NPCs (monte o banco com
  `DatabaseManager(db_path=str(tmp_path/"teste.db"), pool_size=2)`; para apontar o
  dashboard pra ele, injete via `web.banco` — leia `web/banco.py` e, se não houver como
  injetar, acrescente `configurar_db(db)` no mesmo padrão de `config.configurar_fonte`).

**Medir (Parada 2):** tamanho e tempo de `/api/estado`.

## P02 — `/api/habitantes` paginado e filtrado no SQL

**Solução:**

1. `engine/repositorios/npc.py` — dataclass de filtro (≤ 5 parâmetros por método,
   ARQUITETURA §4) e dois métodos:
   ```python
   @dataclass
   class FiltroHabitantes:
       cidade_id: Optional[int] = None
       busca_nome: str = ""
       estagio_vida: Optional[str] = None   # EstagioVida.X.value
       acao: Optional[str] = None           # Acao.X.value
       situacao: str = "vivos"              # "vivos" | "mortos" | "todos" — enum SituacaoHabitante
       pagina: int = 1
       por_pagina: int = 50
   ```
   - `contar_habitantes(filtro) -> int`
   - `listar_habitantes(filtro) -> list` — `SELECT` só das colunas do cartão, `WHERE`
     montado com parâmetros (`?`, **nunca** f-string com valor do usuário),
     `ORDER BY nome LIMIT ? OFFSET ?`. Busca: `nome LIKE ?` com `%termo%`.
   - `SituacaoHabitante` é enum (P4) em `engine/models.py`.
2. `config.json` → bloco novo `painel`:
   ```json
   "painel": {
     "_comentario": "Bloco P (docs/16_PLANO_PAINEL_E_IA.md): parâmetros de apresentação do dashboard, servidos pela API — o JS nunca repete estes números (ARQUITETURA §10 regra 6).",
     "habitantes_por_pagina": 50,
     "habitantes_por_pagina_maximo": 200,
     "estado_polling_ms": 1000,
     "estatisticas_polling_ms": 5000
   }
   ```
3. `web/rotas/habitantes.py` (blueprint `habitantes_bp`):
   `GET /api/habitantes?cidade=&busca=&estagio=&acao=&situacao=&pagina=&por_pagina=`.
   Valide: `por_pagina` limitado ao máximo do config; `estagio`/`acao`/`situacao`
   convertidos pelo enum (valor inválido → 400 com mensagem). Resposta:
   `{"total": N, "pagina": p, "por_pagina": k, "habitantes": [...]}`.
4. `GET /api/habitantes/filtros` → cidades (`db.mundo.carregar_cidades_por_id()`),
   valores de `EstagioVida`, `Acao`, `SituacaoHabitante`, e `painel.*` — **servidos**, não
   copiados no JS.

**Teste:** `tests/test_repositorio_npc.py`:
- `test_listar_habitantes_pagina_e_filtra_por_cidade(tmp_path)` — 120 NPCs em 2 cidades;
  página 2 de 50 da cidade 1 devolve os itens certos e `contar` o total certo;
- `test_busca_por_nome_nao_aceita_injecao(tmp_path)` — busca `"'; DROP TABLE npcs; --"`
  devolve 0 e a tabela continua existindo.

## P03 — `/api/habitantes/<id>`: a ficha resolvida no servidor

**Problema:** a ficha (`dashboard.js:249-347`) resolve pai, mãe, cônjuge e filhos
procurando em `allNpcs` — a lista inteira que P01 elimina.

**Solução:**

1. `RepositorioNPC.buscar_ficha(npc_id) -> Optional[dict]`: o NPC + nomes de mãe, pai,
   cônjuge (subconsulta ou `LEFT JOIN` na própria tabela) + filhos
   (`WHERE mae_id = ? OR pai_id = ?`).
2. `GET /api/habitantes/<id>` → a ficha; 404 se não existir.
3. Relacionamentos continuam em `/api/npc_rels/<id>` e logs em `/api/npc_logs/<id>`
   (já existem em `web/dashboard.py`); acrescente o **nome** do outro NPC em
   `/api/npc_rels` (hoje o front resolve com `allNpcs`).

**Teste:** `test_buscar_ficha_resolve_nomes_de_pais_e_filhos(tmp_path)`.

## P04 — a aba Habitantes, reescrita

**Solução (frontend):**

1. `web/static/js/painel_npcs.js` (criado em F05 — aqui ele é **reescrito**):
   - barra de filtros: seletor de cidade, estágio, ação, situação, campo de busca com
     debounce de 300 ms (constante de módulo nomeada — é detalhe de UI, não config);
   - grade de cartões da página atual; paginação "‹ anterior · página X de Y · próxima ›";
   - **não** faz polling da lista. Recarrega ao mudar filtro/página, ao clicar num botão
     "↻ Atualizar", e automaticamente a cada `painel.estatisticas_polling_ms` **só se a
     aba estiver visível**;
   - comportamento por delegação `data-acao` (ARQUITETURA §10 regra 2).
2. `web/static/js/ficha_npc.js` (criado em F05, reescrito aqui): abre o modal existente
   (`#npc-log-modal`) usando `/api/habitantes/<id>`; links de pai/mãe/cônjuge/filho
   reabrem a ficha pelo id.
3. `web/static/js/formatacao.js` (criado em F05): acrescente só o que faltar. Remova
   `FiltroNpc` de `constantes.js` (F03) — as situações agora vêm de `/api/habitantes/filtros`.
4. `index.html`: substitua o conteúdo de `#npc-view` pela nova estrutura (sem `onclick`,
   sem `style=""`); estilos novos em `style.css`.
5. Remova dos módulos de F05 o que ficou sem uso: `setNpcFilter`, `allNpcs`, `allRels`, `getNPCNameById`,
   `getNPCChildren`, `getNPCRelationships`, `switchModalNPC`, `renderNPCProfile`,
   `abrirHistorico`, o bloco `npc-view` do `update()`. Confira com
   `grep -n "allNpcs\|abrirHistorico" web/` que nada restou.

**Teste manual (registre no Registro):** com a run de ~30 mil NPCs, trocar de página
responde em < 300 ms; buscar "Thorne" filtra; a ficha abre com os nomes dos pais.

## P05 — aba Estatísticas

**Solução:**

1. `GET /api/estatisticas` (em `web/rotas/estado.py`): devolve o JSON de
   `MetaChave.ESTATISTICAS` como está (o painel não recalcula nada — ARQUITETURA §2,
   "web não contém regra").
2. `index.html`: nova aba `📊 Estatísticas` (botão com `data-acao="trocar-aba"
   data-aba="estatisticas"`), view `#estatisticas-view`.
3. `web/static/js/painel_estatisticas.js` (módulo ES): polling de
   `painel.estatisticas_polling_ms` só com a aba visível. Mostra:
   - cartão de desempenho: velocidade efetiva × pedida, ms/tick médio e p95;
   - tabela por cidade: vivos (bebê/criança/adulto/idoso), empregados, desempregados,
     famintos, saldo ≤ 0, mediana de saldo;
   - cartão "hoje" e "ontem": nascimentos, óbitos (velhice / saúde), casamentos,
     refeições parciais, sem dinheiro e sem sopão, minutos em inanição.
4. Tabela dentro de um contêiner com `overflow-x: auto`.

**Teste:** `test_api_estatisticas_devolve_o_json_gravado(tmp_path)`.

---

# Bloco M — Mapa Live

## M01 — medir antes de mexer

**Por quê:** o "2 minutos na primeira vez / 30 s por zoom" foi observado **com o polling
de 23 MB ativo**. Não foi medido depois de P01. Otimizar sem medir de novo é otimizar a
coisa errada (P06 do doc 1: "nunca paralelizar antes de medir").

**Passo a passo (depois de P01 pronto):**

1. Rode `run_simulation.py` e `run_dashboard.py`. Abra o painel no Chrome, DevTools →
   aba Network, "Disable cache" marcado.
2. Aba 🗾 Mapa Live. Anote: tempo até o primeiro tile aparecer; tempo até as cidades
   aparecerem; soma de tempo das requisições `/tiles/`, `/api/mapa/features`,
   `/api/cidade/*/lotes_alterados`.
3. Duplo-clique em Quenanfield (vai pro zoom de edifícios). Anote o tempo total até os
   edifícios aparecerem, e na aba **Performance** grave 5 s de pan/zoom: quanto tempo foi
   "Scripting" e "Rendering/Painting".
4. Repita com o servidor aquecido (segunda vez).
5. Registre tudo no Registro. **Se o tempo já estiver aceitável** (primeiro carregamento
   < 10 s, zoom < 2 s), registre e pule direto para M04.

## M02 — Leaflet em canvas, e não recarregar o que já está na tela

**Onde:** `web/static/js/mapa_leaflet.js:93-103` (criação do mapa), `:156`
(`moveend`), `:392-423` (`carregarFeaturesVisiveisLeaflet`) — linhas de antes do F. Depois de F05, a
criação fica em `mapa_leaflet.js` e o carregamento em `mapa_leaflet_camadas.js`.

**Solução:**

1. `L.map(..., { preferCanvas: true, ... })` — polígonos e linhas do `L.geoJSON` passam a
   ser desenhados num canvas em vez de milhares de elementos SVG. Popups (`bindPopup`)
   continuam funcionando.
2. Debounce do `moveend`: 250 ms (constante nomeada no módulo).
3. Guarde a última requisição feita: `{ x0, y0, x1, y1, z }`. Num novo `moveend`, **só
   busque de novo** se `Math.floor(zoom)` mudou **ou** a bbox visível saiu da última bbox
   buscada. Ao buscar, peça a bbox visível **expandida em 50% de cada lado** (constante
   nomeada), pra um pan pequeno não disparar requisição.
4. `clearLayers()`/`addData()` só nas camadas cujo conteúdo mudou.
5. O controle de "precisa recarregar?" vai num módulo novo `web/static/js/mapa_recorte.js`,
   importado por `mapa_leaflet_camadas.js` (F05) — mantém os dois abaixo de 250 linhas.

**Medir:** repita o M01.

## M03 — `lotes_alterados` com cache por cidade

**Onde:** `mesclarLotesAlteradosLeaflet` (antes do F: `mapa_leaflet.js:373-390`; depois: `mapa_leaflet_camadas.js`) — `Promise.all` com um `fetch` por cidade visível, a
cada `moveend`, 0,41 s cada.

**Solução:**

1. `config.json` → `painel`: `"mapa_lotes_alterados_cache_ms": 30000` (servido pela API
   em `/api/continentes`, junto dos outros parâmetros de mapa em `web/rotas/mapa.py`).
2. No front: `Map` de `cidade_id -> { quando, estadoPorId }`; só busca de novo se passou do
   TTL. Só busca se a camada `lote` veio com features nessa resposta (zoom abaixo do
   `zoom_min` de lote não pede nada).

## M04 — camada de NPCs se locomovendo

**Problema:** Seção 1.1. Pedido explícito do dono do projeto.

**Desenho:**

- Só aparece a partir de um zoom mínimo (`painel.mapa_npcs_zoom_min`, default: o mesmo
  zoom em que os edifícios de uma cidade média acendem — leia o valor real em
  `cidade_zoom_min_por_tamanho` servido por `/api/continentes` e registre qual usou).
- O servidor devolve **no máximo** `painel.mapa_npcs_max_pontos` NPCs **dentro da bbox
  visível**.
- A posição de cada NPC é a coordenada do local onde ele está
  (`locais.coordenadas`, pixel de mundo) **mais um deslocamento determinístico** dentro de
  um raio em metros (`painel.mapa_npcs_espalhamento_m`), pra 20 pessoas numa taverna não
  virarem 1 ponto. O deslocamento é calculado **no servidor** com `zlib.crc32(npc.id)` —
  **nunca `hash()`** (ARQUITETURA §11 D2) — convertido de metros para pixel de mundo com
  `cartographer/cities/escala.py::metros_por_pixel_mundo`.
- O front consulta a cada `painel.mapa_npcs_polling_ms` e **anima** cada ponto da
  posição anterior à nova ao longo do intervalo (interpolação linear com
  `requestAnimationFrame`). É isso que devolve a sensação de "andando".

**Passo a passo:**

1. `config.json` → `painel`:
   ```json
   "_comentario_mapa_npcs": "M04 (docs/16_PLANO_PAINEL_E_IA.md): camada de NPCs do Mapa Live. Teto de pontos por requisição, raio de espalhamento dentro do local (metros reais), intervalo de polling e zoom mínimo.",
   "mapa_npcs_zoom_min": 13,
   "mapa_npcs_max_pontos": 2000,
   "mapa_npcs_espalhamento_m": 6.0,
   "mapa_npcs_polling_ms": 2000
   ```
   e sirva essas chaves em `/api/continentes`.
2. `engine/repositorios/local.py`: `listar_coordenadas() -> list` — `id, cidade_id,
   coordenadas` de todos os locais ativos.
3. `web/cache_locais.py` (novo, mesmo espírito de `web/cache_mapa.py`): mantém em memória
   do processo web `local_id -> (x, y)`, recarregado **só** quando
   `MetaChave.LOCAIS_VERSAO` mudar (mesmo contrato de `run_simulation.py::sincronizar_locais_se_mudou`).
   Função `locais_na_bbox(x0, y0, x1, y1) -> list[str]`.
4. `engine/repositorios/npc.py`: `listar_posicoes(local_ids: list, limite: int) -> list`
   — `SELECT id, nome, acao_atual, localizacao_atual_id FROM npcs WHERE saude > 0 AND
   localizacao_atual_id IN (...)`, em blocos de no máximo 900 ids por consulta (limite de
   parâmetros do SQLite), parando ao atingir `limite`.
5. `web/rotas/mapa_npcs.py` (blueprint `mapa_npcs_bp`):
   `GET /api/mapa/npcs?bbox=x0,y0,x1,y1&z=N`. Se `z < mapa_npcs_zoom_min` → `{"npcs": []}`.
   Senão: locais na bbox → posições → aplica o deslocamento → resposta
   `{"npcs": [{"id", "nome", "acao", "x", "y"}], "truncado": bool}`.
   A função do deslocamento (`deslocamento_deterministico(npc_id, raio_px) -> (dx, dy)`)
   é pura e fica em `web/serializadores.py` ou num módulo próprio — **testável**.
6. `web/static/js/camada_npcs.js` (módulo ES):
   - `L.layerGroup` com `L.circleMarker` (canvas, por causa do `preferCanvas` de M02),
     cor por `acao` (tabela de cores em `formatacao.js`; a lista de ações vem de
     `/api/habitantes/filtros`, não copiada);
   - `Map` de `id -> { marker, de: [lat,lng], para: [lat,lng] }`; a cada resposta,
     `de = posição atual`, `para = nova`; um laço `requestAnimationFrame` interpola até
     `mapa_npcs_polling_ms`; NPC que sumiu da resposta é removido; novo nasce já na posição;
   - clique abre a ficha (P03);
   - entra no `L.control.layers` como "🚶 Habitantes", **ligada** por padrão;
   - para o polling quando a aba 🗾 não estiver visível ou o zoom estiver abaixo do mínimo;
   - se `truncado`, mostra um aviso discreto "mostrando 2.000 de N — aproxime".

**Testes:**
- `tests/test_rotas_painel.py::test_deslocamento_deterministico_e_estavel` — mesmo id,
  mesmo resultado em duas chamadas; distância ≤ raio.
- `tests/test_rotas_painel.py::test_mapa_npcs_abaixo_do_zoom_minimo_devolve_vazio`.
- `tests/test_repositorio_npc.py::test_listar_posicoes_respeita_limite_e_blocos(tmp_path)`
  — 2.000 locais, 3.000 NPCs, limite 1.000.

**Teste manual (registre):** no zoom de edifícios de Quenanfield, pontos se deslocam
entre casa, trabalho e taverna com a simulação rodando.

---

# Bloco G — Geometria: quadras sobrepostas

> ⚠️ **Protocolo obrigatório da ARQUITETURA §11** (md5 antes/depois). Aqui o md5 **vai**
> mudar — de propósito, **só** nas cidades de modelo `organica`. Se mudar o md5 de uma
> cidade `radial`, `grade` ou `linear`, a mudança está vazando: reverta e refaça.

## G01 — invariante de sobreposição por área (auditoria e teste)

**Problema:** `builder/fix/audit_cidades.py` passa sem acusar nada porque **não mede
sobreposição entre polígonos** — e a primeira tentativa de medir (por cruzamento de
arestas) conta borda encostando (Armadilha 21).

**Solução:**

1. `cartographer/cities/geometria/sobreposicao.py` (módulo novo, puro, sem numpy
   obrigatório; cabeçalho MODULE/FUNÇÃO/DESCRIÇÃO):
   - `area_poligono(pontos) -> float` (fórmula do laço/shoelace, valor absoluto);
   - `recortar_convexo(sujeito, recorte) -> list` — Sutherland–Hodgman: para cada aresta
     do polígono de recorte (orientado anti-horário), mantém os pontos do sujeito do lado
     de dentro e insere a interseção quando a aresta do sujeito atravessa a borda;
   - `area_de_intersecao(a, b) -> float` = `area_poligono(recortar_convexo(a, b))`
     (0 se o recorte tiver menos de 3 pontos);
   - `pares_sobrepostos(poligonos, area_minima_m2) -> list[(i, j, area)]` — pré-filtro por
     bbox (descarta pares cujas caixas não se tocam) antes de recortar.
   - ⚠️ Documente na docstring: Sutherland–Hodgman é exato quando o polígono de recorte é
     **convexo**. Quadras, lotes e edifícios deste projeto são quadriláteros
     (contrato de `Quadra.vertices`: exatamente 4) e o gerador já rejeita quad côncavo
     (`test_encolher_quad_rejeita_quad_concavo`), então vale; se um dia houver polígono
     côncavo, esta função subestima a área.
   - As coordenadas das features estão em pixel de mundo, `[lng, lat] = [x, -y]`;
     converta para metros com `metros_por_pixel_mundo(config)` **antes** de calcular área
     (senão os números saem em px², invisíveis).
2. `config.json` → `cartografia`:
   ```json
   "_comentario_sobreposicao": "G01 (docs/16_PLANO_PAINEL_E_IA.md): área mínima (m²) para uma interseção entre dois polígonos contar como sobreposição — abaixo disso é ruído numérico de borda encostada (Armadilha 21).",
   "cidade_geo_sobreposicao_area_minima_m2": 1.0,
   "cidade_geo_sobreposicao_edificio_tolerada_m2": 5.0
   ```
3. `builder/fix/audit_cidades.py`: três colunas novas — `quad_sobrep`, `edif_sobrep`,
   `lote_sobrep` (contagem de pares acima de `area_minima`). Invariante que faz o script
   sair com código 1: `quad_sobrep > 0` **ou** pares de edifício com área acima de
   `edificio_tolerada_m2`. **Lote não é invariante** (G03) — só coluna informativa.
4. `tests/test_cidades.py`:
   - `test_area_de_intersecao_de_quadrados_conhecidos` — dois quadrados 10×10 m
     deslocados 5 m num eixo → 50 m²; encostados → 0;
   - `@pytest.mark.parametrize("nome_modelo", ["radial", "organica"])`
     `test_quadras_e_edificios_nao_se_sobrepoem(nome_modelo)` — gera com o helper
     `_gerar` existente (`tests/test_cidades.py:54`) **mas com `tamanho="grande"`** (a
     cidade de teste padrão é `"medio"`; crie `_gerar_grande` ao lado, não mude o padrão)
     e afirma: 0 pares de quadra acima de 1 m² e 0 pares de edifício acima de 5 m².
   - Rode: **`organica` deve falhar** (o experimento da Seção 2.5 deu 2 quadras em
     Quenanfield). Se não falhar com "Aurora Vales" (o nome de teste), parametrize também o
     nome da cidade com `"Quenanfield"` e `"Belmir"` — estes dois falharam no experimento.
     Registre qual nome usou.

**Medir:** rode `venv/bin/python builder/fix/audit_cidades.py` e confira `echo $?`.
Esperado **antes** de G02: Quenanfield com `quad_sobrep = 2`.

## G02 — aresta `sem_via` recua como a via que deixou de existir

**Problema e prova:** Seção 2.5.

**Onde:**
- `cartographer/cities/modelos/base.py:71-83` (`distancia_faixa_dominio`, usada por
  `expansao.py`);
- `cartographer/cities/geometria/gerador.py:144-150`
  (`GeradorCidade._distancia_faixa_dominio`, **gêmeo** do de cima — armadilha 18 do doc 4:
  "a correção foi aplicada num arquivo e não no gêmeo").

Só `cartographer/cities/modelos/organica.py:98,118` produz `"sem_via"` (verificado com
`grep`), então a mudança só alcança cidades orgânicas.

**Solução:**

1. `config.json` → `cartografia`:
   ```json
   "_comentario_sem_via_recuo": "G02 (docs/16_PLANO_PAINEL_E_IA.md): uma aresta 'sem_via' (anel orgânico aberto, L02) recua do quarteirão como se a via desta classe ainda existisse. Com recuo zero as duas quadras vizinhas avançavam sobre a faixa da rua removida: medido 2 quadras (95 m²) e 13 edifícios sobrepostos em Quenanfield. A frente de lote continua proibida nessa aresta — isso é decidido em geometria/lotes.py, não aqui.",
   "cidade_geo_sem_via_recuo_como_classe": "anel"
   ```
2. **Elimine o gêmeo antes de corrigir:** faça `GeradorCidade._distancia_faixa_dominio`
   delegar para `base.distancia_faixa_dominio(self.config_do_gerador, classe)`. Leia o
   `__init__` de `GeradorCidade` (`gerador.py:46-80`) pra ver qual atributo guarda a
   config e como `via_largura_por_classe`/`recuo_rua` são lidos; se o valor calculado pelas
   duas funções for **idêntico** hoje para toda classe (confira `principal`, `anel`,
   `secundaria`, `servico`, `sem_via`), a delegação não muda nada — rode o md5 **agora**,
   antes do passo 3, e confirme diff vazio. Se não for idêntico, **pare** e registre a
   diferença: a unificação vira uma tarefa própria.
3. Em `base.distancia_faixa_dominio`, troque o `return 0.0` do `sem_via` por:
   ```python
   if classe == "sem_via":
       # G02: recua como a via que deixou de existir (ver comentário no config).
       classe = cfg_get(config, "cidade_geo_sem_via_recuo_como_classe")
   ```
   seguindo para a conta normal. Atualize a docstring (a frase "sem_via tem distância
   zero" virou mentira — ARQUITETURA §12, "comentário que virou mentira").
4. **Não mexa** em `geometria/lotes.py:147-149,164-165,186-188`: é o que mantém "nenhum
   lote com frente onde não há rua".
5. Rode `tests/test_cidades.py` — o teste do G01 deve passar; os existentes
   (`test_todo_lote_tem_frente`, `test_rua_coincide_com_aresta_de_quadra`,
   `test_lotes_por_quadra_em_faixa`, `test_determinismo`) devem continuar passando. Se
   `test_lotes_por_quadra_em_faixa` quebrar para `organica` (a quadra encolheu), registre
   os números e **pare pra decidir** — não afrouxe a faixa do teste por conta própria.
6. Protocolo de md5 (ARQUITETURA §11):
   ```bash
   md5sum database/cidades/*.geojson > /tmp/antes.md5
   venv/bin/python cartographer/cities/generate_city_geometry.py
   md5sum database/cidades/*.geojson | diff - /tmp/antes.md5
   ```
   Esperado: mudam **só** os arquivos cujo `properties.modelo == "organica"` (hoje:
   `quenanfield`, `cidade_das_flores`, `toranvale`). Confira o modelo de cada arquivo que
   mudou com
   `python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['properties']['modelo'])" database/cidades/<arquivo>`.
7. `builder/fix/audit_cidades.py` sai com código 0 nas colunas novas.
8. **Não repovoe ainda.** A geometria mudou e o banco não bate mais com ela, mas E01
   também muda a cartografia. Faça E01 em seguida e repovoe **uma vez só**, no último
   passo de E01.

**Resultado esperado** (do experimento, Seção 2.5): quadras sobrepostas 0; edifícios
sobrepostos 0–1 com área ≤ 3,2 m²; lotes ≤ ~23 m² residuais.

## G03 — sobreposição residual entre lotes (registrar, não corrigir)

Depois de G02 o experimento ainda mostra **18–23 pares de lote** com até 23,5 m² nas
cidades orgânicas grandes (3 em Belmir). Não gera edifício sobreposto (G01 prova), então
**não** é invariante agora.

**Tarefa:** registre no Registro a coluna `lote_sobrep` do `audit_cidades.py` para cada
cidade depois de G02. **Não tente corrigir** neste documento.

## G04 — o popup do edifício diz em qual quadra ele está

**Problema:** "Residência Bairro Médio 42" existe em 5 quadras de Quenanfield (Seção 2.5).

**Solução (só frontend, não muda o mundo; depois do Bloco F):** em `criarCamadasVetoriaisLeaflet`
(`mapa_leaflet_camadas.js`; antes do F era `mapa_leaflet.js:262-267`)
(`onEachFeature` de `edificio`), acrescente `props.quarteirao_id` ao popup:
`Residência Bairro Médio 42 · Bairro Médio · quadra 2_4`. Texto passa por `escaparHtml`.

---

# Bloco E — Mais empregos

> Decisão ❼: aumentar **um pouco** os empregos. Não é a solução da economia — é um ajuste
> de capacidade enquanto as opções de empreendedorismo não existem.

## E01 — o comércio de bairro emprega uma pessoa a mais

**Problema:** na run real, **5.205 vagas** (soma de `capacidade` dos locais ativos das
`urbanismo.categorias_empregadoras`) para **19.209 adultos** vivos = **27,1%**. Todas as
vagas estão ocupadas; os outros 73% não têm onde trabalhar.

De onde vêm as vagas (run real, por `tipo_local`):

| tipo_local | categoria | locais | capacidade | vagas |
|---|---|---|---|---|
| Quitanda | mercado | 311 | 3 | 933 |
| Taverna de Bairro | taverna | 220 | 4 | 880 |
| Padaria de Bairro | forja | 279 | 3 | 837 |
| Oficina | forja | 262 | 3 | 786 |
| Capela de Bairro | publico | 107 | 2 | 214 |
| **5 tipos de comércio de bairro** | | **1.179** | | **3.650 (70%)** |
| todos os edifícios notáveis juntos (Taverna, Mercado, Templo, ...) | | | | 1.555 |

**Onde:** `config.json` → `cartografia.cidade_geo_catalogo_comercio_bairro` (as
capacidades são gravadas nas features de edifício na geração, e o povoamento as importa em
`builder/populador.py:109`).

**Solução:** **+1 de capacidade** em cada um dos 5 tipos acima. Com a contagem de locais
de hoje, isso dá **+1.179 vagas → 6.384 = 33,2% dos adultos**. `Poço de Bairro`
(categoria `generic`, não emprega) e os edifícios notáveis **não mudam**.

| tipo_local | capacidade hoje | capacidade nova |
|---|---|---|
| Quitanda | 3 | 4 |
| Taverna de Bairro | 4 | 5 |
| Padaria de Bairro | 3 | 4 |
| Oficina | 3 | 4 |
| Capela de Bairro | 2 | 3 |

**Passo a passo:**

1. **Medir antes**, no mundo atual: rode a consulta do Anexo A.6 e registre vagas,
   adultos e a razão.
2. Edite as 5 capacidades e acrescente, no bloco `cartografia`:
   `"_comentario_e01": "E01 (docs/16_PLANO_PAINEL_E_IA.md, decisão ❼): +1 de capacidade no comércio de bairro — 5.205 vagas para 19.209 adultos (27%) medidos em 2026-09-14. Ajuste de transição: a saída de verdade para o desemprego é empreendedorismo, num plano futuro."`
3. Guarde a geometria atual (já com G02): `cp -r database/cidades /tmp/cidades_antes_E01`.
4. Regenere a geometria **mantendo o manifesto**:
   `venv/bin/python cartographer/cities/generate_city_geometry.py`.
5. Prove que **só** a capacidade mudou:
   ```python
   import json, glob, os
   for novo in sorted(glob.glob("database/cidades/*.geojson")):
       antigo = os.path.join("/tmp/cidades_antes_E01", os.path.basename(novo))
       a, b = json.load(open(antigo)), json.load(open(novo))
       assert len(a["features"]) == len(b["features"]), novo
       for fa, fb in zip(a["features"], b["features"]):
           assert fa["geometry"] == fb["geometry"], novo
           pa = {k: v for k, v in fa["properties"].items() if k != "capacidade"}
           pb = {k: v for k, v in fb["properties"].items() if k != "capacidade"}
           assert pa == pb, novo
   print("só a capacidade mudou")
   ```
   Se falhar, a mudança deslocou o sorteio de edifícios: **reverta e registre** — não siga.
6. **Repovoe uma vez só** (decisão ❽), **sem** `builder/reset_world.sh`:
   ```bash
   rm -f database/openworld.db database/openworld.db-wal database/openworld.db-shm
   venv/bin/python builder/populate.py --ia-max-thread 4
   ```
   O manifesto (`database/world_manifest.json`), as features e o cache de tiles ficam — as
   cidades são as mesmas. Registre a população total resultante.
7. **Medir depois:** Anexo A.6 de novo, `venv/bin/python builder/fix/audit_mundo.py`
   (0 violações, incluindo o invariante 10 de C02) e
   `venv/bin/python builder/fix/audit_cidades.py` (código de saída 0).
8. Critério: razão vagas/adultos **entre 31% e 36%**. Abaixo de 31%, **pare e registre**:
   não aumente mais nada sem o dono do projeto (o próximo botão seria
   `um_a_cada_n_lotes`, que muda a geometria).

**Efeito colateral esperado (registre):** menos locais em superlotação, então menos
desgaste por superlotação (`InfrastructureManager.processar_desgaste`).

---

# Bloco I — IA configurável, OpenRouter e medição de custo

> Referências: ARQUITETURA §2 (IA mora em `engine/ai/`), §5 (config), §7 (injeção),
> §9 "Fallback de IA" (fallback sempre existe, loga `warning`, resposta de LLM é entrada
> não confiável). Decisões ❷ ❸ ❹ ❺ ❻.

### Visão geral do desenho

```
chamador (Mestre, bebê, DNA, ...)
   │  AIClient.query(prompt, cliente=ClienteIA.MESTRE, json_format=True)
   ▼
RoteadorIA  ── resolve a config do cliente (padrão + sobrescrita)
   │         ── percorre a cadeia [(provedor, modelo), ...]
   │              ├─ LimitadorDeTaxa do provedor permite?  não → próximo
   │              ├─ ProvedorOpenAICompativel.completar(...)
   │              │     ok → registra uso (JSONL) → devolve texto
   │              │     429 → pausa o provedor → próximo
   │              │     rede/5xx → tenta de novo (até N) → próximo
   │              │     401/400 → erro de configuração, loga ERROR → próximo
   │              └─ registra CADA tentativa no JSONL (sucesso ou falha)
   ▼
cadeia esgotada → levanta ErroIAIndisponivel → o chamador usa o fallback procedural
                  que JÁ existe (AIFallbacks), exatamente como hoje
```

Os chamadores **não mudam de comportamento**: continuam com `try/except` e fallback. O
que muda é **de onde** vêm URL, modelo, timeout e chave, e o que fica registrado.

## I01 — vocabulário de clientes e o bloco `ia` no config

**Passo a passo:**

1. `engine/ai/clientes.py` (novo):
   ```python
   class ClienteIA(Enum):
       """I01 (docs/16_PLANO_PAINEL_E_IA.md): quem está chamando a IA. O valor é a chave
       do cliente em config.json["ia"]["clientes"] e o campo `cliente` do registro de
       uso (logs/ia_uso.jsonl)."""
       MESTRE                   = "mestre"
       NOME_BEBE                = "nome_bebe"
       DNA_NPC                  = "dna_npc"
       BACKGROUND_NPC           = "background_npc"      # sem chamador hoje — mantido de propósito (decisão ⓫)
       LOCAIS_CIDADE            = "locais_cidade"       # sem chamador hoje — mantido de propósito (decisão ⓫)
       EVENTO_GLOBAL            = "evento_global"
       PLANEJAMENTO_CONTINENTES = "planejamento_continentes"
       FUNDACAO_CIDADES         = "fundacao_cidades"
   ```
2. `config.json` — bloco novo **no topo** (`"ia"`), exatamente com esta estrutura
   (ajuste só os `_comentario`):
   ```json
   "ia": {
     "_comentario": "Bloco I (docs/16_PLANO_PAINEL_E_IA.md). provedores: como falar com cada serviço (todos no formato OpenAI /chat/completions — o Ollama também aceita, em /v1). padrao: cadeia de fallback e limites usados por todo cliente. clientes: sobrescritas por cliente (chave = ClienteIA.value); objeto vazio = herda tudo do padrão. A CHAVE de API nunca fica aqui: chave_api_env é o NOME da variável de ambiente.",
     "provedores": {
       "ollama_local": {
         "url_base": "http://localhost:11434/v1",
         "chave_api_env": "",
         "requisicoes_por_minuto": 0,
         "requisicoes_por_dia": 0,
         "pausa_apos_limite_s": 0,
         "cabecalhos_extras": {}
       },
       "openrouter": {
         "_comentario": "Limites do plano gratuito (modelos ':free'), consultados em 2026-09-14 em openrouter.ai/docs/api-reference/limits: 20 req/min; 50 req/dia com menos de 10 créditos comprados, 1000 req/dia com 10 ou mais. 0 = sem limite local.",
         "url_base": "https://openrouter.ai/api/v1",
         "chave_api_env": "OPENROUTER_API_KEY",
         "requisicoes_por_minuto": 20,
         "requisicoes_por_dia": 50,
         "pausa_apos_limite_s": 60,
         "cabecalhos_extras": {"X-Title": "OpenWorld"}
       }
     },
     "padrao": {
       "cadeia": [
         {"provedor": "openrouter", "modelo": "google/gemma-4-31b-it:free"},
         {"provedor": "ollama_local", "modelo": "qwen2.5-coder:7b"}
       ],
       "timeout_s": 60,
       "tentativas_por_provedor": 2,
       "backoff_inicial_s": 1.0
     },
     "clientes": {
       "_comentario": "nome_bebe e dna_npc começam no Ollama local: são volume (um nome por nascimento, um DNA por NPC da cidade em foco) e esgotariam os 50 req/dia gratuitos em minutos. mestre e evento_global têm timeout maior porque o contexto deles tem ~28 mil tokens: medido 50-83 s (Mestre) e 187-262 s (evento) no Ollama local com contexto de 32 mil — com o padrão de 60 s, o fallback para o Ollama falharia sempre (Seção 2.7).",
       "mestre": {"timeout_s": 180},
       "nome_bebe": {"cadeia": [{"provedor": "ollama_local", "modelo": "qwen2.5-coder:7b"}], "timeout_s": 8, "tentativas_por_provedor": 1},
       "dna_npc": {"cadeia": [{"provedor": "ollama_local", "modelo": "qwen2.5-coder:7b"}], "timeout_s": 120},
       "background_npc": {"cadeia": [{"provedor": "ollama_local", "modelo": "qwen2.5-coder:7b"}], "timeout_s": 8},
       "locais_cidade": {},
       "evento_global": {"timeout_s": 300},
       "planejamento_continentes": {"timeout_s": 120},
       "fundacao_cidades": {"timeout_s": 120}
     },
     "coleta_uso": {
       "ativa": true,
       "arquivo": "logs/ia_uso.jsonl",
       "gravar_texto": true
     },
     "estimativa_custo": {
       "_comentario": "Preço de referência (decisão ❸), consultado em 2026-09-14 em openrouter.ai/api/v1/models. Mude aqui quando o preço mudar — o script de estimativa lê daqui, ou ao vivo com --precos-ao-vivo.",
       "modelo_referencia": "deepseek/deepseek-v4-flash",
       "preco_entrada_usd_por_milhao_tokens": 0.08246,
       "preco_saida_usd_por_milhao_tokens": 0.16492
     }
   }
   ```
3. **Regra de resolução** (escreva na docstring de I04): a config efetiva de um cliente é
   `{**padrao, **clientes[cliente.value]}` — sobrescrita **rasa**, por chave. `cadeia`
   sobrescrita substitui a lista inteira (não concatena).
4. **Validação na construção** (falhar alto, ARQUITETURA P5): todo membro de `ClienteIA`
   tem entrada em `clientes`; toda entrada de `cadeia` aponta pra um provedor existente;
   `timeout_s > 0`; `tentativas_por_provedor >= 1`. Violação → `ValueError` com a chave
   exata.

**Teste:** `tests/test_ia.py` (novo; docstring citando este documento; **nenhum teste
toca rede**):
- `test_cliente_sem_entrada_no_config_falha_alto`;
- `test_cliente_vazio_herda_o_padrao`;
- `test_sobrescrita_de_cadeia_substitui_a_lista`;
- `test_cadeia_com_provedor_inexistente_falha_alto`.

## I02 — o provedor compatível com OpenAI

**Onde:** `engine/ai/provedores/__init__.py` e
`engine/ai/provedores/openai_compativel.py` (novos).

**Contrato:**

```python
@dataclass
class RespostaIA:
    texto: str
    tokens_entrada: Optional[int]      # usage.prompt_tokens
    tokens_saida: Optional[int]        # usage.completion_tokens
    custo_informado_usd: Optional[float]  # usage.cost (o OpenRouter manda; o Ollama não)
    latencia_s: float

@dataclass
class PedidoIA:                         # agrupa os parâmetros (limite de 5, §4)
    prompt: str
    modelo: str
    json_format: bool
    timeout_s: float

class ErroLimiteDeTaxa(Exception): ...           # HTTP 429
class ErroProvedorIndisponivel(Exception): ...   # rede, timeout, 5xx, corpo com "error"
class ErroConfiguracaoProvedor(Exception): ...   # 400/401/403/404, chave ausente

class ProvedorOpenAICompativel:
    def __init__(self, nome: str, url_base: str, chave_api: str, cabecalhos_extras: dict,
                 transporte: Callable = None): ...
    def completar(self, pedido: PedidoIA) -> RespostaIA: ...
```

**Detalhes obrigatórios:**

1. URL: `f"{url_base.rstrip('/')}/chat/completions"`.
2. Corpo:
   ```json
   {"model": "<modelo>", "messages": [{"role": "user", "content": "<prompt>"}], "stream": false}
   ```
   e, se `json_format`, `"response_format": {"type": "json_object"}`.
3. Cabeçalhos: `Content-Type: application/json`; `Authorization: Bearer <chave>` **só se
   houver chave**; mais `cabecalhos_extras`.
4. `transporte` é **injetado** (ARQUITETURA §7): uma função
   `(url, corpo_bytes, cabecalhos, timeout) -> (status_http, corpo_bytes)`. O default usa
   `urllib.request` (sem dependência nova no `requirements.txt`). É isso que permite
   testar sem rede.
5. Classificação de erro — **nomeie cada exceção** (ARQUITETURA §9):
   - `urllib.error.HTTPError` com 429 → `ErroLimiteDeTaxa`;
   - `HTTPError` 5xx, `urllib.error.URLError`, `TimeoutError`, `socket.timeout` →
     `ErroProvedorIndisponivel`;
   - `HTTPError` 400/401/403/404 → `ErroConfiguracaoProvedor` (inclua o corpo da resposta
     na mensagem — é onde o OpenRouter explica o erro);
   - ⚠️ capture `HTTPError` **antes** de `URLError` (é subclasse);
   - 200 com `"error"` no corpo, ou sem `choices`, ou `content` vazio/`None` →
     `ErroProvedorIndisponivel`.
6. `texto = choices[0]["message"]["content"].strip()`. `usage` pode faltar → campos `None`.
7. A chave **nunca** aparece em log nem em mensagem de exceção.

**Teste** (`tests/test_ia.py`, com transporte falso):
- `test_provedor_envia_response_format_so_quando_json`;
- `test_provedor_sem_chave_nao_envia_authorization`;
- `test_provedor_le_usage_e_custo`;
- `test_provedor_429_vira_erro_limite_de_taxa`;
- `test_provedor_401_vira_erro_de_configuracao_sem_vazar_chave` — afirme que a chave de
  teste não aparece em `str(excecao)`;
- `test_provedor_200_com_error_no_corpo_vira_indisponivel`.

## I03 — limitador de taxa por provedor

**Onde:** `engine/ai/limite_taxa.py` (novo).

```python
class LimitadorDeTaxa:
    """I03: janela deslizante por minuto e por dia, e pausa depois de um 429. Seguro
    entre threads (o nome de bebê roda em thread, o DNA em ThreadPool)."""
    def __init__(self, por_minuto: int, por_dia: int, pausa_apos_limite_s: float,
                 relogio: Callable[[], float] = time.monotonic): ...
    def pode_chamar(self) -> bool: ...        # não consome
    def registrar_chamada(self) -> None: ...
    def pausar_por_limite(self) -> None: ...  # chamado ao receber 429
```

- `0` em `por_minuto`/`por_dia` = sem limite.
- Janela de minuto: `deque` de instantes, descarta os com mais de 60 s.
- Janela de dia: `deque` de instantes, descarta os com mais de 86.400 s. (Aproximação
  local: o dia do OpenRouter pode virar em outro horário — **não medido**. O 429 de
  verdade é tratado pela pausa.)
- Tudo sob `threading.Lock`.
- `relogio` injetado → testável sem `sleep`.

**Teste:** `test_limitador_bloqueia_a_21a_chamada_no_mesmo_minuto`,
`test_limitador_libera_depois_de_60s` (relógio falso),
`test_limitador_pausa_apos_429`, `test_limitador_zero_e_ilimitado`.

## I04 — o roteador com cadeia de fallback

**Onde:** `engine/ai/roteador.py` (novo).

```python
class ErroIAIndisponivel(Exception):
    """Toda a cadeia do cliente falhou — o chamador usa o fallback procedural."""

class RoteadorIA:
    def __init__(self, config: dict, registrador: "RegistradorDeUsoIA",
                 fabrica_provedor: Callable = None, ambiente: Mapping = os.environ): ...
    def consultar(self, prompt: str, cliente: ClienteIA, json_format: bool) -> str: ...
```

**Comportamento:**

1. No `__init__`: valida o config (I01, passo 4); cria **um** provedor e **um**
   limitador por nome em `ia.provedores`. Chave: `ambiente.get(chave_api_env)` quando
   `chave_api_env` não é vazio. Provedor que **exige** chave e não tem → marcado
   indisponível, **um único** `WorldLogger.error` na construção
   ("[IA] provedor openrouter sem chave: defina a variável OPENROUTER_API_KEY — pulado
   em toda cadeia"), e pulado depois sem logar de novo.
2. `consultar`: resolve a config do cliente; para cada `(provedor, modelo)` da cadeia:
   - provedor indisponível ou limitador nega → registra tentativa pulada (I06) e segue;
   - até `tentativas_por_provedor` vezes: `limitador.registrar_chamada()`;
     `provedor.completar(PedidoIA(...))`;
     - sucesso → registra (I06) e **devolve o texto**;
     - `ErroLimiteDeTaxa` → `limitador.pausar_por_limite()`, registra, **próximo provedor
       imediatamente** (sem backoff);
     - `ErroProvedorIndisponivel` → registra; se ainda há tentativa, dorme
       `backoff_inicial_s * 2**(tentativa-1)`; senão próximo provedor;
     - `ErroConfiguracaoProvedor` → `WorldLogger.error` (uma vez por provedor+modelo),
       registra, próximo provedor (não repete — não vai melhorar).
   - cadeia esgotada → `WorldLogger.warning("[IA] cadeia esgotada para <cliente>")` e
     `raise ErroIAIndisponivel`.
3. `fabrica_provedor` e `ambiente` injetados → testável sem rede e sem variável de
   ambiente real.
4. ≤ 40 linhas por método: separe `_tentar_provedor`, `_resolver_cliente`,
   `_validar_config`.

**Teste** (`tests/test_ia.py`):
- `test_cadeia_cai_para_o_segundo_provedor_apos_429`;
- `test_cadeia_repete_no_mesmo_provedor_apos_erro_de_rede` (backoff com `sleep`
  injetado ou `backoff_inicial_s = 0` na config de teste);
- `test_provedor_sem_chave_e_pulado_e_loga_uma_vez`;
- `test_cadeia_esgotada_levanta_erro_ia_indisponivel`.

## I05 — `AIClient.query` vira fachada, e todo chamador passa o cliente

**Problema:** `AIClient` é estático e chamado de 8 lugares, inclusive de threads e de
scripts do `cartographer/`. Converter tudo pra injeção de instância agora é uma reescrita
de 6 módulos — fora de escopo.

**Solução (⚠️ paliativo consciente, marcar no código):** `AIClient` continua estático,
mas delega a um `RoteadorIA` de processo, no mesmo padrão que o projeto já usa em
`config.configurar_fonte`:

```python
class AIClient:
    """⚠️ Paliativo consciente (I05, docs/16_PLANO_PAINEL_E_IA.md): fachada estática sobre
    um RoteadorIA por processo, porque os 8 chamadores são estáticos e alguns rodam em
    thread. O substituto é injetar RoteadorIA nos gerenciadores (ARQUITETURA §7) quando
    eles forem convertidos em classes de instância."""
    _roteador: Optional[RoteadorIA] = None
    _trava = threading.Lock()

    @classmethod
    def configurar(cls, roteador: RoteadorIA) -> None: ...   # testes e pontos de entrada

    @classmethod
    def query(cls, prompt: str, cliente: ClienteIA, json_format: bool = False) -> str:
        """Levanta ErroIAIndisponivel quando a cadeia inteira falha."""
```

- Sem `configurar` explícito, o primeiro `query` constrói o roteador com `get_config()` e
  `RegistradorDeUsoIA` (I06), **sob a trava** (duas threads não constroem dois).
- **Apague** `OLLAMA_URL`, `MODEL_NAME` e os parâmetros `max_retries`, `timeout`,
  `model_name` de `query` — agora vêm do config.
- `read_prompt` fica como está.

**Atualize cada chamador** (troque o `timeout=` literal pelo `cliente=`; o timeout vai
pro config):

| arquivo | chamada | `cliente=` |
|---|---|---|
| `engine/ai/game_master.py` (`gerar_resposta_mestre`) | `AIClient.query(prompt, json_format=True, timeout=60.0)` | `ClienteIA.MESTRE` |
| `engine/ai/biography.py` (`gerar_nome_bebe`) | `timeout=8.0` | `ClienteIA.NOME_BEBE` |
| `engine/ai/biography.py` (`gerar_background_npc`) | `timeout=8.0` | `ClienteIA.BACKGROUND_NPC` |
| `engine/ai/generator.py` (`gerar_locais_cidade`) | `timeout=60.0` | `ClienteIA.LOCAIS_CIDADE` |
| `engine/ai/generator.py` (`gerar_dna_npc`) | `timeout=120.0` | `ClienteIA.DNA_NPC` |
| `engine/ai/storyteller.py` (`gerar_evento_global`) | `timeout=60.0` | `ClienteIA.EVENTO_GLOBAL` |
| `cartographer/ai/world_manager_ai.py` (`planejar_continentes`) | `timeout=120.0` | `ClienteIA.PLANEJAMENTO_CONTINENTES` |
| `cartographer/ai/city_manager_ai.py` (`generate_cities_for_continent`) | `timeout=120.0, model_name=model_name` | `ClienteIA.FUNDACAO_CIDADES` — e **remova o parâmetro `model_name="qwen2.5-coder:7b"`** da assinatura |

Nos chamadores:
- Os `except Exception as e:` genéricos existentes: troque por
  `except (ErroIAIndisponivel, json.JSONDecodeError, KeyError, ValueError) as e:`
  conforme o que cada um realmente pode levantar (ARQUITETURA §9), mantendo o
  `WorldLogger.warning` de fallback que já existe.
- `biography.py::gerar_background_npc` tem `import json` **dentro** da função (§15 #7) —
  mova para o topo.
- Mensagens de fallback que citam "Ollama" (`game_master.py`, `biography.py`,
  `world_manager_ai.py`) passam a dizer "serviço de IA".

**Verificação:** `grep -rn "OLLAMA_URL\|MODEL_NAME\|model_name=\|timeout=" engine/ai cartographer/ai`
não encontra mais chamada a `AIClient.query` com esses parâmetros.

**Teste:** `test_aiclient_query_delega_ao_roteador_configurado` — `AIClient.configurar`
com um roteador falso; afirme que recebeu o `cliente` certo. Restaure
`AIClient._roteador = None` no fim.

## I06 — coleta de uso em JSONL

**Onde:** `engine/ai/coleta_uso.py` (novo) e `engine/caminhos.py` (novo — a ARQUITETURA
§2 já cita esse módulo, mas ele não existe).

1. `engine/caminhos.py` (infraestrutura, cabeçalho MODULE):
   ```python
   RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

   def na_raiz(caminho_relativo: str) -> str:
       """Resolve um caminho do config (relativo à raiz do projeto) — ARQUITETURA §15
       #24: nunca montar caminho à mão em cada módulo."""
   ```
   Não migre os outros módulos pra ele agora; só o código novo usa.
2. `RegistradorDeUsoIA(arquivo: str, gravar_texto: bool, ativo: bool)`:
   - `registrar(registro: RegistroUsoIA) -> None` — uma linha JSON por chamada,
     `json.dumps(..., ensure_ascii=False)`, `open(..., "a", encoding="utf-8")`, **sob
     `threading.Lock`**; cria o diretório se faltar.
   - `OSError` ao gravar → um único `WorldLogger.warning` e segue (a coleta nunca derruba
     a IA; comentário explicando o silêncio, §9).
3. `RegistroUsoIA` (dataclass) — **campos exatos** (são o contrato do script de I07):

   | campo | tipo | observação |
   |---|---|---|
   | `ts` | str | `datetime.now(timezone.utc).isoformat()` — tempo **real** |
   | `cliente` | str | `ClienteIA.value` |
   | `provedor` | str | nome em `ia.provedores` |
   | `modelo` | str | |
   | `tentativa` | int | 1, 2, ... dentro do provedor |
   | `resultado` | str | enum `ResultadoChamadaIA`: `"sucesso"`, `"limite_taxa"`, `"indisponivel"`, `"erro_configuracao"`, `"pulado_limitador"`, `"pulado_sem_chave"` |
   | `latencia_s` | float \| null | null quando pulado |
   | `tokens_entrada` | int \| null | do provedor |
   | `tokens_saida` | int \| null | do provedor |
   | `tokens_estimados` | bool | `true` quando o provedor não mandou `usage` e os números vieram de `len(texto) / 4` |
   | `custo_informado_usd` | float \| null | `usage.cost` do OpenRouter |
   | `json_format` | bool | |
   | `prompt` | str \| null | null se `gravar_texto` for false |
   | `resposta` | str \| null | idem; null se falhou |
   | `erro` | str \| null | mensagem curta, **sem a chave** |

4. O `RoteadorIA` (I04) registra **toda** tentativa, inclusive as puladas.
5. `logs/` já está no `.gitignore` — o arquivo não vai pro git. Confirme.

⚠️ Com `gravar_texto = true`, o arquivo cresce com o texto do contexto do Mestre (até
200 NPCs, `mestre.limite_npcs_contexto`). **Não medido** quanto por chamada — registre o
tamanho médio de linha na Parada 3.

**Teste:** `test_registrador_grava_uma_linha_json_por_chamada(tmp_path)`,
`test_registrador_sem_texto_nao_grava_prompt(tmp_path)`,
`test_registrador_e_seguro_entre_threads(tmp_path)` (10 threads × 50 registros → 500
linhas, todas JSON válido).

## I07 — script de estimativa de custo

**Onde:** `builder/fix/estimar_custo_ia.py` (novo; cabeçalho `SCRIPT/OBJETIVO/MOMENTO DE
USO/USO`, com o aviso "FERRAMENTA MANUAL DE DIAGNÓSTICO" igual aos outros de
`builder/fix/`).

**USO:**
```bash
venv/bin/python builder/fix/estimar_custo_ia.py \
    [--arquivo logs/ia_uso.jsonl] [--desde 2026-09-14T00:00:00] \
    [--cliente mestre] [--precos-ao-vivo]
```

**O que faz:**

1. Lê o JSONL; considera só `resultado == "sucesso"` pra tokens (as falhas aparecem numa
   contagem à parte).
2. Preço: de `ia.estimativa_custo` no config; com `--precos-ao-vivo`, faz `GET
   https://openrouter.ai/api/v1/models`, acha o `id == modelo_referencia` e usa
   `pricing.prompt`/`pricing.completion` (USD **por token** — multiplique por 1.000.000
   pra comparar com o config). Falha de rede → avisa e usa o config.
3. Imprime uma tabela por **cliente** e total:
   `chamadas ok | falhas | tokens entrada (soma, média) | tokens saída (soma, média) |
   % estimados | custo estimado USD | custo por 1.000 chamadas`.
4. Imprime também a janela de tempo real coberta (primeiro e último `ts`) e a
   **projeção por dia real** = custo total × 86.400 / duração da janela em segundos.
5. Se houver linhas com `custo_informado_usd`, mostra a soma real ao lado (serve pra
   calibrar a estimativa).
6. Sai com código 0; arquivo inexistente → mensagem clara e código 1.

**Aviso obrigatório impresso no fim** (e na docstring):

> Tokens contados pelo tokenizer do modelo que **respondeu** (Gemma/Qwen), não pelo do
> DeepSeek. Tokenizers diferentes contam o mesmo texto com diferença típica de 10–20%
> (**não medido neste projeto**). Trate a estimativa como ordem de grandeza. As
> respostas do DeepSeek também podem ser mais longas ou mais curtas que as do modelo
> medido.

**Teste:** `tests/test_ia.py::test_estimativa_de_custo_com_jsonl_conhecido(tmp_path)` —
JSONL com 2 sucessos (1.000.000 in / 0 out e 0 in / 1.000.000 out) e 1 falha; com os
preços do config, o total é exatamente `0.08246 + 0.16492`. A função de cálculo é pura e
importável; o `main()` só faz I/O.

## I08 — os chamadores que rodam em thread

**Onde:** `engine/mechanics/reproduction.py::_iniciar_batizado_assincrono` e
`builder/populador.py::_gerar_dnas_em_paralelo`.

1. Confirme que ambos capturam `ErroIAIndisponivel` (via o `except` dos clientes
   especializados, I05) e caem no fallback.
2. `reproduction.py`: a thread de batizado faz `for n in mundo.npcs` (varre a população
   inteira pra achar o bebê pelo id) **fora da thread principal**, enquanto o tick muta a
   lista. Não é escopo corrigir a varredura aqui, mas **registre** no Registro que isso é
   uma corrida de dados conhecida (Armadilha 20 de novo, entre threads).
3. `populador.py`: com `ia_max_thread = 4` e `dna_npc` apontando pro Ollama local (I01), o
   limitador do Ollama é 0 (ilimitado) — comportamento idêntico ao de hoje. Se alguém
   apontar `dna_npc` pro OpenRouter, o limitador segura em 20/min e o resto cai no
   fallback: **isso é o esperado**, não bug.

## I10 — `engine/ai/utils.py` ganha um nome que diz o assunto

**Problema:** `utils.py` é nome proibido pela ARQUITETURA P1 (§3) — convida qualquer coisa
a entrar. O arquivo faz uma coisa só: limpar e interpretar a resposta de texto do LLM.

**Passo a passo:**

1. `git mv engine/ai/utils.py engine/ai/respostas_llm.py`.
2. Classe `AIUtils` → `RespostaLLM`. Os dois métodos mantêm o nome
   (`clean_json_response`, `parse_json_safely`) — renomeá-los não é o objetivo e aumentaria
   o diff.
3. Atualize os 6 imports e os 7 usos:
   `engine/ai/__init__.py` (import e `__all__`), `engine/ai/storyteller.py`,
   `engine/ai/generator.py`, `engine/ai/game_master.py`,
   `cartographer/ai/world_manager_ai.py`, `cartographer/ai/city_manager_ai.py`.
   Confira com `grep -rn "AIUtils\|ai.utils\|from .utils" --include="*.py" engine cartographer builder web` → 0.
4. Em `parse_json_safely`, `except Exception as e:` → `except json.JSONDecodeError as e:`
   (ARQUITETURA §9).
5. Atualize o comentário de `world_manager_ai.py:90` ("via AIUtils global").

**Teste:** `tests/test_ia.py::test_resposta_llm_extrai_json_de_bloco_markdown` —
`'```json\n{"a": 1}\n```'` vira `{"a": 1}`; texto sem JSON vira `None`.

## I11 — contexto truncado no Ollama, e o contexto do Mestre em JSON compacto

**Problema:** Seção 2.7 e Armadilha 26. O Ollama local roda com a janela de contexto
padrão (4.096 tokens), embora o `qwen2.5-coder:7b` aceite 32.768 (`/api/show` →
`qwen2.context_length`). O prompt do Mestre e o do evento global passam disso e são
**cortados sem erro**. Hoje o Mestre responde sem ver boa parte do mundo.

**Passo a passo:**

1. **Configuração do servidor (ação do dono do projeto — mexe em configuração do
   sistema; o modelo que executa não faz):** o Ollama roda como serviço systemd com
   `OLLAMA_HOST=0.0.0.0:11434`. Acrescentar `OLLAMA_CONTEXT_LENGTH=32768`:
   `sudo systemctl edit ollama` → em `[Service]`, `Environment="OLLAMA_CONTEXT_LENGTH=32768"`
   → `sudo systemctl restart ollama`. Registre no Registro quando foi feito. Mais contexto
   usa mais memória de GPU/RAM: registre se o Ollama passou a rodar em CPU.
2. `config.json` → `ia.provedores.<nome>`: chave nova `"contexto_tokens_servidor"`
   (`ollama_local`: `4096` até o passo 1 ser feito, depois `32768`; `openrouter`: `0` = não
   verificar). Comentário citando I11.
3. `RoteadorIA` (I04): ao registrar uma chamada com sucesso, se
   `contexto_tokens_servidor > 0` e `tokens_entrada >= contexto_tokens_servidor`, grave
   `resultado = "sucesso_truncado"` (novo membro de `ResultadoChamadaIA`, I06) e dê **um**
   `WorldLogger.warning` por cliente:
   `"[IA] prompt de <cliente> atingiu o contexto do servidor <provedor> (<n> tokens) — provável truncamento"`.
4. `engine/ai/game_master.py` e `engine/ai/storyteller.py`: o contexto vai para o prompt
   com `json.dumps(contexto, ensure_ascii=False, separators=(",", ":"))` em vez de
   `indent=2`. É o mesmo conteúdo, sem espaço de indentação. Economia medida: **~5%** da
   entrada (Mestre 27.748 → 26.278; evento 29.089 → 27.619, Seção 2.7) — pequena, mas de
   graça. Não espere mais que isso daqui.
5. O estimador (I07) conta `sucesso_truncado` como sucesso para tokens, mas mostra quantas
   houve e avisa que os tokens desses registros são **o teto, não o real**.

**Teste:** `tests/test_ia.py::test_roteador_marca_sucesso_truncado_quando_bate_no_contexto`
(provedor falso devolvendo `prompt_tokens = 4096`, config com
`contexto_tokens_servidor = 4096`).

## I09 — validação manual (Parada 3)

Pré-requisito: uma chave do OpenRouter numa variável de ambiente **só nesta sessão de
terminal**: `export OPENROUTER_API_KEY=...` (nunca num arquivo do projeto).

| # | situação | como provocar | linha esperada em `logs/ia_uso.jsonl` |
|---|---|---|---|
| 1 | caminho feliz | Painel → aba Mestre → mande "descreva a cidade" | `cliente: "mestre"`, `provedor: "openrouter"`, `modelo: "google/gemma-4-31b-it:free"`, `resultado: "sucesso"`, `tokens_entrada` e `tokens_saida` preenchidos, `tokens_estimados: false` |
| 2 | OpenRouter fora | reinicie o dashboard **sem** a variável de ambiente e mande de novo | uma linha `pulado_sem_chave` (openrouter) + uma `sucesso` (ollama_local); **um** `ERROR` no log dizendo pra definir a variável |
| 3 | tudo fora | sem a variável **e** com o Ollama parado (`systemctl stop ollama` ou equivalente — pergunte ao dono do projeto antes) | `pulado_sem_chave` + `indisponivel` (×2 tentativas) e a narração de fallback do Mestre na tela |

Depois: rode `builder/fix/estimar_custo_ia.py` e cole a saída no Registro.

---

# Bloco T — Validação final

## T01 — suíte

`venv/bin/python -m pytest tests/ -q` — registre o total (esperado: 176 + os testes
novos deste documento, todos passando).

## T02 — run de validação

1. Mundo repovoado (E01, último passo).
2. `run_simulation.py` + `run_dashboard.py`, painel aberto alternando entre Estatísticas,
   Habitantes e Mapa Live (com a camada de NPCs), por **30 min reais** na velocidade
   máxima.
3. Registre: dias simulados alcançados; velocidade efetiva média; ms/tick p95; tamanho
   final de `world.log` e do `-wal`; nenhum `Traceback` no terminal da simulação;
   `/api/estado` < 5 KB; tempo de troca de página em Habitantes; o que as Estatísticas
   mostram de desemprego e mortes por dia (é o insumo da decisão de economia pendente).

---

## Decisões pendentes para o dono do projeto

> As decisões da segunda rodada (❾–⓭) já foram incorporadas às tarefas. O que continua
> em aberto:

1. **Economia além do E01.** Mesmo com vagas para ~33% dos adultos, a maioria continua
   sem renda. Na run medida: 804 mortes por inanição em 3,5 dias (de 1.479 óbitos),
   inclusive de adolescentes de 14 anos; 6.921 NPCs com saldo ≤ 0. Próximo plano:
   **empreendedorismo** (NPC abrir o próprio negócio). Sopão, renda de desempregado e
   tamanho das famílias continuam sem decisão. Continuação da pendência 1 do
   `15_PLANO_MUNDO_CRIVEL.md`.
2. **Teto de velocidade.** Aceito por enquanto (❶): ~700–1500×, então 200 dias simulados
   levam de 3 a 7 horas reais. Se isso travar a validação de sustentabilidade do
   `15_PLANO_MUNDO_CRIVEL.md` (T02, `--ate-renovacao`), o modo grosso volta à mesa.
3. **Cota do OpenRouter.** Com US$ 5 em créditos (menos de 10), o teto dos modelos `:free` é
   50 requisições por dia. Comprar mais US$ 5 (chegando a 10) libera 1.000/dia — só vale se
   o Mestre passar a usar mais do que isso. Custo pago de referência na Seção 2.7.
4. **Configurar o contexto do Ollama** (I11, passo 1): é configuração do sistema, fica com
   você.
5. **Corrida de dados no batizado** (I08): a thread de nome de bebê percorre `mundo.npcs`
   enquanto o tick altera a lista. Não corrigida aqui.
6. **Sobreposição residual entre lotes** (G03): pequena, registrada, sem correção.

## Registro de execução

> Preencha **durante** a execução, não no fim. Uma linha por tarefa, com o número
> medido — não "feito", e sim "392 ms → 61 ms".
>
> ⚠️ Onde a implementação divergir do texto deste plano, **escreva a divergência e o
> motivo**.

| tarefa | data | resultado / número medido | divergências |
|---|---|---|---|
| C01 | 2026-09-14 | Teste reproduz o crash (`RuntimeError`) antes da correção; `list(...)` no laço de `processar_interacoes`. Sonda de 1.440 ticks (1 dia simulado) na cópia real do banco (~28.700 NPCs): 0 `RuntimeError`. | — |
| C02 | 2026-09-14 | Teste reproduz `cidade_id is None` no bebê antes da correção. Invariante 10 acrescentado a `audit_mundo.py`. | Não foi escrita migração pros bebês já gravados (decisão ❽: mundo repovoado no fim de E01). |
| C03 | 2026-09-14 | `engine/identificadores.py` novo; 13 pontos trocados por `novo_id(...)`. Teste reproduz a colisão (2 bebês viram 1 no banco) com relógio/sorteio congelados antes da correção. `grep` de `int(time.time())`/`datetime.now().timestamp())` fora de `builder/fix/`: 0 ocorrências. | — |
| O01 | 2026-09-14 | Níveis vêm de `observabilidade.log_arquivo_nivel`/`log_console_nivel` (`NivelLog`, falha alto em valor inválido). `is_npc_logging_enabled` parou de abrir `config.json` a cada 5s. Cabeçalho de tick virou `debug`; print de velocidade por tick removido; alimentação/deslocamento amostrados. | Tamanho de `world.log` em 10 min medido na Parada 1 (abaixo). |
| O02 | 2026-09-14 | `ContadorMundo` + `EstadoDoMundo.contar()`. Inanição, refeição parcial, sem-dinheiro-sem-sopão, óbito e casamento contados em vez de logados por NPC. | — |
| O03 | 2026-09-14 | `ColetorDeEstatisticas` grava `MetaChave.ESTATISTICAS` a cada 60 ticks; console resume a cada 10s reais. Ponta a ponta validado numa cópia do banco real (65 ticks): JSON com `por_cidade`/`total`/`hoje`/`desempenho` gravado e lido de volta corretamente. | `desempenho` ficou sem `ms_por_tick`/`velocidade_efetiva` até D03 completar (entregues no mesmo dia). |
| O04 | 2026-09-14 | `journal_size_limit` + `checkpoint_wal()` (`PRAGMA wal_checkpoint(TRUNCATE)`). Tamanho do `-wal` medido na Parada 1 (abaixo). | — |
| O05 | 2026-09-14 | `saldo_residual_pc = 0.01`. Teste com saldo `1e-13` PC reproduz o NPC preso em refeição parcial antes da correção; depois, cai no ramo do sopão e o saldo zera. | — |
| D01 | 2026-09-14 | Teste com 50 casas reproduz 50 recálculos de dependentes numa única morte antes da correção; depois, ≤ 2. Medido depois (cópia do banco real, ~28.700 NPCs): 61,4 ms/tick médio (p50 54,0 / p95 66,2 / máx 905,7), sonda de 120 ticks. | — |
| D02 | 2026-09-14 | `mundo.filhos_por_genitor` (índice mantido). Teste com `list` que levanta em `__iter__` prova que `processar_heranca` não varre `mundo.npcs`. Corrigido de passagem o mesmo padrão em `NPCMarriageManager._filhos_para_mudar`/`_ocupacao_apos_casamento`. `processar_heranca` some do topo do profile de 60 ticks (antes: 0,92s/60 ticks). | — |
| D03 | 2026-09-14 | `RitmoDoLaco` (janela de 120 ticks). Medido numa cópia do banco real (~28.600 NPCs, 65 ticks a 21.600× pedido): 890× efetivo, 67,4 ms/tick médio, 61,5 ms/tick p95. | — |
| D04 | 2026-09-14 | `idx_npcs_cidade_saude`, `idx_npcs_localizacao`. `EXPLAIN QUERY PLAN` confirma `SEARCH ... USING INDEX` nas duas consultas (filtro por cidade+saúde e por localização). Custo de escrita medido na mesma cópia, com/sem os índices: -0,4% (ruído) — mantidos os dois. | — |
| **Parada 1** | 2026-09-14 | 4.786 ticks em 600,1s reais, **0 RuntimeError**, cópia isolada do banco real (~28.700 → 24.700 NPCs — mortalidade alta é a economia pendente, decisão ❼, não um regressão de C/O/D). Velocidade efetiva (janela O03/D03, leitura final): **631×** (≥ 500× ✅); média do run inteiro (4.786 min simulados / 600,1 s) ≈ 479× — abaixo da janela por causa de rajadas de óbito que derrubam a velocidade a ~180-300× por alguns segundos. `world.log`: **+5,99 MB** em 10 min (< 20 MB ✅). WAL: checkpointado a cada 60 ticks (O04); nenhum `-wal` residual ao fim (< 128 MB ✅). | Painel fechado de verdade (nenhum `run_dashboard.py` rodando) — a única forma de rodar `run_simulation.py` sem tocar `database/openworld.db` ao vivo foi apontar `SimulationEngine` pra uma cópia isolada e reusar as funções de `run_simulation.py` (`RitmoDoLaco`, `atualizar_estatisticas`, `checkpoint_wal_se_devido`) num script equivalente ao laço real, em vez de rodar `python run_simulation.py` literalmente (ele não aceita um `--db` — sempre abre `database/openworld.db`). |
| F01 + F02 | 2026-09-14 | 3 tags viram 1 (`app.js`, módulo ES). `grep onclick\|onkeydown`: 0. `grep -cE '^(let\|var) '`: 0 em todos os 5 arquivos (dashboard.js era 7, mapa_composto.js 23, mapa_leaflet.js 14 — consolidados em `estado`, não só ≤ 3 como pedia o critério). | ⚠️ Extensão do Chrome não conectada neste ambiente — não deu pra tirar as capturas de tela nem inspecionar o console do navegador de verdade (pedido pelo cabeçalho do Bloco F). Verificação alternativa: harness Node com DOM falso importando `app.js` (grafo de módulos carrega sem lançar exceção), `node --check` nos 5 arquivos, checksum confirmando que o dashboard já em execução serve o conteúdo atual, suíte Python (194, inalterada por este bloco). Dono do projeto avisado e optou por seguir assim; recomendo uma conferência manual (abrir o painel, clicar pelas abas, checar o console) quando puder. |
| F03 | 2026-09-14 | `constantes.js` (Modo/Aba/FiltroNpc/AbaModal). `estado.activeView` passou a guardar o valor de `Aba`, não o id de DOM — `switchView`/`update()` comparam contra o enum. `setNpcFilter` decide o botão ativo por `data-filtro`, não mais `innerText` (Armadilha 19). `grep`: só resta `'map-view'` como VALOR do mapa `Aba -> id de DOM` (não é comparação de texto solto, é o próprio id do elemento). | `Modo.CONTINENTE`/`Modo.CIDADE` usam os valores em português do exemplo do plano ('continente'/'cidade'), renomeando os antigos 'continent'/'city' — estado interno, nunca observado fora do módulo, então sem risco de comportamento. `AbaModal.PERFIL` ficou `'profile'` (não `'perfil'` do exemplo do plano) pra bater com os ids reais `tab-profile-btn`/`modal-tab-profile` já existentes no HTML. |
| F04 | 2026-09-14 | 7 fallbacks (`\|\| 768`, `\|\| 15`, `\|\| 11`, `\|\| 5`, `\|\| leafletMetrosPorPixelMundo`, `\|\| leafletViaLarguraM`, `\|\| 5` em estiloRua) removidos; validação de chave obrigatória adicionada (`CHAVES_OBRIGATORIAS_CONTINENTES`, 7 chaves). `/api/continentes` real confirmado com as 7 presentes (curl). Simulado com harness Node (fetch stub faltando `metros_por_pixel_mundo`): console.error + mensagem visível em `#mapa-leaflet-container`, mapa não desenha. Achado lateral (grep "Zona Urbana"): `fetchTerrainInfo` inventava `bioma_id: 6` "Zona Urbana" pra hover em modo cidade — não existe no classificador Python (`cartographer/math/climate.py` só tem 1-5, e o próprio comentário do código já denunciava isso). Corrigido: mostra "🏰 Zona Urbana" sem fingir ser um bioma real. | Mensagem de erro mostrada em `#mapa-leaflet-container` (dentro da própria aba), não em `#status-bar` (citado no texto do plano) — `#status-bar` é sobrescrito a cada 1s pelo polling de `dashboard.js`, e uma falha de configuração do Mapa Live merecia ficar visível até ser corrigida. `CATEGORIA_EDIFICIO_COR` (9 chaves) bate exatamente com `CategoriaLocal` (verificado). `TIPO_CIDADE_EMOJI` (9 chaves) — 7 batem com a lista `_TIPOS` de `cartographer/ai/city_manager_ai.py` (não é enum, é lista solta); `capital` e `residencial` não vêm de lá. |
| F05 | 2026-09-14 | dashboard.js/mapa_composto.js/mapa_leaflet.js (1.919 linhas) viraram 19 arquivos (2.107 linhas): app, acoes, api, constantes, formatacao, navegacao, painel_npcs, ficha_npc, chat_mestre, estado_dashboard, mapa_composto{,_estado,_desenho,_interacao,_inspetor}, mapa_leaflet{,_estado,_estilos,_camadas}. Todo `fetch` (16 chamadas) consolidado em api.js. Auditoria de `innerHTML`/`bindPopup`/`bindTooltip` (~20 sites): todo texto do servidor (nome, profissão, ação, humor, mensagem de log, resumo de evento, nome de cidade/continente, tipo_local, bairro, descrição) passa por `escaparHtml` — confirmado com harness Node simulando NPC renomeado para `<b>Teste</b>` (aparece escapado). `window.updateMapEntities` removido (a contagem de NPCs da região já vem de `/api/regiao/<nome>/entities`). `10_PLANO_REFATORACAO.md` marcado como executado. `wc -l`: só mapa_composto.js acima de 250 (260-270, justificado no cabeçalho do arquivo). | Extensão do Chrome não conectada (mesma limitação de F01+F02) — sem capturas de tela nem console real; compensado com harness Node + suíte Python (194, inalterada). 2 arquivos de estado NÃO listados na tabela original do plano (`estado_dashboard.js`, `mapa_leaflet_estado.js`) — necessários pra evitar import circular entre os módulos que o plano pediu pra separar (mesmo padrão de `mapa_composto_estado.js`, que o plano já previa). `Modo.CONTINENTE`/`Modo.CIDADE` (F03) tiveram os valores internos renomeados de 'continent'/'city' — só durante o split isso ficou claro como puramente interno, sem observador externo. |
| F06 | 2026-09-14 | 114 `style="..."` (35 em index.html, 79 nos 8 módulos JS que ainda tinham — dashboard.js/mapa_composto.js/mapa_leaflet.js originais já tinham sido divididos em F05) viraram classes em `style.css`/`mapa_composto.css`. Barra de saúde/energia/fome/social: `data-percentual` no template + `elemento.style.setProperty('--percentual', ...)` depois de `grid.innerHTML =` (não `style="width:..."`), consumido por `.health-fill`/`.status-fill` via `width: var(--percentual, 0%)`; a cor por faixa é classe (`saude-baixa`/`saude-ok`, nome do próprio texto do plano). Objetos de estilo do Leaflet (`ESTILO_CAMADA_CIDADE`, `estiloRua` etc.) não tocados — são API do Leaflet, não HTML. `grep -rn 'style="' web/templates web/static/js`: 0 (restam só 2 linhas de comentário citando a string). `node --check` nos 19 arquivos: ok. Harness Node dedicado confirma `--percentual` aplicado via `setProperty` e a classe de saúde correta. Suíte Python: 194 (inalterada). Checksum confirma que o dashboard já em execução serve `style.css`/`mapa_composto.css`/`painel_npcs.js` idênticos ao disco. | Também movidas 4 atribuições `citiesDiv.style.*`/`cidBtn.style.*` de `mapa_composto.js` (propriedade JS, não pega pelo grep, mas mesmo espírito da tarefa) para `.cities-list`/`.city-btn` em `mapa_composto.css` — não contavam no "Problema" original nem na validação, mas ficar com `style=""` por atribuição de propriedade ao lado de tudo o resto em classe seria inconsistente. Não tocadas (fora do escopo literal — nenhuma tem `style="..."`, são `elemento.style.propriedade = valor`, já eram assim antes de F01): as trocas de cor de `#status-mapa`/`#terrainMetricsContainer`/`#pause-btn` feitas via JS em `mapa_composto.js`/`navegacao.js` (`.style.borderColor`, `.style.color`, `.style.display`, `.style.background`) — são estado dinâmico pré-existente, não os `style=""` que este bloco pediu para eliminar; convertê-las também é um refactor maior (várias classes de estado por elemento) sem mandato explícito do plano nem risco identificado. `mapa_composto.js` ficou com 254 linhas (era 260-270 antes de F06 remover as 4 atribuições `.style.*`), ainda acima de 250 — mesma justificativa já escrita no cabeçalho do arquivo (F05). |
| P01 | 2026-09-14 | `/api/estado` substitui `/api/update`. Teste com 500 NPCs: resposta sem `npcs`/`locs`/`locais`, < 5 KB (era proporcional a 23 MB/s com o mundo cheio). `velocidade_efetiva` vem de `MetaChave.ESTATISTICAS` (O03), `null` confirmado sem estatística nenhuma gravada. `/api/init` perdeu `locais` (18 mil, sem leitor no JS). Suíte: 196 (194 + 2 novos). Confirmado via curl no dashboard já em execução: `/api/estado` responde, `/api/update` agora 404. | `estado_polling_ms` (que P02 traz pro config) ainda não existe — `estado.js` usa 1000 ms fixo, o mesmo valor que `/api/update` já usava (não é duplicação nova: a chave de config não existia ainda quando isto foi escrito); revisitar ao implementar P02. Consumidores de NPCs (aba Habitantes, ficha) ficam sem dado novo até P02/P03/P04 — inofensivo na prática porque a grade de habitantes fica vazia e nada na UI aciona `abrir-ficha` enquanto isso. |
| P02 | 2026-09-14 | `FiltroHabitantes` + `listar_habitantes`/`contar_habitantes` (WHERE parametrizado, nunca f-string). `GET /api/habitantes` e `/api/habitantes/filtros` em `web/rotas/habitantes.py`. `SituacaoHabitante` (vivos/mortos/todos) em `engine/models.py`. `config.json` ganha o bloco `painel` (inclui `estado_polling_ms` — `estado.js` (P01) passou a lê-lo de `/api/estado` em vez de fixar 1000). Teste de injeção (`busca_nome="'; DROP TABLE npcs; --"`): 0 resultados, tabela intacta. Situação inválida -> 400 (errorhandler de `ValueError` mais específico que o `Exception` do blueprint). Confirmado via curl no dashboard real (~30 mil NPCs): paginação funciona, filtros lista as cidades reais. Suíte: 203 (196 + 7). | — |
| P03 | 2026-09-14 | `RepositorioNPC.buscar_ficha` (LEFT JOIN pra mãe/pai/cônjuge + filhos por `mae_id OR pai_id`, uma consulta só). `GET /api/habitantes/<id>` → ficha (404 se não existir); confirmado que não colide com a rota estática `/api/habitantes/filtros` (Werkzeug prioriza regra sem parâmetro — teste e curl real confirmam). `/api/npc_rels/<id>` ganha `nome` do outro NPC (JOIN novo, `listar_relacionamentos` original intocado). Idade calculada com o mesmo `RelogioMundo.idade_em_anos` que `/api/update` usava. Suíte: 207 (203 + 4 no repositório + 2 na rota, contagem líquida 4 já soma os 2 de rota). Confirmado via curl no dashboard real (~30 mil NPCs): ficha com idade calculada, rels com nome, 404 pra id inexistente. | — |
| P04 | 2026-09-14 | `painel_npcs.js`/`ficha_npc.js` reescritos contra `/api/habitantes`/`/api/habitantes/<id>` — sem polling da lista, recarrega em filtro/página/"Atualizar"/troca de aba/intervalo (só com a aba visível). `FiltroNpc` saiu de `constantes.js`; `allNpcs`/`allRels`/`npcFilter` saíram de `estado_dashboard.js`. **Teste manual** (mundo real, ~30 mil NPCs, cópia de produção via curl): página 1 em 104ms, página 500 (offset profundo) em 80ms — bem abaixo dos 300ms pedidos; busca "Thorne" filtra (2.338 de ~30 mil, 30ms); ficha de "Alistair Thorne" abre com `mae_nome`/`pai_nome` resolvidos ("Lady 22 de Greycastle Thorne"/"Sir 51 de Thorne"). `grep -rn "allNpcs\|abrirHistorico" web/`: só comentário de contexto histórico (nenhum código), `grep -n "onclick=\|style=\""`: 0. Harnesses Node novos confirmam escape de nome/ação/humor (grade) e mãe/pai/cônjuge/filhos/relação (ficha) com HTML malicioso. Suíte Python: 207 (inalterada, bloco é só frontend). | O grep do plano (`allNpcs\|abrirHistorico`) foi interpretado como "nenhum CÓDIGO restante" — comentários que citam os nomes antigos pra explicar a mudança (ex.: "abrirHistorico saiu, virou abrirFicha") continuam existindo, no mesmo estilo que o resto deste documento já usa pra registrar histórico. |
| P05 | 2026-09-15 | `GET /api/estatisticas` devolve `MetaChave.ESTATISTICAS` como está + `polling_ms`. `painel_estatisticas.js` (desempenho, hoje/ontem, tabela por cidade) — não faz polling fora da aba. Confirmado no mundo real (sem `run_simulation.py` ativo): a chave realmente não existe ainda, `{"polling_ms": 5000}` é a resposta correta pra esse caso (não um bug). Harness Node confirma escape do nome de cidade e formatação da tabela. Suíte: 209 (207 + 2). | O processo `run_dashboard.py` que vinha rodando desde o início do Bloco F caiu entre sessões (ambiente reiniciou; nada relacionado a este código) — reiniciado (`nohup python run_dashboard.py &`) só pra continuar a verificação por curl; nenhuma ação destrutiva no banco. |
| **Parada 2** | 2026-09-15 | 4.692 ticks em 600,0s reais, **0 RuntimeError, 0 erros HTTP** ("painel aberto" simulado com `app.test_client()` chamando `/api/estado` e `/api/habitantes?situacao=vivos` a cada 1s — mesmo cadência de polling do painel real — durante os 10 min inteiros, na MESMA cópia isolada do banco que o motor usava, competindo pelo mesmo pool de conexões). `/api/estado`: **484 chamadas**, tempo médio 19,67 ms / p95 23,29 ms / máx **30,94 ms** (< 50 ms ✅); tamanho médio 2.417 B / máx **2.761 B** (< 5 KB ✅). Velocidade efetiva final (janela): **617,5×** vs 631× da Parada 1 → queda de **2,1%** (≤ 15% ✅); média do run inteiro ≈ 469× vs ≈ 479× da Parada 1 → queda de 1,9%. De brinde (não exigido por esta parada, mas gratuito): `world.log` **+5,71 MB** em 10 min (consistente com os +5,99 MB da Parada 1); WAL fully checkpointado ao fim (nenhum `-wal` residual). | ⚠️ Extensão do Chrome não conectada (mesma limitação do resto do bloco) — "nenhum erro no console do navegador em nenhuma aba" não foi literalmente observado num navegador. Substituído por: 0 respostas HTTP não-200 em 484+484 chamadas às DUAS rotas que uma aba Habitantes aberta de verdade chamaria (`/api/estado` do polling da barra superior, `/api/habitantes` do polling da própria aba), rodando pelo MESMO código Python que uma requisição de rede real executaria (`app.test_client()`, sem socket TCP, mas mesmas queries SQL e mesmo pool de conexões disputado pelo motor) — e a suíte Python completa (209) e os harnesses Node (grafo de módulos, escape de HTML) já cobrem exceção/erro de JS fora do event loop de rede. Dono do projeto avisado desta limitação quando ela apareceu pela primeira vez (Bloco F) e optou por seguir assim; recomendo conferência manual (abrir o painel, aba Habitantes, deixar rodando, checar o console) quando puder. |
| M01 | 2026-09-15 | Sem Chrome real, medi só o lado do servidor via curl (dashboard real, ~30 mil NPCs, depois de P01): `/tiles/{z}/{x}/{y}.png` 2-3 ms (cache em disco já quente); `/api/mapa/features` numa bbox de cidade grande (z=11, todas as 13 camadas): 71 ms servidor, **25 KB**; a mesma consulta numa bbox maior (z=13): 68 ms servidor, **~3 MB** de payload — é o número que M02/M03 (cache/dedupe de refetch) atacam, não o tempo de servidor. `/api/cidade/1/lotes_alterados`: 3 ms. Todo tempo de SERVIDOR medido está bem abaixo de 10s/2s. | ⚠️ Não dá pra medir "tempo até o primeiro tile aparecer"/"tempo até os edifícios aparecerem"/Performance (Scripting/Rendering) sem um navegador de verdade — isso inclui decode de imagem, download dos ~3 MB de GeoJSON e o tempo do Leaflet desenhando milhares de elementos SVG, nenhum dos quais o curl mede. Não apliquei a regra "se já estiver aceitável, pule pra M04" no sentido literal (não posso confirmar o critério de verdade); segui pra M02/M03 mesmo assim porque são melhorias de baixo risco e mecanismo bem estabelecido pra este padrão exato (muitas features, `moveend` frequente) — não dependem de um número de antes/depois pra serem corretas. M04 (pedido explícito do dono do projeto) seguiu de qualquer forma. |
| M02 | 2026-09-15 | `preferCanvas:true`; `moveend` debounced em 250ms; `mapa_recorte.js` (novo, bbox expandida 50%, rebusca só se zoom `floor` mudou ou o pan saiu da área coberta) — harness confirma a regra (pan pequeno não rebusca, pan que sai da bbox e mudança de zoom rebuscam, `zoomSnap` 0.25 dentro do mesmo `floor` não rebusca). `clearLayers`/`addData` só na camada cujo GeoJSON (string) mudou. `mapa_leaflet_camadas.js` ficou com 239 linhas (dentro do limite de 250). | Sem navegador real pra medir o "antes/depois" de verdade (mesma limitação de M01) — a mudança é justificada por ser boa prática estabelecida pro padrão (muitas features vetoriais, `moveend` frequente), não por um número medido aqui. |
| M03 | 2026-09-15 | `painel.mapa_lotes_alterados_cache_ms` (30000) servido em `/api/continentes`, 8ª chave obrigatória validada por `mapa_leaflet.js` (harness F04 confirma). Cache por cidade (`Map<cidade_id, {quando, lista}>`) em `mapa_leaflet_camadas.js` — só rebusca depois do TTL. | — |
| M04 | 2026-09-15 | `web/cache_locais.py` (índice em memória, invalida por `MetaChave.LOCAIS_VERSAO`); `RepositorioNPC.listar_posicoes` (blocos de 900); `deslocamento_deterministico` (zlib.crc32, testado estável e dentro do raio); `GET /api/mapa/npcs`; `camada_npcs.js` (cria/reaproveita/remove marcador, anima com requestAnimationFrame, clique abre ficha, entra no seletor de camadas como "🚶 Habitantes" ligada por padrão). `mapa_npcs_zoom_min=13` = zoom_min de `edificio` numa cidade `medio` (lido de `cidade_zoom_min_por_tamanho` no mundo real). Confirmado via curl no mundo real (~30 mil NPCs, bbox grande, z=14): 2.000 NPCs devolvidos, `truncado:true` (o mundo tem mais que o teto); z=5 devolve vazio sem consultar o banco. Suíte: 214 (209 + 5). | Mensagem de "truncado" não cita o total real de NPCs na bbox (o texto do plano exemplifica "mostrando 2.000 de N") — a resposta de `/api/mapa/npcs` não traz esse N (só a lista limitada + o booleano), e adicioná-lo exigiria uma contagem extra no banco só pra um aviso cosmético; o aviso ficou "mostrando os habitantes mais próximos — aproxime", sem inventar um número que a API não fornece. **Teste manual pendente**: sem navegador real, não dá pra confirmar visualmente "pontos se deslocam entre casa/trabalho/taverna com a simulação rodando" — os harnesses Node e os testes de rota cobrem a lógica (posição muda entre duas respostas simuladas), mas não a experiência visual real; recomendo conferência manual quando possível. |
| G01 | 2026-09-15 | `sobreposicao.py` (shoelace + Sutherland-Hodgman + pré-filtro bbox). `audit_cidades.py`: 3 colunas novas; `quad_sobrep`/`edif_sobrep` viram invariante, `lote_sobrep` só informativo. **Medido no mundo real** (antes de G02): Quenanfield (organica) `quad_sobrep=2, edif_sobrep=8, lote_sobrep=78` — confirma a Seção 2.5. "Cidade das Flores" (organica) também tem `edif_sobrep=3`/`lote_sobrep=148` mesmo com `quad_sobrep=0` (achado adicional, fora do que a Seção 2.5 media). Nenhuma grade/linear/radial com sobreposição. Performance: 0,42s pra 4.393 lotes (camada mais pesada). Teste puro (`test_area_de_intersecao_de_quadrados_conhecidos`) passa; suíte completa 215 (214+1). | O teste de regressão "quadras/edifícios não se sobrepõem" (que falharia pra organica antes de G02) foi escrito e verificado manualmente como parte da medição desta tarefa, mas só **entra no repositório em G02** — o padrão desta sessão inteira é commitar teste+correção juntos (nunca um teste vermelho sozinho); "Aurora Vales" (cidade de teste padrão) não reproduziu o bug em nenhum tamanho — usei "Quenanfield" e "Belmir" (tamanho="grande", organica), as mesmas duas do experimento da Seção 2.5, confirmadas via script ad-hoc antes de escrever o teste formal. |
| G02 | 2026-09-15 | `base.distancia_faixa_dominio`: "sem_via" recua como `cidade_geo_sem_via_recuo_como_classe` ("anel"), não mais 0.0. Gêmeo eliminado (`GeradorCidade._distancia_faixa_dominio` delega). md5 confirmado: delegação sozinha não muda nada; a correção muda só `cidade_das_flores.geojson`/`quenanfield.geojson`/`toranvale.geojson` (as 3 `organica`). Quenanfield: `quad_sobrep` 2→0, `edif_sobrep` 8→0. Toranvale: 0/0. `test_lotes_por_quadra_em_faixa[organica]` continua passando (aviso do passo 5 do plano não se confirmou). Suíte: 219 (215+4). **Ainda não repovoado** — repovoa uma vez só no fim de E01. | "Cidade das Flores" (organica) — fora do escopo do experimento original da Seção 2.5 — tem `edif_sobrep=4` mesmo depois de G02 (áreas 5,0–10,0 m², pares (633,970)/(948,973)/(968,975)/(970,972)), não relacionado a `sem_via` (G02 já zerou isso nesta mesma cidade nos outros índices). `audit_cidades.py` continua saindo com código 1 por causa disso — G02 zerou `quad_sobrep` em TODAS as cidades (o alvo desta tarefa), mas não zerou `edif_sobrep` em "Cidade das Flores". Não investiguei a causa nem tentei corrigir (fora do escopo desta tarefa) — registrado para decisão do dono do projeto, mesmo espírito do G03 (sobreposição residual que não é o invariante que esta tarefa ataca). |
| G03 | 2026-09-15 | Coluna `lote_sobrep` (informativa, não corrigida) depois de G02, no mundo real: Cidade da Sombra (grade) 0; Cidade das Flores (organica) 148; Elorfield (linear) 0; Kelanstead (radial) 0; Kelverstead (radial) 0; Quenanfield (organica) 18; Toranvale (organica) 3; Tordordor (radial) 0; Vila Velha (linear) 0 — só cidades `organica` têm sobreposição residual de lote, consistente com a causa (`sem_via` só existe em `organica.py`). | — |
| G04 | 2026-09-15 | `onEachFeature` de edifício acrescenta "· quadra {quarteirao_id}" ao popup, escapado. Confirmado via curl no mundo real: edifício de Quenanfield mostra `quarteirao_id: "1_0"`. Suíte: 219 (inalterada — só frontend). | — |
| E01 | 2026-09-15 | Medido antes: 5.205 vagas / 19.209 adultos = 27,1% (bate exatamente com o número do plano). +1 capacidade nos 5 tipos de comércio de bairro (config.json). Geometria regenerada mantendo o manifesto; provado (script do plano) que só `capacidade` mudou em toda feature de toda cidade. **Repovoado uma vez só** (usuário confirmou explicitamente antes de apagar `database/openworld.db`): `rm` + `builder/populate.py --ia-max-thread 4` (Ollama local, sem custo externo) → 9 cidades, **30.936 habitantes**. Medido depois: 6.402 vagas / 19.365 adultos = **33,1%** — dentro da faixa 31–36% pedida (bem próximo da previsão do plano, 33,2%). `audit_mundo.py`: 0 violações nos 10 invariantes (incluindo o 10 de C02). Suíte Python: 219 (inalterada). Dashboard reiniciado depois do repovoamento (pool de conexões antigo apontava pro arquivo apagado) e confirmado servindo os 30.936 habitantes novos. | `audit_cidades.py` continua saindo com código 1 — não por causa de E01, mas pelo mesmo residual já registrado em G02 (edif_sobrep=4 em "Cidade das Flores", não relacionado a sem_via, fora do escopo desta tarefa). **Efeito colateral esperado** (menos superlotação -> menos desgaste): não medido numericamente nesta tarefa — registrado como expectativa qualitativa, per o texto do plano ("registre" refere-se a anotar o efeito esperado, não a uma medição adicional que o plano não pediu). |
| I01 | 2026-09-15 | `ClienteIA` (8 membros) + `resolver_config_cliente`/`validar_config_ia` (engine/ai/clientes.py). Bloco `ia` no topo do config.json (provedores, padrão, 8 sobrescritas de cliente, coleta_uso, estimativa_custo). `contexto_tokens_servidor` (I11) já incluído desde este commit — evitou editar o mesmo bloco duas vezes. Suíte: 226 (219+7). Confirmado: `validar_config_ia` aceita o `config.json["ia"]` real. | — |
| I02 | 2026-09-15 | `ProvedorOpenAICompativel` (engine/ai/provedores/): POST /chat/completions, `transporte` injetado — `(url,corpo,cabecalhos,timeout) -> (status,corpo)`, default via urllib convertendo HTTPError na mesma tupla (a classificação 429/4xx/5xx acontece toda em `completar()`, não em tipos de exceção do urllib). Suíte: 233 (226+7... 14 no arquivo, 7 novos). | — |
| I03 | 2026-09-15 | `LimitadorDeTaxa` (janela deslizante minuto/dia + pausa pós-429), `relogio` injetado. Suíte: 237 (233+4). | — |
| I04 | 2026-09-15 | `RoteadorIA.consultar` — cadeia com fallback (429 pula sem backoff; indisponível repete no mesmo provedor com backoff exponencial; erro de configuração loga uma vez e pula; cadeia esgotada levanta `ErroIAIndisponivel`). Smoke-test contra `config.json` real: `ollama_local` disponível, `openrouter` marcado indisponível (sem `OPENROUTER_API_KEY` no ambiente) — comportamento esperado. Suíte: 247 (241+6). | — |
| I05 | 2026-09-15 | `AIClient.query` vira fachada sobre um `RoteadorIA` de processo (dupla checagem + trava). 8 chamadores atualizados pra `cliente=`; `model_name` saiu da assinatura de `generate_cities_for_continent` (nenhum chamador real passava valor diferente do default). `except Exception` genérico virou lista específica por chamador. Escrito um teste cobrindo os 8 chamadores caindo no fallback com `ErroIAIndisponivel` — nenhum tinha teste antes desta tarefa. Suíte: 249 (247+2). | — |
| I06 | 2026-09-15 | `engine/caminhos.py` (novo, só a ARQUITETURA já citava). `RegistradorDeUsoIA`/`RegistroUsoIA`/`ResultadoChamadaIA` — implementados ANTES de I04/I05 na ordem de commits (a doc lista I06 depois, mas o roteador da I04 já precisa dos tipos). `logs/` confirmado no `.gitignore`. Suíte: 241 (237+4). | — |
| I07 | 2026-09-15 | `builder/fix/estimar_custo_ia.py` — tabela por cliente+total, janela real coberta, projeção por dia, custo real informado ao lado quando existe, `--precos-ao-vivo`. Rodado de ponta a ponta contra um JSONL de exemplo (tabela/projeção corretas) e contra arquivo inexistente (código 1, mensagem clara). Suíte: 252 (250+2). | — |
| I08 | 2026-09-15 | Confirmado (leitura, sem mudança de código): `reproduction.py::_iniciar_batizado_assincrono` e `populador.py::_gerar_dnas_em_paralelo` já capturam `ErroIAIndisponivel` (via os clientes especializados, I05) e caem no fallback — os dois `except Exception` externos nesses dois arquivos são redes de segurança mais amplas (também cobrem escrita no banco/sincronização de lista), fora do escopo de I05. | `reproduction.py` linha ~237: a thread de batizado faz `for n in mundo.npcs` (acha o bebê pelo id) FORA da thread principal enquanto o tick muta a lista — corrida de dados CONHECIDA (Armadilha 20 de novo, entre threads). Não corrigida aqui (fora do escopo desta tarefa) — registrada pra decisão do dono do projeto. `populador.py`: com `ia_max_thread=4` e `dna_npc` no Ollama local (limite 0 = ilimitado), o comportamento é idêntico ao de hoje; se `dna_npc` apontar pro OpenRouter, o limitador (20/min) vai segurar a maioria das 750 chamadas de uma cidade grande e o resto cai no fallback — **isso é o esperado**, não bug. |
| I10 | 2026-09-15 | `git mv utils.py respostas_llm.py`, `AIUtils` -> `RespostaLLM`, `except Exception` -> `except json.JSONDecodeError`. `grep -rn "AIUtils\|ai.utils\|from .utils"` -> 0. Suíte: 250 (249+1). | O primeiro commit (`git add -A` com um pathspec já inválido pós-rename) só pegou o `git mv` em si, sem o conteúdo — corrigido num segundo commit imediato com o resto (classe renomeada, imports dos 6 arquivos, teste). Registrado aqui porque é exatamente o tipo de erro que os protocolos deste plano existem pra pegar (git status antes de confiar num `git add -A`). |
| I11 | 2026-09-15 | Implementado dentro do commit de I04 (mesma função que já registra o resultado da chamada). `sucesso_truncado` quando `tokens_entrada >= contexto_tokens_servidor`; JSON compacto (`separators=(",",":")`, sem `indent`) em `game_master.py`/`storyteller.py`. | **Passo 1 (ação do dono do projeto, configuração de sistema) não realizado nesta sessão** — não mexo em `systemctl`/serviços do SO. `contexto_tokens_servidor` do `ollama_local` continua em `4096` no config (o valor de ANTES do ajuste); se o dono do projeto aumentar a janela do Ollama pra 32768, é só atualizar essa chave — o resto (detecção de truncamento, JSON compacto) já está pronto e não muda. |
| **Parada 3 / I09** | | | |
| T01 | | | |
| T02 | | | |

---

## Anexo A — Como reproduzir cada medição

> Os scripts de sonda da análise original não fazem parte do repositório. Abaixo está o
> suficiente pra reescrevê-los. **Nunca** rode sonda contra `database/openworld.db` com a
> simulação no ar: copie o banco primeiro (`cp database/openworld.db* /tmp/`).

### A.1 Tamanho e tempo de endpoint

```bash
for u in /api/update /api/estado "/api/mapa/features?camadas=cidades,pois,estradas,fronteiras,muralha,torre,portao,praca,rua,quarteirao,patio,lote,edificio&bbox=296.9,344.9,297.1,345.1&z=13" /api/cidade/9/lotes_alterados; do
  curl -s -o /dev/null -w "%{http_code} %{size_download}B %{time_total}s  $u\n" "http://127.0.0.1:5000$u"
done
ps aux | grep -E "run_(simulation|dashboard)" | grep -v grep
ls -la database/openworld.db-wal logs/world.log
```
(Os ids de cidade e a bbox mudam quando o mundo é regenerado — pegue a bbox de uma cidade
em `database/cidades/_indice.json`.)

### A.2 Velocidade efetiva de uma run no ar (sem tocar na simulação)

```python
import sqlite3, time
from datetime import datetime
c = sqlite3.connect("file:database/openworld.db?mode=ro", uri=True)
def hora():
    return datetime.fromisoformat(c.execute(
        "SELECT valor FROM mundo_meta WHERE chave='hora_simulada_iso'").fetchone()[0])
a, t = hora(), time.time(); time.sleep(40); b, dt = hora(), time.time() - t
m = (b - a).total_seconds() / 60
print(f"{m:.0f} min simulados em {dt:.1f}s = {1000*dt/m:.0f} ms/tick = {m*60/dt:.0f}x")
```
(Ferramenta de diagnóstico manual: `sqlite3.connect` somente leitura é aceitável aqui,
fora do runtime — ARQUITETURA §15 #5 vale para o runtime.)

### A.3 Linhas mais frequentes do log

```bash
tail -c 300000000 logs/world.log | sed -E 's/\[[0-9: -]+\] //; s/[0-9]+/N/g' | cut -c1-45 | sort | uniq -c | sort -rn | head -25
```

### A.4 ms/tick e perfil do motor isolado

```python
import sys, time, cProfile, pstats, io
sys.path.insert(0, "/caminho/do/OpenWorld")
from engine.core import SimulationEngine
engine = SimulationEngine("/tmp/copia/openworld.db")
def medir(n):
    ts = []
    for _ in range(n):
        a = time.perf_counter(); engine.tick(); ts.append((time.perf_counter() - a) * 1000)
    ts.sort(); return sum(ts) / n, ts[n // 2], ts[int(n * .95)], ts[-1]
print("média/p50/p95/máx ms:", medir(120))
pr = cProfile.Profile(); pr.enable(); medir(60); pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(30); print(s.getvalue())
```
Antes de C01, esta sonda quebra com `RuntimeError` em poucos minutos — é a reprodução do
crash.

### A.5 Sobreposição por área

Depois de G01, é o próprio `builder/fix/audit_cidades.py`. O experimento de causa da
Seção 2.5 foi: gerar a mesma cidade (`{"nome": N, "tamanho": "grande", "tipo":
"residencial", "x_global": 300, "y_global": 400}`, `SitioCidade.medir(...,
"ContinenteTeste", CARTOGRAPHER_CONFIG)`, `random.Random(sitio.seed)`) com subclasses de
`OrganicaModelo` que desligam uma coisa por vez, e contar pares acima de 1 m² com as
funções de `cartographer/cities/geometria/sobreposicao.py`.

### A.6 Economia (números da seção de pendências)

```python
import sqlite3, json
c = sqlite3.connect("file:database/openworld.db?mode=ro", uri=True)
cats = json.load(open("config.json"))["urbanismo"]["categorias_empregadoras"]
ph = ",".join("?" * len(cats))
print(c.execute(f"SELECT cidade_id, SUM(capacidade) FROM locais WHERE status=1 AND categoria IN ({ph}) GROUP BY 1", cats).fetchall())
print(c.execute("SELECT cidade_id, COUNT(*) FROM npcs WHERE saude>0 AND estagio_vida='adulto' GROUP BY 1").fetchall())
print(c.execute("SELECT tipo_evento, COUNT(*) FROM eventos GROUP BY 1 ORDER BY 2 DESC").fetchall())
```

### A.7 Tokens por cliente de IA

Para cada `ClienteIA`, monte o prompt com o template real e argumentos realistas:
- `mestre` e `evento_global`: contexto de
  `MestreManager(DatabaseManager(<cópia do banco>), get_config()).montar_contexto()`,
  formatado como `AIGameMasterClient.gerar_resposta_mestre` e
  `AIStorytellerClient.gerar_evento_global` formatam;
- `planejamento_continentes` e `fundacao_cidades`: os templates de
  `cartographer/ai/prompt/` com as substituições de `world_manager_ai.py` e
  `city_manager_ai.py`;
- os demais: `AIClient.read_prompt(<arquivo>).format(...)` com os mesmos campos que o
  cliente usa.

Envie para o Ollama pela **API nativa**, com a janela aumentada — a API compatível com
OpenAI não aceita mudar a janela por requisição, e com a janela padrão o prompt grande
volta com 4.096 tokens (truncado):
```bash
curl -s localhost:11434/api/chat -d '{"model": "qwen2.5-coder:7b", "stream": false,
  "format": "json", "options": {"num_ctx": 32768},
  "messages": [{"role": "user", "content": "<prompt>"}]}'
```
Tokens de entrada = `prompt_eval_count`; de saída = `eval_count`. Volumes: continentes em
`database/world_manifest.json`; adultos/idosos por cidade e nascimentos por dia no banco
(`eventos` com `tipo_evento='NASCIMENTO'`, agrupados pelo dia do `timestamp`).

Depois de I06/I07, **use o JSONL real** em vez desta sonda.

---

## Anexo B — Fatos externos (OpenRouter e Ollama)

> Consultados em **2026-09-14**. Preços e limites de serviço externo mudam — o config e o
> script de I07 existem exatamente pra não depender deste anexo.

**OpenRouter**

- API compatível com OpenAI: `POST https://openrouter.ai/api/v1/chat/completions`,
  cabeçalho `Authorization: Bearer <chave>`. `X-Title` é opcional (nome do app nas
  estatísticas deles).
- Modelos gratuitos (sufixo `:free`), de `GET https://openrouter.ai/api/v1/models`:
  - `google/gemma-4-31b-it:free` — contexto 262.144, aceita `response_format` ⭐ (❷)
  - `google/gemma-4-26b-a4b-it:free` — contexto 262.144, aceita `response_format`
- Limites dos `:free` (docs/api-reference/limits): **20 requisições/minuto**; **50
  requisições/dia** com menos de 10 créditos comprados; **1.000/dia** com 10 ou mais.
  O dono do projeto tem **US$ 5** em créditos → vale o teto de 50/dia.
- A resposta **sempre** traz `usage` com `prompt_tokens`, `completion_tokens`,
  `total_tokens`, `cost`, e detalhes (`prompt_tokens_details.cached_tokens`,
  `completion_tokens_details.reasoning_tokens`). Não é preciso parâmetro extra (o antigo
  `usage: {include: true}` está depreciado). Também existe consulta assíncrona por id de
  geração (`/generation`).
- Preços DeepSeek relevantes (USD por **milhão** de tokens, entrada / saída):

  | modelo | entrada | saída | contexto |
  |---|---|---|---|
  | **`deepseek/deepseek-v4-flash`** ⭐ (❸) | **0,08246** | **0,16492** | 1.048.576 |
  | `deepseek/deepseek-v4.1-flash` | 0,15 | 0,60 | 1.048.576 |
  | `deepseek/deepseek-v3.2` | 0,269 | 0,40 | 163.840 |
  | `deepseek/deepseek-v4-pro` | 1,60 | 3,20 | 1.048.576 |

**Ollama (local)**

- API nativa (usada hoje): `POST http://localhost:11434/api/chat`, `"format": "json"`.
- API compatível com OpenAI (usada a partir de I02): `POST
  http://localhost:11434/v1/chat/completions`. **Verificado nesta máquina:** aceita
  `"response_format": {"type": "json_object"}` e devolve `usage` (`prompt_tokens`,
  `completion_tokens`, `total_tokens`); não devolve `cost`.
- Não exige chave.
