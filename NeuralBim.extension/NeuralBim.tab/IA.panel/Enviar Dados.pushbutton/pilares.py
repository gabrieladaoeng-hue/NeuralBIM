# -*- coding: utf-8 -*-
"""Fluxo especifico de pilares: filtro de selecao, opcoes de material do
pilar, altura do pilar, leitura de material estrutural (via parametro do
elemento, sem CompoundStructure) e extracao de dados do pilar."""

from pyrevit import DB, UI

from comum import (
    obter_id_como_numero,
    obter_nivel,
    montar_observacoes,
    classificar_material_automatico,
    FATOR_FT_PARA_M,
)


OPCOES_MATERIAL_PILAR = [
    "Concreto armado moldado in loco",
    "Aco estrutural",
    "Madeira laminada colada",
    "Nao definido / outro",
]


class FiltroApenasPilares(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        if not isinstance(element, DB.FamilyInstance):
            return False
        categoria = element.Category
        if categoria is None:
            return False
        return obter_id_como_numero(categoria.Id) == int(
            DB.BuiltInCategory.OST_StructuralColumns
        )

    def AllowReference(self, reference, position):
        return False


def extrair_material_pilar(coluna, doc):
    """Le o material estrutural do pilar direto do parametro do elemento
    (STRUCTURAL_MATERIAL_PARAM), sem CompoundStructure. Se a instancia nao
    tiver material atribuido, tenta o tipo (FamilySymbol).

    Retorna (sucesso, categoria, nomes_brutos), igual as funcoes de parede/laje.
    """
    nomes = []
    try:
        param = coluna.get_Parameter(DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
        material_id = param.AsElementId() if param else DB.ElementId.InvalidElementId

        if material_id == DB.ElementId.InvalidElementId:
            tipo = doc.GetElement(coluna.GetTypeId())
            param_tipo = tipo.get_Parameter(
                DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM
            ) if tipo else None
            material_id = param_tipo.AsElementId() if param_tipo else material_id

        material = doc.GetElement(material_id) \
            if material_id != DB.ElementId.InvalidElementId else None
        if material is not None:
            nomes.append(material.Name)
    except Exception:
        return False, None, nomes

    sucesso, categoria, categorias_distintas = classificar_material_automatico(nomes)
    return sucesso, categoria, nomes


def _altura_pilar_ft(coluna, doc):
    """Altura do pilar em pes, tentando em ordem:
    1) INSTANCE_LENGTH_PARAM (comprimento real da instancia);
    2) (nivel topo + offset) - (nivel base + offset);
    3) altura do bounding box (eixo Z) como ultimo recurso.
    """
    param_len = coluna.get_Parameter(DB.BuiltInParameter.INSTANCE_LENGTH_PARAM)
    if param_len is not None and param_len.AsDouble() > 0:
        return param_len.AsDouble()

    try:
        p_base = coluna.get_Parameter(DB.BuiltInParameter.SCHEDULE_BASE_LEVEL_PARAM)
        p_topo = coluna.get_Parameter(DB.BuiltInParameter.SCHEDULE_TOP_LEVEL_PARAM)
        p_off_base = coluna.get_Parameter(
            DB.BuiltInParameter.SCHEDULE_BASE_LEVEL_OFFSET_PARAM
        )
        p_off_topo = coluna.get_Parameter(
            DB.BuiltInParameter.SCHEDULE_TOP_LEVEL_OFFSET_PARAM
        )

        nivel_base = doc.GetElement(p_base.AsElementId()) if p_base else None
        nivel_topo = doc.GetElement(p_topo.AsElementId()) if p_topo else None

        if nivel_base is not None and nivel_topo is not None:
            base = nivel_base.Elevation + (p_off_base.AsDouble() if p_off_base else 0.0)
            topo = nivel_topo.Elevation + (p_off_topo.AsDouble() if p_off_topo else 0.0)
            if topo - base > 0:
                return topo - base
    except Exception:
        pass

    try:
        caixa = coluna.get_BoundingBox(None)
        if caixa is not None:
            return caixa.Max.Z - caixa.Min.Z
    except Exception:
        pass

    return 0.0


def extrair_dados_pilar(coluna, doc, classificacao):
    largura_ft = 0.0
    profundidade_ft = 0.0

    tipo_col = doc.GetElement(coluna.GetTypeId())
    if tipo_col is not None:
        p_larg = None
        p_prof = None
        try:
            p_larg = tipo_col.get_Parameter(DB.BuiltInParameter.FAMILY_WIDTH_PARAM)
        except Exception:
            p_larg = None
        try:
            p_prof = tipo_col.get_Parameter(DB.BuiltInParameter.FAMILY_DEPTH_PARAM)
        except Exception:
            p_prof = None

        if p_larg is None:
            p_larg = (tipo_col.LookupParameter("b")
                      or tipo_col.LookupParameter("Largura")
                      or tipo_col.LookupParameter("Width"))
        if p_prof is None:
            p_prof = (tipo_col.LookupParameter("h")
                      or tipo_col.LookupParameter("Profundidade")
                      or tipo_col.LookupParameter("Depth"))
        if p_larg is not None:
            largura_ft = p_larg.AsDouble()
        if p_prof is not None:
            profundidade_ft = p_prof.AsDouble()

    obs = montar_observacoes(classificacao)
    if profundidade_ft == 0 and largura_ft > 0:
        profundidade_ft = largura_ft
        nota_quadrada = (
            "Profundidade nao encontrada como parametro separado - assumida "
            "igual a largura (secao provavelmente quadrada)."
        )
        obs = (obs + " | " + nota_quadrada) if obs else nota_quadrada

    altura_ft = _altura_pilar_ft(coluna, doc)
    altura_m = round(altura_ft * FATOR_FT_PARA_M, 2)
    largura_cm = round(largura_ft * FATOR_FT_PARA_M * 100, 1)
    profundidade_cm = round(profundidade_ft * FATOR_FT_PARA_M * 100, 1)

    volume_m3 = round((largura_cm / 100.0) * (profundidade_cm / 100.0) * altura_m, 3)
    perimetro_m = 2 * (largura_cm + profundidade_cm) / 100.0
    area_forma_m2 = round(perimetro_m * altura_m, 2)

    return {
        "Categoria": "Pilar",
        "ID": obter_id_como_numero(coluna.Id),
        "Nivel": obter_nivel(doc, coluna),
        "Posicao": "",
        "Room_Lado1": "",
        "Room_Lado2": "",
        "Material_Estrutural": classificacao["material_estrutural"],
        "Acabamento_Lado1": "",
        "Acabamento_Lado2": "",
        "Classificacao_Automatica": classificacao["classificacao_automatica"],
        "Materiais_Brutos_Extraidos": classificacao["materiais_brutos_extraidos"],
        "Comprimento_m": "",
        "Altura_m": altura_m,
        "Largura_cm": largura_cm,
        "Profundidade_cm": profundidade_cm,
        "Espessura_cm": "",
        "Espessura_Estrutural_cm": "",
        "Area_m2": "",
        "Area_Forma_m2": area_forma_m2,
        "Volume_m3": volume_m3,
        "Observacoes": obs,
    }
