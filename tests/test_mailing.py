"""Pruebas del módulo de correo (mailing.py) y de la migración de esquema."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

import mailing

# conftest.py desactiva _enviar globalmente; aquí conservamos la versión
# original para poder probar la lógica de envío con un SMTP falso.
_ENVIAR_ORIGINAL = mailing._enviar

_CRED = Path(tempfile.mkdtemp(prefix="mail_")) / "vacias.json"


@pytest.fixture(autouse=True)
def _sin_credenciales(monkeypatch):
    # Los tests nunca deben usar el fichero de credenciales real ni enviar
    # correos reales.
    monkeypatch.setattr(mailing, "CREDENTIALS_FILE", _CRED)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)


def _cita(email="ana@example.com"):
    return {
        "codigo": "C202608091200001",
        "fecha": "2026-08-17",
        "hora": "10:30",
        "nombre": "Ana",
        "apellido1": "García",
        "apellido2": "Ruiz",
        "email": email,
        "medico_nombre": "Dra. Lucía Fernández",
        "medico_especialidad": "Medicina de Familia",
    }


def test_sin_smtp_no_envia_ni_falla():
    assert mailing.enviar_confirmacion(_cita()) is False
    assert mailing.enviar_cancelacion(_cita()) is False
    assert mailing.enviar_confirmacion(_cita(email="")) is False


def test_correos_usan_destinatario(monkeypatch):
    # Forzamos SMTP falso para comprobar que intenta enviar al email correcto.
    monkeypatch.setattr(mailing, "_enviar", _ENVIAR_ORIGINAL)
    monkeypatch.setenv("SMTP_USER", "clinica@test.local")
    monkeypatch.setenv("SMTP_PASS", "secreta")
    monkeypatch.setenv("SMTP_FROM", "clinica@test.local")
    recibidos = []

    import smtplib

    class FalsoSmtp:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            pass

        def has_extn(self, name):
            return False

        def login(self, *a):
            pass

        def send_message(self, msg):
            recibidos.append(msg)

    monkeypatch.setattr(smtplib, "SMTP", FalsoSmtp)
    assert mailing.enviar_confirmacion(_cita()) is True
    assert mailing.enviar_cancelacion(_cita()) is True
    assert len(recibidos) == 2
    asunto = [m["Subject"] for m in recibidos]
    assert any("Confirmación" in s for s in asunto)
    assert any("Anulación" in s for s in asunto)
    cuerpo = "\n".join(str(m.get_content()) for m in recibidos)[:100]
    # El cuerpo menciona la fecha y la hora de la cita
    assert "17/08/2026" in "\n".join(str(m.get_content()) for m in recibidos)
    assert "10:30" in "\n".join(str(m.get_content()) for m in recibidos)


def test_credenciales_json_cargadas(monkeypatch, tmp_path):
    cfg_file = tmp_path / "creds.json"
    cfg_file.write_text('{"gmail_user": "a@b.com", "app_password": "clave"}',
                        encoding="utf-8")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.setattr(mailing, "CREDENTIALS_FILE", cfg_file)
    cfg = mailing._smtp_cfg()
    assert cfg["user"] == "a@b.com"
    assert cfg["pass"] == "clave"
    assert cfg["host"] == "smtp.gmail.com"


def test_migracion_dba_antigua_sin_email(tmp_path):
    # Creamos una base con el esquema antiguo (sin columna email).
    db = tmp_path / "viejas.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        "CREATE TABLE medicos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "nombre TEXT NOT NULL, especialidad TEXT NOT NULL DEFAULT '', "
        "intervalo_minutes INTEGER NOT NULL DEFAULT 20);"
        "CREATE TABLE citas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "codigo TEXT NOT NULL UNIQUE, medico_id INTEGER, fecha TEXT, "
        "hora TEXT, tipo TEXT, nombre TEXT, apellido1 TEXT, apellido2 TEXT, "
        "telefono TEXT, seguro TEXT, creada TEXT);"
    )
    conn.execute(
        "INSERT INTO medicos (nombre, especialidad, intervalo_minutes) "
        "VALUES ('Dra. A', 'Familia', 20)"
    )
    conn.execute(
        "INSERT INTO citas (codigo, medico_id, fecha, hora, tipo, nombre, "
        "apellido1, apellido2, telefono, seguro, creada) VALUES "
        "('C1', 1, '2026-01-01', '09:00', 'web', 'A', 'B', 'C', '612345678', "
        "'PRIVADO', 'x')"
    )
    conn.commit()
    conn.close()

    from storage import Repo

    r = Repo(db)
    cols = [c["name"] for c in r.conn.execute("PRAGMA table_info(citas)")]
    assert "email" in cols
    # Las filas viejas conservan un email vacío.
    fila = r.get_citas_fecha("2026-01-01")
    assert fila and fila[0]["email"] == ""
    r.close()