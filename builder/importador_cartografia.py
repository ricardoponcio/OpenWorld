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

        CartographyImporter._falhar_se_nome_de_cidade_duplicado(manifest)

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

    @staticmethod
    def _falhar_se_nome_de_cidade_duplicado(manifest: dict) -> None:
        """G05 (docs/PLANO_MUNDO_CRIVEL.md, Bloco G): o nome da cidade vira o slug
        do arquivo GeoJSON e o namespace de id de lote/local (armadilha 3) —
        importar duas cidades com o mesmo nome deixa uma delas com ZERO locais, em
        silêncio (achado real: duas "Cidade dos Ventos" no mesmo manifesto).
        `generate_cities_metadata.py::_garantir_nomes_unicos` já evita isso na
        GERAÇÃO; esta é a rede de segurança da IMPORTAÇÃO — falha alto, nomeando as
        duas cidades, em vez de importar pela metade."""
        continente_do_nome = {}
        for cont in manifest.get("continentes", []):
            for cid in cont.get("cidades", []):
                nome = cid["nome"]
                if nome in continente_do_nome:
                    raise ValueError(
                        f"[CARTOGRAFIA] Nome de cidade duplicado no manifesto: '{nome}' "
                        f"aparece em '{continente_do_nome[nome]}' e em '{cont['nome']}'. "
                        f"Rode cartographer/reset_cartography.sh pra gerar um mundo novo "
                        f"(G05, docs/PLANO_MUNDO_CRIVEL.md) — importar pela metade "
                        f"deixaria uma das duas cidades sem locais."
                    )
                continente_do_nome[nome] = cont["nome"]
