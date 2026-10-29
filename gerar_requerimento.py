
"""
gerar_requerimento.py

Lê os dados do JSON e preenche o modelo HTML do requerimento RSC-PCCTAE.
Preserva o HTML original e grava uma cópia preenchida em RequerimentoRSC/.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from pathlib import Path


# Diretório em que este script está localizado.
BASE = Path(__file__).resolve().parent

ARQUIVO_JSON = BASE / "dadosdoServidor" / "dadosServidor.json"
MODELO_HTML = BASE / "requerimentoSolicitacaoModelo.html"
PASTA_SAIDA = BASE / "RequerimentoRSC"

NOME_SAIDA = "Requerimento de solicitação para RSC-PCCTAE.html"


# Associação: id do HTML -> chave do JSON.
CAMPOS = {
    "nome": "nome",
    "nome_social": "nome_social",
    "matricula_siape": "matricula_siape",
    "cargo": "cargo",
    "data_ingresso": "data_ingresso",
    "unidade_lotacao": "unidade_lotacao",
    "telefone": "telefone",
    "email": "email",
    "pontuacao_minima_necessaria": "pontuacao_minima_necessaria",
    "pontuacao_total": "pontuacao_total",
    "pontuacao_total2":"pontuacao_total",
    "quantidade_criterios_comprovados": "quantidade_criterios_comprovados",
    "pontuacao_total_excedente": "pontuacao_total_excedente",
    "saldo_pontuacao_anterior": "saldo_pontuacao_anterior",
    "processo_anterior": "processo_anterior",
}


def ler_html(caminho: Path) -> str:
    """Lê o modelo, aceitando UTF-8 e codificações comuns de HTML legado."""
    conteudo = caminho.read_bytes()

    for codificacao in ("utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Não foi possível ler o HTML: {caminho}")


def formatar_valor(chave: str, valor: object) -> str:
    """Converte valores do JSON para sua apresentação no requerimento."""

    if valor is None:
        return ""

    if chave == "data_ingresso":
        if isinstance(valor, date):
            return valor.strftime("%d/%m/%Y")

        texto = str(valor).strip()

        if not texto:
            return ""

        try:
            return date.fromisoformat(texto).strftime("%d/%m/%Y")
        except ValueError:
            return texto

    if isinstance(valor, bool):
        return "Sim" if valor else "Não"

    return str(valor)


def substituir_campos(corpo: str, dados: dict) -> str:
    """Substitui o conteúdo dos elementos HTML identificados por id."""

    for id_html, chave_json in CAMPOS.items():
        valor = formatar_valor(
            chave_json,
            dados.get(chave_json, "")
        )
        # Escapa o valor para que caracteres como <, > e & não
        # sejam interpretados como HTML.
        valor_html = html.escape(valor, quote=False)

        padrao = re.compile(
            rf'(<(?P<tag>[a-zA-Z][\w:-]*)\b'
            rf'(?=[^>]*\bid=["\']{re.escape(id_html)}["\'])'
            rf'[^>]*>).*?(</(?P=tag)\s*>)',
            flags=re.IGNORECASE | re.DOTALL,
        )

        corpo, quantidade = padrao.subn(
            lambda m: m.group(1) + valor_html + m.group(3),
            corpo,
            count=1,
        )

        if quantidade == 0:
            raise ValueError(
                f'O elemento HTML id="{id_html}" não foi encontrado.'
            )

    return corpo


def texto_linha_html(linha: str) -> str:
    """Extrai o texto de uma linha da tabela para identificar sua opção."""

    texto = re.sub(r"<[^>]+>", " ", linha)
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def marcar_opcoes(corpo: str, escolhidas: list[str]) -> str:
    """
    Marca com X as opções selecionadas.

    Cada opção do modelo está em uma linha de tabela que contém
    o marcador e o texto da opção.
    """

    escolhidas = [op.strip() for op in escolhidas if op and op.strip()]
    encontradas: set[str] = set()

    padrao_linha = re.compile(
        r"<tr\b[^>]*>.*?</tr\s*>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def processar_linha(match: re.Match) -> str:
        linha = match.group(0)

        # Só processa linhas que contenham o marcador de opção.
        if not re.search(
            r'<p\b[^>]*class=["\'][^"\']*Texto_Centralizado_Maiusculas',
            linha,
            flags=re.IGNORECASE,
        ):
            return linha

        texto = texto_linha_html(linha)

        # Evita confundir "Sim" com "Sim. Motivo: ...".
        alvo = next(
            (
                opcao for opcao in escolhidas
                if (
                    texto == opcao
                    or (
                        opcao == "Sim"
                        and texto.startswith("Sim. Motivo:")
                    )
                )
            ),
            None,
        )

        if alvo is None:
            return linha

        padrao_marcador = re.compile(
            r'(<p\b[^>]*class=["\'][^"\']*'
            r'Texto_Centralizado_Maiusculas[^"\']*["\'][^>]*>)'
            r'\s*\((?:\s|&nbsp;|&#160;|&#xA0;)*\)\s*'
            r'(</p>)',
            flags=re.IGNORECASE,
        )

        nova_linha, quantidade = padrao_marcador.subn(
            r"\1(&nbsp;X&nbsp;)\2",
            linha,
            count=1,
        )

        if quantidade:
            encontradas.add(alvo)
            return nova_linha

        return linha

    corpo = padrao_linha.sub(processar_linha, corpo)

    faltantes = sorted(set(escolhidas) - encontradas)

    if faltantes:
        raise ValueError(
            "Não foi possível localizar ou marcar estas opções: "
            + ", ".join(faltantes)
        )

    return corpo

def marcar_nivel_classificacao(corpo: str, nivel_classificacao: str) -> str:
    """Marca com X somente o nível de classificação selecionado no JSON."""

    nivel = str(nivel_classificacao or "").strip().upper()
    niveis_validos = {"A", "B", "C", "D", "E"}

    if nivel not in niveis_validos:
        raise ValueError(
            "O JSON precisa conter um nível de classificação válido: "
            "A, B, C, D ou E."
        )

    opcoes_encontradas = set()

    padrao = re.compile(
        r'(<p\b[^>]*\bdata-value\s*=\s*["\']([A-E])["\'][^>]*>)'
        r'.*?'
        r'(</p>)',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def substituir_opcao(match: re.Match) -> str:
        abertura = match.group(1)
        opcao = match.group(2).upper()
        fechamento = match.group(3)

        opcoes_encontradas.add(opcao)

        if opcao == nivel:
            conteudo = "(&nbsp;X&nbsp;)"
        else:
            conteudo = "(&nbsp; &nbsp; )"

        return abertura + conteudo + fechamento

    corpo = padrao.sub(substituir_opcao, corpo)

    if not niveis_validos.issubset(opcoes_encontradas):
        faltantes = sorted(niveis_validos - opcoes_encontradas)
        raise ValueError(
            "Não foi possível localizar todas as opções de classificação "
            "no HTML. Opções ausentes: " + ", ".join(faltantes)
        )

    return corpo



def marcar_por_data_value(corpo: str, valores: list[str]) -> str:
    """Marca opções por data-value, tratando NAO e NÃO como equivalentes."""

    valores = [
        str(v).strip().upper()
        for v in valores
        if str(v).strip()
    ]

    if not valores:
        return corpo

    # Normaliza a resposta negativa para evitar diferenças de acentuação.
    normalizar = lambda valor: (
        "NAO" if valor.upper() in ("NAO", "NÃO") else valor.upper()
    )

    valores_normalizados = {normalizar(v) for v in valores}

    # Define os grupos cujas opções devem ser limpas e remarcadas.
    if any(v.startswith("RSC-") for v in valores):
        grupo = [
            "RSC-I", "RSC-II", "RSC-III",
            "RSC-IV", "RSC-V", "RSC-VI",
        ]
    elif any(normalizar(v) in ("SIM", "NAO") for v in valores):
        grupo = ["SIM", "NAO", "NÃO"]
    elif any(v in ("FG", "CD") for v in valores):
        grupo = ["FG", "CD"]
    else:
        grupo = valores

    # Localiza os data-values realmente existentes no HTML.
    existentes = re.findall(
        r'<p\b(?=[^>]*\bdata-value\s*=\s*["\']([^"\']+)["\'])[^>]*>',
        corpo,
        flags=re.IGNORECASE | re.DOTALL,
    )

    existentes_normalizados = {normalizar(v) for v in existentes}

    for valor in valores:
        if normalizar(valor) not in existentes_normalizados:
            raise ValueError(
                f'Não foi encontrado no HTML o marcador '
                f'data-value="{valor}" (considerando variações de acentuação).'
            )

    # Processa somente opções do grupo que existem no modelo.
    for valor in grupo:
        valor_normalizado = normalizar(valor)

        if valor_normalizado not in existentes_normalizados:
            continue

        padrao = re.compile(
            r'(<p\b(?=[^>]*\bdata-value\s*=\s*["\']'
            + re.escape(valor)
            + r'["\'])[^>]*>).*?(</p>)',
            flags=re.IGNORECASE | re.DOTALL,
        )

        marcador = (
            "(&nbsp;X&nbsp;)"
            if valor_normalizado in valores_normalizados
            else "(&nbsp; &nbsp; )"
        )

        corpo = padrao.sub(
            lambda m: m.group(1) + marcador + m.group(2),
            corpo,
        )

    return corpo


def preencher_texto_pts_enivel(corpo: str, dados: dict) -> str:
    """Preenche a pontuação total e o nível de RSC no texto do requerimento."""

    pontuacao = formatar_valor(
        "pontuacao_total",
        dados.get("pontuacao_total", "")
    )

    nivel_rsc = formatar_valor(
        "nivel_rsc_pretendido",
        dados.get("nivel_rsc_pretendido", "")
    )

    texto = (
        "À vista das informações apresentadas, totalizo "
        f"{html.escape(pontuacao)} pontos e atendo aos critérios "
        "legais e regulamentares para o nível "
        f"{html.escape(nivel_rsc)} do RSC-PCCTAE. "
        "Solicito a análise pela CRSC-PCCTAE."
    )

    padrao = r'(<[^>]+\bid=["\']ptsEnivel["\'][^>]*>).*?(</[^>]+>)'

    corpo, quantidade = re.subn(
        padrao,
        lambda m: m.group(1) + texto + m.group(2),
        corpo,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if quantidade == 0:
        raise ValueError('O elemento HTML com id="ptsEnivel" não foi encontrado.')

    return corpo
def marcar_funcao_encargo(corpo: str, dados: dict) -> str:
    """Marca somente FG ou CD conforme os dados do JSON."""

    opcoes = {
        "FG": dados.get("funcao_gratificada"),
        "CD": dados.get("cargo_direcao"),
    }

    selecionadas = []

    for codigo, valor in opcoes.items():
        if isinstance(valor, bool):
            resposta = valor
        else:
            texto = str(valor or "").strip().casefold()

            if texto in ("sim", "true", "1"):
                resposta = True
            elif texto in ("não", "nao", "false", "0"):
                resposta = False
            else:
                raise ValueError(
                    f'O campo "{codigo}" recebeu valor inválido: {valor!r}.'
                )

        if resposta:
            selecionadas.append(codigo)

    for codigo in ("FG", "CD"):
        padrao = re.compile(
            r'(<p\b(?=[^>]*\bdata-value\s*=\s*["\']'
            + codigo
            + r'["\'])[^>]*>)(.*?)(</p>)',
            flags=re.IGNORECASE | re.DOTALL,
        )

        marcador = (
            "(&nbsp;X&nbsp;)"
            if codigo in selecionadas
            else "(&nbsp; &nbsp; )"
        )

        corpo, quantidade = padrao.subn(
            lambda m: m.group(1) + marcador + m.group(3),
            corpo,
            count=1,
        )

        if quantidade == 0:
            raise ValueError(
                f'Não foi encontrado o marcador HTML data-value="{codigo}".'
            )

    return corpo
def preencher_motivo_prioridade(corpo: str, dados: dict) -> str:
    """Preenche o motivo do atendimento prioritário quando solicitado."""

    valor = dados.get("atendimento_prioritario")

    if isinstance(valor, bool):
        atendimento = valor
    else:
        resposta = str(valor or "").strip().casefold()

        if resposta in ("sim", "true", "1"):
            atendimento = True
        elif resposta in ("não", "nao", "false", "0"):
            atendimento = False
        else:
            raise ValueError(
                "O campo atendimento_prioritario precisa ser true/false ou Sim/Não."
            )

    if not atendimento:
        return corpo

    motivo = str(dados.get("motivo_prioridade") or "").strip()

    if not motivo:
        raise ValueError(
            'O atendimento prioritário foi solicitado, mas '
            'o campo "motivo_prioridade" está vazio no JSON.'
        )

    motivo_html = html.escape(motivo, quote=False)

    # Localiza somente o texto do motivo, sem alterar a caixa de seleção.
    padrao = re.compile(
        r'(<p\b[^>]*class=["\'][^"\']*\bTexto_Justificado\b[^"\']*["\'][^>]*>)'
        r'\s*Sim\.\s*Motivo:\s*'
        r'(?:\[digite aqui o motivo\])?'
        r'\s*(</p>)',
        flags=re.IGNORECASE | re.DOTALL,
    )

    corpo, quantidade = padrao.subn(
        lambda m: m.group(1) + "Sim. Motivo: " + motivo_html + m.group(2),
        corpo,
        count=1,
    )

    if quantidade == 0:
        raise ValueError(
            'Não foi encontrado no HTML o texto "Sim. Motivo: '
            '[digite aqui o motivo]".'
        )

    return corpo
def preencher_nivel_classificacao(html, dados):
    nivel = str(dados.get("nivel_classificacao", "")).strip().upper()

    if nivel not in {"A", "B", "C", "D", "E"}:
        return html

    padrao = (
        r'(<p\b[^>]*class="Texto_Centralizado_Maiusculas"'
        r'[^>]*data-value="([A-E])"[^>]*>)'
        r'(.*?)'
        r'(</p>)'
    )

    def substituir(match):
        abertura = match.group(1)
        opcao = match.group(2)
        conteudo = match.group(3)
        fechamento = match.group(4)

        if opcao == nivel:
            conteudo = "( X )"
        else:
            conteudo = "(   )"

        return abertura + conteudo + fechamento

    return re.sub(padrao, substituir, html, flags=re.DOTALL)

def formatar_numero_tabela(valor) -> str:
    """Formata números no padrão brasileiro: 3,0; 7,5; 10,0."""
    if valor is None or valor == "":
        return ""

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)

    return f"{numero:.1f}".replace(".", ",")


def gerar_linha_tabela(modelo_linha: str, valores: list[str]) -> str:
    """Preenche as seis células de uma linha da tabela, preservando o HTML."""
    indice = 0

    def substituir_paragrafo(match):
        nonlocal indice

        if indice >= len(valores):
            return match.group(0)

        valor = valores[indice]
        indice += 1

        conteudo = (
            valor
            if indice == 6 and valor
            else html.escape(str(valor), quote=False) if valor
            else "&nbsp;"
        )

        return match.group(1) + conteudo + match.group(3)

    linha = re.sub(
        r"(<p\b[^>]*>)(.*?)(</p>)",
        substituir_paragrafo,
        modelo_linha,
        count=6,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if indice != 6:
        raise ValueError(
            "O modelo da linha da tabela precisa conter seis parágrafos, "
            "um para cada coluna."
        )

    return linha



def preencher_tabela_criterio(
    corpo: str,
    dados: dict,
    numero_criterio: int = 1,
) -> str:
    """Preenche a tabela de um critério com os dados do JSON."""

    criterios = dados.get("criterios", [])

    criterio = next(
        (
            c for c in criterios
            if c.get("numero_requisito") == numero_criterio
        ),
        None,
    )

    if criterio is None:
        raise ValueError(
            f'Não foi encontrado "numero_requisito": {numero_criterio} no JSON.'
        )

    titulos = {
        1: "Critério I - Participação em grupos de trabalho",
        2: "Critério II - Projetos institucionais, gestão, ensino, pesquisa, extensão, inovação ou assistência",
        3: "Critério III - Premiações e reconhecimentos públicos",
        4: "Critério IV - Responsabilidades técnico-administrativas e/ou especializadas",
        5: "Critério V - Funções ou cargos de direção e assessoramento institucional",
        6: "Critério VI - Produção, prospecção e difusão de conhecimento",
    }

    titulo = titulos.get(numero_criterio)

    if not titulo:
        raise ValueError(
            f"Não há título cadastrado para o Critério {numero_criterio}."
        )

    padrao_tabela = re.compile(
        r"<table\b[^>]*>.*?</table>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    tabela_encontrada = None

    for match in padrao_tabela.finditer(corpo):
        if titulo.casefold() in match.group(0).casefold():
            tabela_encontrada = match
            break

    if tabela_encontrada is None:
        raise ValueError(
            f"Não foi encontrada a tabela do {titulo} no HTML."
        )

    tabela = tabela_encontrada.group(0)

    linhas = list(
        re.finditer(
            r"<tr\b[^>]*>.*?</tr>",
            tabela,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    indice_cabecalho = next(
        (
            i for i, linha in enumerate(linhas)
            if "Critério específico" in linha.group(0)
        ),
        None,
    )

    indice_subtotal = next(
        (
            i for i, linha in enumerate(linhas)
            if re.search(
                r"\bSubtotal\s*:",
                linha.group(0),
                flags=re.IGNORECASE,
            )
        ),
        None,
    )

    if (
        indice_cabecalho is None
        or indice_subtotal is None
        or indice_subtotal <= indice_cabecalho + 1
    ):
        raise ValueError(
            f"Não foi possível identificar as linhas da tabela do {titulo}."
        )

    modelo_linha = linhas[indice_cabecalho + 1].group(0)
    novas_linhas = []

    for item in criterio.get("itens", []):
        numero_item = item.get("numero_item", "")
        descricao = item.get("criterio_especifico", "")
        unidade = item.get("unidade_medida", "")

        linhas_preenchidas = item.get("linhas_preenchidas") or [None]


        for linha_dados in linhas_preenchidas:
            if linha_dados is None:
                # O item não possui registros preenchidos.
                # Não gera uma linha sem documentos comprobatórios.
                continue

            documentos = linha_dados.get("documentos_comprobatorios") or []

            # Ignora a linha se não houver documentos anexados.
            if not documentos or not any(
                str(documento).strip() for documento in documentos
            ):
                continue

            pontuacao_unitaria = linha_dados.get(
                "pontuacao_unitaria",
                item.get("pontuacao_unitaria_titular"),
            )
            pontuacao_obtida = linha_dados.get("pontuacao_obtida", 0)

            texto_documentos = "<br>".join(
                html.escape(str(documento), quote=False)
                for documento in documentos
                if str(documento).strip()
            )


            valores = [
                str(numero_item),
                str(descricao),
                str(unidade),
                formatar_numero_tabela(pontuacao_unitaria),
                formatar_numero_tabela(pontuacao_obtida),
                texto_documentos,
            ]

            novas_linhas.append(
                gerar_linha_tabela(modelo_linha, valores)
            )

    subtotal = formatar_numero_tabela(criterio.get("subtotal"))
    linha_subtotal = linhas[indice_subtotal].group(0)

    celulas = list(
        re.finditer(
            r"<td\b[^>]*>.*?</td>",
            linha_subtotal,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    if not celulas:
        raise ValueError(
            f"A linha do subtotal do {titulo} não possui células."
        )

    ultima_celula = celulas[-1]
    conteudo_celula = ultima_celula.group(0)

    conteudo_celula, quantidade = re.subn(
        r"(<p\b[^>]*>).*?(</p>)",
        lambda m: (
            m.group(1)
            + (html.escape(subtotal, quote=False) if subtotal else "&nbsp;")
            + m.group(2)
        ),
        conteudo_celula,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if quantidade == 0:
        raise ValueError(
            f"Não foi encontrado o parágrafo do subtotal do {titulo}."
        )

    linha_subtotal = (
        linha_subtotal[:ultima_celula.start()]
        + conteudo_celula
        + linha_subtotal[ultima_celula.end():]
    )

    inicio_dados = linhas[indice_cabecalho].end()
    fim_dados = linhas[indice_subtotal].start()

    tabela = (
        tabela[:inicio_dados]
        + "\n"
        + "\n".join(novas_linhas)
        + "\n"
        + linha_subtotal
        + tabela[linhas[indice_subtotal].end():]
    )

    return (
        corpo[:tabela_encontrada.start()]
        + tabela
        + corpo[tabela_encontrada.end():]
    )

def preencher_requerimento(modelo: str, dados: dict) -> str:
    """Preenche os campos e marca as opções selecionadas."""

    # Obtém os dados específicos do requerimento.
    dados_requerimento = dados.get("requerimento", {})

    # Combina os dados gerais com os dados do requerimento.
    # Os valores de "requerimento" prevalecem em caso de chaves repetidas.
    dados = {**dados, **dados_requerimento}

    # Agora os campos são preenchidos com os dados combinados.
    corpo = substituir_campos(modelo, dados)
    corpo = preencher_texto_pts_enivel(corpo, dados)
    corpo = preencher_tabela_criterio(corpo, dados, 1)
    corpo = preencher_tabela_criterio(corpo, dados, 2)    
    corpo = preencher_tabela_criterio(corpo, dados, 3) 
    corpo = preencher_tabela_criterio(corpo, dados, 4) 
    corpo = preencher_tabela_criterio(corpo, dados, 5) 
    corpo = preencher_tabela_criterio(corpo, dados, 6)
    

    nivel_classificacao = str(
        dados.get("nivel_classificacao") or ""
    ).strip().upper()

    nivel_rsc = str(
        dados.get("nivel_rsc_pretendido") or ""
    ).strip().upper()

    if nivel_classificacao not in ("A", "B", "C", "D", "E"):
        raise ValueError(
            "O JSON precisa conter um nível de classificação válido (A a E)."
        )

    if nivel_rsc not in (
        "RSC-I",
        "RSC-II",
        "RSC-III",
        "RSC-IV",
        "RSC-V",
        "RSC-VI",
    ):
        raise ValueError("O JSON precisa conter um nível de RSC válido.")

    # Marca o nível de classificação.
    corpo = marcar_nivel_classificacao(
        corpo,
        nivel_classificacao,
    )

    # Marca o nível RSC usando o data-value.
    corpo = marcar_por_data_value(
        corpo,
        [nivel_rsc],
    )
    corpo = preencher_motivo_prioridade(corpo, dados)

    # Marca o atendimento prioritário usando NAO ou SIM.
    valor_atendimento = dados.get("atendimento_prioritario")

    if isinstance(valor_atendimento, bool):
        atendimento = "SIM" if valor_atendimento else "NAO"
    else:
        resposta = str(valor_atendimento or "").strip().casefold()

        if resposta in ("sim", "true", "1"):
            atendimento = "SIM"
        elif resposta in ("não", "nao", "false", "0"):
            atendimento = "NAO"
        else:
            raise ValueError(
                "O campo atendimento_prioritario precisa ser "
                "true/false ou Sim/Não."
            )

    corpo = marcar_por_data_value(
        corpo,
        [atendimento],
    )

    # Marca função gratificada e cargo de direção pelos data-values.
    corpo = marcar_funcao_encargo(corpo, dados)

    # Ajusta o charset para UTF-8.
    corpo = re.sub(
        r'(<meta\b[^>]*charset\s*=\s*)["\']?[\w-]+["\']?',
        r'\1"utf-8"',
        corpo,
        count=1,
        flags=re.IGNORECASE,
    )

    return corpo


def gerar() -> Path:
    """Gera o requerimento preenchido sem modificar o modelo original."""

    if not ARQUIVO_JSON.exists():
        raise FileNotFoundError(
            f"JSON não encontrado: {ARQUIVO_JSON}"
        )

    if not MODELO_HTML.exists():
        raise FileNotFoundError(
            f"Modelo HTML não encontrado: {MODELO_HTML}"
        )

    dados = json.loads(ARQUIVO_JSON.read_text(encoding="utf-8"))


    
    modelo = ler_html(MODELO_HTML)

    corpo_final = preencher_requerimento(modelo, dados)

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / NOME_SAIDA

    destino.write_text(corpo_final, encoding="utf-8")

    return destino


if __name__ == "__main__":
    try:
        arquivo = gerar()
        print(f"Requerimento gerado com sucesso:\n{arquivo}")

    except (OSError, ValueError, KeyError, json.JSONDecodeError) as erro:
        print(f"Erro ao gerar o requerimento: {erro}")
