"""Prueba de flujo completo de reserva con AppTest (Streamlit)."""

import pathlib

from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=120)


def _lunes_futuro():
    """Próximo lunes estrictamente futuro (la agenda pública bloquea el pasado)."""
    import datetime as _dt

    hoy = _dt.date.today()
    lunes = hoy + _dt.timedelta(days=(7 - hoy.weekday()) % 7)
    if lunes <= hoy:
        lunes += _dt.timedelta(days=7)
    return lunes.isoformat()


def _goto_dia(at, iso=None):
    import datetime as _dt

    fecha = _dt.date.fromisoformat(iso or _lunes_futuro())
    at.query_params["y"] = str(fecha.year)
    at.query_params["m"] = str(fecha.month)
    at.query_params["dia"] = fecha.isoformat()
    at.run()


def _primer_hueco(iso):
    """Primera hora libre del primer profesional activo para el día iso."""
    import datetime as _dt

    import services as sv
    from storage import Repo

    r = Repo()
    sv.seed_medicos(r)
    fecha = _dt.date.fromisoformat(iso)
    mid = sv.medicos_activos(fecha, r)[0]["id"]
    hora = sv.slots_disponibles(fecha, mid, r)[0]
    r.close()
    return hora


def _paso1(at, nombre="María", ap1="García", ap2="López",
           tel="612345678", email="maria@example.com"):
    """Rellena el paso 1 (datos) y pulsa Continuar."""
    at.text_input[0].set_value(nombre)
    at.text_input[1].set_value(ap1)
    at.text_input[2].set_value(ap2)
    at.text_input[3].set_value(tel)
    at.text_input[4].set_value(email)
    [b for b in at.button if b.label == "Continuar ›"][0].click()
    at.run()


def _elegir_hora_y_confirmar(at, iso=None):
    """En el paso 2: elige la primera hora libre y confirma la cita."""
    at.segmented_control[0].set_value(_primer_hueco(iso or _lunes_futuro()))
    at.run()
    [b for b in at.button if "Confirmar cita" in b.label][0].click()
    at.run()


def test_reserva_completa():
    import datetime as _dt

    at = _app()
    iso = _lunes_futuro()
    _goto_dia(at, iso)
    assert len(at.exception) == 0

    # Paso 1: el formulario de datos aparece
    labels = [t.label for t in at.text_input]
    assert "Nombre" in labels
    assert "Primer apellido" in labels
    assert "Segundo apellido" in labels
    assert "Teléfono (9 dígitos)" in labels
    assert "Email" in labels

    # Rellenamos los 5 campos y continuamos
    _paso1(at)
    assert len(at.exception) == 0, [e.message for e in at.exception]

    # Paso 2: se pide elegir doctor y hora
    mds = [m.value for m in at.markdown]
    assert any("Seleccione el doctor y la hora deseada" in m for m in mds), mds

    # Elegimos la primera hora libre y confirmamos
    _elegir_hora_y_confirmar(at, iso)
    assert len(at.exception) == 0, [e.message for e in at.exception]

    success = [x for x in at.success]
    assert success, "no hay mensaje de éxito"
    assert "Cita confirmada" in success[0].value
    # El mensaje debe mostrar el día y la hora, como en el correo.
    fecha_iso = _dt.date.fromisoformat(iso).strftime("%d/%m/%Y")
    assert f"Fecha: {fecha_iso}" in success[0].value
    assert "Hora: " in success[0].value


def test_validacion_nombre_vacio():
    at = _app()
    _goto_dia(at)
    [b for b in at.button if b.label == "Continuar ›"][0].click()
    at.run()
    errors = [e for e in at.error]
    assert len(errors) >= 2
    print("validación ok:", [e for e in errors])


def test_sin_dia():
    at = _app()
    at.run()
    assert len(at.exception) == 0
    # Sin día seleccionado se muestra la agenda de hoy junto al calendario.
    mds = [m.value for m in at.markdown]
    assert any("Agenda del" in m for m in mds), mds


def test_no_se_solicita_cita_en_fecha_pasada():
    # 2026-08-03 ya pasó: no debe ofrecer huecos, solo avisar.
    at = _app()
    _goto_dia(at, iso="2026-08-03")
    assert len(at.exception) == 0
    infos = [i.value for i in at.info]
    assert any("ya ha pasado" in i for i in infos), infos
    assert not at.segmented_control, \
        "no deben mostrarse huecos en una fecha pasada"


def test_huecos_sin_intervalo():
    at = _app()
    iso = _lunes_futuro()
    _goto_dia(at, iso)
    assert len(at.exception) == 0
    # Avanzamos al paso 2: ahí se ofrecen las horas libres.
    _paso1(at)
    assert len(at.exception) == 0
    labels = [s.label for s in at.segmented_control]
    assert "Horas libres" in labels, labels
    todo = " ".join([m.value for m in at.markdown] + labels).lower()
    assert "intervalo" not in todo, \
        "no debe mostrarse el comentario de intervalo"


def test_cita_por_telefono_muestra_telefonos():
    at = _app()
    _goto_dia(at)
    assert len(at.exception) == 0

    # Por defecto la cita es por Web: no se muestran los teléfonos.
    md = " ".join(m.value for m in at.markdown)
    assert "910821180" not in md
    assert "63536415" not in md

    # Al elegir "Teléfono" deben aparecer resaltados.
    at.segmented_control[0].set_value("Teléfono")
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    md = " ".join(m.value for m in at.markdown)
    assert "910821180" in md
    assert "63536415" in md


def test_pin_incorrecto():
    at = _app()
    at.run()
    at.sidebar.radio[0].set_value("Zona clínica")
    at.run()
    assert len(at.exception) == 0
    pin = [t for t in at.text_input if "Código de acceso" in t.label]
    assert pin, "debe pedir el código de acceso"
    pin[0].set_value("incorrecto")
    at.run()
    btn = [b for b in at.button if "Entrar a la clínica" in b.label][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0
    assert at.error, "debe mostrar error de PIN"
    assert "clinica_ok" not in at.session_state


def test_pagina_clinica():
    at = _app()
    at.run()
    at.sidebar.radio[0].set_value("Zona clínica")
    at.run()
    assert len(at.exception) == 0
    pin = [t for t in at.text_input if "Código de acceso" in t.label]
    pin[0].set_value("clinic2026")
    at.run()
    btn = [b for b in at.button if "Entrar a la clínica" in b.label][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0
    assert at.session_state["clinica_ok"]
    at.sidebar.radio[1].set_value("Configuración")
    at.run()
    assert len(at.exception) == 0
    assert len(at.expander) == 6  # seis médicos
    assert len(at.number_input) == 7  # 6 médicos + formulario de alta


def test_zona_publica_no_filtra_datos_pacientes():
    # Reservamos una cita con datos muy identificables.
    at = _app()
    iso = _lunes_futuro()
    _goto_dia(at, iso)
    _paso1(at, nombre="Confidencial", ap1="Paciente", ap2="Especial",
           tel="699000111", email="confidencial@example.com")
    _elegir_hora_y_confirmar(at, iso)
    assert len(at.exception) == 0
    assert [x for x in at.success], "no se registró la cita"

    # Una sesión nueva de visitante NO debe mostrar esos datos.
    visita = _app()
    _goto_dia(visita)
    assert len(visita.exception) == 0
    contenido = [t.value for t in visita.text_input]
    contenido += [b.label for b in visita.button]
    contenido += [m.value for m in visita.markdown]
    contenido += [i.value for i in visita.info]
    contenido += [w.value for w in visita.warning]
    blob = " ".join(str(x) for x in contenido)
    assert "Confidencial" not in blob
    assert "699000111" not in blob


def test_paciente_anula_su_cita():
    # Creamos una cita directamente con código conocido.
    import datetime as _dt
    from storage import Repo

    r = Repo()
    # aseguramos médicos
    import services as sv
    sv.seed_medicos(r)
    mid = r.get_medicos()[0]["id"]
    fecha = _dt.date(2026, 8, 17)  # lunes
    r.add_cita(mid, fecha.isoformat(), "09:00", "web",
               "Carmen", "Díaz", "Núñez", "622333444",
               "carmen@example.com", "PRIVADO")
    codigo = r.get_citas_fecha(fecha.isoformat())[0]["codigo"]
    r.close()

    at = _app()
    at.run()
    assert len(at.exception) == 0

    def inp(label):
        return [t for t in at.text_input if t.label == label][0]

    inp("Código de tu cita").set_value(codigo)
    inp("Email o teléfono que usaste").set_value("carmen@example.com")
    at.run()
    buscar = [b for b in at.button if b.label == "Buscar"][0]
    buscar.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    # Se muestra la cita y el botón de anular
    anular = [b for b in at.button if b.label == "Anular mi cita"]
    assert anular, "no aparece el botón anular mi cita"
    anular[0].click()
    at.run()
    conf = [b for b in at.button if b.label == "Sí, anularla"]
    assert conf, "no aparece la confirmación"
    conf[0].click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert [s for s in at.success], "no hay mensaje de cita anulada"
    assert "anulada" in [s.value for s in at.success][0]

    # Comprobamos que la cita ya no existe.
    r = Repo()
    assert r.get_cita_by_codigo(codigo) is None
    r.close()


def test_paciente_intento_anular_datos_incorrectos():
    import datetime as _dt
    from storage import Repo

    r = Repo()
    import services as sv
    sv.seed_medicos(r)
    mid = r.get_medicos()[0]["id"]
    r.add_cita(mid, "2026-08-17", "09:00", "web",
               "Ana", "García", "Ruiz", "612345678",
               "ana@example.com", "PRIVADO")
    r.close()

    at = _app()
    at.run()

    def inp(label):
        return [t for t in at.text_input if t.label == label][0]

    inp("Código de tu cita").set_value("C000000000000000")
    inp("Email o teléfono que usaste").set_value("otro@example.com")
    at.run()
    buscar = [b for b in at.button if b.label == "Buscar"][0]
    buscar.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert [e for e in at.error], "debe haber error de búsqueda"
    assert not [b for b in at.button if b.label == "Anular mi cita"]


if __name__ == "__main__":
    test_reserva_completa()
    print("FIN")