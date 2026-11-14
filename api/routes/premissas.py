"""Etapa 7: expoe pro painel as premissas de engenharia ja documentadas em
mapeamento_sinapi.json (_leia_isto_primeiro) -- fck, taxa de armadura,
bitola, forma e concretagem etc. Rota de leitura pura, sem estado."""

from fastapi import APIRouter

from precificacao import obter_premissas

router = APIRouter()


@router.get("/premissas")
def premissas():
    return obter_premissas()
