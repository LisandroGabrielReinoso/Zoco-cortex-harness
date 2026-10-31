import argparse
import json
import tempfile
from pathlib import Path

from agente_zoco.evaluacion.escenario import ejecutar


def main():
    parser = argparse.ArgumentParser(description="Corre un escenario con el modelo simulado y escribe la salida.")
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    argumentos = parser.parse_args()

    escenario = json.loads(argumentos.scenario.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as carpeta:
        salida = ejecutar(escenario, Path(carpeta))
    argumentos.output.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
