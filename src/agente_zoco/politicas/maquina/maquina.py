#Máquina de estados ia-humano: aplica δ, valida quién dispara cada evento y registra cada transición

from datetime import datetime
from typing import NamedTuple

from agente_zoco.politicas.maquina.estados import ESTADOS, Estado
from agente_zoco.politicas.maquina.transiciones import TRANSICIONES


class TransicionInvalida(Exception):
    pass

class Transicion(NamedTuple):
    anterior: str
    nuevo: str
    evento: str
    actor: str
    fecha: datetime

class MaquinaDeEstados:
    def __init__(self, inicial: str = "AUTO"):
        self.actual = inicial
        self.fuera_de_horario = False
        self.historial: list[Transicion] = []

    @property
    def estado(self) -> Estado:
        return ESTADOS[self.actual]

    def transicionar(self, evento: str, actor: str, fecha: datetime | None = None) -> Estado:
        # si algo no cierra se lanza el error antes de tocar el estado
        if (self.actual, evento) not in TRANSICIONES:
            raise TransicionInvalida(f"No hay transición desde {self.actual} con el evento {evento}.")
        nuevo, actores = TRANSICIONES[(self.actual, evento)]

        if actor not in actores:
            raise TransicionInvalida(f"El actor {actor} no puede disparar {evento} en {self.actual}.")
        if self.fuera_de_horario and nuevo in ("HUMAN", "SUGGEST"):
            raise TransicionInvalida(f"Fuera del horario de atención no hay operadores: {evento} no aplica.")
        if evento == "out_of_hours_started" and self.fuera_de_horario:
            raise TransicionInvalida("La conversación ya está fuera del horario de atención.")
        if evento == "out_of_hours_ended" and not self.fuera_de_horario:
            raise TransicionInvalida("La conversación no estaba fuera del horario de atención.")

        if evento == "out_of_hours_started":
            self.fuera_de_horario = True
        if evento == "out_of_hours_ended":
            self.fuera_de_horario = False

        self.historial.append(Transicion(self.actual, nuevo, evento, actor, fecha or datetime.now()))
        self.actual = nuevo
        return self.estado
