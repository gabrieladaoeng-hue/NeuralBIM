# -*- coding: utf-8 -*-
"""Fluxo especifico de lajes: filtro de selecao, opcoes de material da laje
e extracao de dados da laje. Material e classificado via CompoundStructure
do FloorType (funcao generica em comum.py)."""

from pyrevit import DB, UI

from comum import (
    obter_id_como_numero,
    obter_nivel,
    montar_observacoes,
    FATOR_FT_PARA_M,
    FATOR_FT2_PARA_M2,
    FATOR_FT3_PARA_M3,
)


OPCOES_MATERIAL_LAJE = [
    "Concreto armado moldado in loco",
    "Laje pre-moldada / trelicada",
    "Laje maciça de concreto",
    "Piso sobre solo",
    "Laje pre-moldada trelicada (cobertura/forro)",
    "Nao definido / outro",
]


class FiltroApenasLajes(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        return isinstance(element, DB.Floor)

    def AllowReference(self, reference, position):
        return False


def extrair_dados_laje(laje, doc, classificacao):
    area_param = laje.get_Parameter(DB.BuiltInParameter.HOST_AREA_COMPUTED)
    volume_param = laje.get_Parameter(DB.BuiltInParameter.HOST_VOLUME_COMPUTED)

    area_ft2 = area_param.AsDouble() if area_param else 0
    volume_ft3 = volume_param.AsDouble() if volume_param else 0

    try:
        espessura_param = laje.get_Parameter(
            DB.BuiltInParameter.FLOOR_ATTR_THICKNESS_PARAM
        )
        espessura_ft = espessura_param.AsDouble() if espessura_param else 0
    except Exception:
        espessura_ft = 0

    if not espessura_ft:
        try:
            laje_tipo = doc.GetElement(laje.GetTypeId())
            estrutura = laje_tipo.GetCompoundStructure() if laje_tipo else None
            if estrutura is not None:
                espessura_ft = estrutura.GetWidth()
        except Exception:
            espessura_ft = 0

    obs = montar_observacoes(classificacao)
    nota_area_forma = (
        "Area_Forma_m2 e uma aproximacao (area total da laje via "
        "HOST_AREA_COMPUTED, ja liquida de furos) - nao e a area de forma "
        "real de fundo, e sim o proxy disponivel sem modelagem adicional."
    )
    obs = (obs + " | " + nota_area_forma) if obs else nota_area_forma

    return {
        "Categoria": "Laje",
        "ID": obter_id_como_numero(laje.Id),
        "Nivel": obter_nivel(doc, laje),
        "Posicao": "",
        "Room_Lado1": "",
        "Room_Lado2": "",
        "Material_Estrutural": classificacao["material_estrutural"],
        "Acabamento_Lado1": "",
        "Acabamento_Lado2": "",
        "Classificacao_Automatica": classificacao["classificacao_automatica"],
        "Materiais_Brutos_Extraidos": classificacao["materiais_brutos_extraidos"],
        "Comprimento_m": "",
        "Altura_m": "",
        "Largura_cm": "",
        "Profundidade_cm": "",
        "Espessura_cm": round(espessura_ft * FATOR_FT_PARA_M * 100, 1),
        "Espessura_Estrutural_cm": "",
        "Area_m2": round(area_ft2 * FATOR_FT2_PARA_M2, 2),
        "Area_Forma_m2": round(area_ft2 * FATOR_FT2_PARA_M2, 2),
        "Volume_m3": round(volume_ft3 * FATOR_FT3_PARA_M3, 3),
        "Observacoes": obs,
    }
