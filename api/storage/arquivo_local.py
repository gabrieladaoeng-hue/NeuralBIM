"""Implementacao de armazenamento: grava o lote como um arquivo JSON dentro
da pasta configurada (config.STORAGE_DIR). Cada execucao do plugin vira um
arquivo, nomeado pelo timestamp de inicio de execucao."""

import json
from pathlib import Path

from config import STORAGE_DIR
from models.elemento import LoteElementos
from storage.base import ArmazenamentoBase


class ArmazenamentoArquivoLocal(ArmazenamentoBase):
    def __init__(self, pasta: Path = STORAGE_DIR):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)

    def salvar(self, lote: LoteElementos) -> str:
        # "2026-09-10 14:30:00" -> "2026-09-10_14-30-00" (":" e espaco nao
        # servem em nome de arquivo no Windows).
        nome_base = (
            lote.timestamp_inicio_execucao.replace(":", "-").replace(" ", "_")
        )
        caminho = self.pasta / "lote_{}.json".format(nome_base)

        # Duas execucoes no mesmo segundo -> sufixo numerico, sem sobrescrever.
        contador = 2
        while caminho.exists():
            caminho = self.pasta / "lote_{}_{}.json".format(nome_base, contador)
            contador += 1

        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(lote.model_dump(), arquivo, ensure_ascii=False, indent=2)

        return str(caminho)
