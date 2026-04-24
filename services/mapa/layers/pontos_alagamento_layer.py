import folium


class PontosAlagamentoLayer:
    def __init__(self, pontos):
        self.pontos = pontos

    def get(self):
        fg = folium.FeatureGroup(name="Pontos de Alagamento")

        for endereco, lat, lon in self.pontos:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(endereco, max_width=300),
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(fg)

        return fg
