
# Proyecto Opti

Este proyecto contiene scripts de Python para el procesamiento, análisis y optimización de infraestructura de carga de vehículos eléctricos en la Región Metropolitana de Santiago.

## Estructura del proyecto

```
Optimizacion-2025-G37/
├── raw_data/                          # Datos originales
│   ├── dpc_csv/                      # Sitios candidatos (CSV)
│   ├── dpc_gpkg/                     # Sitios candidatos (GeoPackage)
│   ├── epc/                          # Electrolineras existentes
│   ├── autos_demanda.csv
│   ├── electrolineras_rm.csv
│   ├── comunas_rm_limpias.gpkg
│   ├── features_rm_total.gpkg
│   └── mapa_completo_final.html
│
├── combinado_epc_dpc/                # Datos procesados por comuna
│   ├── cerrillos.csv
│   ├── santiago.csv
│   └── ... (40 archivos)
│
├── resultados/                        # Resultados de optimización
│   ├── modelo_completo_latex.lp
│   ├── solucion_completo_latex.sol
│   ├── resumen_solucion_por_comuna.csv
│   ├── resumen_global.csv
│   ├── estaciones_activadas_coordenadas.csv
│   ├── estaciones_activadas.geojson
│   └── mapa_estaciones_activas.html
│
├── src/                               # Código fuente
│   ├── scripts/
│   │   ├── main.py                   # Modelo de optimización principal
│   │   └── analizar_solucion.py      # Análisis de resultados
│   └── auxiliar/
│       ├── locations/
│       │   ├── 1_get_boundaries.py
│       │   ├── 2_get_features.py
│       │   ├── 3_get_features_by.py
│       │   ├── 4_process_map.py
│       │   ├── 6_mapa_estaciones_activas.py
│       │   └── 7_get_coords_estaciones.py
│       └── parameters/
│           ├── 1_anadir_pcap.py
│           ├── 2_añadir_zmax_zinit.py
│           ├── 3_unir_epc_dpc.py
│           ├── 4_añadir_demanda.py
│           └── 5_run_all_preprocessing.py
│
├── requirements.txt
└── README.md
```

## 1. Configuración del entorno virtual (venv)

1. Abre una terminal en la carpeta del proyecto.
2. Crea el entorno virtual:
   ```bash
   python3 -m venv .venv
   ```
3. Activa el entorno virtual:
   - En Linux/Mac:
     ```bash
     source .venv/bin/activate
     ```
   - En Windows:
     ```bash
     .venv\Scripts\activate
     ```
4. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```

## 2. Scripts principales

### Optimización (Gurobi)

- **src/scripts/main.py**: Script principal que implementa el modelo de optimización MILP para la localización y dimensionamiento de infraestructura de carga de vehículos eléctricos usando Gurobi. Ejecuta la solución completa y genera archivos de salida con el modelo y la solución óptima.

Para ejecutar el modelo de optimización:
```bash
python src/scripts/main.py
```

### Preprocesamiento y análisis de datos

**Scripts de preprocesamiento (`src/auxiliar/parameters/`):**

- **1_anadir_pcap.py**: Añade la capacidad máxima de cargadores a los datos base.
- **2_añadir_zmax_zinit.py**: Añade información de paneles solares.
- **3_unir_epc_dpc.py**: Une datos de EPC y DPC.
- **4_añadir_demanda.py**: Añade estimaciones de demanda.
- **5_run_all_preprocessing.py**: Ejecuta todo el preprocesamiento en orden.

Para ejecutar el preprocesamiento completo:
```bash
python src/auxiliar/parameters/5_run_all_preprocessing.py
```

**Scripts de análisis (`src/scripts/`):**

- **analizar_solucion.py**: Analiza la solución del modelo y genera resúmenes por comuna.

```bash
python src/scripts/analizar_solucion.py
```

**Scripts de procesamiento geoespacial (`src/auxiliar/locations/`):**

- **1_get_boundaries.py**: Procesa los límites de las comunas.
- **2_get_features.py**: Extrae características geoespaciales.
- **3_get_features_by.py**: Agrupa características por comuna.
- **4_process_map.py**: Genera el mapa de sitios candidatos.
- **6_mapa_estaciones_activas.py**: Genera mapa de estaciones seleccionadas.
- **7_get_coords_estaciones.py**: Extrae coordenadas de estaciones activadas.

## 3. Notas y resultados

- Los archivos `.gpkg` en `raw_data/` contienen datos geoespaciales procesados.
- El archivo `raw_data/mapa_completo_final.html` muestra todos los sitios candidatos.
- Los datos procesados por comuna están en la carpeta `combinado_epc_dpc/`.
- Los resultados de la optimización se guardan en la carpeta `resultados/`:
  - `modelo_completo_latex.lp` - Modelo en formato LP
  - `solucion_completo_latex.sol` - Solución óptima
  - `resumen_solucion_por_comuna.csv` - Resumen por comuna
  - `resumen_global.csv` - Resumen global
  - `estaciones_activadas_coordenadas.csv` - Coordenadas de estaciones
  - `mapa_estaciones_activas.html` - Mapa interactivo de la solución

---

Si tienes dudas, revisa los comentarios en cada script o consulta con el responsable del proyecto.

## Benchmarks de Cargadores por Ubicación

Este documento detalla los benchmarks (cotas) utilizados para validar la cantidad de cargadores eléctricos por tipo de ubicación (tags de OpenStreetMap).

El objetivo es establecer un rango razonable que sirva como límite superior en los modelos de optimización, contrastando la realidad actual en Chile (datos 2023) con estándares y casos de estudio internacionales.

---

### Tabla de Benchmarks

La siguiente tabla define las cotas máximas observadas en los datos de Chile (2023) y establece el **Benchmark Razonable** (cota adoptada para el modelo) basado en referentes internacionales.

| Tipo de Ubicación (Tag OSM) | Cota Máx. Observada (Chile 2023) | Benchmark Razonable (Internacional) | Fuente Principal del Benchmark |
| :--- | :---: | :---: | :--- |
| `parking` | 9 | 20 – 30 | US DOE (Ratio 5%-15%) |
| `fuel` | 9 | 8 – 12 | ICCT (2024) |
| `charging_station` | 13 | 20 – 40 | GRIDSERVE (Caso UK) |
| `mall` | 4 | 10 – 30 | ICCT (2024) / Guía Delhi (Ratio 5%) |
| `supermarket` | 4 | 6 – 12 | ICCT (2024) / Guía Delhi (Ratio 5%) |
| `stadium` | 2 | 10 – 20 | IEA (2023) |
| `office` | 2 | 4 – 10 | EV Council (Ratio 15%) |
| `commercial` | 3 | 4 – 10 | IEA (2023) |
| `university` | 2 | 4 – 10 | US DOE |
| `hospital` | 2 | 4 – 8 | NHS (Caso UK) |
| `retail` | 2 | 4 – 8 | IEA (2023) |
| `car_wash` | 1 | 1 – 2 | Observación de mercado |

---

### Fuentes de Referencia

A continuación, se detallan las fuentes utilizadas para definir los benchmarks internacionales:

1.  **[ICCT 2024]** The International Council on Clean Transportation. (2024). *Quantifying the EV charging infrastructure needs at shopping centers in the EU*. [Informe Específico](https://theicct.org/publication/ev-charging-shopping-centers-eu-mar24/)
2.  **[Guía Delhi 2021]** Delhi Government. (2021). *EV Charging Guidebook for Shopping Malls*. Establece un ratio mandatorio del 5% de los estacionamientos. [Guía Gubernamental](http://ev.delhi.gov.in/files/Delhi%20Shopping%20Mall%20EV%20Charging%20Guidebook.pdf)
3.  **[GRIDSERVE (Caso UK)]** Caso de estudio de la red GRIDSERVE. Sus "Electric Forecourts" (electrolineras dedicadas) instalan hubs de 30-36 cargadores. [Ejemplo Comercial](https://www.gridserve.com/)
4.  **[EV Council (Caso AUS)]** Electric Vehicle Council of Australia. (2024). *Workplace Charging Guide*. Recomienda preparar el 15% de los espacios en oficinas nuevas. [Guía Sectorial](https://electricvehiclecouncil.com.au/wp-content/uploads/2024/12/EV-Workplace-Charging.pdf)
5.  **[NHS (Caso UK)]** Caso de estudio. (2025). Contrato de Herefordshire and Worcestershire NHS Trust para instalar 48 cargadores en 10 sitios (hospitales/clínicas), promediando **4.8 por sitio**. [Fuente de Noticia](https://www.investing.com/news/company-news/nhs-trust-awards-eenergy-333000-contract-for-ev-charging-project-93CH-4309506)
6.  **[US DOE]** U.S. Department of Energy. *Alternative Fuels Data Center (AFDC)*. Establece benchmarks y ratios para estacionamientos públicos y lugares de trabajo (workplace). [Base de Datos](https://afdc.energy.gov/fuels/electricity-stations)
7.  **[IEA 2023]** International Energy Agency. (2023). *Global EV Outlook 2023*. Provee análisis general de tendencias de instalación en espacios comerciales y públicos. [Informe Global](https://www.iea.org/reports/global-ev-outlook-2023)