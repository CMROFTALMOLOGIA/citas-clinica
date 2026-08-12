"""Configuración global de las pruebas.

Aísla cada prueba con su propia base de datos temporal y garantiza que nunca
se envien correos reales ni se dependa del fichero de credenciales de la
aplicación.
"""

import os
import tempfile
from pathlib import Path

import pytest

import mailing
import sms


@pytest.fixture(autouse=True)
def _test_aislado(monkeypatch, tmp_path):
    # Base de datos propia por prueba: las AppTest comparten proceso y mustoe
    # las pruebas no deben tocarse entre sí.
    db = Path(tmp_path) / "test.db"
    monkeypatch.setenv("CITAS_DB_PATH", str(db))

    # Nunca correo real durante las pruebas.
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.setattr(mailing, "_enviar",
                        lambda *a, **k: False)

    # Nunca SMS real durante las pruebas.
    monkeypatch.delenv("AFILNET_USER", raising=False)
    monkeypatch.delenv("AFILNET_PASS", raising=False)
    monkeypatch.delenv("AFILNET_FROM", raising=False)
    monkeypatch.setattr(sms, "_enviar",
                        lambda *a, **k: False)