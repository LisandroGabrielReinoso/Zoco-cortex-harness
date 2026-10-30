#Buscador final, elegido con las tablas de resultados/:
# chunking por sección + híbrida (BM25 y vectorial fusionados con RRF) + filtro de vigencia

import os
from datetime import date

from dotenv import load_dotenv
from openai import OpenAI

from agente_zoco.buscador.bm25 import BM25, tokenizar
from agente_zoco.buscador.chunking import Chunk, chunks_por_seccion
from agente_zoco.buscador.corpus import cargar_documentos
from agente_zoco.buscador.embeddings import EmbeddingNoDisponible, Embeddings
from agente_zoco.buscador.hibrida import rrf
from agente_zoco.buscador.metadata import filtrar_por_vigencia, periodo_de_la_pregunta
from agente_zoco.buscador.vectorial import similitud_coseno
from agente_zoco.config import RAIZ

CARPETA_DOCS = RAIZ / "docs" / "docs"
CARPETA_CACHE = RAIZ / "cache" / "embeddings"


def crear_embeddings() -> Embeddings:
    # sin clave igual funciona si todos los vectores ya están en el caché
    load_dotenv(RAIZ / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if api_key else None
    return Embeddings(client, CARPETA_CACHE)


class Buscador:
    def __init__(self, docs=None, embeddings=None):
        # todo lo que depende solo de los documentos se arma una vez
        self.chunks = chunks_por_seccion(docs if docs is not None else cargar_documentos(CARPETA_DOCS))
        self.embeddings = embeddings if embeddings is not None else crear_embeddings()
        self.bm25 = BM25([tokenizar(c.texto) for c in self.chunks])
        try:
            self.matriz = self.embeddings.vectores([c.texto for c in self.chunks])
        except EmbeddingNoDisponible:
            self.matriz = None

    def puntajes_bm25(self, consulta: str) -> list[float]:
        return self.bm25.puntajes(tokenizar(consulta))

    def puntajes_vectorial(self, consulta: str) -> list[float]:
        if self.matriz is None:
            raise EmbeddingNoDisponible("no hay embeddings de los documentos")
        vector = self.embeddings.vectores([consulta])[0]
        return similitud_coseno(vector, self.matriz)

    def puntajes(self, consulta: str, hoy: date | None = None) -> tuple[list[float], str]:
        # un puntaje por chunk; los de documentos no vigentes en la fecha de la consulta quedan en 0
        desde, hasta = periodo_de_la_pregunta(consulta, hoy or date.today())
        bm25 = filtrar_por_vigencia(self.puntajes_bm25(consulta), self.chunks, desde, hasta)
        try:
            vectorial = filtrar_por_vigencia(self.puntajes_vectorial(consulta), self.chunks, desde, hasta)
        except EmbeddingNoDisponible:
            return bm25, "bm25"
        return rrf([bm25, vectorial]), "hibrida"

    def buscar(self, consulta: str, k: int = 3, hoy: date | None = None) -> tuple[list[Chunk], str]:
        # los k chunks con mejor puntaje; cada uno trae su documento con id, tipo y vigencia
        puntajes, modo = self.puntajes(consulta, hoy)
        orden = sorted(range(len(puntajes)), key=lambda i: puntajes[i], reverse=True)
        return [self.chunks[i] for i in orden[:k] if puntajes[i] > 0], modo
