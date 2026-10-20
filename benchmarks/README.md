# Avaliação — planejamento

Nenhum benchmark foi executado. Testes unitários comprovam a mecânica da política,
não a qualidade das decisões ou a calibração dos limiares.

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

O dataset real ainda não está disponível. Não substituir essa etapa por mais casos
sintéticos nem usar os resultados abaixo para escolher limiares de produção.

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
