"""Pruebas del núcleo de negocio (core.py)."""

import datetime as dt

import pytest

import core


def test_add_minutes():
    assert core.to_hhmm(core.add_minutes(core.parse_time("09:00"), 20)) == "09:20"
    assert core.to_hhmm(core.add_minutes(core.parse_time("09:50"), 15)) == "10:05"
    assert core.to_hhmm(core.add_minutes(core.parse_time("23:50"), 20)) == "00:10"


def test_generate_slot_times_includes_start_excludes_end():
    slots = core.generate_slot_times("09:00", "10:00", 20)
    assert slots == ["09:00", "09:20", "09:40"]


def test_slots_for_windows():
    windows = [("09:00", "10:00"), ("11:00", "11:30")]
    slots = core.slots_for_windows(windows, 15)
    assert slots == ["09:00", "09:15", "09:30", "09:45", "11:00", "11:15"]


def test_slots_for_windows_union_sorted():
    windows = [("16:00", "17:00"), ("09:00", "10:00")]
    slots = core.slots_for_windows(windows, 30)
    assert slots == ["09:00", "09:30", "16:00", "16:30"]


# ---- Validación del paciente ----


def test_validate_patient_data_ok():
    assert core.validate_patient_data("Ana", "García", "Ruiz", "612345678",
                                      "ana@example.com", "SANITAS") == []


def test_validate_patient_data_privado():
    assert core.validate_patient_data("Ana", "López", "Pérez", "612 345 678",
                                     "ana@example.com",
                                     core.INSURANCE_DEFAULT) == []


def test_validate_patient_data_required():
    errors = core.validate_patient_data("", "", "", "", "", "")
    assert "El nombre es obligatorio." in errors
    assert "El primer apellido es obligatorio." in errors
    assert "El segundo apellido es obligatorio." in errors
    assert "El teléfono no es válido." in errors
    assert "El email es obligatorio." in errors


def test_validate_patient_data_phone_short():
    errors = core.validate_patient_data("Ana", "García", "Ruiz", "123",
                                        "ana@example.com", "PRIVADO")
    assert any("teléfono" in e for e in errors)


def test_validate_patient_data_phone_wrong_length():
    errors = core.validate_patient_data("Ana", "García", "Ruiz",
                                        "6123456789", "ana@example.com",
                                        "PRIVADO")
    assert any("9 dígitos" in e for e in errors)


def test_validate_patient_data_email_invalido():
    errors = core.validate_patient_data("Ana", "García", "Ruiz", "612345678",
                                        "esto-no-es-email", "PRIVADO")
    assert "El email no es válido." in errors


def test_validate_patient_data_phone_bad_chars():
    errors = core.validate_patient_data("Ana", "García", "Ruiz", "abc!!!",
                                        "ana@example.com", "X")
    assert any("teléfono" in e for e in errors)


# ---- Niveles de ocupación ----


def test_occupancy_none():
    assert core.occupancy_level(0, 0) == core.OCC_NONE


def test_occupancy_low():
    # 5 huecos, 1 citado -> 20% -> bajo
    assert core.occupancy_level(5, 1) == core.OCC_LOW


def test_occupancy_third_exact():
    # 1/3 exacto -> medio
    assert core.occupancy_level(9, 3) == core.OCC_MID


def test_occupancy_half_exact():
    assert core.occupancy_level(6, 3) == core.OCC_HIGH


def test_occupancy_over_half():
    assert core.occupancy_level(10, 6) == core.OCC_HIGH


def test_occupancy_total():
    assert core.occupancy_level(8, 8) == core.OCC_HIGH


def test_color_for_level():
    assert core.color_for_level(core.OCC_HIGH) == core.COLORS[core.OCC_HIGH]


# ---- Calendario mensual ----


def test_first_day_grid_2026_01():
    # 1 de enero de 2026 es jueves -> weekday() == 3
    assert core.first_day_grid(2026, 1) == 3
    assert core.days_in_month(2026, 1) == 31


def test_first_day_grid_2026_08():
    assert core.days_in_month(2026, 8) == 31


def test_build_month_grid_dimensions():
    for m in range(1, 13):
        grid = core.build_month_grid(2026, m)
        assert len(grid) == 42
        # El número de celdas no vacías coincide con los días del mes
        assert sum(1 for c in grid if c is not None) == core.days_in_month(2026, m)


def test_build_month_grid_starts_on_weekday():
    grid = core.build_month_grid(2026, 1)
    # primer día del mes en la posición correcta (jueves -> índice 3)
    assert grid[3] == 1
    assert grid[:3] == [None, None, None]


def test_iter_weeks():
    weeks = core.iter_weeks(2026, 1)
    assert len(weeks) == 6
    assert len(weeks[0]) == 7
    flat = [c for week in weeks for c in week]
    assert len(flat) == 42