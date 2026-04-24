import geopandas as gpd


class MunicipioService:
    def __init__(self, municipios_path):
        self.municipios = gpd.read_file(municipios_path)

    def get_nome_cidades(self):
        return sorted(self.municipios["NM_MUN"].unique())

    def get_gdf(self, nome_cidade):
        gdf = self.municipios[self.municipios['NM_MUN'] == nome_cidade]
        return gdf
