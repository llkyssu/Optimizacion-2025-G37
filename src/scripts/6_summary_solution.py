#!/usr/bin/env python3
"""
6_summary_solution.py

Lee results_optimization.csv y muestra un resumen por comuna de las estaciones instaladas
y principales agregados (cargadores, paneles, demanda satisfecha, energía).
"""
import os
import sys

try:
    import pandas as pd
except Exception:
    print("ERROR: instalar pandas: pip install pandas")
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(ROOT, "results_optimization.csv")
OUT_SUMMARY = os.path.join(ROOT, "results_summary_by_comuna.csv")

if not os.path.isfile(RESULTS_PATH):
    print(f"No se encontró '{RESULTS_PATH}'. Ejecuta primero el solver (5_solve_optimization.py).")
    sys.exit(1)

df = pd.read_csv(RESULTS_PATH)

# Asegurar columnas esperadas
expected = ["comuna", "activated", "active", "chargers_total", "chargers_new",
            "panels_total", "panels_new", "demand_estimated", "demand_satisfied",
            "solar_used_kwh", "grid_used_kwh"]
for c in expected:
    if c not in df.columns:
        df[c] = 0

# Normalizar tipos numéricos
numcols = ["activated", "active", "chargers_total", "chargers_new", "panels_total",
           "panels_new", "demand_estimated", "demand_satisfied", "solar_used_kwh", "grid_used_kwh"]
for c in numcols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

agg = df.groupby("comuna").agg(
    sites_total = ("site_id", "count"),
    sites_activated = ("activated", "sum"),
    sites_active = ("active", "sum"),
    chargers_total = ("chargers_total", "sum"),
    chargers_new = ("chargers_new", "sum"),
    panels_total = ("panels_total", "sum"),
    panels_new = ("panels_new", "sum"),
    demand_estimated = ("demand_estimated", "sum"),
    demand_satisfied = ("demand_satisfied", "sum"),
    solar_kwh = ("solar_used_kwh", "sum"),
    grid_kwh = ("grid_used_kwh", "sum")
).reset_index()

# Métricas derivadas
agg["pct_demand_satisfied"] = (agg["demand_satisfied"] / agg["demand_estimated"]).replace([float("inf"), float("nan")], 0.0) * 100.0
agg["pct_demand_satisfied"] = agg["pct_demand_satisfied"].round(1)

# Imprimir resumen por comuna (ordenado por demand_estimated desc)
print("\nResumen por comuna (ordenado por demanda estimada):\n")
display_cols = ["comuna","sites_total","sites_activated","sites_active","chargers_total","chargers_new",
                "panels_total","panels_new","demand_estimated","demand_satisfied","pct_demand_satisfied",
                "solar_kwh","grid_kwh"]
print(agg.sort_values("demand_estimated", ascending=False)[display_cols].to_string(index=False))

# Guardar CSV resumen
agg.to_csv(OUT_SUMMARY, index=False)
print(f"\nResumen guardado en: {OUT_SUMMARY}")
# filepath: /Users/max/Desktop/opti/Optimizacion-2025-G37/src/scripts/6_summary_solution.py
#!/usr/bin/env python3
"""
6_summary_solution.py

Lee results_optimization.csv y muestra un resumen por comuna de las estaciones instaladas
y principales agregados (cargadores, paneles, demanda satisfecha, energía).
"""
import os
import sys

try:
    import pandas as pd
except Exception:
    print("ERROR: instalar pandas: pip install pandas")
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(ROOT, "results_optimization.csv")
OUT_SUMMARY = os.path.join(ROOT, "results_summary_by_comuna.csv")

if not os.path.isfile(RESULTS_PATH):
    print(f"No se encontró '{RESULTS_PATH}'. Ejecuta primero el solver (5_solve_optimization.py).")
    sys.exit(1)

df = pd.read_csv(RESULTS_PATH)

# Asegurar columnas esperadas
expected = ["comuna", "activated", "active", "chargers_total", "chargers_new",
            "panels_total", "panels_new", "demand_estimated", "demand_satisfied",
            "solar_used_kwh", "grid_used_kwh"]
for c in expected:
    if c not in df.columns:
        df[c] = 0

# Normalizar tipos numéricos
numcols = ["activated", "active", "chargers_total", "chargers_new", "panels_total",
           "panels_new", "demand_estimated", "demand_satisfied", "solar_used_kwh", "grid_used_kwh"]
for c in numcols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

agg = df.groupby("comuna").agg(
    sites_total = ("site_id", "count"),
    sites_activated = ("activated", "sum"),
    sites_active = ("active", "sum"),
    chargers_total = ("chargers_total", "sum"),
    chargers_new = ("chargers_new", "sum"),
    panels_total = ("panels_total", "sum"),
    panels_new = ("panels_new", "sum"),
    demand_estimated = ("demand_estimated", "sum"),
    demand_satisfied = ("demand_satisfied", "sum"),
    solar_kwh = ("solar_used_kwh", "sum"),
    grid_kwh = ("grid_used_kwh", "sum")
).reset_index()

# Métricas derivadas
agg["pct_demand_satisfied"] = (agg["demand_satisfied"] / agg["demand_estimated"]).replace([float("inf"), float("nan")], 0.0) * 100.0
agg["pct_demand_satisfied"] = agg["pct_demand_satisfied"].round(1)

# Imprimir resumen por comuna (ordenado por demand_estimated desc)
print("\nResumen por comuna (ordenado por demanda estimada):\n")
display_cols = ["comuna","sites_total","sites_activated","sites_active","chargers_total","chargers_new",
                "panels_total","panels_new","demand_estimated","demand_satisfied","pct_demand_satisfied",
                "solar_kwh","grid_kwh"]
print(agg.sort_values("demand_estimated", ascending=False)[display_cols].to_string(index=False))

# Guardar CSV resumen
agg.to_csv(OUT_SUMMARY, index=False)
print(f"\nResumen guardado en: {OUT_SUMMARY}")