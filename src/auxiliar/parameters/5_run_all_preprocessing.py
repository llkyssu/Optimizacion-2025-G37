#!/usr/bin/env python3
"""
Script maestro para ejecutar en orden los scripts de preprocesamiento:
1. 1_anadir_pcap.py
2. 2_añadir_zmax_zinit.py
3. 3_unir_epc_dpc.py
4. 4_añadir_demanda.py

Uso:
    python src/auxiliar/parameters/5_run_all_preprocessing.py

Este script asume que los scripts individuales están en el mismo directorio.
"""
import subprocess
import os
import sys

SCRIPTS = [
    "1_anadir_pcap.py",
    "2_añadir_zmax_zinit.py",
    "3_unir_epc_dpc.py",
    "4_añadir_demanda.py",
]

# Directorio donde está este script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

for script in SCRIPTS:
    script_path = os.path.join(SCRIPT_DIR, script)
    print(f"\n=== Ejecutando: {script} ===")
    result = subprocess.run([sys.executable, script_path], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\n[ERROR] El script {script} terminó con error (código {result.returncode}).")
        sys.exit(result.returncode)
print("\nTodos los scripts ejecutados correctamente.")
