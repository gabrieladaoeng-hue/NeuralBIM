"""Persistencia simples em lista JSON -- sem banco de dados, e prototipo
(Etapa 7). Cada arquivo e uma lista JSON plana, nunca sobrescrita por
inteiro -- so cresce por acrescentar_item e encolhe por remover_item. Todo
item tem um "id" (uuid4) pra poder ser removido depois -- itens salvos antes
dessa garantia existir sao migrados (recebem id) na primeira leitura via
carregar_lista, sem exigir nenhuma acao manual."""

import json
import uuid
from pathlib import Path


def carregar_lista(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open("r", encoding="utf-8") as arquivo:
        lista = json.load(arquivo)

    precisa_migrar = False
    for item in lista:
        if "id" not in item:
            item["id"] = str(uuid.uuid4())
            precisa_migrar = True

    if precisa_migrar:
        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(lista, arquivo, ensure_ascii=False, indent=2)

    return lista


def acrescentar_item(caminho, item):
    caminho = Path(caminho)
    lista = carregar_lista(caminho)
    item["id"] = str(uuid.uuid4())
    lista.append(item)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(lista, arquivo, ensure_ascii=False, indent=2)
    return lista


def remover_item(caminho, item_id):
    """Remove o item cujo "id" bate com item_id e regrava o arquivo.
    Devolve a lista atualizada, ou None se nenhum item com esse id foi
    encontrado -- pra rota poder responder 404 sem regravar o arquivo a
    toa (e sem confundir "removi e ficou vazio" com "nao achei")."""
    caminho = Path(caminho)
    lista = carregar_lista(caminho)
    nova_lista = [item for item in lista if item.get("id") != item_id]
    if len(nova_lista) == len(lista):
        return None
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(nova_lista, arquivo, ensure_ascii=False, indent=2)
    return nova_lista
