import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Use o argumento da linha de comando como contexto, com verificação
if len(sys.argv) < 2:
    print("Erro: Nenhum contexto fornecido. Use: python npc_generator.py '<contexto>'")
    sys.exit(1)

context = sys.argv[1]

# Definir o caminho do modelo
model_path = "microsoft/Phi-3-mini-4k-instruct"
#model_path = "microsoft/phi-1"

# Definir o dispositivo (CPU ou GPU, se disponível)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Usando o dispositivo: {device}")

# Carregar o tokenizer e o modelo para o dispositivo
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path, 
    torch_dtype=torch.float32 if device == "cpu" else "auto", # Força float32 para CPU
    trust_remote_code=True
).to(device)

def generate_npc_data(context: str):
    """
    Gera dados de NPC usando o modelo Phi-3-mini com um prompt estruturado.
    """
    try:
        # Prompt template para o modelo
        messages = [
            {"role": "system", "content": """Você é um sistema de geração de conteúdo para um mundo de RPG de mesa.
Seu trabalho é criar um novo NPC com base nas informações históricas e de relacionamento fornecidas.
O NPC deve ter as seguintes características:
- nome: Nome completo do personagem. (Texto)
- idade: Idade do personagem. (Número)
- personalidade: Um traço de personalidade principal. (Texto)
- trabalho: Profissão ou ocupação do personagem. (Texto)
- habitacao: Tipo de moradia ou local de residência. (Texto)
- genealogia: Um relacionamento familiar com um NPC existente (ex: 'pai', 'filha').
Retorne a saída como um objeto JSON válido, sem texto adicional antes ou depois.
"""},
            {"role": "user", "content": f"Gere um novo NPC com base no seguinte contexto: {context}"}
        ]

        # Tokenizar o input
        input_ids = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(device)

        # Gerar a saída
        outputs = model.generate(
            input_ids,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id # Adiciona para evitar aviso de pad_token_id
        )

        # AQUI ESTÁ A ALTERAÇÃO CRUCIAL
        # `model.generate` retorna um tensor 2D. É necessário pegar o primeiro elemento (índice 0)
        # que representa a sequência gerada.
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # O modelo repete o prompt na resposta, então precisamos removê-lo.
        prompt_length = len(tokenizer.apply_chat_template(messages, return_tensors="pt")[0])
        generated_text_only = response[prompt_length:]
        
        # Limpar o texto para garantir que seja um JSON válido
        import re
        json_match = re.search(r'\{.*\}', generated_text_only.strip(), re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json_str
        else:
            return f"Erro: Resposta do modelo não contém um JSON válido. Resposta: {generated_text_only}"

    except Exception as e:
        return f"Erro ao gerar dados do NPC: {e}"

# Executar a função e imprimir a saída para o Java
if __name__ == "__main__":
    generated_data = generate_npc_data(context)
    print(generated_data)