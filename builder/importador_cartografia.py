import os
import json


class CartographyImporter:
    @staticmethod
    def import_manifest(db, manifest_path: str) -> list:
        if not os.path.exists(manifest_path):
            print("❌ Manifesto não encontrado. Por favor, execute a Cartografia Global primeiro.")
            return []

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        print("🗺️  Importando Continentes e Cidades para o Banco de Dados...")
        cidades_salvas = []

        for cont in manifest.get("continentes", []):
            db.mundo.salvar_continente(cont["uuid"], cont["nome"], cont.get("area_real_km2", 0))

            for cid in cont.get("cidades", []):
                cid_id = db.mundo.salvar_cidade(
                    continente_uuid=cont["uuid"],
                    nome=cid["nome"],
                    tamanho=cid.get("tamanho", "Pequeno"),
                    tipo=cid.get("tipo", "Desconhecido"),
                    x_global=cid.get("x_global", 0),
                    y_global=cid.get("y_global", 0)
                )
                cid["db_id"] = cid_id
                cidades_salvas.append(cid)
        return cidades_salvas
