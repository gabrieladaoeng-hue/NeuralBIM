"""Rota de contador de analises geradas (Etapa 7) -- le LOG_ANALISES_PATH,
que POST /estimativa/gerar alimenta a cada chamada."""

from fastapi import APIRouter

from config import LOG_ANALISES_PATH
from storage.lista_json import carregar_lista

router = APIRouter()


@router.get("/analises/contador")
def contador_analises():
    lista = carregar_lista(LOG_ANALISES_PATH)
    total_chamadas_ia = sum(item.get("chamadas_ia", 0) for item in lista)
    return {
        "total_analises_geradas": len(lista),
        "total_chamadas_ia": total_chamadas_ia,
    }
