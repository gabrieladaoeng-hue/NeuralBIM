"""Rotas de estimativa de custo (Etapa 7): gerar (roda IA), ler a ultima
ja gerada (so disco, sem IA), congelar uma versao especifica como oficial
da validacao (Etapa 8) e listar o historico de versoes ja geradas."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import ESTIMATIVAS_DIR, LOG_ANALISES_PATH, STORAGE_DIR
from estimativa_ia import gerar_estimativa_lote
from models.congelar_estimativa import CongelarEstimativa
from storage.lista_json import acrescentar_item

router = APIRouter()


def _encontrar_mais_recente(pasta, padrao):
    candidatos = sorted(
        Path(pasta).glob(padrao),
        key=lambda caminho: caminho.stat().st_mtime,
        reverse=True,
    )
    return candidatos[0] if candidatos else None


def _caminho_oficial():
    return Path(ESTIMATIVAS_DIR) / "oficial.json"


def _ler_oficial_registrada():
    """Le oficial.json se existir. Nome de arquivo comeca com "oficial",
    nunca "estimativa_" -- nao aparece nos glob("estimativa_*.json") de
    _encontrar_mais_recente/historico, entao nunca e confundido com uma
    versao de verdade."""
    caminho = _caminho_oficial()
    if not caminho.exists():
        return None
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


@router.post("/estimativa/gerar")
def gerar_estimativa():
    """Roda o fluxo completo (retrieval + Bedrock) no lote mais recente
    recebido do plugin, salva o resultado em ESTIMATIVAS_DIR e devolve.
    Unico endpoint que chama a IA -- acionamento deliberado, nunca
    automatico. Cada chamada registra uma entrada em LOG_ANALISES_PATH
    (timestamp + quantidade_chamadas_ia), pro contador de analises da
    pagina inicial."""
    caminho_lote = _encontrar_mais_recente(STORAGE_DIR, "lote_*.json")
    if caminho_lote is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Nenhum lote encontrado em dados_recebidos/ -- envie dados "
                "do plugin (POST /elementos) primeiro."
            ),
        )
    resultado = gerar_estimativa_lote(str(caminho_lote))
    acrescentar_item(LOG_ANALISES_PATH, {
        "timestamp": datetime.now().isoformat(),
        "chamadas_ia": resultado["quantidade_chamadas_ia"],
    })
    return resultado


@router.get("/estimativa/ultima")
def obter_ultima_estimativa():
    """So le do disco a estimativa a mostrar -- nunca chama a IA. Se houver
    uma oficial congelada (POST /estimativa/congelar) e o arquivo dela ainda
    existir, devolve ela; senao cai pra mais recente por data de geracao,
    como antes. Se a oficial foi congelada mas o arquivo dela sumiu (ex.:
    apagado a mao), NAO cai no fallback em silencio -- ainda devolve a mais
    recente, mas com "oficial.arquivo_oficial_ausente" preenchido, pro
    frontend avisar."""
    oficial_registrada = _ler_oficial_registrada()

    caminho_estimativa = None
    oficial_info = {"congelada": False}

    if oficial_registrada:
        caminho_candidato = Path(ESTIMATIVAS_DIR) / oficial_registrada["arquivo"]
        if caminho_candidato.is_file():
            caminho_estimativa = caminho_candidato
            oficial_info = {
                "congelada": True,
                "congelado_em": oficial_registrada["congelado_em"],
            }
        else:
            oficial_info = {
                "congelada": False,
                "arquivo_oficial_ausente": oficial_registrada["arquivo"],
                "congelado_em": oficial_registrada["congelado_em"],
            }

    if caminho_estimativa is None:
        caminho_estimativa = _encontrar_mais_recente(ESTIMATIVAS_DIR, "estimativa_*.json")

    if caminho_estimativa is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma estimativa gerada ainda -- rode POST /estimativa/gerar primeiro.",
        )

    with caminho_estimativa.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    # setdefault, nao atribuicao direta -- estimativas geradas antes desse
    # campo existir continuam sendo lidas normalmente.
    dados.setdefault("arquivo", caminho_estimativa.name)
    dados["oficial"] = oficial_info
    return dados


@router.post("/estimativa/congelar")
def congelar_estimativa(corpo: CongelarEstimativa):
    """Marca um arquivo de estimativa ja gerado (ver GET /estimativa/historico)
    como a oficial da validacao -- GET /estimativa/ultima passa a devolver
    esse arquivo especifico em vez do mais recente. Sobrescrever
    oficial.json de novo (congelando outro arquivo) troca qual e a oficial;
    nao ha rota de "descongelar" separada porque nao foi pedida."""
    caminho = Path(ESTIMATIVAS_DIR) / corpo.arquivo
    # corpo.arquivo normalmente vem do GET /estimativa/historico, nunca
    # digitado a mao -- ainda assim, resolve() + checagem da pasta-pai
    # bloqueia qualquer tentativa de sair de ESTIMATIVAS_DIR via "../".
    dentro_da_pasta = caminho.resolve().parent == Path(ESTIMATIVAS_DIR).resolve()
    if not dentro_da_pasta or not caminho.is_file():
        raise HTTPException(
            status_code=404,
            detail="Arquivo de estimativa nao encontrado: {}".format(corpo.arquivo),
        )

    dados_oficial = {
        "arquivo": corpo.arquivo,
        "congelado_em": datetime.now().isoformat(),
    }
    with _caminho_oficial().open("w", encoding="utf-8") as arquivo:
        json.dump(dados_oficial, arquivo, ensure_ascii=False, indent=2)
    return dados_oficial


@router.get("/estimativa/historico")
def historico_estimativas():
    """Lista os arquivos de estimativa ja gerados (mais recente primeiro),
    com data de geracao e custo total de cada um, e qual deles (se algum) e
    a oficial congelada. Sem essa rota o versionamento existe no disco mas
    ninguem consegue ver nem escolher o que congelar."""
    oficial_registrada = _ler_oficial_registrada()
    arquivo_oficial = oficial_registrada["arquivo"] if oficial_registrada else None

    candidatos = sorted(
        Path(ESTIMATIVAS_DIR).glob("estimativa_*.json"),
        key=lambda caminho: caminho.stat().st_mtime,
        reverse=True,
    )

    resultado = []
    for caminho in candidatos:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        resultado.append({
            "arquivo": caminho.name,
            "gerado_em": datetime.fromtimestamp(caminho.stat().st_mtime).isoformat(),
            # custo_total_calculado_rs (versao_schema 2, ver estimativa_ia.py)
            # com fallback pro nome antigo -- arquivos gerados antes dessa
            # mudanca so tem custo_total_estimado_rs. Chave de saida
            # continua "custo_total_estimado_rs" de proposito: e a unica
            # fonte de custo que painel.html:renderizarHistorico le, entao
            # o fallback fica so aqui, sem duplicar a logica no frontend.
            "custo_total_estimado_rs": dados.get(
                "custo_total_calculado_rs", dados.get("custo_total_estimado_rs")
            ),
            "oficial": caminho.name == arquivo_oficial,
        })
    return resultado
