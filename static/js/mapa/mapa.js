export let map = null;
export let layerControl = null;
export let baseLayers = {};
export let overlays = {};

export function createMap(center, zoom = 12) {
    if (map) {
        map.remove();
    }

    map = L.map("map").setView(center, zoom);

    const base = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { attribution: "Esri" }
    ).addTo(map);

    baseLayers = { "Satélite": base };
    overlays = {};

    layerControl = L.control.layers(baseLayers, overlays).addTo(map);
}
