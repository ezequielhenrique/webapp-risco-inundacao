import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
import folium


class RasterLayer:
    def __init__(self, raster_path, colormap="RdYlGn_r", name="Raster"):
        self.raster_path = raster_path
        self.colormap = colormap
        self.name = name

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

        # Normalização
        norm = (data - data.min()) / (data.max() - data.min())

        cmap = plt.get_cmap(self.colormap)
        rgba = (cmap(norm) * 255).astype(np.uint8)

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
