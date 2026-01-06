from flask import Flask, render_template, request, redirect, url_for, jsonify
from pathlib import Path
from typing import Any
import base64
import io

import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform as rio_transform
from rasterio.warp import calculate_default_transform, reproject, Resampling

import matplotlib.cm as cm
from PIL import Image
from services.municipio_service import MunicipioService
from services.analise_service import AnaliseService
from utils.utils import load_config, save_config


_CITY_COLOR_SCALE: dict[str, tuple[float, float]] = {}


def _get_city_color_scale(slug: str) -> tuple[float, float]:
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


app = Flask(__name__)
municipios = MunicipioService("dados/PE_Municipios_2023/PE_Municipios_2023.shp")


def _slug_cidade(nome: str) -> str:
    return nome.strip().lower().replace(" ", "-")


def _uso_do_solo_label(uso_id: int | None, config: dict[str, Any]) -> str | None:
    if uso_id is None:
        return None
    classes = ((config.get("criterios") or {}).get("uso_do_solo") or {}).get("classes")
    if not isinstance(classes, dict):
        return None
    for nome_classe, info in classes.items():
        ids = (info or {}).get("ids")
        if isinstance(ids, list) and uso_id in ids:
            return str(nome_classe)
    return None


def _sample_raster_epsg4326(path: Path, lon: float, lat: float) -> float | int | None:
    with rasterio.open(path) as src:
        if src.crs is None:
            raise RuntimeError(f"Raster sem CRS: {path}")

        if str(src.crs).upper() != "EPSG:4326":
            xs, ys = rio_transform("EPSG:4326", src.crs, [lon], [lat])
            x, y = xs[0], ys[0]
        else:
            x, y = lon, lat

        val = next(src.sample([(x, y)]))[0]
        nodata = src.nodata

        if nodata is not None:
            try:
                if float(val) == float(nodata):
                    return None
            except Exception:
                pass

        try:
            if np.isnan(val):
                return None
        except Exception:
            pass

        return val


def _try_parse_weights(args) -> np.ndarray | None:
    w_uso = args.get("w_uso", type=float)
    w_decl = args.get("w_decl", type=float)
    w_flux = args.get("w_flux", type=float)
    w_hipso = args.get("w_hipso", type=float)
    if w_uso is None and w_decl is None and w_flux is None and w_hipso is None:
        return None

    raw = np.array([w_uso, w_decl, w_flux, w_hipso], dtype=float)
    if not np.isfinite(raw).all() or raw.sum() <= 0:
        return None
    return raw / raw.sum()


def _risk_at_point_from_reclass(slug: str, lon: float, lat: float, w: np.ndarray) -> float | None:
    uso_reclass = Path(f"outputs/uso_do_solo/uso_do_solo_{slug}_reclass.tif")
    decl_reclass = Path(f"outputs/declividade/declividade_{slug}_reclass.tif")
    fluxo_reclass = Path(f"outputs/fluxo_acumulado/fluxo_acumulado_{slug}_reclass.tif")
    hipso_reclass = Path(f"outputs/hipsometria/hipsometria_{slug}_reclass.tif")

    if not (uso_reclass.exists() and decl_reclass.exists() and fluxo_reclass.exists() and hipso_reclass.exists()):
        return None

    uso = _sample_raster_epsg4326(uso_reclass, lon=lon, lat=lat)
    decl = _sample_raster_epsg4326(decl_reclass, lon=lon, lat=lat)
    fluxo = _sample_raster_epsg4326(fluxo_reclass, lon=lon, lat=lat)
    hipso = _sample_raster_epsg4326(hipso_reclass, lon=lon, lat=lat)

    vals = [uso, decl, fluxo, hipso]
    if any(v is None for v in vals):
        return None

    vals_f = np.array([float(v) for v in vals], dtype=float)
    # No pipeline, 0 significa NoData/fora da área recortada
    if np.any(vals_f <= 0):
        return None

    return float(np.dot(w, vals_f))


def _risk_overlay_png_data_url(slug: str, w: np.ndarray) -> str:
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

    mask_valid = (uso > 0) & (decl > 0) & (fluxo > 0) & (hipso > 0)
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
        resampling=Resampling.bilinear,
        src_nodata=nodata,
        dst_nodata=nodata,
    )

    dst = dst.astype(np.float32, copy=False)
    dst[dst == nodata] = np.nan

    # 4) Aplicar MESMA lógica de cores do overlay inicial (normalização pelo min/max)
    valid = np.isfinite(dst)
    if not valid.any():
        # Sem dados válidos: devolve imagem transparente
        img = np.zeros((dst.shape[0], dst.shape[1], 4), dtype=np.uint8)
    else:
        # Escala fixa: usa vmin/vmax do TIFF inicial recortado (para não "mudar" a paleta a cada ajuste)
        vmin, vmax = _get_city_color_scale(slug)
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax == vmin:
            norm_data = np.zeros_like(dst, dtype=np.float32)
        else:
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


@app.route("/", methods=["GET"])
def index():
    config = load_config() or {}
    lista_cidades = municipios.get_nome_cidades()

    def _get_mde_estadual_path(cfg: dict):
        mde_cfg = (cfg.get("dados") or {}).get("mde")
        candidates: list[Path] = []
        if isinstance(mde_cfg, dict) and mde_cfg.get("estado"):
            candidates.append(Path(str(mde_cfg["estado"])))
        candidates.extend(
            [
                Path("dados/mde_pernambuco_srtm.tif"),
                Path("dados/mde_pernambuco.tif"),
            ]
        )
        for p in candidates:
            if p.exists():
                return p
        return None

    ui_cfg = config.get("ui") if isinstance(config.get("ui"), dict) else {}
    mostrar_ajustar_parametros = bool((ui_cfg or {}).get("mostrar_ajustar_parametros", False))

    # Opcional: limitar a lista de cidades enquanto o MDE estadual não está disponível
    cidades_suportadas = config.get("cidades_suportadas")
    mde_estadual_existe = _get_mde_estadual_path(config) is not None
    if (not mde_estadual_existe) and isinstance(cidades_suportadas, list) and cidades_suportadas:
        permitidas = set(cidades_suportadas)
        lista_cidades = [c for c in lista_cidades if c in permitidas]

    mapa_html = municipios.gerar_mapa_base()
    return render_template(
        "index.html",
        cidade=None,
        lista_cidades=lista_cidades,
        mapa_html=mapa_html,
        mostrar_ajustar_parametros=mostrar_ajustar_parametros,
    )


@app.route("/executar_analise", methods=["POST"])
def executar_analise():
    payload = request.get_json(silent=True) or {}
    cidade = payload.get("cidade")

    if not cidade:
        return jsonify({"status": "erro", "mensagem": "Nenhuma cidade informada"}), 400

    config = load_config() or {}

    # Se não houver MDE estadual, impede cidades fora da allowlist (quando definida)
    cidades_suportadas = config.get("cidades_suportadas")
    mde_cfg = (config.get("dados") or {}).get("mde")
    mde_estadual_candidates: list[Path] = []
    if isinstance(mde_cfg, dict) and mde_cfg.get("estado"):
        mde_estadual_candidates.append(Path(str(mde_cfg["estado"])))
    mde_estadual_candidates.extend(
        [
            Path("dados/mde_pernambuco_srtm.tif"),
            Path("dados/mde_pernambuco.tif"),
        ]
    )
    mde_estadual_existe = any(p.exists() for p in mde_estadual_candidates)
    if (
        isinstance(cidades_suportadas, list)
        and cidades_suportadas
        and (cidade not in cidades_suportadas)
        and not mde_estadual_existe
    ):
        return (
            jsonify(
                {
                    "status": "erro",
                    "mensagem": (
                        f"Cidade '{cidade}' não está habilitada neste modo de teste. "
                        "Habilite-a em static/config/config.json (cidades_suportadas) "
                        "ou adicione o MDE estadual em dados/mde_pernambuco_srtm.tif (ou ajuste dados.mde.estado)."
                    ),
                }
            ),
            400,
        )

    try:
        analise_multicriterio = AnaliseService()
        raster_risco_path = analise_multicriterio.executar(cidade, municipios.get_gdf_municipio(cidade))

        mapa_html = municipios.gerar_mapa_municipio(cidade, raster_risco_path)

        return jsonify({"status": "ok", "mapa_html": mapa_html})
    
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/valor_ponto", methods=["GET"])
def valor_ponto():
    """Retorna risco e uso do solo no ponto clicado (lat/lon em EPSG:4326)."""

    cidade = request.args.get("cidade", type=str)
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)

    if not cidade or lat is None or lon is None:
        return (
            jsonify({"status": "erro", "mensagem": "Parâmetros obrigatórios: cidade, lat, lon"}),
            400,
        )

    slug = _slug_cidade(cidade)
    config = load_config() or {}

    w = _try_parse_weights(request.args)

    risco_path = Path(f"outputs/mapas_de_risco/risco_alagamento_{slug}_recortado.tif")
    uso_path = Path(f"outputs/uso_do_solo/uso_do_solo_{slug}.tif")

    if not risco_path.exists():
        return (
            jsonify({"status": "erro", "mensagem": "Raster de risco não encontrado. Execute a análise primeiro."}),
            404,
        )
    if not uso_path.exists():
        return (
            jsonify({"status": "erro", "mensagem": "Raster de uso do solo não encontrado. Execute a análise primeiro."}),
            404,
        )

    try:
        # Se houver pesos, calcula risco dinamicamente (consistente com o overlay)
        risco_val = None
        if w is not None:
            risco_val = _risk_at_point_from_reclass(slug, lon=lon, lat=lat, w=w)

        # Fallback para o TIFF estático
        if risco_val is None:
            risco_val = _sample_raster_epsg4326(risco_path, lon=lon, lat=lat)

        uso_val = _sample_raster_epsg4326(uso_path, lon=lon, lat=lat)

        risco_out = None if risco_val is None else float(risco_val)
        uso_id = None if uso_val is None else int(uso_val)
        uso_label = _uso_do_solo_label(uso_id, config)

        return jsonify(
            {
                "status": "ok",
                "cidade": cidade,
                "lat": lat,
                "lon": lon,
                "risco": risco_out,
                "w": None if w is None else w.tolist(),
                "uso_id": uso_id,
                "uso_classe": uso_label,
            }
        )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


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
        slug = _slug_cidade(cidade)
        url = _risk_overlay_png_data_url(slug, w)
        return jsonify({"status": "ok", "url": url, "w": w.tolist()})
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


@app.route("/sobre", methods=["GET"])
def sobre():
    return render_template('sobre.html')
