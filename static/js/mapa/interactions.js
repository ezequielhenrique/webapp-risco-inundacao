import { map } from "./mapa.js";


export function enableClickInfo(cidade) {
    map.on("click", function (e) {
        const { lat, lng } = e.latlng;

        fetch("/valor_ponto", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                cidade: cidade,
                lat: lat,
                lon: lng
            })
        })
        .then(res => res.json())
        .then(data => {

            console.log(data)

            const content = `
                <b>Informações</b><br>
                Lat: ${lat.toFixed(5)}<br>
                Lon: ${lng.toFixed(5)}<br>
                Risco: ${data.risco.toFixed(2)}<br>
                Uso do solo: ${data.uso_solo}<br>
                Declividade: ${data.declividade.toFixed(2)}<br>
                Elevação: ${data.elevacao.toFixed(2)}<br>
                Fluxo: ${data.fluxo}
            `;

            L.popup()
                .setLatLng([lat, lng])
                .setContent(content)
                .openOn(map);
        })
        .catch(err => {
            console.error("Erro ao buscar dados do ponto:", err);

            L.popup()
                .setLatLng([lat, lng])
                .setContent("<b>Erro ao obter dados")
                .openOn(map);
        });
    });
}
