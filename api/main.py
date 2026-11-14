"""Ponto de entrada da API NeuralBIM (Fase 2).

Sobe um FastAPI com a rota de ingestao. Rodar de dentro da pasta api/:
    python main.py
"""

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import API_HOST, API_PORT
from routes.ingestao import router as router_ingestao
from routes.estimativa import router as router_estimativa
from routes.precos_confirmados import router as router_precos_confirmados
from routes.fornecedores import router as router_fornecedores
from routes.gastos_reais import router as router_gastos_reais
from routes.analises import router as router_analises
from routes.premissas import router as router_premissas
from routes.materiais import router as router_materiais
from routes.estimativa_mercado import router as router_estimativa_mercado

app = FastAPI(
    title="API de Estimativa de Custo BIM",
    description="Recebe os dados de elementos extraidos pelo plugin PyRevit.",
    version="0.1.0",
)

app.include_router(router_ingestao, tags=["ingestao"])
app.include_router(router_estimativa, tags=["estimativa"])
app.include_router(router_precos_confirmados, tags=["precos-confirmados"])
app.include_router(router_fornecedores, tags=["fornecedores"])
app.include_router(router_gastos_reais, tags=["gastos-reais"])
app.include_router(router_analises, tags=["analises"])
app.include_router(router_premissas, tags=["premissas"])
app.include_router(router_materiais, tags=["materiais"])
app.include_router(router_estimativa_mercado, tags=["estimativa-mercado"])

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/painel/")
def painel_inicio():
    """Serve a pagina inicial do painel (Etapa 7) -- so navegacao, sem build step."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/painel/estimativa")
def painel_estimativa():
    """Serve o painel de estimativa de custo -- HTML/CSS/JS autocontidos."""
    return FileResponse(str(_STATIC_DIR / "painel.html"))


@app.get("/painel/fornecedores")
def painel_fornecedores():
    """Serve o painel de fornecedores -- HTML/CSS/JS autocontidos."""
    return FileResponse(str(_STATIC_DIR / "fornecedores.html"))


@app.get("/painel/obra")
def painel_obra():
    """Serve o painel de controle de obra (gastos reais) -- HTML/CSS/JS autocontidos."""
    return FileResponse(str(_STATIC_DIR / "obra.html"))


@app.get("/painel/mercado")
def painel_mercado():
    """Serve o painel de estimativa de mercado (Etapa 8b) -- HTML/CSS/JS autocontidos."""
    return FileResponse(str(_STATIC_DIR / "mercado.html"))


@app.get("/")
def raiz():
    """Healthcheck simples - confirma que a API esta no ar."""
    return {"servico": "API de Estimativa de Custo BIM", "status": "no ar"}


if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
