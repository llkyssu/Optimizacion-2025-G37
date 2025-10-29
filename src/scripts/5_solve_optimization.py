#!/usr/bin/env python3
"""
5_solve_optimization.py

Implementación del modelo MILP de infraestructura de carga para vehículos eléctricos
siguiendo la formulación del Informe 2 - Grupo 37.

Qué hace:
 - Carga los archivos CSV pre-procesados en `data_with_demand/`
   (estos archivos ya DEBEN contener la demanda estimada)
 - Construye modelo MILP con PuLP/CBC
 - Resuelve el modelo
 - Guarda solución detallada en `results_optimization.csv`

Requisitos: pandas, pulp

Uso:
    python src/scripts/5_solve_optimization.py
    (Asegúrese de haber ejecutado 4a_calculate_demand.py primero)

Salida:
    - results_optimization.csv (decisiones óptimas por sitio)
    - Resumen en consola con valor objetivo y estadísticas
"""

import os
import glob
import math
import csv
import sys

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
# Directorio de entrada: DEBE ser el que genera 4a_calculate_demand.py
DATA_DIR = os.path.join(ROOT, "data_with_demand")


def discover_comunas():
    """
    Descubre comunas leyendo los archivos pre-procesados en DATA_DIR.
    """
    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(f"No se encontró la carpeta de datos: {DATA_DIR}\n"
                                 "Por favor, ejecute '4a_calculate_demand.py' primero.")
    
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*_with_demand.csv")))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos '*_with_demand.csv' en {DATA_DIR}\n"
                                 "Por favor, ejecute '4a_calculate_demand.py' primero.")
                                 
    comunas = [os.path.basename(f).replace("_with_demand.csv", "") for f in files]
    return dict(zip(comunas, files))


def load_sites_for_comuna(file_path):
    """
    Carga los sitios desde un archivo CSV pre-procesado.
    Asume que las columnas ya están limpias y 'demand_estimated' existe.
    """
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error leyendo archivo {file_path}: {e}")
        return []

    sites = []
    for _, row in df.iterrows():
        site = row.to_dict()
        # Asegurar tipos correctos y valores por defecto del modelo
        try:
            site["id"] = int(site.get("id", 0))
            site["Zcap"] = int(site.get("Zcap")) if pd.notna(site.get("Zcap")) else None
            site["q"] = int(site.get("q", 0))
            site["epsilon"] = int(site.get("epsilon", 0))
            site["delta"] = int(site.get("delta", 0))
            site["distancia_asignacion"] = float(site.get("distancia_asignacion")) if pd.notna(site.get("distancia_asignacion")) else None
            # Campo clave: leer la demanda pre-calculada
            site["demand_estimated"] = int(site.get("demand_estimated", 0))
            sites.append(site)
        except Exception as e:
            print(f"Error procesando fila en {file_path}: {row}\nError: {e}")
            
    return sites


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

    # *** CAMBIO PRINCIPAL ***
    # La demanda ahora se lee directamente de los datos cargados
    d = {}  # d_{ij}
    D_j = {}
    total_demand = 0
    for j in comunas:
        D_j[j] = 0
        for s in comuna_sites[j]:
            # Leer demanda pre-calculada del 'site' dict
            di = s.get("demand_estimated", 0)
            
            d[(s["id"], j)] = di
            D_j[j] += di
            total_demand += di
    # *** FIN DEL CAMBIO ***

    print(f"Demanda total leída: {total_demand:,.0f} sesiones/mes")
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
            
            X[(i, j)] = pulp.LpVariable(f"X_{i}_{j}", lowBound=0, cat="Integer")
            Z[(i, j)] = pulp.LpVariable(f"Z_{i}_{j}", lowBound=0, cat="Integer")
            y[(i, j)] = pulp.LpVariable(f"y_{i}_{j}", lowBound=0, upBound=1, cat="Binary")
            a[(i, j)] = pulp.LpVariable(f"a_{i}_{j}", lowBound=0, upBound=1, cat="Binary")
            
            prob += a[(i, j)] >= q_ij + y[(i, j)], f"R5_active_{i}_{j}"
            prob += y[(i, j)] <= 1 - q_ij, f"R2_no_reactivate_{i}_{j}"
            prob += X[(i, j)] >= epsilon_ij + y[(i, j)], f"activate_implies_new_{i}_{j}"
            
            d_sat[(i, j)] = pulp.LpVariable(f"d_sat_{i}_{j}", lowBound=0, cat="Integer")
            s[(i, j)] = pulp.LpVariable(f"s_{i}_{j}", lowBound=0, cat="Continuous")
            r[(i, j)] = pulp.LpVariable(f"r_{i}_{j}", lowBound=0, cat="Continuous")

    # Auxiliary per comuna
    S_j = {j: pulp.LpVariable(f"S_{j}", lowBound=0, cat="Integer") for j in comunas}
    phi_j = {j: pulp.LpVariable(f"phi_{j}", lowBound=0, upBound=1, cat="Continuous") for j in comunas}
    psi_j = {j: pulp.LpVariable(f"psi_{j}", lowBound=0, cat="Continuous") for j in comunas}

    # Objective
    Vcliente = params["V_cliente"]
    Bco2 = params.get("B_CO2", 0.0)
    obj_equity = pulp.lpSum([psi_j[j] * Vcliente for j in comunas])
    obj_env = pulp.lpSum([s[(i, j)] * Bco2 for j in comunas for i in I[j]])
    obj_cov = pulp.lpSum([ (pulp.lpSum([a[(i, j)] for i in I[j]]) / max(1, len(I[j]))) * Vcliente for j in comunas])
    prob += obj_equity + obj_env + obj_cov

    # Constraints
    for j in comunas:
        for sdict in comuna_sites[j]:
            i = sdict["id"]
            epsilon_ij = sdict.get("epsilon", 0)
            delta_ij = sdict.get("delta", 0)
            pcap = sdict.get("Zcap") if sdict.get("Zcap") is not None else params["Pcap_default"]
            
            prob += X[(i, j)] >= epsilon_ij, f"min_chargers_{i}_{j}"
            effective_capacity = max(pcap, epsilon_ij + 5)
            prob += X[(i, j)] <= effective_capacity * a[(i, j)], f"cap_site_{i}_{j}"
            
            prob += Z[(i, j)] >= delta_ij, f"min_panels_{i}_{j}"
            zmax = sdict.get("Zmax") if sdict.get("Zmax") is not None else params["Zmax_default"]
            prob += Z[(i, j)] <= zmax * a[(i, j)], f"cap_panels_{i}_{j}"

    for j in comunas:
        for i in I[j]:
            prob += d_sat[(i, j)] <= params["C"] * X[(i, j)], f"d_sat_capacity_{i}_{j}"
            # AHORA d[(i,j)] VIENE DEL ARCHIVO
            prob += d_sat[(i, j)] <= d[(i, j)], f"d_sat_leq_d_{i}_{j}"

    for j in comunas:
        prob += S_j[j] == pulp.lpSum([d_sat[(i, j)] for i in I[j]]), f"Sagg_{j}"

    for j in comunas:
        for i in I[j]:
            e_ij = params["energy_per_client"] * d_sat[(i, j)]
            prob += e_ij == s[(i, j)] + r[(i, j)], f"energy_balance_{i}_{j}"
            prob += s[(i, j)] <= params["p_per_panel"] * Z[(i, j)], f"solar_prod_{i}_{j}"
            prob += r[(i, j)] <= params["gmax_default"] * a[(i, j)], f"grid_lim_{i}_{j}"

    for j in comunas:
        if D_j[j] > 0:
            coverage_ratio = S_j[j] / float(D_j[j])
            prob += phi_j[j] >= 1.0 - coverage_ratio - 0.3, f"phi_lower_{j}"
            prob += phi_j[j] <= 1.0 - coverage_ratio + 0.3, f"phi_upper_{j}"
        else:
            prob += phi_j[j] == 0.0, f"phi_zero_{j}"

    for j in comunas:
        Smax = float(D_j[j]) if D_j[j] > 0 else 1.0
        prob += psi_j[j] >= 0
        prob += psi_j[j] >= S_j[j] + phi_j[j] * Smax - Smax
        prob += psi_j[j] <= S_j[j]
        prob += psi_j[j] <= phi_j[j] * Smax

    total_cost = []
    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            epsilon_ij = sinfo.get("epsilon", 0)
            delta_ij = sinfo.get("delta", 0)
            
            total_cost.append(params["k_slow"] * y[(i, j)])
            x_new = X[(i, j)] - epsilon_ij
            total_cost.append(params["c_slow"] * x_new)
            total_cost.append(params["h_slow"] * X[(i, j)])
            z_new = Z[(i, j)] - delta_ij
            total_cost.append(params["v_panel"] * z_new)
            total_cost.append(params["m_panel"] * Z[(i, j)])
            total_cost.append(params["p_red"] * r[(i, j)])
    prob += pulp.lpSum(total_cost) <= params["B"], "budget"

    # CAMBIO 6: Diagnóstico (sin cambios, sigue siendo útil)
    print("\n=== DIAGNÓSTICO PRE-SOLVE ===")
    for j in list(comunas)[:3]:
        sites_j = comuna_sites[j]
        for sdict in sites_j[:5]:
            i = sdict["id"]
            epsilon = sdict.get("epsilon", 0)
            pcap = sdict.get("Zcap", params["Pcap_default"])
            if epsilon > pcap:
                print(f"⚠️ CONFLICTO: {j} site {i} tiene epsilon={epsilon} > Pcap={pcap}")
    total_estimated_cost = 0
    for j in comunas:
        for sdict in comuna_sites[j]:
            if sdict.get("epsilon", 0) == 0:
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
                # Se usa la demanda estimada 'd' que se leyó al inicio
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
    print("Leyendo datos desde:", DATA_DIR)

    # Descubrir comunas y cargar sites (versión simplificada)
    try:
        mapping = discover_comunas()
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

    if not comuna_sites:
        print("No se cargaron datos de ninguna comuna. Abortando.")
        sys.exit(1)

    print(f"Comunas encontradas: {len(comuna_sites)} (ejemplos: {list(comuna_sites.keys())[:6]})")

    # Parámetros (sin cambios)
    params = {
        "k_slow": 6500000.0, "k_fast": 20000000.0, "c_slow": 2000000.0,
        "c_fast": 49000000.0, "h_slow": 63000.0, "h_fast": 119000.0,
        "v_panel": 900000.0, "m_panel": 625.0, "p_per_panel": 56.25,
        "p_red": 180.0, "CI_m": 18.07, "B_CO2": 50.0, "Pcap_default": 6,
        "Zmax_default": 50, "gmax_default": 10000.0, "beta_slow": 1188.0,
        "beta_fast": 2700.0, "C": 70, "energy_per_client": 30.0,
        "B": 400_000_000_000.0, "V_cliente": 1200.0,
    }

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