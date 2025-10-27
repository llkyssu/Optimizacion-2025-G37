import osmnx as ox
import geopandas as gpd

# --- Configuración ---
lugar = "Santiago Metropolitan Region, Chile"
projected_crs = "EPSG:32719"
output_file = "comunas_rm_sucias.gpkg" # Archivo de salida

print(f"--- SCRIPT 1: OBTENIENDO LÍMITES ---")
print(f"Iniciando proceso para: '{lugar}'")

# --- 1. Descargar Límite de la Región (El molde maestro) ---
print("Descargando límite de la Región Metropolitana (admin_level=6)...")
try:
    gdf_region = ox.features_from_place(lugar, tags={"admin_level": "6", "boundary": "administrative"})
    gdf_region = gdf_region[gdf_region.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    gdf_region = gdf_region.to_crs(projected_crs)
    print(f"Límite de la RM (1 polígono) descargado.")
except Exception as e:
    print(f"Error fatal: No se pudo descargar el límite de la Región Metropolitana. {e}")
    exit()

# --- 2. Descargar TODOS los límites admin_level=8 (la lista sucia) ---
print("Descargando todos los límites Nivel 8 (comunas, provincias, etc.)...")
gdf_comunas_todas = ox.features_from_place(lugar, tags={"admin_level": "8", "boundary": "administrative"})
gdf_comunas_todas = gdf_comunas_todas[gdf_comunas_todas.geometry.type.isin(['Polygon', 'MultiPolygon'])]
gdf_comunas_todas = gdf_comunas_todas.to_crs(projected_crs)
print(f"Descargados {len(gdf_comunas_todas)} límites etiquetados como Nivel 8.")

# --- 3. ¡LA LIMPIEZA! Filtrar solo verdaderas comunas ---
print("Limpiando la lista para quedarnos solo con comunas reales...")

# Columnas de otros niveles admin que NO queremos (Provincias, Regiones, Países)
cols_a_excluir = ['admin_level:4', 'admin_level:6', 'admin_level:7']
# Vemos cuáles de esas columnas realmente existen en nuestros datos
cols_existentes = [col for col in cols_a_excluir if col in gdf_comunas_todas.columns]

# Filtramos: Mantenemos solo las filas donde TODAS esas columnas (cols_existentes)
# están VACÍAS (NaN). Esto elimina Provincias, Regiones, etc.
gdf_comunas_limpias = gdf_comunas_todas[gdf_comunas_todas[cols_existentes].isna().all(axis=1)].copy()
print(f"Primer filtro: Quedan {len(gdf_comunas_limpias)} geometrías (después de sacar regiones/provincias).")

# --- 4. Filtro espacial: Quedarse solo con las de la RM ---
print("Filtrando espacialmente solo las comunas DENTRO de la RM...")
# 'predicate="within"' asegura que el polígono completo esté dentro de la RM
gdf_comunas_final = gpd.sjoin(gdf_comunas_limpias, gdf_region[['geometry']], how="inner", predicate="within")

# Limpiamos columnas finales
gdf_comunas_final = gdf_comunas_final[["name", "geometry"]].drop_duplicates(subset=["name"])
print(f"Filtro final: {len(gdf_comunas_final)} comunas limpias encontradas DENTRO de la RM.")

# --- 5. Guardar ---
if not gdf_comunas_final.empty:
    gdf_comunas_final.to_file(output_file, driver="GPKG")
    print(f"\n¡Éxito! Molde de comunas limpias guardado en '{output_file}'")
else:
    print("\nError: No se encontró ninguna comuna. Revisa los filtros.")