import streamlit as st
import pandas as pd
import numpy as np
import mysql.connector
import os
import time
import io

# Desactivar logs innecesarios de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from sklearn.preprocessing import StandardScaler

# Configuración inicial de la página de Streamlit
st.set_page_config(
    page_title="Sistema SIARR - Inteligencia Artificial",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONEXIÓN INTELIGENTE A LA BASE DE DATOS
# ==========================================
def get_db_connection():
    """
    Detecta automáticamente si el entorno es local o la nube (JAWSDB / CLEARDB)
    y retorna un objeto de conexión activo.
    """
    # 1. Intentar detectar variables de entorno de la nube (Heroku / Clever Cloud, etc.)
    jawsdb_url = os.environ.get("JAWSDB_URL") or os.environ.get("CLEARDB_DATABASE_URL")
    
    if jawsdb_url:
        try:
            # Parsear URL de base de datos de producción
            from urllib.parse import urlparse
            url = urlparse(jawsdb_url)
            return mysql.connector.connect(
                host=url.hostname,
                user=url.username,
                password=url.password,
                database=url.path[1:],
                port=url.port or 3306
            )
        except Exception as e:
            st.error(f"Error de conexión a la base de datos en la nube: {e}")
    
    # 2. Configuración por defecto para el Entorno Local (XAMPP / Workbench)
    return mysql.connector.connect(
        host=st.secrets.get("DB_HOST", "localhost"),
        user=st.secrets.get("DB_USER", "root"),
        password=st.secrets.get("DB_PASSWORD", ""),
        database=st.secrets.get("DB_NAME", "siarr_db"),
        port=int(st.secrets.get("DB_PORT", 3306))
    )

# ==========================================
# INICIALIZACIÓN DEL ESTADO DE LA SESIÓN
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
if 'rol_actual' not in st.session_state:
    st.session_state['rol_actual'] = None
if 'matricula' not in st.session_state:
    st.session_state['matricula'] = None
if 'nombre' not in st.session_state:
    st.session_state['nombre'] = None
if 'analisis_completado' not in st.session_state:
    st.session_state['analisis_completado'] = False
if 'df_resultados' not in st.session_state:
    st.session_state['df_resultados'] = None
if 'dataset_personalizado' not in st.session_state:
    st.session_state['dataset_personalizado'] = None

# Lógica auxiliar para colorear el dataframe en la interfaz web
def colorear_filas(row):
    if "RIESGO" in str(row['Resultado IA']):
        return ['background-color: #FFCCCC; color: #900000; font-weight: bold;'] * len(row)
    elif "ESTABLE" in str(row['Resultado IA']):
        return ['background-color: #E6FFE6; color: #006600; font-weight: bold;'] * len(row)
    return [''] * len(row)

# ==========================================
# INTERFAZ DE LOGUEO / AUTENTICACIÓN
# ==========================================
if not st.session_state['autenticado']:
    st.title("🎓 Sistema SIARR")
    st.subheader("Predicción de Riesgo Académico mediante Inteligencia Artificial")
    
    col_log, _ = st.columns([1, 1])
    with col_log:
        st.markdown("### 🔐 Iniciar Sesión en el Portal")
        with st.form("form_login"):
            input_user = st.text_input("Matrícula o ID de Usuario").strip()
            input_pass = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
            
            if btn_login:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor(dictionary=True) as cursor:
                            query = "SELECT * FROM usuarios WHERE matricula = %s AND password = %s"
                            cursor.execute(query, (input_user, input_pass))
                            usuario = cursor.fetchone()
                            
                            if usuario:
                                st.session_state['autenticado'] = True
                                st.session_state['rol_actual'] = usuario['rol'].lower()
                                st.session_state['matricula'] = usuario['matricula']
                                st.session_state['nombre'] = usuario['nombre']
                                st.success(f"¡Bienvenido(a) {usuario['nombre']}!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("❌ Credenciales incorrectas. Verifique e intente de nuevo.")
                except Exception as e:
                    st.error(f"Error de base de datos durante el login: {e}")
    st.stop()

# ==========================================
# BARRA LATERAL (CERRAR SESIÓN)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
    st.markdown(f"**Usuario:** {st.session_state['nombre']}")
    st.markdown(f"**Rol:** `{st.session_state['rol_actual'].upper()}`")
    st.markdown("---")
    
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['autenticado'] = False
        st.session_state['rol_actual'] = None
        st.session_state['matricula'] = None
        st.session_state['nombre'] = None
        st.session_state['analisis_completado'] = False
        st.session_state['df_resultados'] = None
        st.rerun()

# ==========================================
# ROL: ALUMNO
# ==========================================
if st.session_state['rol_actual'] == 'alumno':
    st.title("👨‍🎓 Panel Estudiantil - SIARR")
    st.write(f"Hola **{st.session_state['nombre']}**, por favor responde de forma honesta el cuestionario contextual.")
    
    with st.form("form_respuestas_alumno"):
        st.markdown("### 📊 Cuestionario Socioemocional y Técnico")
        
        c1, c2 = st.columns(2)
        with c1:
            semestre = st.number_input("Semestre Actual", min_value=1, max_value=12, value=1)
            sexo = st.selectbox("Sexo", ["Hombre", "Mujer"])
            sistema = st.selectbox("Sistema Escolar", ["Escolarizado", "Semiescolarizado"])
            horas_estudio = st.number_input("Horas de estudio autónomo a la semana", min_value=0, max_value=50, value=5)
            dias_estudio = st.number_input("Días dedicados al estudio por semana", min_value=0, max_value=7, value=3)
        
        with c2:
            apoyo = st.selectbox("¿Cuenta con apoyo familiar para estudiar?", [5, 4, 3, 2, 1], format_func=lambda x: f"Nivel {x}")
            motivacion = st.selectbox("Nivel de motivación hacia la programación", [5, 4, 3, 2, 1])
            confianza = st.selectbox("Nivel de confianza en aprobar el ciclo", [5, 4, 3, 2, 1])
            dificultad = st.selectbox("Nivel de dificultad percibida en materias clave", [1, 2, 3, 4, 5])
            estres = st.selectbox("Nivel de estrés académico actual", [1, 2, 3, 4, 5])
            
        st.markdown("#### Destrezas Tecnológicas")
        cc1, cc2, cc3 = st.columns(3)
        with cc1: computadora = st.selectbox("¿Posee computadora propia?", ["Sí", "No"])
        with cc2: internet = st.selectbox("¿Tiene internet en su hogar?", ["Sí", "No"])
        with cc3: calidad_internet = st.selectbox("Calidad de conexión", [5, 4, 3, 2, 1], format_func=lambda x: f"Estrellas {x}")
        
        btn_enviar_alumno = st.form_submit_button("Guardar y Enviar Cuestionario", use_container_width=True)
        if btn_enviar_alumno:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        query = """
                            REPLACE INTO respuestas_alumnos (matricula, semestre, sexo, sistema, horas_estudio, 
                            dias_estudio, apoyo, motivacion, confianza, dificultad, estres, computadora, internet, calidad_internet)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(query, (st.session_state['matricula'], semestre, sexo, sistema, horas_estudio,
                                               dias_estudio, apoyo, motivacion, confianza, dificultad, estres, computadora, internet, calidad_internet))
                        conn.commit()
                st.success("🎉 Tus datos socioemocionales han sido guardados con éxito.")
            except Exception as e:
                st.error(f"Error al enviar el formulario técnico: {e}")

# ==========================================
# ROL: DOCENTE
# ==========================================
elif st.session_state['rol_actual'] == 'docente':
    st.title("👨‍🏫 Panel de Seguimiento Docente")
    st.write(f"Profesor(a): **{st.session_state['nombre']}**")
    
    # Filtrar solo alumnos asignados a este profesor
    try:
        with get_db_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT matricula, nombre FROM usuarios WHERE docente_id = %s AND rol = 'alumno'", (st.session_state['matricula'],))
                mis_alumnos = cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar alumnos: {e}")
        mis_alumnos = []
        
    if not mis_alumnos:
        st.warning("Usted no tiene alumnos asignados en la base de datos actualmente.")
    else:
        opciones_alumnos = {a['matricula']: f"{a['matricula']} - {a['nombre']}" for a in mis_alumnos}
        seleccion_alumno = st.selectbox("Seleccione el alumno a evaluar o actualizar desempeño:", opciones_alumnos.keys(), format_func=lambda x: opciones_alumnos[x])
        
        with st.form("form_evaluacion_docente"):
            st.markdown(f"### ✏️ Carga de Notas Académicas: {opciones_alumnos[seleccion_alumno]}")
            col1, col2 = st.columns(2)
            with col1:
                promedio = st.number_input("Promedio General (0.0 a 10.0)", min_value=0.0, max_value=10.0, step=0.1, value=8.0)
                reprobadas = st.number_input("Cantidad de materias actualmente reprobadas", min_value=0, max_value=10, value=0)
                calif_ultima = st.number_input("Calificación de la última materia troncal", min_value=0.0, max_value=10.0, step=0.1, value=8.0)
                dias_asistencia = st.number_input("Días asistidos en el mes parcial", min_value=0, max_value=31, value=20)
                asistencia_clases = st.selectbox("Porcentaje de asistencia general estimado", [5, 4, 3, 2, 1], format_func=lambda x: f"{x*20}% o similar")
            with col2:
                cumplimiento = st.selectbox("Nivel de cumplimiento de tareas", [5, 4, 3, 2, 1])
                participacion = st.selectbox("Participación activa en clase", [5, 4, 3, 2, 1])
                practicas = st.selectbox("Desempeño en prácticas de laboratorio/código", [5, 4, 3, 2, 1])
                uso_plataformas = st.selectbox("Frecuencia de interacción con plataformas educativas", [5, 4, 3, 2, 1])
                
            btn_guardar_nota = st.form_submit_button("Registrar Historial Académico", use_container_width=True)
            if btn_guardar_nota:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            query = """
                                REPLACE INTO evaluaciones_docentes (matricula, promedio, reprobadas, calif_ultima, 
                                dias_asistencia, asistencia_clases, cumplimiento, participacion, practicas, uso_plataformas)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            cursor.execute(query, (seleccion_alumno, promedio, reprobadas, calif_ultima,
                                                   dias_asistencia, asistencia_clases, cumplimiento, participacion, practicas, uso_plataformas))
                            conn.commit()
                    st.success("🎉 Datos académicos del alumno registrados correctamente en la base de datos.")
                except Exception as e:
                    st.error(f"Error al guardar evaluación: {e}")

# ==========================================
# ROL: ADMINISTRATIVO (CON TU CRUD SOLICITADO Y EXCEL CON COLOR)
# ==========================================
elif st.session_state['rol_actual'] == 'administrativo':
    st.title("🏛️ Panel de Administración General - SIARR")
    st.write(f"Bienvenido(a), **{st.session_state['nombre']}** (Coordinación Institucional)")
    
    # ==========================================
    # CRUD HORIZONTAL DE USUARIOS (PARTE SUPERIOR)
    # ==========================================
    st.markdown("### 🛠️ Gestión Global de Usuarios")
    
    col_crear, col_editar, col_eliminar = st.columns(3)
    
    # --- COLUMNA 1: REGISTRAR / CREAR ---
    with col_crear:
        st.markdown("**➕ Registrar Nuevo Usuario**")
        with st.form("form_crear_usuario", clear_on_submit=True):
            reg_matricula = st.text_input("Matrícula / ID", key="reg_mat").strip()
            reg_nombre = st.text_input("Nombre Completo", key="reg_nom")
            reg_correo = st.text_input("Correo Electrónico", key="reg_corr")
            reg_password = st.text_input("Contraseña", type="password", key="reg_pass")
            reg_rol = st.selectbox("Asignar Rol", ["alumno", "docente", "administrativo"], key="reg_rol")
            reg_docente = st.text_input("ID Docente Asignado (Solo Alumnos)", value="None", key="reg_doc").strip()
            
            btn_crear = st.form_submit_button("Guardar Usuario", use_container_width=True)
            if btn_crear:
                if reg_matricula and reg_nombre and reg_correo and reg_password:
                    docente_val = None if reg_docente.lower() == "none" or reg_docente == "" else reg_docente
                    try:
                        with get_db_connection() as conn:
                            with conn.cursor() as c:
                                query = """
                                    INSERT INTO usuarios (matricula, password, rol, nombre, correo, docente_id) 
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    ON DUPLICATE KEY UPDATE password=%s, rol=%s, nombre=%s, correo=%s, docente_id=%s
                                """
                                c.execute(query, (reg_matricula, reg_password, reg_rol, reg_nombre, reg_correo, docente_val,
                                                   reg_password, reg_rol, reg_nombre, reg_correo, docente_val))
                                conn.commit()
                        st.success(f"🎉 Usuario {reg_matricula} guardado correctamente.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
                else:
                    st.warning("⚠️ Llena los campos obligatorios.")

    # --- COLUMNA 2: EDITAR ---
    with col_editar:
        st.markdown("**✏️ Editar Usuario Existente**")
        try:
            with get_db_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT matricula FROM usuarios")
                    lista_usuarios = [r[0] for r in c.fetchall()]
        except:
            lista_usuarios = []
            
        edit_mat = st.selectbox("Selecciona Matrícula a Editar", [""] + lista_usuarios, key="edit_sel")
        
        if edit_mat:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(dictionary=True) as c:
                        c.execute("SELECT * FROM usuarios WHERE matricula = %s", (edit_mat,))
                        u_data = c.fetchone()
            except:
                u_data = None
                
            if u_data:
                with st.form("form_editar_usuario"):
                    edit_nom = st.text_input("Nombre", value=u_data['nombre'])
                    edit_corr = st.text_input("Correo", value=u_data['correo'])
                    edit_pass = st.text_input("Contraseña", value=u_data['password'])
                    roles_idx = ["alumno", "docente", "administrativo"]
                    default_idx = roles_idx.index(u_data['rol']) if u_data['rol'] in roles_idx else 0
                    edit_rol = st.selectbox("Cambiar Rol", roles_idx, index=default_idx)
                    edit_doc = st.text_input("ID Docente Asignado", value=str(u_data['docente_id']) if u_data['docente_id'] else "None")
                    
                    btn_editar = st.form_submit_button("Actualizar Cambios", use_container_width=True)
                    if btn_editar:
                        docente_val = None if edit_doc.lower() == "none" or edit_doc.strip() == "" else edit_doc
                        try:
                            with get_db_connection() as conn:
                                with conn.cursor() as c:
                                    query = """UPDATE usuarios SET nombre=%s, correo=%s, password=%s, rol=%s, docente_id=%s WHERE matricula=%s"""
                                    c.execute(query, (edit_nom, edit_corr, edit_pass, edit_rol, docente_val, edit_mat))
                                    conn.commit()
                            st.success("🎉 Usuario modificado con éxito.")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

    # --- COLUMNA 3: ELIMINAR ---
    with col_eliminar:
        st.markdown("**🗑️ Eliminar Usuario**")
        with st.form("form_eliminar_usuario"):
            del_mat = st.selectbox("Selecciona Matrícula a Eliminar", [""] + lista_usuarios, key="del_sel")
            confirm_del = st.checkbox("Confirmo la eliminación definitiva.")
            
            btn_eliminar = st.form_submit_button("Eliminar Definitivamente", type="primary", use_container_width=True)
            if btn_eliminar:
                if del_mat and confirm_del:
                    try:
                        with get_db_connection() as conn:
                            with conn.cursor() as c:
                                c.execute("DELETE FROM usuarios WHERE matricula = %s", (del_mat,))
                                conn.commit()
                        st.success(f"🚀 Usuario {del_mat} eliminado.")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
                else:
                    st.warning("⚠️ Selecciona un usuario y confirma la casilla.")

    st.markdown("---")
    
    # ==========================================
    # VISUALIZACIÓN DE USUARIOS (ABAJO)
    # ==========================================
    st.markdown("### 📋 Vista General de Usuarios Registrados y sus Roles")
    try:
        with get_db_connection() as conn:
            query_usuarios = """
                SELECT u1.matricula AS 'Matrícula', u1.nombre AS 'Nombre Completo', 
                       u1.correo AS 'Correo', u1.rol AS 'Rol Asignado', 
                       COALESCE(u2.nombre, 'Sin Asignar/No Aplica') AS 'Docente Asignado'
                FROM usuarios u1
                LEFT JOIN usuarios u2 ON u1.docente_id = u2.matricula
            """
            df_usuarios = pd.read_sql(query_usuarios, conn)
        st.dataframe(df_usuarios, use_container_width=True)
    except Exception as e:
        st.error(f"Error al cargar la lista de usuarios: {e}")

    st.markdown("---")

    # ==========================================
    # EJECUCIÓN GLOBAL DE LA IA Y EXCEL CON COLOR
    # ==========================================
    st.markdown("### 🧠 Inteligencia Artificial: Diagnóstico Institucional Global")
    
    if st.button("🚀 Ejecutar Modelo IA sobre Toda la Matrícula", key="btn_ia_admin", use_container_width=True):
        consola_admin = st.empty()
        consola_admin.info("Cargando base de datos institucional completa y configurando Red Neuronal...")
        
        try:
            # Forzar reproducibilidad del entrenamiento de la IA
            os.environ['PYTHONHASHSEED'] = '42'
            np.random.seed(42)
            tf.random.set_seed(42)
            
            # Carga de dataset histórico de base para ajustar el transformador estadístico
            if st.session_state['dataset_personalizado'] is not None:
                df_base = st.session_state['dataset_personalizado'].copy()
            else:
                archivo_csv = 'dataset_final_sin_duplicados.xlsx - Sheet1.csv'
                archivo_excel = 'dataset_final_sin_duplicados.xlsx'
                df_base = pd.read_csv(archivo_csv) if os.path.exists(archivo_csv) else pd.read_excel(archivo_excel)
            
            cols_ignorar = ['Matrícula', 'Matricula', 'matricula', 'Nombre', 'Nombre_completo', 'ID', 'Id']
            df_base = df_base.drop(columns=[c for c in cols_ignorar if c in df_base.columns], errors='ignore')
            if 'Resultado' in df_base.columns:
                df_base['Resultado'] = df_base['Resultado'].map({'Aprobado': 0, 'Reprobado': 1})
            df_base = df_base.dropna(subset=['Resultado'])
            
            if 'Sexo' in df_base.columns: df_base['Sexo_Num'] = df_base['Sexo'].map({'Hombre': 0, 'Mujer': 1}).fillna(0)
            if 'Sistema_Escolar' in df_base.columns: df_base['Sistema_Escolar_Num'] = df_base['Sistema_Escolar'].map({'Escolarizado': 0, 'Semiescolarizado': 1}).fillna(0)
            
            X_train_bruto = df_base.drop(columns=['Resultado'], errors='ignore').select_dtypes(include=[np.number]).fillna(0)
            nombres_variables = X_train_bruto.columns
            correlaciones = X_train_bruto.corrwith(df_base['Resultado']).fillna(0).values
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train_bruto)
            
            # Red Neuronal Artificial en Keras
            model = Sequential([
                Input(shape=(X_train_scaled.shape[1],)),
                Dense(64, activation='relu'),
                Dropout(0.3),
                Dense(32, activation='relu'),
                Dense(1, activation='sigmoid')
            ])
            model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
            model.fit(X_train_scaled, df_base['Resultado'], epochs=15, shuffle=False, verbose=0)
            
            # CONSULTA GLOBAL - CONEXIÓN CON DOCENTE ASOCIADO MEDIANTE UN LEFT JOIN
            query_completos = """
                SELECT 
                    u.matricula, u.nombre, COALESCE(d.nombre, 'Sin Docente Asignado') as docente_nombre,
                    ra.semestre, ra.sexo, ra.sistema,
                    ed.promedio, ed.reprobadas, ed.calif_ultima, ed.dias_asistencia,
                    ed.asistencia_clases, ed.cumplimiento, ed.participacion, ed.practicas, ed.uso_plataformas,
                    ra.horas_estudio, ra.dias_estudio, ra.apoyo, ra.motivacion, ra.confianza, ra.dificultad, ra.estres,
                    ra.computadora, ra.internet, ra.calidad_internet
                FROM usuarios u
                INNER JOIN respuestas_alumnos ra ON u.matricula = ra.matricula
                INNER JOIN evaluaciones_docentes ed ON u.matricula = ed.matricula
                LEFT JOIN usuarios d ON u.docente_id = d.matricula
                WHERE u.rol = 'alumno'
            """
            
            with get_db_connection() as conn:
                df_db = pd.read_sql(query_completos, conn)
                
            if df_db.empty:
                st.warning("⚠️ No hay expedientes cruzados válidos (Cuestionario + Notas) para evaluar en este momento.")
            else:
                df_db_prep = pd.DataFrame()
                df_db_prep['Matrícula'] = df_db['matricula']
                df_db_prep['Nombre_completo'] = df_db['nombre']
                df_db_prep['Docente Asignado'] = df_db['docente_nombre']
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
                        nivel, estado = "🔴 Alto", "⚠️ RIESGO"
                    elif prob_num >= 0.40:
                        nivel, estado = "🟡 Medio", "⚠️ RIESGO"
                    else:
                        nivel, estado = "🟢 Bajo", "✅ ESTABLE"

                    if estado == "⚠️ RIESGO":
                        impacto_variables = X_custom_scaled[i] * correlaciones
                        impacto_dict = {nombres_variables[j]: impacto_variables[j] for j in range(len(nombres_variables))}
                        top_3 = sorted(impacto_dict.items(), key=lambda x: x[1], reverse=True)[:3]
                        motivos = [f"{str(var).replace('_', ' ')}" for var, imp in top_3]
                        motivos_str = " | ".join(motivos)
                    else:
                        motivos_str = "Buen rendimiento general"
                        
                    resultados_custom.append({
                        "Matrícula": fila['Matrícula'],
                        "Nombre": fila['Nombre_completo'],
                        "Docente Asignado": fila['Docente Asignado'],
                        "Semestre": fila['Semestre'],
                        "Resultado IA": estado,
                        "Nivel de Riesgo": nivel,
                        "Prob. Exacta (%)": f"{prob_num * 100:.2f}%",
                        "Factores Críticos": motivos_str
                    })
                    
                st.session_state['df_resultados'] = pd.DataFrame(resultados_custom)
                st.session_state['analisis_completado'] = True
                consola_admin.success("✅ Diagnóstico institucional completo finalizado con éxito.")
                
        except Exception as e:
            st.error(f"❌ Error crítico en procesamiento de IA: {e}")

    # --- PINTAR DIAGNÓSTICO EN PANTALLA Y EXPORTAR EXCEL FORMATEADO ---
    if st.session_state['analisis_completado'] and st.session_state['df_resultados'] is not None:
        df_res = st.session_state['df_resultados']
        
        st.subheader("📋 Diagnóstico de la Matrícula Completa")
        st.dataframe(df_res.style.apply(colorear_filas, axis=1), use_container_width=True)
        
        # INYECCIÓN DINÁMICA DE COLORES EN EL EXCEL REAL MEDIANTE OPENPYXL
        try:
            from openpyxl.styles import PatternFill, Font
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_res.to_excel(writer, index=False, sheet_name='Diagnostico_SIARR')
                
                workbook = writer.book
                worksheet = writer.sheets['Diagnostico_SIARR']
                
                # Definición de celdas con el mismo patrón de la interfaz web
                fill_riesgo = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
                font_riesgo = Font(color="900000", bold=True)
                
                fill_estable = PatternFill(start_color="E6FFE6", end_color="E6FFE6", fill_type="solid")
                font_estable = Font(color="006600", bold=True)
                
                # Buscamos el valor de la columna 'Resultado IA' (columna 5) para formatear la fila completa
                for row_idx in range(2, worksheet.max_row + 1):
                    val_resultado = worksheet.cell(row=row_idx, column=5).value
                    
                    if val_resultado == "⚠️ RIESGO":
                        for col_idx in range(1, worksheet.max_column + 1):
                            cell = worksheet.cell(row=row_idx, column=col_idx)
                            cell.fill = fill_riesgo
                            cell.font = font_riesgo
                    elif val_resultado == "✅ ESTABLE":
                        for col_idx in range(1, worksheet.max_column + 1):
                            cell = worksheet.cell(row=row_idx, column=col_idx)
                            cell.fill = fill_estable
                            cell.font = font_estable
            
            st.markdown("### 📊 Reportes de Canalización Académica")
            st.download_button(
                label="📥 Descargar Reporte Global con Estilos de Color (Excel)",
                data=buffer.getvalue(),
                file_name=f"Reporte_Institucional_IA_{time.strftime('%Y%m%d-%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.caption("Este archivo incluye el mapeo de docentes y el degradado de colores automatizado para agilizar tutorías.")
        except Exception as e:
            st.error(f"Error técnico al dar formato al archivo Excel: {e}")
