import sqlite3
from contextlib import closing

import pytest

from agente_zoco.config import cargar_limites
from agente_zoco.memoria.memoria import Memoria
from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.tools import crear_reclamo

CONTEXTO_A = cargar_contexto("comercio_a", "operador_a")
CONTEXTO_B = cargar_contexto("comercio_b", "operador_b")
RECLAMO = {"tool": "crear_reclamo", "args": {"motivo": "demora", "descripcion": "No recibi comprobante"}}


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    monkeypatch.setattr(crear_reclamo, "ARCHIVO_RECLAMOS", tmp_path / "reclamos.db")
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


@pytest.fixture
def memoria(tmp_path):
    return Memoria(tmp_path / "harness.db")


def abrir(memoria, conversation_id="conv_1", contexto=CONTEXTO_A, pasos=(), limites=None):
    return Agente(contexto, ModeloGuionado(list(pasos)), limites, conversation_id, memoria)


def textos_del_usuario(agente):
    return [m["texto"] for m in agente.conv.mensajes if m["rol"] == "usuario"]


def test_despues_de_reiniciar_sigue_el_estado(memoria):
    agente = abrir(memoria)
    agente.evento("operator_takeover", "operador")
    agente.responder("¿Hay alguien?")

    reiniciado = abrir(memoria)
    assert reiniciado.conv.maquina.actual == "HUMAN"
    assert reiniciado.conv.version == 1
    assert reiniciado.responder("Hola").tipo == "ninguna"
    assert textos_del_usuario(reiniciado) == ["¿Hay alguien?", "Hola"]


def test_despues_de_reiniciar_sigue_el_reclamo_pendiente(memoria):
    agente = abrir(memoria, pasos=[RECLAMO])
    agente.responder("No recibí el comprobante")

    reiniciado = abrir(memoria)
    assert reiniciado.conv.pendiente == agente.conv.pendiente
    assert crear_reclamo.listar() == []


def test_despues_de_reiniciar_un_si_confirma_el_reclamo_que_estaba_pendiente(memoria):
    abrir(memoria, pasos=[RECLAMO]).responder("No recibí el comprobante")
    reiniciado = abrir(memoria)
    assert "REC-000001" in reiniciado.responder("sí").texto
    assert len(crear_reclamo.listar()) == 1


def test_la_misma_conversacion_en_otra_empresa_es_otra_conversacion(memoria):
    abrir(memoria, contexto=CONTEXTO_A, pasos=[{"final": "Hola A"}]).responder("Soy Alex del comercio A")
    abrir(memoria, contexto=CONTEXTO_B, pasos=[{"final": "Hola B"}]).responder("Soy Alex del comercio B")
    assert textos_del_usuario(abrir(memoria, contexto=CONTEXTO_A)) == ["Soy Alex del comercio A"]
    assert textos_del_usuario(abrir(memoria, contexto=CONTEXTO_B)) == ["Soy Alex del comercio B"]


def test_conversaciones_intercaladas_no_se_mezclan(memoria):
    a = abrir(memoria, "conv_a", CONTEXTO_A, [{"final": "ok"}, {"final": "ok"}])
    b = abrir(memoria, "conv_b", CONTEXTO_B, [{"final": "ok"}])
    a.responder("Soy Alex del comercio A")
    b.responder("Soy Alex del comercio B")
    a.responder("¿Cuánto vendí?")
    assert textos_del_usuario(abrir(memoria, "conv_a", CONTEXTO_A)) == ["Soy Alex del comercio A", "¿Cuánto vendí?"]
    assert textos_del_usuario(abrir(memoria, "conv_b", CONTEXTO_B)) == ["Soy Alex del comercio B"]


def test_corrida_fallida_guarda_el_mensaje(memoria):
    class ModeloRoto:
        def generar(self, historial, herramientas):
            raise KeyError("algo inesperado")

    abrir(memoria, pasos=[{"final": "Hola"}]).responder("Hola")
    agente = Agente(CONTEXTO_A, ModeloRoto(), conversation_id="conv_1", memoria=memoria)
    with pytest.raises(KeyError):
        agente.responder("¿Seguís ahí?")
    reiniciado = abrir(memoria)
    assert textos_del_usuario(reiniciado) == ["Hola", "¿Seguís ahí?"]
    assert reiniciado.conv.mensajes[-1]["rol"] == "usuario"


def test_no_se_puede_guardar_un_mensaje_de_una_conversacion_que_no_existe(memoria):
    with closing(memoria._conectar()) as conexion, pytest.raises(sqlite3.IntegrityError):
        conexion.execute("INSERT INTO mensajes VALUES ('comercio_a', 'no_existe', 0, '{}')")


def test_al_modelo_le_llegan_solo_los_ultimos_mensajes(memoria):
    vistos = []

    class ModeloQueMira:
        def generar(self, historial, herramientas):
            vistos.append(historial)
            return ModeloGuionado([{"final": "ok"}]).generar(historial, herramientas)

    agente = Agente(CONTEXTO_A, ModeloQueMira(), cargar_limites(ventana_historial=4), "conv_1", memoria)
    for i in range(5):
        agente.responder(f"mensaje {i}")
    ultima = vistos[-1]
    assert ultima[0]["rol"] == "sistema"
    assert [m["texto"] for m in ultima[1:]] == ["mensaje 3", "ok", "mensaje 4"]
