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
- Nenhuma publicação no GitHub ou PyPI nesta etapa; apenas configuração e Git local.

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

## Hipóteses a avaliar

- Um LLM de reserva melhora as decisões nos casos de confiança intermediária.
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

## Questões abertas antes do adaptador

- Esquema exato da chave de estado: tipos, reducers e histórico entre execuções.
- Reutilização de `attach()` em subgrafos e destinos especiais além de `END`.
- Esquema de estado: o usuário declara `state_key` no schema do grafo; avaliar um helper
  para evitar esse passo manual e definir se o histórico entre episódios é preservado.
- Execução assíncrona (`ainvoke`) fica fora do MVP; o `langchain-typesafe` já implementa
  `ainvoke`, então um adaptador async é viável depois.
- Os adaptadores só foram testados com fakes; falta verificação contra TypeSafe e um
  provedor LLM reais, e confirmar que a resposta em texto livre é confiável na prática.
- Piso e teto de versão de `langchain-typesafe`: a versão mais recente é alfa e pode
  mudar sem aviso; decidir se fixamos um intervalo estreito e como testamos contra ela.
- Plug and play exige chamadas reais a TypeSafe e a um LLM: definir testes de integração
  opt-in (com chaves do mantenedor, fora da suíte padrão) e um modo de demonstração.
- Publicação: repositório remoto, identidade do pacote e trusted publishing no PyPI.

## Fontes consultadas

- [Integração TypeSafe](https://docs.langchain.com/oss/python/integrations/providers/typesafe):
  `invoke` recebe `state` e `questions`; `Choice` retorna escolha, probabilidades e confiança.
- [Confiança](https://docs.typesafe.ai/confidence): a estatística de `Choice` depende
  da maior probabilidade e do número de opções; não interpretar como taxa de acerto.
- [Interrupções](https://docs.langchain.com/oss/python/langgraph/interrupts):
  retomada reexecuta o nó; persistência exige checkpointer e `thread_id` estável.
