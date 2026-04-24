from services.analise.analise_base import AnaliseBase
import rasterio
import numpy as np


class AnaliseDeclividade(AnaliseBase):

    def executar(self):
        path_mde = f"outputs/mde/mde_{self.cidade}.tif"
        output = f"outputs/declividade/declividade_{self.cidade}.tif"

        with rasterio.open(path_mde) as src:
            mde = src.read(1, masked=True)
            transform = src.transform
            profile = src.profile

        xres = transform.a
        yres = -transform.e

        gy, gx = np.gradient(mde, yres, xres)

        slope = np.arctan(np.sqrt(gx**2 + gy**2))
        slope_degrees = np.degrees(slope)

        profile.update(dtype=rasterio.float32, count=1)

        with rasterio.open(output, "w", **profile) as dst:
            dst.write(slope_degrees.astype(rasterio.float32), 1)

        return output
