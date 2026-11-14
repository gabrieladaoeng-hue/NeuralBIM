# NeuralBIM

Integração BIM + Inteligência Artificial para automação de quantitativos e estimativa de custos
baseada em preços de mercado (TCC — Engenharia Civil, Faculdade Guarapuava).

## Componentes

- `NeuralBim.extension/` — plugin pyRevit que extrai quantitativos (paredes, lajes, pilares) do modelo Revit.
- `api/` — API FastAPI que recebe os dados, aplica a base SINAPI-PR e gera estimativas via AWS Bedrock (RAG).
- `api/dados_referencia/` — mapeamento SINAPI e preços de referência.
- `docs/` — especificações técnicas.
- `CLAUDE.md` — decisões técnicas detalhadas.

## Rodando a API

```
cd api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Requer credenciais AWS configuradas localmente (`~/.aws/credentials`) com acesso ao Amazon Bedrock.
Nenhuma credencial é armazenada neste repositório.
