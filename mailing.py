"""Envío de correos de confirmación y de anulación de citas.

Recibe la configuración por variables de entorno o, si no están, de un
fichero local `mailing_credentials.json` en la carpeta del proyecto. Si no hay
ninguna configuración el envío se desactiva y la aplicación sigue funcionando.

Variables de entorno (con prioridad):

  SMTP_HOST  — servidor (por defecto `smtp.gmail.com`)
  SMTP_PORT  — puerto (587 por defecto)
  SMTP_USER  — usuario de autenticación
  SMTP_PASS  — contraseña o clave de aplicación
  SMTP_FROM  — remitente (por defecto el usuario)

Fichero `mailing_credentials.json` (Gmail):

  {"gmail_user": "tu@correo.com", "app_password": "xxxxx"}

El fichero de credenciales NO debe subirse a un repositorio (está en
.gitignore).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger("citas.mailing")

CREDENTIALS_FILE = Path(__file__).parent / "mailing_credentials.json"


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


def _smtp_cfg() -> dict:
    """Lee la configuración SMTP. Prioriza variables de entorno."""
    json_cfg = _cargar_json_credenciales()
    json_user = json_cfg.get("gmail_user") or ""
    json_pass = json_cfg.get("app_password") or ""

    user = os.environ.get("SMTP_USER") or json_user
    password = os.environ.get("SMTP_PASS") or json_pass
    return {
        "host": os.environ.get("SMTP_HOST") or "smtp.gmail.com",
        "port": int(os.environ.get("SMTP_PORT") or 587),
        "user": user,
        "pass": password,
        "from": (os.environ.get("SMTP_FROM") or user) or "no-reply@localhost",
    }


def _enviar(to_addr: str, subject: str, cuerpo: str) -> bool:
    """Devuelve True si se pudo entregar el correo."""
    cfg = _smtp_cfg()
    if not (cfg["user"] and cfg["pass"] and to_addr):
        log.info("Correo no enviado: SMTP sin credenciales o sin destinatario.")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to_addr
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls()
                server.ehlo()
            if cfg["user"]:
                server.login(cfg["user"], cfg["pass"])
            server.send_message(msg)
        return True
    except Exception as ex:  # noqa: BLE001 - no queremos romper la app
        log.warning("Fallo al enviar correo a %s: %s", to_addr, ex)
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
    return f"{cita['nombre']} {cita['apellido1']} {cita['apellido2']}".strip()


def enviar_confirmacion(cita) -> bool:
    """Envía una copia de la cita al solicitante."""
    cita = _fila(cita)
    if not cita.get("email"):
        return False
    medico = cita.get("medico_nombre") or ""
    esp = cita.get("medico_especialidad") or ""
    cuerpo = (
        f"Hola {_nombre_paciente(cita)}:\n\n"
        f"Tu cita médica ha sido confirmada.\n\n"
        f"  Código:   {cita['codigo']}\n"
        f"  Fecha:    {_fecha_humana(cita)}\n"
        f"  Hora:     {cita['hora']}\n"
        f"  Médico:   {medico}{' - ' if esp else ''}{esp}\n\n"
        f"Si no puedes acudir, por favor avísenos con antelación.\n"
        f"Un cordial saludo.\n\n"
        f"Clínica Citas Médicas"
    )
    return _enviar(cita["email"], f"Confirmación de tu cita {cita['codigo']}",
                   cuerpo)


def enviar_cancelacion(cita) -> bool:
    """Envía el aviso estándar de anulación de la cita."""
    cita = _fila(cita)
    if not cita.get("email"):
        return False
    cuerpo = (
        f"Hola {_nombre_paciente(cita)}:\n\n"
        f"Lamentamos comunicarte que tu cita médica ha sido cancelada.\n\n"
        f"  Código: {cita['codigo']}\n"
        f"  Fecha:  {_fecha_humana(cita)}\n"
        f"  Hora:   {cita['hora']}\n\n"
        f"Si lo deseas, puedes pedir una nueva cita a través de nuestro "
        f"calendario web o por teléfono.\n\n"
        f"Un cordial saludo.\n\n"
        f"Clínica Citas Médicas"
    )
    return _enviar(cita["email"],
                   f"Anulación de tu cita {cita['codigo']}", cuerpo)