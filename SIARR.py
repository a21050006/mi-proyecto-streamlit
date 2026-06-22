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

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SIARR", page_icon="🎓", layout="wide")

# --- CSS PERSONALIZADO (Limpio y Responsivo Nativo) ---
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
if 'tab_actual' not in st.session_state:
    st.session_state['tab_actual'] = None

# --- ESTADO PARA MÓDULO DE IA Y DATASETS ---
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None

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
                    usuarios_prueba = [
                        ('admin', '123', 'administrative', 'Coordinación General', 'admin@itsperote.edu.mx', None),
                        ('profe_juan', '123', 'docente', 'Ing. Juan Pérez', 'juan@itsperote.edu.mx', None),
                        ('21050002', '123', 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan'),
                        ('21050003', '123', 'alumno', 'Luz Rueda Tereso', 'rueda@gmail.com', 'profe_juan'),
                        ('21050009', '123', 'alumno', 'Miguel Angel Sanchez', 'angel@gmail.com', 'profe_juan')
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
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    c.execute("SELECT * FROM usuarios WHERE matricula=%s AND password=%s", (usuario, password))
                                    resultado = c.fetchone()
                            
                            if resultado:
                                st.session_state['usuario_actual'] = resultado[0] 
                                st.session_state['rol_actual'] = resultado[2] # Guarda 'administrative'
                                st.session_state['nombre'] = resultado[3]          
                                if resultado[2] == 'administrative':
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
        
        if st.session_state['rol_actual'] != 'docente':
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
                            
                        resultados_custom.append({
                            "Matrícula": fila.get('Matrícula'),
                            "Nombre": fila.get('Nombre_completo'),
                            "Docente Asignado": fila.get('Docente_Tutor'),
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
            df_estilado = st.session_state['df_resultados'].style.apply(colorear_filas, axis=1)
            st.dataframe(df_estilado, use_container_width=True)
            
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

                    if st.session_state['rol_actual'] == 'administrative':
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
                
                opciones_tabs = ["👥 Gestión de Usuarios (CRUD)", "🚀 Ejecutar Diagnóstico"]
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
                                try:
                                    pass
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
                                label_u = "Matrícula / Usuario" if st.session_state['rol_actual'] == 'administrative' else "Matrícula del Alumno"
                                al_matricula = st.text_input(label_u).strip()
                                al_nombre = st.text_input("Nombre Completo")
                                al_correo = st.text_input("Correo Electrónico")
                                al_password = st.text_input("Contraseña por Defecto", value="123")
                                
                                if st.session_state['rol_actual'] == 'administrative':
                                    al_rol = st.selectbox("Asignar Rol", ["alumno", "docente", "administrative"])
                                    doc_asig = st.selectbox("Docente Tutor (Solo Alumnos)", list(dict_docentes.keys()))
                                    al_docente_id = dict_docentes[doc_asig]
                                else:
                                    al_rol = "alumno"
                                    al_docente_id = st.session_state['usuario_actual']
                                    
                                if st.form_submit_button("Guardar Usuario", type="primary", use_container_width=True):
                                    if not al_matricula or not al_nombre:
                                        st.error("❌ Matrícula y Nombre Obligatorios.")
                                    else:
                                        try:
                                            with get_db_connection() as conn:
                                                with conn.cursor() as c:
                                                    c.execute("INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) VALUES (%s, %s, %s, %s, %s, %s)",
                                                              (al_matricula, al_password, al_rol, al_nombre, al_correo, al_docente_id))
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
                                    edit_password = st.text_input("Modificar Contraseña", value=datos_originales[4])
                                    
                                    if st.session_state['rol_actual'] == 'administrative':
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
                                        try:
                                            with get_db_connection() as conn:
                                                with conn.cursor() as c:
                                                    c.execute("""UPDATE usuarios 
                                                                 SET nombre=%s, correo=%s, password=%s, rol=%s, docente_id=%s 
                                                                 WHERE matricula=%s""",
                                                              (edit_nombre, edit_correo, edit_password, edit_rol, edit_docente_id, datos_originales[0]))
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

                        if st.session_state['rol_actual'] == 'administrative':
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
    elif st.session_state['rol_actual'] in ['docente', 'administrative']:
        pantalla_docente()
