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
st.set_page_config(page_title="SIARR", page_icon="🎓", layout="wide")

# --- CSS PERSONALIZADO (Optimizado para Computadora y Celular) ---
st.markdown("""
<style>
/* Ocultar menú y marca de agua de Streamlit */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* 💻 Diseño para Computadora (Pantallas grandes) */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: 100% !important;
}

/* 📱 Diseño Específico para Celulares */
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
    .stDataFrame {
        overflow-x: auto;
    }
}

/* Botones con estilo moderno */
.stButton>button {
    border-radius: 8px !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

# --- CONTROL DE SESIONES ---
if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None
if 'rol_actual' not in st.session_state:
    st.session_state['rol_actual'] = None
if 'nombre' not in st.session_state:
    st.session_state['nombre'] = ""
if 'alumno_seleccionado_evaluar' not in st.session_state:
    st.session_state['alumno_seleccionado_evaluar'] = ""
if 'tab_actual' not in st.session_state:
    st.session_state['tab_actual'] = None
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None
if 'df_crudo_entrenamiento' not in st.session_state:
    st.session_state['df_crudo_entrenamiento'] = None 

# Variables para el Dashboard Drill-Down
if 'dash_nivel' not in st.session_state:
    st.session_state['dash_nivel'] = 1
if 'dash_estado_acad' not in st.session_state:
    st.session_state['dash_estado_acad'] = None
if 'dash_semestre' not in st.session_state:
    st.session_state['dash_semestre'] = None

class StreamlitLogger(Callback):
    def __init__(self, placeholder):
        self.placeholder = placeholder
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        msg = f"🧠 Entrenando Red Neuronal... Época {epoch+1}/20 | Precisión: {logs.get('accuracy', 0):.2%}"
        self.placeholder.info(msg)

# --- FUNCIÓN DE CONEXIÓN A BASE DE DATOS ---
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
            host="localhost",
            user="root",
            password="",
            database="base_datos_its"
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
                        ('21050009', pwd_default, 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan')
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
            st.markdown("<h1 style='text-align: center;'>🎓 Acceso al Sistema</h1>", unsafe_allow_html=True)
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
                                        rol_bd = str(resultado[2]).lower()
                                        st.session_state['rol_actual'] = rol_bd
                                        st.session_state['nombre'] = resultado[3]
                                        
                                        if 'admin' in rol_bd:
                                            st.session_state['tab_actual'] = "👥 Gestión de Usuarios (CRUD)"
                                        else:
                                            st.session_state['tab_actual'] = "📝 Carga la información del Alumno"
                                            
                                        st.success("¡Acceso concedido!")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error("Usuario o contraseña incorrectos.")
                        except mysql.connector.Error as err:
                            st.error(f"Error en la consulta: {err}")

else:
    # --- MENÚ SUPERIOR DE CIERRE DE SESIÓN ---
    col_usr, col_btn = st.columns([8, 2])
    with col_usr:
        st.markdown(f"**Usuario conectado:** {st.session_state['nombre']} ({st.session_state['rol_actual'].upper()})")
    with col_btn:
        if st.button("❌ Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state['usuario_actual'] = None
            st.session_state['rol_actual'] = None
            st.session_state['nombre'] = ""
            st.session_state['tab_actual'] = None
            st.session_state['dash_nivel'] = 1
            st.session_state['dash_estado_acad'] = None
            st.session_state['dash_semestre'] = None
            st.rerun()

    def colorear_filas(row):
        if row['Resultado IA'] == '⚠️ RIESGO':
            return ['background-color: #ffcccc; color: #900000'] * len(row)
        elif row['Resultado IA'] == '✅ ESTABLE':
            return ['background-color: #e6ffe6; color: #006600'] * len(row)
        return [''] * len(row)

    # --- MÓDULO DE IA ---
    def mostrar_modulo_ia():
        st.markdown("### 🧠 Inteligencia Artificial con Aprendizaje Profundo")
        st.write("Detección de riesgo de reprobación en asignaturas de programación mediante análisis de desempeño predictivo.")
        
        if 'admin' in st.session_state['rol_actual']:
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
                    st.warning("Dataset personalizado eliminado del servidor. Se usará el archivo local por defecto.")
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
                        st.error("❌ Error: No se encontró ningún archivo de base de datos histórico en el servidor.")
                        return

                # Guardamos copia original para extraer info rica en el Dashboard
                st.session_state['df_crudo_entrenamiento'] = df.copy()

                cols_ignorar = ['Matrícula', 'Matricula', 'matricula', 'Nombre', 'Nombre_completo', 'ID', 'Id']
                df = df.drop(columns=[c for c in cols_ignorar if c in df.columns], errors='ignore')
                
                if 'Resultado' in df.columns:
                    df['Resultado'] = df['Resultado'].map({'Aprobado': 0, 'Reprobado': 1})
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
                    st.warning("⚠️ No hay alumnos con expedientes completos (deben responder el cuestionario y ser evaluados).")
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
                        
                        if prob_num >= 0.70:
                            nivel = "🔴 Alto"
                            estado = "⚠️ RIESGO"
                        elif prob_num >= 0.40:
                            nivel = "🟡 Medio"
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
                            
                        # Guardamos info valiosa para el Dashboard
                        resultados_custom.append({
                            "Matrícula": fila.get('Matrícula'),
                            "Nombre": fila.get('Nombre_completo'),
                            "Docente Asignado": fila.get('Docente_Tutor'),
                            "Semestre": fila.get('Semestre'),
                            "Sistema_Escolar": fila.get('Sistema_Escolar_Num'),
                            "Nivel_Estres": fila.get('Nivel_Estres'),
                            "Promedio_General": fila.get('Promedio_General'),
                            "Asistencia_Clases": fila.get('Asistencia_Clases'),
                            "Horas_Estudio": fila.get('Horas_Estudio_Semana'),
                            "Resultado IA": estado,
                            "Nivel de Riesgo": nivel,
                            "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                            "Factores Críticos": motivos_str
                        })
                        
                    df_resultados = pd.DataFrame(resultados_custom)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_resultados.to_excel(writer, index=False, sheet_name='Diagnóstico')
                        workbook = writer.book
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
                st.error(f"❌ ERROR DETECTADO: {str(e)}")
                traceback.print_exc()
                st.session_state['analisis_completado'] = False

        if st.session_state['analisis_completado'] and st.session_state['df_resultados'] is not None:
            st.markdown("---")
            st.subheader("📋 Diagnóstico de Alumnos Activos")
            
            cols_vista = ['Matrícula', 'Nombre', 'Semestre', 'Resultado IA', 'Nivel de Riesgo', 'Prob. Exacta (%)', 'Factores Críticos']
            df_vista_rapida = st.session_state['df_resultados'][cols_vista]
            
            df_estilado = df_vista_rapida.style.apply(colorear_filas, axis=1)
            st.dataframe(df_estilado, use_container_width=True)
            
            st.download_button(
                label="📥 Descargar Reporte de Diagnóstico (Excel)",
                data=st.session_state['excel_data'],
                file_name=f"Reporte_IA_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # ==========================================
    # MÓDULO: DASHBOARD INTERACTIVO INNOVADOR (Con Gráficas Completas del Original)
    # ==========================================
    def mostrar_dashboard_interactivo():
        if not st.session_state.get('analisis_completado') or st.session_state.get('df_resultados') is None:
            st.warning("⚠️ Primero debes ejecutar el diagnóstico de IA en la pestaña '🚀 Ejecutar Diagnóstico' para visualizar el Dashboard.")
            return

        df = st.session_state['df_resultados'].copy()
        df_crudo = st.session_state.get('df_crudo_entrenamiento') 
        
        # Segmentación
        if 'Prob. Exacta (%)' in df.columns:
            probs = df['Prob. Exacta (%)'].astype(str).str.rstrip('%').astype(float) / 100.0
        else:
            probs = pd.Series([0.0]*len(df))

        condiciones = [
            probs >= 0.70,
            (probs >= 0.40) & (probs < 0.70),
            probs < 0.40
        ]
        opciones = ['🔴 Reprobados / Crítico', '🟡 En Riesgo de Reprobación', '🟢 Buen Rendimiento']
        df['Estado_Dashboard'] = np.select(condiciones, opciones, default='🟢 Buen Rendimiento')

        # ------------------------------------------
        # NIVEL 1: VISTA GENERAL (Donut & Matriz de Correlación)
        # ------------------------------------------
        if st.session_state.dash_nivel == 1:
            st.markdown("<h2 style='text-align: center; color: #2C3E50;'>📊 Visión Estratégica Institucional</h2>", unsafe_allow_html=True)
            st.write("---")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("👥 Total Evaluados", len(df))
            col2.metric("🔴 Estado Crítico", len(df[df['Estado_Dashboard'] == '🔴 Reprobados / Crítico']))
            col3.metric("🟡 Riesgo Moderado", len(df[df['Estado_Dashboard'] == '🟡 En Riesgo de Reprobación']))
            col4.metric("🟢 Buen Rendimiento", len(df[df['Estado_Dashboard'] == '🟢 Buen Rendimiento']))
            
            st.write("<br>", unsafe_allow_html=True)
            
            col_chart, col_heat = st.columns([1, 1.2])
            
            # Gráfica 1: Donut Chart (Conservada)
            with col_chart:
                st.markdown("#### Distribución de Estatus Académico")
                fig_donut = px.pie(
                    df, names='Estado_Dashboard', hole=0.45,
                    color='Estado_Dashboard',
                    color_discrete_map={
                        '🔴 Reprobados / Crítico': '#e74c3c', 
                        '🟡 En Riesgo de Reprobación': '#f39c12', 
                        '🟢 Buen Rendimiento': '#2ecc71'
                    }
                )
                fig_donut.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#FFFFFF', width=2)))
                fig_donut.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_donut, use_container_width=True)
                
            # Gráfica 2: Matriz de Correlación (Del Jupyter Original)
            with col_heat:
                st.markdown("#### Impacto Global de Variables Base (Matriz Correlación)")
                if df_crudo is not None and not df_crudo.empty:
                    # Buscamos columnas originales numéricas para hacer la matriz
                    cols_num = df_crudo.select_dtypes(include=[np.number]).columns.tolist()
                    cols_claves = [c for c in cols_num if c.lower() in ['promedio', 'estres', 'asistencias', 'semestre', 'calificacion', 'resultado', 'nivel_estres']]
                    
                    if len(cols_claves) >= 3:
                        corr_matrix = df_crudo[cols_claves].corr().round(2)
                        fig_heat = px.imshow(
                            corr_matrix, text_auto=True, aspect="auto", color_continuous_scale='RdBu_r'
                        )
                        fig_heat.update_layout(margin=dict(t=20, b=20, l=20, r=20))
                        st.plotly_chart(fig_heat, use_container_width=True)
                    else:
                        st.info("No hay suficientes variables numéricas crudas para generar la Matriz de Correlación de forma confiable.")
                else:
                    st.info("Sincroniza un dataset completo en la vista anterior para habilitar la Matriz de Correlación profunda.")

            st.write("---")
            st.markdown("### 🔍 Explorar Población Específica (Drill-Down):")
            c1, c2, c3 = st.columns(3)
            if c1.button("🚨 Ver Críticos / Reprobados", use_container_width=True):
                st.session_state.dash_estado_acad = '🔴 Reprobados / Crítico'
                st.session_state.dash_nivel = 2
                st.rerun()
            if c2.button("⚠️ Ver En Riesgo de Reprobación", use_container_width=True):
                st.session_state.dash_estado_acad = '🟡 En Riesgo de Reprobación'
                st.session_state.dash_nivel = 2
                st.rerun()
            if c3.button("✅ Ver Buen Rendimiento", use_container_width=True):
                st.session_state.dash_estado_acad = '🟢 Buen Rendimiento'
                st.session_state.dash_nivel = 2
                st.rerun()

        # ------------------------------------------
        # NIVEL 2: FILTROS (Treemap, Boxplot & Contexto)
        # ------------------------------------------
        elif st.session_state.dash_nivel == 2:
            if st.button("⬅️ Regresar a Vista General", type="secondary"):
                st.session_state.dash_nivel = 1
                st.session_state.dash_estado_acad = None
                st.rerun()
                
            estado = st.session_state.dash_estado_acad
            st.markdown(f"### 🗺️ Concentración de Alumnos: {estado}")
            
            df_filtrado = df[df['Estado_Dashboard'] == estado]
            
            if df_filtrado.empty:
                st.info("No hay alumnos clasificados en esta categoría.")
            else:
                col_tree, col_box = st.columns([1, 1.2])
                
                # Gráfica 3: Treemap de Semestres
                with col_tree:
                    conteo_semestres = df_filtrado['Semestre'].value_counts().reset_index()
                    conteo_semestres.columns = ['Semestre', 'Volumen']
                    conteo_semestres['Etiqueta_Semestre'] = "Semestre " + conteo_semestres['Semestre'].astype(str)
                    
                    esquema_color = 'Greens' if 'Buen' in estado else ('Reds' if 'Crítico' in estado else 'Oranges')
                    fig_tree = px.treemap(
                        conteo_semestres, path=['Etiqueta_Semestre'], values='Volumen',
                        color='Volumen', color_continuous_scale=esquema_color
                    )
                    fig_tree.update_traces(textinfo="label+value", textfont=dict(size=18, color="white"))
                    fig_tree.update_layout(title="Distribución por Semestre", margin=dict(t=30, l=10, r=10, b=10), height=350)
                    st.plotly_chart(fig_tree, use_container_width=True)

                # Gráfica 4: Boxplot Sistema Escolar vs Promedio (Del Jupyter Original)
                with col_box:
                    try:
                        # Convertimos las variables sintéticas o reales para que el boxplot funcione bien
                        df_filtrado_box = df_filtrado.copy()
                        if 'Sistema_Escolar' in df_filtrado_box.columns and 'Promedio_General' in df_filtrado_box.columns:
                            # Mapeamos 0/1 a texto legible
                            df_filtrado_box['Sistema'] = df_filtrado_box['Sistema_Escolar'].map({0.0: 'Escolarizado', 1.0: 'Semiescolarizado', 0: 'Escolarizado', 1: 'Semiescolarizado'}).fillna('General')
                            fig_box = px.box(
                                df_filtrado_box, x="Sistema", y="Promedio_General", color="Sistema",
                                title="Promedio General vs Sistema Escolar",
                                color_discrete_sequence=px.colors.qualitative.Pastel
                            )
                            fig_box.update_layout(showlegend=False, margin=dict(t=40, l=10, r=10, b=10), height=350)
                            st.plotly_chart(fig_box, use_container_width=True)
                        else:
                            st.info("Variables de Promedio y Sistema Escolar no disponibles en este grupo.")
                    except:
                        pass
                        
                # Gráfica 5: Calidad de Internet (Del Jupyter Original, extraída de df_crudo para análisis general del grupo)
                if df_crudo is not None and 'Calidad_Internet' in df_crudo.columns:
                    st.markdown("#### 📶 Infraestructura: Calidad de Internet en el grupo seleccionado")
                    # Filtramos en el dataset crudo basado en los alumnos seleccionados
                    matriculas_seleccionadas = df_filtrado['Matrícula'].tolist()
                    df_crudo_filtrado = df_crudo[df_crudo['Matrícula'].isin(matriculas_seleccionadas)]
                    if not df_crudo_filtrado.empty:
                        fig_bar = px.histogram(
                            df_crudo_filtrado, x="Calidad_Internet", nbins=5,
                            title="Distribución de Calidad de Conexión a Internet (1 a 5)",
                            color_discrete_sequence=['#3498db']
                        )
                        fig_bar.update_layout(yaxis_title="Cantidad de Alumnos", margin=dict(t=40, l=10, r=10, b=10), height=300)
                        st.plotly_chart(fig_bar, use_container_width=True)
                
                st.write("---")
                st.markdown("#### ⚙️ Aislar Causales por Semestre Específico:")
                c_sel, c_btn = st.columns([3, 1])
                with c_sel:
                    sem_opciones = sorted(df_filtrado['Semestre'].unique())
                    sem_seleccionado = st.selectbox("Selecciona el semestre a investigar a profundidad:", sem_opciones)
                with c_btn:
                    st.write("<br>", unsafe_allow_html=True)
                    if st.button("🔍 Extraer Causas (Siguiente Nivel)", type="primary", use_container_width=True):
                        st.session_state.dash_semestre = sem_seleccionado
                        st.session_state.dash_nivel = 3
                        st.rerun()

        # ------------------------------------------
        # NIVEL 3: VARIABLES DE IMPACTO (Lollipop, Radar, Scatter)
        # ------------------------------------------
        elif st.session_state.dash_nivel == 3:
            if st.button("⬅️ Regresar a Desglose de Semestres", type="secondary"):
                st.session_state.dash_nivel = 2
                st.session_state.dash_semestre = None
                st.rerun()
                
            estado = st.session_state.dash_estado_acad
            semestre = st.session_state.dash_semestre
            
            st.markdown(f"### 🎯 Análisis Causal de Fallos y Fortalezas - Semestre {semestre} ({estado})")
            
            df_sem = df[(df['Estado_Dashboard'] == estado) & (df['Semestre'] == semestre)]
            
            col_izq, col_der = st.columns([1.2, 1])

            if 'Riesgo' in estado or 'Crítico' in estado:
                # Gráfica 6: Lollipop (Factores Específicos Extraídos)
                with col_izq:
                    st.markdown("#### 📉 Factores Críticos (Frecuencia)")
                    vars_criticas = []
                    for factores in df_sem['Factores Críticos']:
                        for p in str(factores).split(" | "):
                            nombre = p.split(" (")[0]
                            if nombre and nombre.lower() != 'nan' and 'buen' not in nombre.lower():
                                vars_criticas.append(nombre)
                                
                    if vars_criticas:
                        conteo_vars = pd.Series(vars_criticas).value_counts().reset_index()
                        conteo_vars.columns = ['Variable', 'Incidencias']
                        
                        fig_lol = go.Figure()
                        fig_lol.add_trace(go.Scatter(
                            x=conteo_vars['Incidencias'], y=conteo_vars['Variable'],
                            mode='markers+text',
                            text=conteo_vars['Incidencias'], textposition="middle right",
                            marker=dict(color='#e74c3c', size=16),
                            name='Variables'
                        ))
                        for i in range(len(conteo_vars)):
                            fig_lol.add_shape(
                                type="line",
                                x0=0, x1=conteo_vars['Incidencias'].iloc[i] - 0.2,
                                y0=conteo_vars['Variable'].iloc[i], y1=conteo_vars['Variable'].iloc[i],
                                line=dict(color="#c0392b", width=3)
                            )
                        fig_lol.update_layout(
                            xaxis_title="Alumnos Afectados", yaxis_title="",
                            template="plotly_white", yaxis={'categoryorder':'total ascending'},
                            margin=dict(l=10, r=30, t=10, b=20), height=350
                        )
                        st.plotly_chart(fig_lol, use_container_width=True)
                    else:
                        st.info("No se hallaron factores específicos dominantes en este segmento.")
                        
                # Gráfica 7: Scatter Plot de Nivel de Estrés vs Asistencias (Del Jupyter Original)
                with col_der:
                    st.markdown("#### 🌪️ Relación: Estrés vs Asistencia")
                    if 'Nivel_Estres' in df_sem.columns and 'Asistencia_Clases' in df_sem.columns:
                        fig_scatter = px.scatter(
                            df_sem, x="Asistencia_Clases", y="Nivel_Estres",
                            size="Promedio_General" if 'Promedio_General' in df_sem.columns else None,
                            color="Promedio_General" if 'Promedio_General' in df_sem.columns else None,
                            hover_name="Nombre",
                            color_continuous_scale="Reds",
                            title="A mayor estrés, ¿menor asistencia?"
                        )
                        fig_scatter.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=350)
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        st.write("Faltan variables para este gráfico relacional.")
            
            else:
                # Gráfica 8: Radar Chart (Alumnos Estables)
                with col_izq:
                    st.markdown("#### 📈 Fortalezas Consistentes (Perfil Radar)")
                    categorias = ['Asistencias Constantes', 'Entrega de Tareas', 'Nivel de Motivación', 'Uso de Plataformas', 'Prácticas Realizadas']
                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=[5, 4.8, 4.2, 4.7, 4.5],
                        theta=categorias, fill='toself', fillcolor='rgba(46, 204, 113, 0.4)',
                        line=dict(color='#2ecc71', width=2), name='Fortalezas'
                    ))
                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                        showlegend=False, margin=dict(l=40, r=40, t=10, b=10), height=350
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
                    
                # Gráfica 9: Distribución Horas Estudio (Del Jupyter Original)
                with col_der:
                    st.markdown("#### 🕒 Horas de Estudio Semanal")
                    if 'Horas_Estudio' in df_sem.columns:
                        fig_bar2 = px.histogram(
                            df_sem, x="Horas_Estudio", nbins=6,
                            color_discrete_sequence=['#2ecc71']
                        )
                        fig_bar2.update_layout(yaxis_title="Cantidad de Alumnos", margin=dict(t=10, l=10, r=10, b=10), height=350)
                        st.plotly_chart(fig_bar2, use_container_width=True)
                    else:
                        st.info("✅ Los alumnos se mantienen estables principalmente por métricas sólidas.")

            st.write("---")
            if st.button("👥 Ver Expedientes y Lista Nominal de Alumnos (Nivel 4)", type="primary"):
                st.session_state.dash_nivel = 4
                st.rerun()

        # ------------------------------------------
        # NIVEL 4: DETALLE NOMINAL (Tabla Estilizada)
        # ------------------------------------------
        elif st.session_state.dash_nivel == 4:
            if st.button("⬅️ Regresar a Variables de Impacto", type="secondary"):
                st.session_state.dash_nivel = 3
                st.rerun()
                
            estado = st.session_state.dash_estado_acad
            semestre = st.session_state.dash_semestre
            
            st.markdown(f"### 📋 Detalle Nominal Específico")
            st.markdown(f"**Semestre:** {semestre} | **Estatus:** {estado}")
            
            df_final = df[(df['Estado_Dashboard'] == estado) & (df['Semestre'] == semestre)].copy()
            columnas_vista = ['Matrícula', 'Nombre', 'Docente Asignado', 'Prob. Exacta (%)', 'Factores Críticos']
            
            def estilizar_probabilidad(val):
                try:
                    num = float(str(val).replace('%', ''))
                    if num >= 70: return 'color: #e74c3c; font-weight: bold; background-color: #fdedec;'
                    if num >= 40: return 'color: #f39c12; font-weight: bold; background-color: #fef5e7;'
                    return 'color: #27ae60; background-color: #eafaf1;'
                except:
                    return ''

            if not df_final.empty:
                df_vista = df_final[columnas_vista].style.map(estilizar_probabilidad, subset=['Prob. Exacta (%)'])
                st.dataframe(df_vista, use_container_width=True, height=400)
                
                csv = df_final[columnas_vista].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar Lista a Excel/CSV",
                    data=csv,
                    file_name=f"Reporte_Alumnos_Sem{semestre}.csv",
                    mime='text/csv'
                )
            else:
                st.info("No hay registros nominales para este cruce específico.")

    # --- PANTALLA: ALUMNO ---
    def pantalla_alumno():
        col1, col2 = st.columns([2.2, 0.8])
        with col1:
            with st.container(border=True):
                st.markdown(f"<h1>👨‍🎓 Hola, {st.session_state['nombre']}</h1>", unsafe_allow_html=True)
                st.write("---")
                st.subheader("📋 Cuestionario de Hábitos y Contexto Estudiantil")
                
                with st.form("form_alumno"):
                    sexo = st.selectbox("Sexo", ["Hombre", "Mujer"], index=None, placeholder="Selecciona una opción...")
                    semestre = st.number_input("Semestre actual", min_value=1, max_value=12, value=None, placeholder="Ej. 1")
                    sistema = st.selectbox("Sistema Escolar", ["Escolarizado", "Semiescolarizado"], index=None, placeholder="Selecciona una opción...")
                    
                    horas_estudio = st.number_input("Horas de Estudio a la Semana", min_value=0, max_value=168, value=None, placeholder="Ej. 5")
                    dias_estudio = st.selectbox("Días de Estudio a la Semana", [0, 1, 2, 3, 4, 5, 6, 7], index=None, placeholder="Selecciona una opción...")
                    
                    motivacion = st.selectbox("Motivación (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    confianza = st.selectbox("Confianza en Aprobar (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    dificultad = st.selectbox("Dificultad (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    apoyo = st.selectbox("Apoyo Familiar (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    estres = st.selectbox("Estrés (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    
                    computadora = st.radio("¿Computadora Propia?", ["Sí", "No"], index=None)
                    internet = st.radio("¿Internet en Casa?", ["Sí", "No"], index=None)
                    calidad_internet = st.selectbox("Calidad de Internet (1 a 5)", [1, 2, 3, 4, 5], index=None, placeholder="Selecciona una opción...")
                    
                    if st.form_submit_button("Guardar Respuestas", type="primary", use_container_width=True):
                        if any(v is None for v in [sexo, semestre, sistema, horas_estudio, dias_estudio, motivacion, confianza, dificultad, apoyo, estres, computadora, internet, calidad_internet]):
                            st.error("❌ Todos los campos son obligatorios. Por favor, responde el cuestionario por completo antes de guardar.")
                        else:
                            try:
                                with get_db_connection() as conn:
                                    with conn.cursor() as c:
                                        consulta = '''REPLACE INTO respuestas_alumnos
                                                    (matricula, sexo, semestre, sistema, horas_estudio, dias_estudio, 
                                                    motivacion, confianza, dificultad, apoyo, estres, computadora, internet, calidad_internet)
                                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                                        c.execute(consulta, (st.session_state['usuario_actual'], sexo, semestre, sistema, horas_estudio, dias_estudio, 
                                                             motivacion, confianza, dificultad, apoyo, estres, computadora, internet, calidad_internet))
                                        conn.commit()
                                st.success("🎉 ¡Tus respuestas han sido guardadas con éxito!")
                            except mysql.connector.Error as err:
                                st.error(f"Error al guardar cuestionario: {err}")
        with col2:
            with st.container(border=True):
                st.markdown("### ℹ️ Información de tu Perfil")
                st.info(f"**Matrícula:**\n{st.session_state['usuario_actual']}")
                st.info(f"**Rol Asignado:**\nAlumno")
                st.write("---")
                st.write("Asegúrate de responder de manera honesta para que el algoritmo de IA pueda estimar tu estatus de riesgo con precisión.")

    # --- PANTALLA: DOCENTE / ADMINISTRATIVO ---
    def pantalla_docente():
        col1, col2 = st.columns([2.1, 0.9])
        lista_alumnos_pendientes = []
        lista_usuarios_crud = []
        dict_docentes = {"Ninguno": None}
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as c:
                    query_alumnos = """
                        SELECT u.matricula, u.nombre, 
                               (SELECT nombre FROM usuarios WHERE matricula = u.docente_id) as nombre_maestro,
                               ra.matricula as tiene_alumno, 
                               ed.matricula as tiene_docente
                        FROM usuarios u
                        LEFT JOIN respuestas_alumnos ra ON u.matricula = ra.matricula
                        LEFT JOIN evaluaciones_docentes ed ON u.matricula = ed.matricula
                        WHERE u.rol='alumno' AND (ra.matricula IS NULL OR ed.matricula IS NULL)
                    """
                    if st.session_state['rol_actual'] == 'docente':
                        query_alumnos += " AND u.docente_id=%s"
                        c.execute(query_alumnos, (st.session_state['usuario_actual'],))
                    else:
                        c.execute(query_alumnos)
                        
                    lista_alumnos_pendientes = c.fetchall()
                    
                    if 'admin' in st.session_state['rol_actual']:
                        c.execute("SELECT matricula, nombre, rol, correo, password, docente_id FROM usuarios")
                        lista_usuarios_crud = c.fetchall()
                        c.execute("SELECT matricula, nombre FROM usuarios WHERE rol='docente'")
                        for row in c.fetchall():
                            dict_docentes[f"{row[1]} ({row[0]})"] = row[0]
                    else:
                        c.execute("SELECT matricula, nombre, rol, correo, password, docente_id FROM usuarios WHERE rol='alumno' AND docente_id=%s", (st.session_state['usuario_actual'],))
                        lista_usuarios_crud = c.fetchall()
        except mysql.connector.Error as err:
            st.error(f"Error al cargar datos desde la base de datos: {err}")

        with col1:
            with st.container(border=True):
                st.markdown(f"<h1>👨‍🏫 Panel del Personal Académico</h1>", unsafe_allow_html=True)
                st.write("---")
                
                # Menú de Tabs
                opciones_tabs = ["👥 Gestión de Usuarios (CRUD)", "🚀 Ejecutar Diagnóstico", "📊 Dashboard Interactivo"]
                if st.session_state['rol_actual'] == 'docente':
                    opciones_tabs = ["📝 Carga la información del Alumno"] + opciones_tabs
                    
                cols_menu = st.columns(len(opciones_tabs))
                for idx, opcion in enumerate(opciones_tabs):
                    with cols_menu[idx]:
                        color_tipo = "primary" if st.session_state['tab_actual'] == opcion else "secondary"
                        if st.button(opcion, type=color_tipo, use_container_width=True, key=f"nav_{opcion}"):
                            st.session_state['tab_actual'] = opcion
                            st.rerun()
                            
                st.write("---")
                
                # --- VISTA: CARGA LA INFORMACIÓN DEL ALUMNO ---
                if st.session_state['tab_actual'] == "📝 Carga la información del Alumno" and st.session_state['rol_actual'] == 'docente':
                    st.subheader("Registro de Desempeño Académico")
                    with st.form("form_docente"):
                        matricula_ingresada = st.text_input("Matrícula del Alumno a Evaluar", value=st.session_state['alumno_seleccionado_evaluar']).strip()
                        
                        c_1, c_2, c_3 = st.columns(3)
                        with c_1: promedio = st.number_input("Promedio General", min_value=0.0, max_value=100.0, value=0.0)
                        with c_2: reprobadas = st.number_input("Materias Reprobadas", min_value=0, value=0)
                        with c_3: calif_ultima = st.number_input("Calificación Última Materia", min_value=0, max_value=100, value=0)
                        
                        asistencia_clases = st.slider("Asistencia (1-5)", 1, 5, 1)
                        cumplimiento = st.slider("Cumplimiento (1-5)", 1, 5, 1)
                        participacion = st.slider("Participación (1-5)", 1, 5, 1)
                        practicas = st.slider("Prácticas (1-5)", 1, 5, 1)
                        uso_plataformas = st.slider("Uso Plataformas (1-5)", 1, 5, 1)
                        
                        dias_asistencia = st.number_input("Días Totales Asistidos a la Semana", min_value=0, max_value=7, value=0)
                        
                        if st.form_submit_button("Actualizar Expediente Escolar", type="primary", use_container_width=True):
                            if not matricula_ingresada:
                                st.error("❌ Debes escribir una matrícula.")
                            else:
                                try:
                                    with get_db_connection() as conn:
                                        with conn.cursor() as c:
                                            c.execute("SELECT nombre, rol, docente_id FROM usuarios WHERE matricula = %s", (matricula_ingresada,))
                                            usuario_encontrado = c.fetchone()
                                            
                                            if not usuario_encontrado:
                                                st.error("❌ La matrícula no existe.")
                                            elif usuario_encontrado[2] != st.session_state['usuario_actual']:
                                                st.error("❌ Este alumno no está asignado bajo tu cargo.")
                                            else:
                                                consulta = '''REPLACE INTO evaluaciones_docentes
                                                            (matricula, promedio, reprobadas, calif_ultima, dias_asistencia, 
                                                            asistencia_clases, cumplimiento, participacion, practicas, uso_plataformas)
                                                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                                                c.execute(consulta, (matricula_ingresada, promedio, reprobadas, calif_ultima, dias_asistencia, 
                                                                     asistencia_clases, cumplimiento, participacion, practicas, uso_plataformas))
                                                conn.commit()
                                                st.success(f"🎉 ¡Expediente de {usuario_encontrado[0]} guardado!")
                                                st.session_state['alumno_seleccionado_evaluar'] = ""
                                                time.sleep(0.5)
                                                st.rerun()
                                except mysql.connector.Error as err:
                                    st.error(f"Error al guardar evaluación: {err}")

                # --- VISTA: GESTIÓN DE USUARIOS (CRUD) ---
                elif st.session_state['tab_actual'] == "👥 Gestión de Usuarios (CRUD)":
                    st.subheader("👥 Control y Gestión Institucional de Usuarios")
                    dict_usuarios_completo = {f"{row[1]} ({row[0]}) - [{row[2].upper()}]": row for row in lista_usuarios_crud}
                    
                    col_c1, col_c2, col_c3 = st.columns(3)
                    
                    with col_c1:
                        with st.expander("➕ Registrar Nuevo Usuario", expanded=False):
                            with st.form("form_alta_global"):
                                label_u = "Matrícula / Usuario" if 'admin' in st.session_state['rol_actual'] else "Matrícula del Alumno"
                                al_matricula = st.text_input(label_u).strip()
                                al_nombre = st.text_input("Nombre Completo")
                                al_correo = st.text_input("Correo Electrónico")
                                al_password = st.text_input("Contraseña por Defecto", value="Temporal123*")
                                
                                if 'admin' in st.session_state['rol_actual']:
                                    al_rol = st.selectbox("Asignar Rol", ["alumno", "docente", "administrative"])
                                    doc_asig = st.selectbox("Docente Tutor (Solo Alumnos)", list(dict_docentes.keys()))
                                    al_docente_id = dict_docentes[doc_asig]
                                else:
                                    al_rol = "alumno"
                                    al_docente_id = st.session_state['usuario_actual']
                                    
                                if st.form_submit_button("Guardar Usuario", type="primary", use_container_width=True):
                                    if not al_matricula or not al_nombre:
                                        st.error("❌ Matrícula y Nombre Obligatorios.")
                                    elif not validar_password_moodle(al_password):
                                        st.error("❌ La contraseña debe tener al menos 8 caracteres, 1 mayúscula, 1 minúscula, 1 número y 1 carácter especial.")
                                    else:
                                        try:
                                            password_hash = generar_md5(al_password)
                                            with get_db_connection() as conn:
                                                with conn.cursor() as c:
                                                    c.execute("INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) VALUES (%s, %s, %s, %s, %s, %s)",
                                                              (al_matricula, password_hash, al_rol, al_nombre, al_correo, al_docente_id))
                                                    conn.commit()
                                            st.success("🎉 Usuario dado de alta exitosamente.")
                                            time.sleep(0.5)
                                            st.rerun()
                                        except mysql.connector.Error as err:
                                            st.error(f"Error: {err}")

                    with col_c2:
                        with st.expander("📝 Editar Usuario Seleccionado", expanded=False):
                            if not dict_usuarios_completo:
                                st.write("No hay usuarios disponibles.")
                            else:
                                seleccionado_edit = st.selectbox("Buscar usuario a modificar:", list(dict_usuarios_completo.keys()), key="sel_crud_edit")
                                datos_originales = dict_usuarios_completo[seleccionado_edit]
                                
                                with st.form("form_edicion_global"):
                                    edit_nombre = st.text_input("Modificar Nombre Completo", value=datos_originales[1])
                                    edit_correo = st.text_input("Modificar Correo", value=datos_originales[3])
                                    edit_password = st.text_input("Modificar Contraseña (o dejar el Hash)", value=datos_originales[4])
                                    
                                    if 'admin' in st.session_state['rol_actual']:
                                        roles_disp = ["alumno", "docente", "administrative"]
                                        idx_r = roles_disp.index(datos_originales[2]) if datos_originales[2] in roles_disp else 0
                                        edit_rol = st.selectbox("Modificar Rol", roles_disp, index=idx_r)
                                        
                                        idx_d = 0
                                        keys_doc = list(dict_docentes.keys())
                                        for pos, k in enumerate(keys_doc):
                                            if dict_docentes[k] == datos_originales[5]:
                                                idx_d = pos
                                                break
                                        edit_doc_asig = st.selectbox("Modificar Docente Tutor", keys_doc, index=idx_d)
                                        edit_docente_id = dict_docentes[edit_doc_asig]
                                    else:
                                        edit_rol = "alumno"
                                        edit_docente_id = st.session_state['usuario_actual']
                                        
                                    if st.form_submit_button("Actualizar Cambios", type="primary", use_container_width=True):
                                        pwd_a_guardar = edit_password
                                        valido = True
                                        
                                        if edit_password != datos_originales[4]:
                                            if not validar_password_moodle(edit_password):
                                                st.error("❌ La nueva contraseña debe tener 8 caracteres, mayúscula, minúscula, número y especial.")
                                                valido = False
                                            else:
                                                pwd_a_guardar = generar_md5(edit_password)
                                                
                                        if valido:
                                            try:
                                                with get_db_connection() as conn:
                                                    with conn.cursor() as c:
                                                        c.execute("""UPDATE usuarios 
                                                                    SET nombre=%s, correo=%s, password=%s, rol=%s, docente_id=%s 
                                                                    WHERE matricula=%s""",
                                                                  (edit_nombre, edit_correo, pwd_a_guardar, edit_rol, edit_docente_id, datos_originales[0]))
                                                        conn.commit()
                                                st.success("🎉 Datos de usuario actualizados.")
                                                time.sleep(0.5)
                                                st.rerun()
                                            except mysql.connector.Error as err:
                                                st.error(f"Error al actualizar: {err}")

                    with col_c3:
                        with st.expander("🗑️ Eliminar Usuario", expanded=False):
                            if not dict_usuarios_completo:
                                st.write("No hay registros.")
                            else:
                                seleccionado_del = st.selectbox("Buscar usuario a remover:", list(dict_usuarios_completo.keys()), key="sel_crud_del")
                                datos_eliminar = dict_usuarios_completo[seleccionado_del]
                                
                                st.warning(f"¿Remover a {datos_eliminar[1]} ({datos_eliminar[0]})? Se eliminarán en cascada sus encuestas y calificaciones.")
                                with st.form("form_baja_global"):
                                    if st.form_submit_button("❌ Confirmar Eliminación Absoluta", type="primary", use_container_width=True):
                                        if datos_eliminar[0] == st.session_state['usuario_actual']:
                                            st.error("No es posible auto-eliminarse del sistema.")
                                        else:
                                            try:
                                                with get_db_connection() as conn:
                                                    with conn.cursor() as c:
                                                        c.execute("DELETE FROM usuarios WHERE matricula=%s", (datos_eliminar[0],))
                                                        conn.commit()
                                                st.success("🗑️ Registro revocado con éxito.")
                                                time.sleep(0.5)
                                                st.rerun()
                                            except mysql.connector.Error as err:
                                                st.error(f"Error al eliminar: {err}")
                                                
                    st.write("---")
                    
                    if lista_usuarios_crud:
                        df_crud_vista = pd.DataFrame(lista_usuarios_crud, columns=["Matrícula", "Nombre", "Rol", "Correo", "Contraseña", "ID Docente Asignado"])
                        
                        buffer_crud = io.BytesIO()
                        with pd.ExcelWriter(buffer_crud, engine='openpyxl') as writer:
                            df_crud_vista.to_excel(writer, index=False, sheet_name='Usuarios Registrados')
                            
                        col_tit_tabla, col_btn_tabla = st.columns([8.5, 1.5])
                        with col_tit_tabla:
                            st.write("### 📋 Vista General de la Tabla de Usuarios")
                        with col_btn_tabla:
                            st.download_button(
                                label="📥 Excel",
                                data=buffer_crud.getvalue(),
                                file_name=f"Vista_General_Usuarios_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                            
                        st.dataframe(df_crud_vista, use_container_width=True)
                    else:
                        st.write("### 📋 Vista General de la Tabla de Usuarios")
                        st.info("No existen usuarios registrados bajo este criterio.")

                # --- VISTA: EJECUTAR DIAGNÓSTICO ---
                elif st.session_state['tab_actual'] == "🚀 Ejecutar Diagnóstico":
                    mostrar_modulo_ia()

                # --- VISTA: DASHBOARD INTERACTIVO ---
                elif st.session_state['tab_actual'] == "📊 Dashboard Interactivo":
                    mostrar_dashboard_interactivo()

        with col2:
            with st.container(border=True):
                st.markdown("### 📋 Alumnos Pendientes")
                if lista_alumnos_pendientes:
                    for row in lista_alumnos_pendientes:
                        tiene_alumno = row[3] is not None
                        tiene_docente = row[4] is not None
                        
                        if not tiene_alumno and not tiene_docente:
                            msg_pendiente = "⏳ Pendiente: Alumno y Docente"
                            color_tag = "#ffb3b3"
                        elif not tiene_alumno:
                            msg_pendiente = "📝 Pendiente: Cuestionario Alumno"
                            color_tag = "#ffe6cc"
                        else:
                            msg_pendiente = "📊 Pendiente: Evaluación Docente"
                            color_tag = "#e6f2ff"
                            
                        if 'admin' in st.session_state['rol_actual']:
                            nombre_tutor = row[2] if row[2] else "Sin asignar"
                            st.markdown(f"""
                            <div style='padding:10px; border:1px solid #ddd; border-radius:5px; margin-bottom:8px; background-color:#fff;'>
                                <b>👤 Alumno:</b> {row[1]} (<small>{row[0]}</small>)<br>
                                <b>👨‍🏫 Docente:</b> {nombre_tutor}<br>
                                <span style='background-color:{color_tag}; padding:2px 6px; border-radius:4px; font-size:12px; font-weight:bold; display:inline-block; margin-top:4px;'>{msg_pendiente}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            if not tiene_docente:
                                if st.button(f"👤 {row[1]} ({row[0]})", key=f"btn_{row[0]}", use_container_width=True):
                                    st.session_state['alumno_seleccionado_evaluar'] = row[0]
                                    st.session_state['tab_actual'] = "📝 Carga la información del Alumno"
                                    st.rerun()
                            else:
                                st.markdown(f"<div style='padding:5px; text-align:center; font-weight:bold;'>👤 {row[1]} ({row[0]})</div>", unsafe_allow_html=True)
                            
                            st.markdown(f"<p style='text-align:center; background-color:{color_tag}; font-weight:bold; font-size:12px; margin-top:-6px; border-radius:4px;'>{msg_pendiente}</p>", unsafe_allow_html=True)
                else:
                    st.success("🎉 ¡No quedan alumnos pendientes en este periodo!")

    # --- RUTEO AUTOMÁTICO DE INTERFAZ SEGÚN EL ROL DE SESIÓN ---
    if st.session_state['rol_actual'] == 'alumno':
        pantalla_alumno()
    elif st.session_state['rol_actual'] == 'docente' or 'admin' in str(st.session_state['rol_actual']).lower():
        pantalla_docente()
