# 🏗️ Ecossistema de Construção (Builder)

Este diretório contém as ferramentas responsáveis pela gênese e manutenção do mundo de OpenWorld.

## 🚀 Comandos Principais

### Reset Total com IA
Para apagar o mundo atual e criar um novo com habitantes únicos gerados por IA:
```bash
./builder/reset_world.sh
```

## 🛠️ Scripts de Construção

*   **`manager.py`**: O orquestrador. Cria o banco, o mapa e invoca a geração de população.
*   **`setup_jobs.py`**: O arquiteto econômico. Define as profissões mestras e vincula-as às categorias técnicas.
*   **`storyteller.py`**: A mente narrativa. Usado para gerar descrições e novos eventos de construção via IA.
*   **`cartographer.py`**: O mestre dos mapas. Gerencia coordenadas e posicionamento espacial.
*   **`generator.py`**: O criador de vidas. Interface direta com a IA para gerar nomes e backgrounds de NPCs.

## 🩹 Ferramentas de Manutenção (Pasta `fix/`)

Localizadas em `builder/fix/`, estas ferramentas são usadas para sanar o mundo sem a necessidade de um reset total:

*   **`repair_db.py`**: Realiza faxina nas colunas de localização e realoca NPCs "perdidos" para casas reais. Use se ver NPCs no ponto (0,0).
*   **`audit_market.py`**: Analisa a saúde da economia, mostrando mismatches entre profissões de NPCs e prédios disponíveis.

---
*Nota: Todos os scripts possuem cabeçalhos internos detalhando sua motivação e contexto histórico de criação.*
