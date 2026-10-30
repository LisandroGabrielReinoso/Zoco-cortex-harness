import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from agente_zoco.config import RAIZ
from agente_zoco.memoria.conversacion import Borrador, Conversacion, Seguimiento
from agente_zoco.politicas.confirmacion import AccionReclamo
from agente_zoco.politicas.maquina import MaquinaDeEstados

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
    responsable TEXT,
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
CREATE TABLE IF NOT EXISTS seguimientos (
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    orden INTEGER NOT NULL,
    opportunity_id TEXT,
    decision TEXT NOT NULL,
    motivo TEXT NOT NULL,
    fecha TEXT,
    responsable TEXT,
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

    def cargar(self, tenant_id: str, conversation_id: str) -> Conversacion | None:
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
            seguimientos = [
                Seguimiento(s["opportunity_id"], s["decision"], s["motivo"], s["fecha"], s["responsable"])
                for s in conexion.execute(
                    "SELECT * FROM seguimientos WHERE tenant_id = ? AND conversation_id = ? ORDER BY orden", clave
                )
            ]
        maquina = MaquinaDeEstados(fila["estado"])
        maquina.fuera_de_horario = bool(fila["fuera_de_horario"])
        return Conversacion(
            tenant_id,
            conversation_id,
            mensajes=mensajes,
            maquina=maquina,
            version=fila["version"],
            pendiente=AccionReclamo(**json.loads(fila["pendiente"])) if fila["pendiente"] else None,
            confirmadas=[AccionReclamo(**a) for a in json.loads(fila["confirmadas"])],
            borrador=Borrador(**json.loads(fila["borrador"])) if fila["borrador"] else None,
            responsable=fila["responsable"],
            seguimientos=seguimientos,
            revision=fila["revision"],
            guardados=len(mensajes),
            seguimientos_guardados=len(seguimientos),
        )

    def control(self, tenant_id: str, conversation_id: str) -> Control | None:
        with closing(self._conectar()) as conexion:
            fila = conexion.execute(
                "SELECT estado, version, revision FROM conversaciones WHERE tenant_id = ? AND conversation_id = ?",
                (tenant_id, conversation_id),
            ).fetchone()
        return None if fila is None else Control(fila["estado"], fila["version"], fila["revision"])

    def guardar(self, conv: Conversacion):
        # solo guarda si nadie más escribió desde la revisión que se leyó; los mensajes se agregan sin reescribir
        clave = (conv.tenant_id, conv.conversation_id)
        nuevos = conv.mensajes[conv.guardados:]
        seguimientos_nuevos = conv.seguimientos[conv.seguimientos_guardados:]
        revision = 0 if conv.revision is None else conv.revision + 1
        datos = (
            conv.maquina.actual,
            conv.version,
            int(conv.maquina.fuera_de_horario),
            a_json(asdict(conv.pendiente) if conv.pendiente else None),
            a_json([asdict(a) for a in conv.confirmadas]),
            a_json(conv.borrador._asdict() if conv.borrador else None),
            conv.responsable,
            revision,
            datetime.now(timezone.utc).isoformat(),
        )
        try:
            with closing(self._conectar()) as conexion, conexion:
                if conv.revision is None:
                    conexion.execute(
                        "INSERT INTO conversaciones (tenant_id, conversation_id, estado, version, fuera_de_horario,"
                        " pendiente, confirmadas, borrador, responsable, revision, actualizado)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (*clave, *datos),
                    )
                else:
                    cursor = conexion.execute(
                        "UPDATE conversaciones SET estado = ?, version = ?, fuera_de_horario = ?, pendiente = ?,"
                        " confirmadas = ?, borrador = ?, responsable = ?, revision = ?, actualizado = ?"
                        " WHERE tenant_id = ? AND conversation_id = ? AND revision = ?",
                        (*datos, *clave, conv.revision),
                    )
                    if cursor.rowcount == 0:
                        raise ConflictoDeVersion(f"la conversación {conv.conversation_id} cambió desde que se leyó")
                conexion.executemany(
                    "INSERT INTO mensajes VALUES (?, ?, ?, ?)",
                    [(*clave, conv.guardados + i, a_json(m)) for i, m in enumerate(nuevos)],
                )
                conexion.executemany(
                    "INSERT INTO seguimientos VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(*clave, conv.seguimientos_guardados + i, *s) for i, s in enumerate(seguimientos_nuevos)],
                )
        except sqlite3.IntegrityError as error:
            raise ConflictoDeVersion(f"la conversación {conv.conversation_id} cambió desde que se leyó") from error
        conv.revision = revision
        conv.guardados += len(nuevos)
        conv.seguimientos_guardados += len(seguimientos_nuevos)


def a_json(valor) -> str | None:
    return None if valor is None else json.dumps(valor, ensure_ascii=False)
