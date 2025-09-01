from flask import Flask, render_template, request, redirect, url_for, jsonify
from services.municipio_service import MunicipioService
from services.analise_service import AnaliseService
from utils.utils import load_config, save_config


app = Flask(__name__)
municipios = MunicipioService("dados/PE_Municipios_2023/PE_Municipios_2023.shp")


@app.route("/", methods=["GET"])
def index():
    lista_cidades = municipios.get_nome_cidades()
    mapa_html = municipios.gerar_mapa_base()
    return render_template("index.html", cidade=None, lista_cidades=lista_cidades, mapa_html=mapa_html)


@app.route("/executar_analise", methods=["POST"])
def executar_analise():
    payload = request.get_json(silent=True) or {}
    cidade = payload.get("cidade")

    if not cidade:
        return jsonify({"status": "erro", "mensagem": "Nenhuma cidade informada"}), 400

    try:
        analise_multicriterio = AnaliseService()
        raster_risco_path = analise_multicriterio.executar(cidade, municipios.get_gdf_municipio(cidade))

        mapa_html = municipios.gerar_mapa_municipio(cidade, raster_risco_path)
        
        return jsonify({"status": "ok", "mapa_html": mapa_html})
    
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
