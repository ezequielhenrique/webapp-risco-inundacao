import { map, layerControl, overlays } from "./mapa.js";

export let overlay = null;
export let pontosAlagamentoLayer = null;

const pontos = [
    ["Rua Imperial, bairro de São José", -8.07581, -34.89415],
    ["Rua Nicolau Pereira", -8.07804, -34.90558],
    ["Av. Eng. Abdias de Carvalho", -8.06123, -34.92227],
    ["Av. Dois Rios", -8.11289, -34.93864],
    ["Av. Mal Mascarenhas de Moraes", -8.11383, -34.91281],
    ["Av. Recife próximo ao cruzamento com a Rua João Cabral de Melo Neto", -8.07953, -34.93374],
    ["Av. Abdias de Carvalho, no cruzamento com a rua Delmiro Gouveia", -8.06252, -34.93219],
    ["Av. Norte Miguel Arraes de Alencar, ao lado do Senai", -8.04713, -34.87757]
];

export function createOverlay(url, bounds) {
    if (overlay) {
        map.removeLayer(overlay);
    }

    overlay = L.imageOverlay(url, bounds, { opacity: 0.6 }).addTo(map);

    return overlay;
}

export function updateOverlay(url) {
    if (!overlay) return;
    overlay.setUrl(url);
}

export function addOverlay(name, layer) {
    overlays[name] = layer;
    layerControl.addOverlay(layer, name);
}

export function createUsoSoloLayer(url, bounds) {
    const layer = L.imageOverlay(url, bounds, { opacity: 0.7 });
    addOverlay("Uso do Solo", layer);
}

export function createPontosAlagamentoLayer() {
    if (pontosAlagamentoLayer) {
        map.removeLayer(pontosAlagamentoLayer);
    }

    const markers = pontos.map(([nome, lat, lng]) => {
        return L.marker([lat, lng])
        .bindPopup(`
            <b>Ponto de Alagamento</b><br>
            ${nome}<br>
            Lat: ${lat}<br>
            Lon: ${lng}
        `);
    });

    pontosAlagamentoLayer = L.layerGroup(markers);
    return pontosAlagamentoLayer;
}
