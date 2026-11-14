"""Schemas Pydantic que espelham o que o plugin exporta hoje (as colunas do
CSV gerado pelo botao 'Enviar Dados').

- Elemento       -> uma linha do CSV (uma parede, laje ou pilar).
- LoteElementos  -> uma execucao inteira do plugin: os dois carimbos de
                    tempo + a lista de elementos daquela rodada.
"""

from typing import List, Optional

from pydantic import BaseModel, field_validator


class Elemento(BaseModel):
    # --- Sempre preenchidos, em qualquer categoria ---
    Categoria: str                        # "Parede" | "Laje" | "Pilar"
    ID: int                               # ElementId do Revit
    Nivel: str
    Material_Estrutural: str
    Classificacao_Automatica: bool        # True = automatica; False = fallback manual
    Materiais_Brutos_Extraidos: List[str] = []
    Observacoes: str = ""

    # --- Texto especifico de parede (laje/pilar mandam "" -> vira None) ---
    Posicao: Optional[str] = None
    Room_Lado1: Optional[str] = None
    Room_Lado2: Optional[str] = None
    Acabamento_Lado1: Optional[str] = None
    Acabamento_Lado2: Optional[str] = None

    # --- Numericos: cada categoria usa um subconjunto; o resto vem "" -> None ---
    Comprimento_m: Optional[float] = None    # parede
    Altura_m: Optional[float] = None         # parede, pilar
    Largura_cm: Optional[float] = None       # pilar
    Profundidade_cm: Optional[float] = None  # pilar
    Espessura_cm: Optional[float] = None     # parede, laje
    Espessura_Estrutural_cm: Optional[float] = None  # parede (Fase 5)
    Area_m2: Optional[float] = None          # parede, laje
    Area_Forma_m2: Optional[float] = None    # pilar, laje (Fase 5/6, aproximado p/ laje)
    Volume_m3: Optional[float] = None        # parede, laje, pilar

    @field_validator(
        "Posicao", "Room_Lado1", "Room_Lado2",
        "Acabamento_Lado1", "Acabamento_Lado2",
        "Comprimento_m", "Altura_m", "Largura_cm", "Profundidade_cm",
        "Espessura_cm", "Espessura_Estrutural_cm", "Area_m2", "Area_Forma_m2", "Volume_m3",
        mode="before",
    )
    @classmethod
    def vazio_vira_none(cls, valor):
        """O plugin escreve "" (string vazia) nas colunas que a categoria nao
        usa. Aqui isso vira None, pra o schema ficar limpo e os numericos
        nao quebrarem tentando converter "" pra float."""
        if isinstance(valor, str) and valor.strip() == "":
            return None
        return valor


class LoteElementos(BaseModel):
    """Uma execucao completa do plugin."""
    timestamp_inicio_execucao: str
    timestamp_fim_execucao: str
    elementos: List[Elemento]
