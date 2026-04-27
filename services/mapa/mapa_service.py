import folium
from folium.plugins import Draw
from branca.element import Template, MacroElement

from utils.mapa_templates import TEMPLATE_LEGENDA, get_template_popup, get_sliders_html, get_sliders_template, get_sliders_script


class MapaService:
    def __init__(self, center, cidade=None, zoom=11):
        self.cidade = cidade
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
    
    def add_legend(self):
        template = TEMPLATE_LEGENDA

        macro = MacroElement()
        macro._template = Template(template)
        self.map.add_child(macro)
    
    def add_click_popup(self):
        template = get_template_popup(self.cidade)

        macro = MacroElement()
        macro._template = Template(template)
        self.map.add_child(macro)
    
    def add_ahp_sliders(self, pesos_iniciais, cidade, overlay_name):
        w_uso0, w_decl0, w_flux0, w_hipso0 = pesos_iniciais

        sliders_inner_html = get_sliders_html(w_uso0, w_decl0, w_flux0, w_hipso0)
        template = get_sliders_template(sliders_inner_html)
        script = get_sliders_script(cidade, overlay_name, w_uso0, w_decl0, w_flux0, w_hipso0)

        macro = MacroElement()
        macro._template = Template(template + script)
        self.map.add_child(macro)
    
    def render(self):
        return self.map._repr_html_()
