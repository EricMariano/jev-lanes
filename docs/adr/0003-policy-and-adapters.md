---
status: accepted
date: 2026-10-19
---

# Separar política de integrações

A seleção de faixa será uma operação pura, independente de LangGraph, chamadas
ao Jev e modelos de reserva. Preferimos essa separação a incorporar todas as
regras nos nós: permite testar os limites sem rede e distinguir erro de execução
de incerteza do modelo. O primeiro adaptador continuará sendo Jev/StateGraph;
esta decisão não amplia o MVP para um framework genérico de provedores.
A distribuição inicial não precisa de dependências de runtime; elas serão
declaradas quando os adaptadores forem implementados.
