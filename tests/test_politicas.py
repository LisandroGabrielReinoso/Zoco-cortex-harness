import pytest

from agente_zoco.politicas.contexto import cargar_contexto
from agente_zoco.politicas.maquina import FRANJA_HUMANA
from agente_zoco.runner.agent import Agente, Respuesta
from agente_zoco.runner.modelos import ModeloGuionado
from agente_zoco.tools import crear_reclamo
from agente_zoco.tools.fallas import Fallas

CONTEXTO = cargar_contexto("comercio_a", "operador_a")


def guion(*pasos):
    # el modelo devuelve los pasos que le da el test, en orden: así se lo puede obligar a saltear las reglas
    return ModeloGuionado(list(pasos))


def llama_crear_reclamo(motivo, descripcion):
    return {"tool": "crear_reclamo", "args": {"motivo": motivo, "descripcion": descripcion}}


def responde(texto):
    return {"final": texto}


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    # cada test usa su propia base vacía y sin fallas
    monkeypatch.setattr(crear_reclamo, "ARCHIVO_RECLAMOS", tmp_path / "reclamos.db")
    monkeypatch.setenv("TOOL_FAILURE_RATE", "0")


def reclamos_guardados():
    return crear_reclamo.listar()


# regla 2: no registrar sin confirmación explícita, y la confirmación vale para esos datos exactos

def test_si_el_modelo_llama_sin_preguntar_no_se_registra():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces")))
    respuesta = agente.responder("Me cobraron dos veces la misma entrada").texto
    assert reclamos_guardados() == []
    assert "Motivo: PAGO" in respuesta and "Descripción: Me cobraron dos veces" in respuesta


def test_con_si_se_registra_con_los_datos_mostrados():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces")))
    agente.responder("Me cobraron dos veces la misma entrada")
    respuesta = agente.responder("Sí").texto
    assert [(r["motivo"], r["descripcion"]) for r in reclamos_guardados()] == [("PAGO", "Me cobraron dos veces")]
    assert "REC-000001" in respuesta


def test_si_el_usuario_cambia_algo_hay_que_volver_a_confirmar():
    agente = Agente(CONTEXTO, guion(
        llama_crear_reclamo("PAGO", "Me cobraron dos veces"),
        llama_crear_reclamo("PAGO", "Me cobraron tres veces"),
    ))
    agente.responder("Me cobraron dos veces")
    respuesta = agente.responder("Sí, pero poné que fueron tres veces").texto
    assert reclamos_guardados() == []  # "sí, pero..." no confirma
    assert "Descripción: Me cobraron tres veces" in respuesta
    agente.responder("sí")
    assert [r["descripcion"] for r in reclamos_guardados()] == ["Me cobraron tres veces"]


def test_si_el_usuario_dice_no_no_se_registra():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("ACCESO", "El QR no funciona")))
    agente.responder("El QR no me funciona")
    agente.responder("no")
    assert reclamos_guardados() == []


def test_la_herramienta_sola_nunca_registra():
    resultado = crear_reclamo.ejecutar(motivo="PAGO", descripcion="x", tenant_id="comercio_a")
    assert "error" in resultado
    assert reclamos_guardados() == []


# regla 3: un reclamo confirmado no se registra dos veces

def test_repetir_si_no_duplica():
    agente = Agente(CONTEXTO, guion(
        llama_crear_reclamo("PAGO", "Me cobraron dos veces"),
        llama_crear_reclamo("PAGO", "Me cobraron dos veces"),  # el modelo lo propone otra vez
    ))
    agente.responder("Me cobraron dos veces")
    agente.responder("sí")
    agente.responder("sí")  # ya no hay pendiente: va al modelo, que lo vuelve a proponer
    respuesta = agente.responder("sí").texto
    assert len(reclamos_guardados()) == 1
    assert "ya estaba registrado" in respuesta and "REC-000001" in respuesta


def test_timeout_antes_de_guardar_y_reintento_no_duplica():
    fallas = Fallas({"crear_reclamo": ["TIMEOUT"]})
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces")), fallas=fallas)
    agente.responder("Me cobraron dos veces")
    assert "reintente" in agente.responder("sí").texto
    respuesta = agente.responder("sí").texto
    assert len(reclamos_guardados()) == 1
    assert "REC-000001" in respuesta


# Parte 3: lo que puede hacer el agente depende del estado

@pytest.mark.parametrize("evento, actor", [("operator_takeover", "operador"), ("abuse_detected", "sistema")])
def test_en_human_y_blocked_no_se_genera_respuesta(evento, actor):
    agente = Agente(CONTEXTO, guion())  # sin respuestas: si el agente llamara al modelo, el test fallaría
    agente.evento(evento, actor)
    assert agente.responder("Hola, ¿hay alguien?") == Respuesta("ninguna", None)


def test_en_suggest_la_respuesta_espera_al_operador():
    agente = Agente(CONTEXTO, guion(responde("El mínimo es de 400 entradas [DOC-07].")))
    agente.evento("low_confidence", "sistema")
    assert agente.responder("¿Cuál es el mínimo del plan PRO?").tipo == "borrador"
    assert agente.conv.mensajes[-1]["rol"] == "usuario"  # el cliente todavía no recibió nada
    assert agente.aprobar_borrador() == Respuesta("enviada", "El mínimo es de 400 entradas [DOC-07].")


def test_en_suggest_el_reclamo_necesita_tambien_al_operador():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces")))
    agente.evento("low_confidence", "sistema")
    agente.responder("Me cobraron dos veces")  # borrador con el pedido de confirmación
    agente.aprobar_borrador()  # el operador deja que el cliente lo vea
    agente.responder("sí")  # el cliente confirma
    assert reclamos_guardados() == []  # falta la aprobación del operador
    assert "REC-000001" in agente.aprobar_borrador().texto
    assert len(reclamos_guardados()) == 1


def test_en_suggest_si_el_operador_rechaza_no_se_registra():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces")))
    agente.evento("low_confidence", "sistema")
    agente.responder("Me cobraron dos veces")
    agente.aprobar_borrador()
    agente.responder("sí")
    agente.rechazar_borrador()
    assert reclamos_guardados() == []


def test_si_el_cliente_no_vio_el_pedido_de_confirmacion_su_si_no_vale():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces"), responde("¿En qué te ayudo?")))
    agente.evento("low_confidence", "sistema")
    agente.responder("Me cobraron dos veces")
    agente.rechazar_borrador()  # el operador no deja pasar el pedido de confirmación
    agente.responder("sí")
    agente.aprobar_borrador()
    assert reclamos_guardados() == []


def test_si_el_operador_toma_el_control_el_reclamo_pendiente_no_se_registra():
    agente = Agente(CONTEXTO, guion(llama_crear_reclamo("PAGO", "Me cobraron dos veces"), responde("¿En qué te ayudo?")))
    agente.responder("Me cobraron dos veces")  # AUTO: se pide confirmación
    agente.evento("operator_takeover", "operador")
    assert agente.conv.pendiente is not None
    agente.responder("sí")  # en HUMAN no se ejecuta nada
    agente.evento("operator_release", "operador")
    agente.responder("sí")  # de vuelta en AUTO ya no hay pendiente: va al modelo
    assert reclamos_guardados() == []


def test_fuera_de_horario_pedir_un_humano_informa_la_franja():
    agente = Agente(CONTEXTO, guion())
    agente.evento("out_of_hours_started", "sistema")
    respuesta = agente.evento("customer_requests_human", "cliente")
    assert respuesta.tipo == "enviada" and FRANJA_HUMANA in respuesta.texto
    assert agente.conv.maquina.actual == "AUTO"
