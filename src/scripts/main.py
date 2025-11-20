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
RESULTADOS_DIR = os.path.join(ROOT, "resultados")


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

def definir_parametros(M=12):
    """
    Define todos los parámetros del modelo según la especificación LaTeX.
    
    Parámetros:
        M: Horizonte de planificación en AÑOS (default: 12 años)
    
    Retorna:
        dict con todos los parámetros del modelo (todos anualizados)
    """
    
    params = {
        # ============================================================
        # HORIZONTE TEMPORAL
        # ============================================================
        "M": M,  # Número de AÑOS del proyecto
        
        # ============================================================
        # INFRAESTRUCTURA
        # ============================================================
        "k_slow": 6_500_000,   # CLP - Costo fijo activación carga lenta
        "k_fast": 20_000_000,  # CLP - Costo fijo activación carga rápida
        "k": (6_500_000 + 20_000_000)/2,  # CLP - Costo fijo activación (promedio)
        
        # ============================================================
        # CARGADORES (VALORES ANUALIZADOS: mensual × 12)
        # ============================================================
        "c_slow": 2_000_000,   # CLP - Costo instalación cargador lento
        "c_fast": 49_000_000,  # CLP - Costo instalación cargador rápido
        "h_slow": 63_000 * 12,      # CLP/año - Mantenimiento cargador lento
        "h_fast": 119_000 * 12,     # CLP/año - Mantenimiento cargador rápido
        "h": (63_000 + 119_000)/2 * 12,  # CLP/año - Mantenimiento cargador (promedio)
        "beta_slow": 1_188 * 12,    # kWh/año - Capacidad energética cargador lento
        "beta_fast": 2_700 * 12,    # kWh/año - Capacidad energética cargador rápido
        "C": 7200,              # clientes/año - Clientes por cargador
        
        # ============================================================
        # PANELES FOTOVOLTAICOS (VALORES ANUALIZADOS)
        # ============================================================
        "v": 900_000,          # CLP - Costo instalación panel FV
        "m": 625 * 12,         # CLP/año - Mantenimiento panel FV
        "p": 56.25 * 12,       # kWh/panel/año - Producción panel FV
        
        # ============================================================
        # ENERGÍA
        # ============================================================
        "p_red": 180,          # CLP/kWh - Precio energía de la red
        "CI": 18.07,           # CLP/kWh - Costo emisiones red
        "g_max_default": 50000 * 12, # kWh/año - Límite importación red (default)
        
        # ============================================================
        # CAPACIDADES FÍSICAS (defaults si no están en CSV)
        # ============================================================
        "Pcap_default": 10,    # Cargadores máximos por estación
        "Zmax_default": 20,    # Paneles máximos por estación
        
        # ============================================================
        # DEMANDA Y SERVICIO
        # ============================================================
        "alpha_min": 0.4,     # Objetivo cobertura mínima (φ ≤ 0.30)
        "V_cliente": 1_200,   # CLP - Valor social por cliente atendido
        "mu_prom": 30,        # kWh - Consumo promedio por sesión de carga
        "Delta_eq": 0.15,     # Umbral máximo de inequidad entre comunas (15%)
        
        # ============================================================
        # BENEFICIOS AMBIENTALES
        # ============================================================
        "B_CO2": 18.07,        # CLP/kWh - Beneficio social energía renovable
        
        # ============================================================
        # PRESUPUESTO TOTAL
        # ============================================================
        "B": 500_000_000_000,  # CLP - Presupuesto total (500 mil millones)
        
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
    
    periodos = range(1, M + 1)  # Períodos anuales (años)
    
    print(f"\n✓ Conjuntos definidos:")
    print(f"  - Comunas (J): {len(J)}")
    print(f"  - Sitios totales: {sum(len(I[j]) for j in J)}")
    print(f"  - Horizonte temporal: {M} años")
    
    # ========================================================================
    # PARÁMETROS POR SITIO
    # ========================================================================
    q_ij = {}      # Infraestructura existente (0 o 1)
    epsilon_ij = {} # Cargadores iniciales
    delta_ij = {}  # Paneles iniciales
    Pcap_ij = {}   # Capacidad máxima cargadores
    Zmax_ij = {}   # Capacidad máxima paneles
    g_max_ij = {}  # Límite importación red
    d_ijm = {}     # Demanda de clientes por sitio y período (año)
    
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
            demanda_base_anual = row.get('demand_estimated', 0) * 12 * factor_tipo  # Anualizar demanda
            # --- Demanda por período (año) con crecimiento compuesto ---
            for periodo in periodos:
                factor = (1 + g) ** (periodo - 1)  # Crecimiento anual directo
                d_ijm[i, j, periodo] = int(demanda_base_anual * factor)
            # --- Dmax por sitio (opcional, margen de crecimiento 30%) ---
            Dmax_ij[i, j] = demanda_base_anual * 1.3
    
    # ========================================================================
    # CALCULAR DEMANDA AGREGADA POR COMUNA (para McCormick)
    # ========================================================================
    D_jm = {}  # Demanda total por comuna y período
    
    for j in J:
        for periodo in periodos:
            D_jm[j, periodo] = sum(d_ijm.get((i, j, periodo), 0) for i in I[j])
    
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
            
            for periodo in periodos:
                # Infraestructura (por período)
                y[i, j, periodo] = model.addVar(vtype=GRB.BINARY, name=f"y[{i},{j},{periodo}]")
                a[i, j, periodo] = model.addVar(vtype=GRB.BINARY, name=f"a[{i},{j},{periodo}]")
                
                # Cargadores
                x[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"x[{i},{j},{periodo}]")
                X[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"X[{i},{j},{periodo}]")
                n_fast[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_fast[{i},{j},{periodo}]")
                n_slow[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"n_slow[{i},{j},{periodo}]")
                
                # Paneles
                z[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"z[{i},{j},{periodo}]")
                Z[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Z[{i},{j},{periodo}]")
                
                # Energía
                r[i, j, periodo] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"r[{i},{j},{periodo}]")
                s[i, j, periodo] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"s[{i},{j},{periodo}]")
                e[i, j, periodo] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"e[{i},{j},{periodo}]")
                
                # Demanda
                d_sat[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_sat[{i},{j},{periodo}]")
                d_unsat[i, j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_unsat[{i},{j},{periodo}]")
    
    # Variables agregadas por comuna
    for j in J:
        for periodo in periodos:
            S_jm[j, periodo] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"S_jm[{j},{periodo}]")
            phi_jm[j, periodo] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=1, name=f"phi_jm[{j},{periodo}]")
    
    model.update()
    print(f"  - Variables totales: {model.NumVars:,}")
    
    # ========================================================================
    # FUNCIÓN OBJETIVO (SIMPLIFICADA: S × V_cliente)
    # ========================================================================
    print("\n✓ Definiendo función objetivo...")
    
    # Beneficio social (demanda satisfecha directa)
    # Maximizar: Σ S_jt × V_cliente
    # Interpretación: cada cliente atendido vale V_cliente = 1,200 CLP
    beneficio_social = gp.quicksum(
        S_jm[j, periodo] * params["V_cliente"] / SCALE
        for j in J for periodo in periodos
    )
    
    # Beneficio ambiental (energía solar)
    beneficio_ambiental = gp.quicksum(
        params["B_CO2"] * s[i, j, periodo] / SCALE
        for j in J for i in I[j] for periodo in periodos
    )
    
    objetivo = beneficio_social + beneficio_ambiental
    
    model.setObjective(objetivo, GRB.MAXIMIZE)
    print(f"  - Objetivo: MAXIMIZAR demanda satisfecha + energía solar")
    
    # ========================================================================
    # RESTRICCIONES
    # ========================================================================
    print("\n✓ Agregando restricciones...")
    
    # R1: Infraestructura final
    for j in J:
        for i in I[j]:
            model.addConstr(
                w[i, j] == q_ij[i, j] + gp.quicksum(y[i, j, periodo] for periodo in periodos),
                name=f"R1_{i}_{j}"
            )
    
    # R2: Activación única
    for j in J:
        for i in I[j]:
            model.addConstr(
                gp.quicksum(y[i, j, periodo] for periodo in periodos) <= 1 - q_ij[i, j],
                name=f"R2_{i}_{j}"
            )
    
    # R3: Total cargadores acumulados
    # X_ijt = ε_ij + Σ(t'≤t) x_ijt' (t = período en años)
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    X[i, j, periodo] == epsilon_ij[i, j] + gp.quicksum(
                        x[i, j, p] for p in range(1, periodo + 1)
                    ),
                    name=f"R3_{i}_{j}_{periodo}"
                )
    
    # R4: Total paneles acumulados
    # Z_ijt = δ_ij + Σ(t'≤t) z_ijt' 
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    Z[i, j, periodo] == delta_ij[i, j] + gp.quicksum(
                        z[i, j, p] for p in range(1, periodo + 1)
                    ),
                    name=f"R4_{i}_{j}_{periodo}"
                )
    
    # R4b: Instalación de estación requiere cargadores (LaTeX)
    # y_ijt ≤ X_ijt (si activas, debe haber al menos 1 cargador)
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    y[i, j, periodo] <= X[i, j, periodo],
                    name=f"R4b_{i}_{j}_{periodo}"
                )
    
    # R4c: NUEVA - Instalar cargadores requiere estación activa
    # x_ijt ≤ M_big × a_ijt (solo puedes instalar si la estación opera)
    M_big = 1000  # Suficientemente grande
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    x[i, j, periodo] <= M_big * a[i, j, periodo],
                    name=f"R4c_instalar_requiere_activa_{i}_{j}_{periodo}"
                )
    
    # R4d: NUEVA - Tener cargadores finales requiere estación abierta
    # X_ijM ≤ M_big × w_ij (si hay cargadores al final, estación abierta)
    for j in J:
        for i in I[j]:
            model.addConstr(
                X[i, j, M] <= M_big * w[i, j],
                name=f"R4d_cargadores_requieren_estacion_{i}_{j}"
            )
    
    
    # R5: Estado operativo por período
    # a_ijt ≥ q_ij + Σ(t'≤t) y_ijt', a_ijt ∈ {0,1}
    # La estación está activa si existía o se activó en algún período anterior
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    a[i, j, periodo] >= q_ij[i, j] + gp.quicksum(  # ✅ >= no ==
                        y[i, j, p] for p in range(1, periodo + 1)
                    ),
                    name=f"R5_{i}_{j}_{periodo}"
                )


    # R6: Cotas superiores de capacidad y operación
    # X_ijt ≤ P^cap_ij * a_ijt, Z_ijt ≤ Z^max_ij * a_ijt (stock = 0 si no está activa)
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    X[i, j, periodo] <= Pcap_ij[i, j] * a[i, j, periodo],
                    name=f"R6a_{i}_{j}_{periodo}"
                )
                model.addConstr(
                    Z[i, j, periodo] <= Zmax_ij[i, j] * a[i, j, periodo],
                    name=f"R6b_{i}_{j}_{periodo}"
                )
    
    # R7: Cargadores rápidos y lentos
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    n_slow[i, j, periodo] + n_fast[i, j, periodo] == X[i, j, periodo],
                    name=f"R7_{i}_{j}_{periodo}"
                )
    
    # R8: Balance energético
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    e[i, j, periodo] == s[i, j, periodo] + r[i, j, periodo],
                    name=f"R8_{i}_{j}_{periodo}"
                )
    
    # R9: Producción máxima paneles
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    s[i, j, periodo] <= params["p"] * Z[i, j, periodo],
                    name=f"R9_{i}_{j}_{periodo}"
                )
    
    # R10: Importación máxima red
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    r[i, j, periodo] <= g_max_ij[i, j] * a[i, j, periodo],
                    name=f"R10_{i}_{j}_{periodo}"
                )
    
    # R11: Límite energético por cargador
    # e_ijt ≤ n^fast_ijt * β^fast + n^slow_ijt * β^slow
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    e[i, j, periodo] <= n_fast[i, j, periodo] * params["beta_fast"] + 
                                        n_slow[i, j, periodo] * params["beta_slow"],
                    name=f"R11_{i}_{j}_{periodo}"
                )
    
    # R12: Vinculación demanda-energía
    # e_ijt ≥ d^sat_ijt * μ_prom
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    e[i, j, periodo] >= d_sat[i, j, periodo] * params["mu_prom"],
                    name=f"R12_{i}_{j}_{periodo}"
                )
    
    # R13: Demanda de cargadores por período (era R12)
    # d^sat_ijt ≤ C·X_ijt
    # La demanda satisfecha depende de la cantidad de cargadores y su promedio de clientes atendidos
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    d_sat[i, j, periodo] <= params["C"] * X[i, j, periodo],
                    name=f"R13_{i}_{j}_{periodo}"
                )
    
    # R14: Demanda satisfecha e insatisfecha (era R13)
    # d^sat_ijt + d^unsat_ijt = d_ijt
    # La demanda total se reparte entre clientes atendidos y no atendidos
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                model.addConstr(
                    d_sat[i, j, periodo] + d_unsat[i, j, periodo] == d_ijm[i, j, periodo],
                    name=f"R14_{i}_{j}_{periodo}"
                )
    
    # R15: Agregación demanda por comuna (era R14)
    for j in J:
        for periodo in periodos:
            model.addConstr(
                S_jm[j, periodo] == gp.quicksum(d_sat[i, j, periodo] for i in I[j]),
                name=f"R15_{j}_{periodo}"
            )
    
    # R16: Definición de phi (linearización de φ = 1 - S/D) (era R15)
    for j in J:
        for periodo in periodos:
            D_total = D_jm[j, periodo]
            if D_total > 0:
                # D_total * φ = D_total - S
                model.addConstr(
                    D_total * phi_jm[j, periodo] == D_total - S_jm[j, periodo],
                    name=f"R16_{j}_{periodo}"
                )
            else:
                model.addConstr(
                    phi_jm[j, periodo] == 0,
                    name=f"R16_zero_{j}_{periodo}"
                )
    
    # R17: Equidad entre comunas (solo período final M) (era R16)
    # φ_j,M - φ_l,M ≤ Δ_eq (la diferencia no puede exceder el umbral)
    for j in J:
        for l in J:
            if j < l:  # Evitar duplicados
                model.addConstr(
                    phi_jm[j, M] - phi_jm[l, M] <= params["Delta_eq"],
                    name=f"R17a_{j}_{l}"
                )
                model.addConstr(
                    phi_jm[l, M] - phi_jm[j, M] <= params["Delta_eq"],
                    name=f"R17b_{j}_{l}"
                )
    
    # R18: Cobertura mínima (φ ≤ α_min significa al menos 70% cubierto) (era R17)
    for j in J:
        model.addConstr(
            phi_jm[j, M] <= params["alpha_min"],
            name=f"R18_{j}"
        )
    
    # R19: Restricción presupuestaria (era R20)
    costo_total = gp.LinExpr()
    
    for j in J:
        for i in I[j]:
            for periodo in periodos:
                # Activación infraestructura (asumir promedio)
                costo_total += params["k"] * y[i, j, periodo] / SCALE
                
                # Instalación cargadores (asumir promedio)
                costo_total += params["c_slow"] * x[i, j, periodo] / SCALE
                
                # Mantenimiento cargadores (asumir promedio)
                costo_total += params["h"] * X[i, j, periodo] / SCALE
                
                # Instalación paneles
                costo_total += params["v"] * z[i, j, periodo] / SCALE
                
                # Mantenimiento paneles
                costo_total += params["m"] * Z[i, j, periodo] / SCALE
                
                # Energía de la red
                costo_total += params["p_red"] * r[i, j, periodo] / SCALE
    
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
        ilp_file = os.path.join(RESULTADOS_DIR, "modelo_completo_latex_conflictos.ilp")
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
        ilp_file = os.path.join(RESULTADOS_DIR, "modelo_infactible.ilp")
        model.write(ilp_file)
        print(f"  - Sistema de restricciones irreducible guardado en: {ilp_file}")
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
        for j in J for i in I[j] for m in periodos
    )
    
    paneles_nuevos = sum(
        z[i, j, m].X 
        for j in J for i in I[j] for m in periodos
    )
    
    demanda_total = sum(d_ijm.values())
    demanda_satisfecha = sum(
        d_sat[i, j, m].X 
        for j in J for i in I[j] for m in periodos
    )
    
    energia_solar = sum(
        s[i, j, m].X 
        for j in J for i in I[j] for m in periodos
    )
    
    energia_red = sum(
        r[i, j, m].X 
        for j in J for i in I[j] for m in periodos
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
    
    # Definir parámetros - AHORA M ES EN AÑOS
    # M=3 significa 3 años (antes era 3 meses)
    params = definir_parametros(M=6)
    
    print(f"\n✓ Parámetros definidos (horizonte: {params['M']} años)")
    
    # Construir y resolver modelo
    try:
        modelo, resumen = construir_y_resolver_modelo(comunas, datos_comunas, params)
        
        # Crear carpeta resultados si no existe
        os.makedirs(os.path.join(ROOT, "resultados"), exist_ok=True)
        
        # Guardar modelo
        modelo_file = os.path.join(ROOT, "resultados", "modelo_completo_latex.lp")
        modelo.write(modelo_file)
        print(f"\n✓ Modelo guardado en: {modelo_file}")

        # Guardar solución si existe
        if modelo.SolCount > 0:
            sol_file = os.path.join(ROOT, "resultados", "solucion_completo_latex.sol")
            modelo.write(sol_file)
            print(f"✓ Solución guardada en: {sol_file}")
        
    except Exception as e:
        print(f"\n✗ Error durante la optimización: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✓ Proceso completado")


if __name__ == "__main__":
    main()
