# ⏩ Plano de Avanço e Calibragem — por que D13 não bateu, e as cinco pendências fechadas

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este é o **terceiro** documento da série, e o menor. Os dois anteriores
> ([`PLANO_CIDADE_VIVA.md`](PLANO_CIDADE_VIVA.md) e
> [`PLANO_POPULACAO_E_ESCALA.md`](PLANO_POPULACAO_E_ESCALA.md)) foram executados quase por
> inteiro — 31 + 28 tarefas — e o segundo parou com **cinco pendências** e um alvo (D13)
> que não foi atingido. Este documento fecha as cinco, corrige um diagnóstico errado com
> medição, e destrava o Bloco R que ficou esperando.
>
> 👉 **Leia os dois anteriores antes deste.** As doze armadilhas deles continuam valendo.
> Este acrescenta três.
>
> 👉 **Nada aqui refaz trabalho feito.** Onde a implementação divergiu do texto do plano, a
> divergência foi analisada e, em dois casos, **estava certa** — está escrito qual.

**Criado em:** 2026-09-12
**Base analisada:** branch `reescrita-estrutura`, commit `e6dd2bf`
**Estado da suíte:** `143 passed` (o invariante novo de L04 é ferramenta de linha de
comando, fora do pytest)
**Medições:** 14 cidades em `database/cidades/` (57 mil lotes) e mundos sintéticos de
25.000 NPCs / 60.000 locais / 40 cidades, um dia simulado completo (1.440 ticks) por
execução.

---

## Índice

- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. As cinco pendências, respondidas](#1-as-cinco-pendências-respondidas)
- [2. Por que D13 não bateu — o diagnóstico completo](#2-por-que-d13-não-bateu--o-diagnóstico-completo)
- [3. Decisões já tomadas (não reabra)](#3-decisões-já-tomadas-não-reabra)
- [4. As três novas armadilhas](#4-as-três-novas-armadilhas)
- [Bloco H — O avanço de dias que D13 promete](#bloco-h--o-avanço-de-dias-que-d13-promete)
- [Bloco F — O Mestre passa a rodar no processo da simulação](#bloco-f--o-mestre-passa-a-rodar-no-processo-da-simulação)
- [Bloco C — Calibragem, e o caminho de volta ao Bloco R](#bloco-c--calibragem-e-o-caminho-de-volta-ao-bloco-r)
- [Bloco Y — Validação](#bloco-y--validação)
- [Anexo — Tabela de medições](#anexo--tabela-de-medições)
- [Registro de execução](#registro-de-execução)

---

## 0. Como usar este documento

As regras de execução dos dois documentos anteriores valem sem mudança: uma tarefa por
commit, suíte antes e depois, auditar depois de tarefa de geometria, parar e anotar quando
algo for maior do que o descrito.

Duas ferramentas de medida, que este documento usa o tempo todo:

```
venv/bin/python3 builder/fix/bench_avanco.py --dias 1      # o número de D13
venv/bin/python3 builder/fix/audit_cidades.py ; echo $?     # sem pipe: o pipe engole o código
```

### Ordem e dependências

```
Bloco H  (o avanço de dias)          ← o alvo do projeto; comece por H01
    │
    ▼
Bloco F  (o Mestre no processo certo)  ← fecha as pendências 3 e 4 de uma vez
    │
    ▼
Bloco C  (calibragem: invariante + anéis)
    │
    ▼
R01–R04 do PLANO_POPULACAO_E_ESCALA.md   ← destravado por C01/C02, não reescrito aqui
    │
    ▼
Bloco Y  (validação) + W02 do documento anterior
```

**Parada obrigatória — depois de H03.** Rode `bench_avanco.py --dias 1`. O número tem que
cair de **189 s** para a casa de **20 a 40 s**, e o pico de decisões num único tick tem que
cair de **25.000** para alguns milhares. Se o pico continuar em 25.000, H03 não pegou a
sincronização toda — não siga para H04 antes de achar qual fronteira ficou de fora.

---

## 1. As cinco pendências, respondidas

### 1.1 O teto de 30 lotes por quadra — o invariante estava errado, não a geometria

**Você estava certo em não mexer no valor sem medir.** E a medição mostra que o problema
não é calibragem: é o invariante.

Uma quadra **perfeitamente quadrada** no alvo de S01 (95 m) tem perímetro de 380 m. A
~11 m de frente por lote, isso dá **34 lotes** — acima de 30 sem nenhum erro em lugar
nenhum. O `4 a 30` foi um número que eu escrevi no primeiro plano **sem nunca ter medido**,
e ele nunca foi alcançável para uma quadra desse tamanho.

Pior: o número depende de coisas que variam legitimamente por modelo — o tamanho da quadra,
o inset da faixa de domínio, e a frente alvo por banda. Medido hoje: `grade` 9–21,
`linear` 12–18, `radial` 34–41, `organica` 30–34. Nenhum desses está errado.

**A correção (C01):** o gate duro passa a ser uma **auto-consistência**, não um número
absoluto:

```
lotes_na_quadra  ≈  perímetro_urbanizável / frente_alvo_da_banda     (±25%)
```

Isso vale em qualquer tamanho de quadra, em qualquer modelo, e pega o que interessa de
verdade — lote fantasma, lote sem frente, faixa contada duas vezes. A contagem absoluta
vira coluna de relatório.

**E o Bloco S funcionou muito bem**, o que o teto de 30 estava escondendo:

| | antes de S | depois de S |
|---|---|---|
| Jordorstead: quadras | 60 | **240** |
| Jordorstead: lotes/quadra (mediana / máx) | 151 / 195 | **41 / 94** |
| Jordorstead: largura ÷ profundidade | 4,28 | **1,66** |
| Fenelburgo: lotes/quadra (mediana / máx) | 101,5 / 198 | **34 / 117** |
| `sem_frente_pct`, todas as cidades | até 4,6% | **0,0** |

### 1.2 A profundidade da quadra: o teto de anéis é que está mordendo

Achado que sai da mesma medição. A coluna `larg/prof` do `radial` ficou em 1,43–1,72, não
em ~1,0 como S01 pretendia. A causa não é a largura (que S01 controla bem): é a
**profundidade**, que está em 110–143 m quando `cidade_geo_vao_anel_alvo_m` pede **95**.

O motivo está em `cidade_geo_num_aneis_faixa_por_tamanho`, cujo teto para `grande` é **6**.
Jordorstead (raio 992 m) precisaria de **9** anéis para ter vão de 95. G05 já tinha
registrado isso como "decisão de balanceamento visual, não bug" — e agora é hora de tomar
a decisão. **C02 sobe o teto**, e a quadra vai para ~85 × 95 m, quase quadrada, como o
Bloco S prometia.

### 1.3 D13 não bateu — mas o grafo de relacionamentos **não** é a causa

Aqui eu preciso corrigir o diagnóstico do registro de A07, e a correção importa porque ela
muda completamente o que fazer.

Você profilou e viu `processar_coabitacao` / `verificar_elegibilidade_casamento`
dominando. **Isso está certo.** A conclusão de que a causa era o grafo social sem teto é
que não está. Medi o grafo no mesmo cenário, ao fim de um dia simulado com 25.000 NPCs:

| | valor medido |
|---|---|
| relacionamentos por NPC, mediana | **0** |
| relacionamentos por NPC, máximo | **14** |

O grafo praticamente não cresceu. O custo de `processar_coabitacao` não vem do tamanho do
dicionário de cada NPC — vem de ela **rodar a cada tick**, varrendo todos os solteiros de
todas as cidades, 1.440 vezes por dia simulado, para produzir no máximo um casamento. A
[Seção 2](#2-por-que-d13-não-bateu--o-diagnóstico-completo) tem o diagnóstico inteiro, com
três causas que nenhuma delas é o grafo.

Isso não quer dizer que pôr um teto no grafo seja desnecessário — é, e H06 faz isso. Mas é
uma questão de memória e de mundo longevo, **não** o que está bloqueando D13.

### 1.4 e 1.5 O Mestre: a lacuna e o desvio de M02 são o mesmo problema

As duas pendências têm uma causa só: o Modo Mestre roda no processo do Flask e só tem
`db`. Disso decorrem, em cadeia:

- não dá para chamar `mundo.acordar()` (pendência 3);
- não dá para chamar `abrir_obra`, que precisa de um `EstadoDoMundo` vivo (pendência 4);
- foi preciso inventar `_avaliar_expansao_fora_do_processo`, que monta um `EstadoDoMundo`
  **de trabalho** só para a auto-expansão funcionar de fora;
- M01 precisou de um contador de versão para o caminho contrário.

**O seu desvio em M02 estava certo**, e por duas razões, não uma. A que você escreveu (não
há `EstadoDoMundo` no processo do Flask) é a circunstancial. A outra é de modelagem, e vale
mais: **`abrir_obra(dono_npc)` assume que todo edifício tem um dono pessoal**, e um quartel
não tem. O texto do plano que mandava chamar `abrir_obra` estava errado sobre isso.

**A solução (Bloco F) resolve as duas de uma vez:** as ações de mundo do Mestre passam a
ser **enfileiradas** e aplicadas pelo processo da simulação, com o mundo vivo — exatamente
o padrão que `AVANCAR_MINUTOS` já usa e que a `ARQUITETURA.md` já abençoa. Aí `acordar`
funciona, `abrir_obra` funciona, e `_avaliar_expansao_fora_do_processo` pode ser apagado.
E `abrir_obra` ganha dono opcional, porque o problema do quartel é real.

---

## 2. Por que D13 não bateu — o diagnóstico completo

D13 pede **7 dias simulados em ~30 s** com 25.000 NPCs. Medido: **189 s para 1 dia**
(131 ms/tick), ou seja 22 minutos para 7 dias. Rodei um dia inteiro registrando decisões
avaliadas e milissegundos, tick a tick, e o resultado tem três causas independentes.

### 2.1 A manada: cinco horas do dia carregam o custo inteiro

Decisões avaliadas por tick, e ms por tick, por hora do dia:

| hora | decisões/tick | ms/tick |
|---|---|---|
| 0–5 | 0 a 639 | 49 a 106 |
| **6** | **24.997** | **770,6** |
| **7** | **23.999** | **553,8** |
| 8–18 | 0 a 417 | 52 a 68 |
| **19** | 6.162 | 168,1 |
| **20** | 8.007 | 200,0 |
| **21** | 9.978 | 230,2 |
| 22–23 | 158 a 884 | 51 a 69 |

Os dez maiores picos são todos de **25.000 decisões num único tick** — a população inteira
— entre 06:29 e 06:37, e às 08:01, custando de 890 a **1.051 ms** cada.

**A causa é sincronização.** `agenda.calcular_proximo_instante` já tem jitter (você o
acrescentou ao perceber os picos, e estava certo), mas **só no teto de segurança**. As
fronteiras de relógio não têm nenhum: `_minutos_ate_fim_do_sono_obrigatorio` devolve
**exatamente o mesmo valor** para todo NPC dormindo, então os 25.000 acordam no mesmo
minuto. `hora_inicio_trabalho` faz o mesmo às 8h. E os cruzamentos de limiar de fome também
sincronizam, porque a taxa é a mesma para todos.

É o problema clássico de fila com despertador comum, e a solução é a mesma de sempre:
espalhar. Gente de verdade também não acorda toda às 6h em ponto.

### 2.2 O piso: 52 ms num tick com ZERO decisões

Medi um tick numa hora morta (9h, nenhuma decisão devida): **51,8 ms**. Perfilado, o piso
tem quatro donos, e **os quatro são varreduras de todos os NPCs**:

| o que varre todo mundo, todo tick | participação do piso |
|---|---|
| `marriage.processar_coabitacao` (todos os solteiros × relacionamentos) | ~46% |
| `consultas_npc.assinatura_dependentes_por_casa` (N04) | ~16% |
| `consultas_npc.agrupar_npcs_por_localizacao` (chamada por `social.py`) | ~12% |
| o próprio laço de `executar_tick`: `for npc in mundo.npcs` + `npc_esta_em_dia` | ~10% |

O último é o mais importante para entender, porque é uma lição de arquitetura, não um
descuido: **A02 implementou a agenda como um predicado, não como uma estrutura de dados.**
O laço continua percorrendo os 25.000 NPCs e perguntando "você está em dia?" para cada um.
O predicado está correto e o comportamento está correto — mas o custo por tick continua
sendo O(NPCs), que é exatamente o que a agenda existia para eliminar.

E a terceira linha é um resto: A04 criou `mundo.npcs_por_localizacao` como índice mantido,
mas `social.py` continua chamando `NPCUtils.agrupar_npcs_por_localizacao(mundo.npcs)` e
reconstruindo tudo. O índice existe e está sendo ignorado.

### 2.3 A conta total: 4,6 milhões de decisões por dia

Somando a tabela de 2.1: **~4,6 milhões de decisões por dia simulado**, ou **184 decisões
por NPC por dia** — uma a cada 8 minutos. Compare com os 78 minutos de duração média de uma
ação, medidos contra o banco real no documento anterior. A diferença tem nome: as ações
**não loteáveis**.

`ACOES_LOTEAVEIS` inclui só `DORMIR`, `TRABALHAR` e `OCIOSO`. `COMER`, `CONSTRUIR` e
`CUIDAR_PROLE` são reavaliadas **todo minuto**, por escolha consciente de escopo em A02 —
e foi uma escolha razoável na hora. Mas quando 25.000 NPCs acordam juntos às 6h e vão comer
juntos, uma refeição de algumas dezenas de ticks vira algumas centenas de milhares de
decisões. É isso que sustenta as horas 6 e 7 em 25.000 decisões por **uma hora inteira**,
não só num tick.

As três causas são independentes e precisam das três correções. Nenhuma delas é o grafo
social.

---

## 3. Decisões já tomadas (não reabra)

| # | Decisão | Consequência |
|---|---|---|
| **D18** | **O invariante de lotes por quadra vira auto-consistência**, não um intervalo absoluto. | C01. `LOTES_POR_QUADRA_MEDIANA_MIN/MAX` saem; a contagem vira relatório. |
| **D19** | **Subir o teto de anéis** para a quadra radial ficar quase quadrada (~85 × 95 m). | C02. `cidade_geo_num_aneis_faixa_por_tamanho` recalibrado. |
| **D20** | **As ações de mundo do Mestre passam a ser aplicadas pelo processo da simulação**, por fila, como `AVANCAR_MINUTOS`. | Bloco F. Resolve `acordar`, resolve `abrir_obra`, apaga o `EstadoDoMundo` de trabalho. |
| **D21** | **A agenda vira estrutura de dados, não predicado.** | H01. É a correção que o texto de A02 pedia e que não ficou explícita o bastante. |
| **D22** | **D13 é revisado para 7 dias em ~2 minutos** com 25.000 NPCs. | Ver [a aritmética em H06](#h06--medir-de-novo-e-o-que-d13-passa-a-prometer). Os 30 s originais exigiriam ~8 decisões por NPC por dia, que é menos do que um dia crível tem. |

---

## 4. As três novas armadilhas

### Armadilha 13 — predicado não é agenda

A02 foi implementada como `for npc in mundo.npcs: if npc_esta_em_dia(npc): ...`. Está
**correta** e passa em todos os testes. E custa O(NPCs) por tick, para sempre, que é
precisamente o que a agenda existia para eliminar.

A lição vale além desta tarefa: quando um plano diz "só processe quem está vencido", a
pergunta a fazer é **"como eu chego nesses sem olhar os outros?"**. Se a resposta envolve
percorrer a lista inteira, o ganho é só no corpo do laço — e num mundo de 25.000 agentes o
corpo do laço não é o único custo.

### Armadilha 14 — jitter no teto não desfaz sincronização de relógio

O jitter que A02 aplica ao teto de segurança resolve **um** dos casos de sincronização: a
população homogênea que agenda tudo para o mesmo instante futuro. Ele **não** toca nos
outros dois, que são os grandes:

- fronteira de relógio (`hora_fim_sono_obrigatorio`, `hora_inicio_trabalho`) — o mesmo
  instante para todo mundo, por construção;
- cruzamento de limiar com taxa idêntica — todos cruzam a fome de 40 no mesmo minuto.

Toda vez que você acrescentar um candidato a "próximo instante", pergunte: **este valor é o
mesmo para muita gente ao mesmo tempo?** Se for, ele precisa de jitter próprio. E o jitter
tem que ser **determinístico por NPC** (derivado do id com `zlib.crc32`, nunca `random`
puro), senão o mesmo mundo com a mesma seed deixa de ser reproduzível.

### Armadilha 15 — "está no índice" não quer dizer "está sendo usado"

A04 criou `mundo.npcs_por_localizacao` e `social.py` continuou reconstruindo o agrupamento
do zero, todo tick, sobre os 25.000. Nenhum teste falhou, porque as duas coisas devolvem a
mesma resposta. Só o relógio sabia.

Antes de dar uma tarefa de índice por encerrada, faça o `grep` do que ele substitui e
confirme que **não sobrou chamador**:

```
grep -rn "agrupar_npcs_por_localizacao\|agrupar_por_casa" engine/ builder/ web/
```

Cada ocorrência fora de `consultas_npc.py` e de um teste é um lugar que ignora o índice.

---

## Bloco H — O avanço de dias que D13 promete

> **O que este bloco resolve:** 1 dia simulado custa 189 s com 25.000 NPCs, quando D13
> pede 7 dias em 30 s. As três causas da [Seção 2](#2-por-que-d13-não-bateu--o-diagnóstico-completo)
> precisam das três correções — H01/H02 derrubam o piso, H03/H04 desfazem a manada, H05
> corta o número total de decisões.

### H01 · A agenda vira estrutura de dados, não predicado

**Arquivos:** `engine/mundo.py`, `engine/loop.py`, `engine/mechanics/agenda.py`

**Problema:** [armadilha 13](#armadilha-13--predicado-não-é-agenda). O laço faz
`for npc in self._mundo.npcs` e pergunta `npc_esta_em_dia` a cada um dos 25.000, todo tick.
Medido: ~10% de um piso de 51,8 ms num tick com **zero** decisões devidas.

**Ação:**

1. `EstadoDoMundo` ganha um **balde por minuto**: `dict[datetime, list[NPC]]`. Quando
   `proximo_instante_decisao` é definido, o NPC entra no balde daquele minuto.
2. O laço do tick passa a ler **só** `baldes.pop(agora, [])`, mais os baldes de minutos
   passados que ficaram para trás (um NPC agendado para um instante já vencido, por
   exemplo depois de um salto do Mestre).
3. Um **conjunto separado e pequeno** para os NPCs em estado de consequência (fome acima
   de `inaniacao_fome_limiar`), que são avaliados todo tick por definição. `npc_esta_em_dia`
   deixa de ser chamada 25.000 vezes e passa a ser a regra de **entrada e saída** desse
   conjunto.
4. `mundo.acordar(npc)` passa a **mover** o NPC de balde, não só mudar o campo. Essa é a
   única forma de a porta continuar sendo porta ([armadilha 12](PLANO_POPULACAO_E_ESCALA.md)).
5. ⚠️ Um dicionário de baldes com chave `datetime` cresce para sempre se ninguém limpar.
   Remova o balde ao consumi-lo, e **não** agende nada além do teto de segurança — isso
   limita o número de baldes vivos a `intervalo_maximo_decisao_min`.

**Validar:** um tick em hora morta cai de ~52 ms para poucos ms. E um teste de invariante,
que é o que segura este bloco inteiro: **a soma dos tamanhos de todos os baldes mais o
conjunto de consequência é sempre igual ao número de NPCs vivos.** Rode-o depois de partos,
mortes, casamentos, mudanças de casa e `acordar`.

**Risco:** alto.

---

### H02 · As outras três varreduras por tick

**Arquivos:** `engine/mechanics/social.py`, `engine/mechanics/marriage.py`,
`engine/consultas_npc.py`, `engine/loop.py`

**Problema:** as outras três linhas do piso de 51,8 ms, todas do mesmo feitio.

**Ação, uma por vez, medindo entre elas:**

1. **`processar_coabitacao` ganha cadência (≈46% do piso).** A06 criou a máquina de
   cadência e `NPCMarriageManager`/`NPCSocialManager` ficaram de fora — a coabitação roda
   no fim de `processar_interacoes`, todo tick. Casamento não é um evento de minuto:
   declare `CADENCIA = "por_dia"` e registre no despacho de `loop.py`, como as outras cinco
   mecânicas já fazem. ⚠️ Ela sai de `processar_interacoes` e passa a ser chamada pelo
   despacho — **não** deixe as duas chamadas coexistindo.
2. **`social.py` usa o índice mantido (≈12%).**
   [Armadilha 15](#armadilha-15--está-no-índice-não-quer-dizer-está-sendo-usado).
   Troque `NPCUtils.agrupar_npcs_por_localizacao(self._mundo.npcs, ignorar_dormindo=True)`
   por `self._mundo.npcs_por_localizacao`, filtrando os que dormem **dentro de cada balde**
   (que é pequeno) em vez de varrer o mundo. Rode o `grep` da armadilha 15 depois.
3. **`assinatura_dependentes_por_casa` (≈16%).** N04 detecta mudança de composição
   comparando uma assinatura calculada sobre **todas** as casas, todo tick — trocou uma
   varredura por outra. Como `mudar_casa`/`registrar_npc`/`remover_npc` já são a porta
   única (A04), elas podem simplesmente **anotar** o `casa_id` num conjunto de casas sujas
   do tick. Aí `_atualizar_dependentes` recalcula só essas.

**Validar:** `bench_avanco.py --dias 1` depois de cada um dos três, com o número anotado no
[Registro](#registro-de-execução). Somados com H01, o tick em hora morta tem que ficar
abaixo de **5 ms**.

**Risco:** médio.

---

### H03 · Jitter nas fronteiras de relógio

**Arquivos:** `engine/mechanics/agenda.py`

**Problema:** [armadilha 14](#armadilha-14--jitter-no-teto-não-desfaz-sincronização-de-relógio).
Dez dos dez maiores picos do dia são de **25.000 decisões num tick só** — a população
inteira. `_minutos_ate_fim_do_sono_obrigatorio` devolve o mesmo valor para todo NPC
dormindo; `hora_inicio_trabalho` faz o mesmo; e os cruzamentos de fome sincronizam porque a
taxa é igual para todos.

**Ação:**

1. Um deslocamento **determinístico por NPC**, derivado do id:
   ```
   import zlib
   desvio = zlib.crc32(npc.id.encode("utf-8")) % janela_de_jitter_min
   ```
   ⚠️ `zlib.crc32`, **nunca** `hash()` nem `random` puro — é a regra de determinismo do
   projeto desde o primeiro documento, e aqui ela vale duas vezes, porque um `random` no
   cálculo do próximo instante torna o mundo irreproduzível com a mesma seed.
2. Aplique-o às fronteiras de relógio (fim do sono obrigatório, início e fim do
   expediente) com `cidade`... não: com uma config nova
   `simulacao_jitter_fronteira_min` (valor inicial **45**). O NPC acorda entre 6:00 e 6:45,
   o que é mais realista do que a vila inteira abrindo os olhos junto.
3. Aplique-o também ao **cruzamento de limiar**, de forma mais sutil: em vez de jitter no
   instante, dê a cada NPC um desvio pequeno e permanente nos próprios limiares de decisão
   (±5% sobre `gatilho_fome_normal`, por exemplo, derivado do mesmo `crc32`). Isso dessincroniza
   **e** dá personalidade — uns comem mais cedo, outros aguentam mais.
   ⚠️ **Não** aplique desvio nenhum aos limiares de **consequência** (inanição): aquele é o
   limite onde o NPC começa a morrer, e ele não é lugar para variação estética.
4. Mantenha o jitter que já existe no teto de segurança. Ele resolve um caso diferente e
   continua necessário.

**Validar:** rode um dia com o registro por hora. As horas 6, 7, 19, 20 e 21 têm que perder
o pico, e o maior pico de decisões num tick tem que cair de 25.000 para alguns milhares.
**É a parada obrigatória deste documento.**

**Risco:** médio.

---

### H04 · Comer, construir e cuidar da prole entram na agenda

**Arquivos:** `engine/mechanics/agenda.py`

**Problema:** `ACOES_LOTEAVEIS` tem só `DORMIR`, `TRABALHAR` e `OCIOSO`. As outras três são
reavaliadas **todo minuto**, e A02 registrou isso como escolha consciente de escopo. Com a
manada, essa escolha custa caro: 25.000 NPCs que acordam juntos comem juntos, e uma
refeição de algumas dezenas de ticks vira centenas de milhares de decisões. É o que
sustenta as horas 6 e 7 em ~25.000 decisões por **uma hora inteira**, não só num pico.

**Ação:** as três têm **fim conhecido**, que é justamente o que a agenda precisa:

| ação | quando termina | próximo instante |
|---|---|---|
| `COMER` | depois de `parcelas_refeicao` ticks | o tick em que a última parcela é paga |
| `CONSTRUIR` | quando a integridade da obra cruza 100% | integridade restante ÷ ganho por tick |
| `CUIDAR_PROLE` | quando a necessidade que a disparou desaparece | o cruzamento dessa necessidade |

Acrescente cada uma ao cálculo, uma por vez, medindo. Se alguma tiver transição interna que
você não consegue calcular com confiança, **deixe-a de fora e anote** — duas das três já
pagam o bloco.

⚠️ Continua valendo a regra das três classes de limiar: mesmo lotável, a ação nunca salta
por cima de um limiar de consequência.

**Validar:** decisões por dia caem de ~4,6 milhões. Anote o número novo no Registro.
E um teste de comportamento: uma refeição continua durando exatamente `parcelas_refeicao`
ticks e custando o mesmo total.

**Risco:** médio.

---

### H05 · O teto do grafo social

**Arquivos:** `engine/models.py`, `engine/mechanics/social.py`, `config.json`

**Problema:** não é o que trava D13 — medido, a mediana de relacionamentos por NPC é **0** e
o máximo é **14** num dia. Mas `npc.relacionamentos` só cresce, nunca decai, e num mundo que
roda meses isso vira memória (25.000 × centenas de entradas) e custo em `salvar_completo`.
A Seção 5.2 do primeiro documento já marcava isto como horizonte; agora é barato fazer.

**Ação:**

1. Config nova `simulacao_relacionamentos_max_por_npc` (valor inicial **150** — o número de
   Dunbar, que por acaso é também o que a performance pede).
2. Quando passar do teto, descarte os mais fracos e mais antigos. **Nunca** descarte:
   cônjuge, pais, filhos, e quem estiver acima do limiar de vínculo forte. Uma pessoa
   esquece um conhecido de taverna, não a própria irmã.
3. Decaimento leve: a afinidade de quem não é reencontrado anda em direção a zero, e a
   entrada some quando chega lá. Pendure no despacho de cadência diária (A06).

**Validar:** um mundo de 30 dias simulados com o tamanho do grafo estável em vez de
crescente. Nenhum NPC perde cônjuge ou parente do próprio dicionário.

**Risco:** baixo.

---

### H06 · Medir de novo, e o que D13 passa a prometer

**Arquivos:** `builder/fix/bench_avanco.py`, [Registro](#registro-de-execução)

**A aritmética, para você saber o que esperar e não perseguir um número impossível.**
D13 pedia 7 dias (10.080 ticks) em 30 s, ou seja **3 ms por tick**. Com o piso em ~2 ms
depois de H01/H02, sobra ~1 ms para as decisões, ou **~50 decisões por tick** — que dá
**8 decisões por NPC por dia**. Um dia crível tem mais que isso: acordar, três refeições,
começar e terminar o expediente, dormir, mais os cruzamentos de necessidade.

Um alvo honesto é **20 a 30 decisões por NPC por dia**, ou seja 350 a 520 decisões por tick,
o que dá **9 a 12 ms por tick**:

| | ms/tick | 1 dia | 7 dias |
|---|---|---|---|
| hoje | 131 | 189 s | 22 min |
| depois do Bloco H (estimado) | 9 a 12 | 13 a 17 s | **1,5 a 2 min** |
| D13 como escrito | 3 | 4 s | 30 s |

**D22: D13 passa a prometer 7 dias em ~2 minutos.** Para um avanço de aventura isso é
perfeitamente utilizável, e é 11× melhor que hoje. Chegar aos 30 s originais exigiria
menos decisões por NPC do que um dia crível tem, ou menos NPCs, ou o modo grosso de passo
diário que D17 manteve fora de escopo.

**Ação:**

1. `bench_avanco.py` ganha o relatório por hora (decisões e ms por hora do dia) e o
   **maior pico de decisões num tick** — os dois números que expõem a manada. Sem eles,
   H03 é impossível de validar.
2. Rode 1 dia e 7 dias, cole as duas tabelas no Registro.
3. Se o resultado ficar acima de ~15 ms/tick, **pare e perfile** antes de mexer em mais
   nada. Não introduza thread nem processo (D11 continua valendo).

**Risco:** baixo.

---

## Bloco F — O Mestre passa a rodar no processo da simulação

> **O que este bloco resolve:** as pendências 3 e 4 de uma vez. O Mestre escreve no banco a
> partir do processo do Flask, e por isso não consegue acordar NPC, não consegue chamar
> `abrir_obra`, e precisou de um `EstadoDoMundo` de trabalho para a auto-expansão.

### F01 · Fila de ações de mundo

**Arquivos:** `engine/schema.sql`, `engine/repositorios/mestre.py`,
`engine/mechanics/mestre/gerenciador.py`, `run_simulation.py`, `engine/core.py`

**Ação:**

1. Tabela nova `mestre_acoes_pendentes` (id, payload JSON, criada_em, aplicada_em). O
   `MestreManager` no Flask **enfileira** em vez de aplicar.
2. `run_simulation.py` drena a fila a cada volta do laço, **inclusive pausado** — é o mesmo
   ponto onde M01 já checa `LOCAIS_VERSAO` e onde `AVANCAR_MINUTOS` já é lido, e o Mestre
   prepara cena com a simulação parada.
3. As classes de `engine/mechanics/mestre/acoes/` passam a receber `EstadoDoMundo` além de
   `db`, e a partir daí podem chamar `mundo.acordar`, `mundo.mover_npc`, `abrir_obra` —
   tudo que a simulação chama.
4. **Apague** `_avaliar_expansao_fora_do_processo` e o `EstadoDoMundo` de trabalho. Ele
   existia só para contornar isto, e deixá-lo vivo é manter dois caminhos para a mesma
   coisa.
5. `LOCAIS_VERSAO` (M01) **continua**: ele resolve o caminho contrário, que é o dashboard
   ler estado, e não deixa de ser necessário.
6. ⚠️ **O retorno para o jogador vira assíncrono.** A ação é confirmada na hora e aplicada
   no tick seguinte. A rota do Flask precisa dizer isso ("ação enviada"), e o resultado
   aparece quando o processo da simulação a aplicar. Se você fingir que foi aplicada na
   hora, o jogador vai ver a tela mentir.
7. ⚠️ Se `run_simulation.py` **não** estiver rodando, a fila não drena. Mostre isso na
   interface em vez de deixar a ação sumir em silêncio — é a mesma condição que
   `AVANCAR_MINUTOS` já tem hoje, só que agora ela fica visível.

**Validar:** com a simulação rodando, criar um local pelo Modo Mestre e ver no log do
processo da simulação que ele nasceu **num lote**, com o índice atualizado, e que um NPC
mandado para lá **acorda** e reage no tick seguinte.

**Risco:** alto. É mudança de fluxo entre processos.

---

### F02 · `abrir_obra` aceita edifício sem dono

**Arquivos:** `engine/mechanics/urbanismo.py`

**Problema:** o desvio de M02 que **estava certo**. `abrir_obra(cidade_id, dono_npc, ...)`
usa o dono para duas coisas: marcar o lote como dele, e escolher um lote perto da casa
dele. Um quartel criado pelo Mestre não tem dono pessoal, e nem deveria ter.

**Ação:**

1. `dono_npc` vira opcional. Sem dono: `npc_id` do lote fica vazio (edifício institucional)
   e `perto_de` vira `None` (qualquer lote livre da cidade serve, ou o de melhor frente).
2. Escreva no docstring **que tipo de edifício não tem dono** — quartel, praça, poço,
   muralha — para que a próxima pessoa não ache que é um caso degenerado a ser consertado.
3. Depois de F01, `CriarLocal` passa a chamar `abrir_obra` de verdade, e a reserva direta
   de lote que M02 precisou fazer some. A garantia de O03 — `abrir_obra` é o único caminho
   para um edifício nascer — volta a ser verdade sem exceção.
4. Um edifício do Mestre nasce **pronto** (não em obra), ao contrário do de um casal. Deixe
   isso como parâmetro explícito de `abrir_obra`, não como uma segunda função.

**Validar:** `tests/test_mestre.py` continua passando, com o caso novo de edifício sem dono.
`grep` prova que `db.lotes.reservar_livre` só é chamado de dentro de `abrir_obra`.

**Risco:** baixo.

---

### F03 · O Mestre acorda quem ele tocou

**Arquivos:** `engine/mechanics/mestre/acoes/*.py`

**Ação:** com F01 no lugar, toda ação do Mestre que muda um NPC (`AFETAR_NPC`,
`REATRIBUIR_NPC`) chama `mundo.acordar(npc)`; `DESTRUIR_LOCAL` chama `acordar` em quem
trabalhava ou morava ali. É o ponto que A03 registrou como impossível e que agora é uma
linha.

**Validar:** o teste de A03 ganha o caso do Mestre: reatribuir o trabalho de um NPC
agendado para daqui a horas faz ele reavaliar no tick seguinte.

**Risco:** baixo.

---

## Bloco C — Calibragem, e o caminho de volta ao Bloco R

### C01 · O invariante de lotes por quadra vira auto-consistência

**Arquivos:** `builder/fix/audit_cidades.py`

**Problema:** [1.1](#11-o-teto-de-30-lotes-por-quadra--o-invariante-estava-errado-não-a-geometria).
Uma quadra quadrada de 95 m dá 34 lotes; o teto de 30 nunca foi alcançável. O número era
meu e nunca foi medido.

**Ação:**

1. Remova `LOTES_POR_QUADRA_MEDIANA_MIN/MAX`.
2. Invariante novo, por quadra: `lotes ≈ perímetro_urbanizável / frente_alvo_da_banda`,
   com tolerância de **±25%**. Repare que isto compara a quadra **consigo mesma**, então
   funciona igual num quarteirão de 45 m do `grade` e num de 95 m do `radial`.
3. A quadra sem pátio (o caso raso do `linear`) tem lotes nos **dois** lados do eixo médio,
   não no perímetro inteiro — a conta dela usa o comprimento das duas arestas longas, não o
   perímetro. Trate-a à parte, e escreva por quê.
4. Reporte a fração de quadras fora da tolerância, por cidade. Violação dura acima de,
   digamos, 5% das quadras — uma ou outra quadra degenerada num canto não é bug.
5. Mantenha lotes por quadra (mediana e máximo) como **coluna de relatório**. O número
   continua útil para olhar; ele só deixa de ser porta.

**Validar:** `audit_cidades.py ; echo $?` devolve **0** nas 14 cidades. Sem pipe.

**Risco:** baixo.

---

### C02 · Subir o teto de anéis

**Arquivos:** `config.json`

**Problema:** [1.2](#12-a-profundidade-da-quadra-o-teto-de-anéis-é-que-está-mordendo).
`cidade_geo_vao_anel_alvo_m` pede 95 m de profundidade; o medido é 110–143, porque
`cidade_geo_num_aneis_faixa_por_tamanho.grande` limita em 6 e Jordorstead precisaria de 9.

**Ação:**

1. Suba o teto para `{"pequeno": [2, 4], "medio": [3, 7], "grande": [4, 10]}`. G05 já
   calcula o número ideal a partir do raio; o teto só precisa parar de cortar.
2. Regenere e confira a coluna `larg/prof`: tem que cair de 1,43–1,72 para perto de
   **1,0–1,2** em `radial` e `organica`.
3. ⚠️ Mais anéis quer dizer mais ruas e mais quadras, logo **mais lotes** na mesma cidade.
   Isso muda a densidade que R02 vai calibrar — por isso C02 vem **antes** de R02, e é a
   mesma [armadilha 8](PLANO_POPULACAO_E_ESCALA.md) do documento anterior, agora com um
   segundo motivo.
4. Confira também o custo: Jordorstead já foi de 60 para 240 quadras com o Bloco S. Anote
   quantas ficam depois de C02 e quanto tempo a geração leva.

**Validar:** `audit_cidades.py` com `larg/prof` perto de 1 e código de saída 0.

**Risco:** baixo.

---

### C03 · Destravar R01–R04

**Arquivos:** os do Bloco R do [`PLANO_POPULACAO_E_ESCALA.md`](PLANO_POPULACAO_E_ESCALA.md)

**Ação:** com C01 e C02 prontos, execute **R01, R02, R03 e R04 como estão escritos no
documento anterior**. Nada neles mudou. Dois lembretes que agora valem mais:

- R02 calibra `lotes = k · raio^e` por modelo, **medindo**. Meça **depois** de C02, senão
  você calibra contra uma densidade que vai mudar na semana seguinte.
- R00 continua sendo a regra que mais gente erra: `cartographer/` não pode saber o que é um
  NPC nem uma família. Ele raciocina em **domicílio**; o povoador **conta** o resultado.

**Validar:** o que R04 já pede — a tabela alvo contra medido, e o mapa aberto.

---

## Bloco Y — Validação

### Y01 · Os testes que H e F exigem

**Arquivos:** `tests/test_agenda.py`, `tests/test_mestre.py`, `tests/test_cidades.py`

1. `test_baldes_somam_a_populacao`: a soma dos baldes mais o conjunto de consequência é
   sempre igual ao número de NPCs vivos, depois de parto, morte, casamento, mudança de casa
   e `acordar`. É o invariante que segura H01.
2. `test_jitter_e_deterministico`: o mesmo NPC, com o mesmo id, recebe sempre o mesmo
   desvio. Prova que H03 não quebrou a reprodutibilidade por seed.
3. `test_refeicao_dura_o_mesmo`: com `COMER` lotável (H04), uma refeição continua durando
   `parcelas_refeicao` ticks e custando o mesmo total.
4. `test_nao_esquece_familia`: o teto do grafo (H05) nunca descarta cônjuge, pai, mãe ou
   filho.
5. `test_acao_do_mestre_acorda_npc`: o caso que A03 registrou como impossível.
6. `test_lotes_batem_com_o_perimetro`: o invariante de C01, em código, para os 4 modelos.

### Y02 · W02 do documento anterior

`bench_tick.py` ainda usa `BancoFalso` e portanto **não mede disco**. W02 ficou pendente e
continua valendo palavra por palavra: modo `--com-banco`, com SQLite temporário real, e as
duas colunas lado a lado. Depois de N02 a diferença deve ser pequena — mas "deve ser" não é
um número, e é justamente esse tipo de suposição que este documento passou a sessão inteira
corrigindo.

---

## Anexo — Tabela de medições

Todas feitas em 2026-09-12, commit `e6dd2bf`, mundo sintético de 25.000 NPCs / 60.000
locais / 40 cidades, um dia simulado completo por execução.

### Um dia simulado

| variante | 1 dia | ms/tick médio |
|---|---|---|
| como está hoje | 189,0 s | 131,3 |
| com coabitação em cadência diária (simulado) | 162,5 s | 112,9 |

Por janelas de 240 ticks, hoje: `62 60 89 145 65 367` ms — a última janela (04:00–08:00) é
**6× a primeira**.

### Decisões e custo por hora do dia

| hora | decisões/tick | ms/tick |
|---|---|---|
| 0 | 0 | 49,0 |
| 1 | 60 | 49,8 |
| 2 | 335 | 106,5 |
| 3 | 22 | 49,2 |
| 4 | 0 | 48,7 |
| 5 | 639 | 66,2 |
| **6** | **24.997** | **770,6** |
| **7** | **23.999** | **553,8** |
| 8 | 417 | 67,7 |
| 9–18 | 0 a 417 | 52 a 64 |
| **19** | 6.162 | 168,1 |
| **20** | 8.007 | 200,0 |
| **21** | 9.978 | 230,2 |
| 22 | 884 | 69,3 |
| 23 | 158 | 51,5 |

Total: **~4,6 milhões de decisões por dia**, ou 184 por NPC por dia — uma a cada 8 minutos,
contra 78 minutos de duração média de uma ação medidos no documento anterior.

### Os dez maiores picos

Todos de **25.000 decisões num único tick**: 06:29 a 06:37 (890 a 937 ms) e 08:01
(1.051 ms).

### O piso: um tick com zero decisões

**51,8 ms.** Perfilado (20 ticks), os quatro donos:

| | participação |
|---|---|
| `marriage.processar_coabitacao` | ~46% |
| `consultas_npc.assinatura_dependentes_por_casa` | ~16% |
| `consultas_npc.agrupar_npcs_por_localizacao` (via `social.py`) | ~12% |
| laço de `executar_tick` + `npc_esta_em_dia` × 25.000 | ~10% |

### Grafo social, ao fim de um dia

| | valor |
|---|---|
| relacionamentos por NPC, mediana | **0** |
| relacionamentos por NPC, máximo | **14** |

É a medição que desmente o diagnóstico de A07: o grafo não cresceu, logo não é ele que
domina `processar_coabitacao`.

### As 14 cidades depois dos Blocos S e L

| cidade | modelo | quadras | lotes | l/quadra | máx/qd | sem frente % | larg/prof | lotes/raio² |
|---|---|---|---|---|---|---|---|---|
| Belinhaven | linear | 23 | 401 | 18 | 23 | 0,0 | 4,74 | 0,0047 |
| Cidade da Lua | grade | 311 | 5.295 | 13 | 32 | 0,0 | 1,06 | 0,0090 |
| Cidade das Flores | organica | 79 | 2.799 | 30 | 96 | 0,0 | 1,45 | 0,0123 |
| Cidade dos Sonhos | grade | 323 | 3.005 | 9 | 26 | 0,0 | 1,08 | 0,0085 |
| Cidade dos Ventos | grade | 178 | 1.910 | 10 | 26 | 0,0 | 1,08 | 0,0086 |
| Corarfield | linear | 87 | 1.281 | 15 | 20 | 0,0 | 7,15 | 0,0018 |
| Elorfield | linear | 67 | 969 | 14 | 20 | 0,0 | 4,80 | 0,0037 |
| Fenelburgo | organica | 209 | 8.361 | 34 | 117 | 0,0 | 1,43 | 0,0117 |
| Irenburgo | grade | 394 | 8.195 | 21 | 30 | 0,0 | 1,07 | 0,0131 |
| Jordorstead | radial | 240 | 11.103 | 41 | 94 | 0,0 | 1,66 | 0,0113 |
| Kelandor | linear | 61 | 716 | 12 | 16 | 0,0 | 3,90 | 0,0046 |
| Keldorstead | radial | 126 | 5.650 | 40 | 75 | 0,0 | 1,72 | 0,0110 |
| Pelvermont | radial | 36 | 1.445 | 34 | 66 | 0,0 | 1,57 | 0,0134 |
| Tordordor | radial | 108 | 4.267 | 34,5 | 67 | 0,0 | 1,54 | 0,0114 |

`bowtie_q`, `bowtie_l`, `anel_x` e `fora_muro` são **0** em todas as 14. A única violação é
a mediana contra o teto de 30, que C01 remove.

---

## Registro de execução

| Tarefa | Data | Observação / número medido |
|---|---|---|
| H01 | 2026-09-12 | Agenda virou balde/consequência/sem-agenda em `EstadoDoMundo`; laço de `executar_tick` lê só os "devidos". Invariante testado tick a tick (`test_baldes_somam_a_populacao`). Medido isolado (25.000 NPCs, 1 dia): 189,0s→**177,9s** (131,3→**123,5 ms/tick**), decisões médias 3196,7/tick (ainda alto — H02/H03/H04 atacam o resto). Suíte: 144 passed. |
| H02 | 2026-09-12 | Três itens: (1) `processar_coabitacao` ganhou cadência diária (`casamento_hora`, config nova) via `_rotinas_diarias` — saiu de `NPCSocialManager.processar_interacoes`; `casamento_chance_coabitacao` recalibrada 0,00135→0,857 (mesma probabilidade composta 1-(1-p)^1440 já usada na config). (2) `social.py` usa `mundo.npcs_por_localizacao` (índice mantido) em vez de `NPCUtils.agrupar_npcs_por_localizacao`, filtrando dormindo só nos locais com ≥2 moradores. (3) `EstadoDoMundo.casas_sujas` (marcado por mudar_casa/registrar_npc/remover_npc/reindexar_casa_do_npc/mudar_cidade, e por `processar_crescimento` na transição criança→adulto, que muda `eh_dependente()` sem mudar de casa) substitui a assinatura calculada sobre TODAS as casas; `NPCUtils.assinatura_dependentes_por_casa` removida (ficou sem chamador). Medido (25.000 NPCs, 1 dia, acumulado com H01): 177,9s→**122,4s** (123,5→**85,0 ms/tick**). Testes novos: `test_crescer_para_adulto_suja_a_casa_sem_passar_pelas_portas_de_mundo`, `test_coabitacao_so_roda_na_cadencia_diaria_nao_a_cada_tick`. Suíte: 146 passed. |
| H03 | | |
| H04 | 2026-09-13 | CUIDAR_PROLE, CONSTRUIR e COMER entram em `ACOES_LOTEAVEIS`. CUIDAR_PROLE/CONSTRUIR generalizados por inteiro (agendamento + efeito em lote, mesma matemática de `minutos_ate_cruzar`); CONSTRUIR usa `candidatos_extra` (agenda.py continua sem ler `mundo`, R-F01) porque `obra.integridade` mora em `mundo.locais`. COMER é mais conservador: o efeito em lote só aplica o ramo de PREÇO CHEIO (nunca parcial/sopão), e `NPCActionManager.minutos_seguros_para_pular_comer` capa o bloco pelo saldo do pagador — nunca deixa o bloco ultrapassar o dinheiro disponível. Testes de equivalência bloco-vs-minuto-a-minuto pras três (`tests/test_agenda_loop.py`). Medido (25.000 NPCs, 1 dia, acumulado com H01-H03): 110,0s→**62,6s** (76,4→**43,5 ms/tick**); horas 6/7 (as piores) caíram de (18069, 24467) pra **(9022, 5076)** decisões/tick médias. **Achado novo, fora do escopo literal de H04:** horas 19-21 continuam altas (~6000-10000) — `Acao.SOCIALIZAR` é a única ação que continua fora de `ACOES_LOTEAVEIS` (não generalizada de propósito: sua utilidade não cruza um limiar fixo, decresce suavemente até perder a competição de utilidade pra outra ação — não é o mesmo tipo de "cruzamento calculável" das outras três), e sua janela de bônus (happy hour, fim do expediente até o sono) cobre exatamente 19h-21h. Não confirmado por profiling direto, só por leitura de código — deixado para o dono do projeto decidir se vale medir/generalizar depois. `pico_decisoes_tick` continua em 25.000: é o PRIMEIRO tick da simulação (toda a população nasce em `npcs_sem_agenda`), não uma manada recorrente — `bench_avanco.py` não distingue os dois casos hoje. |
| H05 | 2026-09-13 | `NPCSocialManager.processar_poda_de_relacionamentos` (cadência diária, `relacionamentos_poda_hora`): decai afinidade não protegida 1 ponto/dia em direção a zero (some ao chegar lá) e, acima do teto (`relacionamentos_max_por_npc`=150, Dunbar), descarta os mais fracos primeiro. Nunca cônjuge/pais/filhos (resolvidos via `mae_id`/`pai_id`, com um `id->npc` montado uma vez por chamada — O(NPCs) 1x/dia, não por tick) nem vínculo forte (afinidade >= `vinculo_limiar_amigo`). `salvar_completo` em lote só pros NPCs cuja lista mudou. 4 testes novos (proteção de família, decaimento, vínculo forte, ordem de descarte). Não medido em bench_avanco isolado — roda 1x/dia (não por tick) e o próprio plano já classifica como "não é o que trava D13" e "Risco: baixo"; o custo amortizado (O(NPCs) uma vez a cada 1440 ticks) é desprezível frente ao orçamento por tick. Suíte: 156 passed. |
| H06 | | |
| F01 | 2026-09-13 | Fila `mestre_acoes_pendentes` (payload JSON, criada_em, aplicada_em). `MestreManager.aplicar_acoes` (processo do Flask) filtra comandos inválidos e ENFILEIRA (`db.mestre.enfileirar_acoes`); `drenar_e_aplicar(mundo)` (novo método) é o lado da simulação — só `run_simulation.py` chama, a cada volta do laço (`drenar_acoes_do_mestre`, INCLUSIVE pausado, antes do branch de pausa), com o `EstadoDoMundo` vivo. Todas as 4 classes em `acoes/*.py` passaram a receber `mundo` em vez de `db`. `_avaliar_expansao_fora_do_processo`/`EstadoDoMundo` de trabalho de M02 apagados. `LOCAIS_VERSAO`/`recarregar_locais` NÃO tocados — ficam vestigiais pro caminho do Mestre (que agora aplica no mesmo processo) mas continuam existindo pro "caminho contrário" que o plano cita; decidi NÃO fazer `registrar_local`/`desativar_local` incrementá-lo por padrão porque `_executar_construir` chama `registrar_local` TODO TICK durante obra — incrementar ali reintroduziria o reload de 60 mil locais por tick que M01 existia pra evitar. Resposta HTTP virou assíncrona (`enfileirado: True`, não `aplicado`); `db.mestre.ha_fila_nao_drenada(10s)` avisa se a fila parece parada (run_simulation.py não rodando) sem bloquear a requisição. `dashboard.js` atualizado pro texto assíncrono. Métodos mortos removidos: `RepositorioNPC.ajustar_saude_e_humor/atualizar_local_trabalho/atualizar_casa`, `RepositorioLocal.existe`. |
| F02 | 2026-09-13 | `abrir_obra` ganha `SpecObra` (dataclass — o método já tinha 8 parâmetros, acima do limite de 5 da ARQUITETURA.md; a tarefa foi o motivo de finalmente agrupar) e dois parâmetros novos: `dono_npc: Optional[NPC] = None` (sem dono: `perto_de=None`, `npc_id=""` na reserva do lote, `Local.dono_npc_id=""`) e `pronta: bool = False` (nasce com `status=1, integridade=100`, e `lotes.concluir` já na hora — sem dono não existe "alguém construindo"). `CriarLocal` chama `abrir_obra(cidade_id, spec, dono_npc=None, pronta=True)` de verdade — a reserva direta de lote e `_avaliar_expansao_fora_do_processo` de M02 somem (dependia de F01 pra ter `mundo` disponível). Callers existentes (`housing.py`, `urbanismo.py._abrir_estabelecimento`, `tests/test_expansao_urbana.py`) atualizados pro novo formato. |
| F03 | 2026-09-13 | `mundo.acordar(npc)` chamado por AFETAR_NPC (mudou saúde/humor), REATRIBUIR_NPC (mudou trabalho/casa — só se algo de fato mudou) e DESTRUIR_LOCAL (todo mundo que morava, trabalhava OU só estava no local: `npcs_por_casa`/`npcs_por_localizacao`, O(1) via índice mantido, mais uma varredura O(NPCs) pra trabalho, que não tem índice próprio — aceitável, ação rara disparada pelo jogador). `AcaoDeMundo.encontrar_npc` (novo helper na base) resolve id->NPC por varredura, pelo mesmo motivo. `REATRIBUIR_NPC` passou a usar `mundo.mudar_casa` (porta de A04) em vez de SQL direto — sem isso os índices em memória (`npcs_por_casa`) ficariam desatualizados até o próximo `recarregar_habitantes()`, um bug de armadilha 12 que só apareceria batendo de frente com o Mestre. `test_mestre.py` reescrito inteiro (20 testes) usando o `BancoFalso`/`mundo_de` compartilhado de `tests/mundo_sintetico.py` em vez de dublês só deste arquivo — ganhou `RepositorioMestreFalso`, `RepositorioMundoFalso`, e `RepositorioFalso.carregar` (meta). Suíte: 164 passed. |
| C01 | 2026-09-14 | `audit_cidades.py` ganha `_lotes_vs_frente_alvo`: substitui o teto absoluto de L04 (mediana em [4,30]) por auto-consistência por quadra — `lotes ≈ perímetro_das_arestas_com_lote / frente_alvo_da_banda`, ±25%, violação dura acima de 5% das quadras da cidade. "Perímetro só das arestas com lote" (via a propriedade `aresta` de cada feature lote) trata a quadra sem pátio e uma aresta `sem_via` de graça, sem caminho à parte. ACHADO: quadras recursivamente cortadas (`_cortar_quadra_funda`, Q01 Passo 2 — quadra funda demais vira duas) reusam os mesmos índices de aresta 0-3 pras DUAS metades, então "soma por índice único" sub-conta o perímetro real — detectável de fora porque toda quadra cortada tem pelo menos um lote com `classe_frente == "servico"` (a aresta do corte); essas são contadas à parte (`quadras_cortadas`) e não entram no invariante, já que sua sub-geometria não sobrevive à exportação GeoJSON. Mediana/máximo viram coluna de relatório. `audit_cidades.py ; echo $?` → 0 nas 14 cidades reais (medido: fora_alvo% caiu de 25-42% pras radial/organica, todas as violações eram quadras cortadas, pra 0,0% em todas). |
| C02 | 2026-09-14 | `cidade_geo_num_aneis_faixa_por_tamanho` subiu de `{pequeno:[2,3], medio:[3,4], grande:[4,6]}` pra `{pequeno:[2,4], medio:[3,7], grande:[4,10]}` — G05 já calculava o ideal a partir do raio, o teto só cortava (Jordorstead precisava de 9, ficava preso em 6). Medido: Jordorstead aneis 6→9 (vao_m 142→99, larg/prof 1,66→1,24), Keldorstead 4→7 (larg/prof 1,72→1,25), Fenelburgo 6→8 (1,43→1,31), Tordordor 4→5 (1,54→1,18) — mais perto de ~1,0 (quase quadrada), sem chegar exatamente lá (a largura é outra fórmula, S01; C02 só parou de cortar a profundidade). Geração das 15 cidades: ~5,9s. Determinismo (md5sum, duas gerações): idêntico. **Dois achados de geometria, expostos por destravar bandas mais profundas, corrigidos nesta tarefa (não são regressão de C02 — sempre existiram, só nunca tinham as condições certas pra aparecer):** (1) `tests/test_cidades.py::test_nenhum_poligono_auto_intersectante` — um lote com dois vértices coincidentes (corte de canto quase-degenerado) passava despercebido por `e_quad_simples` (colinearidade conta como "não cruza", de propósito) e pelo piso de ÁREA (a área do quase-triângulo resultante pode ser grande); `gerador.py`/`expansao.py` ganham o mesmo guard `quad.aresta_minima(poligono) < 0,1m` que `distribuicao.py` já usava pra footprint de edifício. (2) `tests/test_cidades.py::test_praca_sem_lote_dentro` — o anel do núcleo cívico é concêntrico na ORIGEM, mas `centro_praca` pode estar deslocado dela; a fórmula de `raio_nucleo_candidato` não reservava a perturbação (`amplitude_m`) do próprio anel na direção da praça, só a faixa de domínio — com bandas mais estreitas (mais anéis no mesmo raio_m) isso deixava de ser folga suficiente. `radial.py` passa a somar `amplitude_m` na fórmula. Suíte completa: 164 passed. |
| C03 | | |
| Y01 | | |
| Y02 | | |
