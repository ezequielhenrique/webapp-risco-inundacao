from flask import Flask, render_template, request, jsonify

from services.municipio_service import MunicipioService
from services.analise_service import AnaliseService

from services.mapa.layers.raster_layer import RasterLayer
from services.mapa.layers.uso_solo_layer import UsoSoloLayer

from utils.utils import slug_cidade
from utils.uso_solo_classes import USO_SOLO_CLASSES
from utils.raster_utils import sample_raster
from utils.slider_utils import risk_overlay_png_data_url

import numpy as np


app = Flask(__name__)
municipios = MunicipioService("dados/PE_Municipios_2023/PE_Municipios_2023.shp")


@app.route("/", methods=["GET"])
def index():
    lista_cidades = municipios.get_nome_cidades()

    return render_template(
        "index.html", 
        cidade=None, 
        lista_cidades=lista_cidades, 
    )


@app.route("/executar_analise", methods=["POST"])
def executar_analise():
    payload = request.get_json(silent=True) or {}
    cidade = payload.get("cidade")
    config = payload.get("config")

    if not cidade:
        return jsonify({"status": "erro", "mensagem": "Nenhuma cidade informada"}), 400

    try:
        gdf = municipios.get_gdf(cidade)

        analise = AnaliseService()
        resultado = analise.executar(cidade, gdf, config=config)

        raster_path = resultado["risco_path"]
        config = resultado["config"]

        centro = gdf.geometry.centroid.iloc[0]

        uso_layer = UsoSoloLayer(
                raster_path=f"outputs/uso_do_solo/uso_do_solo_{slug_cidade(cidade)}_recortado.tif",
                legenda=USO_SOLO_CLASSES
            )

        raster_layer = RasterLayer(
                raster_path,
                colormap='RdYlGn_r',
                name='Risco de Alagamento',
                tipo='classes',
                num_classes=4
            )

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

        return jsonify({
            "status": "ok", 
            "cidade": cidade,
            "centro": [centro.y, centro.x],
            "config": config,
            "overlay_url": raster_layer.get_image_url(),
            "bounds": raster_layer.get_bounds(),
            "uso_url": uso_layer.get_image_url(),
            "uso_bounds": uso_layer.get_bounds()
        })
    
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


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
        return jsonify({
            "status": "erro", 
            "mensagem": str(e)
        }), 500


@app.route("/sobre", methods=["GET"])
def sobre():
    return render_template('sobre.html')
