import { updateOverlay } from "./layers.js";
import { debounce } from "./utils.js";


export function initSliders(data) {
    const { cidade, pesos } = data;

    const container = document.getElementById("ahp-panel");

    if (!container) return;

    container.innerHTML = `
        <div style="
            font-size: 13px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        ">
            <b>Pesos (AHP)</b>

            <button id="w_reset_btn">Resetar</button>

            ${createSlider("uso", "Uso do solo", pesos.uso)}
            ${createSlider("decl", "Declividade", pesos.declividade)}
            ${createSlider("flux", "Fluxo", pesos.fluxo)}
            ${createSlider("hipso", "Hipsometria", pesos.hipsometria)}

            <span id="w_status">Arraste para atualizar</span>
        </div>
    `;

    function createSlider(id, label, value) {
        return `
            <div>
                <label>${label}: <span id="w_${id}_val">${value.toFixed(3)}</span></label>
                <input id="w_${id}" type="range" min="0" max="1" step="0.0001" value="${value}">
            </div>
        `;
    }

    const sliders = ["uso", "decl", "flux", "hipso"];

    sliders.forEach(id => {
        const el = document.getElementById(`w_${id}`);

        el.addEventListener("input", () => {
            document.getElementById(`w_${id}_val`).innerText = el.value;
            debouncedUpdate();
        });
    });

    const debouncedUpdate = debounce(updateMap, 400);

    function updateMap() {
        console.log("Overlay atual:", window.overlay);

        if (!window.overlay) {
            console.warn("Overlay ainda não carregado");
            return;
        }

        document.getElementById("w_status").innerText = "Atualizando...";

        const params = new URLSearchParams({
            cidade: cidade,
            w_uso: document.getElementById("w_uso").value,
            w_decl: document.getElementById("w_decl").value,
            w_flux: document.getElementById("w_flux").value,
            w_hipso: document.getElementById("w_hipso").value
        });

        fetch(`/overlay_risco?${params}`)
            .then(res => res.json())
            .then(resp => {
                if (resp.status === "ok") {
                    updateOverlay(resp.url);
                }
                document.getElementById("w_status").innerText = "Atualizado";
            })
            .catch(() => {
                document.getElementById("w_status").innerText = "Erro";
            });
    }

    // RESET
    document.getElementById("w_reset_btn").addEventListener("click", () => {
        initSliders(data);
        updateMap();
    });
}
