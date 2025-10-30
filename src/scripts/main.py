#!/usr/bin/env python3
"""
modelo_completo_latex.py

Implementación EXACTA del modelo de optimización para infraestructura de carga
de vehículos eléctricos con energías renovables según especificación LaTeX.

Modelo MILP que maximiza el bienestar social considerando:
- Beneficio ponderado por equidad y servicio
- Beneficio ambiental por uso de energía solar

Restricciones R1-R19 implementadas fielmente según el documento LaTeX.
"""

import os
import glob
import sys
from collections import defaultdict

try:
    import pandas as pd
except Exception:
    print("ERROR: pandas no instalado. Ejecuta: pip install pandas")
    sys.exit(1)

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception:
    print("ERROR: gurobipy no instalado. Ejecuta: pip install gurobipy")
    print("Nota: Requiere licencia Gurobi (académica gratuita disponible)")
    sys.exit(1)


# ============================================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================================
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMBINADO_DIR = os.path.join(ROOT, "combinado_epc_dpc")


# ============================================================================
# FUNCIONES AUXILIARES PARA CARGA DE DATOS
# ============================================================================

def descubrir_comunas():
    """Descubre comunas disponibles en la carpeta combinado_epc_dpc"""
    if not os.path.isdir(COMBINADO_DIR):
        raise FileNotFoundError(f"No se encontró carpeta {COMBINADO_DIR}")
    
    archivos = sorted(glob.glob(os.path.join(COMBINADO_DIR, "*.csv")))
    
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos CSV en {COMBINADO_DIR}")
    
    comunas = []
    for archivo in archivos:
        nombre = os.path.basename(archivo).replace(".csv", "")
        comunas.append(nombre)
    
    print(f"✓ Se encontraron {len(comunas)} comunas")
    return sorted(comunas)


def cargar_sitios_comuna(comuna):
    """
    Carga los sitios candidatos para una comuna desde su archivo CSV.
    
    Retorna: DataFrame con columnas relevantes para el modelo
    """
    archivo = os.path.join(COMBINADO_DIR, f"{comuna}.csv")
    
    if not os.path.exists(archivo):
        print(f"⚠ Advertencia: No existe {archivo}")
        return pd.DataFrame()
    
    df = pd.read_csv(archivo)
    
    # Validar columnas necesarias
    columnas_requeridas = ['demand_estimated']
    for col in columnas_requeridas:
        if col not in df.columns:
            print(f"⚠ Advertencia: Columna {col} no encontrada en {comuna}.csv")
            return pd.DataFrame()
    
    return df


# ============================================================================
# PARÁMETROS DEL MODELO (según documento LaTeX)
# ============================================================================

def definir_parametros(M=144):
    """
    Define todos los parámetros del modelo según la especificación LaTeX.
    
    Parámetros:
        M: Horizonte de planificación en meses (default: 12)
    
    Retorna:
        dict con todos los parámetros del modelo
    """
    
    params = {
        # ============================================================
        # HORIZONTE TEMPORAL
        # ============================================================
        "M": M,  # Número de meses del proyecto
        
        # ============================================================
        # INFRAESTRUCTURA
        # ============================================================
        "k_slow": 6_500_000,   # CLP - Costo fijo activación carga lenta
        "k_fast": 20_000_000,  # CLP - Costo fijo activación carga rápida
        "k": (6_500_000 + 20_000_000)/2,  # CLP - Costo fijo activación (promedio)
        
        # ============================================================
        # CARGADORES
        # ============================================================
        "c_slow": 2_000_000,   # CLP - Costo instalación cargador lento
        "c_fast": 49_000_000,  # CLP - Costo instalación cargador rápido
        "h_slow": 63_000,      # CLP/mes - Mantenimiento cargador lento
        "h_fast": 119_000,     # CLP/mes - Mantenimiento cargador rápido
        "h": (63_000 + 119_000)/2,  # CLP/mes - Mantenimiento cargador (promedio)
        "beta_slow": 1_188,    # kWh/mes - Capacidad energética cargador lento
        "beta_fast": 2_700,    # kWh/mes - Capacidad energética cargador rápido
        "C": 180,              # clientes/mes - Clientes por cargador
        
        # ============================================================
        # PANELES FOTOVOLTAICOS
        # ============================================================
        "v": 900_000,          # CLP - Costo instalación panel FV
        "m": 625,              # CLP/mes - Mantenimiento panel FV
        "p": 56.25,            # kWh/panel/mes - Producción panel FV
        
        # ============================================================
        # ENERGÍA
        # ============================================================
        "p_red": 180,          # CLP/kWh - Precio energía de la red
        "CI": 18.07,           # CLP/kWh - Costo emisiones red
        "g_max_default": 50000, # kWh/mes - Límite importación red (default)
        
        # ============================================================
        # CAPACIDADES FÍSICAS (defaults si no están en CSV)
        # ============================================================
        "Pcap_default": 10,    # Cargadores máximos por estación
        "Zmax_default": 20,    # Paneles máximos por estación
        
        # ============================================================
        # DEMANDA Y SERVICIO
        # ============================================================
        "alpha_min": 0.30,     # Objetivo cobertura mínima (φ ≤ 0.30)
        "V_cliente": 12_000,   # CLP - Valor social por cliente atendido
        
        # ============================================================
        # BENEFICIOS AMBIENTALES
        # ============================================================
        "B_CO2": 18.07,        # CLP/kWh - Beneficio social energía renovable
        
        # ============================================================
        # PRESUPUESTO TOTAL
        # ============================================================
        "B": 50_000_000_000,  # CLP - Presupuesto total (500 mil millones)
        
        # ============================================================
        # ESCALAMIENTO NUMÉRICO
        # ============================================================
        "SCALE_MONEY": 1e6,    # Trabajar en millones de CLP
    }
    
    return params


# ============================================================================
# CONSTRUCCIÓN Y RESOLUCIÓN DEL MODELO
# ============================================================================

def construir_y_resolver_modelo(comunas, datos_comunas, params):
    """
    Construye y resuelve el modelo MILP completo según especificación LaTeX.
    
    Args:
        comunas: Lista de nombres de comunas
        datos_comunas: Dict {comuna: DataFrame con sitios}
        params: Dict con parámetros del modelo
    
    Returns:
        tuple: (modelo, resumen_solución)
    """
    
    M = params["M"]
    SCALE = params["SCALE_MONEY"]
    
    print("\n" + "="*70)
    print("CONSTRUCCIÓN DEL MODELO DE OPTIMIZACIÓN")
    print("="*70)
    
    # ========================================================================
    # CREAR MODELO GUROBI
    # ========================================================================
    model = gp.Model("InfraestructuraCarga_VE_EnergiasRenovables")
    
    # ========================================================================
    # CONJUNTOS
    # ========================================================================
    J = comunas  # Conjunto de comunas
    I = {}       # I[j] = lista de índices de sitios en comuna j
    
    for j in J:
        df = datos_comunas[j]
        I[j] = list(range(len(df)))
    
    meses = range(1, M + 1)
    
    print(f"\n✓ Conjuntos definidos:")
    print(f"  - Comunas (J): {len(J)}")
    print(f"  - Sitios totales: {sum(len(I[j]) for j in J)}")
    print(f"  - Horizonte temporal (M): {M} meses")
    
    # ========================================================================
    # PARÁMETROS POR SITIO
    # ========================================================================
    q_ij = {}      # Infraestructura existente (0 o 1)
    epsilon_ij = {} # Cargadores iniciales
    delta_ij = {}  # Paneles iniciales
    Pcap_ij = {}   # Capacidad máxima cargadores
    Zmax_ij = {}   # Capacidad máxima paneles
    g_max_ij = {}  # Límite importación red
    d_ijm = {}     # Demanda de clientes por sitio y mes
    
    # --- Ajuste de demanda base por tipo de estación ---
    g = 0.08  # 8% crecimiento anual
    # Factores de ajuste de demanda por tipo OSM
    factor_tipo_dict = {
        # amenity
        "parking": 1.0,
        "fuel": 1.2,
        "charging_station": 1.1,
        "car_wash": 0.8,
        "hospital": 1.8,
        "university": 1.6,
        # shop
        "supermarket": 1.3,
        "mall": 1.5,
        # building
        "retail": 1.2,
        "commercial": 1.1,
        "office": 1.0,
        # leisure
        "stadium": 2.0,
        # Otros
        "otros": 1.0
    }
    Dmax_ij = {}  # Demanda máxima por sitio (opcional)
    for j in J:
        df = datos_comunas[j]
        for i in I[j]:
            row = df.iloc[i]
            
            # Infraestructura existente
            q_ij[i, j] = int(row.get('cargadores_iniciales', 0) > 0)
            
            # Cargadores y paneles iniciales
            epsilon_ij[i, j] = int(row.get('cargadores_iniciales', 0))
            delta_ij[i, j] = int(row.get('paneles_iniciales', 0))
            
            # Capacidades físicas
            Pcap_ij[i, j] = max(
                int(row.get('dpc_Pcap', params["Pcap_default"])),
                epsilon_ij[i, j]
            )
            Zmax_ij[i, j] = max(
                int(row.get('dpc_Zmax', params["Zmax_default"])),
                delta_ij[i, j]
            )
            
            # Límite importación red
            g_max_ij[i, j] = params["g_max_default"]
            # --- Demanda base ajustada por tipo de estación ---
            tipo = row.get('dpc_tipo_osm', 'otros')
            factor_tipo = factor_tipo_dict.get(tipo, 1.0)
            demanda_base = row.get('demand_estimated', 0) * factor_tipo
            # --- Demanda mensual con crecimiento compuesto ---
            for m in meses:
                factor = (1 + g) ** ((m-1)/12)
                d_ijm[i, j, m] = int(demanda_base * factor)
            # --- Dmax por sitio (opcional, margen de crecimiento 30%) ---
            Dmax_ij[i, j] = demanda_base * 1.3
    
    # ========================================================================
    # CALCULAR DEMANDA AGREGADA POR COMUNA (para McCormick)
    # ========================================================================
    D_jm = {}  # Demanda total por comuna y mes
    
    for j in J:
        for m in meses:
            D_jm[j, m] = sum(d_ijm.get((i, j, m), 0) for i in I[j])
    
    print(f"\n✓ Parámetros por sitio calculados")
    print(f"  - Demanda total: {sum(D_jm.values()):,} clientes")
    
    # ========================================================================
    # VARIABLES DE DECISIÓN (con lb=0 EXPLÍCITO en cada variable)
    # ========================================================================
    print("\n✓ Creando variables de decisión...")
    
    # Usar diccionarios para almacenar variables
    w = {}
    y = {}
    a = {}
    x = {}
    X = {}
    n_fast = {}
    n_slow = {}
    z = {}
    Z = {}
    r = {}
    s = {}
    e = {}
    d_sat = {}
    d_unsat = {}
    S_jm = {}
    phi_jm = {}
    psi_jm = {}
    
    # Crear variables con addVar individual para garantizar lb=0
    for j in J:
        for i in I[j]:
            # Infraestructura (una vez por sitio)
            w[i, j] = model.addVar(vtype=GRB.BINARY, name=f"w[{i},{j}]")
            
            for m in meses:
                # Infraestructura (por mes)
                y[i, j, m] = model.addVar(vtype=GRB.BINARY, name=f"y[{i},{j},{m}]")
                a[i, j, m] = model.addVar(vtype=GRB.BINARY, name=f"a[{i},{j},{m}]")
                
                # Cargadores
                x[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"x[{i},{j},{m}]")
                X[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"X[{i},{j},{m}]")
                n_fast[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_fast[{i},{j},{m}]")
                n_slow[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_slow[{i},{j},{m}]")
                
                # Paneles
                z[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"z[{i},{j},{m}]")
                Z[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Z[{i},{j},{m}]")
                
                # Energía
                r[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"r[{i},{j},{m}]")
                s[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"s[{i},{j},{m}]")
                e[i, j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"e[{i},{j},{m}]")
                
                # Demanda
                d_sat[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_sat[{i},{j},{m}]")
                d_unsat[i, j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_unsat[{i},{j},{m}]")
    
    # Variables agregadas por comuna
    for j in J:
        for m in meses:
            S_jm[j, m] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"S_jm[{j},{m}]")
            phi_jm[j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=1, name=f"phi_jm[{j},{m}]")
            psi_jm[j, m] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"psi_jm[{j},{m}]")
    
    model.update()
    print(f"  - Variables totales: {model.NumVars:,}")
    
    # ========================================================================
    # FUNCIÓN OBJETIVO
    # ========================================================================
    print("\n✓ Definiendo función objetivo...")
    
    # Beneficio ponderado por equidad y servicio
    beneficio_social = gp.quicksum(
        psi_jm[j, m] * params["V_cliente"] / SCALE
        for j in J for m in meses
    )
    
    # Beneficio ambiental (energía solar)
    beneficio_ambiental = gp.quicksum(
        params["B_CO2"] * s[i, j, m] / SCALE
        for j in J for i in I[j] for m in meses
    )
    
    objetivo = beneficio_social + beneficio_ambiental
    
    model.setObjective(objetivo, GRB.MAXIMIZE)
    print(f"  - Objetivo: MAXIMIZAR bienestar social")
    
    # ========================================================================
    # RESTRICCIONES
    # ========================================================================
    print("\n✓ Agregando restricciones...")
    
    # R1: Infraestructura final
    for j in J:
        for i in I[j]:
            model.addConstr(
                w[i, j] == q_ij[i, j] + gp.quicksum(y[i, j, m] for m in meses),
                name=f"R1_{i}_{j}"
            )
    
    # R2: Activación única
    for j in J:
        for i in I[j]:
            model.addConstr(
                gp.quicksum(y[i, j, m] for m in meses) <= 1 - q_ij[i, j],
                name=f"R2_{i}_{j}"
            )
    
    # R3: Total cargadores acumulados
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    X[i, j, m] == epsilon_ij[i, j] + gp.quicksum(
                        x[i, j, mp] for mp in range(1, m + 1)
                    ),
                    name=f"R3_{i}_{j}_{m}"
                )
    
    # R4: Total paneles acumulados
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    Z[i, j, m] == delta_ij[i, j] + gp.quicksum(
                        z[i, j, mp] for mp in range(1, m + 1)
                    ),
                    name=f"R4_{i}_{j}_{m}"
                )
    
    # R5: Estado operativo
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    a[i, j, m] >= q_ij[i, j] + gp.quicksum(
                        y[i, j, mp] for mp in range(1, m + 1)
                    ),
                    name=f"R5_{i}_{j}_{m}"
                )
                
                # Si ya existe infraestructura O cargadores, la estación debe estar activa
                if q_ij[i, j] == 1 or epsilon_ij[i, j] > 0:
                    model.addConstr(a[i, j, m] == 1, name=f"R5_force_active_{i}_{j}_{m}")
    
    # R6: Capacidad máxima de cargadores y paneles
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    X[i, j, m] <= Pcap_ij[i, j],
                    name=f"R6a_{i}_{j}_{m}"
                )
                model.addConstr(
                    Z[i, j, m] <= Zmax_ij[i, j],
                    name=f"R6b_{i}_{j}_{m}"
                )
    
    # R7: Cargadores rápidos y lentos
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    n_slow[i, j, m] + n_fast[i, j, m] == X[i, j, m],
                    name=f"R7_{i}_{j}_{m}"
                )
    
    # R8: Balance energético
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    e[i, j, m] == s[i, j, m] + r[i, j, m],
                    name=f"R8_{i}_{j}_{m}"
                )
    
    # R9: Producción máxima paneles
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    s[i, j, m] <= params["p"] * Z[i, j, m],
                    name=f"R9_{i}_{j}_{m}"
                )
    
    # R10: Importación máxima red
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    r[i, j, m] <= g_max_ij[i, j] * a[i, j, m],
                    name=f"R10_{i}_{j}_{m}"
                )
    
    # R11: Límite energético por cargador
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    n_fast[i, j, m] * params["beta_fast"] + 
                    n_slow[i, j, m] * params["beta_slow"] <= e[i, j, m],
                    name=f"R11_{i}_{j}_{m}"
                )
    
    # R12: Demanda satisfecha limitada por capacidad
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    d_sat[i, j, m] <= params["C"] * X[i, j, m],
                    name=f"R12_{i}_{j}_{m}"
                )
    
    # R13: Balance demanda satisfecha/insatisfecha
    for j in J:
        for i in I[j]:
            for m in meses:
                model.addConstr(
                    d_sat[i, j, m] + d_unsat[i, j, m] == d_ijm[i, j, m],
                    name=f"R13_{i}_{j}_{m}"
                )
    
    # R14: Agregación demanda por comuna
    for j in J:
        for m in meses:
            model.addConstr(
                S_jm[j, m] == gp.quicksum(d_sat[i, j, m] for i in I[j]),
                name=f"R14_{j}_{m}"
            )
    
    # R15: Definición de phi (linearización de φ = 1 - S/D)
    for j in J:
        for m in meses:
            D_total = D_jm[j, m]
            if D_total > 0:
                # D_total * φ = D_total - S
                model.addConstr(
                    D_total * phi_jm[j, m] == D_total - S_jm[j, m],
                    name=f"R15_{j}_{m}"
                )
            else:
                model.addConstr(
                    phi_jm[j, m] == 0,
                    name=f"R15_zero_{j}_{m}"
                )
    
    # R16: Equidad entre comunas (solo mes final M)
    for j in J:
        for l in J:
            if j < l:  # Evitar duplicados
                model.addConstr(
                    phi_jm[j, M] <= 2.0 * phi_jm[l, M],
                    name=f"R16_{j}_{l}"
                )
    
    # R17: Cobertura mínima (φ ≤ α_min significa al menos 70% cubierto)
    for j in J:
        model.addConstr(
            phi_jm[j, M] <= params["alpha_min"],
            name=f"R17_{j}"
        )
    
    # R18: McCormick para ψ = φ * S
    for j in J:
        for m in meses:
            S_max = D_jm[j, m]
            if S_max > 0:
                model.addConstr(psi_jm[j, m] >= 0, 
                               name=f"R18a_{j}_{m}")
                model.addConstr(
                    psi_jm[j, m] >= S_jm[j, m] + phi_jm[j, m] * S_max - S_max,
                    name=f"R18b_{j}_{m}"
                )
                model.addConstr(psi_jm[j, m] <= S_jm[j, m], 
                               name=f"R18c_{j}_{m}")
                model.addConstr(psi_jm[j, m] <= phi_jm[j, m] * S_max, 
                               name=f"R18d_{j}_{m}")
            else:
                model.addConstr(psi_jm[j, m] == 0, 
                               name=f"R18_zero_{j}_{m}")
    
    # R19: Restricción presupuestaria
    costo_total = gp.LinExpr()
    
    for j in J:
        for i in I[j]:
            for m in meses:
                # Activación infraestructura (asumir promedio)
                costo_total += params["k"] * y[i, j, m] / SCALE
                
                # Instalación cargadores (asumir promedio)
                costo_total += params["c_slow"] * x[i, j, m] / SCALE
                
                # Mantenimiento cargadores (asumir promedio)
                costo_total += params["h"] * X[i, j, m] / SCALE
                
                # Instalación paneles
                costo_total += params["v"] * z[i, j, m] / SCALE
                
                # Mantenimiento paneles
                costo_total += params["m"] * Z[i, j, m] / SCALE
                
                # Energía de la red
                costo_total += params["p_red"] * r[i, j, m] / SCALE
    
    model.addConstr(
        costo_total <= params["B"] / SCALE,
        name="R19_presupuesto"
    )
    
    print(f"  - Restricciones totales: {model.NumConstrs:,}")
    
    # ========================================================================
    # CONFIGURACIÓN DEL SOLVER
    # ========================================================================
    print("\n✓ Configurando solver...")
    model.Params.TimeLimit = 3600  # 1 hora
    model.Params.MIPGap = 0.02     # 2% gap
    model.Params.Threads = 0       # Usar todos los núcleos disponibles
    
    # ========================================================================
    # OPTIMIZACIÓN
    # ========================================================================
    print("\n" + "="*70)
    print("INICIANDO OPTIMIZACIÓN")
    print("="*70)
    
    model.optimize()
    
    # ========================================================================
    # DIAGNÓSTICO DE INFACTIBILIDAD
    # ========================================================================
    if model.Status == GRB.INF_OR_UNBD or model.Status == GRB.INFEASIBLE:
        print("\n⚠ MODELO INFACTIBLE - EJECUTANDO DIAGNÓSTICO...")
        model.computeIIS()
        ilp_file = "modelo_completo_latex_conflictos.ilp"
        model.write(ilp_file)
        print(f"\n✓ Restricciones conflictivas guardadas en: {ilp_file}")
        
        # Contar restricciones conflictivas
        conflictos = 0
        print("\n  Primeras restricciones conflictivas:")
        for c in model.getConstrs():
            if c.IISConstr:
                conflictos += 1
                if conflictos <= 20:  # Mostrar primeras 20
                    print(f"    - {c.ConstrName}")
        print(f"\n  Total restricciones conflictivas: {conflictos}")
    
    # ========================================================================
    # ANÁLISIS DE RESULTADOS
    # ========================================================================
    print("\n" + "="*70)
    print("RESULTADOS DE LA OPTIMIZACIÓN")
    print("="*70)
    
    resumen = {}
    
    if model.Status == GRB.OPTIMAL:
        print("\n✓ SOLUCIÓN ÓPTIMA ENCONTRADA")
        resumen["status"] = "OPTIMAL"
        resumen["objetivo"] = model.ObjVal * SCALE
        resumen["gap"] = 0
        
    elif model.Status == GRB.TIME_LIMIT:
        print("\n⚠ LÍMITE DE TIEMPO ALCANZADO")
        if model.SolCount > 0:
            resumen["status"] = "TIME_LIMIT_WITH_SOLUTION"
            resumen["objetivo"] = model.ObjVal * SCALE
            resumen["gap"] = model.MIPGap
        else:
            resumen["status"] = "TIME_LIMIT_NO_SOLUTION"
            return model, resumen
            
    elif model.Status == GRB.INFEASIBLE:
        print("\n✗ MODELO INFACTIBLE")
        resumen["status"] = "INFEASIBLE"
        model.computeIIS()
        model.write("modelo_infactible.ilp")
        print("  - Sistema de restricciones irreducible guardado en modelo_infactible.ilp")
        return model, resumen
        
    else:
        print(f"\n✗ ESTADO NO MANEJADO: {model.Status}")
        resumen["status"] = f"STATUS_{model.Status}"
        return model, resumen
    
    # ========================================================================
    # EXTRACCIÓN Y RESUMEN DE LA SOLUCIÓN
    # ========================================================================
    print(f"\nValor objetivo: {resumen['objetivo']:,.0f} CLP")
    if "gap" in resumen:
        print(f"Gap: {resumen['gap']*100:.2f}%")
    
    # Contar decisiones
    estaciones_activadas = sum(
        1 for j in J for i in I[j] 
        if w[i, j].X > 0.5
    )
    
    cargadores_nuevos = sum(
        x[i, j, m].X 
        for j in J for i in I[j] for m in meses
    )
    
    paneles_nuevos = sum(
        z[i, j, m].X 
        for j in J for i in I[j] for m in meses
    )
    
    demanda_total = sum(d_ijm.values())
    demanda_satisfecha = sum(
        d_sat[i, j, m].X 
        for j in J for i in I[j] for m in meses
    )
    
    energia_solar = sum(
        s[i, j, m].X 
        for j in J for i in I[j] for m in meses
    )
    
    energia_red = sum(
        r[i, j, m].X 
        for j in J for i in I[j] for m in meses
    )
    
    resumen["estaciones_activadas"] = estaciones_activadas
    resumen["cargadores_nuevos"] = cargadores_nuevos
    resumen["paneles_nuevos"] = paneles_nuevos
    resumen["demanda_total"] = demanda_total
    resumen["demanda_satisfecha"] = demanda_satisfecha
    resumen["cobertura_pct"] = (demanda_satisfecha / demanda_total * 100) if demanda_total > 0 else 0
    resumen["energia_solar_kWh"] = energia_solar
    resumen["energia_red_kWh"] = energia_red
    
    print("\n" + "="*70)
    print("RESUMEN DE LA SOLUCIÓN")
    print("="*70)
    print(f"Estaciones activadas: {estaciones_activadas}")
    print(f"Cargadores nuevos instalados: {cargadores_nuevos:,.0f}")
    print(f"Paneles FV nuevos instalados: {paneles_nuevos:,.0f}")
    print(f"\nDEMANDA:")
    print(f"  Total: {demanda_total:,} clientes")
    print(f"  Satisfecha: {demanda_satisfecha:,.0f} clientes")
    print(f"  Cobertura: {resumen['cobertura_pct']:.1f}%")
    print(f"\nENERGÍA:")
    print(f"  Solar: {energia_solar:,.1f} kWh")
    print(f"  Red: {energia_red:,.1f} kWh")
    print(f"  % Renovable: {(energia_solar/(energia_solar+energia_red)*100) if (energia_solar+energia_red) > 0 else 0:.1f}%")
    print("="*70)
    
    return model, resumen


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Función principal que ejecuta el modelo completo"""
    
    print("\n" + "="*70)
    print("MODELO DE OPTIMIZACIÓN - INFRAESTRUCTURA DE CARGA VE")
    print("Implementación según especificación LaTeX")
    print("="*70)
    
    # Descubrir comunas
    try:
        comunas = descubrir_comunas()
    except Exception as e:
        print(f"\n✗ Error al descubrir comunas: {e}")
        return
    
    # Cargar datos
    print("\n✓ Cargando datos de sitios...")
    datos_comunas = {}
    for j in comunas:
        df = cargar_sitios_comuna(j)
        if not df.empty:
            datos_comunas[j] = df
    
    if not datos_comunas:
        print("\n✗ No se cargaron datos de ninguna comuna")
        return
    
    print(f"  - Comunas con datos: {len(datos_comunas)}")
    
    # Definir parámetros (comenzar con M=1 para prueba)
    params = definir_parametros(M=1)
    
    # Construir y resolver modelo
    try:
        modelo, resumen = construir_y_resolver_modelo(comunas, datos_comunas, params)
        
        # Guardar modelo
        modelo.write("modelo_completo_latex.lp")
        print(f"\n✓ Modelo guardado en: modelo_completo_latex.lp")
        
        # Guardar solución si existe
        if modelo.SolCount > 0:
            modelo.write("solucion_completo_latex.sol")
            print(f"✓ Solución guardada en: solucion_completo_latex.sol")
        
    except Exception as e:
        print(f"\n✗ Error durante la optimización: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✓ Proceso completado")


if __name__ == "__main__":
    main()
