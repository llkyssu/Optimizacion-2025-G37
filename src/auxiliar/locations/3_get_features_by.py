import pandas as pd
import geopandas as gpd
import os

# --- Configuración ---

# --- RUTA RELATIVA AL PROYECTO ---
project_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
raw_data_folder = os.path.join(project_folder, "raw_data")

# --- Archivos de ENTRADA ---
comunas_file = os.path.join(raw_data_folder, "comunas_rm_limpias.gpkg")
features_file = os.path.join(raw_data_folder, "features_rm_total.gpkg")

# --- Carpeta de SALIDA ---
output_folder = os.path.join(raw_data_folder, "dpc_gpkg")  # Carpeta de salida

os.makedirs(output_folder, exist_ok=True) 

print(f"--- SCRIPT 3A: PROCESANDO Y DIVIDIENDO POR COMUNA ---")

# --- 1. Cargar datos desde el disco ---
print(f"Cargando molde de comunas desde '{comunas_file}'...")
try:
    gdf_comunas = gpd.read_file(comunas_file)
except Exception as e:
    print(f"Error: No se pudo leer el archivo '{comunas_file}'. {e}")
    exit()

print(f"Cargando puntos de interés desde '{features_file}'...")
try:
    gdf_features = gpd.read_file(features_file)
except Exception as e:
    print(f"Error: No se pudo leer el archivo '{features_file}'. ¿Corriste el Script 2? {e}")
    exit()

print(f"Datos cargados: {len(gdf_comunas)} comunas y {len(gdf_features)} puntos de interés.")

# --- 2. Procesar en Bucle (Ligero en RAM) ---
print("\nIniciando procesamiento iterativo por comuna...")
total_puntos_guardados = 0

# Define las columnas que te interesa conservar
columnas_a_guardar = [
    col for col in ["name", "amenity", "shop", "building", "leisure"] 
    if col in gdf_features.columns
] + ["geometry"] 

for index, comuna in gdf_comunas.iterrows():
    comuna_name = comuna["name"]
    comuna_geom = comuna.geometry
    
    print(f"  Procesando '{comuna_name}'...")
    
    # Filtra los puntos que están dentro de la geometría de la comuna actual
    puntos_en_comuna = gdf_features[gdf_features.geometry.within(comuna_geom)]

    if puntos_en_comuna.empty:
        print(f"    -> No se encontraron puntos en '{comuna_name}'.")
        continue

    # Selecciona solo las columnas de interés y añade el nombre de la comuna
    comuna_gdf = puntos_en_comuna[columnas_a_guardar].copy()
    comuna_gdf["comuna"] = comuna_name
    
    # Genera un nombre de archivo seguro
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
    safe_name = normalizar_nombre(str(comuna_name))
    filename = os.path.join(output_folder, f"{safe_name}.gpkg")
    
    # Guarda el archivo GPKG (Corregí EPSG:4G326 a EPSG:4326, asumiendo WGS84)
    try:
        comuna_gdf.to_crs("EPSG:4326").to_file(filename, driver="GPKG")
        print(f"    -> ¡Éxito! Guardados {len(comuna_gdf)} puntos en '{filename}'")
        total_puntos_guardados += len(comuna_gdf)
    except Exception as e:
        print(f"    -> ERROR al guardar '{filename}'. {e}")


print(f"\n¡Proceso de división completado! Se guardaron {total_puntos_guardados} puntos en {len(gdf_comunas)} comunas.")