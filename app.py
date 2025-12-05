import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os

# ==========================================
# 1. DISEÑO "PREMIUM"
# ==========================================
st.set_page_config(layout="wide", page_title="SITS Catemaco Pro", page_icon="🏛️")

st.markdown("""
<style>
    /* Estilo de Tarjetas KPI */
    .kpi-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #e74c3c; 
        text-align: center;
        margin-bottom: 10px;
    }
    .kpi-title { font-size: 14px; color: #7f8c8d; text-transform: uppercase; font-weight: 600; }
    .kpi-value { font-size: 28px; font-weight: 800; color: #2c3e50; margin-top: 5px; }
    .kpi-sub { font-size: 12px; color: #95a5a6; }
    
    /* Filtros */
    .filter-container { background-color: #f1f2f6; padding: 15px; border-radius: 8px; border: 1px solid #dfe4ea; }
    
    /* Semáforo */
    .dot {height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right:5px;}
    .red {background-color: #c0392b;}
    .orange {background-color: #e67e22;}
    .yellow {background-color: #f1c40f;}
    .green {background-color: #27ae60;}
</style>
""", unsafe_allow_html=True)

st.title("🏛️ SITS: Sistema de Inteligencia Territorial")
st.markdown("**Diagnóstico Estratégico Municipal 2025** | H. Ayuntamiento de Catemaco")

# ==========================================
# 2. CARGA DE DATOS
# ==========================================
@st.cache_data
def cargar_datos():
    f_urb = "sits_urbano_oficial.geojson"
    f_rur = "sits_rural_oficial.geojson"
    
    u = gpd.read_file(f_urb) if os.path.exists(f_urb) else None
    r = gpd.read_file(f_rur) if os.path.exists(f_rur) else None
    
    if u is not None: u['TIPO'] = 'Urbano'
    if r is not None: r['TIPO'] = 'Rural'
    
    return u, r

gdf_u, gdf_r = cargar_datos()

if gdf_u is None or gdf_r is None:
    st.error("⚠️ Error Crítico: Ejecute 'prepara_datos_final.py' primero para generar los archivos GeoJSON.")
    st.stop()

# ==========================================
# 3. FILTROS (BARRA LATERAL)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/235/235861.png", width=50)
    st.header("🎛️ Panel de Control")
    
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("**1. Nivel Territorial**")
    
    # A. LOCALIDAD
    all_locs = sorted(list(set(gdf_u['NOM_LOC'].unique()) | set(gdf_r['NOM_LOC'].unique())))
    sel_loc = st.selectbox("📍 Seleccione Localidad:", ["TODO EL MUNICIPIO"] + all_locs)
    
    du = gdf_u.copy()
    dr = gdf_r.copy()
    
    if sel_loc != "TODO EL MUNICIPIO":
        du = du[du['NOM_LOC'] == sel_loc]
        dr = dr[dr['NOM_LOC'] == sel_loc]
    
    # B. AGEB
    sel_ageb = "TODAS"
    if not du.empty:
        agebs = sorted(du['CVE_AGEB'].unique())
        if len(agebs) > 0:
            st.markdown("**2. Colonia / AGEB**")
            sel_ageb = st.selectbox("🏘️ Seleccione Zona:", ["TODAS"] + agebs)
            if sel_ageb != "TODAS":
                du = du[du['CVE_AGEB'] == sel_ageb]
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")
    
    # C. INDICADOR
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("**3. Indicador Social**")
    dict_inds = {
        "SITS_INDEX": "🔥 Pobreza Extrema (Índice)",
        "CAR_ALIM": "🍲 Alimentación (Ingreso)",
        "CAR_SERV": "🚰 Servicios Básicos (Viv)",
        "CAR_VIV": "🏠 Calidad Vivienda",
        "CAR_SALUD": "🏥 Acceso a Salud",
        "CAR_EDU": "🎓 Rezago Educativo"
    }
    carencia = st.radio("Variable:", list(dict_inds.keys()), format_func=lambda x: dict_inds[x])
    st.markdown('</div>', unsafe_allow_html=True)

lbl_zona = sel_loc
if sel_ageb != "TODAS": lbl_zona = f"{sel_loc} - AGEB {sel_ageb}"

# ==========================================
# FUNCIÓN AUXILIAR PARA CENTRAR MAPA (SIN WARNS)
# ==========================================
def get_bounds_center(gdf):
    """Calcula el centro usando los límites totales para evitar errores de CRS"""
    if gdf.empty: return 18.42, -95.11 # Default Catemaco
    minx, miny, maxx, maxy = gdf.total_bounds
    return (miny + maxy) / 2, (minx + maxx) / 2

# ==========================================
# 4. PESTAÑAS
# ==========================================
tab_mapa, tab_stats, tab_comp = st.tabs(["🗺️ MAPA GEOESPACIAL", "📊 ESTADÍSTICA POBLACIONAL", "⚖️ COMPARATIVA 2020-2025"])

# --- TAB 1: MAPA ---
with tab_mapa:
    c1, c2 = st.columns([3, 1])
    with c1:
        # Lógica de centrado robusta
        if not du.empty:
            clat, clon = get_bounds_center(du)
            zoom = 15 if sel_ageb != "TODAS" else (14 if sel_loc != "TODO EL MUNICIPIO" else 12)
        elif not dr.empty:
            clat, clon = get_bounds_center(dr)
            zoom = 13
        else:
            clat, clon = 18.42, -95.11
            zoom = 12

        m = folium.Map([clat, clon], zoom_start=zoom, tiles="CartoDB positron")
        
        def color_oficial(val):
            if val >= 0.4: return '#800000'
            elif val >= 0.25: return '#ff0000'
            elif val >= 0.15: return '#ffa500'
            elif val > 0: return '#ffff00'
            else: return '#008000'

        if not du.empty:
            folium.Choropleth(
                geo_data=du, data=du, columns=['CVEGEO', carencia],
                key_on='feature.properties.CVEGEO',
                fill_color='YlOrRd', fill_opacity=0.7, line_opacity=0.1,
                name="Zonas Urbanas", legend_name="Intensidad del Rezago"
            ).add_to(m)
            folium.GeoJson(du, tooltip=folium.GeoJsonTooltip(fields=['NOM_LOC', 'CVE_AGEB', carencia], aliases=['Localidad:', 'AGEB:', 'Rezago:'], localize=True)).add_to(m)

        if not dr.empty:
            for _, row in dr.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.centroid.y, row.geometry.centroid.x],
                    radius=min(max(row.get('POBTOT_25', 100)/40, 5), 20), # Blindaje si falta columna
                    color='#333', weight=1, fill=True, fill_color=color_oficial(row.get(carencia, 0)), fill_opacity=0.9,
                    popup=f"<b>{row['NOM_LOC']}</b><br>Val: {row.get(carencia,0):.1%}"
                ).add_to(m)
        
        # Corrección width para st_folium
        st_folium(m, height=600, width=None) # width=None usa el ancho completo del contenedor por defecto

    with c2:
        st.markdown(f"**Viendo:** {dict_inds[carencia]}")
        st.write("---")
        st.markdown("""
        **Simbología (Nivel de Urgencia):**
        * <span class='dot red'></span> **Muy Alto (>40%)**
        * <span class='dot orange'></span> **Alto (25-40%)**
        * <span class='dot yellow'></span> **Medio (15-25%)**
        * <span class='dot green'></span> **Bajo (<15%)**
        """, unsafe_allow_html=True)

# --- TAB 2: ESTADÍSTICAS ---
with tab_stats:
    st.markdown(f"### 📊 Reporte: {lbl_zona}")
    
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        st.markdown("**🎯 Grupo Poblacional:**")
        opciones_pob = {
            "Población Total": "POBTOT_25",
            "Mujeres": "POB_FEM_25",
            "Hombres": "POB_MAS_25",
            "Niños (0-14)": "POB_NINOS_25",
            "Adultos Mayores (65+)": "POB_MAYORES_25",
            "🏠 Hogares con Jefatura Femenina": "HOGARES_JEFAS_25",
            "🧡 Población Afromexicana": "POB_AFRO_25",
            "💬 Población Indígena (Lengua)": "POB_INDIGENA_25",
            "♿ Personas con Discapacidad": "POB_DISC_25"
        }
        # CORREGIDO: Label visible collapsed
        tipo_filtro = st.selectbox(
            "Seleccione Grupo",
            list(opciones_pob.keys()),
            label_visibility="collapsed"
        )
        col_focalizada = opciones_pob[tipo_filtro]
    
    df_zona = pd.concat([du, dr])
    
    if df_zona.empty:
        st.warning("No hay datos para calcular.")
    else:
        # Blindaje de tipos para evitar errores de String
        if col_focalizada in df_zona.columns:
            df_zona[col_focalizada] = pd.to_numeric(df_zona[col_focalizada], errors='coerce').fillna(0)
        
        if tipo_filtro == "🏠 Hogares con Jefatura Femenina":
            lbl_base = "Total Hogares"; lbl_afec = "Hogares Jefas"
        else:
            lbl_base = f"Total {tipo_filtro}"; lbl_afec = "Con Carencia"

        total_grupo = df_zona[col_focalizada].sum()
        afectados_estimados = (df_zona[col_focalizada] * df_zona[carencia]).sum()
        pct_real = (afectados_estimados / total_grupo * 100) if total_grupo > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-title">{lbl_base} (2025)</div><div class="kpi-value">{int(total_grupo):,}</div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #c0392b;"><div class="kpi-title">{lbl_afec}</div><div class="kpi-value">{int(afectados_estimados):,}</div><div class="kpi-sub">Estimado Vulnerable</div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #f1c40f;"><div class="kpi-title">INTENSIDAD</div><div class="kpi-value">{pct_real:.1f}%</div></div>""", unsafe_allow_html=True)
        with c4:
             mujeres = df_zona['POB_FEM_25'].sum() if 'POB_FEM_25' in df_zona.columns else 0
             st.markdown(f"""<div class="kpi-card" style="border-left-color: #8e44ad;"><div class="kpi-title">MUJERES</div><div class="kpi-value">{int(mujeres):,}</div></div>""", unsafe_allow_html=True)
        
        st.write("---")

        g1, g2 = st.columns(2)
        with g1:
            metricas = ['CAR_ALIM', 'CAR_SERV', 'CAR_VIV', 'CAR_SALUD', 'CAR_EDU']
            vals = []
            for m in metricas:
                 df_zona[m] = pd.to_numeric(df_zona[m], errors='coerce').fillna(0)
                 vals.append((df_zona[m] * df_zona[col_focalizada]).sum())
            
            nombres = ['Alimentación', 'Servicios', 'Vivienda', 'Salud', 'Educación']
            fig = px.bar(x=nombres, y=vals, text_auto='.2s', title="Personas Afectadas por Tipo", labels={'y':'Personas', 'x':''})
            fig.update_traces(marker_color='#e74c3c')
            # CORREGIDO: width="stretch" (nueva API) en vez de use_container_width
            st.plotly_chart(fig, use_container_width=True)
            
        with g2:
            # Validación de columnas antes de graficar
            cols_disc = ['DISC_MOTRIZ_25', 'DISC_VISUAL_25', 'DISC_AUDITIVA_25', 'DISC_MENTAL_25']
            cols_edad = ['POB_NINOS_25', 'POB_ADULTOS_25', 'POB_MAYORES_25']
            
            # Crear columnas si no existen (blindaje)
            for c in cols_disc + cols_edad:
                if c not in df_zona.columns: df_zona[c] = 0

            if tipo_filtro == "♿ Personas con Discapacidad":
                vals_disc = [
                    pd.to_numeric(df_zona['DISC_MOTRIZ_25'], errors='coerce').sum(),
                    pd.to_numeric(df_zona['DISC_VISUAL_25'], errors='coerce').sum(),
                    pd.to_numeric(df_zona['DISC_AUDITIVA_25'], errors='coerce').sum(),
                    pd.to_numeric(df_zona['DISC_MENTAL_25'], errors='coerce').sum()
                ]
                fig2 = px.pie(names=['Motriz', 'Visual', 'Auditiva', 'Mental'], values=vals_disc, title="Tipos de Discapacidad", hole=0.4)
            else:
                edades = pd.DataFrame({'Grupo': ['0-14', '15-64', '65+'], 'Pob': [
                    pd.to_numeric(df_zona['POB_NINOS_25'], errors='coerce').sum(),
                    pd.to_numeric(df_zona['POB_ADULTOS_25'], errors='coerce').sum(),
                    pd.to_numeric(df_zona['POB_MAYORES_25'], errors='coerce').sum()
                ]})
                fig2 = px.pie(edades, values='Pob', names='Grupo', hole=0.4, title="Distribución por Edad")
            
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📋 Padrón de Focalización")
        df_tabla = df_zona.copy()
        df_tabla['Ubicación'] = df_tabla.apply(lambda x: x['NOM_LOC'] if x['TIPO']=='Rural' else f"{x['NOM_LOC']} - AGEB {x['CVE_AGEB']}", axis=1)
        df_tabla['Grupo Objetivo'] = df_tabla[col_focalizada]
        df_tabla['Estimado Afectados'] = (df_tabla[col_focalizada] * df_tabla[carencia]).astype(int)
        df_tabla['% Rezago'] = (df_tabla[carencia] * 100).round(1)
        
        cols_fin = ['Ubicación', 'TIPO', 'Grupo Objetivo', 'Estimado Afectados', '% Rezago']
        tabla_final = df_tabla[cols_fin].sort_values('% Rezago', ascending=False)
        
        # CORREGIDO: width="stretch" en lugar de use_container_width para dataframes
        st.dataframe(
            tabla_final,
            hide_index=True,
            use_container_width=True, # Usamos use_container_width=True porque en versiones <1.30 width="stretch" puede fallar. Si tienes la última versión y te da warning, cambia a width="stretch".
            column_config={"% Rezago": st.column_config.ProgressColumn("Intensidad", format="%.1f%%", min_value=0, max_value=100)}
        )
        csv = tabla_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte (.csv)", csv, "SITS_Reporte.csv", "text/csv")

# ==========================================
# TAB 3: COMPARATIVA 2020 VS 2025 (CORREGIDO BLINDAJE)
# ==========================================
with tab_comp:
    st.markdown(f"### ⚖️ Evolución: Real 2020 vs Proyectado 2025")
    st.caption(f"Zona Analizada: {lbl_zona}")

    df_comp = pd.concat([du, dr])
    
    if df_comp.empty:
        st.warning("No hay datos.")
    else:
        vars_pob = [
            ("Población Total", "POBTOT", "POBTOT_25"),
            ("Población Femenina", "POB_FEM", "POB_FEM_25"),
            ("Población Masculina", "POB_MAS", "POB_MAS_25"),
            ("Población Indígena", "P_HLI", "POB_INDIGENA_25"),
            ("Población Afro", "POB_AFRO", "POB_AFRO_25"),
            ("Discapacidad", "PCON_DISC", "POB_DISC_25")
        ]

        # 1. CÁLCULO DE CRECIMIENTO POBLACIONAL
        pob_data = []
        for label, col20, col25 in vars_pob:
            
            # --- BLINDAJE DE TIPOS (CONVERTIR A NUMÉRICO) ---
            if col20 in df_comp.columns:
                df_comp[col20] = pd.to_numeric(df_comp[col20], errors='coerce').fillna(0)
            if col25 in df_comp.columns:
                df_comp[col25] = pd.to_numeric(df_comp[col25], errors='coerce').fillna(0)
            # -----------------------------------------------

            val20 = df_comp[col20].sum() if col20 in df_comp.columns else 0
            val25 = df_comp[col25].sum() if col25 in df_comp.columns else 0
            
            diff = val25 - val20
            pct = (diff / val20 * 100) if val20 > 0 else 0
            pob_data.append({"Variable": label, "2020 (Censo)": val20, "2025 (Estimado)": val25, "Diferencia": diff, "% Cambio": pct})
        
        df_pob_viz = pd.DataFrame(pob_data)

        # KPIs Comparativos
        tot20 = df_pob_viz.loc[0, "2020 (Censo)"]
        tot25 = df_pob_viz.loc[0, "2025 (Estimado)"]
        crecimiento = df_pob_viz.loc[0, "% Cambio"]
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Población 2020 (Real)", f"{int(tot20):,}")
        k2.metric("Población 2025 (Proyección)", f"{int(tot25):,}")
        k3.metric("Crecimiento Quinquenal", f"{crecimiento:.1f}%", delta=f"{int(tot25-tot20)} personas")
        
        st.write("---")

        # GRÁFICA COMPARATIVA DE POBLACIÓN
        st.subheader("📈 Dinámica Poblacional")
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=df_pob_viz['Variable'], y=df_pob_viz['2020 (Censo)'], name='2020', marker_color='#95a5a6'))
        fig_comp.add_trace(go.Bar(x=df_pob_viz['Variable'], y=df_pob_viz['2025 (Estimado)'], name='2025', marker_color='#3498db'))
        fig_comp.update_layout(barmode='group', height=400, title="Comparativa de Volúmenes")
        st.plotly_chart(fig_comp, use_container_width=True)

        # 3. COMPARATIVA DE INDICADORES (REZAGOS)
        st.subheader("📉 Evolución de Carencias (Porcentajes)")
        
        vars_rez = [
            ("Alimentación", "CAR_ALIM_20", "CAR_ALIM"),
            ("Servicios Básicos", "CAR_SERV_20", "CAR_SERV"),
            ("Calidad Vivienda", "CAR_VIV_20", "CAR_VIV"),
            ("Salud", "CAR_SALUD_20", "CAR_SALUD"),
            ("Educación", "CAR_EDU_20", "CAR_EDU")
        ]
        
        rez_data = []
        for label, col20, col25 in vars_rez:
            # --- BLINDAJE TAMBIÉN AQUÍ ---
            if col20 in df_comp.columns:
                 df_comp[col20] = pd.to_numeric(df_comp[col20], errors='coerce').fillna(0)
            if col25 in df_comp.columns:
                 df_comp[col25] = pd.to_numeric(df_comp[col25], errors='coerce').fillna(0)
            
            # Asegurar que POBTOT es numérico
            if 'POBTOT' in df_comp.columns: df_comp['POBTOT'] = pd.to_numeric(df_comp['POBTOT'], errors='coerce').fillna(0)
            if 'POBTOT_25' in df_comp.columns: df_comp['POBTOT_25'] = pd.to_numeric(df_comp['POBTOT_25'], errors='coerce').fillna(0)

            pond25 = (df_comp[col25] * df_comp['POBTOT_25']).sum() / df_comp['POBTOT_25'].sum() * 100
            
            if col20 in df_comp.columns:
                pond20 = (df_comp[col20] * df_comp['POBTOT']).sum() / df_comp['POBTOT'].sum() * 100
            else:
                pond20 = 0
            
            rez_data.append({"Indicador": label, "2020 (%)": pond20, "2025 (%)": pond25})

        df_rez_viz = pd.DataFrame(rez_data)
        
        fig_rez = go.Figure()
        
        if df_rez_viz['2020 (%)'].sum() > 0:
            fig_rez.add_trace(go.Bar(x=df_rez_viz['Indicador'], y=df_rez_viz['2020 (%)'], name='2020', marker_color='#bdc3c7'))
            fig_rez.add_trace(go.Bar(x=df_rez_viz['Indicador'], y=df_rez_viz['2025 (%)'], name='2025', marker_color='#e74c3c'))
            fig_rez.update_layout(title="Cambio Porcentual en Carencias", yaxis_title="% de Población Afectada", barmode='group')
            st.plotly_chart(fig_rez, use_container_width=True)
            
            df_rez_viz['Mejora'] = df_rez_viz['2020 (%)'] - df_rez_viz['2025 (%)']
            st.dataframe(df_rez_viz.style.format("{:.1f}%", subset=['2020 (%)', '2025 (%)', 'Mejora'])
                         .applymap(lambda v: 'color: green' if v > 0 else 'color: red', subset=['Mejora']),
                         use_container_width=True)
        else:
            st.info("ℹ️ Para ver la comparativa de Carencias, asegúrate de haber ejecutado 'prepara_datos_final.py' para integrar los datos históricos.")
            fig_rez.add_trace(go.Bar(x=df_rez_viz['Indicador'], y=df_rez_viz['2025 (%)'], name='2025', marker_color='#e74c3c'))
            st.plotly_chart(fig_rez, use_container_width=True)
