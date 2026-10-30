#Estados de la conversación y qué puede hacer el agente en cada uno

from typing import NamedTuple

TODAS = frozenset({"buscar_documentacion", "consultar_ventas", "crear_reclamo"})
FRANJA_HUMANA = "de lunes a viernes de 9 a 18 h"  # la consigna no la define (ver SPEC_REVIEW.md)


class Estado(NamedTuple):
    nombre: str
    respuesta: str  # enviar, borrador (la aprueba un operador) o ninguna
    herramientas: frozenset  # las que el modelo puede usar en este estado


AUTO = Estado("AUTO", "enviar", TODAS)
# en SUGGEST todo es borrador, también el registro de un reclamo (reglas 2 y 6)
SUGGEST = Estado("SUGGEST", "borrador", TODAS)
HUMAN = Estado("HUMAN", "ninguna", frozenset())  
BLOCKED = Estado("BLOCKED", "ninguna", frozenset())

ESTADOS = {e.nombre: e for e in (AUTO, SUGGEST, HUMAN, BLOCKED)}
