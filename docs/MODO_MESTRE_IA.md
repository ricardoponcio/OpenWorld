# 🎭 Modo Mestre de IA — Rascunho de Design

> Documento de apoio à **Frente 5** do [`ROADMAP.md`](ROADMAP.md). Este é o design mais em aberto
> das 6 frentes — o objetivo aqui é registrar o que já existe reaproveitável, o que falta decidir, e
> uma proposta inicial de arquitetura para servir de ponto de partida da conversa, não uma
> especificação fechada.

## O que o autor pediu

> "Adicionar um segundo 'modo temporal', o modo mestre de IA, onde poderemos pausar o tempo e o
> mestre usará o contexto atual para gerar narração em tempo real, e poderemos colaborar com a
> aventura e avançar o tempo o quanto for decidido, além de ver posteriormente os efeitos disso para
> a narração."

Decompondo em capacidades concretas:
1. **Pausar o relógio da simulação** (já existe: `mundo_meta.simulacao_pausada`, toggle no dashboard).
2. **O Mestre de IA narra usando o contexto atual** do mundo (NPCs, locais, relações, eventos recentes).
3. **Colaboração**: o jogador (o autor, mestre humano de RPG de mesa) interage/conversa com a IA, não
   é só uma geração unidirecional.
4. **Avançar o tempo em quantidade escolhida** (não necessariamente 1 tick — pode ser "avance 3 horas").
5. **Ver os efeitos depois**: após o avanço, revisar o que aconteceu no mundo durante esse intervalo
   e trazer isso de volta para a narração (fechar o ciclo).

## O que já existe e é reaproveitável

A revisão do código encontrou um **protótipo funcional de boa parte do backend** deste modo,
hoje desconectado do loop principal e do dashboard:

| Peça necessária | Já existe como | Arquivo |
|---|---|---|
| Coleta de contexto do mundo em JSON (NPCs, locais, relações, eventos recentes, eventos ativos) | `run_storyteller()` | `builder/storyteller.py` |
| Prompt estruturado pedindo evento + ações de mundo em JSON | Prompt inline em `run_storyteller()` | `builder/storyteller.py` |
| Cliente LLM com fallback determinístico se Ollama offline | `AIStorytellerClient.gerar_evento_global` | `engine/ai/storyteller.py` |
| Aplicação de ações de mundo no banco (criar/destruir local, realocar NPC, afetar saúde/humor) | Bloco `for acao in evento.get('acoes_mundo', [])` | `builder/storyteller.py` |
| Persistência de eventos globais com duração e modificadores de utilidade | Tabela `eventos_globais` + `GlobalEventManager` | `engine/mechanics/events.py` |
| Pausa/retomada da simulação | `mundo_meta.simulacao_pausada` + `/api/toggle_pause` | `web/dashboard.py` |
| Histórico de eventos do mundo para "ver os efeitos depois" | Tabela `eventos` (eventos por NPC) + `eventos_globais` | `engine/database.py` |

**Conclusão prática**: este modo não começa do zero. O trabalho principal é **orquestração e
interface** (transformar um script de disparo único em um ciclo interativo integrado ao dashboard),
não reconstruir a geração de conteúdo via IA.

## Lacunas identificadas (o que falta construir)

1. **Ciclo de ida e volta, não disparo único.** Hoje `run_storyteller` gera *um* evento e aplica.
   O Modo Mestre precisa de uma conversa: o jogador propõe/pergunta, a IA responde narrativamente,
   o jogador decide uma ação, a IA a incorpora — isso é um histórico de "chat de mesa", diferente do
   modelo atual de "um JSON por chamada".
2. **Integração real com a pausa.** O script hoje roda independente do estado de
   `simulacao_pausada` — precisa checar/forçar esse estado ao entrar no Modo Mestre, e o
   `run_simulation.py` precisa respeitar isso (já respeita a pausa para o tick físico; falta decidir
   se o Modo Mestre *é* uma forma de pausa ou um estado à parte).
3. **"Avançar o tempo o quanto for decidido."** Hoje o avanço de tempo só acontece tick a tick
   dentro do loop físico (`run_simulation.py`) — não existe um comando de "rode N minutos/horas de
   uma vez e pare". Depende da Frente 4 (tempo 1:1) para ter granularidade fina o suficiente para
   isso ser uma unidade útil (hoje um "tick" é sempre 15 minutos fixos).
4. **"Ver os efeitos depois."** Precisa de uma rotina que, após o avanço de tempo, colete os eventos
   gerados nesse intervalo (`eventos`/`eventos_globais` com timestamp dentro da janela) e os devolva
   à IA como novo contexto, para ela narrar o que aconteceu — hoje `run_storyteller` só olha para
   "os últimos 10 eventos", sem noção de janela de tempo.
5. **Superfície de interface.** Precisa de um lugar no dashboard (aba/painel "Mestre de IA") com uma
   caixa de conversa e um controle de "avançar tempo", em vez de rodar por terminal.
6. **Consistência de tema.** `storyteller.py` usa `"Cyberpunk"` como tema padrão; o resto do mundo
   (`populate.py`) usa `"Fantasia Medieval"`. O tema deveria vir de um único lugar (provavelmente o
   `world_manifest.json` ou o config único da Frente 1), não ser passado solto por script.

## Proposta inicial de arquitetura (para discussão, não decisão fechada)

```
[Dashboard: aba "Mestre de IA"]
        │
        │ 1. Jogador pausa a simulação (reusa toggle_pause existente)
        ▼
[Novo endpoint /api/mestre/mensagem]
        │
        │ 2. Coleta contexto atual (reaproveita a lógica de run_storyteller,
        │    promovida de script para função de biblioteca)
        ▼
[Novo AIGameMasterClient — evolução de AIStorytellerClient]
        │
        │ 3. Prompt inclui: contexto do mundo + histórico da conversa atual
        │    (não só "gere 1 evento": suporta narração livre + comandos de mundo)
        ▼
[Resposta: narração em texto + (opcional) ações de mundo estruturadas]
        │
        │ 4. Ações de mundo aplicadas via as mesmas rotinas de
        │    CRIAR_LOCAL/DESTRUIR_LOCAL/REATRIBUIR_NPC/AFETAR_NPC já existentes
        ▼
[Jogador decide: continuar conversando OU avançar tempo]
        │
        │ 5. Novo endpoint /api/mestre/avancar_tempo?quantidade=X
        │    → roda X ticks do GameLoop de uma vez (despausado internamente,
        │      sem o sleep normal do run_simulation.py)
        ▼
[Novo resumo automático: coleta eventos gerados na janela de tempo que passou]
        │
        │ 6. Esse resumo volta como contexto novo para a IA narrar as consequências
        ▼
[Ciclo se repete]
```

Pontos que essa proposta deixa em aberto de propósito, para decidir com o autor antes de implementar:

- **Onde mora o histórico da conversa com o Mestre?** Tabela nova (`mestre_conversas`) ou é
  transiente (só na sessão do navegador)? Se o autor quer retomar uma sessão de RPG depois, precisa
  persistir.
- **O Mestre pode agir sozinho enquanto o tempo avança rápido (fast-forward), ou só narra quando
  explicitamente chamado?** Isto é, ao "avançar tempo", o Modo Mestre gera automaticamente um evento
  a cada tanto (como hoje faria batch), ou fica em silêncio até o jogador pedir um resumo?
- **Como equilibrar a autonomia da IA em `AFETAR_NPC`/`DESTRUIR_LOCAL` com o desejo de "colaborar"?**
  O prompt atual já pede para a IA "não gerar desastres aleatórios sem justificativa" — mas talvez o
  Modo Mestre deva propor a ação e pedir confirmação do jogador antes de aplicar no mundo, em vez de
  aplicar direto como o script batch faz hoje.
- **Multi-modelo**: o resto do projeto já assume Ollama local (`qwen2.5-coder:7b`) com fallback
  procedural. Para narração livre em prosa, esse modelo (voltado a código) pode não ser o ideal —
  vale reavaliar o modelo usado especificamente para este modo quando chegar a hora.

## Dependências
- **Depende da Frente 4** para o "avançar o tempo o quanto for decidido" ter uma unidade útil
  (minutos, não só blocos de 15 min).
- **Toca a Frente 3** (comportamento dos NPCs): `AFETAR_NPC` é hoje a única via que escreve os
  humores "mortos" do enum (Pânico, Medo, Angustiado) — o Modo Mestre pode ser exatamente o lugar
  certo para esses estados finalmente serem usados de forma intencional/narrativa, em vez de o motor
  tentar simulá-los sozinho.

## Status
🔴 Não iniciado. Nenhuma decisão de arquitetura fechada — este documento existe para não perder o
que já foi levantado, e para servir de pauta da próxima conversa sobre este tema.
