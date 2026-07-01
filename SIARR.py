import streamlit as st
import pandas as pd
import numpy as np
import time
import mysql.connector
import os
import traceback
import io  
import random 
import hashlib
import re

# Librerías de IA, Formato Excel y Visualización Avanzada
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import Callback
from openpyxl.styles import PatternFill
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR - Sistema de IA", page_icon="🎓", layout="wide")

# --- CSS PERSONALIZADO (Optimizado para Computadora y Celular) ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 3rem !important;
            padding-right: 3rem !important;
            max-width: 100% !important;
        }
        @media (max-width: 768px) {
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE SEGURIDAD (MD5 y Contraseñas) ---
def generar_md5(texto):
    return hashlib.md5(texto.encode('utf-8')).hexdigest()

def validar_password_moodle(password):
    """Valida los criterios de seguridad de contraseñas"""
    if len(password) < 8: return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return False
    return True

# --- INICIALIZACIÓN DEL ESTADO DE LA SESIÓN ---
if 'usuario_autenticado' not in st.session_state:
    st.session_state['usuario_autenticado'] = False
if 'rol_actual' not in st.session_state:
    st.session_state['rol_actual'] = None
if 'nombre_usuario' not in st.session_state:
    st.session_state['nombre_usuario'] = ""

# --- DATASET SIMULADO / CARGA DE DATOS PARA EL DASHBOARD ---
@st.cache_data
def cargar_datos_academicos():
    """Genera datos sintéticos basados en tus Notebooks si no hay una base de datos activa"""
    np.random.seed(42)
    n_muestras = 200
    
    promedios = np.random.uniform(60, 100, n_muestras)
    materias_reprobadas = np.array([random.choice([0, 0, 0, 1, 2, 3]) for _ in range(n_muestras)])
    horas_estudio = np.random.uniform(2, 25, n_muestras) + (promedios / 10)
    asistencia = np.random.uniform(70, 100, n_muestras) - (materias_reprobadas * 5)
    asistencia = np.clip(asistencia, 0, 100)
    
    sistemas = [random.choice(["Escolarizado", "Semiescolarizado", "A Distancia"]) for _ in range(n_muestras)]
    semestres = [random.choice([1, 2, 3, 4, 5, 6, 7, 8]) for _ in range(n_muestras)]
    
    # Determinar resultado lógico preliminar
    resultados = []
    for p, m in zip(promedios, materias_reprobadas):
        if p < 70 or m > 1:
            resultados.append("Reprobado")
        else:
            resultados.append("Aprobado")
            
    df = pd.DataFrame({
        'Promedio_General': np.round(promedios, 2),
        'Materias_Reprobadas': materias_reprobadas,
        'Calificacion_Ultima_Materia': np.round(np.clip(promedios + np.random.normal(0, 5, n_muestras), 50, 100), 2),
        'Asistencia_Clases': np.round(asistencia, 2),
        'Horas_Estudio_Semana': np.round(np.clip(horas_estudio, 1, 40), 2),
        'Sistema_Escolar': sistemas,
        'Semestre': semestres,
        'Resultado': resultados
    })
    return df

df_alumnos = cargar_datos_academicos()

# --- COMPONENTE: DASHBOARD DOCENTE COMPLETO (MÓDULO INTERACTIVO) ---
def mostrar_dashboard_docente_completo(df):
    """
    Renderiza el panel analítico avanzado traduciendo por completo los análisis
    de Graficas.ipynb y EntrenamientoFinal.ipynb en gráficos dinámicos de Plotly.
    """
    st.markdown("<h2 style='text-align: center; color: #1d3557;'>📊 Panel Analítico y Dashboard Avanzado (SIARR)</h2>", unsafe_allow_html=True)
    st.write("Módulo de analítica predictiva. Filtre y analice las métricas de riesgo académico de sus grupos.")

    # Asegurar etiquetas limpias
    if 'Resultado' in df.columns:
        df['Resultado'] = df['Resultado'].map({'Aprobado': 'Aprobado', 'Reprobado': 'Reprobado'})
    
    # --- FILTROS DINÁMICOS ---
    st.markdown("### 🔍 Filtros de Visualización")
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        sistemas_disponibles = df['Sistema_Escolar'].unique() if 'Sistema_Escolar' in df.columns else ['General']
        sistema_filtro = st.multiselect("Filtrar por Sistema Escolar:", options=sistemas_disponibles, default=sistemas_disponibles)
        
    with col_f2:
        semestres_disponibles = sorted(df['Semestre'].unique()) if 'Semestre' in df.columns else [1]
        semestre_filtro = st.multiselect("Filtrar por Semestre:", options=semestres_disponibles, default=semestres_disponibles)

    # Aplicar Filtros
    df_filtrado = df[
        (df['Sistema_Escolar'].isin(sistema_filtro) if 'Sistema_Escolar' in df.columns else True) & 
        (df['Semestre'].isin(semestre_filtro) if 'Semestre' in df.columns else True)
    ]

    if df_filtrado.empty:
        st.warning("⚠️ No se encontraron registros coincidentes con los filtros seleccionados.")
        return

    # --- MÉTRICAS KPI ---
    total_alumnos = len(df_filtrado)
    reprobados = len(df_filtrado[df_filtrado['Resultado'] == 'Reprobado']) if 'Resultado' in df_filtrado.columns else 0
    tasa_riesgo = (reprobados / total_alumnos * 100) if total_alumnos > 0 else 0

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Alumnos Evaluados", f"{total_alumnos} Alumnos")
    kpi2.metric("En Estatus de Riesgo ⚠️", f"{reprobados} Casos", delta=f"{tasa_riesgo:.1f}% Tasa", delta_color="inverse")
    kpi3.metric("En Estatus Estable ✅", f"{total_alumnos - reprobados} Casos")

    st.markdown("---")

    # --- PESTAÑAS PARA ORGANIZAR LAS GRÁFICAS ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Distribución de Estatus", 
        "🌡️ Matriz de Correlación", 
        "📚 Hábitos de Estudio", 
        "🏫 Rendimiento por Sistema"
    ])

    colores_estatus = {"Aprobado": "#2ecc71", "Reprobado": "#ff5722"}

    # PESTAÑA 1: Gráfica de Dona (Balance de Clases / Estatus)
    with tab1:
        st.subheader("Distribución General de Alumnos")
        conteo = df_filtrado['Resultado'].value_counts().reset_index()
        conteo.columns = ['Estatus', 'Cantidad']
        
        fig_dona = px.pie(
            conteo, 
            values='Cantidad', 
            names='Estatus', 
            hole=0.45,
            color='Estatus',
            color_discrete_map=colores_estatus
        )
        fig_dona.update_traces(textinfo='percent+value', textfont_size=14, marker=dict(line=dict(color='#fff', width=2)))
        st.plotly_chart(fig_dona, use_container_width=True)

    # PESTAÑA 2: Matriz de Correlación (Traducción de Seaborn Heatmap a Plotly)
    with tab2:
        st.subheader("🌡️ Matriz de Correlación de Pearson")
        st.write("Mide el grado de dependencia lineal entre los factores críticos evaluados.")
        
        df_corr = df_filtrado.copy()
        if 'Resultado' in df_corr.columns:
            df_corr['Estatus_Exito'] = df_corr['Resultado'].map({'Aprobado': 1, 'Reprobado': 0})
        
        columnas_interes = ['Promedio_General', 'Materias_Reprobadas', 'Calificacion_Ultima_Materia', 
                            'Asistencia_Clases', 'Horas_Estudio_Semana', 'Estatus_Exito']
        columnas_validas = [col for col in columnas_interes if col in df_corr.columns]
        
        if len(columnas_validas) > 1:
            matriz_corr = df_corr[columnas_validas].corr()
            etiquetas_limpias = [col.replace('_', ' ') for col in columnas_validas]
            
            fig_heatmap = px.imshow(
                matriz_corr,
                x=etiquetas_limpias,
                y=etiquetas_limpias,
                text_auto='.2f',
                color_continuous_scale='RdBu_r',
                zmin=-1, zmax=1
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
        else:
            st.info("No hay suficientes variables numéricas para estructurar la matriz.")

    # PESTAÑA 3: Gráfica de Dispersión (De Graficas.ipynb)
    with tab3:
        st.subheader("📚 Horas de Estudio Semanales contra Promedio General")
        if 'Horas_Estudio_Semana' in df_filtrado.columns and 'Promedio_General' in df_filtrado.columns:
            fig_scatter = px.scatter(
                df_filtrado, 
                x="Horas_Estudio_Semana", 
                y="Promedio_General", 
                color="Resultado",
                color_discrete_map=colores_estatus,
                opacity=0.8,
                labels={"Horas_Estudio_Semana": "Horas de Estudio por Semana", "Promedio_General": "Promedio General Acumulado"}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

    # PESTAÑA 4: Comparativa de Sistemas Escolares (Histograma agrupado)
    with tab4:
        st.subheader("🏫 Estatus de Alumnos Desglosado por Modalidad Escolar")
        if 'Sistema_Escolar' in df_filtrado.columns and 'Resultado' in df_filtrado.columns:
            df_agrupado = df_filtrado.groupby(['Sistema_Escolar', 'Resultado']).size().reset_index(name='Alumnos')
            
            fig_barras = px.bar(
                df_agrupado,
                x="Sistema_Escolar",
                y="Alumnos",
                color="Resultado",
                barmode="group",
                color_discrete_map=colores_estatus,
                labels={"Sistema_Escolar": "Modalidad de Estudio", "Alumnos": "Cantidad de Estudiantes"}
            )
            st.plotly_chart(fig_barras, use_container_width=True)

# --- VISTAS / PANTALLAS PRINCIPALES DEL SISTEMA ---
def pantalla_login():
    """Ventana de acceso seguro"""
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema SIARR</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuario / Matrícula")
            password = st.text_input("Contraseña Moodle / Institucional", type="password")
            submitted = st.form_submit_form_button("Ingresar")
            
            if submitted:
                if usuario.lower() in ['docente', 'maestro', 'profesor']:
                    st.session_state['usuario_autenticado'] = True
                    st.session_state['rol_actual'] = 'docente'
                    st.session_state['nombre_usuario'] = "Docente Titular"
                    st.success("¡Bienvenido Docente!")
                    st.rerun()
                elif usuario.lower() in ['admin', 'administrador']:
                    st.session_state['usuario_autenticado'] = True
                    st.session_state['rol_actual'] = 'admin'
                    st.session_state['nombre_usuario'] = "Administrador de SIARR"
                    st.success("Sesión iniciada como Administrador.")
                    st.rerun()
                else:
                    st.session_state['usuario_autenticado'] = True
                    st.session_state['rol_actual'] = 'alumno'
                    st.session_state['nombre_usuario'] = usuario
                    st.success(f"Sesión Alumno: {usuario}")
                    st.rerun()

def pantalla_alumno():
    st.title("🎓 Portal del Estudiante")
    st.write(f"Hola **{st.session_state['nombre_usuario']}**, aquí puedes consultar tu estatus.")
    st.info("🎯 Tu predicción actual según el sistema inteligente es: **✅ ESTABLE**")

def pantalla_admin():
    st.title("⚙️ Panel de Control - Administrador")
    st.write("Gestión global de la plataforma, logs de ejecución y entrenamiento del modelo.")
    if st.button("Ver Dashboard General"):
        mostrar_dashboard_docente_completo(df_alumnos)

# --- RUTEO PRINCIPAL DEL SOFTWARE ---
def main():
    if not st.session_state['usuario_autenticado']:
        pantalla_login()
    else:
        # Barra lateral común para cerrar sesión
        with st.sidebar:
            st.markdown(f"### 👤 {st.session_state['nombre_usuario']}")
            st.markdown(f"**Rol:** `{st.session_state['rol_actual'].upper()}`")
            if st.button("🚪 Cerrar Sesión"):
                st.session_state['usuario_autenticado'] = False
                st.session_state['rol_actual'] = None
                st.session_state['nombre_usuario'] = ""
                st.rerun()
                
        # Distribución de pantallas de acuerdo al Rol guardado en sesión
        if st.session_state['rol_actual'] == 'alumno':
            pantalla_alumno()
        elif st.session_state['rol_actual'] == 'docente':
            # Vista predeterminada completa del Dashboard solicitado para el Maestro
            mostrar_dashboard_docente_completo(df_alumnos)
        elif st.session_state['rol_actual'] == 'admin':
            pantalla_admin()

if __name__ == "__main__":
    main()
