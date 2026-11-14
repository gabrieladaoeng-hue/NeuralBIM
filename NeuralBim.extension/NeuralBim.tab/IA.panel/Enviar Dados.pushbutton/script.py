# -*- coding: utf-8 -*-
"""Botao 'Enviar Dados' - ponto de entrada. Seleciona parede/laje/pilar em
3 etapas e consolida tudo num CSV unico com timestamp de execucao.

A logica mora nos modulos irmaos: comum.py (helpers, classificacao,
orquestracao laje/pilar, CSV), paredes.py, lajes.py, pilares.py."""

import datetime

from pyrevit import revit, forms

from comum import (
    selecionar_elementos,
    extrair_materiais_estruturais_do_tipo,
    classificar_material_automatico,
    processar_categoria,
    exportar_csv,
)
from paredes import (
    selecionar_paredes,
    agrupar_paredes_por_tipo,
    mostrar_contexto_do_grupo,
    perguntar_classificacao_do_tipo,
    extrair_dados_parede,
)
from lajes import FiltroApenasLajes, extrair_dados_laje
from pilares import FiltroApenasPilares, extrair_dados_pilar
from envio_api import enviar_dados_para_api


# ---------------------------------------------------------
# EXECUCAO PRINCIPAL
# ---------------------------------------------------------

doc = revit.doc

timestamp_inicio = datetime.datetime.now()

forms.alert(
    "ETAPA 1 de 3: Selecione as PAREDES do modelo. Clique OK e depois "
    "selecione os elementos no Revit."
)
paredes = selecionar_paredes()

forms.alert(
    "ETAPA 2 de 3: Selecione as LAJES do modelo. Clique OK e depois "
    "selecione os elementos no Revit."
)
lajes = selecionar_elementos(
    FiltroApenasLajes(), "Selecione as lajes desejadas e aperte Enter"
)

forms.alert(
    "ETAPA 3 de 3: Selecione os PILARES do modelo. Clique OK e depois "
    "selecione os elementos no Revit."
)
pilares = selecionar_elementos(
    FiltroApenasPilares(), "Selecione os pilares desejados e aperte Enter"
)

if not paredes and not lajes and not pilares:
    forms.alert("Nenhum elemento (parede, laje ou pilar) foi selecionado.")
else:
    dados_finais = []

    # ---------- PAREDES (fluxo original, inalterado) ----------
    if paredes:
        grupos_por_tipo = agrupar_paredes_por_tipo(paredes, doc)
        lista_tipos = list(grupos_por_tipo.keys())
        total_tipos = len(lista_tipos)

        classificacao_por_tipo = {}
        for indice, nome_tipo in enumerate(lista_tipos, start=1):
            lista_paredes_do_tipo = grupos_por_tipo[nome_tipo]

            wall_type = doc.GetElement(lista_paredes_do_tipo[0].GetTypeId())
            materiais_brutos, houve_erro = extrair_materiais_estruturais_do_tipo(wall_type, doc)
            auto_ok, categoria_auto, categorias_distintas = classificar_material_automatico(materiais_brutos)

            if auto_ok and not houve_erro:
                classificacao_por_tipo[nome_tipo] = {
                    "material_estrutural": categoria_auto,
                    "acabamento_lado1": "Nao definido / outro",
                    "acabamento_lado2": "Nao definido / outro",
                    "classificacao_automatica": True,
                    "materiais_brutos_extraidos": materiais_brutos,
                    "categorias_distintas": categorias_distintas,
                }
            else:
                mostrar_contexto_do_grupo(nome_tipo, lista_paredes_do_tipo, indice, total_tipos)
                manual = perguntar_classificacao_do_tipo(nome_tipo, indice, total_tipos)
                manual["classificacao_automatica"] = False
                manual["materiais_brutos_extraidos"] = materiais_brutos
                classificacao_por_tipo[nome_tipo] = manual

        for nome_tipo, lista_paredes in grupos_por_tipo.items():
            classificacao = classificacao_por_tipo[nome_tipo]
            for parede in lista_paredes:
                dados_finais.append(extrair_dados_parede(parede, doc, classificacao))

    # ---------- LAJES ----------
    if lajes:
        dados_finais.extend(
            processar_categoria(lajes, doc, "lajes", extrair_dados_laje, usa_compound=True)
        )

    # ---------- PILARES ----------
    if pilares:
        dados_finais.extend(
            processar_categoria(pilares, doc, "pilares", extrair_dados_pilar, usa_compound=False)
        )

    timestamp_fim = datetime.datetime.now()

    inicio_str = timestamp_inicio.strftime("%Y-%m-%d %H:%M:%S")
    fim_str = timestamp_fim.strftime("%Y-%m-%d %H:%M:%S")

    # Envio HTTP para a API (Fase 2). Nao bloqueia nem quebra o fluxo:
    # se falhar, so avisa; a exportacao do CSV acontece de qualquer jeito.
    envio_ok, envio_msg = enviar_dados_para_api(inicio_str, fim_str, dados_finais)
    if envio_ok:
        forms.alert("Envio para a API: OK\n\n{}".format(envio_msg))
    else:
        forms.alert("Envio para a API: FALHOU\n\n{}".format(envio_msg))

    for linha in dados_finais:
        linha["Timestamp_Inicio_Execucao"] = inicio_str
        linha["Timestamp_Fim_Execucao"] = fim_str

    caminho_salvo = exportar_csv(dados_finais)

    if caminho_salvo:
        forms.alert(
            "{} elemento(s) exportado(s) com sucesso para:\n{}".format(
                len(dados_finais), caminho_salvo
            )
        )
    else:
        forms.alert("Exportacao cancelada pelo usuario.")
