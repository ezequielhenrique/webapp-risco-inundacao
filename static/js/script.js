import { map, createMap } from "./mapa/mapa.js";
import { createOverlay, createUsoSoloLayer, addOverlay } from "./mapa/layers.js";
import { initSliders } from "./mapa/sliders.js";
import { enableClickInfo } from "./mapa/interactions.js";


window.addEventListener("DOMContentLoaded", () => {
    createMap([-8.38, -37.86], 6);
});

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

            console.log(data)

            createMap(data.centro);

            const riscoLayer = createOverlay(data.overlay_url, data.bounds);
            addOverlay("Risco de Alagamento", riscoLayer);

            createUsoSoloLayer(data.uso_url, data.uso_bounds);

            initSliders(data);
            enableClickInfo(data.cidade);

            document.getElementById("sliders").classList.remove("hidden");
            document.getElementById("legend").classList.remove("hidden");

        } else {
            showAlert("Erro: " + data.mensagem);
        }
    })
    .catch(err => {
        console.error(err);
        showAlert("Erro ao processar análise: " + err);
    })
    .finally(() => {
        modal.classList.add("hidden");
    });
});


const toggleBtn = document.getElementById("toggle-ahp");

if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
        const panel = document.getElementById("ahp-panel");
        panel.classList.toggle("hidden");
    });
}

// SIDEBAR

const sidebar = document.getElementById("sidebar");
const overlayEl = document.getElementById("overlay");
const menuBtn = document.getElementById("menu-toggle");

menuBtn.addEventListener("click", () => {
    sidebar.classList.add("open");
    overlayEl.classList.add("active");

    toggleMapInteraction();
});

overlayEl.addEventListener("click", () => {
    sidebar.classList.remove("open");
    overlayEl.classList.remove("active");

    toggleMapInteraction();
});

function toggleMapInteraction() {
    if (!map) return;

    const isOpen = sidebar.classList.contains("open");

    if (isOpen) {
        map.dragging.disable();
        map.scrollWheelZoom.disable();
        map.doubleClickZoom.disable();
    } else {
        map.dragging.enable();
        map.scrollWheelZoom.enable();
        map.doubleClickZoom.enable();
    }
}

const closeBtn = document.getElementById("close-sidebar");

closeBtn.addEventListener("click", () => {
    sidebar.classList.remove("open");
    overlayEl.classList.remove("active");
    toggleMapInteraction();
});
