import pytest

from agente_zoco.memoria.memoria import Memoria
from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.tools import crear_reclamo
from agente_zoco.zoco_chat import eventos
from agente_zoco.zoco_chat.ficha import armar_ficha

CONTEXTO = cargar_contexto("comercio_a", "operador_a")
TOMA = {"type": "operator_took_over", "tenant_id": "comercio_a", "conversation_id": "conv_1", "actor": "operador_a"}
VENTAS_DEL_15 = {"tool": "consultar_ventas", "args": {"fecha": "2026-10-15"}}
RECLAMO = {"tool": "crear_reclamo", "args": {"motivo": "demora", "descripcion": "No recibi comprobante"}}


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    monkeypatch.setattr(crear_reclamo, "ARCHIVO_RECLAMOS", tmp_path / "reclamos.db")
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


@pytest.fixture
def memoria(tmp_path):
    return Memoria(tmp_path / "harness.db")


def abrir(memoria, *pasos):
    return Agente(CONTEXTO, ModeloGuionado(list(pasos)), conversation_id="conv_1", memoria=memoria)


def test_ficha_al_tomar(memoria):
    abrir(memoria, VENTAS_DEL_15, {"final": "Vendiste 15 entradas."}).responder("¿Cuánto vendí el 2026-10-15?")
    ficha = eventos.aplicar(abrir(memoria), TOMA)
    assert ficha.consulta == "¿Cuánto vendí el 2026-10-15?"
    assert ficha.herramienta["nombre"] == "consultar_ventas"
    assert '"neto": 300000' in ficha.herramienta["resultado"]
    assert ficha.ultima_respuesta == "Vendiste 15 entradas."
    assert ficha.responsable == "operador_a"
    assert ficha.pendiente is None


def test_ficha_con_respuesta_en_curso(memoria):
    fichas = []

    class ModeloConToma:
        def generar(self, historial, herramientas):
            fichas.append(eventos.aplicar(abrir(memoria), TOMA))
            return ModeloGuionado([{"final": "Vendiste 15 entradas."}]).generar(historial, herramientas)

    Agente(CONTEXTO, ModeloConToma(), conversation_id="conv_1", memoria=memoria).responder("¿Cuánto vendí ayer?")
    assert fichas[0].consulta == "¿Cuánto vendí ayer?"
    assert fichas[0].ultima_respuesta is None


def test_ficha_con_pendiente(memoria):
    abrir(memoria, RECLAMO).responder("No recibí el comprobante")
    ficha = eventos.aplicar(abrir(memoria), TOMA)
    assert (ficha.pendiente["motivo"], ficha.pendiente["descripcion"]) == ("demora", "No recibi comprobante")


def test_responsable_tras_reinicio(memoria):
    eventos.aplicar(abrir(memoria), TOMA)
    assert armar_ficha(abrir(memoria).conv).responsable == "operador_a"


def test_sin_responsable_al_liberar(memoria):
    eventos.aplicar(abrir(memoria), TOMA)
    abrir(memoria).evento("operator_release", "operador")
    assert armar_ficha(abrir(memoria).conv).responsable is None


def test_ficha_vacia(memoria):
    ficha = armar_ficha(abrir(memoria).conv)
    assert ficha == (None, None, None, None, None)
