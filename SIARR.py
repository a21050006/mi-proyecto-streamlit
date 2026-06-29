import streamlit as st
import pandas as pd
import numpy as np
import time
import mysql.connector
import os
import traceback
import io 
import random 
import hashlib  # 🔒 Cifrado MD5
import re       # 🔒 Validación de políticas de contraseña
import plotly.express as px # 📊 Dashboard Dinámico

# Librerías de IA y Formato Excel
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import Callback
from openpyxl.styles import PatternFill

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR", page_icon=" 🎓 ", layout="wide")

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
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }
            h1 { font-size: 1.8rem !important; }
            h2 { font-size: 1.5rem !important; }
            h3 { font-size: 1.2rem !important; }
            .stButton>button {
                width: 100% !important;
                padding: 0.5rem !important;
            }
            .stDataFrame { overflow-x: auto; }
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

# --- ESTADO PARA MÓDULO DE IA Y DATASETS ---
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None

# --- 🔄 ESTADOS INTERACTIVOS PARA EL DRILL-DOWN DASHBOARD ---
if 'drill_paso' not in st.session_state:
    st.session_state['drill_paso'] = 'inicio'
if 'drill_estatus' not in st.session_state:
    st.session_state['drill_estatus'] = None
if 'drill_semestre' not in st.session_state:
    st.session_state['drill_semestre'] = None
if 'drill_variable' not in st.session_state:
    st.session_state['drill_variable'] = None

# --- 🔒 FUNCIONES DE SEGURIDAD (MD5 Y POLÍTICA MOODLE) ---
def hash_password(password):
    """Genera el hash MD5 de una contraseña en texto plano."""
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def validar_password_moodle(password):
    """Valida que la contraseña cumpla las políticas estrictas de Moodle."""
    if len(password) < 8:
        return False, "Debe tener al menos 8 caracteres de longitud."
    if not re.search(r"[a-z]", password):
        return False, "Debe incluir al menos una letra minúscula."
    if not re.search(r"[A-Z]", password):
        return False, "Debe incluir al menos una letra mayúscula."
    if not re.search(r"\d", password):
        return False, "Debe incluir al menos un número."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Debe incluir al menos un carácter no alfanumérico (ej. *, -, #, !, ó ?)."
    return True, ""

class StreamlitLogger(Callback):
    def __init__(self, placeholder):
        self.placeholder = placeholder
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        msg = f" 🧠  Entrenando Red Neuronal... Época {epoch+1}/20 | Precisión: {logs.get('accuracy', 0):.2%}"
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
                    pass_segura_hashed = hash_password("Moodle2026!")
                    usuarios_prueba = [
                        ('admin', pass_segura_hashed, 'administrative', 'Coordinación General', 'admin@itsperote.edu.mx', None),
                        ('profe_juan', pass_segura_hashed, 'docente', 'Ing. Juan Pérez', 'juan@itsperote.edu.mx', None),
                        ('21050002', pass_segura_hashed, 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan'),
                        ('21050003', pass_segura_hashed, 'alumno', 'Luz Rueda Tereso', 'rueda@gmail.com', 'profe_juan'),
                        ('21050009', pass_segura_hashed, 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan')
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
            st.markdown("<h1 style='text-align: center;'> 🎓  Acceso al Sistema</h1>", unsafe_allow_html=True)
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
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    pass_hashed = hash_password(password)
                                    c.execute("SELECT * FROM usuarios WHERE matricula=%s AND password=%s", (usuario, pass_hashed))
                                    resultado = c.fetchone()

                                    if resultado:
                                        st.session_state['usuario_actual'] = resultado[0]
                                        rol_bd = str(resultado[2]).lower()
                                        st.session_state['rol_actual'] = rol_bd
                                        st.session_state['nombre'] = resultado[3]

                                        if 'admin' in rol_bd or 'administrative' in rol_bd:
                                            st.session_state['tab_actual'] = " 👥  Gestión de Usuarios (CRUD)"
                                        else:
                                            st.session_state['tab_actual'] = " 📝  Carga la información del Alumno"

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
        if st.button(" ❌  Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state['usuario_actual'] = None
            st.session_state['rol_actual'] = None
            st.session_state['nombre'] = ""
            st.session_state['tab_actual'] = None
            st.session_state['df_resultados'] = None
            st.session_state['analisis_completado'] = False
            st.rerun()

    def colorear_filas(row):
        if row['Resultado IA'] == ' ⚠️  RIESGO':
            return ['background-color: #ffcccc; color: #900000'] * len(row)
        elif row['Resultado IA'] == ' ✅  ESTABLE':
            return ['background-color: #e6ffe6; color: #006600'] * len(row)
        return [''] * len(row)

    # --- MÓDULO DE IA Y DASHBOARD INTERACTIVO ---
    def mostrar_modulo_ia():
        st.markdown("###  🧠  Inteligencia Artificial con Aprendizaje Profundo")
        st.write("Detección de riesgo de reprobación en asignaturas de programación mediante análisis de desempeño predictivo.")

        if 'admin' in st.session_state['rol_actual'] or 'administrative' in st.session_state['rol_actual']:
            st.markdown("####  📂  Configuración del Dataset de Entrenamiento")
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

                        st.success(f" ✅  Dataset guardado globalmente en el servidor: {archivo_cargado.name}")
                    except Exception as e:
                        st.error(f"Error al escribir el archivo compartido: {e}")
            with col_da2:
                st.write("")
                st.write("")
                if st.button(" 🗑️  Borrar Dataset de Análisis", type="secondary", use_container_width=True):
                    if os.path.exists("dataset_compartido_admin.xlsx"): os.remove("dataset_compartido_admin.xlsx")
                    if os.path.exists("dataset_compartido_admin.csv"): os.remove("dataset_compartido_admin.csv")
                    st.session_state['analisis_completado'] = False
                    st.session_state['df_resultados'] = None
                    st.session_state['drill_paso'] = 'inicio'
                    st.warning("Dataset personalizado eliminado del servidor. Se usará el archivo local por defecto.")
                    time.sleep(0.5)
                    st.rerun()

        if os.path.exists("dataset_compartido_admin.xlsx") or os.path.exists("dataset_compartido_admin.csv"):
            st.info(" ℹ️  Actualmente utilizando el dataset personalizado cargado por el Administrador.")
        else:
            st.info(" ℹ️  Utilizando el dataset histórico predeterminado del sistema institucional.")

        if st.button(" 🚀  Iniciar Análisis de Red Neuronal", type="primary", use_container_width=True):
            consola_placeholder = st.empty()
            consola_placeholder.info("Buscando y cargando archivo de base de datos histórico...")

            st.session_state['drill_paso'] = 'inicio'

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
                        st.error(" ❌  Error: No se encontró ningún archivo de base de datos histórico en el servidor.")
                        return

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
                consola_placeholder.success(" ✅  Red neuronal entrenada con éxito.")

                query_completos = """
                SELECT u.matricula, u.nombre,
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
                    st.warning(" ⚠️  No hay alumnos con expedientes completos (deben responder el cuestionario y ser evaluados por el docente).")
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
                            nivel = " 🔴  Alto"
                            estado = " ⚠️  RIESGO"
                        elif prob_num >= 0.40:
                            nivel = " 🟡  Medio"
                            estado = " ⚠️  RIESGO"
                        else:
                            nivel = " 🟢  Bajo"
                            estado = " ✅  ESTABLE"

                        if estado == " ⚠️  RIESGO":
                            impacto_variables = X_custom_scaled[i] * correlaciones
                            impacto_dict = {nombres_variables[j]: impacto_variables[j] for j in range(len(nombres_variables))}
                            top_3 = sorted(impacto_dict.items(), key=lambda x: x[1], reverse=True)[:3]
                            motivos = [f"{str(var).replace('_', ' ')}" for var, imp in top_3]
                            motivos_str = " | ".join(motivos)
                        else:
                            motivos_str = "Buen rendimiento general"

                        resultados_custom.append({
                            "Matrícula": fila.get('Matrícula'),
                            "Nombre": fila.get('Nombre_completo'),
                            "Docente Asignado": fila.get('Docente_Tutor'),
                            "Semestre": int(fila.get('Semestre', 1)),
                            "Resultado IA": estado,
                            "Nivel de Riesgo": nivel,
                            "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                            "Factores Críticos": motivos_str
                        })

                    df_resultados = pd.DataFrame(resultados_custom)

                    buffer = io.BytesIO()
                    # 🛠️ Se movió la lógica OpenPyXL adentro del bloque contextual para evitar archivos corruptos
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
                                current_fill = fill_riesgo if cell_val == " ⚠️  RIESGO" else fill_estable if cell_val == " ✅  ESTABLE" else None
                                if current_fill:
                                    for c_num in range(1, len(df_resultados.columns) + 1):
                                        worksheet.cell(row=r_num, column=c_num).fill = current_fill
                        except:
                            pass

                    st.session_state['df_resultados'] = df_resultados
                    st.session_state['excel_data'] = buffer.getvalue()
                    st.session_state['analisis_completado'] = True
            except Exception as e:
                st.error(f" ❌  ERROR DETECTADO: {str(e)}")
                traceback.print_exc()
                st.session_state['analisis_completado'] = False

        # =========================================================================
        # INTERFAZ INTERACTIVA DRILL-DOWN (SÓLO SI EL ANÁLISIS YA SE COMPLETÓ)
        # =========================================================================
        if st.session_state['analisis_completado'] and st.session_state['df_resultados'] is not None:
            st.markdown("---")
            st.subheader("🔍 Dashboard de Profundización Diagnóstica")
            
            df_res = st.session_state['df_resultados']

            # 🗺️ Barra de Navegación del Dashboard (Breadcrumbs)
            ruta = "🏠 Global"
            if st.session_state['drill_paso'] != 'inicio':
                ruta += f" ➔ {st.session_state['drill_estatus']}"
            if st.session_state['drill_paso'] in ['variables', 'alumnos']:
                ruta += f" ➔ Semestre {st.session_state['drill_semestre']}"
            if st.session_state['drill_paso'] == 'alumnos':
                ruta += f" ➔ Causa: {st.session_state['drill_variable']}"
            
            st.info(f"**Ubicación actual:** {ruta}")

            if st.session_state['drill_paso'] != 'inicio':
                if st.button("🔄 Volver a la Vista Global", key="btn_reset_drill"):
                    st.session_state['drill_paso'] = 'inicio'
                    st.rerun()

            # --- NIVEL 1: VISTA GLOBAL (DONA INTERACTIVA) ---
            if st.session_state['drill_paso'] == 'inicio':
                st.markdown("#### Nivel 1: Balance General Institucional")
                conteo_global = df_res['Resultado IA'].value_counts().reset_index()
                conteo_global.columns = ['Estatus', 'Alumnos']

                fig_dona = px.pie(
                    conteo_global, names='Estatus', values='Alumnos', hole=0.45,
                    color='Estatus', color_discrete_map={' ✅  ESTABLE': '#2ecc71', ' ⚠️  RIESGO': '#ff5722'}
                )
                st.plotly_chart(fig_dona, use_container_width=True)

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("🚨 Inspeccionar Alumnos en Riesgo", use_container_width=True):
                        st.session_state['drill_estatus'] = ' ⚠️  RIESGO'
                        st.session_state['drill_paso'] = 'semestres'
                        st.rerun()
                with col_b2:
                    if st.button("✅ Analizar Alumnos Estables", use_container_width=True):
                        st.session_state['drill_estatus'] = ' ✅  ESTABLE'
                        st.session_state['drill_paso'] = 'semestres'
                        st.rerun()

            # --- NIVEL 2: FILTRADO POR SEMESTRES ---
            elif st.session_state['drill_paso'] == 'semestres':
                st.markdown(f"#### Nivel 2: Distribución de Estudiantes ({st.session_state['drill_estatus']}) por Semestre")
                df_lvl2 = df_res[df_res['Resultado IA'] == st.session_state['drill_estatus']]
                
                conteo_semestre = df_lvl2['Semestre'].value_counts().reset_index()
                conteo_semestre.columns = ['Semestre', 'Cantidad']
                conteo_semestre = conteo_semestre.sort_values(by='Semestre')
                conteo_semestre['Semestre'] = conteo_semestre['Semestre'].apply(lambda x: f"{x}° Semestre")

                fig_barras = px.bar(
                    conteo_semestre, x='Semestre', y='Cantidad', text='Cantidad',
                    color_discrete_sequence=['#ff7675' if 'RIESGO' in st.session_state['drill_estatus'] else '#55efc4']
                )
                st.plotly_chart(fig_barras, use_container_width=True)

                st.write("Selecciona el semestre que deseas auditar:")
                semestres_lista = sorted(df_lvl2['Semestre'].unique())
                semestre_elegido = st.selectbox("Semestre Académico:", semestres_lista, format_func=lambda x: f"{x}° Semestre")
                
                if st.button("🔍 Extraer Factores de Influencia"):
                    st.session_state['drill_semestre'] = semestre_elegido
                    st.session_state['drill_paso'] = 'variables'
                    st.rerun()

            # --- NIVEL 3: EXTRACCIÓN DE FACTORES CRÍTICOS DE LA IA ---
            elif st.session_state['drill_paso'] == 'variables':
                st.markdown(f"#### Nivel 3: Causas Críticas en {st.session_state['drill_semestre']}° Semestre ({st.session_state['drill_estatus']})")
                df_lvl3 = df_res[(df_res['Resultado IA'] == st.session_state['drill_estatus']) & (df_res['Semestre'] == st.session_state['drill_semestre'])]
                
                lista_causas = []
                for celda in df_lvl3['Factores Críticos'].dropna():
                    partes = celda.split('|')
                    for p in partes:
                        causa_limpia = p.strip().title()
                        if causa_limpia and "Buen Rendimiento" not in causa_limpia:
                            lista_causas.append(causa_limpia)

                if len(lista_causas) == 0:
                    st.success("✨ No existen factores críticos negativos acumulados para este subgrupo.")
                    lista_causas = ["Buen Rendimiento General"]
                
                df_causas_conteo = pd.Series(lista_causas).value_counts().reset_index()
                df_causas_conteo.columns = ['Factor Predictivo', 'Frecuencia (Alumnos)']

                fig_causas = px.bar(
                    df_causas_conteo, x='Frecuencia (Alumnos)', y='Factor Predictivo', orientation='h',
                    title="Frecuencia de Variables de Mayor Peso en la Red Neuronal",
                    color_discrete_sequence=['#fdcb6e']
                )
                st.plotly_chart(fig_causas, use_container_width=True)

                st.write("Elige un factor de riesgo para obtener el listado nominal de alumnos afectados:")
                variable_elegida = st.selectbox("Factor a Auditar:", df_causas_conteo['Factor Predictivo'].tolist())
                
                if st.button("📋 Desplegar Listado de Estudiantes"):
                    st.session_state['drill_variable'] = variable_elegida
                    st.session_state['drill_paso'] = 'alumnos'
                    st.rerun()

            # --- NIVEL 4: LISTADO NOMINAL FILTRADO CON REPORTES ---
            elif st.session_state['drill_paso'] == 'alumnos':
                st.markdown("#### Nivel 4: Reporte de Estudiantes Identificados")
                
                df_lvl4 = df_res[
                    (df_res['Resultado IA'] == st.session_state['drill_estatus']) & 
                    (df_res['Semestre'] == st.session_state['drill_semestre'])
                ]

                # 🛠️ Corrección de la línea truncada original
                if st.session_state['drill_variable'] != "Buen Rendimiento General":
                    df_final = df_lvl4[df_lvl4['Factores Críticos'].str.lower().str.contains(st.session_state['drill_variable'].lower())]
                else:
                    df_final = df_lvl4

                st.write(f"Alumnos en estado **{st.session_state['drill_estatus']}** ({st.session_state['drill_semestre']}° Semestre) debido al factor: **{st.session_state['drill_variable']}**")
                
                if df_final.empty:
                    st.info("No se encontraron alumnos que coincidan exactamente con este subfiltro.")
                else:
                    st.dataframe(df_final.style.apply(colorear_filas, axis=1), use_container_width=True)
                    
                    if st.session_state.get('excel_data') is not None:
                        st.download_button(
                            label="📥 Descargar Reporte Completo de Diagnóstico (Excel)",
                            data=st.session_state['excel_data'],
                            file_name="Reporte_Diagnostico_SIARR.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

    # =========================================================================
    # --- ENRUTADOR Y MENÚ DE PANTALLAS SEGÚN EL ROL DE USUARIO ---
    # =========================================================================
    rol = st.session_state['rol_actual']
    opciones_menu = []

    # Determinar qué opciones de menú tiene cada rol de forma segura
    if 'admin' in rol or 'administrative' in rol:
        opciones_menu = ["👥  Gestión de Usuarios (CRUD)", "🧠  Módulo de IA (Dashboard)"]
    elif rol == 'docente':
        opciones_menu = ["📝  Carga la información del Alumno", "🧠  Módulo de IA (Dashboard)"]
    elif rol == 'alumno':
        opciones_menu = ["📝  Responder Cuestionario"]

    # Validar o inicializar la pestaña por defecto
    if st.session_state['tab_actual'] not in opciones_menu and opciones_menu:
        st.session_state['tab_actual'] = opciones_menu[0]

    # Renderizar el control de navegación lateral
    st.sidebar.title("🧭 Navegación SIARR")
    tab_seleccionada = st.sidebar.radio(
        "Seleccione un módulo:", 
        opciones_menu, 
        index=opciones_menu.index(st.session_state['tab_actual']) if st.session_state['tab_actual'] in opciones_menu else 0
    )
    st.session_state['tab_actual'] = tab_seleccionada

    # Ejecutar la lógica de la pantalla activa
    if tab_seleccionada == "🧠  Módulo de IA (Dashboard)":
        mostrar_modulo_ia()
        
    elif tab_seleccionada == "👥  Gestión de Usuarios (CRUD)":
        st.markdown("### 👥  Gestión de Usuarios (CRUD)")
        st.write("Interfaz administrativa para la gestión de altas, bajas, consultas y modificaciones de usuarios (Alumnos, Docentes y Coordinadores).")
        st.info("💡 Aquí se incrusta el código de tus operaciones CRUD de la base de datos.")

    elif tab_seleccionada == "📝  Carga la información del Alumno":
        st.markdown("### 📝  Carga la información del Alumno")
        st.write("Panel para que los docentes registren y evalúen las métricas académicas correspondientes a los alumnos bajo su tutoría.")
        st.info("💡 Despliegue de alumnos asignados para evaluación continua.")

    elif tab_seleccionada == "📝  Responder Cuestionario":
        st.markdown("### 📝  Cuestionario de Bienestar e Historial de Estudio")
        st.write("Por favor responde con honestidad las preguntas del formulario socioeconómico y hábitos de estudio.")
        st.info("💡 Formulario del alumno para actualizar la tabla `respuestas_alumnos`.")
