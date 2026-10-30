import json
from datetime import date
import pytest

from agente_zoco.agent import Agente
from agente_zoco.contexto import cargar_contexto
from agente_zoco.modelos import ModeloGuionado
from agente_zoco.tools import consultar_ventas

HOY = date(2026, 10, 26)
CONTEXTO = cargar_contexto("comercio_a", "operador_a")

VENTAS = [
    {"tenant_id": "comercio_a", "fecha": "2026-10-15", "cantidad": 15, "bruto": 300000, "devoluciones": 0},
    {"tenant_id": "comercio_a", "fecha": "2026-10-12", "cantidad": 2, "bruto": 40000, "devoluciones": 90000},
    {"tenant_id": "comercio_a", "fecha": "2030-01-15", "cantidad": 99, "bruto": 3600000, "devoluciones": 0},
    {"tenant_id": "comercio_b", "fecha": "2026-10-15", "cantidad": 8, "bruto": 160000, "devoluciones": 10000},
]


@pytest.fixture(autouse=True)
def ventas_de_prueba(tmp_path, monkeypatch):
    archivo = tmp_path / "ventas.json"
    archivo.write_text(json.dumps({"sales": VENTAS}), encoding="utf-8")
    monkeypatch.setattr(consultar_ventas, "ARCHIVO_VENTAS", archivo)
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


def test_cada_empresa_ve_solo_sus_ventas():
    a = consultar_ventas.ejecutar("2026-10-15", tenant_id="comercio_a", hoy=HOY)
    b = consultar_ventas.ejecutar("2026-10-15", tenant_id="comercio_b", hoy=HOY)
    assert (a["cantidad"], a["neto"]) == (15, 300000)
    assert (b["cantidad"], b["neto"]) == (8, 150000)


def test_el_neto_se_calcula_y_puede_ser_negativo():
    resultado = consultar_ventas.ejecutar("2026-10-12", tenant_id="comercio_a", hoy=HOY)
    assert resultado["neto"] == 40000 - 90000


def test_dia_sin_ventas():
    resultado = consultar_ventas.ejecutar("2026-10-05", tenant_id="comercio_a", hoy=HOY)
    assert resultado == {"fecha": "2026-10-05", "sin_registros": True}


def test_fecha_futura_no_devuelve_datos_aunque_esten_en_el_archivo():
    resultado = consultar_ventas.ejecutar("2030-01-15", tenant_id="comercio_a", hoy=HOY)
    assert "error" in resultado and "bruto" not in resultado


@pytest.mark.parametrize("fecha", ["03/04", "ayer", "2026-13-01", "2026-10-5"])
def test_fecha_fuera_de_formato(fecha):
    assert "error" in consultar_ventas.ejecutar(fecha, tenant_id="comercio_a", hoy=HOY)


def resultado_de_ventas(argumentos: dict) -> str:
    agente = Agente(CONTEXTO, ModeloGuionado([{"tool": "consultar_ventas", "args": argumentos}, {"final": "listo"}]))
    agente.responder("¿Cuánto vendí?")
    return [m for m in agente.conv.mensajes if m["rol"] == "resultado"][-1]["texto"]


@pytest.mark.parametrize("fecha", ["ayer", "2026-13-01", "20261015"])
def test_fecha_invalida_se_rechaza_antes_de_ejecutar(fecha):
    salida = resultado_de_ventas({"fecha": fecha})
    assert salida == "El argumento 'fecha' tiene que ser una fecha válida AAAA-MM-DD."


def test_el_modelo_no_puede_mandar_hoy():
    salida = resultado_de_ventas({"fecha": "2030-01-15", "hoy": "2031-01-01"})
    assert salida == "Argumentos no permitidos: ['hoy']."
