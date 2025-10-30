#!/usr/bin/env python3
"""
analizar_solucion.py

Script para analizar la solución del modelo de optimización y generar
un resumen detallado por comuna con todas las decisiones tomadas.

Genera archivo CSV con:
- Estaciones activadas por comuna
- Cargadores nuevos instalados
- Paneles fotovoltaicos instalados
- Demanda satisfecha y cobertura
- Energía solar vs red
"""

import os
import sys
import pandas as pd
import gurobipy as gp
from gurobipy import GRB

# Importar funciones del modelo principal
sys.path.insert(0, os.path.dirname(__file__))
from main import descubrir_comunas, cargar_sitios_comuna, definir_parametros



def extraer_solucion_gurobi(archivo_sol="solucion_completo_latex.sol", 
                             archivo_modelo="modelo_completo_latex.lp"):
    """
    Carga el modelo y la solución de Gurobi para extraer variables.
    
    Returns:
        dict: Diccionario con todas las variables y sus valores
    """
    print("\n" + "="*70)
    print("CARGANDO SOLUCIÓN DE GUROBI")
    print("="*70)
    
    # Verificar que existan los archivos
    if not os.path.exists(archivo_sol):
        print(f"✗ Error: No se encontró {archivo_sol}")
        print("  Ejecuta primero: python3 src/scripts/modelo_completo_latex.py")
        return None
    
    if not os.path.exists(archivo_modelo):
        print(f"✗ Error: No se encontró {archivo_modelo}")
        return None
    
    # Cargar modelo
    print(f"✓ Cargando modelo: {archivo_modelo}")
    model = gp.read(archivo_modelo)
    
    # Cargar solución
    print(f"✓ Cargando solución: {archivo_sol}")
    
    # Método correcto: parsear el archivo .sol manualmente
    variables = {}
    
    with open(archivo_sol, 'r') as f:
        for linea in f:
            linea = linea.strip()
            
            # Líneas de variables tienen formato: "nombre valor"
            if linea and not linea.startswith('#'):
                partes = linea.split()
                if len(partes) >= 2:
                    nombre_var = partes[0]
                    try:
                        valor = float(partes[1])
                        variables[nombre_var] = valor
                    except ValueError:
                        continue
    
    print(f"  - Total variables: {len(variables):,}")
    print(f"  - Variables no-cero: {sum(1 for v in variables.values() if abs(v) > 1e-6):,}")
    
    # Verificar que se cargaron variables
    if len(variables) == 0:
        print("✗ Error: No se pudieron extraer variables de la solución")
        print("  Verifica que el archivo .sol tenga el formato correcto")
        return None
    
    return variables

def parsear_nombre_variable(nombre):
    """
    Parsea el nombre de una variable de Gurobi.
    
    Ejemplos:
        "w[0,cerrillos]" -> ('w', 0, 'cerrillos', None)
        "x[0,cerrillos,1]" -> ('x', 0, 'cerrillos', 1)
        "phi_jm[cerrillos,1]" -> ('phi_jm', None, 'cerrillos', 1)
    """
    import re
    
    # Patrón para variables con índices [i,j,m]
    patron1 = r'(\w+)\[(\d+),([\w_]+),(\d+)\]'
    match = re.match(patron1, nombre)
    if match:
        tipo, i, j, m = match.groups()
        return (tipo, int(i), j, int(m))
    
    # Patrón para variables con índices [i,j]
    patron2 = r'(\w+)\[(\d+),([\w_]+)\]'
    match = re.match(patron2, nombre)
    if match:
        tipo, i, j = match.groups()
        return (tipo, int(i), j, None)
    
    # Patrón para variables con índices [j,m]
    patron3 = r'(\w+)\[([\w_]+),(\d+)\]'
    match = re.match(patron3, nombre)
    if match:
        tipo, j, m = match.groups()
        return (tipo, None, j, int(m))
    
    return (None, None, None, None)


def analizar_por_comuna(variables, comunas, datos_comunas, params):
    """
    Analiza la solución y genera resumen por comuna.
    
    Returns:
        DataFrame con métricas por comuna
    """
    print("\n" + "="*70)
    print("ANALIZANDO SOLUCIÓN POR COMUNA")
    print("="*70)
    
    M = params["M"]
    resultados = []
    
    for j in comunas:
        if j not in datos_comunas:
            continue
        
        df = datos_comunas[j]
        n_sitios = len(df)
        
        # Inicializar contadores
        estaciones_activadas = 0
        estaciones_nuevas = 0
        cargadores_iniciales = 0
        cargadores_nuevos = 0
        cargadores_totales = 0
        paneles_iniciales = 0
        paneles_nuevos = 0
        paneles_totales = 0
        demanda_total = 0
        demanda_satisfecha = 0
        demanda_insatisfecha = 0
        energia_solar = 0
        energia_red = 0
        
        # Recorrer todos los sitios de la comuna
        for i in range(n_sitios):
            row = df.iloc[i]
            
            # Infraestructura existente
            cargadores_iniciales += int(row.get('cargadores_iniciales', 0))
            paneles_iniciales += int(row.get('paneles_iniciales', 0))
            
            # Variables de decisión (mes M final)
            var_w = f"w[{i},{j}]"
            var_X = f"X[{i},{j},{M}]"
            var_Z = f"Z[{i},{j},{M}]"
            var_a = f"a[{i},{j},{M}]"
            
            if var_w in variables and variables[var_w] > 0.5:
                estaciones_activadas += 1
                if row.get('cargadores_iniciales', 0) == 0:
                    estaciones_nuevas += 1
            
            if var_X in variables:
                cargadores_totales += variables[var_X]
            
            if var_Z in variables:
                paneles_totales += variables[var_Z]
            
            # Acumular por todos los meses
            for m in range(1, M + 1):
                # Cargadores y paneles nuevos instalados
                var_x = f"x[{i},{j},{m}]"
                var_z = f"z[{i},{j},{m}]"
                
                if var_x in variables:
                    cargadores_nuevos += variables[var_x]
                
                if var_z in variables:
                    paneles_nuevos += variables[var_z]
                
                # Demanda
                var_d_sat = f"d_sat[{i},{j},{m}]"
                var_d_unsat = f"d_unsat[{i},{j},{m}]"
                
                demanda_sitio = row.get('demand_estimated', 0)
                demanda_total += demanda_sitio
                
                if var_d_sat in variables:
                    demanda_satisfecha += variables[var_d_sat]
                
                if var_d_unsat in variables:
                    demanda_insatisfecha += variables[var_d_unsat]
                
                # Energía
                var_s = f"s[{i},{j},{m}]"
                var_r = f"r[{i},{j},{m}]"
                
                if var_s in variables:
                    energia_solar += variables[var_s]
                
                if var_r in variables:
                    energia_red += variables[var_r]
        
        # Calcular métricas
        cobertura_pct = (demanda_satisfecha / demanda_total * 100) if demanda_total > 0 else 0
        energia_total = energia_solar + energia_red
        pct_renovable = (energia_solar / energia_total * 100) if energia_total > 0 else 0
        
        # Calcular phi (ponderador de equidad) del mes final
        var_phi = f"phi_jm[{j},{M}]"
        phi_final = variables.get(var_phi, 0)
        
        resultados.append({
            'comuna': j,
            'sitios_totales': n_sitios,
            'estaciones_activadas': int(estaciones_activadas),
            'estaciones_nuevas': int(estaciones_nuevas),
            'cargadores_iniciales': int(cargadores_iniciales),
            'cargadores_nuevos': int(cargadores_nuevos),
            'cargadores_totales': int(cargadores_totales),
            'paneles_iniciales': int(paneles_iniciales),
            'paneles_nuevos': int(paneles_nuevos),
            'paneles_totales': int(paneles_totales),
            'demanda_total': int(demanda_total),
            'demanda_satisfecha': int(demanda_satisfecha),
            'demanda_insatisfecha': int(demanda_insatisfecha),
            'cobertura_%': round(cobertura_pct, 2),
            'energia_solar_kWh': round(energia_solar, 2),
            'energia_red_kWh': round(energia_red, 2),
            'energia_total_kWh': round(energia_total, 2),
            'pct_renovable': round(pct_renovable, 2),
            'phi_final': round(phi_final, 4),
        })
    
    df_resultados = pd.DataFrame(resultados)
    
    # Ordenar por cobertura descendente
    df_resultados = df_resultados.sort_values('cobertura_%', ascending=False)
    
    return df_resultados


def generar_resumen_global(df_comunas, params):
    """
    Genera resumen global agregado de todas las comunas.
    """
    print("\n" + "="*70)
    print("RESUMEN GLOBAL DE LA SOLUCIÓN")
    print("="*70)
    
    # Totales
    total_estaciones = df_comunas['estaciones_activadas'].sum()
    total_estaciones_nuevas = df_comunas['estaciones_nuevas'].sum()
    total_cargadores_nuevos = df_comunas['cargadores_nuevos'].sum()
    total_cargadores = df_comunas['cargadores_totales'].sum()
    total_paneles_nuevos = df_comunas['paneles_nuevos'].sum()
    total_paneles = df_comunas['paneles_totales'].sum()
    
    total_demanda = df_comunas['demanda_total'].sum()
    total_satisfecha = df_comunas['demanda_satisfecha'].sum()
    cobertura_global = (total_satisfecha / total_demanda * 100) if total_demanda > 0 else 0
    
    total_solar = df_comunas['energia_solar_kWh'].sum()
    total_red = df_comunas['energia_red_kWh'].sum()
    total_energia = total_solar + total_red
    pct_renovable = (total_solar / total_energia * 100) if total_energia > 0 else 0
    
    print(f"\n📊 INFRAESTRUCTURA:")
    print(f"  • Estaciones activadas: {total_estaciones:,}")
    print(f"    - Nuevas: {total_estaciones_nuevas:,}")
    print(f"    - Existentes: {total_estaciones - total_estaciones_nuevas:,}")
    print(f"  • Cargadores totales: {total_cargadores:,}")
    print(f"    - Nuevos: {total_cargadores_nuevos:,}")
    print(f"  • Paneles FV totales: {total_paneles:,}")
    print(f"    - Nuevos: {total_paneles_nuevos:,}")
    
    print(f"\n📈 DEMANDA:")
    print(f"  • Demanda total: {total_demanda:,} clientes")
    print(f"  • Satisfecha: {total_satisfecha:,.0f} clientes ({cobertura_global:.1f}%)")
    print(f"  • Insatisfecha: {total_demanda - total_satisfecha:,.0f} clientes")
    
    print(f"\n⚡ ENERGÍA:")
    print(f"  • Total: {total_energia:,.0f} kWh")
    print(f"  • Solar: {total_solar:,.0f} kWh ({pct_renovable:.1f}%)")
    print(f"  • Red: {total_red:,.0f} kWh ({100-pct_renovable:.1f}%)")
    
    print(f"\n🏆 TOP 5 COMUNAS POR COBERTURA:")
    for idx, row in df_comunas.head(5).iterrows():
        print(f"  {idx+1}. {row['comuna']:20s}: {row['cobertura_%']:6.2f}% "
              f"({int(row['estaciones_activadas'])} estaciones, "
              f"{int(row['cargadores_totales'])} cargadores)")
    
    print(f"\n⚠️  BOTTOM 5 COMUNAS POR COBERTURA:")
    for idx, row in df_comunas.tail(5).iterrows():
        print(f"  {idx+1}. {row['comuna']:20s}: {row['cobertura_%']:6.2f}% "
              f"({int(row['estaciones_activadas'])} estaciones, "
              f"{int(row['cargadores_totales'])} cargadores)")
    
    # Verificar restricciones de equidad
    print(f"\n✓ VERIFICACIÓN RESTRICCIONES:")
    phi_max = df_comunas['phi_final'].max()
    phi_min = df_comunas['phi_final'].min()
    ratio_equidad = phi_max / max(phi_min, 0.0001)
    
    print(f"  • R17 (Cobertura mínima φ ≤ 0.30): ", end="")
    if phi_max <= 0.31:  # Tolerancia numérica
        print(f"✅ Cumple (φ_max = {phi_max:.4f})")
    else:
        print(f"❌ Viola (φ_max = {phi_max:.4f})")
    
    print(f"  • R16 (Equidad φ_j ≤ 2φ_l): ", end="")
    if ratio_equidad <= 2.1:  # Tolerancia numérica
        print(f"✅ Cumple (ratio = {ratio_equidad:.2f})")
    else:
        print(f"❌ Viola (ratio = {ratio_equidad:.2f})")
    
    return {
        'total_estaciones': total_estaciones,
        'total_cargadores_nuevos': total_cargadores_nuevos,
        'total_paneles_nuevos': total_paneles_nuevos,
        'cobertura_global_%': cobertura_global,
        'pct_renovable': pct_renovable,
    }


def main():
    """Función principal"""
    print("\n" + "="*70)
    print("ANÁLISIS DE SOLUCIÓN - MODELO INFRAESTRUCTURA CARGA VE")
    print("="*70)
    
    # Extraer solución de Gurobi
    variables = extraer_solucion_gurobi()
    if variables is None:
        return
    
    # Cargar datos de comunas
    print("\n✓ Cargando datos de comunas...")
    comunas = descubrir_comunas()
    datos_comunas = {}
    for j in comunas:
        df = cargar_sitios_comuna(j)
        if not df.empty:
            datos_comunas[j] = df
    
    # Definir parámetros (debe coincidir con el modelo ejecutado)
    params = definir_parametros(M=1)
    
    # Analizar por comuna
    df_comunas = analizar_por_comuna(variables, comunas, datos_comunas, params)
    
    # Guardar en CSV
    archivo_salida = "resumen_solucion_por_comuna.csv"
    df_comunas.to_csv(archivo_salida, index=False, encoding='utf-8')
    print(f"\n✓ Resumen guardado en: {archivo_salida}")
    
    # Generar resumen global
    resumen_global = generar_resumen_global(df_comunas, params)
    
    # Guardar resumen global en archivo separado
    df_global = pd.DataFrame([resumen_global])
    df_global.to_csv("resumen_global.csv", index=False)
    print(f"✓ Resumen global guardado en: resumen_global.csv")
    
    print("\n" + "="*70)
    print("✓ ANÁLISIS COMPLETADO")
    print("="*70)


if __name__ == "__main__":
    main()
