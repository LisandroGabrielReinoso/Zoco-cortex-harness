import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from agente_zoco.config import RAIZ

ARCHIVO_MEMORIA = RAIZ / "datos" / "harness.db"

TABLAS = """
CREATE TABLE IF NOT EXISTS conversaciones (
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    estado TEXT NOT NULL,
    version INTEGER NOT NULL,
    fuera_de_horario INTEGER NOT NULL,
    pendiente TEXT,
    confirmadas TEXT NOT NULL,
    borrador TEXT,
    revision INTEGER NOT NULL,
    actualizado TEXT NOT NULL,
    PRIMARY KEY (tenant_id, conversation_id)
);
CREATE TABLE IF NOT EXISTS mensajes (
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    orden INTEGER NOT NULL,
    mensaje TEXT NOT NULL,
    PRIMARY KEY (tenant_id, conversation_id, orden),
    FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversaciones (tenant_id, conversation_id)
);
"""


class ConflictoDeVersion(Exception):
    pass


class Control(NamedTuple):
    estado: str
    version: int
    revision: int


class Guardado(NamedTuple):
    estado: str
    version: int
    fuera_de_horario: bool
    pendiente: dict | None
    confirmadas: list[dict]
    borrador: dict | None
    mensajes: list[dict]
    revision: int | None = None


class Memoria:
    def __init__(self, archivo: Path = ARCHIVO_MEMORIA):
        self.archivo = archivo
        self.archivo.parent.mkdir(exist_ok=True)
        with closing(self._conectar()) as conexion:
            conexion.executescript(TABLAS)

    def _conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self.archivo)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")  # SQLite no controla las claves foráneas si no se activa
        return conexion

    def cargar(self, tenant_id: str, conversation_id: str) -> Guardado | None:
        clave = (tenant_id, conversation_id)
        with closing(self._conectar()) as conexion:
            fila = conexion.execute(
                "SELECT * FROM conversaciones WHERE tenant_id = ? AND conversation_id = ?", clave
            ).fetchone()
            if fila is None:
                return None
            mensajes = [
                json.loads(m["mensaje"])
                for m in conexion.execute(
                    "SELECT mensaje FROM mensajes WHERE tenant_id = ? AND conversation_id = ? ORDER BY orden", clave
                )
            ]
        return Guardado(
            estado=fila["estado"],
            version=fila["version"],
            fuera_de_horario=bool(fila["fuera_de_horario"]),
            pendiente=json.loads(fila["pendiente"]) if fila["pendiente"] else None,
            confirmadas=json.loads(fila["confirmadas"]),
            borrador=json.loads(fila["borrador"]) if fila["borrador"] else None,
            mensajes=mensajes,
            revision=fila["revision"],
        )

    def control(self, tenant_id: str, conversation_id: str) -> Control | None:
        with closing(self._conectar()) as conexion:
            fila = conexion.execute(
                "SELECT estado, version, revision FROM conversaciones WHERE tenant_id = ? AND conversation_id = ?",
                (tenant_id, conversation_id),
            ).fetchone()
        return None if fila is None else Control(fila["estado"], fila["version"], fila["revision"])

    def guardar(self, tenant_id: str, conversation_id: str, guardado: Guardado, desde: int) -> int:
        # solo guarda si nadie más escribió desde la revisión que se leyó; devuelve la revisión nueva
        revision = 0 if guardado.revision is None else guardado.revision + 1
        datos = (
            guardado.estado,
            guardado.version,
            int(guardado.fuera_de_horario),
            a_json(guardado.pendiente),
            json.dumps(guardado.confirmadas, ensure_ascii=False),
            a_json(guardado.borrador),
            revision,
            datetime.now(timezone.utc).isoformat(),
        )
        try:
            with closing(self._conectar()) as conexion, conexion:
                if guardado.revision is None:
                    conexion.execute(
                        "INSERT INTO conversaciones (tenant_id, conversation_id, estado, version, fuera_de_horario,"
                        " pendiente, confirmadas, borrador, revision, actualizado)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (tenant_id, conversation_id, *datos),
                    )
                else:
                    cursor = conexion.execute(
                        "UPDATE conversaciones SET estado = ?, version = ?, fuera_de_horario = ?, pendiente = ?,"
                        " confirmadas = ?, borrador = ?, revision = ?, actualizado = ?"
                        " WHERE tenant_id = ? AND conversation_id = ? AND revision = ?",
                        (*datos, tenant_id, conversation_id, guardado.revision),
                    )
                    if cursor.rowcount == 0:
                        raise ConflictoDeVersion(f"la conversación {conversation_id} cambió desde que se leyó")
                conexion.executemany(
                    "INSERT INTO mensajes VALUES (?, ?, ?, ?)",
                    [
                        (tenant_id, conversation_id, desde + i, json.dumps(m, ensure_ascii=False))
                        for i, m in enumerate(guardado.mensajes)
                    ],
                )
        except sqlite3.IntegrityError as error:
            raise ConflictoDeVersion(f"la conversación {conversation_id} cambió desde que se leyó") from error
        return revision


def a_json(valor) -> str | None:
    return None if valor is None else json.dumps(valor, ensure_ascii=False)
