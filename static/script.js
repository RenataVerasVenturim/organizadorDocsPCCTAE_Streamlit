
document.addEventListener("DOMContentLoaded", () => {
    // Atendimento prioritário
    const prioridade = document.querySelector("#atendimento-prioritario");
    const campoMotivo = document.querySelector("#campo-motivo-prioridade");

    function atualizarMotivo() {
        if (!prioridade || !campoMotivo) return;

        const mostrar = prioridade.value === "Sim";
        campoMotivo.hidden = !mostrar;

        const campo = campoMotivo.querySelector("input");

        if (campo) {
            campo.required = mostrar;

            if (!mostrar) {
                campo.value = "";
            }
        }
    }

    if (prioridade) {
        prioridade.addEventListener("change", atualizarMotivo);
        atualizarMotivo();
    }

    // Campos do resumo de pontuação
    const nivelRsc = document.querySelector(
        'select[name="nivel_rsc_pretendido"]'
    );

    const pontosMinimos = document.querySelector("#pontosMinimos");
    const pontuacaoTotal = document.querySelector("#pontuacaoTotal");

    const saldoPontuacaoAnterior = document.querySelector(
        '[name="saldo_pontuacao_anterior"]'
    );

    const qtdCriterios = document.querySelector("#qtdCriterios");

    const qtdCriteriosMinima = document.querySelector(
        "#qtdCriteriosMinima"
    );

    const situacaoRSC = document.querySelector("#situacaoRSC");

    // Regras configuradas para cada nível de RSC
    const regrasRSC = {
        "RSC-I": {
            pontos: 10,
            criterios: null,
            requisitosAdicionais: []
        },
        "RSC-II": {
            pontos: 15,
            criterios: 2,
            requisitosAdicionais: []
        },
        "RSC-III": {
            pontos: 25,
            criterios: 2,
            requisitosAdicionais: []
        },
        "RSC-IV": {
            pontos: 30,
            criterios: 3,
            requisitosAdicionais: [2, 4, 5, 6]
        },
        "RSC-V": {
            pontos: 52,
            criterios: 5,
            requisitosAdicionais: [4, 5, 6]
        },
        "RSC-VI": {
            pontos: 75,
            criterios: 7,
            requisitosAdicionais: [6]
        }
    };

    // Converte valores numéricos, inclusive decimais brasileiros.
    function converterNumero(valor) {
        if (valor === null || valor === undefined || valor === "") {
            return 0;
        }

        let texto = String(valor).trim();

        if (texto.includes(",")) {
            texto = texto.replace(/\./g, "").replace(",", ".");
        }

        const numero = Number(texto);

        return Number.isFinite(numero) ? numero : 0;
    }

    // Obtém a pontuação unitária de uma linha.
    function obterPontos(linha) {
        const celula = linha.querySelector(".pontos-unitarios");
        const tipo = linha.querySelector(".tipo-pontuacao");

        if (!celula) return 0;

        if (tipo) {
            const atributo = tipo.value === "substituto"
                ? "pontosSubstituto"
                : "pontosTitular";

            const valorVariavel = celula.dataset[atributo];

            if (valorVariavel !== undefined && valorVariavel !== "") {
                return converterNumero(valorVariavel);
            }
        }

        return converterNumero(celula.dataset.pontos);
    }

    // Lê a pontuação exibida em uma linha.
    function obterPontuacao(elemento) {
        return converterNumero(elemento.textContent);
    }

    // Atualiza o resumo geral.
    function atualizarResumoRSC() {
        let totalPontos = 0;
        let totalCriterios = 0;

        const requisitosComprovados = new Set();

        // Soma os pontos dos critérios apresentados.
        document.querySelectorAll(".criterio").forEach(criterio => {
            let pontosDoCriterio = 0;

            criterio.querySelectorAll(".pontuacao-obtida").forEach(elemento => {
                pontosDoCriterio += obterPontuacao(elemento);
            });

            totalPontos += pontosDoCriterio;

            // Várias linhas do mesmo critério contam como um único critério.
            if (pontosDoCriterio > 0) {
                totalCriterios++;

                requisitosComprovados.add(
                    Number(criterio.dataset.requisito)
                );
            }
        });

        totalPontos = Number(totalPontos.toFixed(2));

        // Lê o saldo anterior ATUAL do campo.
        const saldoAnterior = Math.max(
            0,
            converterNumero(saldoPontuacaoAnterior?.value)
        );

        // Recalcula o total do zero: critérios atuais + saldo anterior.
        // Não utiliza pontuacaoTotal.value como base, evitando duplicação.
        const pontuacaoFinal = Number(
            (totalPontos + saldoAnterior).toFixed(2)
        );

        if (pontuacaoTotal) {
            pontuacaoTotal.value = pontuacaoFinal;
        }

        if (qtdCriterios) {
            qtdCriterios.value = totalCriterios;
        }

        // Identifica o nível de RSC selecionado.
        const nivel = nivelRsc?.value || "";
        const regra = regrasRSC[nivel];

        if (!regra) {
            if (pontosMinimos) {
                pontosMinimos.value = "";
            }

            if (qtdCriteriosMinima) {
                qtdCriteriosMinima.value = "—";
            }

            if (situacaoRSC) {
                situacaoRSC.textContent =
                    "Selecione o nível de RSC pretendido.";
            }

            return;
        }

        if (pontosMinimos) {
            pontosMinimos.value = regra.pontos;
        }

        if (qtdCriteriosMinima) {
            qtdCriteriosMinima.value =
                regra.criterios === null
                    ? "Não especificado"
                    : regra.criterios;
        }

        // Verifica a pontuação incluindo o saldo anterior.
        const atendePontos = pontuacaoFinal >= regra.pontos;

        // A contagem de critérios considera apenas os critérios atuais.
        const atendeCriterios =
            regra.criterios === null ||
            totalCriterios >= regra.criterios;

        // Verifica os requisitos adicionais.
        const atendeRequisitos =
            regra.requisitosAdicionais.length === 0 ||
            regra.requisitosAdicionais.some(requisito =>
                requisitosComprovados.has(requisito)
            );

        const pendencias = [];

        if (!atendePontos) {
            const faltamPontos = Number(
                (regra.pontos - pontuacaoFinal).toFixed(2)
            );

            pendencias.push(
                `faltam ${faltamPontos.toLocaleString("pt-BR")} pontos`
            );
        }

        if (!atendeCriterios) {
            pendencias.push(
                `faltam ${regra.criterios - totalCriterios} critérios específicos`
            );
        }

        if (!atendeRequisitos) {
            pendencias.push(
                `é necessário comprovar ao menos um critério dos requisitos: ${
                    regra.requisitosAdicionais.join(", ")
                }`
            );
        }

        if (situacaoRSC) {
            situacaoRSC.textContent = pendencias.length === 0
                ? "Os mínimos de pontuação e critérios previstos para o nível selecionado foram atingidos."
                : "Pendências: " + pendencias.join("; ") + ".";
        }
    }

    // Calcula a pontuação individual de uma linha.
    function calcularLinha(linha) {
        const quantidade = linha.querySelector(".quantidade");
        const resultado = linha.querySelector(".pontuacao-obtida");

        if (!quantidade || !resultado) return;

        const unidades = Math.max(
            0,
            converterNumero(quantidade.value)
        );

        const total = Number(
            (unidades * obterPontos(linha)).toFixed(2)
        );

        resultado.textContent = Number.isInteger(total)
            ? String(total)
            : total.toLocaleString("pt-BR", {
                maximumFractionDigits: 2
            });

        atualizarResumoRSC();
    }

    // Configura uma linha existente ou recém-criada.
    function configurarLinha(linha) {
        const quantidade = linha.querySelector(".quantidade");
        const tipo = linha.querySelector(".tipo-pontuacao");
        const entradaPDF = linha.querySelector(".entrada-pdf");
        const nomesArquivos = linha.querySelector(".nomes-arquivos");

        if (quantidade) {
            quantidade.addEventListener("input", () => {
                calcularLinha(linha);
            });
        }

        if (tipo) {
            tipo.addEventListener("change", () => {
                calcularLinha(linha);
            });
        }

        if (entradaPDF && nomesArquivos) {
            entradaPDF.addEventListener("change", () => {
                const arquivos = Array.from(entradaPDF.files || []);

                nomesArquivos.textContent = arquivos.length
                    ? arquivos.map(arquivo => arquivo.name).join(", ")
                    : "Nenhum arquivo selecionado";

                if (quantidade) {
                    quantidade.value = arquivos.length > 0 ? "1" : "0";
                    calcularLinha(linha);
                }
            });
        }

        calcularLinha(linha);
    }

    // Configura os critérios e permite adicionar linhas de documentos.
    document.querySelectorAll(".criterio").forEach(criterio => {
        const corpo = criterio.querySelector(".linhas-criterio");
        const botaoAdicionar = criterio.querySelector(".botao-adicionar");

        if (!corpo) return;

        corpo.querySelectorAll(".linha-criterio").forEach(configurarLinha);

        if (!botaoAdicionar) return;

        botaoAdicionar.addEventListener("click", () => {
            const original = corpo.querySelector(".linha-criterio");

            if (!original) return;

            const novaLinha = original.cloneNode(true);

            const numeroLinha = Number(
                criterio.dataset.proximaLinha || 2
            );

            criterio.dataset.proximaLinha = String(numeroLinha + 1);

            const requisito = criterio.dataset.requisito;
            const item = criterio.dataset.item;

            const quantidade = novaLinha.querySelector(".quantidade");
            const entradaPDF = novaLinha.querySelector(".entrada-pdf");
            const nomesArquivos = novaLinha.querySelector(".nomes-arquivos");
            const resultado = novaLinha.querySelector(".pontuacao-obtida");
            const tipo = novaLinha.querySelector(".tipo-pontuacao");

            if (quantidade) {
                quantidade.value = "0";
            }

            if (entradaPDF) {
                entradaPDF.value = "";
                entradaPDF.name =
                    `pdf__${requisito}_${item}_${numeroLinha}`;
            }

            // Mantém o nome do campo de tipo de pontuação por linha.
            if (tipo) {
                tipo.name =
                    `tipo_pontuacao__${requisito}_${item}_${numeroLinha}`;
                tipo.value = "titular";
            }

            if (nomesArquivos) {
                nomesArquivos.textContent = "Nenhum arquivo selecionado";
            }

            if (resultado) {
                resultado.textContent = "0";
            }

            corpo.appendChild(novaLinha);
            configurarLinha(novaLinha);
        });
    });

    // Recalcula quando o nível de RSC mudar.
    if (nivelRsc) {
        nivelRsc.addEventListener("change", atualizarResumoRSC);
    }

    // Recalcula imediatamente a cada alteração no saldo anterior.
    if (saldoPontuacaoAnterior) {
        saldoPontuacaoAnterior.addEventListener(
            "input",
            atualizarResumoRSC
        );

        saldoPontuacaoAnterior.addEventListener(
            "change",
            atualizarResumoRSC
        );
    }

    // Inicializa o resumo ao abrir a página.
    atualizarResumoRSC();
});
