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
st.set_page_config(page_title="SIARR - ITS", page_icon="🎓", layout="wide")

# --- CSS PERSONALIZADO ---
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
}

.stButton>button {
    border-radius: 8px !important;
    font-weight: bold !important;
}

/* CSS para las Tarjetas del Dashboard */
.card {
    background-color: #f8f9fa;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
    border-top: 4px solid #1f77b4;
}
.card-title {
    color: #2c3e50;
    font-weight: bold;
    margin-bottom: 15px;
    text-align: center;
    font-size: 1.1rem;
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
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'df_db_prep' not in st.session_state:
    st.session_state['df_db_prep'] = None
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None
if 'df_crudo_entrenamiento' not in st.session_state:
    st.session_state['df_crudo_entrenamiento'] = None 
if 'variables_correlacionadas' not in st.session_state:
    st.session_state['variables_correlacionadas'] = {}

# Variables para el Dashboard Drill-Down
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

# --- FUNCIÓN DE CONEXIÓN A BASE DE DATOS (LOCAL) ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="base_datos_its"
    )

def init_db():
    try:
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
                        ('21050006', pwd_default, 'alumno', 'Maribel Mendoza Zendejas', 'maribel@gmail.com', 'profe_juan')
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
        st.error(f"Error de inicialización de Base de Datos: {err}")

init_db()

def colorear_filas(row):
    if row['Resultado IA'] == '⚠️ RIESGO':
        return ['background-color: #ffcccc; color: #900000'] * len(row)
    elif row['Resultado IA'] == '✅ ESTABLE':
        return ['background-color: #e6ffe6; color: #006600'] * len(row)
    return [''] * len(row)

# --- MÓDULO DE IA (ENTRENAMIENTO Y DIAGNÓSTICO) ---
def mostrar_modulo_ia():
    st.markdown("### 🧠 Inteligencia Artificial con Aprendizaje Profundo")
    st.write("Detección de riesgo de reprobación en asignaturas de programación mediante análisis de desempeño predictivo.")
    
    if 'administrative' in st.session_state['rol_actual'] or 'admin' in st.session_state['rol_actual']:
        st.markdown("#### 📂 Configuración del Dataset de Entrenamiento")
        col_da1, col_da2 = st.columns([2, 1])
        with col_da1:
            archivo_cargado = st.file_uploader("Agregar un nuevo dataset (.csv, .xlsx)", type=["csv", "xlsx"])
            if archivo_cargado is not None:
                try:
                    ext = ".xlsx" if archivo_cargado.name.endswith('.xlsx') else ".csv"
                    nombre_archivo_compartido = f"dataset_compartido_admin{ext}"
                    with open(nombre_archivo_compartido, "wb") as f:
                        f.write(archivo_cargado.getbuffer())
                    st.success(f"✅ Dataset guardado globalmente.")
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
        with col_da2:
            st.write("<br><br>", unsafe_allow_html=True)
            if st.button("🗑️ Borrar Dataset", type="secondary", use_container_width=True):
                if os.path.exists("dataset_compartido_admin.xlsx"): os.remove("dataset_compartido_admin.xlsx")
                if os.path.exists("dataset_compartido_admin.csv"): os.remove("dataset_compartido_admin.csv")
                st.session_state['analisis_completado'] = False
                st.rerun()

    if st.button("🚀 Iniciar Análisis de Red Neuronal", type="primary", use_container_width=True):
        consola_placeholder = st.empty()
        consola_placeholder.info("Buscando y cargando archivo de base de datos histórico...")
        
        try:
            # Control de aleatoriedad
            os.environ['PYTHONHASHSEED'] = '42'
            np.random.seed(42)
            random.seed(42)
            tf.random.set_seed(42)
            
            # Cargar archivo
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
                    st.error("❌ No se encontró ningún archivo de base de datos histórico.")
                    return

            st.session_state['df_crudo_entrenamiento'] = df.copy()

            # Preprocesamiento
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
            
            # Calcular e incrustar Feature Importance en sesión
            nombres_variables = X_train.columns
            correlaciones = X_train.corrwith(y_train).fillna(0).values
            st.session_state['variables_correlacionadas'] = dict(zip(nombres_variables, correlaciones))
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            
            # Construcción de la Red
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
            
            # Obtener datos de la Base de Datos para predecir
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
                st.warning("⚠️ No hay alumnos con expedientes completos.")
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
                
                # Guardamos exploratorio en sesión antes del reindex
                st.session_state['df_db_prep'] = df_db_prep.copy()
                
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
                        riesgo_predicho = "Alto"
                    elif prob_num >= 0.40:
                        nivel = "🟡 Medio"
                        estado = "⚠️ RIESGO"
                        riesgo_predicho = "Medio"
                    else:
                        nivel = "🟢 Bajo"
                        estado = "✅ ESTABLE"
                        riesgo_predicho = "Bajo"
                        
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
                        "Sistema_Escolar": fila.get('Sistema_Escolar_Num'),
                        "Nivel_Estres": fila.get('Nivel_Estres'),
                        "Promedio_General": fila.get('Promedio_General'),
                        "Asistencia_Clases": fila.get('Asistencia_Clases'),
                        "Horas_Estudio_Semana": fila.get('Horas_Estudio_Semana'), # Agregado para Scatter Plot
                        "Resultado IA": estado,
                        "Nivel de Riesgo": nivel,
                        "Riesgo_Predicho": riesgo_predicho, # Variable limpia para gráficos
                        "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                        "Factores Críticos": motivos_str
                    })
                    
                df_resultados = pd.DataFrame(resultados_custom)
                
                # Generar Reporte Excel
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_resultados.drop(columns=['Riesgo_Predicho']).to_excel(writer, index=False, sheet_name='Diagnóstico')
                    worksheet = writer.sheets['Diagnóstico']
                    fill_riesgo = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
                    fill_estable = PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid")
                    try:
                        idx_col_resultado = df_resultados.columns.get_loc("Resultado IA") + 1
                        for r_num in range(2, len(df_resultados) + 2):
                            cell_val = worksheet.cell(row=r_num, column=idx_col_resultado).value
                            current_fill = fill_riesgo if cell_val == "⚠️ RIESGO" else fill_estable if cell_val == "✅ ESTABLE" else None
                            if current_fill:
                                for c_num in range(1, len(df_resultados.columns)):
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
            label="📥 Descargar Reporte (Excel)",
            data=st.session_state['excel_data'],
            file_name=f"Reporte_IA_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# --- MÓDULO: DASHBOARD INTERACTIVO INNOVADOR ---
def mostrar_dashboard_interactivo():
    if not st.session_state.get('analisis_completado') or st.session_state.get('df_resultados') is None:
        st.warning("⚠️ Primero debes ejecutar el diagnóstico de IA en la pestaña '🚀 Ejecutar Diagnóstico' para visualizar el Dashboard.")
        return

    # NIVEL 1: TARJETAS Y GRÁFICAS PRINCIPALES
    if st.session_state.dash_nivel == 1:
        st.markdown("<h2 style='text-align: center; color: #2C3E50;'>📊 Panel de Inteligencia Académica Institucional</h2>", unsafe_allow_html=True)
        st.write("---")

        df_resultados = st.session_state['df_resultados'].copy()
        df_exploratorio = st.session_state['df_db_prep'].copy()

        # Fila 1: Tarjetas Métricas
        st.markdown("### 📌 Resumen Ejecutivo")
        c1, c2, c3, c4 = st.columns(4)
        
        total = len(df_resultados)
        critico = len(df_resultados[df_resultados['Riesgo_Predicho'] == 'Alto'])
        estable = len(df_resultados[(df_resultados['Riesgo_Predicho'] == 'Bajo') | (df_resultados['Riesgo_Predicho'] == 'Medio')])
        
        df_historico = st.session_state.get('df_crudo_entrenamiento')
        reprobados_reales = len(df_historico[df_historico['Resultado'] == 1]) if df_historico is not None and 'Resultado' in df_historico.columns else 0

        with c1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("👥 Total Alumnos Evaluados", total)
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("🔴 Alumnos Riesgo Alto", critico, f"{(critico/total*100) if total>0 else 0:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("🟢 Alumnos Estables", estable)
            st.markdown('</div>', unsafe_allow_html=True)
        with c4:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("🛑 Histórico Reprobados (BD)", reprobados_reales)
            st.markdown('</div>', unsafe_allow_html=True)

        # Fila 2: Gráficas de Impacto
        st.write("<br>", unsafe_allow_html=True)
        col_variables, col_pie_semestres = st.columns([1.5, 1])

        with col_variables:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">🚨 Factores Críticos de Riesgo (Feature Importance)</div>', unsafe_allow_html=True)
            
            if 'variables_correlacionadas' in st.session_state and st.session_state['variables_correlacionadas']:
                var_corr = st.session_state['variables_correlacionadas']
                df_importancia = pd.DataFrame(list(var_corr.items()), columns=['Variable', 'Correlación'])
                df_importancia['Variable'] = df_importancia['Variable'].str.replace('_', ' ')
                df_importancia['Abs_Correlación'] = df_importancia['Correlación'].abs()
                df_importancia = df_importancia.sort_values(by='Abs_Correlación', ascending=False).head(10)

                fig_variables = px.bar(
                    df_importancia, y='Variable', x='Correlación', orientation='h',
                    color='Correlación', color_continuous_scale='RdBu', text_auto='.2f',
                    labels={'Correlación': 'Impacto (+ Aprobación, - Reprobación)'}
                )
                fig_variables.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=20, b=20), height=380)
                fig_variables.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_variables, use_container_width=True)
            else:
                st.info("Variables no disponibles.")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_pie_semestres:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">✅ Estatus Actual Predicho</div>', unsafe_allow_html=True)
            
            fig_riesgo_pie = px.pie(
                df_resultados, names='Resultado IA', hole=0.45, color='Resultado IA',
                color_discrete_map={'⚠️ RIESGO': '#e74c3c', '✅ ESTABLE': '#2ecc71'}
            )
            fig_riesgo_pie.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#FFFFFF', width=2)))
            fig_riesgo_pie.update_layout(showlegend=False, margin=dict(l=20, r=20, t=10, b=10), height=180)
            st.plotly_chart(fig_riesgo_pie, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">📅 Distribución por Semestre</div>', unsafe_allow_html=True)
            
            if 'Semestre' in df_exploratorio.columns:
                fig_semestres = px.histogram(df_exploratorio, x='Semestre', color_discrete_sequence=['#34495E'], text_auto=True)
                fig_semestres.update_layout(xaxis_title="Semestre", yaxis_title="Alumnos", margin=dict(l=20, r=20, t=10, b=10), height=150)
                st.plotly_chart(fig_semestres, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Fila 3: Drill Down
        st.write("---")
        st.markdown("### 🔍 Explorar Población Específica (Drill-Down):")
        c1, c2, c3 = st.columns(3)
        if c1.button("🚨 Ver Críticos (Riesgo Alto)", use_container_width=True):
            st.session_state.dash_estado_acad = 'Alto'
            st.session_state.dash_nivel = 2
            st.rerun()
        if c2.button("⚠️ Ver Riesgo Medio", use_container_width=True):
            st.session_state.dash_estado_acad = 'Medio'
            st.session_state.dash_nivel = 2
            st.rerun()
        if c3.button("✅ Ver Buen Rendimiento", use_container_width=True):
            st.session_state.dash_estado_acad = 'Bajo'
            st.session_state.dash_nivel = 2
            st.rerun()

    # NIVEL 2: DRILL DOWN SCATTER PLOT Y TABLA
    elif st.session_state.dash_nivel == 2:
        st.markdown(f"<h2 style='text-align: center; color: #2C3E50;'>🔍 Segmentación Detallada: Riesgo {st.session_state.dash_estado_acad}</h2>", unsafe_allow_html=True)
        st.write("---")
        
        if st.button("⬅️ Volver al Panel Estratégico", type="secondary"):
            st.session_state.dash_nivel = 1
            st.session_state.dash_estado_acad = None
            st.rerun()
            
        df_filtrado = st.session_state['df_resultados'][st.session_state['df_resultados']['Riesgo_Predicho'] == st.session_state.dash_estado_acad]
        
        if df_filtrado.empty:
            st.info("No se encontraron alumnos en este segmento.")
        else:
            st.markdown(f"**Alumnos encontrados en este grupo:** {len(df_filtrado)}")
            
            # Gráfica 7: Scatter Plot de Rendimiento
            st.markdown("### 🎯 Análisis de Dispersión - Estudio vs. Rendimiento")
            
            if all(col in df_filtrado.columns for col in ['Horas_Estudio_Semana', 'Promedio_General', 'Nivel_Estres', 'Riesgo_Predicho']):
                fig7 = px.scatter(
                    df_filtrado,
                    x='Horas_Estudio_Semana',
                    y='Promedio_General',
                    color='Riesgo_Predicho',
                    size='Nivel_Estres',
                    hover_data=['Nombre'],
                    title="Horas de Estudio vs Promedio (Tamaño = Nivel de Estrés)",
                    color_discrete_map={'Alto': '#e74c3c', 'Medio': '#f39c12', 'Bajo': '#2ecc71'}
                )
                fig7.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig7, use_container_width=True)
                st.info("💡 **Guía:** Burbujas grandes indican mayor estrés. Monitorear alumnos con estrés alto y bajo promedio.")
            
            # Tabla 
            cols_mostrar = ['Matrícula', 'Nombre', 'Semestre', 'Promedio_General', 'Asistencia_Clases', 'Prob. Exacta (%)', 'Factores Críticos']
            st.dataframe(df_filtrado[cols_mostrar], use_container_width=True)

# =====================================================================
# --- CONTROL DE INTERFAZ Y FLUJO PRINCIPAL (ENRUTADOR COMPLETO) ---
# =====================================================================

if st.session_state['usuario_actual'] is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center;'>🎓 Acceso al Sistema (SIARR)</h1>", unsafe_allow_html=True)
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
                            st.error(f"Error en BD: {err}")
else:
    # --- MENÚ SUPERIOR DE USUARIO Y CIERRE DE SESIÓN ---
    col_usr, col_btn = st.columns([8, 2])
    with col_usr:
        st.markdown(f"👤 **Bienvenido:** {st.session_state['nombre']} | Rol: `{st.session_state['rol_actual'].upper()}`")
    with col_btn:
        if st.button("❌ Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state['usuario_actual'] = None
            st.session_state['rol_actual'] = None
            st.session_state['nombre'] = ""
            st.session_state['analisis_completado'] = False
            st.session_state['df_resultados'] = None
            st.session_state['df_db_prep'] = None
            st.session_state['dash_nivel'] = 1
            st.rerun()

    # --- BARRA LATERAL: NAVEGACIÓN BASADA EN ROLES ---
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
        st.info("Módulo reservado para la administración física, alta, baja y modificación de matrículas y docentes.")
    elif seleccion == "📝 Evaluar Alumnos":
        st.subheader("📝 Evaluación del Desempeño por el Docente")
        st.info("Módulo para que el Docente guarde los promedios, asistencias y escalas en 'evaluaciones_docentes'.")
    elif seleccion == "📝 Responder Cuestionario":
        st.subheader("📝 Cuestionario de Hábitos de Estudio (Alumno)")
        st.info("Módulo para que el estudiante conteste sus datos socioeconómicos y estresores en 'respuestas_alumnos'.")
