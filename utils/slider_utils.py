from utils.utils import load_config

from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio
from pathlib import Path
import matplotlib.cm as cm
from PIL import Image
import numpy as np
import base64
import io


_CITY_COLOR_SCALE: dict[str, tuple[float, float]] = {}


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
        vmin, vmax = get_raster_color_scale(slug)
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


def get_raster_color_scale(slug: str) -> tuple[float, float]:
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
