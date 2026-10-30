#Eventos que llegan de Zoco Chat, traducidos a los eventos de la máquina de estados

from agente_zoco.agent import Agente, Respuesta
from agente_zoco.contexto import AccesoDenegado

EVENTOS = {
    "operator_took_over": ("operator_takeover", "operador"),
}


def aplicar(agente: Agente, evento: dict) -> Respuesta | None:
    if evento.get("tenant_id", agente.contexto.tenant_id) != agente.contexto.tenant_id:
        raise AccesoDenegado("el evento es de otra empresa")
    if evento.get("conversation_id", agente.conversacion) != agente.conversacion:
        raise ValueError("el evento es de otra conversación")
    if evento["type"] not in EVENTOS:
        raise ValueError(f"evento de Zoco Chat desconocido: {evento['type']}")
    nombre, actor = EVENTOS[evento["type"]]
    return agente.evento(nombre, actor, version=evento.get("version"))
