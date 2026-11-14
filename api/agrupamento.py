"""Fase 6/Etapa 7/Etapa 8b: agrupa elementos com retrieval identico antes de
chamar a IA -- em vez de uma chamada ao Bedrock por elemento, um lote com N
paredes idênticas (mesma categoria, mesma chave de agrupamento resolvida)
vira uma unica chamada, com as quantidades somadas. Elementos com erro no
retrieval NAO sao agrupados -- continuam individuais, um por um, exatamente
como ja funcionava antes deste modulo existir.

`agrupar_elementos` recebe a chave de agrupamento e a soma de membros como
funcoes injetadas (`chave_extra_fn`/`somar_fn`), com o comportamento SINAPI
de sempre (`_chave_agrupamento`/`_somar_dados_preco`, por codigo SINAPI) como
padrao -- o modo mercado (Etapa 8b, sem SINAPI, ver estimativa_mercado_ia.py)
passa as suas proprias (por Categoria + Material_Estrutural + espessura).
"""


def _obter_elemento_id(elemento):
    return "{}_{}".format(
        str(elemento.get("Categoria", "elemento")).lower(), elemento.get("ID", "?")
    )


def _chave_agrupamento(elemento, dados_preco):
    if dados_preco.get("tipo") == "direto":
        return dados_preco.get("preco", {}).get("codigo_sinapi")
    if dados_preco.get("tipo") == "decomposto":
        return tuple(sorted(
            componente.get("preco", {}).get("codigo_sinapi")
            for componente in dados_preco.get("componentes", [])
        ))
    return None


def _somar_dados_preco(membros):
    """Soma as quantidades de N dados_preco do MESMO tipo/mesma(s) chave(s)
    de codigo SINAPI (garantido por quem chama, via _chave_agrupamento) --
    preco_unitario_rs e o mesmo em todos os membros, entao so reaproveita o
    do primeiro."""
    tipo = membros[0]["tipo"]

    if tipo == "direto":
        preco = membros[0]["preco"]
        quantidade_total = sum(membro["quantidade"] for membro in membros)
        return {"tipo": "direto", "preco": preco, "quantidade": quantidade_total}

    if tipo == "decomposto":
        componentes_por_codigo = {}
        ordem_codigos = []
        for membro in membros:
            for componente in membro["componentes"]:
                codigo = componente["preco"]["codigo_sinapi"]
                if codigo not in componentes_por_codigo:
                    componentes_por_codigo[codigo] = {
                        "componente": componente["componente"],
                        "preco": componente["preco"],
                        "quantidade": 0.0,
                    }
                    ordem_codigos.append(codigo)
                componentes_por_codigo[codigo]["quantidade"] += componente["quantidade"]
        return {
            "tipo": "decomposto",
            "componentes": [componentes_por_codigo[codigo] for codigo in ordem_codigos],
        }

    raise ValueError("tipo de dados_preco desconhecido para agrupamento: {}".format(tipo))


def agrupar_elementos(elementos, resolver_dados, chave_extra_fn=None, somar_fn=None):
    """Recebe a lista de elementos de um lote e a funcao de retrieval
    (ex.: precificacao.resolver_preco_elemento, ou
    estimativa_mercado_ia.resolver_dados_mercado). `chave_extra_fn(elemento,
    dados) -> chave` e `somar_fn(membros) -> dados_agrupado` sao injetaveis --
    por padrao (None) usam a logica SINAPI de sempre (por codigo_sinapi
    resolvido). Devolve uma lista, na ordem de primeira ocorrencia, de:

    - {"tipo": "erro", "elemento_id": ..., "categoria": ..., "motivo": ...}
      -- um por elemento com retrieval sem sucesso, nunca agrupado.
    - {"tipo": "grupo", "elemento": <elemento sintetico>,
       "dados_preco": <dados agrupados, formato depende de somar_fn>,
       "elementos_originais": [elemento_id, ...],
       "quantidade_elementos_agrupados": N}
      -- um por grupo de elementos com a MESMA chave de agrupamento (mesma
      Categoria + o que chave_extra_fn devolver). N pode ser 1, quando
      nenhum outro elemento do lote teve retrieval identico -- o elemento
      ainda passa pelo mesmo fluxo, so que sozinho no seu grupo.
    """
    chave_extra_fn = chave_extra_fn or _chave_agrupamento
    somar_fn = somar_fn or _somar_dados_preco

    indice_do_grupo = {}
    resultado = []

    for elemento in elementos:
        elemento_id = _obter_elemento_id(elemento)
        dados = resolver_dados(elemento)

        if dados.get("tipo") == "erro":
            resultado.append({
                "tipo": "erro",
                "elemento_id": elemento_id,
                "categoria": elemento.get("Categoria"),
                "motivo": dados.get("motivo"),
            })
            continue

        categoria = elemento.get("Categoria")
        chave = (categoria, chave_extra_fn(elemento, dados))

        if chave not in indice_do_grupo:
            indice_do_grupo[chave] = len(resultado)
            resultado.append({
                "tipo": "grupo",
                "_categoria": categoria,
                "_materiais_distintos": [],
                "_observacoes_distintas": [],
                "elementos_originais": [],
                "_dados_membros": [],
            })

        grupo = resultado[indice_do_grupo[chave]]
        grupo["elementos_originais"].append(elemento_id)
        grupo["_dados_membros"].append(dados)
        material = elemento.get("Material_Estrutural")
        if material not in grupo["_materiais_distintos"]:
            grupo["_materiais_distintos"].append(material)
        # Observacoes descartadas ate aqui -- era por isso que o aviso
        # "Multiplas categorias reconhecidas nas camadas estruturais"
        # (gravado pela extracao, Fase 5) nunca chegava na tela nem na IA,
        # mesmo a instrucao sobre o campo Observacoes ja existindo no
        # prompt desde sempre (letra morta). Mesmo padrao de
        # _materiais_distintos: sem duplicar, na ordem de aparicao.
        observacao = elemento.get("Observacoes")
        if observacao and observacao not in grupo["_observacoes_distintas"]:
            grupo["_observacoes_distintas"].append(observacao)

    for item in resultado:
        if item.get("tipo") != "grupo":
            continue
        dados_agrupado = somar_fn(item.pop("_dados_membros"))
        elementos_originais = item["elementos_originais"]
        quantidade = len(elementos_originais)
        # Dois nomes de Material_Estrutural diferentes podem resolver pro
        # mesmo codigo_sinapi (ex.: duas espessuras de bloco ceramico
        # proximas o suficiente pra cair no mesmo bucket de preco) -- nesse
        # caso o grupo e valido (mesmo preco pra todos), mas o rotulo junta
        # os nomes distintos em vez de esconder que ha mais de um.
        materiais_distintos = item.pop("_materiais_distintos")
        material_final = " / ".join(materiais_distintos)
        observacoes_distintas = item.pop("_observacoes_distintas")
        item["elemento"] = {
            "Categoria": item.pop("_categoria"),
            "Material_Estrutural": material_final,
            "Elementos_Agrupados": elementos_originais,
            "Quantidade_Elementos_Agrupados": quantidade,
            "Observacoes": " | ".join(observacoes_distintas),
        }
        item["dados_preco"] = dados_agrupado
        item["quantidade_elementos_agrupados"] = quantidade

    return resultado
