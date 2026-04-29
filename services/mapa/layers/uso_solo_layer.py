import rasterio
import numpy as np
from rasterio.warp import calculate_default_transform, reproject, Resampling

import base64
from io import BytesIO
from PIL import Image


class UsoSoloLayer:
    def __init__(self, raster_path, legenda, name="Uso do Solo"):
        self.raster_path = raster_path
        self.legenda = legenda
        self.name = name

    def _hex_to_rgba(self, hex_color):
        hex_color = hex_color.lstrip("#")
        
        if len(hex_color) != 6:
            raise ValueError(f"HEX inválido: {hex_color}")

        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        except ValueError:
            raise ValueError(f"HEX inválido: {hex_color}")

    def process(self):
        with rasterio.open(self.raster_path) as src:
            nodata = src.nodata if src.nodata is not None else 0

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )

            data = np.empty((height, width), dtype=src.meta['dtype'])

            reproject(
                source=rasterio.band(src, 1),
                destination=data,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                resampling=Resampling.nearest
            )

            bounds = rasterio.transform.array_bounds(height, width, transform)

        # Criar imagem RGBA
        rgba = np.zeros((height, width, 4), dtype=np.uint8)

        for class_id, (nome, hex_color) in self.legenda.items():
            mask = data == class_id
            rgba[mask] = self._hex_to_rgba(hex_color)

        # Transparência para nodata
        rgba[data == nodata] = (0, 0, 0, 0)

        bounds_folium = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]

        return rgba, bounds_folium

    def get_legenda_dict(self):
        return {
            class_id: {
                "nome": nome,
                "cor": cor
            }
            for class_id, (nome, cor) in self.legenda.items()
        }
    
    def _ensure_processed(self):
        if not hasattr(self, "_cache"):
            rgba, bounds = self.process()
            self._cache = (rgba, bounds)

    def get_bounds(self):
        self._ensure_processed()
        return self._cache[1]

    def get_image_url(self):
        self._ensure_processed()
        rgba = self._cache[0]

        img = Image.fromarray(rgba)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return f"data:image/png;base64,{img_base64}"
