
"""
servidor.py
Regras de negócio e armazenamento do organizador de dossiê RSC-PCCTAE.

Responsabilidades:
- Definir os dados da servidora.
- Validar o cadastro.
- Salvar os dados em dadosdoServidor/dadosServidor.json.
- Salvar documentos PDF em documentosServidor/.
- Listar os documentos já armazenados.
- Limpar as pastas de armazenamento quando solicitado.

Este módulo não depende de Flask, HTML, CSS ou JavaScript.
"""

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path


# ---------------------------------------------------------
# Configurações e caminhos
# ---------------------------------------------------------

PASTA_BASE = Path(__file__).resolve().parent

PASTA_DADOS = PASTA_BASE / "dadosdoServidor"
PASTA_DOCUMENTOS = PASTA_BASE / "documentosdoServidor"
PASTA_PROCESSOS = PASTA_BASE / "processoArquivos"

ARQUIVO_DADOS = PASTA_DADOS / "dadosServidor.json"


# Confira se estes níveis correspondem aos do projeto original.
NIVEIS_CLASSIFICACAO = ["A", "B", "C", "D", "E"]
NIVEIS_RSC = [
    "RSC-I",
    "RSC-II",
    "RSC-III",
    "RSC-IV",
    "RSC-V",
    "RSC-VI",
]

TAMANHO_MAXIMO_PDF = 25 * 1024 * 1024  # 25 MB por arquivo


# ---------------------------------------------------------
# Estrutura dos dados
# ---------------------------------------------------------

@dataclass
class DadosServidor:
    nome: str
    matricula_siape: str
    cargo: str
    data_ingresso: date | None
    nivel_classificacao: str
    unidade_lotacao: str
    funcao_gratificada: bool
    cargo_direcao: bool
    telefone: str
    email: str
    atendimento_prioritario: bool
    motivo_prioridade: str
    nivel_rsc_pretendido: str
    nome_social: str = ""
    processo_anterior: str = ""
    saldo_pontuacao_anterior: float = 0.0


# ---------------------------------------------------------
# Preparação e limpeza das pastas
# ---------------------------------------------------------

def preparar_armazenamento() -> None:
    """Cria as pastas necessárias, caso ainda não existam."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    PASTA_DOCUMENTOS.mkdir(parents=True, exist_ok=True)


def esvaziar_pasta(pasta: Path) -> None:
    for item in pasta.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def limpar_armazenamento():
    esvaziar_pasta(PASTA_DADOS)
    esvaziar_pasta(PASTA_DOCUMENTOS)
    esvaziar_pasta(PASTA_PROCESSOS)

# ---------------------------------------------------------
# Validação do cadastro
# ---------------------------------------------------------

def validar(dados: DadosServidor) -> list[str]:
    """
    Verifica os campos obrigatórios e a consistência dos dados.
    Retorna uma lista de mensagens de erro.
    """
    erros = []

    if not dados.nome.strip():
        erros.append("Informe o nome completo da servidora.")

    if not re.fullmatch(r"\d{7}", dados.matricula_siape):
        erros.append(
            "A matrícula SIAPE deve conter exatamente 7 dígitos."
        )

    if not dados.cargo.strip():
        erros.append("Informe o cargo.")

    if dados.data_ingresso is None:
        erros.append("Informe a data de ingresso na UFF.")
    elif not isinstance(dados.data_ingresso, date):
        erros.append("A data de ingresso é inválida.")
    elif dados.data_ingresso > date.today():
        erros.append("A data de ingresso não pode ser futura.")
    elif dados.data_ingresso < date(1960, 1, 1):
        erros.append(
            "A data de ingresso deve ser posterior a 01/01/1960."
        )

    if dados.nivel_classificacao not in NIVEIS_CLASSIFICACAO:
        erros.append("Selecione um nível de classificação válido.")

    if not dados.unidade_lotacao.strip():
        erros.append("Informe a unidade de lotação.")

    if dados.email and not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        dados.email,
    ):
        erros.append("Informe um endereço de e-mail válido.")

    if (
        dados.atendimento_prioritario
        and not dados.motivo_prioridade.strip()
    ):
        erros.append("Informe o motivo do atendimento prioritário.")

    if dados.nivel_rsc_pretendido not in NIVEIS_RSC:
        erros.append("Selecione um nível de RSC pretendido válido.")

    return erros


# ---------------------------------------------------------
# Salvamento dos dados
# ---------------------------------------------------------


def salvar_dados(
    dados: DadosServidor,
    dados_adicionais: dict | None = None,
) -> None:
    preparar_armazenamento()

    conteudo = asdict(dados)

    if conteudo["data_ingresso"] is not None:
        conteudo["data_ingresso"] = (
            conteudo["data_ingresso"].isoformat()
        )

    # Acrescenta os dados do requerimento sem apagar o cadastro.
    if dados_adicionais:
        conteudo.update(dados_adicionais)

    conteudo["atualizado_em"] = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    with ARQUIVO_DADOS.open("w", encoding="utf-8") as arquivo:
        json.dump(
            conteudo,
            arquivo,
            ensure_ascii=False,
            indent=4,
        )
        arquivo.write("\n")

    # Confirma o conteúdo efetivamente gravado no arquivo.
    with ARQUIVO_DADOS.open("r", encoding="utf-8") as arquivo:
        conteudo_gravado = json.load(arquivo)

# ---------------------------------------------------------
# Gerenciamento de documentos PDF
# ---------------------------------------------------------

def listar_pdfs() -> list[str]:
    """Retorna os nomes dos PDFs existentes na pasta."""
    preparar_armazenamento()

    return sorted(
        arquivo.name
        for arquivo in PASTA_DOCUMENTOS.iterdir()
        if arquivo.is_file()
        and arquivo.suffix.lower() == ".pdf"
    )


def _nome_seguro(nome_original: str) -> str:
    """
    Remove caminhos e caracteres inadequados do nome do arquivo.
    Impede que o nome enviado seja usado para sair da pasta de PDFs.
    """
    nome = nome_original.replace("\\", "/").split("/")[-1]
    nome = re.sub(r"[^A-Za-z0-9À-ÿ._() -]", "_", nome)
    nome = nome.strip(" .")

    if not nome:
        nome = "documento.pdf"

    if not nome.lower().endswith(".pdf"):
        nome += ".pdf"

    return nome


def _caminho_disponivel(nome: str) -> Path:
    """Evita sobrescrever documentos com o mesmo nome."""
    caminho = PASTA_DOCUMENTOS / nome

    if not caminho.exists():
        return caminho

    nome_base = Path(nome).stem
    extensao = Path(nome).suffix
    contador = 1

    while True:
        candidato = PASTA_DOCUMENTOS / (
            f"{nome_base}_{contador}{extensao}"
        )

        if not candidato.exists():
            return candidato

        contador += 1


def salvar_pdfs(
    arquivos: list[tuple[str, bytes]],
) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Salva documentos PDF.

    Parâmetro:
        arquivos: lista de pares (nome_do_arquivo, conteúdo_em_bytes).

    Retorna:
        (nomes_salvos, arquivos_recusados)

    Cada item recusado contém (nome, motivo).
    """
    preparar_armazenamento()

    salvos = []
    recusados = []

    for nome_original, conteudo in arquivos:
        if not nome_original.lower().endswith(".pdf"):
            recusados.append(
                (nome_original, "a extensão do arquivo não é PDF")
            )
            continue

        if not isinstance(conteudo, bytes) or not conteudo:
            recusados.append(
                (nome_original, "o arquivo está vazio ou é inválido")
            )
            continue

        if len(conteudo) > TAMANHO_MAXIMO_PDF:
            recusados.append(
                (nome_original, "o arquivo excede o limite de 25 MB")
            )
            continue

        # Verificação básica da assinatura do arquivo PDF.
        if not conteudo.startswith(b"%PDF-"):
            recusados.append(
                (
                    nome_original,
                    "o conteúdo não possui assinatura PDF válida",
                )
            )
            continue

        nome = _nome_seguro(nome_original)
        destino = _caminho_disponivel(nome)

        try:
            with destino.open("xb") as arquivo:
                arquivo.write(conteudo)

            salvos.append(destino.name)

        except OSError as erro:
            recusados.append(
                (
                    nome_original,
                    f"não foi possível salvar o arquivo: {erro}",
                )
            )

    return salvos, recusados
