---
status: accepted
date: 2026-10-19
---

# Separar classificação e interrupção humana

No adaptador LangGraph, a classificação e a gravação de sua decisão ocorrerão
antes de um nó dedicado à revisão humana. O nó que chama `interrupt()` reinicia
na retomada; chamar o Jev nesse mesmo nó repetiria a classificação nesse fluxo.
A separação evita essa repetição causada pela retomada humana e mantém disponível
a decisão anterior. Não é uma garantia de execução exatamente uma vez diante de
falhas, retries ou replay. A função de arestas condicionais apenas selecionará
destinos e não solicitará revisão humana. O exemplo completo deverá mostrar
checkpointer, `thread_id` e retomada explicitamente.
