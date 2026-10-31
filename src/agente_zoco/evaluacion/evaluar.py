import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path

from agente_zoco.config import RAIZ
from agente_zoco.evaluacion.escenario import ejecutar
from agente_zoco.evaluacion.verificacion import verificar

CARPETA_EJEMPLOS = RAIZ / "examples"


def evaluar(archivo: Path) -> dict:
    escenario = json.loads(archivo.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as carpeta:
        salida = ejecutar(escenario, Path(carpeta))
    chequeos = verificar(escenario, salida)
    return {
        "id": escenario["id"],
        "description": escenario["description"],
        "result": "PASS" if all(c.ok for c in chequeos) else "FAIL",
        "checks": [{"key": c.clave, "expected": c.esperado, "actual": c.obtenido, "ok": c.ok} for c in chequeos],
        "output": salida,
    }


def main():
    parser = argparse.ArgumentParser(description="Corre los escenarios de examples/ y verifica efectos y estado.")
    parser.add_argument("--carpeta", type=Path, default=CARPETA_EJEMPLOS)
    parser.add_argument("--resultados", type=Path, help="carpeta donde guardar el resultado fechado")
    argumentos = parser.parse_args()

    resultados = [evaluar(archivo) for archivo in sorted(argumentos.carpeta.glob("T*.json"))]
    for r in resultados:
        print(f"{r['id']}  {r['result']}  {r['description']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"      {c['key']}: esperado {c['expected']!r}, obtenido {c['actual']!r}")
    aprobados = sum(r["result"] == "PASS" for r in resultados)
    print(f"\n{aprobados}/{len(resultados)} PASS")

    if argumentos.resultados is not None:
        argumentos.resultados.mkdir(parents=True, exist_ok=True)
        fecha = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        archivo = argumentos.resultados / f"evaluacion_{fecha}.json"
        resumen = {"date": fecha, "passed": aprobados, "total": len(resultados), "scenarios": resultados}
        archivo.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Resultado guardado en {archivo}")

    raise SystemExit(0 if aprobados == len(resultados) else 1)
