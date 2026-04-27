from flask import Flask, render_template, request, redirect, url_for, jsonify

from services.municipio_service import MunicipioService
from services.mapa.mapa_service import MapaService
from services.analise_service import AnaliseService

from services.mapa.layers.municipio_layer import MunicipioLayer
from services.mapa.layers.raster_layer import RasterLayer
from services.mapa.layers.pontos_alagamento_layer import PontosAlagamentoLayer
from services.mapa.layers.uso_solo_layer import UsoSoloLayer
from services.ahp_service import AHPService

from utils.utils import load_config, save_config, slug_cidade
from utils.uso_solo_classes import USO_SOLO_CLASSES
from utils.raster_utils import sample_raster
from utils.slider_utils import risk_overlay_png_data_url

import numpy as np


app = Flask(__name__)
municipios = MunicipioService("dados/PE_Municipios_2023/PE_Municipios_2023.shp")


@app.route("/", methods=["GET"])
def index():
    lista_cidades = municipios.get_nome_cidades()

    mapa = MapaService(center=[-8.38, -37.86])
    mapa.add_base_layer()
    mapa.add_layer_control()

    return render_template(
        "index.html", 
        cidade=None, 
        lista_cidades=lista_cidades, 
        mapa_html=mapa.render()
    )


@app.route("/executar_analise", methods=["POST"])
def executar_analise():
    payload = request.get_json(silent=True) or {}
    cidade = payload.get("cidade")
    pesos = payload.get("pesos")

    if not cidade:
        return jsonify({"status": "erro", "mensagem": "Nenhuma cidade informada"}), 400

    try:
        gdf = municipios.get_gdf(cidade)

        analise = AnaliseService()
        raster_path = analise.executar(cidade, gdf, pesos=pesos)

        centro = gdf.geometry.centroid.iloc[0]

        mapa_service = MapaService(center=[centro.y, centro.x], cidade=cidade)

        mapa_service.add_base_layer()

        mapa_service.add_layer(MunicipioLayer(gdf).get())

        mapa_service.add_layer(
            UsoSoloLayer(
                raster_path=f"outputs/uso_do_solo/uso_do_solo_{slug_cidade(cidade)}_recortado.tif",
                legenda=USO_SOLO_CLASSES
            ).get()
        )

        raster_layer = RasterLayer(
                raster_path,
                colormap='RdYlGn_r',
                name='Risco de Alagamento',
                tipo='classes',
                num_classes=4
            )
        
        overlay = raster_layer.get()
        mapa_service.add_layer(overlay)

        overlay_name = overlay.get_name()

        if not pesos:
            ahp = AHPService()
            pesos, cr = ahp.calcular_pesos()

        mapa_service.add_ahp_sliders(pesos, slug_cidade(cidade), overlay_name)

        pontos = [
            ("Rua Imperial, bairro de São José", -8.07581, -34.89415),
            ("Rua Nicolau Pereira", -8.07804, -34.90558),
            ("Av. Eng. Abdias de Carvalho", -8.06123, -34.92227),
            ("Av. Dois Rios", -8.11289, -34.93864),
            ("Av. Mal Mascarenhas de Moraes", -8.11383, -34.91281),
            ("Av. Recife próximo ao cruzamento com a Rua João Cabral de Melo Neto", -8.07953, -34.93374),
            ("Av. Abdias de Carvalho, no cruzamento com a rua Delmiro Gouveia", -8.06252, -34.93219),
            ("Av. Norte Miguel Arraes de Alencar, ao lado do Senai", -8.04713, -34.87757)
        ]

        mapa_service.add_layer(PontosAlagamentoLayer(pontos).get())

        mapa_service.add_default_plugins()
        mapa_service.add_layer_control()
        mapa_service.add_legend()
        mapa_service.add_click_popup()

        return jsonify({"status": "ok", "mapa_html": mapa_service.render()})
    
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/config", methods=["POST"])
def config():
    config = load_config()

    # Atualizar pesos AHP
    config["pesos"] = {}
    for key, value in request.form.items():
        if key.startswith("pesos[") and key.endswith("]"):
            nome = key[6:-1]  # remove "pesos[" e "]"
            config["pesos"][nome] = float(value)

    # Atualizar classes intervalares
    for criterio in config["criterios"]:
        if isinstance(config["criterios"][criterio]["classes"], list):
            nova_classes = []
            i = 0
            while f"{criterio}[{i}][min]" in request.form:
                min_val = request.form.get(f"{criterio}[{i}][min]", "")
                max_val = request.form.get(f"{criterio}[{i}][max]", "")
                valor = request.form.get(f"{criterio}[{i}][valor]", "")
                nova_classes.append({
                    "min": float(min_val) if min_val else None,
                    "max": float(max_val) if max_val else None,
                    "valor": float(valor) if valor else None
                })
                i += 1
            config["criterios"][criterio]["classes"] = nova_classes

    # Atualizar classes categóricas (uso_do_solo)
    for criterio in config["criterios"]:
        if isinstance(config["criterios"][criterio]["classes"], dict):
            for nomeClasse in config["criterios"][criterio]["classes"]:
                ids = request.form.get(f"{criterio}[{nomeClasse}][ids]", "")
                valor = request.form.get(f"{criterio}[{nomeClasse}][valor]", "")
                config["criterios"][criterio]["classes"][nomeClasse]["ids"] = [int(x.strip()) for x in ids.split(",") if x.strip()]
                config["criterios"][criterio]["classes"][nomeClasse]["valor"] = float(valor) if valor else None

    save_config(config)
    return redirect(url_for("index"))


@app.route("/valor_ponto", methods=["POST"])
def get_pixel_info():
    data = request.get_json()

    cidade = slug_cidade(data['cidade'])
    lat = data['lat']
    lon = data['lon']

    valores = {}

    valores["risco"] = sample_raster(f"outputs/mapas_de_risco/risco_alagamento_{cidade}_recortado.tif", lon, lat)
    valores["uso_solo"] = sample_raster(f"outputs/uso_do_solo/uso_do_solo_{cidade}.tif", lon, lat)
    valores["declividade"] = sample_raster(f"outputs/declividade/declividade_{cidade}.tif", lon, lat)
    valores["elevacao"] = sample_raster(f"outputs/mde/mde_{cidade}.tif", lon, lat)
    valores["fluxo"] = sample_raster(f"outputs/fluxo_acumulado/fluxo_acumulado_{cidade}.tif", lon, lat)

    valores['uso_solo'] = USO_SOLO_CLASSES[valores['uso_solo']][0]

    return jsonify(valores)


@app.route("/overlay_risco", methods=["GET"])
def overlay_risco():
    """Retorna um data-url PNG do overlay de risco recalculado para os pesos informados."""

    cidade = request.args.get("cidade", type=str)
    w_uso = request.args.get("w_uso", type=float)
    w_decl = request.args.get("w_decl", type=float)
    w_flux = request.args.get("w_flux", type=float)
    w_hipso = request.args.get("w_hipso", type=float)

    if not cidade:
        return jsonify({"status": "erro", "mensagem": "Parâmetro obrigatório: cidade"}), 400

    raw = np.array([w_uso, w_decl, w_flux, w_hipso], dtype=float)
    if not np.isfinite(raw).all() or raw.sum() <= 0:
        raw = np.array([1.0, 1.0, 1.0, 1.0], dtype=float)
    w = raw / raw.sum()

    try:
        slug = slug_cidade(cidade)
        url = risk_overlay_png_data_url(slug, w)
        return jsonify({"status": "ok", "url": url, "w": w.tolist()})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/sobre", methods=["GET"])
def sobre():
    return render_template('sobre.html')
