#!/usr/bin/env python3
"""
test_minimal_model.py
=====================
Modelo MÍNIMO para identificar qué está mal
"""

import pandas as pd
import glob
import gurobipy as gp
from gurobipy import GRB

# Cargar UNA comuna pequeña
df = pd.read_csv('combinado_epc_dpc/pirque.csv')

print("\n" + "="*80)
print("TEST MODELO MÍNIMO - 1 Comuna (Pirque)")
print("="*80 + "\n")

# Filtrar candidatos (q=0)
candidatos = df[df['cargadores_iniciales'] == 0].copy()
print(f"Candidatos totales: {len(candidatos)}")

if len(candidatos) == 0:
    print("❌ No hay candidatos en Pirque, probando con otra comuna...")
    df = pd.read_csv('combinado_epc_dpc/padre_hurtado.csv')
    candidatos = df[df['cargadores_iniciales'] == 0].copy()
    print(f"Candidatos en Padre Hurtado: {len(candidatos)}")

# Tomar solo 5 sitios para simplificar
candidatos = candidatos.head(5)
print(f"Usando {len(candidatos)} sitios para test\n")

# Parámetros
M = 1  # Solo 1 mes para simplificar
k_slow = 2_000_000
c_slow = 2_000_000
C = 180
V_cliente = 50_000
B = 500_000_000_000

# Crear modelo
model = gp.Model("Test_Minimal")
model.setParam('OutputFlag', 1)
model.setParam('LogFile', 'gurobi_minimal.log')

# Variables
print("Creando variables...")
y = {}  # Activación
x = {}  # Cargadores instalados
X = {}  # Total cargadores
d_sat = {}  # Demanda satisfecha
d_unsat = {}  # Demanda insatisfecha

for idx, row in candidatos.iterrows():
    i = int(idx)
    
    # Demanda de este sitio
    demand = int(row['demand_estimated']) if pd.notna(row['demand_estimated']) else 100
    
    y[i] = model.addVar(vtype=GRB.BINARY, name=f"y_{i}")
    x[i] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"x_{i}")
    X[i] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"X_{i}")
    d_sat[i] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_sat_{i}")
    d_unsat[i] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"d_unsat_{i}")
    
    print(f"  Sitio {i}: demanda = {demand}")

model.update()
print(f"\nVariables creadas: {model.NumVars}")

# Restricciones
print("\nAgregando restricciones...")

for idx, row in candidatos.iterrows():
    i = int(idx)
    epsilon = int(row['cargadores_iniciales'])
    pcap = int(row['dpc_Pcap'])
    demand = int(row['demand_estimated']) if pd.notna(row['demand_estimated']) else 100
    
    # R2: Activar máximo una vez
    model.addConstr(y[i] <= 1, name=f"R2_{i}")
    
    # R3: Acumulación (simplificado para M=1)
    model.addConstr(X[i] == epsilon + x[i], name=f"R3_{i}")
    
    # R6: Capacidad (solo si activo)
    model.addConstr(X[i] <= pcap * y[i], name=f"R6_{i}")
    
    # R12: Capacidad de atención
    model.addConstr(d_sat[i] <= C * X[i], name=f"R12_{i}")
    
    # R13: Balance demanda
    model.addConstr(d_sat[i] + d_unsat[i] == demand, name=f"R13_{i}")

# Presupuesto
total_cost = gp.quicksum(k_slow * y[i] + c_slow * x[i] for i in y.keys())
model.addConstr(total_cost <= B, name="budget")

print(f"Restricciones: {model.NumConstrs}")

# Objetivo: Maximizar demanda satisfecha
obj = gp.quicksum(d_sat[i] * V_cliente for i in d_sat.keys())
model.setObjective(obj, GRB.MAXIMIZE)

print(f"\nObjetivo: Maximizar Σ(d_sat × {V_cliente:,})\n")

# Resolver
print("="*80)
print("RESOLVIENDO...")
print("="*80 + "\n")

model.optimize()

# Resultados
print("\n" + "="*80)
print("RESULTADO")
print("="*80 + "\n")

print(f"Status:      {model.status}")
print(f"Variables:   {model.NumVars}")
print(f"Restricciones: {model.NumConstrs}")

if model.status == GRB.OPTIMAL:
    print(f"Objetivo:    ${model.objVal:,.0f} CLP")
    
    print("\nSitios activados:")
    activados = 0
    for i in y.keys():
        if y[i].X > 0.5:
            activados += 1
            print(f"  Sitio {i}: y=1, X={int(X[i].X)}, d_sat={int(d_sat[i].X)}")
    
    if activados == 0:
        print("  ❌ NINGUNO")
        print("\n🚨 PROBLEMA: Modelo no activa sitios pese a ser rentables")
        
        print("\n📊 Análisis de valores duales:")
        for c in model.getConstrs():
            if c.Pi != 0:
                print(f"  {c.ConstrName}: Pi = {c.Pi:.2f}")
    else:
        print(f"\n✅ Se activaron {activados} sitios")

elif model.status == GRB.INFEASIBLE:
    print("\n🔴 INFACTIBLE")
    model.computeIIS()
    model.write("minimal_infeasible.ilp")
    print("IIS guardado en: minimal_infeasible.ilp")
    
    print("\nRestricciones en conflicto:")
    for c in model.getConstrs():
        if c.IISConstr:
            print(f"  - {c.ConstrName}")

else:
    print(f"\n⚠️  Status desconocido: {model.status}")

print("\n📋 Log completo guardado en: gurobi_minimal.log")