import json
from datetime import date

from agente_zoco.buscador.chunking import Chunk
from agente_zoco.buscador.corpus import Documento
from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.runner.agent import Agente
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.tools import ESQUEMAS, ESQUEMAS_PARA_EL_MODELO, buscar_documentacion
from agente_zoco.tools.fallas import Fallas

CONTEXTO = cargar_contexto("comercio_a", "operador_a")
DOC07 = Documento("DOC-07", "Planes comerciales", "tarifario", date(2026, 9, 1), date(2027, 3, 31), "...")

class BuscadorFalso:
    # evita cargar documentos y llamar a la API: devuelve siempre el mismo fragmento
    def buscar(self, consulta, k=3):
        return [Chunk("DOC-07#0", "ZT-PRO-2: requiere al menos 400 entradas.", DOC07)], "hibrida"


def resultado_de(nombre: str, argumentos: dict) -> str:
    guion = ModeloGuionado([{"tool": nombre, "args": argumentos}, {"final": "listo"}])
    agente = Agente(CONTEXTO, guion, fallas=Fallas(tasa=0))
    agente.responder("consulta")
    return [m for m in agente.conv.mensajes if m["rol"] == "resultado"][-1]["texto"]


def test_operation_id_oculto_al_modelo():
    visibles = {e["name"]: set(e["parameters"]["properties"]) for e in ESQUEMAS_PARA_EL_MODELO}
    assert visibles["crear_reclamo"] == {"motivo", "descripcion"}
    assert "operation_id" in {e["name"]: e for e in ESQUEMAS}["crear_reclamo"]["parameters"]["properties"]


def test_herramienta_inexistente_devuelve_un_mensaje():
    assert resultado_de("borrar_todo", {}) == "La herramienta 'borrar_todo' no existe."


def test_buscar_documentacion_devuelve_id_y_vigencia(monkeypatch):
    monkeypatch.setattr(buscar_documentacion, "buscador", BuscadorFalso())
    salida = json.loads(resultado_de("buscar_documentacion", {"consulta": "mínimo ZT-PRO-2"}))
    assert salida["modo"] == "hibrida"
    assert salida["fragmentos"] == [{
        "doc_id": "DOC-07",
        "titulo": "Planes comerciales",
        "tipo": "tarifario",
        "vigencia_desde": "2026-09-01",
        "vigencia_hasta": "2027-03-31",
        "texto": "ZT-PRO-2: requiere al menos 400 entradas.",
    }]


def test_buscar_documentacion_rechaza_argumentos_fuera_del_contrato():
    salida = resultado_de("buscar_documentacion", {"consulta": "x", "limite": 50})
    assert salida == "Argumentos no permitidos: ['limite']."
