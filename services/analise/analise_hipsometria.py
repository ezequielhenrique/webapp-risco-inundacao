from services.analise.analise_base import AnaliseBase

from utils.paths import path_output
from utils.raster_utils import reclassificar_raster

import rasterio
import numpy as np


class AnaliseHipsometria(AnaliseBase):

    def executar(self, classes):
        mde_path = path_output('mde', self.cidade)

        reclassificar_raster(
                mde_path,
                path_output('hipsometria', self.cidade, '_reclass'),
                classes,
            )
    
    def gerar_classes(self):
        """
        Calcula classes de hipsometria.

        - Recife: usa classes específicas
        - Outras cidades: divide min-max em intervalos iguais

        Returns:
            Lista de classes no formato:
            [{"min": float, "max": float|None, "valor": float}]
        """

        mde_path = path_output('mde', self.cidade)

        if self.cidade == "recife":
            return [
                {"min": 0.0, "max": 3.0, "valor": 4.0},
                {"min": 3.0, "max": 10.0, "valor": 3.0},
                {"min": 10.0, "max": 50.0, "valor": 2.0},
                {"min": 50.0, "max": None, "valor": 1.0},
            ]
        
        # Outras cidades

        with rasterio.open(mde_path) as src:
            data = src.read(1)
            nodata = src.nodata

        valid = np.isfinite(data)
        if nodata is not None and np.isfinite(nodata):
            valid &= data != nodata

        min_alt = float(np.nanmin(data[valid]))
        max_alt = float(np.nanmax(data[valid]))

        if min_alt >= max_alt:
            min_alt = 0.0
            max_alt = 1.0

        n_classes = 4
        intervalo = (max_alt - min_alt) / n_classes

        classes = []

        for i in range(n_classes):
            cls_min = min_alt + (i * intervalo)

            if i < n_classes - 1:
                cls_max = min_alt + ((i + 1) * intervalo)
            else:
                cls_max = None  # última classe aberta

            # menor altitude = maior risco
            valor = float(n_classes - i)

            classes.append({
                "min": cls_min,
                "max": cls_max,
                "valor": valor,
            })

        return classes
