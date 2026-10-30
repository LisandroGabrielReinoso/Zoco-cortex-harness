import os
from dotenv import load_dotenv
from openai import OpenAI
from agente_zoco.agent import Agente
from agente_zoco.contexto import cargar_contexto
from agente_zoco.maquina import TransicionInvalida
from agente_zoco.memoria import Memoria
from agente_zoco.modelos import ModeloOpenAI

AYUDA = (
    "Lo que escribas es un mensaje del cliente. Para simular al operador, supervisor o sistema:\n"
    "  /evento <evento> <actor>   ej: /evento operator_takeover operador\n"
    "  /aprobar  /rechazar        el borrador de SUGGEST\n"
    "  /estado                    estado actual y registro de transiciones\n"
    "  salir"
)


def mostrar(respuesta):
    if respuesta is None:
        print("(no hay borrador)")
    elif respuesta.tipo == "enviada":
        print("Agente:", respuesta.texto)
    elif respuesta.tipo == "borrador":
        print("Borrador para el operador (/aprobar o /rechazar):", respuesta.texto)
    else:
        print("(en este estado el agente no responde)")


def comando(agente, linea):
    partes = linea.split()
    if partes[0] == "/evento" and len(partes) == 3:
        try:
            respuesta = agente.evento(partes[1], partes[2])
        except TransicionInvalida as error:
            print("Error:", error)
            return
        if respuesta is not None:
            mostrar(respuesta)
        print("Estado:", agente.conv.maquina.actual)
    elif partes[0] == "/aprobar":
        mostrar(agente.aprobar_borrador())
    elif partes[0] == "/rechazar":
        agente.rechazar_borrador()
        print("Borrador descartado.")
    elif partes[0] == "/estado":
        print("Estado:", agente.conv.maquina.actual, "| fuera de horario:", agente.conv.maquina.fuera_de_horario)
        for t in agente.conv.maquina.historial:
            print(f"  {t.fecha:%Y-%m-%d %H:%M:%S}  {t.anterior} -> {t.nuevo}  ({t.evento}, {t.actor})")
    else:
        print(AYUDA)


def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Falta OPENAI_API_KEY en el .env")

    # la consola simula ser el operador de comercio_a, como si ya hubiera iniciado sesión
    contexto = cargar_contexto("comercio_a", "operador_a")
    agente = Agente(contexto, ModeloOpenAI(OpenAI(api_key=api_key)), conversation_id="consola", memoria=Memoria())
    print(AYUDA)

    while True:
        men = input(f"[{agente.conv.maquina.actual}] > ").strip()
        if men.lower() == "salir": break
        if not men:
            continue
        if men.startswith("/"):
            comando(agente, men)
        else:
            mostrar(agente.responder(men))
