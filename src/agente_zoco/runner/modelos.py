#Modelos que puede usar el agente: el guionado (sin internet, para los escenarios) y OpenAI
#Los dos devuelven una Salida, así el agente no depende del proveedor

import json
from typing import NamedTuple

import openai

MODELO = "gpt-4.1-mini"


class Llamada(NamedTuple):
    id: str
    nombre: str
    argumentos: dict | None  # None si el modelo mandó algo que no es JSON


class Salida(NamedTuple):
    texto: str | None
    llamadas: list[Llamada]


class ErrorDelModelo(Exception):
    pass


class GuionTerminado(ErrorDelModelo):
    pass


class ModeloGuionado:
    def __init__(self, guion: list[dict]):
        self.guion = list(guion)
        self.paso = 0

    def generar(self, historial: list[dict], herramientas: list[dict]) -> Salida:
        if self.paso >= len(self.guion):
            raise GuionTerminado(f"el guion tiene {len(self.guion)} pasos y se pidió otro")
        paso = self.guion[self.paso]
        self.paso += 1
        if "tool" in paso:
            return Salida(None, [Llamada(f"call_{self.paso}", paso["tool"], paso.get("args", {}))])
        return Salida(paso["final"], [])


class ModeloOpenAI:
    def __init__(self, client, modelo: str = MODELO):
        self.client = client
        self.modelo = modelo

    def generar(self, historial: list[dict], herramientas: list[dict]) -> Salida:
        try:
            respuesta = self.client.responses.create(
                model=self.modelo,
                input=[a_openai(m) for m in historial],
                tools=herramientas,
            )
        except openai.APIError as error:
            raise ErrorDelModelo(type(error).__name__) from error
        llamadas = []
        for item in respuesta.output:
            if item.type != "function_call":
                continue
            try:
                argumentos = json.loads(item.arguments)
            except json.JSONDecodeError:
                argumentos = None
            llamadas.append(Llamada(item.call_id, item.name, argumentos))
        if llamadas:
            return Salida(None, llamadas)
        return Salida(respuesta.output_text, [])


ROLES = {"sistema": "system", "usuario": "user", "asistente": "assistant"}


def a_openai(mensaje: dict) -> dict:
    # del formato del historial al de la API de OpenAI
    rol = mensaje["rol"]
    if rol in ROLES:
        return {"role": ROLES[rol], "content": mensaje["texto"]}
    if rol == "llamada":
        return {
            "type": "function_call",
            "call_id": mensaje["id"],
            "name": mensaje["nombre"],
            "arguments": json.dumps(mensaje["argumentos"], ensure_ascii=False),
        }
    return {"type": "function_call_output", "call_id": mensaje["id"], "output": mensaje["texto"]}
