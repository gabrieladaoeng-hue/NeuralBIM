"""Configuracao da API. Tudo que muda entre ambientes vem de variavel de
ambiente, com um valor padrao razoavel pra rodar local sem configurar nada
(regra do projeto: nada de caminho ou porta fixos no meio do codigo)."""

import os
from pathlib import Path

# Pasta onde os lotes recebidos do plugin sao gravados.
# Sobrescreva com a variavel de ambiente NEURALBIM_STORAGE_DIR.
# Padrao: ./dados_recebidos, ao lado deste arquivo.
_PADRAO_STORAGE = Path(__file__).resolve().parent / "dados_recebidos"
STORAGE_DIR = Path(os.environ.get("NEURALBIM_STORAGE_DIR", _PADRAO_STORAGE))

# Pasta onde os resultados de gerar_estimativa_lote sao salvos (Etapa 7).
# Sobrescreva com NEURALBIM_ESTIMATIVAS_DIR. Padrao: dentro de STORAGE_DIR.
_PADRAO_ESTIMATIVAS = STORAGE_DIR / "estimativas"
ESTIMATIVAS_DIR = Path(os.environ.get("NEURALBIM_ESTIMATIVAS_DIR", _PADRAO_ESTIMATIVAS))

# Pasta onde os resultados do modo mercado (Etapa 8b -- estimativa sem
# SINAPI, so conhecimento da IA, ver estimativa_mercado_ia.py) sao salvos.
# Pasta PROPRIA, fora de ESTIMATIVAS_DIR -- assim o glob "estimativa_*.json"
# que GET /estimativa/ultima, GET /estimativa/historico e POST
# /estimativa/congelar usam nunca alcanca (nem corre risco de colidir com)
# um arquivo do modo mercado. Sobrescreva com NEURALBIM_ESTIMATIVAS_MERCADO_DIR.
_PADRAO_ESTIMATIVAS_MERCADO = ESTIMATIVAS_DIR / "mercado"
ESTIMATIVAS_MERCADO_DIR = Path(
    os.environ.get("NEURALBIM_ESTIMATIVAS_MERCADO_DIR", _PADRAO_ESTIMATIVAS_MERCADO)
)

# Pasta com os arquivos de referencia (mapeamento SINAPI, precos, e agora
# tambem os cadastros manuais da Etapa 7). Sobrescreva com
# NEURALBIM_DADOS_REFERENCIA_DIR.
_PADRAO_DADOS_REFERENCIA = Path(__file__).resolve().parent / "dados_referencia"
DADOS_REFERENCIA_DIR = Path(
    os.environ.get("NEURALBIM_DADOS_REFERENCIA_DIR", _PADRAO_DADOS_REFERENCIA)
)

# Lista (JSON) de correcoes manuais de preco confirmadas por um engenheiro.
_PADRAO_PRECOS_CONFIRMADOS = DADOS_REFERENCIA_DIR / "precos_confirmados.json"
PRECOS_CONFIRMADOS_PATH = Path(
    os.environ.get("NEURALBIM_PRECOS_CONFIRMADOS_PATH", _PADRAO_PRECOS_CONFIRMADOS)
)

# Lista (JSON) de fornecedores cadastrados manualmente.
_PADRAO_FORNECEDORES = DADOS_REFERENCIA_DIR / "fornecedores.json"
FORNECEDORES_PATH = Path(
    os.environ.get("NEURALBIM_FORNECEDORES_PATH", _PADRAO_FORNECEDORES)
)

# Lista (JSON) de gastos reais registrados pelo engenheiro em obra.
_PADRAO_GASTOS_REAIS = DADOS_REFERENCIA_DIR / "gastos_reais.json"
GASTOS_REAIS_PATH = Path(
    os.environ.get("NEURALBIM_GASTOS_REAIS_PATH", _PADRAO_GASTOS_REAIS)
)

# Log (JSON) de cada chamada a POST /estimativa/gerar -- timestamp e quantas
# vezes a IA foi chamada nessa analise. Alimenta o contador de analises
# geradas exibido na pagina inicial.
_PADRAO_LOG_ANALISES = DADOS_REFERENCIA_DIR / "log_analises.json"
LOG_ANALISES_PATH = Path(
    os.environ.get("NEURALBIM_LOG_ANALISES_PATH", _PADRAO_LOG_ANALISES)
)

# Porta HTTP da API. Sobrescreva com NEURALBIM_API_PORT.
API_PORT = int(os.environ.get("NEURALBIM_API_PORT", "8000"))

# Host de bind. Padrao 127.0.0.1 (so acesso local).
# Sobrescreva com NEURALBIM_API_HOST (ex.: "0.0.0.0" pra expor na rede).
API_HOST = os.environ.get("NEURALBIM_API_HOST", "127.0.0.1")
