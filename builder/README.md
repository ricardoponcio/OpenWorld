# 🏗️ Ecossistema de Construção (Builder)

Este diretório contém a infraestrutura e o ferramental responsável por criar e configurar a gênese do mundo de OpenWorld. A pipeline de geração usa chamadas de Inteligência Artificial e heurísticas processuais de cartografia para criar mapas, edifícios e habitantes totalmente únicos a cada iteração.

## 🚀 Comandos Principais e Reset do Mundo

O script central para iniciar e reformatar sua simulação é o bash automático:

```bash
./builder/reset_world.sh
```

*(Lembre-se de dar permissões de execução: `chmod +x builder/reset_world.sh`)*

Este script executa a limpeza dos dados sujos (apaga o antigo `openworld.db`) e chama o orquestrador `manager.py`, seguido pelos preparos econômicos e auditorias da cidade.

### 🔥 Customização de Escala (CLI)

O script construtor suporta parâmetros avançados que definem o hardware e a escala da simulação. Você pode modificar a execução no `reset_world.sh` ou chamar diretamente:

```bash
python3 builder/manager.py --npcs 20 --ia --map-size 40 --ia-max-thread 8
```

*   `--npcs [INT]`: Define o número base inicial de habitantes na fundação da cidade.
*   `--ia`: Habilita as consultas ao modelo local do Ollama para gerar histórias ricas. Sem ela, o mundo usará backups genéricos.
*   `--map-size [INT]`: Define a largura e altura da grade da matriz de terreno. Por padrão é 20, mas o motor e o front-end escalam dinamicamente tamanhos massivos (ex: 40, 50, etc.).
*   `--ia-max-thread [INT]`: Especifica quantos workers do sistema rodarão em paralelo na geração de IDs da IA. Use isso para acelerar consideravelmente o processo em hardwares mais potentes (Aviso: requer mais VRAM do modelo).

---

## 🛠️ Arquitetura dos Scripts de Construção

*   **`manager.py`**: O Grande Orquestrador. Cria as fundações do banco SQLite, aciona a formatação do mapa via `Cartographer` e invoca paralelamente a IA para popular o ecossistema.
*   **`setup_jobs.py`**: O Arquiteto Econômico. Lê as tabelas de locais criados, aplica as taxonomias de vagas de trabalho e garante o alinhamento funcional dos blocos de serviço na matriz econômica.
*   **`cartographer.py`**: O Mestre Espacial. Responsável pela disposição x,y bidimensional do grid. Usa lógica de geração processual de rios e terrenos e espalha residências e indústrias pelo terreno sem colisões indevidas.
*   **`generator.py`**: A Matriz Biológica. Módulo de conexão direta (`AIWorldGenerator`) com o serviço do Ollama, onde prompts e JSON parsers dão nomes, gêneros e lore para a vida criada.

---

## 🩹 Ferramentas de Manutenção (Pasta `fix/`)

Ferramentas usadas em momento de desenvolvimento para corrigir falhas e realizar análises "cirúrgicas" no banco, sem perder a simulação.

*   **`repair_db.py`**: Efetua limpeza em coordenadas vazias. Realoca habitantes com glitch para dentro das extremidades corretas das casas.
*   **`audit_market.py`**: Script pericial. Confere toda a matriz econômica da base de dados e alerta de desemprego, escassez de infraestrutura, além da balança salarial base.

---
*OpenWorld Builder — A arquitetura por trás da complexidade.*
