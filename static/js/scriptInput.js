const dataDiv = document.getElementById("cidade-data");
const cidades = JSON.parse(dataDiv.dataset.cidades);

const input = document.getElementById("cidade");
const box = document.getElementById("suggestions");

input.addEventListener("input", () => {
    const valor = input.value.toLowerCase();
    box.innerHTML = "";

    if (!valor) {
        box.style.display = "none";
        return;
    }

    const filtradas = cidades.filter(c =>
        c.toLowerCase().includes(valor)
    ).slice(0, 10);

    filtradas.forEach(cidade => {
        const div = document.createElement("div");
        div.textContent = cidade;

        div.onclick = () => {
            input.value = cidade;
            box.style.display = "none";
        };

        box.appendChild(div);
    });

    box.style.display = "block";
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".autocomplete")) {
        box.style.display = "none";
    }
});