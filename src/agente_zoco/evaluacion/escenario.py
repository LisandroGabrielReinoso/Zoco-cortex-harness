import json
from dataclasses import asdict
from pathlib import Path

from agente_zoco.config import cargar_limites
from agente_zoco.memoria.conversacion import Conversacion
from agente_zoco.memoria.memoria import Memoria
from agente_zoco.politicas.confirmacion import AccionReclamo
from agente_zoco.politicas.contexto import ARCHIVO_EMPRESAS, cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.runner.trazas import Trazas
from agente_zoco.tools import crear_reclamo
from agente_zoco.tools.fallas import Fallas
from agente_zoco.zoco_chat import eventos

MENSAJE = "Mensaje del cliente"


class ModeloConEvento:
    def __init__(self, modelo, al_terminar):
        self.modelo = modelo
        self.al_terminar = al_terminar

    def generar(self, historial, herramientas):
        salida = self.modelo.generar(historial, herramientas)
        if not salida.llamadas and self.al_terminar is not None:
            accion, self.al_terminar = self.al_terminar, None
            accion()
        return salida


class Entorno:
    def __init__(self, escenario: dict, carpeta: Path):
        self.escenario = escenario
        self.tenant_id = escenario["tenant_id"]
        self.conversation_id = escenario["conversation_id"]
        self.contexto = cargar_contexto(self.tenant_id, escenario["principal_id"])
        self.memoria = Memoria(carpeta / "harness.db")
        self.trazas = Trazas(carpeta / "trazas.jsonl")
        self.reclamos = carpeta / "reclamos.db"
        cambios = {}
        if "max_steps" in escenario.get("preconditions", {}):
            cambios["max_pasos"] = escenario["preconditions"]["max_steps"]
        self.limites = cargar_limites(**cambios)
        self.fallas = Fallas(escenario.get("faults", {}), tasa=0)

    def agente(self, modelo=None, contexto=None, conversation_id=None) -> Agente:
        return Agente(
            contexto or self.contexto,
            modelo or ModeloGuionado(self.escenario.get("model_script", [])),
            self.limites,
            conversation_id or self.conversation_id,
            self.memoria,
            self.fallas,
            self.trazas,
        )


def ejecutar(escenario: dict, carpeta: Path) -> dict:
    archivo_anterior = crear_reclamo.ARCHIVO_RECLAMOS
    entorno = Entorno(escenario, carpeta)
    crear_reclamo.ARCHIVO_RECLAMOS = entorno.reclamos
    try:
        return correr(entorno)
    finally:
        crear_reclamo.ARCHIVO_RECLAMOS = archivo_anterior


def correr(entorno: Entorno) -> dict:
    escenario = entorno.escenario
    previas = escenario.get("preconditions", {})
    efectos = {}

    preparar_estado(entorno, previas)
    if "interleaved_conversations" in previas:
        efectos["contexts_separated"] = intercalar(entorno, previas["interleaved_conversations"])

    agente = entorno.agente()
    for accion in previas.get("confirmed_actions", []):
        agente.confirmar_accion(accion["args"])
    if previas.get("restart_between_events"):
        agente = entorno.agente()

    evento = escenario.get("incoming_event")
    if evento is not None:
        evento = {"tenant_id": entorno.tenant_id, "conversation_id": entorno.conversation_id, **evento}

    corte = None
    if evento is not None and evento.get("when") == "after_response_generation_before_delivery":
        def tomar():
            nonlocal corte
            corte = len(agente.corridas[-1].eventos)
            eventos.aplicar(entorno.agente(), evento)

        agente.modelo = ModeloConEvento(agente.modelo, tomar)
        agente.responder(escenario.get("message", MENSAJE))
    elif evento is not None:
        resultado = eventos.aplicar(agente, evento)
        if evento["type"] == "followup_due":
            efectos["decision"] = resultado.decision
            efectos["reason"] = resultado.motivo
    else:
        agente.responder(escenario.get("message", MENSAJE))

    corrida = agente.corridas[-1]
    conv = entorno.memoria.cargar(entorno.tenant_id, entorno.conversation_id)
    efectos.update(efectos_reales(entorno, corrida, conv, corte))
    return {
        **corrida.traza(),
        "effects": efectos,
        "state": estado(conv),
    }


def preparar_estado(entorno: Entorno, previas: dict):
    inicial = previas.get("initial_state") or previas.get("current_state")
    if inicial is None and "pending_action" not in previas and "current_version" not in previas:
        return
    conv = Conversacion(entorno.tenant_id, entorno.conversation_id)
    conv.maquina.actual = inicial or "AUTO"
    conv.version = previas.get("current_version", 0)
    pendiente = previas.get("pending_action")
    if pendiente is not None:
        conv.pendiente = AccionReclamo(
            pendiente.get("motivo", ""), pendiente.get("descripcion", ""), pendiente["operation_id"]
        )
    entorno.memoria.guardar(conv)


def intercalar(entorno: Entorno, conversaciones: list[dict]) -> bool:
    agentes = []
    for datos in conversaciones:
        contexto = cargar_contexto(datos["tenant_id"], principal_de(datos["tenant_id"]))
        agente = entorno.agente(contexto=contexto, conversation_id=datos["conversation_id"])
        agentes.append((datos, agente))
    for datos, agente in agentes:
        agente.responder(datos["message"])

    for datos in conversaciones:
        conv = entorno.memoria.cargar(datos["tenant_id"], datos["conversation_id"])
        mensajes = [m["texto"] for m in conv.mensajes if m["rol"] == "usuario"]
        if mensajes != [datos["message"]]:
            return False
        for otra in conversaciones:
            if otra["tenant_id"] != datos["tenant_id"]:
                if entorno.memoria.cargar(otra["tenant_id"], datos["conversation_id"]) is not None:
                    return False
    return True


def efectos_reales(entorno: Entorno, corrida, conv: Conversacion | None, corte: int | None) -> dict:
    eventos_corrida = corrida.eventos
    ejecutadas = [e["tool"] for e in eventos_corrida if e["type"] == "tool_executed"]
    rechazadas = [e["tool"] for e in eventos_corrida if e["type"] == "tool_rejected"]
    reclamos = crear_reclamo.listar() if entorno.reclamos.exists() else []
    mensajes = conv.mensajes if conv else []
    efectos = {
        "claims_created": len(reclamos),
        "unique_claims_created": len({(r["tenant_id"], r["operation_id"]) for r in reclamos}),
        "cross_tenant_effects": len([r for r in reclamos if r["tenant_id"] != entorno.tenant_id]),
        "cross_tenant_data_exposed": datos_de_otra_empresa(entorno.tenant_id, mensajes),
        "customer_messages_sent": len([m for m in mensajes if m["rol"] == "asistente"]),
        "executed_tools": list(dict.fromkeys(ejecutadas)),
        "rejected_tools": list(dict.fromkeys(rechazadas)),
        "external_calls_to_rejected_tool": len([t for t in ejecutadas if t in rechazadas]),
        "retry_count": len([e for e in eventos_corrida if e["type"] == "tool_retry"]),
    }
    if corte is not None:
        despues = eventos_corrida[corte:]
        efectos["delivered_ai_messages_after_takeover"] = len([e for e in despues if e["type"] == "final_answer"])
        efectos["tool_effects_after_takeover"] = len([e for e in despues if e["type"] == "tool_executed"])
    return efectos


def datos_de_otra_empresa(tenant_id: str, mensajes: list[dict]) -> bool:
    ventas = json.loads(ARCHIVO_EMPRESAS.read_text(encoding="utf-8"))["sales"]
    ajenas = {(v["fecha"], v["cantidad"], v["bruto"]) for v in ventas if v["tenant_id"] != tenant_id}
    for mensaje in mensajes:
        if mensaje["rol"] != "resultado":
            continue
        try:
            resultado = json.loads(mensaje["texto"])
        except json.JSONDecodeError:
            continue
        if isinstance(resultado, dict) and (
            resultado.get("fecha"), resultado.get("cantidad"), resultado.get("bruto")
        ) in ajenas:
            return True
    return False


def estado(conv: Conversacion | None) -> dict:
    if conv is None:
        return {"conversation_mode": "AUTO", "version": 0, "pending_action": None, "responsible": None}
    return {
        "conversation_mode": conv.maquina.actual,
        "version": conv.version,
        "pending_action": asdict(conv.pendiente) if conv.pendiente else None,
        "responsible": conv.responsable,
    }


def principal_de(tenant_id: str) -> str:
    empresas = json.loads(ARCHIVO_EMPRESAS.read_text(encoding="utf-8"))["tenants"]
    return next(e["test_principal"] for e in empresas if e["tenant_id"] == tenant_id)
