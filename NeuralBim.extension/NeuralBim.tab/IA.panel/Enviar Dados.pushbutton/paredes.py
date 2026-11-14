# -*- coding: utf-8 -*-
"""Fluxo especifico de paredes: selecao, agrupamento por tipo, deteccao de
posicao interna/externa por geometria (room dos dois lados), formulario de
classificacao (material + 2 acabamentos) e extracao de dados da parede.

Nao alterado na reorganizacao em modulos - so movido pra ca."""

from pyrevit import revit, DB, UI, forms

from comum import (
    obter_id_como_numero,
    obter_nivel,
    montar_lista_ids,
    FATOR_FT_PARA_M,
    FATOR_FT2_PARA_M2,
    FATOR_FT3_PARA_M3,
)


# ---------------------------------------------------------
# LISTAS PADRONIZADAS (so usadas pelo formulario de parede)
# ---------------------------------------------------------

MATERIAIS_ESTRUTURAIS = [
    "Bloco ceramico de vedacao 9 furos",
    "Bloco ceramico de vedacao 6 furos",
    "Bloco ceramico estrutural",
    "Bloco de concreto de vedacao",
    "Bloco de concreto estrutural",
    "Tijolo ceramico macico",
    "Drywall (gesso acartonado)",
    "Concreto armado moldado in loco",
    "Nao definido / outro",
]

ACABAMENTOS = [
    "Sem revestimento (aparente)",
    "Chapisco + reboco (sem pintura)",
    "Reboco + pintura PVA",
    "Reboco + pintura acrilica",
    "Reboco + textura acrilica",
    "Revestimento ceramico",
    "Revestimento em porcelanato",
    "Nao definido / outro",
]


# ---------------------------------------------------------
# SELECAO DE PAREDES
# ---------------------------------------------------------

class FiltroApenasParedes(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        return isinstance(element, DB.Wall)

    def AllowReference(self, reference, position):
        return False


def selecionar_paredes():
    doc = revit.doc
    uidoc = revit.uidoc
    try:
        referencias = uidoc.Selection.PickObjects(
            UI.Selection.ObjectType.Element,
            FiltroApenasParedes(),
            "Selecione as paredes desejadas e aperte Enter"
        )
    except Exception:
        return []
    return [doc.GetElement(ref) for ref in referencias]


# ---------------------------------------------------------
# FUNCOES AUXILIARES DE PAREDE
# ---------------------------------------------------------

def obter_nome_room(room):
    if room is None:
        return "Nenhum"
    try:
        nome = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
        numero = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
        return "{} ({})".format(nome, numero)
    except Exception:
        return "Nao identificado"


def obter_rooms_dos_lados(parede, doc):
    """Encontra os ambientes (Room) de cada lado da parede via ponto geometrico."""
    try:
        curva = parede.Location.Curve
        ponto_medio = curva.Evaluate(0.5, True)

        largura = parede.Width
        offset = (largura / 2.0) + 0.5

        orientacao = parede.Orientation

        ponto_lado1 = ponto_medio + orientacao.Multiply(offset)
        ponto_lado2 = ponto_medio - orientacao.Multiply(offset)

        room_lado1 = doc.GetRoomAtPoint(ponto_lado1)
        room_lado2 = doc.GetRoomAtPoint(ponto_lado2)

        return room_lado1, room_lado2
    except Exception:
        return None, None


def classificar_posicao(room_lado1, room_lado2):
    """Classificacao automatica baseada nos ambientes dos dois lados."""
    tem_lado1 = room_lado1 is not None
    tem_lado2 = room_lado2 is not None

    if tem_lado1 and tem_lado2:
        return "Interna"
    elif tem_lado1 or tem_lado2:
        return "Externa"
    else:
        return "Indefinida"


def obter_espessura_estrutural_ft(parede, doc):
    """Soma a largura (Width) das camadas com funcao estrutural
    (MaterialFunctionAssignment.Structure) do WallType da parede, em pes -
    a mesma camada que extrair_materiais_estruturais_do_tipo (comum.py) usa
    pra identificar o material, mas aqui pegando a dimensao em vez do nome.

    Diferente de parede.Width (espessura TOTAL, inclui reboco/chapisco/
    pintura): isto e so a espessura da(s) camada(s) estrutural(is).
    Se nao houver CompoundStructure ou nenhuma camada estrutural, retorna 0.
    """
    try:
        tipo_parede = doc.GetElement(parede.GetTypeId())
        estrutura = tipo_parede.GetCompoundStructure() if tipo_parede else None
        if estrutura is None:
            return 0
        return sum(
            camada.Width for camada in estrutura.GetLayers()
            if camada.Function == DB.MaterialFunctionAssignment.Structure
        )
    except Exception:
        return 0


# ---------------------------------------------------------
# FORMULARIO DE CLASSIFICACAO POR TIPO DE PAREDE (com contexto claro)
# ---------------------------------------------------------

def mostrar_contexto_do_grupo(nome_tipo, lista_paredes, indice_atual, total_tipos):
    """Exibe um aviso claro antes de iniciar as perguntas de um tipo de parede."""
    quantidade = len(lista_paredes)
    ids_texto = montar_lista_ids(lista_paredes)

    mensagem = (
        "CLASSIFICANDO TIPO {} DE {}\n\n"
        "Nome do tipo (Revit): {}\n"
        "Quantidade de paredes deste tipo na selecao: {}\n"
        "IDs das paredes: {}\n\n"
        "Nas proximas 3 telas, responda o material estrutural e os "
        "acabamentos dos dois lados para ESTE tipo de parede."
    ).format(indice_atual, total_tipos, nome_tipo, quantidade, ids_texto)

    forms.alert(mensagem, title="Contexto - Tipo {}/{}".format(indice_atual, total_tipos))


def perguntar_classificacao_do_tipo(nome_tipo, indice_atual, total_tipos):
    """Abre 3 telas de escolha para um tipo de parede e retorna o resultado."""

    prefixo = "[Tipo {}/{}] {}".format(indice_atual, total_tipos, nome_tipo)

    material = forms.SelectFromList.show(
        MATERIAIS_ESTRUTURAIS,
        title="{} - Material estrutural".format(prefixo),
        button_name="Confirmar material"
    )
    if not material:
        material = "Nao definido / outro"

    acabamento_lado1 = forms.SelectFromList.show(
        ACABAMENTOS,
        title="{} - Acabamento LADO 1".format(prefixo),
        button_name="Confirmar acabamento lado 1"
    )
    if not acabamento_lado1:
        acabamento_lado1 = "Nao definido / outro"

    acabamento_lado2 = forms.SelectFromList.show(
        ACABAMENTOS,
        title="{} - Acabamento LADO 2".format(prefixo),
        button_name="Confirmar acabamento lado 2"
    )
    if not acabamento_lado2:
        acabamento_lado2 = "Nao definido / outro"

    return {
        "material_estrutural": material,
        "acabamento_lado1": acabamento_lado1,
        "acabamento_lado2": acabamento_lado2,
    }


def agrupar_paredes_por_tipo(paredes, doc):
    """Agrupa as paredes selecionadas pelo nome do tipo (Nome_Tipo)."""
    grupos = {}
    for parede in paredes:
        tipo_parede = doc.GetElement(parede.GetTypeId())
        nome_tipo = tipo_parede.get_Parameter(
            DB.BuiltInParameter.SYMBOL_NAME_PARAM
        ).AsString() if tipo_parede else "Tipo desconhecido"

        if nome_tipo not in grupos:
            grupos[nome_tipo] = []
        grupos[nome_tipo].append(parede)

    return grupos


# ---------------------------------------------------------
# EXTRACAO DE DADOS DA PAREDE (ja convertidos e "mastigados")
# ---------------------------------------------------------

def extrair_dados_parede(parede, doc, classificacao_material):
    comprimento_param = parede.get_Parameter(DB.BuiltInParameter.CURVE_ELEM_LENGTH)
    area_param = parede.get_Parameter(DB.BuiltInParameter.HOST_AREA_COMPUTED)
    volume_param = parede.get_Parameter(DB.BuiltInParameter.HOST_VOLUME_COMPUTED)
    altura_param = parede.get_Parameter(DB.BuiltInParameter.WALL_USER_HEIGHT_PARAM)

    comprimento_ft = comprimento_param.AsDouble() if comprimento_param else 0
    area_ft2 = area_param.AsDouble() if area_param else 0
    volume_ft3 = volume_param.AsDouble() if volume_param else 0
    altura_ft = altura_param.AsDouble() if altura_param else 0

    espessura_ft = parede.Width
    espessura_estrutural_ft = obter_espessura_estrutural_ft(parede, doc)

    room_lado1, room_lado2 = obter_rooms_dos_lados(parede, doc)
    posicao = classificar_posicao(room_lado1, room_lado2)

    observacoes = []
    if posicao == "Indefinida":
        observacoes.append(
            "Sem room em um ou ambos os lados - posicao nao determinada "
            "geometricamente, revisar manualmente."
        )
    if not classificacao_material["classificacao_automatica"]:
        observacoes.append(
            "Classificacao manual - materiais brutos extraidos nao reconhecidos "
            "integralmente pelo vocabulario padronizado."
        )
    categorias_distintas = classificacao_material.get("categorias_distintas", [])
    if len(categorias_distintas) > 1:
        observacoes.append(
            "Multiplas categorias reconhecidas nas camadas estruturais: {}. "
            "Categoria reportada (Material_Estrutural) e da primeira camada "
            "da lista - conferir se e a dominante para fins de custo.".format(
                ", ".join(categorias_distintas)
            )
        )
    texto_observacoes = " | ".join(observacoes)

    return {
        "Categoria": "Parede",
        "ID": obter_id_como_numero(parede.Id),
        "Nivel": obter_nivel(doc, parede),
        "Posicao": posicao,
        "Room_Lado1": obter_nome_room(room_lado1),
        "Room_Lado2": obter_nome_room(room_lado2),
        "Material_Estrutural": classificacao_material["material_estrutural"],
        "Acabamento_Lado1": classificacao_material["acabamento_lado1"],
        "Acabamento_Lado2": classificacao_material["acabamento_lado2"],
        "Classificacao_Automatica": classificacao_material["classificacao_automatica"],
        "Materiais_Brutos_Extraidos": classificacao_material["materiais_brutos_extraidos"],
        "Comprimento_m": round(comprimento_ft * FATOR_FT_PARA_M, 2),
        "Altura_m": round(altura_ft * FATOR_FT_PARA_M, 2),
        "Largura_cm": "",
        "Profundidade_cm": "",
        "Espessura_cm": round(espessura_ft * FATOR_FT_PARA_M * 100, 1),
        "Espessura_Estrutural_cm": round(espessura_estrutural_ft * FATOR_FT_PARA_M * 100, 1),
        "Area_m2": round(area_ft2 * FATOR_FT2_PARA_M2, 2),
        "Area_Forma_m2": "",
        "Volume_m3": round(volume_ft3 * FATOR_FT3_PARA_M3, 3),
        "Observacoes": texto_observacoes,
    }
