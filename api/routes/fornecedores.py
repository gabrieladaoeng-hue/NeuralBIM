"""Rotas de cadastro de fornecedores (Etapa 7). Lista append-only em
FORNECEDORES_PATH -- so cresce via POST e encolhe via DELETE explicito."""

from datetime import date

from fastapi import APIRouter, HTTPException

from config import FORNECEDORES_PATH
from models.fornecedor import Fornecedor
from storage.lista_json import acrescentar_item, carregar_lista, remover_item

router = APIRouter()


@router.post("/fornecedores")
def salvar_fornecedor(fornecedor: Fornecedor):
    item = fornecedor.model_dump()
    if not item.get("data"):
        item["data"] = date.today().isoformat()
    lista = acrescentar_item(FORNECEDORES_PATH, item)
    return {"status": "ok", "total_registrado": len(lista), "item": item}


@router.get("/fornecedores")
def listar_fornecedores():
    return carregar_lista(FORNECEDORES_PATH)


@router.delete("/fornecedores/{item_id}")
def excluir_fornecedor(item_id: str):
    lista = remover_item(FORNECEDORES_PATH, item_id)
    if lista is None:
        raise HTTPException(
            status_code=404,
            detail="Fornecedor com id '{}' nao encontrado.".format(item_id),
        )
    return {"status": "ok", "total_registrado": len(lista), "lista": lista}
