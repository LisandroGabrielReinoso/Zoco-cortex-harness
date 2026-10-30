from datetime import date, datetime

from agente_zoco.memoria.conversacion import Conversacion, Seguimiento

OPORTUNIDADES_CERRADAS = {"COMPLETED", "CLOSED", "WON", "LOST"}


def decidir(evento: dict, conv: Conversacion, hoy: date | None = None) -> Seguimiento:
    hoy = hoy or fecha_del_evento(evento)
    oportunidad = evento.get("opportunity_id")
    estado = evento.get("opportunity_status", "OPEN")

    if estado in OPORTUNIDADES_CERRADAS:
        return Seguimiento(oportunidad, "CANCELAR", f"la oportunidad ya está cerrada ({estado})")
    if evento.get("customer_responded"):
        return Seguimiento(oportunidad, "CANCELAR", "el cliente ya respondió")
    if evento.get("opted_out"):
        return Seguimiento(oportunidad, "CANCELAR", "el cliente pidió no recibir mensajes")
    if conv.maquina.actual == "BLOCKED":
        return Seguimiento(oportunidad, "CANCELAR", "la conversación está bloqueada")
    if evento.get("pending_on") == "ZOCO":
        return Seguimiento(
            oportunidad, "TAREA_INTERNA", "Zoco le debe una respuesta al cliente",
            responsable=evento.get("responsible"),
        )

    acordada = evento.get("agreed_contact_date")
    if acordada and date.fromisoformat(acordada) > hoy:
        return Seguimiento(oportunidad, "REPROGRAMAR", f"el cliente pidió que lo contacten el {acordada}", fecha=acordada)
    if not evento.get("contact_allowed", False):
        return Seguimiento(oportunidad, "CANCELAR", "no hay permiso para contactar al cliente")
    if conv.maquina.actual == "HUMAN":
        return Seguimiento(
            oportunidad, "TAREA_INTERNA", "un operador tiene la conversación", responsable=conv.responsable
        )
    return Seguimiento(oportunidad, "CONTACTAR", "el seguimiento venció y se puede contactar al cliente")


def fecha_del_evento(evento: dict) -> date:
    if "timestamp" in evento:
        return datetime.fromisoformat(evento["timestamp"]).date()
    return date.today()
