# Información Faltante para Modelo Completo de Optimización

## Script Actual: `src/scripts/5_solve_optimization.py`

El script ha sido **adaptado** para usar los datos existentes en el repositorio:
- ✅ Lee `combinado_epc_dpc_por_comuna/*.csv` (electrolineras existentes + candidatas)
- ✅ Usa `cargadores_iniciales` como ε_ij (cargadores ya instalados)
- ✅ Usa `Pcap` como capacidad máxima por sitio
- ✅ Distingue entre infraestructura existente (q_ij) y nueva
- ✅ Calcula costos solo para cargadores/paneles nuevos

---

## DATOS CRÍTICOS QUE FALTAN (ordenados por prioridad)

### 1. ⚠️ DEMANDA REAL POR SITIO Y MES (d_{ijm})
**Estado**: Actualmente se estima con heurística basada en `tipo_osm`.

**Qué se necesita**:
- Archivo: `demand_real.csv` con columnas:
  ```
  comuna,site_id,month,demand_clients,demand_kwh
  santiago,12,2025-10,240,7200
  santiago,12,2025-11,260,7800
  ...
  ```
- O al menos: demanda agregada por comuna y mes → el modelo la distribuiría proporcionalmente.

**Por qué es crítico**: Sin demanda real, el modelo instala infraestructura basándose en pesos arbitrarios (parking=0.9, mall=1.5, etc.) en lugar de uso real proyectado.

**Alternativa temporal**: Usar datos históricos de uso de electrolineras existentes y extrapolar con factores de crecimiento.

---

### 2. ⚠️ HORIZONTE TEMPORAL Y PARÁMETROS POR MES
**Estado**: Modelo simplificado usa 1 mes estático.

**Qué se necesita**:
- Archivo: `params_monthly.yaml` o `params_monthly.csv`:
  ```yaml
  months: ["2025-10", "2025-11", ..., "2040-12"]  # 180 meses hasta 2040
  c_slow: [2000000, 2020000, ...]  # costos por mes (ajustados por inflación)
  c_fast: [49000000, ...]
  p_per_panel: [56.25, 54.0, ...]  # producción varía por estación
  p_red: [180, 185, ...]  # precio energía de red por mes
  h_slow: [63000, ...]  # mantenimiento por mes
  v_panel: [900000, ...]
  B_monthly: [100000000, ...]  # presupuesto disponible por mes
  ```

**Por qué es crítico**: 
- El modelo original contempla instalación gradual (año 2025 → 2040 = 15 años).
- Costos y producción solar varían estacionalmente.
- Presupuesto debe distribuirse en el tiempo (no todo en un mes).

**Impacto**: Sin esto, el modelo intenta instalar todo de golpe en "mes 1".

---

### 3. 🔴 DISTINCIÓN CARGADORES RÁPIDOS vs LENTOS
**Estado**: Modelo trata todos como "slow" (AC).

**Qué se necesita**:
- En `combinado_epc_dpc_por_comuna/*.csv`, columna adicional: `tipo_cargador` (AC/DC).
- O perfil de demanda por tipo: qué % de sesiones requieren DC.
- Parámetros diferenciados ya existen (c_fast, h_fast, beta_fast) pero no se usan.

**Modelo actualizado debería**:
- Decidir X^{fast}_{ijm} y X^{slow}_{ijm} independientemente.
- Asignar costos y energía según tipo.

**Por qué importa**: Cargadores DC cuestan 25× más pero atienden demanda urgente (valor social mayor).

---

### 4. 🟡 CAPACIDAD MÁXIMA DE PANELES POR SITIO (Z^{max}_{ij})
**Estado**: Usa default de 50 paneles para todos.

**Qué se necesita**:
- Columna `Zmax` en `combinado_epc_dpc_por_comuna/*.csv` o archivo `sites_capacities.csv`:
  ```
  comuna,site_id,Zmax,area_disponible_m2,limite_conexion_kw
  santiago,12,80,400,100
  ```

**Por qué importa**: Espacios pequeños (parking residencial) vs grandes (mall) tienen restricciones distintas.

**Alternativa temporal**: Calcular Zmax = f(tipo_osm):
- parking pequeño: 20 paneles
- mall: 100 paneles
- fuel station: 50 paneles

---

### 5. 🟡 MATRIZ DE DISTANCIAS ENTRE SITIOS (D_{i,i'})
**Estado**: No se usa; la restricción λ_{ijm} (cobertura 10 min) está desactivada.

**Qué se necesita**:
- Opción A (simple): Calcular con coordenadas + velocidad promedio:
  ```python
  # Haversine entre (lon1,lat1) y (lon2,lat2) → km
  # km / velocidad_kmh * 60 → minutos
  ```
- Opción B (realista): Matriz precalculada con OSRM/Google Maps API.
- Archivo: `distances.csv`:
  ```
  site_id_a,site_id_b,time_minutes
  12,15,8.5
  12,18,12.3
  ```

**Por qué importa**: Permite activar restricción de cobertura (cada sitio debe tener cargador a ≤10 min).

**Implementación actual**: Puedo añadir cálculo Haversine + velocidad promedio (parámetro configurable, ej: 20 km/h en ciudad).

---

### 6. 🟢 PERFIL DE PRODUCCIÓN SOLAR MENSUAL
**Estado**: Usa promedio anual (56.25 kWh/panel/mes).

**Qué se necesita**:
- Tabla con producción por mes (Santiago):
  ```
  month,p_kwh_per_panel
  2025-01,68.0  # verano
  2025-02,65.0
  ...
  2025-06,38.0  # invierno
  2025-07,40.0
  ...
  ```

**Fuente**: Datos de NASA POWER, Explorador Solar, o mediciones locales.

**Impacto**: Instalar paneles considerando meses de baja producción (invierno) evita subdimensionamiento.

---

### 7. 🟢 OBJETIVOS DE COBERTURA POR COMUNA (α_j)
**Estado**: Restricción φ_{j,M} ≤ α_j no está implementada.

**Qué se necesita**:
- Archivo: `coverage_targets.csv`:
  ```
  comuna,alpha_min
  santiago,0.20  # al menos 80% de demanda satisfecha
  las_condes,0.15
  la_pintana,0.30  # zonas vulnerables necesitan más cobertura
  ```

**Por qué importa**: Garantiza equidad; evita concentrar toda la inversión en comunas ricas.

---

### 8. 🟢 PONDERADORES SOCIALES (V_cliente, B_CO2)
**Estado**: Usa valores arbitrarios (V_cliente=1200, B_CO2=50).

**Qué se necesita**:
- Justificación basada en:
  - Valor Social del Tiempo (VST) actualizado por comuna.
  - Costo social del carbono (precio impuesto verde).
- Archivo: `social_weights.yaml`:
  ```yaml
  V_cliente: 1200  # CLP por cliente atendido
  B_CO2: 100       # CLP por kWh renovable (beneficio ambiental)
  V_coverage_10min: 500  # beneficio por acceso <10 min
  ```

---

### 9. 🔵 DATOS GEOESPACIALES ADICIONALES
**Estado**: gpkg existen pero no se usan en el modelo.

**Uso potencial**:
- `dpc_gpkg/*.gpkg`: Geometrías de sitios → calcular áreas, distancias de red.
- `comunas_rm_limpias.gpkg`: Límites comunales → validar asignaciones.
- `features_rm_total.gpkg`: Capas adicionales (red vial, densidad poblacional).

**Herramientas**: geopandas, QGIS.

---

### 10. 🔵 RESTRICCIONES OPERACIONALES Y LOGÍSTICAS
**Estado**: No modeladas.

**Ejemplos**:
- Límite de instalaciones por mes (capacidad de contratistas).
- Lead time: meses entre decisión e instalación.
- Mantenimiento programado (paneles requieren limpieza cada X meses).

**Modelado**: Variables de flujo, restricciones de capacidad acumulada.

---

## RESUMEN: Modelo Actual vs Completo

| Componente | Estado Actual | Para Modelo Completo |
|------------|---------------|----------------------|
| Infraestructura existente (q, ε) | ✅ Implementado | ✅ OK |
| Demanda por sitio | ⚠️ Heurística | 🔴 Necesita datos reales |
| Horizonte temporal | ⚠️ 1 mes | 🔴 180 meses (2025-2040) |
| Tipos de cargador | ⚠️ Solo slow | 🔴 Fast + Slow |
| Capacidad paneles (Zmax) | ⚠️ Default 50 | 🟡 Por sitio |
| Distancias 10-min | ❌ No implementado | 🟡 Coordenadas + velocidad |
| Producción solar estacional | ⚠️ Promedio | 🟢 Por mes |
| Cobertura mínima por comuna | ❌ No implementado | 🟢 α_j por comuna |
| Ponderadores sociales | ⚠️ Arbitrarios | 🟢 Justificados |
| Datos geoespaciales | ❌ No usados | 🔵 Opcional |
| Restricciones logísticas | ❌ No modeladas | 🔵 Opcional |

---

## PRÓXIMOS PASOS RECOMENDADOS

### Prioridad ALTA (para modelo funcional mínimo):
1. **Obtener demanda real o proxy**:
   - Datos históricos de electrolineras existentes.
   - Proyecciones basadas en crecimiento de flota EV.
   - Estudios de movilidad (matriz origen-destino).

2. **Implementar horizonte multi-mes**:
   - Definir M = 180 meses (2025-2040).
   - Distribuir presupuesto B por periodos.
   - Usar parámetros variables por mes (al menos p_per_panel estacional).

3. **Distinguir cargadores fast/slow**:
   - Dividir variables X en X^{fast} y X^{slow}.
   - Asignar costos y restricciones diferenciadas.

### Prioridad MEDIA (para realismo):
4. Capacidad paneles por sitio (Zmax).
5. Matriz de distancias (Haversine + velocidad media).
6. Objetivos de cobertura por comuna (α_j).

### Prioridad BAJA (refinamiento):
7. Producción solar mensual detallada.
8. Ponderadores sociales justificados.
9. Restricciones logísticas y operacionales.

---

## CÓMO EJECUTAR EL MODELO ACTUAL

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Instalar dependencias
pip install pandas pulp

# 3. Ejecutar solver
python src/scripts/5_solve_optimization.py

# 4. Revisar resultados
cat results_optimization.csv
```

**Notas**:
- Modelo actual usa datos de `combinado_epc_dpc_por_comuna/*.csv`.
- Presupuesto por defecto: 5 mil millones CLP.
- Timeout: 120 segundos.
- Salida: `results_optimization.csv` con columnas actualizadas (q_existed, epsilon_initial_chargers, chargers_new, etc.).

---

## PREGUNTAS PARA DEFINIR SIGUIENTES PASOS

1. ¿Tienen datos históricos de uso de electrolineras existentes?
2. ¿Cuál es el horizonte temporal realista del proyecto? (¿2025-2030? ¿2025-2040?)
3. ¿Existe presupuesto total definido? ¿Se distribuye anualmente o mensualmente?
4. ¿Hay objetivos de cobertura específicos por comuna (políticas públicas)?
5. ¿Qué tipo de cargadores se priorizan (fast en rutas, slow en residencial)?

---

**Autor**: GitHub Copilot  
**Fecha**: 28 de octubre de 2025  
**Versión**: 1.0
