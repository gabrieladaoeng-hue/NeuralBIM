"""Fase 6: retrieval de precos SINAPI para um elemento extraido pelo plugin.

Le mapeamento_sinapi.json (Material_Estrutural -> codigo(s) SINAPI) e
preco_sinapi_pr.json (codigo SINAPI -> preco unitario no PR) e monta, para
um elemento, os dados de preco que a IA (Fase 6, RAG + Bedrock) vai usar
no prompt. NAO faz a conta final (preco x quantidade) -- isso e decisao
ja registrada de ficar do lado da IA, nao do codigo.
"""

import json
from pathlib import Path

_DIR_REFERENCIA = Path(__file__).resolve().parent / "dados_referencia"

_NOMES_COMPONENTE_FORMA = ("forma", "forma_fabricacao", "forma_montagem_desmontagem")


def _carregar_mapeamento():
    caminho = _DIR_REFERENCIA / "mapeamento_sinapi.json"
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _carregar_precos():
    caminho = _DIR_REFERENCIA / "preco_sinapi_pr.json"
    with caminho.open("r", encoding="utf-8") as arquivo:
        lista = json.load(arquivo)
    return {item["codigo_sinapi"]: item for item in lista}


_MAPEAMENTO = _carregar_mapeamento()
_PRECOS = _carregar_precos()
_TAXA_ARMADURA_KG_POR_M3 = _MAPEAMENTO["_leia_isto_primeiro"]["taxa_armadura_kg_por_m3"]

_RESOLUCOES_SEM_PRECO = ("sem_preco", "fora_de_escopo", "pendente")


def _encontrar_entrada_mapeamento(categoria, material_estrutural):
    for entrada in _MAPEAMENTO["mapeamento"]:
        if categoria not in entrada.get("elemento", []):
            continue
        materiais = entrada.get("material_estrutural")
        if isinstance(materiais, list):
            if material_estrutural in materiais:
                return entrada
        elif materiais == material_estrutural:
            return entrada
    return None


def _buscar_preco(codigo_sinapi):
    """Retorna (preco, motivo_erro). Exatamente um dos dois vem None."""
    if not codigo_sinapi:
        return None, "codigo_sinapi ausente ou nulo"
    preco = _PRECOS.get(codigo_sinapi)
    if preco is None:
        return None, "codigo {} nao encontrado em preco_sinapi_pr.json".format(codigo_sinapi)
    if "erro" in preco:
        return None, preco["erro"]
    return preco, None


def _quantidade_por_unidade(unidade, elemento):
    if unidade == "M2":
        return elemento.get("Area_m2")
    if unidade == "M3":
        return elemento.get("Volume_m3")
    return None


def _quantidade_componente(nome_componente, elemento, categoria):
    if nome_componente == "armacao":
        taxa = _TAXA_ARMADURA_KG_POR_M3.get(categoria.lower())
        volume = elemento.get("Volume_m3")
        if taxa is None or volume is None:
            return None
        return volume * taxa
    if nome_componente in _NOMES_COMPONENTE_FORMA:
        return elemento.get("Area_Forma_m2")
    if nome_componente == "concretagem":
        return elemento.get("Volume_m3")
    return None


def resolver_preco_elemento(elemento):
    """Recebe um elemento no formato do schema Elemento (dict) e devolve os
    dados de preco necessarios pra IA calcular o custo -- sem calcular.

    Formatos de retorno:
    - {"tipo": "direto", "preco": {...}, "quantidade": <float>}
    - {"tipo": "decomposto", "componentes": [{"componente": str, "preco": {...}, "quantidade": <float>}, ...]}
    - {"tipo": "erro", "motivo": str}
    """
    categoria = elemento.get("Categoria")
    material = elemento.get("Material_Estrutural")

    entrada = _encontrar_entrada_mapeamento(categoria, material)
    if entrada is None:
        return {
            "tipo": "erro",
            "motivo": (
                "Nenhuma entrada em mapeamento_sinapi.json para "
                "elemento='{}' / Material_Estrutural='{}'."
            ).format(categoria, material),
        }

    resolucao = entrada.get("resolucao")

    if resolucao in _RESOLUCOES_SEM_PRECO:
        motivo = "resolucao='{}' em mapeamento_sinapi.json para elemento='{}' / Material_Estrutural='{}'.".format(
            resolucao, categoria, material
        )
        if entrada.get("nota"):
            motivo += " Nota: {}".format(entrada["nota"])
        return {"tipo": "erro", "motivo": motivo}

    if resolucao == "direto":
        preco, motivo_erro = _buscar_preco(entrada.get("codigo_sinapi"))
        if preco is None:
            return {"tipo": "erro", "motivo": motivo_erro}

        quantidade = _quantidade_por_unidade(preco.get("unidade_sinapi"), elemento)
        if quantidade is None:
            return {
                "tipo": "erro",
                "motivo": (
                    "Nao foi possivel determinar a quantidade (unidade '{}') "
                    "para elemento='{}' / Material_Estrutural='{}'."
                ).format(preco.get("unidade_sinapi"), categoria, material),
            }
        return {"tipo": "direto", "preco": preco, "quantidade": quantidade}

    if resolucao == "por_espessura_estrutural_cm":
        buckets = entrada.get("buckets", [])
        espessura_real = elemento.get("Espessura_Estrutural_cm")
        if espessura_real is None or not buckets:
            return {
                "tipo": "erro",
                "motivo": (
                    "Nao foi possivel resolver por_espessura_estrutural_cm para "
                    "elemento='{}' / Material_Estrutural='{}': Espessura_Estrutural_cm "
                    "ausente no elemento ou nenhum bucket definido no mapeamento."
                ).format(categoria, material),
            }

        bucket = min(buckets, key=lambda b: abs(b["espessura_cm"] - espessura_real))
        preco, motivo_erro = _buscar_preco(bucket.get("codigo_sinapi"))
        if preco is None:
            return {
                "tipo": "erro",
                "motivo": "Bucket de {}cm (mais proximo de {}cm real): {}".format(
                    bucket.get("espessura_cm"), espessura_real, motivo_erro
                ),
            }

        quantidade = _quantidade_por_unidade(preco.get("unidade_sinapi"), elemento)
        if quantidade is None:
            return {
                "tipo": "erro",
                "motivo": (
                    "Nao foi possivel determinar a quantidade (unidade '{}') "
                    "para elemento='{}' / Material_Estrutural='{}'."
                ).format(preco.get("unidade_sinapi"), categoria, material),
            }
        # espessura_real_cm/bucket_espessura_cm registrados pra rastreabilidade
        # (o painel mostra "espessura medida -> bucket aplicado") -- nao afeta
        # o calculo, so documenta qual bucket foi escolhido e a partir de que
        # medida real.
        return {
            "tipo": "direto",
            "preco": preco,
            "quantidade": quantidade,
            "espessura_real_cm": espessura_real,
            "bucket_espessura_cm": bucket.get("espessura_cm"),
        }

    if resolucao == "decomposto":
        resultado_componentes = []
        for componente in entrada.get("componentes", []):
            nome_componente = componente.get("componente")
            preco, motivo_erro = _buscar_preco(componente.get("codigo_sinapi"))
            if preco is None:
                return {
                    "tipo": "erro",
                    "motivo": "Componente '{}': {}".format(nome_componente, motivo_erro),
                }

            quantidade = _quantidade_componente(nome_componente, elemento, categoria)
            if quantidade is None:
                return {
                    "tipo": "erro",
                    "motivo": (
                        "Nao foi possivel calcular a quantidade do componente "
                        "'{}' para elemento='{}' / Material_Estrutural='{}' "
                        "(campo necessario ausente no elemento)."
                    ).format(nome_componente, categoria, material),
                }
            resultado_componentes.append({
                "componente": nome_componente,
                "preco": preco,
                "quantidade": quantidade,
            })
        return {"tipo": "decomposto", "componentes": resultado_componentes}

    # Qualquer outra resolucao (ex.: "por_espessura_estrutural_cm") ainda nao
    # foi implementada nesta funcao -- fora do escopo deste pedido. Nunca
    # inventa preco: devolve erro explicito em vez de tentar adivinhar.
    return {
        "tipo": "erro",
        "motivo": (
            "resolucao='{}' em mapeamento_sinapi.json ainda nao implementada "
            "em resolver_preco_elemento (elemento='{}' / Material_Estrutural='{}')."
        ).format(resolucao, categoria, material),
    }


def obter_premissas():
    """Devolve as premissas de engenharia documentadas em _leia_isto_primeiro
    (mapeamento_sinapi.json) -- fck, taxa de armadura, bitola, forma e
    concretagem etc -- sem como_resolver_uma_categoria, que e guia de
    implementacao do backend (passo a passo de resolver_preco_elemento), nao
    informacao relevante pro engenheiro que le o painel."""
    premissas = dict(_MAPEAMENTO["_leia_isto_primeiro"])
    premissas.pop("como_resolver_uma_categoria", None)
    return premissas


_RESOLUCOES_COMPARAVEIS = ("direto", "por_espessura_estrutural_cm", "decomposto")


def listar_materiais_com_preco():
    """Achata mapeamento_sinapi.json (por par elemento + material_estrutural)
    numa lista com o preco SINAPI ja resolvido de preco_sinapi_pr.json --
    alimenta o seletor Categoria/Material do cadastro de fornecedores
    (Etapa 7) e a comparacao preco de mercado x preco SINAPI. So inclui
    resolucoes que tem algum codigo SINAPI de verdade (direto,
    por_espessura_estrutural_cm, decomposto) -- sem_preco/fora_de_escopo/
    pendente ficam de fora, ja que nunca vao ter preco pra comparar.

    Formatos por resolucao:
    - direto: {"categoria", "material", "resolucao", "codigo_sinapi",
      "unidade_sinapi", "preco_unitario_rs"}
    - por_espessura_estrutural_cm: idem + "buckets": [{"espessura_cm",
      "codigo_sinapi", "unidade_sinapi", "preco_unitario_rs"}, ...]
    - decomposto: idem (sem codigo/preco no nivel raiz -- nao existe um
      preco unico pra composicao inteira) + "componentes": [{"componente",
      "codigo_sinapi", "unidade_sinapi", "preco_unitario_rs"}, ...], pra
      permitir cotar um componente isolado (ex.: so a armacao) em vez da
      composicao inteira, que nunca tem preco SINAPI comparavel direto.
    """
    materiais = []
    for entrada in _MAPEAMENTO["mapeamento"]:
        resolucao = entrada.get("resolucao")
        if resolucao not in _RESOLUCOES_COMPARAVEIS:
            continue

        material_estrutural = entrada.get("material_estrutural")
        nomes = material_estrutural if isinstance(material_estrutural, list) else [material_estrutural]

        for categoria in entrada.get("elemento", []):
            for nome in nomes:
                item = {"categoria": categoria, "material": nome, "resolucao": resolucao}

                if resolucao == "direto":
                    preco, _motivo = _buscar_preco(entrada.get("codigo_sinapi"))
                    if preco is None:
                        continue
                    item["codigo_sinapi"] = preco["codigo_sinapi"]
                    item["unidade_sinapi"] = preco["unidade_sinapi"]
                    item["preco_unitario_rs"] = preco["preco_unitario_rs"]

                elif resolucao == "por_espessura_estrutural_cm":
                    buckets = []
                    for bucket in entrada.get("buckets", []):
                        preco, _motivo = _buscar_preco(bucket.get("codigo_sinapi"))
                        if preco is None:
                            continue
                        buckets.append({
                            "espessura_cm": bucket.get("espessura_cm"),
                            "codigo_sinapi": preco["codigo_sinapi"],
                            "unidade_sinapi": preco["unidade_sinapi"],
                            "preco_unitario_rs": preco["preco_unitario_rs"],
                        })
                    if not buckets:
                        continue
                    item["buckets"] = buckets

                elif resolucao == "decomposto":
                    componentes = []
                    for componente in entrada.get("componentes", []):
                        preco, _motivo = _buscar_preco(componente.get("codigo_sinapi"))
                        if preco is None:
                            continue
                        componentes.append({
                            "componente": componente.get("componente"),
                            "codigo_sinapi": preco["codigo_sinapi"],
                            "unidade_sinapi": preco["unidade_sinapi"],
                            "preco_unitario_rs": preco["preco_unitario_rs"],
                        })
                    if not componentes:
                        continue
                    item["componentes"] = componentes

                materiais.append(item)

    return materiais
