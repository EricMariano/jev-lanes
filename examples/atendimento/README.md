# Exemplo de atendimento — planejado

O exemplo completo será implementado com o adaptador LangGraph. Deverá mostrar
rotas de produtos e pedidos, as três faixas, checkpointer e retomada humana com
uma decisão validada. O cenário offline usará `FakeJevClassifier` explicitamente.

Por enquanto, execute `uv run python examples/policy.py` (seleção de faixa) e
`uv run python examples/router_offline.py` (roteador com fakes, checkpointer e retomada
humana) a partir da raiz, sem chamadas externas.
