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
    
    def add_legend(self):
        template = """
            {% macro html(this, kwargs) %}
            <div id="legend_risco" style="
                position: fixed;
                bottom: 20px;
                left: 20px;
                width: 150px;
                height: 160px;
                z-index:9999;
                font-size:14px;
                background-color: white;
                border:2px solid grey;
                border-radius:5px;
                padding: 10px;
                box-shadow: 3px 3px 5px rgba(0,0,0,0.4);
                display: block;
            ">
                <b>Risco de Alagamento</b><br>
                <i style="background:#d73027;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Alto<br>
                <i style="background:#ffffb2;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Moderado<br>
                <i style="background:#78c679;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Baixo<br>
                <i style="background:#006837;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Muito Baixo<br>
            </div>
            {% endmacro %}
        """

        macro = MacroElement()
        macro._template = Template(template)
        self.map.add_child(macro)
    
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
    
    def add_ahp_sliders(self, pesos_iniciais, cidade):
        w_uso0, w_decl0, w_flux0, w_hipso0 = pesos_iniciais

        sliders_inner_html = f"""
        <div>
            <b>Pesos (AHP)</b><br>

            <label>Uso do solo: <span id="w_uso_val">{w_uso0:.4g}</span></label>
            <input id="w_uso" type="range" min="0" max="1" step="0.01" value="{w_uso0}">

            <label>Declividade: <span id="w_decl_val">{w_decl0:.4g}</span></label>
            <input id="w_decl" type="range" min="0" max="1" step="0.01" value="{w_decl0}">

            <label>Fluxo: <span id="w_flux_val">{w_flux0:.4g}</span></label>
            <input id="w_flux" type="range" min="0" max="1" step="0.01" value="{w_flux0}">

            <label>Hipsometria: <span id="w_hipso_val">{w_hipso0:.4g}</span></label>
            <input id="w_hipso" type="range" min="0" max="1" step="0.01" value="{w_hipso0}">

            <button onclick="atualizarMapa()">Atualizar</button>
        </div>
        """

        template = f"""
        {{% macro html(this, kwargs) %}}
        <div style="
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 250px;
            z-index:9999;
            background: white;
            padding:10px;
            border:2px solid grey;
        ">
            {sliders_inner_html}
        </div>

        <script>
        function atualizarMapa() {{
            const payload = {{
                cidade: "{cidade}",
                pesos: {{
                    uso: parseFloat(document.getElementById("w_uso").value),
                    declividade: parseFloat(document.getElementById("w_decl").value),
                    fluxo: parseFloat(document.getElementById("w_flux").value),
                    hipsometria: parseFloat(document.getElementById("w_hipso").value)
                }}
            }};

            fetch('/executar_analise', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.mapa_html) {{
                    document.body.innerHTML = data.mapa_html;
                }}
            }});
        }}
        </script>

        {{% endmacro %}}
        """

        macro = MacroElement()
        macro._template = Template(template)

        self.map.add_child(macro)
    
    def render(self):
        return self.map._repr_html_()
