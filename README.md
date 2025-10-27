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
