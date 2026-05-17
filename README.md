# 🌍 OpenWorld Engine: Autonomous City Simulation

OpenWorld é um motor de simulação de mundo autônomo e emergente projetado para suporte a RPG de mesa e mundos persistentes. A engine combina **Utility AI** (lógica matemática para decisões) com **Inteligência Artificial Generativa** (LLMs locais via Ollama) para criar uma experiência onde habitantes vivem, trabalham e interagem de forma independente.

## 🚀 Estado Atual: Reabilitação Urbana (v8.0)

O projeto superou desafios críticos de corrupção de dados e arquitetura, estabelecendo uma base sólida de persistência e matchmaking profissional.

### Funcionalidades Implementadas:
*   **Ciclo de Vida Autônomo**: NPCs gerenciam energia, fome e socialização através de uma Utility AI de 15 minutos (ticks).
*   **Mercado de Trabalho Inteligente (JobMarket)**: Sistema de contratação que vincula NPCs a locais de trabalho baseados em especializações técnicas.
*   **Mapeamento Semântico (Tradução IA)**: Tabela de tradução que permite à IA criar nomes criativos (ex: "Taberna do Dragão") e ao sistema entender que ali há vagas para a categoria funcional "social".
*   **Persistência Híbrida**: Sincronização em tempo real entre o estado em memória (RAM) e o banco de dados (SQLite), garantindo que nenhuma mudança do mundo se perca entre os ticks.
*   **Rede de Segurança Habitacional**: Protocolo automático para evitar NPCs desalojados ou presos em coordenadas nulas (0,0).
*   **Geração de Conteúdo via IA**: Nomes, profissões e descrições de locais gerados dinamicamente para manter a imersão.

---

## 🏗️ Como Iniciar o Mundo

### 1. Requisitos
*   **Python 3.10+**
*   **Ollama** rodando localmente com o modelo `qwen2.5-coder:7b` (ou similar).

### 2. Reset e Construção (Recomendado para novos mundos)
Para criar um novo mundo com 15 habitantes gerados por IA e infraestrutura base:
```bash
./builder/reset_world.sh
```

### 3. Rodar a Simulação
```bash
python3 run_simulation.py
```

---

## 📂 Estrutura do Ecossistema

### `engine/` (O Cérebro)
*   **`core.py`**: Loop principal e motor metabólico dos NPCs.
*   **`logic.py`**: IA de utilidade e tomada de decisão.
*   **`market.py`**: Lógica de contratação e matchmaking profissional.
*   **`database.py`**: Gestão da persistência e mapeamento semântico.

### `builder/` (A Gênese)
*   **`manager.py`**: Orquestrador inicial do mundo.
*   **`setup_jobs.py`**: Definidor da economia e profissões.
*   **`fix/`**: Scripts utilitários para auditoria e reparo rápido do banco.

---

## 🛠️ Tecnologias Utilizadas
- **Python 3** (Lógica Core e Processamento)
- **Ollama / LLM** (Geração de Identidades e Narrativa)
- **SQLite** (Banco de Dados Relacional Persistente)
- **Bash** (Automação de Infraestrutura)

---
*OpenWorld: Onde cada pixel tem uma história e cada habitante tem um plano.*
