"""Aplicación de gestión de citas médicas (Streamlit).

Divide el acceso en dos zonas:

  * **Pública (pacientes)** — calendario mensual con código de color por
    ocupación; al pulsar un día se muestran los profesionales que atienden y
    SOLO sus huecos libres. No se ven los datos de otros pacientes.
  * **Clínica (personal)** — protegida por PIN. Permite ver y anular las
    citas de cualquier día, registrar citas telefónicas/manuales y configurar
    los médicos y sus horarios.

La navegación pública usa st.query_params: cada día es un enlace
`?y=...&m=...&dia=YYYY-MM-DD`. Así un clic dispara el rerun.
"""

from __future__ import annotations

import datetime as dt
import os

import streamlit as st

import core
import mailing
import services
import sms
import storage
import ui

st.set_page_config(page_title="Citas Médicas", page_icon=":material/event:",
                   layout="wide")

# PIN de acceso a la zona de la clínica. Configurable por variable de entorno.
CLINIC_PIN = os.environ.get("CLINIC_PIN", "clinic2026")

# Teléfonos de contacto de la clínica (se muestran al pedir cita por teléfono).
CLINIC_PHONES = ["910821180", "63536415"]

INSURANCE_OPTIONS = [
    "Privado (sin seguro)",
    "SANITAS",
    "ADESLAS",
    "DKV",
    "ASISA",
    "CASER",
    "AXA",
    "Otra compañía…",
]


@st.cache_resource
def get_repo(db_path: str):
    return storage.Repo(db_path)


repo = get_repo(str(storage.default_db_path()))
services.seed_medicos(repo)


# ---- Navegación ---------------------------------------------------------


def params_values() -> tuple[int, int, str | None]:
    q = st.query_params
    hoy = dt.date.today()
    try:
        y = int(q.get("y", hoy.year))
    except (TypeError, ValueError):
        y = hoy.year
    try:
        m = int(q.get("m", hoy.month))
    except (TypeError, ValueError):
        m = hoy.month
    y = max(2000, min(2100, y))
    m = max(1, min(12, m))
    dia = q.get("dia") or None
    return y, m, dia


def url_mes(y: int, m: int) -> str:
    return f"/?y={y}&m={m}"


def previo(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def siguiente(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


def pagina_publica() -> None:
    y, m, dia = params_values()
    # Si no hay día elegido mostramos la agenda de hoy en la columna derecha.
    dia_efectivo = dia or dt.date.today().isoformat()

    col_cal, col_agenda = st.columns([1, 1.9], gap="medium")

    with col_cal:
        py, pm = previo(y, m)
        ny, nm = siguiente(y, m)
        st.markdown(ui.build_nav_mes_html(y, m, url_mes(py, pm),
                                          url_mes(ny, nm)),
                    unsafe_allow_html=True)

        ocupacion = services.ocupacion_mes(y, m, repo)
        st.markdown(ui.build_calendar_html(y, m, url_mes(y, m), dia_efectivo,
                                           ocupacion, compact=True),
                    unsafe_allow_html=True)

        # Leyenda de colores
        c_a, c_b = st.columns(2)
        for i, level in enumerate((core.OCC_LOW, core.OCC_MID,
                                   core.OCC_HIGH, core.OCC_NONE)):
            (c_a if i % 2 == 0 else c_b).markdown(
                f"<span style='display:inline-block;width:.9em;height:.9em;"
                f"border-radius:3px;background:{core.COLORS[level]}'></span> "
                f"{core.OCC_LABELS[level]}", unsafe_allow_html=True)
        c_a.markdown(
            f"<span style='display:inline-block;width:.9em;height:.9em;"
            f"border-radius:3px;background:{core.PAST_COLOR}'></span> "
            f"{core.PAST_LABEL}", unsafe_allow_html=True)
        st.caption("Consulta solo los huecos libres. Tus datos y tu cita son "
                   "confidenciales.")

    with col_agenda:
        vista_publica_dia(dia_efectivo)

    gestion_mi_cita()


def _normaliza_telefono(valor: str) -> str:
    return "".join(ch for ch in (valor or "") if ch.isdigit())


def _contacto_coincide(cita, contacto: str) -> bool:
    contacto = (contacto or "").strip()
    if not contacto:
        return False
    if cita["email"] and cita["email"].strip().lower() == contacto.lower():
        return True
    if _normaliza_telefono(cita["telefono"]) and \
            _normaliza_telefono(cita["telefono"]) == _normaliza_telefono(contacto):
        return True
    return False


def gestion_mi_cita() -> None:
    """Sección pública: el paciente consulta y anula su propia cita."""
    st.markdown("---")
    col_tit, col_info = st.columns([2, 3])
    col_tit.subheader("Mi cita")
    col_info.caption("¿Ya tienes cita? Consulta sus datos y anúlala si no "
                     "puedes acudir.")

    with st.form("buscar_mi_cita"):
        c_a, c_b, c_boton = st.columns([2, 2, 1])
        codigo = c_a.text_input("Código de tu cita")
        contacto = c_b.text_input("Email o teléfono que usaste")
        buscar = c_boton.form_submit_button("Buscar", type="primary")

    if buscar:
        if not (codigo.strip() and contacto.strip()):
            st.error("Escribe el código y el email o teléfono de la cita.")
        else:
            cita = repo.get_cita_detalle(codigo.strip().upper())
            if cita and _contacto_coincide(cita, contacto):
                st.session_state["mi_cita_codigo"] = cita["codigo"]
                st.session_state.pop("mi_cita_error", None)
            else:
                st.session_state.pop("mi_cita_codigo", None)
                st.session_state["mi_cita_error"] = (
                    "No encontramos una cita con esos datos. Revisa el "
                    "código y el email o teléfono.")

    if st.session_state.get("mi_cita_error"):
        st.error(st.session_state["mi_cita_error"])

    codigo_activo = st.session_state.get("mi_cita_codigo")
    if codigo_activo:
        cita = repo.get_cita_detalle(codigo_activo)
        if cita is None:
            # La cita ya no existe (fue anulada en otra sesión)
            st.session_state.pop("mi_cita_codigo", None)
            st.info("Esa cita ya no está registrada.")
            return
        with st.container(border=True):
            st.markdown(
                f"**{fecha_nombre(cita)} · {cita['hora']} h**  \n"
                f"{servicio_medico(cita)}  \n"
                f"Paciente: {cita['nombre']} {cita['apellido1']} "
                f"{cita['apellido2']}  \n"
                f"Código: `{cita['codigo']}`")
            if st.button("Anular mi cita", type="primary",
                         key="anular_mi_cita"):
                st.session_state["mi_cita_confirmar"] = True
            if st.session_state.get("mi_cita_confirmar"):
                st.warning("¿Seguro que quieres anular esta cita? Esta acción "
                           "no se puede deshacer.")
                c_conf, c_cancel = st.columns(2)
                if c_conf.button("Sí, anularla", key="conf_anular"):
                    mailing.enviar_cancelacion(cita)
                    sms.enviar_cancelacion_sms(cita)
                    repo.cancelar_cita(cita["codigo"])
                    st.session_state.pop("mi_cita_codigo", None)
                    st.session_state.pop("mi_cita_confirmar", None)
                    st.success("Tu cita ha sido anulada. Enviaremos el aviso "
                               "a tu correo.")
                if c_cancel.button("No, conservarla", key="no_anular"):
                    st.session_state.pop("mi_cita_confirmar", None)


def fecha_nombre(cita) -> str:
    fecha = dt.date.fromisoformat(cita["fecha"])
    return (f"{fecha.strftime('%d/%m/%Y')} "
            f"({core.WEEKDAY_NAMES[fecha.weekday()]})")


def vista_publica_dia(iso: str) -> None:
    try:
        fecha = dt.date.fromisoformat(iso)
    except ValueError:
        st.error("Fecha no válida.")
        return

    st.markdown(
        f"## Agenda del **{fecha.strftime('%d/%m/%Y')}** "
        f"({core.WEEKDAY_NAMES[fecha.weekday()]})")

    if fecha < dt.date.today():
        st.info("Ese día ya ha pasado. No se pueden solicitar citas para "
                "fechas pasadas.")
        return

    activos = services.medicos_activos(fecha, repo)
    if not activos:
        st.warning("Ningún profesional atiende este día.")
        return

    opciones = {m["id"]: f"{m['nombre']} · {m['especialidad']}" for m in activos}
    ids = list(opciones.keys())
    q = st.query_params
    try:
        sel_q = int(q.get("mid"))
    except (TypeError, ValueError):
        sel_q = None
    sel = sel_q if sel_q in ids else ids[0]
    sel = st.radio("Selecciona el profesional", ids,
                   index=ids.index(sel),
                   format_func=lambda i: opciones[i])

    medico = repo.get_medico(sel)
    hora_actual = dt.datetime.now().time() if fecha == dt.date.today() else None
    libres = services.slots_disponibles(fecha, sel, repo, hora_actual)

    st.markdown(f"**Huecos libres de {opciones[sel]}**")

    if not libres:
        st.warning("No quedan huecos libres este día.")
    else:
        def url_slot(h):
            return (f"/?y={fecha.year}&m={fecha.month}&dia={iso}"
                    f"&mid={sel}&h={h}")
        st.markdown(ui.build_huecos_html(libres, url_slot),
                    unsafe_allow_html=True)

    hora_sel = q.get("h")
    if hora_sel in libres:
        form_cita(fecha, sel, opciones[sel], hora_sel)


def form_cita(fecha: dt.date, medico_id: int, etiqueta: str, hora: str) -> None:
    # Tipo de cita fuera del formulario: elegir Teléfono recalcula la página y
    # muestra los teléfonos de la clínica de forma destacada.
    tipo = st.segmented_control("Tipo de cita", ["Web", "Teléfono"],
                                default="Web", key=f"tipo_{medico_id}_{hora}")
    if tipo == "Teléfono":
        contactos = " &nbsp;&nbsp;·&nbsp;&nbsp; ".join(
            f"<span style='font-size:1.9rem;font-weight:700;color:#c2410c'>"
            f"{t}</span>" for t in CLINIC_PHONES)
        st.markdown(
            f"<div style='border:2px solid #f97316;background:#fff7ed;"
            f"border-radius:10px;padding:14px 18px;text-align:center;'>"
            f"<strong>Llámanos para confirmar tu cita</strong><br>{contactos}"
            f"</div>",
            unsafe_allow_html=True)

    with st.form(f"form_{medico_id}_{hora}"):
        st.subheader("Solicitar cita")
        st.caption(f"{etiqueta} · {fecha.strftime('%d/%m/%Y')} · {hora} h")

        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre")
        apellido1 = c2.text_input("Primer apellido")
        apellido2 = c3.text_input("Segundo apellido")
        c4, c5, c6 = st.columns(3)
        telefono = c4.text_input("Teléfono (9 dígitos)")
        email = c5.text_input("Email")
        seguro = c6.selectbox("Compañía de seguro", INSURANCE_OPTIONS)
        if seguro == "Otra compañía…":
            seguro = st.text_input("Nombre de la compañía")
        enviar = st.form_submit_button("Confirmar cita", type="primary")

    if enviar:
        er = core.validate_patient_data(nombre, apellido1, apellido2,
                                        telefono, email, seguro)
        if er:
            for e in er:
                st.error(e)
            return
        if hora not in services.slots_disponibles(fecha, medico_id, repo):
            st.error("Esa hora acaba de ser ocupada. Elige otra.")
            return
        tipo_db = "telefono" if tipo == "Teléfono" else "web"
        try:
            codigo = repo.add_cita(medico_id, fecha.isoformat(), hora,
                                   tipo_db, nombre.strip(), apellido1.strip(),
                                   apellido2.strip(), telefono.strip(),
                                   email.strip(), seguro.strip())
        except RuntimeError as ex:
            st.error(str(ex))
            return
        confirmar_cita_por_notificaciones(
            codigo, fecha, hora, medico_id, nombre, apellido1, apellido2,
            email, telefono)
        for k in ("h", "mid"):
            try:
                del st.query_params[k]
            except Exception:
                pass
        st.success(
            f"**Cita confirmada.**  \n"
            f"Código: `{codigo}`  \n"
            f"Fecha: {fecha.strftime('%d/%m/%Y')} "
            f"({core.WEEKDAY_NAMES[fecha.weekday()]})  \n"
            f"Hora: {hora} h  \n"
            f"Profesional: {etiqueta}")


# ===== Zona clínica (personal) ===========================================


def pagina_clinica() -> None:
    if not st.session_state.get("clinica_ok"):
        acceso_clinica()
        return

    st.sidebar.markdown("---")
    col1, col2 = st.columns(2)
    st.title("Zona de la clínica")
    st.caption("Acceso reservado al personal autorizado.")
    page = st.sidebar.radio("Panel", ["Citas del día", "Configuración"],
                            key="panel_clinica")
    if page == "Citas del día":
        panel_citas()
    else:
        pagina_configuracion()

    if st.sidebar.button("Salir de la zona"):
        st.session_state.pop("clinica_ok", None)
        st.rerun()


def acceso_clinica() -> None:
    st.title("Zona de la clínica")
    st.caption("Esta zona es privada y solo debe ser usada por el personal "
               "autorizado de la clínica.")
    pin = st.text_input("Código de acceso", type="password",
                        help="Pregunta a tu coordinador/a de la clínica.")
    if st.button("Entrar a la clínica", type="primary"):
        if pin.strip() == CLINIC_PIN:
            st.session_state["clinica_ok"] = True
            st.rerun()
        else:
            st.error("El código de acceso no es correcto.")


def panel_citas() -> None:
    st.markdown("### Agenda del día")
    medicos = {m["id"]: f"{m['nombre']} · {m['especialidad']}"
               for m in repo.get_medicos()}
    fecha = st.date_input("Fecha", dt.date.today(),
                          min_value=dt.date(2020, 1, 1))
    mid = st.selectbox("Agenda de", list(medicos.keys()),
                       format_func=lambda i: medicos[i],
                       key="agenda_mid")
    citas = [c for c in repo.get_citas_fecha(fecha.isoformat())
             if c["medico_id"] == mid]
    if not citas:
        st.info(f"No hay citas asignadas a **{medicos[mid]}** para ese día.")
    else:
        st.write(f"**{len(citas)} citas** de **{medicos[mid]}** el {fecha}")
        for c in citas:
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1.3, 2.4, 1.8, 1.4, 1.4, 1])
                c1.markdown(f"**{c['hora']}**")
                c2.markdown(f"**{c['nombre']} {c['apellido1']} {c['apellido2']}**"
                            f"  \n{servicio_medico(c)}")
                c3.markdown(f"· {c['tipo']}  \n{c['seguro']}")
                c4.markdown(f"📞 {c['telefono']}")
                c5.markdown(f"✉️ {c['email'] or '—'}")
                if c6.button("Anular", key=f"anula_{c['codigo']}"):
                    mailing.enviar_cancelacion(c)
                    sms.enviar_cancelacion_sms(c)
                    repo.cancelar_cita(c["codigo"])
                    st.rerun()

        # Impresión compacta y listado compatible con Excel.
        c_imp, c_exp = st.columns([1, 1])
        if c_imp.button("Imprimir agenda"):
            st.session_state["imprimir_agenda"] = not st.session_state.get(
                "imprimir_agenda", False)
        c_exp.download_button(
            "Descargar listado (Excel/CSV)",
            data=services.agenda_csv(citas),
            file_name=f"agenda_{fecha.isoformat()}.csv",
            mime="text/csv",
        )
        if st.session_state.get("imprimir_agenda"):
            st.markdown(f"### Agenda compacta de **{medicos[mid]}** el {fecha}")
            st.markdown(services.agenda_tabla_html(citas),
                        unsafe_allow_html=True)
            st.caption("Para imprimir usa tu navegador (Ctrl+P). Si prefieres "
                       "Excel, usa el botón 'Descargar listado'.")

    st.markdown("### Registrar cita manualmente (teléfono)")
    # Profesional, fecha y hora fuera del formulario: así la lista de huecos
    # se recalcula al cambiar de profesional o fecha (dentro de un st.form no
    # se dispara el rerun y la lista de horas quedaba obsoleta).
    medicos = {m["id"]: f"{m['nombre']} · {m['especialidad']}"
               for m in repo.get_medicos()}
    mid = st.selectbox("Profesional", list(medicos.keys()),
                       format_func=lambda i: medicos[i],
                       key="manual_mid")
    f2 = st.date_input("Fecha de la cita", value=dt.date.today(),
                       min_value=dt.date(2020, 1, 1), key="manual_fecha")
    libs = services.slots_disponibles(f2, mid, repo)
    if not libs:
        st.warning("No hay huecos libres para ese profesional esa fecha.")
    hora = st.selectbox("Hora", libs or ["No disponible"], key="manual_hora")

    with st.form("nueva_cita"):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre")
        a1 = c2.text_input("Primer apellido")
        a2 = c3.text_input("Segundo apellido")
        c4, c5, c6 = st.columns(3)
        tel = c4.text_input("Teléfono (9 dígitos)")
        email = c5.text_input("Email")
        seg = c6.selectbox("Seguro", INSURANCE_OPTIONS)
        if seg == "Otra compañía…":
            seg = st.text_input("Compañía")
        if st.form_submit_button("Registrar cita"):
            er = core.validate_patient_data(nombre, a1, a2, tel, email, seg)
            if er:
                for e in er:
                    st.error(e)
            elif hora == "No disponible":
                st.error("No hay hueco libre para esa fecha/profesional.")
            else:
                try:
                    cod = repo.add_cita(mid, f2.isoformat(), hora,
                                        "telefono", nombre.strip(),
                                        a1.strip(), a2.strip(), tel.strip(),
                                        email.strip(), seg.strip())
                    confirmar_cita_por_notificaciones(cod, f2, hora, mid,
                                                       nombre, a1, a2, email,
                                                       tel)
                    st.success(f"Cita registrada. Código {cod}.")
                except RuntimeError as ex:
                    st.error(str(ex))


def servicio_medico(c) -> str:
    return f"{c['medico_nombre']} ({c['medico_especialidad']})"


def confirmar_cita_por_notificaciones(codigo, fecha, hora, medico_id, nombre,
                                      apellido1, apellido2, email,
                                      telefono) -> None:
    """Envía la copia de la cita al solicitante por email y SMS."""
    if not email and not telefono:
        return
    med = repo.get_medico(medico_id)
    datos = {
        "codigo": codigo,
        "fecha": fecha.isoformat() if hasattr(fecha, "isoformat") else fecha,
        "hora": hora,
        "nombre": nombre,
        "apellido1": apellido1,
        "apellido2": apellido2,
        "email": email.strip() if email else "",
        "telefono": telefono.strip() if telefono else "",
        "medico_nombre": med["nombre"] if med else "",
        "medico_especialidad": med["especialidad"] if med else "",
    }
    mailing.enviar_confirmacion(datos)
    sms.enviar_confirmacion_sms(datos)


def pagina_configuracion() -> None:
    st.markdown("### Gestión de profesionales y agendas")
    st.caption("Alta y baja de profesionales, configuración de su intervalo "
               "entre citas y de los horarios de mañana y tarde.")
    form_nuevo_medico()
    st.markdown("---")
    for med in repo.get_medicos():
        with st.expander(f"{med['nombre']} — {med['especialidad']}"):
            form_medico(med)
            eliminar_medico(med)


def widget_horario_semanal(key_prefix, horarios) -> dict[int, list[list[int]]]:
    """Widgets de horario semanal. Devuelve {weekday: [[inicio, fin], ...]}."""
    por_dia: dict[int, list[list[int]]] = {}
    for wd in range(7):
        cols = st.columns([1.4, 1, 1, 1, 1])
        cols[0].markdown(f"**{core.WEEKDAY_NAMES[wd]}**")
        info = horarios.get(wd) or []
        v = info[0] if info else [0, 0]
        t = info[1] if len(info) > 1 else [0, 0]
        m_in = cols[1].time_input("Mañana", dt.time(v[0] // 60, v[0] % 60),
                                  key=f"mi_{key_prefix}_{wd}")
        m_fin = cols[2].time_input("Fin mañana",
                                   dt.time(v[1] // 60, v[1] % 60),
                                   key=f"mf_{key_prefix}_{wd}")
        t_in = cols[3].time_input("Tarde",
                                  dt.time(t[0] // 60, t[0] % 60)
                                  if t[0] else dt.time(0, 0),
                                  key=f"ti_{key_prefix}_{wd}")
        t_fin = cols[4].time_input("Fin tarde",
                                   dt.time(t[1] // 60, t[1] % 60)
                                   if t[1] else dt.time(0, 0),
                                   key=f"tf_{key_prefix}_{wd}")
        hor_dia: list[list[int]] = []
        mi = m_in.hour * 60 + m_in.minute
        mf = m_fin.hour * 60 + m_fin.minute
        if 0 < mi < mf:
            hor_dia.append([mi, mf])
        ti = t_in.hour * 60 + t_in.minute
        tf = t_fin.hour * 60 + t_fin.minute
        if 0 < ti < tf:
            hor_dia.append([ti, tf])
        por_dia[wd] = hor_dia
    return por_dia


def form_nuevo_medico() -> None:
    st.markdown("### Dar de alta a un nuevo profesional")
    with st.form("nuevo_medico"):
        c1, c2, c3 = st.columns([2, 2, 1])
        nombre = c1.text_input("Nombre completo")
        esp = c2.text_input("Especialidad", value="Medicina General")
        intervalo = c3.number_input("Minutos entre citas", min_value=5,
                                    max_value=120, value=20, step=5)
        st.markdown("**Horario semanal:** deja ambos en 00:00 los días que "
                    "no atiende.")
        por_dia = widget_horario_semanal("nuevo", {})
        alta = st.form_submit_button("Dar de alta", type="primary")
    if alta:
        if not nombre.strip():
            st.error("El nombre es obligatorio.")
            return
        mid = repo.add_medico(nombre.strip(), esp.strip() or "Medicina General",
                              int(intervalo))
        repo.set_horarios(mid, por_dia)
        st.success(f"Profesional dado de alta. Id {mid}.")
        st.rerun()


def eliminar_medico(med) -> None:
    st.markdown("---")
    clave = f"conf_del_{med['id']}"
    if st.session_state.get(clave):
        st.warning(f"¿Eliminar a **{med['nombre']}**? Se borrarán también "
                   "sus horarios y todas sus citas.")
        c_ok, c_no = st.columns(2)
        if c_ok.button("Sí, eliminar", key=f"ok_del_{med['id']}"):
            repo.delete_medico(med["id"])
            st.session_state.pop(clave, None)
            st.success("Profesional eliminado.")
            st.rerun()
        if c_no.button("Cancelar", key=f"no_del_{med['id']}"):
            st.session_state.pop(clave, None)
            st.rerun()
    else:
        if st.button("Eliminar profesional", key=f"del_{med['id']}"):
            st.session_state[clave] = True
            st.rerun()


def form_medico(med) -> None:
    with st.form(f"med_{med['id']}"):
        c1, c2, c3 = st.columns([2, 2, 1])
        nombre = c1.text_input("Nombre completo", med["nombre"])
        esp = c2.text_input("Especialidad", med["especialidad"])
        intervalo = c3.number_input("Minutos entre citas", min_value=5,
                                    max_value=120,
                                    value=med["intervalo_minutes"], step=5)

        st.markdown("**Horario semanal de mañana y tarde:** deja ambos en "
                    "00:00 los días que no atiende.")
        por_dia = widget_horario_semanal(med["id"],
                                         services.horarios_map(med["id"],
                                                              repo))
        guardado = st.form_submit_button("Guardar agenda")
    if guardado:
        repo.update_medico(med["id"], nombre.strip() or med["nombre"],
                           esp.strip(), int(intervalo))
        repo.set_horarios(med["id"], por_dia)
        st.success("Agenda guardada.")
        st.rerun()


# ---- Lanzador ---------------------------------------------------------------


def main() -> None:
    modo = st.sidebar.radio("Acceso", ["Público", "Zona clínica"])
    if modo == "Zona clínica":
        pagina_clinica()
    else:
        pagina_publica()


if __name__ == "__main__":
    main()