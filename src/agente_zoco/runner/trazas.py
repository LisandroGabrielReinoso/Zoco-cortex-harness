import json
import threading
from pathlib import Path

from agente_zoco.config import RAIZ
from agente_zoco.runner.corrida import Corrida

ARCHIVO_TRAZAS = RAIZ / "datos" / "trazas.jsonl"


class Trazas:
    def __init__(self, archivo: Path = ARCHIVO_TRAZAS):
        self.archivo = archivo
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def registrar(self, corrida: Corrida):
        linea = json.dumps(corrida.traza(), ensure_ascii=False)
        with self._lock, self.archivo.open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")

    def leer(self) -> list[dict]:
        if not self.archivo.exists():
            return []
        return [json.loads(linea) for linea in self.archivo.read_text(encoding="utf-8").splitlines() if linea]
