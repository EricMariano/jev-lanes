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
