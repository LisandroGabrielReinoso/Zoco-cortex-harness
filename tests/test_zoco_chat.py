import pytest

from agente_zoco import zoco_chat
from agente_zoco.agent import Agente, Respuesta
from agente_zoco.contexto import AccesoDenegado, cargar_contexto
from agente_zoco.conversacion import Conversacion
from agente_zoco.memoria import ConflictoDeVersion, Memoria
from agente_zoco.modelos import ModeloGuionado
from agente_zoco.tools import consultar_ventas, crear_reclamo

CONTEXTO = cargar_contexto("comercio_a", "operador_a")
TOMA = {
    "type": "operator_took_over",
    "tenant_id": "comercio_a",
    "conversation_id": "conv_1",
    "actor": "operador_a",
    "version": 2,
}
VENTAS_DEL_15 = {"tool": "consultar_ventas", "args": {"fecha": "2026-10-15"}}
RECLAMO = {"motivo": "demora", "descripcion": "No recibi comprobante", "operation_id": "op_claim_001"}


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    monkeypatch.setattr(crear_reclamo, "ARCHIVO_RECLAMOS", tmp_path / "reclamos.db")
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


@pytest.fixture
def memoria(tmp_path):
    return Memoria(tmp_path / "harness.db")


@pytest.fixture
def llamadas_a_ventas(monkeypatch):
    llamadas = []
    monkeypatch.setattr(consultar_ventas, "ejecutar", lambda **a: llamadas.append(a) or {})
    return llamadas


def abrir(memoria, modelo=None):
    return Agente(CONTEXTO, modelo or ModeloGuionado([]), conversation_id="conv_1", memoria=memoria)


class ModeloConToma:
    # genera con el guion y, antes de que el agente siga, un operador toma la conversación desde otro proceso
    def __init__(self, memoria, *pasos):
        self.guion = ModeloGuionado(list(pasos))
        self.memoria = memoria

    def generar(self, historial, herramientas):
        salida = self.guion.generar(historial, herramientas)
        zoco_chat.aplicar(abrir(self.memoria), TOMA)
        return salida


def tipos_de_evento(agente):
    return [e["type"] for e in agente.corridas[-1].eventos]


def test_la_respuesta_generada_antes_de_la_toma_no_se_entrega(memoria):
    agente = abrir(memoria, ModeloConToma(memoria, {"final": "OK"}))
    assert agente.responder("Hola") == Respuesta("ninguna", None)
    assert "delivery_blocked" in tipos_de_evento(agente)
    assert agente.corridas[-1].motivo == "NEEDS_HUMAN"

    reiniciado = abrir(memoria)
    assert (reiniciado.conv.maquina.actual, reiniciado.conv.version) == ("HUMAN", 2)
    assert [m["rol"] for m in reiniciado.conv.mensajes] == ["usuario"]


def test_si_la_toma_llega_antes_de_usar_una_herramienta_no_se_ejecuta(memoria, llamadas_a_ventas):
    agente = abrir(memoria, ModeloConToma(memoria, VENTAS_DEL_15, {"final": "listo"}))
    agente.responder("¿Cuánto vendí el 2026-10-15?")
    assert llamadas_a_ventas == []
    assert "tool_executed" not in tipos_de_evento(agente)


def test_si_la_toma_llega_antes_de_registrar_un_reclamo_confirmado_no_se_registra(memoria):
    agente = abrir(memoria, ModeloConToma(memoria, {"tool": "crear_reclamo", "args": RECLAMO}, {"final": "listo"}))
    agente.confirmar_accion(RECLAMO)
    agente.responder("Registrá el reclamo")
    assert crear_reclamo.listar() == []


def test_un_agente_que_quedo_desactualizado_se_entera_de_la_toma(memoria):
    agente = abrir(memoria, ModeloGuionado([{"final": "Hola"}]))
    agente.responder("Hola")
    zoco_chat.aplicar(abrir(memoria), TOMA)
    assert agente.responder("¿Hay alguien?") == Respuesta("ninguna", None)
    assert agente.conv.maquina.actual == "HUMAN"


def test_un_evento_atrasado_no_cambia_el_estado(memoria):
    agente = abrir(memoria)
    agente.evento("operator_takeover", "operador", version=2)
    agente.evento("operator_release", "operador", version=3)
    agente.evento("operator_takeover", "operador", version=2)
    assert (agente.conv.maquina.actual, agente.conv.version) == ("AUTO", 3)


def test_con_el_operador_a_cargo_el_pendiente_sigue_despues_de_reiniciar(memoria):
    agente = abrir(memoria, ModeloGuionado([{"tool": "crear_reclamo", "args": RECLAMO}]))
    agente.responder("No recibí el comprobante")
    zoco_chat.aplicar(abrir(memoria), TOMA)

    reiniciado = abrir(memoria)
    assert reiniciado.conv.maquina.actual == "HUMAN"
    assert reiniciado.conv.pendiente == agente.conv.pendiente
    reiniciado.responder("sí")
    assert crear_reclamo.listar() == []


def test_un_evento_de_otra_empresa_se_rechaza(memoria):
    with pytest.raises(AccesoDenegado):
        zoco_chat.aplicar(abrir(memoria), {**TOMA, "tenant_id": "comercio_b"})


def test_guardar_sobre_una_revision_vieja_da_conflicto(memoria):
    memoria.guardar(Conversacion("comercio_a", "conv_1"))
    with pytest.raises(ConflictoDeVersion):
        memoria.guardar(Conversacion("comercio_a", "conv_1"))

    proceso_1 = memoria.cargar("comercio_a", "conv_1")
    proceso_2 = memoria.cargar("comercio_a", "conv_1")
    memoria.guardar(proceso_1)
    with pytest.raises(ConflictoDeVersion):
        memoria.guardar(proceso_2)
