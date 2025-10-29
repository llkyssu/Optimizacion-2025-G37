zmax_por_tipo = {
    "parking": 30,
    "fuel": 20,
    "charging_station": 40,
    "car_wash": 10,
    "hospital": 25,
    "university": 35,
    "supermarket": 18,
    "mall": 50,
    "retail": 12,
    "commercial": 15,
    "office": 14,
    "stadium": 60
}

import sys
import pandas as pd

def añadir_zmax_a_csv(path_csv):
    df = pd.read_csv(path_csv)
    # Detectar columna de tipo OSM
    if "dpc_tipo_osm" in df.columns:
        col_tipo = "dpc_tipo_osm"
    elif "tipo_osm" in df.columns:
        col_tipo = "tipo_osm"
    else:
        raise ValueError("No se encontró columna de tipo OSM en el archivo")

    # Asignar Zmax según tipo
    df["Zmax"] = df[col_tipo].map(zmax_por_tipo).fillna(10).astype(int)
    # Agregar columna Z_inicial en 0
    df["Z_inicial"] = 0
    # Sobrescribir archivo
    df.to_csv(path_csv, index=False)
    print(f"Archivo actualizado: {path_csv}")

import os
import glob

if __name__ == "__main__":
    # Directorio de combinados
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    combinado_dir = os.path.join(root, "combinado_epc_dpc")
    pattern = os.path.join(combinado_dir, "*_combinado.csv")
    archivos = sorted(glob.glob(pattern))
    if not archivos:
        print(f"No se encontraron archivos *_combinado.csv en {combinado_dir}")
        sys.exit(1)
    for archivo in archivos:
        try:
            añadir_zmax_a_csv(archivo)
        except Exception as e:
            print(f"Error procesando {archivo}: {e}")