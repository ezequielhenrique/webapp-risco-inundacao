from services.analise.analise_base import AnaliseBase
import rasterio
from rasterio.warp import reproject, Resampling


class AnaliseUsoSolo(AnaliseBase):

    def executar(self):
        uso_src = "dados/uso-do-solo-pernambuco-2023.tif"
        moldura = f"outputs/molduras_municipios/moldura-{self.cidade}.tif"
        output = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}.tif"

        with rasterio.open(moldura) as ref:
            transform = ref.transform
            width = ref.width
            height = ref.height
            crs = ref.crs

        with rasterio.open(uso_src) as src:
            profile = src.meta.copy()
            profile.update({
                "crs": crs,
                "transform": transform,
                "width": width,
                "height": height
            })

            with rasterio.open(output, "w", **profile) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=crs,
                        resampling=Resampling.nearest
                    )

        return output
