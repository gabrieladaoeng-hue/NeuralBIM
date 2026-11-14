"""Etapa 8b: segundo modo de estimativa, paralelo ao SINAPI (Fase 6,
estimativa_ia.py) -- a IA estima o preco unitario de mercado a partir do
proprio conhecimento, SEM nenhuma fonte oficial (nada de codigo SINAPI ou
preco de referencia no prompt). Serve pra comparar, no mesmo quantitativo,
uma estimativa ancorada em base oficial (RAG/SINAPI) contra uma nao
ancorada -- nunca substitui o modo SINAPI, nunca e usado por ele.

Diferenca central de responsabilidade em relacao ao modo SINAPI: la a IA
recebe o preco JA calculado (preco_unitario_rs) e o codigo dela e multiplicar
e somar -- o que gerou o achado documentado no CLAUDE.md de erro sistematico
de aritmetica. Aqui a IA NUNCA multiplica: devolve so uma faixa de preco
unitario (minimo/provavel/maximo) e todo o calculo (preco x quantidade,
totais do lote) e feito em Python, em _validar_e_calcular_mercado.
"""

import json
from pathlib import Path

import boto3

from agrupamento import agrupar_elementos
from config import ESTIMATIVAS_MERCADO_DIR
from estimativa_ia import (
    _extrair_uso_tokens,
    _gravar_estimativa_versionada,
    _remover_cercas_markdown,
    _rotulo_grupo,
    _somar_uso_tokens,
)
from precificacao import _quantidade_por_unidade

# Mesmo modelo/regiao/temperatura ja validados no modo SINAPI
# (estimativa_ia.py) -- duplicados aqui de proposito (constantes pequenas,
# nao logica) em vez de importar nomes privados de outro modulo so pra isso.
_REGION_NAME = "us-east-2"
_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_REGIAO_MERCADO = "Parana, Brasil"

_SYSTEM_PROMPT_MERCADO = (
    "Voce e um assistente de orcamentacao de obras. Recebera a descricao de "
    "um servico ou material de construcao civil e deve estimar seu preco "
    "unitario praticado no mercado da regiao informada, incluindo material "
    "e mao de obra, como seria cotado por um fornecedor ou empreiteiro "
    "local.\n\n"
    "Voce NAO tem acesso a internet. Sua estimativa vem exclusivamente do "
    "seu conhecimento previo, sem consulta a nenhuma fonte, e deve ser "
    "tratada como ordem de grandeza -- nao como cotacao verificada.\n\n"
    "Devolva uma FAIXA de preco unitario (minimo, provavel, maximo) que "
    "reflita honestamente sua incerteza: faixas estreitas so para itens "
    "padronizados e comuns, faixas largas para itens variaveis ou que voce "
    "conhece mal. Nunca multiplique por quantidade, nunca calcule totais -- "
    "devolva apenas o preco por unidade. Declare explicitamente no campo "
    "premissas tudo que assumiu (tipo de acabamento, incluso ou nao mao de "
    "obra, condicoes de obra), e no campo limitacoes o que reduz a "
    "confiabilidade da sua estimativa."
)

_FORMATO_SAIDA_MERCADO = (
    "{\n"
    '  "preco_unitario_minimo_rs": 0.0,\n'
    '  "preco_unitario_provavel_rs": 0.0,\n'
    '  "preco_unitario_maximo_rs": 0.0,\n'
    '  "unidade": "...",\n'
    '  "premissas": ["..."],\n'
    '  "limitacoes": ["..."],\n'
    '  "confianca_declarada": "alta|media|baixa"\n'
    "}"
)

# Categoria -> unidade padrao pro modo mercado, ja que sem SINAPI nao existe
# codigo pra ditar a unidade. Mesma convencao ja implicita em
# precificacao._quantidade_por_unidade (M2 por area, M3 por volume) --
# nao inventa nada novo, so torna essa convencao explicita por categoria.
_UNIDADE_POR_CATEGORIA = {"Parede": "M2", "Laje": "M2", "Pilar": "M3"}


def resolver_dados_mercado(elemento):
    """Equivalente a precificacao.resolver_preco_elemento, mas para o modo
    mercado: NAO consulta mapeamento_sinapi.json nem preco_sinapi_pr.json --
    so determina a unidade (por categoria) e a quantidade do elemento nessa
    unidade. Nunca falha por falta de codigo SINAPI (nao usa nenhum); so
    falha se a categoria nao tiver unidade padrao definida ou se o campo de
    quantidade correspondente estiver ausente no elemento.

    Formatos de retorno:
    - {"tipo": "mercado", "unidade": "M2"|"M3", "quantidade": <float>,
       "espessura_cm": <float ou None>}
    - {"tipo": "erro", "motivo": str}
    """
    categoria = elemento.get("Categoria")
    material = elemento.get("Material_Estrutural")

    unidade = _UNIDADE_POR_CATEGORIA.get(categoria)
    if unidade is None:
        return {
            "tipo": "erro",
            "motivo": "Categoria '{}' sem unidade padrao definida para o modo mercado.".format(
                categoria
            ),
        }

    quantidade = _quantidade_por_unidade(unidade, elemento)
    if quantidade is None:
        return {
            "tipo": "erro",
            "motivo": (
                "Nao foi possivel determinar a quantidade (unidade '{}') "
                "para elemento='{}' / Material_Estrutural='{}'."
            ).format(unidade, categoria, material),
        }

    return {
        "tipo": "mercado",
        "unidade": unidade,
        "quantidade": quantidade,
        "espessura_cm": elemento.get("Espessura_Estrutural_cm"),
    }


def _chave_mercado(elemento, dados):
    """Agrupa por Material_Estrutural + espessura EXATA (sem bucket -- sem
    uma tabela de referencia dizendo que duas espessuras proximas tem o
    mesmo preco de mercado, arredondar seria inventar uma equivalencia que a
    IA nao fez). Categoria ja entra na chave por fora, em agrupar_elementos."""
    return (elemento.get("Material_Estrutural"), dados.get("espessura_cm"))


def _somar_mercado(membros):
    """Ao contrario do modo SINAPI, aqui nao ha preco pra mesclar no momento
    do agrupamento (o preco so existe depois da IA responder, uma vez por
    grupo) -- so a quantidade e somada."""
    return {
        "tipo": "mercado",
        "unidade": membros[0]["unidade"],
        "quantidade": sum(membro["quantidade"] for membro in membros),
        "espessura_cm": membros[0]["espessura_cm"],
    }


def _montar_user_message_mercado(elemento, dados_mercado):
    entrada = {
        "categoria": elemento.get("Categoria"),
        "material": elemento.get("Material_Estrutural"),
    }
    if dados_mercado.get("espessura_cm") is not None:
        entrada["espessura_cm"] = dados_mercado["espessura_cm"]
    entrada["unidade"] = dados_mercado["unidade"]
    entrada["regiao"] = _REGIAO_MERCADO

    entrada_json = json.dumps(entrada, ensure_ascii=False, indent=2)

    partes = [
        "Servico/material a estimar (sem nenhum codigo ou preco de "
        "referencia -- estime pelo seu conhecimento previo, nunca "
        "multiplique por quantidade):",
        entrada_json,
        "",
        "Responda APENAS com um objeto JSON, sem nenhum texto antes ou "
        "depois e SEM cercas de markdown (```) -- exatamente neste formato:",
        _FORMATO_SAIDA_MERCADO,
    ]
    return "\n".join(partes)


def _preco_valido(valor):
    return isinstance(valor, (int, float)) and valor > 0


def _validar_e_calcular_mercado(resultado, dados_mercado):
    """Calcula os 3 custos (preco x quantidade, SEMPRE em Python, nunca pela
    IA) e roda a validacao de sanidade da faixa. NUNCA corrige os valores da
    IA -- so sinaliza. Devolve {"erro": ...} se algum preco vier ausente ou
    <= 0 (nesse caso, nao estima nada pro grupo)."""
    minimo = resultado.get("preco_unitario_minimo_rs")
    provavel = resultado.get("preco_unitario_provavel_rs")
    maximo = resultado.get("preco_unitario_maximo_rs")

    if not (_preco_valido(minimo) and _preco_valido(provavel) and _preco_valido(maximo)):
        return {
            "erro": "Preco unitario ausente ou <= 0 na resposta da IA (modo mercado).",
            "resposta_ia": resultado,
        }

    quantidade = dados_mercado["quantidade"]
    resultado["custo_minimo_rs"] = round(minimo * quantidade, 2)
    resultado["custo_provavel_rs"] = round(provavel * quantidade, 2)
    resultado["custo_maximo_rs"] = round(maximo * quantidade, 2)

    if minimo > provavel or provavel > maximo:
        resultado["faixa_inconsistente"] = True
        resultado["confianca_declarada"] = "baixa"

    resultado["origem_preco"] = "estimado_pelo_modelo_sem_fonte_verificada"
    return resultado


def gerar_estimativa_mercado_ia(elemento, dados_mercado):
    """Chama o Bedrock pra estimar a faixa de preco unitario de mercado de
    UM grupo -- nunca inventa numero: se a chamada falhar, a resposta nao
    for um JSON valido, ou os precos forem invalidos (ausentes/<=0),
    devolve {"erro": ...} e o grupo fica de fora dos totais."""
    user_message = _montar_user_message_mercado(elemento, dados_mercado)

    client = boto3.client("bedrock-runtime", region_name=_REGION_NAME)
    try:
        resposta = client.converse(
            modelId=_MODEL_ID,
            system=[{"text": _SYSTEM_PROMPT_MERCADO}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"temperature": 0.1},
        )
    except Exception as erro:
        return {
            "erro": "Falha ao chamar o Bedrock: {}".format(erro),
            "categoria": elemento.get("Categoria"),
        }

    uso_tokens = _extrair_uso_tokens(resposta)

    texto_resposta = resposta["output"]["message"]["content"][0]["text"]
    texto_limpo = _remover_cercas_markdown(texto_resposta)

    try:
        resultado = json.loads(texto_limpo)
    except json.JSONDecodeError as erro:
        return {
            "erro": "Resposta da IA nao e um JSON valido: {}".format(erro),
            "resposta_bruta": texto_resposta,
            "categoria": elemento.get("Categoria"),
            "uso_tokens": uso_tokens,
        }

    resultado = _validar_e_calcular_mercado(resultado, dados_mercado)
    resultado["categoria"] = elemento.get("Categoria")
    resultado["uso_tokens"] = uso_tokens
    return resultado


def gerar_estimativa_mercado_lote(caminho_lote):
    """Roda o fluxo completo do modo mercado (agrupamento + IA, SEM
    retrieval SINAPI) pra todos os elementos de um lote. Mesma estrutura de
    gerar_estimativa_lote (estimativa_ia.py), com as pecas que realmente
    diferem (chave de agrupamento, chamada a IA, calculo, formato de saida)
    proprias deste modulo -- ver contrato do modo mercado_ia.

    Elemento sem unidade padrao ou sem quantidade determinavel NAO e
    agrupado e NAO chama o Bedrock -- fica de fora dos totais, como no modo
    SINAPI.
    """
    with open(caminho_lote, "r", encoding="utf-8") as arquivo:
        lote = json.load(arquivo)

    grupos = agrupar_elementos(lote["elementos"], resolver_dados_mercado, _chave_mercado, _somar_mercado)

    estimativa_por_elemento = []
    qtd_elementos_originais = 0
    qtd_erro_retrieval = 0
    qtd_erro_ia = 0
    qtd_faixa_inconsistente = 0

    for item in grupos:
        if item["tipo"] == "erro":
            qtd_erro_retrieval += 1
            qtd_elementos_originais += 1
            estimativa_por_elemento.append({
                "elemento_id": item["elemento_id"],
                "categoria": item["categoria"],
                "erro": item["motivo"],
                "tipo_erro": "retrieval",
                "quantidade_elementos_agrupados": 1,
            })
            continue

        elemento = item["elemento"]
        dados_mercado = item["dados_preco"]
        elementos_originais = item["elementos_originais"]
        quantidade_grupo = item["quantidade_elementos_agrupados"]
        qtd_elementos_originais += quantidade_grupo
        rotulo_grupo = _rotulo_grupo(elemento, quantidade_grupo)

        resultado = gerar_estimativa_mercado_ia(elemento, dados_mercado)

        if "erro" in resultado:
            qtd_erro_ia += 1
            resultado = dict(resultado)
            resultado["elemento_id"] = rotulo_grupo
            resultado["elementos_originais"] = elementos_originais
            resultado["quantidade_elementos_agrupados"] = quantidade_grupo
            resultado["quantidade"] = dados_mercado["quantidade"]
            resultado["tipo_erro"] = "ia"
            estimativa_por_elemento.append(resultado)
            continue

        resultado["elemento_id"] = rotulo_grupo
        resultado["elementos_originais"] = elementos_originais
        resultado["quantidade_elementos_agrupados"] = quantidade_grupo
        # Quantidade real do grupo (soma exata feita em _somar_mercado, ANTES
        # de qualquer arredondamento de exibicao) -- gravada explicita pra o
        # frontend nunca precisar derivar por divisao inversa
        # (custo_provavel_rs / preco_unitario_provavel_rs), o que geraria
        # dizima por operar sobre valores ja arredondados a 2 casas.
        resultado["quantidade"] = dados_mercado["quantidade"]

        if resultado.get("faixa_inconsistente"):
            qtd_faixa_inconsistente += 1
        estimativa_por_elemento.append(resultado)

    custo_total_minimo_rs = sum(
        item["custo_minimo_rs"] for item in estimativa_por_elemento if "custo_minimo_rs" in item
    )
    custo_total_provavel_rs = sum(
        item["custo_provavel_rs"] for item in estimativa_por_elemento if "custo_provavel_rs" in item
    )
    custo_total_maximo_rs = sum(
        item["custo_maximo_rs"] for item in estimativa_por_elemento if "custo_maximo_rs" in item
    )
    qtd_total_entradas = len(estimativa_por_elemento)
    qtd_com_custo = qtd_total_entradas - qtd_erro_retrieval - qtd_erro_ia
    qtd_excluidas_da_soma = qtd_erro_retrieval + qtd_erro_ia

    observacoes_gerais = (
        "Lote com {} elemento(s) original(is), agrupados em {} entrada(s) "
        "(mesma categoria + mesmo Material_Estrutural + mesma espessura "
        "estrutural exata, quando houver -- sem SINAPI, sem bucket "
        "aproximado): {} com faixa de preco estimada (das quais {} com "
        "faixa_inconsistente=true -- revisar); {} sem unidade/quantidade "
        "determinavel e {} com falha na chamada, no parse ou na validacao "
        "de sanidade da resposta da IA -- essas {} entrada(s) ficaram de "
        "fora dos totais."
    ).format(
        qtd_elementos_originais,
        qtd_total_entradas,
        qtd_com_custo,
        qtd_faixa_inconsistente,
        qtd_erro_retrieval,
        qtd_erro_ia,
        qtd_excluidas_da_soma,
    )

    resultado_final = {
        "versao_schema": 2,
        "modo": "mercado_ia",
        "origem_preco": "estimado_pelo_modelo_sem_fonte_verificada",
        "rotulo_interface": "Estimativa sem base oficial (conhecimento do modelo)",
        "estimativa_por_elemento": estimativa_por_elemento,
        "custo_total_minimo_rs": round(custo_total_minimo_rs, 2),
        "custo_total_provavel_rs": round(custo_total_provavel_rs, 2),
        "custo_total_maximo_rs": round(custo_total_maximo_rs, 2),
        "observacoes_gerais": observacoes_gerais,
        "quantidade_chamadas_ia": qtd_total_entradas - qtd_erro_retrieval,
        "uso_tokens_total_lote": _somar_uso_tokens(estimativa_por_elemento),
    }

    _gravar_estimativa_versionada(
        ESTIMATIVAS_MERCADO_DIR,
        Path(caminho_lote).stem,
        resultado_final,
        prefixo="estimativa_mercado",
    )

    return resultado_final
