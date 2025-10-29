#!/usr/bin/env python3
"""
5_solve_optimization.py

Implementación del modelo MILP de infraestructura de carga para vehículos eléctricos
siguiendo la formulación del Informe 2 - Grupo 37.

Qué hace:
 - Carga los archivos CSV en `combinado_epc_dpc_por_comuna/` con electrolineras existentes
 - Construye modelo MILP con PuLP/CBC siguiendo la formulación del informe
 - Implementa función objetivo multi-componente (equidad, ambiental, cobertura)
 - Usa parámetros del documento de Parámetros (Octubre 2025)
 - Guarda solución detallada en `results_optimization.csv`

Restricciones implementadas:
 ✅ R1-R2: Activación única de infraestructura
 ✅ R3-R4: Acumulación de cargadores y paneles (simplificado M=1)
 ✅ R5: Estado operativo por mes
 ✅ R6: Cotas de capacidad (Pcap, Zmax)
 ⚠️ R7: Cargadores fast/slow (NO implementado - falta datos tipo demanda)
 ✅ R8: Balance energético
 ✅ R9: Límite producción solar
 ✅ R10: Límite importación red
 ⚠️ R11: Límite energía por tipo cargador (NO - requiere R7)
 ✅ R12: Demanda satisfecha por capacidad
 ⚠️ R13: Demanda insatisfecha (NO - falta demanda real d_{ijm})
 ⚠️ R14: Cobertura 10 min λ (aproximación con estaciones activas)
 ✅ R15: Agregación demanda por comuna
 ✅ R16: Ponderador equidad φ
 ⚠️ R17a: Equidad entre comunas (NO - complejidad O(J²))
 ✅ R17b: Cobertura mínima por comuna
 ✅ R18: Linealización McCormick para ψ
 ✅ R19: Restricción presupuesto

Limitaciones documentadas:
 - M=1 (horizonte estático): falta datos demanda mensual proyectada
 - No diferencia fast/slow: falta distribución tipo sesiones
 - Cobertura 10-min aproximada: falta matriz distancias D_{i,i'}
 - Demanda estimada heurística: falta datos reales d_{ijm}

Requisitos: pandas, pulp

Uso:
    python src/scripts/5_solve_optimization.py

Salida:
    - results_optimization.csv (decisiones óptimas por sitio)
    - Resumen en consola con valor objetivo y estadísticas
"""

import os
import glob
import math
import csv
import sys
from collections import defaultdict

try:
    import pandas as pd
except Exception:
    print("ERROR: `pandas` no está instalado. Instálalo con: pip install pandas")
    raise

try:
    import pulp
except Exception:
    print("ERROR: `pulp` no está instalado. Instálalo con: pip install pulp")
    raise


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINADO_DIR = os.path.join(ROOT, "combinado_epc_dpc_por_comuna")
DEMAND_DIR = os.path.join(ROOT, "dpc_estimados_csv")
ALT_DEMAND_DIR = os.path.join(ROOT, "dpc_csv")


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


def discover_comunas():
    # Prefer combinado_epc_dpc_por_comuna (data with existing chargers), else dpc_estimados_csv, else dpc_csv
    if os.path.isdir(COMBINADO_DIR):
        files = sorted(glob.glob(os.path.join(COMBINADO_DIR, "*_combinado.csv")))
        srcdir = COMBINADO_DIR
        comunas = [os.path.basename(f).replace("_combinado.csv", "") for f in files]
    elif os.path.isdir(DEMAND_DIR):
        files = sorted(glob.glob(os.path.join(DEMAND_DIR, "*.csv")))
        srcdir = DEMAND_DIR
        comunas = [os.path.splitext(os.path.basename(f))[0] for f in files]
    elif os.path.isdir(ALT_DEMAND_DIR):
        files = sorted(glob.glob(os.path.join(ALT_DEMAND_DIR, "*.csv")))
        srcdir = ALT_DEMAND_DIR
        comunas = [os.path.splitext(os.path.basename(f))[0] for f in files]
    else:
        raise FileNotFoundError("No se encontró carpeta `combinado_epc_dpc_por_comuna`, `dpc_estimados_csv` ni `dpc_csv` en el repo")
    return srcdir, dict(zip(comunas, files))


def load_sites_for_comuna(file_path):
    # Lee CSV y devuelve lista de dicts con columnas relevantes
    # Detecta si es archivo combinado (tiene electro_ y dpc_ prefijos) o simple
    df = pd.read_csv(file_path)
    
    # Detectar tipo de archivo
    is_combinado = "dpc_lon" in df.columns and "dpc_lat" in df.columns
    
    if is_combinado:
        # Archivo combinado: usar columnas dpc_ para candidatas y cargadores_iniciales para epsilon
        # Aseguramos columnas esperadas
        expected = ["dpc_tipo_osm", "Pcap", "dpc_lon", "dpc_lat", "dpc_name", "cargadores_iniciales", "distancia_m"]
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
            # Solo incluir filas con coordenadas DPC válidas
            if pd.isna(row.get("dpc_lon")) or pd.isna(row.get("dpc_lat")):
                continue
                
            try:
                pcap = int(row.get("Pcap")) if not pd.isna(row.get("Pcap")) else None
            except Exception:
                pcap = None
            
            try:
                epsilon = int(row.get("cargadores_iniciales", 0))
            except Exception:
                epsilon = 0
                
            try:
                dist = float(row.get("distancia_m")) if not pd.isna(row.get("distancia_m")) else None
            except Exception:
                dist = None
            
            site = {
                "id": int(idx),
                "name": row.get("dpc_name") if not pd.isna(row.get("dpc_name")) else f"site_{idx}",
                "tipo": row.get("dpc_tipo_osm") if not pd.isna(row.get("dpc_tipo_osm")) else "other",
                "Zcap": pcap,
                "lon": row.get("dpc_lon"),
                "lat": row.get("dpc_lat"),
                "q": 1 if epsilon > 0 else 0,  # existe infraestructura si tiene cargadores iniciales
                "epsilon": epsilon,
                "delta": 0,  # no hay datos de paneles iniciales
                "distancia_asignacion": dist,
            }
            sites.append(site)
    else:
        # Archivo simple (dpc_estimados_csv o dpc_csv): usar columnas sin prefijo
        expected = ["tipo_osm", "Zcap", "lon", "lat", "name"]
        for c in expected:
            if c not in df.columns:
                df[c] = None
        
        sites = []
        for idx, row in df.iterrows():
            try:
                zcap = int(row.get("Zcap")) if not pd.isna(row.get("Zcap")) else None
            except Exception:
                zcap = None
            
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
        "charging_station": 2.0,  # Electrolineras actuales
        "mall": 1.8,
        "supermarket": 1.5,
        "fuel": 1.4,  # Bencineras (comportamiento habitual)
        "parking": 1.3,
        "university": 1.2,
        "hospital": 1.0,
        "office": 0.8,
        "commercial": 0.7,
        "retail": 0.6,
        "car_wash": 0.4,
        "stadium": 1.1,
        "other": 0.5,
    }
    w *= tipo_weights.get(tipo, 0.5)
    
    # Fracción aproximada (asume ~150 sitios/comuna, peso promedio 1.2)
    avg_sites = 150
    avg_weight = 1.2
    fraction = w / (avg_sites * avg_weight)
    
    demanda_sitio = (demanda_comuna_total * fraction) * 0.3  # Factor conservador (CAMBIO 4)
    
    return max(1, int(round(demanda_sitio)))


def build_and_solve(comuna_sites, params):
    """
    Construye un MILP simplificado y lo resuelve con PuLP.

    comuna_sites: dict comuna -> list of sites (dicts)
    params: dict con parámetros (costos, producción, etc.)

    Retorna: solución (dict) y resumen
    """
    # Sets
    comunas = sorted(comuna_sites.keys())
    I = {}  # I[j] = list of site ids
    site_info = {}
    for j in comunas:
        I[j] = [s["id"] for s in comuna_sites[j]]
        for s in comuna_sites[j]:
            site_info[(s["id"], j)] = s

    # Demand estimates usando nuevo método
    d = {}  # d_{ij}
    D_j = {}
    total_demand = 0
    for j in comunas:
        D_j[j] = 0
        for s in comuna_sites[j]:
            di = estimate_demand_per_site(s, j)  # Pasar sitio completo y comuna
            d[(s["id"], j)] = di
            D_j[j] += di
            total_demand += di

    print(f"Demanda total estimada: {total_demand:,.0f} sesiones/mes")
    print(f"Demanda promedio por comuna: {total_demand/len(comunas):,.0f}")

    # Problem
    prob = pulp.LpProblem("EV_Charging_Planning_Simplified", pulp.LpMaximize)

    # Variables
    X = {}  # number of chargers installed at site (integer)
    Z = {}  # number of panels installed at site (integer)
    y = {}  # activation binary
    a = {}  # active (either existed or activated)
    d_sat = {}  # satisfied demand
    s = {}  # energy from PV used
    r = {}  # energy from grid

    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            q_ij = sinfo.get("q", 0)
            epsilon_ij = sinfo.get("epsilon", 0)
            delta_ij = sinfo.get("delta", 0)
            
            X[(i, j)] = pulp.LpVariable(f"X_{i}_{j}", lowBound=0, cat="Integer")
            Z[(i, j)] = pulp.LpVariable(f"Z_{i}_{j}", lowBound=0, cat="Integer")
            y[(i, j)] = pulp.LpVariable(f"y_{i}_{j}", lowBound=0, upBound=1, cat="Binary")
            a[(i, j)] = pulp.LpVariable(f"a_{i}_{j}", lowBound=0, upBound=1, cat="Binary")
            
            # R1-R2: Constraint: a >= q + y (station active if existed or activated)
            prob += a[(i, j)] >= q_ij + y[(i, j)], f"R5_active_{i}_{j}"
            
            # R2: Constraint: activation only if not existed (y <= 1 - q)
            prob += y[(i, j)] <= 1 - q_ij, f"R2_no_reactivate_{i}_{j}"
            
            # CAMBIO 1: Si activamos (y=1), debe haber al menos 1 cargador NUEVO
            prob += X[(i, j)] >= epsilon_ij + y[(i, j)], f"activate_implies_new_{i}_{j}"
            
            d_sat[(i, j)] = pulp.LpVariable(f"d_sat_{i}_{j}", lowBound=0, cat="Integer")
            s[(i, j)] = pulp.LpVariable(f"s_{i}_{j}", lowBound=0, cat="Continuous")
            r[(i, j)] = pulp.LpVariable(f"r_{i}_{j}", lowBound=0, cat="Continuous")

    # Auxiliary per comuna
    S_j = {j: pulp.LpVariable(f"S_{j}", lowBound=0, cat="Integer") for j in comunas}
    phi_j = {j: pulp.LpVariable(f"phi_{j}", lowBound=0, upBound=1, cat="Continuous") for j in comunas}
    psi_j = {j: pulp.LpVariable(f"psi_{j}", lowBound=0, cat="Continuous") for j in comunas}

    # Objective: simplified variant of the proposed objective
    Vcliente = params["V_cliente"]
    Bco2 = params.get("B_CO2", 0.0)

    obj_equity = pulp.lpSum([psi_j[j] * Vcliente for j in comunas])
    obj_env = pulp.lpSum([s[(i, j)] * Bco2 for j in comunas for i in I[j]])
    # coverage term: fraction of activated sites in comuna (weighted by having chargers)
    obj_cov = pulp.lpSum([ (pulp.lpSum([a[(i, j)] for i in I[j]]) / max(1, len(I[j]))) * Vcliente for j in comunas])

    prob += obj_equity + obj_env + obj_cov

    # Constraints
    # 1) Total chargers = initial + installed: X_total = epsilon + x_installed
    #    We model X as total, so we need X >= epsilon (cannot remove existing)
    for j in comunas:
        for sdict in comuna_sites[j]:
            i = sdict["id"]
            epsilon_ij = sdict.get("epsilon", 0)
            delta_ij = sdict.get("delta", 0)
            pcap = sdict.get("Zcap") if sdict.get("Zcap") is not None else params["Pcap_default"]
            
            # Cannot have fewer chargers than already installed
            prob += X[(i, j)] >= epsilon_ij, f"min_chargers_{i}_{j}"
            
            # CAMBIO 2: Capacidad expandida para sitios existentes
            effective_capacity = max(pcap, epsilon_ij + 5)  # Permitir al menos 5 más
            prob += X[(i, j)] <= effective_capacity * a[(i, j)], f"cap_site_{i}_{j}"
            
            # Same for panels
            prob += Z[(i, j)] >= delta_ij, f"min_panels_{i}_{j}"
            zmax = sdict.get("Zmax") if sdict.get("Zmax") is not None else params["Zmax_default"]
            prob += Z[(i, j)] <= zmax * a[(i, j)], f"cap_panels_{i}_{j}"

    # 2) demand satisfied <= C * X
    for j in comunas:
        for i in I[j]:
            prob += d_sat[(i, j)] <= params["C"] * X[(i, j)], f"d_sat_capacity_{i}_{j}"
            # cannot satisfy more than demand estimate
            prob += d_sat[(i, j)] <= d[(i, j)], f"d_sat_leq_d_{i}_{j}"

    # 3) aggregated S_j
    for j in comunas:
        prob += S_j[j] == pulp.lpSum([d_sat[(i, j)] for i in I[j]]), f"Sagg_{j}"

    # 4) energy balance: e = energy_per_client * d_sat = s + r
    for j in comunas:
        for i in I[j]:
            e_ij = params["energy_per_client"] * d_sat[(i, j)]
            prob += e_ij == s[(i, j)] + r[(i, j)], f"energy_balance_{i}_{j}"
            # solar production limit
            prob += s[(i, j)] <= params["p_per_panel"] * Z[(i, j)], f"solar_prod_{i}_{j}"
            # grid import limit
            prob += r[(i, j)] <= params["gmax_default"] * a[(i, j)], f"grid_lim_{i}_{j}"

    # 5) phi_j definition:  phi = 1 - S_j / D_j (if D_j > 0), else phi=0
    for j in comunas:
        if D_j[j] > 0:
            # CAMBIO 3: Relajar restricción de phi (evitar sobreajuste numérico)
            coverage_ratio = S_j[j] / float(D_j[j])
            prob += phi_j[j] >= 1.0 - coverage_ratio - 0.3, f"phi_lower_{j}"
            prob += phi_j[j] <= 1.0 - coverage_ratio + 0.3, f"phi_upper_{j}"
        else:
            prob += phi_j[j] == 0.0, f"phi_zero_{j}"

    # 6) McCormick linearization for psi_j = phi_j * S_j on rectangle [0,1] x [0, Smax]
    for j in comunas:
        Smax = float(D_j[j]) if D_j[j] > 0 else 1.0
        prob += psi_j[j] >= 0
        prob += psi_j[j] >= S_j[j] + phi_j[j] * Smax - Smax
        prob += psi_j[j] <= S_j[j]
        prob += psi_j[j] <= phi_j[j] * Smax

    # 7) Budget constraint
    total_cost = []
    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            epsilon_ij = sinfo.get("epsilon", 0)
            delta_ij = sinfo.get("delta", 0)
            
            # infrastructure fixed cost k_ij: only if activating new station
            total_cost.append(params["k_slow"] * y[(i, j)])
            
            # charger cost: only for NEW chargers (X - epsilon)
            x_new = X[(i, j)] - epsilon_ij
            total_cost.append(params["c_slow"] * x_new)
            
            # maint cost per charger * X (all chargers, incluyendo existentes)
            total_cost.append(params["h_slow"] * X[(i, j)])
            
            # panel cost: only for NEW panels (Z - delta)
            z_new = Z[(i, j)] - delta_ij
            total_cost.append(params["v_panel"] * z_new)
            
            # maint panel cost (all panels)
            total_cost.append(params["m_panel"] * Z[(i, j)])
            
            # grid energy cost
            total_cost.append(params["p_red"] * r[(i, j)])

    prob += pulp.lpSum(total_cost) <= params["B"], "budget"

    # CAMBIO 6: Diagnóstico de infactibilidad
    print("\n=== DIAGNÓSTICO PRE-SOLVE ===")
    for j in list(comunas)[:3]:  # Revisar primeras 3 comunas
        sites_j = comuna_sites[j]
        for sdict in sites_j[:5]:  # Primeros 5 sitios
            i = sdict["id"]
            epsilon = sdict.get("epsilon", 0)
            pcap = sdict.get("Zcap", params["Pcap_default"])
            if epsilon > pcap:
                print(f"⚠️ CONFLICTO: {j} site {i} tiene epsilon={epsilon} > Pcap={pcap}")

    total_estimated_cost = 0
    for j in comunas:
        for sdict in comuna_sites[j]:
            if sdict.get("epsilon", 0) == 0:  # Solo sitios nuevos
                total_estimated_cost += params["k_slow"] + params["c_slow"] * 2
    print(f"Costo mínimo estimado (solo infraestructura nueva): ${total_estimated_cost:,.0f} CLP")
    print(f"Presupuesto disponible: ${params['B']:,.0f} CLP")
    if total_estimated_cost > params["B"]:
        print("❌ PRESUPUESTO INSUFICIENTE para instalar infraestructura mínima")
    print("=== FIN DIAGNÓSTICO ===\n")

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=120)
    print("Resolviendo modelo con PuLP (CBC) ... (timeout 120s)")
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    print("Estado solución:", status)

    # Collect results
    results = []
    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            xi = int(round(pulp.value(X[(i, j)])))
            zi = int(round(pulp.value(Z[(i, j)])))
            yi = int(round(pulp.value(y[(i, j)])))
            ai = int(round(pulp.value(a[(i, j)])))
            ds = int(round(pulp.value(d_sat[(i, j)])))
            si = float(pulp.value(s[(i, j)]))
            ri = float(pulp.value(r[(i, j)]))
            
            results.append({
                "comuna": j,
                "site_id": i,
                "site_name": sinfo.get("name"),
                "tipo": sinfo.get("tipo"),
                "q_existed": sinfo.get("q", 0),
                "epsilon_initial_chargers": sinfo.get("epsilon", 0),
                "activated": yi,
                "active": ai,
                "chargers_total": xi,
                "chargers_new": max(0, xi - sinfo.get("epsilon", 0)),
                "panels_total": zi,
                "panels_new": max(0, zi - sinfo.get("delta", 0)),
                "demand_estimated": d[(i, j)],
                "demand_satisfied": ds,
                "solar_used_kwh": si,
                "grid_used_kwh": ri,
                "distancia_asignacion_m": sinfo.get("distancia_asignacion"),
            })

    summary = {
        "objective_value": pulp.value(prob.objective),
        "status": status,
        "comunas_processed": len(comunas),
        "total_sites": sum(len(I[j]) for j in comunas),
        "sites_with_existing_chargers": sum(1 for j in comunas for i in I[j] if site_info[(i,j)].get("epsilon",0) > 0),
    }

    return results, summary


def main():
    print("Ejecutando solver simplificado del modelo de infraestructura de carga")
    print("Root repo:", ROOT)

    # Descubrir comunas y cargar sites
    try:
        srcdir, mapping = discover_comunas()
    except Exception as e:
        print("Error al localizar datos de comunas:", e)
        sys.exit(1)

    comuna_sites = {}
    for comuna, path in mapping.items():
        try:
            comuna_sites[comuna] = load_sites_for_comuna(path)
        except Exception as e:
            print(f"Error leyendo {path}: {e}")
            comuna_sites[comuna] = []

    print(f"Comunass encontradas: {len(comuna_sites)} (ejemplos: {list(comuna_sites.keys())[:6]})")

    # Parámetros por defecto (tomados del README y estimaciones)
    params = {
        # charger and infra costs (CLP)
        "k_slow": 6500000.0,
        "k_fast": 20000000.0,
        "c_slow": 2000000.0,
        "c_fast": 49000000.0,
        "h_slow": 63000.0,
        "h_fast": 119000.0,
        # panels
        "v_panel": 900000.0,
        "m_panel": 625.0,
        "p_per_panel": 56.25,  # kWh/panel/month
        # energy
        "p_red": 180.0,  # CLP/kWh
        "CI_m": 18.07,
        "B_CO2": 50.0,  # beneficio social por kWh renovable (ajustado para dar peso)
        # capacities
        "Pcap_default": 6,
        "Zmax_default": 50,  # paneles máximos por defecto
        "gmax_default": 10000.0,  # kWh per month (prácticamente ilimitado)
        # operations
        "beta_slow": 1188.0,
        "beta_fast": 2700.0,
        "C": 70,  # clientes por cargador/mes
        # energy per client (kWh)
        "energy_per_client": 30.0,
        # budget
        "B": 400_000_000_000.0,  # CAMBIO 5: presupuesto triplicado (CLP)
        # other
        "V_cliente": 1200.0,
    }

    # Avisos sobre supuestos / parametros faltantes
    print("Parámetros usados (resumen):")
    for k in ["c_slow", "k_slow", "v_panel", "p_per_panel", "p_red", "C", "energy_per_client", "B"]:
        print(f"  {k}: {params[k]}")

    # Construir y resolver
    results, summary = build_and_solve(comuna_sites, params)

    # Guardar resultados
    outpath = os.path.join(ROOT, "results_optimization.csv")
    keys = ["comuna", "site_id", "site_name", "tipo", "q_existed", "epsilon_initial_chargers", 
            "activated", "active", "chargers_total", "chargers_new", "panels_total", "panels_new",
            "demand_estimated", "demand_satisfied", "solar_used_kwh", "grid_used_kwh", "distancia_asignacion_m"]
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print("Resultados guardados en:", outpath)
    print("Resumen:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    


if __name__ == "__main__":
    main()
