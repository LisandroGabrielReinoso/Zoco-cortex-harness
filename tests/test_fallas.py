import pytest

from agente_zoco.config import cargar_limites
from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.tools import consultar_ventas, crear_reclamo
from agente_zoco.tools.fallas import Fallas

CONTEXTO = cargar_contexto("comercio_a", "operador_a")
VENTAS_DEL_15 = {"tool": "consultar_ventas", "args": {"fecha": "2026-10-15"}}
RECLAMO = {"motivo": "demora", "descripcion": "No recibi comprobante", "operation_id": "op_claim_001"}


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    monkeypatch.setattr(crear_reclamo, "ARCHIVO_RECLAMOS", tmp_path / "reclamos.db")
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


@pytest.fixture
def llamadas_a_ventas(monkeypatch):
    llamadas = []
    original = consultar_ventas.ejecutar
    monkeypatch.setattr(consultar_ventas, "ejecutar", lambda **a: llamadas.append(a) or original(**a))
    return llamadas


def agente_con(fallas, *pasos, limites=None):
    return Agente(CONTEXTO, ModeloGuionado(list(pasos)), limites, fallas=Fallas(fallas))


def eventos(agente, tipo):
    return [e for e in agente.corridas[-1].eventos if e["type"] == tipo]


def test_un_timeout_en_una_lectura_se_reintenta_una_vez(llamadas_a_ventas):
    agente = agente_con({"consultar_ventas": ["TIMEOUT", "SUCCESS"]}, VENTAS_DEL_15, {"final": "listo"})
    agente.responder("¿Cuánto vendí el 2026-10-15?")
    assert len(llamadas_a_ventas) == 1
    assert len(eventos(agente, "tool_retry")) == 1
    assert eventos(agente, "tool_executed")[0]["retry_count"] == 1
    assert agente.corridas[-1].motivo == "COMPLETED"


def test_los_reintentos_de_lectura_tienen_un_limite(llamadas_a_ventas):
    agente = agente_con(
        {"consultar_ventas": ["TIMEOUT"] * 5}, VENTAS_DEL_15, {"final": "no pude"},
        limites=cargar_limites(max_reintentos_lectura=2),
    )
    agente.responder("¿Cuánto vendí el 2026-10-15?")
    assert llamadas_a_ventas == []
    error = eventos(agente, "tool_error")[0]
    assert (error["error_type"], error["retry_count"]) == ("transient", 2)


def test_un_error_permanente_no_se_reintenta(llamadas_a_ventas):
    agente = agente_con({"consultar_ventas": ["INVALID_REQUEST", "SUCCESS"]}, VENTAS_DEL_15, {"final": "no pude"})
    agente.responder("¿Cuánto vendí el 2026-10-15?")
    assert llamadas_a_ventas == []
    assert eventos(agente, "tool_retry") == []
    assert eventos(agente, "tool_error")[0]["error_type"] == "permanent"


def confirmado(fallas):
    agente = agente_con(fallas, {"tool": "crear_reclamo", "args": RECLAMO}, {"final": "listo"})
    agente.confirmar_accion(RECLAMO)
    return agente


def test_si_se_guardo_antes_del_timeout_se_concilia_sin_reintentar():
    agente = confirmado({"crear_reclamo": ["COMMITTED_BUT_TIMEOUT"]})
    agente.responder("Registrá el reclamo")
    assert len(crear_reclamo.listar()) == 1
    assert eventos(agente, "tool_error")[0]["error_type"] == "uncertain"
    assert eventos(agente, "write_reconciled")[0]["found"] is True
    assert eventos(agente, "tool_retry") == []


def test_si_no_se_guardo_antes_del_timeout_la_conciliacion_no_lo_encuentra():
    agente = confirmado({"crear_reclamo": ["TIMEOUT"]})
    agente.responder("Registrá el reclamo")
    assert crear_reclamo.listar() == []
    assert eventos(agente, "write_reconciled")[0]["found"] is False


def test_una_escritura_rechazada_no_se_concilia_ni_se_reintenta():
    agente = confirmado({"crear_reclamo": ["INVALID_REQUEST"]})
    agente.responder("Registrá el reclamo")
    assert crear_reclamo.listar() == []
    assert eventos(agente, "tool_error")[0]["error_type"] == "permanent"
    assert eventos(agente, "write_reconciled") == []


def test_con_el_si_del_usuario_un_timeout_despues_de_guardar_igual_da_el_numero():
    agente = agente_con(
        {"crear_reclamo": ["COMMITTED_BUT_TIMEOUT"]},
        {"tool": "crear_reclamo", "args": {"motivo": "PAGO", "descripcion": "Me cobraron dos veces"}},
    )
    agente.responder("Me cobraron dos veces")
    assert "REC-000001" in agente.responder("sí").texto
    assert agente.conv.pendiente is None
    assert eventos(agente, "write_reconciled")[0]["found"] is True


def test_en_suggest_la_aprobacion_del_operador_deja_eventos():
    agente = agente_con({}, {"tool": "crear_reclamo", "args": {"motivo": "PAGO", "descripcion": "Me cobraron dos veces"}})
    agente.evento("low_confidence", "sistema")
    agente.responder("Me cobraron dos veces")
    agente.aprobar_borrador()
    agente.responder("sí")
    agente.aprobar_borrador()
    tipos = [e["type"] for e in agente.corridas[-1].eventos]
    assert tipos == ["draft_approved", "tool_executed", "final_answer", "run_finished"]


def test_las_fallas_de_un_agente_no_afectan_a_otro(llamadas_a_ventas):
    con_fallas = agente_con({"consultar_ventas": ["INVALID_REQUEST"]}, VENTAS_DEL_15, {"final": "no pude"})
    sin_fallas = agente_con({}, VENTAS_DEL_15, {"final": "listo"})
    sin_fallas.responder("¿Cuánto vendí el 2026-10-15?")
    con_fallas.responder("¿Cuánto vendí el 2026-10-15?")
    assert len(llamadas_a_ventas) == 1
    assert eventos(sin_fallas, "tool_error") == []
