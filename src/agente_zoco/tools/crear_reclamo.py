#Herramienta crear_reclamo: guarda reclamos en datos/reclamos.json
#El modelo solo la propone; el agente registra después de que el usuario confirma (ver politicas.py)

import hashlib
import json
from pathlib import Path

from agente_zoco.tools.fallas import sortear_falla

ARCHIVO_RECLAMOS = Path(__file__).parents[3] / "datos" / "reclamos.json"
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


def registrar(tenant_id: str, motivo: str, descripcion: str, operation_id: str) -> tuple[str, bool]:
    # devuelve (id, nuevo); si el operation_id ya estaba en esa empresa, devuelve el mismo id sin guardar otro
    falla = sortear_falla()
    if falla == "error":
        raise RuntimeError("error simulado")

    reclamos = []
    if ARCHIVO_RECLAMOS.exists():
        reclamos = json.loads(ARCHIVO_RECLAMOS.read_text(encoding="utf-8"))
    for reclamo in reclamos:
        if reclamo["tenant_id"] == tenant_id and reclamo["operation_id"] == operation_id:
            if (reclamo["motivo"], reclamo["descripcion"]) != (motivo, descripcion):
                raise ValueError(f"el operation_id {operation_id} ya se usó con otros datos")
            return reclamo["id"], False

    nuevo = {
        "id": f"REC-{len(reclamos) + 1:06d}",
        "tenant_id": tenant_id,
        "operation_id": operation_id,
        "motivo": motivo,
        "descripcion": descripcion,
    }
    reclamos.append(nuevo)
    ARCHIVO_RECLAMOS.write_text(json.dumps(reclamos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if falla == "timeout":
        # el caso más traicionero: el reclamo quedó guardado pero la respuesta se perdió
        raise TimeoutError("timeout simulado")
    return nuevo["id"], True
