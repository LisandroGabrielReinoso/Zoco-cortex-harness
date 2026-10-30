import json
import time
from typing import Callable, NamedTuple

from agente_zoco.config import Limites
from agente_zoco.politicas.confirmacion import AccionReclamo
from agente_zoco.politicas.contexto import Contexto
from agente_zoco.runner.corrida import Corrida, con_timeout
from agente_zoco.tools import REGLAS, argumentos_para, crear_reclamo, herramientas, validar_llamada
from agente_zoco.tools.fallas import Fallas, PedidoInvalido


class Registro(NamedTuple):
    estado: str
    id_reclamo: str | None
    nuevo: bool


class Ejecutor:
    def __init__(self, contexto: Contexto, limites: Limites, fallas: Fallas | None = None):
        self.contexto = contexto
        self.limites = limites
        self.fallas = fallas or Fallas()

    def validar(self, nombre: str, argumentos: dict | None) -> str | None:
        return validar_llamada(nombre, argumentos, self.contexto)[1]

    def leer(self, nombre: str, argumentos: dict, corrida: Corrida) -> str:
        modulo = herramientas[nombre]
        argumentos = argumentos_para(nombre, argumentos, self.contexto)
        es_lectura = REGLAS[nombre]["kind"] == "read"
        inicio = time.monotonic()
        reintentos = 0
        while True:
            try:
                resultado = self._con_fallas(nombre, lambda: modulo.ejecutar(**argumentos))
                break
            except TimeoutError:
                puede_reintentar = (
                    es_lectura
                    and reintentos < self.limites.max_reintentos_lectura
                    and corrida.ms_transcurridos() < self.limites.timeout_total_ms
                )
                if not puede_reintentar:
                    corrida.evento("tool_error", tool=nombre, reason="timeout", retry_count=reintentos,
                                   error_type="transient" if es_lectura else "uncertain")
                    return "La herramienta no respondió a tiempo. Se puede reintentar más tarde."
                reintentos += 1
                corrida.evento("tool_retry", tool=nombre, attempt=reintentos, reason="timeout")
            except Exception as error:
                corrida.evento("tool_error", tool=nombre, reason=type(error).__name__,
                               retry_count=reintentos, error_type="permanent")
                return "La herramienta rechazó el pedido. Reintentar no va a cambiar el resultado."
        corrida.evento("tool_executed", tool=nombre, retry_count=reintentos,
                       duration_ms=int((time.monotonic() - inicio) * 1000))
        return json.dumps(resultado, ensure_ascii=False)

    def registrar_reclamo(self, accion: AccionReclamo, corrida: Corrida) -> Registro:
        nombre = crear_reclamo.ESQUEMA["name"]
        try:
            id_reclamo, nuevo = self._con_fallas(nombre, lambda: crear_reclamo.registrar(
                self.contexto.tenant_id, accion.motivo, accion.descripcion, accion.operation_id
            ))
        except (PedidoInvalido, ValueError) as error:
            corrida.evento("tool_error", tool=nombre, reason=type(error).__name__, error_type="permanent",
                           operation_id=accion.operation_id)
            return Registro("rechazado", None, False)
        except Exception as error:
            corrida.evento("tool_error", tool=nombre, reason=type(error).__name__, error_type="uncertain",
                           operation_id=accion.operation_id)
            return self._conciliar(accion, corrida)
        corrida.evento("tool_executed", tool=nombre, claim_created=nuevo, operation_id=accion.operation_id)
        return Registro("registrado", id_reclamo, nuevo)

    def _conciliar(self, accion: AccionReclamo, corrida: Corrida) -> Registro:
        # sin respuesta no se sabe si el reclamo se guardo antes de cualquier reintento se busca por operation_id
        try:
            reclamo = crear_reclamo.consultar(self.contexto.tenant_id, accion.operation_id)
        except Exception:
            corrida.evento("write_reconciled", operation_id=accion.operation_id, found=None)
            return Registro("incierto", None, False)
        corrida.evento("write_reconciled", operation_id=accion.operation_id, found=reclamo is not None)
        if reclamo is None:
            return Registro("no_registrado", None, False)
        return Registro("registrado", reclamo["id"], True)

    def _con_fallas(self, nombre: str, funcion: Callable):
        return con_timeout(lambda: self.fallas.ejecutar(nombre, funcion), self.limites.timeout_herramienta_ms / 1000)
