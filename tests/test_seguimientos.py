import json
from datetime import date

import pytest

from agente_zoco.config import CARPETA_FIXTURES, RAIZ
from agente_zoco.memoria.conversacion import Conversacion
from agente_zoco.memoria.memoria import Memoria
from agente_zoco.politicas.contexto import AccesoDenegado, cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.zoco_chat import eventos
from agente_zoco.zoco_chat.seguimientos import decidir

HOY = date(2026, 10, 30)
CONTEXTO = cargar_contexto("comercio_a", "operador_a")
EVENTOS_DE_EJEMPLO = [
    e
    for e in json.loads((CARPETA_FIXTURES / "chat_events.json").read_text(encoding="utf-8"))["events"]
    if e["type"] == "followup_due"
]
EJEMPLOS_CON_SEGUIMIENTO = [
    json.loads((RAIZ / "examples" / f"{nombre}.json").read_text(encoding="utf-8")) for nombre in ("T12", "T13")
]
VENCIDO = {"type": "followup_due", "opportunity_id": "opp_1", "contact_allowed": True}


@pytest.fixture
def memoria(tmp_path):
    return Memoria(tmp_path / "harness.db")


def abrir(memoria):
    return Agente(CONTEXTO, ModeloGuionado([]), conversation_id="conv_1", memoria=memoria)


def conversacion(estado="AUTO", responsable=None):
    conv = Conversacion("comercio_a", "conv_1", responsable=responsable)
    conv.maquina.actual = estado
    return conv


@pytest.mark.parametrize("evento", EVENTOS_DE_EJEMPLO, ids=lambda e: e["id"])
def test_eventos_de_ejemplo(evento):
    seguimiento = decidir(evento, Conversacion(evento["tenant_id"], evento["conversation_id"]), HOY)
    assert seguimiento.decision == evento["expected_decision"]
    assert seguimiento.motivo


@pytest.mark.parametrize("ejemplo", EJEMPLOS_CON_SEGUIMIENTO, ids=lambda e: e["id"])
def test_conversaciones_de_ejemplo(ejemplo):
    conv = Conversacion(ejemplo["tenant_id"], ejemplo["conversation_id"])
    assert decidir(ejemplo["incoming_event"], conv, HOY).decision == ejemplo["expected"]["decision"]


def test_tarea_interna_con_responsable():
    evento = {**VENCIDO, "pending_on": "ZOCO", "responsible": "Benjamin"}
    assert decidir(evento, conversacion(), HOY).responsable == "Benjamin"


def test_reprogramar_con_fecha():
    evento = {**VENCIDO, "pending_on": "CUSTOMER", "agreed_contact_date": "2026-11-06"}
    seguimiento = decidir(evento, conversacion(), HOY)
    assert (seguimiento.decision, seguimiento.fecha) == ("REPROGRAMAR", "2026-11-06")


def test_fecha_vencida_contacta():
    evento = {**VENCIDO, "pending_on": "CUSTOMER", "agreed_contact_date": "2026-11-06"}
    assert decidir(evento, conversacion(), date(2026, 11, 7)).decision == "CONTACTAR"


def test_sin_permiso_cancela():
    assert decidir({**VENCIDO, "contact_allowed": False}, conversacion(), HOY).decision == "CANCELAR"


def test_cliente_respondio_cancela():
    assert decidir({**VENCIDO, "customer_responded": True}, conversacion(), HOY).decision == "CANCELAR"


def test_operador_a_cargo_tarea_interna():
    seguimiento = decidir(VENCIDO, conversacion("HUMAN", "operador_a"), HOY)
    assert (seguimiento.decision, seguimiento.responsable) == ("TAREA_INTERNA", "operador_a")


def test_bloqueada_cancela():
    assert decidir(VENCIDO, conversacion("BLOCKED"), HOY).decision == "CANCELAR"


def test_contactar_por_defecto():
    assert decidir(VENCIDO, conversacion(), HOY).decision == "CONTACTAR"


def test_decision_guardada_sin_mensajes(memoria):
    evento = {**VENCIDO, "pending_on": "ZOCO", "responsible": "Benjamin"}
    eventos.aplicar(abrir(memoria), evento, HOY)
    reiniciado = abrir(memoria)
    assert [s.decision for s in reiniciado.conv.seguimientos] == ["TAREA_INTERNA"]
    assert reiniciado.conv.seguimientos[0].motivo
    assert [m for m in reiniciado.conv.mensajes if m["rol"] == "asistente"] == []


def test_otra_empresa_rechazada(memoria):
    with pytest.raises(AccesoDenegado):
        eventos.aplicar(abrir(memoria), {**VENCIDO, "tenant_id": "comercio_b"}, HOY)
