#Límites del harness, leídos de config/harness_config.json

import json
from dataclasses import dataclass, replace
from pathlib import Path

RAIZ = Path(__file__).parents[2]
CARPETA_CONFIG = RAIZ / "config"
CARPETA_FIXTURES = RAIZ / "fixtures"


@dataclass(frozen=True)
class Limites:
    max_pasos: int
    timeout_total_ms: int
    timeout_herramienta_ms: int
    max_reintentos_lectura: int
    ventana_historial: int


def cargar_limites(**cambios) -> Limites:
    # los cambios pisan los valores del archivo, por ejemplo max_pasos=3 en un escenario
    config = json.loads((CARPETA_CONFIG / "harness_config.json").read_text(encoding="utf-8"))
    d = config["defaults"]
    limites = Limites(
        max_pasos=d["max_steps"],
        timeout_total_ms=d["total_timeout_ms"],
        timeout_herramienta_ms=d["tool_timeout_ms"],
        max_reintentos_lectura=d["max_read_retries"],
        ventana_historial=d["context_window_messages"],
    )
    return replace(limites, **cambios)
