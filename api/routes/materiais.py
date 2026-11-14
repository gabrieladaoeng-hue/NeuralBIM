"""Etapa 7: expoe pro painel a lista de materiais (categoria + material, com
preco SINAPI ja resolvido) que alimenta o seletor de Categoria/Material do
cadastro de fornecedores e a comparacao preco de mercado x preco SINAPI.
Rota de leitura pura, sem estado."""

from fastapi import APIRouter

from precificacao import listar_materiais_com_preco

router = APIRouter()


@router.get("/materiais")
def materiais():
    return listar_materiais_com_preco()
