import pandas as pd
import geopandas as gpd
import numpy as np
import os
import warnings

warnings.filterwarnings("ignore")

print("🗳️ MOTOR DE CRUCE PROFUNDO (SOCIAL + POLÍTICO)...")

# RUTAS
F_MUN_21 = 'datos_crudos/Municipal_2021.csv'
F_GOB_24 = 'datos_crudos/Gobernatura_2024.csv'
F_DIP_LOC_24 = 'datos_crudos/Dip_local_2024.csv'
F_DIP_FED_24 = 'datos_crudos/Dip_federa_2024.csv'
F_PRES_24 = 'datos_crudos/Presidete_2024.csv'
F_MUN_25 = 'datos_crudos/Municipal_2025.csv'
F_MAPA_SEC = 'datos_crudos/SECCION.shp'
F_SITS_U = 'sits_urbano_oficial.geojson'
F_SITS_R = 'sits_rural_oficial.geojson'

# 1. CARGA Y LIMPIEZA DE VOTOS (Igual que antes)
def cargar_votos(ruta, etiqueta):
    if not os.path.exists(ruta): return pd.DataFrame()
    try: df = pd.read_csv(ruta, encoding='latin-1')
    except: df = pd.read_csv(ruta, encoding='utf-8')
    df.columns = df.columns.str.strip().str.upper()
    col_sec = [c for c in df.columns if 'SECCION' in c]
    if not col_sec: return pd.DataFrame()
    col_sec = col_sec[0]
    cols_mc = [c for c in df.columns if 'MC' == c or 'MOVIMIENTO' in c]
    cols_tot = [c for c in df.columns if 'TOTAL' in c or 'SUMA' in c or 'VALIDOS' in c]
    if not cols_mc or not cols_tot: return pd.DataFrame()
    df['SECCION'] = df[col_sec]
    df['VOTOS_MC'] = pd.to_numeric(df[cols_mc[0]].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df['TOTAL'] = pd.to_numeric(df[cols_tot[-1]].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_g = df.groupby('SECCION')[['VOTOS_MC', 'TOTAL']].sum().reset_index()
    df_g[f'PCT_MC_{etiqueta}'] = df_g['VOTOS_MC'] / df_g['TOTAL'].replace(0, 1)
    return df_g[['SECCION', f'PCT_MC_{etiqueta}']]

df_m21 = cargar_votos(F_MUN_21, "MUN21")
df_g24 = cargar_votos(F_GOB_24, "GOB24")
df_dl24 = cargar_votos(F_DIP_LOC_24, "LOC24")
df_df24 = cargar_votos(F_DIP_FED_24, "FED24")
df_p24 = cargar_votos(F_PRES_24, "PRES24")

# 2. ANÁLISIS 2025
try: df25 = pd.read_csv(F_MUN_25, encoding='latin-1')
except: df25 = pd.read_csv(F_MUN_25, encoding='utf-8')
df25.columns = df25.columns.str.strip().str.upper()
c_sec_25 = [c for c in df25.columns if 'SECCION' in c][0]
cols_25 = {'MC':'V_MC', 'MORENA':'V_MOR', 'PAN':'V_PAN', 'PRI':'V_PRI', 'VERDE':'V_PVE', 'PT':'V_PT', 'SUMATOTAL':'TOTAL'}
for o, d in cols_25.items():
    if o in df25.columns: df25[d] = pd.to_numeric(df25[o].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    else: df25[d] = 0
df25_g = df25.groupby(c_sec_25)[list(cols_25.values())].sum().reset_index().rename(columns={c_sec_25: 'SECCION'})

def analizar_25(row):
    total = row['TOTAL']
    if total == 0: return pd.Series([0, 0, "SIN DATO", "DESCONOCIDO"])
    mc = row['V_MC']
    rival = max(row['V_MOR']+row['V_PVE']+row['V_PT'], row['V_PAN']+row['V_PRI'])
    pct_mc = mc / total
    margen = pct_mc - (rival/total)
    if margen > 0:
        estatus = "GANADA"
        sens = "ALTA (RIESGO)" if abs(margen) < 0.05 else "BAJA (BASTIÓN)"
    else:
        estatus = "PERDIDA"
        sens = "ALTA (RECUPERABLE)" if abs(margen) < 0.05 else "MEDIA (DIFÍCIL)"
    return pd.Series([pct_mc, abs(margen), sens, estatus])

df25_g[['PCT_MC_25', 'MARGEN_ABS', 'SENSIBILIDAD', 'ESTATUS']] = df25_g.apply(analizar_25, axis=1)

base = df25_g
for d in [df_m21, df_g24, df_dl24, df_df24, df_p24]:
    if not d.empty: base = base.merge(d, on='SECCION', how='left')
base = base.fillna(0)

# 3. CRUCE GEOGRÁFICO
gdf_sec = gpd.read_file(F_MAPA_SEC)
if gdf_sec.crs != "EPSG:4326": gdf_sec = gdf_sec.to_crs("EPSG:4326")
col_sec_map = [c for c in gdf_sec.columns if 'SECCION' in c.upper()][0]
gdf_sec['seccion_fix'] = pd.to_numeric(gdf_sec[col_sec_map])
gdf_data = gdf_sec.merge(base, left_on='seccion_fix', right_on='SECCION')
if 'SECCION' not in gdf_data.columns: gdf_data['SECCION'] = gdf_data['seccion_fix']

# Cargar SITS FASE 1 (Aquí vienen las Jefas, Indígenas, etc.)
u = gpd.read_file(F_SITS_U)
r = gpd.read_file(F_SITS_R)

def inyectar(gdf_puntos, gdf_poly):
    # Preservamos TODAS las columnas sociales originales
    columnas_sociales = list(gdf_puntos.columns)
    
    puntos = gdf_puntos.copy()
    puntos['geometry'] = puntos.geometry.centroid
    
    cols_elec = ['SECCION', 'PCT_MC_25', 'MARGEN_ABS', 'SENSIBILIDAD', 'ESTATUS']
    join = gpd.sjoin(puntos, gdf_poly[['geometry']+cols_elec], how='left', predicate='within')
    
    # Agregar lo electoral a lo social
    for c in cols_elec:
        gdf_puntos[c] = join[c]
    
    # ESTRATEGIA DEFINITIVA
    def definir(row):
        pobreza = row.get('SITS_INDEX', 0)
        margen = row.get('MARGEN_ABS', 1)
        estatus = row.get('ESTATUS', 'DESC')
        
        # 1. ZONAS CERRADAS (<5%) - ORO PURO
        if margen < 0.05:
            if pobreza > 0.3: return "1. GUERRA SOCIAL (Empate + Pobreza Alta)"
            else: return "4. GUERRA ELECTORAL (Empate + Clase Media)"
        # 2. GANADAS
        if estatus == "GANADA":
            if pobreza > 0.3: return "2. BLINDAJE (Ganada + Pobreza Alta)"
            else: return "5. MANTENIMIENTO (Ganada + Clase Media)"
        # 3. PERDIDAS
        else:
            if pobreza > 0.4: return "3. OPORTUNIDAD (Perdida + Pobreza Extrema)"
            else: return "6. ZONA PERDIDA"

    gdf_puntos['ACCION_TACTICA'] = gdf_puntos.apply(definir, axis=1)
    
    # ID de Prioridad para ordenar tablas
    prio_map = {
        "1. GUERRA SOCIAL (Empate + Pobreza Alta)": 1,
        "2. BLINDAJE (Ganada + Pobreza Alta)": 2,
        "3. OPORTUNIDAD (Perdida + Pobreza Extrema)": 3,
        "4. GUERRA ELECTORAL (Empate + Clase Media)": 4,
        "5. MANTENIMIENTO (Ganada + Clase Media)": 5,
        "6. ZONA PERDIDA": 6
    }
    gdf_puntos['PRIORIDAD_NUM'] = gdf_puntos['ACCION_TACTICA'].map(prio_map).fillna(7)
    
    return gdf_puntos

u_fin = inyectar(u, gdf_data)
r_fin = inyectar(r, gdf_data)

u_fin.to_file("sits_urbano_fase2.geojson", driver='GeoJSON')
r_fin.to_file("sits_rural_fase2.geojson", driver='GeoJSON')

print("✅ FASE 2 LISTA: Datos integrales (Sociales + Políticos) fusionados.")
