#Herramienta crear_reclamo: guarda reclamos en datos/reclamos.db
#El modelo solo la propone; el agente registra después de que el usuario confirma (ver politicas.py)

import hashlib
import sqlite3
from contextlib import closing

from agente_zoco.config import RAIZ

ARCHIVO_RECLAMOS = RAIZ / "datos" / "reclamos.db"
CATEGORIAS = ["PAGO", "ENTRADA", "LIQUIDACION", "ACCESO", "OTROS"]  # categorías de DOC-11

ESQUEMA = {
    "type": "function",
    "name": "crear_reclamo",
    "description": (
        "Registra un reclamo del comercio. El sistema le muestra al usuario el motivo y la descripción "
        "y le pide confirmación antes de guardarlo: no digas que el reclamo está creado hasta que el "
        "sistema lo confirme con un número REC-."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "motivo": {
                "type": "string",
                "description": f"Motivo breve del reclamo. Si encaja, usá una categoría: {', '.join(CATEGORIAS)}.",
            },
            "descripcion": {"type": "string", "description": "Qué pasó, con las palabras del usuario."},
            "operation_id": {
                "type": "string",
                "description": "Identificador de la operación. Si no lo tenés, no lo mandes: lo genera el sistema.",
            },
        },
        "required": ["motivo", "descripcion"],
        "additionalProperties": False,
    },
}


def ejecutar(motivo: str, descripcion: str, tenant_id: str, operation_id: str | None = None) -> dict:
    # nunca registra: guardar un reclamo necesita la confirmación del usuario, que maneja el agente
    return {"error": "El reclamo no se registró: falta la confirmación del usuario."}


def operation_id_de(tenant_id: str, conversacion: str, motivo: str, descripcion: str) -> str:
    # mismo reclamo en la misma conversación y empresa = mismo operation_id
    texto = f"{tenant_id}\n{conversacion}\n{motivo}\n{descripcion}"
    return "op_" + hashlib.sha256(texto.encode("utf-8")).hexdigest()[:24]


def conectar() -> sqlite3.Connection:
    ARCHIVO_RECLAMOS.parent.mkdir(exist_ok=True)
    conexion = sqlite3.connect(ARCHIVO_RECLAMOS)
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        "CREATE TABLE IF NOT EXISTS reclamos ("
        " numero INTEGER PRIMARY KEY AUTOINCREMENT,"
        " tenant_id TEXT NOT NULL,"
        " operation_id TEXT NOT NULL,"
        " motivo TEXT NOT NULL,"
        " descripcion TEXT NOT NULL,"
        " UNIQUE (tenant_id, operation_id))"
    )
    return conexion


def como_dict(fila: sqlite3.Row) -> dict:
    return {
        "id": f"REC-{fila['numero']:06d}",
        "tenant_id": fila["tenant_id"],
        "operation_id": fila["operation_id"],
        "motivo": fila["motivo"],
        "descripcion": fila["descripcion"],
    }


def registrar(tenant_id: str, motivo: str, descripcion: str, operation_id: str) -> tuple[str, bool]:
    # devuelve (id, nuevo); si el operation_id ya estaba en esa empresa, devuelve el mismo id sin guardar otro
    with closing(conectar()) as conexion, conexion:
        cursor = conexion.execute(
            "INSERT INTO reclamos (tenant_id, operation_id, motivo, descripcion) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (tenant_id, operation_id) DO NOTHING",
            (tenant_id, operation_id, motivo, descripcion),
        )
        nuevo = cursor.rowcount == 1
        fila = conexion.execute(
            "SELECT * FROM reclamos WHERE tenant_id = ? AND operation_id = ?", (tenant_id, operation_id)
        ).fetchone()

    if (fila["motivo"], fila["descripcion"]) != (motivo, descripcion):
        raise ValueError(f"el operation_id {operation_id} ya se usó con otros datos")
    return como_dict(fila)["id"], nuevo


def consultar(tenant_id: str, operation_id: str) -> dict | None:
    with closing(conectar()) as conexion:
        fila = conexion.execute(
            "SELECT * FROM reclamos WHERE tenant_id = ? AND operation_id = ?", (tenant_id, operation_id)
        ).fetchone()
    return None if fila is None else como_dict(fila)


def listar() -> list[dict]:
    with closing(conectar()) as conexion:
        return [como_dict(f) for f in conexion.execute("SELECT * FROM reclamos ORDER BY numero")]
