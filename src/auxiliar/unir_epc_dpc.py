import pandas as pd
import geopandas as gpd
import os

# Parámetros
CRS_GEOGRAFICO = "EPSG:4326"
CRS_METRICO = "EPSG:32719"
RADIOS_METROS = [500, 1000, 1500, 2000, 3000, 5000]

# Rutas
DIR_DPC = "dpc_estimados_csv"
DIR_ELECTRO = "electrolineras_por_comuna"


def combinar_electrolineras_dpc(df_candidatas, df_electro):
    # Prepara GeoDataFrames
    gdf_candidatas = gpd.GeoDataFrame(
        df_candidatas.copy(),
        geometry=gpd.points_from_xy(df_candidatas.lon, df_candidatas.lat),
        crs=CRS_GEOGRAFICO
    ).to_crs(CRS_METRICO)

    gdf_electro = gpd.GeoDataFrame(
        df_electro.copy(),
        geometry=gpd.points_from_xy(df_electro.lon, df_electro.lat),
        crs=CRS_GEOGRAFICO
    ).to_crs(CRS_METRICO)

    filas_combinadas = []
    usadas_candidatas = set()

    # 1. Para cada electrolinera, buscar la candidata más cercana (sin repetir candidata)
    if len(gdf_candidatas) > 0:
        candidatas_disponibles = set(gdf_candidatas.index)
        for idx_e, row_e in gdf_electro.iterrows():
            if not candidatas_disponibles:
                # Si ya no quedan candidatas, asociar a null
                row_c = None
                dist = None
                idx_cercano = None
            else:
                candidatas = gdf_candidatas.loc[list(candidatas_disponibles)].copy()
                candidatas['dist'] = candidatas.geometry.distance(row_e.geometry)
                idx_cercano = candidatas['dist'].idxmin()
                row_c = candidatas.loc[idx_cercano]
                dist = candidatas.loc[idx_cercano, 'dist']
                candidatas_disponibles.remove(idx_cercano)
                usadas_candidatas.add(idx_cercano)
            fila = {}
            # Datos electrolinera (prefijo electro_)
            for col in df_electro.columns:
                fila[f"electro_{col}"] = row_e[col]
            # Datos candidata (prefijo dpc_)
            if row_c is not None:
                for col in df_candidatas.columns:
                    fila[f"dpc_{col}"] = row_c[col]
            else:
                for col in df_candidatas.columns:
                    fila[f"dpc_{col}"] = '' if col != 'Zcap' else 0
            fila["distancia_m"] = dist
            filas_combinadas.append(fila)
    else:
        # No hay candidatas, solo electrolineras
        for idx_e, row_e in gdf_electro.iterrows():
            fila = {}
            for col in df_electro.columns:
                fila[f"electro_{col}"] = row_e[col]
            for col in df_candidatas.columns:
                fila[f"dpc_{col}"] = '' if col != 'Zcap' else 0
            fila["distancia_m"] = None
            filas_combinadas.append(fila)

    # 2. Para cada candidata que no fue usada, agregarla con campos de electrolinera vacíos/0
    for idx_c, row_c in gdf_candidatas.iterrows():
        if idx_c in usadas_candidatas:
            continue
        fila = {}
        for col in df_electro.columns:
            fila[f"electro_{col}"] = '' if col != 'Zcap' else 0
        for col in df_candidatas.columns:
            fila[f"dpc_{col}"] = row_c[col]
        fila["distancia_m"] = None
        filas_combinadas.append(fila)

    df_combinado = pd.DataFrame(filas_combinadas)
    return df_combinado


def detectar_columnas_electrolineras(df):
    # Detecta columnas de latitud, longitud y cargadores
    lat_col = next((c for c in df.columns if c.lower() in ['lat', 'latitud']), None)
    lon_col = next((c for c in df.columns if c.lower() in ['lon', 'longitud', 'lng']), None)
    zcap_col = next((c for c in df.columns if c.lower() in ['zcap', 'numero de cargadores', 'n_cargadores', 'cargadores']), None)
    if not lat_col or not lon_col or not zcap_col:
        raise ValueError(f"No se detectaron columnas de coordenadas/cargadores en: {df.columns}")
    return lat_col, lon_col, zcap_col


def main():
    comunas = [f.replace('.csv','') for f in os.listdir(DIR_DPC) if f.endswith('.csv')]
    output_dir = "combinado_epc_dpc_por_comuna"
    os.makedirs(output_dir, exist_ok=True)
    for comuna in comunas:
        file_dpc = os.path.join(DIR_DPC, f"{comuna}.csv")
        file_electro = os.path.join(DIR_ELECTRO, f"{comuna}.csv")
        if not os.path.exists(file_dpc):
            print(f"Saltando {comuna}: falta archivo de candidatas.")
            continue
        df_candidatas = pd.read_csv(file_dpc)
        # Leer electrolineras, detectando delimitador
        if os.path.exists(file_electro):
            try:
                df_electro = pd.read_csv(file_electro)
                if df_electro.shape[1] == 1:
                    # Si solo hay una columna, probablemente es delimitador ;
                    df_electro = pd.read_csv(file_electro, delimiter=';')
            except Exception:
                df_electro = pd.read_csv(file_electro, delimiter=';')
            # Detectar columnas y estandarizar
            try:
                lat_col, lon_col, zcap_col = detectar_columnas_electrolineras(df_electro)
            except Exception as e:
                print(f"Saltando {comuna}: {e}")
                # Si no se detectan columnas, se asume que no hay electrolineras válidas
                df_electro = pd.DataFrame(columns=['lat','lon','Zcap'])
            else:
                df_electro = df_electro.rename(columns={lat_col: 'lat', lon_col: 'lon', zcap_col: 'Zcap'})
                # Asegurar tipos
                df_electro['lat'] = pd.to_numeric(df_electro['lat'], errors='coerce')
                df_electro['lon'] = pd.to_numeric(df_electro['lon'], errors='coerce')
                df_electro['Zcap'] = pd.to_numeric(df_electro['Zcap'], errors='coerce')
                df_electro = df_electro.dropna(subset=['lat', 'lon', 'Zcap'])
        else:
            # No hay archivo de electrolineras, crear DataFrame vacío con columnas estándar
            df_electro = pd.DataFrame(columns=['lat','lon','Zcap'])
        if 'Zcap' not in df_candidatas.columns:
            print(f"Saltando {comuna}: candidatas sin columna Zcap.")
            continue
        # Generar tabla combinada
        df_combinado = combinar_electrolineras_dpc(df_candidatas, df_electro)
        # Renombrar columnas según lo solicitado
        df_combinado = df_combinado.rename(columns={
            'electro_Zcap': 'cargadores_iniciales',
            'dpc_Zcap': 'Pcap'
        })
        # Limitar cargadores_iniciales a que no sea mayor que Pcap (solo si ambos son numéricos y no nulos)
        if 'cargadores_iniciales' in df_combinado.columns and 'Pcap' in df_combinado.columns:
            def limitar_cargadores(row):
                try:
                    ci = float(row['cargadores_iniciales'])
                    pc = float(row['Pcap'])
                    if not pd.isna(ci) and not pd.isna(pc):
                        return int(min(ci, pc))
                    else:
                        return int(row['cargadores_iniciales']) if row['cargadores_iniciales'] != '' else 0
                except Exception:
                    return 0 if row['cargadores_iniciales'] == '' else int(float(row['cargadores_iniciales']))
            df_combinado['cargadores_iniciales'] = df_combinado.apply(limitar_cargadores, axis=1)
        out_file = os.path.join(output_dir, f"{comuna}_combinado.csv")
        df_combinado.to_csv(out_file, index=False, encoding="utf-8-sig")
        print(f"Guardado: {out_file}")
    print(f"¡Listo! Tablas combinadas por comuna en '{output_dir}'")

if __name__ == "__main__":
    main()