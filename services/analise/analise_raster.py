from services.analise.analise_base import AnaliseBase

from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
import geopandas as gpd
import numpy as np

import rasterio


class AnaliseRaster(AnaliseBase):

    def executar(self):
        self._criar_moldura_municipio()
        self._processar_mde()
    
    def _criar_moldura_municipio(self):
        shp = gpd.read_file(f"outputs/limites_municipios/limite_{self.cidade}_reprojetado.shp")

        xmin, ymin, xmax, ymax = shp.total_bounds

        # Adicionar padding
        padding = 1000  # 1000m
        xmin_pad, ymin_pad = xmin - padding, ymin - padding
        xmax_pad, ymax_pad = xmax + padding, ymax + padding

        res = 30

        width = int((xmax_pad - xmin_pad) / res)
        height = int((ymax_pad - ymin_pad) / res)

        transform_raster = from_origin(xmin_pad, ymax_pad, res, res)

        base_raster = np.zeros((height, width), dtype=np.uint8)

        out_path = f"outputs/molduras_municipios/moldura-{self.cidade}.tif"
        profile = {
            "driver": "GTiff",
            "dtype": "uint8",
            "count": 1,
            "width": width,
            "height": height,
            "crs": shp.crs,
            "transform": transform_raster
        }

        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(base_raster, 1)
    
    def _processar_mde(self):
        mde_path = "dados/mde_pernambuco.tif"
        moldura_path = f"outputs/molduras_municipios/moldura-{self.cidade}.tif"
        output_path = f"outputs/mde/mde_{self.cidade}.tif"

        # Pegar limites e dados do raster da moldura
        with rasterio.open(moldura_path) as moldura:
            moldura_transform = moldura.transform
            moldura_width = moldura.width
            moldura_height = moldura.height
            moldura_crs = moldura.crs
            moldura_profile = moldura.profile

        # Reprojetar e alinhar o MDE à moldura
        with rasterio.open(mde_path) as src:
            profile = src.meta.copy()
            profile.update({
                "crs": moldura_crs,
                "transform": moldura_transform,
                "width": moldura_width,
                "height": moldura_height
            })

            with rasterio.open(output_path, "w", **profile) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=moldura_transform,
                        dst_crs=moldura_crs,
                        resampling=Resampling.bilinear
                    )
