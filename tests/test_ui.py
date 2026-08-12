"""Pruebas del renderizado del calendario (ui.build_calendar_html)."""

import datetime as dt

import core
import ui


def _anyo_mes_anterior(hoy=None) -> tuple[int, int]:
    hoy = hoy or dt.date.today()
    if hoy.month == 1:
        return hoy.year - 1, 12
    return hoy.year, hoy.month - 1


def test_mes_pasado_muestra_todo_en_marron_sin_enlaces():
    y, m = _anyo_mes_anterior()
    html = ui.build_calendar_html(y, m, f"?y={y}&m={m}", None, {},
                                  compact=True)
    assert core.PAST_COLOR in html
    assert "cal-pasado" in html
    assert "<td><a" not in html, "un mes entero pasado no debe ser clicable"


def test_dias_futuros_mantienen_enlace_y_color_de_ocupacion():
    hoy = dt.date.today()
    y, m = hoy.year, hoy.month
    html = ui.build_calendar_html(y, m, f"?y={y}&m={m}", None, {},
                                  compact=True)
    assert "<td><a" in html, "el día de hoy debe seguir siendo un enlace"


def test_fecha_seleccionada_realza_el_dia():
    # Un día futuro (visible y clicable) debe marcarse como seleccionado.
    fecha_diana = dt.date.today() + dt.timedelta(days=1)
    y, m = fecha_diana.year, fecha_diana.month
    html = ui.build_calendar_html(y, m, f"?y={y}&m={m}",
                                  fecha_diana.isoformat(), {}, compact=True)
    assert "cal-seleccionado" in html


if __name__ == "__main__":
    test_mes_pasado_muestra_todo_en_marron_sin_enlaces()
    print("OK")