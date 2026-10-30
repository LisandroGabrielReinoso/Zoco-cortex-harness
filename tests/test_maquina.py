from datetime import datetime

import pytest

from agente_zoco.politicas.maquina import MaquinaDeEstados, TransicionInvalida

# (origen, evento, actor, destino): escrita aparte de transiciones.py para no probar la tabla contra sí misma
DEFINIDAS = [
    ("AUTO", "operator_takeover", "operador", "HUMAN"),
    ("AUTO", "customer_requests_human", "cliente", "HUMAN"),
    ("AUTO", "low_confidence", "sistema", "SUGGEST"),
    ("AUTO", "abuse_detected", "sistema", "BLOCKED"),
    ("SUGGEST", "operator_takeover", "operador", "HUMAN"),
    ("SUGGEST", "operator_release", "operador", "AUTO"),
    ("SUGGEST", "abuse_detected", "sistema", "BLOCKED"),
    ("HUMAN", "operator_release", "operador", "AUTO"),
    ("HUMAN", "abuse_detected", "operador", "BLOCKED"),
    ("BLOCKED", "supervisor_unblock", "supervisor", "AUTO"),
    ("AUTO", "out_of_hours_started", "sistema", "AUTO"),
    ("SUGGEST", "out_of_hours_started", "sistema", "AUTO"),
    ("HUMAN", "out_of_hours_started", "sistema", "AUTO"),
    ("BLOCKED", "out_of_hours_started", "sistema", "BLOCKED"),
    ("AUTO", "out_of_hours_ended", "sistema", "AUTO"),
    ("BLOCKED", "out_of_hours_ended", "sistema", "BLOCKED"),
]


@pytest.mark.parametrize("origen, evento, actor, destino", DEFINIDAS)
def test_transicion_definida(origen, evento, actor, destino):
    maquina = MaquinaDeEstados(inicial=origen)
    if evento == "out_of_hours_ended":
        maquina.fuera_de_horario = True  # ese evento solo vale fuera de horario
    maquina.transicionar(evento, actor)
    assert maquina.actual == destino


def test_cada_transicion_queda_registrada():
    fecha = datetime(2026, 10, 26, 15, 30)
    maquina = MaquinaDeEstados()
    maquina.transicionar("low_confidence", "sistema", fecha)
    registro = maquina.historial[-1]
    assert (registro.anterior, registro.nuevo, registro.evento, registro.actor, registro.fecha) == (
        "AUTO", "SUGGEST", "low_confidence", "sistema", fecha,
    )


@pytest.mark.parametrize("origen, evento, actor", [
    ("HUMAN", "customer_requests_human", "cliente"),  # par que no está en la tabla
    ("BLOCKED", "operator_release", "operador"),      # estaba en la consigna, contradice la regla 4
    ("BLOCKED", "supervisor_unblock", "operador"),    # solo un supervisor saca de BLOCKED
    ("AUTO", "supervisor_unblock", "supervisor"),     # no se puede desbloquear algo que no está bloqueado
    ("HUMAN", "abuse_detected", "sistema"),           # en HUMAN decide el operador
    ("AUTO", "evento_inventado", "sistema"),
])
def test_transicion_invalida_falla_y_no_cambia_nada(origen, evento, actor):
    maquina = MaquinaDeEstados(inicial=origen)
    with pytest.raises(TransicionInvalida):
        maquina.transicionar(evento, actor)
    assert maquina.actual == origen and maquina.historial == []


def test_fuera_de_horario_no_se_puede_pasar_a_un_operador():
    maquina = MaquinaDeEstados()
    maquina.transicionar("out_of_hours_started", "sistema")
    with pytest.raises(TransicionInvalida):
        maquina.transicionar("customer_requests_human", "cliente")
    assert maquina.actual == "AUTO"
