"""Rotas de registro de gastos reais em obra (Etapa 7). Lista append-only em
GASTOS_REAIS_PATH -- so cresce via POST e encolhe via DELETE explicito."""

from datetime import date

from fastapi import APIRouter, HTTPException

from config import GASTOS_REAIS_PATH
from models.gasto_real import GastoReal
from storage.lista_json import acrescentar_item, carregar_lista, remover_item

router = APIRouter()


@router.post("/gastos-reais")
def salvar_gasto_real(gasto: GastoReal):
    item = gasto.model_dump()
    if not item.get("data"):
        item["data"] = date.today().isoformat()
    lista = acrescentar_item(GASTOS_REAIS_PATH, item)
    return {"status": "ok", "total_registrado": len(lista), "item": item}


@router.get("/gastos-reais")
def listar_gastos_reais():
    return carregar_lista(GASTOS_REAIS_PATH)


@router.delete("/gastos-reais/{item_id}")
def excluir_gasto_real(item_id: str):
    lista = remover_item(GASTOS_REAIS_PATH, item_id)
    if lista is None:
        raise HTTPException(
            status_code=404,
            detail="Gasto real com id '{}' nao encontrado.".format(item_id),
        )
    return {"status": "ok", "total_registrado": len(lista), "lista": lista}
