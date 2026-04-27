import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
import folium


class RasterLayer:
    def __init__(self, raster_path, colormap="RdYlGn_r", name="Raster", tipo="continuo", num_classes=4):
        self.raster_path = raster_path
        self.colormap = colormap
        self.name = name
        self.tipo = tipo.lower()
        self.num_classes = num_classes

    def process(self):
        with rasterio.open(self.raster_path) as src:
            nodata = src.nodata if src.nodata is not None else 0

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )

            data_reproj = np.empty((height, width), dtype=src.meta['dtype'])

            reproject(
                source=rasterio.band(src, 1),
                destination=data_reproj,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                resampling=Resampling.nearest
            )

            data = np.ma.masked_equal(data_reproj, nodata)
            bounds = rasterio.transform.array_bounds(height, width, transform)

        # NORMALIZAÇÃO / CLASSIFICAÇÃO

        vmin = data.min()
        vmax = data.max()

        if self.tipo == "classes":
            if vmin < vmax:
                intervalo = (vmax - vmin) / float(self.num_classes)
                norm_data = np.zeros_like(data, dtype=np.float32)

                for i in range(self.num_classes):
                    lower = vmin + i * intervalo
                    upper = vmin + (i + 1) * intervalo if i < self.num_classes - 1 else vmax

                    if i < self.num_classes - 1:
                        mask = (data >= lower) & (data < upper)
                    else:
                        mask = (data >= lower)

                    # valor central da classe
                    norm_value = (i + 0.5) / self.num_classes
                    norm_data[mask] = norm_value
            else:
                norm_data = np.zeros_like(data, dtype=np.float32)

        else:
            # contínuo
            norm_data = (data - vmin) / (vmax - vmin)

        # COLORIZAÇÃO

        cmap = plt.get_cmap(self.colormap)
        rgba = (cmap(norm_data) * 255).astype(np.uint8)

        bounds_folium = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]

        return rgba, bounds_folium

    def get(self):
        rgba, bounds = self.process()

        return folium.raster_layers.ImageOverlay(
            image=rgba,
            bounds=bounds,
            name=self.name,
            opacity=0.6
        )
