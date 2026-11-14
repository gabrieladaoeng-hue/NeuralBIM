# Validação do NeuralBIM: CasaMCMV 65 m² (28/10/2026)

Modelo de validação: `CasaMCMV_65m2_VALIDACAO_2026-10-28.rvt`, cópia congelada. É uma casa térrea padrão Minha Casa Minha Vida de 8,00 × 8,15 m, com sala, cozinha, área de serviço, 2 quartos, banheiro e circulação. Tem pé-direito de 2,80 m, níveis TÉRREO e COBERTURA, 10 paredes, 2 lajes, 8 pilares, 7 portas e 6 janelas.

Preços: SINAPI-PR, referência 07/2026, não desonerado, fonte CSD (os mesmos conferidos contra a planilha oficial em 26/10/2026).

## 1. Resumo dos resultados

| Indicador | Resultado |
|---|---|
| Custo total estimado (oficial, congelado 28/10 20:44) | **R$ 56.269,11** |
| Conferência independente (preço × quantidade recalculado fora do sistema) | R$ 56.269,12, diferença de R$ 0,01 (arredondamento por item) |
| Execuções do plugin com o modelo completo | 6, com **resultado idêntico nas 6** (20 elementos, mesmos valores) |
| Execuções da IA no modo SINAPI (mesmo lote) | 8 (3 em 26/10 e 5 em 28/10), com **custo idêntico nas 8** e 0 erros |
| Quantitativo × referência geométrica | lajes 0,00%; pilares −0,08%; paredes externas −0,01% (total); paredes internas −4,05% (convenção de medição, ver §4) |
| Diferença de custo total frente à referência pelo eixo | −R$ 509,17 (−0,90%) |
| Tempo médio do plugin (seleção + extração + envio) | 30,3 s (de 20 a 49 s, n = 6) |
| Tempo médio da análise de IA no modo SINAPI | 27,6 s (de 26,9 a 28,6 s, n = 5) |
| Custo de API por análise SINAPI | ≈ US$ 0,024 (6.163 tokens de entrada e 3.123 de saída) |
| Modo mercado (IA sem tabela), provável | R$ 29.655,25, **47,3% abaixo do SINAPI**. Variou 11% entre 26/10 e 28/10 |

## 2. Execuções do plugin (Enviar Dados)

| Lote | Quem | Elementos | Duração (s) | Igual ao primeiro lote completo? |
|---|---|---|---|---|
| lote_2026-10-26_20-16-22 | Gabriel | 20 | 24 | sim |
| lote_2026-10-26_20-41-44 | Gabriel | 20 | 20 | sim |
| lote_2026-10-28_20-34-40 | Claude | 20 | 49 | sim |
| lote_2026-10-28_20-36-19 | Claude | 20 | 32 | sim |
| lote_2026-10-28_20-37-20 | Claude | 20 | 28 | sim |
| lote_2026-10-28_20-38-31 | Claude (só paredes) | 10 | 22 | seleção parcial |
| lote_2026-10-28_20-39-25 | Claude | 20 | 29 | sim (lote oficial) |

- **Duração:** é a diferença entre os carimbos de início e fim gravados no lote. Inclui o tempo humano de seleção nas 3 etapas. Nas execuções do Claude, o tempo de operação remota da tela está incluído.
- **Classificação:** todos os tipos foram reconhecidos automaticamente, sem diálogo de classificação manual.
- **Posição das paredes:** com ambientes modelados, as paredes saíram como Externa (4) e Interna (6). No modelo anterior, sem ambientes, saíam todas como "Indefinida".
- **Seleção parcial:** foram enviadas só as paredes, e o sistema estimou R$ 26.444,60 (2 grupos, 11,4 s). Lajes e pilares ausentes simplesmente não entram no orçamento, sem erro e sem aviso de que estão faltando.

## 3. Referência geométrica

Botão "Medir Referência" do plugin, somente leitura. Ele mede direto da geometria, sem usar a área calculada pelo Revit:

- **Parede:** comprimento do eixo × altura (do nível base ao nível topo), menos largura × altura de cada porta ou janela hospedada (todas descontadas).
- **Laje:** área do contorno do esboço, pela fórmula do polígono.
- **Pilar:** b × h × altura; a fôrma é perímetro × altura.

## 4. NeuralBIM × referência

| Categoria | n | Qtd. referência | Qtd. NeuralBIM | Erro médio absoluto (MAPE) | Maior erro | Elementos > 5% | Custo ref. | Custo NeuralBIM |
|---|---|---|---|---|---|---|---|---|
| Parede | 10 | 132,61 m² | 130,36 m² | 3,59% | 10,33% | 3 | R$ 26.956,26 | R$ 26.444,61 |
| Laje | 2 | 130,40 m² | 130,40 m² | 0,00% | 0,00% | 0 | R$ 23.341,60 | R$ 23.341,60 |
| Pilar | 8 | 0,809 m³ | 0,808 m³ | 0,08% | 0,08% | 0 | R$ 6.480,40 | R$ 6.482,88 |
| **Total** | 20 | | | 1,83% | | 3 | **R$ 56.778,26** | **R$ 56.269,09** |

O custo NeuralBIM desta tabela (R$ 56.269,09) é o lote recalculado com a mesma conta da referência. O total oficial do sistema é R$ 56.269,11; a diferença de R$ 0,02 está no pilar, porque o sistema arredonda cada componente antes de somar.

**Por que as paredes diferem:**

- **A diferença é de convenção, não de extração.** O NeuralBIM lê a área calculada pelo próprio Revit, que reparte cada encontro de paredes entre elas sem contar duas vezes. A medição pelo eixo conta duas vezes o trecho de cada encontro.
- **No total das paredes externas a diferença é de 0,01%.** Por parede ela chega a +3,05% e −2,50%, porque o Revit atribui o canto a uma das duas paredes.
- **Nas internas, a diferença total é de −4,05%** (2,25 m², ou 0,80 m de comprimento a 2,80 m de altura). Isso coincide com a soma das sobreposições nos encontros calculada a partir das espessuras: 0,795 m.
- **A parede menor tem o maior erro relativo.** A 328137 (1,70 m de eixo) chega a −10,3%, porque os dois encontros dela representam uma fração grande do comprimento.
- **Conclusão para o TCC:** a ferramenta não erra na extração. O resultado depende da convenção de medição. O levantamento manual precisa declarar a convenção: pelo eixo, ou de face a face nos encontros. Esse é o mesmo ponto da seção 5 do protocolo.

## 5. Custo por grupo (estimativa oficial)

| Grupo | Código SINAPI | Quantidade | Preço unitário | Custo |
|---|---|---|---|---|
| Paredes externas, bloco cerâmico 14 cm (4) | 103335 | 77,11 m² | R$ 186,09 | R$ 14.349,40 |
| Paredes internas, bloco cerâmico 9 cm (6) | 103351 | 53,25 m² | R$ 227,14 | R$ 12.095,20 |
| Laje treliçada da cobertura h12 | 106059 | 65,20 m² | R$ 207,51 | R$ 13.529,65 |
| Piso sobre solo 10 cm | 103076 | 65,20 m² | R$ 150,49 | R$ 9.811,95 |
| Pilares 19×19 de concreto (8) | 92762 · 92269 · 92413 · 103669 | 0,808 m³; fôrma 17,04 m²; aço 105,04 kg | composto | R$ 6.482,91 |
| **Total** | | | | **R$ 56.269,11** |

O custo por m² construído é de R$ 863,02/m², considerando só alvenaria, lajes e pilares. Não inclui revestimento, esquadrias, cobertura em telha, fundação nem instalações.

## 6. Módulo de IA

- **Custo idêntico em todas as execuções:** o preço vem da tabela SINAPI, a quantidade vem do modelo e a multiplicação é feita em Python (versao_schema 2). Os mesmos códigos SINAPI foram escolhidos em 100% das execuções.
- **O texto da IA varia:**
  - a memória de cálculo teve de 682 a 1.471 caracteres por grupo;
  - as suposições foram de 3 a 6 por grupo.
  - Essa variação não afeta o número.
- **Qualidade das justificativas:** as justificativas citam corretamente a descrição oficial de cada composição (por exemplo, 106059 "LT = 12 cm (8+4)" e 103076 "espessura de 10 cm, fck 30 MPa"). As suposições registram as decisões implícitas: seção quadrada do pilar, fck e fôrma de madeira.
- **Tempo e custo:** 27,6 s por análise de 5 grupos. São 6.163 tokens de entrada e cerca de 3.100 de saída, aproximadamente US$ 0,024 por análise, pelo preço público do Claude Haiku 4.5 no Bedrock (perfil us, US$ 1,10 e US$ 5,50 por milhão de tokens).

## 7. Modo mercado (IA sem tabela) × SINAPI

| Categoria | SINAPI (NeuralBIM) | Mercado: mín – provável – máx | Desvio do provável |
|---|---|---|---|
| Parede | R$ 26.444,60 | R$ 8.950,60 – R$ 12.714,45 – R$ 17.130,10 | −51,9% |
| Laje | R$ 23.341,60 | R$ 11.084,00 – R$ 15.648,00 – R$ 20.864,00 | −33,0% |
| Pilar | R$ 6.482,91 | R$ 969,60 – R$ 1.292,80 – R$ 1.777,60 | −80,1% |
| **Total** | **R$ 56.269,11** | R$ 21.004,20 – R$ 29.655,25 – R$ 39.771,70 | **−47,3%** |

- **A faixa não contém o valor oficial:** mesmo o valor máximo da faixa de mercado (R$ 39.771,70) fica 29% abaixo do SINAPI.
- **O caso mais extremo é o pilar:** a IA estimou R$ 1.600/m³, enquanto o custo SINAPI equivalente do pilar, com fôrma e aço, é de cerca de R$ 8.023/m³.
- **Instabilidade entre dias:** dentro da mesma sessão, as 3 execuções deram o mesmo valor. Entre 26/10 e 28/10, porém, o provável passou de R$ 26.721,25 para R$ 29.655,25 (+11%) com o mesmo modelo, porque o piso sobre solo foi de R$ 75 para R$ 120/m².
- **Leitura para o TCC:** sem uma tabela de referência, a IA subestima o custo e não é estável ao longo do tempo. Isso reforça a decisão de basear o preço no SINAPI (recuperação de dados + cálculo determinístico).

## 8. Testes do painel (servidor real)

| Página | Teste | Resultado |
|---|---|---|
| Início | KPIs × API | Custo R$ 56.269,11, 20 elementos em 5 grupos, contador de análises 39 / 138 chamadas: OK |
| Estimativa | faixa oficial, tabela, rodapé, histórico | Oficial congelada 28/10 20:44; soma dos grupos = total; 0 sem preço, 0 falhas: OK |
| Fornecedores | cadastro pelo formulário (preço "175,00") | gravado 175,00: OK |
| Fornecedores | 7 cadastros via API (todas as categorias, componente de pilar, unidade divergente) | comparação com o SINAPI correta; "unidade divergente" sinalizada; desvio médio −1,1% e cobertura 6/8 conferidos à mão: OK |
| Fornecedores | excluir | OK (o registro de teste antigo "xxx" foi removido; cópia de segurança guardada) |
| Controle de obra | valores "1.500,00", "2500" e "12abc" | 1.500 e 2.500 gravados; "12abc" recusado; desvio por categoria (−94,3%) correto; registros de teste excluídos: OK* |
| Mercado | KPIs e tabela por categoria × arquivo | OK |

\* **Cache do navegador:** na primeira tentativa, o navegador ainda usava a página antiga (de antes da correção de 26/10) e gravou "1.500,00" como 1,50. O servidor já tinha a versão corrigida. Num navegador que abriu o painel antes de 26/10, aperte **Ctrl+F5** uma vez. Uma solução definitiva seria enviar as páginas com cabeçalho `Cache-Control: no-cache` em `main.py`, o que exige reiniciar a API.

**Detalhe visual:** em Início, a barra de progresso mostra "0.0%" com ponto decimal, em vez de "0,0%".

**Fornecedores cadastrados:** são 8, todos com "(fictício – teste)" no nome. Servem para demonstrar a função, **não são cotações reais**. Antes da banca, substitua por cotações reais de Guarapuava ou apresente-os como dados ilustrativos.

## 9. O que falta (depende de você)

1. **Levantamento manual cronometrado** (seção 4 do protocolo), sem abrir o painel. Atenção: o NeuralBIM já rodou neste modelo antes do levantamento manual, o que inverte a ordem prevista no protocolo. Isso precisa entrar como limitação ("exposição prévia aos resultados", seção 7). Não abra este relatório antes de fazer o levantamento manual, se ainda der.
2. **Cronometrar o NeuralBIM por você:** do clique em Enviar Dados até o total visível no painel. Como referência, os tempos medidos foram de 20 a 49 s no plugin e cerca de 28 s na IA.
3. **Prints da interface para o TCC:** não consegui capturar em resolução boa nesta sessão. Abra o painel no navegador em tela cheia e capture com Win+Shift+S:
   - Início;
   - Estimativa, com a faixa "oficial" e a tabela;
   - um grupo de pilar expandido;
   - Fornecedores, com a tabela de comparação;
   - Mercado;
   - o Revit com a casa em 3D e a planta do TÉRREO.

## 10. Arquivos

Pasta `C:\NeuralBim\validacao_2026-10-28\`:

- **`dados\`:** os 7 lotes do plugin, as estimativas SINAPI e de mercado, `oficial_2026-10-28.json`, `referencia_CasaMCMV_65m2_VALIDACAO_2026-10-28.json`, `comparacao_neuralbim_x_referencia.csv` e `.json`, `execucoes_ia_2026-10-28.json` (tempos e tokens de cada análise), `fornecedores.json` e `log_analises.json`.
- **`figuras\`:**
  - fig01: erro por parede;
  - fig02: custo por categoria, com a faixa de mercado;
  - fig03: repetibilidade;
  - fig04: tempos.
- **`scripts\`:** `comparar_referencia.py` e `figuras.py`, para reproduzir as tabelas e figuras.
- **`backup_antes_dos_testes\`:** fornecedores, gastos, preços confirmados, log e `oficial.json` como estavam antes dos testes.

Novos botões do plugin, na aba NeuralBim:

- **Salvar Copia Validacao** e **Medir Referencia:** aparecem depois de reiniciar o Revit.
- **Atalhos de teclado criados:** NBE (Enviar Dados), NBA (Auditar Materiais), NBP (Preparar Validacao) e ZQ (pyRevit Reload).
