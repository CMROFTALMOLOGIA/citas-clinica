"""Auditoría end-to-end: el código de color del calendario pasa por los tres
niveles cuando se llena 1/3, 1/2 y el total de los huecos del día.
"""

import datetime as dt

import core  # noqa: E402
import services  # noqa: E402
from storage import Repo  # noqa: E402


def _slot_todos(r, fecha):
    out = []
    for med in r.get_medicos():
        vent = services.ventanas_dia(fecha, med["id"], r)
        for h in services.slots_dia(vent, med["intervalo_minutes"]):
            out.append((med["id"], h))
    return out


def _citar(r, fecha, cuantos):
    for mid, h in _slot_todos(r, fecha):
        if cuantos <= 0:
            return
        try:
            r.add_cita(mid, fecha.isoformat(), h, "web",
                       "A", "B", "C", "612345678", "a@b.es", "PRIVADO")
            cuantos -= 1
        except RuntimeError:
            pass


def _nivel(r, fecha):
    res = services.resumen_dia(fecha, r)
    return res["citados"], res["total_slots"], res["level"]


def test_tres_niveles_de_color():
    r = Repo()
    services.seed_medicos(r)
    fecha = dt.date(2026, 8, 3)  # lunes
    total = len(_slot_todos(r, fecha))
    assert total > 0

    for marca, meta, esperado in [
        ("poco", total // 10, core.OCC_LOW),
        ("1/3+", total // 3 + 2, core.OCC_MID),
        ("1/2+", total // 2 + 1, core.OCC_HIGH),
        ("total", total, core.OCC_HIGH),
    ]:
        citadas = len(r.get_citas_fecha(fecha.isoformat()))
        _citar(r, fecha, meta - citadas)
        c, t, lvl = _nivel(r, fecha)
        assert lvl == esperado, f"{marca}: {c}/{t} -> {lvl} != {esperado}"


def test_dia_sin_agenda():
    r = Repo()
    # domingo 9 de agosto 2026: nadie atiende
    res = services.resumen_dia(dt.date(2026, 8, 9), r)
    assert res["total_slots"] == 0
    assert res["level"] == core.OCC_NONE