export function renderizarSidebar(config) {

    const container = document.getElementById("sidebar-content")

    container.innerHTML = ""

    // CRITÉRIOS

    Object.entries(config.criterios)
    .forEach(([nome, criterio]) => {

        const criterioDiv = document.createElement("div")

        criterioDiv.classList.add("criterio")

        criterioDiv.innerHTML = `
            <div class="criterio-header">
                <h3 class="criterio-title">${formatarNome(nome)}</h3>

                <span class="status ${criterio.ativo ? "ativo" : "inativo"}">
                    ${criterio.ativo ? "Ativo" : "Inativo"}
                </span>
            </div>
        `

        // CLASSES NUMÉRICAS

        if (Array.isArray(criterio.classes)) {

            criterio.classes.forEach((classe) => {

                const classeDiv = document.createElement("div")

                classeDiv.classList.add("classe-item")

                classeDiv.innerHTML = `
                    <div class="classe-linha">
                        <span>
                            ${classe.min ?? "-"}
                            →
                            ${classe.max ?? "∞"}
                        </span>

                        <span class="badge-risco">
                            Risco ${classe.valor}
                        </span>
                    </div>
                `

                criterioDiv.appendChild(classeDiv)
            })
        }

        // USO DO SOLO

        else {

            Object.entries(criterio.classes)
            .forEach(([classeNome, classe]) => {

                const classeDiv = document.createElement("div")

                classeDiv.classList.add("classe-item")

                classeDiv.innerHTML = `
                    <div class="uso-header">
                        <strong>${formatarNome(classeNome)}</strong>

                        <span class="badge-risco">
                            Risco ${classe.valor}
                        </span>
                    </div>

                    <small>
                        IDs:
                        ${classe.ids.join(", ")}
                    </small>
                `

                criterioDiv.appendChild(classeDiv)
            })
        }

        container.appendChild(criterioDiv)
    })

    renderizarPesos(config.pesos)
}

// PESOS

function renderizarPesos(pesos) {

    const container = document.getElementById("sidebar-content")

    const div = document.createElement("div")

    div.classList.add("pesos-container")

    div.innerHTML = `
        <h2 class="criterio-title">Pesos da Análise</h2>
    `

    Object.entries(pesos)
    .forEach(([nome, valor]) => {

        div.innerHTML += `
            <div class="peso-item">
                <span class="peso-nome">${formatarNome(nome)}</span>
                <span class="peso-valor">${Number(valor).toFixed(2)}</span>
            </div>
        `
    })

    container.appendChild(div)
}

// FORMATAR NOMES

function formatarNome(nome) {

    return nome
        .replaceAll("_", " ")
        .replace(/\b\w/g, l => l.toUpperCase())
}
