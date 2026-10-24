# Avaliação — planejamento

Testes unitários comprovam a mecânica do gate, não a qualidade das decisões nem a
calibração das confianças mínimas. Há três avaliações registradas, todas com limites claros:

- **Gate de confiança no Banking77** ([banking77/README.md](banking77/README.md),
  [relatório](results/banking77/gate-report.md)): repete as respostas gravadas do Jev pela
  política do `GatedAgent` (agir, perguntar ao cliente ou recusar). Usa um **cliente
  simulado** que favorece a pergunta, então os ganhos são um limite superior. O limiar
  principal foi fixado antes da execução; a comparação com "apenas baixar o limiar" foi
  acrescentada depois de ver os primeiros números.
- **Banking77, desenho antigo de três faixas** (arquivado,
  [relatório](results/banking77/report.md)): dados públicos em inglês, rótulos dos autores
  do dataset, limiares escolhidos numa amostra de calibração e avaliados uma vez em 770
  casos de teste. Os scripts `banking77/run.py` e `smoke_battery.py` exigem o commit
  `8d07291`; os resultados gravados continuam válidos. É uma avaliação em dados públicos de
  outro domínio, não em mensagens reais do usuário do pacote.
- **Bateria de fumaça** (arquivada, abaixo): 37 casos sintéticos, só para ver o comportamento.

### O que o gate mostrou (uma execução, cliente simulado)

- No limiar 0,995: agir sempre dá 608 atendimentos corretos e 162 atos nocivos; o gate sem
  perguntas, 418 e 25; o gate com até duas perguntas, 501 e 41.
- Perguntar recupera 83 dos 238 clientes bloqueados, sem nenhum na rota errada; os 16 atos
  nocivos a mais são mensagens fora do escopo, que o Jev empurra para uma das quatro rotas
  por não haver rota "outros".
- Contra um gate simples com o mesmo orçamento de atos nocivos, o ganho no limiar principal
  é de +9 atendidos (IC 95%: −8 a +26), indistinguível de zero; entre 0,7 e 0,95 fica em
  +19 a +24 (cerca de 2,5–3% dos clientes).
- Não medido: o modelo de linguagem do agente, clientes reais, outros idiomas e domínios.

### O que o desenho antigo de três faixas mostrou (uma execução, `gpt-5-nano`)

- O alvo de ≥ 95% de acerto automático **não foi atingido** na calibração, com ou sem
  fallback. No teste, três faixas (auto ≥ 0,95, llm ≥ 0,9) automatizaram 77,4% dos casos
  com 90,6% de acerto; Jev + humano (auto ≥ 0,995) automatizou 57,5% com 94,4%.
- A confiança do Jev separa acertos de erros de forma útil, mas imperfeita (AUROC 0,884
  entre casos do escopo; 0,818 contra mensagens fora do escopo).
- **O fallback não ajudou onde foi consultado.** Na faixa `llm` do teste (30 casos do
  escopo) o Jev acertou 25 e o fallback 23: corrigiu 0 e piorou 2. Em todos os casos
  abaixo do limiar `auto` (134), o fallback corrigiu 12 respostas do Jev e piorou 16
  (teste do sinal, p = 0,57). Não há evidência de que melhore a decisão, nem de que a
  piore de forma significativa; as amostras são pequenas.
- Mensagens fora do escopo continuam sendo roteadas automaticamente quando o Jev está
  confiante (40 de 110 com três faixas).

Estes números valem para este dataset, estas rotas e estes modelos. Não os cite como
desempenho esperado em outro domínio.

Existe uma **bateria de fumaça**, que não é benchmark: `smoke_battery.py` roda 37 casos
sintéticos rotulados pelos mantenedores contra os serviços reais (com as suas chaves) e
`make_report.py` gera o relatório em Markdown. O primeiro resultado está em
[results/2026-10-20-battery.md](results/2026-10-20-battery.md). Serve para ver como as
peças se comportam, não para estimar acerto.

Antes de divulgar resultados:

- Construir uma amostra rotulada com casos claros, ambíguos e fora do escopo.
- Separar dados usados para escolher limiares dos dados de avaliação final.
- Comparar Jev sozinho, LLM sozinho e política com escalada, com versões fixadas.
- Medir acerto entre casos automáticos e cobertura da automação, além do acerto global.
- Registrar proporção por faixa, escaladas adicionais, latência e custo observado.
- Declarar como decisões humanas são obtidas e contabilizadas.
- Publicar tamanho da amostra, limitações e condições de reprodução.

Concordância entre modelos não substitui comparação com rótulos independentes.

## Protocolo para a avaliação real

Os dados reais do domínio do usuário não estão neste repositório. O Banking77 aplicou
este protocolo a um dataset público; não substituir a avaliação no seu domínio por ele,
nem por mais casos sintéticos, e não usar os resultados registrados para escolher
limiares de produção.

1. Definir rotas, critérios de desempate e quando a resposta correta é pedir
   esclarecimento ou revisão humana. A rota `other` não significa automaticamente
   incerteza: na bateria, entradas vagas receberam essa rota com confiança 1.0.
2. Reunir mensagens reais anonimizadas e registrar origem, período, critérios de
   inclusão e distribuição por categoria. Evitar mensagens do mesmo incidente em
   splits diferentes. Guardar dados privados fora do Git.
3. Pedir rótulos a pessoas que não viram as respostas dos modelos. Registrar o conjunto
   de rotas aceitáveis, os casos que exigem revisão e como divergências foram resolvidas.
4. Separar calibração e teste antes de ajustar os limiares. Escolher na calibração o
   par de limiares que atende ao erro automático tolerável e à capacidade de revisão;
   congelar rotas, prompts, modelos, versões e limiares antes de abrir o teste.
5. No mesmo split de teste, comparar Jev sozinho, LLM sozinho e política de três faixas.
   Registrar chamadas dos dois provedores para os baselines, mas contabilizar como
   custo da política apenas as chamadas que ela faria. Repetir execuções e declarar
   o número de repetições; não escolher apenas a melhor execução.
6. Reportar acertos/total de decisões automáticas, cobertura automática/total de casos,
   erros automáticos e seus exemplos anonimizados, proporção por faixa, abstenções,
   rotas inválidas e falhas de provedor. Falha de serviço é erro operacional; não
   contar como revisão humana. Se nenhuma decisão for automática, o acerto seletivo
   é indefinido, e não 100%.
7. Contabilizar casos rotulados como "requer revisão" separadamente: automatizá-los
   deve aparecer como falha da política de escalada, mesmo que a rota pareça defensável.
   Decisões humanas só entram no acerto final se tiverem sido efetivamente coletadas e
   avaliadas; não presumir que uma pessoa acerta todos os casos escalados.
8. Medir latência fim a fim e por provedor, incluindo mediana e p95, e custo observado
   com moeda, preços/data e contagem de tokens ou faturas. Separar tempo de espera
   humana. Publicar denominadores, tamanho da amostra e incerteza das estimativas.

Um resultado reproduzível deve acompanhar manifesto do dataset (sem dados sensíveis),
IDs/splits, processo de rotulagem, configuração congelada, lockfile/commit e respostas
brutas redigidas dos provedores. O esquema da bateria sintética pode servir de ponto
de partida, mas seu `accept` vazio significa "sem rota correta" e não deve desaparecer
dos indicadores de escalada. As tabelas históricas usam rótulos permissivos escritos
pelos mantenedores e não substituem esse protocolo.
