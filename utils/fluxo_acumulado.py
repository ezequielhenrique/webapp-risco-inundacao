import os
import sys
import subprocess

def realizar_analise_de_fluxo(cidade):
    # Caminho da instalação do GRASS
    os.environ['GISBASE'] = r"C:\Program Files\GRASS GIS 8.4"
    grass_base = os.environ['GISBASE']

    # Adiciona ao PATH
    os.environ['PATH'] += os.pathsep + os.path.join(grass_base, 'extrabin')
    os.environ['PATH'] += os.pathsep + os.path.join(grass_base, 'bin')
    os.environ['PATH'] += os.pathsep + os.path.join(grass_base, 'scripts')

    # Adiciona bibliotecas do Python do GRASS
    sys.path.append(os.path.join(grass_base, 'etc', 'python'))

    import grass.script as gs
    import grass.script.setup as gsetup

    mde_tratado_path = f"outputs/mde/mde_{cidade}.tif"

    grass_bin = r"C:\Program Files\GRASS GIS 8.4\grass84.bat"
    gisdb = r"C:\grassdata"
    location = cidade
    mde_path = os.path.abspath(rf"outputs/mde/mde_{cidade}.tif")

    # Criar a location se não existir
    location_path = os.path.join(gisdb, location)
    if not os.path.exists(location_path):
        subprocess.run([
            grass_bin,
            "-c", mde_path,
            location_path,
            "--exec", "exit"
        ], check=True)

    # Inicializar sessão GRASS
    mapset = "PERMANENT"
    gsetup.init(gisdb, location, mapset)

    mde_tratado_path = rf"outputs/mde/mde_{cidade}.tif"

    gs.run_command("r.import", input=mde_tratado_path, output=f"mde_{cidade}", overwrite=True)

    fluxo_acumulado_rast = f"fluxo_acumulado_{cidade}"

    gs.run_command("r.watershed",
                elevation=f"mde_{cidade}",
                accumulation=fluxo_acumulado_rast,
                drainage=150,   # Tamanho mínimo da bacia em número de células
                overwrite=True)

    fluxo_acumulado_path = rf"outputs/fluxo_acumulado/fluxo_acumulado_{cidade}.tif"

    gs.run_command("r.out.gdal",
                input=fluxo_acumulado_rast,
                output=fluxo_acumulado_path,
                format="GTiff",
                overwrite=True)
