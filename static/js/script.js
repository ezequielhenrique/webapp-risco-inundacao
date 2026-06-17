import { map, createMap } from "./mapa/mapa.js";
import { createOverlay, createUsoSoloLayer, addOverlay, createPontosAlagamentoLayer } from "./mapa/layers.js";
import { initSliders } from "./mapa/sliders.js";
import { enableClickInfo } from "./mapa/interactions.js";
import { renderizarSidebar } from "./sidebar.js"


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

            const alagamentosLayer = createPontosAlagamentoLayer();
            addOverlay("Pontos de Alagamento", alagamentosLayer);

            initSliders(data);
            enableClickInfo(data.cidade);
            renderizarSidebar(data.config);

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

// SIDEBAR + OVERLAY + AHP

const sidebar = document.getElementById("sidebar");
const overlayEl = document.getElementById("overlay");
const menuBtn = document.getElementById("menu-toggle");

const ahpPanel = document.getElementById("ahp-panel");
const toggleAhpBtn = document.getElementById("toggle-ahp");

const closeBtn = document.getElementById("close-sidebar");

// ABRIR SIDEBAR

function abrirSidebar() {

    sidebar.classList.add("open");
    overlayEl.classList.add("active");

    menuBtn.classList.add("active");

    // Fecha painel AHP automaticamente
    ahpPanel.classList.add("hidden");
    toggleAhpBtn.classList.remove("active");

    bloquearMapa();
}

// FECHAR SIDEBAR

function fecharSidebar() {

    sidebar.classList.remove("open");
    overlayEl.classList.remove("active");

    menuBtn.classList.remove("active");

    liberarMapa();
}

// BLOQUEAR MAPA

function bloquearMapa() {

    if (!map) return;

    map.dragging.disable();
    map.scrollWheelZoom.disable();
    map.doubleClickZoom.disable();
}

// LIBERAR MAPA

function liberarMapa() {

    if (!map) return;

    map.dragging.enable();
    map.scrollWheelZoom.enable();
    map.doubleClickZoom.enable();
}

// EVENTOS SIDEBAR

menuBtn.addEventListener("click", () => {

    const aberta = sidebar.classList.contains("open");

    if (aberta) {
        fecharSidebar();
    } else {
        abrirSidebar();
    }
});

closeBtn.addEventListener("click", fecharSidebar);

overlayEl.addEventListener("click", fecharSidebar);

// EVENTO AHP

if (toggleAhpBtn) {

    toggleAhpBtn.addEventListener("click", () => {

        // Fecha sidebar ao abrir AHP
        fecharSidebar();

        ahpPanel.classList.toggle("hidden");
        toggleAhpBtn.classList.toggle(
            "active",
            !ahpPanel.classList.contains("hidden")
        );
    });
}
