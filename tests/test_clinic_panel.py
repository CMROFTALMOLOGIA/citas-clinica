"""Pruebas del panel 'Citas del día' de la zona clínica (AppTest)."""

import datetime as dt
import pathlib

from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")

# 2026-08-17 es lunes: los 6 médicos atienden ese día.
FECHA = dt.date(2026, 8, 17)


def _entrar_clinica() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value("Zona clínica")
    at.run()
    pin = [t for t in at.text_input if "Código de acceso" in t.label][0]
    pin.set_value("clinic2026")
    at.run()
    btn = [b for b in at.button if "Entrar a la clínica" in b.label][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    return at


def test_registrar_cita_manual_y_anular():
    at = _entrar_clinica()
    # El panel por defecto es "Citas del día".
    # date_input[0] = "Fecha" (lista), date_input[1] = "Fecha de la cita".
    at.date_input[1].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    # Rellenamos el formulario de registro manual.
    def inp(label):
        return [t for t in at.text_input if t.label == label][0]

    inp("Nombre").set_value("Luis")
    inp("Primer apellido").set_value("Martín")
    inp("Segundo apellido").set_value("Sanz")
    inp("Teléfono (9 dígitos)").set_value("699000222")
    inp("Email").set_value("luis@example.com")
    at.run()
    btn = [b for b in at.button if b.label == "Registrar cita"][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert [s for s in at.success], "no hay mensaje de éxito al registrar"

    # La cita aparece en la lista del día (fecha de la vista).
    at.date_input[0].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    md = " ".join(m.value for m in at.markdown)
    assert "Luis Martín Sanz" in md
    assert "699000222" in md

    # La anulamos.
    anular = [b for b in at.button if b.label == "Anular"][0]
    anular.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert any("No hay citas" in i.value for i in at.info), \
        "tras anular no debe haber citas en la lista"


def test_registrar_cita_manual_calcula_huecos():
    at = _entrar_clinica()
    at.date_input[1].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    # Debe haber un desplegable de hora con opciones libres (05:00…).
    hora = [s for s in at.selectbox if s.label == "Hora"][0]
    opciones = hora.options
    assert len(opciones) > 0
    primera = opciones[0]
    assert primera[0] == "0" or primera[0] == "1"  # formato HH:MM


def test_huecos_se_actualizan_con_la_fecha():
    # Reproducción del fallo: al cambiar de profesional o fecha la lista de
    # horas debía refrescarse, no quedarse fija en "No disponible".
    at = _entrar_clinica()
    # Domingo 2026-08-16: nadie atiende ese día.
    at.date_input[1].set_value(dt.date(2026, 8, 16))
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert any("No hay huecos libres" in w.value for w in at.warning), \
        "un día sin actividad debe avisar de que no hay huecos"
    hora = [s for s in at.selectbox if s.label == "Hora"][0]
    assert hora.options == ["No disponible"]

    # Lunes 2026-08-17: sí hay huecos; la lista debe recuperarse.
    at.date_input[1].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert not any("No hay huecos libres" in w.value for w in at.warning), \
        "al volver a un día laborable la lista debe refrescarse"
    hora = [s for s in at.selectbox if s.label == "Hora"][0]
    assert hora.options and hora.options[0][0] in "01"


def test_agenda_se_muestra_por_profesional():
    # Dos citas para médicos distintos el mismo día.
    import services as sv
    from storage import Repo

    r = Repo()
    sv.seed_medicos(r)
    mid1 = r.get_medicos()[0]["id"]
    mid2 = r.get_medicos()[1]["id"]
    r.add_cita(mid1, FECHA.isoformat(), "09:00", "web",
               "Ana", "Uno", "Rojo", "611111111", "a1@example.com", "PRIVADO")
    r.add_cita(mid2, FECHA.isoformat(), "09:30", "web",
               "Luis", "Dos", "Azul", "622222222", "a2@example.com", "PRIVADO")
    r.close()

    at = _entrar_clinica()
    at.date_input[0].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    md = " ".join(m.value for m in at.markdown)
    # Solo la agenda del primer médico: su cita sí, la del otro no.
    assert "Ana Uno Rojo" in md
    assert "Luis Dos Azul" not in md

    # Cambiamos al segundo médico.
    agenda = [s for s in at.selectbox if s.label == "Agenda de"][0]
    agenda.select(mid2)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    md = " ".join(m.value for m in at.markdown)
    assert "Luis Dos Azul" in md
    assert "Ana Uno Rojo" not in md


def _cita_para_agenda():
    import services as sv
    from storage import Repo

    r = Repo()
    sv.seed_medicos(r)
    mid = r.get_medicos()[0]["id"]
    r.add_cita(mid, FECHA.isoformat(), "09:00", "web",
               "Ana", "Uno", "Rojo", "611111111", "a1@example.com", "PRIVADO")
    r.add_cita(mid, FECHA.isoformat(), "09:30", "telefono",
               "Luis", "Dos", "Azul", "622222222", "a2@example.com", "SANITAS")
    r.close()


def test_imprimir_agenda_compacta():
    _cita_para_agenda()
    at = _entrar_clinica()
    at.date_input[0].set_value(FECHA)
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    imprimir = [b for b in at.button if b.label == "Imprimir agenda"][0]
    imprimir.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    md = " ".join(m.value for m in at.markdown)
    assert "Agenda compacta" in md
    assert "Sociedad" in md
    # una línea por paciente: apellidos y nombre
    assert "Uno Rojo, Ana" in md
    assert "Dos Azul, Luis" in md

    # Botón de descarga compatible con Excel.
    assert [d for d in at.download_button
            if d.label == "Descargar listado (Excel/CSV)"]


def test_listados_csv_y_tabla():
    import services as sv
    import storage

    r = storage.Repo()
    sv.seed_medicos(r)
    mid = r.get_medicos()[0]["id"]
    r.add_cita(mid, FECHA.isoformat(), "09:00", "web",
               "Ana", "Uno", "Rojo", "611111111", "a1@example.com", "PRIVADO")
    r.add_cita(mid, FECHA.isoformat(), "10:00", "telefono",
               "Luis", "Dos", "Azul", "622222222", "a2@example.com", "SANITAS")
    citas = [c for c in r.get_citas_fecha(FECHA.isoformat())]

    csv_bytes = sv.agenda_csv(citas)
    texto = csv_bytes.decode("utf-8")
    assert texto.startswith("\ufeff")
    assert "Hora;Apellido 1;Apellido 2;Nombre;Sociedad;Teléfono" in texto
    assert "Uno;Rojo;Ana;PRIVADO;611111111" in texto
    assert "Dos;Azul;Luis;SANITAS;622222222" in texto

    html = sv.agenda_tabla_html(citas)
    assert "<table" in html
    assert "Uno Rojo, Ana" in html
    assert "Dos Azul, Luis" in html
    assert "SANITAS" in html


def test_registrar_cita_manual_envia_email_y_sms(monkeypatch):
    # El registro manual debe notificar por email y por SMS al paciente.
    enviados = {"mail": [], "sms": []}
    import mailing
    import sms

    def ver_mail(*a, **k):
        enviados["mail"].append(a)
        return True

    def ver_sms(*a, **k):
        enviados["sms"].append(a)
        return True

    monkeypatch.setattr(mailing, "enviar_confirmacion", ver_mail)
    monkeypatch.setattr(sms, "enviar_confirmacion_sms", ver_sms)

    at = _entrar_clinica()
    at.date_input[1].set_value(FECHA)
    at.run()

    def inp(label):
        return [t for t in at.text_input if t.label == label][0]

    inp("Nombre").set_value("Luis")
    inp("Primer apellido").set_value("Martín")
    inp("Segundo apellido").set_value("Sanz")
    inp("Teléfono (9 dígitos)").set_value("699000222")
    inp("Email").set_value("luis@example.com")
    at.run()
    btn = [b for b in at.button if b.label == "Registrar cita"][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert len(enviados["mail"]) == 1, "debe enviar la confirmación por email"
    assert len(enviados["sms"]) == 1, "debe enviar la confirmación por SMS"
    cita = enviados["sms"][0][0]
    assert cita["telefono"] == "699000222"
    assert cita["email"] == "luis@example.com"


if __name__ == "__main__":
    test_registrar_cita_manual_y_anular()
    print("OK")
