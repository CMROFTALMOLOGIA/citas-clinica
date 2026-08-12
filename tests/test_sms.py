"""Pruebas del módulo de SMS (sms.py) vía Afilnet."""

import io
import json
import tempfile
from pathlib import Path

import pytest

import sms

# conftest.py desactiva _enviar globalmente; aquí conservamos la versión
# original para poder probar la lógica de envío con un urlopen falso.
_ENVIAR_ORIGINAL = sms._enviar

_CRED = Path(tempfile.mkdtemp(prefix="sms_")) / "vacias.json"


@pytest.fixture(autouse=True)
def _sin_credenciales(monkeypatch):
    # Los tests nunca deben usar el fichero de credenciales real ni enviar
    # SMS reales.
    monkeypatch.setattr(sms, "CREDENTIALS_FILE", _CRED)
    monkeypatch.delenv("AFILNET_USER", raising=False)
    monkeypatch.delenv("AFILNET_PASS", raising=False)
    monkeypatch.delenv("AFILNET_FROM", raising=False)


def _cita(telefono="612345678"):
    return {
        "codigo": "C202608091200001",
        "fecha": "2026-08-17",
        "hora": "10:30",
        "nombre": "Ana",
        "apellido1": "García",
        "apellido2": "Ruiz",
        "telefono": telefono,
        "medico_nombre": "Dra. Lucía Fernández",
        "medico_especialidad": "Medicina de Familia",
    }


def test_sin_credenciales_no_envia_ni_falla():
    assert sms.enviar_confirmacion_sms(_cita()) is False
    assert sms.enviar_cancelacion_sms(_cita()) is False
    assert sms.enviar_confirmacion_sms(_cita(telefono="")) is False


def test_normalizacion_telefono():
    assert sms._telefono_internacional("612345678") == "34612345678"
    assert sms._telefono_internacional("612 34 56 78") == "34612345678"
    assert sms._telefono_internacional("34612345678") == "34612345678"
    assert sms._telefono_internacional("0034612345678") == "34612345678"
    assert sms._telefono_internacional("") == ""
    assert sms._telefono_internacional("123") == ""


def _fake_urlopen(respuesta):
    import urllib.request

    def fake(request, timeout=15):
        clase = type(request)
        return io.BytesIO(json.dumps(respuesta).encode("utf-8"))

    return fake


def test_envio_sms_correcto(monkeypatch):
    import urllib.request

    monkeypatch.setattr(sms, "_enviar", _ENVIAR_ORIGINAL)
    monkeypatch.setenv("AFILNET_USER", "usuario")
    monkeypatch.setenv("AFILNET_PASS", "secreta")
    enviados = []

    def fake_urlopen(req, timeout=15):
        enviados.append(req.data.decode("utf-8"))
        return io.BytesIO(json.dumps(
            {"status": "SUCCESS",
             "result": {"messageid": "msg_1", "credits": "1"}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert sms.enviar_confirmacion_sms(_cita()) is True
    assert len(enviados) == 1
    datos = dict(p.split("=", 1) for p in enviados[0].split("&"))
    assert datos["class"] == "sms"
    assert datos["method"] == "sendsms"
    assert datos["user"] == "usuario"
    assert datos["to"] == "34612345678"
    assert "confirmada" in datos["sms"].replace("+", " ")


def test_envio_sms_rechazado(monkeypatch):
    import urllib.request

    monkeypatch.setattr(sms, "_enviar", _ENVIAR_ORIGINAL)
    monkeypatch.setenv("AFILNET_USER", "usuario")
    monkeypatch.setenv("AFILNET_PASS", "secreta")
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda req, timeout=15: io.BytesIO(json.dumps(
            {"status": "ERROR", "error": "NO_CREDITS"}).encode()))
    assert sms.enviar_cancelacion_sms(_cita()) is False


def test_credenciales_json_cargadas(monkeypatch, tmp_path):
    cfg_file = tmp_path / "creds.json"
    cfg_file.write_text(
        '{"afilnet_user": "user1", "afilnet_password": "clave", '
        '"from": "MI CLINICA"}',
        encoding="utf-8")
    monkeypatch.delenv("AFILNET_USER", raising=False)
    monkeypatch.delenv("AFILNET_PASS", raising=False)
    monkeypatch.setattr(sms, "CREDENTIALS_FILE", cfg_file)
    cfg = sms._cfg()
    assert cfg["user"] == "user1"
    assert cfg["pass"] == "clave"
    assert cfg["from"] == "MI CLINICA"


def test_mensajes_incluyen_fecha_hora(monkeypatch):
    import urllib.request

    monkeypatch.setattr(sms, "_enviar", _ENVIAR_ORIGINAL)
    monkeypatch.setenv("AFILNET_USER", "usuario")
    monkeypatch.setenv("AFILNET_PASS", "secreta")
    enviados = []

    def fake_urlopen(req, timeout=15):
        enviados.append(req.data.decode("utf-8"))
        return io.BytesIO(json.dumps(
            {"status": "SUCCESS",
             "result": {"messageid": "msg_1", "credits": "1"}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert sms.enviar_confirmacion_sms(_cita()) is True
    assert sms.enviar_cancelacion_sms(_cita()) is True
    import urllib.parse
    textos = []
    for p in enviados:
        datos = dict(p.split("=", 1) for p in p.split("&"))
        textos.append(urllib.parse.unquote_plus(datos["sms"]))
    assert "17/08/2026" in textos[0]
    assert "10:30" in textos[0]
    assert "cancelada" in textos[1]