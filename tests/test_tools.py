import json
from datetime import date

from agente_zoco.buscador.chunking import Chunk
from agente_zoco.buscador.corpus import Documento
from agente_zoco.contexto import cargar_contexto
from agente_zoco.tools import ESQUEMAS, buscar_documentacion, ejecutar_herramienta

CONTEXTO = cargar_contexto("comercio_a", "operador_a")
DOC07 = Documento("DOC-07", "Planes comerciales", "tarifario", date(2026, 9, 1), date(2027, 3, 31), "...")

class BuscadorFalso:
    # evita cargar documentos y llamar a la API: devuelve siempre el mismo fragmento
    def buscar(self, consulta, k=3):
        return [Chunk("DOC-07#0", "ZT-PRO-2: requiere al menos 400 entradas.", DOC07)]


def test_herramienta_inexistente_devuelve_un_mensaje():
    assert ejecutar_herramienta("borrar_todo", {}, CONTEXTO) == "La herramienta 'borrar_todo' no existe."


def test_buscar_documentacion_devuelve_id_y_vigencia(monkeypatch):
    monkeypatch.setattr(buscar_documentacion, "buscador", BuscadorFalso())
    salida = json.loads(ejecutar_herramienta("buscar_documentacion", {"consulta": "mínimo ZT-PRO-2"}, CONTEXTO))
    assert salida["fragmentos"] == [{
        "doc_id": "DOC-07",
        "titulo": "Planes comerciales",
        "tipo": "tarifario",
        "vigencia_desde": "2026-09-01",
        "vigencia_hasta": "2027-03-31",
        "texto": "ZT-PRO-2: requiere al menos 400 entradas.",
    }]


def test_buscar_documentacion_rechaza_argumentos_fuera_del_contrato():
    salida = ejecutar_herramienta("buscar_documentacion", {"consulta": "x", "limite": 50}, CONTEXTO)
    assert salida == "Argumentos no permitidos: ['limite']."
