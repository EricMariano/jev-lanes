# Decisões do projeto

Registro iniciado em **19 de outubro de 2026**. Diferenciar decisões aceitas,
hipóteses de produto e questões em aberto; uma API proposta não é compromisso de implementação.

## Decisões aceitas

- A contribuição central é a **política de decisão e escalada**, confirmada pelo autor;
  `attach()` será uma conveniência para aplicar essa política.
- Python 3.10+, type hints, layout `src/`, uv, Ruff, pytest e licença MIT.
- O MVP será síncrono e usará `Choice`, três faixas e testes sem rede.
- O núcleo da política será independente do provedor e do executor do grafo.
- Limiares serão explícitos; `0.85` e `0.60` são exemplos provisórios, sem calibração.
- Limites: `0 <= llm < auto <= 1`; igualdade seleciona a faixa superior.
  `llm=0` é permitido e torna a faixa humana inicial vazia.
- Confiança inválida gera erro; indisponibilidade de serviço não vira confiança zero.
- Classificação e interrupção humana devem ocorrer em nós distintos.
- Abstenção ou rota inválida do modelo de reserva escala diretamente para revisão
  humana, sem nova tentativa no MVP.
- Falhas de provedor (timeout, indisponibilidade, credencial ausente) propagam o erro;
  não são convertidas em revisão humana nem em confiança baixa.
- Na revisão humana, a pessoa escolhe uma das rotas válidas do `Choice`; a decisão é
  validada como as demais. Revisão humana não é uma rota de atendimento.
- `route_trace` é uma lista serializável de avaliações (avaliador jev/llm/human, rota
  sugerida, confiança quando for do Jev, faixa de entrada e motivo de escalada) mais a
  rota final. Não persiste o texto do caso nem payloads brutos dos provedores.
- O projeto será open source e a v0.1 deve ser **plug and play com BYOK**: o usuário
  instala o pacote, define suas próprias chaves no ambiente e usa o fluxo completo, sem
  escrever adaptadores. O projeto não guarda nem repassa chaves.
- Classificador e modelo de reserva são injetados por `Protocol`s mínimos definidos no
  núcleo, com implementações padrão incluídas: `TypeSafeClassifier` (via
  `langchain-typesafe`, chave `TYPESAFE_API_KEY`) e qualquer chat model LangChain para o
  fallback (instância de `BaseChatModel` ou string de `init_chat_model`; a chave é a do
  provedor escolhido). Os Protocols permitem trocar qualquer um deles.
- `pip install jev-lanes` traz `langgraph` e `langchain-typesafe` por padrão; os provedores
  de LLM (`langchain-openai` etc.) ficam a cargo do usuário. `jev_lanes.lanes` continua
  importável e testável sem rede nem chaves.
- Payload: por padrão o adaptador envia as `messages` do estado (chave configurável);
  `extract(state)` opcional permite restringir ou redigir o que sai do ambiente. A
  documentação deve dizer que o texto é enviado ao TypeSafe e ao provedor do fallback.
- A rota escolhida na revisão humana é validada com `response_schema` do `interrupt()`;
  o piso de `langgraph` é 1.2.12. O schema é `Literal` das rotas do roteador e a retomada
  é `Command(resume="<rota>")`. Verificado no código do `langgraph` 1.2.16: uma rota
  desconhecida levanta `pydantic.ValidationError` sem salvar nada, e o `interrupt` pode
  ser respondido de novo.
- Implementado em `adapters.py`: `JevClassifier` envia um `Choice` com as rotas como
  critérios via `TypeSafeClassifier` (chave `TYPESAFE_API_KEY`; ausência falha na
  construção) e `LangChainFallback` aceita `BaseChatModel` ou string de `init_chat_model`.
  O fallback responde em texto livre com o nome da rota ou `ABSTAIN`; a resposta é
  interpretada de forma tolerante (aspas, caixa, ponto final) e qualquer texto que não
  seja rota, truncado, escala para revisão humana. Texto livre foi preferido a saída
  estruturada porque funciona com qualquer chat model, sem exigir tool calling.
  `ABSTAIN` é nome reservado de rota. Dependências diretas: `langgraph>=1.2.12`,
  `langchain>=1.3.15`, `langchain-core>=1.6.2` e `langchain-typesafe>=0.0.1a3,<0.1`.
- Implementado em `router.py`: um `JevRouter` por `name`, chave de estado
  `<name>_route` com `RouteTrace.to_dict()`, nós `<name>_classify`, `<name>_llm` e
  `<name>_human`, e `attach(builder, after=..., targets=...)`. Cada invocação inicia um
  novo episódio. A classificação que devolve rota fora de `routes` é erro de execução,
  não incerteza. O valor da interrupção traz as sugestões, nunca o texto do caso.
- Cada `JevRouter` tem um `name` e guarda decisão e rastro em uma única chave de estado
  serializável derivada desse nome; nós e destinos usam o mesmo prefixo, permitindo
  vários roteadores no mesmo grafo.
- Nome de trabalho: **jev-lanes**, import `jev_lanes`. O diretório local permanece `langgraph-jev`.
- README e código em inglês para colaboração pública; decisões iniciais em português.
- O repositório está no GitHub em `EricMariano/jev-lanes`. A candidata local é
  `0.1.0rc1`; ainda não publicada no PyPI. O workflow `release.yml` publica por OIDC
  quando uma GitHub Release é publicada e o job do ambiente `pypi` é aprovado,
  após configurar as proteções e o Trusted Publisher; ver RELEASE.md.

## ADRs

- [0001 — Política como núcleo do projeto](adr/0001-policy-as-core.md)
- [0002 — Separar classificação e interrupção](adr/0002-resumable-human-review.md)
- [0003 — Separar política de integrações](adr/0003-policy-and-adapters.md)

## Descoberta de nome e trabalhos relacionados

Em 2026-10-19, `langgraph-jev-router` já existia no PyPI com escopo relacionado
(Jev à frente de um roteador existente). Portanto, a alegação ampla de ausência
de integração Jev/StateGraph não deve ser usada na apresentação do projeto.
Precisamos comparar os comportamentos antes de afirmar diferenciais exclusivos.

Consultas HTTPS verificadas aos endpoints públicos:

- `https://pypi.org/pypi/langgraph-jev-router/json`: HTTP 200.
- `https://pypi.org/pypi/jev-lanes/json`: HTTP 404.
- `https://pypi.org/pypi/confroute/json`: HTTP 404.

HTTP 404 indica ausência de projeto público naquele momento, não reserva do nome.

## Resultado da avaliação no Banking77 e posição sobre o fallback (2026-10-23)

Primeira avaliação com rótulos externos (Banking77, 770 casos de teste, `gpt-5-nano`,
limiares escolhidos em 231 casos de calibração; relatório em
`benchmarks/results/banking77/report.md`). Resultados e decisões:

- A confiança do Jev é informativa (AUROC 0,884 entre acertos e erros), mas o alvo de 95%
  de acerto automático não foi atingido na calibração.
- O fallback não melhorou as decisões: na faixa `llm`, o Jev acertou 25 de 30 casos e o
  fallback 23 (0 corrigidos, 2 piorados); abaixo do limiar `auto`, 12 corrigidos e 16
  piorados (teste do sinal, p = 0,57). Uma execução, um modelo, inglês.
- **Decisão:** o projeto mantém as três faixas como contrato, mas apresenta o fallback
  como uma opção **não comprovada**, e não como um benefício. README e relatórios devem
  citar este resultado; nenhum texto deve afirmar que o fallback reduz erros ou custo.
- **Decisão:** não escolher limiares padrão a partir do Banking77; os limiares seguem
  explícitos e específicos do domínio.
- Aberto: tornar o fallback opcional (Jev + humano) é candidato a v0.2; ver PLAN.md.
- Dados: as amostras em `benchmarks/results/banking77/*.jsonl` redistribuem textos do
  dataset sob CC BY 4.0, com atribuição em `benchmarks/banking77/README.md`.

## Hipóteses a avaliar

- Um LLM de reserva melhora as decisões nos casos de confiança intermediária. (No
  Banking77, não: ver acima. Continua sendo uma hipótese para outros domínios e modelos.)
- A política reduz custo ou latência sem ultrapassar o erro aceitável na automação.
- Os limiares iniciais produzem volume de revisão humana operacionalmente viável.

Testes offline validam execução e contratos; não comprovam essas hipóteses.

## Fatos de API confirmados em 2026-10-19

Verificados na documentação oficial e no JSON público do PyPI; reconferir antes de fixar versões.

- `langchain-typesafe` está em **0.0.1a3 (alfa)**, Python `>=3.10`, depende de
  `langchain-core>=1.6.2`. A documentação indica que a API pode mudar; o adaptador
  precisa isolar essa dependência atrás dos Protocols.
- `TypeSafeClassifier().invoke({"state": ..., "questions": {...}})`, com `state` em
  string, JSON ou mensagens LangChain. Resposta: `response.choices[id].choice`,
  `.probabilities` e `.confidence`. A página de documentação não descreve `ainvoke`, mas o
  código de `langchain-typesafe` 0.0.1a3 o implementa; o MVP continua síncrono por escolha. Exige `TYPESAFE_API_KEY`; `TYPESAFE_BASE_URL` é opcional.
- A confiança de `Choice` é `(p_max - 1/n) / (1 - 1/n)`, em `[0, 1]`: depende só da
  maior probabilidade e do número de opções, e não é taxa de acerto. A documentação
  sugere bandas alta/média/baixa e alternativas (`p_max`, razão top1/top2).
- `langgraph` 1.2.16, Python `>=3.10`. `interrupt()` exige checkpointer e `thread_id`
  estável; o nó reinicia do começo na retomada. Efeitos antes do `interrupt()` devem ser
  idempotentes. `response_schema` em `interrupt()` valida a retomada a partir de
  `langgraph>=1.2.12`.

Implicação: o `state` enviado ao TypeSafe sai do ambiente do usuário, então o adaptador
precisa permitir escolher o que é enviado (ver decisões de payload acima).

## Contratos fechados para a candidata v0.1

- Uma resposta do fallback que não é rota é registrada no rastro como `<invalid route>`
  (constante `INVALID_ROUTE`), nunca literalmente: é saída de modelo e pode repetir o
  texto do caso. `attach()` recusa um segundo roteador com o mesmo `name` no mesmo grafo.

- O usuário declara `<name>_route: dict[str, Any]` no estado do grafo, sem reducer.
  A chave recebe `RouteTrace.to_dict()` e é substituída a cada episódio; o histórico
  fica nos snapshots do checkpointer, conforme sua política de retenção. O rastro não
  contém o caso, mas o restante do estado e os checkpoints podem contê-lo.
- `targets` deve mapear exatamente as rotas. Destinos compartilhados e `END` são
  suportados e cobertos pela comparação entre ligação manual e `attach()`.
- Dependências ficam em intervalos limitados por versão principal, com
  `langchain-typesafe>=0.0.1a3,<0.1`. O lockfile fixa o ambiente de desenvolvimento/CI;
  mudanças do provedor devem passar pela suíte offline e por smoke tests opt-in.
- Existem testes reais opt-in em `tests/live/`, bateria sintética separada e demos
  offline completas. O modelo padrão dessas verificações é `openai:gpt-5-nano`;
  o usuário pode escolher outro modelo e instalar seu provedor.

## Questões abertas e extensões posteriores

- Helper para declarar a chave de estado, sem alterar o contrato explícito do MVP.
- Documentar/testar composição com subgrafos e destinos especiais além de `END`
  antes de prometer suporte. Isso não bloqueia o fluxo síncrono atual.
- Execução assíncrona fica fora do MVP.
- Avaliação em dados reais: obter rótulos independentes, ajustar limiares em um split
  e avaliar no outro. A bateria sintética de 37 casos mostrou confiança elevada em
  casos ambíguos; não demonstrou benefício do fallback. O Banking77 aplicou o protocolo a
  dados públicos (ver acima); falta o domínio de uso. Ver `benchmarks/results/`.
- Confirmar identidade do pacote na publicação e configurar o Trusted Publisher
  no PyPI e o ambiente protegido no GitHub. O workflow está preparado, sem upload.

## Fontes consultadas

- [Integração TypeSafe](https://docs.langchain.com/oss/python/integrations/providers/typesafe):
  `invoke` recebe `state` e `questions`; `Choice` retorna escolha, probabilidades e confiança.
- [Confiança](https://docs.typesafe.ai/confidence): a estatística de `Choice` depende
  da maior probabilidade e do número de opções; não interpretar como taxa de acerto.
- [Interrupções](https://docs.langchain.com/oss/python/langgraph/interrupts):
  retomada reexecuta o nó; persistência exige checkpointer e `thread_id` estável.
