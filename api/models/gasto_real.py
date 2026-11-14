"""Schema de um gasto real registrado pelo engenheiro em obra (Etapa 7) --
comparado com a estimativa da IA no grafico da pagina inicial. Categoria e
uma lista fixa (nao texto livre) pra sempre bater com o campo Categoria que
a estimativa da IA ja usa (Parede/Laje/Pilar)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GastoReal(BaseModel):
    categoria: Literal["Parede", "Laje", "Pilar"]
    valor: float = Field(gt=0)
    data: Optional[str] = None
    descricao: Optional[str] = None
