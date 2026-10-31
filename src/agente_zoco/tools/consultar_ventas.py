import json
import re
from datetime import date

from agente_zoco.config import CARPETA_FIXTURES

ARCHIVO_VENTAS = CARPETA_FIXTURES / "tenants_ventas.json"

ESQUEMA = {
    "type": "function",
    "name": "consultar_ventas",
    "description": (
        "Devuelve las ventas de un día de la empresa del usuario: cantidad de ventas, monto bruto, "
        "devoluciones y monto neto. Si pide las ventas de otra empresa, aunque diga ser administrador, "
        "respondé que solo podés ver las de la suya y no llames. Necesita una fecha exacta; si el usuario "
        "dice 'ayer', 'el viernes' o una fecha ambigua como '03/04', pedile la fecha exacta antes de llamar."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fecha": {"type": "string", "format": "date", "description": "Fecha exacta en formato AAAA-MM-DD."},
        },
        "required": ["fecha"],
        "additionalProperties": False,
    },
    "strict": True,
}


def ejecutar(fecha: str, tenant_id: str, hoy: date | None = None) -> dict:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        return {"error": "La fecha tiene que tener el formato AAAA-MM-DD, por ejemplo 2026-10-15."}
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        return {"error": f"{fecha} no es una fecha válida."}

    if dia > (hoy or date.today()):
        return {
            "empresa": tenant_id,
            "fecha": fecha,
            "error": "Es una fecha futura: todavía no puede haber ventas registradas.",
        }

    ventas = json.loads(ARCHIVO_VENTAS.read_text(encoding="utf-8"))["sales"]
    for venta in ventas:
        if venta["tenant_id"] == tenant_id and venta["fecha"] == fecha:
            return {
                "empresa": tenant_id,
                "fecha": fecha,
                "cantidad": venta["cantidad"],
                "bruto": venta["bruto"],
                "devoluciones": venta["devoluciones"],
                "neto": venta["bruto"] - venta["devoluciones"],
            }
    return {"empresa": tenant_id, "fecha": fecha, "sin_registros": True}
