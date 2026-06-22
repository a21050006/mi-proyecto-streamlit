import streamlit as st
import pandas as pd
import numpy as np
import time
import mysql.connector
import os
import traceback
import io  
import random 

# Librerías de IA
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import Callback

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR", page_icon="🎓", layout="wide")

# --- CSS PERSONALIZADO PARA PANTALLA COMPLETA ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
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

# --- ESTADO PARA MÓDULO DE IA Y DATASETS ---
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None
if 'dataset_personalizado' not in st.session_state:
    st.session_state['dataset_personalizado'] = None

class StreamlitLogger(Callback):
    def __init__(self, placeholder):
        self.placeholder = placeholder

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        msg = f"🧠 Entrenando Red Neuronal... Época {epoch+1}/20 | Precisión: {logs.get('accuracy', 0):.2%}"
        self.placeholder.info(msg)

# --- FUNCIÓN INTELIGENTE DE CONEXIÓN (NUBE / LOCAL) ---
def get_db_connection():
    # Si existen los Secrets en Streamlit Cloud, se conecta a Aiven de forma automática e invisible
    if "DB_HOST" in st.secrets:
        return mysql.connector.connect(
            host=st.secrets["DB_HOST"],
            port=int(st.secrets["DB_PORT"]),
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            database=st.secrets["DB_NAME"]
        )
    else:
        # Respaldo local por si estás programando en tu computadora
        return mysql.connector.connect(
            host="localhost", 
            user="root", 
            password="", 
            database="base_datos_its"
        )

def init_db():
    try:
        # Solo inicializa local si no estamos en Streamlit Cloud
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
                    usuarios_prueba = [
                        ('admin', '123', 'administrativo', 'Coordinación General', 'admin@itsperote.edu.mx', None),
                        ('profe_juan', '123', 'docente', 'Ing. Juan Pérez', 'juan@itsperote.edu.mx', None),
                        ('24050001', '123', 'alumno', 'María López', 'maria@itsperote.edu.mx', 'profe_juan')
                    ]
                    c.executemany('INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) VALUES (%s, %s, %s, %s, %s, %s)', usuarios_prueba)
                    conn.commit()
                    
                # CORREGIDO AQUÍ: Se cambió 'apoio' por 'apoyo'
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
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    c.execute("SELECT * FROM usuarios WHERE matricula=%s AND password=%s", (usuario, password))
                                    resultado = c.fetchone()
                            
                            if resultado:
                                st.session_state['usuario_actual'] = resultado[0] 
                                st.session_state['rol_actual'] = resultado[2]     
                                st.session_state['nombre'] = resultado[3]          
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
        
        st.markdown("#### 📂 Configuración del Dataset de Entrenamiento")
        col_da1, col_da2 = st.columns([2, 1])
        with col_da1:
            archivo_cargado = st.file_uploader("Agregar un nuevo dataset para el análisis (.csv, .xlsx)", type=["csv", "xlsx"])
            if archivo_cargado is not None:
                try:
                    if archivo_cargado.name.endswith('.csv'):
                        st.session_state['dataset_personalizado'] = pd.read_csv(archivo_cargado)
                    else:
                        st.session_state['dataset_personalizado'] = pd.read_excel(archivo_cargado)
                    st.success(f"✅ Nuevo dataset cargado con éxito: {archivo_cargado.name}")
                except Exception as e:
                    st.error(f"Error al leer el archivo: {e}")
        with col_da2:
            st.write("") 
            st.write("") 
            if st.button("🗑️ Borrar Dataset de Análisis", type="secondary", use_container_width=True):
                st.session_state['dataset_personalizado'] = None
                st.session_state['analisis_completado'] = False
                st.session_state['df_resultados'] = None
                st.warning("Dataset personalizado eliminado. Se usará el archivo local por defecto.")
                time.sleep(0.5)
                st.rerun()

        if st.session_state['dataset_personalizado'] is not None:
            st.info("ℹ️ Actualmente utilizando el dataset recién agregado por el usuario.")
        else:
            st.info("ℹ️ Utilizando el dataset histórico predeterminado del sistema.")

        if st.button("🚀 Iniciar Análisis de Red Neuronal", type="primary", use_container_width=True):
            consola_placeholder = st.empty()
            consola_placeholder.info("Buscando y cargando archivo de base de datos histórico...")
            
            try:
                os.environ['PYTHONHASHSEED'] = '42'
                np.random.seed(42)
                random.seed(42)
                tf.random.set_seed(42)
                
                if st.session_state['dataset_personalizado'] is not None:
                    df = st.session_state['dataset_personalizado'].copy()
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
                
                cols_ignorar = ['Matrícula', 'Matricula', 'matricula', 'Nombre', 'Nombre_completo', 'ID', 'Id']
                df = df.drop(columns=[c for c in cols_ignorar if c in df.columns], errors='ignore')
                
                df['Resultado'] = df['Resultado'].map({'Aprobado': 0, 'Reprobado': 1})
                df = df.dropna(subset=['Resultado'])

                if 'Sexo' in df.columns:
                    df['Sexo_Num'] = df['Sexo'].map({'Hombre': 0, 'Mujer': 1}).fillna(0)
                if 'Sistema_Escolar' in df.columns:
                    df['Sistema_Escolar_Num'] = df['Sistema_Escolar'].map({'Escolarizado': 0, 'Semiescolarizado': 1}).fillna(0)

                df_train, df_test = train_test_split(df, test_size=0.2, random_state=42)
                y_train = df_train['Resultado']

                X_train_bruto = df_train.drop(columns=['Resultado'])
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
                
                # CORREGIDO: Se cambió ra.apoio por ra.apoyo
                query_completos = """
                    SELECT 
                        u.matricula, u.nombre, ra.semestre, ra.sexo, ra.sistema,
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
                    st.warning("⚠️ No hay alumnos con expedientes completos (deben responder el cuestionario y ser evaluados por ti).")
                    st.session_state['analisis_completado'] = False
                else:
                    df_db_prep = pd.DataFrame()
                    df_db_prep['Matrícula'] = df_db['matricula']
                    df_db_prep['Nombre_completo'] = df_db['nombre']
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
                            
                        resultados_custom.append({
                            "Matrícula": fila.get('Matrícula'),
                            "Nombre": fila.get('Nombre_completo'),
                            "Semestre": fila.get('Semestre'),
                            "Resultado IA": estado,
                            "Nivel de Riesgo": nivel,
                            "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                            "Factores Críticos": motivos_str
                        })
                        
                    df_resultados = pd.DataFrame(resultados_custom)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_resultados.to_excel(writer, index=False, sheet_name='Diagnóstico')
                    
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
            df_estilado = st.session_state['df_resultados'].style.apply(colorear_filas, axis=1)
            st.dataframe(df_estilado, use_container_width=True)
            
            # CORREGIDO: Añadido el botón para descargar el Excel generado
            st.download_button(
                label="📥 Descargar Reporte de Diagnóstico (Excel)",
                data=st.session_state['excel_data'],
                file_name=f"Reporte_IA_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # --- PANTALLA: ALUMNO ---
    def pantalla_alumno():
        col1, col2 = st.columns([2.2, 0.8])
        
        with col1:
            with st.container(border=True):
                st.markdown(f"<h1>👨‍🎓 Hola, {st.session_state['nombre']}</h1>", unsafe_allow_html=True)
                st.write("---")
                st.subheader("📋 Cuestionario de Hábitos y Contexto Estudiantil")
                
                with st.form("form_alumno"):
                    sexo = st.selectbox("Sexo", ["Hombre", "Mujer"])
                    semestre = st.number_input("Semestre actual", min_value=1, max_value=12, value=1)
                    sistema = st.selectbox("Sistema Escolar", ["Escolarizado", "Semiescolarizado"])
                    horas_estudio = st.number_input("Horas de Estudio a la Semana", min_value=0, max_value=168, value=5)
                    dias_estudio = st.slider("Días de Estudio a la Semana", 0, 7, 3)
                    fields = [st.slider(f"{label} (1 a 5)", 1, 5, 3) for label in ["Motivación", "Confianza en Aprobar", "Dificultad", "Apoyo Familiar", "Estrés"]]
                    motivacion, confianza, dificultad, apoyo, estres = fields
                    computadora = st.radio("¿Computadora Propia?", ["Sí", "No"])
                    internet = st.radio("¿Internet en Casa?", ["Sí", "No"])
                    calidad_internet = st.slider("Calidad de Internet (1 a 5)", 1, 5, 3)
                    
                    if st.form_submit_button("Guardar Respuestas", type="primary", use_container_width=True):
                        try:
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    # CORREGIDO: Se cambió 'apoio' por 'apoyo' en las columnas
                                    consulta = '''REPLACE INTO respuestas_alumnos 
                                                 (matricula, sexo, semestre, sistema, horas_estudio, dias_estudio,
                                                 motivacion, confianza, dificultad, apoyo, estres, computadora, internet, calidad_internet)
                                                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                                    c.execute(consulta, (st.session_state['usuario_actual'], sexo, semestre, sistema, horas_estudio, dias_estudio,
                                               motivacion, confianza, dificultad, apoyo, estres, computadora, internet, calidad_internet))
                                    conn.commit()
                            st.success("🎉 ¡Tus respuestas han sido guardadas!")
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
        
        lista_alumnos = []
        try:
            with get_db_connection() as conn:
                with conn.cursor() as c:
                    query = """
                        SELECT u.matricula, u.nombre, 
                               CASE WHEN ed.matricula IS NOT NULL THEN 'EVALUADO' ELSE 'PENDIENTE' END as estado,
                               u.correo, u.password
                        FROM usuarios u
                        LEFT JOIN evaluaciones_docentes ed ON u.matricula = ed.matricula
                        WHERE u.rol='alumno'
                    """
                    if st.session_state['rol_actual'] == 'docente':
                        query += " AND u.docente_id=%s"
                        c.execute(query, (st.session_state['usuario_actual'],))
                    else:
                        c.execute(query)
                    lista_alumnos = c.fetchall()
        except mysql.connector.Error as err:
            st.error(f"Error al cargar alumnos: {err}")

        with col1:
            with st.container(border=True):
                st.markdown(f"<h1>👨‍🏫 Panel del Personal Académico</h1>", unsafe_allow_html=True)
                st.write("---")
                
                tab1, tab_crud, tab2 = st.tabs(["¼ Carga la información del Alumno", "👥 Gestión de Alumnos (CRUD)", "🚀 Ejecutar Diagnóstico"])
                
                with tab1:
                    st.subheader("Registro de Desempeño Académico")
                    with st.form("form_docente"):
                        matricula_ingresada = st.text_input("Matrícula del Alumno a Evaluar", value=st.session_state['alumno_seleccionado_evaluar']).strip()
                        
                        c_1, c_2, c_3 = st.columns(3)
                        with c_1: promedio = st.number_input("Promedio General", min_value=0.0, max_value=100.0, value=70.0)
                        with c_2: reprobadas = st.number_input("Materias Reprobadas", min_value=0, value=0)
                        with c_3: calif_ultima = st.number_input("Calificación Última Materia", min_value=0, max_value=100, value=70)
                            
                        asistencia_clases = st.slider("Asistencia (1-5)", 1, 5, 4)
                        cumplimiento = st.slider("Cumplimiento (1-5)", 1, 5, 4)
                        participacion = st.slider("Participación (1-5)", 1, 5, 3)
                        practicas = st.slider("Prácticas (1-5)", 1, 5, 3)
                        uso_plataformas = st.slider("Uso Plataformas (1-5)", 1, 5, 3)
                        
                        dias_asistencia = st.number_input("Días Totales Asistidos a la Semana", min_value=0, max_value=7, value=5)
                            
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
                                            elif st.session_state['rol_actual'] == 'docente' and usuario_encontrado[2] != st.session_state['usuario_actual']:
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

                with tab_crud:
                    st.subheader("👥 Control de Alumnos Asignados")
                    if lista_alumnos:
                        df_alumnos = pd.DataFrame([list(row[:4]) for row in lista_alumnos], columns=["Matrícula", "Nombre Completo", "Estado", "Correo"])
                        st.dataframe(df_alumnos, use_container_width=True)
                    else:
                        st.info("No hay alumnos asignados.")
                    
                    # CRUD: CREAR
                    with st.expander("➕ Registrar Nuevo Alumno"):
                        with st.form("form_alta_doc"):
                            al_nombre = st.text_input("Nombre Completo")
                            al_correo = st.text_input("Correo")
                            al_matricula = st.text_input("Matrícula")
                            al_password = st.text_input("Contraseña", value="123")
                            if st.form_submit_button("Guardar Alumno"):
                                try:
                                    with get_db_connection() as conn:
                                        with conn.cursor() as c:
                                            c.execute("INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) VALUES (%s, %s, 'alumno', %s, %s, %s)",
                                                      (al_matricula, al_password, al_nombre, al_correo, st.session_state['usuario_actual']))
                                            conn.commit()
                                    st.success("Alumno dado de alta.")
                                    time.sleep(0.5)
                                    st.rerun()
                                catch mysql.connector.Error as err:
                                    st.error(f"Error: {err}")
                    
                    # CRUD: EDITAR
                    with st.expander("📝 Editar Alumno Seleccionado"):
                        if not lista_alumnos:
                            st.write("No hay alumnos para editar.")
                        else:
                            dict_alumnos = {row[1]: row for row in lista_alumnos}
                            alumno_a_editar_nom = st.selectbox("Selecciona el alumno a modificar:", list(dict_alumnos.keys()))
                            datos_alumno = dict_alumnos[alumno_a_editar_nom]
                            
                            with st.form("form_editar_doc"):
                                edit_nombre = st.text_input("Modificar Nombre Completo", value=datos_alumno[1])
                                edit_correo = st.text_input("Modificar Correo", value=datos_alumno[3])
                                edit_password = st.text_input("Modificar Contraseña", value=datos_alumno[4])
                                
                                if st.form_submit_button("💾 Guardar Cambios Realizados", type="primary"):
                                    try:
                                        with get_db_connection() as conn:
                                            with conn.cursor() as c:
                                                c.execute("""UPDATE usuarios 
                                                             SET nombre=%s, correo=%s, password=%s 
                                                             WHERE matricula=%s""",
                                                          (edit_nombre, edit_correo, edit_password, datos_alumno[0]))
                                                conn.commit()
                                        st.success(f"🎉 Datos de {edit_nombre} actualizados con éxito.")
                                        time.sleep(0.5)
                                        st.rerun()
                                    except mysql.connector.Error as err:
                                        st.error(f"Error al editar: {err}")

                    # CRUD: ELIMINAR
                    with st.expander("🗑️ Eliminar Alumno del Sistema"):
                        if not lista_alumnos:
                            st.write("No hay alumnos para eliminar.")
                        else:
                            dict_alumnos_del = {f"{row[1]} ({row[0]})": row[0] for row in lista_alumnos}
                            alumno_a_eliminar_sel = st.selectbox("Selecciona el alumno a dar de baja definitiva:", list(dict_alumnos_del.keys()))
                            matricula_a_eliminar = dict_alumnos_del[alumno_a_eliminar_sel]
                            
                            st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar completamente al alumno con matrícula {matricula_a_eliminar}?")
                            if st.button("🚨 Confirmar Eliminación Definitiva", type="primary", use_container_width=True):
                                try:
                                    with get_db_connection() as conn:
                                        with conn.cursor() as c:
                                            c.execute("DELETE FROM usuarios WHERE matricula=%s", (matricula_a_eliminar,))
                                            conn.commit()
                                    st.success("🚀 Alumno eliminado correctamente.")
                                    time.sleep(0.5)
                                    st.rerun()
                                except mysql.connector.Error as err:
                                    st.error(f"Error al eliminar: {err}")
                                            
                with tab2:
                    mostrar_modulo_ia()

        with col2:
            with st.container(border=True):
                st.markdown("### 📋 Lista de Alumnos")
                st.write("---")
                if not lista_alumnos:
                    st.info("Sin alumnos.")
                else:
                    for row in lista_alumnos:
                        color = "green" if row[2] == "EVALUADO" else "orange"
                        st.markdown(f"**{row[1]}** ({row[0]})  \nEstatus: :{color}[{row[2]}]")
                        st.write("---")

    # --- ENRUTADOR DE VISTAS POR ROL ---
    if st.session_state['rol_actual'] == 'alumno':
        pantalla_alumno()
    elif st.session_state['rol_actual'] in ['docente', 'administrativo']:
        pantalla_docente()
