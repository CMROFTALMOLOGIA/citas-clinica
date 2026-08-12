"""Alta y baja de profesionales desde la zona clínica."""

import pathlib

from streamlit.testing.v1 import AppTest

import storage

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")


def _entrar_clinica(at):
    at.run()
    at.sidebar.radio[0].set_value("Zona clínica")
    at.run()
    assert len(at.exception) == 0
    pin = [t for t in at.text_input if "Código de acceso" in t.label][0]
    pin.set_value("clinic2026")
    at.run()
    btn = [b for b in at.button if "Entrar a la clínica" in b.label][0]
    btn.click()
    at.run()
    assert len(at.exception) == 0
    at.sidebar.radio[1].set_value("Configuración")
    at.run()


def test_dar_de_alta_nuevo_profesional():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    r = storage.Repo()
    assert len(r.get_medicos()) == 6

    # Primeros widgets del formulario "Dar de alta":
    # text_input[0] = Nombre, text_input[1] = Especialidad,
    # number_input[0] = Minutos entre citas.
    at.text_input[0].set_value("Dra. Laura Gómez")
    at.text_input[1].set_value("Oftalmología")
    at.number_input[0].set_value(25)
    at.run()
    alta = [b for b in at.button if b.label == "Dar de alta"][0]
    alta.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    r = storage.Repo()
    medicos = r.get_medicos()
    assert len(medicos) == 7
    nuevo = [m for m in medicos if m["nombre"] == "Dra. Laura Gómez"]
    assert len(nuevo) == 1
    assert nuevo[0]["especialidad"] == "Oftalmología"
    assert nuevo[0]["intervalo_minutes"] == 25


def test_alta_sin_nombre_muestra_error():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    assert len(storage.Repo().get_medicos()) == 6
    alta = [b for b in at.button if b.label == "Dar de alta"][0]
    alta.click()
    at.run()
    assert len(at.exception) == 0
    assert any("El nombre es obligatorio" in e.value
               for e in at.error), [e.value for e in at.error]
    assert len(storage.Repo().get_medicos()) == 6


def test_eliminar_profesional():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    assert len(storage.Repo().get_medicos()) == 6

    eliminar = [b for b in at.button if b.label == "Eliminar profesional"][0]
    eliminar.click()
    at.run()
    assert len(at.exception) == 0
    confirma = [b for b in at.button if b.label == "Sí, eliminar"][0]
    confirma.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    restantes = storage.Repo().get_medicos()
    assert len(restantes) == 5
    assert all(m["id"] != 1 for m in restantes)


def test_cancelar_eliminacion_no_borra():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    assert len(storage.Repo().get_medicos()) == 6

    eliminar = [b for b in at.button if b.label == "Eliminar profesional"][0]
    eliminar.click()
    at.run()
    assert len(at.exception) == 0
    cancela = [b for b in at.button if b.label == "Cancelar"][0]
    cancela.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]
    assert len(storage.Repo().get_medicos()) == 6


if __name__ == "__main__":
    test_dar_de_alta_nuevo_profesional()
    print("OK")