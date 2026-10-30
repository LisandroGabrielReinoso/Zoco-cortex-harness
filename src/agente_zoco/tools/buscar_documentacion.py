from agente_zoco.buscador import Buscador

ESQUEMA = {
    "type": "function",
    "name": "buscar_documentacion",
    "description": (
        "Busca en la documentación de ZocoTickets (planes, tarifas, liquidaciones, eventos, entradas, "
        "devoluciones, QR, reclamos). Devuelve fragmentos con el ID del documento y su vigencia. "
        "Si la pregunta es sobre un mes concreto, incluí el mes y el año en la consulta (ej. 'julio de 2026')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "consulta": {"type": "string", "description": "La pregunta o el tema a buscar, en español."},
        },
        "required": ["consulta"],
        "additionalProperties": False,
    },
    "strict": True,
}

buscador = None


def obtener_buscador() -> Buscador:
    global buscador
    if buscador is None:
        buscador = Buscador()
    return buscador


def ejecutar(consulta: str, tenant_id: str) -> dict:
    # la documentación es la del producto, la misma para todas las empresas
    fragmentos, modo = obtener_buscador().buscar(consulta, k=3)
    return {
        "modo": modo,
        "fragmentos": [
            {
                "doc_id": c.doc_id,
                "titulo": c.documento.titulo,
                "tipo": c.documento.tipo,
                "vigencia_desde": c.documento.vigencia_desde.isoformat(),
                "vigencia_hasta": c.documento.vigencia_hasta.isoformat(),
                "texto": c.texto,
            }
            for c in fragmentos
        ]
    }
