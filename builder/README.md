# 🏗️ Ecossistema de Construção (Builder)

Este diretório contém a infraestrutura e o ferramental responsável por criar e configurar a gênese do mundo de OpenWorld. A pipeline de geração usa chamadas de Inteligência Artificial e heurísticas processuais de cartografia para criar mapas, edifícios e habitantes totalmente únicos a cada iteração.

## 🚀 Comandos Principais e Reset do Mundo

O script central para iniciar e reformatar sua simulação é o bash automático:

```bash
./builder/reset_world.sh
```

*(Lembre-se de dar permissões de execução: `chmod +x builder/reset_world.sh`)*

Este script executa a limpeza dos dados sujos e invoca a pipeline completa: chamando o `reset_cartography.sh` (para modelar toda a geologia) e em seguida o `populate.py` (para dar vida às casas e criar NPCs via Inteligência Artificial).

### 🔥 Customização de Escala (CLI)

O script construtor de população suporta threads paralelas diretamente na chamada do Python:

```bash
venv/bin/python builder/populate.py --npcs 20 --ia-max-thread 4
```

*   `--npcs [INT]`: Define o número base inicial de habitantes na fundação do mundo.
*   `--ia-max-thread [INT]`: Especifica quantos workers do sistema rodarão em paralelo na geração de IDs da IA (Ollama). Use isso para acelerar consideravelmente o processo (Aviso: requer mais VRAM do modelo).

---

## 🛠️ Arquitetura dos Scripts de Construção

*   **`populate.py`**: O Grande Orquestrador Demográfico. Insere habitantes iniciais na simulação de maneira distribuída por entre as cidades e biomas.
*   **`storyteller.py`**: O Narrador. Lida com chamadas de IA para batizar recém-nascidos e futuramente analisar registros vitais e comportamentais.

---

## 🩹 Ferramentas de Manutenção (Pasta `fix/`)

Ferramentas usadas em momento de desenvolvimento para corrigir falhas e realizar análises "cirúrgicas" no banco, sem perder a simulação.

*   **`repair_db.py`**: Efetua limpeza em coordenadas vazias. Realoca habitantes com glitch para dentro das extremidades corretas das casas.
*   **`audit_market.py`**: Script pericial. Confere toda a matriz econômica da base de dados e alerta de desemprego, escassez de infraestrutura, além da balança salarial base.

---
*OpenWorld Builder — A arquitetura por trás da complexidade.*
