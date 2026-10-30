from datetime import date
import pytest

from agente_zoco.tools import consultar_ventas, ejecutar_herramienta

HOY = date(2026, 10, 26)

def test_fecha_futura_no_devuelve_datos_aunque_esten_en_el_archivo():
    resultado = consultar_ventas.ejecutar("2030-01-15", hoy=HOY)
    assert "error" in resultado and "monto_bruto" not in resultado


@pytest.mark.parametrize("fecha", ["03/04", "ayer", "2026-13-01", "2026-10-5"])
def test_fecha_fuera_de_formato(fecha):
    assert "error" in consultar_ventas.ejecutar(fecha, hoy=HOY)


def test_el_modelo_no_puede_mandar_hoy():
    salida = ejecutar_herramienta("consultar_ventas", {"fecha": "2030-01-15", "hoy": "2031-01-01"})
    assert salida == "Argumentos no permitidos: ['hoy']."
