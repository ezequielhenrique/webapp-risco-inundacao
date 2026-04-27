TEMPLATE_LEGENDA = """
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


def get_template_popup(cidade):
    return f"""
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
                        cidade: "{cidade}"
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


def get_sliders_html(w_uso0, w_decl0, w_flux0, w_hipso0):
    return f"""
            <div style="
                width: 100%;
                font-size: 13px;
                background-color: white;
                border: 2px solid grey;
                border-radius: 6px;
                padding: 10px;
                box-shadow: 3px 3px 5px rgba(0,0,0,0.25);
            ">
                <b>Pesos (AHP simplificado)</b><br>
                <div style="margin-top:6px; display:flex; gap:8px; align-items:center;">
                    <button id="w_reset_btn" type="button" style="
                        padding: 4px 8px;
                        border: 1px solid #777;
                        background: #f7f7f7;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 12px;
                    ">Resetar</button>
                    <span style="color:#666; font-size:12px;">volta ao padrão do AHP</span>
                </div>
                <div style=\"margin-top:6px;\">
                    <label>Uso do solo: <span id=\"w_uso_val\">{w_uso0:.4g}</span></label>
                    <div style=\"display:flex; gap:6px; align-items:center;\">
                        <input id=\"w_uso\" type=\"range\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_uso0:.6f}\" style=\"flex:1;\" />
                        <input id=\"w_uso_num\" type=\"number\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_uso0:.6f}\" style=\"width:82px;\" />
                    </div>
                </div>
                <div>
                    <label>Declividade: <span id=\"w_decl_val\">{w_decl0:.4g}</span></label>
                    <div style=\"display:flex; gap:6px; align-items:center;\">
                        <input id=\"w_decl\" type=\"range\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_decl0:.6f}\" style=\"flex:1;\" />
                        <input id=\"w_decl_num\" type=\"number\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_decl0:.6f}\" style=\"width:82px;\" />
                    </div>
                </div>
                <div>
                    <label>Fluxo: <span id=\"w_flux_val\">{w_flux0:.4g}</span></label>
                    <div style=\"display:flex; gap:6px; align-items:center;\">
                        <input id=\"w_flux\" type=\"range\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_flux0:.6f}\" style=\"flex:1;\" />
                        <input id=\"w_flux_num\" type=\"number\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_flux0:.6f}\" style=\"width:82px;\" />
                    </div>
                </div>
                <div>
                    <label>Hipsometria: <span id=\"w_hipso_val\">{w_hipso0:.4g}</span></label>
                    <div style=\"display:flex; gap:6px; align-items:center;\">
                        <input id=\"w_hipso\" type=\"range\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_hipso0:.6f}\" style=\"flex:1;\" />
                        <input id=\"w_hipso_num\" type=\"number\" min=\"0\" max=\"1\" step=\"0.0001\" value=\"{w_hipso0:.6f}\" style=\"width:82px;\" />
                    </div>
                </div>
                <div style=\"margin-top:8px; color:#444;\">
                    <span id=\"w_status\">Arraste os sliders para atualizar o mapa</span>
                </div>
            </div>
        """


def get_sliders_template(sliders_html):
    return f"""
        {{% macro html(this, kwargs) %}}
        <div style="
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 260px;
            z-index: 9999;
            font-size: 13px;
            background-color: white;
            border: 2px solid grey;
            border-radius: 6px;
            padding: 10px;
            box-shadow: 3px 3px 5px rgba(0,0,0,0.25);
        ">
            <button type="button" onclick="
                var el = document.getElementById('ahp_panel');
                if (el) el.style.display = (el.style.display === 'none') ? 'block' : 'none';
            " style="
                width: 100%;
                padding: 6px 8px;
                border: 1px solid #777;
                background: #f7f7f7;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
            ">Ajustes AHP</button>
            <div id="ahp_panel" style="margin-top:8px; display:none;">
                {sliders_html}
            </div>
        </div>
        {{% endmacro %}}
        """


def get_sliders_script(cidade, overlay_name, w_uso0, w_decl0, w_flux0, w_hipso0):
    return f"""
            {{% macro script(this, kwargs) %}}

            var map = {{{{this._parent.get_name()}}}};

            map.whenReady(function () {{

                function initSliders() {{
                    ["w_uso", "w_decl", "w_flux", "w_hipso"].forEach(id => {{
                        const el = document.getElementById(id);

                        if (el) {{
                            el.addEventListener("input", onSliderChange);
                        }} else {{
                            console.warn("Slider não encontrado:", id);
                        }}
                    }});

                    console.log("Sliders conectados!");
                }}

                function atualizarMapa() {{
                    const status = document.getElementById("w_status");
                    status.innerText = "Atualizando...";

                    const params = new URLSearchParams({{
                        cidade: "{cidade}",
                        w_uso: document.getElementById("w_uso").value,
                        w_decl: document.getElementById("w_decl").value,
                        w_flux: document.getElementById("w_flux").value,
                        w_hipso: document.getElementById("w_hipso").value
                    }});

                    fetch(`/overlay_risco?${{params}}`)
                        .then(res => res.json())
                        .then(data => {{
                            if (data.status === "ok") {{

                                console.log("Atualizando overlay...");

                                {overlay_name}.setUrl(data.url);

                            }} else {{
                                showAlert(data.mensagem);
                            }}

                            status.innerText = "Arraste os sliders para atualizar o mapa";
                        }})
                        .catch(err => {{
                            console.error(err);
                            status.innerText = "Erro ao atualizar";
                        }});
                }}

                let timeout = null;

                function onSliderChange() {{
                    console.log("Slider mudou!");

                    document.getElementById("w_uso_val").innerText = document.getElementById("w_uso").value;
                    document.getElementById("w_decl_val").innerText = document.getElementById("w_decl").value;
                    document.getElementById("w_flux_val").innerText = document.getElementById("w_flux").value;
                    document.getElementById("w_hipso_val").innerText = document.getElementById("w_hipso").value;

                    clearTimeout(timeout);

                    timeout = setTimeout(() => {{
                        atualizarMapa();
                    }}, 400);
                }}

                function resetSliders() {{
                    document.getElementById("w_uso").value = {w_uso0:.6f};
                    document.getElementById("w_decl").value = {w_decl0:.6f};
                    document.getElementById("w_flux").value = {w_flux0:.6f};
                    document.getElementById("w_hipso").value = {w_hipso0:.6f};

                    document.getElementById("w_uso_val").innerText = {w_uso0:.6f};
                    document.getElementById("w_decl_val").innerText = {w_decl0:.6f};
                    document.getElementById("w_flux_val").innerText = {w_flux0:.6f};
                    document.getElementById("w_hipso_val").innerText = {w_hipso0:.6f};

                    atualizarMapa();
                }}

                function initResetButton() {{
                    const resetBtn = document.getElementById("w_reset_btn");

                    if (resetBtn) {{
                        resetBtn.addEventListener("click", resetSliders);
                    }} else {{
                        console.warn("Botão reset não encontrado");
                    }}
                }}

                setTimeout(() => {{
                    initSliders();
                    initResetButton();
                }}, 300);

            }});

            {{% endmacro %}}
            """
