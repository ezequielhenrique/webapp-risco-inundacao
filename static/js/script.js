function openModal() {
    fetch('static/config/config.json')
        .then(res => res.json())
        .then(data => {
            configData = data;
            preencherPesos();
            preencherClasses();
            document.getElementById("configModal").style.display = "block";
        });
    document.getElementById("configModal").style.display = "block";
}

function closeModal() {
    document.getElementById("configModal").style.display = "none";
}

window.onclick = function(event) {
    let modal = document.getElementById("configModal");
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

document.getElementById("btn-executar").addEventListener("click", function() {
    let cidade = document.getElementById("cidade").value;
    let mapaContainer = document.getElementById("mapa-container");
    let modal = document.getElementById("loadingModal");

    modal.classList.remove("hidden");

    fetch("/executar_analise", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ cidade: cidade })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "ok") {
            mapaContainer.innerHTML = data.mapa_html;
        } else {
            showAlert("Erro: " + data.mensagem);
        }
    })
    .catch(err => {
        console.error(err);
        showAlert("Erro ao processar análise");
    })
    .finally(() => {
        modal.classList.add("hidden");
    });
});

function preencherCheckboxes() {
    document.querySelector('[name="uso_ativo"]').checked = configData.criterios.uso_do_solo.ativo;
    document.querySelector('[name="declividade_ativo"]').checked = configData.criterios.declividade.ativo;
    document.querySelector('[name="fluxo_ativo"]').checked = configData.criterios.fluxo_acumulado.ativo;
}

function preencherPesos() {
    const container = document.getElementById("criteriaContainer");
    container.innerHTML = '';

    const opcoesAHP = [
        { value: 1/9, label: "Extremamente menos importante que" },
        { value: 1/7, label: "Muito fortemente menos importante que" },
        { value: 1/5, label: "Fortemente menos importante que" },
        { value: 1/3, label: "Moderadamente menos importante que" },
        { value: 1,   label: "Igualmente importante a" },
        { value: 3,   label: "Moderadamente mais importante que" },
        { value: 5,   label: "Fortemente mais importante que" },
        { value: 7,   label: "Muito fortemente mais importante que" },
        { value: 9,   label: "Extremamente mais importante que" }
    ];

    Object.entries(configData.pesos).forEach(([nome, valor]) => {
        let optionsHTML = opcoesAHP.map(opt => {

            const selected = (parseFloat(valor) === opt.value) ? "selected" : "";
            return `<option value="${opt.value}" ${selected}>${opt.label}</option>`;
        }).join("");

        container.innerHTML += `
            <div class="pesos-item">
                <label class="modal-label">${nome.replaceAll('_', ' ')}</label>
                <select class="modal-input" name="pesos[${nome}]">
                    ${optionsHTML}
                </select>
            </div>
        `;
    });
}

function preencherClasses() {
    const container = document.getElementById("classesContainer");
    container.innerHTML = '';

    Object.entries(configData.criterios).forEach(([criterio, dados]) => {
        container.innerHTML += `<p class="modal-subtitle">${criterio.replaceAll('_', ' ')}</p>`;

        if (Array.isArray(dados.classes)) {
            // Intervalos (declividade, fluxo)
            dados.classes.forEach((cls, i) => {
                container.innerHTML += `
                    <div class="class-item">
                        <label class="modal-label">Min</label>
                        <input class="modal-input" type="number" name="${criterio}[${i}][min]" value="${cls.min ?? ''}">
                        <label class="modal-label">Max</label>
                        <input class="modal-input" type="number" name="${criterio}[${i}][max]" value="${cls.max ?? ''}">
                        <label class="modal-label">Valor</label>
                        <input class="modal-input" type="number" name="${criterio}[${i}][valor]" value="${cls.valor}">
                    </div>
                `;
            });
        } else {
            // Categóricas (uso_do_solo)
            Object.entries(dados.classes).forEach(([nomeClasse, cls]) => {
                container.innerHTML += `
                    <div class="class-item">
                        <label class="modal-label">${nomeClasse}</label>
                        <input class="modal-input" type="text" name="${criterio}[${nomeClasse}][ids]" value="${cls.ids.join(',')}">
                        <label class="modal-label">Valor</label>
                        <input class="modal-input" type="number" name="${criterio}[${nomeClasse}][valor]" value="${cls.valor}">
                    </div>
                `;
            });
        }
    });
}

