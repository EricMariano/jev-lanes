# Confidence gate on Banking77

Replays recorded Jev answers through the gate policy of `GatedAgent`. Public data (Banking77, PolyAI, CC BY 4.0), routes and held-out intents fixed in `config.py`. **The simulated customer is optimistic; read the limitations before quoting a number.**

## Setup

- Cases: 770 (660 in-scope, 110 held-out with no correct route).
- Cases below confidence 1.0 (could need a question): 327; left out because a clarification call failed or is missing: 0 (the same cases are left out of every policy).
- The agent's question is always: “Could you tell me a bit more about what you need?”
- The simulated reply is another Banking77 train message of the same intent, so it restates the problem in new words instead of answering the question. Jev then classifies the whole conversation (customer and assistant turns).
- Questions are limited to 2 per case; a case still below the threshold is declined.
- Primary threshold, frozen in `config.py` before any clarification call: 0.995.
- A harmful act is an action on the wrong route, or any action on a held-out message.

## Primary comparison at threshold 0.995

| Policy | Served correctly | Harmful acts (wrong route + unsupported) | Declined in-scope | Declined held-out | Customers asked | Questions asked |
|---|---|---|---|---|---|---|
| always act | 608 | 162 (52 + 110) | 0 | 0 | 0 (0.0%) | 0 |
| gate, no questions | 418 | 25 (4 + 21) | 238 | 89 | 0 (0.0%) | 0 |
| gate + 1 question | 485 | 35 (4 + 31) | 171 | 79 | 327 (42.5%) | 327 |
| gate + 2 questions | 501 | 41 (4 + 37) | 155 | 73 | 327 (42.5%) | 577 |

“Served correctly” counts in-scope messages whose classified route is the right one. Declining a held-out message is the right outcome; declining an in-scope one is a customer who was not served.

### What the questions bought

- With 1 question: 77 cases were acted on only after being asked; 87.0% (67/77; 95% CI 77.7–92.8%) of those were the right action (+67 served correctly, +10 harmful acts, 327 questions in total).
- With 2 questions: 99 cases were acted on only after being asked; 83.8% (83/99; 95% CI 75.3–89.8%) of those were the right action (+83 served correctly, +16 harmful acts, 577 questions in total).
- For comparison, the first-pass acts (no question needed): 94.4% (418/443; 95% CI 91.8–96.1%) right.
- Of the 99 cases acted on after questions: 83 right, 0 on the wrong route, 16 on held-out messages (nothing correct to do).

### Is asking better than lowering the threshold?

*Added after the first replay, as a control; not part of the frozen design.* A plain gate can also serve more customers by lowering its threshold, at the price of more harmful acts. For each gate that asks (2 questions), the table gives the plain gate with the highest served count whose harmful acts do not exceed it. Intervals come from resampling cases (2000 draws) with both policies fixed beforehand.

| Asking gate (threshold, 2 q) | Served / harm | Plain gate at the same harm budget (threshold) | Served / harm | Δ served (95% CI) | Δ harm (95% CI) |
|---|---|---|---|---|---|
| 0.5 | 608 / 160 | 0.37 | 608 / 154 | +0 (-5 to +5) | +6 (-1 to +13) |
| 0.6 | 613 / 147 | 0.47 | 605 / 139 | +8 (+1 to +16) | +8 (-3 to +20) |
| 0.7 | 614 / 122 | 0.57 | 593 / 117 | +21 (+11 to +31) | +5 (-6 to +17) |
| 0.8 | 607 / 109 | 0.6 | 588 / 106 | +19 (+8 to +30) | +3 (-9 to +15) |
| 0.9 | 594 / 80 | 0.73 | 575 / 80 | +19 (+6 to +32) | +0 (-12 to +12) |
| 0.95 | 582 / 67 | 0.85 | 558 / 64 | +24 (+10 to +39) | +3 (-8 to +13) |
| 0.98 | 541 / 53 | 0.93 | 530 / 51 | +11 (-3 to +25) | +2 (-6 to +10) |
| 0.995 (primary) | 501 / 41 | 0.97 | 492 / 38 | +9 (-8 to +26) | +3 (-4 to +11) |
| 1.0 | 501 / 41 | 0.97 | 492 / 38 | +9 (-8 to +26) | +3 (-4 to +11) |

## Sweep over thresholds (descriptive, not used for selection)

For each threshold: served correctly / harmful acts. The gate only helps if asking moves a row toward more served at the same or fewer harmful acts.

| Threshold | No questions | 1 question | 2 questions | Customers asked (2 q) |
|---|---|---|---|---|
| 0.5 | 599 / 134 | 607 / 156 | 608 / 160 | 37 |
| 0.6 | 588 / 106 | 609 / 141 | 613 / 147 | 76 |
| 0.7 | 578 / 89 | 606 / 116 | 614 / 122 | 103 |
| 0.8 | 567 / 73 | 598 / 105 | 607 / 109 | 130 |
| 0.9 | 542 / 55 | 581 / 75 | 594 / 80 | 173 |
| 0.95 | 517 / 49 | 564 / 64 | 582 / 67 | 204 |
| 0.98 | 473 / 33 | 531 / 50 | 541 / 53 | 264 |
| 0.995 | 418 / 25 | 485 / 35 | 501 / 41 | 327 |
| 1.0 | 418 / 25 | 485 / 35 | 501 / 41 | 327 |

Always act: 608 served correctly / 162 harmful acts.

## Limitations

- **The customer is simulated and helpful.** Real replies to a question may add nothing, go off topic or not come at all; here every reply is a fluent message of the right intent. Treat the gain as an upper bound.
- **Part of the gain may be a second look, not a better question.** Jev sees one more message of the same intent; no control separates the value of asking from the value of more text.
- **Only the gate is evaluated.** The agent's language model (which tool it proposes, its question wording, its use of the answer) is not in the loop, and no tool runs.
- One dataset, English only, one run, one simulated reply per case and round, no repeated draws.
- Held-out messages stand for requests the desk cannot serve; their share (14%) is a design choice.
- Banking77 labels are ambiguous in places; a “wrong route” may be a defensible one.
- Confidence is a distribution statistic, not an accuracy guarantee.

