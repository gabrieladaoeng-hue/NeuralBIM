"""Rota de ingestao: recebe um lote do plugin e manda pro armazenamento."""

from fastapi import APIRouter

from models.elemento import LoteElementos
from storage.arquivo_local import ArmazenamentoArquivoLocal

router = APIRouter()

# Uma instancia so, reaproveitada em todas as requisicoes.
_armazenamento = ArmazenamentoArquivoLocal()


@router.post("/elementos")
def receber_elementos(lote: LoteElementos):
    caminho = _armazenamento.salvar(lote)
    return {
        "status": "ok",
        "quantidade_recebida": len(lote.elementos),
        "arquivo_gerado": caminho,
    }
