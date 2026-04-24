import folium
from folium.plugins import Draw
from branca.element import Template, MacroElement


class MapaService:
    def __init__(self, center, cidade=None, zoom=11):
        self.cidade = cidade
        self.map = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles=None
        )

    def add_base_layer(self):
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satélite"
        ).add_to(self.map)

    def add_layer(self, layer):
        layer.add_to(self.map)

    def add_default_plugins(self):
        Draw(
            draw_options={
                'polyline': False,
                'polygon': True,
                'circle': False,
                'rectangle': True,
                'marker': True
            }
        ).add_to(self.map)

    def add_layer_control(self):
        folium.LayerControl().add_to(self.map)
    
    def add_click_popup(self):
        template = f"""
            {{% macro script(this, kwargs) %}}

            var map = {{{{this._parent.get_name()}}}};

            map.on('click', function(e) {{
                const lat = e.latlng.lat;
                const lon = e.latlng.lng;

                L.popup()
                    .setLatLng([lat, lon])
                    .setContent("Carregando...")
                    .openOn(map);

                fetch('/valor_ponto', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        lat: lat,
                        lon: lon,
                        cidade: "{self.cidade}"
                    }})
                }})
                .then(response => response.json())
                .then(data => {{

                    const popupContent = `
                        <b>Coordenadas</b><br>
                        Lat: ${{lat.toFixed(5)}}<br>
                        Lon: ${{lon.toFixed(5)}}<br><br>

                        <b>Risco:</b> ${{data.risco?.toFixed(2)}}<br>
                        <b>Uso do solo:</b> ${{data.uso_solo}}<br>
                        <b>Declividade (°):</b> ${{data.declividade?.toFixed(2)}}<br>
                        <b>Elevação (m):</b> ${{data.elevacao?.toFixed(2)}}<br>
                        <b>Fluxo acumulado:</b> ${{data.fluxo?.toFixed(2)}}
                    `;

                    L.popup()
                        .setLatLng([lat, lon])
                        .setContent(popupContent)
                        .openOn(map);
                }})
                .catch(() => {{
                    L.popup()
                        .setLatLng([lat, lon])
                        .setContent("Erro ao buscar dados")
                        .openOn(map);
                }});
            }});

            {{% endmacro %}}
            """

        macro = MacroElement()
        macro._template = Template(template)
        self.map.add_child(macro)
    
    def render(self):
        return self.map._repr_html_()
