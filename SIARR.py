¿                                        st.error("❌ La contraseña debe tener al menos 8 caracteres, 1 mayúscula, 1 minúscula, 1 número y 1 carácter especial.")
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
                                        if str(datos_originales[0]).lower() == "admin":
                                            roles_disp = ["administrative"]
                                        idx_r = roles_disp.index(datos_originales[2]) if datos_originales[2] in roles_disp else 0
                                        edit_rol = st.selectbox("Modificar Rol", roles_disp, index=idx_r)
                                        
                                        if edit_rol == "alumno":
                                            idx_d = 0
                                            keys_doc = list(dict_docentes.keys())
                                            for pos, k in enumerate(keys_doc):
                                                if dict_docentes[k] == datos_originales[5]:
                                                    idx_d = pos
                                                    break
                                            edit_doc_asig = st.selectbox("Modificar Docente Tutor", keys_doc, index=idx_d)
                                            edit_docente_id = dict_docentes[edit_doc_asig]
                                        else:
                                            edit_docente_id = None
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
