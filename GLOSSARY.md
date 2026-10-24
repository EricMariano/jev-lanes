# Ferramentas controladas por confiança

Vocabulário do projeto: um agente só executa uma ferramenta quando a leitura do pedido pelo
classificador é clara o suficiente para aquela ferramenta.

## Linguagem

**Intenção (intent)**:
O que o cliente quer, descrito pelo domínio da aplicação. É o que o classificador escolhe.
_Evitar_: rota, quando se fala de agentes; "rota" é o nome usado no protocolo `Classifier`.

**Confiança (confidence)**:
Estatística que resume a distribuição de probabilidades de uma resposta do Jev.
Não representa uma garantia de acerto no domínio da aplicação.
_Evitar_: acurácia, certeza de acerto.

**Ferramenta controlada (gated tool)**:
Ferramenta do agente acompanhada das intenções que ela atende e da confiança mínima exigida.

**Confiança mínima (min_confidence)**:
Confiança que o classificador precisa atingir (igualdade basta) para a ferramenta rodar.
Ferramentas difíceis de desfazer pedem valores mais altos.

**Verificação (check)**:
Comparação de uma chamada de ferramenta proposta com a classificação. Resulta em `allowed`,
`low_confidence` ou `intent_mismatch` (a intenção classificada não é uma das da ferramenta,
mesmo com confiança alta).

**Passo bloqueado**:
Passo em que ao menos uma chamada proposta não foi permitida. Nenhuma chamada do passo roda.

**Esclarecimento (clarification)**:
Pergunta curta ao cliente depois de um passo bloqueado. O grafo pausa em `interrupt()` e
continua quando recebe a resposta.
_Evitar_: revisão humana; quem responde é o cliente, não um atendente.

**Recusa (refusal)**:
Mensagem fixa que encerra o turno quando as perguntas se esgotam sem confiança suficiente.
Nenhuma ferramenta com efeito colateral rodou.

**Turno (turn)**:
Uma invocação do grafo. Cada invocação começa com um rastro vazio.

**Rastro do gate (gate trace)**:
Registro das verificações e das perguntas de um turno. Nunca guarda texto de mensagens nem
argumentos de ferramentas.

**Ato nocivo (harmful act)**:
Termo da avaliação: executar a ferramenta de uma intenção errada, ou executar qualquer
ferramenta para uma mensagem que o atendimento não cobre.

**Cliente simulado**:
Na avaliação, a resposta à pergunta é outra mensagem do dataset com a mesma intenção. Favorece
a pergunta; os ganhos medidos são um limite superior.
