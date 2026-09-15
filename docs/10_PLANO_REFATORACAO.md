# 🔧 Plano de Refatoração Estrutural do OpenWorld

> **Para quem vai executar (modelo de desenvolvimento ou humano):**
> Este documento é uma **lista de tarefas fechadas**. Cada tarefa tem: arquivo(s) alvo,
> o problema concreto, o que fazer, e como validar. Execute **na ordem dos blocos**.
> Não invente escopo: se uma tarefa não está aqui, não faça agora.
>
> 👉 **Antes de escrever qualquer código novo**, leia [`11_ARQUITETURA.md`](11_ARQUITETURA.md).
> Ele define o padrão que o código deve ter *depois* desta refatoração — e que toda
> feature nova deve seguir por padrão.

**Criado em:** 2026-09-11
**Base analisada:** branch `reescrita-estrutura`, commit `5e596ae`
**Escopo:** ~12.700 linhas de código próprio (Python, JS, HTML, CSS), excluindo `venv/`.

---

## Índice

- [0. Como usar este documento](#0-como-usar-este-documento)
- [1. Diagnóstico resumido](#1-diagnóstico-resumido)
- [Bloco A — Preparação e remoção de código morto](#bloco-a--preparação-e-remoção-de-código-morto)
- [Bloco B — Vocabulário: enums e constantes](#bloco-b--vocabulário-enums-e-constantes)
- [Bloco C — Modelo de dados e invariantes](#bloco-c--modelo-de-dados-e-invariantes)
- [Bloco D — Quebra de métodos gigantes (SRP)](#bloco-d--quebra-de-métodos-gigantes-srp)
- [Bloco E — Camada de acesso a dados](#bloco-e--camada-de-acesso-a-dados)
- [Bloco F — Estático vs. instância, injeção de dependência](#bloco-f--estático-vs-instância-injeção-de-dependência)
- [Bloco G — Camada web (Python)](#bloco-g--camada-web-python)
- [Bloco H — Frontend (JS/HTML/CSS)](#bloco-h--frontend-jshtmlcss)
- [Bloco I — Verificação final](#bloco-i--verificação-final)
- [Anexo 1 — Tabela de números mágicos encontrados](#anexo-1--tabela-de-números-mágicos-encontrados)
- [Anexo 2 — Tabela de strings que devem virar enum](#anexo-2--tabela-de-strings-que-devem-virar-enum)
- [Anexo 3 — Bugs reais encontrados durante a análise](#anexo-3--bugs-reais-encontrados-durante-a-análise)

---

## 0. Como usar este documento

### Regras de execução

1. **Uma tarefa por commit.** O título do commit é o ID da tarefa mais a descrição
   curta. Ex.: `R-A02: remove builder/old (código morto)`.
2. **Refatoração é `diff` de comportamento vazio.** Exceto onde a tarefa diz
   explicitamente "corrige bug", o comportamento observável não pode mudar.
3. **Rode os testes antes e depois de cada tarefa.** Comando na tarefa `R-A01`.
4. **Se uma tarefa parecer maior do que o descrito**, pare e anote no final do
   documento em vez de improvisar uma solução diferente.
5. **Não renomeie arquivos e funções além do que a tarefa pede.** Renomeação em massa
   estoura o `diff` e impede revisão.

### Formato de cada tarefa

```
### R-XNN · Título
**Arquivos:** caminho(s)
**Problema:** o que está errado hoje, com linha de referência
**Ação:** o que fazer, passo a passo
**Validar:** como provar que deu certo
**Risco:** baixo | médio | alto
```

### Convenções de nomenclatura adotadas nesta refatoração

| Elemento | Convenção | Exemplo |
|---|---|---|
| Classe | `PascalCase`, substantivo, em português | `GerenciadorHabitacao` (mantemos nomes existentes, veja abaixo) |
| Enum | `PascalCase` singular | `Acao`, `EstagioVida`, `VinculoSocial` |
| Membro de enum | `UPPER_SNAKE` | `EstagioVida.BEBE` |
| Constante de módulo/classe | `UPPER_SNAKE` | `EPOCA_INICIAL`, `SAUDE_MAXIMA` |
| Método privado | prefixo `_` | `_calcular_utilidade_comer` |
| Arquivo Python | `snake_case.py` | `mood.py` |

> ⚠️ **Não traduza nomes de classes existentes.** O projeto mistura inglês
> (`NPCBrain`, `JobMarket`) e português (`GeradorCidade`, `MestreManager`). Padronizar
> isso agora geraria um `diff` enorme sem ganho funcional. A regra daqui pra frente,
> registrada em `11_ARQUITETURA.md`, é: **código novo em português**; código existente fica
> como está até ter outro motivo pra ser tocado.

---

## 1. Diagnóstico resumido

O projeto tem **partes excelentes** e **partes que envelheceram mal**. É importante
reconhecer as duas coisas, porque as partes boas são o modelo a seguir.

### O que já está certo (use como referência, não mexa)

| Arquivo | Por que é um bom exemplo |
|---|---|
| `config/resolver.py` + `config/sources.py` | Fonte de configuração intercambiável, resolução estrita com `KeyError` em vez de default silencioso. É o padrão. |
| `cartographer/cities/modelos/base.py` | Strategy pattern real: interface de ganchos documentada, classes de instância, cada modelo sobrescreve só o que precisa. **Melhor arquitetura do projeto.** |
| `engine/mechanics/decay.py` | Método público curto que delega para privados curtos; toda parametrização via `cfg_get`; enum (`EstadoInfraestrutura`) em vez de string. |
| `cartographer/cities/escala.py` | Uma conversão de unidade, um lugar só, com o "porquê" documentado. |

### O que precisa mudar

| # | Problema | Onde dói mais |
|---|---|---|
| 1 | **Métodos gigantes** com muitas responsabilidades | `logic.py:8` (144 linhas), `loop.py:27` (123), `populate.py:127` (227), `tile_cartographer.py:92` (180), `generate_city_geometry.py:350` (110) |
| 2 | **Strings soltas** onde já existe enum | `"dependente"`, `"bebe"`, `"Casa"`, `"residencia"`, `"Social"`, `"Aliado"`, `"Amigo"`, `"CONVERSA"`… |
| 3 | **Números mágicos** no meio da lógica | `90`, `100`, `80.0`, `datetime(1200,1,1)`, `% 4`, `0.5`, `70/30/-20/-50` |
| 4 | **Três formas diferentes** de falar com o banco | `DatabaseManager`, SQL cru dentro de mecânicas, `sqlite3.connect` direto no web |
| 5 | **Tudo `@staticmethod`** recebendo `engine` como primeiro argumento | 13 dos 16 módulos em `engine/mechanics/` |
| 6 | **Camadas de indireção vazias** | `NPCBiologyManager`, `AIWorldGenerator`, `engine/ai/client.py`, `mover_para_local_social` |
| 7 | **Código morto versionado** | `builder/old/` inteiro, `capacidade_efetiva`, `engine/world/` |
| 8 | **Frontend sem módulos** | 56 variáveis globais em 3 arquivos JS, 22 `onclick=` inline no HTML |
| 9 | **Dados duplicados entre Python e JS** | nomes de bioma em 4 lugares, largura de via em 2, `dimensao_global` em 3 |
| 10 | **Fuga de defaults silenciosos** apesar da política `cfg_get` | `loop.py:79-80`, `logic.py:56`, `composed_routes.py` (`768`) |

---

# Bloco A — Preparação e remoção de código morto

> Objetivo: reduzir a superfície do código antes de mexer nele. **Tudo neste bloco é
> deleção ou verificação.** Nenhum comportamento muda.

### R-A01 · Estabelecer a linha de base de testes
**Arquivos:** nenhum (só execução)
**Problema:** as tarefas seguintes precisam de um "antes" confiável.
**Ação:**
1. Rode a suíte existente e guarde a saída:
   ```bash
   venv/bin/python -m pytest tests/ -v
   ```
2. Anote quantos testes passam. Se algum já falha **antes** da refatoração, registre
   no final deste documento e **não tente consertar agora**.
3. Gere um mundo pequeno de referência para comparar depois:
   ```bash
   venv/bin/python cartographer/cities/generate_city_geometry.py > /tmp/geom_antes.txt 2>&1
   md5sum database/cidades/*.geojson > /tmp/geom_antes.md5
   ```
**Validar:** os dois arquivos em `/tmp` existem e a contagem de testes foi anotada.
**Risco:** baixo

---

### R-A02 · Remover `builder/old/` inteiro
**Arquivos:** `builder/old/manager.py`, `builder/old/cartographer.py`, `builder/old/setup_jobs.py`
**Problema:** 470 linhas nunca importadas por nada fora da própria pasta. O
`builder/README.md` já as declara "arquivo morto". `manager.py` ainda importa
`AIWorldGenerator` e por isso mantém vivo artificialmente um wrapper que também é morto.
**Ação:**
1. Confirme que nada referencia a pasta:
   ```bash
   grep -rn "builder.old\|builder/old\|setup_jobs" --exclude-dir=venv --exclude-dir=.git --exclude-dir=old .
   ```
   A saída deve conter apenas linhas do `builder/README.md`.
2. `git rm -r builder/old`
3. Remova do `builder/README.md` a seção que descreve `old/`.
**Validar:** `venv/bin/python -m pytest tests/ -v` continua igual à linha de base.
**Risco:** baixo

---

### R-A03 · Remover a pasta vazia `engine/world/`
**Arquivos:** `engine/world/__init__.py`
**Problema:** pacote com um `__init__.py` de 0 bytes e nenhum outro arquivo. Nada
importa `engine.world`.
**Ação:** `git rm -r engine/world`
**Validar:** testes iguais à linha de base.
**Risco:** baixo

---

### R-A04 · Remover `InfrastructureManager.capacidade_efetiva`
**Arquivos:** `engine/mechanics/decay.py:47-61`
**Problema:** método público bem escrito, com docstring dizendo *"Deve ser consultado
pelo JobMarket em vez de `local.capacidade` diretamente"* — e **nunca é chamado por
ninguém**. O `JobMarket` consulta `l.capacidade` cru no SQL (`market.py:78`).
**Ação:** escolha **uma** das duas saídas e registre a escolha no commit:
- **(a) Cumprir a intenção** *(preferida — corrige um comportamento incoerente)*: fazer
  `JobMarket.processar_contratacoes` descontar a degradação. Como a consulta é SQL,
  traga `integridade` na query e aplique `capacidade_efetiva` em Python antes de montar
  `vagas_por_categoria`.
- **(b) Remover** o método, se você não quiser mudar comportamento neste momento.
**Validar:** `grep -rn "capacidade_efetiva"` retorna 0 ocorrências (saída b) ou 2
(definição + uso no `market.py`, saída a).
**Risco:** baixo (b) · médio (a — muda balanceamento)

---

### R-A05 · Colapsar a fachada vazia `NPCBiologyManager`
**Arquivos:** `engine/mechanics/biology.py`, `engine/loop.py`, `engine/mechanics/__init__.py`
**Problema:** `biology.py` inteiro (24 linhas) só redireciona 4 chamadas para
`NPCReproductionManager` e `NPCLifecycleManager`. Não adiciona nada. Quem lê `loop.py`
precisa de dois saltos para achar o código real.
**Ação:**
1. Em `engine/loop.py`, troque os imports e as 4 chamadas:
   - `NPCBiologyManager.processar_concepcao` → `NPCReproductionManager.processar_concepcao`
   - `NPCBiologyManager.processar_parto` → `NPCReproductionManager.processar_parto`
   - `NPCBiologyManager.processar_crescimento` → `NPCLifecycleManager.processar_crescimento`
   - `NPCBiologyManager.processar_morte` → `NPCLifecycleManager.processar_morte`
2. `git rm engine/mechanics/biology.py`
3. Em `engine/mechanics/__init__.py`, remova a linha de import e a entrada em `__all__`;
   adicione `NPCReproductionManager` e `NPCLifecycleManager` no lugar.
**Validar:** `grep -rn "NPCBiologyManager" --exclude-dir=venv --exclude-dir=docs .`
retorna 0 ocorrências.
**Risco:** baixo

---

### R-A06 · Colapsar `AIWorldGenerator`
**Arquivos:** `builder/generator.py`, `builder/populate.py:22,207`
**Problema:** `AIWorldGenerator` (26 linhas) é um passa-tudo para `AIGeneratorClient`.
Depois do `R-A02`, o único chamador real é `populate.py`, em **um** lugar.
**Ação:**
1. Em `populate.py`, troque
   `from builder.generator import AIWorldGenerator` por
   `from engine.ai import AIGeneratorClient`, e
   `AIWorldGenerator.generate_npc_dna(...)` por `AIGeneratorClient.gerar_dna_npc(...)`
   (mesma assinatura).
2. `git rm builder/generator.py`
3. Atualize `builder/README.md` removendo a descrição de `generator.py`.
**Validar:** `grep -rn "AIWorldGenerator" --exclude-dir=venv .` retorna 0.
**Risco:** baixo

---

### R-A07 · Unificar o pacote de IA: `ai/` vs `engine/ai/`
**Arquivos:** `ai/client.py`, `ai/utils.py`, `engine/ai/client.py`, `engine/ai/__init__.py`
**Problema:** existem **dois** pacotes de IA. `engine/ai/client.py` tem **uma linha**:
`from ai.client import AIClient`. E `ai/client.py` lê os prompts de
`engine/ai/prompts/` subindo um diretório com `os.path.dirname(current_dir)`
(`ai/client.py:63-66`) — um caminho frágil que quebra se qualquer um dos dois se mover.
**Ação:**
1. Mova `ai/client.py` → `engine/ai/client.py` (substituindo o shim de 1 linha).
2. Mova `ai/utils.py` → `engine/ai/utils.py`.
3. Corrija `read_prompt` para resolver a partir do **próprio** arquivo, sem subir:
   ```python
   PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
   ...
   path = os.path.join(PROMPTS_DIR, filename)
   ```
4. Atualize os imports em `engine/ai/__init__.py`, `engine/ai/generator.py`,
   `engine/ai/storyteller.py`, `engine/ai/game_master.py` para `from .utils import AIUtils`.
5. `git rm -r ai/`
**Validar:**
```bash
grep -rn "^from ai\.\|^import ai\b\|from ai import" --exclude-dir=venv .   # deve dar 0
venv/bin/python -c "from engine.ai import AIClient; print(AIClient.read_prompt('dna.txt')[:40])"
```
**Risco:** médio (mexe em imports de vários módulos)

---

### R-A08 · Remover o alias `mover_para_local_social`
**Arquivos:** `engine/mechanics/movement.py:108-111`, `engine/mechanics/actions.py:148`
**Problema:** método cuja única linha é chamar `mover_para_social`. A docstring diz
"para compatibilidade externa", mas o único chamador é interno ao projeto.
**Ação:** em `actions.py:148` troque para `NPCMovementManager.mover_para_social(...)` e
apague o método alias.
**Validar:** `grep -rn "mover_para_local_social"` retorna 0.
**Risco:** baixo

---

### R-A09 · Remover o `except` inalcançável em `dashboard.py`
**Arquivos:** `web/dashboard.py:170-174`
**Problema:** há **dois** blocos `except Exception as e:` em sequência no fim de
`get_update()`. O segundo (linhas 173-174) é inalcançável — resto de merge.
**Ação:** apague as linhas 173-174 e as linhas em branco duplicadas acima.
**Validar:** `venv/bin/python -c "import ast,sys; ast.parse(open('web/dashboard.py').read())"` sem erro.
**Risco:** baixo

---

### R-A10 · Remover a ramificação morta em `extrair_sobrenome`
**Arquivos:** `engine/mechanics/reproduction.py:85-91`
**Problema:**
```python
if "de" in partes:
    return partes[-1]
return partes[-1]      # mesma coisa
```
Os dois ramos são idênticos. A função inteira reduz a "último token, ou o nome se for
único".
**Ação:** substitua a função aninhada por uma função de módulo de 3 linhas:
```python
def _extrair_sobrenome(nome: str) -> str:
    partes = nome.split()
    return partes[-1] if len(partes) > 1 else nome
```
**Validar:** revisão de código; testes iguais à linha de base.
**Risco:** baixo

---

### R-A11 · Documentar `builder/fix/` como ferramenta manual
**Arquivos:** `builder/fix/repair_db.py`, `builder/fix/audit_market.py`
**Problema:** os dois abrem `sqlite3.connect('database/openworld.db')` com caminho
relativo hardcoded, ignorando `DatabaseManager`. São scripts de diagnóstico pontuais —
não é erro grave, mas eles **parecem** parte do sistema.
**Ação:** **não refatore.** Adicione no topo de cada um, dentro da docstring existente:
```
⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine, com conexão SQLite própria e
caminho relativo à raiz do projeto. Não importe estes módulos de dentro de engine/,
web/ ou cartographer/ — eles não fazem parte do runtime.
```
**Validar:** revisão de código.
**Risco:** baixo

---

# Bloco B — Vocabulário: enums e constantes

> Objetivo: acabar com strings soltas e números mágicos. **Regra geral:**
> se um valor de texto tem um conjunto fechado de possibilidades, é enum.
> Se um número aparece duas vezes ou tem um significado de domínio, é constante ou
> config.

### R-B01 · Criar o enum `VinculoSocial` e **corrigir a ordem quebrada**
**Arquivos:** `engine/models.py`, `engine/mechanics/social.py:62-66`, `engine/mechanics/marriage.py:138`, `builder/populate.py:320,343`
**Problema:** duplo. Os vínculos são strings soltas (`"Conhecido"`, `"Aliado"`,
`"Amigo"`, `"Rival"`, `"Inimigo"`, `"Cônjuge"`), **e a cadeia `elif` está errada**:

```python
vinculo = "Conhecido"
if   nova_afinidade >= 70: vinculo = "Aliado"
elif nova_afinidade >= 30: vinculo = "Amigo"
elif nova_afinidade < -20: vinculo = "Rival"
elif nova_afinidade < -50: vinculo = "Inimigo"   # ← INALCANÇÁVEL
```
Afinidade `-60` satisfaz `< -20` e para ali. **`"Inimigo"` nunca é atribuído.**

**Ação:**
1. Em `engine/models.py`, adicione:
   ```python
   class VinculoSocial(Enum):
       CONJUGE    = "Cônjuge"
       ALIADO     = "Aliado"
       AMIGO      = "Amigo"
       CONHECIDO  = "Conhecido"
       RIVAL      = "Rival"
       INIMIGO    = "Inimigo"
   ```
2. Mova os limiares para `config.json`, em `biologia_e_sociedade`:
   ```json
   "vinculo_limiar_aliado": 70,
   "vinculo_limiar_amigo": 30,
   "vinculo_limiar_rival": -20,
   "vinculo_limiar_inimigo": -50
   ```
3. Substitua a cadeia por um método de classificação, **com a ordem corrigida**
   (testar o mais negativo primeiro):
   ```python
   @staticmethod
   def _classificar_vinculo(afinidade: int, cfg_bio: dict) -> VinculoSocial:
       if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_aliado"):
           return VinculoSocial.ALIADO
       if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_amigo"):
           return VinculoSocial.AMIGO
       if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_inimigo"):
           return VinculoSocial.INIMIGO
       if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_rival"):
           return VinculoSocial.RIVAL
       return VinculoSocial.CONHECIDO
   ```
4. Troque os literais em `marriage.py:138` (`"Aliado"`) e `populate.py:320,343`
   (`"Cônjuge"`, `"Amigo"`, `"Conhecido"`) por `VinculoSocial.X.value`.
**Validar:** `grep -rn '"Aliado"\|"Inimigo"\|"Conhecido"\|"Rival"\|"Cônjuge"' --include="*.py" engine/ builder/`
retorna apenas a definição do enum.
**Risco:** médio — **muda comportamento de propósito** (corrige bug). Registre isso no commit.

---

### R-B02 · Criar o enum `Genero` e eliminar `'M'` / `'F'`
**Arquivos:** `engine/models.py`, `engine/mechanics/reproduction.py`, `engine/mechanics/marriage.py:34`, `builder/populate.py`, `engine/ai/biography.py`, `engine/ai/generator.py`
**Problema:** `'M'` e `'F'` aparecem como literais em pelo menos 14 lugares, inclusive
em comparações (`npc.genero == 'M'`) e em construção de texto
(`'menino' if genero_bebe == 'M' else 'menina'`).
**Ação:**
1. Em `engine/models.py`:
   ```python
   class Genero(Enum):
       MASCULINO = "M"
       FEMININO  = "F"
   ```
2. Substitua **todas** as comparações por `== Genero.MASCULINO.value`.
3. Em `reproduction.py`, `random.choice(['M','F'])` vira
   `random.choice([g.value for g in Genero])`.
4. Os rótulos de exibição (`"menino"/"menina"`, `"Masculino ♂️"`) **não** entram no
   enum — são apresentação. Centralize-os numa constante de módulo no arquivo que
   exibe, não no modelo.
**Validar:** `grep -rn "== 'M'\|== \"M\"\|== 'F'\|== \"F\"" --include="*.py" engine/ builder/` retorna 0.
**Risco:** baixo

---

### R-B03 · Usar `EstagioVida` e `PROFISSAO_DEPENDENTE` em todo lugar
**Arquivos:** `engine/mechanics/logic.py:19`, `movement.py:14,42`, `actions.py:65,82,255`, `loop.py:105`
**Problema:** `EstagioVida` e a constante `PROFISSAO_DEPENDENTE` **já existem** em
`models.py`, mas o código continua escrevendo `'bebe'`, `'crianca'`, `'dependente'` à
mão. Em `movement.py:14` e `:42`:
```python
if getattr(npc, 'estagio_vida', '') == 'bebe' or npc.profissao == 'dependente':
```
**Ação:** substitua todas as ocorrências pelos símbolos existentes. `getattr` defensivo
some (ver `R-C02`).
**Validar:**
```bash
grep -rn "'bebe'\|'crianca'\|'dependente'\|'adulto'\|'idoso'\|'morto'" --include="*.py" engine/ builder/ web/
```
deve retornar apenas a definição do enum em `models.py`.
**Risco:** baixo

---

### R-B04 · Criar `NPC.eh_dependente()` e eliminar a lógica repetida
**Arquivos:** `engine/models.py`, `logic.py:19`, `actions.py:65,82,255`, `movement.py:14,42`, `loop.py:105`
**Problema:** a **mesma** expressão está copiada em 6 lugares:
```python
npc.profissao == "dependente" or npc.estagio_vida in ('bebe', 'crianca')
```
Se a regra mudar, muda em 6 lugares — e em `movement.py` a cópia já é **diferente**
(só olha `'bebe'`, não `'crianca'`).
**Ação:**
1. Em `NPC` (dataclass), some ao lado de `is_adulto`/`is_idoso`:
   ```python
   def eh_dependente(self) -> bool:
       """Bebê, criança ou adulto marcado como dependente — não trabalha, não
       socializa fora de casa e tem a conta paga por um responsável."""
       return (self.profissao == PROFISSAO_DEPENDENTE
               or self.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value))
   ```
2. Troque as 6 ocorrências por `npc.eh_dependente()`.
3. Em `movement.py`, a troca **corrige** o comportamento divergente: registre no commit.
**Validar:** as 6 expressões desaparecem; `grep -rn "eh_dependente" engine/` mostra 1 definição e ≥6 usos.
**Risco:** médio (unifica um comportamento hoje divergente)

---

### R-B05 · Criar `MetaChave` para as chaves de `mundo_meta`
**Arquivos:** `engine/models.py` (ou novo `engine/meta.py`), `run_simulation.py`, `engine/loop.py`, `engine/utils.py`, `web/dashboard.py`, `web/mestre_routes.py`, `engine/mechanics/mestre.py`, `builder/populate.py`
**Problema:** as chaves da tabela `mundo_meta` são strings digitadas à mão em 7
arquivos: `"simulacao_pausada"`, `"velocidade_simulacao"`,
`"mestre_avancar_minutos_restantes"`, `"hora_simulada"`, `"hora_simulada_iso"`,
`"cidade_simulada"`, `"cidades_ativas"`, `"mapa_terreno"`. Um erro de digitação em
qualquer uma é silencioso: `carregar_meta` devolve `None` e o sistema segue com o
default.
**Ação:**
1. Crie o enum:
   ```python
   class MetaChave(Enum):
       SIMULACAO_PAUSADA   = "simulacao_pausada"
       VELOCIDADE          = "velocidade_simulacao"
       AVANCAR_MINUTOS     = "mestre_avancar_minutos_restantes"
       HORA_FORMATADA      = "hora_simulada"
       HORA_ISO            = "hora_simulada_iso"
       CIDADE_SIMULADA     = "cidade_simulada"
       CIDADES_ATIVAS      = "cidades_ativas"
       MAPA_TERRENO        = "mapa_terreno"
   ```
2. Faça `DatabaseManager.salvar_meta`/`carregar_meta` aceitarem `MetaChave`:
   ```python
   def carregar_meta(self, chave) -> str:
       chave_str = chave.value if isinstance(chave, MetaChave) else chave
       ...
   ```
   (aceitar `str` também mantém `builder/fix/` e SQL ad-hoc funcionando)
3. Troque os literais nos 7 arquivos.
**Validar:** `grep -rn '"simulacao_pausada"\|"hora_simulada_iso"\|"velocidade_simulacao"' --include="*.py" .`
retorna apenas a definição do enum.
**Risco:** baixo

---

### R-B06 · Criar `Bioma` e servi-lo ao frontend
**Arquivos:** `cartographer/math/climate.py:14`, `web/composed_routes.py:~100 e ~285`, `web/static/js/mapa_composto.js:337-341`
**Problema:** os nomes de bioma existem em **quatro** lugares independentes:
- `ClimateProcessor.BIOME_IDS` (o ID canônico)
- `NOME_BIOMAS = {1: "Oceano", ...}` literal em `api_mapa_composto_info`
- **o mesmo dicionário, copiado literalmente**, em `api_continente_info`
- `biomeBadges` em `mapa_composto.js`, que ainda tem um `6: "🏰 Zona Urbana"` que não
  existe no Python

**Ação:**
1. Em `cartographer/math/climate.py` (ou novo `cartographer/math/biomas.py`):
   ```python
   class Bioma(Enum):
       OCEANO              = (1, "Oceano",              "🌊")
       DESERTO             = (2, "Deserto",             "🏜️")
       MEDITERRANEO        = (3, "Mediterrâneo",        "🌱")
       FLORESTA_TEMPERADA  = (4, "Floresta Temperada",  "🌲")
       MONTANHA_ROCHOSA    = (5, "Montanha Rochosa",    "🏔️")

       def __init__(self, id_numerico, rotulo, emoji):
           self.id_numerico = id_numerico
           self.rotulo = rotulo
           self.emoji = emoji

       @classmethod
       def por_id(cls, id_numerico: int):
           return next((b for b in cls if b.id_numerico == id_numerico), None)
   ```
2. Mantenha `BIOME_IDS` como um dicionário **derivado** do enum, para não reescrever a
   matemática vetorizada de `classify_biomes`:
   ```python
   BIOME_IDS = {b.name: b.id_numerico for b in Bioma}
   ```
3. Em `composed_routes.py`, apague os **dois** `NOME_BIOMAS` e use `Bioma.por_id`.
4. Adicione ao payload de `/api/continentes` uma entrada `"biomas"` com a tabela
   `{id: {rotulo, emoji}}`, e faça `mapa_composto.js` consumi-la em vez de manter
   `biomeBadges` local (ver `R-H04`).
**Validar:** `grep -rn "Mediterrâneo" --exclude-dir=venv .` retorna só a definição do
enum e o CSS.
**Risco:** médio (toca cartografia + web + JS)

---

### R-B07 · Extrair a época inicial do mundo para uma constante
**Arquivos:** novo `engine/tempo.py`, `engine/loop.py:34`, `engine/utils.py:226`, `engine/mechanics/reproduction.py:43,100`, `lifecycle.py:13,103`, `marriage.py:113`, `social.py:73`, `finance.py`, `builder/populate.py:260`, `web/dashboard.py:83`
**Problema:** `datetime(1200, 1, 1, 0, 0)` está escrito à mão em **8 arquivos**, e com
horas diferentes (`0,0` para contar dias; `6,0` como hora de início em `utils.py:226`;
`'1200-01-01T06:00:00'` como string em `dashboard.py:83`). Junto com ele vem o bloco
copiado:
```python
dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
```
que aparece **6 vezes**, idêntico.

**Ação:** crie `engine/tempo.py`:
```python
"""
MODULE: tempo.py
FUNÇÃO: Origem do calendário do mundo e formatação de data simulada.

DESCRIÇÃO:
    Ponto único do "Dia 1" do mundo. Antes desta classe, `datetime(1200,1,1)` estava
    escrito à mão em 8 arquivos, com horas divergentes entre eles — mudar a época
    exigiria caçar todas e acertar cada uma.
"""
from datetime import datetime

class RelogioMundo:
    EPOCA = datetime(1200, 1, 1, 0, 0)
    HORA_INICIAL_PADRAO = datetime(1200, 1, 1, 6, 0)
    ANOS_DE_VIDA_DE_REFERENCIA = 80.0   # ver R-B08

    @staticmethod
    def dia_do_mundo(data_simulada: datetime) -> int:
        return (data_simulada - RelogioMundo.EPOCA).days + 1

    @staticmethod
    def timestamp_rpg(data_simulada: datetime) -> str:
        """'Dia 42, 14:30' — o carimbo usado em todo Evento persistido."""
        return f"Dia {RelogioMundo.dia_do_mundo(data_simulada)}, {data_simulada.strftime('%H:%M')}"
```
Depois troque as 8 ocorrências de `datetime(1200,...)` e as 6 do bloco de
`timestamp_rpg` por chamadas a `RelogioMundo`.
**Validar:** `grep -rn "datetime(1200" --exclude-dir=venv --exclude-dir=docs .` retorna
apenas `engine/tempo.py`.
**Risco:** baixo

---

### R-B08 · Extrair a expectativa de vida de referência (`80.0`)
**Arquivos:** `engine/tempo.py` (criado em `R-B07`), `engine/mechanics/lifecycle.py:115`, `builder/populate.py:259`, `web/dashboard.py:115`
**Problema:** a conversão "dias de simulação → anos de idade" usa o literal `80.0` em
três arquivos diferentes, sem nome e sem explicação:
```python
idade_anos = int((idade_dias / limiar_morte) * 80.0)
```
Se um deles for alterado, a idade mostrada na UI diverge da usada na engine.
**Ação:** use `RelogioMundo.ANOS_DE_VIDA_DE_REFERENCIA` e extraia a conversão inteira
para um método:
```python
@staticmethod
def idade_em_anos(data_nascimento_iso: str, agora: datetime, dias_ate_a_morte: int) -> int:
    """Converte a idade em dias simulados para 'anos' narrativos, escalando pelo
    tempo de vida configurado. Retorna 0 se a data de nascimento for inválida."""
```
Os três chamadores passam a usar esse método.
**Validar:** `grep -rn "80\.0" --include="*.py" engine/ builder/ web/` retorna apenas a
constante.
**Risco:** baixo

---

### R-B09 · Nomear os limites de escala (0–100) do NPC
**Arquivos:** `engine/models.py`, `engine/loop.py:118,122-131`, `engine/mechanics/actions.py:38,168,191,209`, `decay.py:209`
**Problema:** `100`, `0`, `90` e `20` aparecem soltos em toda a engine como limites de
`energia`, `fome`, `social`, `saude` e `integridade`. O bloco
```python
npc.energia = max(0, min(100, npc.energia))
npc.fome    = max(0, min(100, npc.fome))
npc.social  = max(0, min(100, npc.social))
npc.saude   = max(0, min(100, npc.saude))
```
se repete parcialmente em `actions.py` com `if npc.social > 100.0: npc.social = 100.0`.
**Ação:**
1. Em `engine/models.py`, no topo:
   ```python
   ESCALA_MINIMA = 0.0
   ESCALA_MAXIMA = 100.0
   ```
2. Dê ao `NPC` um método de normalização e chame-o **num lugar só** (no fim do laço do
   tick, `loop.py`):
   ```python
   def normalizar_necessidades(self) -> None:
       """Prende energia/fome/social/saúde na faixa válida. Ponto único de clamp —
       as ações somam e subtraem livremente e o tick fecha a conta."""
       self.energia = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.energia))
       self.fome    = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.fome))
       self.social  = min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.social))
       self.saude   = int(min(ESCALA_MAXIMA, max(ESCALA_MINIMA, self.saude)))
   ```
3. Apague os clamps espalhados em `actions.py` (linhas 38-39, 168-169, 173-174,
   191-192, 209-210).
4. Os limiares de **decisão** (`fome > 90`, `fome < 20` em `loop.py:118,122`) **não são
   limites de escala** — são parâmetros de balanceamento. Mova-os para `config.json`
   em `biologia_e_sociedade`: `"inanicao_fome_limiar": 90`,
   `"recuperacao_sono_fome_maxima": 20`.
**Validar:** `grep -rn "min(100\|max(0, min(100\|> 100.0" --include="*.py" engine/`
retorna apenas o método `normalizar_necessidades`.
**Risco:** médio (mexe na ordem dos clamps; rode uma simulação e compare os logs)

---

### R-B10 · Nomear o divisor de log (`tick_count % 4`)
**Arquivos:** `engine/mechanics/actions.py:122,143,196,232`, `kingdom.py:36`
**Problema:** `if engine.tick_count % 4 == 0:` aparece 5 vezes para "logar só de vez em
quando". O `4` não tem nome nem está em config.
**Ação:**
1. Em `config.json`, bloco novo `"observabilidade"`:
   ```json
   "observabilidade": { "log_acao_a_cada_n_ticks": 4 }
   ```
2. Adicione um helper em `WorldLogger`:
   ```python
   @staticmethod
   def deve_logar_amostra(tick_count: int, config: dict) -> bool:
       """Amostragem de log de ação: registrar todo tick de 1 min inunda o arquivo."""
       n = cfg_get(config, "observabilidade", "log_acao_a_cada_n_ticks")
       return tick_count % n == 0
   ```
3. Troque as 5 ocorrências.
**Validar:** `grep -rn "% 4 == 0" --include="*.py" engine/` retorna 0.
**Risco:** baixo

---

### R-B11 · Mover as probabilidades soltas de `movement.py` para o config
**Arquivos:** `engine/mechanics/movement.py:71,103`
**Problema:** duas decisões de comportamento são literais:
- `if num_dep > 0 and random.random() < 0.50:` — chance de ficar em casa com filhos
- `if locais_comida and random.random() < 0.5:` — chance de comer fora

O comentário ao lado do segundo já explica a intenção, mas o número não é ajustável sem
editar código.
**Ação:** adicione em `config.json`, bloco `ia_decisao`:
```json
"chance_ficar_em_casa_com_dependentes": 0.50,
"chance_comer_fora_de_casa": 0.50
```
e leia com `cfg_get`.
**Validar:** `grep -rn "random.random() < 0\." --include="*.py" engine/mechanics/movement.py` retorna 0.
**Risco:** baixo

---

### R-B12 · Mover as listas de fallback da IA para o config
**Arquivos:** `engine/ai/biography.py:33-34,60-73`, `engine/ai/generator.py:28-29,68-70`, `engine/ai/storyteller.py:32-38,40-47`, `builder/populate.py:244`
**Problema:** quando o Ollama está offline, o sistema cai em listas de nomes,
personalidades, backgrounds e eventos **escritas dentro do código Python**. São ~60
strings de conteúdo criativo misturadas com lógica. Mudar o tema do mundo (de
"Fantasia Medieval" para outro) exige editar 4 arquivos de código.
**Ação:**
1. Crie `engine/ai/fallbacks.json` com a estrutura:
   ```json
   {
     "nomes_bebe": { "M": ["Arthur", "..."], "F": ["Lyra", "..."] },
     "nomes_npc":  { "M": [...], "F": [...], "sobrenomes": [...] },
     "racas": { "Humano": 0.7, "Elfo": 0.1, "Anão": 0.1, "Orc": 0.1 },
     "personalidades": [...],
     "backgrounds": [...],
     "locais_oficina": [...],
     "locais_sociais": [...],
     "eventos_globais": [ { "titulo": "...", "descricao": "...", "tipo": "...", "modificadores": {...}, "duracao_ticks": 6 } ]
   }
   ```
2. Crie `engine/ai/fallbacks.py` com uma classe que carrega o JSON uma vez e expõe
   sorteios nomeados (`sortear_nome_bebe(genero)`, `sortear_evento_global()`, …).
3. Substitua as listas inline pelas chamadas.
4. Em `storyteller.py:39-47`, note que `random.randint(0, 3)` está acoplado ao tamanho
   da lista — depois da mudança, sorteie o **objeto inteiro**, não um índice.
**Validar:** `grep -rn '"Arthur"\|"Nevasca Súbita"\|"Stonefist"' --include="*.py" .` retorna 0.
**Risco:** médio

---

# Bloco C — Modelo de dados e invariantes

### R-C01 · Declarar `num_dependentes` no dataclass `NPC`
**Arquivos:** `engine/models.py`, `engine/loop.py:100-106`, `logic.py:98`, `movement.py:70`
**Problema:** `loop.py:100` faz `npc.num_dependentes = 0` em um campo que **não existe**
no dataclass. `logic.py` e `movement.py` então leem defensivamente com
`getattr(npc, 'num_dependentes', 0)`. É um atributo fantasma: não aparece no modelo, não
é persistido, não é documentado.
**Ação:**
1. Declare-o no dataclass, **marcado como derivado**:
   ```python
   # Campo DERIVADO, recalculado por GameLoop a cada tick a partir dos moradores da
   # casa. Não é persistido (ver DatabaseManager.salvar_npc) e não deve ser escrito
   # por nenhum outro módulo.
   num_dependentes: int = 0
   ```
2. Troque os dois `getattr(...)` por `npc.num_dependentes`.
**Validar:** `grep -rn "getattr(npc, 'num_dependentes'" engine/` retorna 0.
**Risco:** baixo

---

### R-C02 · Eliminar o `getattr` defensivo sobre campos que existem
**Arquivos:** `engine/mechanics/movement.py` (9 ocorrências), `logic.py` (5), `actions.py` (1), `utils.py` (3)
**Problema:** o código consulta campos declarados no dataclass com `getattr` e default:
```python
getattr(l, 'status', 1)          # Local.status existe, default 1
getattr(l, 'categoria', '')      # Local.categoria existe, default 'generic'
getattr(loc_trab, 'status', 1)   # idem
getattr(local, 'tipo', '')       # idem
```
Isso mascara erros: se o campo for renomeado, o código continua rodando com o default
errado em vez de estourar.
**Ação:** substitua por acesso direto ao atributo. **Exceção:** `utils.py:198` usa
`getattr(l, 'descricao', '')` — que some junto com `R-C03`.
**Validar:**
```bash
grep -rn "getattr(" --include="*.py" engine/ | grep -v "logger.py"
```
deve retornar 0 linhas.
**Risco:** baixo

---

### R-C03 · Usar `Local.dono_npc_id` em vez de parsear `descricao`
**Arquivos:** `engine/mechanics/housing.py:182`, `engine/utils.py:191-200`, `engine/mechanics/actions.py:238,242`
**Problema:** **o problema de modelagem mais grave do projeto.** O dono de uma obra é
gravado como **texto livre** dentro de outro campo:
```python
descricao=f"Dono: {n1.id}"                      # housing.py:182
if npc.id in getattr(l, 'descricao', '')        # utils.py:198  ← substring!
dono_id = obra.descricao.replace("Dono: ", "")  # actions.py:242
nome_familia = obra.nome.replace("Obra de ", "")# actions.py:238
```
E o campo **`Local.dono_npc_id` já existe** no dataclass (`models.py:118`) e no schema
(`schema.sql:34`), populado a partir do GeoJSON, mas nunca usado aqui.

A busca por substring é frágil de verdade: `npc.id in descricao` casa `npc_01` dentro de
`npc_012`.

**Ação:**
1. Em `housing.py:176-187`, troque `descricao=f"Dono: {n1.id}"` por:
   ```python
   descricao=f"Obra da família {sobrenome}, em construção.",
   dono_npc_id=n1.id,
   ```
2. Em `utils.py`, reescreva `obter_obra_do_npc`:
   ```python
   @staticmethod
   def obter_obra_do_npc(locais: Dict[str, 'Local'], npc: NPC):
       """Retorna a obra (Local com status=0) cujo dono é o NPC ou seu cônjuge."""
       if not locais:
           return None
       donos = {npc.id}
       if npc.conjuge_id:
           donos.add(npc.conjuge_id)
       for local in locais.values():
           if local.tipo == TipoLocal.CASA.value and local.status == 0 and local.dono_npc_id in donos:
               return local
       return None
   ```
3. Em `actions.py:242`, troque o `replace("Dono: ", "")` por `obra.dono_npc_id`.
4. Em `actions.py:238`, o `obra.nome.replace("Obra de ", "")` também parseia um prefixo.
   Guarde o sobrenome no momento da criação — o caminho mais barato é derivar o nome
   final do próprio `dono_npc_id`:
   ```python
   dono = next((n for n in engine.npcs if n.id == obra.dono_npc_id), npc)
   obra.nome = f"Residência {dono.nome.split()[-1]}"
   ```
**Validar:**
```bash
grep -rn '"Dono: "\|Obra de \|descricao.replace' --include="*.py" engine/
```
retorna 0.
**Risco:** médio — **corrige bug de colisão de substring**. Registre no commit.
> ⚠️ Bancos já gerados terão obras antigas com `dono_npc_id` vazio. Isso só as torna
> não-encontráveis (a obra vira um prédio inacabado inerte). Aceitável: o fluxo normal
> é `builder/reset_world.sh`. Se quiser preservar, adicione um passo de migração em
> `builder/fix/repair_db.py`.

---

### R-C04 · Tipar `humor` como enum no `NPC`
**Arquivos:** `engine/models.py:140`, `engine/mechanics/mood.py`, `engine/mechanics/mestre.py:146`
**Problema:** `humor: str = "Neutro"` — existe `HumorNPC` no mesmo arquivo, 60 linhas
acima. `mood.py` mantém uma lista paralela `_ESCALA_HUMOR` de `.value`s. `mestre.py:146`
aceita `d.get("humor", "Neutro")` **direto da IA**, sem validar contra o enum.
**Ação:**
1. Mantenha o campo como `str` **no dataclass** (é o que vai pro banco) mas some um
   atributo `ordem` ao enum, tornando `_ESCALA_HUMOR` desnecessária:
   ```python
   class HumorNPC(Enum):
       ANGUSTIADO = ("Angustiado", 0)
       TRISTE     = ("Triste", 1)
       NEUTRO     = ("Neutro", 2)
       CONTENTE   = ("Contente", 3)
       ALEGRE     = ("Alegre", 4)
       PANICO     = ("Em Pânico", None)   # forçado externamente, fora da escala
       MEDO       = ("Amedrontado", None)

       def __init__(self, rotulo, ordem):
           self._value_ = rotulo
           self.ordem = ordem

       @classmethod
       def escala_normal(cls):
           return sorted((h for h in cls if h.ordem is not None), key=lambda h: h.ordem)
   ```
2. Em `mood.py`, apague `_ESCALA_HUMOR` e use `HumorNPC.escala_normal()`.
3. Em `mestre.py`, valide a entrada da IA:
   ```python
   humor_bruto = d.get("humor")
   try:
       humor = HumorNPC(humor_bruto).value
   except ValueError:
       humor = HumorNPC.NEUTRO.value
   ```
**Validar:** `grep -rn "_ESCALA_HUMOR"` retorna 0; os testes passam.
**Risco:** médio

---

### R-C05 · Simplificar `is_adulto` / `is_idoso` / `esta_vivo`
**Arquivos:** `engine/models.py:181-191`
**Problema:** os três comparam contra **o enum e o `.value`**:
```python
return self.estagio_vida == EstagioVida.ADULTO.value or self.estagio_vida == EstagioVida.ADULTO
```
Isso existe porque, em algum momento, o campo às vezes guardava o enum e às vezes a
string. Depois do `R-B03`, o campo guarda **sempre** a string (é o que vai pro SQLite).
**Ação:** deixe apenas a comparação com `.value`. Documente a decisão no dataclass:
```python
# INVARIANTE: estagio_vida guarda SEMPRE EstagioVida.X.value (str), nunca o membro
# do enum. É o valor que vai direto para a coluna TEXT do SQLite.
estagio_vida: str = EstagioVida.ADULTO.value
```
E troque os defaults literais (`"adulto"`, `"Neutro"`, `"M"`) pelos `.value` dos enums.
**Validar:** testes passam; rode uma simulação de ~200 ticks e confirme que NPCs ainda
envelhecem.
**Risco:** médio

---

### R-C06 · Padronizar o retorno de `DatabaseManager`: lista vs. dicionário
**Arquivos:** `engine/database.py:107,125,169`
**Problema:** `carregar_npcs()` devolve `list[NPC]`, `carregar_locais()` devolve
`dict[str, Local]` e `carregar_cidades()` devolve `list[dict]` (dicionários crus, não
objetos). Três formas de retorno diferentes na mesma classe. `SimulationEngine.__init__`
tem que reindexar cidades à mão:
```python
self.cidades = {c["id"]: c for c in self.db.carregar_cidades()}
```
**Ação:**
1. Crie um dataclass `Cidade` em `models.py` com os campos da tabela
   (`id, continente_uuid, nome, tamanho, tipo, x_global, y_global`).
2. Renomeie os métodos para dizer o que devolvem:
   - `carregar_npcs()` → mantém, devolve `list[NPC]`
   - `carregar_locais()` → `carregar_locais_por_id()` devolve `dict[str, Local]`
   - `carregar_cidades()` → `carregar_cidades_por_id()` devolve `dict[int, Cidade]`
3. Atualize os chamadores (`core.py`, `populate.py`, `composed_routes.py`).
**Validar:** `grep -rn 'cidade.get("x_global"\|cidade\["x_global"\]' engine/ builder/`
retorna 0 (acesso passa a ser por atributo).
**Risco:** médio

---

# Bloco D — Quebra de métodos gigantes (SRP)

> **Regra de tamanho adotada** (registrada em `11_ARQUITETURA.md`):
> método ≤ 40 linhas · classe ≤ 300 linhas · arquivo ≤ 400 linhas.
> Acima disso, exige justificativa escrita na docstring.

### R-D01 · Quebrar `NPCBrain.calcular_utilidade` em avaliadores por ação
**Arquivos:** `engine/mechanics/logic.py:8-151` (144 linhas), novo `engine/mechanics/utilidade/`
**Problema:** **o método mais problemático do projeto.** 144 linhas calculam a utilidade
de 7 ações diferentes, sequencialmente, num único corpo. Tem:
- 7 blocos de responsabilidades independentes que só compartilham `utilidades`
- 3 recálculos do mesmo predicado `esta_descansando` (linhas 44, 65)
- 2 `import` no meio do corpo (linhas 83, 122)
- mistura de `cfg["x"]` e `cfg_get(cfg, "x")` — os primeiros **furam a política de
  configuração estrita**
- `except: continue` silencioso no laço de eventos globais (linha 140)
- argumento mutável default `eventos_globais: List = []` (linha 8) — armadilha clássica
  do Python

**Ação:** converta em **Strategy**, seguindo o padrão que `cartographer/cities/modelos/`
já usa bem.

1. Crie o pacote `engine/mechanics/utilidade/` com `base.py`:
   ```python
   """
   MODULE: utilidade/base.py
   FUNÇÃO: Contrato de um avaliador de utilidade de ação (Utility AI).

   DESCRIÇÃO:
       Cada ação do enum `Acao` tem UM avaliador, que responde uma pergunta só:
       "quanto este NPC quer fazer isto, agora?". O NPCBrain só soma as respostas e
       escolhe o máximo — ele não conhece a regra de nenhuma ação em particular.
   """
   from abc import ABC, abstractmethod
   from dataclasses import dataclass
   from typing import Dict, List
   from ...models import NPC, Acao


   @dataclass(frozen=True)
   class ContextoDecisao:
       """Tudo que um avaliador pode consultar. Imutável de propósito: nenhum
       avaliador altera o estado do NPC — isso é trabalho de NPCActionManager."""
       npc: NPC
       hora: int
       config: dict
       locais: Dict[str, 'Local']
       eventos_globais: List[dict]


   class AvaliadorDeUtilidade(ABC):
       acao: Acao = None

       @abstractmethod
       def avaliar(self, ctx: ContextoDecisao) -> float:
           """Utilidade bruta desta ação. 0.0 = não quer / não pode."""
   ```

2. Um arquivo por ação, cada um com **um** `avaliar` curto:

   | Arquivo | Classe | Linhas de origem em `logic.py` |
   |---|---|---|
   | `comer.py` | `AvaliadorComer` | 23-37 |
   | `dormir.py` | `AvaliadorDormir` | 39-61 |
   | `trabalhar.py` | `AvaliadorTrabalhar` | 63-72 |
   | `socializar.py` | `AvaliadorSocializar` | 74-100 |
   | `cuidar_prole.py` | `AvaliadorCuidarProle` | 102-111 |
   | `construir.py` | `AvaliadorConstruir` | 113-124 |
   | `ocioso.py` | `AvaliadorOcioso` | 126 |

3. Os modificadores transversais (humor, eventos globais, persistência, trava de
   dependente — linhas 128-149) **não** são avaliadores: são pós-processadores.
   Coloque-os em `modificadores.py` como funções puras
   `aplicar(utilidades: dict, ctx) -> dict`.

4. `NPCBrain` fica assim:
   ```python
   class NPCBrain:
       AVALIADORES = (AvaliadorComer(), AvaliadorDormir(), AvaliadorTrabalhar(),
                      AvaliadorSocializar(), AvaliadorCuidarProle(),
                      AvaliadorConstruir(), AvaliadorOcioso())
       MODIFICADORES = (aplicar_humor, aplicar_eventos_globais,
                        aplicar_trava_dependente, aplicar_persistencia)

       @staticmethod
       def calcular_utilidade(ctx: ContextoDecisao) -> Dict[Acao, float]:
           utilidades = {acao: 0.0 for acao in Acao}
           for avaliador in NPCBrain.AVALIADORES:
               utilidades[avaliador.acao] = avaliador.avaliar(ctx)
           for modificador in NPCBrain.MODIFICADORES:
               utilidades = modificador(utilidades, ctx)
           return utilidades
   ```

5. **Junto com a quebra, corrija:**
   - `eventos_globais: List = []` → `eventos_globais: List = None` + `or []` no corpo,
     ou (melhor) exija o campo no `ContextoDecisao`.
   - todos os `cfg["x"]` viram `cfg_get(cfg, "x")` — **12 ocorrências**.
   - `cfg.get("hora_fim_sono_obrigatorio", 6)` (linha 56) → `cfg_get(cfg, "hora_fim_sono_obrigatorio")`.
     A chave **existe** no config.json; o default silencioso é herança antiga.
   - `except: continue` (linha 140) → `except (json.JSONDecodeError, KeyError, TypeError) as e:`
     com `WorldLogger.warning`.
   - os literais `10` (fome mínima para continuar comendo) e `100` viram config /
     `ESCALA_MAXIMA`.

**Validar:**
- `wc -l engine/mechanics/logic.py` < 80
- nenhum arquivo novo em `utilidade/` passa de 60 linhas
- **teste de regressão obrigatório:** antes de refatorar, grave a saída de
  `calcular_utilidade` para 200 NPCs sintéticos em vários horários; depois, confirme
  que os valores são idênticos.
**Risco:** **alto** — é o coração do comportamento. Faça com o teste de regressão acima,
ou não faça.

---

### R-D02 · Quebrar `GameLoop.executar_tick`
**Arquivos:** `engine/loop.py:27-149` (123 linhas)
**Problema:** um método faz: avançar relógio, persistir meta, logar, disparar 4 rotinas
agendadas, aplicar metabolismo, contar dependentes, decidir, executar, aplicar saúde,
clampar, calcular humor, processar morte, persistir, limpar mortos, processar partos,
processar interações. Além disso:
- `engine.config["metabolismo"]` (linha 73) **acessa o config direto**, furando `cfg_get`
- `meta.get("multiplicador_fome_dormindo", 0.33)` (linha 79) — **default silencioso
  proibido pela política do projeto**, e a chave existe no config
- horas de agendamento `6` e `8` (linhas 59, 63) são literais, enquanto `concepcao_hora`
  e `crescimento_hora` vêm do config — inconsistência dentro do mesmo método

**Ação:** mantenha `GameLoop` como orquestrador e extraia:

```python
class GameLoop:
    @staticmethod
    def executar_tick(engine):
        GameLoop._avancar_relogio(engine)
        eventos_globais = GameLoop._atualizar_eventos_globais(engine)
        GameLoop._executar_rotinas_agendadas(engine)

        maes_em_parto = []
        for npc in engine.npcs:
            if not npc.esta_vivo():
                continue
            GameLoop._aplicar_metabolismo(engine, npc, maes_em_parto)
            GameLoop._decidir_e_executar(engine, npc, eventos_globais)
            GameLoop._aplicar_consequencias_de_saude(engine, npc)
            npc.normalizar_necessidades()
            NPCMoodManager.processar_humor(engine, npc)
            if npc.saude <= 0:
                NPCLifecycleManager.processar_morte(engine, npc)
                continue
            engine.db.salvar_npc(npc)

        GameLoop._remover_falecidos(engine)
        GameLoop._processar_partos(engine, maes_em_parto)
        NPCSocialManager.processar_interacoes(engine)
```

Cada privado fica com ≤ 25 linhas. A contagem de dependentes (linhas 100-106) vai para
`NPCUtils.contar_dependentes_na_casa(npcs, npc)` — ela já é **quase idêntica** ao bloco
de `actions.py:78-83`, que passa a usar o mesmo helper.

**Junto com a quebra, corrija:**
- `engine.config["metabolismo"]` → `cfg_get(engine.config, "metabolismo")`
- os dois `.get(..., default)` → `cfg_get(...)` sem default
- as horas `6` e `8` → `config.json`:
  `"habitacao_hora": 6`, `"pagamento_reino_hora": 8` em `biologia_e_sociedade`

**Validar:** `wc -l engine/loop.py` < 160; nenhum método passa de 30 linhas; simulação
de 500 ticks produz os mesmos eventos que antes (compare `logs/world.log`).
**Risco:** médio

---

### R-D03 · Quebrar `populate_world`
**Arquivos:** `builder/populate.py:127-353` (227 linhas), novo `builder/populador.py`
**Problema:** uma função procedural com 10 fases numeradas em comentário, ~12 variáveis
locais vivas do começo ao fim, e uma função aninhada (`generate_single_npc`) que captura
`nomes_gerados` de fora e é chamada em **thread pool** — captura mutável compartilhada
entre threads sem lock.
**Ação:** converta numa classe com fases explícitas:
```python
class PopuladorDeMundo:
    """Orquestra o povoamento inicial. Cada fase é um método; o estado compartilhado
    entre fases é atributo da instância, não variável local de uma função de 227 linhas."""

    def __init__(self, db: DatabaseManager, tema: str, usar_ia: bool, ia_max_thread: int):
        ...

    def executar(self, num_npcs: int) -> None:
        self._importar_cartografia()
        self._eleger_cidade_spawn()
        self._importar_geometria_das_cidades()
        self._coletar_locais_de_trabalho()
        dnas = self._gerar_dnas_em_paralelo(num_npcs)
        self._criar_npcs(dnas)
        self._formar_casais_iniciais()
        self._estabelecer_lacos_sociais()
        self._inicializar_mercado_de_trabalho()
```
**Junto com a quebra, corrija:**
- `nomes_gerados` compartilhado entre threads: colete os nomes **depois** do
  `executor.map`, não dentro do worker. Hoje a lista é lida pela IA para evitar
  duplicatas, mas está sendo escrita fora do pool — ou seja, a deduplicação já não
  funciona de forma confiável. Documente ou corrija explicitamente.
- `num_casas = 5` (linha 114) → config `geracao_urbana.casas_paliativas`
- `'adulto'` / `'idoso'` (linhas 254, 257) → `EstagioVida.X.value`
- `datetime(1200,1,1,0,0)` e `80.0` (linhas 259-260) → `RelogioMundo` (`R-B07`/`R-B08`)
- `random.randint(10, 99)` no nome de fallback → some com `R-B12`
**Validar:** `builder/populate.py` vira um CLI fino (< 50 linhas: `argparse` + chamada).
`./builder/reset_world.sh` roda até o fim e gera o mesmo número de NPCs.
**Risco:** médio

---

### R-D04 · Quebrar `TileCartographer.gerar_janela`
**Arquivos:** `cartographer/world/tile_cartographer.py:92-300` (~180 linhas)
**Problema:** um método faz: montar a grade, gerar 3 campos de ruído, iterar continentes
(com culling, distorção costeira, perfil geológico, climatologia), aplicar vinheta,
gerar ruído marinho, mesclar terra/mar, aplicar campo de detalhe, calcular clima,
classificar biomas. São 6 etapas independentes e ~15 variáveis locais vivas.
**Ação:** este é o código mais delicado do projeto (tem testes de determinismo bit a
bit). Refatore **conservadoramente**, extraindo apenas privados que recebem e devolvem
arrays, sem reordenar nada:
```python
def gerar_janela(self, x0, y0, x1, y1, largura, altura, oitavas_extra=0,
                  _desabilitar_culling=False, retornar_donos=False):
    grid_x, grid_y = self._montar_grade(x0, y0, x1, y1, largura, altura)
    ruidos = self._gerar_campos_de_ruido(grid_x, grid_y, oitavas_extra)
    massa = self._acumular_continentes(grid_x, grid_y, ruidos, x0, y0, x1, y1,
                                        oitavas_extra, _desabilitar_culling, retornar_donos)
    altitude = self._mesclar_terra_e_mar(massa, grid_x, grid_y, oitavas_extra)
    altitude_final = self._aplicar_detalhe_local(altitude, grid_x, grid_y, largura, x0, x1)
    return self._classificar_clima_e_bioma(altitude, altitude_final, massa, grid_x, grid_y,
                                            retornar_donos)
```
**Junto com a quebra, corrija apenas:**
- `offset=12345` e `offset=9999` (linhas 140, 235) → constantes nomeadas de classe:
  `OFFSET_RUIDO_COSTA = 12345`, `OFFSET_RUIDO_MAR = 9999`, com comentário explicando que
  mudá-las **muda o mundo gerado**.
- `0.02` e `0.90` no ruído marinho → `config.json["cartografia"]`:
  `"ruido_mar_piso"` e `"ruido_mar_teto_fracao_nivel_mar"`.
- `"Alpino"` (linha 166) → constante `PERFIL_GEOLOGICO_PADRAO`.
- `tile_size=256, seed=1337` em `generate_world.py:39` → `config.json["cartografia"]`
  (`tile_size_px` **já existe** lá; a semente precisa de chave nova `mundo_seed`).
**Validar:** **obrigatório** — `venv/bin/python -m pytest tests/test_cartografia.py -v`
deve passar inteiro. Esses testes travam igualdade bit a bit entre zooms; se passarem, a
refatoração é segura.
**Risco:** **alto** — só faça com os testes verdes antes e depois.

---

### R-D05 · Quebrar `GeradorCidade._distribuir_edificios`
**Arquivos:** `cartographer/cities/generate_city_geometry.py:350-465` (~110 linhas)
**Problema:** um método faz três passadas de distribuição (marcos, comércio de bairro,
residências) e ainda constrói os índices auxiliares. Tem uma closure (`tem_vaga`) que
referencia `ocupados`, definido **depois** dela — funciona por escopo tardio do Python,
mas é frágil e confuso de ler.
**Ação:** extraia uma estrutura de estado e três métodos:
```python
@dataclass
class _AlocacaoDeLotes:
    """Índices auxiliares da distribuição: que lote pertence a que quarteirão, que
    quarteirão pertence a que zona, e que lote já foi tomado."""
    lotes_por_quarteirao: dict
    quarteiroes_por_zona: dict
    ocupados: dict

    def tem_vaga(self, quadra) -> bool:
        return any(p not in self.ocupados for p in self.lotes_por_quarteirao[quadra.id])
```
e depois:
```python
def _distribuir_edificios(self, malha):
    alocacao = self._indexar_lotes()
    self._alocar_marcos(alocacao)
    self._alocar_comercio_de_bairro(alocacao)
    self._emitir_edificios(alocacao)
```
**Junto com a quebra, corrija:**
- `0.95` / `0.15` (linha 344) → config
  `cidade_geo_edificacao_taxa_ocupacao_min` / `_max`
- `"Residência", "residencia", 5, 0` e `80` (linhas 440, 445) → config
  `cidade_geo_residencia_padrao: { capacidade, salario_base }`
**Validar:** `venv/bin/python -m pytest tests/test_cidades.py -v` passa (inclui o teste
de determinismo e o de teto de notáveis). Os `.geojson` gerados devem ter o **mesmo
md5** do baseline de `R-A01`.
**Risco:** **alto** — a geração é determinística por semente; qualquer mudança na ordem
de consumo do `rng` muda todas as cidades. Use o md5 como juiz.

---

### R-D06 · Quebrar `engine/utils.py` em módulos por assunto
**Arquivos:** `engine/utils.py` (289 linhas, 4 classes sem relação)
**Problema:** arquivo "utils" clássico: `GeoUtils` (geometria + numpy + cache de arquivo),
`NPCUtils` (regras de domínio de NPC), `LocationUtils` (regras de domínio de Local) e
`CartographyImporter` (ETL de manifesto para banco). São 4 responsabilidades e 4 razões
diferentes para o arquivo mudar. Além disso, há `import` dentro de função em 5 métodos
(sintoma de import circular) e 2 `except:` nus.
**Ação:** divida em:

| Novo arquivo | Conteúdo | Observação |
|---|---|---|
| `engine/geo.py` | `GeoUtils` | mantém o cache de `.npz` |
| `engine/consultas_npc.py` | `NPCUtils` | consultas sobre a população |
| `engine/consultas_local.py` | `LocationUtils` | classificação de locais |
| `builder/importador_cartografia.py` | `CartographyImporter` | é **ferramenta de build**, não runtime da engine — só `populate.py` usa |

**Junto com a divisão, corrija:**
- os `import` locais viram imports de topo (o ciclo some com a divisão)
- `except:` (linhas 212, 224) → `except ValueError:`
- `LocationUtils.is_local_publico` (linha 240) classifica por **substring de nome**
  (`'praça' in nome.lower()`). Isso é heurística de texto livre no meio de uma regra de
  domínio. Mova a lista `palavras_publicas` para `config.json`
  (`geracao_urbana.palavras_chave_local_publico`) e marque na docstring que é um
  paliativo até `CategoriaLocal.PUBLICO` estar corretamente populado em todos os locais.
**Validar:** `engine/utils.py` não existe mais; nenhum arquivo novo passa de 120 linhas;
`grep -rn "from ..utils import\|from .utils import" engine/` retorna 0.
**Risco:** médio (muitos imports mudam)

---

### R-D07 · Quebrar `web/composed_routes.py`
**Arquivos:** `web/composed_routes.py` (633 linhas) → `web/rotas/`
**Problema:** o maior arquivo Python do projeto mistura: 3 caches em memória, 2
calculadoras de janela de mundo, 6 rotas de imagem/info, o servidor de tiles, o leitor de
GeoJSON e o agregador de camadas vetoriais. Além disso:
- `NOME_BIOMAS` está **copiado literalmente** em duas funções (resolve em `R-B06`)
- `_janela_continente` (207-223) e `_janela_regiao` (318-336) repetem a mesma conta de
  "resolução de imagem proporcional ao aspecto"
- `manifest.get("dimensao_global", 768)` — o default `768` aparece **3 vezes**
- `api_regiao_entities` (linha 405) cria um `DatabaseManager`, descarta, e abre
  `sqlite3.connect(db.db_path)` cru
- `import` dentro de função em 4 rotas (`from PIL import Image`, `import io as _io`, …)
- **10 blocos** `except Exception as e: return jsonify({"error": str(e)}), 500` idênticos

**Ação:** crie o pacote `web/rotas/` e distribua:

| Arquivo | Responsabilidade | Origem |
|---|---|---|
| `web/rotas/__init__.py` | registra os blueprints | — |
| `web/rotas/mapa.py` | `/api/mapa_composto/*`, `/api/continentes`, `/api/continente/*` | 76-307 |
| `web/rotas/regiao.py` | `/api/regiao/<nome>/*` | 309-443 |
| `web/rotas/tiles.py` | `/tiles/<z>/<x>/<y>.png` | 445-460 |
| `web/rotas/features.py` | `/api/mapa/features` e leitura de GeoJSON | 462-633 |
| `web/janelas.py` | `_janela_continente`, `_janela_regiao`, `_gerar_janela_com_cache` | 22-74, 207-223, 318-336 |
| `web/cache_mapa.py` | os 3 caches por `mtime` | 20-39, 467-505 |

**Junto com a divisão, corrija:**
1. Unifique a conta de resolução:
   ```python
   def resolucao_de_imagem(largura_mundo, altura_mundo, alvo_maior_lado_px):
       """Resolução proporcional ao aspecto real da janela — nunca força quadrado,
       então a isotropia sai de graça (Fase 0.5)."""
       fator = alvo_maior_lado_px / max(largura_mundo, altura_mundo)
       return (max(1, round(largura_mundo * fator)), max(1, round(altura_mundo * fator)))
   ```
2. Substitua os 10 `try/except` por **um** tratador de erro no blueprint:
   ```python
   @composed_bp.errorhandler(Exception)
   def erro_inesperado(e):
       WorldLogger.error(f"[API] {request.path}: {e}")
       return jsonify({"error": str(e)}), 500
   ```
   As rotas perdem o `try` e ficam com 6-10 linhas cada.
3. `manifest.get("dimensao_global", 768)` → leia de
   `cfg_get(CARTOGRAPHER_CONFIG, "mundo_tiles_por_lado") * cfg_get(..., "tile_size_px")`
   quando o manifesto não trouxer. O `768` some.
4. Suba todos os `import` para o topo do módulo.
5. `api_regiao_entities` passa a usar **só** `DatabaseManager` (ver `R-E01`).
**Validar:** nenhum arquivo em `web/rotas/` passa de 200 linhas; todas as rotas
respondem igual (teste manual com `curl` em cada endpoint).
**Risco:** médio

---

# Bloco E — Camada de acesso a dados

### R-E01 · Uma única porta de entrada para o banco
**Arquivos:** `engine/database.py`, `web/dashboard.py`, `web/composed_routes.py`, `engine/mechanics/market.py`, `engine/mechanics/mestre.py`, `engine/mechanics/events.py`, `engine/mechanics/reproduction.py`, `builder/storyteller.py`
**Problema:** existem **três** formas de falar com o SQLite no runtime:
1. `DatabaseManager` com pool de 5 conexões e WAL
2. `sqlite3.connect(...)` cru em `web/dashboard.py:22` e `composed_routes.py:405`
3. SQL cru **dentro da camada de mecânicas**, usando o `connection()` do
   `DatabaseManager` mas escrevendo a query na regra de negócio:
   `market.py:77-176`, `mestre.py:26-149`, `events.py:21-28`, `reproduction.py:184-190`

Consequência prática: `web/dashboard.py` abre uma conexão nova por requisição, sem WAL
configurado, com `timeout=20`, competindo com a engine.

**Ação:** **não** tente mover todo SQL para `DatabaseManager` de uma vez — ele viraria um
arquivo de 800 linhas (o problema que estamos resolvendo). Divida por assunto:

1. Crie `engine/repositorios/` com uma classe por agregado, todas recebendo o
   `DatabaseManager` por construtor:

   | Repositório | Métodos | Origem do SQL |
   |---|---|---|
   | `RepositorioNPC` | `carregar_todos`, `salvar`, `renomear`, `buscar_desempregados` | `database.py:147-209`, `market.py:106-123`, `reproduction.py:186` |
   | `RepositorioLocal` | `carregar_por_id`, `salvar`, `buscar_com_vagas`, `mapear_categorias_genericas` | `database.py:114-145`, `market.py:34-61,77-82` |
   | `RepositorioEvento` | `salvar`, `carregar_globais_ativos`, `decrementar_globais`, `coletar_apos_rowid`, `ultimo_rowid` | `database.py:68-80,211-217`, `events.py:21-28`, `mestre.py:53-71` |
   | `RepositorioMeta` | `salvar`, `carregar` (com `MetaChave`) | `database.py:82-92` |
   | `RepositorioMestre` | conversas do Modo Mestre | `database.py:231-258` |
   | `RepositorioMundo` | continentes, cidades | `database.py:94-112` |

2. `DatabaseManager` fica **só** com: pool de conexões, `connection()`, `_init_db()` e
   os repositórios como propriedades:
   ```python
   class DatabaseManager:
       def __init__(self, db_path=CAMINHO_BANCO_PADRAO, pool_size=5):
           ...
           self.npcs    = RepositorioNPC(self)
           self.locais  = RepositorioLocal(self)
           self.eventos = RepositorioEvento(self)
           self.meta    = RepositorioMeta(self)
           self.mestre  = RepositorioMestre(self)
           self.mundo   = RepositorioMundo(self)
   ```
   Chamada fica `engine.db.npcs.salvar(npc)` em vez de `engine.db.salvar_npc(npc)`.

3. `web/dashboard.py` e `web/composed_routes.py` passam a usar `DatabaseManager`
   (ver `R-E02` para o ciclo de vida).

4. `engine/mechanics/*` **não** contém mais nenhuma string SQL.

**Validar:**
```bash
grep -rn "SELECT \|INSERT \|UPDATE \|DELETE " --include="*.py" engine/mechanics/ web/
```
retorna 0. Todo SQL vive em `engine/repositorios/` e `engine/schema.sql`.
**Risco:** **alto** — é a maior mudança do plano. Faça repositório por repositório, um
commit cada, começando por `RepositorioMeta` (o menor).

---

### R-E02 · Corrigir o vazamento de pool no `mestre_routes.py`
**Arquivos:** `web/mestre_routes.py:26-27`, `web/dashboard.py:22-25`
**Problema:** **vazamento de recursos real.**
```python
def _get_db():
    return DatabaseManager(DB_PATH)
```
Cada uma das 5 rotas chama `_get_db()` **a cada requisição**. `DatabaseManager.__init__`
abre um pool de **5 conexões SQLite** e executa o `schema.sql` inteiro. Nada é fechado.
Com o dashboard fazendo polling de `/api/mestre/estado`, isso acumula conexões até o
processo Flask bater no limite de descritores de arquivo.
**Ação:**
1. Crie **uma** instância por processo, em `web/banco.py`:
   ```python
   """
   MODULE: banco.py
   FUNÇÃO: Instância única de DatabaseManager para o processo do dashboard.

   DESCRIÇÃO:
       DatabaseManager abre um pool de conexões e roda o schema no __init__ — criar um
       por requisição (comportamento anterior de mestre_routes._get_db) vazava 5
       conexões SQLite por chamada. O dashboard é um processo só, leitor da simulação;
       uma instância compartilhada basta, e o pool já é seguro entre threads.
   """
   import os
   from engine.database import DatabaseManager

   CAMINHO_BANCO = os.path.abspath(
       os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))

   _db = None

   def obter_db() -> DatabaseManager:
       global _db
       if _db is None:
           _db = DatabaseManager(CAMINHO_BANCO)
       return _db
   ```
2. Troque `_get_db()` por `obter_db()` nas 5 rotas de `mestre_routes.py`.
3. Troque `get_db_connection()` de `dashboard.py` por `obter_db().connection()`.
4. Apague as 4 definições duplicadas de `DB_PATH` (`dashboard.py:20`,
   `mestre_routes.py:22`, `composed_routes.py:~407`, `builder/storyteller.py:20`) —
   todas passam a importar `CAMINHO_BANCO`.
**Validar:**
```bash
# com o dashboard rodando, faça 200 chamadas e conte descritores
for i in $(seq 200); do curl -s localhost:5000/api/mestre/estado > /dev/null; done
ls /proc/$(pgrep -f run_dashboard)/fd | wc -l
```
O número deve ficar estável.
**Risco:** médio — **corrige bug real**. Registre no commit.

---

### R-E03 · Remover a programação defensiva de schema em `DatabaseManager`
**Arquivos:** `engine/database.py:125-145,169-209`
**Problema:** cada campo é lido assim:
```python
categoria=row['categoria'] if 'categoria' in row.keys() else 'generic',
tipo_local=row['tipo_local'] if 'tipo_local' in row.keys() and row['tipo_local'] is not None else '',
```
São **26 expressões** desse tipo. Elas existem para sobreviver a bancos antigos com
schema desatualizado. Mas o `_init_db()` roda `schema.sql` com `CREATE TABLE IF NOT
EXISTS` no começo de tudo — ou seja, **em banco novo essas colunas sempre existem**, e em
banco antigo o `CREATE IF NOT EXISTS` não adiciona colunas mesmo, então o fallback só
esconde o problema.
**Ação:**
1. Escreva um método de migração honesto em `DatabaseManager`:
   ```python
   COLUNAS_ESPERADAS = {
       "npcs":   [...],   # nome -> tipo SQL, na ordem do schema
       "locais": [...],
   }

   def _migrar_colunas_ausentes(self, conn) -> None:
       """Adiciona com ALTER TABLE as colunas que o schema declara e a tabela não tem.
       Substitui os 26 fallbacks `if 'x' in row.keys()` espalhados pelos carregadores:
       o banco passa a ficar correto uma vez, em vez de ser remendado a cada leitura."""
   ```
   Chame-o no fim de `_init_db()`.
2. Simplifique os construtores de `NPC` e `Local` para acesso direto:
   ```python
   categoria=row['categoria'] or CategoriaLocal.GENERIC.value,
   ```
   (o `or` cobre apenas `NULL` no banco, que é um estado legítimo — a ausência de
   coluna deixa de ser)
3. Troque o `_safe_json_load` com `except:` nu por `except json.JSONDecodeError` e
   um `WorldLogger.warning`, para o dado corrompido aparecer em vez de sumir.
**Validar:** `grep -c "in row.keys()\|in r.keys()" engine/database.py` retorna 0.
Apague o banco e rode `./builder/reset_world.sh`, depois rode a simulação: tem que
funcionar do zero.
**Risco:** médio

---

### R-E04 · Tirar o seed de domínio de dentro do `_init_db`
**Arquivos:** `engine/database.py:49-59`, `engine/mechanics/market.py:19-31`
**Problema:** `DatabaseManager._init_db` — cuja responsabilidade é *criar o schema* —
insere 23 linhas de **regra de negócio** (mapeamento `'padaria' → 'comercio'`,
`'quartel' → 'militar'`, …). O mesmo padrão está em `JobMarket.bootstrap_market`, que
insere as 8 profissões mestras. São dados de domínio escritos em Python, dentro de duas
classes de infraestrutura diferentes.
**Ação:**
1. Mova os dois conjuntos para `database/seed_dominio.json`:
   ```json
   {
     "profissoes": [ {"id": "fazendeiro", "nome": "Fazendeiro", "categoria": "agricultura"}, ... ],
     "mapeamento_categorias": { "padaria": "comercio", "taberna": "social", ... }
   }
   ```
2. Crie `engine/repositorios/seed.py` com `SemeadorDeDominio.aplicar(db)`, chamado
   explicitamente por `builder/populate.py` — não mais como efeito colateral de abrir
   uma conexão.
3. `DatabaseManager._init_db` fica **só** com pool + `executescript(schema.sql)`.
**Validar:** `grep -rn "'padaria'\|'taberna'" --include="*.py" .` retorna 0.
**Risco:** médio

---

# Bloco F — Estático vs. instância, injeção de dependência

> **Critério de decisão** (registrado em `11_ARQUITETURA.md`):
> - **`@staticmethod` / função de módulo**: função pura, sem estado, sem dependências.
>   Ex.: `escala.metros_por_pixel_mundo`, `base.pontos_ao_longo_do_poligono`.
> - **Classe de instância**: tem estado, ou depende de algo (banco, config, RNG) que
>   deveria ser injetado e trocado em teste. Ex.: `GeradorCidade`, `ModeloCidade`.
> - **Classe só de `@staticmethod` recebendo o mesmo objeto como 1º argumento em todo
>   método** é uma classe de instância disfarçada. É o caso de 13 dos 16 módulos de
>   `engine/mechanics/`.

### R-F01 · Converter os gerenciadores de mecânica em classes de instância
**Arquivos:** todos em `engine/mechanics/` exceto `market.py`, `logic.py`, `mood.py`
**Problema:** o padrão é sempre:
```python
class NPCHousingManager:
    @staticmethod
    def processar_habitacao(engine):   # engine em TODOS os métodos
```
`engine` carrega `db`, `config`, `npcs`, `locais`, `cidades`, `data_simulada`. Ou seja:
**todo gerenciador depende de tudo**, e nada pode ser testado sem construir uma
`SimulationEngine` completa (que abre um banco real).
**Ação:** converta para instância, recebendo **só** o que cada um usa:
```python
class NPCHousingManager:
    """Expansão urbana: detecta casas superlotadas e inicia obras.

    Recebe o mundo (não a engine inteira) — precisa de locais, npcs, cidades e do
    repositório de locais, e de nada mais. Isso é o que permite testá-lo com um
    mundo sintético em memória."""

    def __init__(self, mundo: 'EstadoDoMundo', config: dict):
        self._mundo = mundo
        self._config = config

    def processar_habitacao(self) -> None: ...
```
Introduza um objeto `EstadoDoMundo` (em `engine/mundo.py`) que agrupa
`npcs`, `locais`, `cidades`, `data_simulada`, `tick_count` e o `db`. `SimulationEngine`
passa a **conter** um `EstadoDoMundo` em vez de ser ele.

**Ordem sugerida** (do mais fácil para o mais acoplado):
1. `KingdomManager` (2 métodos)
2. `NPCMoodManager`
3. `InfrastructureManager`
4. `NPCHousingManager`
5. `NPCMarriageManager`
6. `NPCSocialManager`
7. `NPCLifecycleManager` / `NPCReproductionManager`
8. `NPCActionManager`
9. `NPCMovementManager`

**Validar:** depois de cada conversão, escreva **um** teste que monta um
`EstadoDoMundo` sintético (sem banco) e exercita o gerenciador. Se o teste for difícil
de escrever, a injeção ainda está errada.
**Risco:** **alto** — é uma mudança estrutural grande. **Pode ser adiada** sem prejuízo
dos outros blocos; se o tempo for curto, faça só de 1 a 4 e deixe o resto registrado.

---

### R-F02 · `JobMarket` deve receber o banco, não criar o seu
**Arquivos:** `engine/mechanics/market.py:8-11`, `run_simulation.py:20`, `builder/populate.py:348`
**Problema:**
```python
class JobMarket:
    def __init__(self, db_path="database/openworld.db"):
        self.db = DatabaseManager(db_path)     # ← segundo pool de conexões
```
`run_simulation.py` cria a `SimulationEngine` (pool de 5) **e** o `JobMarket` (mais 5).
Dois pools apontando para o mesmo arquivo, no mesmo processo, sem nenhum motivo.
**Ação:**
```python
class JobMarket:
    def __init__(self, db: DatabaseManager, config: dict):
        self._db = db
        self._config = config
```
`run_simulation.py` passa `engine.db`; `populate.py` passa o `db` que já tem.
Remova também o `if __name__ == "__main__"` no fim de `market.py` (linhas 180-182): é
um ponto de entrada esquecido que cria ainda outro pool.
**Validar:** `grep -c "DatabaseManager(" --include="*.py" -r . | grep -v venv` — só
`web/banco.py`, `builder/populate.py` e `builder/storyteller.py` devem construir um.
**Risco:** baixo

---

### R-F03 · Tirar o SQL cru do `mestre.py` e trocar o `if/elif` por comandos
**Arquivos:** `engine/mechanics/mestre.py:74-150`
**Problema:** `aplicar_acoes` é um `if/elif` de 4 ramos sobre strings vindas **da IA**
(`"CRIAR_LOCAL"`, `"REATRIBUIR_NPC"`, `"DESTRUIR_LOCAL"`, `"AFETAR_NPC"`), cada ramo com
SQL cru inline e defaults literais dentro do `INSERT`:
```sql
VALUES (?, ?, ?, ?, ?, ?, ?, 1, 100, 5, 100)
```
Adicionar um comando novo significa mexer num método de 76 linhas.
**Ação:**
1. Enum + tabela de comandos:
   ```python
   class ComandoMestre(Enum):
       CRIAR_LOCAL     = "CRIAR_LOCAL"
       REATRIBUIR_NPC  = "REATRIBUIR_NPC"
       DESTRUIR_LOCAL  = "DESTRUIR_LOCAL"
       AFETAR_NPC      = "AFETAR_NPC"
   ```
2. Uma classe por comando, com interface única:
   ```python
   class AcaoDeMundo(ABC):
       comando: ComandoMestre

       @abstractmethod
       def aplicar(self, db, contexto: 'ContextoMestre', dados: dict) -> str:
           """Aplica a ação e devolve a descrição legível do que foi feito."""
   ```
3. `MestreManager.aplicar_acoes` vira um laço de despacho de ~15 linhas, com o
   comando desconhecido virando `WorldLogger.warning` em vez de ser ignorado
   silenciosamente (comportamento atual).
4. O SQL de cada ação vai para os repositórios de `R-E01`. Os defaults do `INSERT` viram
   os defaults do dataclass `Local` — que já existem.
**Validar:** `grep -c "INSERT\|UPDATE" engine/mechanics/mestre.py` retorna 0; adicionar
um 5º comando exige criar **um** arquivo e **uma** linha no registro.
**Risco:** médio

---

### R-F04 · Tornar `WorldLogger` configurável em vez de auto-descobrir tudo
**Arquivos:** `engine/logger.py`
**Problema:** a classe é toda estática com estado de classe mutável
(`_logger`, `_log_queue`, `_log_thread`, `_db_path`, `_npc_logging_enabled`,
`_last_config_check`). Pior: `is_npc_logging_enabled()` **abre e parseia `config.json`
sozinha** (linhas 65-73), a cada 5 segundos, ignorando o resolvedor central de
`config/`. É o único módulo do projeto que lê o arquivo direto.
Além disso, `_log_worker` engole toda exceção com `pass` (linha 40) — se a escrita no
banco falhar, ninguém fica sabendo.
**Ação:**
1. `is_npc_logging_enabled` passa a usar `cfg_get(get_config(), "salvar_logs_npc_no_banco", default=True)`.
   O cache de 5 segundos some — `get_config()` já cacheia por processo.
   > ⚠️ Isso muda um comportamento: hoje, alterar `config.json` com a simulação rodando
   > liga/desliga o log de NPC em até 5s. Depois, exige reiniciar. Se a recarga a quente
   > for desejada, adicione um método `config.recarregar()` explícito em vez de o logger
   > abrir arquivo por conta própria.
2. `_log_worker`: troque `pass` por um `print` em `stderr` na primeira falha (com flag
   para não inundar).
3. Extraia a configuração de handlers (`get_logger`, linhas 94-128) para um método
   `_configurar_handlers()` — o método atual mistura criação de diretório, formatação,
   dois handlers e caching.
**Validar:** `grep -n "json.load\|open(config" engine/logger.py` retorna 0.
**Risco:** baixo

---

# Bloco G — Camada web (Python)

### R-G01 · `dashboard.py` deixa de duplicar a formatação de moeda
**Arquivos:** `web/dashboard.py:28-39`, `engine/models.py:164-179`
**Problema:** `formatar_moeda()` em `dashboard.py` é uma **cópia literal** da property
`NPC.dinheiro_formatado`. Duas implementações da mesma regra (1 PO = 10 PP = 100 PC).
**Ação:** extraia para `engine/moeda.py`:
```python
"""
MODULE: moeda.py
FUNÇÃO: Conversão de peças de cobre (PC) para a notação PO/PP/PC.

DESCRIÇÃO:
    O saldo é fracionário desde a Frente 4 (salário pago a cada tick de 1 min); o
    arredondamento acontece SÓ na exibição. Esta era a única regra do projeto
    implementada duas vezes — em NPC.dinheiro_formatado e em web/dashboard.py.
"""
PC_POR_PP = 100
PP_POR_PO = 10

def formatar(total_pc: float) -> str: ...
```
`NPC.dinheiro_formatado` e o dashboard passam a chamar `moeda.formatar`.
**Validar:** `grep -c "// 1000" --include="*.py" -r .` retorna 1 (só em `moeda.py`).
**Risco:** baixo

---

### R-G02 · Dar nomes legíveis ao payload das APIs
**Arquivos:** `web/dashboard.py:119-166`, `web/static/js/dashboard.js`
**Problema:** o payload de `/api/update` usa chaves de **uma letra**:
```python
"status": {"e": ..., "f": ..., "s": ..., "d": ..., "h": ..., "m": ...},
"bio":    {"g": ..., "ev": ..., "dn": ..., "pai": ..., "mae": ..., "ec": ..., "cj": ..., "gr": ...}
```
e o topo é `{"h", "p", "v", "npcs", "evs", "locs", "evg", "warnings"}`. Ler o JS exige
uma tabela de tradução mental. O ganho de bytes é irrelevante num payload local.
**Ação:**
1. Crie `web/serializadores.py` com funções de serialização explícitas:
   ```python
   def serializar_npc(npc_row, coordenadas, idade_anos) -> dict:
       return {
           "id": ..., "nome": ..., "profissao": ..., "acao": ...,
           "necessidades": {"energia": ..., "fome": ..., "social": ...,
                            "dinheiro": ..., "saude": ..., "humor": ...},
           "biografia": {"genero": ..., "estagio_vida": ..., "nascimento": ...,
                         "pai_id": ..., "mae_id": ..., "estado_civil": ...,
                         "conjuge_id": ..., "gravidez_ticks": ..., "idade_anos": ...},
       }
   ```
2. Atualize os acessos no JS junto (`n.status.h` → `n.necessidades.saude`, etc.).
**Validar:** `grep -n '"e":\|"f":\|"ev":\|"gr":' web/dashboard.py` retorna 0; o dashboard
abre e mostra os NPCs.
**Risco:** médio (Python e JS mudam no mesmo commit, obrigatoriamente)

---

### R-G03 · Centralizar os caminhos de arquivo do projeto
**Arquivos:** novo `engine/caminhos.py`; `dashboard.py:20`, `mestre_routes.py:22`, `composed_routes.py:15-17`, `helpers.py:159`, `populate.py:27-29`, `storyteller.py:20`, `generate_world.py:16`, `generate_city_geometry.py:38-39`, `logger.py:12,51`, `utils.py:28`
**Problema:** o caminho de cada artefato do projeto é recalculado em cada arquivo, com
três estilos diferentes: relativo (`"database/openworld.db"`), absoluto via
`os.path.dirname(__file__)` + `'..'`, e absoluto via `os.getcwd()`. Isso é o que obriga
alguns scripts a rodar só da raiz do projeto.
**Ação:**
```python
"""
MODULE: caminhos.py
FUNÇÃO: Localização única dos artefatos do projeto em disco.

DESCRIÇÃO:
    Todo caminho resolve a partir da raiz do repositório, calculada uma vez. Antes
    deste módulo, os mesmos caminhos eram recalculados em 11 arquivos com 3 estilos
    diferentes — e alguns scripts só funcionavam se executados da raiz.
"""
import os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BANCO            = os.path.join(RAIZ, "database", "openworld.db")
MANIFESTO_MUNDO  = os.path.join(RAIZ, "database", "world_manifest.json")
MAPA_COMPOSTO    = os.path.join(RAIZ, "database", "mapa_composto.npz")
DIR_CIDADES      = os.path.join(RAIZ, "database", "cidades")
DIR_FEATURES     = os.path.join(RAIZ, "database", "features")
DIR_LOGS         = os.path.join(RAIZ, "logs")
CONFIG_JSON      = os.path.join(RAIZ, "config.json")
```
Todos os 11 arquivos importam daqui. `config/resolver._raiz_do_projeto` também.
**Validar:** `grep -rn "database/openworld.db" --include="*.py" --exclude-dir=venv .`
retorna apenas `caminhos.py`.
**Risco:** baixo

---

# Bloco H — Frontend (JS/HTML/CSS)

> ✅ Executado em 16_PLANO_PAINEL_E_IA.md, Bloco F (2026-09-14).

### R-H01 · Converter os três arquivos JS para módulos ES
**Arquivos:** `web/static/js/dashboard.js`, `mapa_composto.js`, `mapa_leaflet.js`, `web/templates/index.html:216-219`
**Problema:** 56 variáveis globais (`let`/`const` de topo) compartilhando o mesmo escopo
`window`. `dashboard.js` chama `initMapaLeaflet()` e `window.updateMapEntities()`
definidos em outros arquivos, sem nenhuma declaração de dependência — a ordem das tags
`<script>` no HTML é a única coisa que faz funcionar.
**Ação:**
1. Em `index.html`, troque as 3 tags por uma só:
   ```html
   <script type="module" src="{{ url_for('static', filename='js/app.js') }}"></script>
   ```
   (Leaflet continua como `<script>` global antes — é uma lib UMD.)
2. Crie `web/static/js/app.js` como ponto de entrada, que importa os módulos e registra
   os handlers (ver `R-H02`).
3. Cada arquivo passa a exportar explicitamente o que os outros usam:
   ```js
   // mapa_leaflet.js
   export function initMapaLeaflet() { ... }
   export function atualizarEntidadesNoMapa(npcs) { ... }
   ```
4. O estado global de cada módulo vira um objeto único, não 20 `let` soltos:
   ```js
   const estado = { modo: Modo.GLOBAL, continenteUuid: null, escala: 1.0, ... };
   ```
**Validar:** o console do navegador não mostra `ReferenceError`; `grep -c "^let \|^var "`
em cada arquivo cai para ≤ 3.
**Risco:** médio

---

### R-H02 · Tirar os `onclick` inline do HTML
**Arquivos:** `web/templates/index.html` (22 ocorrências), `web/static/js/app.js`
**Problema:** o HTML chama funções JS por nome (`onclick="setSpeed(1)"`,
`onclick="switchView(this, 'map-view')"`, `onclick="switchModalNPC('${id}')"`). Isso
obriga as funções a serem globais (bloqueando `R-H01`) e espalha comportamento pelo
template. Há também **strings de estado no HTML** (`'map-view'`, `'vivos'`) que precisam
casar exatamente com o JS.
**Ação:**
1. No HTML, troque `onclick` por atributos de dados:
   ```html
   <button class="tab-btn" data-acao="trocar-view" data-view="mapa">🗺️ Mapa</button>
   <button class="speed-btn" data-acao="velocidade" data-valor="60">60x</button>
   ```
2. Em `app.js`, um delegador único:
   ```js
   document.addEventListener('click', (ev) => {
       const alvo = ev.target.closest('[data-acao]');
       if (!alvo) return;
       const handler = ACOES[alvo.dataset.acao];
       if (handler) handler(alvo, ev);
   });
   ```
3. Os `onclick` gerados **dentro de template strings** (`renderNPCProfile`,
   `dashboard.js:261-262,275,278`) seguem a mesma regra: emitem `data-acao` e o
   delegador cuida.
**Validar:** `grep -c "onclick=" web/templates/index.html web/static/js/*.js` retorna 0.
**Risco:** médio

---

### R-H03 · Criar enums de estado no JS e tirar as strings soltas
**Arquivos:** `web/static/js/dashboard.js:2-6`, `mapa_composto.js:6`
**Problema:** os modos e filtros são strings comparadas à mão:
```js
let currentMode = 'global';   // 'global', 'continent' ou 'city'
let activeView = 'map-view';
let npcFilter = 'vivos';
let activeModalTab = 'profile';
```
E o filtro é reconstituído de forma frágil — `setNpcFilter` lê o **texto visível do
botão** para decidir qual está ativo:
```js
if (filter === 'vivos' && text.includes('vivos')) isMatch = true;
```
Trocar o rótulo de um botão quebra o filtro.
**Ação:**
1. Crie `web/static/js/constantes.js`:
   ```js
   export const Modo       = Object.freeze({ GLOBAL: 'global', CONTINENTE: 'continente', CIDADE: 'cidade' });
   export const Aba        = Object.freeze({ MAPA: 'mapa', HABITANTES: 'habitantes', MESTRE: 'mestre', MAPA_LIVE: 'mapa-live' });
   export const FiltroNpc  = Object.freeze({ VIVOS: 'vivos', MORTOS: 'mortos', TODOS: 'todos' });
   export const AbaModal   = Object.freeze({ PERFIL: 'perfil', LOGS: 'logs' });
   ```
2. `setNpcFilter` passa a comparar `btn.dataset.filtro === filtro` (vem do `R-H02`), não
   o texto.
**Validar:** `grep -n "'vivos'\|'mortos'\|'global'\|'map-view'" web/static/js/*.js`
retorna apenas `constantes.js`.
**Risco:** baixo — **corrige uma fragilidade real**

---

### R-H04 · Servir ao frontend o que hoje está duplicado
**Arquivos:** `web/static/js/mapa_leaflet.js:23-51`, `mapa_composto.js:337-342`, `web/rotas/mapa.py`
**Problema:** valores que existem no `config.json` estão **reescritos como default no
JS**, com o comentário do próprio arquivo avisando que já divergiram uma vez:
```js
let leafletDimensaoGlobal = 768;
let leafletZoomMaximo = 15;
let leafletMaxNativeZoom = 11;
let leafletMetrosPorPixelMundo = 15811.4;
let leafletViaLarguraM = { principal: 11, anel: 7, secundaria: 5 };
let leafletViaLarguraMinPx = 1.5;
let leafletTooltipZoomMin = 5;
```
Mais o dicionário de biomas (`R-B06`), que tem uma entrada a mais que o Python.
**Ação:**
1. `/api/continentes` **já** serve quase tudo isso. Remova os defaults do JS e faça o
   mapa **falhar visivelmente** (mensagem no console + banner) se a API não responder,
   em vez de desenhar com números errados.
2. Adicione `"biomas"` ao payload (`R-B06`) e consuma em `mapa_composto.js`.
3. Se algum valor não puder faltar antes da resposta da API, marque-o como
   `const PLACEHOLDER_ATE_CARREGAR` e comente **explicitamente** que ele nunca é usado
   para desenhar.
**Validar:** com o servidor parado, o mapa mostra erro em vez de um mundo com escala
errada.
**Risco:** baixo

---

### R-H05 · Quebrar `dashboard.js` por assunto e parar de montar HTML com string
**Arquivos:** `web/static/js/dashboard.js` (529 linhas)
**Problema:** um arquivo cuida de: navegação de abas, polling, render do grid de NPCs,
render do perfil, modal de logs, e **todo o chat do Modo Mestre**. `update()` tem 110
linhas e `renderNPCProfile()` tem 98 — esta última é uma única template string com
~40 atributos `style=` inline.

Há também um risco de injeção: `renderNPCProfile` interpola `npc.nome` e
`npc.personalidade` — **texto gerado por LLM** — direto em `innerHTML`, sem escape. A
função `escapeHtmlMestre` existe, mas só é usada no chat.

**Ação:**
1. Divida em:
   | Arquivo | Responsabilidade |
   |---|---|
   | `app.js` | bootstrap, delegador de eventos, polling |
   | `navegacao.js` | abas e views |
   | `painel_npcs.js` | grid + filtro |
   | `ficha_npc.js` | modal de perfil e crônicas |
   | `chat_mestre.js` | Modo Mestre |
   | `formatacao.js` | avatares, rótulos de estágio de vida, cores |
2. Mova os `style="..."` inline para classes em `style.css`. O CSS já tem variáveis
   (`--accent`, `--danger`); use-as por classe, não por atributo.
3. Extraia a tradução `estagio_vida → rótulo`, hoje um ternário aninhado **duplicado**
   em `update()` (linha 135) e `renderNPCProfile()` (linhas 251-254):
   ```js
   const ROTULO_ESTAGIO = Object.freeze({
       bebe:    { curto: '🍼 Bebê',     longo: 'Bebê 👶' },
       crianca: { curto: '🧸 Criança',  longo: 'Criança 👦' },
       adulto:  { curto: null,          longo: 'Adulto(a) 🧑' },
       idoso:   { curto: null,          longo: 'Idoso(a) 👴👵' },
       morto:   { curto: '💀 Falecido', longo: 'Falecido(a) 💀' },
   });
   ```
4. Renomeie `escapeHtmlMestre` → `escaparHtml` e **use em todo texto vindo do
   servidor**: nome, profissão, personalidade, background, resumo de evento.
**Validar:** nenhum arquivo JS passa de 250 linhas; `grep -c 'style="' web/static/js/*.js`
cai para 0.
**Risco:** médio — o item 4 **corrige uma vulnerabilidade**. Registre no commit.

---

### R-H06 · Mover os estilos inline do `index.html` para o CSS
**Arquivos:** `web/templates/index.html`
**Problema:** elementos com `style="margin-left:1rem; background: var(--accent); border:none; border-radius: 50%; ..."` direto no atributo (linha 27 tem 9 propriedades).
**Ação:** crie classes em `style.css` (`.botao-pausa`, `.botao-filtro-compacto`, …) e
troque os atributos. Não mude nenhum valor — é movimentação pura.
**Validar:** `grep -c 'style="' web/templates/index.html` cai para 0; a página fica
visualmente idêntica (compare capturas de tela).
**Risco:** baixo

---

# Bloco I — Verificação final

### R-I01 · Checklist de saída
Rode e confirme cada item:

```bash
# 1. Testes verdes
venv/bin/python -m pytest tests/ -v

# 2. Geração de mundo determinística (compare com o baseline de R-A01)
venv/bin/python cartographer/cities/generate_city_geometry.py
md5sum database/cidades/*.geojson | diff - /tmp/geom_antes.md5

# 3. Nenhum arquivo Python acima de 400 linhas
find . -name "*.py" -not -path "./venv/*" -not -path "*/__pycache__/*" \
  -exec wc -l {} + | sort -rn | head -10

# 4. Nenhum SQL fora dos repositórios
grep -rn "SELECT \|INSERT \|UPDATE \|DELETE " --include="*.py" \
  --exclude-dir=venv engine/mechanics/ web/ builder/populate.py

# 5. Nenhum except nu
grep -rn "except:" --include="*.py" --exclude-dir=venv .

# 6. Nenhum getattr defensivo sobre campo declarado
grep -rn "getattr(" --include="*.py" --exclude-dir=venv engine/

# 7. Nenhum default silencioso de config
grep -rn 'config\[\|cfg\.get(\|meta\.get(' --include="*.py" --exclude-dir=venv engine/

# 8. Nenhum onclick inline
grep -rn "onclick=" web/templates/ web/static/js/

# 9. Reset completo do mundo funciona do zero
rm -f database/openworld.db && ./builder/reset_world.sh

# 10. Simulação roda 500 ticks sem erro
timeout 60 venv/bin/python run_simulation.py
```

### R-I02 · Atualizar a documentação
**Arquivos:** `README.md`, `builder/README.md`, `docs/05_ROADMAP.md`
**Ação:**
1. `builder/README.md`: remova as seções de `old/` e `generator.py`.
2. `docs/05_ROADMAP.md`: adicione uma linha no Log de Sessões com o que esta refatoração
   mudou e uma entrada na tabela de frentes apontando para este documento.
3. `README.md`: se a estrutura de diretórios estiver documentada lá, atualize.
**Risco:** baixo

---

## Anexo 1 — Tabela de números mágicos encontrados

| Valor | Arquivo:linha | Significado | Destino |
|---|---|---|---|
| `1200, 1, 1` | 8 arquivos | época do mundo | `RelogioMundo.EPOCA` (R-B07) |
| `80.0` | `lifecycle.py:115`, `populate.py:259`, `dashboard.py:115` | anos de vida de referência | `RelogioMundo` (R-B08) |
| `100` / `0` | ~20 lugares | limites de escala de necessidade | `ESCALA_MAXIMA/MINIMA` (R-B09) |
| `90` | `loop.py:118` | fome que causa inanição | `config.biologia_e_sociedade` (R-B09) |
| `20` | `loop.py:122` | fome máxima para recuperar saúde dormindo | `config` (R-B09) |
| `10` | `logic.py:25` | fome mínima para continuar comendo | `config.ia_decisao` (R-D01) |
| `6` / `8` | `loop.py:59,63` | horas de habitação e pagamento | `config` (R-D02) |
| `% 4` | 5 lugares | amostragem de log | `config.observabilidade` (R-B10) |
| `0.50` / `0.5` | `movement.py:71,103` | chances de movimento | `config.ia_decisao` (R-B11) |
| `0.33` / `0.0` | `loop.py:79,80` | defaults silenciosos de metabolismo | remover default (R-D02) |
| `6` | `logic.py:56` | default silencioso de hora de sono | remover default (R-D01) |
| `70/30/-20/-50` | `social.py:63-66` | limiares de vínculo | `config` (R-B01) |
| `50` / `30` | `marriage.py:119,122` | bônus de afinidade de casamento | `config` |
| `1000` | `marriage.py:136-137` | afinidade máxima | constante nomeada |
| `15` / `20` / `10` | `reproduction.py:53,158`, `lifecycle.py:41,63,86` | modificador de afinidade por evento | `config` |
| `60.0` / `0.5` | `kingdom.py:29,33` | gatilho e potência do sopão | `config.reino` |
| `5` | `populate.py:114` | casas do fallback paliativo | `config.geracao_urbana` |
| `256` / `1337` | `generate_world.py:39` | tile size e semente do mundo | `config.cartografia` (R-D04) |
| `12345` / `9999` | `tile_cartographer.py:140,235` | offsets de ruído | constantes de classe (R-D04) |
| `0.02` / `0.90` | `tile_cartographer.py:235-236` | piso/teto do ruído marinho | `config.cartografia` (R-D04) |
| `0.95` / `0.15` | `generate_city_geometry.py:344` | limites de taxa de ocupação | `config` (R-D05) |
| `5` / `0` / `80` | `generate_city_geometry.py:440,445` | capacidade e salário padrão | `config` (R-D05) |
| `3.0` / `0.25` | `modelos/base.py:151,154` | bônus/penalidade de peso por tipo de cidade | `config` |
| `768` | `composed_routes.py` (3×), `mapa_leaflet.js:23` | dimensão global do mundo | derivar do config (R-D07, R-H04) |
| `600` | `mapa_composto.js:44-45` | tamanho do canvas | constante nomeada |
| `30` | `mapa_composto.js:329` | debounce de hover em ms | constante nomeada |
| `8` | `composed_routes.py:67` | teto do cache de janelas | `config` |

---

## Anexo 2 — Tabela de strings que devem virar enum

| String literal | Onde aparece | Enum destino | Existe? |
|---|---|---|---|
| `'M'` / `'F'` | 14 lugares | `Genero` | criar (R-B02) |
| `'bebe'`, `'crianca'`, `'adulto'`, `'idoso'`, `'morto'` | 12 lugares | `EstagioVida` | **já existe** — só usar (R-B03) |
| `'dependente'` | 6 lugares | `PROFISSAO_DEPENDENTE` | **já existe** — só usar (R-B03) |
| `'Casa'`, `'Social'`, `'Loja'`, `'Ruina'` | 9 lugares | `TipoLocal` | **já existe** — só usar |
| `'residencia'`, `'generic'`, `'publico'`, `'taverna'` | 11 lugares | `CategoriaLocal` | **já existe** — só usar |
| `'Conhecido'`, `'Aliado'`, `'Amigo'`, `'Rival'`, `'Inimigo'`, `'Cônjuge'` | 6 lugares | `VinculoSocial` | criar (R-B01) |
| `"CONVERSA"`, `"DISCUSSAO"` | `social.py:71` | `TipoEvento` | **já existe** — só usar |
| `"Neutro"`, `"Alegre"`… | `models.py:140`, `mestre.py:146`, banco | `HumorNPC` | **já existe** — usar (R-C04) |
| `"Desempregado"`, `"Aposentado(a)"` | `lifecycle.py:52,75`, `market.py:149,172` | `ProfissaoID` + rótulo | parcial |
| `"simulacao_pausada"`, `"hora_simulada_iso"`… | 7 arquivos | `MetaChave` | criar (R-B05) |
| `"CRIAR_LOCAL"`, `"REATRIBUIR_NPC"`… | `mestre.py:105-143` | `ComandoMestre` | criar (R-F03) |
| `"jogador"` / `"mestre"` | `mestre_routes.py`, `database.py` | `AutorConversa` | criar |
| `"nucleo"`, `"centro"`, `"meio"`, `"borda"` | `modelos/base.py:109-120` | `ZonaUrbana` | criar |
| `"principal"`, `"anel"`, `"secundaria"` | `modelos/*.py`, `mapa_leaflet.js` | `ClasseVia` | criar |
| `"rua"`, `"quarteirao"`, `"edificio"`… | `composed_routes.py:512`, `mapa_leaflet.js:53` | `CamadaCidade` | criar e servir ao JS |
| `"Oceano"`, `"Deserto"`… | 4 lugares | `Bioma` | criar (R-B06) |
| `'global'`, `'continent'`, `'city'`, `'vivos'`, `'map-view'` | JS | `Modo`, `Aba`, `FiltroNpc` | criar (R-H03) |

---

## Anexo 3 — Bugs reais encontrados durante a análise

Estes **não são** questões de estilo. Estão referenciados nas tarefas indicadas.

| # | Gravidade | Bug | Onde | Tarefa |
|---|---|---|---|---|
| 1 | **Alta** | Pool de 5 conexões SQLite criado a cada requisição HTTP, nunca fechado | `web/mestre_routes.py:26` | R-E02 |
| 2 | **Alta** | Dono de obra identificado por substring: `npc_01` casa dentro de `npc_012` | `engine/utils.py:198` | R-C03 |
| 3 | **Média** | `VinculoSocial.INIMIGO` é inalcançável — `elif < -20` vem antes de `elif < -50` | `engine/mechanics/social.py:63-66` | R-B01 |
| 4 | **Média** | Texto gerado por LLM interpolado em `innerHTML` sem escape | `web/static/js/dashboard.js:249+` | R-H05 |
| 5 | **Média** | `nomes_gerados` mutado dentro de `ThreadPoolExecutor` sem lock; a deduplicação de nomes provavelmente não funciona | `builder/populate.py:202-219` | R-D03 |
| 6 | **Média** | `movement.py` trata só `'bebe'` como dependente; o resto da engine trata `'bebe'` **e** `'crianca'`. Crianças conseguem sair de casa onde não deveriam | `engine/mechanics/movement.py:14,42` | R-B04 |
| 7 | **Média** | Dois pools de conexão no mesmo processo (`SimulationEngine` + `JobMarket`) | `run_simulation.py:19-20` | R-F02 |
| 8 | **Baixa** | `capacidade_efetiva` documenta que o `JobMarket` deve usá-la; o `JobMarket` ignora e contrata em prédios degradados | `engine/mechanics/decay.py:47` | R-A04 |
| 9 | **Baixa** | `setNpcFilter` decide o botão ativo lendo o texto visível; mudar o rótulo quebra o filtro | `web/static/js/dashboard.js:36-41` | R-H03 |
| 10 | **Baixa** | `except Exception` inalcançável depois de outro idêntico | `web/dashboard.py:173` | R-A09 |
| 11 | **Baixa** | `logger` lê `config.json` por conta própria a cada 5s, fora do resolvedor central | `engine/logger.py:65-73` | R-F04 |
| 12 | **Baixa** | Ramos idênticos em `extrair_sobrenome` | `engine/mechanics/reproduction.py:88-90` | R-A10 |
| 13 | **Baixa** | `biomeBadges` no JS tem um bioma `6: "Zona Urbana"` que não existe no Python | `web/static/js/mapa_composto.js:342` | R-B06 |

---

## Registro de execução

> Preencha esta tabela conforme executar. Se uma tarefa for pulada, escreva o motivo.

> As linhas abaixo registram só o que foi **verificado na árvore de trabalho**. Uma
> tarefa sem linha não é uma tarefa pulada — é uma tarefa cujo estado ainda não foi
> auditado.

| Tarefa | Status | Commit | Observações |
|---|---|---|---|
| R-E01 | ✅ | (não comitado) | Pacote `engine/repositorios/` com seis repositórios; `engine/database.py` ficou só com pool e schema. |
| R-E02 | ✅ | (não comitado) | `web/banco.py` com instância única do processo; `mestre_routes` e `dashboard` consomem ela. |
| R-E03 | ✅ | (não comitado) | Leitura defensiva de schema removida do `DatabaseManager`. |
| R-E04 | ✅ | (não comitado) | Seed de domínio saiu do `_init_db`. |
| R-F01 | ✅ | (não comitado) | Os 9 gerenciadores + `GameLoop` + `MestreManager` são classes de instância recebendo `EstadoDoMundo`/config. `mood` recebe só a config (é o único que não usa o mundo) e `events` só o mundo. Validado por `tests/test_mecanicas.py` (19 testes, sem banco) e por 120 ticks + as 4 rotinas agendadas numa cópia do banco real. |
| R-F02 | ✅ | (não comitado) | `JobMarket` recebe o banco; um pool por processo. |
| R-F03 | ✅ | (não comitado) | `engine/mechanics/mestre.py` virou pacote; os 4 ramos do if/elif são classes `AcaoDeMundo` com registro explícito. Enum `ComandoMestre` criado e **servido ao prompt** em vez de copiado no .txt. Validado por `tests/test_mestre.py` (11 testes). |
| … | | | |

### Bug encontrado durante o R-F03 (fora do Anexo 3)

`HumorNPC` tem valor composto (`rótulo`, `ordem`) e reatribui `_value_` no `__init__`, mas
o mapa interno do `Enum` continua indexado pelas **tuplas** originais. Resultado:
`HumorNPC("Em Pânico")` levantava `ValueError` para **todos** os humores, então
`AFETAR_NPC` no Modo Mestre caía sempre no fallback `Neutro` — o Mestre não conseguia
assustar ninguém. Corrigido com `_missing_` em `engine/models.py`; protegido por
`test_humor_valido_da_ia_e_preservado`, que falha antes da correção.
