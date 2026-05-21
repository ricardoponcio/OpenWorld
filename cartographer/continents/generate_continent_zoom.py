"""
SCRIPT: generate_continent_zoom.py
FUNÇÃO: Geração de mapa de zoom por demanda para um continente específico.
USO:
    python3 cartographer/generate_continent_zoom.py <uuid_ou_nome>

    Exemplos:
        python3 cartographer/generate_continent_zoom.py Terrae
        python3 cartographer/generate_continent_zoom.py db04bd07-3c05-553f-9cd9-078178b9be47

SAÍDA:
    database/continentes/mapa_<nome>.npz  — mapa em alta resolução (3000x3000, 4 canais)
"""
import os
import sys

# Garante que a raiz do projeto esteja no sys.path
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.continents.roi_zoom import ROIZoomGenerator
from cartographer.config import CARTOGRAPHER_CONFIG

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 cartographer/generate_continent_zoom.py <uuid_ou_nome_do_continente>")
        print("\nContinentes disponíveis no manifesto:")
        import json
        try:
            with open("database/world_manifest.json", "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for c in manifest.get("continentes", []):
                pixels = c.get("pixels_terra", 0)
                status = "✔" if pixels > 0 else "✘ (sem terra detectada)"
                print(f"  {status}  {c['nome']:20s}  uuid: {c['uuid']}")
        except FileNotFoundError:
            print("  (manifesto não encontrado — execute generate_world.py primeiro)")
        sys.exit(1)

    alvo = sys.argv[1]

    generator = ROIZoomGenerator(
        manifest_path="database/world_manifest.json",
        npz_path="database/mapa_composto.npz",
        output_dir="database/continentes",
        target_resolution=3000,
        seed=1337,
        config=CARTOGRAPHER_CONFIG,
    )

    try:
        caminho = generator.generate(alvo)
        print(f"\n✅ Sucesso! Mapa de zoom disponível em:\n   {caminho}")
    except (ValueError, FileNotFoundError) as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
