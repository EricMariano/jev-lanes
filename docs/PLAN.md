# Plano de implementação

## Estado atual — Candidata v0.1 (`0.1.0rc1`)

Atualizado em 2026-10-23. A implementação do fluxo está concluída e foi avaliada
uma vez em dados públicos (Banking77). A avaliação em dados reais do domínio e a
publicação no PyPI são etapas externas ainda pendentes; o pacote
continua experimental, com limiares ilustrativos.

## Fundação

- [x] Estrutura Python empacotável, licença MIT e Git local.
- [x] Seleção pura de faixa com limiares explícitos.
- [x] Testes offline para limites e entradas inválidas.
- [x] Configuração de lint, formatação e CI para Python 3.10–3.14.
- [x] ADRs, glossário e registro de questões em aberto.

O repositório remoto é `EricMariano/jev-lanes`. O CI da base passou no GitHub em
2026-10-20; as novas verificações precisam passar no commit da candidata.

Verificação local inicial em 2026-10-19: 30 testes passaram em Python 3.10.22 e
3.14.4, sem chamadas externas durante os testes. Ruff (lint e formatação), exemplo
de política e build de wheel/sdist passaram. A instalação de ferramentas e
dependências usou rede.

Verificação da candidata em 2026-10-20: 132 testes passaram em Python 3.10.22,
3.11.14, 3.12.15, 3.13.16 e 3.14.4; os quatro testes live foram pulados intencionalmente.
As demos e o notebook executaram sem provedores reais. Ruff e validação estrita das
distribuições passaram; o wheel também foi instalado em ambiente limpo, com execução
das quatro demos offline fora do checkout. Instalação de ferramentas e dependências
usou rede; a validação não repetiu as chamadas pagas da bateria histórica.

## Contratos do MVP

- [x] Fechar contratos necessários ao MVP; extensões estão separadas em DECISIONS.md.
- [x] Rastro auditável serializável (`RouteTrace`, `Evaluation`) com validação das sequências.
- [x] Estado e identidade: `<name>_route`, sem reducer, substituído a cada episódio.
- [x] Interfaces injetáveis para classificador e fallback (`Classifier`, `FallbackModel`).
- [x] Fakes determinísticos sem rede (`FakeJevClassifier`, `FakeFallback`).
- [x] Confirmar versões e API oficial (ver DECISIONS); reconferir antes de fixar versões.
- [x] Implementações padrão BYOK: classificador TypeSafe e fallback com chat model LangChain.

Módulos existentes:

```text
src/jev_lanes/
  lanes.py      # existente: limites e seleção de faixa
  trace.py      # existente: rastro de decisão serializável
  protocols.py  # existente: Classification, Classifier, FallbackModel
  testing.py    # existente: FakeJevClassifier, FakeFallback
  router.py     # existente: JevRouter, nós classify/llm/human e attach(builder, after=...)
  adapters.py   # existente: JevClassifier (TypeSafe) e LangChainFallback (BYOK)
```

Os nós ficaram em `router.py` (não em `nodes.py`): são métodos do `JevRouter` e só fazem
sentido ligados à sua configuração.

## v0.1 — Fluxo completo

- [x] Classificador TypeSafe (`Choice` com `routes` como critérios) e fallback LangChain
  (`jev_lanes.adapters`), testados offline com fakes.
- [x] Teste opt-in contra os serviços reais (`tests/live/`, `JEV_RUN_LIVE=1`): 4 testes
  passaram em 2026-10-20 com TypeSafe e `gpt-5-nano`, em casos inequívocos.
- [x] Três faixas com validação de rotas e abstenção/escalada do fallback.
- [x] Nós separados para classificação e interrupção humana.
- [x] Persistir decisão antes da escalada e registrar `route_trace`.
- [x] Provar em teste que retomar o nó humano não chama Jev novamente.
- [x] Testar resposta inválida, falhas de provedor e isolamento de estado.
- [x] `FakeJevClassifier` e testes de integração offline com LangGraph real.
- [x] Exemplo de atendimento com checkpointer, resposta inválida e retomada humana.
- [x] Notebook de cinco minutos, executor e job de CI próprios, sem chamadas externas.
- [x] README com diagrama, instalação local e exemplos executáveis.
- [x] Comparação manual versus `attach()`: 18 cenários de comportamento equivalente.
- [x] Bateria sintética rotulada registrada separadamente dos testes mecânicos, sem
  claims de desempenho; protocolo de avaliação real em `benchmarks/README.md`.
- [x] Preparar candidata: versão/metadados, changelog, lockfile e workflow de publicação
  por Trusted Publishing, com instruções em `docs/RELEASE.md`.

## Avaliação no Banking77 (2026-10-20)

- [x] Protocolo aplicado a dados públicos: 231 casos de calibração, 770 de teste, regra de
  seleção congelada antes da execução, relatório reprodutível (`benchmarks/banking77/`).
- [x] Atribuição CC BY 4.0 dos dados e das amostras redistribuídas.
- [x] Resultado: o alvo de 95% de acerto automático não foi atingido; Jev + humano
  automatizou 57,5% a 94,4%, três faixas 77,4% a 90,6%.
- [x] O fallback não ajudou: na faixa `llm`, 0 corrigidos e 2 piorados em 30 casos; abaixo
  do limiar `auto`, 12 corrigidos e 16 piorados (p = 0,57). Não é evidência de dano
  significativo, nem de benefício. Posição adotada: o fallback é uma opção não comprovada
  e a documentação diz isso (README, DECISIONS).

## Pendências externas para publicação e validação de qualidade

- [ ] Confirmar o nome no momento da publicação e configurar o Trusted Publisher na
  conta PyPI, com o ambiente `pypi` protegido no GitHub.
- [ ] Publicar a versão revisada após CI verde, tag e aprovação do mantenedor.
- [ ] Obter mensagens reais anonimizadas e rótulos independentes do domínio de uso, definir
  o objetivo operacional, separar calibração/teste e medir
  acerto/cobertura/custo/latência.

Não há dados reais do domínio de uso neste repositório. Os 37 casos sintéticos mostram
funcionamento; o Banking77 dá uma medida em dados públicos de outro domínio, sem
comprovar benefício do fallback.

## v0.2 — Extensões candidatas

- Fallback opcional (política Jev + humano, sem modelo de reserva): é a configuração que
  atingiu a melhor precisão automática no Banking77. Exige permitir `("jev", "human")`
  no rastro da faixa `llm`.
- Teste do fallback com outros modelos e prompts, e com repetições, antes de recomendá-lo.
- Tratamento de mensagens fora do escopo (rota `other`, rejeição de classe) — o Jev roteou
  automaticamente 40 de 110 no teste.
- Margem entre top1 e top2; guardrail `Noul` no mesmo request.
- Política própria para `Score`, considerando a ordem dos níveis.
- Execução async e tags de faixa no LangSmith.

## v0.3 — Calibração e métricas

- `Lanes.from_calibration(dataset)` com objetivo e protocolo de avaliação definidos.
- Proporção por faixa, taxa de escalada e estimativas documentadas de custo.
- Separar ajuste dos limiares e avaliação final para evitar resultados otimistas.
