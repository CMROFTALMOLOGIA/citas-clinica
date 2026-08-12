"""Prueba de guardado de agenda desde la interfaz."""

import pathlib

from streamlit.testing.v1 import AppTest

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


def test_guardar_intervalo():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    # number_input[0] es el nuevo formulario de alta; [1] el primer médico.
    # Cambiamos el intervalo del primer médico (15 -> 30)
    at.number_input[1].set_value(30)
    at.run()
    guardar = [b for b in at.button if b.label == "Guardar agenda"][0]
    guardar.click()
    at.run()
    assert len(at.exception) == 0, [e.message for e in at.exception]

    from storage import Repo
    r = Repo()
    assert r.get_medicos()[0]["intervalo_minutes"] == 30


def test_guardar_horario_diferente():
    at = AppTest.from_file(APP, default_timeout=120)
    _entrar_clinica(at)
    at.run()
    assert len(at.exception) == 0

    # Los 28 primeros time_input son del formulario de alta. El siguiente
    # (índice 28) es el "Mañana" del lunes del primer médico.
    # Lo cambiamos a 08:30.
    from datetime import time
    at.time_input[28].set_value(time(8, 30))
    at.run()
    guardar = [b for b in at.button if b.label == "Guardar agenda"][0]
    guardar.click()
    at.run()
    assert len(at.exception) == 0

    from storage import Repo
    r = Repo()
    hor = r.get_horarios(1)
    lunes = [h for h in hor if h["weekday"] == 0]
    assert lunes and lunes[0]["inicio"] == 8 * 60 + 30


if __name__ == "__main__":
    test_guardar_intervalo()
    print("OK")