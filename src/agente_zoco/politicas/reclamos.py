import json

from agente_zoco.memoria.conversacion import Conversacion
from agente_zoco.politicas import confirmacion
from agente_zoco.politicas.confirmacion import AccionReclamo
from agente_zoco.runner.corrida import Corrida
from agente_zoco.runner.ejecutor import Ejecutor
from agente_zoco.tools import crear_reclamo


class Reclamos:
    def __init__(self, ejecutor: Ejecutor):
        self.ejecutor = ejecutor

    def accion(self, conv: Conversacion, argumentos: dict) -> AccionReclamo:
        operation_id = argumentos.get("operation_id") or crear_reclamo.operation_id_de(
            conv.tenant_id, conv.conversation_id, argumentos["motivo"], argumentos["descripcion"]
        )
        return AccionReclamo(argumentos["motivo"], argumentos["descripcion"], operation_id)

    def confirmar(self, conv: Conversacion, argumentos: dict):
        conv.confirmadas.append(self.accion(conv, argumentos))

    def proponer(self, conv: Conversacion, argumentos: dict, corrida: Corrida) -> str:
        accion = self.accion(conv, argumentos)
        if accion in conv.confirmadas:
            # ya confirmada con estos datos exactos: se registra, y si se repite el operation_id no se duplica
            registro = self.ejecutor.registrar_reclamo(accion, corrida)
            if registro.estado == "registrado":
                return json.dumps({"id": registro.id_reclamo, "nuevo": registro.nuevo})
            return {
                "rechazado": "El sistema rechazó el reclamo: no quedó registrado.",
                "no_registrado": "El reclamo no quedó registrado por una falla temporal. Se puede reintentar.",
                "incierto": "No se pudo confirmar si el reclamo quedó registrado.",
            }[registro.estado]

        # no registra nada: deja el reclamo pendiente hasta que el usuario confirme
        conv.pendiente = accion
        return "Reclamo pendiente: el sistema le pidió confirmación al usuario. Todavía no está registrado."

    def responder_pendiente(self, conv: Conversacion, mensaje: str) -> tuple[str, bool] | None:
        # devuelve (texto, registra) o None si la respuesta no es un sí ni un no
        if confirmacion.es_confirmacion(mensaje):
            # el registro queda atado al texto: en AUTO corre enseguida, en SUGGEST cuando aprueba el operador
            p = conv.pendiente
            return f"Al aprobar se registra el reclamo. Motivo: {p.motivo}. Descripción: {p.descripcion}", True
        if confirmacion.es_negativa(mensaje):
            conv.pendiente = None
            return "De acuerdo, no avanzo con el reclamo.", False
        # cualquier otra respuesta no confirma: si el usuario cambió algo, el modelo propone de nuevo
        conv.pendiente = None
        return None

    def registrar_pendiente(self, conv: Conversacion, corrida: Corrida) -> str:
        p = conv.pendiente
        if p is None:
            return "No hay ningún reclamo para registrar."
        registro = self.ejecutor.registrar_reclamo(p, corrida)
        if registro.estado == "no_registrado":
            # queda pendiente: si el usuario reintenta, el operation_id evita que se guarde dos veces
            return "El reclamo no quedó registrado por una falla del sistema. ¿Querés que lo reintente? (sí/no)"
        if registro.estado == "incierto":
            return (
                "No pude confirmar si el reclamo quedó registrado por una falla del sistema. "
                "¿Querés que lo reintente? (sí/no)"
            )
        conv.pendiente = None
        if registro.estado == "rechazado":
            return "El sistema rechazó el reclamo, así que no quedó registrado."
        if registro.nuevo:
            return f"Listo, registré tu reclamo con el número {registro.id_reclamo}."
        return f"Ese reclamo ya estaba registrado con el número {registro.id_reclamo}."
