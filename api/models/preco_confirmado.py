"""Schema de uma correcao manual de preco (Etapa 7) -- confirmado por um
engenheiro por fora do retrieval automatico das Fases 5/6."""

from typing import Optional

from pydantic import BaseModel, model_validator


class PrecoConfirmado(BaseModel):
    material_estrutural: Optional[str] = None
    codigo_sinapi: Optional[str] = None
    preco_confirmado: float
    data: Optional[str] = None

    @model_validator(mode="after")
    def exige_identificador(self):
        if not self.material_estrutural and not self.codigo_sinapi:
            raise ValueError(
                "Informe material_estrutural ou codigo_sinapi (pelo menos um dos dois)."
            )
        return self
