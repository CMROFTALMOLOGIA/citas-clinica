"""Pruebas de la capa de servicios y persistencia."""

import datetime as dt

import pytest

import core
import services
from storage import Repo


@pytest.fixture
def repo(tmp_path):
    r = Repo(tmp_path / "test.db")
    yield r
    r.close()


@pytest.fixture
def repo_con_medico(repo):
    repo.add_medico("Test Médico", "Pruebas", 20)
    # Lunes (weekday 0): mañana 9-10, tarde 16-17
    repo.set_horarios(1, {0: [(9 * 60, 10 * 60), (16 * 60, 17 * 60)]})
    return repo


def _oid(repo):
    return repo.get_medicos()[0]["id"]


def test_add_medico(repo_con_medico):
    medicos = repo_con_medico.get_medicos()
    assert len(medicos) == 1
    assert medicos[0]["nombre"] == "Test Médico"
    assert medicos[0]["intervalo_minutes"] == 20


def test_ventanas_dia_y_slots(repo_con_medico):
    mid = _oid(repo_con_medico)
    fecha = dt.date(2026, 1, 5)  # lunes
    ventanas = services.ventanas_dia(fecha, mid, repo_con_medico)
    slots = services.slots_dia(ventanas, 20)
    assert slots == ["09:00", "09:20", "09:40", "16:00", "16:20", "16:40"]


def test_domingo_sin_agenda(repo_con_medico):
    mid = _oid(repo_con_medico)
    fecha = dt.date(2026, 1, 11)  # domingo: no atiende
    assert services.ventanas_dia(fecha, mid, repo_con_medico) == []
    assert services.slots_disponibles(fecha, mid, repo_con_medico) == []


def test_slots_disponibles_excluye_ocupados(repo_con_medico):
    mid = _oid(repo_con_medico)
    fecha = dt.date(2026, 1, 5)
    repo_con_medico.add_cita(mid, fecha.isoformat(), "09:20", "web",
                             "Ana", "García", "Ruiz", "612345678",
                             "ana@example.com", "PRIVADO")
    libres = services.slots_disponibles(fecha, mid, repo_con_medico)
    assert "09:20" not in libres
    assert "09:00" in libres


def test_ocupacion_mes(repo_con_medico):
    mid = _oid(repo_con_medico)
    repo_con_medico.add_cita(mid, "2026-01-05", "09:20", "web",
                             "Ana", "García", "López", "123456789",
                             "ana@example.com", "PRIVADO")
    resumen = services.resumen_dia(dt.date(2026, 1, 5), repo_con_medico)
    assert resumen["total_slots"] == 6
    assert resumen["citados"] == 1
    # 1 de 6 citado -> ocupación baja (< 1/3)
    assert resumen["level"] == core.OCC_LOW

    # Llenamos: la mitad => nível alto
    repo_con_medico.add_cita(mid, "2026-01-05", "09:00", "web",
                             "X", "Y", "Z", "123456789",
                             "x@example.com", "PRIVADO")
    repo_con_medico.add_cita(mid, "2026-01-05", "09:40", "web",
                             "X", "Y", "Z", "123456789",
                             "x@example.com", "PRIVADO")
    resumen = services.resumen_dia(dt.date(2026, 1, 5), repo_con_medico)
    assert resumen["citados"] == 3
    assert resumen["level"] == core.OCC_HIGH  # exactamente 1/2 -> alto


def test_seed_medicos(repo):
    services.seed_medicos(repo)
    assert len(repo.get_medicos()) == 6
    # Idempotente: volver a llamar no duplica
    services.seed_medicos(repo)
    assert len(repo.get_medicos()) == 6


def test_cancelar_cita_repo(repo_con_medico):
    mid = _oid(repo_con_medico)
    codigo = repo_con_medico.add_cita(mid, "2026-01-05", "09:00",
                                      "web", "Ana", "García", "López",
                                      "123456789", "ana@example.com",
                                      "PRIVADO")
    assert repo_con_medico.get_cita_by_codigo(codigo)
    assert repo_con_medico.cancelar_cita(codigo) is True
    assert repo_con_medico.get_cita_by_codigo(codigo) is None
    assert repo_con_medico.cancelar_cita(codigo) is False