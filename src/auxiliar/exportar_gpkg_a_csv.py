
import geopandas as gpd
import glob
import os
import unicodedata

def normalizar_nombre(nombre):
    base, ext = os.path.splitext(nombre)
    base = base.lower()
    base = base.replace('ñ', 'n')
    base = ''.join((c for c in unicodedata.normalize('NFD', base) if unicodedata.category(c) != 'Mn'))
    base = base.replace(' ', '_').replace('-', '_')
    while '__' in base:
        base = base.replace('__', '_')
    base = base.strip('_')
    return base + ext

input_folder = "datos_por_comuna_gpkg"
output_folder = "datos_por_comuna_csv"
os.makedirs(output_folder, exist_ok=True)


for path in glob.glob(f"{input_folder}/*.gpkg"):
    gdf = gpd.read_file(path)
    comuna = os.path.splitext(os.path.basename(path))[0]
    comuna_norm = normalizar_nombre(comuna)
    # Extrae latitud y longitud de la geometría
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    gdf.drop(columns="geometry").to_csv(f"{output_folder}/{comuna_norm}.csv", index=False)

print("Exportación completada.")
