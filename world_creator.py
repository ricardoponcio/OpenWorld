import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

if len(sys.argv) < 2:
    print("Erro: Nenhum contexto fornecido. Use: python world_creator.py '<contexto>'")
    sys.exit(1)
context = sys.argv[1]

device = "cuda" if torch.cuda.is_available() else "cpu"

model_path = "microsoft/Phi-3-mini-4k-instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path, 
    torch_dtype=torch.float32 if device == "cpu" else "auto", # Força float32 para CPU
    trust_remote_code=True
).to(device)

try:
    messages = [
        {"role": "system", "content": """Você é um sistema de geração de conteúdo para um mundo de RPG de mesa.
Seu trabalho é criar um local que será posicionado em um mundo medieval, as entradas irão guiar os dados base para geração desse local.
Os locais criados deverão possuir certo volume de pessoas/comercios/eventos, porém não devem ser muito grandes, como uma cidade grande ou metrópole.
O local deve ter as seguintes características:
- nome: Nome do local. (Texto)
- tipo: Tipo do local (ex: vila, cidade, floresta, montanha, etc). (Texto)
- descrição: Uma descrição detalhada do local, incluindo pontos de interesse, habitantes notáveis, e qualquer característica única. (Texto)
- habitantes: quantidade de habitantes. (Número)
- clima: Descrição do clima predominante no local. (Texto)
- susbistencia: Descrição de como os habitantes do local obtêm sua subsistência (ex: agricultura, comércio, caça, etc). (Texto)
- comercios: Uma lista de tipos de comércios presentes no local (ex: ferreiro, taverna, mercado, etc). (Lista de textos)
- historia: Uma breve história do local, incluindo eventos importantes que moldaram sua identidade. (Texto)
- localizacao: Coordenada do local no mundo, em formato (x, y). (Lista de dois números)
Retorne a saída como um objeto JSON válido, sem texto adicional antes ou depois.
"""},
        {"role": "user", "content": f"Gere um novo local com base no contexto: {context}"}
    ]

    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(device)
    outputs = model.generate(
        input_ids,
        max_new_tokens=256,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=1.1,
        pad_token_id=tokenizer.eos_token_id
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(response)
    exit(0)
    prompt_length = len(tokenizer.apply_chat_template(messages, return_tensors="pt")[0])
    generated_text_only = response[prompt_length:]
    
    import re
    json_match = re.search(r'\{.*\}', generated_text_only.strip(), re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        print (json_str)
        exit(0)
    else:
        exit(1)

except Exception as e:
    exit(1)