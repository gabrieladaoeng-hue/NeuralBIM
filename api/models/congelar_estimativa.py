"""Schema do corpo de POST /estimativa/congelar (Etapa 8 -- versionamento):
so o nome do arquivo de estimativa (dentro de ESTIMATIVAS_DIR) a marcar
como oficial da validacao."""

from pydantic import BaseModel


class CongelarEstimativa(BaseModel):
    arquivo: str
