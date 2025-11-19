import torch

print("Verificando se o PyTorch está vendo a GPU...")

if torch.cuda.is_available():
    print("Sucesso! GPU encontrada.")
    print(f"Nome da GPU: {torch.cuda.get_device_name(0)}")
    print(f"Versão do CUDA com PyTorch: {torch.version.cuda}")
    print(f"Contagem de GPUs: {torch.cuda.device_count()}")
else:
    print("Falha! GPU não encontrada. Tente os passos de reinstalação novamente.")