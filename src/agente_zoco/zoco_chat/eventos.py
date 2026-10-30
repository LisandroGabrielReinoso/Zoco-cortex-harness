#Eventos que llegan de Zoco Chat, traducidos a los eventos de la máquina de estados

from datetime import date

from agente_zoco.memoria.conversacion import Seguimiento
from agente_zoco.politicas.contexto import AccesoDenegado
from agente_zoco.runner.agent import Agente
from agente_zoco.zoco_chat.ficha import Ficha, armar_ficha
from agente_zoco.zoco_chat.seguimientos import decidir

EVENTOS = {
    "operator_took_over": ("operator_takeover", "operador"),
}


def aplicar(agente: Agente, evento: dict, hoy: date | None = None) -> Ficha | Seguimiento:
    if evento.get("tenant_id", agente.contexto.tenant_id) != agente.contexto.tenant_id:
        raise AccesoDenegado("el evento es de otra empresa")
    if evento.get("conversation_id", agente.conv.conversation_id) != agente.conv.conversation_id:
        raise ValueError("el evento es de otra conversación")

    if evento["type"] == "followup_due":
        return agente.registrar_seguimiento(lambda conv: decidir(evento, conv, hoy))
    if evento["type"] not in EVENTOS:
        raise ValueError(f"evento de Zoco Chat desconocido: {evento['type']}")
    nombre, actor = EVENTOS[evento["type"]]
    agente.evento(nombre, actor, version=evento.get("version"), responsable=evento.get("actor"))
    return armar_ficha(agente.conv)
