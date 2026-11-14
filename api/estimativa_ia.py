"""Fase 6: chamada ao Bedrock (Claude Haiku 4.5) pra analisar a estimativa de
custo de um elemento, a partir do quantitativo (elemento) e do(s) preco(s)
recuperado(s) via resolver_preco_elemento.

A IA NAO faz mais aritmetica (ver correcao registrada no CLAUDE.md, Fase 6):
preco vem da tabela SINAPI e quantidade vem do modelo BIM, os dois ja
deterministicos antes da chamada -- multiplicar/somar e sempre feito em
Python, em _calcular_custo_do_item/_definir_custo_calculado. A IA so avalia
se a correspondencia elemento -> codigo(s) SINAPI faz sentido e registra as
decisoes de interpretacao (memoria_calculo/suposicoes). Ver
docs/modulo_ia_fase6_spec_prompt.md pro contrato historico (desatualizado
nesse ponto especifico -- mantido como referencia da fase anterior).
"""

import json
from datetime import datetime
from pathlib import Path

import boto3

from agrupamento import agrupar_elementos
from config import ESTIMATIVAS_DIR
from precificacao import resolver_preco_elemento

_REGION_NAME = "us-east-2"
_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_SYSTEM_PROMPT = (
    "Voce e um modulo de analise de custos de construcao civil. Recebe "
    "quantitativos extraidos de um modelo BIM (Revit) e registros oficiais "
    "de preco da tabela SINAPI-PR -- que podem vir como um preco unico ou "
    "como uma lista de componentes (quando a composicao foi decomposta). "
    "O calculo do custo (preco x quantidade) e feito pelo sistema, nao por "
    "voce. Sua tarefa e avaliar se a correspondencia entre o elemento e "
    "o(s) codigo(s) SINAPI recuperado(s) faz sentido, e registrar em texto "
    "as decisoes de interpretacao envolvidas -- divergencias de unidade, "
    "multiplas categorias de material por elemento, ou qualquer ajuste que "
    "a correspondencia exija. Nenhuma suposicao pode ser silenciosa: toda "
    "decisao de desambiguacao deve ser explicitada no campo suposicoes da "
    "resposta."
)

_FORMATO_DIRETO = (
    "{\n"
    '  "elemento_id": "...",\n'
    '  "codigo_sinapi_usado": "...",\n'
    '  "memoria_calculo": "...",\n'
    '  "suposicoes": []\n'
    "}"
)

_FORMATO_DECOMPOSTO = (
    "{\n"
    '  "elemento_id": "...",\n'
    '  "codigos_sinapi_usados": ["...", "..."],\n'
    '  "memoria_calculo": "...",\n'
    '  "suposicoes": []\n'
    "}"
)


def _montar_user_message(elemento, dados_preco):
    elemento_id = "{}_{}".format(
        str(elemento.get("Categoria", "elemento")).lower(), elemento.get("ID", "?")
    )
    elemento_json = json.dumps(elemento, ensure_ascii=False, indent=2)
    dados_preco_json = json.dumps(dados_preco, ensure_ascii=False, indent=2)
    resolucao = dados_preco.get("tipo")

    partes = [
        "Quantitativo do elemento (schema Elemento, extraido do modelo BIM):",
        elemento_json,
        "",
        "Preco(s) recuperado(s) da tabela SINAPI-PR (resolucao '{}'):".format(resolucao),
        dados_preco_json,
        "",
        "O preco unitario e a quantidade de cada item acima ja foram "
        "resolvidos pelo sistema (preco vem da tabela SINAPI, quantidade "
        "vem do quantitativo do modelo BIM) -- o calculo do custo (preco x "
        "quantidade) e feito pelo sistema, nao por voce. Sua tarefa e "
        "avaliar se a correspondencia entre o elemento e o(s) codigo(s) "
        "SINAPI faz sentido e registrar, em memoria_calculo, a "
        "justificativa dessa correspondencia e qualquer decisao de "
        "interpretacao necessaria.",
        "",
        "Casos especiais a tratar explicitamente quando se aplicarem: (1) se "
        "a unidade do preco nao bater com o quantitativo disponivel, "
        "explique em memoria_calculo como a espessura informada resolve "
        "essa conversao; (2) se o campo Observacoes indicar multiplas "
        "categorias de material reconhecidas no elemento, decida como "
        "combinar/ponderar os codigos SINAPI envolvidos e registre a "
        "decisao em suposicoes; (3) se a resolucao for 'decomposto', "
        "justifique a aplicacao de cada componente da lista em "
        "memoria_calculo, nao so do conjunto.",
        "",
        "Gere a analise deste elemento. Use elemento_id = '{}'.".format(
            elemento_id
        ),
        "Responda APENAS com um objeto JSON, sem nenhum texto antes ou "
        "depois e SEM cercas de markdown (```) -- somente a entrada de "
        "estimativa_por_elemento correspondente a ESTE elemento (um unico "
        "objeto, nao uma lista).",
        "",
        "Se o preco for unico (resolucao 'direto' ou "
        "'por_espessura_estrutural_cm'), use este formato:",
        _FORMATO_DIRETO,
        "",
        "Se o preco for decomposto (lista de componentes), use este formato:",
        _FORMATO_DECOMPOSTO,
    ]
    return "\n".join(partes)


def _remover_cercas_markdown(texto):
    texto = texto.strip()
    if texto.startswith("```"):
        partes = texto.split("\n", 1)
        texto = partes[1] if len(partes) > 1 else ""
    texto = texto.strip()
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()


def _calcular_custo_do_item(dados_preco):
    """Calcula preco x quantidade a partir do proprio dados_preco recuperado
    -- fonte UNICA do custo do item (a IA nao faz mais essa conta, ver
    docstring do modulo). Direto: preco_unitario x quantidade. Decomposto:
    soma preco_unitario x quantidade de cada componente."""
    if dados_preco.get("tipo") == "direto":
        preco = dados_preco.get("preco", {})
        preco_unitario = preco.get("preco_unitario_rs")
        quantidade = dados_preco.get("quantidade")
        if preco_unitario is None or quantidade is None:
            return None
        return preco_unitario * quantidade

    if dados_preco.get("tipo") == "decomposto":
        total = 0.0
        for componente in dados_preco.get("componentes", []):
            preco = componente.get("preco", {})
            preco_unitario = preco.get("preco_unitario_rs")
            quantidade = componente.get("quantidade")
            if preco_unitario is None or quantidade is None:
                return None
            total += preco_unitario * quantidade
        return total

    return None


def _definir_custo_calculado(resultado, dados_preco):
    """Calcula o custo do item (preco x quantidade, sempre em Python -- ver
    docstring do modulo) e grava em custo_calculado_rs. Nome novo, NAO
    reaproveita custo_estimado_rs: esse campo era o valor DECLARADO pela IA
    (podia divergir da conta real, ver achado documentado no CLAUDE.md,
    Fase 6) -- custo_calculado_rs e sempre a conta certa, nunca declarada
    pela IA, e serve tambem pra distinguir arquivos gerados antes desta
    mudanca (tem custo_estimado_rs, nao tem custo_calculado_rs) dos
    gerados depois (o inverso)."""
    if not isinstance(resultado, dict) or "erro" in resultado:
        return resultado

    custo_calculado = _calcular_custo_do_item(dados_preco)
    if custo_calculado is not None:
        resultado["custo_calculado_rs"] = round(custo_calculado, 2)

    return resultado


def _extrair_uso_tokens(resposta):
    """Extrai tokens de entrada/saida da resposta do Bedrock -- campo
    "usage" (TokenUsage), sempre presente no Converse, mesmo quando a
    resposta nao e um JSON valido (o modelo ja gastou tokens gerando aquele
    texto). Nao calcula custo em R$ aqui -- preco por token muda com o
    tempo/plano e nao e responsabilidade deste modulo hardcodear; so
    registra os tokens de verdade, pra permitir apurar custo por analise
    depois (ver GET .../ultima e o agregado uso_tokens_total_lote)."""
    uso = resposta.get("usage", {})
    return {
        "tokens_entrada": uso.get("inputTokens"),
        "tokens_saida": uso.get("outputTokens"),
        "tokens_total": uso.get("totalTokens"),
    }


def _somar_uso_tokens(itens):
    """Soma uso_tokens de uma lista de entradas de estimativa_por_elemento
    (algumas podem nao ter -- erro de retrieval nunca chama a IA; erro de
    chamada ao Bedrock tambem nao chega a ter resposta). Compartilhado entre
    o modo SINAPI (gerar_estimativa_lote) e o modo mercado
    (estimativa_mercado_ia.gerar_estimativa_mercado_lote)."""
    entrada = saida = total = 0
    for item in itens:
        uso = item.get("uso_tokens")
        if not uso:
            continue
        entrada += uso.get("tokens_entrada") or 0
        saida += uso.get("tokens_saida") or 0
        total += uso.get("tokens_total") or 0
    return {"tokens_entrada": entrada, "tokens_saida": saida, "tokens_total": total}


def gerar_estimativa_ia(elemento, dados_preco):
    """Chama o Bedrock (Claude Haiku 4.5) pra analisar UM elemento (a IA nao
    calcula custo, so avalia a correspondencia com o(s) codigo(s) SINAPI e
    registra suposicoes -- ver docstring do modulo). Nunca inventa numero:
    se a chamada falhar ou a resposta nao for um JSON valido, devolve
    {"erro": ..., "resposta_bruta": ...} (o segundo campo so quando houve
    resposta pra mostrar). Se a resposta for valida, o custo e sempre
    calculado aqui em Python (_definir_custo_calculado), nunca pela IA."""
    user_message = _montar_user_message(elemento, dados_preco)

    client = boto3.client("bedrock-runtime", region_name=_REGION_NAME)
    try:
        resposta = client.converse(
            modelId=_MODEL_ID,
            system=[{"text": _SYSTEM_PROMPT}],
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

    resultado = _definir_custo_calculado(resultado, dados_preco)
    resultado["categoria"] = elemento.get("Categoria")
    resultado["uso_tokens"] = uso_tokens
    return resultado


def _extrair_mes_referencia(dados_preco):
    if dados_preco.get("tipo") == "direto":
        return dados_preco.get("preco", {}).get("mes_referencia")
    if dados_preco.get("tipo") == "decomposto":
        componentes = dados_preco.get("componentes", [])
        if componentes:
            return componentes[0].get("preco", {}).get("mes_referencia")
    return None


def _gravar_estimativa_versionada(pasta_destino, nome_lote, resultado_final, prefixo="estimativa"):
    """Grava resultado_final em pasta_destino com nome versionado (inclui o
    timestamp da geracao, nunca sobrescreve -- ver comentario em
    gerar_estimativa_lote). Mecanismo compartilhado entre o modo SINAPI
    (gerar_estimativa_lote, prefixo='estimativa') e o modo mercado
    (estimativa_mercado_ia.gerar_estimativa_mercado_lote, prefixo=
    'estimativa_mercado') -- so o "onde" e o prefixo mudam, o "como" e
    identico. Devolve o nome do arquivo gravado."""
    pasta = Path(pasta_destino)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_arquivo = "{}_{}_{}.json".format(
        prefixo, nome_lote, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    resultado_final["arquivo"] = nome_arquivo
    caminho_saida = pasta / nome_arquivo
    with caminho_saida.open("w", encoding="utf-8") as arquivo:
        json.dump(resultado_final, arquivo, ensure_ascii=False, indent=2)
    return nome_arquivo


def _rotulo_grupo(elemento_sintetico, quantidade):
    """Rotulo legivel do grupo, usado como elemento_id na saida -- assim o
    painel (api/static/painel.html, que nao e tocado por este agrupamento)
    mostra o grupo sem precisar de nenhuma mudanca de codigo nele, ja que
    elemento_id sempre foi tratado como texto livre. Categoria entra no
    rotulo pra evitar ambiguidade quando duas categorias diferentes usam o
    mesmo texto de Material_Estrutural (ex.: laje e pilar de "Concreto
    armado moldado in loco" -- sem a categoria, os dois grupos teriam o
    mesmo elemento_id)."""
    categoria = elemento_sintetico.get("Categoria") or "Elemento"
    material = elemento_sintetico.get("Material_Estrutural") or categoria
    sufixo = "elemento" if quantidade == 1 else "elementos"
    return "{} - {} ({} {})".format(categoria, material, quantidade, sufixo)


def gerar_estimativa_lote(caminho_lote):
    """Roda o fluxo completo (agrupamento + retrieval + IA) pra todos os
    elementos de um lote exportado pelo plugin, no formato de saida da
    secao 4 do spec (docs/modulo_ia_fase6_spec_prompt.md), com uma extensao:
    elementos com o MESMO retrieval (mesma categoria + mesmo(s) codigo(s)
    SINAPI resolvido(s)) sao agrupados ANTES da chamada a IA -- uma unica
    chamada por grupo, com as quantidades somadas, em vez de uma por
    elemento (ver agrupamento.agrupar_elementos).

    Elemento cujo resolver_preco_elemento ja da erro NAO e agrupado e NAO
    chama o Bedrock -- continua individual, evitando gastar chamada num
    elemento que ja sabemos que nao tem preco. custo_total_calculado_rs so
    soma entradas com custo_calculado_rs de verdade -- erro nunca vira zero
    silencioso na soma.
    """
    with open(caminho_lote, "r", encoding="utf-8") as arquivo:
        lote = json.load(arquivo)

    grupos = agrupar_elementos(lote["elementos"], resolver_preco_elemento)

    estimativa_por_elemento = []
    mes_referencia_precos = None
    qtd_elementos_originais = 0
    qtd_erro_retrieval = 0
    qtd_erro_ia = 0

    for item in grupos:
        if item["tipo"] == "erro":
            qtd_erro_retrieval += 1
            qtd_elementos_originais += 1
            estimativa_por_elemento.append({
                "elemento_id": item["elemento_id"],
                "categoria": item["categoria"],
                "erro": item["motivo"],
                "tipo_erro": "retrieval",
                # Sempre 1, nao um default -- item "erro" de agrupar_elementos
                # nunca e agrupado, e um por elemento original (ver
                # agrupamento.py). Gravado explicito pra o painel nao ter que
                # assumir nada.
                "quantidade_elementos_agrupados": 1,
            })
            continue

        elemento = item["elemento"]
        dados_preco = item["dados_preco"]
        elementos_originais = item["elementos_originais"]
        quantidade_grupo = item["quantidade_elementos_agrupados"]
        qtd_elementos_originais += quantidade_grupo
        rotulo_grupo = _rotulo_grupo(elemento, quantidade_grupo)

        if mes_referencia_precos is None:
            mes_referencia_precos = _extrair_mes_referencia(dados_preco)

        resultado = gerar_estimativa_ia(elemento, dados_preco)

        if "erro" in resultado:
            qtd_erro_ia += 1
            resultado = dict(resultado)
            resultado["elemento_id"] = rotulo_grupo
            resultado["elementos_originais"] = elementos_originais
            resultado["quantidade_elementos_agrupados"] = quantidade_grupo
            resultado["tipo_erro"] = "ia"
            estimativa_por_elemento.append(resultado)
            continue

        if dados_preco.get("tipo") == "decomposto":
            resultado["componentes_detalhados"] = [
                {
                    "componente": componente.get("componente"),
                    "codigo_sinapi": componente.get("preco", {}).get("codigo_sinapi"),
                    "unidade_sinapi": componente.get("preco", {}).get("unidade_sinapi"),
                    "preco_unitario_rs": componente.get("preco", {}).get("preco_unitario_rs"),
                    "quantidade": componente.get("quantidade"),
                }
                for componente in dados_preco.get("componentes", [])
            ]
        else:
            # Equivalente a componentes_detalhados para o caso nao-decomposto
            # -- codigo, descricao oficial SINAPI e (quando resolucao foi
            # por_espessura_estrutural_cm) a espessura medida e o bucket
            # escolhido, pro painel mostrar sem inventar nada.
            preco_usado = dados_preco.get("preco", {})
            resultado["preco_aplicado"] = {
                "codigo_sinapi": preco_usado.get("codigo_sinapi"),
                "descricao_sinapi": preco_usado.get("descricao"),
                "unidade_sinapi": preco_usado.get("unidade_sinapi"),
                # preco_unitario_rs/quantidade: mesma evidencia que
                # componentes_detalhados ja da pro caso decomposto -- sem
                # isso, o item nao-decomposto nao tinha nenhum campo
                # estruturado com o preco/quantidade usados no calculo.
                "preco_unitario_rs": preco_usado.get("preco_unitario_rs"),
                "quantidade": dados_preco.get("quantidade"),
                "espessura_real_cm": dados_preco.get("espessura_real_cm"),
                "bucket_espessura_cm": dados_preco.get("bucket_espessura_cm"),
            }

        resultado["elemento_id"] = rotulo_grupo
        resultado["elementos_originais"] = elementos_originais
        resultado["quantidade_elementos_agrupados"] = quantidade_grupo

        estimativa_por_elemento.append(resultado)

    custo_total_calculado_rs = sum(
        item["custo_calculado_rs"]
        for item in estimativa_por_elemento
        if "custo_calculado_rs" in item
    )
    qtd_total_entradas = len(estimativa_por_elemento)
    qtd_com_custo = qtd_total_entradas - qtd_erro_retrieval - qtd_erro_ia
    qtd_excluidas_da_soma = qtd_erro_retrieval + qtd_erro_ia

    observacoes_gerais = (
        "Lote com {} elemento(s) original(is), agrupados em {} entrada(s) "
        "(elementos com retrieval identico -- mesma categoria e mesmo(s) "
        "codigo(s) SINAPI -- viram uma unica chamada a IA, com as "
        "quantidades somadas, em vez de uma chamada por elemento): {} com "
        "custo calculado; {} sem preco (retrieval sem correspondencia no "
        "mapeamento_sinapi.json ou codigo sem preco em preco_sinapi_pr.json) "
        "e {} com falha na chamada ou no parse da resposta da IA -- essas "
        "{} entrada(s) ficaram de fora de custo_total_calculado_rs."
    ).format(
        qtd_elementos_originais,
        qtd_total_entradas,
        qtd_com_custo,
        qtd_erro_retrieval,
        qtd_erro_ia,
        qtd_excluidas_da_soma,
    )

    resultado_final = {
        # Distingue arquivos gerados antes/depois da IA parar de fazer
        # aritmetica (ver _definir_custo_calculado) -- versao 1 (implicita,
        # sem este campo) tem custo_estimado_rs/confianca/validacao_custo;
        # versao 2 tem custo_calculado_rs, sem nenhum dos tres.
        "versao_schema": 2,
        "estimativa_por_elemento": estimativa_por_elemento,
        "custo_total_calculado_rs": round(custo_total_calculado_rs, 2),
        "observacoes_gerais": observacoes_gerais,
        "mes_referencia_precos": mes_referencia_precos,
        "quantidade_chamadas_ia": qtd_total_entradas - qtd_erro_retrieval,
        "uso_tokens_total_lote": _somar_uso_tokens(estimativa_por_elemento),
    }

    # Nome de saida inclui o timestamp da GERACAO (nao so o nome do lote) --
    # antes disso, rodar "Gerar nova analise" 2x sobre o mesmo lote
    # sobrescrevia o arquivo anterior em silencio, perdendo a estimativa
    # gerada antes. Cada chamada agora cria um arquivo novo; ver tambem
    # POST /estimativa/congelar e GET /estimativa/historico (routes/estimativa.py).
    _gravar_estimativa_versionada(
        ESTIMATIVAS_DIR, Path(caminho_lote).stem, resultado_final, prefixo="estimativa"
    )

    return resultado_final
