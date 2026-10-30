#Estado de una conversación: lo que se guarda en la base y se recupera después de reiniciar

from dataclasses import dataclass, field
from typing import NamedTuple

from agente_zoco.maquina import MaquinaDeEstados
from agente_zoco.politicas import AccionReclamo


class Borrador(NamedTuple):
    texto: str  # lo que ve el operador antes de aprobar
    registra_reclamo: bool  # si al aprobarlo se registra el reclamo pendiente


@dataclass
class Conversacion:
    tenant_id: str
    conversation_id: str
    mensajes: list[dict] = field(default_factory=list)
    maquina: MaquinaDeEstados = field(default_factory=MaquinaDeEstados)
    version: int = 0
    pendiente: AccionReclamo | None = None  # reclamo propuesto por el modelo, esperando el "sí" del usuario
    confirmadas: list[AccionReclamo] = field(default_factory=list)  # escrituras confirmadas con estos datos exactos
    borrador: Borrador | None = None  # en SUGGEST, la respuesta que espera la aprobación del operador
    revision: int | None = None
    guardados: int = 0

    def ventana(self, tamano: int) -> list[dict]:
        desde = max(0, len(self.mensajes) - tamano)
        usuarios = [i for i, m in enumerate(self.mensajes) if m["rol"] == "usuario"]
        siguientes = [i for i in usuarios if i >= desde]
        if siguientes:
            desde = siguientes[0]
        elif usuarios:
            desde = usuarios[-1]
        return self.mensajes[desde:]
