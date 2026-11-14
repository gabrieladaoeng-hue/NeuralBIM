"""Schema de um fornecedor cadastrado manualmente (Etapa 7).

categoria+material identificam o material no mesmo vocabulario do plugin
(mapeamento_sinapi.json) -- categoria e obrigatoria porque o par
(elemento, material_estrutural) e a chave real do sistema (o mesmo texto de
material pode significar entradas diferentes em categorias diferentes, ex.
"Concreto armado moldado in loco" em Laje x Pilar tem codigos SINAPI
diferentes). componente e espessura_cm sao opcionais e so fazem sentido
conforme a resolucao do material (decomposto / por_espessura_estrutural_cm,
ver precificacao.listar_materiais_com_preco) -- validados no frontend, que
ja restringe as opcoes via cascata de selects.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class Fornecedor(BaseModel):
    nome: str
    contato: Optional[str] = None
    telefone: Optional[str] = None
    categoria: Literal["Parede", "Laje", "Pilar"]
    material: str
    componente: Optional[str] = None
    espessura_cm: Optional[float] = None
    unidade: Literal["M2", "M3", "KG", "UN"]
    preco: float
    data: Optional[str] = None
