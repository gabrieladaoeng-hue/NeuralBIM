# -*- coding: utf-8 -*-
"""Helpers compartilhados do botao 'Enviar Dados': vocabulario de material,
fatores de conversao, classificacao automatica de material, orquestracao
generica por categoria (laje/pilar), observacoes e exportacao CSV.

Nao depende de paredes.py / lajes.py / pilares.py no topo. As duas
referencias a lajes/pilares (OPCOES_MATERIAL_* e extrair_material_pilar)
sao feitas com import dentro da funcao, so em runtime, pra evitar ciclo
de import."""

from pyrevit import revit, DB, UI, forms


# ---------------------------------------------------------
# LISTAS PADRONIZADAS / CONSTANTES
# ---------------------------------------------------------

# Vocabulario inicial: substring do nome do material (Revit) -> categoria SINAPI.
# Comeca pequeno, com o que ja aparece no modelo de teste. Cresce conforme
# novos materiais forem auditados via campo "Materiais_Brutos_Extraidos".
VOCABULARIO_MATERIAIS = {
    "bloco ceramico":     "Alvenaria de bloco ceramico",
    "bloco cerâmico":     "Alvenaria de bloco ceramico",
    "ceramico":           "Alvenaria de bloco ceramico",
    "cerâmico":           "Alvenaria de bloco ceramico",
    "alvenaria":          "Alvenaria de bloco ceramico",
    "bloco de concreto":  "Alvenaria de bloco de concreto",
    "concreto":           "Concreto armado moldado in loco",
    "gesso":              "Drywall (gesso acartonado)",
    "drywall":            "Drywall (gesso acartonado)",
    "tijolo":             "Alvenaria de tijolo ceramico macico",
    "pre moldado":        "Laje pre-moldada",
    "piso sobre solo":    "Piso sobre solo",
    "trelicada":          "Laje pre-moldada trelicada (cobertura/forro)",
}

# Termos que identificam o TIPO DE PECA (bloco, tijolo): tem prioridade
# sobre termos genericos de material/composicao (alvenaria, ceramico,
# concreto...), que dizem do que a peca e feita mas nao QUAL peca e. Sem
# essa prioridade, "Alvenaria de Tijolo Ceramico Macico" seria classificado
# como bloco ceramico, porque "alvenaria"/"ceramico" sao mais longos que
# "tijolo" e bateriam primeiro so pelo criterio de tamanho da string.
# "trelicada" entrou aqui pelo mesmo motivo: e um TIPO DE PECA especifico
# (laje trelicada e um produto estrutural, nao uma composicao generica como
# "concreto"/"alvenaria"), e precisa vencer "pre moldado" (11 caracteres,
# mais longo que "trelicada", 9) se as duas substrings aparecerem juntas no
# mesmo nome bruto do Revit -- sem essa prioridade, o desempate por tamanho
# escolheria "pre moldado" primeiro e classificaria errado.
_TERMOS_TIPO_PECA = {"bloco ceramico", "bloco cerâmico", "bloco de concreto", "tijolo", "trelicada"}

FATOR_FT_PARA_M = 0.3048
FATOR_FT2_PARA_M2 = 0.092903
FATOR_FT3_PARA_M3 = 0.0283168


# ---------------------------------------------------------
# FUNCOES AUXILIARES
# ---------------------------------------------------------

def obter_id_como_numero(element_id):
    if hasattr(element_id, "Value"):
        return element_id.Value
    return element_id.IntegerValue


def obter_nivel(doc, parede):
    try:
        nivel = doc.GetElement(parede.LevelId)
        return nivel.Name if nivel else "N/A"
    except Exception:
        return "N/A"


def codificar_valor(valor):
    if isinstance(valor, (list, tuple)):
        valor = " | ".join([unicode(v) for v in valor])
    if isinstance(valor, unicode):
        return valor.encode("utf-8")
    return str(valor)


def montar_lista_ids(lista_paredes, limite=8, rotulo="paredes"):
    """Monta um texto com os IDs do grupo, limitando a exibicao.
    `rotulo` so aparece no texto de overflow (ex.: '... (+3 lajes)')."""
    ids = [str(obter_id_como_numero(p.Id)) for p in lista_paredes]
    if len(ids) > limite:
        texto = ", ".join(ids[:limite]) + ", ... (+{} {})".format(
            len(ids) - limite, rotulo
        )
    else:
        texto = ", ".join(ids)
    return texto


# ---------------------------------------------------------
# CLASSIFICACAO AUTOMATICA DE MATERIAL
# (via CompoundStructure do tipo - parede e laje)
# ---------------------------------------------------------

def extrair_materiais_estruturais_do_tipo(element_type, doc):
    """Le o CompoundStructure de um ElementType (WallType ou FloorType) e
    retorna os nomes de material das camadas com funcao estrutural.

    Retorna (lista_nomes_brutos, houve_erro_leitura).
    houve_erro=True quando nao ha CompoundStructure (ex.: curtain/stacked wall)
    ou a leitura falha -> forca o fallback manual.
    """
    nomes = []
    try:
        estrutura = element_type.GetCompoundStructure() if element_type else None
        if estrutura is None:
            return [], True
        for camada in estrutura.GetLayers():
            if camada.Function != DB.MaterialFunctionAssignment.Structure:
                continue
            material = doc.GetElement(camada.MaterialId)
            nomes.append(material.Name if material else "<sem material>")
    except Exception:
        return nomes, True
    return nomes, False


def classificar_material_automatico(nomes_materiais):
    """Casa cada nome bruto com o VOCABULARIO_MATERIAIS.

    Retorna (sucesso, categoria, categorias_distintas):
    - sucesso=True apenas se a lista nao for vazia e TODAS as camadas
      baterem com alguma entrada do vocabulario;
    - categoria = a da primeira camada da lista (mantido por
      compatibilidade - e o que fica em Material_Estrutural);
    - categorias_distintas = lista sem duplicar de todas as categorias
      encontradas entre as camadas, na ordem em que apareceram. Mais de
      uma categoria distinta = camadas estruturais de materiais
      diferentes (ex.: concreto + pre-moldado) - fica pra quem chama
      decidir se registra isso em Observacoes.
    """
    if not nomes_materiais:
        return False, None, []

    # 1o criterio: termos de tipo de peca (bloco/tijolo) antes dos termos
    # genericos de material; 2o criterio, dentro de cada grupo: chave mais
    # longa primeiro (resolve ambiguidade de substring, ex. "bloco de
    # concreto" antes de "concreto"). Nao confia na ordem de insercao do
    # dict, que IronPython/Python 2.7 nao garante.
    chaves_ordenadas = sorted(
        VOCABULARIO_MATERIAIS.keys(),
        key=lambda chave: (chave not in _TERMOS_TIPO_PECA, -len(chave))
    )

    categorias = []
    for nome in nomes_materiais:
        nome_norm = nome.strip().lower()
        categoria = None
        for chave in chaves_ordenadas:
            if chave in nome_norm:
                categoria = VOCABULARIO_MATERIAIS[chave]
                break
        if categoria is None:
            return False, None, []
        categorias.append(categoria)

    categorias_distintas = []
    for categoria in categorias:
        if categoria not in categorias_distintas:
            categorias_distintas.append(categoria)

    return True, categorias[0], categorias_distintas


def classificar_material_via_compound(element_type, doc):
    """Adaptador: extrai os materiais estruturais do tipo e ja classifica.
    Retorna (sucesso, categoria, nomes_brutos) - mesmo formato de
    extrair_material_pilar, pra o pipeline tratar parede/laje/pilar igual."""
    nomes_brutos, houve_erro = extrair_materiais_estruturais_do_tipo(element_type, doc)
    if houve_erro:
        return False, None, nomes_brutos
    sucesso, categoria, categorias_distintas = classificar_material_automatico(nomes_brutos)
    return sucesso, categoria, nomes_brutos


# ---------------------------------------------------------
# ORQUESTRACAO GENERICA POR CATEGORIA (laje / pilar)
# ---------------------------------------------------------

def agrupar_elementos_por_tipo(elementos, doc):
    """Versao generica de agrupar_paredes_por_tipo: agrupa por Element.Name
    do tipo (robusto p/ FloorType e FamilySymbol)."""
    grupos = {}
    for elemento in elementos:
        tipo = doc.GetElement(elemento.GetTypeId())
        try:
            nome_tipo = tipo.Name if tipo is not None else "Tipo desconhecido"
        except Exception as erro:
            nome_tipo = "Tipo desconhecido (ID {} - {})".format(
                obter_id_como_numero(tipo.Id), erro
            )
        grupos.setdefault(nome_tipo, []).append(elemento)
    return grupos


def montar_observacoes(classificacao, posicao=""):
    """Texto de Observacoes comum a todas as categorias. O ramo de posicao
    'Indefinida' so ocorre em parede (as outras passam posicao='')."""
    obs = []
    if posicao == "Indefinida":
        obs.append(
            "Sem room em um ou ambos os lados - posicao nao determinada "
            "geometricamente, revisar manualmente."
        )
    if not classificacao["classificacao_automatica"]:
        obs.append(
            "Classificacao manual - materiais brutos extraidos nao reconhecidos "
            "integralmente pelo vocabulario padronizado."
        )
    categorias_distintas = classificacao.get("categorias_distintas", [])
    if len(categorias_distintas) > 1:
        obs.append(
            "Multiplas categorias reconhecidas nas camadas estruturais: {}. "
            "Categoria reportada (Material_Estrutural) e da primeira camada "
            "da lista - conferir se e a dominante para fins de custo.".format(
                ", ".join(categorias_distintas)
            )
        )
    return " | ".join(obs)


def avisar_contexto_categoria(rotulo, nome_tipo, elementos, indice_atual, total_tipos):
    """Equivalente neutro de mostrar_contexto_do_grupo p/ laje e pilar."""
    ids_texto = montar_lista_ids(elementos, rotulo=rotulo)
    mensagem = (
        "CLASSIFICANDO TIPO {} DE {} - {}\n\n"
        "Nome do tipo (Revit): {}\n"
        "Quantidade de elementos deste tipo na selecao: {}\n"
        "IDs: {}\n\n"
        "Na proxima tela, responda apenas o material estrutural."
    ).format(indice_atual, total_tipos, rotulo.upper(), nome_tipo,
             len(elementos), ids_texto)
    forms.alert(
        mensagem,
        title="Contexto - {} {}/{}".format(rotulo, indice_atual, total_tipos)
    )


def perguntar_material_estrutural_simples(nome_tipo, indice, total_tipos, opcoes, rotulo):
    """Mostra APENAS a tela de material estrutural (mesmo mecanismo de lista
    do perguntar_classificacao_do_tipo), sem nenhuma tela de acabamento.

    Devolve o mesmo formato de dict que resolver_classificacao espera. Os
    acabamentos ficam fixos em 'Nao definido / outro' porque nao se aplicam
    a laje/pilar.
    """
    prefixo = "[{} {}/{}] {}".format(rotulo.capitalize(), indice, total_tipos, nome_tipo)

    material = forms.SelectFromList.show(
        opcoes,
        title="{} - Material estrutural".format(prefixo),
        button_name="Confirmar material"
    )
    if not material:
        material = "Nao definido / outro"

    return {
        "material_estrutural": material,
        "acabamento_lado1": "Nao definido / outro",
        "acabamento_lado2": "Nao definido / outro",
    }


def resolver_classificacao(rotulo, nome_tipo, elementos, indice_atual,
                           total_tipos, tripla_auto):
    """A partir de (sucesso, categoria, nomes_brutos): se sucesso, monta o
    dict de classificacao automatica; senao, cai no formulario manual
    existente (perguntar_classificacao_do_tipo), igual ao fluxo de parede."""
    sucesso, categoria_auto, nomes_brutos = tripla_auto
    if sucesso:
        _, _, categorias_distintas = classificar_material_automatico(nomes_brutos)
        return {
            "material_estrutural": categoria_auto,
            "acabamento_lado1": "Nao definido / outro",
            "acabamento_lado2": "Nao definido / outro",
            "classificacao_automatica": True,
            "materiais_brutos_extraidos": nomes_brutos,
            "categorias_distintas": categorias_distintas,
        }

    avisar_contexto_categoria(rotulo, nome_tipo, elementos, indice_atual, total_tipos)
    if rotulo == "pilares":
        from pilares import OPCOES_MATERIAL_PILAR as opcoes
    else:
        from lajes import OPCOES_MATERIAL_LAJE as opcoes
    manual = perguntar_material_estrutural_simples(
        nome_tipo, indice_atual, total_tipos, opcoes, rotulo
    )
    manual["classificacao_automatica"] = False
    manual["materiais_brutos_extraidos"] = nomes_brutos
    return manual


def processar_categoria(elementos, doc, rotulo, funcao_extracao, usa_compound):
    """Loop generico: agrupa por tipo -> resolve classificacao (auto/manual)
    por tipo -> extrai cada elemento. Retorna lista de dicts.

    usa_compound=True  -> material via CompoundStructure do tipo (laje).
    usa_compound=False -> material via parametro do elemento (pilar), lido
                          da 1a instancia do grupo (aproximacao por tipo).
    """
    grupos = agrupar_elementos_por_tipo(elementos, doc)
    lista_tipos = list(grupos.keys())
    total_tipos = len(lista_tipos)

    classificacao_por_tipo = {}
    for indice, nome_tipo in enumerate(lista_tipos, start=1):
        elementos_do_tipo = grupos[nome_tipo]
        amostra = elementos_do_tipo[0]

        if usa_compound:
            tipo_elem = doc.GetElement(amostra.GetTypeId())
            tripla = classificar_material_via_compound(tipo_elem, doc)
        else:
            from pilares import extrair_material_pilar
            tripla = extrair_material_pilar(amostra, doc)

        classificacao_por_tipo[nome_tipo] = resolver_classificacao(
            rotulo, nome_tipo, elementos_do_tipo, indice, total_tipos, tripla
        )

    registros = []
    for nome_tipo, elementos_do_tipo in grupos.items():
        classificacao = classificacao_por_tipo[nome_tipo]
        for elemento in elementos_do_tipo:
            registros.append(funcao_extracao(elemento, doc, classificacao))
    return registros


# ---------------------------------------------------------
# SELECAO GENERICA (serve laje e pilar)
# ---------------------------------------------------------

def selecionar_elementos(selection_filter, mensagem):
    """Selecao generica via PickObjects. Mesmo corpo de selecionar_paredes(),
    mas com o filtro e a mensagem parametrizados (serve laje e pilar)."""
    uidoc = revit.uidoc
    try:
        referencias = uidoc.Selection.PickObjects(
            UI.Selection.ObjectType.Element, selection_filter, mensagem
        )
    except Exception:
        return []
    return [revit.doc.GetElement(ref) for ref in referencias]


# ---------------------------------------------------------
# EXPORTACAO CSV COM JANELA "SALVAR COMO"
# ---------------------------------------------------------

def exportar_csv(dados):
    colunas = [
        "Categoria",
        "ID", "Nivel", "Posicao", "Room_Lado1", "Room_Lado2",
        "Material_Estrutural", "Acabamento_Lado1", "Acabamento_Lado2",
        "Classificacao_Automatica", "Materiais_Brutos_Extraidos",
        "Comprimento_m", "Altura_m", "Largura_cm", "Profundidade_cm",
        "Espessura_cm", "Espessura_Estrutural_cm", "Area_m2", "Area_Forma_m2", "Volume_m3",
        "Observacoes",
        "Timestamp_Inicio_Execucao", "Timestamp_Fim_Execucao",
    ]

    caminho_escolhido = forms.save_file(file_ext="csv")
    if not caminho_escolhido:
        return None

    arquivo_csv = open(caminho_escolhido, "wb")
    try:
        arquivo_csv.write("\xef\xbb\xbf")

        linha_cabecalho = ";".join([codificar_valor(c) for c in colunas]) + "\r\n"
        arquivo_csv.write(linha_cabecalho)

        for linha in dados:
            valores = [codificar_valor(linha[c]) for c in colunas]
            arquivo_csv.write(";".join(valores) + "\r\n")
    finally:
        arquivo_csv.close()

    return caminho_escolhido
