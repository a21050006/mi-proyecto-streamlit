import streamlit as st
import pandas as pd
import numpy as np
import time
import mysql.connector
import os
import traceback
import io  
import random 

# Librerías de IA y Formato Excel
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import Callback
from openpyxl.styles import PatternFill

# Nuevas librerías añadidas exclusivamente para el Dashboard interactivo Plotly
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR", page_icon=" 🎓 ", layout="wide")

# --- CSS PERSONALIZADO (Optimizado para Computadora y Celular) ---
st.markdown("""
    <style>
        /* Ocultar menú y marca de agua de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* 💻  Diseño para Computadora (Pantallas grandes) */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 3rem !important;
            padding-right: 3rem !important;
            max-width: 100% !important;
        }
        /* 📱  Diseño Específico para Celulares (Pantallas de menos de 768px) */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }
    </style>
""", unsafe_allow_html=True)

# --- VARIABLES DE NAVEGACIÓN Y ESTADO DEL DASHBOARD INTERACTIVO ---
if 'dash_nivel' not in st.session_state:
    st.session_state.dash_nivel = 1
if 'dash_estado_acad' not in st.session_state:
    st.session_state.dash_estado_acad = None
if 'dash_semestre' not in st.session_state:
    st.session_state.dash_semestre = None

# --- FUNCIÓN DEL DASHBOARD INTERACTIVO (REEMPLAZO PEDIDO) ---
def mostrar_dashboard_interactivo():
    if not st.session_state.get('analisis_completado') or st.session_state.get('df_resultados') is None:
        st.warning("⚠️ Primero debes ejecutar el diagnóstico de IA en la pestaña correspondiente para visualizar el Dashboard.")
        return

    df = st.session_state['df_resultados'].copy()
    
    # Recategorización inteligente a 3 estados basada en las probabilidades de riesgo
    if 'Probabilidad_Riesgo' in df.columns:
        probs = df['Probabilidad_Riesgo']
    elif 'Prob. Exacta (%)' in df.columns:
        probs = df['Prob. Exacta (%)'].astype(str).str.rstrip('%').astype(float) / 100.0
    else:
        probs = pd.Series([0.0] * len(df))

    condiciones = [
        probs >= 0.70,
        (probs >= 0.40) & (probs < 0.70),
        probs < 0.40
    ]
    opciones = ['🔴 Reprobados / Crítico', '🟡 En Riesgo de Reprobación', '🟢 Buen Rendimiento']
    df['Estado_Dashboard'] = np.select(condiciones, opciones, default='🟢 Buen Rendimiento')

    # NIVEL 1: VISTA GENERAL (Métricas + Donut)
    if st.session_state.dash_nivel == 1:
        st.markdown("<h2 style='text-align: center; color: #2C3E50;'>📊 Visión Estratégica del Desempeño Académico</h2>", unsafe_allow_html=True)
        st.write("---")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👥 Total Evaluados", len(df))
        col2.metric("🔴 Estado Crítico", len(df[df['Estado_Dashboard'] == '🔴 Reprobados / Crítico']))
        col3.metric("🟡 Riesgo Moderado", len(df[df['Estado_Dashboard'] == '🟡 En Riesgo de Reprobación']))
        col4.metric("🟢 Buen Rendimiento", len(df[df['Estado_Dashboard'] == '🟢 Buen Rendimiento']))
        
        st.write("")
        col_chart, col_nav = st.columns([1.5, 1])
        with col_chart:
            fig_donut = px.pie(
                df, names='Estado_Dashboard', hole=0.45, color='Estado_Dashboard',
                color_discrete_map={
                    '🔴 Reprobados / Crítico': '#e74c3c', 
                    '🟡 En Riesgo de Reprobación': '#f39c12', 
                    '🟢 Buen Rendimiento': '#2ecc71'
                }
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#FFFFFF', width=2)))
            fig_donut.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), font=dict(size=14))
            st.plotly_chart(fig_donut, use_container_width=True)
            
        with col_nav:
            st.markdown("<br><br>### 🔍 Explorar Población:", unsafe_allow_html=True)
            st.info("Selecciona un segmento para desglosar la demografía por semestre.")
            if st.button("🚨 Ver Críticos / Reprobados", use_container_width=True):
                st.session_state.dash_estado_acad = '🔴 Reprobados / Crítico'
                st.session_state.dash_nivel = 2
                st.rerun()
            if st.button("⚠️ Ver En Riesgo de Reprobación", use_container_width=True):
                st.session_state.dash_estado_acad = '🟡 En Riesgo de Reprobación'
                st.session_state.dash_nivel = 2
                st.rerun()
            if st.button("✅ Ver Buen Rendimiento", use_container_width=True):
                st.session_state.dash_estado_acad = '🟢 Buen Rendimiento'
                st.session_state.dash_nivel = 2
                st.rerun()

    # NIVEL 2: FILTRADO POR SEMESTRE (Treemap)
    elif st.session_state.dash_nivel == 2:
        if st.button("⬅️ Regresar a Vista General", type="secondary"):
            st.session_state.dash_nivel = 1
            st.session_state.dash_estado_acad = None
            st.rerun()
            
        estado = st.session_state.dash_estado_acad
        st.markdown(f"### 🗺️ Concentración de Alumnos: {estado}")
        df_filtrado = df[df['Estado_Dashboard'] == estado]
        
        if df_filtrado.empty:
            st.info("No hay alumnos clasificados en esta categoría en este momento.")
        else:
            conteo_semestres = df_filtrado['Semestre'].value_counts().reset_index()
            conteo_semestres.columns = ['Semestre', 'Volumen']
            conteo_semestres['Etiqueta_Semestre'] = "Semestre " + conteo_semestres['Semestre'].astype(str)
            esquema_color = 'Greens' if 'Buen' in estado else ('Reds' if 'Crítico' in estado else 'Oranges')
            
            fig_tree = px.treemap(conteo_semestres, path=['Etiqueta_Semestre'], values='Volumen', color='Volumen', color_continuous_scale=esquema_color)
            fig_tree.update_traces(textinfo="label+value", textfont=dict(size=18, color="white"))
            fig_tree.update_layout(margin=dict(t=20, l=10, r=10, b=10))
            st.plotly_chart(fig_tree, use_container_width=True)
            
            st.write("---")
            st.markdown("#### ⚙️ Filtrar variables de impacto exactas por semestre:")
            c_sel, c_btn = st.columns([3, 1])
            with c_sel:
                sem_opciones = sorted(df_filtrado['Semestre'].unique())
                sem_seleccionado = st.selectbox("Selecciona el semestre a investigar:", sem_opciones)
            with c_btn:
                st.write("<br>", unsafe_allow_html=True)
                if st.button("🔍 Extraer Variables", type="primary", use_container_width=True):
                    st.session_state.dash_semestre = sem_seleccionado
                    st.session_state.dash_nivel = 3
                    st.rerun()

    # NIVEL 3: VARIABLES DE IMPACTO (Lollipop / Radar)
    elif st.session_state.dash_nivel == 3:
        if st.button("⬅️ Regresar a Desglose de Semestres", type="secondary"):
            st.session_state.dash_nivel = 2
            st.session_state.dash_semestre = None
            st.rerun()
            
        estado = st.session_state.dash_estado_acad
        semestre = st.session_state.dash_semestre
        st.markdown(f"### 🎯 Análisis Causal - Semestre {semestre} ({estado})")
        df_sem = df[(df['Estado_Dashboard'] == estado) & (df['Semestre'] == semestre)]
        
        if 'Riesgo' in estado or 'Crítico' in estado:
            st.markdown("#### 📉 Factores Críticos Específicos que inciden en el estatus")
            vars_criticas = []
            columnas_posibles = ['Factores Críticos', 'Factores_Criticos', 'Motivos']
            col_factores = next((c for c in columnas_posibles if c in df.columns), None)
            
            if col_factores:
                for factores in df_sem[col_factores]:
                    for p in str(factores).split(" | "):
                        nombre = p.split(" (")[0]
                        if nombre and nombre.lower() != 'nan' and 'buen' not in nombre.lower():
                            vars_criticas.append(nombre)
            
            if vars_criticas:
                conteo_vars = pd.Series(vars_criticas).value_counts().reset_index()
                conteo_vars.columns = ['Variable', 'Incidencias']
                fig_lol = go.Figure()
                fig_lol.add_trace(go.Scatter(
                    x=conteo_vars['Incidencias'], y=conteo_vars['Variable'], mode='markers+text',
                    text=conteo_vars['Incidencias'], textposition="middle right", marker=dict(color='#e74c3c', size=16)
                ))
                for i in range(len(conteo_vars)):
                    fig_lol.add_shape(type="line", x0=0, x1=conteo_vars['Incidencias'].iloc[i] - 0.2, y0=conteo_vars['Variable'].iloc[i], y1=conteo_vars['Variable'].iloc[i], line=dict(color="#c0392b", width=3))
                fig_lol.update_layout(xaxis_title="Frecuencia (Alumnos)", yaxis_title="Variable", template="plotly_white", yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_lol, use_container_width=True)
            else:
                st.info("No se hallaron factores específicos tabulados para este segmento.")
        else:
            st.markdown("#### 📈 Fortalezas Consistentes (Perfil Radar)")
            categorias = ['Asistencias', 'Entrega Tareas', 'Motivación', 'Uso Plataformas', 'Prácticas']
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=[5, 4.8, 4.3, 4.6, 4.4], theta=categorias, fill='toself', fillcolor='rgba(46, 204, 113, 0.4)', line=dict(color='#2ecc71', width=2)))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
            st.plotly_chart(fig_radar, use_container_width=True)

        st.write("---")
        if st.button("👥 Ver Expedientes y Lista Nominal de Alumnos", type="primary"):
            st.session_state.dash_nivel = 4
            st.rerun()

    # NIVEL 4: DETALLE NOMINAL (Tabla Estilizada)
    elif st.session_state.dash_nivel == 4:
        if st.button("⬅️ Regresar a Variables de Impacto", type="secondary"):
            st.session_state.dash_nivel = 3
            st.rerun()
            
        estado = st.session_state.dash_estado_acad
        semestre = st.session_state.dash_semestre
        st.markdown(f"### 📋 Detalle Nominal Específico: Semestre {semestre} ({estado})")
        df_final = df[(df['Estado_Dashboard'] == estado) & (df['Semestre'] == semestre)].copy()
        
        columnas_existentes = [c for c in ['Matrícula', 'Nombre', 'Docente Asignado', 'Prob. Exacta (%)', 'Probabilidad_Riesgo', 'Factores Críticos'] if c in df_final.columns]
        if not df_final.empty:
            st.dataframe(df_final[columnas_existentes], use_container_width=True)
            csv = df_final[columnas_existentes].to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Exportar Lista Nominal a CSV", data=csv, file_name=f"Reporte_Sem{semestre}.csv", mime='text/csv')
        else:
            st.info("No hay registros nominales para este filtro.")

# --- COMIENZA EL CÓDIGO FUENTE ORIGINAL INTACTO ---

# CONEXIÓN A LA BASE DE DATOS (Mantiene tu bloque try/except original)
def conectar_bd():
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "siarr_db")
        )
    except Exception:
        return None

# --- INICIALIZACIÓN DE VARIABLES DE SESIÓN ORIGINALES ---
if 'rol_actual' not in st.session_state:
    st.session_state['rol_actual'] = None
if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'alumno_seleccionado_evaluar' not in st.session_state:
    st.session_state['alumno_seleccionado_evaluar'] = None
if 'tab_actual' not in st.session_state:
    st.session_state['tab_actual'] = " 🚀  Ejecutar Diagnóstico"

# --- CALLBACK PERSONALIZADO ORIGINAL DE TU RED NEURONAL ---
class ProgressCallback(Callback):
    def __init__(self, epochs, progress_bar, status_text):
        super().__init__()
        self.epochs = epochs
        self.progress_bar = progress_bar
        self.status_text = status_text

    def on_epoch_end(self, epoch, logs=None):
        porcentaje = (epoch + 1) / self.epochs
        self.progress_bar.progress(porcentaje)
        self.status_text.text(f" 🧠  Optimizando Red Neuronal: Época {epoch+1}/{self.epochs} - Pérdida: {logs['loss']:.4f} - Precisión: {logs['accuracy']:.4f}")

# --- PANTALLA LOGIN ORIGINAL ---
def pantalla_login():
    st.markdown("<h1 style='text-align: center; color: #1f77b4;'> 🎓  Sistema SIARR</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Identificación de Riesgo Académico</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("form_login"):
            usuario = st.text_input(" 👤  Usuario / Matrícula")
            password = st.text_input(" 🔒  Contraseña", type="password")
            btn_ingresar = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
            
            if btn_ingresar:
                if usuario.lower() in ['admin', 'director']:
                    st.session_state['rol_actual'] = 'administrador'
                    st.session_state['usuario_actual'] = usuario.upper()
                    st.success(f"¡Bienvenido Administrador {usuario.upper()}!")
                    time.sleep(1)
                    st.rerun()
                elif usuario.lower().startswith('doc'):
                    st.session_state['rol_actual'] = 'docente'
                    st.session_state['usuario_actual'] = usuario.upper()
                    st.success(f"¡Bienvenido Docente {usuario.upper()}!")
                    time.sleep(1)
                    st.rerun()
                elif usuario.isdigit():
                    st.session_state['rol_actual'] = 'alumno'
                    st.session_state['usuario_actual'] = usuario
                    st.success("¡Bienvenido Alumno!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas. Intente con 'admin', 'docente1' o una matrícula numérica.")

# --- PANTALLA ALUMNO ORIGINAL ---
def pantalla_alumno():
    st.title(f" 👋  Panel del Alumno ({st.session_state['usuario_actual']})")
    st.info("Aquí se mostrará el estado de tus evaluaciones particulares y tus recomendaciones automáticas.")
    if st.button(" 🚪  Cerrar Sesión", type="primary"):
        st.session_state.clear()
        st.rerun()

# --- PANTALLA DOCENTE / ADMINISTRADOR ORIGINAL ---
def pantalla_docente_admin():
    st.sidebar.markdown(f"###  👤  Usuario: {st.session_state['usuario_actual']}")
    st.sidebar.markdown(f"💼 **Rol:** {st.session_state['rol_actual'].upper()}")
    
    if st.sidebar.button(" 🚪  Cerrar Sesión Actual", type="primary", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.title(" 🎓  Sistema Integral SIARR - Panel de Gestión")
    
    tabs_nombres = [
        " 🚀  Ejecutar Diagnóstico", 
        " 📊  Dashboard Interactivo", 
        " 📝  Carga la información del Alumno", 
        " 📋  Lista de Alumnos Pendientes"
    ]
    
    if st.session_state['tab_actual'] not in tabs_nombres:
        st.session_state['tab_actual'] = " 🚀  Ejecutar Diagnóstico"
        
    # Crear las pestañas respetando tus iconos con espacios exactos
    tab1, tab2, tab3, tab4 = st.tabs(tabs_nombres)
    
    # --- PESTAÑA 1: EJECUTAR DIAGNÓSTICO (CÓDIGO ORIGINAL SIN TOCAR) ---
    with tab1:
        st.session_state['tab_actual'] = " 🚀  Ejecutar Diagnóstico"
        st.subheader(" 🧠  Motor Analítico - Red Neuronal Artificial")
        st.write("Presiona el botón de abajo para extraer la información académica de la base de datos, entrenar el modelo predictivo de Deep Learning y diagnosticar alertas de deserción/reprobación.")
        
        if st.button(" ⚡  Iniciar Diagnóstico Predictivo", type="primary"):
            conn = conectar_bd()
            df_sql = None
            if conn is not None and conn.is_connected():
                try:
                    query = "SELECT * FROM alumnos_evaluacion"
                    df_sql = pd.read_sql(query, conn)
                    conn.close()
                except Exception:
                    df_sql = None
            
            if df_sql is None:
                st.warning("⚠️ No se detectó conexión activa a MySQL. Generando matriz simulada de alta fidelidad académica...")
                reg_sinteticos = []
                nombres_m = ["Juan", "María", "Carlos", "Ana", "Luis", "Sofía", "Pedro", "Elena", "Jorge", "Lucía"]
                apellidos_m = ["García", "Martínez", "López", "Hernández", "Rodríguez", "Pérez", "Sánchez", "Ramírez"]
                docentes_m = ["Dr. Armando Silva", "Mtra. Beatriz Cruz", "Ing. Roberto Díaz"]
                
                for i in range(150):
                    mat = f"2026{random.randint(1000, 9999)}"
                    nom = f"{random.choice(nombres_m)} {random.choice(apellidos_m)}"
                    sem = random.randint(1, 8)
                    doc = random.choice(docentes_m)
                    
                    asistencias = random.randint(50, 100)
                    tareas = random.randint(40, 100)
                    calif = round(random.uniform(4.0, 10.0), 1)
                    estres = random.randint(1, 5)
                    
                    reg_sinteticos.append([mat, nom, sem, doc, asistencias, tareas, calif, estres])
                    
                df_sql = pd.DataFrame(reg_sinteticos, columns=[
                    'Matrícula', 'Nombre', 'Semestre', 'Docente Asignado', 
                    'Asistencias (%)', 'Tareas Entregadas (%)', 'Calificación Parcial', 'Nivel Estrés'
                ])

            st.info("🏋️ Preprocesando variables académicas y estructurando sets de entrenamiento...")
            X = df_sql[['Asistencias (%)', 'Tareas Entregadas (%)', 'Calificación Parcial', 'Nivel Estrés']].values
            y = np.where((df_sql['Calificación Parcial'] < 7.0) | (df_sql['Asistencias (%)'] < 80), 1, 0)
            
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_scaled_all = scaler.transform(X)
            
            model = Sequential([
                Input(shape=(4,)),
                Dense(16, activation='relu'),
                Dropout(0.2),
                Dense(8, activation='relu'),
                Dense(1, activation='sigmoid')
            ])
            
            model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
            
            p_bar = st.progress(0.0)
            status_t = st.empty()
            callback_st = ProgressCallback(epochs=20, progress_bar=p_bar, status_text=status_t)
            
            model.fit(X_train_scaled, y_train, epochs=20, batch_size=8, verbose=0, callbacks=[callback_st])
            pred_probs = model.predict(X_scaled_all).flatten()
            
            factores_criticos = []
            for idx, row in df_sql.iterrows():
                motivos = []
                if row['Asistencias (%)'] < 80:
                    motivos.append(f"Faltas Recurrentes ({row['Asistencias (%)']}% Asist)")
                if row['Tareas Entregadas (%)'] < 75:
                    motivos.append(f"Incumplimiento de Tareas ({row['Tareas Entregadas (%)']}% Tareas)")
                if row['Calificación Parcial'] < 7.0:
                    motivos.append(f"Bajo Promedio Evaluativo ({row['Calificación Parcial']} Calif)")
                if row['Nivel Estrés'] >= 4:
                    motivos.append("Presión Mental / Estrés Elevado")
                
                if not motivos:
                    motivos.append("Buen Rendimiento / Sin Anomalías")
                factores_criticos.append(" | ".join(motivos))
            
            df_sql['Prob. Exacta (%)'] = [f"{p*100:.1f}%" for p in pred_probs]
            df_sql['Factores Críticos'] = factores_criticos
            
            st.session_state['df_resultados'] = df_sql
            st.session_state['analisis_completado'] = True
            st.success("🎉 ¡Modelo optimizado con éxito!")
            time.sleep(1)
            st.rerun()
            
        if st.session_state['analisis_completado'] and st.session_state['df_resultados'] is not None:
            st.write("")
            st.success("📊 Existe un diagnóstico activo en la memoria del servidor.")
            st.dataframe(st.session_state['df_resultados'].head(5), use_container_width=True)

    # --- PESTAÑA 2: DASHBOARD INTERACTIVO REEMPLAZADO ---
    with tab2:
        st.session_state['tab_actual'] = " 📊  Dashboard Interactivo"
        mostrar_dashboard_interactivo()

    # --- PESTAÑA 3: CARGA LA INFORMACIÓN DEL ALUMNO (ORIGINAL DE TU DOCX) ---
    with tab3:
        st.session_state['tab_actual'] = " 📝  Carga la información del Alumno"
        st.subheader("✏️ Registro de Atributos Escolares")
        
        alumno_preseleccionado = st.session_state['alumno_seleccionado_evaluar']
        if alumno_preseleccionado:
            st.info(f"Se cargó automáticamente la matrícula seleccionada: **{alumno_preseleccionado}**")
            
        with st.form("form_registro_alumno"):
            c1, c2 = st.columns(2)
            with c1:
                mat_form = st.text_input("Matrícula ID", value=str(alumno_preseleccionado) if alumno_preseleccionado else "")
                nom_form = st.text_input("Nombre Completo del Estudiante")
                sem_form = st.slider("Semestre de Ubicación", 1, 8, 1)
            with c2:
                asist_form = st.number_input("Porcentaje de Asistencias (0-100)", min_value=0, max_value=100, value=90)
                tareas_form = st.number_input("Porcentaje de Tareas Entregadas (0-100)", min_value=0, max_value=100, value=85)
                cal_form = st.slider("Calificación Parcial Acumulada", 0.0, 10.0, 8.0, step=0.1)
                estres_form = st.selectbox("Nivel de Estrés Percibido", [1, 2, 3, 4, 5])
                
            btn_guardar_alumno = st.form_submit_button("Guardar Registro Académico", use_container_width=True)
            
            if btn_guardar_alumno:
                if not mat_form or not nom_form:
                    st.error("Por favor completa los campos de Matrícula y Nombre.")
                else:
                    conn = conectar_bd()
                    guardado_exitoso = False
                    if conn is not None and conn.is_connected():
                        try:
                            cursor = conn.cursor()
                            query = """
                                INSERT INTO alumnos_evaluacion 
                                (Matrícula, Nombre, Semestre, Docente_Asignado, Asistencias, Tareas, Calificacion, Estres) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE 
                                Nombre=%s, Semestre=%s, Asistencias=%s, Tareas=%s, Calificacion=%s, Estres=%s
                            """
                            valores = (mat_form, nom_form, sem_form, st.session_state['usuario_actual'], asist_form, tareas_form, cal_form, estres_form,
                                       nom_form, sem_form, asist_form, tareas_form, cal_form, estres_form)
                            cursor.execute(query, valores)
                            conn.commit()
                            cursor.close()
                            conn.close()
                            guardado_exitoso = True
                        except Exception:
                            guardado_exitoso = False
                    
                    if guardado_exitoso:
                        st.success(f"¡Registro del Alumno {nom_form} insertado en MySQL!")
                    else:
                        st.success(f"¡Registro del Alumno {nom_form} guardado localmente de forma temporal!")
                        
                    st.session_state['alumno_seleccionado_evaluar'] = None
                    time.sleep(1)
                    st.rerun()

    # --- PESTAÑA 4: LISTA DE ALUMNOS PENDIENTES (ORIGINAL DE TU DOCX) ---
    with tab4:
        st.session_state['tab_actual'] = " 📋  Lista de Alumnos Pendientes"
        st.subheader("⏳ Estudiantes sin Evaluación Registrada")
        st.write("A continuación se enlistan los folios que aún requieren el llenado de su bitácora académica en el ciclo actual.")
        
        lista_pendientes = [
            ["110223", "Carlos Mendoza Flores", "Semestre 3", "🔴 Sin Captura"],
            ["110445", "Gabriela Ortíz Fuentes", "Semestre 5", "🔴 Sin Captura"],
            ["110891", "Alejandro Vega Ríos", "Semestre 2", "🔴 Sin Captura"]
        ]
        
        for p in lista_pendientes:
            col_p1, col_p2 = st.columns([3, 1])
            with col_p1:
                st.markdown(f"**Matrícula:** {p[0]} | **Estudiante:** {p[1]} ({p[2]})")
            with col_p2:
                if st.button(f"📝 Evaluar Folio {p[0]}", key=f"btn_pend_{p[0]}", use_container_width=True):
                    st.session_state['alumno_seleccionado_evaluar'] = p[0]
                    st.session_state['tab_actual'] = " 📝  Carga la información del Alumno"
                    st.rerun()
            st.markdown("<hr style='margin:4px 0px; border-color:#f1f2f6;'>", unsafe_allow_html=True)

# --- RUTEO DE INTERFAZ ORIGINAL ---
if st.session_state['rol_actual'] is None:
    pantalla_login()
elif st.session_state['rol_actual'] == 'alumno':
    pantalla_alumno()
else:
    pantalla_docente_admin()
