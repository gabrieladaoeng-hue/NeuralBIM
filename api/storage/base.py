"""Contrato de armazenamento. A rota nao sabe COMO o lote e salvo - so que
existe um objeto com .salvar(lote). Hoje a implementacao grava um JSON local;
amanha pode ser S3, banco, fila... sem tocar na rota."""

from abc import ABC, abstractmethod

from models.elemento import LoteElementos


class ArmazenamentoBase(ABC):
    @abstractmethod
    def salvar(self, lote: LoteElementos) -> str:
        """Persiste o lote recebido. Retorna um identificador do que foi
        gravado (ex.: caminho do arquivo, id no banco)."""
        raise NotImplementedError
