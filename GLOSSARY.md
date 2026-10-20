# Política de decisão e escalada

Vocabulário para decisões de roteamento e tratamento explícito da incerteza.

## Linguagem

**Rota (route)**:
Um destino permitido para uma solicitação, descrito pelo domínio da aplicação.

**Confiança (confidence)**:
Estatística que resume a distribuição de probabilidades de uma resposta do Jev.
Não representa uma garantia de acerto no domínio da aplicação.
_Evitar_: acurácia, certeza de acerto.

**Faixa (lane)**:
Intervalo de confiança que determina quem deve decidir: Jev, modelo de reserva ou humano.

**Política de escalada**:
Conjunto de regras que determina quando aceitar uma decisão e quando solicitar outra avaliação.

**Modelo de reserva (fallback LLM)**:
Modelo consultado para uma nova avaliação quando a política não aceita automaticamente a decisão inicial.

**Revisão humana (human review)**:
Etapa na qual uma pessoa recebe o caso para decidir como prosseguir.
_Evitar_: usar como sinônimo de uma rota de atendimento chamada “humano”.

**Rastro de decisão (route trace)**:
Registro das avaliações e da decisão final de um episódio de roteamento.
