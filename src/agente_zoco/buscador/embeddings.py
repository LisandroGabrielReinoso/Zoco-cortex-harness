#Embeddings con caché en disco: cada texto se pide a la API una vez

import hashlib
from pathlib import Path

import numpy as np
from openai import APIError

MODELO_EMBEDDINGS = "text-embedding-3-small"


class EmbeddingNoDisponible(Exception):
    pass


class Embeddings:
    def __init__(self, client, carpeta_cache, modelo: str = MODELO_EMBEDDINGS):
        self.client = client
        self.modelo = modelo
        self.carpeta = Path(carpeta_cache)
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def _ruta(self, texto: str) -> Path:
        # incluye el modelo: si cambia el modelo, no se reutilizan vectores viejos
        clave = hashlib.sha256(f"{self.modelo}\n{texto}".encode("utf-8")).hexdigest()
        return self.carpeta / f"{clave}.npy"

    def vectores(self, textos: list[str]) -> np.ndarray:
        faltan = [t for t in dict.fromkeys(textos) if not self._ruta(t).exists()]
        if faltan:
            if self.client is None:
                raise EmbeddingNoDisponible(f"Faltan {len(faltan)} embeddings en el caché y no hay OPENAI_API_KEY.")
            try:
                respuesta = self.client.embeddings.create(model=self.modelo, input=faltan)
            except APIError as error:
                raise EmbeddingNoDisponible(type(error).__name__) from error
            for dato in sorted(respuesta.data, key=lambda d: d.index):
                np.save(self._ruta(faltan[dato.index]), np.array(dato.embedding, dtype=np.float32))
        return np.array([np.load(self._ruta(t)) for t in textos])
