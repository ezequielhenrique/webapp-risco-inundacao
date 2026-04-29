import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
import folium

import base64
from io import BytesIO
from PIL import Image


class RasterLayer:
    def __init__(self, raster_path, colormap="RdYlGn_r", name="Raster", tipo="continuo", num_classes=4, image_data=None, bounds=None):
        self.raster_path = raster_path
        self.colormap = colormap
        self.name = name
        self.tipo = tipo.lower()
        self.num_classes = num_classes

        self.image_data = image_data
        self.custom_bounds = bounds

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

        # normalização (igual você já fez)
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

                    norm_data[mask] = (i + 0.5) / self.num_classes
            else:
                norm_data = np.zeros_like(data, dtype=np.float32)
        else:
            norm_data = (data - vmin) / (vmax - vmin)

        cmap = plt.get_cmap(self.colormap)
        rgba = (cmap(norm_data) * 255).astype(np.uint8)

        bounds_folium = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]

        self.rgba = rgba
        self.bounds = bounds_folium

    def get(self):
        # Caso dinâmico (base64)
        if self.image_data is not None and self.custom_bounds is not None:
            overlay = folium.raster_layers.ImageOverlay(
                image=self.image_data,
                bounds=self.custom_bounds,
                name=self.name,
                opacity=0.6
            )

            overlay.options["id"] = "riscoOverlay"

            self.overlay = overlay
            return overlay

        # Caso normal
        rgba, bounds = self.process()

        overlay = folium.raster_layers.ImageOverlay(
            image=rgba,
            bounds=bounds,
            name=self.name,
            opacity=0.6
        )

        overlay.options = overlay.options if hasattr(overlay, "options") else {}
        overlay.options["id"] = "riscoOverlay"

        self.overlay = overlay
        return overlay
    
    def get_name(self):
        return self.overlay.get_name()
    
    def get_bounds(self):
        if not hasattr(self, "bounds"):
            self.process()
        return self.bounds
    
    def get_image_url(self):
        if not hasattr(self, "rgba"):
            self.process()

        img = Image.fromarray(self.rgba)

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return f"data:image/png;base64,{img_base64}"
