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

# --- FUNCIONES DE SEGURIDAD (MD5 y Moodle) ---
def generar_md5(texto):
    return hashlib.md5(texto.encode('utf-8')).hexdigest()

def validar_password_moodle(password):
    """Valida: min 8 caracteres, 1 mayúscula, 1 minúscula, 1 número, 1 carácter especial"""
    if len(password) < 8: return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return False
    return True

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR", page_icon=" 🎓 ", layout="wide")

# --- CSS PERSONALIZADO (Optimizado para Computadora y Celular) ---
st.markdown("""
<style>
/* Ocultar elementos innecesarios de Streamlit */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Ajuste del contenedor principal */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: 100% !important;
}

/* Responsividad para pantallas móviles */
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.2rem !important; }
    .stTabs [data-baseweb="tab"] {
        font-size: 12px !important;
        padding: 6px 10px !important;
    }
}

/* Estilo estandarizado para botones */
.stButton>button {
    border-radius: 8px !important;
    font-weight: bold !important;
}

/* Estilos de Tarjetas KPI para el Dashboard */
.kpi-container {
    display: flex;
    gap: 15px;
    margin-bottom: 25px;
}
.kpi-card {
    flex: 1;
    background-color: #f8f9fa;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    border-top: 5px solid #1f77b4;
    text-align: center;
}
.kpi-card h3 { font-size: 1.1rem; color: #555; margin-bottom: 5px; }
.kpi-card h2 { font-size: 2.2rem; color: #2c3e50; margin: 0; font-weight: bold; }

/* Contenedor de Gráficas */
.graph-box {
    background-color: #ffffff;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    border: 1px solid #eef2f5;
    margin-bottom: 25px;
}
</style>
""", unsafe_allow_html=True)

# --- CONTROL DE ESTADOS DE SESIÓN ---
if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None
if 'rol_actual' not in st.session_state:
    st.session_state['rol_actual'] = None
if 'nombre' not in st.session_state:
    st.session_state['nombre'] = ""
if 'alumno_seleccionado_evaluar' not in st.session_state:
    st.session_state['alumno_seleccionado_evaluar'] = ""
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None
if 'df_crudo_entrenamiento' not in st.session_state:
    st.session_state['df_crudo_entrenamiento'] = None 
if 'tab_actual' not in st.session_state:
    st.session_state['tab_actual'] = None

# Variables de navegación del Dashboard (Drill-down)
if 'dash_nivel' not in st.session_state:
    st.session_state['dash_nivel'] = 1
if 'dash_estado_acad' not in st.session_state:
    st.session_state['dash_estado_acad'] = None

class StreamlitLogger(Callback):
    def __init__(self, placeholder):
        self.placeholder = placeholder
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        msg = f"🧠 Entrenando Red Neuronal... Época {epoch+1}/20 | Precisión: {logs.get('accuracy', 0):.2%}"
        self.placeholder.info(msg)

# --- CONEXIÓN Y CONFIGURACIÓN DE BASE DE DATOS ---
def get_db_connection():
    if "DB_HOST" in st.secrets:
        return mysql.connector.connect(
            host=st.secrets["DB_HOST"],
            port=int(st.secrets["DB_PORT"]),
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            database=st.secrets["DB_NAME"]
        )
    else:
        return mysql.connector.connect(
            host="localhost", user="root", password="", database="base_datos_its"
        )

def init_db():
    try:
        if "DB_HOST" not in st.secrets:
            conn = mysql.connector.connect(host="localhost", user="root", password="")
            with conn.cursor() as c:
                c.execute("CREATE DATABASE IF NOT EXISTS base_datos_its")
            conn.close()
            
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                            matricula VARCHAR(50) PRIMARY KEY, 
                            password VARCHAR(50), 
                            rol VARCHAR(50), 
                            nombre VARCHAR(100), 
                            correo VARCHAR(100),
                            docente_id VARCHAR(50) DEFAULT NULL)''')
                
                try:
                    c.execute("ALTER TABLE usuarios ADD COLUMN docente_id VARCHAR(50) DEFAULT NULL")
                    conn.commit()
                except:
                    pass

                c.execute("SELECT COUNT(*) FROM usuarios")
                if c.fetchone()[0] == 0:
                    pwd_default = generar_md5('Temporal123*')
                    usuarios_prueba = [
                        ('admin', pwd_default, 'administrative', 'Coordinación General', 'admin@itsperote.edu.mx', None),
                        ('profe_juan', pwd_default, 'docente', 'Ing. Juan Pérez', 'juan@itsperote.edu.mx', None),
                        ('21050002', pwd_default, 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan'),
                        ('21050003', pwd_default, 'alumno', 'Luz Rueda Tereso', 'rueda@gmail.com', 'profe_juan'),
                        ('21050009', pwd_default, 'alumno', 'Alejandro Ortega Flores', 'ortega@gmail.com', 'profe_juan')
                    ]
                    c.executemany('INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) VALUES (%s, %s, %s, %s, %s, %s)', usuarios_prueba)
                    conn.commit()

                c.execute('''CREATE TABLE IF NOT EXISTS respuestas_alumnos (
                            matricula VARCHAR(50) PRIMARY KEY,
                            sexo VARCHAR(20), semestre INT, sistema VARCHAR(50), 
                            horas_estudio INT, dias_estudio INT, 
                            motivacion INT, confianza INT, dificultad INT, 
                            apoyo INT, estres INT, 
                            computadora VARCHAR(10), internet VARCHAR(10), calidad_internet INT,
                            FOREIGN KEY (matricula) REFERENCES usuarios(matricula) ON DELETE CASCADE)''')

                c.execute('''CREATE TABLE IF NOT EXISTS evaluaciones_docentes (
                            matricula VARCHAR(50) PRIMARY KEY,
                            promedio FLOAT, reprobadas INT, calif_ultima INT, 
                            dias_asistencia INT, asistencia_clases INT, cumplimiento INT, 
                            participacion INT, practicas INT, uso_plataformas INT,
                            FOREIGN KEY (matricula) REFERENCES usuarios(matricula) ON DELETE CASCADE)''')
                conn.commit()
    except mysql.connector.Error as err:
        st.error(f"Error de inicialización de Base de Datos: {err}.")

init_db()

# --- INTERFAZ DE LOGIN ---
if st.session_state['usuario_actual'] is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center;'>🎓 Acceso al Sistema SIARR</h1>", unsafe_allow_html=True)
            st.write("---")
            
            with st.form("formulario_acceso"):
                usuario = st.text_input("Usuario / Matrícula")
                password = st.text_input("Contraseña", type="password")
                boton_ingresar = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)

                if boton_ingresar:
                    if not usuario or not password:
                        st.error("Introduce tu usuario y contraseña.")
                    else:
                        try:
                            password_cifrado = generar_md5(password)
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    c.execute("SELECT * FROM usuarios WHERE matricula=%s AND password=%s", (usuario, password_cifrado))
                                    resultado = c.fetchone()
                                    
                                    if resultado:
                                        st.session_state['usuario_actual'] = resultado[0]
                                        st.session_state['rol_actual'] = str(resultado[2]).lower()
                                        st.session_state['nombre'] = resultado[3]
                                        st.success("¡Acceso concedido!")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error("Usuario o contraseña incorrectos.")
                        except mysql.connector.Error as err:
                            st.error(f"Error en la consulta: {err}")
else:
    # Barra de estado superior
    col_usr, col_btn = st.columns([8, 2])
    with col_usr:
        st.markdown(f"**Usuario conectado:** {st.session_state['nombre']} ({st.session_state['rol_actual'].upper()})")
    with col_btn:
        if st.button("❌ Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state['usuario_actual'] = None
            st.session_state['rol_actual'] = None
            st.session_state['nombre'] = ""
            st.session_state['analisis_completado'] = False
            st.session_state['df_resultados'] = None
            st.session_state['df_crudo_entrenamiento'] = None
            st.session_state['dash_nivel'] = 1
            st.session_state['dash_estado_acad'] = None
            st.rerun()

    def colorear_filas(row):
        if row['Resultado IA'] == '⚠️ RIESGO':
            return ['background-color: #ffcccc; color: #900000'] * len(row)
        elif row['Resultado IA'] == '✅ ESTABLE':
            return ['background-color: #e6ffe6; color: #006600'] * len(row)
        return [''] * len(row)

    # --- MÓDULO DE ENTRENAMIENTO E IA ---
    def mostrar_modulo_ia():
        st.markdown("### 🧠 Inteligencia Artificial con Aprendizaje Profundo")
        st.write("Detección de riesgo de reprobación en asignaturas de programación mediante análisis de desempeño predictivo.")
        
        if 'admin' in st.session_state['rol_actual'] or 'administrative' in st.session_state['rol_actual']:
            st.markdown("#### 📂 Configuración del Dataset de Entrenamiento")
            col_da1, col_da2 = st.columns([2, 1])
            with col_da1:
                archivo_cargado = st.file_uploader("Agregar un nuevo dataset para el análisis (.csv, .xlsx)", type=["csv", "xlsx"], key="file_uploader_ia")
                if archivo_cargado is not None:
                    try:
                        ext = ".xlsx" if archivo_cargado.name.endswith('.xlsx') else ".csv"
                        nombre_archivo_compartido = f"dataset_compartido_admin{ext}"
                        if os.path.exists("dataset_compartido_admin.xlsx"): os.remove("dataset_compartido_admin.xlsx")
                        if os.path.exists("dataset_compartido_admin.csv"): os.remove("dataset_compartido_admin.csv")
                        
                        with open(nombre_archivo_compartido, "wb") as f:
                            f.write(archivo_cargado.getbuffer())
                        st.success(f"✅ Dataset guardado globalmente en el servidor: {archivo_cargado.name}")
                    except Exception as e:
                        st.error(f"Error al escribir el archivo compartido: {e}")
            with col_da2:
                st.write("")
                st.write("")
                if st.button("🗑️ Borrar Dataset de Análisis", type="secondary", use_container_width=True):
                    if os.path.exists("dataset_compartido_admin.xlsx"): os.remove("dataset_compartido_admin.xlsx")
                    if os.path.exists("dataset_compartido_admin.csv"): os.remove("dataset_compartido_admin.csv")
                    st.session_state['analisis_completado'] = False
                    st.session_state['df_resultados'] = None
                    st.session_state['df_crudo_entrenamiento'] = None
                    st.warning("Dataset personalizado eliminado. Se usará el archivo local predeterminado.")
                    time.sleep(0.5)
                    st.rerun()

        if os.path.exists("dataset_compartido_admin.xlsx") or os.path.exists("dataset_compartido_admin.csv"):
            st.info("ℹ️ Actualmente utilizando el dataset compartido cargado por el Administrador.")
        else:
            st.info("ℹ️ Utilizando el dataset histórico predeterminado del sistema institucional.")
            
        if st.button("🚀 Iniciar Análisis de Red Neuronal", type="primary", use_container_width=True):
            consola_placeholder = st.empty()
            consola_placeholder.info("Buscando y cargando archivo de base de datos histórico...")
            
            try:
                os.environ['PYTHONHASHSEED'] = '42'
                np.random.seed(42)
                random.seed(42)
                tf.random.set_seed(42)
                
                if os.path.exists("dataset_compartido_admin.xlsx"):
                    df = pd.read_excel("dataset_compartido_admin.xlsx")
                elif os.path.exists("dataset_compartido_admin.csv"):
                    df = pd.read_csv("dataset_compartido_admin.csv")
                else:
                    archivo_csv = 'dataset_final_sin_duplicados.xlsx - Sheet1.csv'
                    archivo_excel = 'dataset_final_sin_duplicados.xlsx'
                    if os.path.exists(archivo_csv):
                        df = pd.read_csv(archivo_csv)
                    elif os.path.exists(archivo_excel):
                        df = pd.read_excel(archivo_excel)
                    else:
                        st.error("❌ Error: No se encontró ningún archivo de base de datos histórico.")
                        return

                st.session_state['df_crudo_entrenamiento'] = df.copy()

                cols_ignorar = ['Matrícula', 'Matricula', 'matricula', 'Nombre', 'Nombre_completo', 'ID', 'Id']
                df = df.drop(columns=[c for c in cols_ignorar if c in df.columns], errors='ignore')
                
                if 'Resultado' in df.columns:
                    df['Resultado'] = df['Resultado'].map({'Aprobado': 0, 'Reprobado': 1, 0:0, 1:1})
                df = df.dropna(subset=['Resultado'])
                
                if 'Sexo' in df.columns:
                    df['Sexo_Num'] = df['Sexo'].map({'Hombre': 0, 'Mujer': 1}).fillna(0)
                if 'Sistema_Escolar' in df.columns:
                    df['Sistema_Escolar_Num'] = df['Sistema_Escolar'].map({'Escolarizado': 0, 'Semiescolarizado': 1}).fillna(0)
                    
                df_train, df_test = train_test_split(df, test_size=0.2, random_state=42)
                y_train = df_train['Resultado']
                X_train_bruto = df_train.drop(columns=['Resultado'], errors='ignore')
                X_train = X_train_bruto.select_dtypes(include=[np.number]).fillna(0)
                
                nombres_variables = X_train.columns
                correlaciones = X_train.corrwith(y_train).fillna(0).values
                
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                
                model = Sequential([
                    Input(shape=(X_train_scaled.shape[1],)),
                    Dense(64, activation='relu'),
                    Dropout(0.3),
                    Dense(32, activation='relu'),
                    Dense(1, activation='sigmoid')
                ])
                
                model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
                model.fit(X_train_scaled, y_train, epochs=20, shuffle=False, callbacks=[StreamlitLogger(consola_placeholder)], verbose=0)
                consola_placeholder.success("✅ Red neuronal entrenada con éxito.")
                
                query_completos = """
                SELECT 
                    u.matricula, u.nombre, 
                    (SELECT nombre FROM usuarios WHERE matricula = u.docente_id) as maestro_responsable,
                    ra.semestre, ra.sexo, ra.sistema, 
                    ed.promedio, ed.reprobadas, ed.calif_ultima, ed.dias_asistencia, 
                    ed.asistencia_clases, ed.cumplimiento, ed.participacion, ed.practicas, ed.uso_plataformas,
                    ra.horas_estudio, ra.dias_estudio, ra.apoyo, ra.motivacion, ra.confianza, ra.dificultad, ra.estres,
                    ra.computadora, ra.internet, ra.calidad_internet
                FROM usuarios u
                INNER JOIN respuestas_alumnos ra ON u.matricula = ra.matricula
                INNER JOIN evaluaciones_docentes ed ON u.matricula = ed.matricula
                WHERE u.rol = 'alumno'
                """
                
                parametros_query = []
                if st.session_state.get('rol_actual') == 'docente':
                    query_completos += " AND u.docente_id = %s"
                    parametros_query.append(st.session_state['usuario_actual'])
                    
                with get_db_connection() as conn:
                    df_db = pd.read_sql(query_completos, conn, params=parametros_query if parametros_query else None)
                    
                if df_db.empty:
                    st.warning("⚠️ No hay alumnos con expedientes completos en la base de datos.")
                    st.session_state['analisis_completado'] = False
                else:
                    df_db_prep = pd.DataFrame()
                    df_db_prep['Matrícula'] = df_db['matricula']
                    df_db_prep['Nombre_completo'] = df_db['nombre']
                    df_db_prep['Docente_Tutor'] = df_db['maestro_responsable'].fillna("Sin Asignar")
                    df_db_prep['Semestre'] = df_db['semestre']
                    df_db_prep['Sexo_Num'] = df_db['sexo'].map({'Hombre': 0, 'Mujer': 1}).fillna(0)
                    df_db_prep['Sistema_Escolar_Num'] = df_db['sistema'].map({'Escolarizado': 0, 'Semiescolarizado': 1}).fillna(0)
                    df_db_prep['Promedio_General'] = df_db['promedio']
                    df_db_prep['Materias_Reprobadas'] = df_db['reprobadas']
                    df_db_prep['Calificacion_Ultima_Materia'] = df_db['calif_ultima']
                    df_db_prep['Dias_Asistencia'] = df_db['dias_asistencia']
                    df_db_prep['Asistencia_Clases'] = df_db['asistencia_clases']
                    df_db_prep['Cumplimiento_Tareas'] = df_db['cumplimiento']
                    df_db_prep['Participacion_Clase'] = df_db['participacion']
                    df_db_prep['Practicas_Programacion'] = df_db['practicas']
                    df_db_prep['Uso_Plataformas'] = df_db['uso_plataformas']
                    df_db_prep['Horas_Estudio_Semana'] = df_db['horas_estudio']
                    df_db_prep['Dias_Estudio_Semana'] = df_db['dias_estudio']
                    df_db_prep['Apoyo_Familiar'] = df_db['apoyo']
                    df_db_prep['Motivacion_Programacion'] = df_db['motivacion']
                    df_db_prep['Confianza_Aprobar'] = df_db['confianza']
                    df_db_prep['Dificultad_Materia'] = df_db['dificultad']
                    df_db_prep['Nivel_Estres'] = df_db['estres']
                    df_db_prep['Computadora_Propia'] = df_db['computadora'].map({'Sí': 1, 'No': 0}).fillna(0)
                    df_db_prep['Internet_Casa'] = df_db['internet'].map({'Sí': 1, 'No': 0}).fillna(0)
                    df_db_prep['Calidad_Internet'] = df_db['calidad_internet']
                    
                    X_custom = df_db_prep.reindex(columns=nombres_variables, fill_value=0)
                    X_custom_scaled = scaler.transform(X_custom)
                    predicciones_custom = model.predict(X_custom_scaled, verbose=0)
                    
                    resultados_custom = []
                    for i, prob in enumerate(predicciones_custom):
                        fila = df_db_prep.iloc[i]
                        prob_num = prob[0]
                        
                        if prob_num >= 0.50:
                            nivel = "🔴 Alto"
                            estado = "⚠️ RIESGO"
                        else:
                            nivel = "🟢 Bajo"
                            estado = "✅ ESTABLE"
                            
                        if estado == "⚠️ RIESGO":
                            impacto_variables = X_custom_scaled[i] * correlaciones
                            impacto_dict = {nombres_variables[j]: impacto_variables[j] for j in range(len(nombres_variables))}
                            top_3 = sorted(impacto_dict.items(), key=lambda x: x[1], reverse=True)[:3]
                            motivos = [f"{str(var).replace('_', ' ')} ({fila.get(var, 'N/A')})" for var, imp in top_3]
                            motivos_str = " | ".join(motivos)
                        else:
                            motivos_str = "Buen rendimiento general"
                            
                        resultados_custom.append({
                            "Matrícula": fila.get('Matrícula'),
                            "Nombre": fila.get('Nombre_completo'),
                            "Docente Asignado": fila.get('Docente_Tutor'),
                            "Semestre": fila.get('Semestre'),
                            "Promedio_General": fila.get('Promedio_General'),
                            "Asistencia_Clases": fila.get('Asistencia_Clases'),
                            "Resultado IA": estado,
                            "Nivel de Riesgo": nivel,
                            "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                            "Factores Críticos": motivos_str
                        })
                        
                    df_resultados = pd.DataFrame(resultados_custom)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_resultados.to_excel(writer, index=False, sheet_name='Diagnóstico')
                        worksheet = writer.sheets['Diagnóstico']
                        fill_riesgo = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
                        fill_estable = PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid")
                        
                        try:
                            idx_col_resultado = df_resultados.columns.get_loc("Resultado IA") + 1
                            for r_num in range(2, len(df_resultados) + 2):
                                cell_val = worksheet.cell(row=r_num, column=idx_col_resultado).value
                                current_fill = fill_riesgo if cell_val == "⚠️ RIESGO" else fill_estable if cell_val == "✅ ESTABLE" else None
                                if current_fill:
                                    for c_num in range(1, len(df_resultados.columns) + 1):
                                        worksheet.cell(row=r_num, column=c_num).fill = current_fill
                        except:
                            pass
                            
                    st.session_state['df_resultados'] = df_resultados
                    st.session_state['excel_data'] = buffer.getvalue()
                    st.session_state['analisis_completado'] = True
            except Exception as e:
                st.error(f"❌ ERROR: {str(e)}")
                st.session_state['analisis_completado'] = False

        if st.session_state['analisis_completado'] and st.session_state['df_resultados'] is not None:
            st.markdown("---")
            st.subheader("📋 Diagnóstico de Alumnos Activos")
            cols_vista = ['Matrícula', 'Nombre', 'Semestre', 'Resultado IA', 'Nivel de Riesgo', 'Prob. Exacta (%)', 'Factores Críticos']
            df_vista_rapida = st.session_state['df_resultados'][cols_vista]
            st.dataframe(df_vista_rapida.style.apply(colorear_filas, axis=1), use_container_width=True)
            
            st.download_button(
                label="📥 Descargar Reporte de Diagnóstico Completo (Excel)",
                data=st.session_state['excel_data'],
                file_name=f"Reporte_IA_SIARR_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # =====================================================================
    # --- MÓDULO MODIFICADO: DASHBOARD INTERACTIVO REESTRUCTURADO ---
    # =====================================================================
    def mostrar_dashboard_interactivo():
        if not st.session_state.get('analisis_completado') or st.session_state.get('df_resultados') is None:
            st.warning("⚠️ Primero debes ejecutar el diagnóstico de IA en la pestaña '🚀 Ejecutar Diagnóstico IA' para visualizar el Dashboard.")
            return

        df_resultados = st.session_state['df_resultados'].copy()
        
        # Recuperar datos de análisis exploratorio
        if 'df_crudo_entrenamiento' in st.session_state and st.session_state['df_crudo_entrenamiento'] is not None:
            df_exploratorio = st.session_state['df_crudo_entrenamiento'].copy()
        else:
            df_exploratorio = pd.DataFrame()

        # Normalizar datos históricos si existen
        if not df_exploratorio.empty and 'Resultado' in df_exploratorio.columns:
            if df_exploratorio['Resultado'].dtype == 'O':
                df_exploratorio['Resultado_Str'] = df_exploratorio['Resultado']
                df_exploratorio['Resultado_Bin'] = df_exploratorio['Resultado'].map({'Aprobado': 0, 'Reprobado': 1}).fillna(1)
            else:
                df_exploratorio['Resultado_Bin'] = df_exploratorio['Resultado']
                df_exploratorio['Resultado_Str'] = df_exploratorio['Resultado'].map({0: 'Aprobado', 1: 'Reprobado'}).fillna('Reprobado')

        st.markdown("<h2 style='text-align: center; color: #2C3E50;'>📊 Dashboard Estratégico Interactivo (SIARR)</h2><hr>", unsafe_allow_html=True)

        # -------------------------------------------------------------
        # Nivel 1: Métricas Globales y Gráficos Estáticos Reordenados
        # -------------------------------------------------------------
        if st.session_state['dash_nivel'] == 1:
            # 1. BLOQUE SUPERIOR DE TARJETAS KPI
            total_evaluados = len(df_resultados)
            passed_real = len(df_exploratorio[df_exploratorio['Resultado_Bin'] == 0]) if 'Resultado_Bin' in df_exploratorio.columns else 0
            failed_real = len(df_exploratorio[df_exploratorio['Resultado_Bin'] == 1]) if 'Resultado_Bin' in df_exploratorio.columns else 0
            criticos_riesgo = len(df_resultados[df_resultados['Resultado IA'] == '⚠️ RIESGO'])

            st.markdown(f"""
            <div class="kpi-container">
                <div class="kpi-card"><h3>👥 Alumnos Activos</h3><h2>{total_evaluados}</h2></div>
                <div class="kpi-card" style="border-top-color: #2ecc71;"><h3>✅ Aprobados (Histórico)</h3><h2>{passed_real}</h2></div>
                <div class="kpi-card" style="border-top-color: #e74c3c;"><h3>🛑 Reprobados (Histórico)</h3><h2>{failed_real}</h2></div>
                <div class="kpi-card" style="border-top-color: #f39c12;"><h3>🚨 Casos en Riesgo</h3><h2>{criticos_riesgo}</h2></div>
            </div>
            """, unsafe_allow_html=True)

            # 2. VARIABLES QUE MÁS INFLUYEN (EN LA PARTE SUPERIOR COMPLETAMENTE ANCHA)
            st.markdown('<div class="graph-box">', unsafe_allow_html=True)
            st.write("#### 🚨 Variables que más influyen en la reprobación")
            if not df_exploratorio.empty:
                target_col = 'Resultado_Bin'
                df_corr = df_exploratorio.select_dtypes(include=[np.number])
                if target_col in df_corr.columns:
                    correlations = df_corr.corr()[target_col].abs().sort_values(ascending=False).drop(target_col, errors='ignore')
                    clean_names = [name.replace('_', ' ') for name in correlations.index]
                    df_imp = pd.DataFrame({'Variable': clean_names, 'Importancia Relativa': correlations.values})
                    df_imp_top = df_imp.head(10)

                    fig_variables = px.bar(
                        df_imp_top, x='Importancia Relativa', y='Variable', orientation='h',
                        color='Importancia Relativa', color_continuous_scale='Reds'
                    )
                    fig_variables.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=10, r=10, t=10, b=10), height=350)
                    st.plotly_chart(fig_variables, use_container_width=True)
                else:
                    st.warning("No se pudo procesar la matriz de importancia de variables.")
            else:
                st.info("Información histórica no disponible.")
            st.markdown('</div>', unsafe_allow_html=True)

            st.write("---")

            # 3. FILA DE PARALELOS: APROBADOS VS REPROBADOS Y SEMESTRES
            col_izq, col_der = st.columns(2)

            with col_izq:
                st.markdown('<div class="graph-box">', unsafe_allow_html=True)
                st.write("#### ✅ Distribución General: Aprobados vs Reprobados (Histórico)")
                if 'Resultado_Str' in df_exploratorio.columns:
                    fig_passed_failed = px.histogram(
                        df_exploratorio, x="Resultado_Str", color="Resultado_Str",
                        color_discrete_map={'Aprobado': '#2ecc71', 'Reprobado': '#e74c3c'},
                        labels={'Resultado_Str': 'Estatus'}, text_auto=True
                    )
                    fig_passed_failed.update_layout(yaxis_title="Cantidad", margin=dict(l=10, r=10, t=20, b=10), height=300, showlegend=False)
                    st.plotly_chart(fig_passed_failed, use_container_width=True)
                else:
                    st.warning("Columna objetivo 'Resultado' ausente en el archivo cargado.")
                st.markdown('</div>', unsafe_allow_html=True)

            with col_der:
                st.markdown('<div class="graph-box">', unsafe_allow_html=True)
                st.write("#### 📅 Distribución por Semestre")
                if 'Semestre' in df_exploratorio.columns:
                    fig_semestres = px.histogram(
                        df_exploratorio, x="Semestre", color_discrete_sequence=['#34495E'], text_auto=True
                    )
                    fig_semestres.update_layout(yaxis_title="Alumnos", margin=dict(l=10, r=10, t=20, b=10), height=300)
                    st.plotly_chart(fig_semestres, use_container_width=True)
                else:
                    st.warning("Campo 'Semestre' no indexado.")
                st.markdown('</div>', unsafe_allow_html=True)

            # 4. COMPORTAMIENTO EXTRA EXTRADÍDO DE JUPYTER
            if not df_exploratorio.empty:
                col_extra1, col_extra2 = st.columns(2)
                with col_extra1:
                    st.markdown('<div class="graph-box">', unsafe_allow_html=True)
                    st.write("#### 📉 Rendimiento por Género")
                    ejex = 'Sexo' if 'Sexo' in df_exploratorio.columns else None
                    ejey = 'Calificación_Final' if 'Calificación_Final' in df_exploratorio.columns else ('Promedio_General' if 'Promedio_General' in df_exploratorio.columns else None)
                    if ejex and ejey:
                        fig_rend = px.box(df_exploratorio, x=ejex, y=ejey, color=ejex, color_discrete_map={'Hombre': '#3498db', 'Mujer': '#e74c3c'})
                        fig_rend.update_layout(margin=dict(l=10, r=10, t=15, b=10), height=280, showlegend=False)
                        st.plotly_chart(fig_rend, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with col_extra2:
                    st.markdown('<div class="graph-box">', unsafe_allow_html=True)
                    st.write("#### ⏱️ Nivel de Asistencia por Género")
                    ejey_asist = 'Asistencia' if 'Asistencia' in df_exploratorio.columns else ('Asistencia_Clases' if 'Asistencia_Clases' in df_exploratorio.columns else None)
                    if ejex and ejey_asist:
                        fig_asist = px.box(df_exploratorio, x=ejex, y=ejey_asist, color=ejex, color_discrete_map={'Hombre': '#3498db', 'Mujer': '#e74c3c'})
                        fig_asist.update_layout(margin=dict(l=10, r=10, t=15, b=10), height=280, showlegend=False)
                        st.plotly_chart(fig_asist, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            # 5. PANEL INTERACTIVO DE DRILL-DOWN (EXPLORAR ALUMNOS ACTUALES)
            st.write("---")
            st.markdown("### 🔍 Explorar Población Actual Específica (Drill-Down)")
            
            col_sec1, col_sec2 = st.columns([1, 1.2])
            with col_sec1:
                st.markdown('<div class="graph-box">', unsafe_allow_html=True)
                fig_dona = px.pie(
                    df_resultados, names='Resultado IA', hole=0.45,
                    color='Resultado IA', color_discrete_map={'⚠️ RIESGO': '#e74c3c', '✅ ESTABLE': '#2ecc71'}
                )
                fig_dona.update_traces(textposition='inside', textinfo='percent+label')
                fig_dona.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=240)
                st.plotly_chart(fig_dona, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
            with col_sec2:
                st.write("<br>", unsafe_allow_html=True)
                btn_critico = st.button("🔴 Ver Críticos", use_container_width=True)
                btn_bueno = st.button("✅ Ver Estables", use_container_width=True)

                if btn_critico:
                    st.session_state['dash_estado_acad'] = '⚠️ RIESGO'
                    st.session_state['dash_nivel'] = 2
                    st.rerun()
                if btn_bueno:
                    st.session_state['dash_estado_acad'] = '✅ ESTABLE'
                    st.session_state['dash_nivel'] = 2
                    st.rerun()

        # -------------------------------------------------------------
        # Nivel 2: Desglose por Alumno (Ruta Drill-down)
        # -------------------------------------------------------------
        elif st.session_state['dash_nivel'] == 2:
            st.markdown(f"### 🔍 Alumnos identificados bajo el criterio: {st.session_state['dash_estado_acad']}")
            
            if st.button("⬅️ Volver a Gráficas Principales", type="secondary", use_container_width=True):
                st.session_state['dash_nivel'] = 1
                st.session_state['dash_estado_acad'] = None
                st.rerun()
                
            df_filtrado = df_resultados[df_resultados['Resultado IA'] == st.session_state['dash_estado_acad']]
            if df_filtrado.empty:
                st.info("No se hallaron registros en este segmento.")
            else:
                cols_mostrar = ['Matrícula', 'Nombre', 'Semestre', 'Promedio_General', 'Asistencia_Clases', 'Prob. Exacta (%)', 'Factores Críticos']
                st.dataframe(df_filtrado[[c for c in cols_mostrar if c in df_filtrado.columns]], use_container_width=True)

    # --- CONTROLADORES DE RUTA DEL MENÚ LATERAL ---
    st.sidebar.title("🧭 Menú de Navegación")
    rol = st.session_state['rol_actual']
    
    if 'admin' in rol or 'administrative' in rol:
        opciones_menu = ["👥 Gestión de Usuarios", "🚀 Ejecutar Diagnóstico IA", "📊 Dashboard Estratégico"]
    elif 'docente' in rol:
        opciones_menu = ["📝 Evaluar Alumnos", "🚀 Ejecutar Diagnóstico IA", "📊 Dashboard Estratégico"]
    else:
        opciones_menu = ["📝 Responder Cuestionario"]
        
    seleccion = st.sidebar.radio("Selecciona una sección:", opciones_menu)
    st.write("---")
    
    if seleccion == "🚀 Ejecutar Diagnóstico IA":
        mostrar_modulo_ia()
    elif seleccion == "📊 Dashboard Estratégico":
        mostrar_dashboard_interactivo()
    elif seleccion == "👥 Gestión de Usuarios":
        st.subheader("👥 Control de Usuarios (CRUD)")
        st.info("Módulo de administración. Alta, modificación y control de accesos institucionales.")
    elif seleccion == "📝 Evaluar Alumnos":
        st.subheader("📝 Evaluación del Desempeño por el Docente")
        st.info("Formulario para asentar el progreso, nivel de tareas y asistencias del estudiante.")
    elif seleccion == "📝 Responder Cuestionario":
        st.subheader("📝 Cuestionario de Hábitos de Estudio (Alumno)")
        st.info("Espacio designado para la recolección de hábitos de estudio.")
