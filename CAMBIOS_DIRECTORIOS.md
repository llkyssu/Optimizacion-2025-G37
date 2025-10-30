# Cambios en Directorios - Resumen

## 📋 Resumen de Cambios

Se han corregido todos los directorios en los scripts para garantizar que:
1. Los archivos se guarden en las carpetas correctas
2. Las rutas sean relativas al proyecto (no hardcodeadas)
3. Los resultados se guarden en `resultados/`
4. Los datos fuente estén en `raw_data/` y `combinado_epc_dpc/`

---

## ✅ Archivos Corregidos

### 1. **src/scripts/main.py**
**Cambios realizados:**
- ✅ Agregada constante `RESULTADOS_DIR` para la carpeta de resultados
- ✅ Archivos guardados en `resultados/`:
  - `modelo_completo_latex.lp`
  - `solucion_completo_latex.sol`
  - `modelo_completo_latex_conflictos.ilp` (si hay infactibilidad)
  - `modelo_infactible.ilp` (si hay infactibilidad)
- ✅ Se crea la carpeta `resultados/` automáticamente si no existe

**Rutas anteriores → nuevas:**
```python
# ANTES:
"resultados/modelo_completo_latex.lp"  # Ruta relativa
"solucion_completo_latex.sol"          # En raíz

# AHORA:
os.path.join(ROOT, "resultados", "modelo_completo_latex.lp")
os.path.join(ROOT, "resultados", "solucion_completo_latex.sol")
```

---

### 2. **src/scripts/analizar_solucion.py**
**Cambios realizados:**
- ✅ Agregada constante `RESULTADOS_DIR`
- ✅ Lee archivos desde `resultados/`:
  - `solucion_completo_latex.sol`
  - `modelo_completo_latex.lp`
- ✅ Guarda archivos en `resultados/`:
  - `resumen_solucion_por_comuna.csv`
  - `resumen_global.csv`

**Rutas anteriores → nuevas:**
```python
# ANTES:
"solucion_completo_latex.sol"              # En raíz
"resumen_solucion_por_comuna.csv"          # En raíz
"resultados/resumen_global.csv"            # Mixto

# AHORA:
os.path.join(RESULTADOS_DIR, "solucion_completo_latex.sol")
os.path.join(RESULTADOS_DIR, "resumen_solucion_por_comuna.csv")
os.path.join(RESULTADOS_DIR, "resumen_global.csv")
```

---

### 3. **src/auxiliar/locations/7_get_coords_estaciones.py**
**Cambios realizados:**
- ✅ Corregida ruta `ROOT` (ahora sube 3 niveles desde el script)
- ✅ Agregada constante `RESULTADOS_DIR`
- ✅ Lee desde `resultados/solucion_completo_latex.sol`
- ✅ Guarda archivos en `resultados/`:
  - `estaciones_activadas_coordenadas.csv`
  - `resumen_geografico_por_comuna.csv`
  - `estaciones_activadas.geojson`

**Rutas anteriores → nuevas:**
```python
# ANTES:
ROOT = os.path.join(..., "..", "..")  # Solo subía 2 niveles
"estaciones_activadas_coordenadas.csv"  # En raíz
"resumen_geografico_por_comuna.csv"     # En raíz
"estaciones_activadas.geojson"          # En raíz

# AHORA:
ROOT = os.path.join(..., "..", "..", "..")  # Sube 3 niveles
os.path.join(RESULTADOS_DIR, "estaciones_activadas_coordenadas.csv")
os.path.join(RESULTADOS_DIR, "resumen_geografico_por_comuna.csv")
os.path.join(RESULTADOS_DIR, "estaciones_activadas.geojson")
```

---

### 4. **src/auxiliar/locations/6_mapa_estaciones_activas.py**
**Cambios realizados:**
- ✅ Corregida ruta del proyecto (sube 3 niveles)
- ✅ Lee CSV desde `resultados/estaciones_activadas_coordenadas.csv`
- ✅ Guarda mapa en `resultados/mapa_estaciones_activas.html`

**Rutas anteriores → nuevas:**
```python
# ANTES:
project_folder = os.path.join(..., "..", "..")  # Solo subía 2 niveles
csv_file = os.path.join(project_folder, "estaciones_activadas_coordenadas.csv")
mapa_file = os.path.join(project_folder, "mapa_estaciones_activas.html")

# AHORA:
project_folder = os.path.join(..., "..", "..", "..")  # Sube 3 niveles
resultados_dir = os.path.join(project_folder, "resultados")
csv_file = os.path.join(resultados_dir, "estaciones_activadas_coordenadas.csv")
mapa_file = os.path.join(resultados_dir, "mapa_estaciones_activas.html")
```

---

### 5. **src/auxiliar/locations/4_process_map.py**
**Cambios realizados:**
- ✅ Eliminada ruta hardcodeada de WSL (`/home/marti/opti/`)
- ✅ Usa ruta relativa al proyecto
- ✅ Lee archivos desde `raw_data/dpc_gpkg/`
- ✅ Guarda mapa en `raw_data/mapa_completo_final.html`

**Rutas anteriores → nuevas:**
```python
# ANTES:
project_folder = "/home/marti/opti/"  # ❌ Hardcodeado
input_folder = os.path.join(project_folder, "dpc_gpkg")
mapa_file = os.path.join(project_folder, "mapa_completo_final.html")

# AHORA:
project_folder = os.path.abspath(os.path.join(..., "..", "..", ".."))
raw_data_folder = os.path.join(project_folder, "raw_data")
input_folder = os.path.join(raw_data_folder, "dpc_gpkg")
mapa_file = os.path.join(raw_data_folder, "mapa_completo_final.html")
```

---

### 6. **src/auxiliar/locations/3_get_features_by.py**
**Cambios realizados:**
- ✅ Eliminada ruta hardcodeada de WSL
- ✅ Usa ruta relativa al proyecto
- ✅ Lee archivos desde `raw_data/`
- ✅ Guarda archivos en `raw_data/dpc_gpkg/`

**Rutas anteriores → nuevas:**
```python
# ANTES:
project_folder = "/home/marti/opti/"  # ❌ Hardcodeado
comunas_file = os.path.join(project_folder, "comunas_rm_limpias.gpkg")
features_file = os.path.join(project_folder, "features_rm_total.gpkg")
output_folder = os.path.join(project_folder, "datos_por_comuna")

# AHORA:
project_folder = os.path.abspath(os.path.join(..., "..", "..", ".."))
raw_data_folder = os.path.join(project_folder, "raw_data")
comunas_file = os.path.join(raw_data_folder, "comunas_rm_limpias.gpkg")
features_file = os.path.join(raw_data_folder, "features_rm_total.gpkg")
output_folder = os.path.join(raw_data_folder, "dpc_gpkg")
```

---

### 7. **src/auxiliar/parameters/5_run_all_preprocessing.py**
**Cambios realizados:**
- ✅ Corregidas rutas a los scripts hijos
- ✅ Los scripts se buscan en el mismo directorio (parameters/)
- ✅ Se ejecutan desde la raíz del proyecto

**Rutas anteriores → nuevas:**
```python
# ANTES:
SCRIPTS = [
    "src/auxiliar/1_anadir_pcap.py",  # ❌ Ruta incorrecta
    "src/auxiliar/2_añadir_zmax_zinit.py",
    ...
]

# AHORA:
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = [
    "1_anadir_pcap.py",
    "2_añadir_zmax_zinit.py",
    ...
]
script_path = os.path.join(SCRIPT_DIR, script)
```

---

### 8. **src/auxiliar/parameters/3_unir_epc_dpc.py**
**Cambios realizados:**
- ✅ Agregada constante `ROOT`
- ✅ Rutas absolutas a `combinado_epc_dpc/` y `raw_data/epc/`

**Rutas anteriores → nuevas:**
```python
# ANTES:
DIR_COMBINADO = "combinado_epc_dpc"  # Ruta relativa
DIR_EPC = "epc"                       # Ruta relativa

# AHORA:
ROOT = os.path.abspath(os.path.join(..., "..", "..", ".."))
DIR_COMBINADO = os.path.join(ROOT, "combinado_epc_dpc")
DIR_EPC = os.path.join(ROOT, "raw_data", "epc")
```

---

### 9. **src/auxiliar/parameters/1_anadir_pcap.py**
**Cambios realizados:**
- ✅ Agregada constante `ROOT`
- ✅ Lee desde `raw_data/dpc_csv/`
- ✅ Guarda en `combinado_epc_dpc/`

**Rutas anteriores → nuevas:**
```python
# ANTES:
input_folder = 'dpc_csv'              # Ruta relativa
output_folder = 'combinado_epc_dpc'   # Ruta relativa

# AHORA:
ROOT = os.path.abspath(os.path.join(..., "..", "..", ".."))
input_folder = os.path.join(ROOT, 'raw_data', 'dpc_csv')
output_folder = os.path.join(ROOT, 'combinado_epc_dpc')
```

---

## 📁 Estructura de Directorios Final

```
Optimizacion-2025-G37/
├── raw_data/                          # Datos originales
│   ├── dpc_csv/                      # CSVs DPC originales
│   ├── dpc_gpkg/                     # GPKG generados por script 3
│   ├── epc/                          # Electrolineras existentes
│   ├── comunas_rm_limpias.gpkg
│   ├── features_rm_total.gpkg
│   └── mapa_completo_final.html      # Mapa de todos los candidatos
│
├── combinado_epc_dpc/                # Datos procesados por comuna
│   ├── cerrillos.csv
│   ├── santiago.csv
│   └── ...
│
├── resultados/                        # 🎯 Todos los resultados aquí
│   ├── modelo_completo_latex.lp
│   ├── solucion_completo_latex.sol
│   ├── resumen_solucion_por_comuna.csv
│   ├── resumen_global.csv
│   ├── resumen_geografico_por_comuna.csv
│   ├── estaciones_activadas_coordenadas.csv
│   ├── estaciones_activadas.geojson
│   └── mapa_estaciones_activas.html
│
└── src/
    ├── scripts/
    │   ├── main.py
    │   └── analizar_solucion.py
    └── auxiliar/
        ├── locations/
        │   ├── 3_get_features_by.py
        │   ├── 4_process_map.py
        │   ├── 6_mapa_estaciones_activas.py
        │   └── 7_get_coords_estaciones.py
        └── parameters/
            ├── 1_anadir_pcap.py
            ├── 2_añadir_zmax_zinit.py
            ├── 3_unir_epc_dpc.py
            ├── 4_añadir_demanda.py
            └── 5_run_all_preprocessing.py
```

---

## 🚀 Flujo de Trabajo Actualizado

### 1. Preprocesamiento de datos:
```bash
python src/auxiliar/parameters/5_run_all_preprocessing.py
```
Esto ejecuta en orden:
- `1_anadir_pcap.py` → Lee de `raw_data/dpc_csv/`, guarda en `combinado_epc_dpc/`
- `2_añadir_zmax_zinit.py` → Actualiza `combinado_epc_dpc/`
- `3_unir_epc_dpc.py` → Combina con `raw_data/epc/`, actualiza `combinado_epc_dpc/`
- `4_añadir_demanda.py` → Añade demanda, actualiza `combinado_epc_dpc/`

### 2. Ejecutar modelo de optimización:
```bash
python src/scripts/main.py
```
Genera en `resultados/`:
- `modelo_completo_latex.lp`
- `solucion_completo_latex.sol`

### 3. Analizar solución:
```bash
python src/scripts/analizar_solucion.py
```
Genera en `resultados/`:
- `resumen_solucion_por_comuna.csv`
- `resumen_global.csv`

### 4. Extraer coordenadas de estaciones:
```bash
python src/auxiliar/locations/7_get_coords_estaciones.py
```
Genera en `resultados/`:
- `estaciones_activadas_coordenadas.csv`
- `resumen_geografico_por_comuna.csv`
- `estaciones_activadas.geojson`

### 5. Generar mapa de estaciones activas:
```bash
python src/auxiliar/locations/6_mapa_estaciones_activas.py
```
Genera en `resultados/`:
- `mapa_estaciones_activas.html`

---

## ✨ Beneficios de los Cambios

1. **Organización clara:** Todos los resultados en una carpeta
2. **Portabilidad:** No hay rutas hardcodeadas, funciona en cualquier máquina
3. **Reproducibilidad:** Scripts se ejecutan desde cualquier ubicación
4. **Mantenibilidad:** Fácil encontrar y gestionar archivos
5. **Limpieza:** No se ensucian carpetas con archivos temporales

---

## 🔍 Archivos No Modificados

Los siguientes scripts **ya tenían rutas correctas**:
- ✅ `src/auxiliar/parameters/2_añadir_zmax_zinit.py`
- ✅ `src/auxiliar/parameters/4_añadir_demanda.py`

---

## 📝 Notas Importantes

- La carpeta `resultados/` se crea automáticamente si no existe
- Todos los scripts usan rutas absolutas calculadas dinámicamente
- Los scripts funcionan independientemente de dónde se ejecuten
- Se mantiene compatibilidad con estructura de datos existente
