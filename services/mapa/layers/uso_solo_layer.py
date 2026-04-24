import rasterio
import numpy as np
import folium
from rasterio.warp import calculate_default_transform, reproject, Resampling


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

    def get(self):
        rgba, bounds = self.process()

        return folium.raster_layers.ImageOverlay(
            image=rgba,
            bounds=bounds,
            name=self.name,
            opacity=0.7
        )

    def get_legenda_dict(self):
        return {
            class_id: {
                "nome": nome,
                "cor": cor
            }
            for class_id, (nome, cor) in self.legenda.items()
        }
