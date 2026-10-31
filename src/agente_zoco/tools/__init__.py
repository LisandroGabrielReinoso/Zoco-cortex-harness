import json
import re
from datetime import date

from agente_zoco.config import CARPETA_CONFIG
from agente_zoco.politicas.contexto import Contexto
from agente_zoco.tools import buscar_documentacion, consultar_ventas, crear_reclamo

MODULOS = [buscar_documentacion, consultar_ventas, crear_reclamo]

herramientas = {}
ESQUEMAS = []
ESQUEMAS_PARA_EL_MODELO = []


def sin_argumentos_internos(modulo) -> dict:
    internos = getattr(modulo, "ARGUMENTOS_INTERNOS", set())
    parametros = modulo.ESQUEMA["parameters"]
    visibles = {clave: valor for clave, valor in parametros["properties"].items() if clave not in internos}
    return {**modulo.ESQUEMA, "parameters": {**parametros, "properties": visibles}}


for m in MODULOS:
    nombre = m.ESQUEMA["name"]
    herramientas[nombre] = m
    ESQUEMAS.append(m.ESQUEMA)
    ESQUEMAS_PARA_EL_MODELO.append(sin_argumentos_internos(m))


def cargar_reglas() -> dict:
    # permiso, lectura/escritura, empresa y confirmación de cada herramienta, de config/tools_config.json
    config = json.loads((CARPETA_CONFIG / "tools_config.json").read_text(encoding="utf-8"))
    reglas = {r["name"]: r for r in config["tools"]}
    for nombre, modulo in herramientas.items():
        if nombre not in reglas:
            raise RuntimeError(f"{nombre} no está declarada en tools_config.json")
        if set(reglas[nombre]["args_schema"]) != set(modulo.ESQUEMA["parameters"]["properties"]):
            raise RuntimeError(f"los argumentos de {nombre} no coinciden con tools_config.json")
    return reglas


REGLAS = cargar_reglas()


def validar_llamada(nombre: str, argumentos: dict | None, contexto: Contexto):
    # devuelve (modulo, None) si la llamada respeta el contrato, o (None, problema)
    modulo = herramientas.get(nombre)
    if modulo is None:
        return None, f"La herramienta '{nombre}' no existe."

    permiso = REGLAS[nombre]["required_permission"]
    if permiso not in contexto.permisos:
        return None, f"El usuario no tiene el permiso {permiso} que necesita '{nombre}'."

    if argumentos is None:
        return None, "Los parametros no son un JSON válido"

    problema = validar_parametros(modulo.ESQUEMA, argumentos)
    if problema:
        return None, problema
    return modulo, None


def argumentos_para(nombre: str, argumentos: dict, contexto: Contexto) -> dict:
    # la empresa sale del contexto: el modelo no la puede elegir
    if REGLAS[nombre]["tenant_scoped"]:
        return {**argumentos, "tenant_id": contexto.tenant_id}
    return dict(argumentos)


def es_fecha(valor: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        return False
    try:
        date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def validar_parametros(esquema: dict, argumentos) -> str | None:
    if not isinstance(argumentos, dict):
        return "Los argumentos deben ser un objeto JSON"
    params = esquema["parameters"]
    extra = set(argumentos) - set(params["properties"])
    faltan = set(params.get("required", [])) - set(argumentos)
    if extra:
        return f"Argumentos no permitidos: {sorted(extra)}."
    if faltan:
        return f"Faltan argumentos obligatorios: {sorted(faltan)}."
    for clave, valor in argumentos.items():
        propiedad = params["properties"][clave]
        if propiedad.get("type") == "string" and not isinstance(valor, str):
            return f"El argumento '{clave}' tiene que ser texto."
        if propiedad.get("format") == "date" and not es_fecha(valor):
            return f"El argumento '{clave}' tiene que ser una fecha válida AAAA-MM-DD."
        if "enum" in propiedad and valor not in propiedad["enum"]:
            return f"El argumento '{clave}' tiene que ser uno de {propiedad['enum']}."
    return None
