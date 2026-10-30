#Fallas simuladas: una secuencia fija por herramienta, o al azar con probabilidad TOOL_FAILURE_RATE

import os
import random

TIPOS = ["TIMEOUT", "INVALID_REQUEST", "COMMITTED_BUT_TIMEOUT"]


class PedidoInvalido(Exception):
    pass


def tasa_de_falla() -> float:
    try:
        return float(os.getenv("TOOL_FAILURE_RATE", "0"))
    except ValueError:
        return 0.0  # si la variable tiene cualquier cosa, no se simulan fallas


class Fallas:
    def __init__(self, secuencias: dict[str, list[str]] | None = None, tasa: float | None = None):
        self.secuencias = {herramienta: list(s) for herramienta, s in (secuencias or {}).items()}
        self.tasa = tasa_de_falla() if tasa is None else tasa

    def siguiente(self, herramienta: str) -> str:
        cola = self.secuencias.get(herramienta)
        if cola:
            return cola.pop(0)
        if random.random() < self.tasa:
            return random.choice(TIPOS)
        return "SUCCESS"

    def ejecutar(self, herramienta: str, funcion):
        falla = self.siguiente(herramienta)
        if falla == "TIMEOUT":
            raise TimeoutError("timeout simulado")
        if falla == "INVALID_REQUEST":
            raise PedidoInvalido("pedido inválido simulado")
        resultado = funcion()
        if falla == "COMMITTED_BUT_TIMEOUT":
            raise TimeoutError("timeout simulado después de ejecutar")
        return resultado
