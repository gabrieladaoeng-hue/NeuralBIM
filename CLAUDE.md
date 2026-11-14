# Projeto NeuralBIM — TCC Gabriel Festa

## Contexto
Plugin PyRevit + módulo de IA (AWS Bedrock/RAG) pra automatizar levantamento
de quantitativos e estimativa de custo na construção civil. TCC de Engenharia
Civil, com potencial de virar produto comercial depois.

## Nível do desenvolvedor
Python intermediário. Prefere entender o "porquê" antes do "como".
(Ver também a seção "Como trabalhamos" mais abaixo.)

## Decisões de arquitetura já travadas (não reabrir)
- Engine: IronPython (padrão do pyRevit) — necessário porque pyrevit.forms
  é usado no formulário de fallback e não funciona em CPython. Chamadas
  HTTP futuras usam System.Net.Http/WebClient via clr.AddReference, não a
  biblioteca requests.
- Estrutura de dados genérica: um formato comum (dict/JSON) que serve pra
  qualquer categoria de elemento (parede, laje, pilar) — não criar estrutura
  específica por categoria.
- Extração de material: puxar direto do modelo via API do Revit — do
  CompoundStructure do tipo para parede e laje, do parâmetro estrutural
  (STRUCTURAL_MATERIAL_PARAM) para pilar. Formulário manual de
  classificação é só fallback pra caso ambíguo.
- Instrumentação obrigatória em toda extração: timestamp de início/fim,
  flag se foi classificação automática ou manual, campo de confiança/observação.
- Nada de dados hardcoded (caminhos de arquivo, quantidade fixa de elementos)
  — tudo parametrizável.

## Padrões consolidados na Fase 1
- Toda função de classificação de material (parede, laje, pilar) retorna o
  mesmo formato de tripla `(sucesso, categoria, nomes_brutos)`. É isso que
  permite o mesmo fallback manual e a mesma lógica de `Observacoes` servirem
  qualquer categoria nova que for adicionada depois — basta a nova função
  devolver essa tripla.
- Toda suposição ou aproximação automática precisa ser registrada no campo
  `Observacoes` da linha afetada — nunca fica silenciosa. Exemplo já
  implementado: profundidade de pilar assumida igual à largura quando não
  existe parâmetro de profundidade separado (seção provavelmente quadrada).
- Casos de modelo BIM mal modelado ou ambíguo (função de camada mal
  definida, material fora do vocabulário) NÃO são corrigidos no Revit por
  padrão — são mantidos como casos de teste válidos, porque validam o
  comportamento de fallback do sistema sobre dados reais imperfeitos. Só
  mexer no modelo se for decidido explicitamente em conversa.
- Os vocabulários de material (`VOCABULARIO_MATERIAIS`,
  `OPCOES_MATERIAL_LAJE`, `OPCOES_MATERIAL_PILAR`) são intencionalmente
  pequenos no início e crescem conforme o uso real vai revelando os
  materiais que aparecem nos modelos.
- `json.dumps()` com o parâmetro padrão `ensure_ascii=True` quebra neste
  ambiente IronPython, porque a função interna que ele usa pra escapar
  caracteres não-ASCII tenta seu próprio `.decode()` — que não funciona
  neste ambiente, independente da codificação pedida (mesmo problema que
  afeta `.decode()` direto em qualquer lugar do código). Sempre chamar
  `json.dumps(..., ensure_ascii=False)` neste projeto.

## Padrões consolidados na Fase 5
- Espessura de parede tem dois campos distintos no registro exportado:
  `Espessura_cm` (`parede.Width` — a parede inteira, inclui reboco/
  chapisco/pintura) e `Espessura_Estrutural_cm` (novo — soma das camadas
  com `MaterialFunctionAssignment.Structure` do `WallType`, via
  `GetCompoundStructure()`, a mesma camada já usada na classificação de
  material). Motivo: os códigos SINAPI de alvenaria são pela espessura do
  bloco, não da parede acabada — os dois valores divergem na prática (ex.:
  bloco de 14cm com reboco nos dois lados mede ~17cm de `Espessura_cm`).
- `classificar_material_automatico` (`comum.py`) ordena o vocabulário
  priorizando termos de **tipo de peça** (`bloco ceramico`, `bloco de
  concreto`, `tijolo`) sobre termos **genéricos** de material/composição
  (`alvenaria`, `ceramico`, `concreto`), em vez de ordenar só por tamanho
  da string. Sem isso, "Alvenaria de Tijolo Cerâmico Maciço" seria
  classificada como bloco cerâmico, porque "alvenaria"/"ceramico" soltos
  são mais longos que "tijolo" e bateriam primeiro.
- `classificar_material_automatico` retorna uma **tripla**
  `(sucesso, categoria, categorias_distintas)`, não mais um par —
  `categorias_distintas` é a lista (sem duplicar) de todas as categorias
  encontradas entre as camadas estruturais de um elemento. Quando há mais
  de uma (ex.: laje com camada de concreto E camada pré-moldada), isso é
  registrado em `Observacoes` — no bloco próprio de parede e em
  `montar_observacoes` (laje/pilar) — em vez de reportar silenciosamente
  só a categoria da primeira camada como se fosse a única.
- Base de preços SINAPI vive em
  `api/dados_referencia/mapeamento_sinapi.json` — mapeia cada valor
  possível de `Material_Estrutural` (caminho automático do vocabulário +
  caminho manual dos 3 formulários) pra um código SINAPI, sem preço em R$
  (isso a Fase 6 busca dinamicamente na base SINAPI-PR vigente). As 16
  strings possíveis têm resolução explícita: `direto`,
  `por_espessura_estrutural_cm` (usa `Espessura_Estrutural_cm` pra
  escolher o bucket mais próximo, sem exigir igualdade exata),
  `sem_preco`, `fora_de_escopo` ou `pendente` — nenhuma cai em lacuna
  silenciosa. Suposição registrada: fck=25MPa fixo pra todo concreto
  armado moldado in loco, já que o vocabulário do plugin não distingue
  fck (mesmo espírito de "toda suposição registrada", aqui do lado do
  mapeamento em vez do lado da extração).
- Parede de concreto moldado in loco e pilar de aço/madeira laminada
  ficaram `fora_de_escopo` no mapeamento — decisão deliberada, não lacuna
  esquecida: o projeto real de validação (ver "Modelo de teste") é térreo
  e usa só alvenaria + concreto armado convencional.
- [RESOLVIDO] A composicao parametrica unica de concreto armado moldado
  in loco (codigo SINAPI 104487, versao terrea, e 104484, versao dois
  pavimentos) foi descontinuada na referencia SINAPI em 03/2024, sem
  sucessora do mesmo tipo -- confirmado por checagem cruzada no relatorio
  SINAPI_Manutencoes_2026_07.xlsx. As entradas 'Pilar/Laje - Concreto
  armado moldado in loco' e 'Laje macica de concreto' no
  mapeamento_sinapi.json foram decompostas em componentes separados e
  todos os codigos foram resolvidos: armacao (92762 pilar / 92770 laje),
  forma (92269+92409 pilar, somados / 92482 laje, unico) e concretagem
  (103669 pilar / 103682 laje, especifico para edificacao terrea).
  Suposicoes documentadas em nota_armadura / nota_bitola_armadura /
  nota_forma_concretagem no _leia_isto_primeiro: taxa de armadura
  (130kg/m3 pilar, 75kg/m3 laje), bitola representativa (CA-50 10mm
  pilar, 8mm laje), forma em madeira serrada com 1 utilizacao (sem
  reaproveitamento -- obra terrea unica), concretagem manual com baldes.
  Correcoes de extracao que viabilizaram isso: Volume_m3 do pilar (antes
  hardcoded vazio, agora calculado) e novo campo Area_Forma_m2 (exato
  para pilar via perimetro x altura, aproximado para laje via
  HOST_AREA_COMPUTED).

## Padrões consolidados na Fase 6
- Retrieval de preço (`api/precificacao.py`): `resolver_preco_elemento(elemento) -> dict`
  resolve as 3 resoluções com preço: `direto`, `por_espessura_estrutural_cm` (acha o
  bucket mais próximo por diferença absoluta de espessura, sem exigir igualdade exata)
  e `decomposto` (soma vários componentes, cada um com seu próprio código SINAPI e
  quantidade). Nunca inventa preço — código sem correspondência em
  `preco_sinapi_pr.json`, ou resolução `sem_preco`/`fora_de_escopo`/`pendente`, sempre
  devolve `{"tipo": "erro", "motivo": ...}` explícito.
- Agrupamento antes da IA (`api/agrupamento.py`): `agrupar_elementos()` junta
  elementos com o MESMO retrieval — mesma `Categoria` + mesmo código SINAPI (ou mesma
  tupla ordenada de códigos, no caso decomposto) — numa única chamada à IA, com as
  quantidades somadas, em vez de uma chamada por elemento. Elementos com erro no
  retrieval nunca são agrupados — continuam individuais, um por um. Motivo: menos
  chamadas à IA (custo) sem perder rastreabilidade — cada grupo guarda
  `elementos_originais` (lista de IDs originais) e `quantidade_elementos_agrupados`.
- Chamada ao Bedrock (`api/estimativa_ia.py`): `gerar_estimativa_ia(elemento,
  dados_preco)` monta o prompt (system separado da user message, via `converse()`) e
  chama o modelo `us.anthropic.claude-haiku-4-5-20251001-v1:0` na região `us-east-2`
  — usando o **perfil de inferência** (esse prefixo `us.`), não o ID direto do
  modelo, que não é suportado on-demand nessa região.
- **Contrato da IA sem aritmética (correção de arquitetura, pós-achado
  experimental abaixo)**: a partir da versão 2 do schema de saída (ver
  bullet `versao_schema` abaixo), a IA no modo SINAPI NÃO calcula mais
  custo — preço vem da tabela SINAPI e quantidade vem do modelo BIM, os
  dois já determinísticos antes da chamada, então multiplicar/somar é
  sempre feito em Python (`_calcular_custo_do_item`/
  `_definir_custo_calculado` em `api/estimativa_ia.py`). O papel da IA se
  reduz a avaliar se a correspondência elemento → código(s) SINAPI faz
  sentido e registrar as decisões de interpretação (divergência de
  unidade, múltiplas categorias de material, decomposição em componentes)
  em `memoria_calculo`/`suposicoes` — os dois campos continuam existindo,
  mas `memoria_calculo` deixou de narrar conta pra virar justificativa da
  correspondência. `custo_estimado_rs` e `confianca` saíram do formato de
  saída pedido à IA (`_FORMATO_DIRETO`/`_FORMATO_DECOMPOSTO`). Cada item
  agora carrega `custo_calculado_rs` (nome novo, não reaproveita
  `custo_estimado_rs` — justificativa no achado experimental abaixo), e o
  lote carrega `custo_total_calculado_rs` (soma de `custo_calculado_rs`
  por item, nunca mais soma do valor declarado pela IA).
- `_validar_custo_estimado`, `confianca` e `validacao_custo` estão
  **encerrados** — não são mais produzidos por nenhuma geração nova.
  Arquivos gerados antes da mudança continuam legíveis normalmente (nada
  no disco muda retroativamente) e o bloco "Divergência detectada" de
  `painel.html` (`montarBlocoConsideracoes`) continua renderizando
  `validacao_custo` pra quem tiver esse campo — só não é mais alimentado
  por análises novas. `custoDoItem()` (duplicada em
  `index.html`/`painel.html`/`obra.html`/`mercado.html`) lê
  `custo_calculado_rs` primeiro; só cai pro fallback
  (`componentes_detalhados` ou `custo_estimado_rs` cru) quando o item não
  tem `custo_calculado_rs`, ou seja, quando o arquivo é de antes dessa
  mudança.
- `versao_schema: 2` no topo do JSON de saída dos dois modos (SINAPI e
  mercado, `api/estimativa_ia.py` e `api/estimativa_mercado_ia.py`).
  Versão 1 (implícita — arquivos gerados antes de existir esse campo) tem
  `custo_estimado_rs`/`confianca`/`validacao_custo` por item e
  `custo_total_estimado_rs` no lote; versão 2 tem `custo_calculado_rs` por
  item e `custo_total_calculado_rs` no lote, e nenhum dos três campos
  antigos. Existe porque, sem esse campo, não havia como distinguir
  automaticamente um arquivo gerado antes ou depois da correção de
  arquitetura — e os 18+ arquivos antigos são evidência da monografia, não
  dá pra simplesmente sobrescrever ou ignorar a diferença de contrato.
- `preco_aplicado` (itens não-decompostos, `direto`/
  `por_espessura_estrutural_cm`) ganhou `preco_unitario_rs` e
  `quantidade`, ao lado dos campos que já existiam (`codigo_sinapi`,
  `descricao_sinapi`, `unidade_sinapi`, `espessura_real_cm`,
  `bucket_espessura_cm`). Antes disso, um item não-decomposto não guardava
  em nenhum campo estruturado o preço nem a quantidade usados no cálculo —
  só o item decomposto tinha essa evidência, em `componentes_detalhados`.
  Agora os dois casos têm o mesmo nível de rastreabilidade.
- Nomes de campo diferentes pra resoluções diferentes na saída de
  `estimativa_por_elemento`: itens com resolução `direto`/
  `por_espessura_estrutural_cm` (preço único) usam `codigo_sinapi_usado`
  (singular); itens `decomposto` usam `codigos_sinapi_usados` (lista/plural).
  Não é inconsistência a corrigir — são dois formatos de saída diferentes que
  a IA segue (`_FORMATO_DIRETO` vs `_FORMATO_DECOMPOSTO` em
  `estimativa_ia.py`). Código que lê essa saída (ex.: o painel) não deve
  assumir um nome fixo por categoria (Laje pode ser tanto decomposto —
  concreto armado moldado in loco — quanto não-decomposto — laje
  pré-moldada) — o sinal confiável é a presença de `componentes_detalhados`,
  não a `Categoria`.
- **Achado experimental — repetição de chamada (registro bruto, sem
  interpretação adicional)**: configuração testada — Claude Haiku 4.5 via
  Bedrock, `temperature=0.1`, região `us-east-2`. Mesma entrada (grupo
  "Pilar - Concreto armado moldado in loco", 6 elementos agrupados) chamada 3
  vezes seguidas.
  - Registro original do padrão (Fase 6, anterior a este teste de repetição):
    pilares com geometria idêntica produziram o mesmo valor errado em
    chamadas separadas, confirmando que o erro é sistemático por entrada
    (mesmo dado → mesmo erro), não um acaso de amostragem. Este teste de 3
    execuções repetidas confirma o mesmo padrão por outro ângulo — ver
    `custo_estimado_rs` idêntico abaixo.
  - `custo_estimado_rs` devolvido pela IA: `6847,89` nas 3 execuções (estável).
  - Total escrito em `memoria_calculo` pela IA: `16.148,81` / `16.948,81` /
    `16.948,81` com autocorreção interna para `15.948,81` dentro da própria
    terceira resposta.
  - Soma real dos componentes recuperados (calculada pelo código, via
    `_calcular_custo_esperado`, não pela IA): `15.945,66`, estável nas 3
    execuções.
  - Divergências (`diferenca_percentual`) observadas na análise completa do
    lote, por tipo de item: `-0,01%` e `0,1%` nos itens de cálculo direto
    (Parede); `-65,7%` (Laje) e `-57,1%` (Pilar) nos itens decompostos.
  - Não testado: `temperature=0` — fica como verificação futura.
  - **Observação exploratória adicional (não é experimento controlado)**: os
    18 arquivos de estimativa acumulados em disco ao longo da sessão (lotes e
    versões de código diferentes, não uma repetição controlada da mesma
    entrada) registram 9 valores distintos de `custo_estimado_rs` pro grupo de
    Pilar: `2.045,89` / `1.581,89` / `2.581,89` / `3.110,89` / `5.840,36` /
    `5.840,77` / `4.847,89` / `5.847,89` / `6.847,89`. Todos terminam em
    `,89`, e há diferenças de exatamente R$ 1.000,00 entre três deles
    (`4.847,89` / `5.847,89` / `6.847,89`). Padrão chamativo, mas registrado
    aqui só como observação — não dá pra atribuir a uma causa sem isolar
    lote e prompt como variável única, o que essa amostra não faz.
  - A execução que gerou o total `16.148,81` em `memoria_calculo` (citado
    acima) não sobreviveu: o arquivo de saída daquela geração foi
    sobrescrito por uma chamada seguinte sobre o mesmo lote, antes do
    versionamento por timestamp existir (ver bullet de
    `gerar_estimativa_lote` abaixo). Hoje só consta esse registro escrito —
    não há mais arquivo em disco com esse valor bruto pra conferir.
  - **Status atualizado**: esse achado deixou de ser só um problema
    sinalizado em tempo de execução (`_validar_custo_estimado`, confiança/
    `validacao_custo`) e passou a ser a medição que justifica a correção
    de arquitetura registrada acima — a partir da versão 2 do schema, a IA
    não faz mais essa conta, eliminando o erro na raiz em vez de só
    sinalizá-lo.
- **Bug histórico corrigido na versão 2**: até a versão 1,
  `custo_total_estimado_rs` (gravado no lote) somava o valor DECLARADO
  pela IA (`custo_estimado_rs`), enquanto o KPI do painel
  (`custoDoItem`/`calcularEstimadoPorCategoria`) somava o valor
  recalculado — os dois podiam divergir bastante quando havia itens
  decompostos com erro de aritmética. Exemplo real, mesmo arquivo, mesma
  tela: `estimativa_lote_2026-09-17_20-26-04_2026-09-17_20-26-54.json`
  mostrava R$ 150.606,48 na tabela "Histórico de versões" (`GET
  /estimativa/historico`, leitura direta de `custo_total_estimado_rs`)
  contra R$ 269.174,40 no KPI "Custo total estimado" da mesma página —
  diferença de R$ 118.567,92. Arquivos da versão 1 mantêm essa divergência
  interna (são estáticos, não há como recalcular retroativamente sem
  reprocessar a IA); a versão 2 tem fonte única (`custo_calculado_rs`)
  tanto no KPI quanto no total do lote, então os dois números sempre
  batem.
- `gerar_estimativa_lote(caminho_lote)` roda agrupamento + retrieval + IA pro lote
  inteiro, salva o resultado em `ESTIMATIVAS_DIR`
  (`api/dados_recebidos/estimativas/`), e devolve `quantidade_chamadas_ia` (quantas
  vezes a IA foi chamada de fato, excluindo elementos com erro de retrieval, que
  nunca chegam a chamar).
  Nome do arquivo de saída é `estimativa_{nome_lote}_{timestamp_da_geracao}.json`
  (Etapa 8) — inclui o timestamp da geração, não só o nome do lote. Antes dessa
  mudança o nome era só `estimativa_{nome_lote}.json`: rodar "Gerar nova
  análise" mais de uma vez sobre o mesmo lote sobrescrevia o arquivo anterior
  em silêncio, perdendo a estimativa gerada antes — foi esse mecanismo que
  apagou a evidência bruta de uma das execuções do achado experimental acima.
  Versionamento completo (`oficial.json`, `POST /estimativa/congelar`, `GET
  /estimativa/historico`) documentado no bullet próprio na seção Etapa 7.

## Padrões consolidados na Etapa 7
- Painel web em 4 páginas HTML autocontidas (`api/static/`), sem framework e sem
  build step: `index.html` (início, KPIs de análises geradas/chamadas à IA, gráfico
  comparativo "Estimado pela IA × Gasto real" por categoria), `painel.html`
  (estimativa de custo — KPIs, gráfico por categoria, tabela de elementos/grupos com
  confirmação manual de preço), `fornecedores.html` (cadastro de fornecedor +
  comparação preço de mercado × preço SINAPI, ver bullet próprio abaixo) e
  `obra.html` (registro de gasto real por categoria, com subtotais). Tema escuro
  (`#0d1117`/`#161b22`/`#3b82f6`...) duplicado nas 4 páginas de propósito — mudar uma
  cor exige repetir nas outras 3, documentado em comentário no topo de cada
  `<style>`.
- Persistência simples em lista JSON (`api/storage/lista_json.py`):
  `carregar_lista`/`acrescentar_item`/`remover_item`, sem banco de dados — decisão
  deliberada de protótipo (Etapa 7 vem antes da validação real, ver Roteiro). Todo
  item ganha um `id` (uuid4) ao ser gravado; itens já salvos antes dessa garantia
  existir são migrados (ganham `id`) na primeira leitura via `carregar_lista`, que
  regrava o arquivo imediatamente — sem exigir nenhuma ação manual.
- `POST /estimativa/gerar` é o ÚNICO endpoint que chama o Bedrock — acionamento
  deliberado (botão "Gerar nova análise" no painel), nunca automático. `GET
  /estimativa/ultima` só lê do disco o resultado já salvo, nunca chama a IA.
- Categoria de gasto real (`api/models/gasto_real.py`) é `Literal["Parede", "Laje",
  "Pilar"]` fixo, não texto livre — garante que o gráfico comparativo da página
  inicial sempre consegue casar a categoria do gasto real com a categoria que a
  estimativa da IA já usa.
- Fornecedor (`api/models/fornecedor.py`) exige `categoria`
  (`Literal["Parede", "Laje", "Pilar"]`) e `unidade`
  (`Literal["M2", "M3", "KG", "UN"]`) — `categoria` é obrigatória porque o par
  (elemento, material_estrutural) é a chave real do mapeamento SINAPI, não o
  texto do material sozinho (ex.: "Concreto armado moldado in loco" é uma
  entrada em Pilar e outra, com códigos diferentes, em Laje). `componente` e
  `espessura_cm` são opcionais e só fazem sentido condicionados à resolução do
  material escolhido (`componente` pra `decomposto`, `espessura_cm` pra
  `por_espessura_estrutural_cm`) — o frontend restringe isso via cascata de
  selects, o backend não valida a combinação contra o vocabulário vigente.
  `GET /fornecedores` não tem `response_model` e não revalida contra o
  modelo — registros salvos antes desses campos existirem continuam sendo
  lidos normalmente (sem `categoria`/`unidade`), tratados na tela como "sem
  categoria vinculada", fora de qualquer estatística.
- `GET /materiais` (`api/routes/materiais.py` +
  `precificacao.listar_materiais_com_preco()`) achata mapeamento_sinapi.json
  com o preço SINAPI já resolvido de preco_sinapi_pr.json — alimenta o
  seletor Categoria/Material do cadastro de fornecedores e a comparação
  preço de mercado × SINAPI em `fornecedores.html`. Só inclui resoluções com
  algum código de verdade (`direto`, `por_espessura_estrutural_cm`,
  `decomposto`) — `sem_preco`/`fora_de_escopo`/`pendente` ficam de fora.
  Comparação de preço só é possível em 3 casos: resolução `direto` (código
  único); `por_espessura_estrutural_cm`, desde que o fornecedor informe a
  espessura (o preço varia por bucket, não existe um "preço do material"
  único); e `decomposto`, mas só quando o fornecedor cota um **componente
  isolado** (ex.: só a armação, em R$/kg) — a composição inteira nunca tem
  um preço SINAPI único pra comparar (são códigos de unidades diferentes
  somados, ex.: kg + m² + m³), então nesse caso a tela mostra "comparação
  indisponível (composição multi-código)" e nunca inventa um número.
- Versionamento de estimativas (Etapa 8): cada `POST /estimativa/gerar` grava
  um arquivo novo (nome com timestamp da geração, ver bullet de
  `gerar_estimativa_lote` na Fase 6), nunca sobrescreve. Uma delas pode ser
  marcada como "oficial da validação" via `POST /estimativa/congelar`
  (recebe `{"arquivo": ...}`), que grava `ESTIMATIVAS_DIR/oficial.json` com
  `{"arquivo", "congelado_em"}`. `GET /estimativa/ultima` prioriza a oficial
  (se o arquivo dela ainda existir); senão cai pro mais recente por data de
  geração, como antes — mas se a oficial foi congelada e o arquivo dela
  sumiu do disco (apagado à mão, por exemplo), a rota NÃO cai no fallback em
  silêncio: ainda devolve a mais recente, mas com
  `oficial.arquivo_oficial_ausente` preenchido, pro `painel.html` mostrar um
  aviso vermelho explícito. `GET /estimativa/historico` lista todos os
  arquivos (data, custo total, qual é a oficial) — sem essa rota o
  versionamento existiria só no disco, sem ninguém alcançar. Em
  `painel.html`: uma faixa no topo mostra o status da estimativa exibida
  (não congelada / oficial congelada com data / oficial ausente com aviso)
  com botão "Marcar esta como oficial", e uma seção "Histórico de versões"
  no fim lista todas com botão "Congelar" em cada uma; os dois botões pedem
  confirmação via `window.confirm()` antes de enviar, porque a ação muda
  qual estimativa o painel inteiro (Início, Estimativa de custo, Controle
  de obra) passa a exibir.

## Padrões consolidados na Etapa 8b — modo mercado
- Objetivo: comparar, no mesmo quantitativo, uma estimativa ancorada em base
  oficial (SINAPI/RAG, Fase 6) contra uma não ancorada
  (`api/estimativa_mercado_ia.py`) — mesmo modelo (Claude Haiku 4.5), mesma
  `temperature=0.1`, mesma região (Paraná), mesmo lote. Nunca substitui o
  modo SINAPI, nunca é usado por ele.
- **Primeira execução real** (lote `lote_2026-09-14_19-00-27`), preço
  unitário provável (mercado) × preço unitário SINAPI equivalente:
  - Parede — Alvenaria de bloco cerâmico: R$ 120,00 × R$ 186,09 (-35,5%)
  - Parede — Bloco cerâmico de vedação 6 furos: R$ 65,00 × R$ 186,09 (-65,1%)
  - Laje — Concreto armado moldado in loco: R$ 380,00 × R$ 740,90 (-48,7%)
  - Pilar — Concreto armado moldado in loco: R$ 1.600,00 × R$ 6.944,98 (-77,0%)
  - Total provável: R$ 64.680,75 (faixa R$ 46.944,80–R$ 87.580,35) × total
    SINAPI R$ 71.302,19.
- Observações registradas das premissas devolvidas pela IA nessa execução
  (sem interpretação além do que está escrito):
  (a) a IA declarou "preços praticados no Paraná em 2024" — defasagem
      frente à referência SINAPI vigente (07/2026);
  (b) a IA assumiu taxa de armação ~80-100 kg/m³ e fôrmas "reutilizáveis
      amortizadas em múltiplas utilizações" no pilar — a premissa do
      projeto (`_leia_isto_primeiro` em `mapeamento_sinapi.json`) é 130
      kg/m³ pra pilar e forma de madeira com 1 utilização (sem
      reaproveitamento) — parte do desvio observado é composição/escopo
      diferente, não só preço;
  (c) "Alvenaria de bloco cerâmico" e "Bloco cerâmico de vedação 6 furos"
      resolvem para o MESMO código SINAPI (186,09) no mapeamento, mas
      receberam preços diferentes da IA (120,00 e 65,00) nessa execução.

## Estrutura de arquivos
O código do botão "Enviar Dados"
(`NeuralBim.extension/NeuralBim.tab/IA.panel/Enviar Dados.pushbutton/`) está
dividido em:
- `script.py`: ponto de entrada. Mostra os alertas de etapa, orquestra as 3
  seleções (paredes → lajes → pilares), consolida tudo num só `dados_finais`
  e exporta o CSV único.
- `comum.py`: vocabulário de material, fatores de conversão e funções
  compartilhadas entre categorias — classificação de material, exportação de
  CSV, e a orquestração genérica de laje/pilar (agrupar por tipo, resolver
  classificação automática ou fallback manual).
- `paredes.py`, `lajes.py`, `pilares.py`: tudo que é específico de cada
  categoria (filtro de seleção, opções de material próprias, extração dos
  dados daquele elemento).

`comum.py` tem 2 imports "lazy" (dentro de função, não no topo do arquivo)
que puxam de `lajes.py` / `pilares.py`. São intencionais: resolvem a
dependência circular (esses módulos importam `comum.py` no topo) e só
executam em runtime, quando tudo já está carregado. Não remover nem subir
pro topo.

## Como trabalhamos
- Gabriel: nível intermediário/básico em programação. Aprende melhor com
  analogias de engenharia civil. Quer entender o "porquê" antes do "como".
- Papel esperado do Claude: professor E executor ao mesmo tempo — explicar
  o raciocínio e entregar o código.
- Decisões técnicas: ser assertivo. Decidir e explicar o porquê, sem
  perguntar "qual você prefere" para escolhas puramente técnicas. Só
  perguntar quando a decisão depende de algo que só o Gabriel sabe
  (prioridade, prazo, preferência real de produto).
- Antes de aplicar qualquer mudança de código, sempre mostrar um
  resumo/diff das alterações propostas e aguardar confirmação explícita.
  Nunca aplicar direto.
- Prazo real: setembro a dezembro. Foco importa mais que tempo fixo de
  sessão — cada sessão fecha quando a etapa fecha, não pelo relógio.

## Modelo de teste (já montado no Revit)
Sala 01 e Sala 02 (com room), Pátio (sem room, de propósito — testa fallback),
parede externa (Bloco Cerâmico) e parede interna (15cm INTERNO) com tipos
diferentes, 1 laje única com furo, pilares quadrados (450x450 e 300x300).

Validado na Fase 1:
- Laje única com furo: extração OK, incluindo o caso de material não
  reconhecido pelo vocabulário ("PRE MOLDADO") caindo corretamente no
  fallback manual.
- Pilares quadrados: 450x450 (x2) e 300x300 (x1). Um deles valida o
  fallback de profundidade ausente — parâmetro de profundidade não
  encontrado, profundidade assumida igual à largura e registrada em
  `Observacoes`.

Projeto real de validação (Roteiro, etapa 8): edificação térrea,
estrutura em alvenaria (bloco cerâmico/concreto) + concreto armado
convencional moldado in loco (pilares, vigas, laje). Sem parede de
concreto moldado in loco, sem pilar de aço ou madeira — por isso essas
combinações ficaram `fora_de_escopo` no mapeamento SINAPI da Fase 5. Se o
escopo do projeto real mudar, revisar o mapeamento.

## Fase atual
Etapas 1 a 7 do Roteiro do projeto — COMPLETAS:
- extração de paredes, lajes e pilares num só fluxo/CSV (código dividido
  em script.py + comum.py + paredes.py + lajes.py + pilares.py, ver seção
  Estrutura de arquivos), com classificação automática + fallback manual
  seguro, geometria vencendo nome do tipo, instrumentação completa
  (timestamp, Observacoes), e os ajustes da Fase 5 (Espessura_Estrutural_cm,
  ordenação de vocabulário por tipo de peça, detecção de múltiplas
  categorias);
- API web (`api/`) recebendo esses dados via `envio_api.py` (POST
  /elementos), com storage local em JSON;
- base de preços SINAPI (`api/dados_referencia/mapeamento_sinapi.json`)
  cobrindo os 16 valores possíveis de Material_Estrutural;
- módulo de IA (Fase 6, `api/precificacao.py` + `api/agrupamento.py` +
  `api/estimativa_ia.py`) consultando a base SINAPI-PR vigente e gerando
  estimativa de custo via Bedrock, com agrupamento de elementos idênticos
  antes da chamada e validação cruzada contra erro de aritmética da IA
  (ver seção "Padrões consolidados na Fase 6");
- painel web (Etapa 7, `api/static/*.html`) pro engenheiro ler a
  estimativa gerada, cadastrar fornecedores e registrar gasto real por
  categoria, comparando com o estimado pela IA (ver seção "Padrões
  consolidados na Etapa 7").

Próxima etapa: etapa 8 do Roteiro — validar no projeto real, comparando
com o método tradicional de levantamento manual (tempo e confiabilidade).

## Roteiro do projeto

1. Travar decisões de arquitetura — Concluído
2. Fechar extração de paredes — Concluído
3. Estender extração para lajes e pilares — Concluído
4. Construir a API que recebe os dados do plugin — Concluído
5. Montar a base de preços de mercado — Concluído
6. Implementar o módulo de IA (RAG + AWS Bedrock) — Concluído
7. Construir o painel web de visualização de resultados (engenheiro lê a
   estimativa gerada pela IA) — etapa necessária antes da validação,
   pois comparar com o método tradicional exige uma forma de ler o
   resultado gerado pela IA, não apenas tê-lo armazenado — Concluído
8. Validar no projeto real, comparando com o método tradicional de
   levantamento manual (tempo e confiabilidade)
9. Consolidar dados e redigir a monografia
