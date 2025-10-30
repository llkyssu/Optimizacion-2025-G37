#!/usr/bin/env python3
"""
Pre-procesamiento para el modelo de optimización.
Calcula la demanda estimada para cada sitio candidato y la guarda
en nuevos archivos CSV.

Qué hace:
 - Carga los archivos CSV en `combinado_epc_dpc_por_comuna/`
 - Usa la función `estimate_demand_per_site` para calcular la demanda
 - Guarda nuevos archivos CSV en `data_with_demand/` que incluyen
   todas las columnas originales de `load_sites_for_comuna` más
   una nueva columna "demand_estimated".

Uso:
    python src/scripts/4a_calculate_demand.py

Salida:
    - Varios archivos en `data_with_demand/*.csv`
"""

import os
import glob
import sys
import pandas as pd

# --- Definición de Constantes y Rutas ---

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINADO_DIR = os.path.join(ROOT, "combinado_epc_dpc")


# Directorio de salida para los datos pre-procesados
OUTPUT_DIR = os.path.join(ROOT, "data_with_demand")


# Parque vehicular 2023 por comuna (INE)
PARQUE_VEHICULAR_2023 = {
    "cerrillos": 35000, "cerro_navia": 42000, "colina": 58000, "conchali": 45000,
    "el_bosque": 52000, "estacion_central": 48000, "huechuraba": 38000, "independencia": 28000,
    "la_cisterna": 32000, "la_florida": 125000, "la_granja": 38000, "la_pintana": 55000,
    "la_reina": 42000, "lampa": 35000, "las_condes": 135000, "lo_barnechea": 48000,
    "lo_espejo": 35000, "lo_prado": 38000, "macul": 42000, "maipu": 185000,
    "nunoa": 75000, "padre_hurtado": 22000, "pedro_aguirre_cerda": 32000, "penaflor": 28000,
    "penalolen": 78000, "pirque": 12000, "providencia": 52000, "pudahuel": 65000,
    "puente_alto": 195000, "quilicura": 72000, "quinta_normal": 38000, "recoleta": 58000,
    "renca": 45000, "san_bernardo": 98000, "san_joaquin": 32000, "san_jose_de_maipo": 8000,
    "san_miguel": 35000, "san_ramon": 28000, "santiago": 65000, "vitacura": 48000,
}

# --- Funciones de Carga de Datos (Originales) ---

def discover_comunas():
    # Procesar todos los archivos .csv en combinado_epc_dpc
    if os.path.isdir(COMBINADO_DIR):
        files = sorted(glob.glob(os.path.join(COMBINADO_DIR, "*.csv")))
        comunas = [os.path.splitext(os.path.basename(f))[0] for f in files]
        return dict(zip(comunas, files))
    else:
        raise FileNotFoundError("No se encontró carpeta `combinado_epc_dpc` en el repo")


def load_sites_for_comuna(file_path):
    # Lee CSV y devuelve lista de dicts con columnas relevantes
    # Detecta si es archivo combinado (tiene electro_ y dpc_ prefijos) o simple
    df = pd.read_csv(file_path)
    
    # Detectar tipo de archivo
    is_combinado = "dpc_lon" in df.columns and "dpc_lat" in df.columns
    
    if is_combinado:
        # Archivo combinado: usar columnas dpc_ para candidatas y cargadores_iniciales para epsilon
        expected = ["dpc_tipo_osm", "dpc_Pcap", "dpc_lon", "dpc_lat", "dpc_name", "cargadores_iniciales", "distancia_m"]
        for c in expected:
            if c not in df.columns:
                if c == "cargadores_iniciales":
                    df[c] = 0
                elif c == "distancia_m":
                    df[c] = None
                else:
                    df[c] = None
        
        sites = []
        for idx, row in df.iterrows():
            if pd.isna(row.get("dpc_lon")) or pd.isna(row.get("dpc_lat")):
                continue
            try:
                pcap = int(row.get("Pcap")) if not pd.isna(row.get("Pcap")) else None
            except Exception: pcap = None
            try:
                epsilon = int(row.get("cargadores_iniciales", 0))
            except Exception: epsilon = 0
            try:
                dist = float(row.get("distancia_m")) if not pd.isna(row.get("distancia_m")) else None
            except Exception: dist = None
            
            site = {
                "id": int(idx),
                "name": row.get("dpc_name") if not pd.isna(row.get("dpc_name")) else f"site_{idx}",
                "tipo": row.get("dpc_tipo_osm") if not pd.isna(row.get("dpc_tipo_osm")) else "other",
                "Zcap": pcap,
                "lon": row.get("dpc_lon"),
                "lat": row.get("dpc_lat"),
                "q": 1 if epsilon > 0 else 0,
                "epsilon": epsilon,
                "delta": 0,
                "distancia_asignacion": dist,
            }
            sites.append(site)
    else:
        # Archivo simple (dpc_estimados_csv o dpc_csv): usar columnas sin prefijo
        expected = ["tipo_osm", "Zcap", "lon", "lat", "name"]
        for c in expected:
            if c not in df.columns: df[c] = None
        
        sites = []
        for idx, row in df.iterrows():
            try:
                zcap = int(row.get("Zcap")) if not pd.isna(row.get("Zcap")) else None
            except Exception: zcap = None
            
            site = {
                "id": int(idx),
                "name": row.get("name") if not pd.isna(row.get("name")) else f"site_{idx}",
                "tipo": row.get("tipo_osm") if not pd.isna(row.get("tipo_osm")) else "other",
                "Zcap": zcap,
                "lon": row.get("lon"),
                "lat": row.get("lat"),
                "q": 0,
                "epsilon": 0,
                "delta": 0,
                "distancia_asignacion": None,
            }
            sites.append(site)
    
    return sites

# --- Función de Estimación de Demanda (Original) ---

def estimate_demand_per_site(site_dict, comuna):
    """
    Estima demanda realista basada en:
     - Parque vehicular de la comuna
     - 40% electrificación proyectada 2040
     - 4 cargas/mes por EV (60% en puntos públicos)
     - Peso del sitio según tipo, capacidad y si ya tiene cargadores
    
    Args:
        site_dict: dict con keys {tipo, epsilon, Zcap, ...}
        comuna: str nombre comuna
    
    Returns:
        int: demanda mensual (sesiones de carga)
    """
    # Demanda base de comuna
    parque_total = PARQUE_VEHICULAR_2023.get(comuna, 30000)
    parque_ev_2040 = parque_total * 0.40  # 40% serán EV
    demanda_comuna_total = parque_ev_2040 * 4.0 * 0.60  # 4 cargas/mes, 60% públicas
    
    # Peso del sitio
    w = 1.0
    
    # Factor 1: Sitios existentes atraen más demanda (usuarios ya conocen)
    if site_dict.get("epsilon", 0) > 0:
        w *= 2.5
    
    # Factor 2: Capacidad espacial
    zcap = site_dict.get("Zcap")
    if zcap and zcap > 0:
        w *= (1.0 + 0.05 * zcap)
    
    # Factor 3: Tipo de sitio
    tipo = site_dict.get("tipo", "other")
    tipo_weights = {
        "charging_station": 2.0, "mall": 1.8, "supermarket": 1.5,
        "fuel": 1.4, "parking": 1.3, "university": 1.2, "hospital": 1.0,
        "office": 0.8, "commercial": 0.7, "retail": 0.6, "car_wash": 0.4,
        "stadium": 1.1, "other": 0.5,
    }
    w *= tipo_weights.get(tipo, 0.5)
    
    # Fracción aproximada (asume ~150 sitios/comuna, peso promedio 1.2)
    avg_sites = 150
    avg_weight = 1.2
    fraction = w / (avg_sites * avg_weight)
    
    demanda_sitio = (demanda_comuna_total * fraction) * 0.3  # Factor conservador
    
    return max(1, int(round(demanda_sitio)))


# --- Función Principal (Nueva) ---

def main():
    print("Ejecutando script de pre-cálculo de demanda...")
    print(f"Directorio raíz: {ROOT}")



    # Descubrir comunas
    try:
        mapping = discover_comunas()
    except Exception as e:
        print(f"Error al localizar datos de comunas: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Se procesarán {len(mapping)} comunas...")
    total_sites = 0
    total_demand = 0


    # Procesar cada comuna y añadir/actualizar solo la columna demand_estimated
    for comuna, path in mapping.items():
        try:
            df = pd.read_csv(path)
            # Calcular demanda solo para filas válidas (con dpc_lon y dpc_lat)
            mask_valid = (~df["dpc_lon"].isna()) & (~df["dpc_lat"].isna())
            demandas = {}
            for idx, row in df[mask_valid].iterrows():
                site_data = {
                    "id": idx,
                    "name": row.get("dpc_name") if not pd.isna(row.get("dpc_name")) else f"site_{idx}",
                    "tipo": row.get("dpc_tipo_osm") if not pd.isna(row.get("dpc_tipo_osm")) else "other",
                    "Zcap": int(row.get("Pcap")) if not pd.isna(row.get("Pcap")) else None,
                    "lon": row.get("dpc_lon"),
                    "lat": row.get("dpc_lat"),
                    "q": 1 if (not pd.isna(row.get("cargadores_iniciales")) and int(row.get("cargadores_iniciales")) > 0) else 0,
                    "epsilon": int(row.get("cargadores_iniciales")) if not pd.isna(row.get("cargadores_iniciales")) else 0,
                    "delta": 0,
                    "distancia_asignacion": row.get("distancia_m") if "distancia_m" in row else None,
                }
                demanda = estimate_demand_per_site(site_data, comuna)
                demandas[idx] = demanda
                total_demand += demanda
            total_sites += len(demandas)

            # Solo añadir/actualizar la columna demand_estimated
            df["demand_estimated"] = df.index.map(lambda idx: demandas.get(idx, None))
            df.to_csv(path, index=False, encoding="utf-8")
            print(f"Archivo actualizado: {path}")

        except Exception as e:
            print(f"Error procesando {comuna} desde {path}: {e}", file=sys.stderr)

    print("\nProceso completado.")
    print(f"Total de sitios procesados: {total_sites}")
    print(f"Demanda total estimada: {total_demand:,.0f} sesiones/mes")
    print(f"Archivos actualizados en sus ubicaciones originales.")


if __name__ == "__main__":
    main()