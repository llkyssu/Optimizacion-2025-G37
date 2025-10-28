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

def asignar_electrolineras_a_candidatas(df_candidatas, df_electro, radios):
    # Prepara GeoDataFrames
    gdf_candidatas = gpd.GeoDataFrame(
        df_candidatas.copy(),
        geometry=gpd.points_from_xy(df_candidatas.lon, df_candidatas.lat),
        crs=CRS_GEOGRAFICO
    ).to_crs(CRS_METRICO)
    gdf_candidatas['cargadores_asignados'] = 0
    gdf_candidatas['asignaciones'] = [[] for _ in range(len(gdf_candidatas))]

    gdf_electro = gpd.GeoDataFrame(
        df_electro.copy(),
        geometry=gpd.points_from_xy(df_electro.lon, df_electro.lat),
        crs=CRS_GEOGRAFICO
    ).to_crs(CRS_METRICO)
    gdf_electro['asignada'] = False
    gdf_electro['id_candidata'] = None
    gdf_electro['distancia'] = None

    # 1. Intentar asignar respetando cupo
    for radio in radios:
        for idx_e, row_e in gdf_electro[~gdf_electro['asignada']].iterrows():
            candidatas_cerca = gdf_candidatas[gdf_candidatas.geometry.distance(row_e.geometry) <= radio]
            if candidatas_cerca.empty:
                continue
            candidatas_cerca = candidatas_cerca.copy()
            candidatas_cerca['dist'] = candidatas_cerca.geometry.distance(row_e.geometry)
            candidatas_cerca = candidatas_cerca.sort_values('dist')
            for idx_c, row_c in candidatas_cerca.iterrows():
                max_cupo = row_c['Zcap']
                asignados = row_c['cargadores_asignados']
                z_electro = row_e['Zcap'] if 'Zcap' in row_e else 1
                cupo_disponible = max_cupo - asignados
                if cupo_disponible <= 0:
                    continue
                asignar = min(z_electro, cupo_disponible)
                gdf_candidatas.at[idx_c, 'cargadores_asignados'] += asignar
                gdf_candidatas.at[idx_c, 'asignaciones'].append(idx_e)
                gdf_electro.at[idx_e, 'asignada'] = True
                gdf_electro.at[idx_e, 'id_candidata'] = idx_c
                gdf_electro.at[idx_e, 'distancia'] = candidatas_cerca.loc[idx_c, 'dist']
                break

    # 2. Forzar match para los no asignados (a la más cercana, aunque supere cupo)
    for idx_e, row_e in gdf_electro[~gdf_electro['asignada']].iterrows():
        candidatas_todas = gdf_candidatas.copy()
        candidatas_todas['dist'] = candidatas_todas.geometry.distance(row_e.geometry)
        idx_cercano = candidatas_todas['dist'].idxmin()
        gdf_candidatas.at[idx_cercano, 'cargadores_asignados'] += row_e['Zcap'] if 'Zcap' in row_e else 1
        gdf_candidatas.at[idx_cercano, 'asignaciones'].append(idx_e)
        gdf_electro.at[idx_e, 'asignada'] = True
        gdf_electro.at[idx_e, 'id_candidata'] = idx_cercano
        gdf_electro.at[idx_e, 'distancia'] = candidatas_todas.loc[idx_cercano, 'dist']

    return gdf_electro, gdf_candidatas


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
    output_dir = "asignaciones_por_comuna"
    os.makedirs(output_dir, exist_ok=True)
    for comuna in comunas:
        file_dpc = os.path.join(DIR_DPC, f"{comuna}.csv")
        file_electro = os.path.join(DIR_ELECTRO, f"{comuna}.csv")
        if not os.path.exists(file_dpc) or not os.path.exists(file_electro):
            print(f"Saltando {comuna}: falta archivo.")
            continue
        df_candidatas = pd.read_csv(file_dpc)
        # Leer electrolineras, detectando delimitador
        try:
            df_electro = pd.read_csv(file_electro)
        except Exception:
            df_electro = pd.read_csv(file_electro, delimiter=';')
        # Detectar columnas y estandarizar
        try:
            lat_col, lon_col, zcap_col = detectar_columnas_electrolineras(df_electro)
        except Exception as e:
            print(f"Saltando {comuna}: {e}")
            continue
        df_electro = df_electro.rename(columns={lat_col: 'lat', lon_col: 'lon', zcap_col: 'Zcap'})
        # Asegurar tipos
        df_electro['lat'] = pd.to_numeric(df_electro['lat'], errors='coerce')
        df_electro['lon'] = pd.to_numeric(df_electro['lon'], errors='coerce')
        df_electro['Zcap'] = pd.to_numeric(df_electro['Zcap'], errors='coerce')
        df_electro = df_electro.dropna(subset=['lat', 'lon', 'Zcap'])
        if 'Zcap' not in df_candidatas.columns:
            print(f"Saltando {comuna}: candidatas sin columna Zcap.")
            continue
        if 'Zcap' not in df_electro.columns:
            print(f"Saltando {comuna}: electrolineras sin columna Zcap tras estandarizar.")
            continue
        gdf_electro, gdf_candidatas = asignar_electrolineras_a_candidatas(df_candidatas, df_electro, RADIOS_METROS)
        # Crear columnas finales
        gdf_electro['cargadores'] = gdf_electro['Zcap'] if 'Zcap' in gdf_electro.columns else 1
        gdf_electro['infraestructura'] = gdf_electro['cargadores'] > 0
        # Guardar tabla por comuna
        out_file = os.path.join(output_dir, f"{comuna}_asignacion.csv")
        columnas_finales = list(df_electro.columns) + ['id_candidata', 'distancia', 'cargadores', 'infraestructura']
        gdf_electro[columnas_finales].to_csv(out_file, index=False, encoding="utf-8-sig")
        print(f"Guardado: {out_file}")
    print(f"¡Listo! Tablas por comuna en '{output_dir}'")

if __name__ == "__main__":
    main()