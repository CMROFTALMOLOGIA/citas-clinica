"""Envío de SMS de confirmación y de anulación de citas vía Afilnet.

Recibe la configuración por variables de entorno o, si no están, de un
fichero local `sms_credentials.json` en la carpeta del proyecto. Si no hay
ninguna configuración el envío se desactiva y la aplicación sigue
funcionando.

Variables de entorno (con prioridad):

  AFILNET_USER  — usuario de la cuenta de Afilnet
  AFILNET_PASS  — contraseña de la cuenta de Afilnet
  AFILNET_FROM  — remitente (máx. 11 caracteres, por defecto "CLINICA")

Fichero `sms_credentials.json`:

  {"afilnet_user": "tu_usuario", "afilnet_password": "xxxxx",
   "from": "CLINICA"}

El fichero de credenciales NO debe subirse a un repositorio (está en
.gitignore).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("citas.sms")

CREDENTIALS_FILE = Path(__file__).parent / "sms_credentials.json"
API_URL = "https://www.afilnet.com/api/http/"


def _cargar_json_credenciales() -> dict:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        with CREDENTIALS_FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        log.warning("No se pudo leer %s", CREDENTIALS_FILE.name)
        return {}


def _cfg() -> dict:
    """Lee la configuración de Afilnet. Prioriza variables de entorno."""
    json_cfg = _cargar_json_credenciales()
    json_user = json_cfg.get("afilnet_user") or ""
    json_pass = json_cfg.get("afilnet_password") or ""
    return {
        "user": os.environ.get("AFILNET_USER") or json_user,
        "pass": os.environ.get("AFILNET_PASS") or json_pass,
        "from": (os.environ.get("AFILNET_FROM")
                 or json_cfg.get("from") or "CLINICA"),
    }


def _telefono_internacional(telefono: str) -> str:
    """Normaliza un teléfono español a formato internacional para Afilnet.

    Devuelve "" si el número no tiene dígitos suficientes.
    """
    digitos = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("34") and len(digitos) == 11:
        return digitos
    if len(digitos) == 9:
        return "34" + digitos
    return ""


def _enviar(to: str, msg: str) -> bool:
    """Envía un SMS vía Afilnet. Devuelve True si Afilnet lo aceptó."""
    cfg = _cfg()
    if not (cfg["user"] and cfg["pass"] and to and msg):
        log.info("SMS no enviado: faltan credenciales, teléfono o mensaje.")
        return False
    datos = {
        "class": "sms",
        "method": "sendsms",
        "user": cfg["user"],
        "password": cfg["pass"],
        "to": to,
        "sms": msg,
    }
    datos["from"] = cfg["from"]
    cuerpo = urllib.parse.urlencode(datos).encode("utf-8")
    try:
        req = urllib.request.Request(API_URL, data=cuerpo)
        with urllib.request.urlopen(req, timeout=15) as resp:
            respuesta = json.loads(resp.read().decode("utf-8"))
    except Exception as ex:  # noqa: BLE001 - no queremos romper la app
        log.warning("Fallo al enviar SMS a %s: %s", to, ex)
        return False
    if respuesta.get("status") == "SUCCESS":
        log.info("SMS enviado a %s (id %s)", to,
                 respuesta.get("result", {}).get("messageid"))
        return True
    log.warning("Afilnet rechazó el SMS a %s: %s", to,
                respuesta.get("error"))
    return False


def _fila(cita):
    """Normaliza sqlite3.Row / dict / mappings a un dict."""
    return dict(cita) if hasattr(cita, "keys") else cita


def _fecha_humana(cita) -> str:
    cita = _fila(cita)
    try:
        return dt.date.fromisoformat(cita["fecha"]).strftime("%d/%m/%Y")
    except (KeyError, TypeError, ValueError):
        return str(cita.get("fecha", ""))


def _nombre_paciente(cita) -> str:
    cita = _fila(cita)
    return f"{cita['nombre']} {cita['apellido1']}".strip()


def _telefono_paciente(cita) -> str:
    cita = _fila(cita)
    return _telefono_internacional(cita.get("telefono") or "")


def enviar_confirmacion_sms(cita) -> bool:
    """Envía el SMS de confirmación al paciente (si tiene teléfono)."""
    cita = _fila(cita)
    to = _telefono_paciente(cita)
    if not to:
        return False
    medico = cita.get("medico_nombre") or ""
    esp = cita.get("medico_especialidad") or ""
    msg = (
        f"Hola {_nombre_paciente(cita)}. Tu cita médica ha sido confirmada: "
        f"{_fecha_humana(cita)} a las {cita['hora']}. {medico}"
        f"{' - ' if esp else ''}{esp}. Código: {cita['codigo']}. "
        f"Si no puedes acudir, avísanos con antelación."
    )
    return _enviar(to, msg)


def enviar_cancelacion_sms(cita) -> bool:
    """Envía el SMS de aviso de anulación al paciente."""
    cita = _fila(cita)
    to = _telefono_paciente(cita)
    if not to:
        return False
    msg = (
        f"Hola {_nombre_paciente(cita)}. Tu cita médica del "
        f"{_fecha_humana(cita)} a las {cita['hora']} ha sido cancelada. "
        f"Si lo deseas, pide una nueva cita en nuestra web o por teléfono."
    )
    return _enviar(to, msg)