from services.analise.analise_declividade import AnaliseDeclividade
from services.analise.analise_fluxo import AnaliseFluxo
from services.analise.analise_uso_solo import AnaliseUsoSolo
from services.analise.analise_raster import AnaliseRaster
from services.analise.analise_hipsometria import AnaliseHipsometria

from services.ahp_service import AHPService
from services.config_service import ConfigService

from utils.utils import slug_cidade
from utils.raster_utils import recortar_raster

import rasterio


class AnaliseService:
    def __init__(self):
        self.cidade = None
        self.crs = None

    def executar(self, nome_cidade, gdf_municipio, config=None):

        self.cidade = slug_cidade(nome_cidade)

        self._definir_sistema_coordenadas(gdf_municipio)
        shapefile = self._criar_shapefile_municipio(gdf_municipio)

        AnaliseRaster(self.cidade, self.crs).executar()

        if config is None:
            config_service = ConfigService(self.cidade, self.crs)
            config = config_service.gerar_config()

        if config["criterios"]["declividade"]["ativo"]:
            AnaliseDeclividade(
                self.cidade, 
                self.crs
            ).executar(
                classes=config["criterios"]["declividade"]["classes"]
            )

        if config["criterios"]["fluxo_acumulado"]["ativo"]:
            AnaliseFluxo(
                self.cidade, 
                self.crs
            ).executar(
                classes=config["criterios"]["fluxo_acumulado"]["classes"]
            )

        if config["criterios"]["uso_do_solo"]["ativo"]:
            analise_uso = AnaliseUsoSolo(
                self.cidade, 
                self.crs
            ).executar(
                classes=config["criterios"]["uso_do_solo"]["classes"]
            )

            uso_recortado_path = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}_recortado.tif"

            recortar_raster(shapefile, analise_uso, uso_recortado_path)

        if config["criterios"]["hipsometria"]["ativo"]:
            AnaliseHipsometria(
                self.cidade, 
                self.crs
            ).executar(
                classes=config["criterios"]["hipsometria"]["classes"]
            )

        self._gerar_mapa_risco(config["pesos"])

        risco_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}.tif"
        risco_recortado_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}_recortado.tif"

        recortar_raster(shapefile, risco_path, risco_recortado_path)

        return {
            "risco_path": risco_recortado_path,
            "config": config
        }

    def _definir_sistema_coordenadas(self, gdf_municipio):
        zona_24s = "EPSG:31984"     # SIRGAS 2000 / UTM 24S
        zona_25s = "EPSG:31985"     # SIRGAS 2000 / UTM 25S

        centroid = gdf_municipio.geometry.centroid.iloc[0]
        lon = centroid.x

        if lon < -36:
            self.crs = zona_24s
        else:
            self.crs = zona_25s
    
    def _criar_shapefile_municipio(self, gdf_municipio):
        shapefile_path = f"outputs/limites_municipios/limite_{self.cidade}_reprojetado.shp"

        gdf_reproj = gdf_municipio.to_crs(self.crs)
        gdf_reproj.to_file(shapefile_path)

        return shapefile_path

    def _gerar_mapa_risco(self, pesos):
        peso_uso = pesos["uso"]
        peso_declividade = pesos["declividade"]
        peso_fluxo = pesos["fluxo"]
        peso_hipso = pesos["hipsometria"]

        uso_do_solo_reclass = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}_reclass.tif"
        declividade_reclass = f"outputs/declividade/declividade_{self.cidade}_reclass.tif"
        fluxo_acumulado_reclass = f"outputs/fluxo_acumulado/fluxo_acumulado_{self.cidade}_reclass.tif"
        hipso_reclass = f"outputs/hipsometria/hipsometria_{self.cidade}_reclass.tif"
        saida_risco = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}.tif"

        with rasterio.open(uso_do_solo_reclass) as src1, \
            rasterio.open(declividade_reclass) as src2, \
            rasterio.open(fluxo_acumulado_reclass) as src3, \
            rasterio.open(hipso_reclass) as src4:

            uso = src1.read(1).astype(float)
            declividade = src2.read(1).astype(float)
            fluxo = src3.read(1).astype(float)
            hipso = src4.read(1).astype(float)

            perfil = src1.profile

        # Aplicar pesos
        risco = (uso * peso_uso) + (declividade * peso_declividade) + (fluxo * peso_fluxo) + (hipso * peso_hipso)

        perfil.update(dtype=rasterio.float32, count=1)
        with rasterio.open(saida_risco, "w", **perfil) as dst:
            dst.write(risco.astype(rasterio.float32), 1)
