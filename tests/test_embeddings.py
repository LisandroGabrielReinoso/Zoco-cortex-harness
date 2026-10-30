from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from agente_zoco.buscador.embeddings import EmbeddingNoDisponible, Embeddings

class ClienteFalso:
    def __init__(self):
        self.pedidos = []
        self.embeddings = self

    def create(self, model, input):
        self.pedidos.append(list(input))
        datos = [SimpleNamespace(index=i, embedding=[float(len(t)), 1.0]) for i, t in enumerate(input)]
        return SimpleNamespace(data=datos)

def test_devuelve_un_vector_por_texto_en_orden(tmp_path):
    vectores = Embeddings(ClienteFalso(), tmp_path).vectores(["ab", "abcd"])
    assert vectores.tolist() == [[2.0, 1.0], [4.0, 1.0]]

def test_segunda_corrida_no_llama_a_la_api(tmp_path):
    cliente = ClienteFalso()
    Embeddings(cliente, tmp_path).vectores(["ab", "abcd"])
    Embeddings(cliente, tmp_path).vectores(["ab", "abcd"])  # otra instancia, mismo caché en disco
    assert cliente.pedidos == [["ab", "abcd"]]

def test_solo_pide_los_textos_nuevos(tmp_path):
    cliente = ClienteFalso()
    embeddings = Embeddings(cliente, tmp_path)
    embeddings.vectores(["ab"])
    embeddings.vectores(["ab", "xyz", "xyz"])
    assert cliente.pedidos == [["ab"], ["xyz"]]

def test_sin_clave_y_sin_cache_no_hay_embedding(tmp_path):
    with pytest.raises(EmbeddingNoDisponible):
        Embeddings(None, tmp_path).vectores(["ab"])

def test_sin_conexion_no_hay_embedding(tmp_path):
    class ClienteSinConexion:
        def __init__(self):
            self.embeddings = self

        def create(self, model, input):
            raise APIConnectionError(request=None)

    with pytest.raises(EmbeddingNoDisponible):
        Embeddings(ClienteSinConexion(), tmp_path).vectores(["ab"])
