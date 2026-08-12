"""Núcleo de negocio de la aplicación de citas médicas.

Contiene toda la lógica pura (sin dependencias de Streamlit) para que sea
fácilmente testeable: generación de huecos, ocupación, validaciones y el
calendario mensual.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Optional, Sequence

# ---- Constantes -------------------------------------------------------------

WEEKDAY_NAMES = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]

WEEKDAY_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Niveles de ocupación del calendario
OCC_NONE = 0       # Sin agenda ese día
OCC_LOW = 1        # menos de un tercio citado
OCC_MID = 2        # entre un tercio y la mitad
OCC_HIGH = 3       # mitad o más / llena

COLORS = {
    OCC_NONE: "#9ca3af",
    OCC_LOW: "#22c55e",   # verde  - hay huecos
    OCC_MID: "#f59e0b",   # ámbar  - citada ~1/3..1/2
    OCC_HIGH: "#ef4444",  # rojo   - citada mitad o total
}

# Color de las fechas ya pasadas: marrón, no se pueden solicitar citas.
PAST_COLOR = "#8d6e63"
PAST_LABEL = "Fecha pasada"

OCC_LABELS = {
    OCC_NONE: "Sin agenda",
    OCC_LOW: "Disponible",
    OCC_MID: "A medio llenar",
    OCC_HIGH: "Casi llena / llena",
}

INSURANCE_DEFAULT = "PRIVADO"

# ---- Helpers de tiempo ------------------------------------------------------


def parse_time(value: str) -> dt.time:
    """Convierte 'HH:MM' a datetime.time."""
    h, m = value.split(":")
    return dt.time(int(h), int(m))


def to_hhmm(value: dt.time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def add_minutes(value: dt.time, minutes: int) -> dt.time:
    base = dt.datetime.combine(dt.date(2000, 1, 1), value)
    return (base + dt.timedelta(minutes=minutes)).time()


def generate_slot_times(start: str, end: str, interval: int) -> list[str]:
    """Devuelve las horas de cita entre start (incl.) y stop (excl.)."""
    t = parse_time(start)
    stop = parse_time(end)
    out: list[str] = []
    while t < stop:
        out.append(to_hhmm(t))
        t = add_minutes(t, interval)
    return out


def slots_for_windows(
    windows: Sequence[tuple[str, str]], interval: int
) -> list[str]:
    """Genera huecos de una ventana mañana + tarde."""
    out: list[str] = []
    for start, end in windows:
        if not start or not end:
            continue
        out.extend(generate_slot_times(start, end, interval))
    return sorted(set(out))


# ---- Validación de datos del paciente --------------------------------------


# Teléfono: caracteres típicos de un número de teléfono.
PHONE_RE = re.compile(r"^[\d\s\.\-\(\)\+]{5,25}$")
DIGITS_RE = re.compile(r"\d")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_patient_data(nombre: str, apellido1: str, apellido2: str,
                          telefono: str, email: str, seguro: str) -> list[str]:
    """Devuelve lista de errores (vacía si los datos son correctos)."""
    errors: list[str] = []
    if not nombre.strip():
        errors.append("El nombre es obligatorio.")
    if not apellido1.strip():
        errors.append("El primer apellido es obligatorio.")
    if not apellido2.strip():
        errors.append("El segundo apellido es obligatorio.")
    telefono_ok = bool(PHONE_RE.match(telefono or ""))
    if not telefono_ok:
        errors.append("El teléfono no es válido.")
    elif len(DIGITS_RE.findall(telefono)) != 9:
        errors.append("El teléfono debe tener exactamente 9 dígitos.")
    if not email or not email.strip():
        errors.append("El email es obligatorio.")
    elif not EMAIL_RE.match(email.strip()):
        errors.append("El email no es válido.")
    if not seguro or not seguro.strip():
        errors.append("Debe indicar la compañía de seguro o 'Privado'.")
    return errors


# ---- Ocupación del calendario -----------------------------------------


def occupancy_level(total_slots: int, booked: int) -> int:
    """Calcula el nivel de ocupación de un día dado.

    - OCC_NONE  si no hay agenda (total_slots == 0)
    - OCC_LOW   si se ha citado menos de un tercio
    - OCC_MID   si se citó al menos un tercio pero no llega a la mitad
    - OCC_HIGH  si se citó la mitad o más (hasta el total)
    """
    if total_slots <= 0:
        return OCC_NONE
    ratio = booked / total_slots
    if ratio >= 0.5:
        return OCC_HIGH
    if ratio >= 1 / 3:
        return OCC_MID
    return OCC_LOW


def color_for_level(level: int) -> str:
    return COLORS.get(level, COLORS[OCC_NONE])


# ---- Calendario mensual ----------------------------------------------


def first_day_grid(year: int, month: int) -> int:
    """Índice 0-6 (Lun=0) del primer día del mes."""
    return dt.date(year, month, 1).weekday()


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def build_month_grid(year: int, month: int) -> list[Optional[int]]:
    """Devuelve 42 celdas: los días del mes con None en celdas fuera del mes."""
    offset = first_day_grid(year, month)
    num = days_in_month(year, month)
    cells: list[Optional[int]] = [None] * offset
    cells += list(range(1, num + 1))
    remaining = 42 - offset - num
    cells += [None] * remaining
    return cells


def iter_weeks(year: int, month: int) -> list[list[Optional[int]]]:
    grid = build_month_grid(year, month)
    return [grid[i:i + 7] for i in range(0, 42, 7)]