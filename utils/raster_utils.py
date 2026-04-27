import numpy as np
import geopandas as gpd
from rasterio.mask import mask
import rasterio
from rasterio.warp import transform
from pathlib import Path


def reclassificar_raster(input_path, output_path, classes, is_categorical=False):
    with rasterio.open(input_path) as src:
        data = src.read(1)
        profile = src.profile

    out = np.zeros_like(data, dtype=np.uint8)

    if is_categorical:
        for _, cls in classes.items():
            for val in cls["ids"]:
                out[data == val] = cls["valor"]
    else:
        for cls in classes:
            min_val = cls["min"] if cls["min"] else -np.inf
            max_val = cls["max"] if cls["max"] else np.inf
            out[(data >= min_val) & (data <= max_val)] = cls["valor"]

    profile.update(dtype=rasterio.uint8, count=1, nodata=0)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(out, 1)


def recortar_raster(shapefile_path, input_path, output_path):
    gdf = gpd.read_file(shapefile_path)
    geometries = gdf.geometry.values

    with rasterio.open(input_path) as src:
        dtype = src.dtypes[0]

        # Escolher valor de NoData dependendo do tipo do raster
        if np.issubdtype(dtype, np.integer):
            nodata = 0
        else:
            nodata = -9999.0

        # Aplicar máscara e recorte
        out_image, out_transform = mask(
            src, geometries, crop=True, filled=True, nodata=nodata
        )

        if np.issubdtype(dtype, np.floating):
            out_image = out_image.astype("float32")

        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "dtype": out_image.dtype,
            "nodata": nodata
        })

    with rasterio.open(output_path, "w", **out_meta) as dst:
        dst.write(out_image)


def sample_raster(path, lon, lat):
        with rasterio.open(path) as src:
            xs, ys = transform("EPSG:4326", src.crs, [lon], [lat])

            nodata = src.nodata

            for val in src.sample([(xs[0], ys[0])]):
                v = float(val[0])

                if nodata is not None and v == nodata:
                    return None

                return v
