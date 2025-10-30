import pandas as pd
import glob
import os
import unicodedata
def normalizar_nombre(nombre):
    base, ext = os.path.splitext(nombre)
    base = base.lower()
    base = base.replace('ñ', 'n')
    base = ''.join((c for c in unicodedata.normalize('NFD', base) if unicodedata.category(c) != 'Mn'))
    base = base.replace(' ', '_').replace('-', '_')
    while '__' in base:
        base = base.replace('__', '_')
    base = base.strip('_')
    return base + ext

# Tabla de cotas por tipo

# Tabla de cotas por tipo (como valores enteros, usando el promedio del rango)
"""PCAPS = {
    'parking': '20-30',
    'fuel': '8-12',
    'charging_station': '20-40',
    'mall': '10-30',
    'supermarket': '6-12',
    'stadium': '10-20',
    'office': '4-10',
    'commercial': '4-10',
    'university': '4-10',
    'hospital': '4-8',
    'retail': '4-8',
    'car_wash': '1-2',
}"""

PCAPS = {
    'parking': 25,
    'fuel': 10,
    'charging_station': 30,
    'mall': 20,
    'supermarket': 10,
    'stadium': 20,
    'office': 8,
    'commercial':10,
    'university': 10,
    'hospital': 6,
    'retail': 6,
    'car_wash': 2,
}

# Si no hay match, asignar el promedio de todos los promedios
default_zcap = int(round(sum(PCAPS.values()) / len(PCAPS)))

# Rutas
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
input_folder = os.path.join(ROOT, 'raw_data', 'dpc_csv')
output_folder = os.path.join(ROOT, 'combinado_epc_dpc')
os.makedirs(output_folder, exist_ok=True)

for path in glob.glob(f"{input_folder}/*.csv"):
    df = pd.read_csv(path)
    # Detectar el tipo OSM por fila (amenity, shop, building, leisure)
    tipo_cols = ['amenity', 'shop', 'building', 'leisure']
    def get_tipo(row):
        for col in tipo_cols:
            val = str(row.get(col, '')).strip().lower()
            if val and val != 'nan':
                return val
        return ''
    df['tipo_osm'] = df.apply(get_tipo, axis=1)
    df['Pcap'] = df['tipo_osm'].map(PCAPS)
    df['Pcap'] = df['Pcap'].fillna(default_zcap).astype(int)
    if 'Zcap' in df.columns:
        df = df.drop(columns=['Zcap'])
    out_path = os.path.join(output_folder, normalizar_nombre(os.path.basename(path)))
    df.to_csv(out_path, index=False)
    print(f"Archivo exportado con Pcap: {out_path}")
