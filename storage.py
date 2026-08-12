"""Capa de persistencia en SQLite para la aplicación de citas médicas.

Modelo:
  - medicos: profesionales con intervalo entre citas.
  - horario_semanal: ventanas (inicio, fin) por día de la semana (0=Lun..6=Dom).
    Un médico puede tener dos ventanas por día (mañana y tarde).
  - citas: las reservas.
"""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

DB_PATH = Path(os.environ.get(
    "CITAS_DB_PATH",
    Path(__file__).parent / "data" / "citas.db"))


def default_db_path() -> Path:
    """Ruta por defecto de la base, leída desde el entorno en cada llamada."""
    return Path(os.environ.get(
        "CITAS_DB_PATH",
        Path(__file__).parent / "data" / "citas.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    especialidad TEXT NOT NULL DEFAULT '',
    intervalo_minutes INTEGER NOT NULL DEFAULT 20
);

CREATE TABLE IF NOT EXISTS horarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medico_id INTEGER NOT NULL REFERENCES medicos(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL,             -- 0=Lunes .. 6=Domingo
    inicio INTEGER NOT NULL,              -- minutos desde 00:00
    fin INTEGER NOT NULL,
    UNIQUE(medico_id, weekday, inicio)
);

CREATE TABLE IF NOT EXISTS citas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    medico_id INTEGER NOT NULL REFERENCES medicos(id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,                  -- YYYY-MM-DD
    hora TEXT NOT NULL,                   -- HH:MM
    tipo TEXT NOT NULL,                   -- 'web' | 'telefono'
    nombre TEXT NOT NULL,
    apellido1 TEXT NOT NULL,
    apellido2 TEXT NOT NULL,
    telefono TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    seguro TEXT NOT NULL,
    creada TEXT NOT NULL,                 -- timestamp ISO
    UNIQUE(medico_id, fecha, hora)
);
"""


def _locked(fn):
    """Serializa el acceso a la conexión compartida entre hilos."""
    from functools import wraps

    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        lock = getattr(self, "_lock")
        with lock:
            return fn(self, *args, **kwargs)

    return wrapper


class Repo:
    """Acceso a base de datos SQLite."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __init__(self, path: str | None = None):
        if path is None:
            path = default_db_path()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: el conector se comparte entre sesiones de
        # Streamlit (cada sesión corre en un hilo distinto). Las escrituras
        # usan transacciones cortas dentro del mismo método.
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    @_locked
    def close(self):
        self.conn.close()

    def _migrate(self) -> None:
        """Añade columnas nuevas a bases de datos creadas con esquemas previos."""
        cols = [r["name"] for r in
                self.conn.execute("PRAGMA table_info(citas)").fetchall()]
        if "email" not in cols:
            self.conn.execute(
                "ALTER TABLE citas ADD COLUMN email TEXT NOT NULL DEFAULT ''")

    # ---- médicos -----------------------------------------------------
    def get_medicos(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM medicos ORDER BY id"
        ).fetchall()

    @_locked
    def get_medico(self, medico_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM medicos WHERE id = ?", (medico_id,)
        ).fetchone()

    @_locked
    def add_medico(self, nombre: str, especialidad: str,
                   intervalo_minutes: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO medicos (nombre, especialidad, intervalo_minutes) "
            "VALUES (?, ?, ?)",
            (nombre, especialidad, int(intervalo_minutes)),
        )
        self.conn.commit()
        return cur.lastrowid

    @_locked
    def update_medico(self, medico_id: int, nombre: str, especialidad: str,
                      intervalo_minutes: int) -> None:
        self.conn.execute(
            "UPDATE medicos SET nombre = ?, especialidad = ?, "
            "intervalo_minutes = ? WHERE id = ?",
            (nombre, especialidad, int(intervalo_minutes), medico_id),
        )
        self.conn.commit()

    @_locked
    def delete_medico(self, medico_id: int) -> None:
        self.conn.execute("DELETE FROM citas WHERE medico_id = ?", (medico_id,))
        self.conn.execute("DELETE FROM horarios WHERE medico_id = ?", (medico_id,))
        self.conn.execute("DELETE FROM medicos WHERE id = ?", (medico_id,))
        self.conn.commit()

    # ---- horario semanal ----------------------------------------------
    @_locked
    def get_horarios(self, medico_id: int) -> list[sqlite3.Row]:
        """Ventanas del médico ordenadas por día de la semana e inicio."""
        return self.conn.execute(
            "SELECT * FROM horarios WHERE medico_id = ? "
            "ORDER BY weekday, inicio",
            (medico_id,),
        ).fetchall()

    @_locked
    def set_horarios(self, medico_id: int, ventanas_semana) -> None:
        """Sobrescribe el horario semanal de un médico.

        ventanas_semana: dict {weekday: [(inicio, fin), ...]}. Cada tupla es
        una ventana de atención (mañana, tarde).
        """
        self.conn.execute("DELETE FROM horarios WHERE medico_id = ?", (medico_id,))
        for weekday, ventanas in ventanas_semana.items():
            for inicio, fin in ventanas:
                if inicio is None or fin is None or fin <= inicio:
                    continue
                self.conn.execute(
                    "INSERT INTO horarios (medico_id, weekday, inicio, fin) "
                    "VALUES (?, ?, ?, ?)",
                    (medico_id, int(weekday), int(inicio), int(fin)),
                )
        self.conn.commit()

    @_locked
    def medico_atiende(self, medico_id: int, weekday: int) -> bool:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM horarios WHERE medico_id = ? "
            "AND weekday = ?",
            (medico_id, weekday),
        ).fetchone()
        return row["n"] > 0

    # ---- citas ----------------------------------------------------------
    @_locked
    def add_cita(self, medico_id: int, fecha: str, hora: str, tipo: str,
                 nombre: str, apellido1: str, apellido2: str,
                 telefono: str, email: str, seguro: str) -> str:
        codigo = f"C{dt.datetime.now().strftime('%Y%m%d%H%M%S')}{medico_id}"
        while self.get_cita_by_codigo(codigo):
            codigo += "x"
        try:
            self.conn.execute(
                "INSERT INTO citas (codigo, medico_id, fecha, hora, tipo, "
                "nombre, apellido1, apellido2, telefono, email, seguro, "
                "creada) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (codigo, medico_id, fecha, hora, tipo, nombre, apellido1,
                 apellido2, telefono, email, seguro,
                 dt.datetime.now().isoformat()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Misma hora y mismo médico ya reservada (UNIQUE).
            raise RuntimeError(
                "Esa hora ya no está disponible (doble reserva).")
        return codigo

    @_locked
    def get_cita_by_codigo(self, codigo: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM citas WHERE codigo = ?", (codigo,)
        ).fetchone()

    @_locked
    def get_cita_detalle(self, codigo: str) -> Optional[sqlite3.Row]:
        """Cita con datos del médico, para la vista pública de 'mi cita'."""
        return self.conn.execute(
            "SELECT c.*, m.nombre AS medico_nombre, m.especialidad AS "
            "medico_especialidad FROM citas c JOIN medicos m ON m.id = "
            "c.medico_id WHERE c.codigo = ?", (codigo,),
        ).fetchone()

    @_locked
    def get_citas_fecha(self, fecha: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT c.*, m.nombre AS medico_nombre, m.especialidad AS "
            "medico_especialidad FROM citas c JOIN medicos m ON "
            "m.id = c.medico_id WHERE c.fecha = ? ORDER BY c.hora",
            (fecha,),
        ).fetchall()

    @_locked
    def get_citas_medico_fecha(self, medico_id: int,
                               fecha: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM citas WHERE medico_id = ? AND fecha = ? "
            "ORDER BY hora",
            (medico_id, fecha),
        ).fetchall()

    def get_todas_citas(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT c.*, m.nombre AS medico_nombre, m.especialidad AS "
            "medico_especialidad FROM citas c JOIN medicos m ON m.id = "
            "c.medico_id ORDER BY c.fecha DESC, c.hora DESC"
        ).fetchall()

    @_locked
    def cancelar_cita(self, codigo: str) -> bool:
        cur = self.conn.execute("DELETE FROM citas WHERE codigo = ?", (codigo,))
        self.conn.commit()
        return cur.rowcount > 0