from datetime import date
from types import SimpleNamespace

from agente_zoco.buscador import Buscador
from agente_zoco.buscador.corpus import Documento
from agente_zoco.buscador.embeddings import Embeddings


class ClienteFalso:
    def __init__(self):
        self.embeddings = self

    def create(self, model, input):
        datos = [SimpleNamespace(index=i, embedding=[float("QR" in t), 1.0]) for i, t in enumerate(input)]
        return SimpleNamespace(data=datos)

HOY = date(2026, 10, 30)
DOCS = [
    Documento("DOC-01", "Liquidaciones", "politica", date(2026, 1, 1), date(2026, 12, 31),
              "# Plazo\nLa liquidación de ventas se acredita a las 72 horas."),
    Documento("DOC-02", "Entradas", "politica", date(2026, 1, 1), date(2026, 12, 31),
              "# QR\nCada entrada tiene un código QR único."),
]


def test_sin_ningun_embedding_busca_solo_con_bm25(tmp_path):
    buscador = Buscador(DOCS, Embeddings(None, tmp_path))
    fragmentos, modo = buscador.buscar("plazo de liquidación", hoy=HOY)
    assert modo == "bm25"
    assert fragmentos[0].doc_id == "DOC-01"


def test_si_falta_solo_el_de_la_consulta_busca_con_bm25(tmp_path):
    Buscador(DOCS, Embeddings(ClienteFalso(), tmp_path))  # deja en caché los de los documentos
    fragmentos, modo = Buscador(DOCS, Embeddings(None, tmp_path)).buscar("código QR", hoy=HOY)
    assert modo == "bm25"
    assert fragmentos[0].doc_id == "DOC-02"


def test_con_todos_los_embeddings_la_busqueda_es_hibrida(tmp_path):
    fragmentos, modo = Buscador(DOCS, Embeddings(ClienteFalso(), tmp_path)).buscar("código QR", hoy=HOY)
    assert modo == "hibrida"
    assert fragmentos[0].doc_id == "DOC-02"
