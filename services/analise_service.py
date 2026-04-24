from rasterio.warp import calculate_default_transform, reproject, Resampling, transform
from rasterio.transform import from_origin
from rasterio.mask import mask
from rasterio.windows import from_bounds
from rasterio.plot import show
import geopandas as gpd
import numpy as np
import rasterio
from utils.utils import load_config
from utils.fluxo_acumulado import realizar_analise_de_fluxo


class AnaliseService:
    def __init__(self):
        self.cidade = None
        self.sistema_coordenadas = None

    def executar(self, nome_cidade, gdf_municipio):
        config = load_config()

        self.cidade = nome_cidade.replace(" ", "-").lower()
        self._definir_sistema_coordenadas(gdf_municipio)

        self._definir_sistema_coordenadas(gdf_municipio)
        self._criar_shapefile_municipio(gdf_municipio)
        self._criar_moldura_municipio()
        self._processar_mde()

        if config["criterios"]["declividade"]["ativo"]:
            self._processar_declividade()
            self._reclassificar_raster(
                f"outputs/declividade/declividade_{self.cidade}.tif",
                f"outputs/declividade/declividade_{self.cidade}_reclass.tif",
                config["criterios"]["declividade"]["classes"]
            )
        
        if config["criterios"]["fluxo_acumulado"]["ativo"]:
            self._processar_fluxo_acumulado()
            self._reclassificar_raster(
                f"outputs/fluxo_acumulado/fluxo_acumulado_{self.cidade}.tif",
                f"outputs/fluxo_acumulado/fluxo_acumulado_{self.cidade}_reclass.tif",
                config["criterios"]["fluxo_acumulado"]["classes"]
            )

        if config["criterios"]["uso_do_solo"]["ativo"]:
            self._processar_uso_do_solo()
            self._reclassificar_raster(
                f"outputs/uso_do_solo/uso_do_solo_{self.cidade}.tif",
                f"outputs/uso_do_solo/uso_do_solo_{self.cidade}_reclass.tif",
                config["criterios"]["uso_do_solo"]["classes"],
                is_categorical=True
            )
        
        uso_path = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}.tif"
        uso_recortado_path = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}_recortado.tif"

        self._recortar_mapa(uso_path, uso_recortado_path)
        
        if config["criterios"]["hipsometria"]["ativo"]:
            self._reclassificar_raster(
                f"outputs/mde/mde_{self.cidade}.tif",
                f"outputs/hipsometria/hipsometria_{self.cidade}_reclass.tif",
                config["criterios"]["hipsometria"]["classes"],
            )

        pesos, cr = self._calcular_pesos()
        self._gerar_mapa_risco(pesos)

        risco_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}.tif"
        risco_recortado_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}_recortado.tif"

        self._recortar_mapa(risco_path, risco_recortado_path)

        return risco_recortado_path


    def _definir_sistema_coordenadas(self, gdf_municipio):
        zona_24s = "EPSG:31984"     # SIRGAS 2000 / UTM 24S
        zona_25s = "EPSG:31985"     # SIRGAS 2000 / UTM 25S

        centroid = gdf_municipio.geometry.centroid.iloc[0]
        lon = centroid.x

        if lon < -36:
            self.sistema_coordenadas = zona_24s
        else:
            self.sistema_coordenadas = zona_25s
    
    def _criar_shapefile_municipio(self, gdf_municipio):
        gdf_reproj = gdf_municipio.to_crs(self.sistema_coordenadas)
        gdf_reproj.to_file(f"outputs/limites_municipios/limite_{self.cidade}_reprojetado.shp")
    
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

    def _reclassificar_raster(self, input_path, output_path, classes, is_categorical=False):
        with rasterio.open(input_path) as src:
            data = src.read(1)
            profile = src.profile

        reclass = np.zeros_like(data, dtype=np.uint8)
        if is_categorical:
            for _, cls in classes.items():
                for id_val in cls["ids"]:
                    reclass[data == id_val] = cls["valor"]
        else:
            for cls in classes:
                min_val = cls["min"] if cls["min"] is not None else -np.inf
                max_val = cls["max"] if cls["max"] is not None else np.inf
                reclass[(data >= min_val) & (data <= max_val)] = cls["valor"]

        profile.update(dtype=rasterio.uint8, count=1, nodata=0)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(reclass, 1)
    
    def _processar_declividade(self):
        mde_tratado_path = f"outputs/mde/mde_{self.cidade}.tif"

        with rasterio.open(mde_tratado_path) as src:
            mde = src.read(1, masked=True)
            transform_raster = src.transform
            profile = src.profile

        xres = transform_raster.a
        yres = -transform_raster.e

        gy, gx = np.gradient(mde, yres, xres)

        slope = np.arctan(np.sqrt(gx**2 + gy**2))
        slope_degrees = np.degrees(slope)

        profile.update(dtype=rasterio.float32, count=1)

        with rasterio.open(f"outputs/declividade/declividade_{self.cidade}.tif", "w", **profile) as dst:
            dst.write(slope_degrees.astype(rasterio.float32), 1)
    
    def _processar_fluxo_acumulado(self):
        realizar_analise_de_fluxo(self.cidade)
    
    def _processar_uso_do_solo(self):
        uso_do_solo_pernambuco = "dados/uso-do-solo-pernambuco-2023.tif"
        moldura_path = f"outputs/molduras_municipios/moldura-{self.cidade}.tif"
        uso_alinhado = f"outputs/uso_do_solo/uso_do_solo_{self.cidade}.tif"

        # Abrir moldura como referência
        with rasterio.open(moldura_path) as moldura:
            moldura_transform = moldura.transform
            moldura_width = moldura.width
            moldura_height = moldura.height
            moldura_crs = moldura.crs

        # Reprojetar uso do solo para a moldura
        with rasterio.open(uso_do_solo_pernambuco) as src:
            profile = src.meta.copy()
            profile.update({
                "crs": moldura_crs,
                "transform": moldura_transform,
                "width": moldura_width,
                "height": moldura_height
            })

            with rasterio.open(uso_alinhado, "w", **profile) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=moldura_transform,
                        dst_crs=moldura_crs,
                        resampling=Resampling.nearest
                    )
    
    def _pesos_metodo_ahp(self, pairwise):
        A = np.array(pairwise, dtype=float)
        # Autovetor principal
        vals, vecs = np.linalg.eig(A)
        idx = np.argmax(vals.real)
        w = vecs[:, idx].real
        w = w / w.sum()

        # Consistência
        n = A.shape[0]
        lambda_max = vals[idx].real
        CI = (lambda_max - n) / (n - 1)
        RI_table = {1:0.00, 2:0.00, 3:0.58, 4:0.90, 5:1.12, 6:1.24, 7:1.32, 8:1.41, 9:1.45, 10:1.49}
        RI = RI_table.get(n, 0.9)
        CR = CI / RI if RI > 0 else 0.0
        return w, CR
    
    def _calcular_pesos(self):
        uso_vs_declividade = 1/5
        uso_vs_fluxo = 3
        uso_vs_hipsometria = 1/5
        declividade_vs_fluxo = 3
        declividade_vs_hipsometria = 1
        fluxo_vs_hipsometria = 1/5

        A = [
            [1, uso_vs_declividade, uso_vs_fluxo, uso_vs_hipsometria],
            [1/uso_vs_declividade, 1, declividade_vs_fluxo, declividade_vs_hipsometria],
            [1/uso_vs_fluxo, 1/declividade_vs_fluxo, 1, fluxo_vs_hipsometria],
            [1/uso_vs_hipsometria, 1/declividade_vs_hipsometria, 1/fluxo_vs_hipsometria, 1]
        ]

        pesos, CR = self._pesos_metodo_ahp(A)

        return pesos, CR

    def _gerar_mapa_risco(self, pesos):
        peso_uso, peso_declividade, peso_fluxo, peso_hipso = pesos

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

    
    def _recortar_mapa(self, raster_path, output_path):
        shapefile_path = f"outputs/limites_municipios/limite_{self.cidade}_reprojetado.shp"
    
        gdf = gpd.read_file(shapefile_path)
        geometries = gdf.geometry.values

        with rasterio.open(raster_path) as src:
            dtype = src.dtypes[0]

            # Escolher valor de NoData dependendo do tipo do raster
            if np.issubdtype(dtype, np.integer):
                nodata = 0
            else:
                nodata = -9999.0

            # Aplicar máscara e recorte
            out_image, out_transform = mask(
                src, geometries, crop=True, filled=True, nodata=nodata
            )

            if np.issubdtype(dtype, np.floating):
                out_image = out_image.astype("float32")

            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "dtype": out_image.dtype,
                "nodata": nodata
            })

        with rasterio.open(output_path, "w", **out_meta) as dst:
            dst.write(out_image)
