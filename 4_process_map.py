import pandas as pd
import geopandas as gpd
import os

# --- Configuración ---

# --- RUTA LOCAL DE WSL ---
project_folder = "/home/marti/opti/" # Tu carpeta de trabajo en WSL

# --- Carpeta de ENTRADA ---
# Esta es la carpeta donde el Script 3A guardó los archivos
input_folder = os.path.join(project_folder, "datos_por_comuna") 

# --- Archivo de SALIDA ---
mapa_file = os.path.join(project_folder, "mapa_completo_final.html") # Mapa de salida

print(f"--- SCRIPT 3B: GENERANDO MAPA INTERACTIVO ---")

# --- 1. Cargar datos generados por Script 3A ---
print(f"Buscando archivos .gpkg en '{input_folder}'...")

lista_gdfs_comunas = []
if not os.path.exists(input_folder):
    print(f"Error: La carpeta '{input_folder}' no existe.")
    print("Por favor, ejecuta primero el Script 3A para generar los datos.")
    exit()

for file in os.listdir(input_folder):
    if file.endswith(".gpkg"):
        filepath = os.path.join(input_folder, file)
        try:
            print(f"  Cargando {file}...")
            lista_gdfs_comunas.append(gpd.read_file(filepath))
        except Exception as e:
            print(f"  Advertencia: No se pudo leer el archivo {filepath}. {e}")

# --- 2. Generar Mapa Interactivo ---
if lista_gdfs_comunas:
    print(f"Combinando {len(lista_gdfs_comunas)} archivos en un solo GeoDataFrame...")
    gdf_final_unido = pd.concat(lista_gdfs_comunas, ignore_index=True)
    
    print(f"Generando mapa interactivo con {len(gdf_final_unido)} puntos...")
    
    # 1. Definimos TODAS las columnas que queremos mostrar en el popup (al hacer clic)
    columnas_popup = ["name", "amenity", "shop", "building", "leisure", "comuna"]
    columnas_existentes_popup = [col for col in columnas_popup if col in gdf_final_unido.columns]

    # 2. Definimos qué mostrar al pasar el mouse (tooltip)
    columnas_tooltip = ["name", "amenity", "shop", "comuna"]
    columnas_existentes_tooltip = [col for col in columnas_tooltip if col in gdf_final_unido.columns]

    m = gdf_final_unido.explore(
        column="comuna",
        tooltip=columnas_existentes_tooltip, # <- Columnas para tooltip (mouse-over)
        popup=columnas_existentes_popup,     # <- Columnas para popup (clic)
        tiles="CartoDB positron",
        legend=False,
        marker_kwds={"radius": 4},
        categorical=True
    )
    
    m.save(mapa_file)
    print(f"¡Mapa interactivo guardado en '{mapa_file}'!")
else:
    print("No se encontraron archivos .gpkg para generar el mapa.")
    print(f"Asegúrate de que el Script 3A haya funcionado correctamente y haya datos en '{input_folder}'.")