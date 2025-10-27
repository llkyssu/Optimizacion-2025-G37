import osmnx as ox
import geopandas as gpd
import os

# --- Configuración ---

projected_crs = "EPSG:32719" # CRS Proyectado para Santiago
project_folder = "/home/marti/opti/" # Cambiado a la raíz del proyecto

comunas_file = os.path.join(project_folder, "comunas_rm_limpias.gpkg") 
output_file = os.path.join(project_folder, "features_rm_total.gpkg")  

tags_combinados = {
    "amenity": ["parking", "fuel", "charging_station", "car_wash", "hospital", "university"],
    "shop": ["supermarket", "mall"],
    "building": ["retail", "commercial", "office"],
    "leisure": ["stadium"]
}

print(f"--- SCRIPT 2 (MODIFICADO): OBTENIENDO PUNTOS DE INTERÉS ---")
print(f"Leyendo molde limpio desde: {comunas_file}")

# --- 1. Cargar el "molde" de 40 comunas ---
try:
    gdf_comunas = gpd.read_file(comunas_file)
except Exception as e:
    print(f"Error: No se pudo leer el archivo '{comunas_file}'. {e}")
    exit()

# --- 2. Preparar el polígono para OSMnx ---
print("Preparando polígono de las 40 comunas...")
gdf_comunas_wgs84 = gdf_comunas.to_crs("EPSG:4326")

# --- CORRECCIÓN 1: Arreglar el 'DeprecationWarning' ---
# merged_polygon = gdf_comunas_wgs84.unary_union # Obsoleto
merged_polygon = gdf_comunas_wgs84.geometry.union_all() # Moderno

# --- 3. Descargar ---
print(f"Descargando puntos de interés SÓLO DENTRO de esas 40 comunas...")
gdf_features = ox.features_from_polygon(merged_polygon, tags_combinados)
print(f"Se encontraron {len(gdf_features)} geometrías en total.")

# --- 4. Procesar (Proyectar y Centroide) ---
print("Proyectando puntos de interés a CRS local...")
gdf_features = gdf_features.to_crs(projected_crs)
print("Calculando centroides...")
gdf_features['geometry'] = gdf_features.geometry.centroid
print("Centroides calculados.")

# --- CORRECCIÓN 2: Limpiar columnas ANTES de guardar ---
print("Limpiando columnas para evitar el 'FieldError'...")
# Hacemos una lista de las columnas que SÍ queremos
columnas_a_guardar = [
    col for col in ["name", "amenity", "shop", "building", "leisure"] 
    if col in gdf_features.columns
] + ["geometry"] # Siempre añadimos la geometría

# Filtramos el GeoDataFrame para quedarnos solo con esas columnas
gdf_limpio = gdf_features[columnas_a_guardar]
print(f"Columnas limpiadas. Se guardarán {len(gdf_limpio.columns)} columnas.")

# --- 6. Guardar ---
# Guardamos el GeoDataFrame limpio, no el original
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
output_file_norm = normalizar_nombre(output_file)
gdf_limpio.to_file(output_file_norm, driver="GPKG")
print(f"\n¡Éxito! Todos los puntos de interés guardados en '{output_file_norm}'")