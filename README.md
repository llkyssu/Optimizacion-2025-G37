# Proyecto Opti

Este proyecto contiene scripts de Python para procesar y analizar datos geoespaciales de comunas de la Región Metropolitana.

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
4. Instala las dependencias necesarias (si tienes un requirements.txt):
   ```bash
   pip install -r requirements.txt
   ```

## 2. Ejecución de los scripts

Cada archivo Python realiza una tarea específica:

- **1_get_boundaries.py**: Obtiene y procesa los límites de las comunas.
- **2_get_features.py**: Extrae características geoespaciales de los datos.
- **3_get_features_by.py**: Extrae características agrupadas por algún criterio (por ejemplo, por comuna).
- **4_process_map.py**: Procesa y genera el mapa final a partir de los datos obtenidos.

Para ejecutar un script, usa:
```bash
python nombre_del_script.py
```
Por ejemplo:
```bash
python 1_get_boundaries.py
```

## 3. Notas
- Los archivos `.gpkg` contienen datos geoespaciales procesados.
- El archivo `mapa_completo_final.html` es el resultado visual del procesamiento.
- Los datos por comuna están en la carpeta `datos_por_comuna/`.

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