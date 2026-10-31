from typing import NamedTuple


class Chequeo(NamedTuple):
    clave: str
    esperado: object
    obtenido: object

    @property
    def ok(self) -> bool:
        return self.esperado == self.obtenido


def obtener(clave: str, salida: dict):
    if clave == "finish_reason":
        return salida["finish_reason"]
    if clave == "max_steps":
        return salida["step_count"]
    if clave == "state_after_restart":
        return salida["state"]["conversation_mode"]
    if clave == "pending_action_retained":
        return salida["state"]["pending_action"] is not None
    return salida["effects"].get(clave)


def verificar(escenario: dict, salida: dict) -> list[Chequeo]:
    return [Chequeo(clave, esperado, obtener(clave, salida)) for clave, esperado in escenario["expected"].items()]
