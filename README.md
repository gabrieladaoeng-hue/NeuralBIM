# NeuralBIM

Protótipo que integra **BIM (Autodesk Revit)** e **inteligência artificial** para automatizar o levantamento de quantitativos e gerar estimativas preliminares de custo de obra a partir de preços de referência (SINAPI-PR).

Desenvolvido como Trabalho de Conclusão de Curso em Engenharia Civil — Faculdade Guarapuava, 2026.

---

## Visão geral

```
┌─────────────────────┐   HTTP POST /elementos   ┌──────────────────────────┐   Converse API   ┌─────────────────┐
│  Plugin pyRevit     │ ───────────────────────► │  API FastAPI (local)     │ ───────────────► │ Amazon Bedrock  │
│  (dentro do Revit)  │      lote JSON           │  • agrupamento           │ ◄─────────────── │ Claude Haiku 4.5│
│  paredes/lajes/     │                          │  • retrieval de preços   │                  └─────────────────┘
│  pilares            │                          │    (SINAPI-PR 07/2026)   │
└─────────────────────┘                          │  • validação cruzada     │
                                                 │  • painel web /painel/   │
                                                 └──────────────────────────┘
```

1. **Extração (plugin):** o botão *Enviar Dados* lê paredes, lajes e pilares selecionados, identifica o material estrutural pela estrutura de camadas do tipo (ou pelo parâmetro estrutural, no caso de pilares) e envia um lote JSON para a API.
2. **Precificação (RAG):** a API agrupa elementos equivalentes, recupera as composições SINAPI correspondentes (`api/dados_referencia/`) e envia o contexto ao modelo de linguagem.
3. **Estimativa e verificação:** a resposta da IA é comparada com o cálculo determinístico preço × quantidade. Divergências não são corrigidas silenciosamente — o item é sinalizado com confiança baixa.
4. **Visualização:** painel web servido pela própria API, com estimativa por categoria, confirmação de preços, cadastro de fornecedores e controle de gastos reais.

## Estrutura do repositório

```
.
├── NeuralBim.extension/          # Extensão pyRevit (IronPython)
│   └── NeuralBim.tab/IA.panel/
│       ├── Enviar Dados.pushbutton/     # extração e envio (paredes.py, lajes.py, pilares.py, envio_api.py)
│       ├── Auditar Materiais.pushbutton/
│       ├── Medir Referencia.pushbutton/ # medição geométrica usada na validação
│       └── ...                          # utilitários de preparação do modelo de validação
├── api/                          # Backend FastAPI (CPython 3)
│   ├── main.py                   # ponto de entrada
│   ├── config.py                 # configuração via variáveis de ambiente
│   ├── routes/                   # endpoints HTTP
│   ├── models/                   # schemas Pydantic
│   ├── storage/                  # persistência em arquivos JSON
│   ├── agrupamento.py            # agrupamento de elementos equivalentes
│   ├── precificacao.py           # retrieval de preços SINAPI
│   ├── estimativa_ia.py          # estimativa com base SINAPI (Bedrock)
│   ├── estimativa_mercado_ia.py  # estimativa sem tabela (comparativo)
│   ├── static/                   # painel web (HTML/CSS/JS, sem build)
│   └── dados_referencia/         # mapeamento e preços SINAPI-PR 07/2026
├── validacao_2026-10-28/         # validação no projeto real: relatório, dados brutos, scripts e figuras
├── docs/                         # especificações técnicas
└── scripts/                      # utilitários (iniciar API, testar credenciais AWS/Bedrock)
```

## Requisitos

| Componente | Requisito |
|---|---|
| Plugin | Autodesk Revit 2024+ com [pyRevit](https://github.com/pyrevitlabs/pyRevit) |
| API | Python 3.11+ |
| IA | Conta AWS com acesso ao Amazon Bedrock (modelo `claude-haiku-4-5`, região `us-east-2`) |

## Como executar

### 1. API

```powershell
cd api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

A API sobe em `http://127.0.0.1:8000`. Documentação interativa: `http://127.0.0.1:8000/docs`. Painel: `http://127.0.0.1:8000/painel/`.

Credenciais AWS são lidas da cadeia padrão do `boto3` (`~/.aws/credentials` ou variáveis de ambiente). **Nenhuma credencial é versionada neste repositório.** Para conferir o acesso: `python scripts/verificar_credenciais_aws.py` e `python scripts/testar_bedrock.py`.

### 2. Plugin

No pyRevit: *Settings → Custom Extension Directories* → adicionar a pasta raiz deste repositório e recarregar. A aba **NeuralBim** aparece no Revit. Selecione os elementos e clique em **Enviar Dados**.

### Configuração

Todos os caminhos e portas são parametrizáveis por variável de ambiente (ver `api/config.py`):

| Variável | Padrão |
|---|---|
| `NEURALBIM_API_HOST` / `NEURALBIM_API_PORT` | `127.0.0.1` / `8000` |
| `NEURALBIM_API_URL` (plugin) | `http://127.0.0.1:8000/elementos` |
| `NEURALBIM_STORAGE_DIR` | `api/dados_recebidos` |
| `NEURALBIM_DADOS_REFERENCIA_DIR` | `api/dados_referencia` |

## Endpoints principais

| Método | Rota | Função |
|---|---|---|
| `POST` | `/elementos` | Recebe um lote do plugin |
| `POST` | `/estimativa/gerar` | Gera estimativa (SINAPI + IA) para o último lote |
| `GET` | `/estimativa/ultima` · `/estimativa/historico` | Consulta estimativas |
| `POST` | `/estimativa/congelar` | Congela uma estimativa como oficial |
| `POST` | `/estimativa/gerar-mercado` | Estimativa sem tabela de referência (comparativo) |
| `GET/POST` | `/precos-confirmados` | Correções de preço confirmadas pelo engenheiro |
| `GET/POST/DELETE` | `/fornecedores`, `/gastos-reais` | Cadastros do painel |
| `GET` | `/materiais`, `/premissas`, `/analises/contador` | Dados auxiliares do painel |

## Decisões de projeto

- **Formato de dados único** para todas as categorias (parede, laje, pilar), facilitando incluir novas categorias.
- **Nenhuma suposição silenciosa:** toda aproximação automática (ex.: profundidade de pilar assumida) é registrada no campo `Observacoes` do elemento e chega ao painel.
- **IA verificada por cálculo determinístico:** o valor da IA nunca é sobrescrito; divergências são expostas como confiança baixa.
- **Peças separáveis:** plugin, API e módulo de IA se comunicam só por contratos JSON/HTTP.
- **Plugin em IronPython** (engine padrão do pyRevit) — por isso usa `System.Net` em vez de `requests` e `json.dumps(..., ensure_ascii=False)`.

## Validação

A pasta `validacao_2026-10-28/` contém a aplicação em uma residência térrea de 65 m² (paredes, lajes e pilares), comparando os quantitativos do sistema com uma referência geométrica e o custo com a mesma base SINAPI-PR. O relatório completo, os lotes brutos, os scripts de comparação (`pip install matplotlib` para gerar as figuras) e as figuras estão na pasta.

## Limitações conhecidas

- Escopo restrito a paredes, lajes e pilares; esquadrias, instalações, revestimentos e fundação não são orçados.
- Base de preços fixa (SINAPI-PR, referência 07/2026, não desonerado).
- Persistência em arquivos JSON locais — adequada ao protótipo, não a uso multiusuário.

## Autor

Gabriel Adão Festa — Engenharia Civil, Faculdade Guarapuava.

Projeto acadêmico. Todos os direitos reservados.
