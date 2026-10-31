import json
import subprocess
import sys

import pytest

from agente_zoco.config import RAIZ
from agente_zoco.evaluacion.escenario import ejecutar
from agente_zoco.evaluacion.evaluar import CARPETA_EJEMPLOS, evaluar
from agente_zoco.evaluacion.verificacion import verificar
from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.runner.trazas import Trazas
from agente_zoco.tools.fallas import Fallas

EJEMPLOS = sorted(CARPETA_EJEMPLOS.glob("T*.json"))


def leer(nombre: str) -> dict:
    return json.loads((CARPETA_EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("archivo", EJEMPLOS, ids=lambda a: a.stem)
def test_escenario_pasa(archivo):
    resultado = evaluar(archivo)
    assert resultado["result"] == "PASS", resultado["checks"]


def test_salida_con_campos_del_contrato(tmp_path):
    salida = ejecutar(leer("T01"), tmp_path)
    for campo in ("run_id", "tenant_id", "conversation_id", "finish_reason", "step_count", "events"):
        assert campo in salida
    assert {"claims_created", "customer_messages_sent"} <= salida["effects"].keys()
    assert salida["state"]["conversation_mode"] == "AUTO"
    assert salida["events"][-1]["type"] == "run_finished"


def test_rechazo_con_evento_y_razon(tmp_path):
    salida = ejecutar(leer("T03"), tmp_path)
    rechazo = next(e for e in salida["events"] if e["type"] == "tool_rejected")
    assert rechazo["tool"] == "eliminar_ventas" and rechazo["reason"]


def test_verificacion_detecta_fallo(tmp_path):
    escenario = leer("T09")
    escenario["preconditions"] = {}
    chequeos = verificar(escenario, ejecutar(escenario, tmp_path))
    assert not all(c.ok for c in chequeos)


def test_adaptador_por_consola(tmp_path):
    salida = tmp_path / "resultado.json"
    subprocess.run(
        [sys.executable, "evaluation_adapter.py", "--scenario", "examples/T02.json", "--output", str(salida)],
        cwd=RAIZ,
        check=True,
    )
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    assert resultado["effects"]["executed_tools"] == ["consultar_ventas"]


def test_traza_sin_textos(tmp_path):
    trazas = Trazas(tmp_path / "trazas.jsonl")
    guion = ModeloGuionado([{"tool": "consultar_ventas", "args": {"fecha": "2026-10-15"}}, {"final": "Vendiste 15"}])
    agente = Agente(cargar_contexto("comercio_a", "operador_a"), guion, fallas=Fallas(tasa=0), trazas=trazas)
    agente.responder("Mi clave es secreta123, ¿cuánto vendí el 2026-10-15?")

    [traza] = trazas.leer()
    assert (traza["tenant_id"], traza["finish_reason"], traza["step_count"]) == ("comercio_a", "COMPLETED", 2)
    assert [e["type"] for e in traza["events"]] == [
        "message_received", "tool_requested", "tool_executed", "final_answer", "run_finished",
    ]
    texto = json.dumps(traza, ensure_ascii=False)
    assert "secreta123" not in texto and "Vendiste 15" not in texto and "300000" not in texto
