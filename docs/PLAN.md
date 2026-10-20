# Plano de implementação

## Etapa atual — Fundação

- [x] Estrutura Python empacotável, licença MIT e Git local.
- [x] Seleção pura de faixa com limiares explícitos.
- [x] Testes offline para limites e entradas inválidas.
- [x] Configuração de lint, formatação e CI para Python 3.10–3.14.
- [x] ADRs, glossário e registro de questões em aberto.

O workflow está configurado; sua execução no GitHub depende de um repositório remoto.

Verificação local inicial em 2026-10-19: 30 testes passaram em Python 3.10.22 e
3.14.4, sem chamadas externas durante os testes. Ruff (lint e formatação), exemplo
de política e build de wheel/sdist passaram. A instalação de ferramentas e
dependências usou rede. Python 3.11–3.13 está na matriz de CI, ainda sem execução local.

## Próxima etapa — Contratos do MVP

- [ ] Fechar as questões restantes do [registro de decisões](DECISIONS.md).
- [x] Rastro auditável serializável (`RouteTrace`, `Evaluation`) com validação das sequências.
- [ ] Definir estado e identidade do roteador (esquema exato da chave de estado).
- [x] Interfaces injetáveis para classificador e fallback (`Classifier`, `FallbackModel`).
- [x] Fakes determinísticos sem rede (`FakeJevClassifier`, `FakeFallback`).
- [x] Confirmar versões e API oficial (ver DECISIONS); reconferir antes de fixar versões.
- [ ] Implementações padrão BYOK: classificador TypeSafe e fallback com chat model LangChain.

Módulos existentes e previstos:

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
- [ ] Verificar os adaptadores contra os serviços reais (teste opt-in, fora da suíte padrão).
- [x] Três faixas com validação de rotas e abstenção/escalada do fallback.
- [x] Nós separados para classificação e interrupção humana.
- [x] Persistir decisão antes da escalada e registrar `route_trace`.
- [x] Provar em teste que retomar o nó humano não chama Jev novamente.
- [x] Testar resposta inválida, falhas de provedor e isolamento de estado.
- [x] `FakeJevClassifier` e testes de integração offline com LangGraph real.
- [ ] Exemplo de atendimento com checkpointer e retomada humana.
- [ ] Notebook executável de cinco minutos.
- [ ] README com diagrama, instalação e exemplo mínimo que realmente funcionem.
- [ ] Comparação manual versus `attach()` sobre comportamentos equivalentes.
- [ ] Avaliação rotulada separada de testes mecânicos e claims de desempenho.
- [ ] Preparar publicação PyPI após fechar nome e metadados.

## v0.2 — Extensões candidatas

- Margem entre top1 e top2; guardrail `Noul` no mesmo request.
- Política própria para `Score`, considerando a ordem dos níveis.
- Execução async e tags de faixa no LangSmith.

## v0.3 — Calibração e métricas

- `Lanes.from_calibration(dataset)` com objetivo e protocolo de avaliação definidos.
- Proporção por faixa, taxa de escalada e estimativas documentadas de custo.
- Separar ajuste dos limiares e avaliação final para evitar resultados otimistas.
