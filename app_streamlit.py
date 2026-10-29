"""
app_streamlit.py - Versão Streamlit do organizador de dossiê RSC-PCCTAE (UFF).

Substitui o app.py (Flask) + templates/index.html + JavaScript.
Reaproveita, sem alteração, servidor.py, gerar_requerimento.py e
compactar_dossie.py, e a lógica de pontuação, que passa a morar em
rsc_logica.py (veja as instruções de mudança no final da resposta).

Rodar:   streamlit run app_streamlit.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

import streamlit as st

import servidor as sv
from rsc_logica import CRITERIOS, converter_pontuacao, montar_dados_requerimento

PASTA_BASE = Path(__file__).resolve().parent
SCRIPTS = ["gerar_requerimento.py", "compactar_dossie.py"]
ARQUIVO_ZIP = PASTA_BASE / "processoArquivos" / "Dossie_RSC_PCCTAE.zip"
ROMANO = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}

# Pastas de trabalho. Pastas vazias não vão para o GitHub (e estas estão no
# .gitignore), então no servidor elas precisam ser criadas ao iniciar.
PASTAS_TRABALHO = ["processoArquivos", "RequerimentoRSC", "dadosdoServidor"]


def garantir_pastas() -> None:
    """Cria todas as pastas de trabalho, se ainda não existirem."""
    for nome in PASTAS_TRABALHO:
        (PASTA_BASE / nome).mkdir(parents=True, exist_ok=True)
    (PASTA_BASE / sv.PASTA_DOCUMENTOS).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------- utilidades
def fmt(valor) -> str:
    """12.5 -> '12,5'; 3.0 -> '3'."""
    if valor is None:
        return "-"
    return f"{float(valor):g}".replace(".", ",")


def nome_seguro(nome: str) -> str:
    """Equivalente ao secure_filename do Flask (só ASCII, sem espaços)."""
    nome = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    nome = nome.replace("/", " ").replace("\\", " ")
    nome = re.sub(r"[^A-Za-z0-9_.-]", "", "_".join(nome.split()))
    return nome.strip("._")


def nivel_para_calculo(nivel: str) -> str:
    """'RSC-PCCTAE V', 'RSC-V' ou 'V' -> 'RSC-V' (formato das regras de pontuação)."""
    if not nivel:
        return ""
    romano = nivel.split()[-1].replace("RSC-", "").strip()
    return f"RSC-{romano}"


# ----------------------------------------------- estado: linhas por critério
def _mais(chave: str):
    st.session_state[chave] += 1


def _menos(chave: str):
    st.session_state[chave] = max(1, st.session_state[chave] - 1)


def coletar_envios() -> dict:
    """{(requisito, item, linha): [UploadedFile, ...]} do que está na tela agora."""
    envios = {}
    for c in CRITERIOS:
        r, i = c["requisito"], c["item"]
        for linha in range(1, st.session_state.get(f"n_{r}_{i}", 1) + 1):
            arquivos = st.session_state.get(f"pdf__{r}_{i}_{linha}") or []
            if arquivos:
                envios[(r, i, linha)] = list(arquivos)
    return envios


def coletar_tipos() -> dict:
    """tipo_pontuacao__R_I_L -> 'titular' | 'substituto' (itens variáveis)."""
    tipos = {}
    for c in CRITERIOS:
        if not c.get("variavel"):
            continue
        r, i = c["requisito"], c["item"]
        for linha in range(1, st.session_state.get(f"n_{r}_{i}", 1) + 1):
            tipos[f"tipo_pontuacao__{r}_{i}_{linha}"] = st.session_state.get(
                f"tipo_pontuacao__{r}_{i}_{linha}", "titular")
    return tipos


# ------------------------------------------------- validação e gravação (PDF)
def validar_pdfs(envios: dict):
    """Valida tudo em memória. Devolve (lista_valida, erros)."""
    validos, erros, nomes_finais = [], [], set()
    for (r, i, linha), arquivos in sorted(envios.items()):
        for arq in arquivos:
            original = nome_seguro(arq.name)
            caminho = Path(original)
            base, ext = caminho.stem[:50], caminho.suffix.lower()
            conteudo = arq.getvalue()
            if not original:
                erros.append(f"{arq.name}: nome de arquivo inválido.")
            elif ext != ".pdf":
                erros.append(f"{arq.name}: a extensão não é PDF.")
            elif not base:
                erros.append(f"{arq.name}: nome inválido.")
            elif not conteudo:
                erros.append(f"{arq.name}: arquivo vazio.")
            elif len(conteudo) > sv.TAMANHO_MAXIMO_PDF:
                erros.append(f"{arq.name}: excede o limite de tamanho.")
            elif not conteudo.startswith(b"%PDF-"):
                erros.append(f"{arq.name}: conteúdo PDF inválido.")
            else:
                final = f"{r}.{i}.{linha}.{base}{ext}"
                if final in nomes_finais:
                    erros.append(f"{arq.name}: nome repetido na mesma linha "
                                 f"({r}.{i}, linha {linha}).")
                else:
                    nomes_finais.add(final)
                    validos.append((r, i, linha, final, conteudo))
    return validos, erros


def gravar_pdfs(validos: list) -> dict:
    """Esvazia as pastas e grava os PDFs. Só é chamada depois da validação."""
    garantir_pastas()
    sv.limpar_armazenamento()
    sv.preparar_armazenamento()
    garantir_pastas()
    pdfs_por_linha = defaultdict(list)
    for r, i, linha, final, conteudo in validos:
        (Path(sv.PASTA_DOCUMENTOS) / final).write_bytes(conteudo)
        pdfs_por_linha[(r, i, linha)].append(final)
    return dict(pdfs_por_linha)


def executar_scripts() -> None:
    """Gera o requerimento HTML e compacta o dossiê (mesmos scripts de antes)."""
    for nome in SCRIPTS:
        caminho = PASTA_BASE / nome
        if not caminho.is_file():
            raise FileNotFoundError(f"Script não encontrado: {caminho}")
        res = subprocess.run([sys.executable, str(caminho)], cwd=str(PASTA_BASE),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Falha ao executar {nome}.\n{res.stdout}\n{res.stderr}")
    if not ARQUIVO_ZIP.is_file():
        raise FileNotFoundError(f"O ZIP não foi criado: {ARQUIVO_ZIP}")


# -------------------------------------------------------------------- tela
def bloco_item(c: dict) -> None:
    r, i = c["requisito"], c["item"]
    chave_n = f"n_{r}_{i}"
    if chave_n not in st.session_state:
        st.session_state[chave_n] = 1  # já nasce com um campo de envio
    n = st.session_state[chave_n]

    pontos = fmt(converter_pontuacao(c["pontos"]))
    if c.get("variavel"):
        pontos += f" (substituto: {fmt(converter_pontuacao(c['pontos_substituto']))})"
    com_arquivo = sum(1 for k in range(1, n + 1)
                      if st.session_state.get(f"pdf__{r}_{i}_{k}"))
    marca = f" - {com_arquivo} comprovação(ões)" if com_arquivo else ""
    with st.expander(f"{r}.{i}  |  {pontos} pts  |  {c['titulo'][:85]}…{marca}",
                     expanded=com_arquivo > 0 or n > 1):
        st.write(c["titulo"])
        st.caption(f"Unidade de medida: {c['unidade']}")
        for linha in range(1, n + 1):
            col_pdf, col_tipo = st.columns([3, 1]) if c.get("variavel") else (st.container(), None)
            col_pdf.file_uploader(
                f"Documento(s) da linha {linha}", type=["pdf"],
                accept_multiple_files=True, key=f"pdf__{r}_{i}_{linha}")
            if col_tipo is not None:
                col_tipo.radio(
                    "Exercício", ["titular", "substituto"],
                    format_func=str.capitalize,
                    key=f"tipo_pontuacao__{r}_{i}_{linha}")
        b1, b2, _ = st.columns([1, 1, 3])
        b1.button("➕ Adicionar linha", key=f"mais_{r}_{i}", on_click=_mais,
                  args=(chave_n,))
        if n > 1:
            b2.button("➖ Remover última", key=f"menos_{r}_{i}", on_click=_menos,
                      args=(chave_n,))


def main() -> None:
    st.set_page_config(page_title="Dossiê RSC-PCCTAE - UFF", layout="wide")
    garantir_pastas()
    sv.preparar_armazenamento()
    st.title("Dossiê do RSC-PCCTAE (UFF)")
    st.caption("Tudo é processado neste computador. Ao gerar o dossiê, as pastas "
               "de trabalho anteriores são substituídas.")

    # ---- dados funcionais
    st.subheader("Dados funcionais")
    c1, c2 = st.columns(2)
    nome = c1.text_input("Nome completo")
    nome_social = c2.text_input("Nome social (opcional)")
    c1, c2, c3 = st.columns(3)
    matricula = c1.text_input("Matrícula SIAPE", max_chars=7)
    cargo = c2.text_input("Cargo")
    data_ingresso = c3.date_input("Data de ingresso na UFF", value=None,
                                  min_value=date(1960, 1, 1), max_value=date.today(),
                                  format="DD/MM/YYYY")
    c1, c2 = st.columns(2)
    nivel_class = c1.radio("Nível de classificação", sv.NIVEIS_CLASSIFICACAO,
                           index=None, horizontal=True)
    unidade = c2.text_input("Unidade de lotação")
    c1, c2, c3, c4 = st.columns(4)
    fg = c1.checkbox("Função Gratificada (FG)")
    cd = c2.checkbox("Cargo de Direção (CD)")
    telefone = c3.text_input("Telefone", placeholder="(21) 99999-9999")
    email = c4.text_input("E-mail")

    # ---- pedido
    st.subheader("Pedido")
    c1, c2 = st.columns(2)
    prioridade = c1.radio("Solicita atendimento prioritário?", ["Não", "Sim"],
                          horizontal=True)
    motivo = c2.text_area("Motivo do atendimento prioritário") if prioridade == "Sim" else ""
    nivel_rsc = st.radio("Nível de RSC pretendido", sv.NIVEIS_RSC, index=None,
                         horizontal=True)
    c1, c2 = st.columns(2)
    processo_anterior = c1.text_input("Nº do processo da concessão anterior (se houver)")
    saldo_anterior = c2.number_input("Saldo de pontuação de concessão anterior",
                                     min_value=0.0, step=0.5, value=0.0)

    # ---- critérios
    st.subheader("Comprovantes por critério")
    st.caption("Abra o item e anexe o(s) PDF(s). Use «Adicionar linha» só quando "
               "houver mais de uma ocorrência (cada linha conta uma vez, "
               "não importa quantos PDFs tenha).")
    abas = st.tabs([f"Requisito {ROMANO[r]}" for r in range(1, 7)])
    for r, aba in zip(range(1, 7), abas):
        with aba:
            for c in (x for x in CRITERIOS if x["requisito"] == r):
                bloco_item(c)

    # ---- pontuação ao vivo (barra lateral)
    envios = coletar_envios()
    valores_calculo = {
        "nivel_rsc_pretendido": nivel_para_calculo(nivel_rsc or ""),
        "saldo_pontuacao_anterior": saldo_anterior,
        "processo_anterior": processo_anterior,
        **coletar_tipos(),
    }
    nomes_previa = {k: [a.name for a in v] for k, v in envios.items()}
    previa = montar_dados_requerimento(valores_calculo, nomes_previa)["requerimento"]
    with st.sidebar:
        st.header("Pontuação")
        st.metric("Pontos dos critérios", fmt(previa["pontuacao_criterios_atuais"]))
        st.metric("Total (com saldo anterior)", fmt(previa["pontuacao_total"]))
        st.write(f"Mínimo do nível: **{fmt(previa['pontuacao_minima_necessaria'])}**")
        st.write(f"Critérios comprovados: **{previa['quantidade_criterios_comprovados']}** "
                 f"(mínimo {fmt(previa['quantidade_criterios_minima'])})")
        if previa["pendencias"]:
            for p in previa["pendencias"]:
                st.warning(p["descricao"])
        elif nivel_rsc:
            st.success("Mínimos do nível atendidos.")

    # ---- gerar
    st.divider()
    if st.button("Gerar dossiê (.zip)", type="primary"):
        st.session_state.pop("zip_bytes", None)
        dados = sv.DadosServidor(
            nome=nome, nome_social=nome_social, matricula_siape=matricula,
            cargo=cargo, data_ingresso=data_ingresso,
            nivel_classificacao=nivel_class or "", unidade_lotacao=unidade,
            funcao_gratificada=fg, cargo_direcao=cd, telefone=telefone, email=email,
            atendimento_prioritario=(prioridade == "Sim"), motivo_prioridade=motivo,
            nivel_rsc_pretendido=nivel_rsc or "", processo_anterior=processo_anterior,
            saldo_pontuacao_anterior=float(saldo_anterior))

        erros = list(sv.validar(dados))
        validos, erros_pdf = validar_pdfs(envios)
        erros += erros_pdf
        if not validos and not erros_pdf:
            erros.append("Anexe ao menos um PDF em algum critério.")
        if erros:
            st.error("Corrija antes de gerar:")
            for e in erros:
                st.write(f"- {e}")
        else:
            try:
                with st.spinner("Gravando arquivos e gerando o dossiê..."):
                    pdfs_por_linha = gravar_pdfs(validos)
                    adicionais = montar_dados_requerimento(valores_calculo, pdfs_por_linha)
                    sv.salvar_dados(dados, dados_adicionais=adicionais)
                    executar_scripts()
                    st.session_state["zip_bytes"] = ARQUIVO_ZIP.read_bytes()
                st.success(f"Dossiê gerado com {len(validos)} PDF(s).")
            except Exception as erro:  # mostra a causa em vez de travar a tela
                st.error(f"Erro ao gerar o dossiê: {erro}")

    if "zip_bytes" in st.session_state:
        st.download_button("⬇️ Baixar Dossie_RSC_PCCTAE.zip",
                           data=st.session_state["zip_bytes"],
                           file_name="Dossie_RSC_PCCTAE.zip", mime="application/zip")


if __name__ == "__main__":
    main()