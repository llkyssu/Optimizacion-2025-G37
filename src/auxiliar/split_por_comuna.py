
import pandas as pd
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

df = pd.read_csv('electrolineras_rm.csv', sep=';')
os.makedirs('electrolineras_por_comuna', exist_ok=True)
for comuna, df_comuna in df.groupby('Comuna'):
    nombre_archivo = f"electrolineras_por_comuna/{normalizar_nombre(comuna)}.csv"
    df_comuna.to_csv(nombre_archivo, sep=';', index=False)
    print(f"Archivo guardado para comuna: {comuna} -> {nombre_archivo}")
