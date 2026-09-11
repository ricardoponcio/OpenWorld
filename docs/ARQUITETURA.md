# 🏛️ Arquitetura do OpenWorld

> **Este é o documento de referência para escrever código novo neste projeto.**
> Leia antes de implementar qualquer feature. Ele não descreve o que o código *é* hoje —
> descreve o que ele **deve ser**, e o que toda contribuição nova precisa respeitar.
>
> Quem vai executar a limpeza do que já existe usa o documento irmão,
> [`PLANO_REFATORACAO.md`](PLANO_REFATORACAO.md).
> Quem quer saber *o que* construir usa [`ROADMAP.md`](ROADMAP.md) e
> [`PLANO_EVOLUCAO_V2.md`](PLANO_EVOLUCAO_V2.md).
> **Este documento responde *como* construir.**

**Criado em:** 2026-09-11

---

## Índice

- [1. O que é o sistema](#1-o-que-é-o-sistema)
- [2. As camadas e a regra de dependência](#2-as-camadas-e-a-regra-de-dependência)
- [3. Os cinco princípios inegociáveis](#3-os-cinco-princípios-inegociáveis)
- [4. Limites de tamanho](#4-limites-de-tamanho)
- [5. Configuração](#5-configuração)
- [6. Tipos e vocabulário: quando usar enum](#6-tipos-e-vocabulário-quando-usar-enum)
- [7. Classes: estático, instância ou função](#7-classes-estático-instância-ou-função)
- [8. Acesso a dados](#8-acesso-a-dados)
- [9. Erros, logs e falhas](#9-erros-logs-e-falhas)
- [10. Frontend](#10-frontend)
- [11. Determinismo e geração procedural](#11-determinismo-e-geração-procedural)
- [12. Documentação no código](#12-documentação-no-código)
- [13. Testes](#13-testes)
- [14. Receitas: como adicionar X](#14-receitas-como-adicionar-x)
- [15. Lista de padrões proibidos](#15-lista-de-padrões-proibidos)
- [16. Checklist de revisão](#16-checklist-de-revisão)

---

## 1. O que é o sistema

OpenWorld é um **simulador de mundo persistente** para RPG de mesa. Três programas
independentes compartilham um arquivo SQLite e um conjunto de artefatos em disco:

```
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  builder/            │   │  run_simulation.py   │   │  run_dashboard.py    │
│  cartographer/       │   │                      │   │                      │
│  (GÊNESE)            │   │  (SIMULAÇÃO)         │   │  (OBSERVAÇÃO)        │
│                      │   │                      │   │                      │
│  roda uma vez,       │   │  processo longo,     │   │  Flask, só lê —      │
│  produz o mundo      │   │  único dono do       │   │  nunca instancia     │
│                      │   │  estado em memória   │   │  SimulationEngine    │
└──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘
           │                          │                          │
           └──────────────┬───────────┴──────────────────────────┘
                          ▼
        database/openworld.db · mapa_composto.npz · world_manifest.json
                    · cidades/*.geojson · features/*.geojson
```

### Regra de processo (importante, e já violada no passado)

**Só `run_simulation.py` é dono da `SimulationEngine`.** O dashboard **não** tica a
simulação nem escreve estado de NPC. Quando o dashboard precisa que algo aconteça no
mundo (pausar, mudar velocidade, avançar N minutos no Modo Mestre), ele **sinaliza pela
tabela `mundo_meta`** e o `run_simulation.py` consome o sinal no seu próprio laço.

Se você está tentado a instanciar uma `SimulationEngine` dentro de uma rota Flask,
pare: o resultado são dois donos do mesmo estado, divergindo em memória.

---

## 2. As camadas e a regra de dependência

```
        ┌───────────────────────────────────────────────────┐
        │  web/           builder/        run_*.py          │   APRESENTAÇÃO
        │  (rotas, CLI, orquestração de scripts)            │   e ENTRADA
        └──────────────────────┬────────────────────────────┘
                               │ depende de ▼
        ┌───────────────────────────────────────────────────┐
        │  engine/mechanics/     cartographer/cities/        │   DOMÍNIO
        │  engine/ai/            cartographer/world/         │   (regras)
        └──────────────────────┬────────────────────────────┘
                               │ depende de ▼
        ┌───────────────────────────────────────────────────┐
        │  engine/models.py    engine/tempo.py               │   MODELO
        │  cartographer/cities/modelos/base.py               │   (vocabulário)
        └──────────────────────┬────────────────────────────┘
                               │ depende de ▼
        ┌───────────────────────────────────────────────────┐
        │  engine/repositorios/  engine/database.py          │   INFRAESTRUTURA
        │  config/  engine/logger.py  engine/caminhos.py     │
        └───────────────────────────────────────────────────┘
```

### A regra

**A seta aponta só para baixo.** Uma camada nunca importa de uma camada acima dela.

| Camada | Pode importar de | **Nunca** importa de |
|---|---|---|
| Infraestrutura | stdlib, numpy | qualquer camada acima |
| Modelo | Infraestrutura | Domínio, Apresentação |
| Domínio | Modelo, Infraestrutura | Apresentação |
| Apresentação | tudo abaixo | outra apresentação (web não importa builder) |

### Corolários práticos

- **`engine/mechanics/` não contém SQL.** Ele fala com repositórios.
- **`web/` não contém regra de simulação.** Ele lê estado e serializa.
- **`cartographer/` não conhece NPC.** Ele produz terreno e geometria; a engine consome.
- **`engine/` não conhece Flask.** Nunca `from flask import ...` dentro de `engine/`.
- Se você precisa de um `import` **dentro de uma função** para quebrar um ciclo, o ciclo
  é um sintoma: as duas coisas estão na camada errada. Corrija a camada, não o import.

### Onde colocar um arquivo novo

| Se ele… | Vai em |
|---|---|
| define um tipo, um enum ou um dataclass de domínio | `engine/models.py` ou módulo próprio no nível de `engine/` |
| aplica uma regra de simulação a cada tick | `engine/mechanics/` |
| decide quanto um NPC quer fazer algo | `engine/mechanics/utilidade/` |
| lê ou escreve no banco | `engine/repositorios/` |
| gera terreno, continente, clima | `cartographer/world/` ou `cartographer/math/` |
| gera o traçado de uma cidade | `cartographer/cities/modelos/` |
| fala com o LLM | `engine/ai/` |
| expõe um endpoint HTTP | `web/rotas/` |
| roda uma vez para construir o mundo | `builder/` |
| é diagnóstico manual, fora do runtime | `builder/fix/` (documentado como tal) |

---

## 3. Os cinco princípios inegociáveis

### P1 · Um arquivo, uma razão para mudar

Se você consegue descrever o que um arquivo faz usando "e", ele provavelmente deveria ser
dois arquivos. `engine/utils.py` era o exemplo ruim: geometria **e** consultas de NPC
**e** classificação de local **e** importação de manifesto.

O nome do arquivo tem que dizer o assunto. **`utils.py`, `helpers.py`, `common.py` e
`misc.py` estão proibidos** — são nomes que convidam qualquer coisa a entrar.

### P2 · Um método, uma decisão

Um método faz uma coisa e a faz inteira. Se o corpo tem comentários numerados
(`# 1. ...`, `# 2. ...`), cada número é um método privado esperando para nascer.

**Bom** (`engine/mechanics/decay.py`):
```python
def processar_desgaste(engine):
    cfg = InfrastructureManager._cfg(engine)
    for local_id, local in list(engine.locais.items()):
        ...
        local.integridade = max(0.0, local.integridade - taxa)
        engine.db.salvar_local(local)
        InfrastructureManager._aplicar_consequencias(engine, local, local_id, cfg)
```
Lê-se de cima a baixo. O que cada etapa faz por dentro fica no privado com o nome da
etapa.

### P3 · Nenhum número ou string de domínio no meio da lógica

Todo valor que um jogador ou um game designer poderia querer ajustar vive em
`config.json`. Todo valor com significado de código vive numa constante nomeada no topo
da classe ou do módulo.

```python
# ❌ errado
if npc.fome > 90:
    npc.saude -= 0.5

# ❌ ainda errado — o nome está ali, mas o valor continua no código
FOME_INANICAO = 90
if npc.fome > FOME_INANICAO:

# ✅ certo — é parâmetro de balanceamento, logo é config
limiar = cfg_get(cfg_bio, "inanicao_fome_limiar")
if npc.fome > limiar:
```

**Como decidir:**

| Pergunta | Resposta | Destino |
|---|---|---|
| "Um game designer mexeria nisso pra balancear?" | sim | `config.json` |
| "Mudar isso muda o mundo gerado?" | sim | `config.json` (com aviso na docstring) |
| "É um limite estrutural do código?" (ex.: escala 0–100) | sim | constante de módulo |
| "É um detalhe de implementação?" (ex.: offset de ruído) | sim | constante de classe, documentada |
| "Aparece mais de uma vez?" | sim | **sempre** extrair, seja qual for o caso |

### P4 · Texto de domínio é enum, não string

Se um valor de texto tem um conjunto fechado e conhecido de possibilidades, ele é enum.
Ver [Seção 6](#6-tipos-e-vocabulário-quando-usar-enum).

### P5 · Falhar alto, não baixo

Configuração ausente derruba a simulação. Campo ausente derruba a leitura. Dado
corrompido aparece no log.

O projeto **já tem** essa política escrita em `config/resolver.py`:

> `cfg_get()`: substituto de `dict.get(chave, default)` que NUNCA usa valores padrão
> silenciosos. Se a chave estiver ausente, lança `KeyError` imediatamente — interrompendo
> a simulação com uma mensagem clara sobre o que falta, em vez de rodar silenciosamente
> com parâmetros errados.

O que não pode acontecer é o que aconteceu: alguns módulos continuarem usando
`cfg["chave"]` ou `cfg.get("chave", 0.33)`. Um default silencioso num parâmetro de
balanceamento significa que o `config.json` mente sobre o que a simulação está fazendo.

---

## 4. Limites de tamanho

| Unidade | Limite | O que fazer ao estourar |
|---|---|---|
| Método / função | **40 linhas** | extrair privados nomeados pelas etapas |
| Classe | **300 linhas** | dividir por responsabilidade |
| Arquivo Python | **400 linhas** | virar pacote (`arquivo.py` → `arquivo/`) |
| Arquivo JS | **250 linhas** | dividir por assunto |
| Parâmetros de um método | **5** | agrupar num dataclass de contexto |
| Níveis de indentação | **4** | extrair método, ou inverter a condição e usar `return` cedo |

Estes números não são sagrados; **a justificativa é obrigatória**. Se um método precisa
de 60 linhas, a docstring explica por quê (ex.: pipeline numérico vetorizado que perde
performance se quebrado). Sem justificativa escrita, quebre.

### Como quebrar um método longo

1. Leia o corpo e marque onde as "etapas" começam.
2. Cada etapa vira um `_verbo_substantivo()` privado.
3. O método original vira a lista das etapas, na ordem.
4. Se uma etapa precisa de 6 variáveis da anterior, **as duas são a mesma etapa** — ou
   você precisa de um dataclass de estado intermediário.

### Como quebrar um arquivo longo

```
web/composed_routes.py  (633 linhas)
            ↓
web/rotas/__init__.py    # registra blueprints
web/rotas/mapa.py        # rotas de mapa mundi e continente
web/rotas/regiao.py      # rotas de região
web/rotas/tiles.py       # servidor de tiles
web/rotas/features.py    # camadas vetoriais
web/janelas.py           # cálculo de janela de mundo (compartilhado)
web/cache_mapa.py        # caches por mtime (compartilhado)
```
O `__init__.py` do pacote é o único lugar que muda para quem importava antes.

---

## 5. Configuração

### A cadeia

```
config.json  →  config/sources.py  →  config/resolver.py  →  cfg_get()  →  seu código
  (dados)        (de onde vem)          (como resolve)
```

**Nunca** abra `config.json` diretamente. **Nunca** escreva `config["chave"]`.
**Sempre** `cfg_get(config, "bloco", "chave")`.

### Os dois modos de `cfg_get`

```python
# ESTRITO (padrão) — para parâmetro de simulação. Chave ausente = KeyError.
chance = cfg_get(cfg_bio, "concepcao_chance")

# PERMISSIVO — só para infraestrutura, e o default documenta a intenção.
debug = cfg_get(config, "debug_mode", default=False)
```

**Use `default=` apenas quando a ausência da chave for um estado legítimo do sistema,
nunca por preguiça de adicionar a chave.** Se você está prestes a escrever
`cfg_get(cfg, "algo", default=0.5)` para um parâmetro de balanceamento: adicione a chave
no `config.json`.

### Estrutura do `config.json`

Blocos por assunto, não por módulo:

| Bloco | Assunto |
|---|---|
| `metabolismo` | perda/ganho passivo de energia, fome, social |
| `acoes` | custo e efeito de cada `Acao` |
| `ia_decisao` | pesos e limiares da Utility AI |
| `biologia_e_sociedade` | reprodução, crescimento, morte, humor, vínculos |
| `reino` | políticas do reino (pensão, sopão) |
| `infraestrutura` | desgaste, reparo, limiares de estado |
| `geracao_urbana` | parâmetros de expansão urbana em runtime |
| `geracao_populacao` | povoamento inicial |
| `cartografia` | tudo do `cartographer/` |
| `observabilidade` | amostragem de log |

Chaves usam `snake_case` e **descrevem a grandeza, com a unidade no nome quando houver
ambiguidade**: `locais_raio_px`, `gravidez_duracao_ticks`, `cidade_geo_recuo_rua_m`,
`escala_pixel_area_km2`.

### Comentários no config

`config.json` não aceita comentários. O projeto usa chaves `_comentario`,
`_comentario_2`, `_comentario_1_1` para isso. Mantenha o padrão, mas **prefira nomear
melhor a chave** a explicá-la num comentário adjacente.

### Trocar a fonte de configuração

A infraestrutura já existe e **não deve ser contornada**:

```python
from config import configurar_fonte, ConfigSource

class YamlConfigSource(ConfigSource):
    def carregar(self) -> dict: ...

configurar_fonte(YamlConfigSource("config.yaml"))
# Nenhum outro módulo muda.
```

---

## 6. Tipos e vocabulário: quando usar enum

### A regra

> Se o conjunto de valores válidos é **fechado e conhecido em tempo de escrita**, é enum.

| É enum | Não é enum |
|---|---|
| ações de NPC, estágios de vida, gêneros | nome de NPC, descrição de local |
| categorias de local, tipos de local | texto gerado pelo LLM |
| vínculos sociais, humores | mensagem de log |
| chaves de `mundo_meta` | valor numérico de configuração |
| comandos do Modo Mestre | slug de arquivo |
| biomas, classes de via, camadas de mapa | id gerado (`npc_042`) |
| modos e abas da UI (também em JS) | |

### Como escrever um enum neste projeto

```python
class EstadoInfraestrutura(Enum):
    """Estado qualitativo derivado do campo integridade (0–100)."""
    CONSERVADO  = "Conservado"   # 100–76
    DESGASTADO  = "Desgastado"   # 75–51
    DETERIORADO = "Deteriorado"  # 50–26
    CRITICO     = "Crítico"      # 25–11
    RUINA       = "Ruína"        # 10–0
```

- O **valor** é a string que vai para o banco e para o JSON da API.
- O **nome** é `UPPER_SNAKE` e é o que o código usa.
- Uma docstring diz de onde o valor vem.

Quando o enum precisa carregar mais de um dado (id numérico, rótulo, emoji), use o
construtor:

```python
class Bioma(Enum):
    OCEANO = (1, "Oceano", "🌊")

    def __init__(self, id_numerico, rotulo, emoji):
        self.id_numerico = id_numerico
        self.rotulo = rotulo
        self.emoji = emoji

    @classmethod
    def por_id(cls, id_numerico: int) -> 'Bioma | None':
        return next((b for b in cls if b.id_numerico == id_numerico), None)
```

### Enum e persistência

O SQLite guarda `TEXT`. A regra do projeto:

> **No dataclass, o campo é `str` e guarda `Enum.X.value`. Nunca o membro do enum.**

```python
@dataclass
class NPC:
    # INVARIANTE: guarda sempre EstagioVida.X.value — é o que vai para a coluna TEXT.
    estagio_vida: str = EstagioVida.ADULTO.value
```

Isso evita o padrão defensivo que apareceu quando a regra não era clara:
```python
# ❌ sintoma de invariante não definida
return self.estagio_vida == EstagioVida.ADULTO.value or self.estagio_vida == EstagioVida.ADULTO
```

**Exceção:** `NPC.acao_atual` é `Acao` (o membro), porque o `DatabaseManager` faz a
conversão nas duas pontas (`npc.acao_atual.value` ao salvar, `Acao(row[...])` ao ler).
Se você adicionar outro campo assim, faça a conversão no repositório, nunca no domínio.

### Enum e o frontend

Um enum que o JS também precisa conhecer é **servido pela API**, nunca copiado:

```python
# web/rotas/mapa.py
"biomas": {b.id_numerico: {"rotulo": b.rotulo, "emoji": b.emoji} for b in Bioma}
```

Duplicar a tabela no JS é como os biomas acabaram definidos em quatro lugares, um deles
com uma entrada a mais.

---

## 7. Classes: estático, instância ou função

### A árvore de decisão

```
A coisa tem estado ou dependência (banco, config, rng, cache)?
├── NÃO → é função pura
│         ├── faz parte de um grupo coeso? → @staticmethod numa classe-namespace
│         └── é solitária?                 → função de módulo
└── SIM → é classe de INSTÂNCIA, e as dependências entram pelo __init__
```

### Função de módulo — para utilidades puras e solitárias

```python
# cartographer/cities/escala.py
def metros_por_pixel_mundo(config) -> float:
    """Lado do pixel de mundo, em metros."""
    return math.sqrt(cfg_get(config, "escala_pixel_area_km2")) * 1000.0
```
Não há classe aqui porque não há nada para agrupar. **Bom exemplo do projeto.**

### `@staticmethod` — para um grupo coeso de funções puras

```python
class NPCUtils:
    @staticmethod
    def sao_parentes(n1: NPC, n2: NPC) -> bool: ...
    @staticmethod
    def obter_moradores_da_casa(npcs, casa_id) -> List[NPC]: ...
```
Aceitável: são consultas puras sobre argumentos, sem estado, e o agrupamento ajuda a
achá-las.

### Classe de instância — quando há estado ou dependência

```python
class GeradorCidade:
    def __init__(self, modelo):
        self.modelo = modelo
        self.rng = modelo.rng
        self.features = []          # estado acumulado
```
**Bom exemplo do projeto.**

### O antipadrão a evitar

```python
# ❌ classe de instância disfarçada de estática
class NPCHousingManager:
    @staticmethod
    def processar_habitacao(engine): ...
    @staticmethod
    def iniciar_obra_para_casal(engine, n1, n2): ...
```

Quando **todo** método estático recebe o mesmo objeto como primeiro argumento, esse
objeto é o `self` que a classe deveria ter. O custo prático: nada pode ser testado sem
construir uma `SimulationEngine` inteira, que abre um banco real.

**A forma correta:**
```python
class NPCHousingManager:
    """Expansão urbana: detecta superlotação e inicia obras.

    Recebe o mundo, não a engine — precisa de locais, npcs, cidades e do repositório
    de locais, e de nada mais. É isso que permite testá-lo com um mundo sintético."""

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def processar_habitacao(self) -> None: ...
```

### Injeção de dependência

**Uma classe nunca constrói a sua própria dependência de infraestrutura.**

```python
# ❌ JobMarket abre o próprio pool de conexões — o processo acaba com dois
class JobMarket:
    def __init__(self, db_path="database/openworld.db"):
        self.db = DatabaseManager(db_path)

# ✅ recebe de quem já tem
class JobMarket:
    def __init__(self, db: DatabaseManager, config: dict):
        self._db = db
        self._config = config
```

Quem constrói as dependências são os **pontos de entrada**: `run_simulation.py`,
`run_dashboard.py`, `builder/populate.py`. Ninguém mais.

### Camadas de indireção vazias

**Não crie uma classe que só redireciona.** O projeto teve três:

```python
# ❌ 24 linhas que só fazem isto, 4 vezes
class NPCBiologyManager:
    @staticmethod
    def processar_concepcao(engine):
        NPCReproductionManager.processar_concepcao(engine)
```

Uma fachada só se justifica quando **agrega** (compõe várias chamadas), **adapta**
(muda a interface), ou **protege** (valida, transaciona). Redirecionar 1-para-1 apenas
adiciona um salto para quem lê.

---

## 8. Acesso a dados

### A regra

> **Todo SQL vive em `engine/repositorios/` ou em `engine/schema.sql`. Nenhuma exceção
> dentro do runtime.**

```
engine/mechanics/  ──→  engine/repositorios/  ──→  engine/database.py  ──→  SQLite
   (regra)                  (queries)               (pool + schema)
```

### `DatabaseManager` é infraestrutura, não repositório

Ele cuida de: pool de conexões, `contextmanager connection()`, WAL, e aplicar
`schema.sql`. Ele **não** conhece NPC, Local ou Evento.

```python
class DatabaseManager:
    def __init__(self, db_path=caminhos.BANCO, pool_size=5):
        self._pool = queue.Queue(maxsize=pool_size)
        self._init_db()
        self.npcs    = RepositorioNPC(self)
        self.locais  = RepositorioLocal(self)
        self.eventos = RepositorioEvento(self)
        self.meta    = RepositorioMeta(self)
```

### Um repositório por agregado

```python
class RepositorioNPC:
    """Leitura e escrita de NPC. É o único lugar do projeto que conhece o SQL da
    tabela `npcs` e a conversão linha ↔ dataclass."""

    def __init__(self, db: DatabaseManager):
        self._db = db

    def carregar_todos(self) -> List[NPC]: ...
    def salvar(self, npc: NPC) -> None: ...
    def buscar_desempregados(self) -> List[NPC]: ...
```

### Ciclo de vida da conexão

**Um `DatabaseManager` por processo.** Ele abre 5 conexões e executa o schema no
`__init__` — construí-lo por requisição vaza conexões até o processo bater no limite de
descritores. Foi o que aconteceu em `web/mestre_routes.py`.

```python
# web/banco.py — instância única do processo do dashboard
_db = None

def obter_db() -> DatabaseManager:
    global _db
    if _db is None:
        _db = DatabaseManager(caminhos.BANCO)
    return _db
```

### Migração de schema

Colunas novas entram por `ALTER TABLE` num método de migração explícito, **não** por
leitura defensiva:

```python
# ❌ esconde o problema e multiplica por 26 campos
categoria = row['categoria'] if 'categoria' in row.keys() else 'generic'

# ✅ o banco fica correto uma vez
def _migrar_colunas_ausentes(self, conn) -> None: ...
```

### Seed de domínio não é schema

Profissões e mapeamentos de categoria são **dados de domínio**. Eles vivem em
`database/seed_dominio.json` e são aplicados por um passo explícito de
`builder/populate.py` — nunca como efeito colateral de abrir uma conexão.

---

## 9. Erros, logs e falhas

### `except` sempre nomeia a exceção

```python
# ❌ engole tudo, inclusive KeyboardInterrupt e bugs de programação
try:
    ...
except:
    pass

# ✅
try:
    return json.loads(dado)
except json.JSONDecodeError as e:
    WorldLogger.warning(f"[DB] JSON corrompido em {campo} de {npc_id}: {e}")
    return default
```

**Um `except` que não loga nada precisa de um comentário dizendo por que o silêncio é
correto.** Sem isso, é um bug esperando para ser difícil de achar.

### Níveis de log

| Nível | Uso | Vai para |
|---|---|---|
| `debug` | ação de NPC, movimento, transação | arquivo |
| `info` | evento narrativo (nascimento, morte, casamento, colapso) | arquivo + console |
| `warning` | fallback ativado, dado inesperado que o sistema contornou | arquivo + console |
| `error` | operação falhou e alguém precisa saber | arquivo + console |

### Amostragem

Um tick é 1 minuto de jogo. Logar toda ação de todo NPC a cada tick inunda o arquivo.
Use a amostragem configurada, nunca um `% 4` solto:

```python
if WorldLogger.deve_logar_amostra(engine.tick_count, engine.config):
    WorldLogger.debug(...)
```

### Erro em rota HTTP

Um tratador por blueprint, não um `try/except` por rota:

```python
@composed_bp.errorhandler(Exception)
def erro_inesperado(e):
    WorldLogger.error(f"[API] {request.path}: {e}")
    return jsonify({"error": str(e)}), 500
```

### Fallback de IA

O LLM local pode estar offline. Toda chamada tem fallback — essa é uma decisão
arquitetural correta e deve continuar. Mas:

- o fallback **loga `warning`** dizendo que foi ativado (já é o padrão hoje);
- o **conteúdo** do fallback (nomes, personalidades, eventos) mora em
  `engine/ai/fallbacks.json`, não no código Python;
- resposta de LLM é **entrada não confiável**: valide contra o enum antes de persistir.

```python
try:
    humor = HumorNPC(dados.get("humor")).value
except ValueError:
    humor = HumorNPC.NEUTRO.value
```

---

## 10. Frontend

### Estrutura

```
web/templates/index.html      # só estrutura e data-attributes
web/static/css/style.css      # todo o estilo do dashboard
web/static/css/mapa_composto.css
web/static/js/
    app.js                    # ponto de entrada, delegador de eventos, polling
    constantes.js             # enums compartilhados (Modo, Aba, FiltroNpc)
    api.js                    # todo fetch, um lugar só
    navegacao.js
    painel_npcs.js
    ficha_npc.js
    chat_mestre.js
    mapa_composto.js
    mapa_leaflet.js
    formatacao.js             # avatares, rótulos, cores
```

### Regras

**1. Módulos ES, não escopo global.**
```html
<script type="module" src="{{ url_for('static', filename='js/app.js') }}"></script>
```
Cada arquivo exporta o que os outros usam. Nada de depender da ordem das tags `<script>`.

**2. Zero `onclick` no HTML.** Comportamento é ligado por delegação, a partir de
`data-acao`:
```html
<button class="tab-btn" data-acao="trocar-aba" data-aba="mapa">🗺️ Mapa</button>
```
```js
document.addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-acao]');
    if (alvo) ACOES[alvo.dataset.acao]?.(alvo, ev);
});
```

**3. Zero `style="..."` inline.** Se precisa de uma variação visual, é uma classe. O CSS
do projeto já tem variáveis (`--accent`, `--danger`, `--success`); use-as.

**4. Estado de módulo é um objeto, não 20 `let`.**
```js
const estado = { modo: Modo.GLOBAL, continenteUuid: null, escala: 1.0 };
```

**5. Enums em JS são `Object.freeze`.** Nada de `'global'` comparado à mão.

**6. Nenhum valor de configuração duplicado do Python.** O que o JS precisa saber sobre
escala, zoom, largura de via, biomas, camadas — **vem da API**. Se a API não respondeu, o
mapa mostra erro; ele não desenha com um número escrito à mão que já divergiu do config
uma vez.

**7. Todo texto vindo do servidor passa por `escaparHtml` antes de ir para `innerHTML`.**
Nomes, profissões, personalidades e backgrounds são **gerados por LLM** — trate como
entrada não confiável.

**8. Nada de estado de UI no texto visível.** Decidir qual filtro está ativo lendo
`btn.innerText.toLowerCase().includes('vivos')` quebra quando o rótulo muda. Use
`dataset`.

---

## 11. Determinismo e geração procedural

O `cartographer/` tem uma exigência que o resto do projeto não tem: **o mesmo config e a
mesma semente produzem exatamente o mesmo mundo**, bit a bit, em qualquer resolução.

Isso está travado por `tests/test_cartografia.py` e `tests/test_cidades.py`, e as regras
abaixo existem porque cada uma delas já foi violada e custou uma sessão de depuração.
Estão documentadas em `docs/PLANO_EVOLUCAO_V2.md` e `docs/ESPEC_DESENHO_CIDADE.md`.

### As regras

**D1 · O terreno é função de coordenada de mundo, nunca de índice de array.**
Pedir a mesma janela em resolução maior **refina**; nunca contradiz.

**D2 · Nunca use `hash()` do Python para semente.** Ele é aleatorizado entre processos.
Use `zlib.crc32` sobre o nome, como `SitioCidade` já faz.

**D3 · Nunca consuma o `rng` principal fora da ordem estabelecida.** Sortear uma coisa
nova antes das existentes desloca **toda** a sequência e muda todas as cidades. Se
precisar de aleatoriedade para uma decisão auxiliar, derive um gerador:
```python
rng_selecao = random.Random(sitio.seed ^ 0x9E3779B9)
```

**D4 · Nunca reuse buffer numpy entre chamadas.** Janela não-quadrada quebra um array de
tamanho fixo, e chamadas concorrentes (servidor de tiles) se corrompem.

**D5 · Otimização não pode mudar resultado.** O culling de continentes tem um teste
dedicado (`test_culling_nao_altera_resultado`) que prova isso. Qualquer otimização nova
precisa do mesmo tipo de teste.

**D6 · Nenhuma descoberta automática de módulo.** `cartographer/cities/modelos/__init__.py`
registra os modelos **explicitamente**, e a docstring diz por quê: varrer o diretório
tornaria a ordem de registro dependente do sistema de arquivos.

### Ao mexer no `cartographer/`

```bash
md5sum database/cidades/*.geojson > /tmp/antes.md5
# ... sua mudança ...
venv/bin/python cartographer/cities/generate_city_geometry.py
md5sum database/cidades/*.geojson | diff - /tmp/antes.md5
```
Se o diff não for vazio e você não pretendia mudar o mundo, a refatoração alterou o
consumo do `rng`. Reverta e refaça.

---

## 12. Documentação no código

### Cabeçalho de módulo

O projeto tem um padrão bom. Mantenha:

```python
"""
MODULE: decay.py
FUNÇÃO: Sistema de Decadência e Manutenção de Infraestrutura.

DESCRIÇÃO:
    Gerencia o ciclo de vida físico das construções da vila.
    Toda parametrização numérica vem de config.json["infraestrutura"] via cfg_get.

    Fluxo (chamado uma vez por DIA simulado):
      1. processar_desgaste()           — erosão passiva + penalidade de superlotação
      2. _aplicar_consequencias()       — efeitos estruturais por limiar
      3. processar_reparos_espontaneos()— manutenção informal por NPCs
"""
```

Para scripts executáveis, acrescente `USO:` com a linha de comando.

### Docstring de método

Diga **o que** e **por quê**, não **como** (o código diz o como).

```python
def _encolher_quad(self, quad, distancias):
    """Recua cada aresta do quadrilátero pela distância correspondente, devolvendo o
    polígono interno. Devolve None se o recuo consumir a área — lote estreito demais
    pro recuo não vira edifício nenhum, vira chão vazio."""
```

### Comentários que explicam decisão

Este projeto usa bem um padrão raro e valioso: **comentar por que uma decisão foi tomada,
citando o problema que ela resolveu**. Continue fazendo isso.

```python
# Mesmo limiar de "quase descansado" usado pela Utility AI (NPCBrain) — antes
# era um 85.0 hardcoded aqui, independente do 85 hardcoded em logic.py.
energia_quase_descansado = cfg_get(cfg_dec, "energia_quase_descansado")
```

```python
# `escala_pixel_area_km2` é ÁREA (km² por pixel), então o lado é a RAIZ dela.
# Confundir as duas coisas foi o D1: dava um erro de sqrt(250) = 15,81x.
```

Um comentário assim impede que a próxima pessoa (ou o próximo modelo) desfaça a correção.

### O que **não** comentar

```python
# ❌ narra o óbvio
# Incrementa o contador
engine.tick_count += 1

# ❌ comentário que virou mentira
# Conclui em ~10 ticks (~2.5 horas in-game)
obra.integridade += ganho_integridade   # ← ganho vem do config; o número pode ser outro
```

Se o comentário depende de um valor que agora está no config, ele precisa dizer isso, não
repetir o número antigo.

### Marcar dívida técnica explicitamente

O projeto já faz isso e é excelente:
```python
# ⚠️ Paliativo consciente (documentado na Seção 2.1 do plano): espalhar edifícios num
# raio de poucos pixels de mundo é espalhá-los por dezenas de km — fisicamente
# absurdo, visualmente aceitável até a Fase 4.
```
**Continue.** Um paliativo marcado é uma decisão; um paliativo não marcado é um bug
esperando.

---

## 13. Testes

### O que testar

O projeto deliberadamente **não** busca cobertura alta. Ele testa **invariantes**: coisas
que, se quebrarem, quebram o sistema inteiro e de forma difícil de perceber.

| Testar | Não testar |
|---|---|
| determinismo da geração | formatação de log |
| invariância entre zooms | texto de mensagem |
| contratos de interface (todo modelo responde aos ganchos) | wrappers de 3 linhas |
| regras que já tiveram bug (teto de notáveis por quarteirão) | getters |
| conversão de unidade (metro ↔ pixel ↔ zoom) | |

### Onde o teste mora

`tests/test_<assunto>.py`, com docstring dizendo **qual seção de qual documento** o
arquivo protege:

```python
"""
Testes de geometria de cidade — docs/ESPEC_DESENHO_CIDADE.md, Seção 9.2.

Cobre os invariantes que a arquitetura de modelo de cidade (F4) precisa proteger: a base
sozinha basta pra um modelo mínimo gerar uma cidade completa (T5), todo modelo registrado
responde à interface (T6), ...
"""
```

### O teste que a injeção de dependência habilita

Quando um gerenciador recebe o mundo em vez da engine, o teste fica assim:

```python
def test_obra_nao_duplica_para_casal_que_ja_constroi():
    mundo = EstadoDoMundo(npcs=[casal_a, casal_b], locais={...}, cidades={...})
    gerenciador = NPCHousingManager(mundo, config_de_teste())
    gerenciador.processar_habitacao()
    assert len([l for l in mundo.locais.values() if l.status == 0]) == 1
```
Sem banco, sem arquivo, sem `SimulationEngine`. **Se escrever esse teste for difícil, a
injeção está errada** — o teste é o instrumento de medição do acoplamento.

### Ao corrigir um bug

Todo bug corrigido ganha um teste que falha antes e passa depois. É assim que o teto de
notáveis por quarteirão (`test_teto_de_notaveis_por_quarteirao`) existe: foi o bug 3.2.

---

## 14. Receitas: como adicionar X

### 14.1 · Uma nova ação de NPC

1. `engine/models.py` — adicione o membro em `Acao`.
2. `config.json` → `acoes` — adicione o bloco com o custo/efeito.
3. `config.json` → `ia_decisao` — adicione os pesos que o avaliador vai ler.
4. `engine/mechanics/utilidade/<acao>.py` — crie `AvaliadorX(AvaliadorDeUtilidade)` com
   um `avaliar(ctx)` de ≤ 30 linhas.
5. Registre em `NPCBrain.AVALIADORES`.
6. `engine/mechanics/actions.py` — adicione `_executar_<acao>`.
7. Se a ação move o NPC, adicione `mover_para_<destino>` em `movement.py`.
8. Se a ação gera narrativa, emita um `Evento` com um `TipoEvento` novo.

**Nada mais muda.** Se você precisou tocar em `loop.py`, o desenho está errado.

### 14.2 · Um novo modelo de cidade

1. `cartographer/cities/modelos/<nome>.py` — `class NomeModelo(ModeloCidade)`, com
   `nome = "nome"`.
2. Implemente `construir_malha()` (o único gancho obrigatório).
3. Sobrescreva só os ganchos que fazem sentido para o traçado
   (`zona_de`, `encomendas`, `escolher_quadra`, `precisa_muralha`, `ajustar_por_sitio`).
4. Registre em `modelos/__init__.py` — **explicitamente**, na tupla `MODELOS`.
5. `config.json` → `cartografia.cidade_geo_modelo_por_tipo` — adicione o peso por tipo.
6. Rode `tests/test_cidades.py`: `test_todo_modelo_registrado_responde_a_interface`
   valida o contrato automaticamente.

**Você não toca em `generate_city_geometry.py`.** Se precisou, o trabalho é compartilhado
(inset, lote, footprint, emissão) e pertence ao `GeradorCidade`, não ao modelo.

### 14.3 · Um novo endpoint HTTP

1. Escolha o blueprint por assunto em `web/rotas/`. Se não existir, crie o arquivo.
2. A rota tem ≤ 10 linhas: valida entrada, chama um serviço/repositório, serializa.
3. **Sem `try/except`** — o `errorhandler` do blueprint cuida.
4. **Sem SQL** — chame um repositório.
5. Se o payload tem mais de 3 campos, escreva a serialização em `web/serializadores.py`,
   com chaves **legíveis**.

### 14.4 · Um novo parâmetro de balanceamento

1. Adicione a chave em `config.json`, no bloco do assunto, com nome descritivo e unidade.
2. Leia com `cfg_get(...)` **sem `default=`**.
3. Se a chave substitui um número que estava no código, apague o número e escreva um
   comentário dizendo de onde ele veio.
4. Rode a simulação: se `cfg_get` estourar `KeyError`, o nome no código e no JSON estão
   diferentes — é exatamente para isso que a política estrita existe.

### 14.5 · Uma nova ação do Modo Mestre

1. `ComandoMestre` — adicione o membro.
2. `engine/mechanics/mestre/acoes/<comando>.py` — `class AcaoX(AcaoDeMundo)` com
   `aplicar(db, contexto, dados) -> str`.
3. Registre no dicionário de despacho.
4. Atualize `engine/ai/prompts/mestre_mensagem.txt` para a IA saber que o comando existe.
5. **Nenhuma ação é aplicada sem confirmação explícita do jogador.** Isso é uma decisão
   de produto, não um detalhe: `aplicar_acoes` só roda a partir de
   `/api/mestre/confirmar_acoes`.

### 14.6 · Um novo bioma

1. `cartographer/math/climate.py` — adicione o membro em `Bioma` com id numérico novo.
2. `classify_biomes` — adicione a regra de classificação.
3. `cartographer/math/coloring.py` — adicione a paleta.
4. **Não toque no JS**: a tabela de biomas é servida por `/api/continentes`.
5. Rode `tests/test_cartografia.py` — os testes de detalhe e costa precisam continuar
   passando.

---

## 15. Lista de padrões proibidos

Use como busca antes de abrir um PR.

| # | Proibido | Por quê | Busca |
|---|---|---|---|
| 1 | `except:` nu | engole `KeyboardInterrupt` e bugs reais | `grep -rn "except:"` |
| 2 | `config["chave"]` ou `cfg.get("x", default)` para parâmetro de simulação | fura a política estrita; o config passa a mentir | `grep -rn 'config\[\|cfg\.get('` |
| 3 | `getattr(obj, 'campo', default)` sobre campo declarado | mascara renomeação e digitação errada | `grep -rn "getattr("` |
| 4 | SQL fora de `engine/repositorios/` | espalha o schema por toda a base | `grep -rn "SELECT \|INSERT \|UPDATE "` |
| 5 | `sqlite3.connect` fora de `DatabaseManager` | ignora pool e WAL; compete com a engine | `grep -rn "sqlite3.connect"` |
| 6 | `DatabaseManager(...)` fora de um ponto de entrada | vaza pool de 5 conexões por chamada | `grep -rn "DatabaseManager("` |
| 7 | `import` dentro de função | esconde ciclo de dependência entre camadas | inspeção |
| 8 | Argumento default mutável (`def f(x=[])`) | compartilha estado entre chamadas | `grep -rn "=\[\])\|={})"` |
| 9 | String de domínio onde existe enum | divergência silenciosa entre módulos | Anexo 2 do plano |
| 10 | Número de domínio solto na lógica | impossível balancear sem editar código | inspeção |
| 11 | Dado codificado por parsing de outro campo (`"Dono: " + id`) | frágil, e casa por substring | `grep -rn "\.replace(\"" ` |
| 12 | Classe cujos métodos são todos `@staticmethod(mesmo_1o_arg)` | é instância disfarçada; intestável | inspeção |
| 13 | Fachada 1-para-1 sem agregar/adaptar/proteger | salto de leitura sem ganho | inspeção |
| 14 | `utils.py` / `helpers.py` / `common.py` | vira depósito | `find -name "utils.py"` |
| 15 | `onclick=` no HTML | obriga função global; espalha comportamento | `grep -rn "onclick="` |
| 16 | `style="..."` inline | estilo fora do CSS | `grep -rn 'style="'` |
| 17 | Valor de config duplicado no JS | diverge do Python e ninguém percebe | inspeção |
| 18 | `innerHTML` com texto do servidor sem escape | injeção via texto gerado por LLM | `grep -rn "innerHTML"` |
| 19 | Estado de UI decidido por texto visível | quebra ao mudar rótulo | `grep -rn "innerText"` |
| 20 | Instanciar `SimulationEngine` fora de `run_simulation.py` | dois donos do mesmo estado | `grep -rn "SimulationEngine("` |
| 21 | `hash()` como semente procedural | aleatorizado entre processos | `grep -rn "hash("` |
| 22 | Consumir o `rng` principal fora da ordem | muda todas as cidades geradas | inspeção |
| 23 | Método acima de 40 linhas sem justificativa na docstring | uma decisão por método | inspeção |
| 24 | Caminho de arquivo montado à mão | script só roda de um diretório | `grep -rn "os.path.join(os.path.dirname"` |

---

## 16. Checklist de revisão

Antes de considerar uma mudança pronta:

### Estrutura
- [ ] Nenhum arquivo novo acima de 400 linhas (JS: 250)
- [ ] Nenhum método acima de 40 linhas sem justificativa escrita
- [ ] Nenhum método com mais de 5 parâmetros
- [ ] O arquivo tem uma única razão para mudar, e o nome diz qual
- [ ] Nenhum import viola a direção das camadas (Seção 2)

### Vocabulário
- [ ] Nenhuma string de domínio nova — usei ou criei um enum
- [ ] Nenhum número de domínio novo — está no config ou numa constante nomeada
- [ ] Valor que o frontend precisa é **servido pela API**, não copiado

### Configuração
- [ ] Todo parâmetro lido com `cfg_get` sem `default=`
- [ ] Chave nova adicionada em `config.json` no bloco do assunto
- [ ] Nome da chave diz a grandeza e a unidade

### Dados
- [ ] Nenhum SQL fora de `engine/repositorios/`
- [ ] Nenhum `DatabaseManager` novo fora de um ponto de entrada
- [ ] Campo novo: declarado no dataclass **e** no `schema.sql` **e** no repositório

### Robustez
- [ ] Todo `except` nomeia a exceção e loga ou explica o silêncio
- [ ] Entrada vinda de LLM é validada contra enum antes de persistir
- [ ] Texto do servidor é escapado antes de ir para `innerHTML`

### Testes
- [ ] `venv/bin/python -m pytest tests/ -v` passa
- [ ] Se mexi no `cartographer/`: o md5 dos `.geojson` bate com o baseline
- [ ] Se corrigi um bug: existe um teste que falharia antes

### Documentação
- [ ] Módulo novo tem cabeçalho `MODULE / FUNÇÃO / DESCRIÇÃO`
- [ ] Decisão não óbvia tem comentário dizendo **por quê**, citando o problema resolvido
- [ ] Paliativo consciente está marcado com ⚠️ e o que o substitui

---

## Apêndice · Exemplares do projeto

Quando estiver em dúvida sobre como escrever algo, abra um destes:

| Quero escrever… | Abra |
|---|---|
| uma interface com variantes trocáveis | `cartographer/cities/modelos/base.py` |
| um gerenciador de regra de simulação | `engine/mechanics/decay.py` |
| uma conversão de unidade | `cartographer/cities/escala.py` |
| acesso a configuração | `config/resolver.py` |
| uma fonte de dados intercambiável | `config/sources.py` |
| um teste de invariante | `tests/test_cidades.py` |
| um comentário que explica uma decisão | `cartographer/cities/escala.py:33-38` |

E quando quiser ver o que **não** fazer, o [`PLANO_REFATORACAO.md`](PLANO_REFATORACAO.md)
tem 13 bugs reais catalogados, cada um com o arquivo e a linha.
