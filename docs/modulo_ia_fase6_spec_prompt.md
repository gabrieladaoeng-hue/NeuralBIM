# Módulo de IA (Fase 6) — Especificação do contrato de prompt

> Documento de trabalho pra implementação no Claude Code. Define o que entra no
> prompt do Bedrock e o que ele deve devolver. Atualizado com o schema real da
> API (Fase 4) e a estrutura de decomposição do concreto armado (Fase 5/6).

## Decisão de arquitetura (registrada)

O código (API/plataforma) é responsável só por **recuperar** os dados —
quantitativo do elemento + preço SINAPI do(s) código(s) mapeado(s) na Fase 5.
**A análise/estimativa em si é feita pela IA dentro do prompt**, não por uma
fórmula fixa em Python. Nenhum preço fica pré-calculado ou hardcoded no
código — só os dados brutos de referência (SINAPI) e o quantitativo extraído.

Fonte de preços por enquanto: **só SINAPI-PR** (decisão de escopo do
protótipo — outras fontes de mercado podem entrar depois).

---

## 1. Entrada — quantitativo do elemento (schema real, `api/models/elemento.py`)

Todos os elementos (Parede/Laje/Pilar) usam o mesmo modelo `Elemento`; campos
não aplicáveis à categoria vêm em branco (`""` ou `None`).

Exemplo real (parede):
```json
{
  "Categoria": "Parede",
  "ID": 567696,
  "Nivel": "TÉRREO",
  "Material_Estrutural": "Alvenaria de bloco ceramico",
  "Classificacao_Automatica": true,
  "Materiais_Brutos_Extraidos": ["Alvenaria - Bloco de Cerâmico - 14cm"],
  "Observacoes": "...",
  "Posicao": "Indefinida",
  "Espessura_cm": 17.1,
  "Espessura_Estrutural_cm": 14.0,
  "Area_m2": 14.55,
  "Area_Forma_m2": "",
  "Volume_m3": 2.491
}
```

Exemplo real (pilar):
```json
{
  "Categoria": "Pilar",
  "Material_Estrutural": "Concreto armado moldado in loco",
  "Observacoes": "...",
  "Largura_cm": 45.0,
  "Profundidade_cm": 45.0,
  "Altura_m": 3.0,
  "Espessura_cm": "",
  "Espessura_Estrutural_cm": "",
  "Area_m2": "",
  "Area_Forma_m2": 5.4,
  "Volume_m3": 0.607
}
```

## 2. Entrada — preço(s) recuperado(s) via `mapeamento_sinapi.json` (retrieval, não fixo)

A recuperação consulta `mapeamento_sinapi.json` pelo `Material_Estrutural` do
elemento. Duas formas de resolução:

**`resolucao: "direto"`** — um único preço (ex.: parede de alvenaria):
```json
{
  "codigo_sinapi": "103335",
  "descricao": "ALVENARIA DE VEDAÇÃO DE BLOCOS CERÂMICOS...",
  "unidade_sinapi": "M2",
  "preco_unitario_rs": 186.09,
  "mes_referencia": "07/2026",
  "regime": "não desonerado"
}
```

**`resolucao: "decomposto"`** — lista de componentes, cada um com seu próprio
código, unidade e quantidade (ex.: pilar de concreto armado — 4 componentes):
```json
[
  { "componente": "armacao", "codigo_sinapi": "92762", "unidade_sinapi": "KG",
    "preco_unitario_rs": 11.77, "quantidade_formula": "Volume_m3 x 130 (taxa_armadura_kg_por_m3.pilar)" },
  { "componente": "forma_fabricacao", "codigo_sinapi": "92269", "unidade_sinapi": "M2",
    "preco_unitario_rs": 129.79, "quantidade_formula": "Area_Forma_m2" },
  { "componente": "forma_montagem_desmontagem", "codigo_sinapi": "92409", "unidade_sinapi": "M2",
    "preco_unitario_rs": 270.57, "quantidade_formula": "Area_Forma_m2" },
  { "componente": "concretagem", "codigo_sinapi": "103669", "unidade_sinapi": "M3",
    "preco_unitario_rs": 1020.68, "quantidade_formula": "Volume_m3" }
]
```

## 3. Prompt — papel da IA (system)

> "Você é um módulo de análise de custos de construção civil. Recebe
> quantitativos extraídos de um modelo BIM (Revit) e registros oficiais de
> preço da tabela SINAPI-PR — que podem vir como um preço único ou como uma
> lista de componentes a somar (quando a composição foi decomposta). Sua
> tarefa é analisar essas informações e gerar uma estimativa de custo
> fundamentada — cruzando quantidade, unidade e preço unitário de cada
> componente, tratando divergências de unidade e múltiplas categorias de
> material por elemento. Nenhuma suposição pode ser silenciosa: toda
> conversão, aproximação ou decisão de desambiguação deve ser explicitada no
> campo `suposicoes` da resposta."

O user message envia os dois blocos JSON acima (quantitativo + preço(s)
recuperado(s), único ou lista de componentes) e pede a saída no formato da
seção 4.

## 4. Saída esperada (a IA deve retornar exatamente este formato)

Elemento simples (preço único):
```json
{
  "estimativa_por_elemento": [
    {
      "elemento_id": "parede_0231",
      "custo_estimado_rs": 2706.86,
      "codigo_sinapi_usado": "103335",
      "memoria_calculo": "14.55 m2 x R$186,09/m2",
      "suposicoes": [],
      "confianca": "alta"
    }
  ],
  "custo_total_estimado_rs": 98765.43,
  "observacoes_gerais": "...",
  "mes_referencia_precos": "07/2026"
}
```

Elemento decomposto (soma de componentes) — mesmo formato, com o detalhe por
componente dentro de `memoria_calculo`:
```json
{
  "elemento_id": "pilar_0198",
  "custo_estimado_rs": 3346.71,
  "codigos_sinapi_usados": ["92762", "92269", "92409", "103669"],
  "memoria_calculo": "armacao: 0.607m3 x 130kg/m3 x R$11,77/kg = R$928,15 | forma_fabricacao: 5.4m2 x R$129,79/m2 = R$700,87 | forma_montagem_desmontagem: 5.4m2 x R$270,57/m2 = R$1461,08 | concretagem: 0.607m3 x R$1020,68/m3 = R$619,56 | total = R$3709,66",
  "suposicoes": ["taxa de armadura 130kg/m3 assumida (sem Rebar modelado)"],
  "confianca": "media"
}
```

## 5. Casos especiais que o prompt precisa tratar explicitamente

- **Unidade divergente**: quantitativo do Revit em m³, preço SINAPI cotado por
  m² (ou vice-versa) → IA converte usando a espessura informada e registra a
  conversão em `memoria_calculo`.
- **Múltiplas categorias por elemento** (campo `Observacoes`) → IA decide como
  combinar/ponderar os códigos SINAPI envolvidos e registra a decisão em
  `suposicoes`.
- **Elemento decomposto** (`resolucao: "decomposto"`) → IA soma o custo de
  cada componente da lista (cada um com sua própria quantidade/fórmula) e
  detalha cada parcela em `memoria_calculo`, não apenas o total.
- **Código SINAPI sem preço encontrado** → IA marca `confianca: "baixa"` e não
  inventa valor.

## 6. Próximos passos técnicos

1. Implementar a chamada ao Bedrock (Claude Haiku 4.5, perfil de inferência
   Geo/Global, região us-east-2/Ohio) usando este prompt, retornando o JSON
   da seção 4.
2. Implementar a lógica de retrieval no lado da API: dado um elemento,
   consultar `mapeamento_sinapi.json` pelo `Material_Estrutural`, resolver
   "direto" (1 preço) ou "decomposto" (lista de componentes), buscando cada
   preço em `preco_sinapi_pr.json`.
3. Testar com um lote real exportado do plugin (ex. `lote_2026-09-11_*.json`)
   antes de integrar ao painel web (Etapa 7).
