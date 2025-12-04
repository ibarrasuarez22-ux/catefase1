import pandas as pd
import geopandas as gpd
import numpy as np
import os

print("🏛️ RE-GENERANDO BASE DE DATOS (AGREGANDO COLUMNAS FALTANTES)...")

# CONFIGURACIÓN
ENTIDAD, MUNICIPIO = '30', '032'
FILE_DATA_URB = 'datos_crudos/conjunto_de_datos_ageb_urbana_30_cpv2020.csv'
FILE_MAP_URB  = 'datos_crudos/30m.shp'
FILE_DATA_RUR = 'datos_crudos/iter_veracruz_2020.csv'
FILE_MAP_RUR  = 'datos_crudos/30l.shp'

FACTOR_POB = 1.05
INFLACION_ALIM = 1.38
MEJORA_INFRA = 0.98

def procesar_censo_oficial(df, tipo):
    print(f"   ...Procesando {tipo}...")
    
    # 1. MAPEO EXACTO DE VARIABLES (AQUÍ ESTABA EL FALTANTE)
    cols = {
        'POBTOT': 'POBTOT', 'TVIVPARHAB': 'VIV',
        'TOTHOG': 'TOTAL_HOGARES', 'HOGJEF_F': 'HOGARES_JEFAS',
        'POB0_14': 'POB_NINOS', 'POB15_64': 'POB_ADULTOS', 'POB65_MAS': 'POB_MAYORES',
        'POBFEM': 'POB_FEM', 'POBMAS': 'POB_MAS',
        # GRUPOS VULNERABLES (CRÍTICOS)
        'POB_AFRO': 'POB_AFRO',
        'P3YM_HLI': 'POB_INDIGENA',
        'PCON_DISC': 'POB_DISC',      # <--- ESTA ES LA QUE TE DABA ERROR
        'PCDISC_MOT': 'DISC_MOTRIZ',
        'PCDISC_VIS': 'DISC_VISUAL',
        'PCDISC_AUD': 'DISC_AUDITIVA',
        'PCDISC_MEN': 'DISC_MENTAL',
        # CARENCIAS
        'P15YM_SE': 'R_EDU', 'P_SINDERECHO': 'R_SALUD',
        'VPH_PISOTI': 'R_VIV', 'VPH_AGUAFV': 'R_AGUA',
        'VPH_NODREN': 'R_DREN', 'VPH_S_ELEC': 'R_LUZ',
        'VPH_REFRI': 'R_REFRI', 'VPH_LAVAD': 'R_LAVAD'
    }
    
    if 'PSINDER' in df.columns: df = df.rename(columns={'PSINDER': 'P_SINDERECHO'})
    
    for c_orig, c_dest in cols.items():
        if c_orig in df.columns:
            df[c_dest] = pd.to_numeric(df[c_orig], errors='coerce').fillna(0)
        else:
            df[c_dest] = 0

    # 2. PROYECCIÓN 2025 (CRÍTICO: PROYECTAR LA DISCAPACIDAD)
    cols_proyectar = [
        'POBTOT', 'POB_NINOS', 'POB_ADULTOS', 'POB_MAYORES',
        'POB_FEM', 'POB_MAS', 'TOTAL_HOGARES', 'HOGARES_JEFAS',
        'POB_AFRO', 'POB_INDIGENA', 'POB_DISC', # <--- AQUÍ SE CREA POB_DISC_25
        'DISC_MOTRIZ', 'DISC_VISUAL', 'DISC_AUDITIVA', 'DISC_MENTAL'
    ]
    
    for col in cols_proyectar:
        df[f'{col}_25'] = (df[col] * FACTOR_POB).astype(int)
    
    df['VIV_25'] = (df['VIV'] * FACTOR_POB).astype(int)
    
    # 3. CÁLCULOS DE CARENCIAS (IGUAL QUE SIEMPRE)
    den_pob = df['POBTOT'].replace(0, 1)
    den_viv = df['VIV'].replace(0, 1)
    den_hog = df['TOTAL_HOGARES'].replace(0, 1)

    df['IND_JEFAS'] = (df['HOGARES_JEFAS'] / den_hog).clip(upper=1.0)
    df['CAR_EDU'] = (df['R_EDU'] / den_pob).clip(upper=1.0)
    df['CAR_SALUD'] = ((df['R_SALUD'] / den_pob) * 1.20).clip(upper=1.0)
    df['CAR_VIV'] = (df['R_VIV'] / den_viv).clip(upper=1.0)
    
    rate_agua = df['R_AGUA'] / den_viv
    rate_dren = df['R_DREN'] / den_viv
    rate_luz  = df['R_LUZ'] / den_viv
    df['CAR_SERV'] = ((rate_agua + rate_dren + rate_luz) / 3 * MEJORA_INFRA).clip(upper=1.0)
    
    pct_refri = df['R_REFRI'] / den_viv
    pct_lavad = df['R_LAVAD'] / den_viv
    carencia_activos = ((1 - pct_refri) + (1 - pct_lavad)) / 2
    df['CAR_ALIM'] = (carencia_activos * INFLACION_ALIM).clip(upper=1.0)

    prom_derechos = (df['CAR_EDU'] + df['CAR_SALUD'] + df['CAR_VIV'] + df['CAR_SERV']) / 4
    df['SITS_INDEX'] = (df['CAR_ALIM'] * 0.5) + (prom_derechos * 0.5)
    
    return df

# EJECUCIÓN
print("🏙️ Urbano...")
df_u = pd.read_csv(FILE_DATA_URB, dtype=str)
df_u = df_u[(df_u['ENTIDAD'] == ENTIDAD) & (df_u['MUN'].isin(['32', '032']))].copy()
df_u['CVEGEO'] = df_u['ENTIDAD'].str.zfill(2) + df_u['MUN'].str.zfill(3) + df_u['LOC'].str.zfill(4) + df_u['AGEB'].str.zfill(4) + df_u['MZA'].str.zfill(3)
df_u = procesar_censo_oficial(df_u, "URBANO")

gdf_u = gpd.read_file(FILE_MAP_URB)
if gdf_u.crs != "EPSG:4326": gdf_u = gdf_u.to_crs("EPSG:4326")
gdf_u.merge(df_u, on='CVEGEO').to_file("sits_urbano_oficial.geojson", driver='GeoJSON')

print("tractor Rural...")
df_r = pd.read_csv(FILE_DATA_RUR, dtype=str)
df_r = df_r[(df_r['ENTIDAD'] == ENTIDAD) & (df_r['MUN'].isin(['32', '032']))].copy()
df_r['CVEGEO'] = df_r['ENTIDAD'].str.zfill(2) + df_r['MUN'].str.zfill(3) + df_r['LOC'].str.zfill(4)
df_r = df_r[~df_r['NOM_LOC'].isin(['Catemaco', 'Sontecomapan', 'La Victoria', 'Zapoapan de Cabañas'])]
df_r = procesar_censo_oficial(df_r, "RURAL")

gdf_r = gpd.read_file(FILE_MAP_RUR)
if gdf_r.crs != "EPSG:4326": gdf_r = gdf_r.to_crs("EPSG:4326")
gdf_r.merge(df_r, on='CVEGEO').to_file("sits_rural_oficial.geojson", driver='GeoJSON')

print("✅ BASE ACTUALIZADA: YA TIENE LA COLUMNA POB_DISC_25.")
