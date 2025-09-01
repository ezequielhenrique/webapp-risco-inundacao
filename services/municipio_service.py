import geopandas as gpd
from rasterio.warp import calculate_default_transform, reproject, Resampling
from branca.element import Template, MacroElement
import rasterio
from folium.plugins import Draw, MousePosition
import folium
import matplotlib.pyplot as plt
import numpy as np


class MunicipioService:
    def __init__(self, municipios_path):
        self.municipios = gpd.read_file(municipios_path)

    def get_nome_cidades(self):
        lista_cidades = sorted(self.municipios["NM_MUN"].unique())

        return lista_cidades
    
    def get_gdf_municipio(self, nome_cidade):
        dados_municipios = self.municipios.loc[self.municipios['NM_MUN'] == nome_cidade]
        gdf = gpd.GeoDataFrame(dados_municipios, geometry=dados_municipios['geometry'])

        return gdf
    
    def gerar_mapa_base(self):
        mapa = folium.Map(
            location=[-8.38, -37.86],
            zoom_start=7,
            tiles=None
        )

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satélite",
            overlay=False,
            control=True
        ).add_to(mapa)

        folium.LayerControl().add_to(mapa)

        return mapa._repr_html_()
    
    def gerar_mapa_municipio(self, nome_cidade, raster_path):
        dados_municipios = self.municipios.loc[self.municipios['NM_MUN'] == nome_cidade]
        gdf = gpd.GeoDataFrame(dados_municipios, geometry=dados_municipios['geometry'])

        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)

        centro = gdf.geometry.centroid.iloc[0]
        lat, lon = centro.y, centro.x

        # Base map
        m = folium.Map(
            location=[lat, lon], 
            zoom_start=11,
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri"
        )

        # GeoJson do município
        folium.GeoJson(
            gdf,
            name="Limite do Município",
            style_function=lambda x: {
                'fillColor': 'yellow',
                'color': 'green',
                'weight': 2,
                'fillOpacity': 0
            }
        ).add_to(m)

        # Raster overlay
        with rasterio.open(raster_path) as src:
            if src.nodata is None:
                dtype = src.dtypes[0]
                if np.issubdtype(dtype, np.integer):
                    nodata = 0
                else:
                    nodata = np.nan
            else:
                nodata = src.nodata
            
            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': 'EPSG:4326',
                'transform': transform,
                'width': width,
                'height': height,
                'nodata': nodata
            })

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

        # Converter para imagem normalizada (0-255) para overlay
        norm_data = (data - data.min()) / (data.max() - data.min())
        rgba = plt.cm.RdYlGn_r(norm_data)  # colormap matplotlib
        rgba = (rgba[:, :, :4] * 255).astype(np.uint8)  # converter para 0-255

        # Adicionar ao mapa
        folium.raster_layers.ImageOverlay(
            name="Zonas de risco alagamento",
            image=rgba,
            bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            opacity=0.6,
            interactive=True,
            cross_origin=False
        ).add_to(m)

        # Plugins

        # Mostrar coordenadas ao clicar
        folium.LatLngPopup().add_to(m)

        # Ferramenta de desenho (ponto e retângulo)
        Draw(
            draw_options={
                'polyline': False,
                'polygon': True,
                'circle': False,
                'rectangle': True,
                'marker': True
            },
            edit_options={'edit': True}
        ).add_to(m)

        template = """
        {% macro html(this, kwargs) %}
        <div style="
            position: fixed;
            bottom: 20px;
            left: 20px;
            width: 150px;
            height: 160px;
            z-index:9999;
            font-size:14px;
            background-color: white;
            border:2px solid grey;
            border-radius:5px;
            padding: 10px;
            box-shadow: 3px 3px 5px rgba(0,0,0,0.4);
        ">
            <b>Risco de Alagamento</b><br>
            <i style="background:#d73027;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Alto<br>
            <i style="background:#ffffb2;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Moderado<br>
            <i style="background:#78c679;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Baixo<br>
            <i style="background:#006837;width:20px;height:20px;display:inline-block;margin-right:5px;"></i> Muito Baixo<br>
        </div>
        {% endmacro %}
        """

        macro = MacroElement()
        macro._template = Template(template)

        pontos_alagamento = [
            ("Rua Imperial, bairro de São José", -8.07581, -34.89415),
            ("Rua Nicolau Pereira", -8.07804, -34.90558),
            ("Av. Eng. Abdias de Carvalho", -8.06123, -34.92227),
            ("Av. Dois Rios", -8.11289, -34.93864),
            ("Av. Mal Mascarenhas de Moraes", -8.11383, -34.91281),
            ("Av. Recife próximo ao cruzamento com a Rua João Cabral de Melo Neto", -8.07953, -34.93374),
            ("Av. Abdias de Carvalho, no cruzamento com a rua Delmiro Gouveia", -8.06252, -34.93219),
            ("Av. Norte Miguel Arraes de Alencar, ao lado do Senai", -8.04713, -34.87757)
        ]

        # Adicionar marcadores ao mapa
        for endereco, lat_ponto, lon_ponto in pontos_alagamento:
            folium.Marker(
                location=[lat_ponto, lon_ponto],
                popup=folium.Popup(endereco, max_width=300),
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)

        folium.LayerControl().add_to(m)

        m.add_child(macro)

        return m._repr_html_()
