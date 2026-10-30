#Quién habla y de qué empresa: lo pone el servidor, nunca el mensaje del usuario ni el modelo

import json
from typing import NamedTuple

from agente_zoco.config import CARPETA_FIXTURES

ARCHIVO_EMPRESAS = CARPETA_FIXTURES / "tenants_ventas.json"


class AccesoDenegado(Exception):
    pass


class Contexto(NamedTuple):
    tenant_id: str
    principal_id: str
    permisos: frozenset[str]


def cargar_contexto(tenant_id: str, principal_id: str) -> Contexto:
    empresas = json.loads(ARCHIVO_EMPRESAS.read_text(encoding="utf-8"))["tenants"]
    for empresa in empresas:
        if empresa["tenant_id"] != tenant_id:
            continue
        if empresa["test_principal"] != principal_id:
            raise AccesoDenegado(f"{principal_id} no pertenece a {tenant_id}")
        return Contexto(tenant_id, principal_id, frozenset(empresa["permissions"]))
    raise AccesoDenegado(f"la empresa {tenant_id} no existe")
