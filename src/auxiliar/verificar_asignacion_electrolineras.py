import os
import pandas as pd

def verificar_asignacion_electrolineras(dir_combinado, dir_electro):
    archivos = [f for f in os.listdir(dir_combinado) if f.endswith('_combinado.csv')]
    for archivo in archivos:
        comuna = archivo.replace('_combinado.csv', '')
        file_combinado = os.path.join(dir_combinado, archivo)
        file_electro = os.path.join(dir_electro, f"{comuna}.csv")
        # Contar electrolineras originales
        if not os.path.exists(file_electro):
            print(f"{comuna}: No hay archivo de electrolineras.")
            continue
        # Detectar delimitador
        with open(file_electro, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
        df_electro = pd.read_csv(file_electro, delimiter=delimiter)
        n_electro = len(df_electro)
        # Leer combinado
        df_comb = pd.read_csv(file_combinado)
        # Filas con electrolinera asignada
        asignadas = df_comb[df_comb['cargadores_iniciales'] > 0]
        n_asignadas = len(asignadas)
        # Revisar unicidad de asignación
        ubicaciones = asignadas[['cargadores_iniciales','electro_Dirección','electro_lat','electro_lon']].drop_duplicates()
        ok = (n_electro == n_asignadas == len(ubicaciones))
        print(f"{comuna}: electrolineras originales={n_electro}, asignadas={n_asignadas}, ubicaciones únicas={len(ubicaciones)} -> {'OK' if ok else 'ERROR'}")

if __name__ == "__main__":
    verificar_asignacion_electrolineras('combinado_epc_dpc_por_comuna', 'electrolineras_por_comuna')
