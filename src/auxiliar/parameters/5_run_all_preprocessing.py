#!/usr/bin/env python3
"""
Script maestro para ejecutar en orden los scripts de preprocesamiento:
1. 1_anadir_pcap.py
2. 2_añadir_zmax_zinit.py
3. 3_unir_epc_dpc.py
4. 4_añadir_demanda.py

Uso:
    python src/auxiliar/run_all_preprocessing.py

Este script asume que los scripts individuales están en el mismo directorio.
"""
import subprocess
import os
import sys

SCRIPTS = [
    "src/auxiliar/1_anadir_pcap.py",
    "src/auxiliar/2_añadir_zmax_zinit.py",
    "src/auxiliar/3_unir_epc_dpc.py",
    "src/auxiliar/4_añadir_demanda.py",
]

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

for script in SCRIPTS:
    script_path = os.path.join(PROJECT_ROOT, script)
    print(f"\n=== Ejecutando: {os.path.basename(script)} ===")
    result = subprocess.run([sys.executable, script_path], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\n[ERROR] El script {os.path.basename(script)} terminó con error (código {result.returncode}).")
        sys.exit(result.returncode)
print("\nTodos los scripts ejecutados correctamente.")
