import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os

# ==========================================
# 1. DISEÑO "PREMIUM" (CSS RESTAURADO)
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
        border-left: 5px solid #e74c3c; /* Rojo Catemaco */
        text-align: center;
        margin-bottom: 10px;
    }
    .kpi-title {
        font-size: 14px;
        color: #7f8c8d;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 800;
        color: #2c3e50;
        margin-top: 5px;
    }
    .kpi-sub {
        font-size: 12px;
        color: #95a5a6;
    }
    
    /* Estilo de Filtros */
    .filter-container {
        background-color: #f1f2f6;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dfe4ea;
    }
    
    /* Semáforo visual */
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
    st.error("⚠️ Error Crítico: Ejecute 'preparar_datos_oficial.py' primero.")
    st.stop()

# ==========================================
# 3. FILTROS (BARRA LATERAL - RESTAURADOS)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/235/235861.png", width=50)
    st.header("🎛️ Panel de Control")
    
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("**1. Nivel Territorial**")
    
    # A. LOCALIDAD
    all_locs = sorted(list(set(gdf_u['NOM_LOC'].unique()) | set(gdf_r['NOM_LOC'].unique())))
    sel_loc = st.selectbox("📍 Localidad:", ["TODO EL MUNICIPIO"] + all_locs)
    
    # Lógica de Filtrado Cascada
    du = gdf_u.copy()
    dr = gdf_r.copy()
    
    if sel_loc != "TODO EL MUNICIPIO":
        du = du[du['NOM_LOC'] == sel_loc]
        dr = dr[dr['NOM_LOC'] == sel_loc]
    
    # B. AGEB (Solo si es Urbano)
    sel_ageb = "TODAS"
    if not du.empty:
        agebs = sorted(du['CVE_AGEB'].unique())
        if len(agebs) > 0:
            st.markdown("**2. Colonia / AGEB**")
            sel_ageb = st.selectbox("🏘️ Seleccione Zona:", ["TODAS"] + agebs)
            if sel_ageb != "TODAS":
                du = du[du['CVE_AGEB'] == sel_ageb]
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("") # Espacio
    
    # C. INDICADOR (CARENCIAS OFICIALES)
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("**3. Indicador Social**")
    
    # Aquí NO ponemos Jefatura. Jefatura va en estadísticas.
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

# Etiqueta de Zona para Títulos
lbl_zona = sel_loc
if sel_ageb != "TODAS": lbl_zona = f"{sel_loc} - AGEB {sel_ageb}"

# ==========================================
# 4. PESTAÑAS (ESTRUCTURA ORIGINAL)
# ==========================================
tab_mapa, tab_stats = st.tabs(["🗺️ MAPA GEOESPACIAL", "📊 ESTADÍSTICA POBLACIONAL"])

# --- TAB 1: EL MAPA ---
with tab_mapa:
    c1, c2 = st.columns([3, 1])
    with c1:
        # Centrado Automático
        if not du.empty:
            clat, clon = du.geometry.centroid.y.mean(), du.geometry.centroid.x.mean()
            zoom = 15 if sel_ageb != "TODAS" else (14 if sel_loc != "TODO EL MUNICIPIO" else 12)
        elif not dr.empty:
            clat, clon = dr.geometry.centroid.y.mean(), dr.geometry.centroid.x.mean()
            zoom = 13
        else:
            clat, clon = 18.42, -95.11
            zoom = 12

        m = folium.Map([clat, clon], zoom_start=zoom, tiles="CartoDB positron")
        
        # Semáforo Oficial
        def color_oficial(val):
            if val >= 0.4: return '#800000' # Crítico
            elif val >= 0.25: return '#ff0000' # Alto
            elif val >= 0.15: return '#ffa500' # Medio
            elif val > 0: return '#ffff00' # Bajo
            else: return '#008000' 

        # Capa Urbana
        if not du.empty:
            folium.Choropleth(
                geo_data=du, data=du, columns=['CVEGEO', carencia],
                key_on='feature.properties.CVEGEO',
                fill_color='YlOrRd', fill_opacity=0.7, line_opacity=0.1,
                name="Zonas Urbanas",
                legend_name="Intensidad del Rezago"
            ).add_to(m)
            # Tooltip
            folium.GeoJson(du, tooltip=folium.GeoJsonTooltip(
                fields=['NOM_LOC', 'CVE_AGEB', carencia],
                aliases=['Localidad:', 'AGEB:', 'Rezago:'], localize=True
            )).add_to(m)

        # Capa Rural
        if not dr.empty:
            for _, row in dr.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.centroid.y, row.geometry.centroid.x],
                    radius=min(max(row['POBTOT_25']/40, 5), 20),
                    color='#333', weight=1, fill=True, fill_color=color_oficial(row[carencia]), fill_opacity=0.9,
                    popup=f"<b>{row['NOM_LOC']}</b><br>Val: {row[carencia]:.1%}"
                ).add_to(m)
        
        st_folium(m, height=600, use_container_width=True)

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

# --- TAB 2: ESTADÍSTICAS (AQUÍ ESTÁ LA MAGIA) ---
with tab_stats:
    st.markdown(f"### 📊 Reporte: {lbl_zona}")
    
    # 1. FILTROS ESPECIALES DE ESTA PESTAÑA
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        st.markdown("**🎯 Grupo Poblacional (Filtro):**")
        
        # Opciones AMPLIADAS con lo que pediste
        opciones_pob = {
            "Población Total": "POBTOT_25",
            "Mujeres": "POB_FEM_25",
            "Hombres": "POB_MAS_25",
            "Niños (0-14)": "POB_NINOS_25",
            "Adultos Mayores (65+)": "POB_MAYORES_25",
            # NUEVOS AGREGADOS:
            "🏠 Hogares con Jefatura Femenina": "HOGARES_JEFAS_25",
            "🧡 Población Afromexicana": "POB_AFRO_25",
            "💬 Población Indígena (Lengua)": "POB_INDIGENA_25",
            "♿ Personas con Discapacidad": "POB_DISC_25"
        }
        tipo_filtro = st.selectbox("", list(opciones_pob.keys()))
        col_focalizada = opciones_pob[tipo_filtro]
    
    # Lógica de Selección de Columnas
    df_zona = pd.concat([du, dr])
    
    if df_zona.empty:
        st.warning("No hay datos para calcular.")
    else:
        # Configuración dinámica
        if tipo_filtro == "🏠 Hogares con Jefatura Femenina":
            col_base = "TOTAL_HOGARES_25"
            lbl_base = "Total Hogares"
            lbl_afec = "Hogares Jefas"
        else:
            # Para todos los grupos de personas (incluidos indígenas, afro, disc)
            col_base = opciones_pob[tipo_filtro] # La base es el mismo grupo (ej. total indigenas)
            lbl_base = f"Total {tipo_filtro}"
            lbl_afec = "Con Carencia Seleccionada"

        # Cálculos Matemáticos
        total_grupo = df_zona[col_focalizada].sum()
        afectados_estimados = (df_zona[col_focalizada] * df_zona[carencia]).sum()
        pct_real = (afectados_estimados / total_grupo * 100) if total_grupo > 0 else 0
        
        # --- TARJETAS KPI (ESTILO BONITO RESTAURADO) ---
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">{lbl_base} (EN ZONA)</div>
                <div class="kpi-value">{int(total_grupo):,}</div>
            </div>""", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class="kpi-card" style="border-left-color: #c0392b;">
                <div class="kpi-title">{lbl_afec} (EST.)</div>
                <div class="kpi-value">{int(afectados_estimados):,}</div>
                <div class="kpi-sub">con {dict_inds[carencia]}</div>
            </div>""", unsafe_allow_html=True)
            
        with c3:
            st.markdown(f"""
            <div class="kpi-card" style="border-left-color: #f1c40f;">
                <div class="kpi-title">INTENSIDAD REZAGO</div>
                <div class="kpi-value">{pct_real:.1f}%</div>
                <div class="kpi-sub">del grupo seleccionado</div>
            </div>""", unsafe_allow_html=True)
            
        with c4:
             # Dato de Género Global siempre útil
             mujeres = df_zona['POB_FEM_25'].sum()
             st.markdown(f"""
            <div class="kpi-card" style="border-left-color: #8e44ad;">
                <div class="kpi-title">CONTEXTO MUJERES</div>
                <div class="kpi-value">{int(mujeres):,}</div>
                <div class="kpi-sub">Población Femenina Total</div>
            </div>""", unsafe_allow_html=True)
        
        st.write("---")

        # --- GRÁFICAS DE CONTEXTO ---
        g1, g2 = st.columns(2)
        
        with g1:
            st.markdown("**📉 Comparativa de Carencias** (Para este grupo)")
            metricas = ['CAR_ALIM', 'CAR_SERV', 'CAR_VIV', 'CAR_SALUD', 'CAR_EDU']
            vals = [(df_zona[m] * df_zona[col_focalizada]).sum() for m in metricas]
            nombres = ['Alimentación', 'Servicios', 'Vivienda', 'Salud', 'Educación']
            
            fig = px.bar(x=nombres, y=vals, text_auto='.2s', 
                         title="Personas Afectadas por Tipo", labels={'y':'Personas', 'x':''})
            fig.update_traces(marker_color='#e74c3c')
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
        with g2:
            st.markdown("**👥 Composición Demográfica**")
            
            # SI SELECCIONAN DISCAPACIDAD, MOSTRAMOS TIPOS DE DISCAPACIDAD
            if tipo_filtro == "♿ Personas con Discapacidad":
                vals_disc = [
                    df_zona['DISC_MOTRIZ_25'].sum(), df_zona['DISC_VISUAL_25'].sum(),
                    df_zona['DISC_AUDITIVA_25'].sum(), df_zona['DISC_MENTAL_25'].sum()
                ]
                fig2 = px.pie(names=['Motriz', 'Visual', 'Auditiva', 'Mental'], values=vals_disc, title="Tipos de Discapacidad", hole=0.4)
            
            # SI NO, MOSTRAMOS LA PIRÁMIDE DE EDAD NORMAL
            else:
                edades = pd.DataFrame({
                    'Grupo': ['0-14', '15-64', '65+'],
                    'Pob': [df_zona['POB_NINOS_25'].sum(), df_zona['POB_ADULTOS_25'].sum(), df_zona['POB_MAYORES_25'].sum()]
                })
                fig2 = px.pie(edades, values='Pob', names='Grupo', hole=0.4, title="Distribución por Edad")
                
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

        # --- TABLA DE DESGLOSE (ESTILO LIMPIO) ---
        st.subheader("📋 Padrón de Focalización")
        
        df_tabla = df_zona.copy()
        df_tabla['Ubicación'] = df_tabla.apply(lambda x: x['NOM_LOC'] if x['TIPO']=='Rural' else f"{x['NOM_LOC']} - AGEB {x['CVE_AGEB']}", axis=1)
        
        # Columnas dinámicas
        df_tabla['Grupo Objetivo'] = df_tabla[col_focalizada]
        df_tabla['Estimado Afectados'] = (df_tabla[col_focalizada] * df_tabla[carencia]).astype(int)
        df_tabla['% Rezago'] = (df_tabla[carencia] * 100).round(1)
        
        cols_fin = ['Ubicación', 'TIPO', 'Grupo Objetivo', 'Estimado Afectados', '% Rezago']
        tabla_final = df_tabla[cols_fin].sort_values('% Rezago', ascending=False)
        
        st.dataframe(
            tabla_final, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "% Rezago": st.column_config.ProgressColumn(
                    "Intensidad", format="%.1f%%", min_value=0, max_value=100
                )
            }
        )
        
        # Botón Descarga
        csv = tabla_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte (.csv)", csv, "SITS_Reporte.csv", "text/csv")
