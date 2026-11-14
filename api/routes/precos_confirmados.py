"""Rotas de correcao manual de preco (Etapa 7). Lista append-only em
PRECOS_CONFIRMADOS_PATH -- nunca sobrescreve o historico."""

from datetime import date

from fastapi import APIRouter

from config import PRECOS_CONFIRMADOS_PATH
from models.preco_confirmado import PrecoConfirmado
from storage.lista_json import acrescentar_item, carregar_lista

router = APIRouter()


@router.post("/precos-confirmados")
def salvar_preco_confirmado(correcao: PrecoConfirmado):
    item = correcao.model_dump()
    if not item.get("data"):
        item["data"] = date.today().isoformat()
    lista = acrescentar_item(PRECOS_CONFIRMADOS_PATH, item)
    return {"status": "ok", "total_registrado": len(lista), "item": item}


@router.get("/precos-confirmados")
def listar_precos_confirmados():
    return carregar_lista(PRECOS_CONFIRMADOS_PATH)
