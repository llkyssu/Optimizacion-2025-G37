#!/usr/bin/env python3
"""
8_summary_gurobi.py
===================
Genera un resumen de la solución óptima del modelo Gurobi.

Analiza results_optimization_gurobi.csv y genera:
1. Resumen global (objetivo, cobertura, costos, energía)
2. Resumen por comuna (sitios activados, cargadores, paneles, demanda)
3. Evolución temporal (si M > 1)
4. Análisis de equidad
5. Análisis ambiental

Salida: results_summary_gurobi.txt, results_by_comuna_gurobi.csv
"""

import os
import sys
import pandas as pd
import numpy as np

# Rutas
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
RESULTS_PATH = os.path.join(ROOT, "results_optimization_gurobi.csv")
OUTPUT_SUMMARY = os.path.join(ROOT, "results_summary_gurobi.txt")
OUTPUT_COMUNAS = os.path.join(ROOT, "results_by_comuna_gurobi.csv")


def load_results():
    """Carga resultados del modelo Gurobi."""
    if not os.path.exists(RESULTS_PATH):
        raise FileNotFoundError(f"No existe: {RESULTS_PATH}")
    
    df = pd.read_csv(RESULTS_PATH)
    print(f"✅ Cargados {len(df)} registros de {RESULTS_PATH}\n")
    return df


def calculate_costs(df, params):
    """Calcula costos totales basados en infraestructura instalada."""
    
    # Parámetros (deben coincidir con 7_solve_optimization_gurobi.py)
    k_slow = params.get("k_slow", 2_000_000.0)
    c_slow = params.get("c_slow", 2_000_000.0)
    h_slow = params.get("h_slow", 63_000.0)
    v_panel = params.get("v_panel", 900_000.0)
    m_panel = params.get("m_panel", 625.0)
    
    # Agrupar por sitio (último periodo para infraestructura acumulada)
    last_period = df.groupby(["comuna", "site_id"]).last().reset_index()
    
    # Costos de activación (sitios nuevos tipo="candidato")
    cost_activation = (
        last_period[last_period["tipo"] == "candidato"]["activated"].sum() * k_slow
    )
    
    # Costos de cargadores instalados (nuevos)
    cost_chargers = (
        df.groupby(["comuna", "site_id"])["chargers_installed"].sum().sum() * c_slow
    )
    
    # Costos operacionales (todos los periodos donde está activo)
    cost_operation = (
        df[df["active"] == 1].groupby(["comuna", "site_id", "mes"]).size().sum() * h_slow
    )
    
    # Costos de paneles solares instalados (nuevos)
    cost_panels = (
        df.groupby(["comuna", "site_id"])["panels_installed"].sum().sum() * v_panel
    )
    
    # Costos de mantenimiento paneles (todos los periodos)
    cost_panel_maintenance = (
        df["panels_total"].sum() * m_panel
    )
    
    total_cost = (
        cost_activation + 
        cost_chargers + 
        cost_operation + 
        cost_panels + 
        cost_panel_maintenance
    )
    
    return {
        "cost_activation": cost_activation,
        "cost_chargers": cost_chargers,
        "cost_operation": cost_operation,
        "cost_panels": cost_panels,
        "cost_panel_maintenance": cost_panel_maintenance,
        "total_cost": total_cost
    }


def global_summary(df, costs):
    """Genera resumen global de la solución."""
    
    M = df["mes"].max()
    n_comunas = df["comuna"].nunique()
    n_sites_total = df.groupby(["comuna", "site_id"]).ngroups
    
    # Infraestructura (último periodo)
    last_period = df[df["mes"] == M]
    sites_activated = last_period[last_period["activated"] == 1].groupby(["comuna", "site_id"]).ngroups
    sites_active = last_period[last_period["active"] == 1].groupby(["comuna", "site_id"]).ngroups
    chargers_total = last_period["chargers_total"].sum()
    chargers_slow = last_period["chargers_slow"].sum()
    chargers_fast = last_period["chargers_fast"].sum()
    panels_total = last_period["panels_total"].sum()
    
    # Demanda
    demand_estimated_total = df["demand_estimated"].sum()
    demand_satisfied_total = df["demand_satisfied"].sum()
    demand_unsatisfied_total = df["demand_unsatisfied"].sum()
    coverage_pct = (demand_satisfied_total / demand_estimated_total * 100) if demand_estimated_total > 0 else 0
    
    # Energía
    solar_kwh_total = df["solar_kwh"].sum()
    grid_kwh_total = df["grid_kwh"].sum()
    total_kwh = solar_kwh_total + grid_kwh_total
    solar_pct = (solar_kwh_total / total_kwh * 100) if total_kwh > 0 else 0
    
    # CO2 evitado (asumiendo 0.5 kg CO2/kWh red)
    co2_avoided_kg = solar_kwh_total * 0.5
    
    summary_text = f"""
{'='*80}
RESUMEN DE SOLUCIÓN ÓPTIMA - MODELO GUROBI
{'='*80}

📊 INFORMACIÓN GENERAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Periodos (meses):              {M}
  Comunas analizadas:            {n_comunas}
  Sitios totales (disponibles):  {n_sites_total}

🏗️  INFRAESTRUCTURA (al final del periodo)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sitios activados (nuevos):     {sites_activated}
  Sitios operativos:             {sites_active}
  Cargadores totales:            {chargers_total:,}
    - Lentos:                    {chargers_slow:,}
    - Rápidos:                   {chargers_fast:,}
  Paneles solares:               {panels_total:,}

⚡ DEMANDA Y COBERTURA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Demanda estimada (total):      {demand_estimated_total:,} clientes
  Demanda satisfecha:            {demand_satisfied_total:,} clientes
  Demanda insatisfecha:          {demand_unsatisfied_total:,} clientes
  Cobertura global:              {coverage_pct:.2f}%

🔋 ENERGÍA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Energía solar:                 {solar_kwh_total:,.2f} kWh ({solar_pct:.2f}%)
  Energía red:                   {grid_kwh_total:,.2f} kWh ({100-solar_pct:.2f}%)
  Total consumido:               {total_kwh:,.2f} kWh

🌱 IMPACTO AMBIENTAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CO₂ evitado:                   {co2_avoided_kg:,.2f} kg CO₂
                                 ({co2_avoided_kg/1000:,.2f} toneladas)

💰 COSTOS (CLP)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Activación sitios:             ${costs['cost_activation']:,.0f}
  Instalación cargadores:        ${costs['cost_chargers']:,.0f}
  Operación sitios:              ${costs['cost_operation']:,.0f}
  Instalación paneles:           ${costs['cost_panels']:,.0f}
  Mantenimiento paneles:         ${costs['cost_panel_maintenance']:,.0f}
  ───────────────────────────────────────────────────────────────────────────────
  TOTAL:                         ${costs['total_cost']:,.0f}

{'='*80}
"""
    
    return summary_text


def summary_by_comuna(df):
    """Genera resumen agregado por comuna."""
    
    M = df["mes"].max()
    last_period = df[df["mes"] == M]
    
    # Agrupar por comuna
    comuna_stats = []
    
    for comuna in df["comuna"].unique():
        df_c = df[df["comuna"] == comuna]
        df_c_last = last_period[last_period["comuna"] == comuna]
        
        stats = {
            "comuna": comuna,
            "sites_total": df_c.groupby(["site_id"]).ngroups,
            "sites_activated": df_c_last[df_c_last["activated"] == 1].groupby("site_id").ngroups,
            "sites_active": df_c_last[df_c_last["active"] == 1].groupby("site_id").ngroups,
            "chargers_total": df_c_last["chargers_total"].sum(),
            "chargers_slow": df_c_last["chargers_slow"].sum(),
            "chargers_fast": df_c_last["chargers_fast"].sum(),
            "panels_total": df_c_last["panels_total"].sum(),
            "demand_estimated": df_c["demand_estimated"].sum(),
            "demand_satisfied": df_c["demand_satisfied"].sum(),
            "demand_unsatisfied": df_c["demand_unsatisfied"].sum(),
            "coverage_pct": (df_c["demand_satisfied"].sum() / df_c["demand_estimated"].sum() * 100) 
                           if df_c["demand_estimated"].sum() > 0 else 0,
            "solar_kwh": df_c["solar_kwh"].sum(),
            "grid_kwh": df_c["grid_kwh"].sum(),
            "solar_pct": (df_c["solar_kwh"].sum() / (df_c["solar_kwh"].sum() + df_c["grid_kwh"].sum()) * 100)
                        if (df_c["solar_kwh"].sum() + df_c["grid_kwh"].sum()) > 0 else 0
        }
        
        comuna_stats.append(stats)
    
    df_stats = pd.DataFrame(comuna_stats)
    df_stats = df_stats.sort_values("demand_satisfied", ascending=False)
    
    return df_stats


def equity_analysis(df_stats):
    """Analiza equidad de cobertura entre comunas."""
    
    coverage = df_stats["coverage_pct"].values
    
    equity_text = f"""
📈 ANÁLISIS DE EQUIDAD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Cobertura promedio:            {coverage.mean():.2f}%
  Desviación estándar:           {coverage.std():.2f}%
  Cobertura mínima:              {coverage.min():.2f}% ({df_stats.loc[df_stats['coverage_pct'].idxmin(), 'comuna']})
  Cobertura máxima:              {coverage.max():.2f}% ({df_stats.loc[df_stats['coverage_pct'].idxmax(), 'comuna']})
  Rango (max - min):             {coverage.max() - coverage.min():.2f}%

  📊 Distribución de cobertura:
"""
    
    # Histograma de cobertura
    bins = [0, 20, 40, 60, 80, 100]
    hist, _ = np.histogram(coverage, bins=bins)
    
    for i in range(len(bins)-1):
        count = hist[i]
        pct = count / len(coverage) * 100
        bar = "█" * int(pct / 2)
        equity_text += f"    {bins[i]:3.0f}%-{bins[i+1]:3.0f}%:  {bar} ({count} comunas, {pct:.1f}%)\n"
    
    # Top 5 mejor cobertura
    top5 = df_stats.nlargest(5, "coverage_pct")
    equity_text += f"\n  🏆 Top 5 comunas con mejor cobertura:\n"
    for idx, row in top5.iterrows():
        equity_text += f"    {row['comuna']:25s} {row['coverage_pct']:6.2f}%\n"
    
    # Bottom 5 peor cobertura
    bottom5 = df_stats.nsmallest(5, "coverage_pct")
    equity_text += f"\n  ⚠️  Top 5 comunas con peor cobertura:\n"
    for idx, row in bottom5.iterrows():
        equity_text += f"    {row['comuna']:25s} {row['coverage_pct']:6.2f}%\n"
    
    return equity_text


def temporal_analysis(df):
    """Analiza evolución temporal (si M > 1)."""
    
    M = df["mes"].max()
    
    if M == 1:
        return "\n⏱️  EVOLUCIÓN TEMPORAL: No aplica (modelo estático M=1)\n"
    
    temporal_text = f"""
⏱️  EVOLUCIÓN TEMPORAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    for m in range(1, M + 1):
        df_m = df[df["mes"] == m]
        sites_active = df_m[df_m["active"] == 1].groupby(["comuna", "site_id"]).ngroups
        chargers = df_m["chargers_total"].sum()
        panels = df_m["panels_total"].sum()
        demand_sat = df_m["demand_satisfied"].sum()
        coverage = (demand_sat / df_m["demand_estimated"].sum() * 100) if df_m["demand_estimated"].sum() > 0 else 0
        
        temporal_text += f"  Mes {m:2d}: {sites_active:3d} sitios, {chargers:5,} cargadores, {panels:5,} paneles → {coverage:5.2f}% cobertura\n"
    
    return temporal_text


def main():
    print(f"\n{'='*80}")
    print("GENERADOR DE RESUMEN - SOLUCIÓN GUROBI")
    print(f"{'='*80}\n")
    
    # Cargar resultados
    try:
        df = load_results()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    # Parámetros (deben coincidir con modelo)
    params = {
        "k_slow": 2_000_000.0,
        "c_slow": 2_000_000.0,
        "h_slow": 63_000.0,
        "v_panel": 900_000.0,
        "m_panel": 625.0,
    }
    
    # Calcular costos
    costs = calculate_costs(df, params)
    
    # Generar resúmenes
    print("📝 Generando resumen global...")
    global_text = global_summary(df, costs)
    
    print("📝 Generando resumen por comuna...")
    df_stats = summary_by_comuna(df)
    
    print("📝 Analizando equidad...")
    equity_text = equity_analysis(df_stats)
    
    print("📝 Analizando evolución temporal...")
    temporal_text = temporal_analysis(df)
    
    # Guardar resumen textual
    full_summary = global_text + temporal_text + equity_text
    
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(full_summary)
    
    print(f"✅ Resumen guardado en: {OUTPUT_SUMMARY}")
    
    # Guardar tabla por comuna
    df_stats.to_csv(OUTPUT_COMUNAS, index=False, encoding="utf-8")
    print(f"✅ Resumen por comuna: {OUTPUT_COMUNAS}\n")
    
    # Mostrar en consola
    print(full_summary)


if __name__ == "__main__":
    main()
