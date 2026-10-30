#Una corrida es lo que hace el agente con un mensaje: pasos, eventos y por qué terminó

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

MOTIVOS = ["COMPLETED", "BLOCKED", "NEEDS_HUMAN", "LIMIT_REACHED", "FAILED"]


def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Corrida:
    def __init__(self, conversation_id: str):
        self.run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.conversation_id = conversation_id
        self.inicio = time.monotonic()
        self.pasos = 0
        self.motivo = None
        self.detalle = {}
        self.eventos = []

    def evento(self, tipo: str, **datos):
        self.eventos.append({"type": tipo, "timestamp": ahora(), **datos})

    def terminar(self, motivo: str, **detalle):
        # vale el primer motivo: si se cortó por límite, después no puede quedar como COMPLETED
        if self.motivo is not None:
            return
        if motivo not in MOTIVOS:
            raise ValueError(f"motivo de cierre desconocido: {motivo}")
        self.motivo = motivo
        self.detalle = detalle

    def cerrar(self):
        # último evento de la corrida
        self.evento("run_finished", finish_reason=self.motivo, step_count=self.pasos,
                    duration_ms=self.ms_transcurridos(), **self.detalle)

    def ms_transcurridos(self) -> int:
        return int((time.monotonic() - self.inicio) * 1000)


def con_timeout(funcion, segundos: float):
    # corre la función en otro hilo y espera como máximo esos segundos; si no termina tira TimeoutError
    ejecutor = ThreadPoolExecutor(max_workers=1)
    futuro = ejecutor.submit(funcion)
    try:
        return futuro.result(timeout=segundos)
    finally:
        ejecutor.shutdown(wait=False)
