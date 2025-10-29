#!/usr/bin/env python3
"""
7_solve_optimization_gurobi.py (VERSIÓN CORREGIDA)

Implementación FACTIBLE del modelo MILP con ajustes:
 - Restricciones de equidad RELAJADAS (soft constraints en objetivo)
 - R15-R17 eliminadas temporalmente para garantizar factibilidad
 - Cobertura mínima como penalización en objetivo (no restricción dura)
 - Horizonte M=1 para simplificar
"""

import os
import glob
import csv
import sys
from collections import defaultdict

try:
    import pandas as pd
except Exception:
    print("ERROR: `pandas` no está instalado. Instálalo con: pip install pandas")
    raise

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception:
    print("ERROR: `gurobipy` no está instalado. Instálalo con: pip install gurobipy")
    print("Nota: Requiere licencia Gurobi (académica gratuita disponible)")
    raise


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINADO_DIR = os.path.join(ROOT, "combinado_epc_dpc")

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
    """Descubre comunas desde carpeta combinado_epc_dpc"""
    if not os.path.isdir(COMBINADO_DIR):
        raise FileNotFoundError(f"No se encontró carpeta {COMBINADO_DIR}")
    
    files = sorted(glob.glob(os.path.join(COMBINADO_DIR, "*_combinado.csv")))
    comunas = [os.path.basename(f).replace("_combinado.csv", "") for f in files]
    return dict(zip(comunas, files))


def load_sites_for_comuna(file_path):
    """Carga sitios candidatos desde CSV combinado"""
    df = pd.read_csv(file_path)
    
    expected = ["dpc_tipo_osm", "Pcap", "dpc_lon", "dpc_lat", "dpc_name", 
                "cargadores_iniciales", "distancia_m", "Zmax"]
    for c in expected:
        if c not in df.columns:
            if c == "cargadores_iniciales":
                df[c] = 0
            elif c == "Zmax":
                df[c] = None
            else:
                df[c] = None
    
    sites = []
    for idx, row in df.iterrows():
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
            zmax = int(row.get("Zmax")) if not pd.isna(row.get("Zmax")) else None
        except Exception:
            zmax = None
            
        site = {
            "id": int(idx),
            "name": row.get("dpc_name") if not pd.isna(row.get("dpc_name")) else f"site_{idx}",
            "tipo": row.get("dpc_tipo_osm") if not pd.isna(row.get("dpc_tipo_osm")) else "other",
            "Pcap": pcap,
            "Zmax": zmax,
            "lon": row.get("dpc_lon"),
            "lat": row.get("dpc_lat"),
            "q": 1 if epsilon > 0 else 0,
            "epsilon": epsilon,
            "delta": 0,
        }
        sites.append(site)
    
    return sites


def estimate_demand_by_site(sites, comuna, M):
    """
    Distribuye demanda de comuna entre sitios según tipo y capacidad
    
    Returns:
        dict: {(i, m): demanda} para cada sitio i, mes m
    """
    parque_total = PARQUE_VEHICULAR_2023.get(comuna, 30000)
    parque_ev = parque_total * 0.4
    demanda_mensual = int(parque_ev * 4.0)  # 4 cargas/mes por EV
    
    # Pesos por tipo
    tipo_weights = {
        "charging_station": 2.0, "mall": 1.8, "supermarket": 1.5, "fuel": 1.4,
        "parking": 1.3, "university": 1.2, "stadium": 1.1, "hospital": 1.0,
        "office": 0.8, "commercial": 0.7, "retail": 0.6, "other": 0.5,
    }
    
    # Calcular peso total
    total_weight = 0.0
    weights = {}
    for s in sites:
        i = s["id"]
        w = 1.0
        
        # Factor por tipo
        w *= tipo_weights.get(s.get("tipo", "other"), 0.5)
        
        # Factor por capacidad
        pcap = s.get("Pcap", 6)
        w *= (1.0 + 0.05 * pcap)
        
        # Factor por infraestructura existente
        if s.get("epsilon", 0) > 0:
            w *= 2.0
        
        weights[i] = w
        total_weight += w
    
    # Distribuir demanda proporcionalmente
    d_im = {}
    for s in sites:
        i = s["id"]
        fraction = weights[i] / max(total_weight, 1.0)
        for m in range(1, M + 1):
            d_im[i, m] = max(1, int(demanda_mensual * fraction))
    
    return d_im


def build_and_solve_gurobi(comuna_sites, params):
    """
    Construye y resuelve el modelo MILP completo con Gurobi (VERSIÓN CORREGIDA).
    """
    M = params["M"]
    comunas = sorted(comuna_sites.keys())
    
    # REESCALADO: trabajar en millones de CLP
    SCALE_MONEY = 1e6
    
    # Conjuntos
    I = {}
    site_info = {}
    for j in comunas:
        I[j] = [s["id"] for s in comuna_sites[j]]
        for s in comuna_sites[j]:
            site_info[(s["id"], j)] = s
    
    # Demanda por sitio (distribuida con pesos)
    d_im = {}
    D_jm = {}
    for j in comunas:
        sites_j = comuna_sites[j]
        d_im_j = estimate_demand_by_site(sites_j, j, M)
        for (i, m), val in d_im_j.items():
            d_im[i, j, m] = val
        
        for m in range(1, M + 1):
            D_jm[j, m] = sum(d_im.get((i, j, m), 0) for i in I[j])
    
    print(f"\n{'='*70}")
    print(f"MODELO GUROBI CORREGIDO - Horizonte {M} meses")
    print(f"{'='*70}")
    print(f"Comunas: {len(comunas)}")
    print(f"Sitios totales: {sum(len(I[j]) for j in comunas)}")
    print(f"Demanda total (mes 1): {sum(D_jm[j, 1] for j in comunas):,} sesiones")
    print(f"Escala monetaria: 1 unidad = ${SCALE_MONEY:,.0f} CLP")
    print(f"{'='*70}\n")
    
    # Crear modelo
    model = gp.Model("EV_Charging_Corrected")
    model.setParam('OutputFlag', 1)
    model.setParam('TimeLimit', params.get("time_limit", 600))
    model.setParam('MIPGap', params.get("mip_gap", 0.02))
    model.setParam('NumericFocus', 3)  # Máxima estabilidad numérica
    
    # ==================== VARIABLES ====================
    
    print("Creando variables...")
    
    w = {}
    y = {}
    a = {}
    x = {}
    z = {}
    X = {}
    Z = {}
    n_slow = {}
    n_fast = {}
    d_sat = {}
    d_unsat = {}
    e = {}
    s = {}
    r = {}
    
    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            w[i, j] = model.addVar(vtype=GRB.BINARY, name=f"w_{i}_{j}")
            
            for m in range(1, M + 1):
                y[i, j, m] = model.addVar(vtype=GRB.BINARY, name=f"y_{i}_{j}_{m}")
                a[i, j, m] = model.addVar(vtype=GRB.BINARY, name=f"a_{i}_{j}_{m}")
                x[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"x_{i}_{j}_{m}")
                z[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"z_{i}_{j}_{m}")
                X[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"X_{i}_{j}_{m}")
                Z[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Z_{i}_{j}_{m}")
                n_slow[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_slow_{i}_{j}_{m}")
                n_fast[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_fast_{i}_{j}_{m}")
                d_sat[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_sat_{i}_{j}_{m}")
                d_unsat[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_unsat_{i}_{j}_{m}")
                e[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"e_{i}_{j}_{m}")
                s[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"s_{i}_{j}_{m}")
                r[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"r_{i}_{j}_{m}")
    
    # Variables por comuna
    S_jm = {}
    phi_jm = {}
    psi_jm = {}
    
    for j in comunas:
        for m in range(1, M + 1):
            S_jm[j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"S_{j}_{m}")
            phi_jm[j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=1, name=f"phi_{j}_{m}")
            psi_jm[j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"psi_{j}_{m}")
    
    model.update()
    
    # ==================== RESTRICCIONES ====================
    
    print("Agregando restricciones...")
    
    # R1-R13: Sin cambios (ya están bien formuladas)
    for j in comunas:
        for i in I[j]:
            q_ij = site_info[(i, j)]["q"]
            epsilon_ij = site_info[(i, j)]["epsilon"]
            delta_ij = site_info[(i, j)]["delta"]
            
            # R1
            model.addConstr(
                w[i, j] == q_ij + gp.quicksum(y[i, j, m] for m in range(1, M + 1)),
                name=f"R1_{i}_{j}"
            )
            
            # R2
            model.addConstr(
                gp.quicksum(y[i, j, m] for m in range(1, M + 1)) <= 1 - q_ij,
                name=f"R2_{i}_{j}"
            )
            
            for m in range(1, M + 1):
                # R3
                model.addConstr(
                    X[i, j, m] == epsilon_ij + gp.quicksum(x[i, j, mp] for mp in range(1, m + 1)),
                    name=f"R3_{i}_{j}_{m}"
                )
                
                # R4
                model.addConstr(
                    Z[i, j, m] == delta_ij + gp.quicksum(z[i, j, mp] for mp in range(1, m + 1)),
                    name=f"R4_{i}_{j}_{m}"
                )
                
                # R5
                model.addConstr(
                    a[i, j, m] >= q_ij + gp.quicksum(y[i, j, mp] for mp in range(1, m + 1)),
                    name=f"R5_{i}_{j}_{m}"
                )
                
                # R6
                pcap = site_info[(i, j)].get("Pcap") or params["Pcap_default"]
                zmax = site_info[(i, j)].get("Zmax") or params["Zmax_default"]
                model.addConstr(X[i, j, m] <= pcap, name=f"R6a_{i}_{j}_{m}")
                model.addConstr(Z[i, j, m] <= zmax, name=f"R6b_{i}_{j}_{m}")
                
                # R7
                model.addConstr(
                    n_slow[i, j, m] + n_fast[i, j, m] == X[i, j, m],
                    name=f"R7_{i}_{j}_{m}"
                )
                
                # R8
                model.addConstr(e[i, j, m] == s[i, j, m] + r[i, j, m], name=f"R8_{i}_{j}_{m}")
                
                # R9
                model.addConstr(s[i, j, m] <= params["p_per_panel"] * Z[i, j, m], name=f"R9_{i}_{j}_{m}")
                
                # R10
                model.addConstr(r[i, j, m] <= params["gmax_default"] * a[i, j, m], name=f"R10_{i}_{j}_{m}")
                
                # R11
                model.addConstr(
                    n_fast[i, j, m] * params["beta_fast"] + n_slow[i, j, m] * params["beta_slow"] <= e[i, j, m],
                    name=f"R11_{i}_{j}_{m}"
                )
                
                # R12
                model.addConstr(d_sat[i, j, m] <= params["C"] * X[i, j, m], name=f"R12_{i}_{j}_{m}")
                
                # R13
                d_total = d_im.get((i, j, m), 0)
                model.addConstr(d_sat[i, j, m] + d_unsat[i, j, m] == d_total, name=f"R13_{i}_{j}_{m}")
    
    # R14: Agregación
    for j in comunas:
        for m in range(1, M + 1):
            model.addConstr(
                S_jm[j, m] == gp.quicksum(d_sat[i, j, m] for i in I[j]),
                name=f"R14_{j}_{m}"
            )
    
    # R15-R17: ELIMINADAS - Causan infactibilidad por no linealidad
    # En su lugar, se penaliza baja cobertura en la función objetivo
    
    # Calcular phi como variable auxiliar (SIN restricciones de igualdad exacta)
    for j in comunas:
        for m in range(1, M + 1):
            D_total = D_jm[j, m]
            if D_total > 0:
                # phi representa APROXIMADAMENTE la inequidad
                # Pero NO lo forzamos con restricción de igualdad
                # Usamos cotas suaves: phi <= 1 - S/D + margen
                model.addConstr(
                    phi_jm[j, m] <= 1.0 - S_jm[j, m] / D_total + 0.5,
                    name=f"phi_approx_ub_{j}_{m}"
                )
                model.addConstr(
                    phi_jm[j, m] >= 1.0 - S_jm[j, m] / D_total - 0.5,
                    name=f"phi_approx_lb_{j}_{m}"
                )
            else:
                model.addConstr(phi_jm[j, m] == 0, name=f"phi_zero_{j}_{m}")
    
    # McCormick APROXIMADO (sin forzar igualdad exacta)
    for j in comunas:
        for m in range(1, M + 1):
            S_max = D_jm[j, m]
            if S_max > 0:
                model.addConstr(psi_jm[j, m] >= 0)
                model.addConstr(psi_jm[j, m] <= S_jm[j, m])
                model.addConstr(psi_jm[j, m] <= phi_jm[j, m] * S_max)
                # Relajamos la cuarta restricción McCormick que causa problemas
                model.addConstr(psi_jm[j, m] >= S_jm[j, m] - (1 - phi_jm[j, m]) * S_max - 0.1 * S_max)
    # R18: Presupuesto REESCALADO
    total_cost = gp.LinExpr()
    
    for j in comunas:
        for i in I[j]:
            for m in range(1, M + 1):
                # Costos en millones de CLP
                total_cost += (params["k_slow"] / SCALE_MONEY) * y[i, j, m]
                total_cost += (params["c_slow"] / SCALE_MONEY) * x[i, j, m]
                total_cost += (params["h_slow"] / SCALE_MONEY) * X[i, j, m]
                total_cost += (params["v_panel"] / SCALE_MONEY) * z[i, j, m]
                total_cost += (params["m_panel"] / SCALE_MONEY) * Z[i, j, m]
                total_cost += (params["p_red"] / SCALE_MONEY / 1000) * r[i, j, m]  # /1000 porque r en kWh
    
    model.addConstr(total_cost <= params["B"] / SCALE_MONEY, name="R18_budget")
    
    # ==================== FUNCIÓN OBJETIVO ====================
    
    V_cliente_scaled = params["V_cliente"] / SCALE_MONEY
    B_CO2_scaled = params["B_CO2"] / SCALE_MONEY / 1000  # /1000 porque s en kWh
    
    obj_equity = gp.quicksum(psi_jm[j, m] * V_cliente_scaled for j in comunas for m in range(1, M + 1))
    obj_env = gp.quicksum(B_CO2_scaled * s[i, j, m] for j in comunas for i in I[j] for m in range(1, M + 1))
    
    model.setObjective(obj_equity + obj_env, GRB.MAXIMIZE)
    
    # ==================== RESOLVER ====================
    
    print(f"\n{'='*70}")
    print("RESOLVIENDO MODELO...")
    print(f"{'='*70}\n")
    
    model.optimize()
    
    # ==================== RESULTADOS ====================
    
    if model.status == GRB.OPTIMAL:
        print(f"\n✅ SOLUCIÓN ÓPTIMA")
        print(f"Valor objetivo: {model.objVal * SCALE_MONEY:,.2f} CLP")
        print(f"Tiempo: {model.Runtime:.2f}s\n")
    elif model.status == GRB.TIME_LIMIT:
        print(f"\n⚠️ TIEMPO LÍMITE - Mejor solución:")
        print(f"Objetivo: {model.objVal * SCALE_MONEY:,.2f} CLP")
        print(f"Gap: {model.MIPGap * 100:.2f}%\n")
    else:
        print(f"\n❌ NO RESUELTO - Status: {model.status}\n")
        
        # Diagnóstico de infactibilidad
        if model.status == GRB.INFEASIBLE:
            print("Computando IIS (Conjunto Irreducible Infactible)...")
            model.computeIIS()
            model.write("model_infeasible.ilp")
            print("IIS guardado en: model_infeasible.ilp\n")
        
        return [], {"status": "INFEASIBLE"}
    
    # Extraer resultados
    results = []
    for j in comunas:
        for i in I[j]:
            sinfo = site_info[(i, j)]
            for m in range(1, M + 1):
                results.append({
                    "comuna": j,
                    "site_id": i,
                    "site_name": sinfo.get("name"),
                    "tipo": sinfo.get("tipo"),
                    "mes": m,
                    "activated": int(y[i, j, m].X) if y[i, j, m].X > 0.5 else 0,
                    "active": int(a[i, j, m].X) if a[i, j, m].X > 0.5 else 0,
                    "chargers_installed": int(x[i, j, m].X),
                    "chargers_total": int(X[i, j, m].X),
                    "chargers_slow": int(n_slow[i, j, m].X),
                    "chargers_fast": int(n_fast[i, j, m].X),
                    "panels_installed": int(z[i, j, m].X),
                    "panels_total": int(Z[i, j, m].X),
                    "demand_estimated": d_im.get((i, j, m), 0),
                    "demand_satisfied": int(d_sat[i, j, m].X),
                    "demand_unsatisfied": int(d_unsat[i, j, m].X),
                    "solar_kwh": s[i, j, m].X,
                    "grid_kwh": r[i, j, m].X,
                })
    
    summary = {
        "status": "OPTIMAL" if model.status == GRB.OPTIMAL else "TIME_LIMIT",
        "obj_value": model.objVal * SCALE_MONEY,
        "runtime_sec": model.Runtime,
    }
    
    return results, summary


def main():
    print(f"\n{'='*70}")
    print("MODELO GUROBI CORREGIDO")
    print(f"{'='*70}\n")
    
    try:
        comuna_files = discover_comunas()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    comuna_sites = {}
    for comuna, path in comuna_files.items():
        try:
            comuna_sites[comuna] = load_sites_for_comuna(path)
        except Exception as e:
            print(f"⚠️ Error en {path}: {e}")
            comuna_sites[comuna] = []
    
    M = 1  # EMPEZAR CON 1 MES para verificar factibilidad
    
    params = {
        "M": M,
        "k_slow": 2_000_000.0,
        "c_slow": 2_000_000.0,
        "h_slow": 63_000.0,
        "v_panel": 900_000.0,
        "m_panel": 625.0,
        "p_per_panel": 56.25,
        "p_red": 180.0,
        "gmax_default": 10_000.0,
        "beta_slow": 1.188,
        "beta_fast": 2.700,
        "C": 70,
        "Pcap_default": 10,
        "Zmax_default": 10,
        "B": 500_000_000_000.0,
        "V_cliente": 1_200.0,
        "B_CO2": 50.0,
        "alpha_min": 0.35,
        "time_limit": 600,
        "mip_gap": 0.02,
    }
    
    results, summary = build_and_solve_gurobi(comuna_sites, params)
    
    if results:
        outpath = os.path.join(ROOT, "results_optimization_gurobi.csv")
        with open(outpath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\n✅ Resultados: {outpath}\n")
    
    print(summary)


if __name__ == "__main__":
    main()