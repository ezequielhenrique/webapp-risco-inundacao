import folium
from folium.plugins import Draw


class MapaService:
    def __init__(self, center, zoom=11):
        self.map = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles=None
        )

    def add_base_layer(self):
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satélite"
        ).add_to(self.map)

    def add_layer(self, layer):
        layer.add_to(self.map)

    def add_default_plugins(self):
        folium.LatLngPopup().add_to(self.map)
        Draw(
            draw_options={
                'polyline': False,
                'polygon': True,
                'circle': False,
                'rectangle': True,
                'marker': True
            }
        ).add_to(self.map)

    def add_layer_control(self):
        folium.LayerControl().add_to(self.map)

    def render(self):
        return self.map._repr_html_()
