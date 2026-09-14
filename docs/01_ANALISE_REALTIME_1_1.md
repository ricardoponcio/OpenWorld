# 🕒 Proposta de Implementação: Simulação em Tempo Real (Speed 1:1)

> ⚠️ **Decisão revista em 2026-09-09**: a Abordagem 3 (Engrenagens Híbridas) abaixo foi cogitada
> primeiro, mas **rejeitada pelo autor** ao ver o plano concreto — o motor continuaria amarrado a
> múltiplos de 15 minutos por baixo dos panos (só escondido um nível abaixo do tick visível), o que
> "fingiria" o 1:1 em vez de implementá-lo de verdade. **A Abordagem 2 (Rebalanceamento Total),
> descrita e descartada abaixo por risco de precisão, foi a que acabou implementada** — o tick virou
> genuinamente 1 minuto e todo número de `config.json` foi recalculado (taxas ÷15, probabilidades por
> fórmula composta, durações ×15) em vez de dividido ingenuamente. Na prática o "risco de precisão"
> citado abaixo só se manifestou num único lugar concreto (dinheiro, que virou `float`), não no
> sistema todo. Detalhes de execução e verificação estão na **Frente 4** do [`ROADMAP.md`](ROADMAP.md);
> o vínculo com o "Modo Mestre de IA" está na **Frente 5**.

Este documento descreve a análise técnica e as possíveis abordagens para adaptar o ecossistema do *OpenWorld Engine* a uma proporção de tempo 1:1 com a vida real (onde 1 minuto na vida real equivale a 1 minuto no jogo).
Este formato é ideal para rodar o Dashboard como "pano de fundo" imersivo em uma sessão física de RPG de mesa, sincronizando as horas do jogo com a duração da aventura real.

## O Desafio Matemático e Arquitetural

Atualmente, o núcleo (`engine/core.py`) avança a física e as tomadas de decisão da IA usando `timedelta(minutes=15)` a cada *tick*.
Toda a economia (salários), biologia (cansaço, gravidez) e socialização estão calibradas para acontecerem em blocos de 15 em 15 minutos de simulação.

Alterar isso exige escolher entre performance visual (Dashboard) e rebalanceamento pesado (Banco/Config). Abaixo estão os cenários:

---

### ❌ Abordagem 1: O "Congelamento" (Manter Ticks de 15 min)
O método mais simples e sem alteração na lógica da Engine.
*   **Como Funciona:** No arquivo `run_simulation.py`, a função de atraso do loop (`time.sleep()`) seria alterada de 2 segundos para 900 segundos (15 minutos).
*   **Impacto no Backend:** Código continuaria o mesmo, precisando de 0 horas de refatoração.
*   **Impacto na Imersão (Problema):** O mapa da UI ficaria estático por quase 15 minutos sem nada acontecer. De repente, todos os NPCs se teletransportariam na tela ao mesmo tempo realizando a próxima ação (ex: ir do trabalho para casa instantaneamente). O mundo pareceria "travado".

---

### ⚠️ Abordagem 2: Rebalanceamento Total (1 Tick = 1 Minuto)
Alteração profunda na física do sistema, rodando 1 tick a cada minuto na simulação e 1 minuto na vida real.
*   **Como Funciona:** O `core.py` passaria a somar `timedelta(minutes=1)`. O `run_simulation.py` esperaria 60 segundos por tick em speed 1x.
*   **Impacto no Backend:**
    *   **Metabolismo:** As variáveis no `config.json` precisariam ser divididas por 15. Se o `energia_perda` era 1.8 por tick, teria que virar 0.12.
    *   **Durabilidade de Eventos:** Prazos medidos em ticks (como gravidez, que dura 192 ticks) precisariam ser convertidos na mesma proporção geométrica (ex: 2880 ticks).
*   **Impacto no Banco de Dados:** Essa abordagem forçaria cálculos com números fracionados muito pequenos na base SQLite (ex: pagar um salário fracionado a cada minuto), o que pode causar instabilidade de arredondamento (`float precision issues`).

---

### 🏆 Abordagem 3: Engrenagens Híbridas (Recomendada)
A solução mais segura, elegante e visualmente fluida. Nós separamos as lógicas por "frequência".

*   **Como Funciona:**
    1.  O `core.py` e a movimentação rodam a **1 Tick = 1 Minuto** no tempo de jogo e no tempo real (`sleep(60.0)` ou configurável).
    2.  O Cartógrafo e as decisões de **movimento** do NPC atualizam a cada minuto. O Dashboard verá os pontos caminhando de uma casa para a rua, e da rua para o mercado lentamente, como num "formigueiro" contínuo.
    3.  A física dura e economia rodariam protegidos por um condicional no `core.py`:
        ```python
        if engine.data_simulada.minute % 15 == 0:
            NPCBiologyManager.aplicar_fome_e_cansaço()
            JobMarket.pagar_salarios()
        ```
*   **Por que escolher este caminho:**
    *   Ele **mantém todas as variáveis de balanceamento do `config.json`** idênticas e intactas. Não precisaremos rebalancear moedas nem biologia.
    *   O jogador no frontend verá a cidade viva, se mexendo progressivamente minuto a minuto.
    *   Mantém o banco de dados saudável e rápido, realizando processos pesados e I/O de disco com cálculos inteiros apenas de 15 em 15 passos da engrenagem.

---

### Conclusão e Próximos Passos
Se e quando decidir ativar a **Speed 1:1**, recomendamos a implementação da **Abordagem 3**.
Requer modificações apenas pontuais no `engine/core.py` e ajustes sutis de animação/pathing, mantendo a retrocompatibilidade com sua estrutura atual de RPG.
