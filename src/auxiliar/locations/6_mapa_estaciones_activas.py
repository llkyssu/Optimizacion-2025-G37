import pandas as pd
import geopandas as gpd
import os

# --- Configuración ---
project_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
resultados_dir = os.path.join(project_folder, "resultados")
csv_file = os.path.join(resultados_dir, "estaciones_activadas_coordenadas.csv")
mapa_file = os.path.join(resultados_dir, "mapa_estaciones_activas.html")

def main():
    print("--- Generando mapa de estaciones activas desde CSV ---")
    if not os.path.exists(csv_file):
        print(f"No se encontró el archivo {csv_file}")
        return
    df = pd.read_csv(csv_file)
    # Verificar columnas necesarias
    if not {"latitud", "longitud"}.issubset(df.columns):
        print("El CSV debe tener columnas 'latitud' y 'longitud'.")
        return
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["longitud"], df["latitud"]))
    # Forzar CRS a WGS84 si no está definido
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    # Columnas para mostrar
    columnas_popup = [c for c in ["id_sitio", "comuna", "direccion", "cargadores_iniciales", "cargadores_nuevos", "cargadores_totales", "paneles_iniciales", "paneles_nuevos", "paneles_totales", "utilizacion_cargadores_%", "utilizacion_paneles_%"] if c in gdf.columns]
    columnas_tooltip = [c for c in ["comuna", "direccion", "cargadores_totales"] if c in gdf.columns]
    print(f"Generando mapa interactivo con {len(gdf)} estaciones activas...")
    # Usar el mismo fondo visual que el script 4_process_map.py
    m = gdf.explore(
        column="comuna" if "comuna" in gdf.columns else None,
        tooltip=columnas_tooltip,
        popup=columnas_popup,
        tiles="CartoDB positron",  # Fondo igual al mapa general
        legend=False,
        marker_kwds={"radius": 6, "color": "#0072B2"},
        categorical=True,
        zoom_start=11,
        center=[-33.45, -70.65]  # Centro de Santiago
    )
    m.save(mapa_file)
    print(f"¡Mapa de estaciones activas guardado en '{mapa_file}'!")

if __name__ == "__main__":
    main()