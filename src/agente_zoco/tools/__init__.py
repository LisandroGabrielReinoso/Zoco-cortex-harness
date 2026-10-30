import json

from agente_zoco.tools import buscar_documentacion, consultar_ventas, crear_reclamo

MODULOS = [buscar_documentacion, consultar_ventas, crear_reclamo]

herramientas = {}
ESQUEMAS = []

for m in MODULOS:
    nombre = m.ESQUEMA["name"]
    herramientas[nombre] = m
    ESQUEMAS.append(m.ESQUEMA)

def validar_llamada(nombre: str, argumentos: dict | None):
    # devuelve (modulo, None) si la llamada respeta el contrato, o (None, problema)
    modulo = herramientas.get(nombre)
    if modulo is None:
        return None, f"La herramienta '{nombre}' no existe."

    if argumentos is None:
        return None, "Los parametros no son un JSON válido"

    problema = validar_parametros(modulo.ESQUEMA, argumentos)
    if problema:
        return None, problema
    return modulo, None


def ejecutar_herramienta(nombre: str, argumentos: dict | None) -> str:
    modulo, problema = validar_llamada(nombre, argumentos)
    if problema:
        return problema

    try:
        resultado = modulo.ejecutar(**argumentos)
    except Exception:
        return "La herramienta falló. Se puede reintentar más tarde."

    return json.dumps(resultado, ensure_ascii=False)


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
        if "enum" in propiedad and valor not in propiedad["enum"]:
            return f"El argumento '{clave}' tiene que ser uno de {propiedad['enum']}."
    return None
