# OpenWorld Engine (MVP)

Motor de simulação de mundo autônomo e emergente para suporte a RPG de mesa. Esta engine utiliza uma abordagem híbrida: lógica matemática para o dia-a-dia (Utility AI) e Inteligência Artificial (Ollama) para geração de conteúdo e lore.

## 🚀 Como Executar

1. Certifique-se de que o **Ollama** está rodando localmente.
2. Certifique-se de ter o modelo `qwen2.5-coder:7b` instalado:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
3. Execute o motor principal:
   ```bash
   python3 run_simulation.py
   ```

---

## 🐍 Tutorial: Ambiente Virtual (venv)

Como prometido, aqui está o guia rápido para você nunca mais esquecer como isolar seu ambiente Python no Linux.

### 1. Instalar o suporte ao venv (se necessário)
No Ubuntu, às vezes o módulo de venv não vem por padrão. Se o comando de criação falhar, execute:
```bash
sudo apt update
sudo apt install python3-venv
```

### 2. Criar o ambiente virtual
Dentro da pasta do projeto (`OpenWorld`), execute:
```bash
python3 -m venv venv
```
*Isso criará uma pasta chamada `venv` com uma cópia isolada do Python.*

### 3. Ativar o ambiente
Sempre que for trabalhar no projeto, você precisa "entrar" no ambiente:
```bash
source venv/bin/activate
```
*Dica: Seu terminal geralmente mostrará `(venv)` no início da linha para indicar que está ativo.*

### 4. Dependências
Atualmente, a engine utiliza apenas bibliotecas nativas do Python (Standard Library), então **não é necessário instalar nada via pip** para rodar o motor básico. Basta ter o Ollama rodando localmente.


### 5. Desativar
Quando terminar de trabalhar e quiser voltar ao Python global do sistema:
```bash
deactivate
```

---

## 📂 Estrutura do Projeto

- `run_simulation.py`: Loop principal e lógica de tempo (Time Ticks).
- `world_state.py`: Modelos de dados (NPC, Local, Eventos) e lógica de Utility AI.
- `npc_generator.py`: Integração com Ollama para "dar luz" a novos personagens.
- `database_manager.py`: Gerenciamento do banco de dados SQLite.
- `database/`: Pasta onde o estado do mundo é persistido.

---

## 🛠️ Tecnologias Utilizadas
- **Python 3** (Lógica Core)
- **Ollama** (Geração de Conteúdo Local)
- **SQLite** (Persistência de Dados)
