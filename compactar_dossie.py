
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import servidor as sv

# Pasta onde este script está localizado
PASTA_PROJETO = Path(__file__).resolve().parent

# Caminhos dos arquivos
PASTA_DOCUMENTOS = PASTA_PROJETO / sv.PASTA_DOCUMENTOS
ARQUIVO_REQUERIMENTO = (
    PASTA_PROJETO
    / "RequerimentoRSC"
    / "Requerimento de solicitação para RSC-PCCTAE.html"
)

# Arquivo ZIP de saída
ARQUIVO_ZIP = PASTA_PROJETO / "processoArquivos"/ "Dossie_RSC_PCCTAE.zip"


def compactar_dossie():
    if not PASTA_DOCUMENTOS.is_dir():
        raise FileNotFoundError(
            f"Pasta de documentos não encontrada: {PASTA_DOCUMENTOS}"
        )

    if not ARQUIVO_REQUERIMENTO.is_file():
        raise FileNotFoundError(
            f"Requerimento HTML não encontrado: {ARQUIVO_REQUERIMENTO}"
        )

    # Busca os PDFs, inclusive em subpastas
    arquivos_pdf = sorted(
        arquivo
        for arquivo in PASTA_DOCUMENTOS.rglob("*")
        if arquivo.is_file() and arquivo.suffix.lower() == ".pdf"
    )

    if not arquivos_pdf:
        raise FileNotFoundError(
            f"Nenhum PDF encontrado em: {PASTA_DOCUMENTOS}"
        )
    ARQUIVO_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARQUIVO_ZIP, "w", compression=ZIP_DEFLATED) as zipf:
        # Adiciona os PDFs, preservando a estrutura de subpastas
        for arquivo in arquivos_pdf:
            caminho_relativo = arquivo.relative_to(PASTA_PROJETO)
            zipf.write(arquivo, caminho_relativo)

        # Adiciona o requerimento HTML na raiz do ZIP
        zipf.write(
            ARQUIVO_REQUERIMENTO,
            ARQUIVO_REQUERIMENTO.name,
        )

    print("Dossiê compactado com sucesso!")
    print(f"Arquivo ZIP: {ARQUIVO_ZIP}")
    print(f"PDFs incluídos: {len(arquivos_pdf)}")
    print("Requerimento HTML incluído: Sim")


if __name__ == "__main__":
    try:
        compactar_dossie()
    except (OSError, FileNotFoundError) as erro:
        print(f"Erro ao compactar o dossiê: {erro}")
