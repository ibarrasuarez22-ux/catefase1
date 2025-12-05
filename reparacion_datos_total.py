import pandas as pd
import geopandas as gpd
import os
import warnings

warnings.filterwarnings('ignore')

print("🚨 INICIANDO REPARACIÓN DE DATOS - VERSIÓN FINAL (2020 + 2025) 🚨")
print("-----------------------------------------------------------------------")

# ARCHIVOS
F_GEO_U = "sits_urbano_oficial.geojson"
F_GEO_R = "sits_rural_oficial.geojson"
F_CENSO_U = "conjunto_de_datos_ageb_urbana_30_cpv2020.csv"
F_CENSO_R = "iter_veracruz_2020.csv"

def limpiar_cols(df):
    """Limpia columnas numéricas quitando asteriscos y N/A"""
    cols_necesarias = [
        'POBTOT', 'P_15YMAS', 'P15YM_AN', 'P15YM_SE', 'PDER_SS', 
        'TVIVPARHAB', 'VPH_PISOTIERRA', 'VPH_S_ELEC', 'VPH_DRENAJ', 'VPH_REFRI',
        'POB_FEM', 'POB_MAS', 'P_HLI', 'POB_AFRO', 'PCON_DISC',
        'VPH_NODREN', 'VPH_S_REFRI'
    ]
    
    for c in cols_necesarias:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

def calcular_indicadores(df):
    """Calcula los indicadores 2020 si no existen"""
    df = limpiar_cols(df)
    
    # Evitar div/0
    df['POBTOT'] = df['POBTOT'].replace(0, 1)
    df['TVIVPARHAB'] = df['TVIVPARHAB'].replace(0, 1)
    df['P_15YMAS'] = df['P_15YMAS'].replace(0, 1)
    
    # Crear variables faltantes (Proxy)
    if 'VPH_NODREN' not in df.columns:
        if 'VPH_DRENAJ' in df.columns:
            df['VPH_NODREN'] = (df['TVIVPARHAB'] - df['VPH_DRENAJ']).clip(lower=0)
        else:
            df['VPH_NODREN'] = 0
         
    if 'VPH_S_REFRI' not in df.columns:
        if 'VPH_REFRI' in df.columns:
            df['VPH_S_REFRI'] = (df['TVIVPARHAB'] - df['VPH_REFRI']).clip(lower=0)
        else:
            df['VPH_S_REFRI'] = 0

    # Indicadores
    df['CAR_EDU_20'] = ((df.get('P15YM_AN',0) + df.get('P15YM_SE',0)) / df['P_15YMAS']).clip(0,1)
    df['CAR_SALUD_20'] = ((df['POBTOT'] - df.get('PDER_SS',0)) / df['POBTOT']).clip(0,1)
    df['CAR_VIV_20'] = (df.get('VPH_PISOTIERRA',0) / df['TVIVPARHAB']).clip(0,1)
    df['CAR_SERV_20'] = ((df.get('VPH_S_ELEC',0) + df['VPH_NODREN']) / (df['TVIVPARHAB']*2)).clip(0,1)
    df['CAR_ALIM_20'] = (df['VPH_S_REFRI'] / df['TVIVPARHAB']).clip(0,1)
    
    return df

def limpiar_geojson_antes_de_cruce(gdf):
    """Elimina columnas viejas del GeoJSON para evitar conflictos."""
    cols_a_mantener = [
        'CVEGEO', 'geometry', 
        'NOM_LOC', 'CVE_AGEB', 'CVE_LOC', 'AMBITO', 'TIPOMZA',
        'CVE_ENT', 'CVE_MUN' 
    ]
    cols_existentes = [c for c in cols_a_mantener if c in gdf.columns]
    return gdf[cols_existentes].copy()

def generar_proyecciones_2025(gdf):
    """
    Genera las columnas 2025 (CAR_* y POB_*_25) y el SITS_INDEX
    basándose en los datos 2020 recuperados.
    """
    print("   🔮 Generando proyecciones 2025 y SITS_INDEX...")
    
    # 1. Proyección de Carencias (Simulamos mejora del 5%)
    vars_rez = ['CAR_ALIM', 'CAR_SERV', 'CAR_VIV', 'CAR_SALUD', 'CAR_EDU']
    
    for v in vars_rez:
        col_20 = v + "_20"
        # Si la columna 2020 existe (que debería, tras el cruce)
        if col_20 in gdf.columns:
            gdf[v] = gdf[col_20] * 0.95  # Mejora ligera
        else:
            gdf[v] = 0.0

    # 2. SITS_INDEX (Promedio de carencias 2025)
    # Índice multidimensional simple
    gdf['SITS_INDEX'] = (
        gdf['CAR_ALIM'] + gdf['CAR_SERV'] + gdf['CAR_VIV'] + 
        gdf['CAR_SALUD'] + gdf['CAR_EDU']
    ) / 5.0

    # 3. Proyección de Población (Crecimiento 5% quinquenal aprox)
    mapa_pob = {
        'POBTOT': 'POBTOT_25',
        'POB_FEM': 'POB_FEM_25',
        'POB_MAS': 'POB_MAS_25',
        'P_HLI': 'POB_INDIGENA_25',
        'POB_AFRO': 'POB_AFRO_25',
        'PCON_DISC': 'POB_DISC_25'
    }
    
    for col_20, col_25 in mapa_pob.items():
        if col_20 in gdf.columns:
            gdf[col_25] = gdf[col_20] * 1.05 # Crecimiento
        else:
            gdf[col_25] = 0

    # Variables especiales para la App (Hogares, Niños, Adultos)
    # Estimaciones demográficas simples si no existen
    if 'POBTOT_25' in gdf.columns:
        gdf['POB_NINOS_25'] = gdf['POBTOT_25'] * 0.25 # Est. 25% niños
        gdf['POB_ADULTOS_25'] = gdf['POBTOT_25'] * 0.65 
        gdf['POB_MAYORES_25'] = gdf['POBTOT_25'] * 0.10
        gdf['HOGARES_JEFAS_25'] = gdf['POBTOT_25'] / 4 * 0.3 # Est. 30% de hogares
    
    return gdf

# ==========================================
# 1. REPARACIÓN URBANA
# ==========================================
print("\n🏙️  ANALIZANDO ZONA URBANA...")
if os.path.exists(F_GEO_U) and os.path.exists(F_CENSO_U):
    gdf = gpd.read_file(F_GEO_U)
    gdf = limpiar_geojson_antes_de_cruce(gdf)
    
    df = pd.read_csv(F_CENSO_U, dtype=str, encoding='utf-8')
    df = df[(df['ENTIDAD'] == '30') & (df['MUN'] == '032')]

    # --- CORRECCIÓN DE NOMBRES DE COLUMNA ---
    df.rename(columns={
        'POBFEM': 'POB_FEM', 
        'POBMAS': 'POB_MAS',
        'P3YM_HLI': 'P_HLI' 
    }, inplace=True)
    
    # Llaves
    df['KEY_MZA'] = (
        df['ENTIDAD'].str.zfill(2) + df['MUN'].str.zfill(3) + 
        df['LOC'].str.zfill(4) + df['AGEB'].str.zfill(4) + df['MZA'].str.zfill(3)
    )
    
    df['KEY_AGEB'] = (
        df['ENTIDAD'].str.zfill(2) + df['MUN'].str.zfill(3) + 
        df['LOC'].str.zfill(4) + df['AGEB'].str.zfill(4)
    )
    
    df = calcular_indicadores(df)
    
    cols_data = ['CAR_EDU_20', 'CAR_SALUD_20', 'CAR_VIV_20', 'CAR_SERV_20', 'CAR_ALIM_20', 
                 'POBTOT', 'POB_FEM', 'POB_MAS', 'P_HLI', 'POB_AFRO', 'PCON_DISC']
    
    df = limpiar_cols(df) 

    print("   -> Intentando cruce exacto por Manzana...")
    df_to_merge = df[['KEY_MZA'] + cols_data]
    
    merge_mza = gdf.merge(df_to_merge, left_on='CVEGEO', right_on='KEY_MZA', how='left')
    
    tasa_exito = merge_mza['POBTOT'].notna().mean()
    print(f"   -> Tasa de éxito Manzana: {tasa_exito:.1%}")
    
    if tasa_exito < 0.5:
        print("   ⚠️  Fallo en Manzana. Usando AGEB...")
        df_ageb = df[df['MZA'] == '000'].copy()
        gdf['TEMP_AGEB_KEY'] = gdf['CVEGEO'].str.slice(0, 13)
        df_to_merge_ageb = df_ageb[['KEY_AGEB'] + cols_data]
        
        gdf_final = gdf.merge(df_to_merge_ageb, left_on='TEMP_AGEB_KEY', right_on='KEY_AGEB', how='left')
        
        for c in cols_data: gdf_final[c] = gdf_final[c].fillna(0)
            
        cols_drop = ['TEMP_AGEB_KEY', 'KEY_AGEB', 'KEY_MZA']
        gdf_final = gdf_final.drop(columns=[c for c in cols_drop if c in gdf_final.columns])
        
        # --- PASO CRÍTICO: GENERAR PROYECCIONES ---
        gdf_final = generar_proyecciones_2025(gdf_final)
        # ------------------------------------------

        gdf_final.to_file(F_GEO_U, driver='GeoJSON')
        print("   ✅ Urbano (AGEB) guardado con éxito.")
        
    else:
        cols_drop = ['KEY_MZA']
        merge_mza = merge_mza.drop(columns=[c for c in cols_drop if c in merge_mza.columns])
        for c in cols_data: merge_mza[c] = merge_mza[c].fillna(0)
            
        # --- PASO CRÍTICO: GENERAR PROYECCIONES ---
        merge_mza = generar_proyecciones_2025(merge_mza)
        # ------------------------------------------

        merge_mza.to_file(F_GEO_U, driver='GeoJSON')
        print("   ✅ Urbano (Manzana) guardado con éxito.")

# ==========================================
# 2. REPARACIÓN RURAL
# ==========================================
print("\n🚜  ANALIZANDO ZONA RURAL...")
if os.path.exists(F_GEO_R) and os.path.exists(F_CENSO_R):
    gdf = gpd.read_file(F_GEO_R)
    gdf = limpiar_geojson_antes_de_cruce(gdf)
    
    df = pd.read_csv(F_CENSO_R, dtype=str)
    df = df[df['ENTIDAD'].astype(int) == 30]
    df = df[df['MUN'].astype(int) == 32]
    
    df.rename(columns={
        'POBFEM': 'POB_FEM', 
        'POBMAS': 'POB_MAS',
        'P3YM_HLI': 'P_HLI'
    }, inplace=True)

    df['KEY_LOC'] = (
        df['ENTIDAD'].str.zfill(2) + df['MUN'].str.zfill(3) + df['LOC'].str.zfill(4)
    )
    
    df = calcular_indicadores(df)
    df = limpiar_cols(df)
    
    cols_data = ['CAR_EDU_20', 'CAR_SALUD_20', 'CAR_VIV_20', 'CAR_SERV_20', 'CAR_ALIM_20', 
                 'POBTOT', 'POB_FEM', 'POB_MAS', 'P_HLI', 'POB_AFRO', 'PCON_DISC']
    
    df_to_merge = df[['KEY_LOC'] + cols_data]
    
    gdf_final = gdf.merge(df_to_merge, left_on='CVEGEO', right_on='KEY_LOC', how='left')
    
    for c in cols_data: gdf_final[c] = gdf_final[c].fillna(0)
    if 'KEY_LOC' in gdf_final.columns: del gdf_final['KEY_LOC']
    
    # --- PASO CRÍTICO: GENERAR PROYECCIONES ---
    gdf_final = generar_proyecciones_2025(gdf_final)
    # ------------------------------------------

    gdf_final.to_file(F_GEO_R, driver='GeoJSON')
    print("   ✅ Rural actualizado con éxito.")

print("\n-----------------------------------------------------")
print("🏁 LISTO. EJECUTA 'streamlit run app.py'")
