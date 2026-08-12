"""Capa de servicios: une core.py (lógica) con storage.py (persistencia)."""

from __future__ import annotations

import calendar
import datetime as dt

import core
from storage import Repo

# Semilla por defecto: 6 médicos de distintas especialidades.
SEED_MEDICOS = [
    ("Dra. Lucía Fernández", "Medicina de Familia", 15),
    ("Dr. Carlos Gómez", "Pediatría", 20),
    ("Dra. Marta Ruiz", "Dermatología", 30),
    ("Dr. Javier Torres", "Medicina Interna", 20),
    ("Dra. Elena García", "Psiquiatría", 45),
    ("Dr. Andrés López", "Medicina General", 15),
]

# Horario por defecto: lunes a viernes, mañana 9:00-14:00 y tarde 16:00-20:00.
DEFAULT_BLOQUES = [
    (9 * 60, 14 * 60),      # mañana  09:00-14:00
    (16 * 60, 20 * 60),     # tarde   16:00-20:00
]

DEFAULT_DAYS = [0, 1, 2, 3, 4]  # lunes a viernes

DEFAULT_INT = 20


def seed_medicos(repo: Repo) -> None:
    """Crea los 6 médicos iniciales si no existen y fija horario semanal."""
    if repo.get_medicos():
        return
    for nombre, especialidad, intervalo in SEED_MEDICOS:
        mid = repo.add_medico(nombre, especialidad, intervalo)
        repo.set_horarios(mid, {d: DEFAULT_BLOQUES for d in DEFAULT_DAYS})


# ---- Horario --------------------------------------------------------


def ventanas_dia(fecha: dt.date, medico_id: int, repo: Repo) -> list[tuple[int, int]]:
    """Ventanas (inicio, fin) en minutos del día de la semana de `fecha`."""
    if not repo.medico_atiende(medico_id, fecha.weekday()):
        return []
    return [
        (b["inicio"], b["fin"])
        for b in repo.get_horarios(medico_id)
        if b["weekday"] == fecha.weekday()
    ]


def slots_dia(ventanas: list[tuple[int, int]], interval: int) -> list[str]:
    """Genera los horarios HH:MM de un día a partir de sus ventanas."""
    total: list[str] = []
    for inicio, fin in ventanas:
        t = inicio
        while t < fin:
            total.append(f"{t // 60:02d}:{t % 60:02d}")
            t += interval
    return sorted(set(total))


def horarios_map(medico_id: int, repo: Repo) -> dict[int, list[list[int]]]:
    """Horario semanal: {weekday: [[min_inicio, min_fin], ...]}."""
    out: dict[int, list[list[int]]] = {}
    for b in repo.get_horarios(medico_id):
        out.setdefault(b["weekday"], []).append([b["inicio"], b["fin"]])
    return out


def slots_disponibles(fecha: dt.date, medico_id: int, repo: Repo,
                      hora_actual: dt.time | None = None) -> list[str]:
    """Huecos libres de un médico en una fecha (excluye horas pasadas)."""
    medico = repo.get_medico(medico_id)
    if medico is None:
        return []
    interval = medico["intervalo_minutes"]
    ventanas = ventanas_dia(fecha, medico_id, repo)
    if not ventanas:
        return []
    horas = slots_dia(ventanas, interval)
    ocupadas = {c["hora"] for c in repo.get_citas_medico_fecha(
        medico_id, fecha.isoformat())}
    libres = [h for h in horas if h not in ocupadas]
    if hora_actual is not None:
        actual = f"{hora_actual.hour:02d}:{hora_actual.minute:02d}"
        libres = [h for h in libres if h >= actual]
    return libres


# ---- Calendario ----------------------------------------------------------


def medicos_activos(fecha: dt.date, repo: Repo) -> list:
    """Médicos que atienden en ese día de la semana."""
    return [
        m for m in repo.get_medicos()
        if repo.medico_atiende(m["id"], fecha.weekday())
    ]


def resumen_dia(fecha: dt.date, repo: Repo) -> dict:
    """Resumen de un día: total de huecos, citados y nivel de ocupación."""
    activos = medicos_activos(fecha, repo)
    total_slots = 0
    citados = len(repo.get_citas_fecha(fecha.isoformat()))
    for med in activos:
        ventanas = ventanas_dia(fecha, med["id"], repo)
        total_slots += len(slots_dia(ventanas, med["intervalo_minutes"]))
    level = core.occupancy_level(total_slots, citados)
    return {
        "total_slots": total_slots,
        "citados": citados,
        "level": level,
        "color": core.color_for_level(level),
        "label": core.OCC_LABELS[level],
    }


def ocupacion_mes(anyo: int, mes: int, repo: Repo) -> dict[int, dict]:
    """Nivel de ocupación por día del mes para pintar el calendario."""
    out: dict[int, dict] = {}
    for dia in range(1, calendar.monthrange(anyo, mes)[1] + 1):
        out[dia] = resumen_dia(dt.date(anyo, mes, dia), repo)
    return out


# ---- Impresión / exportación de la agenda ----------------------------------


def agenda_csv(citas) -> bytes:
    """Listado en CSV (';' + BOM) que Excel abre directamente."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["Hora", "Apellido 1", "Apellido 2", "Nombre", "Sociedad",
                "Teléfono", "Email", "Código"])
    for c in citas:
        w.writerow([c["hora"], c["apellido1"], c["apellido2"], c["nombre"],
                    c["seguro"], c["telefono"], c["email"] or "",
                    c["codigo"]])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def agenda_tabla_html(citas) -> str:
    """Tabla compacta imprimible: una línea por paciente."""
    filas = "".join(
        f"<tr><td>{c['hora']}</td>"
        f"<td>{c['apellido1']} {c['apellido2']}, {c['nombre']}</td>"
        f"<td>{c['seguro']}</td>"
        f"<td>{c['telefono']}</td></tr>"
        for c in citas)
    return (
        "<style>"
        "table.agenda { border-collapse:collapse; width:100%; "
        "font-size:0.9rem; }"
        "table.agenda th, table.agenda td { border:1px solid #9ca3af; "
        "padding:4px 8px; text-align:left; }"
        "table.agenda th { background:#e5e7eb; }"
        "</style>"
        "<table class='agenda'>"
        "<thead><tr><th>Hora</th><th>Paciente</th><th>Sociedad</th>"
        "<th>Teléfono</th></tr></thead>"
        f"<tbody>{filas}</tbody></table>"
    )