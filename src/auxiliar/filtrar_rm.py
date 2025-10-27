import pandas as pd

input_file = 'Electrolineras.csv'
# Intentar con encoding latinoamericano
try:
    df = pd.read_csv(input_file, sep=';', skiprows=2, encoding='latin1')
except Exception as e:
    print(f"Error al leer el archivo: {e}")
    exit(1)


# Normalización para evitar diferencias por mayúsculas/minúsculas o tildes
def normalizar_texto(texto):
    if isinstance(texto, str):
        return texto.lower().replace('í', 'i').replace('á', 'a').replace('é', 'e').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n').strip()
    return texto

df['Región'] = df['Región'].apply(normalizar_texto)
filtro = df['Región'].str.contains('metropolitana', na=False)
df_filtrado = df[filtro].copy()
df_filtrado['Dirección'] = df_filtrado['Dirección'].apply(normalizar_texto)
df_filtrado['Nombre Electrolinera'] = df_filtrado['Nombre Electrolinera'].apply(normalizar_texto)



# Agrupar solo por Dirección, Región y Comuna, sumando el número de cargadores
columnas_agrupacion = ['Dirección', 'Región', 'Comuna']
if 'Piso' in df_filtrado.columns:
    columnas_agrupacion.append('Piso')

df_agrupado = df_filtrado.groupby(columnas_agrupacion, as_index=False).agg({
    **{col: 'first' for col in df_filtrado.columns if col not in columnas_agrupacion + ['Nombre Electrolinera', 'Tipo conector']},
    'Tipo conector': 'count'
})
df_agrupado = df_agrupado.rename(columns={'Tipo conector': 'Numero de cargadores'})


output_file = 'Electrolineras_rm.csv'
df_agrupado.to_csv(output_file, sep=';', index=False)
print(f"Archivo agrupado guardado como {output_file}")

# Guardar un archivo por cada comuna
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
os.makedirs('electrolineras_por_comuna', exist_ok=True)
for comuna, df_comuna in df_agrupado.groupby('Comuna'):
    nombre_archivo = f"electrolineras_por_comuna/{normalizar_nombre(comuna)}.csv"
    df_comuna.to_csv(nombre_archivo, sep=';', index=False)
    print(f"Archivo guardado para comuna: {comuna} -> {nombre_archivo}")
