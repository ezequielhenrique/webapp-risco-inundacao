from rasterio.warp import calculate_default_transform, reproject, Resampling, transform
from rasterio.transform import from_origin
from rasterio.mask import mask
from rasterio.windows import from_bounds
from rasterio.plot import show
from pathlib import Path
import os
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
        config = load_config() or {}

        self.cidade = nome_cidade.replace(" ", "-").lower()
        self._definir_sistema_coordenadas(gdf_municipio)
        self._ensure_output_dirs()
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
        
        if config["criterios"]["hipsometria"]["ativo"]:
            # Se for Recife, usar classes hardcoded; senão calcular dinamicamente
            ipso_classes = self._calcular_classes_hipsometria(
                f"outputs/mde/mde_{self.cidade}.tif",
                config["criterios"]["hipsometria"].get("classes", [])
            )
            self._reclassificar_raster(
                f"outputs/mde/mde_{self.cidade}.tif",
                f"outputs/hipsometria/hipsometria_{self.cidade}_reclass.tif",
                ipso_classes,
            )

        pesos, cr = self._calcular_pesos(config)
        self._gerar_mapa_risco(pesos)

        risco_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}.tif"
        risco_recortado_path = f"outputs/mapas_de_risco/risco_alagamento_{self.cidade}_recortado.tif"

        self._recortar_mapa(risco_path, risco_recortado_path)

        return risco_recortado_path


    def _definir_sistema_coordenadas(self, gdf_municipio):
        """Define CRS projetado (SIRGAS 2000 / UTM) baseado na longitude do município.

        Pernambuco pode cair em mais de uma zona UTM (principalmente 23S, 24S, 25S).
        Usar a zona correta melhora alinhamento/área e evita distorções desnecessárias.
        """

        gdf = gdf_municipio
        try:
            if gdf.crs is None or str(gdf.crs).upper() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
        except Exception:
            # Se houver problema de CRS, cai no comportamento antigo (assume 25S)
            self.sistema_coordenadas = "EPSG:31985"
            return

        centroid = gdf.geometry.centroid.iloc[0]
        lon = float(centroid.x)

        # Zona UTM padrão: zone = floor((lon + 180) / 6) + 1
        utm_zone = int(np.floor((lon + 180.0) / 6.0) + 1)

        # SIRGAS 2000 / UTM zone {Z}S => EPSG:31960 + Z (ex.: 23S->31983, 24S->31984, 25S->31985)
        epsg_code = 31960 + utm_zone
        self.sistema_coordenadas = f"EPSG:{epsg_code}"
    
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


        # Resolução padrão (metros/pixel) da grade mestre da análise.
        # Importante: MapBiomas é categórico (usar nearest ao alinhar).
        res = 30  # 30m

        width = int(np.ceil((xmax_pad - xmin_pad) / res))
        height = int(np.ceil((ymax_pad - ymin_pad) / res))

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

    def _ensure_output_dirs(self):
        dirs = [
            "outputs/declividade",
            "outputs/fluxo_acumulado",
            "outputs/hipsometria",
            "outputs/limites_municipios",
            "outputs/mapas_de_risco",
            "outputs/mapas_interativos",
            "outputs/mde",
            "outputs/molduras_municipios",
            "outputs/uso_do_solo",
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def _resolve_mde_path(self) -> str:
        """Resolve o MDE de entrada.

        Estratégia:
        1) Se houver mapeamento em static/config/config.json (dados.mde), usa-o.
        2) Tenta um MDE por-cidade (dados/mde_<cidade>.tif).
        3) Por fim, usa o MDE estadual (preferindo dados/mde_pernambuco_srtm.tif) quando existir.
        """

        config = load_config() or {}
        mde_cfg = (config.get("dados") or {}).get("mde")
        if isinstance(mde_cfg, dict):
            if self.cidade in mde_cfg and mde_cfg[self.cidade]:
                p = Path(str(mde_cfg[self.cidade]))
                if p.exists():
                    return str(p)
            if "estado" in mde_cfg and mde_cfg["estado"]:
                p = Path(str(mde_cfg["estado"]))
                if p.exists():
                    return str(p)

        candidates: list[Path] = [
            Path(f"dados/mde_{self.cidade}.tif"),
            Path(f"dados/mde_{self.cidade.replace('-', '_')}.tif"),
        ]

        # MDE estadual (preferir nome com identificação do produto de origem)
        candidates.extend(
            [
                Path("dados/mde_pernambuco_srtm.tif"),
                Path("dados/mde_pernambuco.tif"),
            ]
        )

        for p in candidates:
            if p.exists():
                return str(p)

        raise FileNotFoundError(
            "Nenhum MDE encontrado. Para rodar em Recife/Belo Jardim, forneça um MDE por-cidade em: "
            f"dados/mde_{self.cidade}.tif (ou configure dados.mde no static/config/config.json). "
            "Para generalizar para todo o estado, gere/adicione o mosaico estadual em dados/mde_pernambuco_srtm.tif (ou configure dados.mde.estado)."
        )

    def _processar_mde(self):
        mde_path = self._resolve_mde_path()
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
            src_nodata = src.nodata
            profile = src.profile

        reclass = np.zeros_like(data, dtype=np.uint8)

        # Máscara de dados válidos (evita classificar NoData/NaN)
        valid = np.isfinite(data)
        if src_nodata is not None and np.isfinite(src_nodata):
            valid &= data != src_nodata

        if is_categorical:
            for _, cls in (classes or {}).items():
                for id_val in cls.get("ids", []):
                    reclass[(data == id_val) & valid] = cls.get("valor", 0)
        else:
            if not isinstance(classes, list) or not classes:
                raise ValueError("Classes de reclassificação (contínuas) inválidas ou vazias")

            # Aplicar classes configuradas
            parsed: list[dict] = []
            for cls in classes:
                min_val = cls.get("min", None)
                max_val = cls.get("max", None)
                val = int(cls.get("valor", 0))
                parsed.append(
                    {
                        "min": (-np.inf if min_val is None else float(min_val)),
                        "max": (np.inf if max_val is None else float(max_val)),
                        "valor": val,
                    }
                )

            parsed.sort(key=lambda d: d["min"])

            for cls in parsed:
                reclass[valid & (data >= cls["min"]) & (data <= cls["max"])] = cls["valor"]

            # Corrigir pixels válidos que ficaram sem classe (muito comum com valor 0 em declividade/fluxo)
            unclassified = valid & (reclass == 0)
            if np.any(unclassified):
                first = parsed[0]
                last = parsed[-1]

                # Abaixo do mínimo -> primeira classe
                reclass[unclassified & (data < first["min"])] = first["valor"]
                # Acima do máximo -> última classe
                reclass[unclassified & (data > last["max"])] = last["valor"]

                # Gaps entre classes: atribui para a classe anterior (comportamento conservador)
                for prev, nxt in zip(parsed[:-1], parsed[1:]):
                    gap = unclassified & (data > prev["max"]) & (data < nxt["min"])
                    if np.any(gap):
                        reclass[gap] = prev["valor"]

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
    
    def _calcular_classes_hipsometria(self, mde_path: str, config_classes: list | None = None) -> list:
        """Calcula classes de hipsometria (altitude) dinamicamente.
        
        Metodologia Cury et al. (2021): Para cada município, divide a faixa altimétrica (min-max)
        em intervalos iguais.
        
        Para Recife (caso especial): Usa as classes hardcoded da config.
        Para outros municípios: Calcula automaticamente 4 intervalos iguais.
        
        Args:
            mde_path: Caminho para o raster do MDE relativo à moldura municipal
            config_classes: Classes configuradas (usadas para Recife)
        
        Returns:
            Lista com dicts contendo {min, max, valor} no formato esperado por _reclassificar_raster
        """
        
        # Se for Recife, usar as classes da config (hardcoded específicas da cidade)
        if self.cidade == "recife":
            if config_classes and isinstance(config_classes, list) and len(config_classes) > 0:
                return config_classes
            # Fallback: usar padrão Recife mesmo se não estiver em config
            return [
                {"min": 0.0, "max": 3.0, "valor": 4.0},
                {"min": 3.0, "max": 10.0, "valor": 3.0},
                {"min": 10.0, "max": 50.0, "valor": 2.0},
                {"min": 50.0, "max": None, "valor": 1.0},
            ]
        
        # Para outros municípios: calcular intervalos iguais
        with rasterio.open(mde_path) as src:
            data = src.read(1)
            src_nodata = src.nodata
        
        # Máscara de dados válidos
        valid = np.isfinite(data)
        if src_nodata is not None and np.isfinite(src_nodata):
            valid &= data != src_nodata
        
        if not np.any(valid):
            # Se não houver dados válidos, retornar padrão genérico
            return [
                {"min": 0.0, "max": 25.0, "valor": 4.0},
                {"min": 25.0, "max": 50.0, "valor": 3.0},
                {"min": 50.0, "max": 100.0, "valor": 2.0},
                {"min": 100.0, "max": None, "valor": 1.0},
            ]
        
        # Extrair min/max de dados válidos
        min_alt = float(np.nanmin(data[valid]))
        max_alt = float(np.nanmax(data[valid]))
        
        # Evitar divisão por zero
        if min_alt >= max_alt:
            min_alt = 0.0
            max_alt = 1.0
        
        # Calcular intervalo igual (metodologia Cury et al. 2021)
        n_classes = 4
        intervalo = (max_alt - min_alt) / n_classes
        
        classes = []
        for i in range(n_classes):
            cls_min = min_alt + (i * intervalo)
            cls_max = min_alt + ((i + 1) * intervalo)
            
            # Última classe: sem limite máximo (None)
            if i == n_classes - 1:
                cls_max = None
            
            # Valor de reclassificação: 4 para mais baixo, 1 para mais alto
            # (inversamente correlacionado com altitude para risco de inundação)
            valor = float(n_classes - i)
            
            classes.append({
                "min": cls_min,
                "max": cls_max,
                "valor": valor,
            })
        
        return classes
    
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
    
    def _calcular_pesos(self, config: dict | None = None):
        cfg = (config or {}).get("pesos") if isinstance((config or {}).get("pesos"), dict) else {}

        # Defaults (mantém o comportamento atual se não houver config)
        uso_vs_declividade = float(cfg.get("uso_vs_declividade", 1 / 5))
        uso_vs_fluxo = float(cfg.get("uso_vs_fluxo", 3))
        uso_vs_hipsometria = float(cfg.get("uso_vs_hipsometria", 1 / 5))
        declividade_vs_fluxo = float(cfg.get("declividade_vs_fluxo", 3))
        declividade_vs_hipsometria = float(cfg.get("declividade_vs_hipsometria", 1))
        fluxo_vs_hipsometria = float(cfg.get("fluxo_vs_hipsometria", 1 / 5))

        # Sanitização mínima para evitar divisões por zero / valores inválidos
        pairwise = [
            uso_vs_declividade,
            uso_vs_fluxo,
            uso_vs_hipsometria,
            declividade_vs_fluxo,
            declividade_vs_hipsometria,
            fluxo_vs_hipsometria,
        ]
        if not np.isfinite(pairwise).all() or any(v <= 0 for v in pairwise):
            uso_vs_declividade = 1 / 5
            uso_vs_fluxo = 3
            uso_vs_hipsometria = 1 / 5
            declividade_vs_fluxo = 3
            declividade_vs_hipsometria = 1
            fluxo_vs_hipsometria = 1 / 5

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
        # IMPORTANTE: 0 nos rasters reclassificados significa NoData/fora da área/"excluído" (ex.: corpos d'água).
        # Para o TIFF "inicial" bater com o overlay dinâmico, precisamos mascarar esses pixels.
        mask_valid = (uso > 0) & (declividade > 0) & (fluxo > 0) & (hipso > 0)
        risco = (uso * peso_uso) + (declividade * peso_declividade) + (fluxo * peso_fluxo) + (hipso * peso_hipso)
        risco = risco.astype(np.float32, copy=False)

        nodata = -9999.0
        risco[~mask_valid] = nodata

        perfil.update(dtype=rasterio.float32, count=1, nodata=nodata)
        with rasterio.open(saida_risco, "w", **perfil) as dst:
            dst.write(risco, 1)

    
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
