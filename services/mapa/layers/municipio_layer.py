import folium


class MunicipioLayer:
    def __init__(self, gdf):
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        self.gdf = gdf

    def get(self):
        return folium.GeoJson(
            self.gdf,
            name="Limite do Município",
            style_function=lambda x: {
                'fillColor': 'yellow',
                'color': 'green',
                'weight': 2,
                'fillOpacity': 0
            }
        )
