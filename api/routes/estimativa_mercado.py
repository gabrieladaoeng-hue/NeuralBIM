"""Rotas do modo mercado (Etapa 8b, paralelo a Etapa 8): estimativa de preco
pelo conhecimento da IA, sem tabela SINAPI -- serve pra comparar, no mesmo
quantitativo, uma estimativa ancorada em base oficial (routes/estimativa.py)
contra uma nao ancorada. Rotas proprias -- nao mexem nas de
routes/estimativa.py, que continuam identicas."""

import json

from fastapi import APIRouter, HTTPException

from config import ESTIMATIVAS_MERCADO_DIR, STORAGE_DIR
from estimativa_mercado_ia import gerar_estimativa_mercado_lote
from routes.estimativa import _encontrar_mais_recente

router = APIRouter()


@router.post("/estimativa/gerar-mercado")
def gerar_estimativa_mercado():
    """Roda o modo mercado (sem SINAPI) no lote mais recente recebido do
    plugin -- o mesmo lote que POST /estimativa/gerar usaria. Endpoint
    proprio: nao aciona nem e acionado pelo fluxo SINAPI."""
    caminho_lote = _encontrar_mais_recente(STORAGE_DIR, "lote_*.json")
    if caminho_lote is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Nenhum lote encontrado em dados_recebidos/ -- envie dados "
                "do plugin (POST /elementos) primeiro."
            ),
        )
    return gerar_estimativa_mercado_lote(str(caminho_lote))


@router.get("/estimativa/mercado/ultima")
def obter_ultima_estimativa_mercado():
    """So le do disco a ultima estimativa de mercado ja gerada -- nunca
    chama a IA. Pasta propria (ESTIMATIVAS_MERCADO_DIR) -- sem conceito de
    "oficial"/congelamento aqui, isso e so do modo SINAPI (Etapa 8)."""
    caminho = _encontrar_mais_recente(ESTIMATIVAS_MERCADO_DIR, "estimativa_mercado_*.json")
    if caminho is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Nenhuma estimativa de mercado gerada ainda -- rode POST "
                "/estimativa/gerar-mercado primeiro."
            ),
        )
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)
