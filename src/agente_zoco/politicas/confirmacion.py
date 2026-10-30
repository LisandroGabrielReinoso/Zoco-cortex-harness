#Guardas de crear_reclamo (reglas 2 y 3 de la consigna):
#el modelo propone el reclamo, el agente muestra los datos exactos y solo registra con un "sí" explícito

import re
import unicodedata
from dataclasses import dataclass

CONFIRMACIONES = {"si", "si confirmo", "confirmo", "dale", "si dale", "ok", "de acuerdo", "correcto"}
NEGATIVAS = {"no", "no gracias", "cancelar", "cancela"}


@dataclass(frozen=True)
class AccionReclamo:
    motivo: str
    descripcion: str
    operation_id: str


def normalizar_respuesta(texto: str) -> str:
    # "¡Sí!" -> "si"; "Sí, confirmo." -> "si confirmo"
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z]+", sin_tildes))


def es_confirmacion(texto: str) -> bool:
    # estricto: "sí, pero cambiá la descripción" no es una confirmación
    return normalizar_respuesta(texto) in CONFIRMACIONES


def es_negativa(texto: str) -> bool:
    return normalizar_respuesta(texto) in NEGATIVAS


def pedir_confirmacion(pendiente: AccionReclamo) -> str:
    # lo arma el código y no el modelo: el usuario confirma exactamente lo que se va a guardar
    return (
        "Voy a registrar este reclamo:\n"
        f"  Motivo: {pendiente.motivo}\n"
        f"  Descripción: {pendiente.descripcion}\n"
        "¿Confirmás? (sí/no)"
    )
