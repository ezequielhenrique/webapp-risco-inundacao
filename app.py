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

import numpy as np

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import base64
import io
from pathlib import Path

import matplotlib.cm as cm
from PIL import Image


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


def risk_overlay_png_data_url(slug: str, w: np.ndarray) -> str:
    """Gera um PNG RGBA (base64) do risco recalculado com pesos w (4 elementos, soma=1)."""

    # Referência: raster de risco recortado (define o footprint/bounds do overlay no front)
    risco_ref = Path(f"outputs/mapas_de_risco/risco_alagamento_{slug}_recortado.tif")
    if not risco_ref.exists():
        raise FileNotFoundError(
            "Raster de risco recortado não encontrado. Execute a análise da cidade primeiro: "
            + str(risco_ref)
        )

    uso_reclass = Path(f"outputs/uso_do_solo/uso_do_solo_{slug}_reclass.tif")
    decl_reclass = Path(f"outputs/declividade/declividade_{slug}_reclass.tif")
    fluxo_reclass = Path(f"outputs/fluxo_acumulado/fluxo_acumulado_{slug}_reclass.tif")
    hipso_reclass = Path(f"outputs/hipsometria/hipsometria_{slug}_reclass.tif")

    missing = [p.name for p in [uso_reclass, decl_reclass, fluxo_reclass, hipso_reclass] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Arquivos reclassificados ausentes (execute a análise da cidade primeiro): " + ", ".join(missing)
        )

    # Determinar tipo de visualização a partir da config
    config = load_config() or {}
    tipo_risco = ((config.get("visualizacao") or {}).get("tipo_risco") or "continuo").lower()
    usar_classes_4 = tipo_risco == "classes_4"

    # 1) Recalcular risco no mesmo grid dos rasters reclassificados
    with rasterio.open(uso_reclass) as s0, rasterio.open(decl_reclass) as s1, rasterio.open(fluxo_reclass) as s2, rasterio.open(hipso_reclass) as s3:
        uso = s0.read(1).astype(np.float32)
        decl = s1.read(1).astype(np.float32)
        fluxo = s2.read(1).astype(np.float32)
        hipso = s3.read(1).astype(np.float32)

        if not (uso.shape == decl.shape == fluxo.shape == hipso.shape):
            raise ValueError("Rasters reclassificados com dimensões diferentes")

        src_crs = s0.crs
        src_transform = s0.transform
        src_profile = s0.profile

    mask_valid = (
        np.isfinite(uso) &
        np.isfinite(decl) &
        np.isfinite(fluxo) &
        np.isfinite(hipso)
    )
    risk_full = (w[0] * uso) + (w[1] * decl) + (w[2] * fluxo) + (w[3] * hipso)
    risk_full = risk_full.astype(np.float32, copy=False)

    # Evitar NaN durante reprojeções (NaN + nearest tende a “espalhar” transparência perto de bordas/água)
    nodata = -9999.0
    risk_full[~mask_valid] = nodata

    # 2) Reamostrar para a grade do raster recortado (garante alinhamento/bounds idênticos ao overlay do Folium)
    with rasterio.open(risco_ref) as ref:
        ref_arr = ref.read(1).astype(np.float32)
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_bounds = ref.bounds
        ref_w = ref.width
        ref_h = ref.height
        ref_nodata = ref.nodata if (ref.nodata is not None and np.isfinite(ref.nodata)) else nodata

    risk_ref = np.full((ref_h, ref_w), nodata, dtype=np.float32)
    reproject(
        source=risk_full,
        destination=risk_ref,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=ref_transform,
        dst_crs=ref_crs,
        resampling=Resampling.nearest,
        src_nodata=nodata,
        dst_nodata=nodata,
    )

    # Aplicar exatamente a mesma máscara do raster recortado (áreas fora do município ficam transparentes)
    ref_mask = (ref_arr == ref_nodata) | (~np.isfinite(ref_arr))
    risk_ref[ref_mask] = nodata

    # 3) Reprojetar para EPSG:4326 usando bounds/dimensões do recortado (para casar com Leaflet/Folium)
    dst_crs = "EPSG:4326"
    transform4326, width4326, height4326 = calculate_default_transform(
        ref_crs, dst_crs, ref_w, ref_h, ref_bounds.left, ref_bounds.bottom, ref_bounds.right, ref_bounds.top
    )

    dst = np.full((height4326, width4326), nodata, dtype=np.float32)
    reproject(
        source=risk_ref,
        destination=dst,
        src_transform=ref_transform,
        src_crs=ref_crs,
        dst_transform=transform4326,
        dst_crs=dst_crs,
        resampling=Resampling.nearest,
        src_nodata=nodata,
        dst_nodata=nodata,
    )

    # Reprojetar a máscara também
    mask_4326 = np.zeros((height4326, width4326), dtype=np.uint8)

    reproject(
        source=ref_mask.astype(np.uint8),
        destination=mask_4326,
        src_transform=ref_transform,
        src_crs=ref_crs,
        dst_transform=transform4326,
        dst_crs=dst_crs,
        resampling=Resampling.nearest
    )

    # Aplicar máscara final
    dst[mask_4326 == 1] = nodata

    dst = dst.astype(np.float32, copy=False)
    dst = np.where(dst == nodata, np.nan, dst)

    # 4) Aplicar MESMA lógica de cores do overlay inicial (normalização pelo min/max)
    valid = np.isfinite(dst)
    if not valid.any():
        # Sem dados válidos: devolve imagem transparente
        img = np.zeros((dst.shape[0], dst.shape[1], 4), dtype=np.uint8)
    else:
        # Escala fixa: usa vmin/vmax do TIFF inicial recortado (para não "mudar" a paleta a cada ajuste)
        vmin, vmax = get_city_color_scale(slug)
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax == vmin:
            norm_data = np.zeros_like(dst, dtype=np.float32)
        else:
            if usar_classes_4:
                # Reclassificar em 4 classes discretas baseadas nos percentis do intervalo [vmin, vmax]
                intervalo = (vmax - vmin) / 4.0
                norm_data = np.zeros_like(dst, dtype=np.float32)
                
                # Classe 1: vmin a vmin + 1*intervalo → valor 0.125 (verde-escuro)
                # Classe 2: vmin + 1*intervalo a vmin + 2*intervalo → valor 0.375 (amarelo)
                # Classe 3: vmin + 2*intervalo a vmin + 3*intervalo → valor 0.625 (laranja)
                # Classe 4: vmin + 3*intervalo a vmax → valor 0.875 (vermelho)
                
                mask1 = valid & (dst >= vmin) & (dst < vmin + intervalo)
                mask2 = valid & (dst >= vmin + intervalo) & (dst < vmin + 2*intervalo)
                mask3 = valid & (dst >= vmin + 2*intervalo) & (dst < vmin + 3*intervalo)
                mask4 = valid & (dst >= vmin + 3*intervalo)
                
                norm_data[mask1] = 0.125  # Classe 1 (menor risco)
                norm_data[mask2] = 0.375  # Classe 2
                norm_data[mask3] = 0.625  # Classe 3
                norm_data[mask4] = 0.875  # Classe 4 (maior risco)
            else:
                # Modo contínuo: normalização linear
                norm_data = (dst - vmin) / (vmax - vmin)
                norm_data = np.clip(norm_data, 0.0, 1.0)

        rgba = cm.get_cmap("RdYlGn_r")(norm_data)
        # Alpha total deve ser controlado pelo `opacity` do Leaflet (ImageOverlay).
        # Se colocarmos 0.6 aqui e o layer já estiver em 0.6, a cor fica "lavada"/marrom.
        rgba[..., 3] = np.where(valid, 1.0, 0.0)
        img = (rgba * 255).astype(np.uint8)

    # Downsample simples para deixar as respostas leves
    h, wpx = img.shape[:2]
    max_size = 1200
    if max(h, wpx) > max_size:
        step = int(np.ceil(max(h, wpx) / max_size))
        img = img[::step, ::step, :]

    pil = Image.fromarray(img, mode="RGBA")
    buf = io.BytesIO()
    pil.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


_CITY_COLOR_SCALE: dict[str, tuple[float, float]] = {}


def get_city_color_scale(slug: str) -> tuple[float, float]:
    """Retorna (vmin, vmax) para normalização das cores, baseado no TIFF inicial recortado."""

    if slug in _CITY_COLOR_SCALE:
        return _CITY_COLOR_SCALE[slug]

    risco_recortado = Path(f"outputs/mapas_de_risco/risco_alagamento_{slug}_recortado.tif")
    if not risco_recortado.exists():
        raise FileNotFoundError(
            "Raster de risco recortado não encontrado para definir a escala de cores. "
            "Execute a análise primeiro."
        )

    with rasterio.open(risco_recortado) as src:
        data = src.read(1)
        nodata = src.nodata

    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)

    data = data.astype(np.float32, copy=False)
    finite = np.isfinite(data)
    if not finite.any():
        vmin, vmax = 0.0, 1.0
    else:
        vmin = float(np.nanmin(data))
        vmax = float(np.nanmax(data))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax == vmin:
            vmin, vmax = 0.0, 1.0

    _CITY_COLOR_SCALE[slug] = (vmin, vmax)
    return vmin, vmax


@app.route("/sobre", methods=["GET"])
def sobre():
    return render_template('sobre.html')
