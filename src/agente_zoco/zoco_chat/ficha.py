from dataclasses import asdict
from typing import NamedTuple

from agente_zoco.memoria.conversacion import Conversacion

class Ficha(NamedTuple):
    consulta: str | None
    herramienta: dict | None
    pendiente: dict | None
    ultima_respuesta: str | None
    responsable: str | None

def armar_ficha(conv: Conversacion) -> Ficha:
    return Ficha(
        consulta=ultimo_texto(conv.mensajes, "usuario"),
        herramienta=ultima_herramienta(conv.mensajes),
        pendiente=asdict(conv.pendiente) if conv.pendiente else None,
        ultima_respuesta=ultimo_texto(conv.mensajes, "asistente"),
        responsable=conv.responsable,
    )

def ultimo_texto(mensajes: list[dict], rol: str) -> str | None:
    return next((m["texto"] for m in reversed(mensajes) if m["rol"] == rol), None)


def ultima_herramienta(mensajes: list[dict]) -> dict | None:
    for i in range(len(mensajes) - 1, -1, -1):
        llamada = mensajes[i]
        if llamada["rol"] != "llamada":
            continue
        resultado = next(
            (m["texto"] for m in mensajes[i + 1:] if m["rol"] == "resultado" and m["id"] == llamada["id"]), None
        )
        return {"nombre": llamada["nombre"], "argumentos": llamada["argumentos"], "resultado": resultado}
    return None
