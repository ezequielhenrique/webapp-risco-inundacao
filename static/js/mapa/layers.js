import { map, layerControl, overlays } from "./mapa.js";

export let overlay = null;

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
