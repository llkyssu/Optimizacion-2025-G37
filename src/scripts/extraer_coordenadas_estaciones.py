#!/usr/bin/env python3
"""
extraer_coordenadas_estaciones.py

Script para extraer las coordenadas geográficas (lat, lon) de todas las 
estaciones activadas en la solución óptima del modelo de optimización.

Genera un archivo CSV con:
- ID estación
- Comuna
- Latitud
- Longitud
- Cargadores totales
- Paneles totales
- Estado (nueva/existente)
"""

import os
import sys
import pandas as pd
import glob

# Configurar rutas
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINADO_DIR = os.path.join(ROOT, "combinado_epc_dpc")

# Funciones auxiliares (copiadas del modelo original)
def descubrir_comunas():
    """Descubre comunas desde carpeta combinado_epc_dpc"""
    if not os.path.isdir(COMBINADO_DIR):
        raise FileNotFoundError(f"No se encontró carpeta {COMBINADO_DIR}")
    
    archivos = sorted(glob.glob(os.path.join(COMBINADO_DIR, "*.csv")))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos CSV en {COMBINADO_DIR}")
    
    comunas = [os.path.basename(f).replace(".csv", "") for f in archivos]
    return sorted(comunas)


def cargar_sitios_comuna(comuna):
    """Carga los sitios candidatos para una comuna desde su archivo CSV"""
    archivo = os.path.join(COMBINADO_DIR, f"{comuna}.csv")
    if not os.path.exists(archivo):
        return pd.DataFrame()
    return pd.read_csv(archivo)


def definir_parametros(M=1):
    """Define parámetros del modelo"""
    return {
        "M": M,
        "Pcap_default": 10,
        "Zmax_default": 20,
    }


def extraer_coordenadas_solucion(archivo_sol="solucion_completo_latex.sol"):
    """
    Extrae coordenadas de estaciones activadas desde la solución de Gurobi.
    
    Returns:
        DataFrame con coordenadas y características de estaciones activadas
    """
    print("\n" + "="*70)
    print("EXTRAYENDO COORDENADAS DE ESTACIONES ACTIVADAS")
    print("="*70)
    
    # Verificar que existe el archivo de solución
    if not os.path.exists(archivo_sol):
        print(f"✗ Error: No se encontró {archivo_sol}")
        print("  Ejecuta primero: python3 src/scripts/modelo_completo_latex.py")
        return None
    
    # Cargar solución parseando el archivo .sol
    print(f"\n✓ Cargando solución: {archivo_sol}")
    
    variables = {}
    with open(archivo_sol, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith('#'):
                partes = linea.split()
                if len(partes) >= 2:
                    nombre_var = partes[0]
                    try:
                        valor = float(partes[1])
                        variables[nombre_var] = valor
                    except ValueError:
                        continue
    
    print(f"  - Variables cargadas: {len(variables):,}")
    
    # Cargar datos de comunas
    print("\n✓ Cargando datos de comunas...")
    comunas = descubrir_comunas()
    datos_comunas = {}
    for j in comunas:
        df = cargar_sitios_comuna(j)
        if not df.empty:
            datos_comunas[j] = df
    
    params = definir_parametros(M=1)
    M = params["M"]
    
    # Extraer estaciones activadas
    print("\n✓ Identificando estaciones activadas...")
    
    estaciones_activadas = []
    
    for j in comunas:
        if j not in datos_comunas:
            continue
        
        df = datos_comunas[j]
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Verificar si la estación está activada (w[i,j] > 0.5)
            var_w = f"w[{i},{j}]"
            
            if var_w in variables and variables[var_w] > 0.5:
                # Estación activada - extraer información
                
                # Coordenadas
                lat = row.get('dpc_lat', row.get('epc_lat', None))
                lon = row.get('dpc_lon', row.get('epc_lon', None))
                
                if lat is None or lon is None:
                    print(f"  ⚠ Advertencia: Estación {i} en {j} sin coordenadas")
                    continue
                
                # Infraestructura
                cargadores_iniciales = int(row.get('cargadores_iniciales', 0))
                paneles_iniciales = int(row.get('paneles_iniciales', 0))
                
                # Valores finales (mes M)
                var_X = f"X[{i},{j},{M}]"
                var_Z = f"Z[{i},{j},{M}]"
                
                cargadores_totales = int(variables.get(var_X, 0))
                paneles_totales = int(variables.get(var_Z, 0))
                
                # Cargadores y paneles nuevos instalados
                cargadores_nuevos = cargadores_totales - cargadores_iniciales
                paneles_nuevos = paneles_totales - paneles_iniciales
                
                # Determinar si es nueva o existente
                estado = "Existente" if cargadores_iniciales > 0 else "Nueva"
                
                # Dirección si está disponible
                direccion = row.get('direccion', row.get('nombre_fantasia', 'Sin dirección'))
                
                # Capacidad máxima
                pcap = row.get('dpc_Pcap', params["Pcap_default"])
                zmax = row.get('dpc_Zmax', params["Zmax_default"])
                
                estaciones_activadas.append({
                    'id_sitio': i,
                    'comuna': j,
                    'latitud': float(lat),
                    'longitud': float(lon),
                    'direccion': direccion,
                    'estado': estado,
                    'cargadores_iniciales': cargadores_iniciales,
                    'cargadores_nuevos': cargadores_nuevos,
                    'cargadores_totales': cargadores_totales,
                    'capacidad_max_cargadores': int(pcap),
                    'paneles_iniciales': paneles_iniciales,
                    'paneles_nuevos': paneles_nuevos,
                    'paneles_totales': paneles_totales,
                    'capacidad_max_paneles': int(zmax),
                    'utilizacion_cargadores_%': round(cargadores_totales / pcap * 100, 1) if pcap > 0 else 0,
                    'utilizacion_paneles_%': round(paneles_totales / zmax * 100, 1) if zmax > 0 else 0,
                })
    
    if not estaciones_activadas:
        print("✗ No se encontraron estaciones activadas en la solución")
        return None
    
    df_estaciones = pd.DataFrame(estaciones_activadas)
    
    # Ordenar por comuna y luego por ID
    df_estaciones = df_estaciones.sort_values(['comuna', 'id_sitio'])
    
    print(f"\n✓ Estaciones activadas encontradas: {len(df_estaciones)}")
    print(f"  - Nuevas: {len(df_estaciones[df_estaciones['estado'] == 'Nueva'])}")
    print(f"  - Existentes: {len(df_estaciones[df_estaciones['estado'] == 'Existente'])}")
    
    return df_estaciones


def generar_resumen_geografico(df_estaciones):
    """
    Genera resumen estadístico por comuna.
    """
    print("\n" + "="*70)
    print("RESUMEN GEOGRÁFICO POR COMUNA")
    print("="*70)
    
    resumen = df_estaciones.groupby('comuna').agg({
        'id_sitio': 'count',
        'cargadores_totales': 'sum',
        'paneles_totales': 'sum',
        'latitud': 'mean',
        'longitud': 'mean'
    }).rename(columns={
        'id_sitio': 'estaciones',
        'latitud': 'lat_centro',
        'longitud': 'lon_centro'
    })
    
    resumen = resumen.sort_values('estaciones', ascending=False)
    
    print("\nTop 10 comunas por número de estaciones:")
    print(resumen.head(10).to_string())
    
    return resumen


def generar_archivo_geojson(df_estaciones, archivo_salida="estaciones_activadas.geojson"):
    """
    Genera archivo GeoJSON compatible con herramientas de mapeo (QGIS, Leaflet, etc.)
    """
    import json
    
    features = []
    
    for idx, row in df_estaciones.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitud'], row['latitud']]  # GeoJSON usa [lon, lat]
            },
            "properties": {
                "id": f"{row['comuna']}_{row['id_sitio']}",
                "comuna": row['comuna'],
                "direccion": row['direccion'],
                "estado": row['estado'],
                "cargadores_totales": row['cargadores_totales'],
                "cargadores_nuevos": row['cargadores_nuevos'],
                "paneles_totales": row['paneles_totales'],
                "paneles_nuevos": row['paneles_nuevos'],
                "utilizacion_cargadores_%": row['utilizacion_cargadores_%'],
                "utilizacion_paneles_%": row['utilizacion_paneles_%']
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "crs": {
            "type": "name",
            "properties": {
                "name": "EPSG:4326"  # WGS84
            }
        }
    }
    
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Archivo GeoJSON generado: {archivo_salida}")
    print(f"  Puedes visualizarlo en: https://geojson.io/")


def main():
    """Función principal"""
    print("\n" + "="*70)
    print("EXTRACTOR DE COORDENADAS - ESTACIONES ACTIVADAS")
    print("="*70)
    
    # Extraer coordenadas
    df_estaciones = extraer_coordenadas_solucion()
    
    if df_estaciones is None:
        return
    
    # Guardar CSV principal
    archivo_csv = "estaciones_activadas_coordenadas.csv"
    df_estaciones.to_csv(archivo_csv, index=False, encoding='utf-8')
    print(f"\n✓ Archivo CSV guardado: {archivo_csv}")
    
    # Generar resumen por comuna
    resumen = generar_resumen_geografico(df_estaciones)
    resumen.to_csv("resumen_geografico_por_comuna.csv")
    print(f"✓ Resumen por comuna guardado: resumen_geografico_por_comuna.csv")
    
    # Generar GeoJSON para visualización
    generar_archivo_geojson(df_estaciones)
    
    # Estadísticas finales
    print("\n" + "="*70)
    print("ESTADÍSTICAS FINALES")
    print("="*70)
    
    total_cargadores = df_estaciones['cargadores_totales'].sum()
    total_paneles = df_estaciones['paneles_totales'].sum()
    nuevos_cargadores = df_estaciones['cargadores_nuevos'].sum()
    nuevos_paneles = df_estaciones['paneles_nuevos'].sum()
    
    print(f"\n📍 UBICACIÓN:")
    print(f"  • Total estaciones: {len(df_estaciones)}")
    print(f"  • Comunas con estaciones: {df_estaciones['comuna'].nunique()}")
    print(f"  • Rango latitud: [{df_estaciones['latitud'].min():.4f}, {df_estaciones['latitud'].max():.4f}]")
    print(f"  • Rango longitud: [{df_estaciones['longitud'].min():.4f}, {df_estaciones['longitud'].max():.4f}]")
    
    print(f"\n⚡ INFRAESTRUCTURA:")
    print(f"  • Cargadores totales: {total_cargadores:,}")
    print(f"    - Nuevos: {nuevos_cargadores:,}")
    print(f"    - Existentes: {total_cargadores - nuevos_cargadores:,}")
    print(f"  • Paneles totales: {total_paneles:,}")
    print(f"    - Nuevos: {nuevos_paneles:,}")
    print(f"    - Existentes: {total_paneles - nuevos_paneles:,}")
    
    print(f"\n📊 UTILIZACIÓN PROMEDIO:")
    print(f"  • Cargadores: {df_estaciones['utilizacion_cargadores_%'].mean():.1f}%")
    print(f"  • Paneles: {df_estaciones['utilizacion_paneles_%'].mean():.1f}%")
    
    print("\n" + "="*70)
    print("✓ PROCESO COMPLETADO")
    print("="*70)
    print("\n💡 Archivos generados:")
    print(f"  1. {archivo_csv} - Datos completos en CSV")
    print(f"  2. resumen_geografico_por_comuna.csv - Agregado por comuna")
    print(f"  3. estaciones_activadas.geojson - Para visualización en mapas")
    print("\n📍 Visualiza el GeoJSON en: https://geojson.io/")
    print("   O impórtalo en QGIS/ArcGIS para análisis espacial")


if __name__ == "__main__":
    main()
