def path_output(tipo, cidade, suffix=""):
    base = f"outputs/{tipo}/{tipo}_{cidade}"
    return f"{base}{suffix}.tif"
