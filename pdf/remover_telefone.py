import os
from pathlib import Path
import fitz  # PyMuPDF

from utils.file_manager import REDE_COMPLETA_DIR, REDE_SEM_TEL_DIR, ensure_dir


def remover_telefones() -> None:
    pasta_origem = REDE_COMPLETA_DIR
    pasta_destino_base = ensure_dir(REDE_SEM_TEL_DIR)

    for uf in os.listdir(pasta_origem):
        pasta_uf_origem = pasta_origem / uf
        if not pasta_uf_origem.is_dir():
            continue

        pasta_uf_destino = ensure_dir(pasta_destino_base / uf)

        for arquivo in os.listdir(pasta_uf_origem):
            if not arquivo.lower().endswith(".pdf"):
                continue

            caminho_origem = pasta_uf_origem / arquivo
            caminho_destino = pasta_uf_destino / arquivo

            doc = fitz.open(caminho_origem)

            for pagina in doc:
                blocks = pagina.get_text("dict")["blocks"]
                for b in blocks:
                    if "lines" not in b:
                        continue
                    for linha in b["lines"]:
                        texto = " ".join(span["text"] for span in linha["spans"])
                        if "Telefone:" in texto:
                            bbox = fitz.Rect(linha["bbox"])
                            pagina.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1))

            doc.save(caminho_destino)
            doc.close()
            print(f"✅ {arquivo} salvo SEM telefones (visualmente).")

    print(f"\n📁 Todos os arquivos foram salvos com o telefone oculto visualmente em: {pasta_destino_base}")


if __name__ == "__main__":
    remover_telefones()